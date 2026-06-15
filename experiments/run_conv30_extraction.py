#!/usr/bin/env python3
"""
Run the ACTUAL User-as-Code v5 extraction pipeline on LOCOMO conv-30
(Jon & Gina) and dump the genuine Phase-1 (facts) and Phase-2 (state)
artifacts.

chromadb is unimportable in this env (opentelemetry version clash) and is
only used for the retrieval vector store, which has no effect on the facts
list or the structured code. We inject a tiny in-memory stub so the real
pipeline module (prompts, model config, Phase-1/Phase-2 logic) runs verbatim.
"""

import sys
import types
import json
import pathlib
import re
import time

# ---- minimal in-memory chromadb stub (only to satisfy imports/__init__) ----
_chroma_stub = types.ModuleType("chromadb")


class _Coll:
    def __init__(self):
        self._docs = []

    def add(self, documents=None, ids=None, metadatas=None):
        if documents:
            self._docs.extend(documents)

    def count(self):
        return len(self._docs)

    def query(self, query_texts=None, n_results=10):
        return {"documents": [[]], "ids": [[]], "metadatas": [[]], "distances": [[]]}


class _Client:
    def __init__(self, *a, **k):
        self._colls = {}

    def delete_collection(self, name):
        self._colls.pop(name, None)

    def create_collection(self, name=None, metadata=None):
        c = _Coll()
        self._colls[name] = c
        return c

    def get_or_create_collection(self, name=None, metadata=None):
        return self._colls.setdefault(name, _Coll())


_chroma_stub.Client = lambda *a, **k: _Client()
sys.modules["chromadb"] = _chroma_stub

# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))
from user_as_code_v5 import UserAsCodeV5, MODEL  # noqa: E402

DATA = ROOT / "benchmarks/locomo/data/locomo10.json"
OUT = ROOT / "experiments/results/conv30_extraction"
OUT.mkdir(parents=True, exist_ok=True)


def get_sessions(conv):
    c = conv["conversation"]
    keys = sorted(
        [k for k in c if re.match(r"^session_\d+$", k)],
        key=lambda x: int(x.split("_")[1]),
    )
    out = []
    for sk in keys:
        out.append({"sid": sk, "date": c.get(f"{sk}_date_time", ""), "turns": c[sk]})
    return out


def main():
    data = json.loads(DATA.read_text())
    conv = next(c for c in data if c.get("sample_id") == "conv-30")
    sessions = get_sessions(conv)
    print(f"conv-30: {len(sessions)} sessions | model={MODEL}", flush=True)

    sysm = UserAsCodeV5(user_id=f"conv30_real_{int(time.time())}")

    # ---- Phase 1: Memorize (per session, append-only) ----
    t0 = time.time()
    for s in sessions:
        lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
        sysm.ingest_session(lines, s["sid"], s["date"])
        print(f"  [P1] {s['sid']} ({s['date']}) -> total facts: {len(sysm.fact_list)}",
              flush=True)
    print(f"Phase 1 done: {len(sysm.fact_list)} facts in {time.time()-t0:.0f}s", flush=True)

    # ---- Phase 2: Structure (periodic, from all facts) ----
    t1 = time.time()
    sysm.structure()
    print(f"Phase 2 done: {len(sysm.code_state)} chars in {time.time()-t1:.0f}s", flush=True)

    # ---- dump genuine artifacts ----
    facts_py = "facts = [\n" + "\n".join(f"    {json.dumps(f)}," for f in sysm.fact_list) + "\n]\n"
    (OUT / "facts.py").write_text(facts_py)
    (OUT / "state.py").write_text(sysm.code_state + "\n")
    (OUT / "provenance.json").write_text(json.dumps({
        "source": "benchmarks/locomo/data/locomo10.json :: conv-30 (Jon & Gina)",
        "pipeline": "experiments/user_as_code_v5.py (UserAsCodeV5)",
        "model": MODEL,
        "sessions": len(sessions),
        "n_facts": len(sysm.fact_list),
        "state_chars": len(sysm.code_state),
    }, indent=2))
    print(f"WROTE {OUT}/facts.py  state.py  provenance.json", flush=True)


if __name__ == "__main__":
    main()
