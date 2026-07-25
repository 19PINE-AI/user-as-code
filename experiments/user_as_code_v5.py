"""
User as Code v5 — Two-Phase Architecture

Phase 1 (Memorizing): Append-only fact extraction per session
  - Extract every fact as a flat string (like v3)
  - Never overwrite, never lose facts
  - Store facts in vector DB for retrieval
  - Store raw conversation in archive for fallback

Phase 2 (Structuring): Periodically regenerate code from accumulated facts
  - Take the full fact list and organize into typed Python dataclasses
  - This is a READ-TIME operation, not write-time
  - Code is regenerated fresh each time from the complete fact corpus
  - No incremental overwrite → no fact loss

The key insight: memorizing (append-only) and structuring (code generation)
are separate concerns with different update patterns.
"""

import hashlib
import re

import chromadb
from krill_client import KRILL_MODEL, krill_call

MODEL = KRILL_MODEL


class UserAsCodeV5:
    """Two-phase User as Code: append-only facts + periodic code structuring."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

        # Phase 1 storage: append-only facts
        self.fact_list: list[str] = []          # ALL facts, ever, in order
        self.session_dates: dict[str, str] = {} # session_id -> date

        # Phase 2 output: structured code (regenerated periodically)
        self.code_state: str = ""
        self._code_stale: bool = True  # needs regeneration

        # Tier 3: Archive (raw conversation chunks)
        self._chroma = chromadb.Client()
        uid = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for name in [f"v5_archive_{uid}", f"v5_facts_{uid}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._archive = self._chroma.create_collection(
            name=f"v5_archive_{uid}", metadata={"hnsw:space": "cosine"})
        self._facts_db = self._chroma.create_collection(
            name=f"v5_facts_{uid}", metadata={"hnsw:space": "cosine"})

    # ---------------------------------------------------------------
    # Phase 1: Memorizing (per session, append-only)
    # ---------------------------------------------------------------

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        """Ingest one session: extract facts (append-only) + store raw archive."""
        session_text = "\n".join(turns)
        self.session_dates[session_id] = session_date

        # Store raw conversation in archive
        self._store_archive(session_text, session_id, session_date)

        # Extract facts and APPEND (never overwrite)
        new_facts = self._extract_facts(session_text, session_id, session_date)
        start_idx = len(self.fact_list)
        self.fact_list.extend(new_facts)

        # Index new facts in vector DB
        if new_facts:
            self._facts_db.add(
                documents=new_facts,
                ids=[f"f_{start_idx + i}" for i in range(len(new_facts))],
                metadatas=[{"session": session_id, "date": session_date}] * len(new_facts),
            )

        self._code_stale = True  # mark code as needing regeneration

    def _extract_facts(self, session_text: str, session_id: str, date: str) -> list[str]:
        """Extract every individual fact as a flat string. Thinking enabled."""
        text = session_text[:12000] if len(session_text) > 12000 else session_text
        try:
            response_text = krill_call(
                f"""Extract EVERY individual fact from this conversation as a numbered list.

Include absolutely everything:
- Names of people, places, organizations
- Dates and times (resolve "yesterday", "last week" etc. using session date: {date})
- Numbers, amounts, durations, ages
- Events that happened, are happening, or are planned
- Activities, hobbies, interests
- Preferences, opinions, likes, dislikes
- Relationships between people
- Emotions and feelings expressed
- Career, education, health information
- Any implicit facts (e.g., mentioning "my sister" = has a sister)

Rules:
- One fact per line, numbered
- Resolve all relative dates to absolute dates
- Include WHO the fact is about
- Do NOT summarize or combine facts
- Do NOT omit anything — completeness over conciseness

Session {session_id} ({date}):
{text}

