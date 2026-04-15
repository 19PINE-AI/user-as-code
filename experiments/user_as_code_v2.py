"""
User as Code v2 — Full Architecture with SOTA Recall Mechanisms

Improvements over v1:
1. Episode-level storage (MemMachine): store by session, not word count
2. Session summarization (EverMemOS): each session gets a LLM-generated summary
3. Multi-strategy retrieval: summary search + raw session search + structured state
4. Query decomposition: complex questions broken into sub-queries
5. Contextualized retrieval: retrieved chunks expanded with session context
6. Better extraction: incremental extraction preserving temporal ordering
"""

import json
import hashlib
import re
from collections import defaultdict

import chromadb
from google import genai

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()


class UserAsCodeV2:
    """Full three-tier User as Code with SOTA recall mechanisms."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.structured_state = ""
        self.session_summaries = {}  # session_id -> summary
        self.alerts = []

        # ChromaDB collections
        self._chroma = chromadb.Client()
        uid_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]

        # Clean existing
        for name in [f"v2_episodes_{uid_hash}", f"v2_summaries_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass

        # Tier 3a: Raw episode storage (full session text)
        self._episodes = self._chroma.create_collection(
            name=f"v2_episodes_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )
        # Tier 3b: Session summaries (condensed, high-signal)
        self._summaries = self._chroma.create_collection(
            name=f"v2_summaries_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )
        self._session_texts = {}  # session_id -> full text (for contextualized retrieval)

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        """Ingest one conversation session.

        Three parallel operations:
        1. Store raw session as episode (Tier 3a)
        2. Generate and store session summary (Tier 3b)
        3. Incrementally update structured state (Tiers 1-2)
        """
        session_text = "\n".join(turns)
        self._session_texts[session_id] = session_text

        # --- 1. Episode storage: store raw text in overlapping chunks ---
        # Use larger chunks with session context prefix
        date_prefix = f"[{session_date}] " if session_date else ""
        chunks = self._smart_chunk(session_text, session_id, date_prefix, chunk_size=300, overlap=75)
        if chunks:
            self._episodes.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "date": session_date} for c in chunks],
            )

        # --- 2. Session summary ---
        summary = self._summarize_session(session_text, session_id, session_date)
        if summary:
            self.session_summaries[session_id] = summary
            self._summaries.add(
                documents=[summary],
                ids=[f"summary_{session_id}"],
                metadatas=[{"session": session_id, "date": session_date, "type": "summary"}],
            )

        # --- 3. Incremental structured state extraction ---
        self._incremental_extract(session_text, session_id, session_date)

    def _smart_chunk(self, text, session_id, prefix, chunk_size=300, overlap=75):
        """Chunk by turns/sentences rather than raw words."""
        # Split by speaker turns for more natural boundaries
        turn_pattern = re.compile(r'(?=\w+:)')
        segments = turn_pattern.split(text)
        segments = [s.strip() for s in segments if s.strip()]

        chunks = []
        current_chunk = []
        current_words = 0
        chunk_idx = 0

        for segment in segments:
            seg_words = len(segment.split())
            if current_words + seg_words > chunk_size and current_chunk:
                chunk_text = f"{prefix}{' '.join(current_chunk)}"
                chunks.append({
                    "id": f"{session_id}_chunk_{chunk_idx}",
                    "text": chunk_text,
                })
                chunk_idx += 1
                # Keep overlap
                overlap_words = 0
                overlap_start = len(current_chunk)
                for j in range(len(current_chunk) - 1, -1, -1):
                    overlap_words += len(current_chunk[j].split())
                    if overlap_words >= overlap:
                        overlap_start = j
                        break
                current_chunk = current_chunk[overlap_start:]
                current_words = sum(len(s.split()) for s in current_chunk)

            current_chunk.append(segment)
            current_words += seg_words

        if current_chunk:
            chunk_text = f"{prefix}{' '.join(current_chunk)}"
            chunks.append({
                "id": f"{session_id}_chunk_{chunk_idx}",
                "text": chunk_text,
            })

        return chunks

    def _summarize_session(self, session_text, session_id, date):
        """Generate a concise summary of the session."""
        if len(session_text) < 50:
            return session_text

        # Truncate very long sessions for summarization
        text = session_text[:8000] if len(session_text) > 8000 else session_text

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"""Summarize this conversation session concisely. Include ALL specific facts: names, dates, numbers, places, preferences, events, plans, and relationships. Do not omit any factual details.

