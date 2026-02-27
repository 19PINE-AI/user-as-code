---
theme: seriph
title: "User as Code: Executable Memory for Personalized Agents"
info: |
  User as Code: Executable Memory for Personalized Agents
  An academic presentation on a novel paradigm for agent personalization.
transition: slide-left
mdc: true
lineNumbers: true
drawings:
  persist: false
colorSchema: light
layout: cover
background: https://cover.sli.dev
class: text-center
---

# User as Code

## Executable Memory for Personalized Agents

<div class="pt-4 text-base opacity-90">
  A novel paradigm where an agent's understanding of a user is maintained as a <strong>modular, version-controlled software project</strong>
</div>

<div class="mt-6 text-sm">
  <strong>Bojie Li</strong><br/>
  <span class="opacity-70">Chief Scientist, Pine AI</span>
</div>

<div class="abs-br m-6">
  <span class="text-sm opacity-50">January 2026</span>
</div>

---

# Agenda

<div class="mt-4 grid grid-cols-1 gap-3 max-w-xl text-sm">
  <div class="flex items-center gap-3 p-3 rounded-lg bg-blue-50 border-l-4 border-blue-400">
    <div class="text-2xl font-bold text-blue-400 w-8">1</div>
    <div>
      <div class="font-bold">Introduction & Motivation</div>
      <div class="text-xs opacity-60">The memory challenge · Bag of Facts · Representation tension</div>
    </div>
  </div>
  <div class="flex items-center gap-3 p-3 rounded-lg bg-amber-50 border-l-4 border-amber-400">
    <div class="text-2xl font-bold text-amber-400 w-8">2</div>
    <div>
      <div class="font-bold">Three-Layer Evaluation Framework</div>
      <div class="text-xs opacity-60">Basic Recall → Multi-session Retrieval → Active Service</div>
    </div>
  </div>
  <div class="flex items-center gap-3 p-3 rounded-lg bg-green-50 border-l-4 border-green-400">
    <div class="text-2xl font-bold text-green-400 w-8">3</div>
    <div>
      <div class="font-bold">Methodology: User as Code Architecture</div>
      <div class="text-xs opacity-60">Code as knowledge · Generate-and-verify loop · Project structure</div>
    </div>
  </div>
  <div class="flex items-center gap-3 p-3 rounded-lg bg-purple-50 border-l-4 border-purple-400">
    <div class="text-2xl font-bold text-purple-400 w-8">4</div>
    <div>
      <div class="font-bold">Discussion</div>
      <div class="text-xs opacity-60">Bitter Lesson · Formalization boundary · Agent-native architecture</div>
    </div>
  </div>
  <div class="flex items-center gap-3 p-3 rounded-lg bg-red-50 border-l-4 border-red-400">
    <div class="text-2xl font-bold text-red-400 w-8">5</div>
    <div>
      <div class="font-bold">Conclusion</div>
      <div class="text-xs opacity-60">Why code — and nothing else</div>
    </div>
  </div>
</div>

---
layout: section
---

# Part 1
## Introduction & Motivation

---

# The Memory Challenge for Personalized Agents

Building truly personalized, continuous-service AI agents requires a **User Memory** system.

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Two Components of Memory

In Chinese, memory is **记忆** (Jìyì) — two characters that capture the two halves precisely:

<div class="mt-2 grid grid-cols-2 gap-3 text-xs">
  <div class="p-2 rounded-lg bg-blue-50 border-2 border-blue-400">
    <div class="font-bold text-sm">记 (Jì) — Memorizing</div>
    <div class="mt-1">Knowledge Extraction: extracting structured knowledge from raw interactions and persisting it</div>
  </div>
  <div class="p-2 rounded-lg bg-green-50 border-2 border-green-400">
    <div class="font-bold text-sm">忆 (Yì) — Retrieval</div>
    <div class="mt-1">Knowledge Retrieval: recalling the right knowledge at the right time to serve the user</div>
  </div>
</div>

User as Code contributes to **both**:
- **Memorizing** — knowledge extracted into structured, typed, version-controlled code
- **Retrieval** — executing code against state computes answers no similarity search could produce

</div>
<div>

### Memory Layers

<div class="mt-2 grid grid-cols-1 gap-2">
<div class="p-2 bg-gray-50 rounded-lg text-sm">

**Working Memory** — Single-session trajectory

</div>
<div class="p-2 bg-green-50 rounded-lg border-2 border-green-400 text-sm">

**Long-term Memory** — Persistent cross-session knowledge **← Our Focus**

</div>
<div class="p-2 bg-gray-50 rounded-lg text-sm">

**Business State** — Task-phase abstractions

</div>
</div>

<div class="mt-3 p-2 bg-amber-50 rounded-lg text-xs">

Memory is not simply recording every word — it is gradually forming a **model of the user** through sustained interaction.

</div>

</div>
</div>

---

# The "Bag of Facts" Problem

Current systems (VectorDBs, JSON stores, Knowledge Graphs) treat memory as a **loose collection of facts**.

<div class="mt-4"></div>

### Conflict Resolution Failure

> **Session 3:** "I love cilantro" &nbsp;→&nbsp; **Session 12:** "I actually hate cilantro"
>
> Vector retrieval might return both — or the wrong one.


### Logic Gap

> User has a flight on **Jan 15** and a passport expiring **Feb 18**.
>
> LLMs struggle to detect: *180-day validity requirement means the passport is insufficient.*


<div class="mt-4 p-4 bg-red-50 rounded-lg border-l-4 border-red-400">

**The fundamental limitations:** All existing formats — natural language, JSON, knowledge graphs — (1) **separate representation from verification**, so no retrieval sophistication can compute <code>(expiry - departure).days >= 180</code>, and (2) **tolerate referential ambiguity**, so "my car" can persist unresolved across sessions.