List ALL facts:""",
                model=MODEL,
                thinking_budget=8192,
                temperature=1.0,
            )
            facts = []
            for line in response_text.split("\n"):
                line = re.sub(r'^\d+[\.\)]\s*', '', line.strip()).strip()
                if line and len(line) > 5 and not line.startswith('#'):
                    facts.append(f"[{session_id}, {date}] {line}")
            return facts
        except Exception as e:
            return [f"[{session_id}, {date}] {session_text[:200]}"]

    def _store_archive(self, text: str, session_id: str, date: str):
        """Store raw conversation chunks in archive."""
        prefix = f"[{date}] " if date else ""
        segments = re.split(r'(?=\w+:)', text)
        segments = [s.strip() for s in segments if s.strip()]
        chunks, current, cw, idx = [], [], 0, 0
        for seg in segments:
            sw = len(seg.split())
            if cw + sw > 300 and current:
                chunks.append({"id": f"{session_id}_a{idx}", "text": f"{prefix}{' '.join(current)}"})
                idx += 1
                ow, start = 0, len(current)
                for j in range(len(current)-1, -1, -1):
                    ow += len(current[j].split())
                    if ow >= 75: start = j; break
                current = current[start:]
                cw = sum(len(s.split()) for s in current)
            current.append(seg)
            cw += sw
        if current:
            chunks.append({"id": f"{session_id}_a{idx}", "text": f"{prefix}{' '.join(current)}"})
        if chunks:
            self._archive.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "date": date}] * len(chunks),
            )

    # ---------------------------------------------------------------
    # Phase 2: Structuring (regenerate code from all facts)
    # ---------------------------------------------------------------

    def structure(self):
        """Regenerate the structured Python code from ALL accumulated facts.
        This is a periodic operation — call after ingesting multiple sessions."""
        if not self.fact_list:
            self.code_state = "# No facts yet"
            return

        # Group facts into manageable chunks for the LLM
        # With ~50 facts/session and ~19 sessions, we may have ~950 facts
        # Send all of them (or as many as fit) to generate code
        all_facts = "\n".join(f"{i+1}. {f}" for i, f in enumerate(self.fact_list))

        # Truncate if extremely long (>30K chars)
        if len(all_facts) > 30000:
            all_facts = all_facts[:30000] + "\n... (truncated)"

        try:
            response_text = krill_call(
                f"""Organize ALL these facts into structured Python code using dataclasses.

FACTS ({len(self.fact_list)} total):
{all_facts}

RULES:
- Use Python dataclasses with proper type annotations
- Use date(year, month, day) for ALL dates — never store dates as strings
- Group by entity: create a dataclass per person, per event type, etc.
- Every dataclass should have a notes: list[str] field for facts that don't fit typed fields
- Include ALL facts — either as typed fields or in the notes list
- ZERO facts should be lost — if a fact doesn't fit a typed field, put it in notes
- Organize collections: people = [...], events = [...], etc.

Output ONLY Python code:""",
                model=MODEL,
                thinking_budget=16384,
                temperature=1.0,
            )
            code = response_text
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]
            self.code_state = code.strip()
            self._code_stale = False
        except Exception as e:
            self.code_state = f"# Structuring error: {e}\n# Facts: {len(self.fact_list)}"

    # ---------------------------------------------------------------
    # Retrieval and answering
    # ---------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 10) -> str:
        """Multi-strategy retrieval: code + facts + archive."""
        parts = []

        # 1. Structured code (if available and not stale)
        if self.code_state and not self._code_stale:
            code = self.code_state
            if len(code) > 6000:
                code = code[:6000] + "\n# ... (truncated)"
            parts.append("=== Structured User State (Python) ===")
            parts.append(code)

        # 2. Relevant facts from vector search
        if self._facts_db.count() > 0:
            try:
                results = self._facts_db.query(
                    query_texts=[query],
                    n_results=min(20, self._facts_db.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Facts ===")
                    for doc in results["documents"][0]:
                        parts.append(f"- {doc}")
            except Exception:
                pass

        # 3. Raw archive search (fallback for details)
        if self._archive.count() > 0:
            try:
                results = self._archive.query(
                    query_texts=[query],
                    n_results=min(top_k, self._archive.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Conversation Excerpts ===")
                    seen = set()
                    for doc in results["documents"][0]:
                        key = doc[:80]
                        if key not in seen:
                            seen.add(key)
                            parts.append(doc)
            except Exception:
                pass

        return "\n\n".join(parts)

    def answer(self, question: str) -> str:
        """Answer using multi-strategy retrieval + thinking."""
        # Auto-structure if stale and we have facts
        if self._code_stale and self.fact_list:
            self.structure()

        context = self.retrieve(question)

        try:
            response_text = krill_call(
                f"{question}\n\nThink step by step using the stored information, then give ONLY a concise final answer on the last line.",
                system_instruction=f"""You have access to a user's stored information: structured Python code, extracted facts, and conversation excerpts.
Use ALL available information to answer. Think carefully about dates, relationships, and details.
If the answer requires computation, compute it from the data.
If truly not available, say "No information available".

{context}""",
                model=MODEL,
                thinking_budget=2048,
                temperature=1.0,
            )
            text = response_text
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            return lines[-1] if len(lines) > 1 else text
        except Exception as e:
            return f"Error: {e}"

    def reset(self):
        self.fact_list = []
        self.session_dates = {}
        self.code_state = ""
        self._code_stale = True
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"v5_archive_{uid}", f"v5_facts_{uid}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._archive = self._chroma.create_collection(
            name=f"v5_archive_{uid}", metadata={"hnsw:space": "cosine"})
        self._facts_db = self._chroma.create_collection(
            name=f"v5_facts_{uid}", metadata={"hnsw:space": "cosine"})
