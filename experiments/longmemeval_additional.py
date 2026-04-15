"""
LongMemEval Additional Benchmark Runner
========================================
Evaluates A-MEM and ENGRAM memory systems on a stratified sample of 60
questions from the LongMemEval oracle dataset (10 per question type).

Usage:
    python -u longmemeval_additional.py
"""

import json
import os
import random
import signal
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from google import genai

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

def log(msg: str):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
EVAL_MODEL = "gemini-3-flash-preview"

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "longmemeval"
DATA_FILE = BENCHMARKS_DIR / "data" / "longmemeval_oracle.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

RESULTS_FILE = RESULTS_DIR / "longmemeval_additional_results.json"

gclient = genai.Client()

ALL_QTYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "temporal-reasoning",
    "knowledge-update",
]

SAMPLE_PER_TYPE = 10
RANDOM_SEED = 42

# Timeout for A-MEM add_note per session (seconds)
AMEM_ADD_TIMEOUT = 60
# Max characters per session text for A-MEM (to limit OpenAI token usage)
AMEM_MAX_SESSION_CHARS = 4000


# ---------------------------------------------------------------------------
# Dataset loading & stratified sampling
# ---------------------------------------------------------------------------

def load_dataset(path: Path = DATA_FILE) -> list[dict]:
    if not path.exists():
        log(f"ERROR: Dataset not found at {path}")
        sys.exit(1)
    data = json.load(open(path))
    log(f"Loaded {len(data)} questions from {path.name}")
    return data


def stratified_sample(data: list[dict], per_type: int = SAMPLE_PER_TYPE,
                       seed: int = RANDOM_SEED) -> list[dict]:
    """Select a stratified sample: `per_type` questions from each question type."""
    rng = random.Random(seed)
    by_type = defaultdict(list)
    for entry in data:
        by_type[entry["question_type"]].append(entry)

    sample = []
    for qtype in ALL_QTYPES:
        pool = by_type[qtype]
        if len(pool) < per_type:
            log(f"  WARNING: only {len(pool)} questions for {qtype}, using all")
            sample.extend(pool)
        else:
            sample.extend(rng.sample(pool, per_type))

    rng.shuffle(sample)
    log(f"Stratified sample: {len(sample)} questions "
        f"({per_type} per type x {len(ALL_QTYPES)} types)")
    return sample


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, system_instruction: str = "",
                temperature: float = 0.2, max_tokens: int = 500) -> str:
    config = genai.types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(3):
        try:
            response = gclient.models.generate_content(
                model=MODEL, contents=prompt, config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
    return ""


def call_gemini_eval(prompt: str) -> str:
    config = genai.types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=50,
    )
    for attempt in range(3):
        try:
            response = gclient.models.generate_content(
                model=EVAL_MODEL, contents=prompt, config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception:
            time.sleep(2 ** attempt)
    return "no"


# ---------------------------------------------------------------------------
# Session formatting
# ---------------------------------------------------------------------------

def format_session_text(session: list[dict], session_date: str) -> str:
    """Format a single chat session for feeding into memory systems."""
    lines = [f"[Date: {session_date}]"]
    for turn in session:
        role = turn["role"].capitalize()
        content = turn["content"].strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, keeping the beginning."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[... truncated ...]"


# ---------------------------------------------------------------------------
# LLM-as-judge evaluation (mirrors LongMemEval protocol)
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
        log(f"    Eval error: {e}")
        return False


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=1)

def run_with_timeout(func, timeout_sec, *args, **kwargs):
    """Run func(*args, **kwargs) with a timeout. Returns (result, error_or_None)."""
    future = _executor.submit(func, *args, **kwargs)
    try:
        result = future.result(timeout=timeout_sec)
        return result, None
    except FuturesTimeoutError:
        # We cannot truly cancel the thread, but we move on
        return None, "TIMEOUT"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Memory System: A-MEM
# ---------------------------------------------------------------------------

