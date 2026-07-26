#!/usr/bin/env python3
"""Compile evaluation result JSONs into compact bundles for the React website.

Outputs into web/public/data/:
  locomo.json        - 600 LOCOMO QAs x 7 systems, with conversation-evidence context
  longmemeval.json   - 500 LongMemEval QAs x 7 systems
  analytical.json    - 100 analytical-inference cases x 5 systems, with executed code traces
  active.json        - 60 exploratory alert scenarios (not publication evidence)
  summary.json       - aggregate tables / chart data supported by the current paper
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "experiments", "results")
EVAL = os.path.join(ROOT, "evaluation")
BENCH = os.path.join(ROOT, "benchmarks")
OUT = os.path.join(ROOT, "web", "public", "data")
os.makedirs(OUT, exist_ok=True)


def load(path):
    with open(path) as f:
        return json.load(f)


def cap(s, n=2000):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + " …[truncated]"


# Display metadata, shared across the site.
SYSTEMS = {
    "uac_v5": {"name": "UaC", "label": "User as Code (ours)", "ours": True},
    "full_context": {"name": "Full Context", "label": "Full Context (reference)", "reference": True},
    "memmachine": {"name": "MemMachine", "label": "MemMachine (lite)", "lite": True},
    "hindsight": {"name": "Hindsight", "label": "Hindsight (lite)", "lite": True},
    "evermemos": {"name": "EverMemOS", "label": "EverMemOS (lite)", "lite": True},
    "a_mem": {"name": "A-MEM", "label": "A-MEM"},
    "mem0": {"name": "Mem0", "label": "Mem0"},
}
SYS_ORDER = ["uac_v5", "full_context", "memmachine", "hindsight", "evermemos", "a_mem", "mem0"]

LOCOMO_CATEGORIES = {
    1: "Multi-hop",
    2: "Temporal reasoning",
    3: "Open-domain",
    4: "Single-hop",
    5: "Adversarial",
}


def build_locomo():
    rj = load(os.path.join(RES, "full_rejudge.json"))["locomo"]
    src = load(os.path.join(BENCH, "locomo", "data", "locomo10.json"))

    # Build dia_id -> turn map and qa-evidence map per conversation.
    conv_meta = {}
    dia_map = {}      # conv_id -> {dia_id: {speaker,text,session,date}}
    qa_evidence = {}  # conv_id -> [evidence list per qa index]
    for conv in src:
        cid = conv["sample_id"]
        c = conv["conversation"]
        conv_meta[cid] = {"speaker_a": c.get("speaker_a"), "speaker_b": c.get("speaker_b")}
        dm = {}
        s = 1
        while f"session_{s}" in c:
            date = c.get(f"session_{s}_date_time", "")
            for turn in c[f"session_{s}"]:
                did = turn.get("dia_id")
                if did:
                    dm[did] = {
                        "speaker": turn.get("speaker"),
                        "text": turn.get("text"),
                        "session": s,
                        "date": date,
                    }
            s += 1
        dia_map[cid] = dm
        qa_evidence[cid] = [qa.get("evidence", []) for qa in conv.get("qa", [])]

    # Per-system gemini judge explanations + answer time.
    gemini_extra = {}  # (conv_id, qa_idx) -> {system: {explanation, time}}
    for sysk in SYS_ORDER:
        fn = os.path.join(RES, f"locomo10_{sysk}.json")
        if not os.path.exists(fn):
            continue
        d = load(fn)
        for cid, items in d.get("details", {}).items():
            for it in items:
                key = (cid, it.get("qa_idx"))
                gemini_extra.setdefault(key, {})[sysk] = {
                    "explanation": it.get("judge_explanation"),
                    "time": it.get("answer_time"),
                }

    # Assemble per-question records keyed off uac_v5's question set.
    base = rj["uac_v5"]
    cases = []
    for qkey, rec in base.items():
        cid = rec["conv_id"]
        qa_idx = rec["qa_idx"]
        cat = rec.get("category")
        # Evidence context turns.
        ctx = []
        ev = qa_evidence.get(cid, [])
        ev_list = ev[qa_idx] if qa_idx < len(ev) else []
        for did in ev_list:
            t = dia_map.get(cid, {}).get(did)
            if t:
                ctx.append({"dia_id": did, **t})
        systems = {}
        for sysk in SYS_ORDER:
            srec = rj.get(sysk, {}).get(qkey)
            if not srec:
                continue
            extra = gemini_extra.get((cid, qa_idx), {}).get(sysk, {})
            systems[sysk] = {
                "prediction": cap(srec.get("prediction"), 1500),
                "gemini_correct": srec.get("gemini_correct"),
                "claude_correct": srec.get("claude_correct"),
                "gemini_reason": cap(extra.get("explanation"), 600),
                "claude_reason": cap(srec.get("claude_reason"), 600),
                "time": extra.get("time"),
            }
        cases.append({
            "id": qkey,
            "conv_id": cid,
            "question": rec["question"],
            "gold": cap(rec.get("gold"), 600),
            "category": cat,
            "category_name": LOCOMO_CATEGORIES.get(cat, f"Cat {cat}"),
            "speakers": conv_meta.get(cid, {}),
            "context": ctx,
            "systems": systems,
        })
    out = {"systems": SYSTEMS, "sys_order": SYS_ORDER, "cases": cases}
    with open(os.path.join(OUT, "locomo.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"locomo.json: {len(cases)} cases")


def build_lme():
    rj = load(os.path.join(RES, "full_rejudge.json"))["lme"]

    # Real context: the LME oracle holds the evidence sessions per question,
    # joined by question_id, with answer turns flagged via has_answer.
    oracle = load(os.path.join(BENCH, "longmemeval", "data", "longmemeval_oracle.json"))
    ctx_map = {}
    for q in oracle:
        qid = q["question_id"]
        sess_ids = q.get("haystack_session_ids", [])
        sessions = q.get("haystack_sessions", [])
        dates = q.get("haystack_dates", [])
        answer_ids = set(q.get("answer_session_ids", []))
        by_id = {sid: (sessions[i] if i < len(sessions) else [],
                       dates[i] if i < len(dates) else "")
                 for i, sid in enumerate(sess_ids)}
        # Prefer the evidence (answer) sessions; fall back to first session.
        chosen = [sid for sid in sess_ids if sid in answer_ids] or sess_ids[:1]
        ctx = []
        for sid in chosen[:2]:
            turns, date = by_id.get(sid, ([], ""))
            # Keep evidence turns plus a little surrounding context, capped.
            ev_idx = [i for i, t in enumerate(turns) if t.get("has_answer")]
            if ev_idx:
                lo = max(0, min(ev_idx) - 1)
                hi = min(len(turns), max(ev_idx) + 2)
                window = turns[lo:hi][:10]
            else:
                window = turns[:8]
            packed = [
                {"role": t.get("role"), "content": cap(t.get("content"), 400),
                 "evidence": bool(t.get("has_answer"))}
                for t in window
            ]
            ctx.append({"date": date, "turns": packed})
        ctx_map[qid] = ctx

    # Gemini explanations per system.
    gem = {}
    for sysk in SYS_ORDER:
        fn = os.path.join(RES, f"lme500_{sysk}.json")
        if not os.path.exists(fn):
            continue
        d = load(fn)
        bq = d.get("by_question", {})
        for qid, it in bq.items():
            gem.setdefault(qid, {})[sysk] = {
                "explanation": it.get("judge_explanation"),
                "time": it.get("answer_time"),
            }

    base = rj["uac_v5"]
    cases = []
    for qkey, rec in base.items():
        qid = rec.get("question_id")
        systems = {}
        for sysk in SYS_ORDER:
            srec = rj.get(sysk, {}).get(qkey)
            if not srec:
                continue
            extra = gem.get(qid, {}).get(sysk, {})
            systems[sysk] = {
                "prediction": cap(srec.get("prediction"), 1500),
                "gemini_correct": srec.get("gemini_correct"),
                "claude_correct": srec.get("claude_correct"),
                "gemini_reason": cap(extra.get("explanation"), 600),
                "claude_reason": cap(srec.get("claude_reason"), 600),
                "time": extra.get("time"),
            }
        cases.append({
            "id": qkey,
            "question_id": qid,
            "question": rec["question"],
            "gold": cap(rec.get("gold"), 800),
            "type": rec.get("question_type"),
            "context": ctx_map.get(qid, []),
            "systems": systems,
        })
    out = {"systems": SYSTEMS, "sys_order": SYS_ORDER, "cases": cases}
    with open(os.path.join(OUT, "longmemeval.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"longmemeval.json: {len(cases)} cases")


ANALYTICAL_SYSTEMS = {
    "uac_v5": {"name": "UaC", "file": "analytical_uac_v5.json", "ours": True},
    "fc_repl": {"name": "FC + REPL", "file": "analytical_fc_repl.json"},
    "full_context": {"name": "Full Context", "file": "analytical_full_context.json"},
    "memmachine": {"name": "MemMachine", "file": "analytical_memmachine.json"},
    "mem0": {"name": "Mem0", "file": "analytical_mem0.json"},
}
ANALYTICAL_ORDER = ["uac_v5", "fc_repl", "full_context", "memmachine", "mem0"]


def slim_log(log):
    if not log:
        return None
    out = []
    for step in log[:4]:
        out.append({
            "tool": step.get("tool"),
            "code": cap(step.get("code"), 1200),
            "stdout": cap(step.get("stdout"), 600),
            "error": cap(step.get("error"), 300),
        })
    return out


def build_analytical():
    sysdata = {}
    for sysk, meta in ANALYTICAL_SYSTEMS.items():
        fn = os.path.join(RES, meta["file"])
        if os.path.exists(fn):
            sysdata[sysk] = load(fn).get("by_case", {})
    base = sysdata["uac_v5"]
    cases = []
    for qid, rec in base.items():
        systems = {}
        for sysk in ANALYTICAL_ORDER:
            srec = sysdata.get(sysk, {}).get(qid)
            if not srec:
                continue
            systems[sysk] = {
                "prediction": cap(srec.get("prediction") or srec.get("raw"), 500),
                "correct": srec.get("correct"),
                "time": srec.get("answer_time"),
                "log": slim_log(srec.get("log")),
                "tool_calls": srec.get("tool_calls"),
                "n_retrieved": srec.get("n_retrieved"),
            }
        cases.append({
            "id": qid,
            "type": rec.get("type"),
            "n": rec.get("n"),
            "question": rec.get("question"),
            "answer_kind": rec.get("answer_kind"),
            "gold": cap(rec.get("gold"), 400),
            "systems": systems,
        })
    smap = {k: {"name": v["name"], "ours": v.get("ours", False)} for k, v in ANALYTICAL_SYSTEMS.items()}
    out = {"systems": smap, "sys_order": ANALYTICAL_ORDER, "cases": cases}
    with open(os.path.join(OUT, "analytical.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"analytical.json: {len(cases)} cases")


def build_active():
    std = load(os.path.join(EVAL, "active_service_scenarios.json"))["scenarios"]
    hard = load(os.path.join(EVAL, "hard_active_service_scenarios.json"))["scenarios"]
    mem0 = load(os.path.join(RES, "active_service_mem0lib.json"))
    amem_hard = load(os.path.join(RES, "active_service_amem_hard.json")).get("by_scenario", {})
    mem0_std = mem0.get("standard", {}).get("by_scenario", {})
    mem0_hard = mem0.get("hard", {}).get("by_scenario", {})

    def pack(scenarios, difficulty, mem0_runs):
        out = []
        for sc in scenarios:
            sid = sc["id"]
            runs = {}
            exp = sc.get("expected_alert", {})
            mr = mem0_runs.get(sid)
            if mr:
                runs["mem0"] = {
                    "response": cap(mr.get("response"), 1500),
                    "detected": mr.get("proactive_alert_detected"),
                    "score": mr.get("keyword_score"),
                }
            if difficulty == "hard":
                ar = amem_hard.get(sid)
                if ar:
                    runs["a_mem"] = {
                        "response": cap(ar.get("response"), 1500),
                        "detected": ar.get("proactive_alert_detected"),
                        "score": ar.get("keyword_score"),
                    }
            out.append({
                "id": sid,
                "difficulty": difficulty,
                "category": sc.get("category"),
                "description": sc.get("description"),
                "sessions": [
                    {"session_id": s.get("session_id"), "timestamp": s.get("timestamp"),
                     "conversation": cap(s.get("conversation"), 2000)}
                    for s in sc.get("sessions", [])
                ],
                "trigger_session": sc.get("trigger_session"),
                "expected_alert": exp,
                "runs": runs,
            })
        return out

    cases = pack(std, "standard", mem0_std) + pack(hard, "hard", mem0_hard)
    out = {
        "publication_ready": False,
        "disclaimer": (
            "Exploratory protocol only. These stored runs do not execute "
            "generated persistent UaC constraints and are not publication evidence."
        ),
        "cases": cases,
    }
    with open(os.path.join(OUT, "active.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"active.json: {len(cases)} cases")


def build_memory():
    """Compile the regenerated per-case UaC memory (Phase-1 facts + Phase-2
    typed state) from experiments/results/memory_<bench>.json into capped,
    lazy-loaded web bundles web/public/data/<bench>_memory.json.

    Keyed by the unit the explorer can look up: LOCOMO -> conv_id, LME ->
    question_id, Active -> scenario id, Analytical -> case id. Generated by
    experiments/gen_case_memory.py (the real v5 pipeline)."""
    # Phase-1 facts may be truncated for display; Phase-2 state.py is kept in
    # FULL — the structured code is the point, so users see all of it.
    FACT_CAP = 40          # facts shown per unit (full count kept as n_facts)

    def pack_extracted(src_name, out_name):
        path = os.path.join(RES, src_name)
        if not os.path.exists(path):
            print(f"  (skip {out_name}: {src_name} not found)")
            return
        raw = load(path)
        out = {}
        for uid, m in raw.items():
            facts = m.get("facts") or []
            out[uid] = {
                "facts": facts[:FACT_CAP],
                "n_facts": m.get("n_facts", len(facts)),
                "state": m.get("state"),  # full, never truncated
            }
        with open(os.path.join(OUT, out_name), "w") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{out_name}: {len(out)} units")

    pack_extracted("memory_locomo.json", "locomo_memory.json")
    pack_extracted("memory_lme.json", "lme_memory.json")
    pack_extracted("memory_active.json", "active_memory.json")

    # Analytical: structured state + a small raw-record preview.
    apath = os.path.join(RES, "memory_analytical.json")
    if os.path.exists(apath):
        raw = load(apath)
        out = {}
        for cid, m in raw.items():
            out[cid] = {
                "state": m.get("state"),  # full, never truncated
                "records_preview": m.get("records_preview", []),
                "n_records": m.get("n_records"),
            }
        with open(os.path.join(OUT, "analytical_memory.json"), "w") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print(f"analytical_memory.json: {len(out)} units")
    else:
        print("  (skip analytical_memory.json: source not found)")


def build_summary():
    """Write only aggregate claims supported by the current manuscript."""
    summary = {
        "locomo": [
            {"system": "Full Context", "acc": 84.8, "reference": True},
            {"system": "UaC (ours)", "acc": 80.6, "ours": True},
            {"system": "MemMachine", "acc": 74.9},
            {"system": "Hindsight", "acc": 71.4, "lite": True},
            {"system": "A-MEM", "acc": 56.6},
            {"system": "EverMemOS", "acc": 51.4, "lite": True},
            {"system": "Mem0", "acc": 20.1},
        ],
        "lme": [
            {"system": "Full Context", "acc": 85.4, "reference": True,
             "types": {"KU": 91, "MS": 87, "SA": 96, "SP": 70, "SU": 96, "TR": 74}},
            {"system": "MemMachine", "acc": 84.8, "lite": True,
             "types": {"KU": 96, "MS": 88, "SA": 96, "SP": 63, "SU": 96, "TR": 69}},
            {"system": "UaC (ours)", "acc": 83.0, "ours": True,
             "types": {"KU": 97, "MS": 81, "SA": 96, "SP": 83, "SU": 94, "TR": 65}},
            {"system": "EverMemOS", "acc": 76.4, "lite": True,
             "types": {"KU": 87, "MS": 72, "SA": 73, "SP": 87, "SU": 87, "TR": 68}},
            {"system": "Hindsight", "acc": 73.0, "lite": True,
             "types": {"KU": 78, "MS": 72, "SA": 66, "SP": 77, "SU": 93, "TR": 62}},
            {"system": "A-MEM", "acc": 49.6,
             "types": {"KU": 54, "MS": 44, "SA": 93, "SP": 40, "SU": 49, "TR": 37}},
            {"system": "Mem0", "acc": 23.8,
             "types": {"KU": 32, "MS": 23, "SA": 7, "SP": 33, "SU": 36, "TR": 18}},
        ],
        "lme_type_legend": {
            "KU": "Knowledge-update", "MS": "Multi-session", "SA": "Single-asst",
            "SP": "Single-pref", "SU": "Single-user", "TR": "Temporal-reasoning",
        },
        "lme_type_n": {"KU": 78, "MS": 133, "SA": 56, "SP": 30, "SU": 70, "TR": 133},
        "notes": {
            "baseline": (
                "MemMachine, Hindsight, and EverMemOS are controlled same-backbone "
                "reimplementations on shared ChromaDB infrastructure, not native-stack "
                "reproductions. The displayed full-LOCOMO judge scores use Gemini 3 Flash "
                "Preview on all 1,986 questions; judge accuracy uses the 1,540 "
                "answer-bearing questions."
            ),
            "active": (
                "The 60 alert scenarios are retained only as exploratory protocol material. "
                "The stored runs do not execute generated persistent UaC constraints and "
                "are not publication evidence."
            ),
        },
        "analytical": [
            {"system": "FC + REPL", "overall": 100.0,
             "byN": {"20": 100, "50": 100, "100": 100, "200": 100, "500": 100}},
            {"system": "UaC (ours)", "overall": 100.0, "ours": True,
             "byN": {"20": 100, "50": 100, "100": 100, "200": 100, "500": 100}},
            {"system": "Full Context", "overall": 94.0,
             "byN": {"20": 100, "50": 90, "100": 100, "200": 90, "500": 90}},
            {"system": "MemMachine", "overall": 43.0,
             "byN": {"20": 100, "50": 55, "100": 20, "200": 15, "500": 25}},
            {"system": "Mem0", "overall": 6.0,
             "byN": {"20": 5, "50": 10, "100": 0, "200": 0, "500": 15}},
        ],
        "modularity": [
            {"strategy": "Monolithic (always dump)", "acc": 97.0,
             "promptTokens": 10155765, "perCase": 36.38797},
            {"strategy": "Modular (load on demand)", "acc": 98.0,
             "promptTokens": 426856, "perCase": 2.446868},
            {"strategy": "Manifest + routing", "acc": 87.0,
             "promptTokens": 624922, "perCase": 3.8},
        ],
    }
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, separators=(",", ":"))
    print("summary.json written")


if __name__ == "__main__":
    build_locomo()
    build_lme()
    build_analytical()
    build_active()
    build_memory()
    build_summary()
    print("\nAll data bundles written to", OUT)
    for fn in sorted(os.listdir(OUT)):
        size = os.path.getsize(os.path.join(OUT, fn)) / 1024
        print(f"  {fn}: {size:.0f} KB")
