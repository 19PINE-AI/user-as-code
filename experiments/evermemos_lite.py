"""Lightweight reimplementation of EverMemOS (arXiv 2601.02163) for benchmarking.

Implements the three-phase pipeline described in the paper abstract:
- Phase 1: Episodic Trace Formation
  Each conversation session is segmented into MemCells. An LLM extracts
  atomic facts and Foresight signals (predicted future information needs).
- Phase 2: Semantic Consolidation
  MemCells with related topics are clustered into MemScenes. A scene-level
  summary is produced and the User Profile is updated with stable attributes.
- Phase 3: Reconstructive Recollection
  Query → embedding → MemCell similarity → MemScene-level filter → re-rank by
  recency + foresight relevance → atomic-fact aggregation → assembled context.

Hybrid retrieval (vector + keyword) follows the paper. Specific
hyperparameters are not stated in the paper text and are not extractable from
the binary PDF, so we use defaults consistent with the paper's narrative.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from google import genai


GEMINI_MODEL = "gemini-3-flash-preview"
_gclient = genai.Client()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MemCell:
    """Atomic memory unit per EverMemOS Section 3."""
    cell_id: str
    session_id: str
    session_date: str
    raw_text: str               # the dialogue snippet
    atomic_facts: list[str]     # extracted facts
    foresight: list[str]        # predicted future information needs
    embedding_text: str         # combined text used for retrieval


@dataclass
class MemScene:
    """A thematic cluster of MemCells."""
    scene_id: str
    topic: str
    summary: str
    cell_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOK_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _toks(s: str) -> list[str]:
    return [t.lower() for t in _TOK_RE.findall(s or "")]


def _gemini_call(prompt: str, system_instruction: Optional[str] = None,
                 thinking_budget: int = 1024, max_retries: int = 4) -> str:
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
        temperature=1.0,
    )
    if system_instruction:
        cfg.system_instruction = system_instruction
    last_err = None
    for attempt in range(max_retries):
        try:
            r = _gclient.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=cfg)
            return (r.text or "").strip()
        except Exception as e:
            last_err = e
            err = str(e)
            wait = 15 * (attempt + 1) if "429" in err or "RESOURCE" in err else 8
            time.sleep(wait)
    raise RuntimeError(f"gemini failed: {last_err}")


def _strip_fences(s: str) -> str:
    s = re.sub(r"^```(?:json)?\s*", "", s.strip())
    return re.sub(r"```\s*$", "", s.strip())


# ---------------------------------------------------------------------------
# Phase 1: Episodic Trace Formation
# ---------------------------------------------------------------------------

_TRACE_SYS = (
    "You convert a conversation session into a structured trace. "
    "Output ONLY a JSON object with: "
    "atomic_facts (array of 5-15 short factual statements; resolve relative "
    "dates to absolute), "
    "foresight (array of 1-5 short predictions of what the user might want to "
    "be reminded of in the future, e.g., upcoming deadlines, expirations, "
    "follow-ups). No commentary."
)


def trace_session(text: str, session_date: str) -> tuple[list[str], list[str]]:
    prompt = f"Session date: {session_date}\nSession:\n{text[:8000]}\n\nJSON:"
    try:
        out = _gemini_call(prompt, system_instruction=_TRACE_SYS, thinking_budget=2048)
    except Exception:
        return [], []
    out = _strip_fences(out)
    try:
        obj = json.loads(out)
    except Exception:
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return [], []
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return [], []
    facts = obj.get("atomic_facts", []) if isinstance(obj, dict) else []
    foresight = obj.get("foresight", []) if isinstance(obj, dict) else []
    return [str(f) for f in facts if f], [str(f) for f in foresight if f]


# ---------------------------------------------------------------------------
# Phase 2: Semantic Consolidation
# ---------------------------------------------------------------------------

_SCENE_SYS = (
    "You group memory cells into thematic scenes. Each scene captures one "
    "coherent topic or storyline. Output ONLY a JSON array. Each element: "
    "{topic: short topic name, summary: one-paragraph summary, "
    "cell_ids: list of cell IDs that belong to this scene}. "
    "Each cell appears in exactly one scene. No commentary."
)


def consolidate_scenes(cells: list[MemCell]) -> list[MemScene]:
    if not cells:
        return []
    listing = "\n".join(
        f"- {c.cell_id} [{c.session_date}]: {c.raw_text[:300].replace(chr(10), ' ')}"
        for c in cells
    )
    prompt = f"Memory cells:\n{listing}\n\nJSON scenes:"
    try:
        out = _gemini_call(prompt, system_instruction=_SCENE_SYS, thinking_budget=2048)
    except Exception:
        return [MemScene("scene_0", "all", "", [c.cell_id for c in cells])]
    out = _strip_fences(out)
    try:
        arr = json.loads(out)
    except Exception:
        m = re.search(r"\[.*\]", out, re.DOTALL)
        if not m:
            return [MemScene("scene_0", "all", "", [c.cell_id for c in cells])]
        try:
            arr = json.loads(m.group(0))
        except Exception:
            return [MemScene("scene_0", "all", "", [c.cell_id for c in cells])]
    if not isinstance(arr, list) or not arr:
        return [MemScene("scene_0", "all", "", [c.cell_id for c in cells])]
    scenes = []
    seen: set[str] = set()
    for i, sc in enumerate(arr):
        if not isinstance(sc, dict):
            continue
        cell_ids = [str(x) for x in sc.get("cell_ids", []) if x]
        cell_ids = [cid for cid in cell_ids if cid not in seen]
        for cid in cell_ids:
            seen.add(cid)
        if not cell_ids:
            continue
        scenes.append(MemScene(
            scene_id=f"scene_{i}",
            topic=str(sc.get("topic", f"topic_{i}")),
            summary=str(sc.get("summary", "")),
            cell_ids=cell_ids,
        ))
    # Cells not assigned go in a catch-all scene.
    leftover = [c.cell_id for c in cells if c.cell_id not in seen]
    if leftover:
        scenes.append(MemScene("scene_misc", "miscellaneous", "", leftover))
    return scenes


# ---------------------------------------------------------------------------
# EverMemOSSystem
# ---------------------------------------------------------------------------

class EverMemOSSystem:
    """Three-phase memory OS with MemCell / MemScene / Profile layers."""

    name = "evermemos"

    SCENE_TOP_K = 3
    CELL_TOP_K = 20
    BM25_TOP_K = 20
    FORESIGHT_BOOST = 0.5  # added when a foresight signal matches the query

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.cells: dict[str, MemCell] = {}
        self.scenes: list[MemScene] = []
        self.user_profile: str = ""
        self._chroma = chromadb.Client()
        uid = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for n in [f"em_cells_{uid}", f"em_scenes_{uid}"]:
            try:
                self._chroma.delete_collection(n)
            except Exception:
                pass
        self._cells_coll = self._chroma.create_collection(
            name=f"em_cells_{uid}", metadata={"hnsw:space": "cosine"})
        self._scenes_coll = self._chroma.create_collection(
            name=f"em_scenes_{uid}", metadata={"hnsw:space": "cosine"})

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = "") -> None:
        text = "\n".join(turns)
        atomic, foresight = trace_session(text, session_date)
        cell = MemCell(
            cell_id=session_id,
            session_id=session_id,
            session_date=session_date,
            raw_text=text,
            atomic_facts=atomic,
            foresight=foresight,
            embedding_text=" | ".join(atomic) + " | " + text[:1000],
        )
        self.cells[cell.cell_id] = cell
        self._cells_coll.add(
            documents=[cell.embedding_text],
            ids=[cell.cell_id],
            metadatas=[{"session_date": session_date, "session_id": session_id}],
        )

    def consolidate(self) -> None:
        """Phase 2: cluster cells into scenes and refresh the user profile."""
        if not self.cells:
            return
        cells_list = list(self.cells.values())
        self.scenes = consolidate_scenes(cells_list)
        # Index scene summaries for coarse routing.
        try:
            self._chroma.delete_collection(self._scenes_coll.name)
        except Exception:
            pass
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        self._scenes_coll = self._chroma.create_collection(
            name=f"em_scenes_{uid}", metadata={"hnsw:space": "cosine"})
        if self.scenes:
            self._scenes_coll.add(
                documents=[f"{s.topic}: {s.summary}" for s in self.scenes],
                ids=[s.scene_id for s in self.scenes],
                metadatas=[{"topic": s.topic} for s in self.scenes],
            )
        # User profile: brief refresh from atomic facts.
        all_facts = [f for c in cells_list for f in c.atomic_facts][:200]
        if all_facts:
            try:
                profile_prompt = (
                    "Summarize stable user attributes (preferences, recurring people, "
                    "long-term goals, communication style) from these facts in 4-6 lines:\n"
                    + "\n".join(f"- {f}" for f in all_facts)
                )
                self.user_profile = _gemini_call(profile_prompt, thinking_budget=1024)
            except Exception:
                self.user_profile = ""

    def answer(self, question: str) -> str:
        """Phase 3: Reconstructive Recollection."""
        if not self.cells:
            return "No information available."
        # Lazy-consolidate if not done yet.
        if not self.scenes:
            self.consolidate()

        # Step 1: find relevant scenes (coarse routing).
        scene_ids: list[str] = []
        if self._scenes_coll.count() > 0:
            try:
                res = self._scenes_coll.query(
                    query_texts=[question],
                    n_results=min(self.SCENE_TOP_K, self._scenes_coll.count()),
                )
                scene_ids = res.get("ids", [[]])[0]
            except Exception:
                pass
        scoped_cell_ids: set[str] = set()
        for sid in scene_ids:
            for sc in self.scenes:
                if sc.scene_id == sid:
                    scoped_cell_ids.update(sc.cell_ids)
                    break

        # Step 2: nucleus retrieval over MemCells (semantic + BM25).
        sem_hits: list[tuple[str, float]] = []
        if self._cells_coll.count() > 0:
            try:
                res = self._cells_coll.query(
                    query_texts=[question],
                    n_results=min(self.CELL_TOP_K, self._cells_coll.count()),
                )
                ids = res.get("ids", [[]])[0]
                dists = res.get("distances", [[]])[0]
                sem_hits = [(i, 1.0 - float(d)) for i, d in zip(ids, dists)]
            except Exception:
                pass
        # BM25 over atomic-fact bags.
        ids = list(self.cells.keys())
        bm_hits: list[tuple[str, float]] = []
        if ids:
            corpus = [_toks(" ".join(self.cells[i].atomic_facts)) for i in ids]
            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(_toks(question))
            order = sorted(range(len(scores)), key=lambda i: -scores[i])[:self.BM25_TOP_K]
            bm_hits = [(ids[i], float(scores[i])) for i in order if scores[i] > 0]

        # Combine + scope to relevant scenes (fall back to global if empty).
        score: dict[str, float] = defaultdict(float)
        for cid, s in sem_hits:
            score[cid] += s
        for cid, s in bm_hits:
            # Normalize BM25 to ~[0,1] roughly.
            score[cid] += min(s / 10.0, 1.0) * 0.5
        # Foresight boost.
        for cid, c in self.cells.items():
            if not c.foresight:
                continue
            for fs in c.foresight:
                if any(tok in question.lower() for tok in _toks(fs)[:5]):
                    score[cid] += self.FORESIGHT_BOOST
                    break
        if scoped_cell_ids:
            # Boost cells that fall in the routed scenes.
            for cid in list(score.keys()):
                if cid in scoped_cell_ids:
                    score[cid] += 1.0

        ranked = sorted(score.items(), key=lambda x: -x[1])[:10]
        if not ranked:
            return "No information available."

        ctx_parts: list[str] = []
        if self.user_profile:
            ctx_parts.append("USER PROFILE:\n" + self.user_profile)
        ctx_parts.append("RETRIEVED MEMORY CELLS:")
        for cid, _s in ranked:
            c = self.cells[cid]
            atom = "; ".join(c.atomic_facts[:8])
            ctx_parts.append(f"[{cid} | {c.session_date}] {atom}")
        ctx = "\n\n".join(ctx_parts)
        sys_inst = (
            "You are reasoning over a user's stored memory cells. "
            "Use only the cells shown to answer. Reason carefully, then "
            "produce ONLY the final answer on the last line.\n\n" + ctx
        )
        try:
            out = _gemini_call(
                f"Question: {question}\n\nFinal answer on the last line.",
                system_instruction=sys_inst, thinking_budget=2048)
            lines = [l.strip() for l in out.split("\n") if l.strip()]
            return lines[-1] if lines else out
        except Exception as e:
            return f"Error: {e}"

    def reset(self) -> None:
        self.cells.clear()
        self.scenes.clear()
        self.user_profile = ""
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"em_cells_{uid}", f"em_scenes_{uid}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._cells_coll = self._chroma.create_collection(
            name=f"em_cells_{uid}", metadata={"hnsw:space": "cosine"})
        self._scenes_coll = self._chroma.create_collection(
            name=f"em_scenes_{uid}", metadata={"hnsw:space": "cosine"})
