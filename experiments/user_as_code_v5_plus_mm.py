"""
UaC v5 + MemMachine-style episode retrieval (additivity experiment).

Tests whether adding a SOTA retrieval mechanism (MemMachine's sentence-
level dense retrieval with ±3-sentence contextual expansion) on top of
UaC v5's existing multi-strategy retrieval (structured code + fact vector
+ raw archive) further improves accuracy on LOCOMO.

If accuracy is the same as plain UaC v5: structured code already contains
the information MemMachine's retrieval would surface.
If accuracy improves: the two mechanisms are complementary (additive).
If accuracy drops: the extra noise hurts the LLM's reasoning.
"""

from __future__ import annotations

import time
import hashlib

import chromadb
from chromadb.utils import embedding_functions

from user_as_code_v5 import UserAsCodeV5, gclient, MODEL
from google import genai


class UaCV5PlusMM(UserAsCodeV5):
    """UaC v5 augmented with MemMachine-style episode retrieval."""

    def __init__(self, user_id: str = "default"):
        super().__init__(user_id=user_id)
        # Sentence-level index for MemMachine-style retrieval.
        self._mm_sentences: list[str] = []
        self._mm_embed_fn = embedding_functions.DefaultEmbeddingFunction()
        uid = hashlib.md5(user_id.encode()).hexdigest()[:8]
        self._mm_coll_name = f"v5mm_sent_{uid}_{int(time.time())}"
        try:
            self._chroma.delete_collection(self._mm_coll_name)
        except Exception:
            pass
        self._mm_coll = self._chroma.create_collection(
            name=self._mm_coll_name,
            embedding_function=self._mm_embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_session(self, turns, session_id, session_date=""):
        # First do v5's normal ingest.
        super().ingest_session(turns, session_id, session_date)
        # Then build MemMachine-style sentence index over the same turns.
        # Each turn is one indexed sentence (MemMachine spec).
        ids = []
        docs = []
        for t in turns:
            idx = len(self._mm_sentences)
            self._mm_sentences.append(f"[{session_id} {session_date}] {t}")
            ids.append(f"mm{idx}")
            docs.append(self._mm_sentences[-1])
        if docs:
            self._mm_coll.add(documents=docs, ids=ids)

    def _mm_retrieve(self, query: str, top_k: int = 30) -> str:
        """MemMachine-style: nucleus + ±3 contextual expansion."""
        if not self._mm_sentences:
            return ""
        k = min(top_k, len(self._mm_sentences))
        try:
            res = self._mm_coll.query(query_texts=[query], n_results=k)
        except Exception:
            return ""
        idxs = []
        for sid in res["ids"][0]:
            try:
                idxs.append(int(sid.lstrip("mm")))
            except ValueError:
                pass
        expanded: set[int] = set()
        for i in idxs:
            for j in range(max(0, i - 3), min(len(self._mm_sentences), i + 4)):
                expanded.add(j)
        return "\n".join(self._mm_sentences[j] for j in sorted(expanded))

    def retrieve(self, query: str, top_k: int = 10) -> str:
        # Reuse v5's multi-strategy retrieval, then append MM episode context.
        base = super().retrieve(query, top_k=top_k)
        mm = self._mm_retrieve(query, top_k=30)
        if mm:
            base = base + "\n\n=== Episode Context (MemMachine-style) ===\n" + mm
        return base

    def reset(self):
        super().reset()
        try:
            self._chroma.delete_collection(self._mm_coll_name)
        except Exception:
            pass
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        self._mm_coll_name = f"v5mm_sent_{uid}_{int(time.time())}"
        self._mm_coll = self._chroma.create_collection(
            name=self._mm_coll_name,
            embedding_function=self._mm_embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._mm_sentences = []
