#!/usr/bin/env python3
"""
LOCOMO Benchmark Evaluation for User Memory Systems

Evaluates memory systems against the LOCOMO benchmark (Maharana et al., ACL 2024):
  - 10 long-term conversations, ~1,986 QA pairs across 5 categories
  - Category 1: Multi-hop (282 QAs) — requires combining facts across sessions
  - Category 2: Temporal (321 QAs) — date/time reasoning
  - Category 3: Open-domain (96 QAs) — inference from evidence
  - Category 4: Single-hop (841 QAs) — direct factual recall
  - Category 5: Adversarial (446 QAs) — detecting unanswerable questions

Protocol:
  1. Feed all conversation sessions into each memory system (one turn at a time)
  2. For each QA, retrieve relevant memories from the system
  3. Use Gemini 3 Flash to generate an answer given the retrieved memories
  4. Score with LOCOMO's token-level F1 metric (and optionally BLEU, LLM-as-Judge)

Supported memory systems:
  - user_as_code: Converts conversations into structured Python code representation
  - mem0:         Uses Mem0's memory extraction and retrieval
  - full_context: Baseline that passes the full conversation text (upper bound)
  - no_memory:    No context baseline (lower bound)

Usage:
    python locomo_eval.py                          # Run all systems, all samples
    python locomo_eval.py --systems mem0           # Single system
    python locomo_eval.py --max-samples 2          # Quick test
    python locomo_eval.py --max-qa 10              # Limit QA per sample
    python locomo_eval.py --resume results.json    # Resume from partial run
"""

import argparse
import json
import os
import random
import re
import string
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import regex as re_unicode
from nltk.stem import PorterStemmer

from google import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()

LOCOMO_DATA = Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
RESULTS_DIR = Path(__file__).parent / "results" / "locomo"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ps = PorterStemmer()

# ---------------------------------------------------------------------------
# LOCOMO Evaluation Metrics (ported from benchmarks/locomo/task_eval/evaluation.py)
# ---------------------------------------------------------------------------

def normalize_answer(s: str) -> str:
    """Normalize answer string for comparison."""
    s = s.replace(",", "")
    s = re_unicode.sub(r'\b(a|an|the|and)\b', ' ', s.lower())
    s = ''.join(ch for ch in s if ch not in string.punctuation)
    return ' '.join(s.split())


def f1_score_single(prediction: str, ground_truth: str) -> float:
    """Token-level F1 between prediction and single ground truth."""
    pred_tokens = [ps.stem(w) for w in normalize_answer(prediction).split()]
    gt_tokens = [ps.stem(w) for w in normalize_answer(ground_truth).split()]
    common = Counter(pred_tokens) & Counter(gt_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gt_tokens)
    return (2 * precision * recall) / (precision + recall)


def f1_multi(prediction: str, ground_truth: str) -> float:
    """F1 for multi-answer (comma-separated) predictions."""
    predictions = [p.strip() for p in prediction.split(",")]
    ground_truths = [g.strip() for g in ground_truth.split(",")]
    import numpy as np
    return float(np.mean([
        max(f1_score_single(p, gt) for p in predictions)
        for gt in ground_truths
    ]))


def evaluate_qa_item(prediction: str, qa: dict) -> float:
    """Evaluate a single QA item using LOCOMO's category-aware scoring."""
    category = qa["category"]
    answer = str(qa.get("answer", ""))

    if category == 3:
        answer = answer.split(";")[0].strip()

    if category in [2, 3, 4]:
        return f1_score_single(prediction, answer)
    elif category == 1:
        return f1_multi(prediction, answer)
    elif category == 5:
        pred_lower = prediction.lower()
        if "no information available" in pred_lower or "not mentioned" in pred_lower:
            return 1.0
        else:
            return 0.0
    else:
        raise ValueError(f"Unknown category: {category}")


# ---------------------------------------------------------------------------
# LLM-as-Judge evaluation
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are evaluating the quality of an answer to a question about a conversation.

Question: {question}
Reference answer: {reference}
Predicted answer: {prediction}

