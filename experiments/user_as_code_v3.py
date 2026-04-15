"""
User as Code v3 — Enhanced Extraction for Maximum Recall

Key improvements over v2:
1. Exhaustive fact extraction: enumerate EVERY fact before structuring
2. No token limits on extraction or summarization
3. Thinking enabled for extraction (catches implicit facts)
4. Dual representation: structured code + exhaustive fact list
5. Append-only fact accumulation (never drop facts from earlier sessions)
6. Session summaries are exhaustive, not concise
"""

import json
import hashlib
import re
from collections import defaultdict

import chromadb
from google import genai

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()


class UserAsCodeV3:
    """Full User as Code with enhanced extraction for maximum recall."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.structured_state = ""       # Tier 1-2: Python code
        self.fact_list = []              # Exhaustive fact list (append-only)
        self.session_summaries = {}      # session_id -> exhaustive summary
        self.alerts = []

        # Tier 3: Archive in ChromaDB
        self._chroma = chromadb.Client()
        uid_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for name in [f"v3_episodes_{uid_hash}", f"v3_facts_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass

        self._episodes = self._chroma.create_collection(
            name=f"v3_episodes_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )
        self._facts_collection = self._chroma.create_collection(
            name=f"v3_facts_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        """Ingest one conversation session with exhaustive extraction."""
        session_text = "\n".join(turns)
        date_prefix = f"[{session_date}] " if session_date else ""

        # --- 1. Store raw episodes (unchanged from v2) ---
        chunks = self._chunk_by_turns(session_text, session_id, date_prefix)
        if chunks:
            self._episodes.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "date": session_date} for c in chunks],
            )

        # --- 2. EXHAUSTIVE fact extraction (new in v3) ---
        new_facts = self._extract_all_facts(session_text, session_id, session_date)
        if new_facts:
            # Append to running fact list (never overwrite)
            start_idx = len(self.fact_list)
            self.fact_list.extend(new_facts)
            # Store in vector DB for retrieval
            self._facts_collection.add(
                documents=new_facts,
                ids=[f"fact_{session_id}_{i}" for i in range(len(new_facts))],
                metadatas=[{"session": session_id, "date": session_date}] * len(new_facts),
            )

        # --- 3. Exhaustive session summary ---
        summary = self._exhaustive_summary(session_text, session_id, session_date)
        if summary:
            self.session_summaries[session_id] = summary

        # --- 4. Update structured state ---
        self._update_structured_state(session_text, session_id, session_date)

    def _chunk_by_turns(self, text, session_id, prefix, chunk_size=300, overlap=75):
        """Chunk by speaker turns."""
        segments = re.split(r'(?=\w+:)', text)
        segments = [s.strip() for s in segments if s.strip()]
        chunks, current, current_words, idx = [], [], 0, 0

        for seg in segments:
            sw = len(seg.split())
            if current_words + sw > chunk_size and current:
                chunks.append({"id": f"{session_id}_ep_{idx}", "text": f"{prefix}{' '.join(current)}"})
                idx += 1
                # Overlap
                ow, start = 0, len(current)
                for j in range(len(current)-1, -1, -1):
                    ow += len(current[j].split())
                    if ow >= overlap: start = j; break
                current = current[start:]
                current_words = sum(len(s.split()) for s in current)
            current.append(seg)
            current_words += sw

        if current:
            chunks.append({"id": f"{session_id}_ep_{idx}", "text": f"{prefix}{' '.join(current)}"})
        return chunks

    def _extract_all_facts(self, session_text, session_id, date):
        """Extract EVERY individual fact as a separate statement. Thinking enabled."""
        text = session_text[:12000] if len(session_text) > 12000 else session_text

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"""Extract EVERY individual fact from this conversation as a numbered list.
Include absolutely everything: names, dates, times, numbers, places, events, activities,
preferences, opinions, relationships, plans, emotions, medical info, financial info.

