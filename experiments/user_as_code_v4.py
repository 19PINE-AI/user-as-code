"""
User as Code v4 — Exhaustive Extraction INTO Structured Code

The pipeline for each session:
1. Extract exhaustive facts (scratchpad — intermediate, not stored)
2. Organize facts into structured Python code (dataclasses, typed fields, dates)
3. Store the code as the primary representation (Tiers 1-2)
4. Store raw conversation in archive for retrieval fallback (Tier 3)

The code representation preserves ALL facts but in structured, typed form:
- date() objects for dates
- Typed dataclasses for entities (Person, Event, Trip, etc.)
- Lists for collections
- String annotations for preferences/opinions
- Explicit relationships between entities
"""

import json
import hashlib
import re

import chromadb
from google import genai

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()


class UserAsCodeV4:
    """User as Code with exhaustive extraction into structured code."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.code_state = ""  # The structured Python code — primary representation
        self.alerts = []

        # Tier 3: Archive
        self._chroma = chromadb.Client()
        uid_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for name in [f"v4_archive_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._archive = self._chroma.create_collection(
            name=f"v4_archive_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        """Ingest one session: extract facts, organize into code, store archive."""
        session_text = "\n".join(turns)

        # --- Tier 3: Store raw conversation in archive ---
        chunks = self._chunk_by_turns(session_text, session_id, session_date)
        if chunks:
            self._archive.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "date": session_date} for c in chunks],
            )

        # --- Tiers 1-2: Extract facts and organize into code ---
        self._extract_into_code(session_text, session_id, session_date)

    def _chunk_by_turns(self, text, session_id, date, chunk_size=300, overlap=75):
        """Chunk raw conversation for archive."""
        prefix = f"[{date}] " if date else ""
        segments = re.split(r'(?=\w+:)', text)
        segments = [s.strip() for s in segments if s.strip()]
        chunks, current, cw, idx = [], [], 0, 0
        for seg in segments:
            sw = len(seg.split())
            if cw + sw > chunk_size and current:
                chunks.append({"id": f"{session_id}_arc_{idx}", "text": f"{prefix}{' '.join(current)}"})
                idx += 1
                ow, start = 0, len(current)
                for j in range(len(current)-1, -1, -1):
                    ow += len(current[j].split())
                    if ow >= overlap: start = j; break
                current = current[start:]
                cw = sum(len(s.split()) for s in current)
            current.append(seg)
            cw += sw
        if current:
            chunks.append({"id": f"{session_id}_arc_{idx}", "text": f"{prefix}{' '.join(current)}"})
        return chunks

    def _extract_into_code(self, session_text, session_id, session_date):
        """Two-phase extraction: enumerate facts, then organize into typed Python code."""
        text = session_text[:12000] if len(session_text) > 12000 else session_text

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"""You are maintaining a Python code representation of everything known about users in a conversation.

CURRENT CODE STATE:
```python
{self.code_state if self.code_state else '# (empty — initialize from this session)'}
```

NEW CONVERSATION SESSION ({session_id}, {session_date}):
{text}

YOUR TASK:
1. First, mentally enumerate EVERY fact in this session — names, dates, times, numbers, places, events, activities, preferences, opinions, relationships, plans, emotions. Resolve relative dates ("yesterday", "last week") using the session date {session_date}.
2. Then, produce UPDATED Python code that incorporates ALL facts (both existing and new).

RULES FOR THE CODE:
- Use Python dataclasses with proper type annotations
- Use `date(year, month, day)` for all dates — NEVER store dates as strings
- Use typed lists for collections: `list[Event]`, `list[str]`
- Every dataclass MUST have a `notes: list[str]` field for facts that don't fit typed fields
- Organize by domain: people, events, activities, preferences, relationships
- PRESERVE all existing information — only add or update, never delete
- Add source session annotations as comments: `# source: session_1`

CRITICAL — TWO KINDS OF FACTS:
1. TYPED facts (dates, numbers, names, relationships) → store as typed fields with proper Python types
2. HARD-TO-TYPE facts (opinions, preferences, subtle context, implicit info, emotional states, nuanced details) → store in the `notes: list[str]` field of the relevant entity

The `notes` field is a CATCH-ALL: if a fact is about Caroline but doesn't fit a typed field, add it to `caroline.notes`. This ensures ZERO facts are lost. Every fact must appear somewhere — either as a typed field or as a note string.

Example:
```
@dataclass
class Person:
    name: str
    birthday: date
    notes: list[str]  # catch-all for hard-to-type facts

caroline = Person(
    name="Caroline",
    birthday=date(1995, 3, 15),
    notes=[
        "Considers friends and mentors to be her 'rocks'",
        "Would likely not pursue writing as a career",
    ]
)
```

Output ONLY the complete updated Python code (no explanations, no markdown fences):""",
                config=genai.types.GenerateContentConfig(
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=16384),
                    temperature=1.0,
                ),
            )
            new_code = response.text.strip()
            # Clean markdown fences if present
            if "```python" in new_code:
                new_code = new_code.split("```python")[1].split("```")[0]
            elif "```" in new_code:
                new_code = new_code.split("```")[1].split("```")[0]
            new_code = new_code.strip()
            if new_code and len(new_code) > 50:
                self.code_state = new_code
        except Exception as e:
            pass  # Keep existing state

    def retrieve(self, query: str, top_k: int = 8) -> str:
        """Retrieve: structured code (primary) + archive search (fallback)."""
        parts = []

        # Primary: structured code state
        if self.code_state:
            code = self.code_state
            if len(code) > 6000:
                code = code[:6000] + "\n# ... (truncated)"
            parts.append("=== User State (Python Code) ===")
            parts.append(code)

        # Fallback: archive search for details not in code
        if self._archive.count() > 0:
            try:
                results = self._archive.query(
                    query_texts=[query],
                    n_results=min(top_k, self._archive.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Conversation Excerpts ===")
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
        """Answer using code state + archive, with thinking."""
        context = self.retrieve(question)

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"{question}\n\nThink step by step using the stored information, then give ONLY a concise final answer on the last line.",
                config=genai.types.GenerateContentConfig(
                    system_instruction=f"""You have access to a user's stored information in Python code and conversation excerpts.
Use the information to answer the question. Think carefully about dates, relationships, and details.
If the answer requires computation (date differences, etc.), compute it from the code.
If the information is truly not available, say "No information available".

{context}""",
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
        self.code_state = ""
        self.alerts = []
        uid_hash = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        try:
            self._chroma.delete_collection(f"v4_archive_{uid_hash}")
        except Exception:
            pass
        self._archive = self._chroma.create_collection(
            name=f"v4_archive_{uid_hash}", metadata={"hnsw:space": "cosine"})