Rate the predicted answer on a scale of 1-5:
1 = Completely wrong or irrelevant
2 = Partially related but mostly wrong
3 = Somewhat correct but missing key details
4 = Mostly correct with minor issues
5 = Fully correct and complete

Respond with ONLY a single number (1-5)."""


def llm_judge_score(question: str, reference: str, prediction: str) -> float:
    """Use Gemini as a judge to score answer quality. Returns 0.0-1.0."""
    try:
        response = gclient.models.generate_content(
            model=MODEL,
            contents=JUDGE_PROMPT.format(
                question=question,
                reference=reference,
                prediction=prediction,
            ),
            config=genai.types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8,
            ),
        )
        score = int(re.search(r'[1-5]', response.text).group())
        return (score - 1) / 4.0  # normalize to 0-1
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Conversation formatting helpers
# ---------------------------------------------------------------------------

def format_conversation_as_text(conversation: dict) -> str:
    """Format a LOCOMO conversation dict into full plaintext."""
    lines = []
    speaker_a = conversation.get("speaker_a", "Speaker A")
    speaker_b = conversation.get("speaker_b", "Speaker B")
    lines.append(f"Conversation between {speaker_a} and {speaker_b}:\n")

    session_nums = sorted(set(
        int(k.split("_")[1])
        for k in conversation.keys()
        if k.startswith("session_") and not k.endswith("date_time")
        and isinstance(conversation[k], list)
    ))

    for num in session_nums:
        key = f"session_{num}"
        dt_key = f"session_{num}_date_time"
        if key not in conversation or not isinstance(conversation[key], list):
            continue
        date_time = conversation.get(dt_key, "")
        lines.append(f"\n--- Session {num} ({date_time}) ---")
        for turn in conversation[key]:
            speaker = turn.get("speaker", "?")
            text = turn.get("text", "")
            line = f"{speaker}: {text}"
            if "blip_caption" in turn:
                line += f" [shared image: {turn['blip_caption']}]"
            lines.append(line)

    return "\n".join(lines)


def get_session_turns(conversation: dict) -> list[dict]:
    """Extract all turns with session metadata, in chronological order."""
    turns = []
    session_nums = sorted(set(
        int(k.split("_")[1])
        for k in conversation.keys()
        if k.startswith("session_") and not k.endswith("date_time")
        and isinstance(conversation[k], list)
    ))

    for num in session_nums:
        key = f"session_{num}"
        dt_key = f"session_{num}_date_time"
        date_time = conversation.get(dt_key, "")
        for turn in conversation[key]:
            turns.append({
                "session_num": num,
                "date_time": date_time,
                "speaker": turn.get("speaker", "?"),
                "text": turn.get("text", ""),
                "dia_id": turn.get("dia_id", ""),
                "blip_caption": turn.get("blip_caption"),
            })
    return turns


# ---------------------------------------------------------------------------
# Memory system wrappers
# ---------------------------------------------------------------------------

class FullContextSystem:
    """Upper bound baseline: pass the full conversation as context."""
    name = "full_context"

    def reset(self):
        self._conv_text = ""

    def ingest_conversation(self, conversation: dict):
        self._conv_text = format_conversation_as_text(conversation)

    def retrieve_for_question(self, question: str) -> str:
        return self._conv_text


class NoMemorySystem:
    """Lower bound baseline: no memory at all."""
    name = "no_memory"

    def reset(self):
        pass

    def ingest_conversation(self, conversation: dict):
        pass

    def retrieve_for_question(self, question: str) -> str:
        return "(No conversation context available)"


class Mem0System:
    """Mem0 memory system: extract facts, retrieve by query."""
    name = "mem0"

    def __init__(self):
        from mem0 import Memory
        self._mem_class = Memory
        self._memory = None
        self._user_id = None

    def reset(self):
        self._memory = self._mem_class()
        self._user_id = f"locomo_{int(time.time())}"

    def ingest_conversation(self, conversation: dict):
        turns = get_session_turns(conversation)
        speaker_a = conversation.get("speaker_a", "Speaker A")
        speaker_b = conversation.get("speaker_b", "Speaker B")

        batch = []
        for turn in turns:
            role = "user" if turn["speaker"] == speaker_a else "assistant"
            content = turn["text"]
            if turn.get("blip_caption"):
                content += f" [shared image: {turn['blip_caption']}]"
            batch.append({"role": role, "content": content})

            # Ingest in batches of ~20 turns to represent session boundaries
            if len(batch) >= 20:
                try:
                    self._memory.add(batch, user_id=self._user_id)
                except Exception as e:
                    print(f"      Mem0 add error: {e}")
                batch = []

        if batch:
            try:
                self._memory.add(batch, user_id=self._user_id)
            except Exception as e:
                print(f"      Mem0 add error: {e}")

    def retrieve_for_question(self, question: str) -> str:
        try:
            results = self._memory.search(question, user_id=self._user_id)
            memories = results.get("results", []) if isinstance(results, dict) else results
            if not memories:
                return "(No relevant memories found)"
            lines = [f"Retrieved memories ({len(memories)} items):"]
            for i, r in enumerate(memories, 1):
                if isinstance(r, dict):
                    mem = r.get("memory", str(r))
                else:
                    mem = str(r)
                lines.append(f"  {i}. {mem}")
            return "\n".join(lines)
        except Exception as e:
            return f"(Memory retrieval error: {e})"


class UserAsCodeSystem:
    """
    User as Code: converts conversation into structured Python code representation.

    For LOCOMO evaluation, we:
    1. Use the LLM to extract structured facts from conversation sessions
    2. Organize them into domain-like Python dataclass state
    3. Retrieve relevant state for each question
    """
    name = "user_as_code"

    def __init__(self):
        self._state_code = ""
        self._facts_by_session = {}
        self._speaker_a = ""
        self._speaker_b = ""
        self._all_turns_text = ""

    def reset(self):
        self._state_code = ""
        self._facts_by_session = {}
        self._speaker_a = ""
        self._speaker_b = ""
        self._all_turns_text = ""

    def ingest_conversation(self, conversation: dict):
        """Extract structured facts from conversation and build code representation."""
        self._speaker_a = conversation.get("speaker_a", "Speaker A")
        self._speaker_b = conversation.get("speaker_b", "Speaker B")

        session_nums = sorted(set(
            int(k.split("_")[1])
            for k in conversation.keys()
            if k.startswith("session_") and not k.endswith("date_time")
            and isinstance(conversation[k], list)
        ))

        all_session_texts = []
        for num in session_nums:
            key = f"session_{num}"
            dt_key = f"session_{num}_date_time"
            date_time = conversation.get(dt_key, "")

            session_lines = [f"[Session {num}, {date_time}]"]
            for turn in conversation[key]:
                line = f"{turn['speaker']}: {turn['text']}"
                if turn.get("blip_caption"):
                    line += f" [image: {turn['blip_caption']}]"
                session_lines.append(line)
            all_session_texts.append("\n".join(session_lines))

        self._all_turns_text = "\n\n".join(all_session_texts)

        # Extract structured state via LLM in batches of sessions
        session_batches = []
        batch = []
        batch_size = 0
        for text in all_session_texts:
            batch.append(text)
            batch_size += len(text)
            # Batch ~8000 chars at a time to fit in context
            if batch_size > 8000:
                session_batches.append("\n\n".join(batch))
                batch = []
                batch_size = 0
        if batch:
            session_batches.append("\n\n".join(batch))

        all_facts = []
        for batch_text in session_batches:
            facts = self._extract_facts(batch_text)
            all_facts.extend(facts)

        # Build code representation
        self._state_code = self._build_code_repr(all_facts)

    def _extract_facts(self, session_text: str) -> list[str]:
        """Use LLM to extract key facts from conversation sessions."""
        prompt = f"""Extract all important facts from this conversation as a list.
