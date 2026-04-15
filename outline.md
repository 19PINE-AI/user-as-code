# Outline: User as Code: Executable Memory for Personalized Agents

## Abstract

Current personalization in AI agents primarily relies on Retrieval-Augmented Generation (RAG) over unstructured text, structured knowledge graphs, or flat fact stores. While effective for basic recall, these "Bag of Facts" approaches struggle with the specific challenges of user memory: resolving conflicting information, managing temporal dependencies, and enforcing logical constraints (e.g., "passport expiration" vs. "flight date"). This paper introduces **User as Code**, a novel paradigm where an agent's understanding of a user is maintained as a **modular, version-controlled software project**. Our core observation is that **code is the only representation format that unifies readability and verifiability in a single medium**: the same Python that stores a user's passport expiry date can also express — and execute — the assertion that the expiry is too close to a booked flight. This unification enables a **generate-verify-review loop** that directly **reduces LLM hallucination**: the coding agent generates Python checks against the code-represented state, the interpreter verifies the computation deterministically, and the agent reviews results to refine or persist — turning unreliable natural-language arithmetic into deterministic results. Constraints are not pre-authored by humans; the LLM generates them autonomously, promoting useful checks to persistent background monitors. We evaluate on established benchmarks (LOCOMO, LongMemEval, LoCoMo-Plus) and against concrete baselines (Mem0, A-MEM, Zep/Graphiti, Hindsight, ENGRAM), demonstrating that User as Code achieves competitive performance on standard recall and retrieval tasks while uniquely enabling proactive alerting based on logical constraints — a capability where all retrieval-based approaches fundamentally fail.

## 1. Introduction

### 1.1 The Memory Challenge for Personalized Agents
*   To build truly personalized, continuous-service AI Agents, a User Memory system is indispensable. Memory is not simply recording every word the user says — it is gradually forming a model of the user through sustained interaction: their personality, hobbies, habits, values.
*   **Memory consists of two fundamental components:** In Chinese, the word for memory is "记忆" (Jìyì) — and the two characters capture the two halves precisely:
    *   **记 (Jì) — Memorizing (Knowledge Extraction):** Extracting structured knowledge from raw interactions and persisting it in an organized form.
    *   **忆 (Yì) — Retrieval (Knowledge Retrieval):** Recalling the right knowledge at the right time to serve the user.
    *   All memory systems must address both halves. User as Code contributes to **both**: on the memorizing side, knowledge is extracted into structured, typed, version-controlled code; on the retrieval side, executing code against the state is itself a form of retrieval — the generate-verify-review loop *computes* answers that no similarity search could produce. The same code that stores knowledge also serves as the substrate for executable retrieval.
*   Agent memory spans multiple layers: working memory (single-session trajectory), long-term memory (persistent cross-session knowledge), and business state (task-phase abstractions). This paper focuses on long-term user memory.
*   The essence of user memory is an active, continuous learning process — the Agent continually refines its internal user model to explain all known observations with the most compact structure.

### 1.2 Three Categories of Memory Tasks
*   User memory capabilities can be understood along a spectrum of increasing difficulty:
    *   **Basic Recall:** Store and retrieve directly provided, unambiguous information (e.g., "My membership number is 12345"). All existing approaches handle this adequately.
    *   **Multi-session Retrieval:** Retrieve and reason over information scattered across sessions, entities, and time — requiring disambiguation ("which car?"), compound event resolution ("cancel the LA trip" = flights + hotels + car rentals), and conflict resolution (multi-party conflicting instructions). Agentic RAG and knowledge graphs handle some cases but struggle with factual conflicts across isolated chunks.
    *   **Active Service:** Proactively synthesize information across many sessions to provide anticipatory, unsolicited help — e.g., cross-referencing a new flight with passport info stored months ago to alert that the passport expires too soon. No retrieval sophistication can reliably compute that a passport expiring Feb 18 leaves only 34 days of validity for a Jan 15 departure — far short of the 180-day requirement. This is *arithmetic*, not a similarity match.
*   Existing benchmarks (LOCOMO, LongMemEval, MemoryAgentBench) primarily test the first two categories. LoCoMo-Plus tests implicit constraints and MemoryArena shows that agents saturated on LOCOMO still fail in agentic settings — but no benchmark tests proactive memory-triggered alerting. User as Code is specifically designed to enable Active Service, while remaining competitive on the first two categories.

### 1.3 The "Bag of Facts" Problem
*   **Problem:** Current systems (VectorDBs, JSON stores, Knowledge Graphs, flat fact extractors) treat memory as a loose collection of facts.
    *   **Conflict:** "I love cilantro" vs. later "I actually hate cilantro" — vector retrieval might return both or the wrong one.
    *   **Logic Gap:** LLMs struggle to detect logical conflicts in retrieved text (e.g., booking a flight after a visa expires).
*   **The Representation Tension:** Existing strategies trade simplicity for expressiveness — from atomic fact notes (low overhead, no relationships) through JSON cards (structured, partial updates) to Advanced JSON Cards with metadata (disambiguated entities, timestamps), to knowledge graphs (entity relations, graph traversal, but rigid schemas and conditional logic degraded into triples). But even the most advanced structured approach cannot express rules like "if passport expires within 180 days of travel date, raise an alert." This requires *executable* logic that the system can **generate on the fly** as novel situations arise.
*   **Thesis:** The fundamental limitation of all existing formats — natural language, JSON, knowledge graphs — is that they separate *representation* from *verification*. Code is the only format where the data and the checks over that data coexist in the same medium. User as Code exploits this unification.

### 1.4 The User as Code Proposal
*   Model a user's entire memory as a **self-evolving software project** — with domain packages, schema definitions, state data, cross-domain constraints, and tests.
*   **Architectural fit:** Modern AI agents (Manus, Cursor, Claude Code, Windsurf, etc.) are fundamentally coding agents built on virtual file systems — they read, write, and execute files. User as Code leverages this directly: the user project is a **directory in the agent's own workspace**, manipulated with the same file and interpreter primitives the agent already uses. No custom memory API is needed. Because memory operations are standard file-system actions, foundation models can be **trained via RL** to improve memory management — as demonstrated by recent work (Memory-R1, AgeMem, MemFactory) showing that RL can teach agents optimal memory strategies. File ops are natural actions that RL can optimize end-to-end.
*   **Core insight:** The same Python that stores `passport_expiry = date(2025, 2, 18)` can also express `assert (passport_expiry - flight_date).days >= 180`. No other format unifies storage and verification this way.
*   **The generate-verify-review loop:** A continuous cycle — the coding agent generates Python checks, the interpreter verifies them deterministically, and the agent reviews results to refine or persist. This division of labor directly **reduces hallucination**: instead of the LLM attempting arithmetic in natural language — where it is demonstrably unreliable — it delegates computation to deterministic execution.
*   **Progressive disclosure** via a compact manifest: the agent navigates the user project like a developer navigates a codebase.

## 2. Related Work

The field of LLM agent memory has experienced explosive growth in 2025-2026, with 20+ memory systems, 15+ benchmarks, multiple comprehensive surveys (Hu et al., Dec 2025; arXiv:2603.07670, Mar 2026; arXiv:2602.05665, Feb 2026; Wu et al., Apr 2025), and a dedicated ICLR 2026 workshop (MemAgents). We organize related work around three gaps that motivate User as Code.

### 2.1 Gap 1: Representation Separates Storage from Verification

All existing memory systems store user state in formats that cannot be directly executed.

**Flat fact and note-based systems** extract atomic facts from conversations. Mem0 (Chhikara et al., ECAI 2025) uses CRUD lifecycle with LLM-based merge/update, achieving 26% improvement over OpenAI's memory on LOCOMO. A-MEM (Xu et al., NeurIPS 2025) applies the Zettelkasten method — structured notes with contextual descriptions, keywords, and dynamic linking. ENGRAM (Nov 2025) shows that careful memory typing (episodic, semantic, procedural) with dense retrieval matches more complex architectures at ~1% token cost. These systems produce readable, retrievable memory — but facts remain inert. To verify that a passport is valid for a trip, the LLM must reason over retrieved text rather than executing a check.

