#!/usr/bin/env python3
"""
Write-Path Extraction Accuracy Evaluation

Measures how accurately an LLM extracts facts from conversations into
structured Python code (the "write path" of User as Code).

Protocol:
1. Take 3 LOCOMO conversations
2. Use Gemini 3 Flash to extract structured facts into Python dataclass code
3. Evaluate extraction quality:
   a. Feed extracted code to LLM, ask it to answer each QA question
   b. Compare against ground-truth answers using token F1
   c. Measure extraction coverage, precision, and compression ratio
"""

import json
import os
import random
import re
import string
import sys
import time
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
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

NUM_CONVERSATIONS = 3

ps = PorterStemmer()

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def normalize_answer(s: str) -> str:
    s = s.replace(",", "")
    s = re_unicode.sub(r'\b(a|an|the|and)\b', ' ', s.lower())
    s = ''.join(ch for ch in s if ch not in string.punctuation)
    return ' '.join(s.split())


def f1_score_single(prediction: str, ground_truth: str) -> float:
    pred_tokens = [ps.stem(w) for w in normalize_answer(prediction).split()]
    gt_tokens = [ps.stem(w) for w in normalize_answer(ground_truth).split()]
    common = Counter(pred_tokens) & Counter(gt_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    if len(pred_tokens) == 0 or len(gt_tokens) == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gt_tokens)
    return (2 * precision * recall) / (precision + recall)


def f1_multi(prediction: str, ground_truth: str) -> float:
    predictions = [p.strip() for p in prediction.split(",")]
    ground_truths = [g.strip() for g in ground_truth.split(",")]
    scores = []
    for gt in ground_truths:
        best = max(f1_score_single(p, gt) for p in predictions)
        scores.append(best)
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_qa_item(prediction: str, qa: dict) -> float:
    category = qa["category"]
    answer = str(qa.get("answer", qa.get("adversarial_answer", "")))

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
# Conversation formatting
# ---------------------------------------------------------------------------

def format_conversation_as_text(conversation: dict) -> str:
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