Include: names, dates, events, plans, preferences, relationships, locations,
activities, emotions, and any specific details mentioned.
Format each fact on a new line starting with "- ".

Conversation:
{session_text}

Facts:"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=2000,
                ),
            )
            lines = response.text.strip().split("\n")
            facts = [l.lstrip("- ").strip() for l in lines if l.strip().startswith("-") or l.strip().startswith("*")]
            return facts if facts else [l.strip() for l in lines if l.strip()]
        except Exception as e:
            print(f"      Fact extraction error: {e}")
            return []

    def _build_code_repr(self, facts: list[str]) -> str:
        """Build a Python code representation from extracted facts."""
        if not facts:
            return "# No facts extracted"

        prompt = f"""Convert these facts about two people ({self._speaker_a} and {self._speaker_b})
into a structured Python representation using dataclasses and typed variables.
Group facts by domain (personal info, events, relationships, preferences, plans, etc.).
Include dates and temporal information as datetime objects where applicable.
Make it concise but complete — every fact should be represented.

Facts:
{chr(10).join('- ' + f for f in facts)}

Python code:"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=4000,
                ),
            )
            code = response.text.strip()
            # Remove markdown code fences if present
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            return code
        except Exception as e:
            # Fallback: simple fact list in Python format
            lines = ["# User state (fact list)", "from datetime import date, datetime", ""]
            lines.append("facts = [")
            for f in facts:
                lines.append(f'    "{f}",')
            lines.append("]")
            return "\n".join(lines)

    def retrieve_for_question(self, question: str) -> str:
        """Return the full code representation plus targeted retrieval."""
        # For LOCOMO, the code representation is compact enough to include fully.
        # We also prepend the raw conversation for maximum context.
        header = (
            f"# === User State: {self._speaker_a} & {self._speaker_b} ===\n"
            f"# Structured Python representation of conversation history\n\n"
        )
        return header + self._state_code


# ---------------------------------------------------------------------------
# QA answering with LLM
# ---------------------------------------------------------------------------

QA_SYSTEM = """You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions. Be concise — answer in a short phrase.
If the question asks about a date, use the conversation dates to answer with an approximate date.
If the information is not available in the context, say "No information available"."""

QA_PROMPT = """Context:
{context}

