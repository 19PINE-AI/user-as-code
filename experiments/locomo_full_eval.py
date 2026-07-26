#!/usr/bin/env python3
"""
LOCOMO Full Benchmark Evaluation — All Memory Systems

Evaluates 6 memory systems against the LOCOMO benchmark:
  - user_as_code: Structured Python code representation
  - mem0:         Mem0 memory extraction and retrieval
  - a_mem:        A-MEM agentic memory system
  - engram:       Engram lightweight memory layer
  - full_context: Reference that receives the full conversation text
  - no_memory:    Lower bound (no context)

Runs on 2 LOCOMO conversations with ALL QA pairs.
Reports per-category F1 scores (categories 1-5).

Usage:
    python locomo_full_eval.py
    python locomo_full_eval.py --systems user_as_code mem0 a_mem
"""

import argparse
import json
import os
import pathlib
import random
import re
import string
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import regex as re_unicode
from nltk.stem import PorterStemmer

from google import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()

LOCOMO_DATA = Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ps = PorterStemmer()

ALL_SYSTEMS = ["user_as_code", "mem0", "a_mem", "engram", "full_context", "no_memory"]

CATEGORY_NAMES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}

# ---------------------------------------------------------------------------
# LOCOMO Evaluation Metrics
# ---------------------------------------------------------------------------

def normalize_answer(s: str) -> str:
    """Normalize answer string for comparison."""
    s = str(s).replace(",", "")
    s = re_unicode.sub(r'\b(a|an|the|and)\b', ' ', s.lower())
    s = ''.join(ch for ch in s if ch not in string.punctuation)
    return ' '.join(s.split())


def f1_score_single(prediction: str, ground_truth: str) -> float:
    """Token-level F1 between prediction and single ground truth."""
    pred_tokens = [ps.stem(w) for w in normalize_answer(prediction).split()]
    gt_tokens = [ps.stem(w) for w in normalize_answer(ground_truth).split()]
    if not pred_tokens or not gt_tokens:
        return 0.0
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
    ground_truths = [g.strip() for g in str(ground_truth).split(",")]
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
    """Reference baseline: pass the full conversation as context."""
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
        # Clean stale Qdrant locks before importing
        for p in [
            pathlib.Path('/tmp/qdrant/.lock'),
            pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock',
        ]:
            p.unlink(missing_ok=True)

        from mem0 import Memory
        self._mem_class = Memory
        self._memory = None
        self._user_id = None

    def reset(self):
        # Clean locks again before each reset
        for p in [
            pathlib.Path('/tmp/qdrant/.lock'),
            pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock',
        ]:
            p.unlink(missing_ok=True)
        self._memory = self._mem_class()
        self._user_id = f"locomo_{int(time.time())}"

    def ingest_conversation(self, conversation: dict):
        turns = get_session_turns(conversation)
        speaker_a = conversation.get("speaker_a", "Speaker A")

        batch = []
        for turn in turns:
            role = "user" if turn["speaker"] == speaker_a else "assistant"
            content = turn["text"]
            if turn.get("blip_caption"):
                content += f" [shared image: {turn['blip_caption']}]"
            batch.append({"role": role, "content": content})

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