</div>

---

# The Representation Tension

Existing strategies trade **simplicity** for **expressiveness** — each solves some problems but introduces new limitations:

<div class="mt-3 grid grid-cols-2 gap-3 text-xs">
  <div class="p-3 rounded-lg bg-gray-50 border-l-4 border-gray-400">
    <div class="font-bold text-sm mb-1">Atomic Fact Notes</div>
    <div class="text-green-700">✓ Low overhead, easy to append</div>
    <div class="text-red-700">✗ No relationships between facts</div>
    <div class="text-red-700">✗ No conflict detection across sessions</div>
    <div class="text-red-700">✗ No structure for partial updates</div>
  </div>
  <div class="p-3 rounded-lg bg-gray-50 border-l-4 border-blue-400">
    <div class="font-bold text-sm mb-1">JSON Cards</div>
    <div class="text-green-700">✓ Structured, supports partial updates</div>
    <div class="text-green-700">✓ Entity-level CRUD operations</div>
    <div class="text-red-700">✗ No cross-entity relationships</div>
    <div class="text-red-700">✗ Cannot express conditional logic</div>
  </div>
  <div class="p-3 rounded-lg bg-gray-50 border-l-4 border-purple-400">
    <div class="font-bold text-sm mb-1">Advanced JSON + Metadata</div>
    <div class="text-green-700">✓ Timestamps, IDs for partial disambiguation</div>
    <div class="text-green-700">✓ Strongest structured approach</div>
    <div class="text-red-700">✗ Still cannot express executable rules</div>
    <div class="text-red-700">✗ Disambiguation is convention, not enforced by the format</div>
  </div>
  <div class="p-3 rounded-lg bg-gray-50 border-l-4 border-amber-400">
    <div class="font-bold text-sm mb-1">Knowledge Graphs</div>
    <div class="text-green-700">✓ Entity-relation structure</div>
    <div class="text-green-700">✓ Graph traversal for related facts</div>
    <div class="text-red-700">✗ Rigid schema, hard to evolve</div>
    <div class="text-red-700">✗ Conditional logic degrades into triples</div>
  </div>
</div>

<div class="mt-3 p-2 bg-red-50 rounded-lg border-l-4 border-red-400 text-xs">

**Two common limitations:** (1) All formats separate *representation* from *verification* — none can express and execute <code>assert (passport.expiry - flight.date).days >= 180</code>. (2) All tolerate **ontological ambiguity** — "my car" can persist unresolved across sessions, deferring disambiguation to error-prone retrieval.

</div>

---
layout: section
---

# Part 2
## Three-Layer Evaluation Framework

---

# Progressively Harder Memory Challenges

We propose a three-layer framework decomposing user memory capability into progressively harder levels.

<div class="mt-6"></div>

<div class="flex items-center gap-3 mt-2">
  <div class="p-3 rounded-lg bg-blue-100 border-2 border-blue-400 text-center flex-1">
    <div class="font-bold text-sm">Layer 1</div>
    <div class="text-xs mt-1">Basic Recall</div>
    <div class="text-xs opacity-70">Store & retrieve unambiguous facts</div>
  </div>
  <div class="text-gray-400 text-xl">→</div>
  <div class="p-3 rounded-lg bg-amber-100 border-2 border-amber-400 text-center flex-1">
    <div class="font-bold text-sm">Layer 2</div>
    <div class="text-xs mt-1">Multi-session Retrieval</div>
    <div class="text-xs opacity-70">Ontological commitment & conflict resolution</div>
  </div>
  <div class="text-gray-400 text-xl">→</div>
  <div class="p-3 rounded-lg bg-red-100 border-2 border-red-400 text-center flex-1">
    <div class="font-bold text-sm">Layer 3</div>
    <div class="text-xs mt-1">Active Service</div>
    <div class="text-xs opacity-70">Proactive alerting & constraint checking</div>
  </div>
</div>


<div class="mt-8 grid grid-cols-3 gap-4 text-sm">
<div class="p-3 bg-blue-50 rounded-lg text-center">

**All approaches** perform adequately

</div>
<div class="p-3 bg-amber-50 rounded-lg text-center">

**Agentic RAG** handles some cases but defers ambiguity to retrieval

</div>
<div class="p-3 bg-red-50 rounded-lg text-center">

**Only User as Code** solves this — retrieval fundamentally fails

</div>
</div>

---

# Layer 1: Basic Recall

**Task:** Accurately store and retrieve directly provided, unambiguous information.

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Example

> "My membership number is 12345"
>
> **Later:** "What's my membership number?"
> → **12345**

### Result

All existing approaches perform adequately at this level. User as Code achieves **parity**.

</div>
<div>

### Why It's Easy

- Single fact, single session
- No ambiguity or conflict
- Direct semantic match
- No computation required

<div class="mt-4 p-3 bg-green-50 rounded-lg text-sm">

This is the baseline — the "table stakes" of user memory. The real differentiation begins at Layer 2.

</div>

</div>
</div>

---

# Layer 2: Multi-session Retrieval

**Task:** Retrieve and reason over information scattered across sessions, entities, and time periods.

<div class="mt-4"></div>

### Challenges

<div class="grid grid-cols-3 gap-4 mt-2">
<div class="p-4 bg-amber-50 rounded-lg">

**Disambiguation**

Two cars mentioned across sessions: *"my car"* in session 3 vs. session 7 — which one?

</div>
<div class="p-4 bg-amber-50 rounded-lg">

**Compound Events**

Canceling *"the LA trip"* means flights + hotels + car rentals across multiple bookings.