Question: {question}

Answer in a short phrase:"""

QA_PROMPT_CAT5 = """Context:
{context}

Question: {question} Select the correct answer: (a) {option_a} (b) {option_b}.

Answer with just (a) or (b):"""


def answer_question(question: str, context: str, qa: dict, max_retries: int = 3) -> str:
    """Generate an answer using the LLM given retrieved context."""
    category = qa["category"]

    if category == 5:
        # Adversarial: present as multiple choice
        adv_answer = qa.get("adversarial_answer", qa.get("answer", ""))
        if random.random() < 0.5:
            option_a = "Not mentioned in the conversation"
            option_b = adv_answer
            answer_key = {"a": "Not mentioned in the conversation", "b": adv_answer}
        else:
            option_a = adv_answer
            option_b = "Not mentioned in the conversation"
            answer_key = {"a": adv_answer, "b": "Not mentioned in the conversation"}

        prompt = QA_PROMPT_CAT5.format(
            context=context, question=question,
            option_a=option_a, option_b=option_b,
        )
    elif category == 2:
        question_aug = question + " Use dates from the conversation to answer with an approximate date."
        prompt = QA_PROMPT.format(context=context, question=question_aug)
    else:
        prompt = QA_PROMPT.format(context=context, question=question)

    for attempt in range(max_retries):
        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=QA_SYSTEM,
                    temperature=0.0,
                    max_output_tokens=64,
                ),
            )

            # Handle None or empty responses
            if response is None or response.text is None:
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return "No information available"

            answer = response.text.strip()
            if not answer:
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return "No information available"

            # Post-process category 5 answers
            if category == 5:
                answer_lower = answer.lower().strip()
                if answer_lower.startswith("(a)") or answer_lower == "a":
                    answer = answer_key["a"]
                elif answer_lower.startswith("(b)") or answer_lower == "b":
                    answer = answer_key["b"]

            return answer

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            return "No information available"

    return "No information available"


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

CATEGORY_NAMES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}


def run_evaluation(
    systems: list[str],
    max_samples: int | None = None,
    max_qa: int | None = None,
    resume_file: str | None = None,
    use_judge: bool = False,
):
    """Run the LOCOMO evaluation."""

    # Load dataset
    print(f"Loading LOCOMO dataset from {LOCOMO_DATA}")
    with open(LOCOMO_DATA) as f:
        dataset = json.load(f)
    print(f"  {len(dataset)} conversations, "
          f"{sum(len(s['qa']) for s in dataset)} QA pairs")

    if max_samples:
        dataset = dataset[:max_samples]

    # Initialize systems
    active_systems = []
    for sys_name in systems:
        if sys_name == "full_context":
            active_systems.append(FullContextSystem())
        elif sys_name == "no_memory":
            active_systems.append(NoMemorySystem())
        elif sys_name == "mem0":
            try:
                active_systems.append(Mem0System())
                print("  Mem0: ready")
            except Exception as e:
                print(f"  Mem0: FAILED ({e})")
        elif sys_name == "user_as_code":
            active_systems.append(UserAsCodeSystem())
            print("  User as Code: ready")
        else:
            print(f"  Unknown system: {sys_name}, skipping")

    if not active_systems:
        print("No systems to evaluate!")
        return

    # Load resume state
    existing_results = {}
    if resume_file and Path(resume_file).exists():
        with open(resume_file) as f:
            existing_data = json.load(f)
        for r in existing_data.get("results", []):
            key = (r["sample_id"], r["system"], r["qa_index"])
            existing_results[key] = r
        print(f"  Resuming: {len(existing_results)} existing results loaded")

    print(f"\n{'='*70}")
    print(f"  LOCOMO Benchmark Evaluation")
    print(f"  Model: {MODEL}")
    print(f"  Systems: {[s.name for s in active_systems]}")
    print(f"  Samples: {len(dataset)}")
    print(f"{'='*70}\n")

    all_results = list(existing_results.values())

    for sample_idx, sample in enumerate(dataset):
        sid = sample["sample_id"]
        conversation = sample["conversation"]
        qas = sample["qa"]
        if max_qa:
            qas = qas[:max_qa]

        speaker_a = conversation.get("speaker_a", "?")
        speaker_b = conversation.get("speaker_b", "?")
        print(f"  [{sample_idx+1}/{len(dataset)}] {sid} "
              f"({speaker_a} & {speaker_b}, {len(qas)} QAs)")

        for sys_obj in active_systems:
            sys_name = sys_obj.name

            # Check if all QAs for this sample+system are already done
            existing_count = sum(
                1 for i in range(len(qas))
                if (sid, sys_name, i) in existing_results
            )
            if existing_count == len(qas):
                print(f"    {sys_name}: all {len(qas)} QAs cached, skipping")
                continue

            print(f"    {sys_name}: ingesting conversation...", end="", flush=True)
            sys_obj.reset()
            t0 = time.time()
            sys_obj.ingest_conversation(conversation)
            ingest_time = time.time() - t0
            print(f" ({ingest_time:.1f}s)")

            # Answer questions
            scores = []
            for qi, qa in enumerate(qas):
                result_key = (sid, sys_name, qi)
                if result_key in existing_results:
                    scores.append(existing_results[result_key]["f1"])
                    continue

                context = sys_obj.retrieve_for_question(qa["question"])
                prediction = answer_question(qa["question"], context, qa)

                f1 = evaluate_qa_item(prediction, qa)

                result = {
                    "sample_id": sid,
                    "system": sys_name,
                    "qa_index": qi,
                    "category": qa["category"],
                    "question": qa["question"],
                    "answer": qa.get("answer", qa.get("adversarial_answer", "")),
                    "prediction": prediction,
                    "f1": round(f1, 4),
                }

                if use_judge and qa["category"] != 5:
                    ref = qa.get("answer", "")
                    result["judge_score"] = round(
                        llm_judge_score(qa["question"], ref, prediction), 4
                    )

                scores.append(f1)
                all_results.append(result)

                # Rate limiting
                time.sleep(0.1)

            avg_f1 = sum(scores) / max(len(scores), 1)
            print(f"      -> avg F1: {avg_f1:.3f} ({len(scores)} QAs)")

            # Save incrementally
            _save_results(all_results, active_systems, dataset)

    # Final summary
    print_summary(all_results)
    outfile = _save_results(all_results, active_systems, dataset)
    print(f"\n  Results saved to: {outfile}")
    return all_results


def _save_results(all_results, systems, dataset):
    """Save current results to JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = RESULTS_DIR / f"locomo_eval_{timestamp}.json"

    output = {
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "n_samples": len(dataset),
        "n_results": len(all_results),
        "systems": [s.name for s in systems],
        "results": all_results,
    }

    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Also save a "latest" symlink-style copy
    latest = RESULTS_DIR / "locomo_eval_latest.json"
    with open(latest, "w") as f:
        json.dump(output, f, indent=2, default=str)

    return outfile