def count_tokens_approx(text: str) -> int:
    """Approximate token count (words * 1.3 for English)."""
    return int(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# LLM call with timeout/retry
# ---------------------------------------------------------------------------

def call_llm(prompt: str, system: str = "", temperature: float = 0.0,
             max_tokens: int = 4000, max_retries: int = 3) -> str:
    """Call Gemini with retries and error handling.

    Uses thinking_budget=0 to disable Gemini 3's internal thinking,
    which otherwise consumes output tokens and causes truncation.
    """
    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "thinking_config": genai.types.ThinkingConfig(thinking_budget=0),
    }
    if system:
        config_kwargs["system_instruction"] = system

    for attempt in range(max_retries):
        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(**config_kwargs),
            )
            if response and response.text:
                return response.text.strip()
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
        except Exception as e:
            print(f"        LLM call error (attempt {attempt+1}): {e}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
    return ""


# ---------------------------------------------------------------------------
# Write-Path: Extract structured code from conversation
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM = """You are a data engineer who converts conversations into structured Python code.
Read the conversation and extract ALL factual information into a well-organized
Python dataclass representation. Be thorough: every fact mentioned should appear in the code.
Use @dataclass classes, datetime.date for dates, and typed fields."""


def extract_code_from_conversation(conversation: dict) -> str:
    """Extract structured Python code from a conversation using a 2-step approach."""
    speaker_a = conversation.get("speaker_a", "Speaker A")
    speaker_b = conversation.get("speaker_b", "Speaker B")

    # Get all session texts
    session_nums = sorted(set(
        int(k.split("_")[1])
        for k in conversation.keys()
        if k.startswith("session_") and not k.endswith("date_time")
        and isinstance(conversation[k], list)
    ))

    session_texts = []
    for num in session_nums:
        key = f"session_{num}"
        dt_key = f"session_{num}_date_time"
        date_time = conversation.get(dt_key, "")
        lines = [f"[Session {num}, {date_time}]"]
        for turn in conversation[key]:
            line = f"{turn['speaker']}: {turn['text']}"
            if turn.get("blip_caption"):
                line += f" [image: {turn['blip_caption']}]"
            lines.append(line)
        session_texts.append("\n".join(lines))

    # Extract code in batches and concatenate (no LLM merge step).
    # Target ~12k chars per batch for fast API responses.
    full_text = "\n\n".join(session_texts)

    if len(full_text) <= 15000:
        batches = [full_text]
    else:
        # Split into batches of ~12k chars
        batches = []
        current_batch = []
        current_size = 0
        for st in session_texts:
            current_batch.append(st)
            current_size += len(st)
            if current_size > 12000:
                batches.append("\n\n".join(current_batch))
                current_batch = []
                current_size = 0
        if current_batch:
            batches.append("\n\n".join(current_batch))

    code_snippets = []
    for i, batch_text in enumerate(batches):
        print(f"      Extracting code from batch {i+1}/{len(batches)}...", flush=True)

        prompt = f"""Read these conversation sessions between {speaker_a} and {speaker_b}.
Extract ALL facts into Python @dataclass instances. Include every name, date, event,
relationship, preference, plan, location, activity, and opinion.

Conversation:
{batch_text}

Generate Python code with @dataclass schemas and populated instances.
Use datetime.date for dates. Keep it concise but complete:"""

        code = call_llm(prompt, system=EXTRACTION_SYSTEM, temperature=0.2, max_tokens=2500)

        if code:
            # Clean markdown fences
            if "```" in code:
                lines = code.split("\n")
                cleaned = []
                for line in lines:
                    if line.strip().startswith("```"):
                        continue
                    cleaned.append(line)
                code = "\n".join(cleaned)
            code_snippets.append(code)

        time.sleep(0.5)

    if not code_snippets:
        return "# No code extracted\npass"

    # Concatenate snippets (no LLM merge to avoid API hangs)
    return "\n\n# --- Additional extracted facts ---\n\n".join(code_snippets)


# ---------------------------------------------------------------------------
# Answer QA from extracted code
# ---------------------------------------------------------------------------

QA_FROM_CODE_SYSTEM = """You are answering questions about people based on structured Python code
that represents extracted information from their conversations.
Use ONLY the information present in the code to answer. Be concise.
If the information is not present in the code, say "No information available"."""


def answer_from_code(question: str, code: str, qa: dict) -> str:
    """Answer a QA question using only the extracted code."""
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
        prompt = f"""Here is structured Python code representing information from conversations:

```python
{code}
```

Question: {question}
Select the correct answer: (a) {option_a} (b) {option_b}.

Answer with just (a) or (b):"""
    elif category == 2:
        prompt = f"""Here is structured Python code representing information from conversations:

```python
{code}
```

Question: {question} Use dates from the code to answer with an approximate date.

Answer in a short phrase:"""
    else:
        prompt = f"""Here is structured Python code representing information from conversations:

```python
{code}
```

Question: {question}

Answer in a short phrase (use only info from the code above):"""

    answer = call_llm(prompt, system=QA_FROM_CODE_SYSTEM, temperature=0.0, max_tokens=64)

    if not answer:
        return "No information available"

    # Post-process cat5
    if category == 5:
        answer_lower = answer.lower().strip()
        if answer_lower.startswith("(a)") or answer_lower == "a":
            answer = answer_key["a"]
        elif answer_lower.startswith("(b)") or answer_lower == "b":
            answer = answer_key["b"]

    return answer


# ---------------------------------------------------------------------------
# Precision check: detect hallucinated facts
# ---------------------------------------------------------------------------

def check_precision(conversation_text: str, code: str) -> dict:
    """Check if extracted code contains hallucinated facts."""
    # Truncate conversation if too long
    if len(conversation_text) > 12000:
        half = 5500
        conversation_text = (conversation_text[:half]
                             + "\n...[middle truncated]...\n"
                             + conversation_text[-half:])

    # Also truncate code if needed
    code_check = code[:4000] if len(code) > 4000 else code

    prompt = f"""Original conversation:
{conversation_text}

Extracted code:
```python
{code_check}
```

List ONLY the facts in the code that are NOT supported by the conversation.
If all facts are supported, write "ALL FACTS VERIFIED".
Format: "- HALLUCINATED: <description>"."""

    system = """You are a careful fact-checker. Identify facts in the code
that are NOT supported by the conversation. Only flag clear fabrications,
not reasonable inferences."""

    text = call_llm(prompt, system=system, temperature=0.0, max_tokens=1500)

    if not text:
        return {"hallucinated_count": -1, "hallucinated_facts": [], "raw": "Error"}

    if "ALL FACTS VERIFIED" in text.upper():
        return {"hallucinated_count": 0, "hallucinated_facts": [], "raw": text}

    hallucinated = [l.strip() for l in text.split("\n")
                    if "HALLUCINATED" in l.upper() or (l.strip().startswith("- ") and len(l.strip()) > 5)]
    return {
        "hallucinated_count": len(hallucinated),
        "hallucinated_facts": hallucinated[:10],
        "raw": text,
    }


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

CATEGORY_NAMES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}