class AMemSystem:
    """Wrapper around A-MEM (AgenticMemorySystem)."""

    NAME = "amem"

    def __init__(self):
        from agentic_memory.memory_system import AgenticMemorySystem
        self._cls = AgenticMemorySystem
        self.memory = None

    def reset(self):
        """Create a fresh A-MEM instance (wipes all state)."""
        self.memory = self._cls(
            model_name="all-MiniLM-L6-v2",
            llm_backend="openai",
            llm_model="gpt-4o-mini",
        )

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        """Feed chat sessions into A-MEM as individual notes."""
        for i, (session, date) in enumerate(zip(sessions, dates)):
            text = format_session_text(session, date)
            text = truncate_text(text, AMEM_MAX_SESSION_CHARS)
            try:
                _, err = run_with_timeout(
                    self.memory.add_note, AMEM_ADD_TIMEOUT, text, date
                )
                if err:
                    log(f"    A-MEM add session {i} error: {err}")
            except Exception as e:
                log(f"    A-MEM add session {i} error: {e}")

    def retrieve(self, question: str) -> str:
        """Search A-MEM and return formatted context string."""
        try:
            results = self.memory.search_agentic(question, k=10)
            if not results:
                return "No relevant memories found."
            memory_texts = []
            for r in results:
                content = r.get("content", "")
                if content:
                    memory_texts.append(content)
            if not memory_texts:
                return "No relevant memories found."
            return "\n\n---\n\n".join(memory_texts)
        except Exception as e:
            log(f"    A-MEM search error: {e}")
            return "Error retrieving memories."

    def answer_question(self, question: str, question_date: str) -> str:
        context = self.retrieve(question)

        system = (
            "You are the user's personal AI assistant. You have access to "
            "memories retrieved from past conversations with the user. "
            "Answer the question based on the available memories. "
            "If the information is not available, say so clearly. "
            "Be concise and direct."
        )

        prompt = f"""Retrieved Memories:
{context}

Current Date: {question_date}
Question: {question}

Answer:"""

        return call_gemini(prompt, system_instruction=system, max_tokens=500)


# ---------------------------------------------------------------------------
# Memory System: ENGRAM
# ---------------------------------------------------------------------------

class EngramSystem:
    """Wrapper around Engram memory system."""

    NAME = "engram"

    def __init__(self):
        from engram.client import Memory
        self._cls = Memory
        self.memory = None
        self._ns_counter = 0

    def reset(self):
        """Create a fresh Engram instance with a unique namespace."""
        self._ns_counter += 1
        ns = f"longmemeval_{int(time.time())}_{self._ns_counter}"
        self.memory = self._cls(namespace=ns)

    def ingest_sessions(self, sessions: list[dict], dates: list[str]):
        """Feed chat sessions into Engram as stored memories."""
        for session, date in zip(sessions, dates):
            text = format_session_text(session, date)
            try:
                self.memory.store(text)
            except Exception as e:
                log(f"    Engram store error: {e}")

    def retrieve(self, question: str) -> str:
        """Search Engram and return formatted context string."""
        memory_texts = []

        # 1. Text search
        try:
            search_results = self.memory.search(question, limit=10)
            for sr in search_results:
                content = sr.memory.content if hasattr(sr, "memory") else str(sr)
                if content and content not in memory_texts:
                    memory_texts.append(content)
        except Exception as e:
            log(f"    Engram search error: {e}")

        # 2. Also list recent memories for broader coverage
        try:
            all_memories = self.memory.list(limit=50)
            for m in all_memories:
                content = m.content if hasattr(m, "content") else str(m)
                if content and content not in memory_texts:
                    memory_texts.append(content)
        except Exception as e:
            log(f"    Engram list error: {e}")

        if not memory_texts:
            return "No relevant memories found."
        return "\n\n---\n\n".join(memory_texts)

    def answer_question(self, question: str, question_date: str) -> str:
        context = self.retrieve(question)

        system = (
            "You are the user's personal AI assistant. You have access to "
            "memories retrieved from past conversations with the user. "
            "Answer the question based on the available memories. "
            "If the information is not available, say so clearly. "
            "Be concise and direct."
        )

        prompt = f"""Retrieved Memories:
{context}

Current Date: {question_date}
Question: {question}

Answer:"""

        return call_gemini(prompt, system_instruction=system, max_tokens=500)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def save_incremental(results: dict, sample: list[dict]):
    """Save results so far (for crash recovery)."""
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = {}
        for sys_name, sys_results in results.items():
            if not sys_results:
                continue
            all_correct = [r["correct"] for r in sys_results]
            type_accs = {}
            for qtype in ALL_QTYPES:
                scores = [r["correct"] for r in sys_results
                          if r["question_type"] == qtype]
                if scores:
                    type_accs[qtype] = round(sum(scores) / len(scores), 4)
            summary[sys_name] = {
                "overall_accuracy": round(sum(all_correct) / len(all_correct), 4)
                    if all_correct else 0,
                "per_type_accuracy": type_accs,
                "n_questions": len(sys_results),
            }

        output = {
            "benchmark": "LongMemEval_Oracle",
            "model": MODEL,
            "eval_model": EVAL_MODEL,
            "timestamp": ts,
            "sample_size": SAMPLE_PER_TYPE * len(ALL_QTYPES),
            "sample_per_type": SAMPLE_PER_TYPE,
            "random_seed": RANDOM_SEED,
            "summary": summary,
            "detailed_results": results,
        }

        with open(RESULTS_FILE, "w") as f:
            json.dump(output, f, indent=2, default=str)
    except Exception:
        pass  # don't let save failures break the run


