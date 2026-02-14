# Outline: User as Code: Executable Memory for Personalized Agents

## Abstract

Current personalization in AI agents primarily relies on Retrieval-Augmented Generation (RAG) over unstructured text or vector databases. While effective for open-domain knowledge, this "Bag of Facts" approach struggles with the specific challenges of user memory: resolving conflicting information, managing temporal dependencies, and enforcing logical constraints (e.g., "passport expiration" vs. "flight date"). This paper introduces **User as Code**, a novel paradigm where an agent's understanding of a user is maintained as a **modular, version-controlled software project**. Our core observation is that **code is the only representation format that unifies readability and verifiability in a single medium**: the same Python that stores a user's passport expiry date can also express — and execute — the assertion that the expiry is too close to a booked flight. This unification enables a **generate-verify-review loop** that directly **reduces LLM hallucination**: the coding agent generates Python checks against the code-represented state, the interpreter verifies the computation deterministically, and the agent reviews results to refine or persist — turning unreliable natural-language arithmetic into deterministic results. Constraints are not pre-authored by humans; the LLM generates them autonomously, promoting useful checks to persistent background monitors. We propose a **Three-Layer Evaluation Framework** (Basic Recall, Multi-session Retrieval, Active Service) and demonstrate that User as Code solves the "Active Service" challenge — proactive alerting based on logical constraints — where all retrieval-based approaches fundamentally fail.

## 1. Introduction

### 1.1 The Memory Challenge for Personalized Agents
*   To build truly personalized, continuous-service AI Agents, a User Memory system is indispensable. Memory is not simply recording every word the user says — it is gradually forming a model of the user through sustained interaction: their personality, hobbies, habits, values.
*   **Memory consists of two fundamental components:** In Chinese, the word for memory is "记忆" (Jìyì) — and the two characters capture the two halves precisely:
    *   **记 (Jì) — Memorizing (Knowledge Extraction):** Extracting structured knowledge from raw interactions and persisting it in an organized form.
    *   **忆 (Yì) — Retrieval (Knowledge Retrieval):** Recalling the right knowledge at the right time to serve the user.
    *   All memory systems must address both halves. User as Code contributes to **both**: on the memorizing side, knowledge is extracted into structured, typed, version-controlled code; on the retrieval side, executing code against the state is itself a form of retrieval — the generate-verify-review loop *computes* answers that no similarity search could produce. The same code that stores knowledge also serves as the substrate for executable retrieval.
*   Agent memory spans multiple layers: working memory (single-session trajectory), long-term memory (persistent cross-session knowledge), and business state (task-phase abstractions). This paper focuses on long-term user memory.
*   The essence of user memory is an active, continuous learning process — the Agent continually refines its internal user model to explain all known observations with the most compact structure.

### 1.2 The "Bag of Facts" Problem
*   **Problem:** Current systems (VectorDBs, JSON stores, Knowledge Graphs) treat memory as a loose collection of facts.
    *   **Conflict:** "I love cilantro" vs. later "I actually hate cilantro" — vector retrieval might return both or the wrong one.
    *   **Logic Gap:** LLMs struggle to detect logical conflicts in retrieved text (e.g., booking a flight after a visa expires).
*   **The Representation Tension:** Existing strategies trade simplicity for expressiveness — from atomic fact notes (low overhead, no relationships) through JSON cards (structured, partial updates) to Advanced JSON Cards with metadata (disambiguated entities, timestamps). But even the most advanced structured approach cannot express rules like "if passport expires within 180 days of travel date, raise an alert." This requires *executable* logic that the system can **generate on the fly** as novel situations arise.
*   **Thesis:** The fundamental limitation of all existing formats — natural language, JSON, knowledge graphs — is that they separate *representation* from *verification*. Code is the only format where the data and the checks over that data coexist in the same medium. User as Code exploits this unification.

