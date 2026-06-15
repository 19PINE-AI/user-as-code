#!/usr/bin/env python3
"""
Regenerate the UaC memory (Phase-1 facts + Phase-2 typed state) for every
benchmark case, so the website explorer can show what UaC actually extracted.

Usage:  python gen_case_memory.py {locomo|lme|active|analytical} [--workers N]

Writes the FULL per-unit memory to experiments/results/memory_<bench>.json
(resumable: existing units are skipped). A later build step caps it for the web.

chromadb is stubbed (vector store irrelevant to facts/state); the real
pipeline prompts / model config in user_as_code_v5.py run verbatim.
"""
import sys, types, json, pathlib, re, time, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---- in-memory chromadb stub ----
_stub = types.ModuleType("chromadb")
class _Coll:
    def __init__(s): s._n = 0
    def add(s, documents=None, ids=None, metadatas=None): s._n += len(documents or [])
    def count(s): return s._n
    def query(s, query_texts=None, n_results=10): return {"documents": [[]]}
class _Client:
    def __init__(s, *a, **k): pass
    def delete_collection(s, name): pass
    def create_collection(s, name=None, metadata=None): return _Coll()
    def get_or_create_collection(s, name=None, metadata=None): return _Coll()
_stub.Client = lambda *a, **k: _Client()
sys.modules["chromadb"] = _stub

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))
from user_as_code_v5 import UserAsCodeV5, MODEL  # noqa: E402

RES = ROOT / "experiments" / "results"
RES.mkdir(parents=True, exist_ok=True)


def extract_unit(unit_id, sessions):
    """sessions: list of (session_id, date, [turn_line, ...]). Returns memory dict."""
    for attempt in range(3):
        sysm = UserAsCodeV5(user_id=f"mem_{unit_id}_{attempt}_{int(time.time()*1000)%100000}")
        try:
            for sid, date, lines in sessions:
                sysm.ingest_session(lines, sid, date)
            sysm.structure()
            if sysm.code_state and not sysm.code_state.startswith("# Structuring error"):
                return {"facts": sysm.fact_list, "state": sysm.code_state,
                        "n_facts": len(sysm.fact_list)}
        except Exception as e:
            last = str(e)
            time.sleep(2 * (attempt + 1))
            continue
    return {"facts": sysm.fact_list, "state": sysm.code_state,
            "n_facts": len(sysm.fact_list), "error": True}


# ---------------------------------------------------------------- LOCOMO
def units_locomo():
    src = json.loads((ROOT / "benchmarks/locomo/data/locomo10.json").read_text())
    for conv in src:
        cid = conv["sample_id"]; c = conv["conversation"]
        sk = sorted([k for k in c if re.match(r"^session_\d+$", k)],
                    key=lambda x: int(x.split("_")[1]))
        sessions = [(s, c.get(f"{s}_date_time", ""),
                     [f"{t['speaker']}: {t['text']}" for t in c[s]]) for s in sk]
        yield cid, sessions


# ---------------------------------------------------------------- LongMemEval
def units_lme():
    oracle = json.loads((ROOT / "benchmarks/longmemeval/data/longmemeval_oracle.json").read_text())
    for q in oracle:
        qid = q["question_id"]
        sess = q.get("haystack_sessions", [])
        sids = q.get("haystack_session_ids", [])
        dates = q.get("haystack_dates", [])
        sessions = []
        for i, turns in enumerate(sess):
            sid = sids[i] if i < len(sids) else f"s{i}"
            date = dates[i] if i < len(dates) else ""
            lines = [f"{t.get('role','user')}: {t.get('content','')}" for t in turns]
            sessions.append((sid, date, lines))
        yield qid, sessions


# ---------------------------------------------------------------- Active Service
def units_active():
    for fn in ["active_service_scenarios.json", "hard_active_service_scenarios.json"]:
        d = json.loads((ROOT / "evaluation" / fn).read_text())
        for sc in d["scenarios"]:
            sessions = []
            for s in sc.get("sessions", []):
                sid = f"session_{s.get('session_id')}"
                date = s.get("timestamp", "")
                sessions.append((sid, date, [s.get("conversation", "")]))
            yield sc["id"], sessions


# ---------------------------------------------------------------- Analytical
def run_analytical(workers, out_path):
    """Memory = the typed `state.py` UaC structures the records into (LLM call),
    plus a small raw-record preview. Records are deterministic (build_cases)."""
    from analytical_bench.build_cases import build_cases
    from analytical_bench.runners import _uac_structure_with_usage
    cases = build_cases()
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"analytical: {len(cases)} cases, {len(todo)} to do", flush=True)

    def work(case):
        for attempt in range(3):
            try:
                code, _ = _uac_structure_with_usage(case)
                if code and "dataclass" in code:
                    return case["case_id"], {"state": code,
                                        "records_preview": case["records"][:3],
                                        "n_records": len(case["records"])}
            except Exception:
                time.sleep(2 * (attempt + 1))
        return case["case_id"], {"state": "# structuring failed",
                            "records_preview": case["records"][:3],
                            "n_records": len(case["records"]), "error": True}

    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(work, c): c["case_id"] for c in todo}
        for fut in as_completed(futs):
            cid, mem = fut.result()
            done[cid] = mem; n += 1
            if n % 10 == 0:
                out_path.write_text(json.dumps(done))
                print(f"  analytical {n}/{len(todo)} (last {cid})", flush=True)
    out_path.write_text(json.dumps(done))
    print(f"analytical DONE: {len(done)} units -> {out_path}", flush=True)


def run_bench(bench, unit_iter, workers, out_path):
    units = list(unit_iter)
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [(uid, s) for uid, s in units if uid not in done]
    print(f"{bench}: {len(units)} units, {len(todo)} to do | model={MODEL}", flush=True)
    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(extract_unit, uid, s): uid for uid, s in todo}
        for fut in as_completed(futs):
            uid = futs[fut]
            done[uid] = fut.result(); n += 1
            if n % 5 == 0 or n == len(todo):
                out_path.write_text(json.dumps(done))
                print(f"  {bench} {n}/{len(todo)} done (last {uid}: "
                      f"{done[uid].get('n_facts','?')} facts)", flush=True)
    out_path.write_text(json.dumps(done))
    print(f"{bench} DONE: {len(done)} units -> {out_path}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", choices=["locomo", "lme", "active", "analytical"])
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = RES / f"memory_{a.bench}.json"
    if a.bench == "locomo":
        run_bench("locomo", units_locomo(), a.workers, out)
    elif a.bench == "lme":
        run_bench("lme", units_lme(), a.workers, out)
    elif a.bench == "active":
        run_bench("active", units_active(), a.workers, out)
    elif a.bench == "analytical":
        run_analytical(a.workers, out)
