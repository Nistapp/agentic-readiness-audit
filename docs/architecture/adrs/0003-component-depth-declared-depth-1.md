# 0003. Component Depth: Declared Components, Depth 1

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

Phase 1 of the framework requires root **and component-level** `AGENTS.md` files. Component-level governance is
the mechanism that keeps a monorepo's differing conventions from bleeding into each other, and it is where
Constraint Engineering becomes enforceable per component rather than per repository.

The question the audit must answer is what a "component" is, and how deep to look for one.

Directory shape is a poor guide. In a Java monolith, `src/main/java/com/acme/orders/` is a package, not a
component; in a Go service, `internal/handlers/` is a package too. Neither should be expected to carry its own
governance file, and a checker that demands one produces noise in exactly the repositories this tool targets.
Build manifests, by contrast, state component boundaries explicitly and unambiguously — and the person who
declares a module is the person who would write its `AGENTS.md`.

Recursion adds real cost: cycle and symlink handling, duplicate findings for a module of a module, a report that
grows faster than its usefulness, and a per-component ratio whose denominator the reader cannot reconstruct.

---

## Decision

**Score declared components only, at depth 1.**

1. **Declared means named by a build manifest** — `workspaces` in `package.json`, `pnpm-workspace.yaml`, maven
   `<modules>`, gradle `include(...)`, `go.work use`, Cargo `[workspace] members`, Nx `project.json`,
   `*.csproj`/`.sln`.
2. **Depth 1**: the root component plus each immediate declared component. No recursion.
3. **Coverage is scored as a ratio** — `declared components with a compliant AGENTS.md / declared components`,
   reported as `PARTIAL` with the ratio, never as a boolean.
4. **Undeclared multi-app layouts are reported, not scored** — a repository with `apps/` and `services/`
   directories and no workspace declaration appears in an informational "candidate components (not declared)"
   list. The undeclared layout is itself a useful finding.
5. **No declarations at all** yields a single root component, which is correct for a monolith rather than a
   degenerate case to be worked around.

Implemented by the component model in `audit/components.py` (`detect_components`); see
[Scan Engine & Tiering](../contributor-deep-dive/01-scan-engine-and-tiering.md) § 4.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Recursive walk over all directories | Report bloat, cycle guards, and duplicate findings for nested modules; the per-component ratio stops being reconstructible by the reader. |
| Infer components from directory depth without manifests | Produces noise in precisely the brownfield targets the tool serves — language package nesting would be scored as "components". |
| Root `AGENTS.md` only | Contradicts the framework's explicit requirement and discards the most valuable monorepo signal the tool can produce. |
| Ask a model which directories are components | Non-deterministic, and the answer would be a guess dressed as a fact. Build manifests are ground truth ([ADR-0004](0004-no-llm-in-v1.md)). |
| Score the candidate (undeclared) list as well | Punishes repositories that legitimately have a flat layout, and scores the absence of a convention rather than the absence of governance. |

---

## Consequences

### Positive

* The coverage ratio is reproducible and defensible: a reader can count the declared components themselves.
* No false findings in Java, Go, and .NET repositories where directory nesting is idiomatic.
* The undeclared-candidate list is often the most actionable output of the first scan, because it names
  boundaries the team has not written down.

### Negative / Trade-offs

* A genuinely nested component — a module with its own build file inside another declared component — is not
  scored, and the report has no per-component finding for it. The candidate list is the only signal.
* Component detection is per-ecosystem code that must be maintained as build tools change.
* Repositories that declare components for packaging reasons but never intend per-component governance will
  receive a `PARTIAL` ratio they consider noise; the correct fix is to improve `AGENTS.md` coverage, not to
  weaken the check.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