### 1.3 The User as Code Proposal
*   Model a user's entire memory as a **self-evolving software project** — with domain packages, schema definitions, state data, cross-domain constraints, and tests.
*   **Architectural fit:** Modern AI agents (OpenClaw, Cursor, Claude Code, etc.) are fundamentally coding agents built on virtual file systems — they read, write, and execute files. User as Code leverages this directly: the user project is a **directory in the agent's own workspace**, manipulated with the same file and interpreter primitives the agent already uses. No custom memory API is needed. Because memory operations are standard file-system actions, foundation models can be **trained via RL** to improve memory management — file ops are natural actions that RL can optimize end-to-end.
*   **Core insight:** The same Python that stores `passport_expiry = date(2025, 2, 18)` can also express `assert (passport_expiry - flight_date).days >= 180`. No other format unifies storage and verification this way.
*   **The generate-verify-review loop:** A continuous cycle — the coding agent generates Python checks, the interpreter verifies them deterministically, and the agent reviews results to refine or persist. This division of labor directly **reduces hallucination**: instead of the LLM attempting arithmetic in natural language — where it is demonstrably unreliable — it delegates computation to deterministic execution.
*   **Progressive disclosure** via a compact manifest: the agent navigates the user project like a developer navigates a codebase.

## 2. Background and Related Work

### 2.1 Current Approaches to User Memory
*   **Vector RAG:** Indexes conversation history as chunks, retrieves via semantic search. Effective for basic recall but struggles with cross-session conflict detection and proactive service.
*   **Structured Knowledge Graphs:** Better at entity relations, but rigid; conditional logic is degraded when forced into entity-relation-entity triples.
*   **Mem0 / Memobase:** Modular memory management with CRUD lifecycle, vector storage, and LLM-based merge/update decisions.
*   **Contextual Retrieval (Anthropic):** Prepends LLM-generated context summaries to each chunk before indexing. Reduces retrieval failure rate by up to 67% with reranking.
*   **Dual-Layer Memory Architecture:** The state-of-the-art: Advanced JSON Cards (structured core, always in context) + Contextual-Retrieval-enhanced RAG (on-demand details). Strongest existing baseline.

### 2.2 Code as a Knowledge Representation Medium
*   Code is a high-density, unambiguous knowledge representation format that allows "Active Knowledge": `if x: do y` is more robust than a text description.
*   **The LLM + Code Interpreter paradigm:** (1) All modern agents are essentially coding agents — Manus, Claude Code, OpenClaw, Cursor, etc. (2) Coding is the most advanced capability of foundation models (OpenAI, Claude), closest to human expertise. (3) Code is verifiable — the interpreter guarantees correctness of computation. User as Code applies this paradigm to user memory.

## 3. The Three-Layer Evaluation Framework

We propose a three-layer evaluation framework that decomposes user memory capability into progressively harder levels.

### 3.1 Layer 1: Basic Recall
*   Accurately store and retrieve directly provided, unambiguous information (e.g., "My membership number is 12345").
*   All existing approaches perform adequately at this level.

### 3.2 Layer 2: Multi-session Retrieval
*   Retrieve and reason over information scattered across sessions, entities, and time periods.
*   **Challenges:** Disambiguation (two cars across sessions), compound events (canceling "the LA trip" means flights + hotels + car rentals), conflict resolution (multi-party conflicting instructions over time).
*   Agentic RAG handles some cases but struggles with factual conflicts across isolated chunks.

### 3.3 Layer 3: Active Service
*   Proactively synthesize information across many sessions to provide anticipatory, unsolicited help.
*   **Challenges:** Proactive alerting (cross-reference a new flight with passport info stored months ago), comprehensive solution assembly (compile all relevant protection plans for a damaged phone).
*   **Where existing approaches fail:** No retrieval sophistication can reliably compute that a passport expiring Feb 18 leaves only 34 days of validity for a Jan 15 departure — far short of the 180-day requirement. This is *arithmetic*, not a similarity match.

## 4. Methodology: The User as Code Architecture

A user is a **self-evolving software project** that lives in the agent's own workspace. The agent reads, writes, and executes this project using the same file system and interpreter tools it already has. Code's value comes from a property no other format shares: the agent can seamlessly transition from reading the user's state to writing and executing checks against it — with no translation step.

### 4.1 Design Principles

1.  **Separation of Structure and Data.** Schema (class definitions) is separated from state (instance data) and archive (historical records).
2.  **Modularity by Life Domain.** Memory is partitioned into independent domain packages (travel, finance, health, etc.), each loadable and testable independently.
3.  **Progressive Disclosure.** The Agent navigates via a compact manifest (always loaded) and retrieves domain-specific modules on demand.
4.  **Unified Representation and Verification.** Code serves as both the storage format the LLM reads and the verification medium the interpreter executes.
5.  **Agent-Native File System Abstraction.** The user project is a directory in the agent's own workspace. Modern coding agents (OpenClaw, Cursor, Claude Code) already read, write, and execute files — User as Code requires no custom memory API, no special toolset. Memory operations are native file operations.