Rules:
- One fact per line
- Include specific dates (resolve "yesterday", "last week" etc. using the session date: {date})
- Include exact numbers, amounts, durations
- Include who said/did what
- Include implicit facts (e.g., if someone mentions "my sister", that's a fact about having a sister)
- Do NOT summarize or combine — list each fact separately
- Do NOT omit anything — completeness is more important than conciseness

Session {session_id} ({date}):
{text}

List ALL facts (one per line, numbered):""",
                config=genai.types.GenerateContentConfig(
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
                    temperature=1.0,
                ),
            )
            # Parse numbered list
            facts = []
            for line in response.text.strip().split("\n"):
                line = line.strip()
                # Remove numbering
                line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if line and len(line) > 5 and not line.startswith('#'):
                    facts.append(f"[{session_id}, {date}] {line}")
            return facts
        except Exception as e:
            return [f"[{session_id}] {session_text[:200]}"]

    def _exhaustive_summary(self, session_text, session_id, date):
        """Generate an EXHAUSTIVE summary — include everything, no length limit."""
        text = session_text[:12000] if len(session_text) > 12000 else session_text

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"""Write an exhaustive summary of this conversation session.
Include EVERY detail: all names, dates, numbers, places, events, preferences, plans, relationships.
Do NOT omit any information. Length is not a concern — completeness is.

Session {session_id} ({date}):
{text}

Exhaustive summary:""",
                config=genai.types.GenerateContentConfig(
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=1024),
                    temperature=1.0,
                ),
            )
            return response.text.strip()
        except Exception as e:
            return session_text[:500]

    def _update_structured_state(self, session_text, session_id, date):
        """Update structured Python state. Uses fact list to avoid missing facts."""
        # Include recent facts in the prompt to help the LLM
        recent_facts = "\n".join(self.fact_list[-50:]) if self.fact_list else "(no facts yet)"
        text = session_text[:10000] if len(session_text) > 10000 else session_text

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"""Update the structured Python state below with ALL information from this session.
IMPORTANT: Do NOT drop any existing facts. Only add new information or update conflicts (newer wins).

Current state:
{self.structured_state if self.structured_state else '# (empty)'}

Extracted facts from this session:
{recent_facts}

Raw session ({session_id}, {date}):
{text}

Output ONLY updated Python code with ALL facts preserved:""",
                config=genai.types.GenerateContentConfig(
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=1024),
                    temperature=1.0,
                ),
            )
            new_state = response.text.strip()
            if "```python" in new_state:
                new_state = new_state.split("```python")[1].split("```")[0]
            elif "```" in new_state:
                new_state = new_state.split("```")[1].split("```")[0]
            self.structured_state = new_state.strip()
        except Exception:
            pass

    def retrieve(self, query: str, top_k: int = 10) -> str:
        """Multi-strategy retrieval: state + facts + summaries + episodes."""
        parts = []

        # Strategy 1: Structured state
        if self.structured_state:
            state = self.structured_state
            if len(state) > 4000:
                state = state[:4000] + "\n# ... (truncated)"
            parts.append("=== Structured State ===")
            parts.append(state)

        # Strategy 2: Relevant facts from fact list (vector search)
        if self._facts_collection.count() > 0:
            try:
                results = self._facts_collection.query(
                    query_texts=[query],
                    n_results=min(15, self._facts_collection.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Facts ===")
                    for doc in results["documents"][0]:
                        parts.append(f"- {doc}")
            except Exception:
                pass

        # Strategy 3: Relevant session summaries
        relevant_summaries = []
        for sid, summary in self.session_summaries.items():
            # Simple keyword overlap to find relevant summaries
            query_words = set(query.lower().split())
            summary_words = set(summary.lower().split())
            if len(query_words & summary_words) >= 2:
                relevant_summaries.append(summary)
        if relevant_summaries:
            parts.append("\n=== Relevant Session Summaries ===")
            for s in relevant_summaries[:3]:
                parts.append(s[:1000])

        # Strategy 4: Raw episode search
        if self._episodes.count() > 0:
            try:
                results = self._episodes.query(
                    query_texts=[query],
                    n_results=min(top_k, self._episodes.count()),
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
        context = self.retrieve(question)

        system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer. Think carefully, then give a concise final answer.
Resolve relative dates using session timestamps. If not available, say "No information available".

Context:
{context}"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"{question}\n\nThink step by step, then give ONLY a concise final answer on the last line.",
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
        self.fact_list = []
        self.session_summaries = {}
        self.alerts = []
        uid_hash = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"v3_episodes_{uid_hash}", f"v3_facts_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._episodes = self._chroma.create_collection(
            name=f"v3_episodes_{uid_hash}", metadata={"hnsw:space": "cosine"})
        self._facts_collection = self._chroma.create_collection(
            name=f"v3_facts_{uid_hash}", metadata={"hnsw:space": "cosine"})