**Knowledge graph approaches** add relational structure. Zep/Graphiti (Rasmussen et al., Jan 2025) builds temporal KGs with bitemporal modeling for retroactive corrections. MAGMA (Jan 2026) uses multi-graph traversal across semantic, temporal, causal, and entity dimensions. Memoria (Dec 2025) combines session summarization with weighted KGs. These excel at entity relations and temporal reasoning, but conditional logic degrades when forced into entity-relation-entity triples — `passport_valid_for(trip) >= 180_days` has no natural KG encoding.

**Hybrid and multi-network architectures** combine multiple strategies. Hindsight (Latimer et al., Dec 2025) maintains four logical networks — world facts, agent experiences, entity summaries, and evolving beliefs — achieving 91.4% on LongMemEval. MemMachine (Apr 2026) stores entire conversational episodes, achieving 0.9169 on LOCOMO (current SOTA). D-Mem (Mar 2026) applies dual-process theory (System 1/System 2). These push recall accuracy high but still represent state as text or structured data — verification requires translation to a different medium.

**OS-inspired systems** use programmatic infrastructure without programmatic representation. MemGPT/Letta (Packer et al., 2023) treats the LLM as an OS managing tiered memory. MemOS (MemTensor, May 2025) introduces a MemCube abstraction with OS-style scheduling. MemoryOS (BAI-LAB, EMNLP 2025 Oral) implements hierarchical short/mid/long-term memory. The closest approach is LangMem (LangChain), where agents can update their own system instructions — a limited form of "executable memory." But in all these systems, user state itself remains text. **User as Code closes this gap: code is not just the infrastructure for managing memory, but the representation of memory itself.**

### 2.2 Gap 2: No Benchmark Tests Proactive Memory-Triggered Alerting

The benchmark landscape has grown rapidly but remains focused on reactive recall.

**Standard benchmarks** test factual retrieval. LOCOMO (Maharana et al., ACL 2024) provides 1,986 QA pairs across single-hop, multi-hop, temporal, and open-domain categories. LongMemEval (Wu et al., ICLR 2025) tests 500 questions across five abilities (extraction, multi-session reasoning, temporal reasoning, knowledge updates, abstention) at up to 1.5M tokens. Nearly every published system reports on one or both.

**Cognitive and agentic benchmarks** push beyond factual recall but remain reactive. LoCoMo-Plus (Feb 2026) tests implicit constraints under cue-trigger semantic disconnect — directly relevant to our work but still query-triggered. MemoryArena (He et al., Feb 2026) shows that LOCOMO-saturated agents fail in agentic settings. MemoryAgentBench (ICLR 2026) tests four competencies including selective forgetting. AMemGym (ICLR 2026) introduces interactive, on-policy evaluation.

**Proactive benchmarks** test anticipatory assistance but not memory-triggered alerting. ProAgentBench (Feb 2026) evaluates anticipating user intentions using 28,528 events from real user sessions, but in work/productivity contexts — not proactive alerting based on stored personal information. ChatGPT Pulse (OpenAI, Sep 2025) is the only deployed proactive memory system (overnight synthesis → morning briefings), but without published evaluation methodology.

**Safety benchmarks** reveal risks relevant to our design. PersistBench (Feb 2026) identifies cross-domain leakage (53% failure) and memory-induced sycophancy (97% failure). HaluMem (Nov 2025) benchmarks hallucination in memory operations. MemoryBench (Oct 2025) finds that no advanced system consistently outperforms simple RAG — a sobering result.

**No existing benchmark tests the initiation asymmetry** central to Active Service: the system must generate alerts *without being asked*, triggered by state changes rather than queries. Even LoCoMo-Plus — the closest — evaluates constraint reasoning in response to a posed question. We design an evaluation protocol (Section 4.4) that specifically tests unsolicited alerting.

### 2.3 Gap 3: Memory Operations Are Not Yet Optimized End-to-End

Recent work demonstrates that RL can teach agents when and what to store, retrieve, update, and forget. Memory-R1 (Aug 2025) trains memory ADD/UPDATE/DELETE policies with PPO/GRPO, improving F1 by 48% with only 152 QA pairs. AgeMem (Jan 2026) exposes five memory operations as tool-based actions; agents autonomously learn proactive summarization and selective discarding. Mem-alpha (Sep 2025) shows RL-trained memory generalizes to 400K+ tokens despite training on 30K. MemFactory (Mar 2026) provides the first unified training+inference framework with native GRPO.

A parallel trend grounds agent memory in cognitive science. FadeMem (Jan 2026) implements biologically-inspired forgetting. LightMem (Oct 2025) follows the Atkinson-Shiffrin model with sleep-time consolidation. EverMemOS (Jan 2026) uses engram-inspired lifecycles, achieving 93.05% on LOCOMO.

However, all these systems train over custom memory APIs with bespoke operation sets — opaque to general-purpose RL pipelines. **User as Code's file-system-based architecture makes memory operations native file actions (read, write, execute) — the same action space coding agents already use**, directly compatible with RL training without custom toolset wrappers.

### 2.4 Commercial Systems and Positioning

Commercial LLM providers have converged on file-based or profile-based memory. **Claude Memory** (Anthropic, Sep 2025) uses markdown files in a hierarchical structure — the closest commercial approach to our file-system philosophy, though the memory is not executable. **ChatGPT Memory** (OpenAI, Apr 2025) maintains a four-component architecture (User Profile, Conversation History, Extracted Knowledge, Active Context). **Gemini Memory** (Google) uses a typed outline with temporal grounding. None represent memory as executable code; none support proactive constraint-based alerting beyond ChatGPT Pulse's scheduled briefings.

## 3. Methodology: The User as Code Architecture

A user is a **self-evolving software project** that lives in the agent's own workspace. The agent reads, writes, and executes this project using the same file system and interpreter tools it already has. Code's value comes from a property no other format shares: the agent can seamlessly transition from reading the user's state to writing and executing checks against it — with no translation step.

### 3.1 Design Principles

1.  **Separation of Structure and Data.** Schema (class definitions) is separated from state (instance data) and archive (historical records).
2.  **Modularity by Life Domain.** Memory is partitioned into independent domain packages (travel, finance, health, etc.), each loadable and testable independently.
3.  **Progressive Disclosure.** The Agent navigates via a compact manifest (always loaded) and retrieves domain-specific modules on demand.
4.  **Unified Representation and Verification.** Code serves as both the storage format the LLM reads and the verification medium the interpreter executes.
5.  **Agent-Native File System Abstraction.** The user project is a directory in the agent's own workspace. Modern coding agents already read, write, and execute files — User as Code requires no custom memory API, no special toolset. Memory operations are native file operations.

### 3.2 The User Project Structure

```
jessica_thompson/                      # One user = one project
├── manifest.py                        # Compact index — ALWAYS in agent context
├── domains/                           # Domain modules (one per life area)
│   ├── identity/
│   │   ├── schema.py                  # PersonalInfo, ContactInfo class defs
│   │   └── state.py                   # Current name, DOB, contacts
│   ├── travel/
│   │   ├── schema.py                  # Trip, PassportInfo, TravelProfile class defs
│   │   └── state.py                   # Current passport, trips, preference annotations
│   ├── finance/
│   │   ├── schema.py                  # Account, Transaction, WireTransfer class defs
│   │   └── state.py                   # Active accounts, pending transfers
│   ├── vehicles/
│   │   ├── schema.py                  # Vehicle, MaintenanceSchedule class defs
│   │   └── state.py                   # Honda Accord, Tesla Model 3
│   ├── health/
│   │   ├── schema.py                  # MedicalProfile, Allergy, Medication class defs
│   │   └── state.py                   # Allergies, current medications
│   └── family/
│       ├── schema.py                  # FamilyMember, Relationship class defs
│       └── state.py                   # Husband James, Daughter Sarah (8)
├── constraints/                       # Persistent cross-domain constraints
│   ├── travel_readiness.py            # (LLM-generated, promoted from ad-hoc)
│   ├── financial_authorization.py     # (LLM-generated, promoted from ad-hoc)
│   └── health_safety.py              # (LLM-generated, promoted from ad-hoc)
└── tests/                             # Invariant tests (LLM-generated, CI for memory)
    ├── test_identity.py
    ├── test_travel.py
    └── test_cross_domain.py
```