class AMemSystem:
    """A-MEM agentic memory system."""
    name = "a_mem"

    def __init__(self):
        from agentic_memory.memory_system import AgenticMemorySystem
        self._mem_class = AgenticMemorySystem
        self._memory = None

    def reset(self):
        self._memory = self._mem_class(
            llm_backend="openai",
            llm_model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

    def ingest_conversation(self, conversation: dict):
        turns = get_session_turns(conversation)
        speaker_a = conversation.get("speaker_a", "Speaker A")
        speaker_b = conversation.get("speaker_b", "Speaker B")

        # Group turns into chunks of ~5 turns for richer context per note
        chunk = []
        for turn in turns:
            speaker = turn["speaker"]
            text = turn["text"]
            if turn.get("blip_caption"):
                text += f" [shared image: {turn['blip_caption']}]"
            date_str = turn.get("date_time", "")
            chunk.append(f"[{date_str}] {speaker}: {text}")

            if len(chunk) >= 5:
                note_text = "\n".join(chunk)
                try:
                    self._memory.add_note(note_text)
                except Exception as e:
                    print(f"      A-MEM add_note error: {e}")
                chunk = []
                time.sleep(0.2)  # Rate limiting for OpenAI

        if chunk:
            note_text = "\n".join(chunk)
            try:
                self._memory.add_note(note_text)
            except Exception as e:
                print(f"      A-MEM add_note error: {e}")

    def retrieve_for_question(self, question: str) -> str:
        try:
            results = self._memory.search_agentic(question, k=10)
            if not results:
                return "(No relevant memories found)"
            lines = [f"Retrieved memories ({len(results)} items):"]
            for i, r in enumerate(results, 1):
                if isinstance(r, dict):
                    content = r.get("content", r.get("text", str(r)))
                else:
                    content = str(r)
                lines.append(f"  {i}. {content}")
            return "\n".join(lines)
        except Exception as e:
            return f"(Memory retrieval error: {e})"


class EngramSystem:
    """Engram lightweight memory system."""
    name = "engram"

    def __init__(self):
        from engram.client import Memory
        self._mem_class = Memory
        self._memory = None

    def reset(self):
        import tempfile
        # Use a fresh temp db for each conversation to isolate state
        self._db_path = Path(tempfile.mktemp(suffix=".db", prefix="engram_locomo_"))
        self._memory = self._mem_class(
            db_path=self._db_path,
            namespace="locomo_eval",
        )

    def ingest_conversation(self, conversation: dict):
        turns = get_session_turns(conversation)
        speaker_a = conversation.get("speaker_a", "Speaker A")
        speaker_b = conversation.get("speaker_b", "Speaker B")

        # Group turns into chunks and store each as a memory
        chunk = []
        for turn in turns:
            speaker = turn["speaker"]
            text = turn["text"]
            if turn.get("blip_caption"):
                text += f" [shared image: {turn['blip_caption']}]"
            date_str = turn.get("date_time", "")
            chunk.append(f"[{date_str}] {speaker}: {text}")

            if len(chunk) >= 5:
                note_text = "\n".join(chunk)
                try:
                    self._memory.store(note_text, type="fact", importance=7)
                except Exception as e:
                    print(f"      Engram store error: {e}")
                chunk = []

        if chunk:
            note_text = "\n".join(chunk)
            try:
                self._memory.store(note_text, type="fact", importance=7)
            except Exception as e:
                print(f"      Engram store error: {e}")

    def retrieve_for_question(self, question: str) -> str:
        try:
            # First try search, then fall back to listing all
            results = self._memory.search(question, limit=20)
            if results:
                lines = [f"Retrieved memories ({len(results)} items):"]
                for i, r in enumerate(results, 1):
                    content = r.content if hasattr(r, 'content') else str(r)
                    lines.append(f"  {i}. {content}")
                return "\n".join(lines)

            # Fallback: list recent memories
            entries = self._memory.list(limit=50)
            if entries:
                lines = [f"All stored memories ({len(entries)} items):"]
                for i, e in enumerate(entries, 1):
                    content = e.content if hasattr(e, 'content') else str(e)
                    lines.append(f"  {i}. {content}")
                return "\n".join(lines)

            return "(No memories stored)"
        except Exception as e:
            return f"(Memory retrieval error: {e})"


class UserAsCodeSystem:
    """User as Code: structured Python code representation of conversation."""
    name = "user_as_code"

    def __init__(self):
        self._state_code = ""
        self._speaker_a = ""
        self._speaker_b = ""

    def reset(self):
        self._state_code = ""
        self._speaker_a = ""
        self._speaker_b = ""

    def ingest_conversation(self, conversation: dict):
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

        # Extract structured state via LLM in batches
        session_batches = []
        batch = []
        batch_size = 0
        for text in all_session_texts:
            batch.append(text)
            batch_size += len(text)
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

        self._state_code = self._build_code_repr(all_facts)

    def _extract_facts(self, session_text: str) -> list[str]:
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
            facts = [l.lstrip("- *").strip() for l in lines if l.strip().startswith("-") or l.strip().startswith("*")]
            return facts if facts else [l.strip() for l in lines if l.strip()]
        except Exception as e:
            print(f"      Fact extraction error: {e}")
            return []

    def _build_code_repr(self, facts: list[str]) -> str:
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
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            return code
        except Exception as e:
            lines = ["# User state (fact list)", "from datetime import date, datetime", ""]
            lines.append("facts = [")
            for f in facts:
                lines.append(f'    "{f}",')
            lines.append("]")
            return "\n".join(lines)

    def retrieve_for_question(self, question: str) -> str:
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

def create_system(sys_name: str):
    """Factory to create a memory system by name."""
    if sys_name == "full_context":
        return FullContextSystem()
    elif sys_name == "no_memory":
        return NoMemorySystem()
    elif sys_name == "mem0":
        return Mem0System()
    elif sys_name == "a_mem":
        return AMemSystem()
    elif sys_name == "engram":
        return EngramSystem()
    elif sys_name == "user_as_code":
        return UserAsCodeSystem()
    else:
        raise ValueError(f"Unknown system: {sys_name}")


def run_evaluation(
    systems: list[str],
    max_samples: int = 2,
    output_file: str | None = None,
):
    """Run the LOCOMO evaluation across all specified systems."""

    # Load dataset
    print(f"Loading LOCOMO dataset from {LOCOMO_DATA}")
    with open(LOCOMO_DATA) as f:
        dataset = json.load(f)

    total_qa = sum(len(s['qa']) for s in dataset)
    print(f"  {len(dataset)} conversations, {total_qa} QA pairs total")

    # Limit to max_samples conversations
    dataset = dataset[:max_samples]
    eval_qa = sum(len(s['qa']) for s in dataset)
    print(f"  Using {len(dataset)} conversations, {eval_qa} QA pairs")

    # Initialize systems
    active_systems = {}
    for sys_name in systems:
        try:
            sys_obj = create_system(sys_name)
            active_systems[sys_name] = sys_obj
            print(f"  {sys_name}: ready")
        except Exception as e:
            print(f"  {sys_name}: FAILED to initialize ({e})")
            traceback.print_exc()

    if not active_systems:
        print("No systems to evaluate!")
        return

    print(f"\n{'='*70}")
    print(f"  LOCOMO Full Benchmark Evaluation")
    print(f"  LLM: {MODEL}")
    print(f"  Systems: {list(active_systems.keys())}")
    print(f"  Conversations: {len(dataset)}")
    print(f"  Total QA pairs: {eval_qa}")
    print(f"{'='*70}\n")

    # Results storage: system -> list of result dicts
    all_results = defaultdict(list)

    for sample_idx, sample in enumerate(dataset):
        sid = sample["sample_id"]
        conversation = sample["conversation"]
        qas = sample["qa"]

        speaker_a = conversation.get("speaker_a", "?")
        speaker_b = conversation.get("speaker_b", "?")
        print(f"\n  [{sample_idx+1}/{len(dataset)}] {sid} "
              f"({speaker_a} & {speaker_b}, {len(qas)} QAs)")
        print(f"  {'-'*60}")

        for sys_name, sys_obj in active_systems.items():
            print(f"\n    === {sys_name} ===")

            try:
                # Reset and ingest
                print(f"    Ingesting conversation...", end="", flush=True)
                sys_obj.reset()
                t0 = time.time()
                sys_obj.ingest_conversation(conversation)
                ingest_time = time.time() - t0
                print(f" done ({ingest_time:.1f}s)")

                # Answer all QA pairs
                cat_scores = defaultdict(list)
                errors = 0

                for qi, qa in enumerate(qas):
                    try:
                        context = sys_obj.retrieve_for_question(qa["question"])
                        prediction = answer_question(qa["question"], context, qa)
                        f1 = evaluate_qa_item(prediction, qa)

                        result = {
                            "sample_id": sid,
                            "system": sys_name,
                            "qa_index": qi,
                            "category": qa["category"],
                            "question": qa["question"],
                            "answer": str(qa.get("answer", qa.get("adversarial_answer", ""))),
                            "prediction": prediction,
                            "f1": round(f1, 4),
                        }
                        all_results[sys_name].append(result)
                        cat_scores[qa["category"]].append(f1)

                        # Progress indicator every 25 QAs
                        if (qi + 1) % 25 == 0:
                            print(f"    ...{qi+1}/{len(qas)} QAs done", flush=True)

                        # Rate limiting
                        time.sleep(0.05)

                    except Exception as e:
                        errors += 1
                        print(f"    QA {qi} error: {e}")
                        all_results[sys_name].append({
                            "sample_id": sid,
                            "system": sys_name,
                            "qa_index": qi,
                            "category": qa["category"],
                            "question": qa["question"],
                            "answer": str(qa.get("answer", "")),
                            "prediction": "ERROR",
                            "f1": 0.0,
                        })

                # Print per-category summary for this system+conversation
                total_f1 = []
                for cat in sorted(cat_scores.keys()):
                    scores = cat_scores[cat]
                    avg = sum(scores) / len(scores) if scores else 0
                    total_f1.extend(scores)
                    print(f"      Cat{cat} ({CATEGORY_NAMES.get(cat, '?'):>10}): "
                          f"F1={avg:.3f} (n={len(scores)})")
                overall = sum(total_f1) / len(total_f1) if total_f1 else 0
                print(f"      {'Overall':>22}: F1={overall:.3f} "
                      f"(n={len(total_f1)}, errors={errors})")

            except Exception as e:
                print(f"    SYSTEM ERROR: {e}")
                traceback.print_exc()
                print(f"    Skipping {sys_name} for conversation {sid}")

        # Incremental save after each conversation
        _save_results(all_results, output_file)

    # Final summary
    print_summary(all_results)

    outfile = _save_results(all_results, output_file)
    print(f"\n  Results saved to: {outfile}")
    return all_results


def _save_results(all_results: dict, output_file: str | None = None) -> str:
    """Save current results to JSON."""
    outfile = output_file or str(RESULTS_DIR / "locomo_full_results.json")

    # Flatten all results
    flat_results = []
    for sys_name in ALL_SYSTEMS:
        if sys_name in all_results:
            flat_results.extend(all_results[sys_name])

    # Compute summary statistics
    summary = {}
    for sys_name in all_results:
        sys_results = all_results[sys_name]
        if not sys_results:
            continue

        sys_summary = {"overall_f1": 0.0, "n": len(sys_results), "per_category": {}}
        sys_summary["overall_f1"] = round(
            sum(r["f1"] for r in sys_results) / len(sys_results), 4
        )

        for cat in [1, 2, 3, 4, 5]:
            cat_results = [r for r in sys_results if r["category"] == cat]
            if cat_results:
                sys_summary["per_category"][CATEGORY_NAMES[cat]] = {
                    "f1": round(sum(r["f1"] for r in cat_results) / len(cat_results), 4),
                    "n": len(cat_results),
                }
        summary[sys_name] = sys_summary

    output = {
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "n_conversations": len(set(r["sample_id"] for r in flat_results)) if flat_results else 0,
        "n_results": len(flat_results),
        "systems": list(all_results.keys()),
        "summary": summary,
        "results": flat_results,
    }

    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, default=str)

    return outfile