</div>
<div class="p-4 bg-amber-50 rounded-lg">

**Conflict Resolution**

Multi-party conflicting instructions over time (Patricia says X, James says Y).

</div>
</div>


<div class="mt-6 p-4 bg-blue-50 rounded-lg">

**User as Code advantage:** Code forces **ontological commitment** — the agent must resolve "my car" into a distinct typed object at write time, structurally eliminating referential ambiguity. Version-controlled patches with session references provide deterministic conflict resolution and audit.

</div>

---

# Layer 2: Ontological Commitment Through Code

Writing code compels the agent to **commit to what exists** — resolving ambiguities that other representations tolerate silently.

<div class="mt-3 grid grid-cols-2 gap-6">
<div>

### The Core Mechanism

In knowledge representation, an **ontological commitment** is the set of entities a formalism asserts to exist (Quine, 1948; Guarino, 1998). Code enforces this through:

1. **Entity identity** — each object is a distinct reference; "my car" *must* resolve to `vehicles[0]` or `vehicles[1]`
2. **Categorical structure** — typed classes define what *kinds* of entities exist and what properties are essential
3. **Compositional relations** — parts, wholes, and cross-references are explicit, not implied

<div class="mt-3 p-2 bg-amber-50 rounded-lg text-xs">

Natural language and JSON tolerate unresolved ambiguity indefinitely. Code does not — **writing a schema is an act of disambiguation**.

</div>

</div>
<div>

### Disambiguation by Construction

```python
# "my car" → code MUST resolve:
vehicles = [
    Vehicle("Honda Accord", year=2020),
    Vehicle("Tesla Model 3", year=2023),
]

# "the LA trip" → explicit composition:
la_trip = Trip(
    dest="Los Angeles",
    flights=[flights["AA-1234"]],
    hotels=[hotels["marriott_0312"]],
    car_rentals=[rentals["hertz_0312"]],
)

# Conflicting authority → typed provenance:
# Patricia (2025-02-10): cancel trip
# James (2025-02-12): keep trip
# → schema enforces: who has authority?
```

The schema serves as a **formal ontology** — ambiguity is structurally eliminated at write time, not deferred to retrieval.

</div>
</div>

---

# Layer 3: Active Service

**Task:** Proactively synthesize information across many sessions to provide **anticipatory, unsolicited help**.

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### The Challenge

Cross-reference a **new flight** (booked in Session 15) with **passport info** (stored in Session 2, months ago) to alert:

> *"Your passport expires Feb 18 — only 34 days of validity for your Jan 15 Tokyo trip. Most countries require 180 days."*

### Why Retrieval Fails

This is **arithmetic**, not a similarity match. No retrieval sophistication can compute:

`(2025-02-18) - (2025-01-15) = 34 days < 180`

</div>
<div>

### User as Code Solves This

```python
# LLM generates this check:
for trip in upcoming_trips:
    if trip.is_international:
        days = (passport.expiry 
                - trip.departure).days
        if days < 180:
            alert(
              f"Passport: {days} days "
              f"validity for {trip.dest}"
              f" — need 180!"
            )
```

The interpreter **executes** it deterministically.

Result: `"Passport: 34 days validity for Tokyo — need 180!"`

</div>
</div>

---
layout: section
---

# Part 3
## Methodology: The User as Code Architecture

*A user is a self-evolving software project.*

---

# Solving Ambiguity and Hallucination with Ontology and Executable Knowledge

The three-layer framework surfaces two fundamental challenges. User as Code addresses each with a distinct design principle.

<div class="mt-4"></div>

<div class="grid grid-cols-2 gap-6">
  <div class="p-4 rounded-lg bg-red-50 border-l-4 border-red-400">
    <div class="text-xs font-bold text-red-600 uppercase tracking-wide">Challenge</div>
    <div class="font-bold text-lg mt-1">Ambiguity</div>
    <div class="text-sm mt-1 opacity-80">Referential ambiguity persists unresolved across sessions — "my car," "the trip," conflicting instructions.</div>
    <div class="text-xs mt-2 opacity-60">Surfaces at Layer 2: Multi-session Retrieval</div>
  </div>
  <div class="p-4 rounded-lg bg-red-50 border-l-4 border-red-400">
    <div class="text-xs font-bold text-red-600 uppercase tracking-wide">Challenge</div>
    <div class="font-bold text-lg mt-1">Hallucination</div>
    <div class="text-sm mt-1 opacity-80">LLMs perform unreliable arithmetic and constraint checking on factual state — "is 34 < 180?"</div>
    <div class="text-xs mt-2 opacity-60">Surfaces at Layer 3: Active Service</div>
  </div>
</div>

<div class="grid grid-cols-2 gap-6 mt-3">
  <div class="p-4 rounded-lg bg-blue-50 border-l-4 border-blue-400">
    <div class="text-xs font-bold text-blue-600 uppercase tracking-wide">Principle</div>
    <div class="font-bold text-lg mt-1">Ontological Commitment</div>
    <div class="text-sm mt-1 opacity-80">Typed schemas force entity identity, categorical structure, and compositional relations — disambiguation at write time.</div>
  </div>
  <div class="p-4 rounded-lg bg-green-50 border-l-4 border-green-400">
    <div class="text-xs font-bold text-green-600 uppercase tracking-wide">Principle</div>
    <div class="font-bold text-lg mt-1">Executable Knowledge</div>
    <div class="text-sm mt-1 opacity-80">Code unifies representation and verification — the interpreter guarantees computation the LLM cannot.</div>
  </div>
</div>

<div class="mt-4 p-3 bg-gray-50 rounded-lg text-sm text-center">