### 4.2 The User Project Structure

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
*   **Domains are added, refactored, and retired — not hardcoded.** The agent creates new domains as needed, and periodically refactors existing ones — schemas restructured, domains split or merged, stale state archived — through the revision process (Section 4.6).
*   **Cold start.** For a new user, the agent bootstraps the project from the first conversation — creating initial domains, populating schema and state from extracted information, and generating the first manifest. The project structure emerges organically from the user's actual life, not from a pre-defined template.

### 4.3 Memory Organization

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

### 4.4 Progressive Disclosure via the Manifest

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

### 4.5 The Generate-Verify-Review Loop

The core mechanism distinguishing User as Code from retrieval-based approaches — and the primary mechanism for **reducing LLM hallucination** in user memory. LLMs are demonstrably unreliable at arithmetic, date calculations, and multi-step logical reasoning in natural language. The loop is a continuous cycle driven by the coding agent:

1.  **Generate:** The coding agent writes Python code — constraints, checks, state updates — against the code-represented state.
2.  **Verify:** Execute the constraint code (similar to running test cases) in a sandbox. Results are deterministic.
3.  **Review:** The coding agent reviews execution results, decides next action — refine the code, persist the constraint, or incorporate the verified result into its response.

The loop iterates: generate → verify → review → generate again, until the agent is satisfied. The coding agent handles *semantic reasoning* (what to check); the interpreter handles *computation* (correctness of the check). The code representation makes this frictionless — data is already Python objects, so the agent directly references `passport.expiry`, `trip.departure_date`, etc.

**From ad-hoc checks to persistent constraints.** When an ad-hoc check proves generally useful — because the condition is time-dependent or the underlying state might change — the agent promotes it to a persistent constraint by writing it to `constraints/` as a `def check(project) -> List[Alert]` function. Persistent constraints re-evaluate automatically: after every state update that touches a relevant domain, and periodically for time-dependent conditions. Triggered alerts surface in the manifest's `ACTIVE_ALERTS`, so the agent sees them at the start of every future conversation. Constraints are not pre-authored by humans; they emerge organically from the LLM's own reasoning.

### 4.6 The Write Path: Updates, Persistence, and Revision

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

## 5. Experiments and Evaluation

### 5.1 Experimental Setup
*   **Benchmark:** Three-Layer Framework (Section 3): 20 test cases per layer (60 total), each comprising 1–3 sessions of ~50 turns. Cross-validated with LOCOMO.
*   **Protocol:** The agent generates memory from initial sessions, updates without access to raw conversation history, and answers from memory alone. LLM-as-a-judge scoring against reference answers.
*   **Baselines:** (1) Agentic RAG, (2) Agentic RAG + Contextual Retrieval, (3) Dual-Layer Memory (Advanced JSON Cards + Contextual RAG).

### 5.2 Experiment 1: Basic Recall
*   **Metric:** Exact-match accuracy. **Hypothesis:** All approaches perform well; User as Code achieves parity.

### 5.3 Experiment 2: Multi-session Retrieval and Conflict Resolution
*   **Metric:** Accuracy in multi-entity retrieval, contradiction resolution, and multi-party conflict handling.
*   **Hypothesis:** Near 100% conflict resolution via single-source-of-truth state and version-controlled patches.

### 5.4 Experiment 3: Active Service
*   **5.4a: Seen Constraints.** Pre-computed alerts already in manifest. Validates the persistent constraint pipeline.
*   **5.4b: Unseen Constraints.** No pre-authored constraint exists; agent must generate ad-hoc checks on the fly. User as Code outperforms because code representation makes ad-hoc verification natural.

### 5.5 Experiment 4: Ablation — Code vs. JSON vs. Markdown
*   Three conditions: (a) User as Code (Python), (b) JSON variant (`schema.json`/`state.json`), (c) Markdown variant (natural-language domain documents). All share the same project structure, manifest, progressive disclosure, and archive RAG. The agent can still generate and execute Python checks in all conditions.
*   **Hypothesis:** Code > JSON > Markdown on Layer 3 (verification), because each additional parsing step adds friction and error surface. All three comparable on Layer 1 (read-only). The gap between JSON and Markdown isolates the cost of parsing natural language; the gap between Code and JSON isolates the unification advantage.
*   **What this reveals:** If all three outperform the baselines on Layer 2, the project structure and version control are doing the work — not the format. If only Code outperforms on Layer 3, the unification property is specifically what matters for Active Service.

