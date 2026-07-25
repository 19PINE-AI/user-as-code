#!/usr/bin/env python3
"""Run one memory system on all 1,986 LOCOMO annotations.

Categories 1--4 (1,540 questions) use LOCOMO's category-aware token-F1 and
the paper's binary LLM judge. Category 5 (446 adversarial questions) uses the
official deterministic refusal criterion and is not sent to the LLM judge.

Every output is isolated under ``results/<run-name>/`` and is resumable at the
original ``(conversation, qa_idx)`` identifier. Existing 600-question results
are never read or overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import string
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

from nltk.stem import PorterStemmer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from krill_client import (  # noqa: E402
    KRILL_BASE_URL,
    KRILL_MODEL,
    gemini_cli_user_agent,
    usage_snapshot,
)
from runner_utils import _log, judge_answer  # noqa: E402
from run_locomo_5conv import SYSTEMS, get_sessions  # noqa: E402
from run_locomo10_memmachine import MemMachine  # noqa: E402


DATA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "benchmarks/locomo/data/locomo10.json"
)
RESULTS_ROOT = pathlib.Path(__file__).resolve().parent / "results"
PAPER_SYSTEMS = {
    "uac_v5": SYSTEMS["uac_v5"],
    "full_context": SYSTEMS["full_context"],
    "mem0": SYSTEMS["mem0"],
    "a_mem": SYSTEMS["a_mem"],
    "memmachine": MemMachine,
    "hindsight": SYSTEMS["hindsight"],
    "evermemos": SYSTEMS["evermemos"],
}
_STEMMER = PorterStemmer()


def _normalize_answer(value: str) -> str:
    text = str(value).replace(",", "").lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the|and)\b", " ", text)
    return " ".join(text.split())


def _single_f1(prediction: str, gold: str) -> float:
    pred = [_STEMMER.stem(w) for w in _normalize_answer(prediction).split()]
    truth = [_STEMMER.stem(w) for w in _normalize_answer(gold).split()]
    if not pred or not truth:
        return 0.0
    overlap = sum((Counter(pred) & Counter(truth)).values())
    if not overlap:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(truth)
    return 2 * precision * recall / (precision + recall)


def official_locomo_score(prediction: str, qa: dict) -> float:
    """Match the category-specific scorer in LOCOMO's official repository."""
    category = int(qa["category"])
    if category == 5:
        value = prediction.lower()
        return float(
            "no information available" in value or "not mentioned" in value
        )

    gold = str(qa["answer"])
    if category == 3:
        gold = gold.split(";", 1)[0].strip()
    if category in {2, 3, 4}:
        return _single_f1(prediction, gold)
    if category == 1:
        predictions = [p.strip() for p in prediction.split(",")]
        truths = [g.strip() for g in gold.split(",")]
        if not predictions or not truths:
            return 0.0
        return sum(
            max(_single_f1(candidate, truth) for candidate in predictions)
            for truth in truths
        ) / len(truths)
    raise ValueError(f"Unknown LOCOMO category: {category}")


def _adversarial_prompt(qa: dict, conv_id: str, qa_idx: int) -> tuple[str, dict]:
    """Create stable option ordering for LOCOMO category-5 questions."""
    unavailable = "Not mentioned in the conversation"
    distractor = str(qa["adversarial_answer"])
    digest = hashlib.sha256(f"{conv_id}:{qa_idx}".encode()).digest()
    if digest[0] % 2:
        options = {"a": unavailable, "b": distractor}
    else:
        options = {"a": distractor, "b": unavailable}
    prompt = (
        f"{qa['question']} Select the correct answer and reply with the option "
        f"text: (a) {options['a']} (b) {options['b']}."
    )
    return prompt, options


def _resolve_adversarial_prediction(prediction: str, options: dict) -> str:
    value = prediction.strip()
    lowered = value.lower()
    if re.match(r"^(?:option\s*)?\(?a\)?(?:[.:\s]|$)", lowered):
        return options["a"]
    if re.match(r"^(?:option\s*)?\(?b\)?(?:[.:\s]|$)", lowered):
        return options["b"]
    return value