Most design elements serve **both** principles simultaneously. The following slides elaborate how.

</div>

---

# Code as Knowledge Representation

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Why Code?

<div class="text-xs">

<span class="inline-block px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-bold">Ontological Commitment</span> Typed schemas force entity identity and categorical structure — referential ambiguity is eliminated at write time

<span class="inline-block px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-bold">Executable Knowledge</span> `if x: do y` is executable, not merely descriptive — the interpreter guarantees correct *computation*; the LLM handles correct *judgment*

<span class="inline-block px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 font-bold">Both</span> Coding is the LLM's **native output medium**; all modern agents (Manus, Claude Code, OpenClaw, Cursor) are coding agents

</div>

**User as Code applies this paradigm to user memory.**

</div>
<div>

### Passive vs. Active Knowledge

```python
# Passive (text/JSON) — LLM must reason
"Passport expires 2025-02-18, 
 flight departs 2025-01-15,
 need 180 days validity"

# Active (code) — Interpreter verifies
days_left = (passport.expiry 
             - trip.departure).days
if days_left < 180:
    alert(f"Only {days_left} days!")
# Output: "Only 34 days!" ✓
```

Turning unreliable natural-language arithmetic into **deterministic** verified computation.

</div>
</div>

---

# The User as Code Proposal

Model a user's entire memory as a **self-evolving software project**.

<div class="mt-3 grid grid-cols-2 gap-6">
<div>

### Core Insight

The same Python that stores:

```python
passport_expiry = date(2025, 2, 18)
```

can also express — and **execute**:

```python
assert (passport_expiry - flight_date).days >= 180
```

**No other format unifies storage and verification.**

</div>
<div>

### Architectural Fit

Modern AI agents (OpenClaw, Cursor, Claude Code, etc.) are fundamentally **coding agents** built on virtual file systems.

- They read, write, and execute files
- The user project is a **directory in the agent's own workspace**
- No custom memory API needed
- **RL-trainable**: file ops are natural actions that RL can optimize end-to-end

</div>
</div>

<div class="mt-3 p-3 bg-blue-50 rounded-lg">

**The Generate-and-Verify Loop** reduces LLM hallucination by design:
- LLM handles *semantic reasoning* — "should I check passport validity?"
- Interpreter handles *computation* — "is 34 < 180?"
- Operations where LLMs are unreliable → delegated to deterministic execution

</div>

---

# Design Principles

<div class="mt-3 grid grid-cols-3 gap-3 text-xs">
  <div class="p-3 rounded-lg bg-blue-50 border-l-4 border-blue-400">
    <div class="font-bold text-sm mb-1">1. Separation of Structure & Data <span class="inline-block px-1 py-0 rounded bg-blue-100 text-blue-700 text-[10px] font-bold align-middle">Ontology</span></div>
    <div>Schema (class definitions) is separated from state (instance data) and archive (historical records). Schemas embody the ontological commitment; each layer evolves independently.</div>
  </div>
  <div class="p-3 rounded-lg bg-green-50 border-l-4 border-green-400">
    <div class="font-bold text-sm mb-1">2. Modularity by Life Domain</div>
    <div>Memory is partitioned into independent domain packages — <code>travel/</code>, <code>finance/</code>, <code>health/</code> — each loadable and testable independently.</div>
  </div>
  <div class="p-3 rounded-lg bg-purple-50 border-l-4 border-purple-400">
    <div class="font-bold text-sm mb-1">3. Progressive Disclosure</div>
    <div>The agent navigates via a compact <strong>manifest</strong> (~200-300 tokens, always loaded) and retrieves domain modules on demand.</div>
  </div>
</div>

<div class="mt-3 grid grid-cols-2 gap-3 text-xs">
  <div class="p-3 rounded-lg bg-amber-50 border-l-4 border-amber-400">
    <div class="font-bold text-sm mb-1">4. Unified Representation & Verification <span class="inline-block px-1 py-0 rounded bg-green-100 text-green-700 text-[10px] font-bold align-middle">Executable</span></div>
    <div>Code serves as both the <strong>storage format</strong> the LLM reads and the <strong>verification medium</strong> the interpreter executes — no translation step between knowing a fact and computing with it.</div>
  </div>
  <div class="p-3 rounded-lg bg-red-50 border-l-4 border-red-400">
    <div class="font-bold text-sm mb-1">5. Agent-Native File System Abstraction</div>
    <div>The user project is a <strong>directory in the agent's own workspace</strong>. Modern coding agents (OpenClaw, Cursor, Claude Code) already read, write, and execute files — User as Code requires <strong>no custom memory API</strong>, no special toolset. Memory operations are native file operations.</div>
  </div>
</div>

---

# The User Project Structure

<div class="mt-2"></div>

<div class="flex gap-3 text-xs mb-2">
  <span class="inline-block px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-bold">Ontology</span> <span class="opacity-70"><code>schema.py</code> — typed classes enforce entity identity and categorical structure</span>
  &nbsp;&nbsp;
  <span class="inline-block px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-bold">Executable</span> <span class="opacity-70"><code>constraints/</code> + <code>tests/</code> — executable verification and invariant checking</span>
</div>

````md magic-move
```text
jessica_thompson/                    # One user = one project
├── manifest.py                      # Compact index — ALWAYS in context
├── domains/                         # One module per life area
│   ├── identity/
│   │   ├── schema.py                # Class defs              ← Ontology
│   │   └── state.py                 # Current instance data
│   ├── travel/
│   │   ├── schema.py                # Trip, PassportInfo      ← Ontology
│   │   └── state.py                 # Passport, trips, prefs
│   ├── finance/                     # ... more domains
│   ├── vehicles/
│   ├── health/
│   └── family/
├── constraints/                     # Cross-domain checks     ← Executable
│   ├── travel_readiness.py
│   └── financial_authorization.py
└── tests/                           # Invariant tests         ← Executable
    └── test_cross_domain.py
```
````