def run_write_path_eval():
    print("=" * 70)
    print("  Write-Path Extraction Accuracy Evaluation")
    print(f"  Model: {MODEL}")
    print(f"  Conversations: {NUM_CONVERSATIONS}")
    print("=" * 70)

    print(f"\nLoading LOCOMO data from {LOCOMO_DATA}")
    with open(LOCOMO_DATA) as f:
        dataset = json.load(f)
    print(f"  {len(dataset)} conversations available")

    conversations = dataset[:NUM_CONVERSATIONS]

    all_results = []
    conversation_summaries = []

    for conv_idx, sample in enumerate(conversations):
        sid = sample["sample_id"]
        conversation = sample["conversation"]
        qas = sample["qa"]
        speaker_a = conversation.get("speaker_a", "?")
        speaker_b = conversation.get("speaker_b", "?")

        print(f"\n{'='*70}")
        print(f"  Conversation {conv_idx+1}/{NUM_CONVERSATIONS}: {sid}")
        print(f"  Speakers: {speaker_a} & {speaker_b}")
        print(f"  QA pairs: {len(qas)}")
        print(f"{'='*70}")

        # Step 1: Format raw conversation
        conv_text = format_conversation_as_text(conversation)
        conv_tokens = count_tokens_approx(conv_text)
        print(f"  Raw conversation: {len(conv_text)} chars, ~{conv_tokens} tokens")

        # Step 2: Extract structured code
        print(f"\n  Extracting structured code...")
        t0 = time.time()
        extracted_code = extract_code_from_conversation(conversation)
        extraction_time = time.time() - t0
        code_tokens = count_tokens_approx(extracted_code)
        compression_ratio = code_tokens / conv_tokens if conv_tokens > 0 else 0

        print(f"  Extracted code: {len(extracted_code)} chars, ~{code_tokens} tokens")
        print(f"  Compression ratio: {compression_ratio:.2f}x ({code_tokens}/{conv_tokens})")
        print(f"  Extraction time: {extraction_time:.1f}s")

        # Step 3: Check precision
        print(f"\n  Checking extraction precision...")
        precision_result = check_precision(conv_text, extracted_code)
        print(f"  Hallucinated facts: {precision_result['hallucinated_count']}")
        if precision_result['hallucinated_facts']:
            for hf in precision_result['hallucinated_facts'][:3]:
                print(f"    {hf}")

        # Step 4: Answer QA questions from extracted code
        print(f"\n  Answering {len(qas)} QA questions from extracted code...")
        qa_results = []
        scores_by_category = defaultdict(list)

        for qi, qa in enumerate(qas):
            question = qa["question"]
            gt_answer = str(qa.get("answer", qa.get("adversarial_answer", "")))
            category = qa["category"]

            prediction = answer_from_code(question, extracted_code, qa)
            f1 = evaluate_qa_item(prediction, qa)

            result = {
                "qa_index": qi,
                "category": category,
                "category_name": CATEGORY_NAMES.get(category, "unknown"),
                "question": question,
                "ground_truth": gt_answer,
                "prediction": prediction,
                "f1": round(f1, 4),
            }
            qa_results.append(result)
            scores_by_category[category].append(f1)

            if (qi + 1) % 25 == 0 or qi == len(qas) - 1:
                running_avg = sum(r["f1"] for r in qa_results) / len(qa_results)
                print(f"    [{qi+1}/{len(qas)}] Running F1: {running_avg:.3f}", flush=True)

            time.sleep(0.15)

        # Summary
        overall_f1 = sum(r["f1"] for r in qa_results) / len(qa_results)
        answerable_count = sum(1 for r in qa_results if r["f1"] > 0.0)
        coverage = answerable_count / len(qa_results)

        cat_stats = {}
        for cat, cat_scores in sorted(scores_by_category.items()):
            cat_avg = sum(cat_scores) / len(cat_scores)
            cat_answerable = sum(1 for s in cat_scores if s > 0)
            cat_stats[CATEGORY_NAMES.get(cat, str(cat))] = {
                "count": len(cat_scores),
                "avg_f1": round(cat_avg, 4),
                "answerable": cat_answerable,
                "coverage": round(cat_answerable / len(cat_scores), 4),
            }

        conv_summary = {
            "sample_id": sid,
            "speakers": f"{speaker_a} & {speaker_b}",
            "num_qa": len(qas),
            "raw_conversation_tokens": conv_tokens,
            "extracted_code_tokens": code_tokens,
            "compression_ratio": round(compression_ratio, 4),
            "extraction_time_s": round(extraction_time, 1),
            "overall_f1": round(overall_f1, 4),
            "extraction_coverage": round(coverage, 4),
            "answerable_from_code": answerable_count,
            "total_qa": len(qa_results),
            "per_category": cat_stats,
            "hallucinated_facts": precision_result["hallucinated_count"],
            "hallucination_examples": precision_result["hallucinated_facts"][:5],
            "extracted_code": extracted_code,
        }
        conversation_summaries.append(conv_summary)

        for r in qa_results:
            r["sample_id"] = sid
        all_results.extend(qa_results)

        print(f"\n  --- Results for {sid} ---")
        print(f"  Overall F1:           {overall_f1:.3f}")
        print(f"  Extraction coverage:  {coverage:.1%} ({answerable_count}/{len(qa_results)})")
        print(f"  Compression ratio:    {compression_ratio:.2f}x")
        for cat_name, stats in cat_stats.items():
            print(f"    {cat_name:>15}: F1={stats['avg_f1']:.3f}  "
                  f"coverage={stats['coverage']:.1%} ({stats['answerable']}/{stats['count']})")

    # -----------------------------------------------------------------------
    # Aggregate results
    # -----------------------------------------------------------------------
    print(f"\n{'='*70}")
    print(f"  AGGREGATE RESULTS ({NUM_CONVERSATIONS} conversations)")
    print(f"{'='*70}")

    total_qa = len(all_results)
    total_answerable = sum(1 for r in all_results if r["f1"] > 0.0)
    avg_f1 = sum(r["f1"] for r in all_results) / total_qa
    avg_coverage = total_answerable / total_qa
    avg_compression = sum(c["compression_ratio"] for c in conversation_summaries) / len(conversation_summaries)

    print(f"\n  Overall token F1:     {avg_f1:.3f}")
    print(f"  Extraction coverage:  {avg_coverage:.1%} ({total_answerable}/{total_qa})")
    print(f"  Avg compression:      {avg_compression:.2f}x")

    agg_cat = defaultdict(list)
    for r in all_results:
        agg_cat[r["category"]].append(r["f1"])

    print(f"\n  Per-category breakdown:")
    for cat in sorted(agg_cat.keys()):
        scores = agg_cat[cat]
        avg = sum(scores) / len(scores)
        answerable = sum(1 for s in scores if s > 0)
        print(f"    {CATEGORY_NAMES.get(cat, str(cat)):>15}: "
              f"F1={avg:.3f}  coverage={answerable/len(scores):.1%}  (n={len(scores)})")

    # Failure analysis
    failures = [r for r in all_results if r["f1"] == 0.0 and r["category"] != 5]
    print(f"\n  Failures (F1=0, excl. adversarial): {len(failures)}")

    failure_cats = Counter(r["category"] for r in failures)
    for cat, count in failure_cats.most_common():
        print(f"    {CATEGORY_NAMES.get(cat, str(cat)):>15}: {count}")

    print(f"\n  Sample failures:")
    for r in failures[:8]:
        print(f"    Cat {r['category']} ({CATEGORY_NAMES.get(r['category'], '?')}): "
              f"Q='{r['question'][:70]}' "
              f"GT='{r['ground_truth'][:40]}' "
              f"Pred='{r['prediction'][:40]}'")

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    # Remove full extracted_code from summaries for output (keep preview)
    for cs in conversation_summaries:
        full_code = cs.pop("extracted_code", "")
        cs["extracted_code_preview"] = full_code[:2000] + ("..." if len(full_code) > 2000 else "")

    output = {
        "experiment": "write_path_extraction_accuracy",
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "num_conversations": NUM_CONVERSATIONS,
        "aggregate": {
            "overall_f1": round(avg_f1, 4),
            "extraction_coverage": round(avg_coverage, 4),
            "avg_compression_ratio": round(avg_compression, 4),
            "total_qa_pairs": total_qa,
            "answerable_from_code": total_answerable,
            "per_category": {
                CATEGORY_NAMES.get(cat, str(cat)): {
                    "avg_f1": round(sum(scores) / len(scores), 4),
                    "coverage": round(sum(1 for s in scores if s > 0) / len(scores), 4),
                    "count": len(scores),
                }
                for cat, scores in sorted(agg_cat.items())
            },
        },
        "per_conversation": conversation_summaries,
        "failure_examples": [
            {
                "question": r["question"],
                "ground_truth": r["ground_truth"],
                "prediction": r["prediction"],
                "category": CATEGORY_NAMES.get(r["category"], str(r["category"])),
                "sample_id": r["sample_id"],
            }
            for r in failures[:15]
        ],
        "all_qa_results": all_results,
    }

    outfile = RESULTS_DIR / "write_path_results.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to: {outfile}")
    return output


if __name__ == "__main__":
    run_write_path_eval()
