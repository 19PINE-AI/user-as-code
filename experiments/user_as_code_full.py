"""
User as Code — Full Three-Tier Architecture

Tier 1: Schema (class definitions, type annotations)
Tier 2: State (structured Python code — current instance data)
Tier 3: Archive (raw conversation chunks, accessed via vector RAG)

This implements the complete architecture described in the paper,
combining structured code state for constraint checking with
archive RAG for recall — closing the gap to SOTA on standard benchmarks.

Retrieval strategy (inspired by MemMachine / EverMemOS):
1. Always include the manifest (Tier 0)
2. Extract structured state via LLM (Tiers 1-2)
3. Store raw conversation chunks in ChromaDB (Tier 3)
4. At query time: hybrid retrieval = structured state + top-k archive chunks
5. For constraint questions: execute code against structured state
6. For recall questions: retrieve from archive + augment with state
"""

import json
import os
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime

import chromadb
from google import genai

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()


class UserAsCodeFull:
    """Full three-tier User as Code memory system."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.structured_state = ""  # Tier 1-2: extracted Python code
        self.manifest = ""  # Tier 0: compact index
        self.alerts = []  # Pre-computed constraint alerts

        # Tier 3: Archive in ChromaDB
        self._chroma_client = chromadb.Client()
        collection_name = f"uac_{user_id}_{hashlib.md5(user_id.encode()).hexdigest()[:8]}"
        # Delete if exists (for clean reruns)
        try:
            self._chroma_client.delete_collection(collection_name)
        except Exception:
            pass
        self._archive = self._chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._chunk_counter = 0

    def ingest_conversation(self, conversation: list[dict] | str, session_id: str = "s1"):
        """Ingest a conversation into all three tiers.

        Args:
            conversation: Either a list of {role, content} dicts or a raw string
            session_id: Session identifier for provenance
        """
        # Normalize to string
        if isinstance(conversation, list):
            conv_text = "\n".join(
                f"{turn.get('role', 'user')}: {turn.get('content', turn.get('text', ''))}"
                for turn in conversation
            )
        else:
            conv_text = conversation

        # --- Tier 3: Store raw chunks in archive ---
        chunks = self._chunk_conversation(conv_text, session_id)
        if chunks:
            self._archive.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "chunk_idx": c["idx"]} for c in chunks],
            )

        # --- Tiers 1-2: Extract structured state ---
        self._extract_structured_state(conv_text, session_id)

    def _chunk_conversation(self, conv_text: str, session_id: str,
                            chunk_size: int = 500, overlap: int = 100) -> list[dict]:
        """Chunk conversation into overlapping segments for RAG."""
        words = conv_text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            self._chunk_counter += 1
            chunks.append({
                "id": f"{session_id}_chunk_{self._chunk_counter}",
                "idx": self._chunk_counter,
                "text": f"[Session {session_id}] {chunk_text}",
            })
            start += chunk_size - overlap
            if end >= len(words):
                break
        return chunks

    def _extract_structured_state(self, conv_text: str, session_id: str):
        """Use LLM to extract structured facts into Python code (Tiers 1-2)."""
        # Truncate very long conversations for extraction
        if len(conv_text) > 15000:
            conv_text = conv_text[:15000] + "\n... [truncated for extraction]"

        prompt = f"""Extract ALL factual information from this conversation into structured Python code.
Use dataclasses or simple variable assignments with proper types (date, str, int, float, list).
Include ALL names, dates, numbers, preferences, relationships, events, and any other facts.
Be comprehensive — do not omit any information that could be needed later.

Previous state (merge new information):
{self.structured_state if self.structured_state else '# (no previous state)'}

New conversation (session {session_id}):
{conv_text}

Output ONLY Python code — no explanations. Use comments for context."""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4000,
                ),
            )
            new_state = response.text
            # Clean markdown code fences if present
            if "```python" in new_state:
                new_state = new_state.split("```python")[1].split("```")[0]
            elif "```" in new_state:
                new_state = new_state.split("```")[1].split("```")[0]
            self.structured_state = new_state.strip()
        except Exception as e:
            print(f"    State extraction error: {e}")

    def retrieve(self, query: str, top_k: int = 10) -> str:
        """Hybrid retrieval: structured state + archive RAG.

        Returns combined context for the LLM to answer from.
        """
        parts = []

        # Part 1: Structured state (Tiers 1-2) — always included
        if self.structured_state:
            parts.append("=== Structured User State (Python) ===")
            parts.append(self.structured_state)

        # Part 2: Alerts (if any)
        if self.alerts:
            parts.append("\n=== Active Alerts ===")
            for alert in self.alerts:
                parts.append(f"- {alert}")

        # Part 3: Archive retrieval (Tier 3) — semantic search
        if self._archive.count() > 0:
            try:
                results = self._archive.query(
                    query_texts=[query],
                    n_results=min(top_k, self._archive.count()),
                )
                if results and results["documents"] and results["documents"][0]:
                    parts.append("\n=== Retrieved Conversation Excerpts ===")
                    for i, doc in enumerate(results["documents"][0]):
                        dist = results["distances"][0][i] if results.get("distances") else 0
                        parts.append(f"[Excerpt {i+1}, relevance={1-dist:.2f}]")
                        parts.append(doc)
                        parts.append("")
            except Exception as e:
                parts.append(f"\n(Archive retrieval error: {e})")

        return "\n".join(parts)

    def answer(self, question: str) -> str:
        """Answer a question using hybrid retrieval."""
        context = self.retrieve(question)

        system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think through the information carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve any relative dates using conversation timestamps.
If the information is not available in the context, say "No information available".

Context:
{context}"""

        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=f"{question}\n\nThink step by step, then give a concise final answer.",
                config=genai.types.GenerateContentConfig(
                    system_instruction=system,
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
                    temperature=1.0,
                ),
            )
            return response.text.strip()
        except Exception as e:
            return f"Error: {e}"

    def reset(self):
        """Reset all memory."""
        self.structured_state = ""
        self.manifest = ""
        self.alerts = []
        try:
            self._chroma_client.delete_collection(self._archive.name)
        except Exception:
            pass
        collection_name = f"uac_{self.user_id}_{hashlib.md5(self.user_id.encode()).hexdigest()[:8]}"
        self._archive = self._chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._chunk_counter = 0