---

# Key Structural Properties

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Bounded Schema, Unbounded Data

- Domain modules are bounded (~10-20)
- `state.py` holds only **current active state**
- History lives in the archive (Tier 3)

### Cold Start

For a new user, the agent **bootstraps** from the first conversation:

1. Create initial domains
2. Populate schema and state
3. Generate the first manifest

The structure **emerges organically** from the user's actual life.

</div>
<div>

### Living Architecture

Domains are **added, refactored, and retired** — not hardcoded.

```python
# The agent might:
# 1. Create a new domain
mkdir("domains/real_estate/")
# 2. Split a growing domain
# vehicles/ → vehicles/ + boats/
# 3. Merge sparse domains
# combine hobbies/ + sports/
# 4. Archive stale state
# move old trips to archive
```

The agent performs **periodic revision**: schema evolution, domain splitting/merging, stale state archival.

</div>
</div>

---

# Memory Organization: Three Tiers

<div class="mt-2"></div>

<div class="flex items-center gap-3 mt-2">
  <div class="p-3 rounded-lg bg-blue-100 border-2 border-blue-400 text-center flex-1">
    <div class="font-bold text-sm">Tier 1: Schema</div>
    <div class="text-xs mt-1">Class definitions, type annotations</div>
    <div class="text-xs opacity-70 italic">O(number of domains), bounded</div>
    <div class="text-xs opacity-60">Loaded per domain on demand</div>
  </div>
  <div class="text-gray-400 text-xl">→</div>
  <div class="p-3 rounded-lg bg-green-100 border-2 border-green-400 text-center flex-1">
    <div class="font-bold text-sm">Tier 2: State</div>
    <div class="text-xs mt-1">Current instance data</div>
    <div class="text-xs opacity-70 italic">O(active entities), moderate</div>
    <div class="text-xs opacity-60">Loaded when domain accessed</div>
  </div>
  <div class="text-gray-400 text-xl">→</div>
  <div class="p-3 rounded-lg bg-amber-100 border-2 border-amber-400 text-center flex-1">
    <div class="font-bold text-sm">Tier 3: Archive</div>
    <div class="text-xs mt-1">Historical data, raw conversations</div>
    <div class="text-xs opacity-70 italic">O(total interactions), unbounded</div>
    <div class="text-xs opacity-60">Accessed via RAG tool calls</div>
  </div>
</div>


<div class="mt-3">

### Tier 2 Example: `domains/travel/state.py`

```python
passport = PassportInfo(number="AB*****67", expiry=date(2025, 2, 18), country="US")
upcoming_trips = [
    Trip("Tokyo", date(2025, 1, 15), date(2025, 1, 25), refs=["JAL-9823"], intl=True),
    Trip("Mexico City", date(2025, 3, 10), date(2025, 3, 17), refs=["AA-4561"], intl=True),
]
seat_notes = "Prefers aisle on flights > 6hrs, window otherwise. Always window on Japan routes."
```

</div>

---

# Memory Organization: Five Types

<div class="mt-4 text-sm"></div>

| Memory Type | Stored As | LLM Interaction | Example |
|---|---|---|---|
| **Factual State** | Typed attributes in `state.py` | **Read** | `passport_expiry = date(2025, 2, 18)` |
| **Subjective Preferences** | String fields in `state.py` | **Read** (not computable) | `seat_notes = "Aisle on long flights..."` |
| **Persistent Constraints** | Functions in `constraints/` | **Auto-Execute** after updates | `travel_readiness.check(project)` |
| **Ad-hoc Verification** | LLM-generated at query time | **Generate-and-Execute** | `print((passport.expiry - trip.date).days)` |
| **Narrative Context** | Conversation chunks in archive | **Search** via RAG | `archive.search("why Jessica chose JAL")` |


<div class="mt-2 flex gap-3 text-xs">
  <div class="flex-1 p-2 rounded-lg bg-blue-50 border-l-4 border-blue-400">
    <div class="font-bold text-sm mb-1">Read Path <span class="inline-block px-1 py-0 rounded bg-blue-100 text-blue-700 text-[10px] font-bold align-middle">Ontology</span></div>
    <div><strong>Subjective preferences</strong> — read-only, LLM reasons contextually. Typed schema provides unambiguous context.</div>
    <div class="mt-1 opacity-70 italic">"Prefers aisle on long flights, window on Japan routes"</div>
  </div>
  <div class="flex-1 p-2 rounded-lg bg-green-50 border-l-4 border-green-400">
    <div class="font-bold text-sm mb-1">Verify Path <span class="inline-block px-1 py-0 rounded bg-green-100 text-green-700 text-[10px] font-bold align-middle">Executable</span></div>
    <div><strong>Factual relationships</strong> — verified by interpreter, deterministic</div>
    <div class="mt-1 opacity-70 italic">"(passport.expiry - trip.date).days >= 180"</div>
  </div>
</div>

---

# Progressive Disclosure via the Manifest

The `manifest.py` is **always in the agent's context** (~200-300 tokens):