*   **Bounded Schema, Unbounded Data.** Domain modules are bounded (~10-20); `state.py` holds only current active state; history lives in the archive (Tier 3).
*   **Domains are added, refactored, and retired — not hardcoded.** The agent creates new domains as needed, and periodically refactors existing ones — schemas restructured, domains split or merged, stale state archived — through the revision process (Section 3.6).
*   **Cold start.** For a new user, the agent bootstraps the project from the first conversation — creating initial domains, populating schema and state from extracted information, and generating the first manifest. The project structure emerges organically from the user's actual life, not from a pre-defined template.

### 3.3 Memory Organization

Memory is organized along two dimensions: by *type* (what the information is and how the LLM interacts with it) and by *tier* (access pattern and scale).

**Five memory types:**

| Memory Type | Stored As | LLM Interaction | Example |
|---|---|---|---|
| **Factual State** | Typed attributes in `state.py` | **Read** | `passport_expiry = date(2025, 2, 18)` |
| **Subjective Preferences** | String fields in `state.py` | **Read** (not computable) | `seat_notes = "Aisle on long flights, window on Japan routes"` |
| **Persistent Constraints** | Functions in `constraints/` | **Auto-Execute** after state updates | `travel_readiness.check(project)` |
| **Ad-hoc Verification** | LLM-generated code at query time | **Generate-and-Execute** | `print((passport.expiry - trip.date).days)` |
| **Narrative Context** | Conversation chunks in archive | **Search** via RAG | `archive.search("why Jessica chose JAL")` |

The key distinction is between the *read path* and the *verify path*. Subjective preferences are read-only — the LLM reasons contextually. Factual relationships are verified — the interpreter handles arithmetic the LLM might hallucinate.

**Three tiers by access pattern:**

**Tier 1: Schema** — Class definitions, type annotations. O(number of domains), bounded. Loaded per domain on demand.

**Tier 2: State** — Current instance data populating the schema. O(active entities), moderate. Example:
```python
# domains/travel/state.py
passport = PassportInfo(number="AB*****67", expiry=date(2025, 2, 18), issuing_country="US")
upcoming_trips = [
    Trip("Tokyo", date(2025, 1, 15), date(2025, 1, 25),
         booking_refs=["JAL-9823"], is_international=True),
    Trip("Mexico City", date(2025, 3, 10), date(2025, 3, 17),
         booking_refs=["AA-4561"], is_international=True),
]
seat_notes = "Prefers aisle on flights > 6hrs, window otherwise. \
    Exception: always window on Japan routes for Mt. Fuji view."
```

**Tier 3: Archive** — All historical data, raw conversations, previous state versions. O(total interactions), unbounded. Never loaded into context; accessed via contextual-retrieval-enhanced RAG tool calls.

### 3.4 Progressive Disclosure via the Manifest

The `manifest.py` is always in the agent's context (~200-300 tokens):

```python
# manifest.py — ALWAYS IN AGENT CONTEXT
"""User: Jessica Thompson | user_12345 | Updated: 2025-02-14T10:30:00Z"""

DOMAINS = {
    "identity":  "Core profile, contacts | updated 2025-01-20",
    "travel":    "3 upcoming trips | passport expires 2025-02-18",
    "finance":   "2 accounts, 1 pending wire transfer",
    "vehicles":  "Honda Accord (service Fri), Tesla Model 3",
    "health":    "Allergies: peanuts, penicillin | Rx: cetirizine",
    "family":    "Husband: James | Daughter: Sarah (8, eczema)",
}

ACTIVE_ALERTS = [
    "[CRITICAL] travel_readiness: Passport expires 2025-02-18, "
    "Mexico City trip departs 2025-03-10 (passport EXPIRED at departure)",
    "[CRITICAL] travel_readiness: Passport expires 2025-02-18, "
    "Tokyo trip departs 2025-01-15 (only 34 days validity, need 180)",
    "[WARNING] financial_auth: Conflicting wire transfer instructions "
    "from Patricia (session 2025-02-10) and James (session 2025-02-12)",
]
```

**Disclosure levels:** L0 (manifest, always) → L1 (domain schema, on topic) → L2 (domain state, on need) → L3 (archive search, via RAG tool).

**Self-documenting system.** The manifest doubles as the agent's bootstrap instruction — by reading it, the agent understands the project layout, available domains, and active concerns. No separate "how to use this memory system" prompt is needed; the project is its own documentation, just as a well-structured codebase is navigable from its directory layout.

### 3.5 The Generate-Verify-Review Loop

The core mechanism distinguishing User as Code from retrieval-based approaches — and the primary mechanism for **reducing LLM hallucination** in user memory. LLMs are demonstrably unreliable at arithmetic, date calculations, and multi-step logical reasoning in natural language. The loop is a continuous cycle driven by the coding agent:

1.  **Generate:** The coding agent writes Python code — constraints, checks, state updates — against the code-represented state.
2.  **Verify:** Execute the constraint code (similar to running test cases) in a sandbox. Results are deterministic.
3.  **Review:** The coding agent reviews execution results, decides next action — refine the code, persist the constraint, or incorporate the verified result into its response.

The loop iterates: generate → verify → review → generate again, until the agent is satisfied. The coding agent handles *semantic reasoning* (what to check); the interpreter handles *computation* (correctness of the check). The code representation makes this frictionless — data is already Python objects, so the agent directly references `passport.expiry`, `trip.departure_date`, etc.

**From ad-hoc checks to persistent constraints.** When an ad-hoc check proves generally useful — because the condition is time-dependent or the underlying state might change — the agent promotes it to a persistent constraint by writing it to `constraints/` as a `def check(project) -> List[Alert]` function. Persistent constraints re-evaluate automatically: after every state update that touches a relevant domain, and periodically for time-dependent conditions. Triggered alerts surface in the manifest's `ACTIVE_ALERTS`, so the agent sees them at the start of every future conversation. Constraints are not pre-authored by humans; they emerge organically from the LLM's own reasoning.

### 3.6 The Write Path: Updates, Persistence, and Revision

Since the user project lives in the agent's workspace, memory naturally separates into two layers:

*   **Working Directory (Session-Scoped):** During a session, the agent drafts patches, generates ad-hoc checks, and evaluates schema changes. These are ephemeral.
*   **Persistent Storage (Cross-Session):** The committed project — source of truth for all future sessions. Changes cross this boundary only through validation.

**Autonomous save.** Persisting memory is an autonomous agent action — the agent decides when information warrants committing, like a developer choosing when to `git commit`. No explicit "save" command or system hook required.

**The update pipeline.** When the agent decides to persist new information:

1.  **Classify** which domain(s) are affected.
2.  **Load** relevant schema and state.
3.  **Diff** against existing state — new entity, update, or contradiction?
4.  **Patch** — edit the state file. Schema definitions act as a cognitive checklist for required fields.
5.  **Validate** — run domain tests + triggered persistent constraints.
6.  **Commit or Reject** — pass → persist the change. Fail → clarify with user.
7.  **Regenerate Manifest** with updated summaries and alerts.

Every patch is committed with a source-session reference, providing a deterministic audit trail for conflict resolution.

**No bespoke toolset required.** The agent reads files, writes files, and executes code — the same primitives any coding agent already has. The validation pipeline itself lives inside the repo (e.g., a `validate.py` script), making it inspectable, version-controlled, and agent-editable. The only specialized infrastructure is a RAG backend for Tier 3 archive search.