def _atomic_write(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with open(temp, "w") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
    os.replace(temp, path)


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _selected_qas(
    conv: dict, limit: int | None, qa_index: int | None = None
) -> list[tuple[int, dict]]:
    if qa_index is not None:
        if qa_index < 0 or qa_index >= len(conv["qa"]):
            return []
        return [(qa_index, conv["qa"][qa_index])]
    selected = list(enumerate(conv["qa"]))
    return selected if limit is None else selected[:limit]


def _aggregate(results: dict, expected: int, usage_offset: dict[str, int]) -> None:
    records = [
        record
        for conv_records in results["details"].values()
        for record in conv_records
        if record.get("status") == "ok"
    ]
    standard = [r for r in records if int(r["category"]) in {1, 2, 3, 4}]
    adversarial = [r for r in records if int(r["category"]) == 5]
    judged = [r for r in standard if isinstance(r.get("judge_correct"), bool)]
    by_category = defaultdict(list)
    for record in records:
        by_category[str(record["category"])].append(record)

    results["aggregate"] = {
        "n_expected": expected,
        "n_completed": len(records),
        "coverage": len(records) / expected if expected else 0.0,
        "official_locomo_score": (
            sum(r["official_score"] for r in records) / len(records)
            if records else None
        ),
        "answer_bearing": {
            "n": len(standard),
            "official_token_f1": (
                sum(r["official_score"] for r in standard) / len(standard)
                if standard else None
            ),
            "judge_accuracy": (
                sum(r["judge_correct"] for r in judged) / len(judged)
                if judged else None
            ),
        },
        "adversarial": {
            "n": len(adversarial),
            "refusal_accuracy": (
                sum(r["official_score"] for r in adversarial) / len(adversarial)
                if adversarial else None
            ),
        },
        "per_category": {
            category: {
                "n": len(values),
                "official_score": sum(r["official_score"] for r in values) / len(values),
                "judge_accuracy": (
                    sum(r["judge_correct"] for r in values if isinstance(r.get("judge_correct"), bool))
                    / sum(isinstance(r.get("judge_correct"), bool) for r in values)
                    if any(isinstance(r.get("judge_correct"), bool) for r in values)
                    else None
                ),
            }
            for category, values in sorted(by_category.items())
        },
    }
    current_usage = usage_snapshot()
    results["shared_krill_usage"] = {
        key: int(usage_offset.get(key, 0)) + int(current_usage.get(key, 0))
        for key in set(usage_offset) | set(current_usage)
    }
    results["updated_at"] = datetime.now(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("system", choices=sorted(PAPER_SYSTEMS))
    parser.add_argument("--conv-start", type=int, default=0)
    parser.add_argument("--conv-end", type=int, default=10)
    parser.add_argument("--max-questions-per-conv", type=int)
    parser.add_argument("--max-sessions-per-conv", type=int)
    parser.add_argument("--qa-index", type=int, help="run one original QA index per conversation")
    parser.add_argument("--run-name", default="full_locomo_gpt56_luna")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.run_name):
        parser.error("--run-name may contain only letters, digits, dot, underscore, and hyphen")
    if not DATA_PATH.exists():
        parser.error(f"LOCOMO data not found: {DATA_PATH}; run benchmarks/fetch_benchmarks.sh")
    if not os.environ.get("KRILL_API_KEY"):
        parser.error("KRILL_API_KEY is not set")

    with open(DATA_PATH) as handle:
        all_conversations = json.load(handle)
    conversations = all_conversations[args.conv_start:args.conv_end]
    expected = sum(
        len(_selected_qas(conv, args.max_questions_per_conv, args.qa_index))
        for conv in conversations
    )

    output = RESULTS_ROOT / args.run_name / f"{args.system}.json"
    if output.exists():
        with open(output) as handle:
            results = json.load(handle)
        if results.get("model") != KRILL_MODEL:
            parser.error(
                f"Refusing to resume {output}: it records model "
                f"{results.get('model')!r}, current model is {KRILL_MODEL!r}"
            )
        _log(f"Resuming {output}")
        usage_offset = dict(results.get("shared_krill_usage", {}))
    else:
        usage_offset = {}
        results = {
            "schema_version": 1,
            "benchmark": "LOCOMO",
            "selection": {
                "description": "all 1,986 annotations across all 10 conversations",
                "categories": [1, 2, 3, 4, 5],
                "answer_bearing_questions": 1540,
                "adversarial_questions": 446,
                "conv_start": args.conv_start,
                "conv_end": args.conv_end,
                "max_questions_per_conv": args.max_questions_per_conv,
                "max_sessions_per_conv": args.max_sessions_per_conv,
                "qa_index": args.qa_index,
            },
            "system": args.system,
            "provider": "krill",
            "base_url": KRILL_BASE_URL,
            "model": KRILL_MODEL,
            "user_agent": gemini_cli_user_agent(KRILL_MODEL),
            "dataset": str(
                DATA_PATH.relative_to(pathlib.Path(__file__).resolve().parent.parent)
            ),
            "dataset_sha256": hashlib.sha256(DATA_PATH.read_bytes()).hexdigest(),
            "package_versions": {
                "openai": _package_version("openai"),
                "mem0ai": _package_version("mem0ai"),
                "agentic-memory": _package_version("agentic-memory"),
                "chromadb": _package_version("chromadb"),
                "sentence-transformers": _package_version("sentence-transformers"),
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "details": {},
        }

    system = PAPER_SYSTEMS[args.system]()
    for conv_offset, conv in enumerate(conversations, start=args.conv_start):
        conv_id = conv.get("sample_id", f"conv_{conv_offset}")
        qa_items = _selected_qas(conv, args.max_questions_per_conv, args.qa_index)
        prior = {int(r["qa_idx"]): r for r in results["details"].get(conv_id, [])}
        completed = {idx for idx, record in prior.items() if record.get("status") == "ok"}
        if all(idx in completed for idx, _qa in qa_items):
            _log(f"=== {conv_id}: SKIP complete ({len(qa_items)} questions) ===")
            continue

        sessions = get_sessions(conv)
        if args.max_sessions_per_conv is not None:
            sessions = sessions[:args.max_sessions_per_conv]
        _log(f"=== {conv_id} [{args.system}]: ingest {len(sessions)} sessions ===")
        try:
            system.ingest(sessions, conv_id)
        except Exception as exc:
            _log(f"INGEST FAILED for {conv_id}: {exc}")
            try:
                system.reset()
            except Exception:
                pass
            continue

        for position, (qa_idx, qa) in enumerate(qa_items, start=1):
            if qa_idx in completed:
                continue
            category = int(qa["category"])
            question = str(qa["question"])
            prompt_question = question
            options = None
            if category == 5:
                prompt_question, options = _adversarial_prompt(qa, conv_id, qa_idx)

            started = time.monotonic()
            try:
                prediction = system.answer(prompt_question)
                if prediction.lower().startswith("error:"):
                    raise RuntimeError(prediction)
                answer_seconds = time.monotonic() - started

                scored_prediction = prediction
                if category == 5:
                    assert options is not None
                    scored_prediction = _resolve_adversarial_prediction(prediction, options)
                score = official_locomo_score(scored_prediction, qa)

                judge_correct = None
                judge_reason = None
                judge_seconds = None
                if category in {1, 2, 3, 4}:
                    judge_started = time.monotonic()
                    judge_correct, judge_reason = judge_answer(
                        question, prediction, str(qa["answer"])
                    )
                    judge_seconds = time.monotonic() - judge_started
                    if judge_reason.startswith("Judge error:"):
                        raise RuntimeError(judge_reason)

                record = {
                    "status": "ok",
                    "qa_id": f"{conv_id}:{qa_idx}",
                    "qa_idx": qa_idx,
                    "question": question,
                    "prompt_question": prompt_question,
                    "gold": qa.get("answer"),
                    "adversarial_answer": qa.get("adversarial_answer"),
                    "prediction": prediction,
                    "scored_prediction": scored_prediction,
                    "category": category,
                    "official_score": score,
                    "judge_correct": judge_correct,
                    "judge_reason": judge_reason,
                    "answer_seconds": round(answer_seconds, 3),
                    "judge_seconds": round(judge_seconds, 3) if judge_seconds is not None else None,
                }
                prior[qa_idx] = record
                marker = "C" if (judge_correct if judge_correct is not None else score == 1.0) else "W"
                _log(
                    f"  {conv_id} {position}/{len(qa_items)} qa_idx={qa_idx} "
                    f"cat={category} score={score:.3f} {marker}"
                )
            except Exception as exc:
                prior[qa_idx] = {
                    "status": "error",
                    "qa_id": f"{conv_id}:{qa_idx}",
                    "qa_idx": qa_idx,
                    "question": question,
                    "category": category,
                    "error": str(exc),
                }
                _log(f"  ERROR {conv_id}:{qa_idx}: {exc}")

            results["details"][conv_id] = [prior[idx] for idx in sorted(prior)]
            _aggregate(results, expected, usage_offset)
            _atomic_write(output, results)

        try:
            system.reset()
        except Exception as exc:
            _log(f"RESET WARNING for {conv_id}: {exc}")

    _aggregate(results, expected, usage_offset)
    _atomic_write(output, results)
    aggregate = results["aggregate"]
    _log(
        f"DONE {args.system}: coverage={aggregate['n_completed']}/{expected} "
        f"official={aggregate['official_locomo_score']} "
        f"judge={aggregate['answer_bearing']['judge_accuracy']}"
    )


if __name__ == "__main__":
    main()