```python {all|1-2|4-11|13-20}{at:1}
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

---

# Four Levels of Disclosure

<div class="mt-2"></div>

<div class="flex items-center gap-2 mt-2">
  <div class="p-2 rounded-lg bg-green-100 border-2 border-green-500 text-center flex-1">
    <div class="font-bold text-sm text-green-800">L0: Manifest</div>
    <div class="text-xs italic">Always loaded</div>
    <div class="text-xs opacity-70">~200-300 tokens</div>
  </div>
  <div class="text-gray-400 text-lg">→</div>
  <div class="p-2 rounded-lg bg-blue-100 border-2 border-blue-400 text-center flex-1">
    <div class="font-bold text-sm">L1: Schema</div>
    <div class="text-xs italic">On topic</div>
    <div class="text-xs opacity-70">Class definitions</div>
  </div>
  <div class="text-gray-400 text-lg">→</div>
  <div class="p-2 rounded-lg bg-amber-100 border-2 border-amber-400 text-center flex-1">
    <div class="font-bold text-sm">L2: State</div>
    <div class="text-xs italic">On need</div>
    <div class="text-xs opacity-70">Instance data</div>
  </div>
  <div class="text-gray-400 text-lg">→</div>
  <div class="p-2 rounded-lg bg-red-100 border-2 border-red-400 text-center flex-1">
    <div class="font-bold text-sm">L3: Archive</div>
    <div class="text-xs italic">Via RAG tool</div>
    <div class="text-xs opacity-70">Full history</div>
  </div>
</div>


<div class="mt-4 grid grid-cols-2 gap-6">
<div>

### Self-Documenting System

The manifest doubles as the agent's **bootstrap instruction**.

By reading it, the agent understands:
- Project layout
- Available domains
- Active concerns and alerts

</div>
<div>

### No Separate Instructions Needed

> No "how to use this memory system" prompt is needed.
>
> The project **is its own documentation** — just as a well-structured codebase is navigable from its directory layout.

</div>
</div>

---

# The Generate-Verify-Review Loop <span class="inline-block px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-xs font-bold align-middle">Executable Knowledge</span>

The core mechanism for **reducing LLM hallucination** in user memory — a continuous loop driven by the coding agent.

<div class="mt-3 flex items-center justify-center gap-2 text-xs">
  <div class="p-3 rounded-lg bg-purple-100 border-2 border-purple-400 text-center" style="min-width:140px">
    <div class="font-bold text-sm">1. Generate</div>
    <div class="opacity-70 mt-1">Coding agent writes Python code — constraints, checks, state updates</div>
  </div>
  <div class="text-gray-400 text-lg">→</div>
  <div class="p-3 rounded-lg bg-green-100 border-2 border-green-400 text-center" style="min-width:140px">
    <div class="font-bold text-sm">2. Verify</div>
    <div class="opacity-70 mt-1">Execute constraint code (like test cases) — deterministic results</div>
  </div>
  <div class="text-gray-400 text-lg">→</div>
  <div class="p-3 rounded-lg bg-blue-100 border-2 border-blue-400 text-center" style="min-width:140px">
    <div class="font-bold text-sm">3. Review</div>
    <div class="opacity-70 mt-1">Coding agent reviews results, decides next action</div>
  </div>
  <div class="text-gray-400 text-lg">↩</div>
</div>

<div class="mt-4 grid grid-cols-2 gap-6">
<div>

### Anti-Hallucination by Design

| | Coding Agent | Interpreter |
|---|---|---|
| **Role** | Semantic reasoning | Computation |
| **Decides** | *What* to check | *Correctness* of check |
| **Hallucination risk** | Low (judgment) | **Zero** (deterministic) |

The loop iterates: generate code → execute to verify → review results → refine or persist.

</div>
<div>

### From Ad-hoc to Persistent

When an ad-hoc check proves useful:
1. Agent writes it to `constraints/`
2. Stored as `def check(project) -> List[Alert]`
3. **Auto-evaluates** after relevant state updates
4. Alerts surface in `ACTIVE_ALERTS`

Constraints are **not pre-authored** — they emerge from the coding agent's own reasoning.

</div>
</div>

---

# The Write Path: Update Pipeline

<div class="mt-4"></div>

<div class="flex items-center gap-1 mt-2 text-xs">
  <div class="p-2 rounded bg-blue-100 border border-blue-400 text-center flex-1">
    <div class="font-bold">1. Classify</div>
    <div class="opacity-70">Which domains?</div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="p-2 rounded bg-gray-100 border border-gray-300 text-center flex-1">
    <div class="font-bold">2. Load</div>
    <div class="opacity-70">Schema + State</div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="p-2 rounded bg-gray-100 border border-gray-300 text-center flex-1">
    <div class="font-bold">3. Diff</div>
    <div class="opacity-70">New? Update? Conflict?</div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="p-2 rounded bg-gray-100 border border-gray-300 text-center flex-1">
    <div class="font-bold">4. Patch</div>
    <div class="opacity-70">Edit state file</div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="p-2 rounded bg-amber-100 border border-amber-400 text-center flex-1">
    <div class="font-bold">5. Validate</div>
    <div class="opacity-70">Tests + Constraints</div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="flex flex-col gap-1 flex-1">
    <div class="p-1 rounded bg-green-100 border border-green-400 text-center">
      <div class="font-bold">6a. Commit ✓</div>
    </div>
    <div class="p-1 rounded bg-red-100 border border-red-400 text-center">
      <div class="font-bold">6b. Clarify ✗</div>
    </div>
  </div>
  <div class="text-gray-400">→</div>
  <div class="p-2 rounded bg-blue-100 border border-blue-400 text-center flex-1">
    <div class="font-bold">7. Manifest</div>
    <div class="opacity-70">Regenerate</div>
  </div>
</div>


<div class="mt-3 grid grid-cols-2 gap-6">
<div>

### Two-Layer Persistence

- **Working Directory** (session-scoped): Drafts, ad-hoc checks, schema experiments — ephemeral
- **Persistent Storage** (cross-session): Committed project — source of truth

**Autonomous save:** The agent decides when to commit, like a developer choosing when to `git commit`.

</div>
<div>

### No Bespoke Toolset

The agent reads, writes, and executes files — **the same primitives any coding agent already has**.

- Validation pipeline lives inside the repo
- Inspectable and version-controlled
- Only specialized infra: RAG for Tier 3

Every patch committed with a **source-session reference** for audit trail.

</div>
</div>

---

# Periodic Revision & External Knowledge

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Periodic Revision — "Dreaming"

Like dreaming — the brain consolidates memories during sleep. The agent periodically steps back to **holistically restructure** its understanding:

- Schema evolution and restructuring
- Domain splitting / merging
- Stale state archival
- Constraint pruning
- Cross-domain reference audits
- Preference synthesis

Triggered by: agent judgment, scheduled cycles, or thresholds.

</div>
<div>

### External Knowledge Integration

Constraints can import **versioned factual reference packages**:

```python
# constraints/travel_readiness.py
from refs.visa_policy import VisaPolicy
from refs.passport_rules import PassportRules

