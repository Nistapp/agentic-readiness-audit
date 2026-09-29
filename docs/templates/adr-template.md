# [NNNN]. [Short Imperative Title]

* **Status:** Accepted *(Proposed is permitted in-flight but MUST NOT be merged)*
* **Date:** YYYY-MM-DD
* **Last reviewed:** YYYY-MM-DD
* **Deciders:** [@github-handle]

---

## Context

[Technical context, problem statement, business driver, and constraints.
Mention what alternative solutions were evaluated.]

---

## Decision

[Chosen design, pattern, or dependency. Links to affected source files.]

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| [Option B] | [Reason] |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive
* [Key benefit 1]

### Negative / Trade-offs
* [Known trade-off]

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/NNNN-title.md`.

See [`docs/STYLE_GUIDE.md`](../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