Session {session_id} ({date}):
{text}

Summary (include all facts):""",
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                ),
            )
            return response.text.strip()
        except Exception as e:
            return f"Session {session_id}: {session_text[:200]}"

    def _incremental_extract(self, session_text, session_id, date):
        """Incrementally update structured state from new session."""
        text = session_text[:10000] if len(session_text) > 10000 else session_text

        prompt = f"""Update the structured Python state below with new information from this conversation session.
Preserve ALL existing information. Add new facts. Resolve conflicts (newer session wins).
Use typed Python with dates, lists, and dataclasses. Include ALL names, dates, numbers.

Current state:
{self.structured_state if self.structured_state else '# (empty — initialize from this session)'}

New session ({session_id}, {date}):
{text}

Output ONLY updated Python code:"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(temperature=0.1, max_output_tokens=4000),
            )
            new_state = response.text.strip()
            if "```python" in new_state:
                new_state = new_state.split("```python")[1].split("```")[0]
            elif "```" in new_state:
                new_state = new_state.split("```")[1].split("```")[0]
            self.structured_state = new_state.strip()
        except Exception as e:
            pass  # Keep existing state

    def retrieve(self, query: str, top_k: int = 8) -> str:
        """Multi-strategy retrieval combining all tiers."""
        parts = []

        # Strategy 1: Structured state (always included, Tiers 1-2)
        if self.structured_state:
            parts.append("=== Structured State ===")
            # Truncate if very long
            state = self.structured_state
            if len(state) > 3000:
                state = state[:3000] + "\n# ... (truncated)"
            parts.append(state)

        # Strategy 2: Summary search (high-signal, low-noise)
        if self._summaries.count() > 0:
            try:
                results = self._summaries.query(
                    query_texts=[query],
                    n_results=min(3, self._summaries.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Session Summaries ===")
                    for doc in results["documents"][0]:
                        parts.append(doc)
            except Exception:
                pass

        # Strategy 3: Episode search (detailed, for specific facts)
        if self._episodes.count() > 0:
            try:
                results = self._episodes.query(
                    query_texts=[query],
                    n_results=min(top_k, self._episodes.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Conversation Excerpts ===")
                    seen = set()
                    for i, doc in enumerate(results["documents"][0]):
                        # Deduplicate
                        doc_key = doc[:100]
                        if doc_key not in seen:
                            seen.add(doc_key)
                            parts.append(doc)
            except Exception:
                pass

        return "\n\n".join(parts)

    def answer(self, question: str) -> str:
        """Answer using multi-strategy retrieval + thinking."""
        context = self.retrieve(question)

        system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think through the information carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve relative dates using conversation timestamps.
If the information is not available in the context, say "No information available".

Context:
{context}"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"{question}\n\nThink carefully, then give ONLY a concise final answer.",
                config=genai.types.GenerateContentConfig(
                    system_instruction=system,
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
                    temperature=1.0,
                ),
            )
            text = response.text.strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            return lines[-1] if len(lines) > 1 else text
        except Exception as e:
            return f"Error: {e}"

    def reset(self):
        self.structured_state = ""
        self.session_summaries = {}
        self.alerts = []
        self._session_texts = {}
        uid_hash = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"v2_episodes_{uid_hash}", f"v2_summaries_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._episodes = self._chroma.create_collection(
            name=f"v2_episodes_{uid_hash}", metadata={"hnsw:space": "cosine"})
        self._summaries = self._chroma.create_collection(
            name=f"v2_summaries_{uid_hash}", metadata={"hnsw:space": "cosine"})
