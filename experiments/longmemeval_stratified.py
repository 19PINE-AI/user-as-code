"""
LongMemEval Stratified Evaluation
===================================
Runs a stratified sample of ~60 questions (10 per question type) across
three memory systems: user_as_code, mem0, full_context.

Uses Gemini 3 Flash for generation and LLM-as-judge evaluation.
"""

import json
import os
import glob
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from tqdm import tqdm
from google import genai

# ---------------------------------------------------------------------------
# Clean stale Qdrant locks before anything else
# ---------------------------------------------------------------------------
for lock in glob.glob('/tmp/qdrant/.lock') + glob.glob(os.path.expanduser('~/.mem0/migrations_qdrant/.lock')):
    try:
        os.remove(lock)
        print(f"Removed stale lock: {lock}")
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
EVAL_MODEL = "gemini-3-flash-preview"

DATASET_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "longmemeval" / "data" / "longmemeval_oracle.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SEED = 42
SAMPLES_PER_TYPE = 10

ALL_QTYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "temporal-reasoning",
    "knowledge-update",
]

SYSTEM_NAMES = ["user_as_code", "mem0", "full_context"]

gclient = genai.Client()

# ---------------------------------------------------------------------------
# Dataset loading & stratified sampling
# ---------------------------------------------------------------------------

def load_and_sample(path: Path, samples_per_type: int = SAMPLES_PER_TYPE,
                    seed: int = SEED) -> list[dict]:
    """Load dataset and return stratified sample."""
    data = json.load(open(path))
    print(f"Loaded {len(data)} questions from {path.name}")

    # Group by question type
    by_type = defaultdict(list)
    for entry in data:
        by_type[entry["question_type"]].append(entry)

    rng = random.Random(seed)
    sampled = []
    for qtype in ALL_QTYPES:
        pool = by_type[qtype]
        n = min(samples_per_type, len(pool))
        chosen = rng.sample(pool, n)
        sampled.extend(chosen)
        print(f"  {qtype}: sampled {n} from {len(pool)}")

    # Shuffle so we don't process all of one type in a row
    rng.shuffle(sampled)
    print(f"Total sampled: {len(sampled)}")
    return sampled