def print_summary(all_results: dict):
    """Print summary table matching requested format."""
    print(f"\n{'='*90}")
    print(f"  LOCOMO FULL BENCHMARK RESULTS")
    print(f"{'='*90}\n")

    # Header
    header = f"  {'System':<16}"
    for cat in [1, 2, 3, 4, 5]:
        short = {1: "Cat1(multi)", 2: "Cat2(temp)", 3: "Cat3(open)",
                 4: "Cat4(single)", 5: "Cat5(adv)"}[cat]
        header += f" {short:>12}"
    header += f" {'Overall F1':>12} {'N':>6}"
    print(header)
    print(f"  {'-'*88}")

    # Rows - in canonical order
    for sys_name in ALL_SYSTEMS:
        if sys_name not in all_results or not all_results[sys_name]:
            continue

        sys_results = all_results[sys_name]
        row = f"  {sys_name:<16}"

        all_f1 = []
        for cat in [1, 2, 3, 4, 5]:
            cat_results = [r for r in sys_results if r["category"] == cat]
            if cat_results:
                avg = sum(r["f1"] for r in cat_results) / len(cat_results)
                all_f1.extend([r["f1"] for r in cat_results])
                row += f" {avg:>12.3f}"
            else:
                row += f" {'n/a':>12}"

        overall = sum(all_f1) / len(all_f1) if all_f1 else 0
        row += f" {overall:>12.3f} {len(sys_results):>6}"
        print(row)

    print()

    # Per-conversation breakdown
    systems_present = [s for s in ALL_SYSTEMS if s in all_results and all_results[s]]
    if systems_present:
        samples = sorted(set(r["sample_id"] for s in systems_present for r in all_results[s]))
        print(f"  Per-conversation F1:")
        header2 = f"  {'Sample':<15}"
        for s in systems_present:
            header2 += f" {s:>15}"
        print(header2)
        print(f"  {'-'*(15 + 16*len(systems_present))}")

        for sid in samples:
            row = f"  {sid:<15}"
            for s in systems_present:
                sample_results = [r for r in all_results[s] if r["sample_id"] == sid]
                if sample_results:
                    avg = sum(r["f1"] for r in sample_results) / len(sample_results)
                    row += f" {avg:>15.3f}"
                else:
                    row += f" {'--':>15}"
            print(row)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LOCOMO Full Benchmark — All Memory Systems"
    )
    parser.add_argument(
        "--systems", nargs="+",
        default=ALL_SYSTEMS,
        choices=ALL_SYSTEMS,
        help="Memory systems to evaluate (default: all)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=2,
        help="Number of conversations to evaluate (default: 2)",
    )
    parser.add_argument(
        "--output", type=str,
        default=str(RESULTS_DIR / "locomo_full_results.json"),
        help="Output file path",
    )
    args = parser.parse_args()

    run_evaluation(
        systems=args.systems,
        max_samples=args.max_samples,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