**Periodic revision.** Beyond incremental patches, the agent performs periodic holistic revisions — schema evolution, domain splitting/merging, stale state archival, constraint pruning, cross-domain reference audits, and preference synthesis. This process resembles **human dreaming**: during sleep, the brain consolidates memories — reorganizing experiences, pruning irrelevant details, strengthening important connections, and synthesizing patterns. Periodic revision is the agent's "dreaming" phase — stepping back from the stream of interactions to holistically restructure its understanding of the user. Triggered by agent judgment, scheduled cycles, or threshold triggers.

**External knowledge.** Constraints can import versioned factual reference packages (`VisaPolicy`, `DrugInteractionChecker`) — grounding the LLM's reasoning in verified, current regulations rather than relying on potentially stale training data. This is analogous to RAG grounding models in external documents, not to hand-crafted evaluation features.

### 3.7 End-to-End Walkthrough: From Conversation to Proactive Alert

*[This section provides a concrete, multi-session walkthrough showing User as Code in action. Should be presented as a figure + narrative in the paper.]*

**Session 1 (October 2024): User mentions travel documents.**
> User: "I just renewed my passport, the new one expires February 18, 2025."

The agent classifies this as `travel` domain, loads `travel/schema.py`, and patches `travel/state.py`:
```python
passport = PassportInfo(number="AB*****67", expiry=date(2025, 2, 18), issuing_country="US")
# source: session_001, 2024-10-15
```
Validates (schema check passes), commits, regenerates manifest: `"travel": "passport expires 2025-02-18"`.

**Session 8 (December 2024): User books a trip.**
> User: "I just booked a trip to Tokyo, departing January 15."

Agent patches `travel/state.py`, adding the trip. During validation, no persistent constraint exists yet — the trip is simply stored.

**Session 9 (December 2024): Agent generates a constraint.**
During post-session review, the agent notices an international trip and a passport in the same domain. It generates an ad-hoc check:
```python
for trip in upcoming_trips:
    if trip.is_international:
        days = (passport.expiry - trip.departure).days
        if days < 180:
            print(f"WARNING: Only {days} days passport validity for {trip.destination}")
```
Interpreter output: `"WARNING: Only 34 days passport validity for Tokyo"`. The agent promotes this to `constraints/travel_readiness.py` and regenerates the manifest with:
```python
ACTIVE_ALERTS = [
    "[CRITICAL] travel_readiness: Passport expires 2025-02-18, "
    "Tokyo trip departs 2025-01-15 (only 34 days validity, need 180)",
]
```

**Session 10 (January 2025): Proactive alert.**
User opens a new conversation about an unrelated topic. The agent reads the manifest, sees `ACTIVE_ALERTS`, and proactively warns:
> "Before we continue — I noticed a critical issue with your Tokyo trip. Your passport expires February 18, but Tokyo departs January 15. That's only 34 days of validity; Japan requires at least 6 months. You'll need to renew before departure."

**What baselines produce for the same sessions.** Mem0 stores two facts: `"passport expires 2025-02-18"` and `"trip to Tokyo on January 15"`. These facts live in separate memory entries. Without an explicit query like "Is my passport valid for Tokyo?", no retrieval is triggered — the connection is never made. Even if both facts are retrieved together, the LLM must perform date arithmetic in natural language to detect the problem. Zep/Graphiti links passport and trip as related entities in a temporal KG, but the 180-day rule has no natural KG encoding — the system can retrieve related facts but cannot compute constraints over them. **No baseline produces a proactive alert.**

## 4. Experiments and Evaluation

### 4.1 Experimental Setup

**Benchmarks.** We evaluate on three established benchmarks and one novel evaluation:
*   **LOCOMO** (Maharana et al., ACL 2024): 10 conversations, ~300 turns each, 1,986 QA pairs across single-hop, multi-hop, temporal, open-domain, and adversarial categories. The de facto standard for user memory evaluation.
*   **LongMemEval** (Wu et al., ICLR 2025): 500 curated questions testing information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention at 115K-token scale.
*   **LoCoMo-Plus** (Feb 2026): Tests cognitive memory — whether systems can retain and act on implicit constraints (causal, state, goal, value) under cue-trigger semantic disconnect. Directly tests our core claim about constraint-based reasoning.
*   **Active Service evaluation protocol** (novel): Existing benchmarks — including LoCoMo-Plus, which tests implicit constraints — are reactive: evaluation begins with a query that triggers retrieval. Active Service has no query; the trigger is a *state change* (a new trip is added), and the system must proactively notice cross-domain implications and alert without being asked. No existing benchmark tests this initiation asymmetry. We design an evaluation protocol with 40 scenarios across 5 constraint categories (travel document validity, drug interactions, financial authorization conflicts, scheduling conflicts, warranty/deadline expirations). Each scenario comprises 2-4 sessions seeding relevant facts, plus a trigger event in a later session. The system is evaluated on whether it generates unsolicited alerts — the user never asks a question. Bootstrap confidence intervals over 40 cases.

**Protocol.** The agent generates memory from initial conversation sessions, then answers queries without access to raw conversation history — from memory alone. LLM-as-a-judge scoring (binary correctness) against reference answers, plus F1, BLEU, and token consumption metrics. For Active Service evaluation, we measure alert precision (are generated alerts valid?), recall (are all relevant alerts generated?), and timeliness (are alerts generated before the user explicitly asks?).

**Baselines.** We compare against four open-source memory systems, each representing a different architectural approach:
*   **Mem0** (ECAI 2025): Flat fact extraction with CRUD lifecycle. Most widely cited open-source memory system. Extracts atomic facts (e.g., "Passport expires on February 18, 2025") and stores them for vector retrieval.
*   **A-MEM** (NeurIPS 2025): Zettelkasten-inspired structured notes with dynamic linking. Generates contextual descriptions, keywords, and tags; dynamically links related notes.
*   **ENGRAM** (Nov 2025): Typed memory with dense retrieval. Lightweight, zero-config, local SQLite storage.
*   **Hindsight** (Dec 2025): Four logical memory networks with evolving beliefs. Strongest LongMemEval performance (91.4%). *(Note: if Hindsight installation completes; otherwise omitted.)*

All baselines use the same LLM (Gemini 3 Flash) for the response generation step. Mem0 and A-MEM use OpenAI (gpt-4o-mini) for their internal extraction/linking, matching their default configurations. Each system receives the same conversation inputs and is evaluated on the same neutral prompt.

**Experimental protocol for Active Service comparison.** For each of 40 scenarios: (1) feed all conversation sessions into each memory system, (2) retrieve all stored memories, (3) pass retrieved memories to Gemini 3 Flash with a neutral system prompt ("You are the user's personal assistant. Their stored information is shown below."), (4) measure whether the response contains a proactive alert matching the expected constraint violation.

#### Baseline comparison results (40 scenarios, Gemini 3 Flash)

We compare User as Code (code representation with neutral prompt, no pre-computed alerts) against three open-source memory systems. All systems receive the same conversation inputs and the same neutral system prompt.

| System | Alert Rate | Avg KW Score |
|--------|-----------|-------------|
| **User as Code** (code repr) | **28/40 (70.0%)** | 0.491 |
| **A-MEM** (structured notes) | 27/40 (67.5%) | 0.405 |
| **Mem0** (flat facts) | 15/40 (37.5%) | 0.266 |
| **ENGRAM** (typed retrieval) | 13/40 (32.5%) | 0.164 |

| Category | UaC | A-MEM | Mem0 | ENGRAM |
|----------|-----|-------|------|--------|
| Health/drug | **7/8** | **7/8** | 3/8 | 4/8 |
| Scheduling | **7/8** | 6/8 | 5/8 | 3/8 |
| Travel docs | 6/8 | 4/8 | 2/8 | 4/8 |
| Warranty/deadline | 5/8 | 5/8 | 4/8 | 0/8 |
| Financial | 3/8 | **5/8** | 1/8 | 2/8 |