# ---------------------------------------------------------------------------
# LLM helpers (same as runner)
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, system_instruction: str = "", temperature: float = 0.0,
                max_tokens: int = 1000, model: str = MODEL) -> str:
    """Call Gemini via google.genai with retries."""
    config = genai.types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(5):
        try:
            response = gclient.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            wait = 2 ** attempt
            if attempt < 4:
                print(f"    Gemini error (attempt {attempt+1}): {e}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    return ""


def call_gemini_eval(prompt: str) -> str:
    """Call Gemini for evaluation (LLM-as-judge)."""
    config = genai.types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=50,
    )
    for attempt in range(5):
        try:
            response = gclient.models.generate_content(
                model=EVAL_MODEL,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception:
            time.sleep(2 ** attempt)
    return "no"


# ---------------------------------------------------------------------------
# Session formatting
# ---------------------------------------------------------------------------

def format_session_for_ingestion(session: list[dict], session_date: str) -> str:
    lines = [f"[Date: {session_date}]"]
    for turn in session:
        role = turn["role"].capitalize()
        content = turn["content"].strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Memory System: User as Code
# ---------------------------------------------------------------------------

class UserAsCodeSystem:
    NAME = "user_as_code"

    def __init__(self):
        self.profile_code = ""

    def reset(self):
        self.profile_code = ""

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        batch_size = 15
        for i in range(0, len(sessions), batch_size):
            batch_sessions = sessions[i:i + batch_size]
            batch_dates = dates[i:i + batch_size]

            session_texts = []
            for session, date in zip(batch_sessions, batch_dates):
                text = format_session_for_ingestion(session, date)
                session_texts.append(text)

            combined = "\n\n---\n\n".join(session_texts)

            prompt = f"""Analyze the following chat sessions between a user and an assistant.
Extract ALL personal facts, preferences, life events, relationships, plans,
and any other information about the user.

Existing user profile (if any):
```python
{self.profile_code if self.profile_code else "# Empty -- no facts yet"}
```

New chat sessions to process:
{combined}

Update the user profile by incorporating any new facts from these sessions.
Output ONLY valid Python code that represents the user's full profile as
structured data. Use dataclasses or plain dicts. Include dates where mentioned.
Preserve ALL existing facts and add new ones. If a fact is updated (e.g., user
moved to a new city), keep both the old and new value with dates.

Output format -- respond with ONLY Python code, no markdown fences:
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# User Profile -- auto-extracted from chat history
..."""

            try:
                result = call_gemini(prompt, max_tokens=4000)
                if result.startswith("```"):
                    lines = result.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    result = "\n".join(lines)
                self.profile_code = result
            except Exception as e:
                print(f"    UaC extraction error: {e}")

    def answer_question(self, question: str, question_date: str) -> str:
        system = """You are the user's personal AI assistant. You have access to
the user's structured profile extracted from past conversations.
Answer the question based on the information in the profile.
If the information is not available in the profile, say so clearly.
Be concise and direct."""

        prompt = f"""User Profile (Python code representation):
```python
{self.profile_code if self.profile_code else "# No profile data available"}
```

Current Date: {question_date}
Question: {question}

Answer:"""

        return call_gemini(prompt, system_instruction=system, max_tokens=500)


# ---------------------------------------------------------------------------
# Memory System: Mem0
# ---------------------------------------------------------------------------

class Mem0System:
    NAME = "mem0"

    def __init__(self):
        from mem0 import Memory
        self.memory = Memory()
        self.user_id = None

    def reset(self):
        if self.user_id:
            try:
                self.memory.delete_all(user_id=self.user_id)
            except Exception:
                pass
        self.user_id = f"longmemeval_strat_{int(time.time())}"

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        for session, date in zip(sessions, dates):
            messages = []
            for turn in session:
                messages.append({
                    "role": turn["role"],
                    "content": f"[{date}] {turn['content']}",
                })
            try:
                self.memory.add(messages, user_id=self.user_id)
            except Exception as e:
                print(f"    Mem0 add error: {e}")

    def answer_question(self, question: str, question_date: str) -> str:
        try:
            search_results = self.memory.search(question, user_id=self.user_id)
            memories = search_results.get("results", [])
        except Exception as e:
            memories = []
            print(f"    Mem0 search error: {e}")

        try:
            all_results = self.memory.get_all(user_id=self.user_id)
            all_memories = all_results.get("results", [])
        except Exception:
            all_memories = []

        seen = set()
        memory_texts = []
        for m in memories + all_memories:
            text = m.get("memory", str(m)) if isinstance(m, dict) else str(m)
            if text not in seen:
                seen.add(text)
                memory_texts.append(text)

        memory_str = "\n".join(f"- {t}" for t in memory_texts) if memory_texts else "No memories found."

        system = """You are the user's personal AI assistant. You have access to
memories stored from past conversations with the user.
Answer the question based on the available memories.
If the information is not available, say so clearly.
Be concise and direct."""

        prompt = f"""Retrieved User Memories ({len(memory_texts)} facts):
{memory_str}

Current Date: {question_date}
Question: {question}

Answer:"""

        return call_gemini(prompt, system_instruction=system, max_tokens=500)


# ---------------------------------------------------------------------------
# Memory System: Full Context Baseline
# ---------------------------------------------------------------------------

class FullContextSystem:
    NAME = "full_context"

    def __init__(self):
        self.history_json = ""

    def reset(self):
        self.history_json = ""

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        all_sessions = []
        for session, date in zip(sessions, dates):
            clean = [{"role": t["role"], "content": t["content"]} for t in session]
            all_sessions.append({"session_date": date, "turns": clean})
        self.history_json = json.dumps(all_sessions, indent=1)

    def answer_question(self, question: str, question_date: str) -> str:
        system = """You are the user's personal AI assistant. You are given the
complete history of past chat sessions with the user.
Answer the question based on the relevant chat history.
First extract relevant information, then reason over it to get the answer.
If the information is not in the history, say so clearly."""

        prompt = f"""History Chats:
{self.history_json}

Current Date: {question_date}
Question: {question}

Answer (first extract relevant information, then give your answer):"""

        return call_gemini(prompt, system_instruction=system, max_tokens=800)


# ---------------------------------------------------------------------------
# Evaluation (LongMemEval's LLM-as-judge protocol)
# ---------------------------------------------------------------------------

def get_anscheck_prompt(question_type: str, question: str, answer: str,
                        hypothesis: str, abstention: bool = False) -> str:
    if not abstention:
        if question_type in ["single-session-user", "single-session-assistant",
                              "multi-session"]:
            template = (
                "I will give you a question, a correct answer, and a response "
                "from a model. Please answer yes if the response contains the "
                "correct answer. Otherwise, answer no. If the response is "
                "equivalent to the correct answer or contains all the "
                "intermediate steps to get the correct answer, you should also "
                "answer yes. If the response only contains a subset of the "
                "information required by the answer, answer no. \n\n"
                "Question: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
        elif question_type == "temporal-reasoning":
            template = (
                "I will give you a question, a correct answer, and a response "
                "from a model. Please answer yes if the response contains the "
                "correct answer. Otherwise, answer no. If the response is "
                "equivalent to the correct answer or contains all the "
                "intermediate steps to get the correct answer, you should also "
                "answer yes. If the response only contains a subset of the "
                "information required by the answer, answer no. In addition, "
                "do not penalize off-by-one errors for the number of days. If "
                "the question asks for the number of days/weeks/months, etc., "
                "and the model makes off-by-one errors (e.g., predicting 19 "
                "days when the answer is 18), the model's response is still "
                "correct. \n\n"
                "Question: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
        elif question_type == "knowledge-update":
            template = (
                "I will give you a question, a correct answer, and a response "
                "from a model. Please answer yes if the response contains the "
                "correct answer. Otherwise, answer no. If the response contains "
                "some previous information along with an updated answer, the "
                "response should be considered as correct as long as the updated "
                "answer is the required answer.\n\n"
                "Question: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
        elif question_type == "single-session-preference":
            template = (
                "I will give you a question, a rubric for desired personalized "
                "response, and a response from a model. Please answer yes if "
                "the response satisfies the desired response. Otherwise, answer "
                "no. The model does not need to reflect all the points in the "
                "rubric. The response is correct as long as it recalls and "
                "utilizes the user's personal information correctly.\n\n"
                "Question: {}\n\nRubric: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
        else:
            template = (
                "I will give you a question, a correct answer, and a response "
                "from a model. Please answer yes if the response contains the "
                "correct answer. Otherwise, answer no.\n\n"
                "Question: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
    else:
        template = (
            "I will give you an unanswerable question, an explanation, and a "
            "response from a model. Please answer yes if the model correctly "
            "identifies the question as unanswerable. The model could say that "
            "the information is incomplete, or some other information is given "
            "but the asked information is not.\n\n"
            "Question: {}\n\nExplanation: {}\n\nModel Response: {}\n\n"
            "Does the model correctly identify the question as unanswerable? "
            "Answer yes or no only."
        )

    return template.format(question, answer, hypothesis)


def evaluate_answer(entry: dict, hypothesis: str) -> bool:
    question_type = entry["question_type"]
    question = entry["question"]
    answer = entry["answer"]
    is_abstention = "_abs" in entry["question_id"]

    prompt = get_anscheck_prompt(question_type, question, answer, hypothesis,
                                 abstention=is_abstention)
    try:
        eval_response = call_gemini_eval(prompt)
        return "yes" in eval_response.lower()
    except Exception as e:
        print(f"    Eval error: {e}")
        return False


# ---------------------------------------------------------------------------
# System factory
# ---------------------------------------------------------------------------

def create_system(name: str):
    if name == "user_as_code":
        return UserAsCodeSystem()
    elif name == "mem0":
        return Mem0System()
    elif name == "full_context":
        return FullContextSystem()
    else:
        raise ValueError(f"Unknown system: {name}")


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def run_stratified_benchmark(sampled_data: list[dict], system_names: list[str]) -> dict:
    """Run the benchmark on the stratified sample for all systems."""

    # Initialize systems
    systems = {}
    for name in system_names:
        try:
            systems[name] = create_system(name)
            print(f"  {name}: initialized")
        except Exception as e:
            print(f"  {name}: FAILED to initialize -- {e}")

    active_names = list(systems.keys())

    print(f"\n{'='*70}")
    print(f"  LongMemEval Stratified Benchmark")
    print(f"  Systems: {active_names}")
    print(f"  Questions: {len(sampled_data)}")
    print(f"  LLM: {MODEL}  |  Eval LLM: {EVAL_MODEL}")
    print(f"{'='*70}\n")

    results = {name: [] for name in active_names}

    for idx, entry in enumerate(tqdm(sampled_data, desc="Questions")):
        qid = entry["question_id"]
        qtype = entry["question_type"]
        question = entry["question"]
        question_date = entry["question_date"]
        answer = entry["answer"]
        is_abs = "_abs" in qid

        sessions = entry["haystack_sessions"]
        dates = entry["haystack_dates"]

        for sys_name in active_names:
            system = systems[sys_name]

            # Reset and ingest
            system.reset()

            t0 = time.time()
            system.ingest_sessions(sessions, dates)
            ingest_time = time.time() - t0

            # Answer
            t0 = time.time()
            try:
                hypothesis = system.answer_question(question, question_date)
            except Exception as e:
                hypothesis = f"ERROR: {e}"
                print(f"  [{qid}] {sys_name} answer error: {e}")
            answer_time = time.time() - t0

            # Evaluate
            t0 = time.time()
            correct = evaluate_answer(entry, hypothesis)
            eval_time = time.time() - t0

            result = {
                "question_id": qid,
                "question_type": qtype,
                "question": question,
                "answer": answer,
                "hypothesis": hypothesis,
                "correct": correct,
                "is_abstention": is_abs,
                "ingest_time_s": round(ingest_time, 2),
                "answer_time_s": round(answer_time, 2),
                "eval_time_s": round(eval_time, 2),
            }
            results[sys_name].append(result)

            tag = "Y" if correct else "N"
            tqdm.write(f"  [{idx+1:3d}/{len(sampled_data)}] {qid[:16]:16s} "
                       f"{qtype[:24]:24s} {sys_name[:14]:14s} => {tag}  "
                       f"(ingest={ingest_time:.1f}s answer={answer_time:.1f}s)")

            # Rate limiting
            time.sleep(0.3)

    return results


def compute_summary(results: dict) -> dict:
    """Compute per-type and overall accuracy for each system."""
    summary = {}
    for sys_name, sys_results in results.items():
        type_accs = {}
        for qtype in ALL_QTYPES:
            scores = [r["correct"] for r in sys_results if r["question_type"] == qtype]
            if scores:
                type_accs[qtype] = {
                    "accuracy": round(float(np.mean(scores)), 4),
                    "correct": sum(scores),
                    "total": len(scores),
                }
        all_scores = [r["correct"] for r in sys_results]
        summary[sys_name] = {
            "overall_accuracy": round(float(np.mean(all_scores)), 4) if all_scores else 0,
            "overall_correct": sum(all_scores),
            "overall_total": len(all_scores),
            "per_type": type_accs,
        }
    return summary


def print_comparison_table(summary: dict):
    """Print a nice comparison table."""
    sys_names = list(summary.keys())

    # Short labels for question types
    short = {
        "single-session-user": "single-user",
        "single-session-assistant": "single-asst",
        "single-session-preference": "single-pref",
        "multi-session": "multi-sess",
        "temporal-reasoning": "temporal",
        "knowledge-update": "know-update",
    }

    print(f"\n{'='*90}")
    print(f"  LONGMEMEVAL STRATIFIED RESULTS  (10 questions per type, 60 total)")
    print(f"{'='*90}\n")

    # Header
    header = f"  {'System':<16}"
    for qtype in ALL_QTYPES:
        header += f" {short[qtype]:>11}"
    header += f" {'Overall':>9}"
    print(header)
    print(f"  {'-' * (16 + 12 * len(ALL_QTYPES) + 10)}")

    for sys_name in sys_names:
        s = summary[sys_name]
        row = f"  {sys_name:<16}"
        for qtype in ALL_QTYPES:
            if qtype in s["per_type"]:
                acc = s["per_type"][qtype]["accuracy"]
                c = s["per_type"][qtype]["correct"]
                t = s["per_type"][qtype]["total"]
                row += f"  {c}/{t} ({acc:.0%})"
            else:
                row += f" {'N/A':>11}"
        oa = s["overall_accuracy"]
        oc = s["overall_correct"]
        ot = s["overall_total"]
        row += f"  {oc}/{ot} ({oa:.0%})"
        print(row)

    print()

    # Also print just accuracy percentages for cleaner view
    print(f"  {'System':<16}", end="")
    for qtype in ALL_QTYPES:
        print(f" {short[qtype]:>11}", end="")
    print(f" {'Overall':>9}")
    print(f"  {'-' * (16 + 12 * len(ALL_QTYPES) + 10)}")

    for sys_name in sys_names:
        s = summary[sys_name]
        row = f"  {sys_name:<16}"
        for qtype in ALL_QTYPES:
            if qtype in s["per_type"]:
                acc = s["per_type"][qtype]["accuracy"]
                row += f" {acc:>10.1%}"
            else:
                row += f" {'N/A':>11}"
        row += f" {s['overall_accuracy']:>8.1%}"
        print(row)

    print()


def save_results(results: dict, summary: dict, sampled_data: list[dict]):
    """Save results to the canonical output path."""
    output_path = RESULTS_DIR / "longmemeval_stratified_results.json"

    # Also save a timestamped copy
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        "benchmark": "LongMemEval_Oracle_Stratified",
        "model": MODEL,
        "eval_model": EVAL_MODEL,
        "timestamp": ts,
        "seed": SEED,
        "samples_per_type": SAMPLES_PER_TYPE,
        "total_questions": len(sampled_data),
        "question_ids": [e["question_id"] for e in sampled_data],
        "summary": summary,
        "detailed_results": {
            name: [
                {k: (int(v) if isinstance(v, (np.integer,)) else
                     float(v) if isinstance(v, (np.floating,)) else v)
                 for k, v in r.items()}
                for r in res
            ]
            for name, res in results.items()
        },
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Results saved: {output_path}")

    # Also save timestamped copy
    ts_path = RESULTS_DIR / f"longmemeval_stratified_{ts}.json"
    with open(ts_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Timestamped copy: {ts_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print(f"LongMemEval Stratified Evaluation")
    print(f"Dataset: {DATASET_PATH}")
    print()

    # Load and sample
    sampled_data = load_and_sample(DATASET_PATH)

    # Save sampled questions for reproducibility
    sample_path = RESULTS_DIR / "longmemeval_stratified_sample.json"
    with open(sample_path, "w") as f:
        json.dump([{"question_id": e["question_id"], "question_type": e["question_type"],
                     "question": e["question"], "answer": e["answer"]}
                    for e in sampled_data], f, indent=2)
    print(f"  Sample manifest saved: {sample_path}\n")

    # Run benchmark
    print(f"Initializing systems...")
    results = run_stratified_benchmark(sampled_data, SYSTEM_NAMES)

    # Compute and display results
    summary = compute_summary(results)
    print_comparison_table(summary)

    # Save
    save_results(results, summary, sampled_data)

    # Final per-system details
    for sys_name in results:
        s = summary[sys_name]
        print(f"\n  {sys_name}:")
        avg_ingest = np.mean([r["ingest_time_s"] for r in results[sys_name]])
        avg_answer = np.mean([r["answer_time_s"] for r in results[sys_name]])
        print(f"    Avg ingest: {avg_ingest:.1f}s  |  Avg answer: {avg_answer:.1f}s")
        for qtype in ALL_QTYPES:
            if qtype in s["per_type"]:
                pt = s["per_type"][qtype]
                print(f"    {qtype}: {pt['correct']}/{pt['total']} = {pt['accuracy']:.1%}")


if __name__ == "__main__":
    main()
