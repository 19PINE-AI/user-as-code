# Outline: User as Code: Executable Memory for Personalized Agents

## Abstract

Current personalization in AI agents primarily relies on Retrieval-Augmented Generation (RAG) over unstructured text or vector databases. While effective for open-domain knowledge, this "Bag of Facts" approach struggles with the specific challenges of user memory: resolving conflicting information, managing temporal dependencies, and enforcing logical constraints (e.g., "passport expiration" vs. "flight date"). This paper introduces **"User as Code"**, a novel paradigm where an agent's understanding of a user is maintained not as a passive database, but as an executable Python class (`class User`). In this framework, memory updates are treated as **code refactoring**, logical constraints are enforced via **unit tests**, and complex preferences are expressed as **methods**. We demonstrate that treating user memory as a software engineering problem leverages the inherent precision, structure, and verifiability of code, effectively solving the "Active Service" and "Conflict Resolution" challenges inherent in vector-based approaches.

## 1. Introduction

### 1.1 The "Bag of Facts" Problem
*   **Context:** AI Agents need to maintain long-term memory to provide personalized services (referenced as the "User Memory Challenge" in the book's Chapter 3).
*   **Problem:** Current systems (VectorDBs, JSON stores) treat memory as a loose collection of facts.
    *   **Conflict:** When a user says "I realized I actually hate cilantro" after previously saying "I love cilantro", vector retrieval might return both or the wrong one.
    *   **Logic Gap:** LLMs struggle to reliably detect subtle logical conflicts in retrieved text (e.g., booking a flight for a date *after* a visa expires).
*   **Thesis:** User models require the strict logical consistency of software. We should transition from "Retrieving Information" to "Executing a User Model."

### 1.2 The "User as Code" Proposal
*   Define the user state as a version-controlled, executable code object.
*   Application of the "Infrastructure as Code" philosophy to Agent Personalization.

## 2. Background and Related Work

### 2.1 Current Approaches to User Memory
*   **Vector RAG:** High recall, low precision on conflicts.
*   **Structured Knowledge Graphs:** Better relations, but rigid and hard to update.
*   **Mem0 and similar frameworks:** Hybrid approaches (Chapter 3).

### 2.2 Code Generation beyond Programming
*   **Insight from Chapter 5:** "Code Generation as a Structured Knowledge Base."
    *   Code is not just for software; it is a high-density, unambiguous knowledge representation format.
    *   Code allows for "Active Knowledge": A rule encoded as `if x: do y` is more robust than a text description of the rule.

## 3. Methodology: The "User as Code" Paradigm

### 3.1 The `User` Class Structure
*   **Attributes as Facts:** `self.passport_expiry`, `self.home_location`.
*   **Methods as Preferences/Heuristics:** 
    *   Instead of storing "Likes aisle seats", define:
        ```python
        def get_seat_preference(flight_duration):
            if flight_duration > 6: return "Aisle"
            else: return "Window"
        ```
    *   This captures *conditional* preferences often lost in static embeddings.

### 3.2 Memory Update as Code Refactoring
*   **The Refactoring Agent:** When new information arrives, the Agent does not "append" to a log. It writes a **Pull Request** to refactor the `User` class.
*   **The "Checklist" Effect (Chapter 5 Insight):**
    *   Updating memory requires calling specific methods (e.g., `update_address(street, city, zip)`).
    *   Strict function signatures act as a cognitive checklist, forcing the LLM to verify it has all necessary details before committing the memory, reducing hallucinations.

### 3.3 Conflict Resolution as Unit Testing
*   **Runtime Validation:** The `User` class contains invariant assertions (e.g., `assert self.budget > 0`).
*   **Scenario:** 
    *   Input: "Book me a flight to Tokyo."
    *   Action: Agent instantiates `User`, runs `user.validate_travel_doc(dest="Tokyo")`.
    *   Result: If passport is expired, the code raises a specific `PassportExpiredError`.
*   **Advantage:** Deterministic detection of conflicts, solving the "Active Service" challenge (Chapter 3).

## 4. System Implementation

### 4.1 Architecture
*   **Memory Compiler:** A module that accepts a "Memory Patch" (Python code) from the Agent and attempts to apply it to the persistent `User` object.
*   **The Critic:** Runs a suite of unit tests against the new state. If tests fail (logical conflict), the update is rejected, and the Agent is prompted to clarify with the human.

### 4.2 Integration with External Knowledge
*   **Importing World Logic:** 
    *   `from world.regulations import VisaPolicy`
    *   Rules are imported as code libraries, ensuring the User Profile is checked against ground-truth regulations (Code as Knowledge Base).

## 5. Experiments and Evaluation

### 5.1 Experimental Setup
*   **Benchmark:** LOCOMO (Long Context and Memory Optimization) benchmark (referenced in Chapter 3).
*   **Baselines:** 
    1.  Standard RAG (Dense Embedding).
    2.  Hybrid RAG (Dense + Sparse).
    3.  GraphRAG.

### 5.2 Experiment 1: Conflict Resolution
*   **Metric:** Accuracy in resolving direct contradictions (e.g., "I moved to NY" vs "Address is SF").
*   **Hypothesis:** "User as Code" achieves near 100% consistency due to the single-source-of-truth nature of class attributes.

### 5.3 Experiment 2: Active Service (Complex constraints)
*   **Metric:** Success rate in flagging "Silent Failures" (e.g., expired constraints, missing prerequisites).
*   **Scenario:** Multi-step travel planning with conflicting constraints.
*   **Result Analysis:** Comparing the interpretability of Code execution traces vs. Chain-of-Thought text reasoning.

## 6. Discussion

*   **Logic as the Ultimate Constraint:** Why LLMs are better at writing logic (code) to check facts than checking facts with pure text.
*   **Limitations:** The overhead of "compiling" memory; handling fuzzy/emotional nuances that don't fit into classes.

## 7. Conclusion
Transforming User Memory into an executable code artifact provides the rigor missing from current Agent systems. By treating users "as code," we enable Agents that are not just knowledgeable, but logically consistent and proactively helpful.