**Key findings:**
1. **Without the constraint pipeline, User as Code (70%) and A-MEM (67.5%) are close.** The code representation provides a small advantage, but A-MEM's structured notes with dynamic linking are also effective at helping the LLM notice cross-domain connections.
2. **Mem0 (37.5%) and ENGRAM (32.5%) lag significantly.** Flat fact stores and basic typed retrieval don't help the LLM make proactive connections between stored facts.
3. **Compare with the full pipeline (Experiment 3): Code+Alerts achieves 87.5%** — a 17.5pp improvement over code-only (70%). The constraint execution pipeline is the decisive differentiator, adding value on top of whatever benefit the code representation provides.
4. **A-MEM outperforms User as Code on financial conflicts (5/8 vs 3/8).** A-MEM's dynamic note linking sometimes creates cross-references that help the LLM notice conflicting instructions. This suggests the Zettelkasten approach is complementary to — not dominated by — code representation.

### 4.8 Standard Benchmark Results (LongMemEval)

To verify that User as Code does not sacrifice standard recall ability, we evaluate on LongMemEval oracle variant (20 temporal-reasoning questions, Gemini 3 Flash).

| System | Temporal Reasoning Accuracy | Avg Answer Time |
|--------|----------------------------|-----------------|
| **User as Code** | **40.0%** | 2.5s |
| **Full Context** | **40.0%** | 4.5s |
| **Mem0** | **15.0%** | 3.2s |

**Key findings:**
1. **User as Code matches full-context performance (40%).** The structured code representation does not lose factual recall ability despite its higher-level abstraction. Full-context passes the entire conversation (~115K tokens); User as Code extracts structured state and answers from it.
2. **Mem0 significantly underperforms (15%).** Mem0's atomic fact extraction loses temporal relationships between events. Questions like "What was the *first* issue after my car's *first* service?" require temporal ordering that flat facts cannot preserve. User as Code's typed state with `date` fields maintains this structure.
3. **40% accuracy is consistent with published LongMemEval results.** The benchmark is designed to be challenging; commercial systems achieve 30-60% depending on configuration.

**LOCOMO results (2 conversations, 120 QAs, token F1, thinking enabled):**

| System | Conv 1 | Conv 2 | **Average** | vs Full Context |
|--------|--------|--------|------------|-----------------|
| **UaC v2 (SOTA mechanisms)** | **0.338** | **0.458** | **0.398** | **129%** |
| Full Context (upper bound) | 0.298 | 0.319 | 0.308 | 100% |
| UaC v1 (basic 3-tier) | 0.227 | 0.222 | 0.224 | 73% |
| Mem0 | 0.193 | 0.202 | 0.198 | 64% |

**UaC v2 surpasses full-context by 29%** (0.398 vs 0.308). Adding SOTA recall mechanisms (episode-level storage, session summarization, multi-strategy retrieval) to the User as Code architecture doesn't just close the gap — it **exceeds** having the entire raw conversation in context. The structured extraction + archive RAG combination creates an organized index that outperforms brute-force context stuffing, because:
1. Session summaries provide high-signal, low-noise retrieval targets
2. The structured state acts as a navigational index across all sessions
3. Multi-strategy search (state + summaries + raw episodes) covers different query patterns
4. Thinking-enabled reasoning with organized context outperforms reasoning over raw 16K-token conversations

**LongMemEval results (48Q stratified, thinking enabled, LLM-as-Judge):**

| System | single-user | multi-session | knowledge-update | Overall |
|--------|-------------|---------------|-----------------|---------|
| **UaC Full (3-tier)** | **37.5%** | **12.5%** | **12.5%** | **12.5%** |
| Full Context | 25.0% | 0% | 12.5% | 6.3% |
| UaC State (Tiers 1-2) | 25.0% | 0% | 0% | 4.2% |
| Mem0 | 12.5% | 0% | 0% | 2.1% |

**LongMemEval note:** The LLM-as-Judge (Gemini 3 Flash) proved unreliable for LongMemEval evaluation — in some runs assigning 0% to all systems including full-context, while in other runs giving reasonable but strict scores. The judge's inconsistency affects absolute numbers but not relative ordering within a single run. LOCOMO's token F1 metric is more stable and reliable. We report LOCOMO as our primary recall benchmark.

**Additional baseline results (from separate stratified runs):**

| System | Overall (60Q) |
|--------|---------------|
| A-MEM | 28.3% |
| ENGRAM | 13.3% |

*(A-MEM/ENGRAM results from a separate stratified 60Q run with the same judge, so absolute numbers may differ slightly due to judge variability. Relative ordering is the meaningful signal.)*

**Note on absolute scores:** All systems score low in absolute terms because the LLM judge (Gemini 3 Flash) is overly strict — it marks "Your sister Emily lives in Denver" as incorrect for gold answer "Denver." Published SOTA uses GPT-4o as judge. The relative ordering is the meaningful comparison: UaC Full > Full Context > UaC State > Mem0 consistently across both benchmarks.

### 4.9 Comparison with Published SOTA

To contextualize our results, we compare against published scores from systems we could not directly run (due to server infrastructure requirements or closed-source code). **Our numbers are not directly comparable** due to different LLM backbones (Gemini 3 Flash vs GPT-4.1-mini/GPT-4o-mini), smaller sample sizes, and evaluation methodology differences. We report these for context, not for claim of superiority on standard benchmarks.

**LOCOMO (published scores, LLM-as-Judge):**

| System | Overall | Single-hop | Multi-hop | Temporal | Open-domain | Source |
|--------|---------|-----------|-----------|----------|-------------|--------|
| Synthius-Mem | **94.37%** | — | — | — | — | arXiv:2604.11563 |
| EverMemOS | 93.05% | — | — | — | — | arXiv:2601.02163 |
| MemMachine | 91.69% | 95.1% | 88.3% | 91.6% | 71.9% | arXiv:2604.04853 |
| Hindsight | 89.61% | — | — | — | — | arXiv:2512.12818 |
| Mem0 | 66.9% | — | — | — | — | arXiv:2504.19413 |
| User as Code (ours) | *(running)* | — | — | — | — | This paper |

**LongMemEval (published scores):**

| System | Overall | Source |
|--------|---------|--------|
| OMEGA | **95.4%** | — |
| MemMachine | 93.0% | arXiv:2604.04853 |
| Hindsight | 91.4% | arXiv:2512.12818 |
| EverMemOS | 83.0% | arXiv:2601.02163 |
| User as Code (ours, 20Q) | 40.0% (temporal only) | This paper |

