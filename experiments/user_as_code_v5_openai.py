"""User as Code v5 with OpenAI (GPT-5.4) backbone.

Drop-in replacement for user_as_code_v5.UserAsCodeV5 that swaps Gemini 3 Flash
for GPT-5.4 in fact extraction, code structuring, and answer generation. The
storage and retrieval architecture is unchanged so any difference in scores
isolates the LLM swap.
"""
import hashlib
import os
import re
import time

import chromadb
from openai import OpenAI

OPENAI_MODEL = os.environ.get("UAC_OPENAI_MODEL", "gpt-5.4")
oclient = OpenAI()


def _openai_chat(messages, max_completion_tokens=4096, max_retries=6):
    last_err = None
    for attempt in range(max_retries):
        try:
            r = oclient.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
            )
            return r.choices[0].message.content or ""
        except Exception as e:
            last_err = e
            err = str(e)
            if "rate" in err.lower() or "429" in err:
                wait = 15 * (attempt + 1)
            elif "5" in err[:3]:
                wait = 10 * (attempt + 1)
            else:
                wait = 5
            time.sleep(wait)
    raise RuntimeError(f"openai failed: {last_err}")


class UserAsCodeV5OpenAI:
    """Two-phase User as Code with GPT-5.4 backbone."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.fact_list: list[str] = []
        self.session_dates: dict[str, str] = {}
        self.code_state: str = ""
        self._code_stale: bool = True

        self._chroma = chromadb.Client()
        uid = hashlib.md5(user_id.encode()).hexdigest()[:8]
        for name in [f"v5oa_archive_{uid}", f"v5oa_facts_{uid}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._archive = self._chroma.create_collection(
            name=f"v5oa_archive_{uid}", metadata={"hnsw:space": "cosine"})
        self._facts_db = self._chroma.create_collection(
            name=f"v5oa_facts_{uid}", metadata={"hnsw:space": "cosine"})

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        session_text = "\n".join(turns)
        self.session_dates[session_id] = session_date
        self._store_archive(session_text, session_id, session_date)
        new_facts = self._extract_facts(session_text, session_id, session_date)
        start_idx = len(self.fact_list)
        self.fact_list.extend(new_facts)
        if new_facts:
            self._facts_db.add(
                documents=new_facts,
                ids=[f"f_{start_idx + i}" for i in range(len(new_facts))],
                metadatas=[{"session": session_id, "date": session_date}] * len(new_facts),
            )
        self._code_stale = True

    def _extract_facts(self, session_text: str, session_id: str, date: str) -> list[str]:
        text = session_text[:12000] if len(session_text) > 12000 else session_text
        prompt = f"""Extract EVERY individual fact from this conversation as a numbered list.

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

List ALL facts:"""
        try:
            out = _openai_chat(
                [{"role": "user", "content": prompt}],
                max_completion_tokens=8192,
            )
            facts = []
            for line in out.strip().split("\n"):
                line = re.sub(r"^\d+[\.\)]\s*", "", line.strip()).strip()
                if line and len(line) > 5 and not line.startswith("#"):
                    facts.append(f"[{session_id}, {date}] {line}")
            return facts
        except Exception as e:
            return [f"[{session_id}, {date}] {session_text[:200]}"]

    def _store_archive(self, text: str, session_id: str, date: str):
        prefix = f"[{date}] " if date else ""
        segments = re.split(r"(?=\w+:)", text)
        segments = [s.strip() for s in segments if s.strip()]
        chunks, current, cw, idx = [], [], 0, 0
        for seg in segments:
            sw = len(seg.split())
            if cw + sw > 300 and current:
                chunks.append({"id": f"{session_id}_a{idx}", "text": f"{prefix}{' '.join(current)}"})
                idx += 1
                ow, start = 0, len(current)
                for j in range(len(current) - 1, -1, -1):
                    ow += len(current[j].split())
                    if ow >= 75:
                        start = j
                        break
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

    def structure(self):
        if not self.fact_list:
            self.code_state = "# No facts yet"
            return
        all_facts = "\n".join(f"{i+1}. {f}" for i, f in enumerate(self.fact_list))
        if len(all_facts) > 30000:
            all_facts = all_facts[:30000] + "\n... (truncated)"
        prompt = f"""Organize ALL these facts into structured Python code using dataclasses.

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

Output ONLY Python code:"""
        try:
            code = _openai_chat([{"role": "user", "content": prompt}], max_completion_tokens=16384)
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]
            self.code_state = code.strip()
            self._code_stale = False
        except Exception as e:
            self.code_state = f"# Structuring error: {e}\n# Facts: {len(self.fact_list)}"

    def retrieve(self, query: str, top_k: int = 10) -> str:
        parts = []
        if self.code_state and not self._code_stale:
            code = self.code_state
            if len(code) > 6000:
                code = code[:6000] + "\n# ... (truncated)"
            parts.append("=== Structured User State (Python) ===")
            parts.append(code)
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
        if self._code_stale and self.fact_list:
            self.structure()
        context = self.retrieve(question)
        try:
            sys_prompt = f"""You have access to a user's stored information: structured Python code, extracted facts, and conversation excerpts.
Use ALL available information to answer. Think carefully about dates, relationships, and details.
If the answer requires computation, compute it from the data.
If truly not available, say "No information available".

{context}"""
            out = _openai_chat([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"{question}\n\nThink step by step using the stored information, then give ONLY a concise final answer on the last line."},
            ], max_completion_tokens=2048)
            text = (out or "").strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return lines[-1] if len(lines) > 1 else text
        except Exception as e:
            return f"Error: {e}"

    def reset(self):
        self.fact_list = []
        self.session_dates = {}
        self.code_state = ""
        self._code_stale = True
        uid = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"v5oa_archive_{uid}", f"v5oa_facts_{uid}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._archive = self._chroma.create_collection(
            name=f"v5oa_archive_{uid}", metadata={"hnsw:space": "cosine"})
        self._facts_db = self._chroma.create_collection(
            name=f"v5oa_facts_{uid}", metadata={"hnsw:space": "cosine"})