def run_evaluation():
    log(f"\n{'='*70}")
    log(f"  LongMemEval Additional Benchmark")
    log(f"  Systems: A-MEM, ENGRAM")
    log(f"  LLM: {MODEL}  |  Eval LLM: {EVAL_MODEL}")
    log(f"{'='*70}\n")

    # Load and sample
    data = load_dataset()
    sample = stratified_sample(data)

    # Print sample distribution
    type_counts = defaultdict(int)
    for e in sample:
        type_counts[e["question_type"]] += 1
    log("\nSample distribution:")
    for qt in ALL_QTYPES:
        log(f"  {qt}: {type_counts[qt]}")
    log("")

    # Initialize systems
    systems = {}
    for SysClass in [AMemSystem, EngramSystem]:
        try:
            sys_obj = SysClass()
            systems[sys_obj.NAME] = sys_obj
            log(f"  {sys_obj.NAME}: initialized")
        except Exception as e:
            log(f"  {SysClass.NAME}: FAILED to initialize -- {e}")
            traceback.print_exc()

    if not systems:
        log("ERROR: No systems initialized. Exiting.")
        sys.exit(1)

    # Run evaluation
    results = {name: [] for name in systems}
    total = len(sample)

    for idx, entry in enumerate(sample):
        qid = entry["question_id"]
        qtype = entry["question_type"]
        question = entry["question"]
        question_date = entry["question_date"]
        answer = entry["answer"]
        is_abs = "_abs" in qid

        sessions = entry["haystack_sessions"]
        dates = entry["haystack_dates"]

        n_sessions = len(sessions)
        log(f"\n  Q {idx+1}/{total}: {qid[:16]} ({qtype}, {n_sessions} sessions)")

        for sys_name, system in systems.items():
            # Reset memory for this question
            system.reset()

            # Ingest
            t0 = time.time()
            try:
                system.ingest_sessions(sessions, dates)
            except Exception as e:
                log(f"    [{qid}] {sys_name} ingest error: {e}")
            ingest_time = time.time() - t0

            # Answer
            t0 = time.time()
            try:
                hypothesis = system.answer_question(question, question_date)
            except Exception as e:
                hypothesis = f"ERROR: {e}"
                log(f"    [{qid}] {sys_name} answer error: {e}")
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
            log(f"    {sys_name:8s} => {tag}  "
                f"(ingest={ingest_time:.1f}s, answer={answer_time:.1f}s)")

            # Rate limiting for Gemini API
            time.sleep(0.5)

        # Save incrementally every 5 questions
        if (idx + 1) % 5 == 0:
            save_incremental(results, sample)
            log(f"  [checkpoint saved at {idx+1}/{total}]")

    # Print and save final results
    print_results(results)
    save_results(results)