def check(project) -> List[Alert]:
    policy = VisaPolicy.for_country(
        trip.destination)
    min_days = policy.passport_validity_days
    # Grounded in verified, current 
    # regulations — not stale training data
```

Analogous to RAG grounding — not hand-crafted features.

</div>
</div>

---
layout: section
---

# Part 4
## Discussion

---

# The Bitter Lesson and the Role of Code

<div class="mt-4"></div>

**Objection:** *Typed schemas contradict Sutton's "Bitter Lesson" — hand-crafted structure is eventually superseded by general methods leveraging computation.*


<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### What is LLM-Generated (Domain Knowledge)

- Schemas, constraints, tests, state data
- Domain partitioning decisions
- `class Trip` design and field selection
- Constraint creation and promotion
- Periodic restructuring

**This is *learned* structure** — the model's own decisions, not imposed features.

</div>
<div>

### What is Human-Designed (Infrastructure)

- Project directory convention
- Update pipeline
- Progressive disclosure levels
- Generate-and-verify loop

**This is *engineering infrastructure*** — analogous to choosing Git or CI/CD. Tools, not domain features.

</div>
</div>


<div class="mt-2 p-3 bg-green-50 rounded-lg">

The interpreter is a **tool**, not a **rule**. The LLM retains full freedom in *what to check*; the interpreter guarantees correct computation.

</div>

---

# A Unified Home for Factual and Preferential Knowledge

Code accommodates **both** factual knowledge and subjective preferences — formalism where it helps, natural language where it must.

<div class="mt-3 flex items-center gap-3">
  <div class="p-3 rounded-lg bg-green-100 border-2 border-green-400 text-center flex-1">
    <div class="font-bold text-sm text-green-800">Factual Knowledge</div>
    <div class="text-xs opacity-70 mt-1">Typed attributes · Date arithmetic · Cross-domain constraints</div>
    <div class="text-xs mt-1">Formalism → <strong>verified by interpreter</strong></div>
  </div>
  <div class="text-gray-400 text-lg flex-shrink-0">+</div>
  <div class="p-3 rounded-lg bg-amber-100 border-2 border-amber-400 text-center flex-1">
    <div class="font-bold text-sm text-amber-800">Preferences & Context</div>
    <div class="text-xs opacity-70 mt-1">Context-dependent preferences · Behavioral patterns · Emotional context</div>
    <div class="text-xs mt-1">Natural language → <strong>expressive freedom</strong></div>
  </div>
</div>

<div class="mt-3 grid grid-cols-2 gap-6">
<div>

### Both in the Same File

```python
# Factual — typed, verified
passport = PassportInfo(
    expiry=date(2025, 2, 18), country="US")

