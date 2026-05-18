#!/usr/bin/env python3
"""Phase-2 failure-mode analysis.

For each of the 5 LOCOMO conversations: ingest (Phase 1), structure (Phase 2),
then audit the structured Python output for:

  - parse: does the generated code parse as valid Python (ast.parse)?
  - dataclass_count: how many dataclass instances?
  - notes_fact_count: facts dumped into notes lists vs typed fields.
  - dropped_facts: count of input facts whose distinctive keywords appear
    nowhere in the structured code (heuristic estimate of information loss).
  - date_typing: number of date()-typed values vs date-like strings.

The dropped-facts heuristic is conservative: a fact is "dropped" only if its
distinctive content tokens (rare lowercased nouns / numbers / dates) appear
nowhere in the structured code, even in notes. False positives are possible
(synonymy, abstraction) but the overall rate is informative as an upper bound
on information loss.
"""
from __future__ import annotations
import ast
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log  # noqa: E402
from user_as_code_v5 import UserAsCodeV5  # noqa: E402

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
OUT_PATH = RESULTS_DIR / "phase2_failure_analysis.json"

# Distinctive-token regex: catch rare nouns/numbers/dates by surface form.
TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]{3,}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{2,5}\b")
# Stopwords / generic tokens we strip before keyword check.
STOP = set("""the and that this with from your have just been said about
they them their there were they're isn't don't didn't doesn't will would could should
yesterday today tomorrow morning evening afternoon night week month year day
session date user have got had has not but for can may any all one two three many
who what when where why how which because while since until before after
mentioned told asked got say very really still also again well think feel know going""".split())


def distinctive_tokens(fact: str) -> set[str]:
    toks = set(t.lower() for t in TOKEN_RE.findall(fact))
    return {t for t in toks if t not in STOP and not t.isdigit() or (t.isdigit() and (1900 < int(t) < 2100 or len(t) > 3))}


def audit_one_conversation(conv_id, sessions, log):
    uac = UserAsCodeV5(user_id=f"phase2_audit_{conv_id}_{int(time.time())}")
    for s in sessions:
        turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
        uac.ingest_session(turn_lines, s["session_id"], s["date"])
        log(f"  {conv_id}: ingested {s['session_id']}, total facts={len(uac.fact_list)}")
    uac.structure()
    code = uac.code_state
    facts = uac.fact_list
    log(f"  {conv_id}: structured ({len(code)} chars), facts={len(facts)}")

    audit = {"conv_id": conv_id, "n_facts": len(facts), "code_chars": len(code)}

    # 1. Parse check
    try:
        tree = ast.parse(code)
        audit["parse_ok"] = True
    except Exception as e:
        audit["parse_ok"] = False
        audit["parse_error"] = str(e)[:200]
        tree = None

    # 2. Count dataclasses and instances
    if tree:
        dataclass_decls = []
        instances = []
        notes_strings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if any(isinstance(d, ast.Name) and d.id == "dataclass" for d in node.decorator_list) or \
                   any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass" for d in node.decorator_list):
                    dataclass_decls.append(node.name)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name):
                    instances.append(func.id)
            # collect notes=[...] entries
            if isinstance(node, ast.keyword) and node.arg == "notes" and isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        notes_strings.append(elt.value)
        audit["dataclass_count"] = len(dataclass_decls)
        audit["instance_count"] = len(instances)
        audit["notes_count"] = len(notes_strings)
    else:
        audit["dataclass_count"] = audit["instance_count"] = audit["notes_count"] = 0

    # 3. Date typing
    n_typed_dates = len(re.findall(r"\bdate\(\s*\d{4}", code))
    n_string_dates = len(re.findall(r'"\d{4}-\d{2}-\d{2}"', code)) + len(re.findall(r"'\d{4}-\d{2}-\d{2}'", code))
    audit["date_typed"] = n_typed_dates
    audit["date_as_string"] = n_string_dates

    # 4. Dropped-facts heuristic: a fact is "missing" if none of its distinctive
    # tokens appear in the code.
    code_lower = code.lower()
    dropped = []
    for f in facts:
        toks = distinctive_tokens(f)
        if not toks:
            continue
        if not any(t in code_lower for t in toks):
            dropped.append(f)
    audit["distinctive_token_facts"] = sum(1 for f in facts if distinctive_tokens(f))
    audit["dropped_facts"] = len(dropped)
    audit["dropped_rate"] = round(len(dropped) / max(1, audit["distinctive_token_facts"]), 4)
    audit["dropped_examples"] = dropped[:5]

    try:
        uac.reset()
    except Exception:
        pass
    return audit, code


def get_sessions(conv):
    c = conv["conversation"]
    keys = sorted([k for k in c.keys() if re.match(r"^session_\d+$", k)],
                  key=lambda x: int(x.split("_")[1]))
    return [{"session_id": sk, "date": c.get(f"{sk}_date_time", ""), "turns": c[sk]} for sk in keys]


def main():
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            saved = json.load(f)
    else:
        saved = {"audits": [], "codes": {}}

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    done_ids = {a["conv_id"] for a in saved["audits"]}

    for ci, conv in enumerate(all_convs[:5]):  # first 5 LOCOMO convs
        conv_id = conv.get("sample_id", f"conv_{ci}")
        if conv_id in done_ids:
            _log(f"=== SKIP {conv_id} (already audited) ===")
            continue
        _log(f"\n=== AUDIT {conv_id} ===")
        sessions = get_sessions(conv)
        audit, code = audit_one_conversation(conv_id, sessions, _log)
        saved["audits"].append(audit)
        saved["codes"][conv_id] = code
        with open(OUT_PATH, "w") as f:
            json.dump(saved, f, indent=2, default=str)
        _log(f"  audit: parse_ok={audit['parse_ok']} dataclasses={audit['dataclass_count']} "
             f"instances={audit['instance_count']} notes={audit['notes_count']} "
             f"date_typed={audit['date_typed']} date_as_string={audit['date_as_string']} "
             f"dropped={audit['dropped_facts']}/{audit['distinctive_token_facts']} ({audit['dropped_rate']*100:.1f}%)")

    # Summary
    audits = saved["audits"]
    if audits:
        total_facts = sum(a["distinctive_token_facts"] for a in audits)
        total_dropped = sum(a["dropped_facts"] for a in audits)
        n_parse_fail = sum(1 for a in audits if not a["parse_ok"])
        total_date_typed = sum(a["date_typed"] for a in audits)
        total_date_string = sum(a["date_as_string"] for a in audits)
        saved["summary"] = {
            "n_convs": len(audits),
            "parse_failures": n_parse_fail,
            "total_facts_with_tokens": total_facts,
            "total_dropped_facts": total_dropped,
            "overall_drop_rate": round(total_dropped / max(1, total_facts), 4),
            "total_date_typed": total_date_typed,
            "total_date_as_string": total_date_string,
        }
        with open(OUT_PATH, "w") as f:
            json.dump(saved, f, indent=2, default=str)
        _log(f"\n=== SUMMARY ===")
        for k, v in saved["summary"].items():
            _log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
