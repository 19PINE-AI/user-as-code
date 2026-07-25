"""Lightweight reimplementation of Hindsight (arXiv 2512.12818) for benchmarking.

Captures the architecture's load-bearing pieces:
- 4 logical fact networks (World / Experience / Opinion / Observation), all
  represented as typed Fact records with confidence and time ranges.
- 10-tuple Fact node: (subject, body, time, embedding, tau_s, tau_e, tau_m,
  label, confidence, extras).
- Coarse-grained chunking of conversation turns into 2-5 facts per turn via
  an LLM extractor.
- Four-channel retrieval (semantic / BM25 / graph spreading activation /
  temporal) fused with Reciprocal Rank Fusion (k=60), then cross-encoder
  rerank with `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- Token-budget packing for the final context.

Omitted for benchmark scope: the CARA disposition layer, opinion
formation/reinforcement (we keep facts as immutable records with confidence),
and the Tempr postgres-backed pgvector store (we use ChromaDB + an in-memory
BM25). These are documented in the paper's CARA section but do not affect
LOCOMO/LME accuracy directly — they shape the agent's voice and beliefs.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from krill_client import KRILL_MODEL, krill_call


GEMINI_MODEL = KRILL_MODEL


# ---------------------------------------------------------------------------
# Fact node
# ---------------------------------------------------------------------------

@dataclass
class Fact:
    """10-tuple fact node per Hindsight Section 3."""
    fact_id: str
    subject: str          # u
    body: str             # b
    mention_time: str     # τ_m  (when the user/assistant said it)
    occurrence_start: str # τ_s  (when the event begins)
    occurrence_end: str   # τ_e  (when the event ends; same as start for points)
    label: str            # ℓ : "world" | "experience" | "observation" | "opinion"
    confidence: float     # c
    extras: dict = field(default_factory=dict)


@dataclass
class Edge:
    """Directed edge between two facts."""
    src: str
    dst: str
    kind: str   # "entity" | "temporal" | "semantic" | "causal"
    weight: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenize(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(s or "")]


def _gemini_call(prompt: str, system_instruction: Optional[str] = None,
                 thinking_budget: int = 1024, max_retries: int = 4) -> str:
    return krill_call(
        prompt,
        system_instruction=system_instruction,
        model=GEMINI_MODEL,
        thinking_budget=thinking_budget,
        temperature=1.0,
        max_retries=max_retries,
    )


def _parse_dates(text: str, default: str) -> tuple[str, str]:
    """Best-effort range extraction. Returns (occurrence_start, occurrence_end)."""
    iso = re.findall(r"\d{4}-\d{2}-\d{2}", text or "")
    if len(iso) >= 2:
        return iso[0], iso[1]
    if len(iso) == 1:
        return iso[0], iso[0]
    return default, default


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACT_SYS = (
    "You extract structured facts from a user's conversation. "
    "Output ONLY a JSON array. Each element is an object with fields: "
    "subject (entity the fact is about, often the user), "
    "body (one-sentence factual statement), "
    "label (one of: world, experience, opinion, observation), "
    "confidence (0.0-1.0), "
    "occurrence_start (YYYY-MM-DD if known, else the session date), "
    "occurrence_end (YYYY-MM-DD; same as start if a point in time). "
    "Produce roughly 2-5 facts per conversational turn (so ~24-60 facts for "
    "a 12-turn session). No commentary."
)


def extract_facts_from_session(text: str, session_date: str) -> list[dict]:
    """Extract all facts for a session in one LLM call.

    The Hindsight paper specifies 2-5 facts per turn. We batch by session
    for efficiency (one LLM call instead of N), targeting the same per-turn
    density. The graph-construction stage still treats each fact as a
    separate node.
    """
    prompt = (
        f"Session date: {session_date}\n"
        f"Session transcript:\n{text[:12000]}\n\n"
        "Output JSON array of facts:"
    )
    try:
        out = _gemini_call(prompt, system_instruction=_EXTRACT_SYS, thinking_budget=4096)
    except Exception:
        return []
    out = re.sub(r"^```(?:json)?\s*", "", out.strip())
    out = re.sub(r"```\s*$", "", out.strip())
    try:
        arr = json.loads(out)
    except Exception:
        m = re.search(r"\[.*\]", out, re.DOTALL)
        if not m:
            return []
        try:
            arr = json.loads(m.group(0))
        except Exception:
            return []
    if not isinstance(arr, list):
        return []
    return arr


# ---------------------------------------------------------------------------
# HindsightSystem
# ---------------------------------------------------------------------------

class HindsightSystem:
    """4-network fact graph with multi-channel retrieval."""

    name = "hindsight"

    # Hyperparameters per Hindsight paper Section 4.
    SIGMA_T_DAYS = 30.0       # temporal-link decay scale
    THETA_S = 0.7             # semantic-link similarity threshold
    DELTA_GRAPH = 0.6         # spreading-activation decay per hop
    GRAPH_HOPS = 2            # 2 hops of spreading activation
    RRF_K = 60                # RRF fusion constant
    TOP_K_PER_CHANNEL = 30    # candidates per retrieval channel
    FINAL_K = 20              # facts kept after rerank
    TOKEN_BUDGET = 4000       # cap on context token budget

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.facts: dict[str, Fact] = {}
        self.edges: list[Edge] = []
        self._chroma = chromadb.Client()
        uid = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for n in [f"hs_facts_{uid}"]:
            try:
                self._chroma.delete_collection(n)
            except Exception:
                pass
        self._coll = self._chroma.create_collection(
            name=f"hs_facts_{uid}", metadata={"hnsw:space": "cosine"})
        self._reranker: Optional[CrossEncoder] = None

    def _get_reranker(self) -> CrossEncoder:
        if self._reranker is None:
            self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return self._reranker

    # -----------------------------------------------------------------------
    # Ingest
    # -----------------------------------------------------------------------

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = "") -> None:
        session_text = "\n".join(turns)
        extracted = extract_facts_from_session(session_text, session_date)
        for ei, e in enumerate(extracted):
            if not isinstance(e, dict):
                continue
            body = str(e.get("body", "")).strip()
            if not body:
                continue
            tau_s, tau_e = _parse_dates(
                f"{e.get('occurrence_start', '')} {e.get('occurrence_end', '')}",
                default=session_date or "1970-01-01",
            )
            fact = Fact(
                fact_id=f"{session_id}_f{ei}",
                subject=str(e.get("subject", "user")).strip(),
                body=body,
                mention_time=session_date,
                occurrence_start=tau_s,
                occurrence_end=tau_e,
                label=str(e.get("label", "experience")).strip().lower(),
                confidence=float(e.get("confidence", 0.8) or 0.8),
                extras={"session": session_id},
            )
            self._add_fact(fact)

    def _add_fact(self, f: Fact) -> None:
        self.facts[f.fact_id] = f
        self._coll.add(
            documents=[f.body],
            ids=[f.fact_id],
            metadatas=[{"session": f.extras.get("session", ""),
                        "occurrence_start": f.occurrence_start,
                        "label": f.label, "confidence": f.confidence}],
        )
        self._link_new_fact(f)

    def _link_new_fact(self, f: Fact) -> None:
        """Add typed edges between f and existing facts.

        - entity: same subject  → w=1.0
        - temporal: |Δt| < 90d  → w=exp(-Δt/σ_t)
        - semantic: cosine ≥ θ_s → w=cosine (computed lazily via embeddings query)
        """
        f_date = _try_parse_iso(f.occurrence_start)
        for other in list(self.facts.values()):
            if other.fact_id == f.fact_id:
                continue
            # Entity
            if other.subject and other.subject == f.subject:
                self.edges.append(Edge(f.fact_id, other.fact_id, "entity", 1.0))
            # Temporal
            o_date = _try_parse_iso(other.occurrence_start)
            if f_date and o_date:
                dt = abs((f_date - o_date).days)
                if dt < 90:
                    w = math.exp(-dt / self.SIGMA_T_DAYS)
                    self.edges.append(Edge(f.fact_id, other.fact_id, "temporal", w))
        # Semantic edges via embedding query
        try:
            res = self._coll.query(query_texts=[f.body], n_results=min(8, self._coll.count()))
            ids = res.get("ids", [[]])[0]
            dists = res.get("distances", [[]])[0]
            for sid, d in zip(ids, dists):
                if sid == f.fact_id:
                    continue
                sim = 1.0 - float(d)
                if sim >= self.THETA_S:
                    self.edges.append(Edge(f.fact_id, sid, "semantic", float(sim)))
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Retrieval channels
    # -----------------------------------------------------------------------

    def _semantic(self, query: str, k: int) -> list[tuple[str, float]]:
        if self._coll.count() == 0:
            return []
        res = self._coll.query(query_texts=[query], n_results=min(k, self._coll.count()))
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [(i, 1.0 - float(d)) for i, d in zip(ids, dists)]

    def _bm25(self, query: str, k: int) -> list[tuple[str, float]]:
        ids = list(self.facts.keys())
        if not ids:
            return []
        corpus = [_tokenize(self.facts[i].body) for i in ids]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(_tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(ids[i], float(scores[i])) for i in order if scores[i] > 0]

    def _graph_spreading(self, seed_ids: list[str], hops: int = 2) -> list[tuple[str, float]]:
        """A(f_j, t+1) = max A(f_i, t) * w * δ"""
        activation = {sid: 1.0 for sid in seed_ids}
        # Build adjacency
        adj: dict[str, list[Edge]] = defaultdict(list)
        for e in self.edges:
            adj[e.src].append(e)
            adj[e.dst].append(Edge(e.dst, e.src, e.kind, e.weight))
        for _ in range(hops):
            new_act: dict[str, float] = dict(activation)
            for fid, val in activation.items():
                for e in adj.get(fid, []):
                    cand = val * e.weight * self.DELTA_GRAPH
                    if cand > new_act.get(e.dst, 0.0):
                        new_act[e.dst] = cand
            activation = new_act
        return sorted(activation.items(), key=lambda x: -x[1])

    def _temporal(self, query: str, k: int) -> list[tuple[str, float]]:
        """Rule-based: pull explicit YYYY-MM-DD mentions and year tokens."""
        iso = re.findall(r"\d{4}-\d{2}-\d{2}", query)
        years = re.findall(r"\b(20\d{2})\b", query)
        if not iso and not years:
            return []
        scores: dict[str, float] = {}
        for fid, f in self.facts.items():
            score = 0.0
            for d in iso:
                if d == f.occurrence_start or d == f.occurrence_end:
                    score += 1.0
            for y in years:
                if f.occurrence_start.startswith(y):
                    score += 0.5
            if score > 0:
                scores[fid] = score
        return sorted(scores.items(), key=lambda x: -x[1])[:k]

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def answer(self, question: str) -> str:
        if not self.facts:
            return "No information available."

        # Run four channels.
        sem = self._semantic(question, self.TOP_K_PER_CHANNEL)
        kw = self._bm25(question, self.TOP_K_PER_CHANNEL)
        seeds = [s[0] for s in sem[:5]] + [s[0] for s in kw[:5]]
        graph = self._graph_spreading(seeds, hops=self.GRAPH_HOPS)[:self.TOP_K_PER_CHANNEL]
        temp = self._temporal(question, self.TOP_K_PER_CHANNEL)

        # RRF fuse
        ranks: dict[str, dict[int, int]] = defaultdict(dict)
        for ch, lst in enumerate([sem, kw, graph, temp]):
            for r, (fid, _s) in enumerate(lst):
                ranks[fid][ch] = r + 1
        rrf_score: dict[str, float] = {}
        for fid, by_ch in ranks.items():
            rrf_score[fid] = sum(1.0 / (self.RRF_K + r) for r in by_ch.values())
        ordered = sorted(rrf_score.items(), key=lambda x: -x[1])[:50]

        # Cross-encoder rerank.
        candidates = [self.facts[fid] for fid, _s in ordered]
        if candidates:
            try:
                pairs = [(question, f.body) for f in candidates]
                ce_scores = self._get_reranker().predict(pairs)
                reranked = sorted(zip(candidates, ce_scores), key=lambda x: -x[1])
            except Exception:
                reranked = [(f, 0.0) for f in candidates]
        else:
            reranked = []
        top = [f for f, _s in reranked[:self.FINAL_K]]

        # Token-budget pack.
        ctx_lines: list[str] = []
        budget = self.TOKEN_BUDGET
        for f in top:
            line = f"[{f.occurrence_start}] {f.body} (label={f.label}, conf={f.confidence:.2f})"
            est = len(line.split()) * 1.3  # rough token estimate
            if est > budget:
                continue
            budget -= est
            ctx_lines.append(line)

        ctx = "\n".join(ctx_lines) if ctx_lines else "No relevant facts."
        sys_inst = (
            "You will answer a question about a user using only the retrieved "
            "facts below. Reason carefully through the facts and produce ONLY "
            "the final answer on the last line.\n\nFacts:\n" + ctx
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
        self.facts.clear()
        self.edges.clear()
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        try:
            self._chroma.delete_collection(f"hs_facts_{uid}")
        except Exception:
            pass
        self._coll = self._chroma.create_collection(
            name=f"hs_facts_{uid}", metadata={"hnsw:space": "cosine"})


def _try_parse_iso(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