def print_results(results: dict):
    log(f"\n{'='*70}")
    log(f"  RESULTS")
    log(f"{'='*70}")

    for sys_name, sys_results in results.items():
        log(f"\n  --- {sys_name.upper()} ---\n")

        type2scores = {t: [] for t in ALL_QTYPES}
        all_scores = []

        for r in sys_results:
            score = 1 if r["correct"] else 0
            type2scores[r["question_type"]].append(score)
            all_scores.append(score)

        log(f"  {'Question Type':<30} {'Accuracy':>10} {'Correct':>8} {'Total':>6}")
        log(f"  {'-'*56}")

        for qtype in ALL_QTYPES:
            scores = type2scores[qtype]
            if scores:
                acc = sum(scores) / len(scores)
                log(f"  {qtype:<30} {acc:>10.2%} {sum(scores):>8} {len(scores):>6}")
            else:
                log(f"  {qtype:<30} {'N/A':>10} {0:>8} {0:>6}")

        log(f"  {'-'*56}")
        if all_scores:
            overall = sum(all_scores) / len(all_scores)
            log(f"  {'Overall':<30} {overall:>10.2%} "
                f"{sum(all_scores):>8} {len(all_scores):>6}")

        # Timing
        if sys_results:
            avg_ingest = sum(r["ingest_time_s"] for r in sys_results) / len(sys_results)
            avg_answer = sum(r["answer_time_s"] for r in sys_results) / len(sys_results)
            log(f"\n  Avg ingest time: {avg_ingest:.2f}s")
            log(f"  Avg answer time: {avg_answer:.2f}s")

    # Side-by-side comparison
    if len(results) > 1:
        log(f"\n\n{'='*70}")
        log(f"  COMPARISON")
        log(f"{'='*70}\n")

        sys_names = list(results.keys())
        header = f"  {'Question Type':<30}"
        for sn in sys_names:
            header += f" {sn.upper():>12}"
        log(header)
        log(f"  {'-' * (30 + 13 * len(sys_names))}")

        for qtype in ALL_QTYPES:
            row = f"  {qtype:<30}"
            for sn in sys_names:
                scores = [1 if r["correct"] else 0
                          for r in results[sn] if r["question_type"] == qtype]
                if scores:
                    acc = sum(scores) / len(scores)
                    row += f" {acc:>11.2%} "
                else:
                    row += f" {'N/A':>12}"
            log(row)

        row = f"  {'Overall':<30}"
        for sn in sys_names:
            scores = [1 if r["correct"] else 0 for r in results[sn]]
            acc = sum(scores) / len(scores) if scores else 0
            row += f" {acc:>11.2%} "
        log(f"  {'-' * (30 + 13 * len(sys_names))}")
        log(row)


def save_results(results: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    summary = {}
    for sys_name, sys_results in results.items():
        all_correct = [r["correct"] for r in sys_results]
        type_accs = {}
        for qtype in ALL_QTYPES:
            scores = [r["correct"] for r in sys_results
                      if r["question_type"] == qtype]
            if scores:
                type_accs[qtype] = round(sum(scores) / len(scores), 4)
        summary[sys_name] = {
            "overall_accuracy": round(sum(all_correct) / len(all_correct), 4)
                if all_correct else 0,
            "per_type_accuracy": type_accs,
            "n_questions": len(sys_results),
        }

    output = {
        "benchmark": "LongMemEval_Oracle",
        "model": MODEL,
        "eval_model": EVAL_MODEL,
        "timestamp": ts,
        "sample_size": SAMPLE_PER_TYPE * len(ALL_QTYPES),
        "sample_per_type": SAMPLE_PER_TYPE,
        "random_seed": RANDOM_SEED,
        "summary": summary,
        "detailed_results": results,
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)
    log(f"\n  Results saved: {RESULTS_FILE}")


if __name__ == "__main__":
    run_evaluation()
