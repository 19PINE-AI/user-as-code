"""
LongMemEval Benchmark Runner
=============================
Evaluates memory systems on the LongMemEval benchmark (500 curated questions
over 115K-token chat histories testing five long-term memory abilities).

Supported systems:
  - user_as_code   : Extracts structured Python user profile from chat sessions
  - mem0           : Mem0 memory system (uses OpenAI under the hood)
  - full_context   : Stuffs all chat history into the LLM context window

Evaluation uses LongMemEval's LLM-as-judge protocol (per-category accuracy).

Usage:
    python longmemeval_runner.py --system user_as_code --limit 10
    python longmemeval_runner.py --system mem0 --limit 10
    python longmemeval_runner.py --system full_context --limit 10
    python longmemeval_runner.py --system all --limit 10
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from tqdm import tqdm

from google import genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
EVAL_MODEL = "gemini-3-flash-preview"  # for LLM-as-judge answer checking

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "longmemeval"
DATA_FILE = BENCHMARKS_DIR / "data" / "longmemeval_s_cleaned.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

gclient = genai.Client()

# Question type categories for reporting (maps to LongMemEval's five abilities)
ABILITY_MAP = {
    "single-session-user": "Information Extraction",
    "single-session-assistant": "Information Extraction",
    "single-session-preference": "Information Extraction",
    "multi-session": "Multi-Session Reasoning",
    "knowledge-update": "Knowledge Updates",
    "temporal-reasoning": "Temporal Reasoning",
    # abstention is detected via question_id suffix "_abs"
}

ALL_QTYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "temporal-reasoning",
    "knowledge-update",
]


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset(path: Path = DATA_FILE, limit: int | None = None) -> list[dict]:
    """Load LongMemEval_S dataset."""
    if not path.exists():
        print(f"ERROR: Dataset not found at {path}")
        print("Run the download commands from the LongMemEval README:")
        print(f"  cd {path.parent}")
        print("  wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned"
              "/resolve/main/longmemeval_s_cleaned.json")
        sys.exit(1)
    data = json.load(open(path))
    if limit:
        data = data[:limit]
    print(f"Loaded {len(data)} questions from {path.name}")
    return data


def format_session_for_ingestion(session: list[dict], session_date: str) -> str:
    """Format a single chat session for feeding into memory systems."""
    lines = [f"[Date: {session_date}]"]
    for turn in session:
        role = turn["role"].capitalize()
        content = turn["content"].strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def format_history_json(entry: dict, max_sessions: int = 1000) -> str:
    """Format full chat history as JSON (for full-context baseline)."""
    sessions = []
    for date, sid, session in zip(
        entry["haystack_dates"],
        entry["haystack_session_ids"],
        entry["haystack_sessions"],
    ):
        clean_session = []
        for turn in session:
            clean_turn = {"role": turn["role"], "content": turn["content"]}
            clean_session.append(clean_turn)
        sessions.append({
            "session_date": date,
            "session_id": sid,
            "turns": clean_session,
        })
    sessions = sessions[-max_sessions:]
    return json.dumps(sessions, indent=1)


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, system_instruction: str = "", temperature: float = 0.0,
                max_tokens: int = 1000) -> str:
    """Call Gemini via google.genai."""
    config = genai.types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(3):
        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                raise
    return ""


def call_gemini_eval(prompt: str) -> str:
    """Call Gemini for evaluation (LLM-as-judge)."""
    config = genai.types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=50,
    )
    for attempt in range(3):
        try:
            response = gclient.models.generate_content(
                model=EVAL_MODEL,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception:
            time.sleep(1)
    return "no"


# ---------------------------------------------------------------------------
# Memory System: User as Code
# ---------------------------------------------------------------------------

class UserAsCodeSystem:
    """
    Extracts structured facts from chat sessions into a Python-code user
    profile, then uses the profile as context for answering questions.

    The profile is built incrementally: each batch of sessions is summarized
    by the LLM into a structured Python representation, which is then merged
    into the running profile.
    """

    NAME = "user_as_code"

    def __init__(self):
        self.profile_code = ""

    def reset(self):
        self.profile_code = ""

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        """Process all chat sessions and build a User-as-Code profile."""
        # Feed sessions in chronological batches to build the profile.
        # Larger batches = fewer API calls but larger prompts.
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
                # Strip markdown code fences if present
                if result.startswith("```"):
                    lines = result.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    result = "\n".join(lines)
                self.profile_code = result
            except Exception as e:
                print(f"    UaC extraction error: {e}")

    def answer_question(self, question: str, question_date: str) -> str:
        """Answer a question using the extracted user profile."""
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
    """
    Uses Mem0 to store and retrieve user memories from chat sessions.
    Mem0 automatically extracts and indexes facts from conversations.
    """

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
        self.user_id = f"longmemeval_{int(time.time())}"

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        """Feed chat sessions into Mem0."""
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
        """Retrieve memories and answer the question."""
        # Search for relevant memories
        try:
            search_results = self.memory.search(question, user_id=self.user_id)
            memories = search_results.get("results", [])
        except Exception as e:
            memories = []
            print(f"    Mem0 search error: {e}")

        # Also get all memories for comprehensive coverage
        try:
            all_results = self.memory.get_all(user_id=self.user_id)
            all_memories = all_results.get("results", [])
        except Exception:
            all_memories = []

        # Combine and deduplicate
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
    """
    Baseline that stuffs the entire chat history into the LLM context window.
    No memory extraction -- relies on the LLM's ability to find information
    in the raw history. This is the "long-context" approach.
    """

    NAME = "full_context"

    def __init__(self):
        self.history_json = ""

    def reset(self):
        self.history_json = ""

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        """Store raw history -- no processing needed."""
        all_sessions = []
        for session, date in zip(sessions, dates):
            clean = [{"role": t["role"], "content": t["content"]} for t in session]
            all_sessions.append({"session_date": date, "turns": clean})
        self.history_json = json.dumps(all_sessions, indent=1)

    def answer_question(self, question: str, question_date: str) -> str:
        """Answer using the full chat history in context."""
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
    """
    Build the LLM-as-judge prompt -- mirrors LongMemEval's evaluate_qa.py.
    """
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
            # Fallback to generic
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
    """Evaluate a single answer using LLM-as-judge."""
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
# Main benchmark runner
# ---------------------------------------------------------------------------

def create_system(name: str):
    """Factory for memory systems."""
    if name == "user_as_code":
        return UserAsCodeSystem()
    elif name == "mem0":
        return Mem0System()
    elif name == "full_context":
        return FullContextSystem()
    else:
        raise ValueError(f"Unknown system: {name}")


def run_benchmark(system_names: list[str], data: list[dict],
                  save_hypotheses: bool = True) -> dict:
    """Run the full benchmark for one or more systems."""

    results = {name: [] for name in system_names}
    hypotheses = {name: [] for name in system_names}

    systems = {}
    for name in system_names:
        try:
            systems[name] = create_system(name)
            print(f"  {name}: initialized")
        except Exception as e:
            print(f"  {name}: FAILED to initialize -- {e}")

    print(f"\n{'='*70}")
    print(f"  LongMemEval Benchmark")
    print(f"  Systems: {list(systems.keys())}")
    print(f"  Questions: {len(data)}")
    print(f"  LLM: {MODEL}")
    print(f"  Eval LLM: {EVAL_MODEL}")
    print(f"{'='*70}\n")

    for idx, entry in enumerate(tqdm(data, desc="Questions")):
        qid = entry["question_id"]
        qtype = entry["question_type"]
        question = entry["question"]
        question_date = entry["question_date"]
        answer = entry["answer"]
        is_abs = "_abs" in qid

        sessions = entry["haystack_sessions"]
        dates = entry["haystack_dates"]

        for sys_name, system in systems.items():
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
            hypotheses[sys_name].append({
                "question_id": qid,
                "hypothesis": hypothesis,
            })

            tag = "Y" if correct else "N"
            tqdm.write(f"  [{idx+1:3d}] {qid[:12]:12s} {qtype[:20]:20s} "
                       f"{sys_name[:10]:10s} => {tag}  ({answer_time:.1f}s)")

            # Rate limiting
            time.sleep(0.3)

    # Save hypotheses (compatible with LongMemEval's evaluate_qa.py)
    if save_hypotheses:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for sys_name, hyps in hypotheses.items():
            hyp_file = RESULTS_DIR / f"longmemeval_{sys_name}_{ts}.jsonl"
            with open(hyp_file, "w") as f:
                for h in hyps:
                    f.write(json.dumps(h) + "\n")
            print(f"  Hypotheses saved: {hyp_file}")

    return results


def print_results(results: dict, data: list[dict]):
    """Print per-category and overall accuracy."""
    qid2entry = {e["question_id"]: e for e in data}

    print(f"\n{'='*70}")
    print(f"  LONGMEMEVAL RESULTS")
    print(f"{'='*70}\n")

    for sys_name, sys_results in results.items():
        print(f"\n  --- {sys_name} ---\n")

        # Per question type
        type2scores = {t: [] for t in ALL_QTYPES}
        abstention_scores = []
        all_scores = []

        for r in sys_results:
            qtype = r["question_type"]
            correct = 1 if r["correct"] else 0
            type2scores[qtype].append(correct)
            all_scores.append(correct)
            if r["is_abstention"]:
                abstention_scores.append(correct)

        print(f"  {'Question Type':<30} {'Accuracy':>10} {'Count':>8}")
        print(f"  {'-'*50}")

        task_accs = []
        for qtype in ALL_QTYPES:
            scores = type2scores[qtype]
            if scores:
                acc = np.mean(scores)
                task_accs.append(acc)
                print(f"  {qtype:<30} {acc:>10.4f} {len(scores):>8}")
            else:
                print(f"  {qtype:<30} {'N/A':>10} {0:>8}")

        print(f"  {'-'*50}")
        if all_scores:
            print(f"  {'Overall Accuracy':<30} {np.mean(all_scores):>10.4f} "
                  f"{len(all_scores):>8}")
        if task_accs:
            print(f"  {'Task-Averaged Accuracy':<30} {np.mean(task_accs):>10.4f}")
        if abstention_scores:
            print(f"  {'Abstention Accuracy':<30} "
                  f"{np.mean(abstention_scores):>10.4f} "
                  f"{len(abstention_scores):>8}")

        # By ability group
        print(f"\n  By Ability:")
        ability2scores = {}
        for r in sys_results:
            if r["is_abstention"]:
                ability = "Abstention"
            else:
                ability = ABILITY_MAP.get(r["question_type"], r["question_type"])
            ability2scores.setdefault(ability, []).append(
                1 if r["correct"] else 0
            )
        for ability, scores in sorted(ability2scores.items()):
            print(f"    {ability:<30} {np.mean(scores):>8.4f} ({len(scores)})")

        # Timing
        avg_ingest = np.mean([r["ingest_time_s"] for r in sys_results])
        avg_answer = np.mean([r["answer_time_s"] for r in sys_results])
        print(f"\n  Avg ingest time: {avg_ingest:.2f}s")
        print(f"  Avg answer time: {avg_answer:.2f}s")

    # Side-by-side comparison
    if len(results) > 1:
        print(f"\n\n{'='*70}")
        print(f"  COMPARISON")
        print(f"{'='*70}\n")

        sys_names = list(results.keys())
        header = f"  {'Question Type':<30}"
        for sn in sys_names:
            header += f" {sn[:12]:>12}"
        print(header)
        print(f"  {'-' * (30 + 13 * len(sys_names))}")

        for qtype in ALL_QTYPES:
            row = f"  {qtype:<30}"
            for sn in sys_names:
                scores = [
                    1 if r["correct"] else 0
                    for r in results[sn]
                    if r["question_type"] == qtype
                ]
                if scores:
                    row += f" {np.mean(scores):>12.4f}"
                else:
                    row += f" {'N/A':>12}"
            print(row)

        row = f"  {'Overall':<30}"
        for sn in sys_names:
            acc = np.mean([1 if r["correct"] else 0 for r in results[sn]])
            row += f" {acc:>12.4f}"
        print(f"  {'-' * (30 + 13 * len(sys_names))}")
        print(row)


def save_full_results(results: dict):
    """Save detailed results to JSON."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"longmemeval_results_{ts}.json"

    # Convert numpy types for JSON serialization
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    summary = {}
    for sys_name, sys_results in results.items():
        all_correct = [r["correct"] for r in sys_results]
        type_accs = {}
        for qtype in ALL_QTYPES:
            scores = [r["correct"] for r in sys_results if r["question_type"] == qtype]
            if scores:
                type_accs[qtype] = round(float(np.mean(scores)), 4)
        summary[sys_name] = {
            "overall_accuracy": round(float(np.mean(all_correct)), 4),
            "per_type_accuracy": type_accs,
            "n_questions": len(sys_results),
        }

    output = {
        "benchmark": "LongMemEval_S",
        "model": MODEL,
        "eval_model": EVAL_MODEL,
        "timestamp": ts,
        "summary": summary,
        "detailed_results": {
            name: [
                {k: convert(v) for k, v in r.items()}
                for r in res
            ]
            for name, res in results.items()
        },
    }
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, default=convert)
    print(f"\n  Full results saved: {out_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LongMemEval benchmark runner for memory systems"
    )
    parser.add_argument(
        "--system", type=str, default="user_as_code",
        choices=["user_as_code", "mem0", "full_context", "all"],
        help="Memory system to evaluate (default: user_as_code)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of questions to evaluate (default: all 500)"
    )
    parser.add_argument(
        "--data-file", type=str, default=None,
        help="Path to LongMemEval data file (default: longmemeval_s_cleaned.json)"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Skip saving hypothesis and result files"
    )
    args = parser.parse_args()

    # Load data
    data_path = Path(args.data_file) if args.data_file else DATA_FILE
    data = load_dataset(data_path, limit=args.limit)

    # Determine systems
    if args.system == "all":
        system_names = ["user_as_code", "mem0", "full_context"]
    else:
        system_names = [args.system]

    print(f"\nInitializing systems...")
    results = run_benchmark(
        system_names, data,
        save_hypotheses=not args.no_save,
    )

    print_results(results, data)
    if not args.no_save:
        save_full_results(results)


if __name__ == "__main__":
    main()