### 5.6 Experiment 5: Scalability and Context Efficiency
*   Users with 5–100 active entities, 1K–100K historical records. **Hypothesis:** Progressive disclosure keeps context usage roughly constant regardless of user complexity.

## 6. Discussion

*   **The Bitter Lesson and the Role of Code.** A natural objection is that typed schemas contradict Sutton's "Bitter Lesson" — that hand-crafted structure is eventually superseded by general methods leveraging computation. This critique misidentifies what is human-imposed in the system. User as Code's domain knowledge — schemas, constraints, tests, state data, domain partitioning — is entirely **LLM-generated and self-evolving**. The agent designs `class Trip`, decides what fields it needs, creates and promotes constraints, and restructures domains during periodic revision. This is *learned* structure — the model's own organizational decisions — not imposed features. Schemas serve as a **self-imposed cognitive scaffold**: they force the LLM to be systematic about what data exists rather than dumping unstructured text, acting as both an index for navigation and a constraint against disorganized writes. The Bitter Lesson warns against hand-coded *domain knowledge* (chess evaluation functions, speech phoneme rules). What IS human-designed in User as Code — the project directory convention, the update pipeline, the progressive disclosure levels — is *engineering infrastructure*, analogous to choosing Git for version control or CI/CD for deployment. These are tools and workflows, not domain features, and they scale with model capability rather than against it. The generate-verify-review loop is the clearest example of alignment: the interpreter is a *tool*, not a *rule*. The LLM retains full freedom in what to check; the interpreter guarantees correct computation — delegating provably unreliable operations to deterministic tools while letting the general model handle all reasoning. The ablation experiment (Section 5.5) tests a Markdown variant to verify this decomposition empirically.
*   **The Formalization Boundary:** User as Code excels at the factual-to-computational end of the memory spectrum: typed attributes, date arithmetic, cross-domain constraint checking. However, a significant portion of personalization resides at the *hard-to-formalize* end: context-dependent preferences, implicit behavioral patterns, emotional context, and holistic personality. Hard-to-formalize memory lives as string annotations — benefiting from structure and version control, but not executable verification. User as Code provides a **unified home** where both types coexist. The periodic revision process (Section 4.6) enables consolidating soft memory into coherent summaries. Future work: LLM-synthesized personality profiles periodically regenerated from cross-domain review.
*   **Agent-Native Architecture:** The user project is a directory in the agent's virtual file system. The agent reads, writes, and executes files using the same primitives it already has — no custom memory API, no special toolset, no new infrastructure beyond a RAG backend for the archive tier. This makes User as Code trivially adoptable by any coding agent framework. Saving memory is an autonomous agent decision, not a system hook. A deeper advantage of the agent-native approach: because memory operations are standard file-system actions (read, write, summarize, retrieve), **foundation models can be trained via reinforcement learning to improve memory management** — learning when to summarize, what to extract, and how to retrieve relevant state. Custom memory APIs with bespoke toolsets are opaque to RL training pipelines; file-system operations are natural actions that RL can optimize end-to-end.
*   **Limitations:**
    *   **Verification Overhead:** Generating structured code and verifying it (e.g., writing and running unit tests, type checking) is more expensive than appending text. Trade-off: paying at write time for deterministic correctness at read time — a favorable exchange.
    *   **Constraint Logic Errors:** The interpreter guarantees correct *computation* but not correct *logic* (e.g., wrong threshold). Same failure mode as any LLM judgment.
    *   **LLM Code Generation Quality:** Mitigated by strict type checking, test validation, and reject-and-retry loops.

## 7. Conclusion
Transforming User Memory from a passive database into a modular software project provides the rigor, scalability, and proactive intelligence missing from current Agent systems. User as Code addresses this through a single unifying insight: **code is the only format that unifies readability and verifiability in a single medium**, enabling a generate-verify-review loop where the coding agent writes executable assertions, the interpreter provides deterministic results, and the agent reviews to refine or persist. Constraints emerge autonomously — ad-hoc checks promoted to persistent monitors without human engineering. By situating the user project in the agent's own virtual file system, memory operations become native file operations with a two-layer working/persistent architecture. Supported by a three-tier memory model, progressive disclosure via manifest, and periodic revision, this enables Agents that are logically consistent, scalable, and proactively helpful.