def print_summary(all_results):
    """Print summary statistics matching LOCOMO paper format."""
    print(f"\n{'='*70}")
    print(f"  LOCOMO EVALUATION RESULTS")
    print(f"{'='*70}\n")

    systems = sorted(set(r["system"] for r in all_results))

    # Overall by system
    print(f"  {'System':<18} {'Overall':>8} ", end="")
    for cat in [4, 1, 2, 3, 5]:
        print(f" {CATEGORY_NAMES[cat]:>12}", end="")
    print(f" {'N':>6}")
    print(f"  {'-'*88}")

    for sys_name in systems:
        sys_results = [r for r in all_results if r["system"] == sys_name]
        overall = sum(r["f1"] for r in sys_results) / max(len(sys_results), 1)

        print(f"  {sys_name:<18} {overall:>8.3f} ", end="")
        for cat in [4, 1, 2, 3, 5]:
            cat_results = [r for r in sys_results if r["category"] == cat]
            if cat_results:
                avg = sum(r["f1"] for r in cat_results) / len(cat_results)
                print(f" {avg:>12.3f}", end="")
            else:
                print(f" {'n/a':>12}", end="")
        print(f" {len(sys_results):>6}")

    # LLM-as-Judge scores if available
    judge_results = [r for r in all_results if "judge_score" in r]
    if judge_results:
        print(f"\n  LLM-as-Judge Scores (1-5 scale, normalized to 0-1):")
        print(f"  {'System':<18} {'Judge Avg':>10}")
        print(f"  {'-'*30}")
        for sys_name in systems:
            sys_judge = [r for r in judge_results if r["system"] == sys_name]
            if sys_judge:
                avg = sum(r["judge_score"] for r in sys_judge) / len(sys_judge)
                print(f"  {sys_name:<18} {avg:>10.3f}")

    # Per-sample breakdown
    print(f"\n  Per-sample F1:")
    samples = sorted(set(r["sample_id"] for r in all_results))
    print(f"  {'Sample':<15}", end="")
    for sys_name in systems:
        print(f" {sys_name:>15}", end="")
    print()
    print(f"  {'-'*(15 + 16*len(systems))}")
    for sid in samples:
        print(f"  {sid:<15}", end="")
        for sys_name in systems:
            sample_sys = [r for r in all_results
                          if r["sample_id"] == sid and r["system"] == sys_name]
            if sample_sys:
                avg = sum(r["f1"] for r in sample_sys) / len(sample_sys)
                print(f" {avg:>15.3f}", end="")
            else:
                print(f" {'--':>15}", end="")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LOCOMO Benchmark Evaluation for User Memory Systems"
    )
    parser.add_argument(
        "--systems", nargs="+",
        default=["user_as_code", "mem0", "full_context", "no_memory"],
        choices=["user_as_code", "mem0", "full_context", "no_memory"],
        help="Memory systems to evaluate",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Max number of conversation samples to evaluate",
    )
    parser.add_argument(
        "--max-qa", type=int, default=None,
        help="Max QA pairs per sample (for quick testing)",
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path to previous results JSON to resume from",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="Also compute LLM-as-Judge scores (slower, costs more)",
    )
    args = parser.parse_args()

    run_evaluation(
        systems=args.systems,
        max_samples=args.max_samples,
        max_qa=args.max_qa,
        resume_file=args.resume,
        use_judge=args.judge,
    )


if __name__ == "__main__":
    main()