# Preference — natural language, expressive
seat_notes = """Prefers aisle on flights 
> 6hrs, window otherwise. Exception: 
always window on Japan routes 
for Mt. Fuji view."""
```

Each gets the representation it deserves: formalism for facts that need verification, natural language for preferences that need expressive freedom.

</div>
<div>

### Shared Infrastructure

Both types benefit from the same architecture:

- **Version control** — preferences evolve over time, just like facts
- **Domain organization** — seat preferences live in `travel/`, not scattered across sessions
- **Progressive disclosure** — loaded on demand, not bloating every context window

<div class="mt-2 p-2 bg-gray-50 rounded-lg text-xs">

**Future work:** LLM-synthesized personality profiles periodically regenerated from cross-domain review of preference strings.

</div>

</div>
</div>

---

# Agent-Native Architecture & Limitations

<div class="mt-2 grid grid-cols-2 gap-6">
<div>

### Agent-Native Architecture

The user project is a **directory in the agent's virtual file system**.

- Reads, writes, and executes files
- Same primitives the agent already has
- **No custom memory API** or special toolset

**RL-trainable:** Memory ops are standard file-system actions, so foundation models can be **trained via RL** to improve memory:
- When to summarize, what to extract, how to retrieve
- Custom APIs are opaque to RL; file ops are natural actions RL optimizes end-to-end

</div>
<div>

### Limitations

**1. Verification Overhead**
More expensive than appending text. *Pay at write time for correctness at read time.*

**2. Constraint Logic Errors**
Interpreter guarantees correct *computation* but not correct *logic* (e.g., wrong threshold). Same failure mode as any LLM judgment.

**3. LLM Code Generation Quality**
Mitigated by strict type checking, test validation, and reject-and-retry loops.

</div>
</div>

---
layout: section
---

# Part 5
## Conclusion

---

# Why Code — and Nothing Else

<div class="mt-2"></div>

Code is the **only** format that simultaneously enforces **ontological commitment** (entities must be named, typed, and distinguished) and enables **seamless verification** (the same file the agent reads is the file the interpreter executes).

<div class="mt-3 grid grid-cols-3 gap-4 text-xs">
  <div class="p-3 rounded-lg bg-gray-100 border border-gray-300">
    <div class="font-bold text-sm mb-1">Natural Language / Markdown</div>
    <div>Read ✓ &nbsp; Disambiguate ✗ &nbsp; Verify ✗</div>
    <div class="opacity-70 mt-1">"My car" persists unresolved. "34 < 180" must be <em>reasoned</em> in prose — error-prone.</div>
  </div>
  <div class="p-3 rounded-lg bg-gray-100 border border-gray-300">
    <div class="font-bold text-sm mb-1">JSON / Knowledge Graph</div>
    <div>Read ✓ &nbsp; Disambiguate ✗ (partial) &nbsp; Verify requires translation</div>
    <div class="opacity-70 mt-1">IDs possible but not enforced — disambiguation is convention. Verification requires translation to code.</div>
  </div>
  <div class="p-3 rounded-lg bg-green-100 border-2 border-green-500">
    <div class="font-bold text-sm mb-1 text-green-800">Python (User as Code)</div>
    <div>Read ✓ &nbsp; Disambiguate ✓ &nbsp; Execute ✓ &nbsp; <strong>Same file</strong></div>
    <div class="opacity-70 mt-1">Typed schemas force ontological commitment; the interpreter verifies computation — zero translation, zero ambiguity.</div>
  </div>
</div>

<div class="mt-4 grid grid-cols-2 gap-6">
<div>

### <span class="inline-block px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 text-xs font-bold">Ontology</span> vs. Ambiguity

- Typed schemas force entity disambiguation **at write time**
- Eliminates referential ambiguity that retrieval-based systems defer indefinitely

### <span class="inline-block px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-xs font-bold">Executable</span> vs. Hallucination

- Generate-and-verify loop: LLM reasons *what* to check; interpreter guarantees the *computation*
- Emergent constraints promoted to persistent monitors — no human authoring
- Active Service (Layer 3): arithmetic, not retrieval

</div>
<div>

### Architecture in One Sentence

A user is a **self-evolving software project** in the agent's workspace:
- Same file and interpreter primitives the agent already has
- Three-tier progressive disclosure
- Version-controlled patches and executable tests

<div class="mt-3 p-2 bg-gray-50 rounded-lg text-xs">

**Two challenges → two principles:** ontological commitment eliminates ambiguity; executable knowledge eliminates hallucination. Most design elements serve both.

</div>

</div>
</div>

---

# Beyond User Memory: Code as Knowledge Representation

User as Code suggests a broader hypothesis: **self-evolving code may be a third paradigm for knowledge representation**, distinct from both external knowledge bases and post-training.

<div class="mt-4 grid grid-cols-3 gap-4 text-xs">
  <div class="p-3 rounded-lg bg-gray-100 border border-gray-300">
    <div class="font-bold text-sm mb-2">Textual KBs</div>
    <div class="text-green-700">✓ Inspectable, low update cost</div>
    <div class="text-green-700">✓ Declarative, structured</div>
    <div class="text-red-700">✗ Not executable — read-only</div>
    <div class="text-red-700">✗ No built-in verification</div>
    <div class="mt-2 opacity-60 italic">Files, databases, knowledge graphs</div>
  </div>
  <div class="p-3 rounded-lg bg-gray-100 border border-gray-300">
    <div class="font-bold text-sm mb-2">Post-Training</div>
    <div class="text-green-700">✓ High capacity, implicit patterns</div>
    <div class="text-green-700">✓ End-to-end optimizable</div>
    <div class="text-red-700">✗ Opaque — not inspectable</div>
    <div class="text-red-700">✗ Expensive to update (training run)</div>
    <div class="mt-2 opacity-60 italic">SFT, RLHF, knowledge in weights</div>
  </div>
  <div class="p-3 rounded-lg bg-green-100 border-2 border-green-500">
    <div class="font-bold text-sm mb-2 text-green-800">Self-Evolving Code</div>
    <div class="text-green-700">✓ Inspectable + low update cost</div>
    <div class="text-green-700">✓ Executable + verifiable</div>
    <div class="text-green-700">✓ Declarative + procedural</div>
    <div class="text-green-700">✓ LLM-generated structure (Bitter Lesson)</div>
    <div class="mt-2 opacity-60 italic">User as Code, agent-maintained repos</div>
  </div>
</div>

<div class="mt-4 grid grid-cols-2 gap-6">
<div>

### The Third Path

Textual KBs are inspectable but inert. Weights are expressive but opaque. Code is **both inspectable and executable** — the structure is LLM-generated (satisfying the Bitter Lesson), while the medium is verifiable (leveraging computation for correctness, not just storage).

</div>
<div>

### Open Questions

- Can self-evolving code scale beyond personal memory to **domain knowledge** (medical protocols, legal rules, financial regulations)?
- How does code KR interact with **continual learning** — can weight updates and code updates be co-optimized?
- What are the **theoretical limits** of LLM-generated ontologies?

</div>
</div>

---
layout: center
class: text-center
---

# Thank You

<div class="mt-6 text-xl">

**User as Code: Executable Memory for Personalized Agents**

</div>

<div class="mt-6 text-base opacity-80">

*Code closes the gap between knowing and computing —<br/>typed schemas eliminate ambiguity, and the interpreter eliminates hallucination.*

</div>

<div class="mt-4 text-sm opacity-50">

Bojie Li

Chief Scientist, Pine AI

</div>

<PoweredBySlidev class="mt-12" />