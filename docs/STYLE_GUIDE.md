# Documentation Style Guide

> **Scope:** Governs all documentation under `docs/`. Applies to both human writers and AI documentation agents.
> **Standard:** [Diátaxis Framework](https://diataxis.fr/) + Constraint-Driven Agent Invariants.
> **Enforcement:** The repository-root `AGENTS.md` (added when this repo is bootstrapped with
> `python-agentic-bootstrap`) MUST require compliance with this file. Link to these rules; never restate
> them elsewhere — restated rules drift.

---

## 1. The 5 Core Invariants

1. **Single Source of Truth:** `docs/` is the sole canonical home for permanent knowledge. `artefacts/` is
   transient scratch and is off-limits to automatic agent reading or indexing.
2. **Zero Specification Drift:** Code and architecture specs MUST remain synchronized. Every behavioural
   change requires a matching spec update **in the same change set**.
3. **Empirical Grounding:** Never document aspirational features as existing facts. Every page that describes
   behaviour that does not yet exist MUST carry a `> [!NOTE] Planned.` status line naming what is missing.
   In this repository that applies to the entire `audit/` package surface; a source anchor is added as each rule pack lands.
4. **Symbol Anchoring:** Reference code symbols using fully-qualified names and explicit file paths. Once the
   file exists, link to its line anchors — the required form is
   ``[registry.py#L1-L40](../audit/rules/registry.py#L1-L40)``, shown here as a real path in this repository so
   the example is itself checkable. Documentation
   pages for behaviour MUST name the file that implements it, even when that file is still planned; while a file
   is planned, name it as a code span instead of linking to it.
5. **Living ADRs (Current-State Only):** An ADR MUST describe only the shipped, current design. When a
   decision changes, revise the ADR body **in place**; when an ADR becomes irrelevant, delete it. Git is the
   archive — never keep tombstone, superseded, or deprecated stubs.

---

## 2. Writing Tones & Audiences

| Track | Audience | Focus | Tone |
|---|---|---|---|
| **User Overview** | CTOs, engineering leads, architects, consulting clients | Value, methodology, what the report means, guarantees | Executive, clear, concise |
| **Contributor Deep Dive** | Engineers, maintainers | Mechanics, scan engine, check catalogue, report schema | Tactical, technical, precise |
| **How-To (Task Track)** | Operators, engineers | One task, executable steps, verification | Direct, imperative |
| **Agent Directives** | AI coding agents | Constraints, rules, mandatory steps | RFC 2119 (MUST, MUST NOT, REQUIRED) |

Rules:
- User-overview pages MUST NOT descend into implementation internals — link to the matching contributor
  page instead.
- Contributor pages MUST ground every claim in a source file, symbol, or check ID.
- How-to pages MUST state their prerequisites and an explicit verification step.

---

## 3. Formatting Standards

- **Headers:** ATX style (`#`, `##`, `###`), maximum 4 levels deep.
- **Diagrams:** Use Mermaid (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`). Do not embed external images
  when a Mermaid representation is possible.
- **Alerts:** Use GitHub-flavoured Markdown alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`,
  `[!CAUTION]`).
- **Tables:** Use standard GFM tables with aligned headers for scannability.
- **Blank lines:** one blank line before and after headers, code blocks, tables, and alert blocks.
- **Check references:** cite checks by their catalogue ID (`EXEC-02`, `TST-01`), never by prose description.

---

## 4. Document Types & Locations

| Content Type | Location | Naming |
|---|---|---|
| This style guide | `docs/STYLE_GUIDE.md` | `STYLE_GUIDE.md` |
| Architecture overview / explanations | `docs/architecture/` | `<topic>.md` |
| Architectural Decision Records | `docs/architecture/adrs/` | `NNNN-short-title.md` |
| ADR index & doc router | `docs/architecture/README.md` | `README.md` |
| Domain glossary | `docs/architecture/glossary.md` | `glossary.md` |
| Evaluator-facing pages | `docs/architecture/user-overview/` | `NN-topic.md` |
| Engineer-facing pages | `docs/architecture/contributor-deep-dive/` | `NN-topic.md` |
| How-to guides | `docs/how-to/` | `<task>.md` |
| Tutorials | `docs/tutorials/` | `<topic>.md` |
| Document templates | `docs/templates/` | `<type>-template.md` |

New documents MUST start from the matching template in `docs/templates/`.

---

## 5. Agent-Specific Writing Rules

### 5.1 Verification first

1. **Query-first:** consult `codebase-memory-mcp` (`search_graph`, `get_code_snippet`, `get_architecture`)
   to verify symbols and file locations against the current codebase before grepping or reading whole files.
2. Check existing pages in `docs/` — update rather than duplicate.
3. Check `docs/architecture/adrs/` for the highest sequence number ever used before creating an ADR.

### 5.2 Doc Maintenance Trigger (definition of done)

When a change alters a public interface, observable behaviour, architecture, or a check's semantics:

1. Run `detect_changes` on `codebase-memory-mcp`.
2. Update every affected documentation page and its source line anchors.
3. Update the ADR index in `docs/architecture/README.md` whenever an ADR is added, revised, or deleted.
4. Do all of the above **in the same change set** as the code change.

Pure internal refactors with no observable or documentation impact do not require doc edits.

### 5.3 Accuracy & status tagging

- Never state aspirational or planned capabilities as working code.
- Tag planned features explicitly: `> [!NOTE] Planned.`
- **Never document a check as implemented while it exists only in the catalogue.** The check catalogue is the
  design; the implementation status column is the fact.

---

## 6. ADR Lifecycle

ADRs live in `docs/architecture/adrs/` and are created from `docs/templates/adr-template.md`.

```markdown
# NNNN. Short Title

* **Status:** Accepted
* **Date:** YYYY-MM-DD
* **Last reviewed:** YYYY-MM-DD
* **Deciders:** [@github-handle]

## Context
[Technical context, problem statement, alternatives considered.]

## Decision
[Chosen design, with links to affected source files.]

## Alternatives Considered
| Alternative | Why it was rejected |
|---|---|

## Consequences
### Positive
* [Benefit]

### Negative / Trade-offs
* [Trade-off]
```

1. **Create:** assign `highest-ever sequence number + 1`. A number whose ADR was deleted is retired and MUST NOT
   be reused.
2. **Record:** use `docs/templates/adr-template.md`.
3. **Index:** add a row to the index table in `docs/architecture/README.md` in the same change set.
4. **Revise in place:** when a decision changes, overwrite the ADR body and keep its number. Fold the reversal
   into the ADR's own *Alternatives Considered* table. Do NOT create a second "superseding" ADR and do NOT
   leave a tombstone stub. Use `git log --follow` to recover older wording.
5. **Delete when irrelevant:** when an ADR no longer describes anything in the current design, delete the file
   and update every inbound reference in the same change set.

> [!IMPORTANT]
> There is no `Deprecated`, `Superseded`, or `Rejected` status. A merged ADR is always `Accepted`
> (`Proposed` is allowed in-flight but MUST NOT be merged). Stale instructions pollute agent context, so
> staleness is treated as a defect, not as history.

---

## 7. Content Boundaries (What Does NOT Belong in Docs)

| ❌ Forbidden in `docs/` | ✅ Proper location |
|---|---|
| In-progress agent plans, research drafts, scratch notes | `artefacts/` |
| Per-run execution logs and audit output | The `--out` path chosen at invocation |
| The check rule packs themselves (ids, globs, weights) | Source code — `docs/` holds the *catalogue and rationale*, never the executable rules |
| Secrets, tokens, and environment values | `.env` (never committed) |
| Copied excerpts of `codebase-agentic-readiness-framework` pages | A link to the framework page plus a phase/anchor reference |

> [!IMPORTANT]
> The last row is a hard rule for this repository. The readiness framework is an external source of truth.
> These docs MUST cite it (phase, section) and MUST NOT restate it — restated rules drift.

`artefacts/` is never an architectural source of truth and is excluded from the `codebase-memory` index.