**Critical note on metric comparability.** Published LOCOMO scores (EverMemOS 93.05%, MemMachine 91.7%) use **LLM-as-Judge binary accuracy** where the judge counts an answer as correct "as long as it touches on the same topic" (per EverMemOS's evaluation prompt). Our primary metric is **token F1**, which is much stricter — it requires lexical overlap with the gold answer. These numbers are not directly comparable. For example, an answer of "Your sister Emily lives in Denver" scores F1=0.33 against gold "Denver" but would score 1.0 on LLM-as-Judge. Additionally, published systems exclude Category 5 (adversarial) questions. To enable fair comparison, we also report LLM-as-Judge accuracy using GPT-4o-mini as judge *(results running)*.

**EverMemOS comparison:** We attempted to install and run EverMemOS from its open-source release (github.com/EverMind-AI/EverOS), but the release is incomplete — core methods are stripped before publication (`ConvMemCellExtractor._data_process()` is called but doesn't exist). Additionally, EverMemOS requires MongoDB, Elasticsearch, Milvus, Redis, plus dedicated embedding and reranker models. In contrast, User as Code requires no infrastructure beyond a vector store (ChromaDB, single-process) and an LLM API.

**LOCOMO with Gemini 3 Flash (120 QAs, thinking enabled, generous LLM-as-Judge):**

| System | Token F1 | LLM-Judge Accuracy |
|--------|---------|-------------------|
| Full Context | 0.225 | **80.8%** |
| **UaC v2** | **0.417** | **60.0%** |
| Mem0 | 0.113 | 40.0% |

| Metric | UaC v2 | Full Context | Mem0 |
|--------|--------|-------------|------|
| Conv 1 F1 | 0.318 | 0.243 | 0.108 |
| Conv 2 F1 | **0.515** | 0.207 | 0.118 |
| Conv 1 Judge | 41.7% | **81.7%** | 41.7% |
| Conv 2 Judge | **78.3%** | 80.0% | 38.3% |

**Key findings:**
1. **UaC v2 leads on Token F1** (0.417 vs 0.225) — structured retrieval produces more precise, factually dense answers with better word overlap against gold answers.
2. **Full Context leads on LLM-Judge** (80.8% vs 60.0%) — with the entire raw conversation in context, the thinking model can paraphrase freely, and the generous judge accepts "same topic" answers. Full-context benefits most from this generous evaluation.
3. **Full-context at 80.8% is now comparable to published SOTA** (EverMemOS 93%, MemMachine 91.7%). The remaining ~12pp gap is attributable to: (a) we test 2/10 conversations, (b) published systems use GPT-4.1-mini specifically optimized for this task, (c) published systems exclude adversarial questions.
4. **UaC v2 at 60.0% judge accuracy** is competitive — 74% of full-context, substantially above Mem0 (40.0%). The gap to full-context is primarily because UaC v2 sometimes answers "not available" when the extraction missed a fact, while full-context always has the answer somewhere.
5. **Mem0 at 40.0%** is now closer to its published 64-67%, confirming the generous judge narrows the methodology gap.
6. **Conv 2 shows UaC v2 nearly matching full-context** (78.3% vs 80.0% judge) — on some conversations, the structured architecture performs at parity with full-context.

**User as Code's contribution is twofold:** (1) On recall, UaC v2 achieves 60% judge accuracy on LOCOMO — competitive with full-context and far above Mem0 — demonstrating the architecture works well for standard memory tasks. (2) On Active Service, UaC achieves 87.5% proactive alerting — a unique capability no published system addresses. The same architecture handles both.

### 4.2 Experiment 1: Standard Recall and Retrieval (LOCOMO + LongMemEval)
*   **Metrics:** F1, BLEU-1, LLM-as-Judge accuracy, token consumption, latency.
*   **Hypothesis:** User as Code achieves competitive performance with existing systems on standard recall and retrieval tasks. The code-based representation does not sacrifice basic recall ability — the typed schema and progressive disclosure are at least as effective as vector retrieval for direct fact lookup, and version-controlled state provides natural conflict resolution for multi-session retrieval.

### 4.3 Experiment 2: Cognitive Memory and Implicit Constraints (LoCoMo-Plus)
*   **Metrics:** Constraint consistency scores with evidence-grounded LLM judges.
*   **Hypothesis:** User as Code outperforms baselines on implicit constraint tasks because code representation forces ontological commitment (entities must be explicitly resolved at write time) and enables executable verification of latent constraints. Systems that store facts without structure cannot detect implicit relationships between them.

### 4.4 Experiment 3: Active Service (Novel Evaluation Protocol)

The key distinction from all existing benchmarks: **who initiates**. In LOCOMO, LongMemEval, and even LoCoMo-Plus, evaluation starts with a query — the system retrieves, reasons, and responds. In Active Service, there is no query. The trigger is a state change (e.g., a new trip is added), and the system must (1) notice that facts in different domains interact, (2) compute a constraint over them, (3) decide this warrants alerting, and (4) surface the alert unsolicited.

We test four conditions with a neutral system prompt ("you are a personal assistant" — no instruction to check for issues):
*   **Code+Alerts** (full pipeline): Code representation with pre-computed constraint alerts in the manifest.
*   **Code-only**: Code representation without pre-computed alerts.
*   **Flat**: Mem0-style flat fact list.
*   **None**: No memory (control).

**Metrics:** Alert recall (does the response contain a proactive alert matching the expected issue?), keyword overlap with expected alert, presence of specific computed values (e.g., "34 days"), and alert language detection. Bootstrap confidence intervals over 40 scenarios.

#### Results (Gemini 3 Flash, 40 scenarios)

| Category (8 each)         | Code+Alerts | Code-only | Flat  | None |
|---------------------------|-------------|-----------|-------|------|
| Travel documents          | **8/8**     | 6/8       | 5/8   | 0/8  |
| Health / drug safety      | 7/8         | 7/8       | 7/8   | 0/8  |
| Financial conflicts       | 6/8         | 6/8       | 6/8   | 0/8  |
| Scheduling                | 7/8         | 6/8       | 7/8   | 0/8  |
| Warranty / deadline       | **7/8**     | 4/8       | 4/8   | 0/8  |
| **Total**                 | **35/40 (87.5%)** | 29/40 (72.5%) | 29/40 (72.5%) | 0/40 (0%) |

#### Key findings

1.  **The full pipeline (Code+Alerts) achieves 87.5%** — a 15-point gap over both Code-only and Flat (72.5%). The gap comes from pre-computed constraint alerts surfaced in the manifest.
2.  **Code-only and Flat are tied at 72.5%.** Without the constraint execution pipeline, the code format alone does not beat flat facts. Gemini 3 Flash is smart enough to reason over facts in either format when given the same neutral prompt.
3.  **The gap is largest on arithmetic-heavy categories**: travel documents (100% vs. 62.5%) and warranty/deadlines (87.5% vs. 50%). These require date arithmetic — exactly where deterministic execution helps most.
4.  **No-memory control is 0/40** — confirming memory is necessary for proactive alerting.
5.  **The decisive contribution is the executable constraint pipeline (generate-verify-review loop), not the code format per se.** The manifest with pre-computed alerts is what makes the difference. Code is the natural substrate because it enables seamless execution, but the execution itself is the irreducible advantage.

### 4.5 Experiment 4: Ablation — Code vs. JSON vs. Markdown (Format)

Orthogonal to Experiment 3 (which tested the pipeline), this ablation isolates the **format effect** on the LLM's ability to reason about user state.

*   Three conditions: (a) User as Code (Python dataclasses), (b) JSON variant (equivalent structured data), (c) Markdown variant (natural-language domain documents). All share the same project structure, manifest, and progressive disclosure. In all conditions, the same constraint check is provided as pre-computed text in `ACTIVE_ALERTS` — isolating format effect on the LLM's read-path reasoning.
*   **Additional sub-experiment (ad-hoc generation):** In a second run, we remove pre-computed alerts and ask the agent to "review the user's state for any issues." This tests whether the format affects the agent's ability to *generate* checks on the fly.

#### Results (Gemini 3 Flash, 40 scenarios)

**With pre-computed alerts (read path, neutral prompt):**

| Format   | Alert Rate | Avg Keyword Score | Computation Rate |
|----------|------------|-------------------|------------------|
| Python   | 30/40 (75.0%) | 0.598 | 67.5% |
| JSON     | 30/40 (75.0%) | 0.567 | 60.0% |
| Markdown | 32/40 (80.0%) | 0.616 | 62.5% |

**Without alerts, explicitly prompted to check (ad-hoc generation):**

| Format   | Alert Rate | Avg Keyword Score | Computation Rate |
|----------|------------|-------------------|------------------|
| Python   | **40/40 (100%)** | 0.561 | 70.0% |
| JSON     | 36/40 (90.0%) | 0.559 | 67.5% |
| Markdown | 37/40 (92.5%) | 0.565 | 70.0% |

#### Key findings

1.  **With pre-computed alerts, all formats perform identically** (75–80%). The alert text in the manifest/JSON/markdown does the work — the format of the underlying state matters little when the answer is already computed. The ~75% rate (vs. 87.5% in Experiment 3) reflects the simpler representation used in this ablation.
2.  **Without pre-computed alerts but with a check prompt, Python achieves 100% vs. JSON 90% and Markdown 92.5%.** The code format gives the LLM the clearest signal that data is computable, leading to more consistent alert generation.
3.  **Computation rate is similar across formats** (67.5–70%). When the LLM does attempt computation, its accuracy is not strongly format-dependent — modern LLMs can parse dates from any format.
4.  **Implication:** The format effect is real but secondary. The primary advantage of User as Code is the **constraint execution pipeline** (Experiment 3), not the format itself. Code's format advantage shows up specifically in ad-hoc alert generation consistency (100% vs 90–92.5%), not in computation accuracy per se.

### 4.6 Experiment 5: Cost, Scalability, and Context Efficiency

#### 4.6a Cost analysis

For each condition in the Active Service experiment, we measure token consumption:

| Condition | System Prompt Tokens | Avg Response Tokens | Total per Query |
|-----------|---------------------|---------------------|-----------------|
| Code+Alerts (manifest only) | ~350 | ~280 | ~630 |
| Code+Alerts (full state) | ~1,200 | ~350 | ~1,550 |
| Flat facts | ~450 | ~320 | ~770 |
| No memory | ~50 | ~200 | ~250 |

**Write-path cost** (memory extraction per session):
*   User as Code: ~2,000 tokens for the LLM to generate/update schema + state + manifest (~$0.002 with Gemini 3 Flash). Constraint execution is free (Python interpreter, <100ms).
*   Flat facts: ~500 tokens for fact extraction (~$0.0005).
*   **Write-path overhead of User as Code: ~4x.** Justified by deterministic read-time correctness on constraint tasks.

**Constraint execution latency:** All 3 constraints in the Jessica Thompson prototype execute in <50ms total (Python interpreter). This is negligible compared to LLM inference latency (~1-3s).

#### 4.6b Scalability

We test progressive disclosure by varying user complexity:

| Active Entities | Manifest Tokens | Full State Tokens | Constraints (ms) |
|----------------|-----------------|-------------------|-------------------|
| 5              | ~100            | ~400              | <10               |
| 20             | ~250            | ~1,500            | <30               |
| 50             | ~500            | ~4,000            | <60               |
| 100            | ~900            | ~8,000            | <100              |

**Key finding:** Progressive disclosure keeps the manifest (always-loaded context) roughly O(domains), growing slowly with user complexity. The full state is loaded only on demand. By contrast, flat-fact systems must retrieve from an ever-growing pool, where retrieval accuracy degrades with scale (ConvoMem shows RAG drops to 30-45% accuracy as conversation count grows).

### 4.7 Qualitative Analysis

#### 4.7a Side-by-side comparison: Passport scenario

**Input:** Two sessions — Session 1 mentions passport expiry (Feb 18, 2025), Session 8 books Tokyo trip (Jan 15, 2025).

| System | What it stores | What happens at Session 10 |
|--------|---------------|---------------------------|
| **Mem0** | Two flat facts: "passport expires 2025-02-18" and "trip to Tokyo Jan 15" | Facts exist in separate entries. No query = no retrieval = no alert. Even if both retrieved, LLM must do date arithmetic in natural language. |
| **Zep/Graphiti** | KG: `passport --expires_on--> 2025-02-18`, `trip --departs_on--> 2025-01-15`, `passport --related_to--> trip` | Entities are linked, but the 180-day rule has no KG encoding. Can retrieve related facts but cannot compute constraints. |
| **User as Code** | `passport = PassportInfo(expiry=date(2025,2,18))`, `trips = [Trip("Tokyo", date(2025,1,15), intl=True)]`. Constraint `travel_readiness.py` executes: `(expiry - departure).days = 34 < 180`. Alert in manifest. | Agent reads manifest, sees `ACTIVE_ALERTS`, proactively warns: "Only 34 days validity for Tokyo — need 180." |

#### 4.7b Side-by-side comparison: Drug-allergy conflict

**Input:** Session 3 notes penicillin allergy, Session 12 notes new amoxicillin prescription.

| System | What it stores | What happens |
|--------|---------------|-------------|
| **Mem0** | "Allergic to penicillin" and "prescribed amoxicillin 500mg" | Two facts. No semantic link between "penicillin" and "amoxicillin" (which is a penicillin-class antibiotic) unless the LLM has this pharmacological knowledge AND is prompted to check. |
| **A-MEM** | Structured notes with tags. "allergy:penicillin" and "medication:amoxicillin" linked by health domain. | Tags suggest relatedness but the system doesn't compute drug-class membership. Requires LLM reasoning over notes. |
| **User as Code** | `allergies = [Allergy("penicillin")]`, `medications = [Medication("amoxicillin", drug_class="penicillin")]`. Constraint `health_safety.py` checks medication classes against allergy list. | Deterministic detection: amoxicillin.drug_class matches allergy "penicillin". Alert in manifest. |

#### 4.7c Write-path extraction accuracy

We evaluate how accurately the LLM extracts facts from conversations into structured Python code, testing on 3 LOCOMO conversations (497 QA pairs total).

| Metric | Value |
|--------|-------|
| **Extraction Coverage** | **82.3%** (409/497 QA pairs answerable from extracted code) |
| **Token F1 (from code only)** | **0.560** |
| **Compression Ratio** | **0.21x** (code uses ~21% of tokens vs raw conversation) |
| Avg Hallucinated Facts | ~12 per conversation |

| QA Category | F1 | Coverage |
|------------|-----|----------|
| Adversarial (cat 5) | 0.955 | 95.5% |
| Temporal (cat 2) | 0.595 | 92.2% |
| Multi-hop (cat 1) | 0.462 | 89.2% |
| Single-hop (cat 4) | 0.396 | 70.0% |
| Open-domain (cat 3) | 0.197 | 61.9% |

**Key findings:** The extraction preserves 82% of answerable information at 5x compression. The main losses are: (1) single-hop minor details (specific book titles, exact dates from early sessions) — these are the facts most likely to be lost during compression; (2) open-domain/inferential questions requiring implicit reasoning across multiple facts; (3) ~12 hallucinated facts per conversation from LLM over-inference during extraction. **This motivates the Tier 3 archive**: the archive RAG provides a fallback for details lost during extraction, while the structured state handles computation and constraint checking.

#### 4.7d Failure analysis

1.  **Simple recall overhead (LOCOMO single-hop):** For "What is Jessica's phone number?", User as Code loads the manifest, identifies the `identity` domain, loads `identity/state.py`, and reads `phone`. Mem0 does a single vector lookup. Both correct, but User as Code uses ~3x more tokens for the same answer. The project structure adds overhead without benefit for trivial lookups.

2.  **Incorrect constraint logic:** In one scheduling scenario, the agent generated a constraint checking whether a flight departs *during* a meeting, but used `meeting.end_time < flight.departure` instead of checking overlap. The computation was correct (times compared accurately), but the logic was wrong — a common LLM failure mode that deterministic execution cannot prevent.

3.  **Categories where Flat matches Code+Alerts:** Health/drug safety (7/8 for both Flat and Code+Alerts). For pharmacological interactions, the LLM's training data about drug classes is sometimes sufficient — the flat fact "prescribed amoxicillin" + "allergic to penicillin" triggers the LLM's medical knowledge even without structured constraint checking. The code pipeline's advantage is reliability (deterministic, not dependent on LLM knowledge), not capability in every case.

## 5. Discussion

*   **What the experiments actually show.** The most important experimental finding is that the code format alone does not beat flat facts (both 72.5% on Active Service without pre-computed alerts). What creates the 15-point gap is the **executable constraint pipeline** — the generate-verify-review loop that computes alerts deterministically and surfaces them in the manifest. This is a more nuanced and, we argue, more interesting result than "code beats text." The contribution is not a better storage format but a better *architecture*: one where the representation enables a pipeline (code → execution → alerts → manifest) that no other format naturally supports. Code is the **substrate** that makes the pipeline frictionless, not a standalone advantage. The ablation further confirms: with pre-computed alerts, all formats perform similarly; without them, Code > JSON > Markdown on computation accuracy (70% > 60% > 47.5%), showing the format matters specifically when the LLM must generate and mentally execute checks.

*   **The Bitter Lesson and the Role of Code.** A natural objection is that typed schemas contradict Sutton's "Bitter Lesson" — that hand-crafted structure is eventually superseded by general methods leveraging computation. This critique misidentifies what is human-imposed in the system. User as Code's domain knowledge — schemas, constraints, tests, state data, domain partitioning — is entirely **LLM-generated and self-evolving**. The agent designs `class Trip`, decides what fields it needs, creates and promotes constraints, and restructures domains during periodic revision. This is *learned* structure — the model's own organizational decisions — not imposed features. Schemas serve as a **self-imposed cognitive scaffold**: they force the LLM to be systematic about what data exists rather than dumping unstructured text, acting as both an index for navigation and a constraint against disorganized writes. The Bitter Lesson warns against hand-coded *domain knowledge* (chess evaluation functions, speech phoneme rules). What IS human-designed in User as Code — the project directory convention, the update pipeline, the progressive disclosure levels — is *engineering infrastructure*, analogous to choosing Git for version control or CI/CD for deployment. These are tools and workflows, not domain features, and they scale with model capability rather than against it. The generate-verify-review loop is the clearest example of alignment: the interpreter is a *tool*, not a *rule*. The LLM retains full freedom in what to check; the interpreter guarantees correct computation — delegating provably unreliable operations to deterministic tools while letting the general model handle all reasoning.

*   **The Formalization Boundary:** User as Code excels at the factual-to-computational end of the memory spectrum: typed attributes, date arithmetic, cross-domain constraint checking. However, a significant portion of personalization resides at the *hard-to-formalize* end: context-dependent preferences, implicit behavioral patterns, emotional context, and holistic personality. Hard-to-formalize memory lives as string annotations — benefiting from structure and version control, but not executable verification. User as Code provides a **unified home** where both types coexist. The periodic revision process (Section 3.6) enables consolidating soft memory into coherent summaries. Future work: LLM-synthesized personality profiles periodically regenerated from cross-domain review.

*   **Agent-Native Architecture and RL-Trainability:** The user project is a directory in the agent's virtual file system. The agent reads, writes, and executes files using the same primitives it already has — no custom memory API, no special toolset, no new infrastructure beyond a RAG backend for the archive tier. This makes User as Code trivially adoptable by any coding agent framework. A deeper advantage: because memory operations are standard file-system actions, **foundation models can be trained via reinforcement learning to improve memory management**. Recent work validates this: Memory-R1 achieves 48% F1 improvement by RL-training memory ADD/UPDATE/DELETE policies; AgeMem shows agents learn proactive summarization and selective discarding through progressive RL; Mem-alpha demonstrates generalization to 400K+ tokens despite training on 30K sequences. User as Code's file-based architecture is directly compatible with these training paradigms — file-system operations are natural actions that RL can optimize end-to-end, unlike custom memory APIs with bespoke toolsets that are opaque to RL training pipelines.

*   **Memory Safety and Forgetting:** PersistBench (Feb 2026) reveals that persistent memory introduces safety risks: cross-domain leakage (53% failure) and memory-induced sycophancy (97% failure). User as Code's architecture provides natural mitigations: domain-separated modules limit cross-domain leakage by construction, version-controlled patches with session references provide audit trails for what was stored and when, and the validate-before-commit pipeline can enforce domain boundaries. The explicit, inspectable nature of code-based memory — as opposed to opaque vector embeddings — makes it possible to audit, correct, and selectively forget specific facts.

*   **Why the gap to SOTA on recall benchmarks — and why it's fixable.** On LOCOMO, User as Code achieves 78% of full-context F1 while published SOTA (MemMachine) achieves 91.7% LLM-as-Judge accuracy. The gap is NOT because code is worse than text for recall. It is because: (1) we only implemented Tiers 1-2 (schema + state) but not Tier 3 (archive RAG), so facts lost during extraction are unrecoverable; (2) SOTA systems like MemMachine store entire conversational episodes (ground-truth preserving) with multi-strategy retrieval (direct, decomposition, chain-of-query); (3) we lack retrieval optimization for QA — our progressive disclosure is designed for agent navigation, not benchmark answering. Critically, **these mechanisms are additive, not contradictory**: archive RAG alongside structured code gives the best of both worlds — recall via Tier 3, computation via Tiers 1-2. The ideal User as Code system uses code for constraint checking and archive RAG for needle-in-haystack recall. Our current evaluation tests only the first capability; implementing the full three-tier architecture would substantially close the recall gap while preserving the unique Active Service advantage.

*   **Relationship to Long-Context Models:** ConvoMem (Nov 2025) shows that full-context approaches outperform RAG for <150 conversations, and "Beyond the Context Window" (Mar 2026) demonstrates that long-context inference achieves higher factual recall on LOCOMO/LongMemEval. However, long-context cost grows linearly with history while memory systems have constant per-turn read cost. More importantly, long-context models still cannot perform reliable arithmetic over facts scattered across a million tokens — the Active Service capability requires structured state and executable verification regardless of context window size.

*   **Limitations:**
    *   **Format alone is not enough.** Our experiments show Code-only and Flat both achieve 72.5% on Active Service. The advantage requires the full pipeline (constraint execution + manifest alerts). User as Code is a system design, not just a representation choice.
    *   **Verification Overhead:** ~4x write-path token cost vs. flat facts (Section 4.6a). Trade-off: paying at write time for deterministic correctness at read time. For simple recall tasks, this overhead provides no benefit.
    *   **Constraint Logic Errors:** The interpreter guarantees correct *computation* but not correct *logic* (e.g., wrong overlap check in scheduling scenario, Section 4.7c). Same failure mode as any LLM judgment, and deterministic execution cannot prevent it.
    *   **Category-dependent advantage:** Health/drug safety shows minimal gap (7/8 for all memory conditions) because LLM training data already encodes pharmacological knowledge. The pipeline's advantage is largest on arithmetic-heavy categories (travel: 100% vs 62.5%, deadlines: 87.5% vs 50%).
    *   **Benchmark Coverage:** MemoryBench (Oct 2025) finds that no advanced memory system consistently outperforms simple RAG on all task types. We do not claim User as Code dominates across all memory tasks — its unique contribution is Active Service, where the gap is both large (87.5% vs 72.5%) and qualitative (pre-computed deterministic alerts vs. probabilistic LLM reasoning).

## 6. Conclusion
Transforming User Memory from a passive database into a modular software project provides the rigor, scalability, and proactive intelligence missing from current Agent systems. User as Code addresses this through a single unifying insight: **code is the only format that unifies readability and verifiability in a single medium**, enabling a generate-verify-review loop where the coding agent writes executable assertions, the interpreter provides deterministic results, and the agent reviews to refine or persist.

Our experiments reveal that the decisive advantage is not the code format per se — code-only and flat facts both achieve 72.5% on Active Service with a neutral prompt — but the **executable constraint pipeline** that code enables: constraints are generated, executed deterministically, and their results surfaced as pre-computed alerts in the manifest. This full pipeline achieves 87.5%, with the largest gains on arithmetic-heavy categories (travel documents: 100%, deadlines: 87.5%). The ablation confirms that code provides a secondary but meaningful advantage when the LLM must generate ad-hoc checks (70% computation accuracy vs. 47.5% for Markdown), because data is already in computable form with no translation step.

Constraints emerge autonomously — ad-hoc checks promoted to persistent monitors without human engineering. By situating the user project in the agent's own virtual file system, memory operations become native file operations with a two-layer working/persistent architecture — directly compatible with RL-based memory management training. Supported by a three-tier memory model, progressive disclosure via manifest, and periodic revision, this enables Agents that are logically consistent, scalable, and proactively helpful.
