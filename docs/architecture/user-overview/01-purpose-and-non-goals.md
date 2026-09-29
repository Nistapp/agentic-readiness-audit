# 1. Purpose & Non-Goals

> **Target Audience:** CTOs, engineering leads, architects, and consulting clients evaluating a legacy codebase for agentic work.
> **Key Goal:** Explain what this audit does, what it deliberately refuses to do, and how to read what it produces.
> **Status:** Published — Page 1 of the User Overview; see [the index](../README.md). The `AGT`, `EXEC`, `CMD`, `SEC`, `TOOL` and `CI` packs are implemented today; the rest of the catalogue reports `UNKNOWN`.

---

## Executive Summary

`python-agentic-audit` scans an existing repository and produces a **prioritised list of what to change so that
AI coding agents can work in it effectively**. It is a diagnostic, not a gate. It never blocks a build, never
fails a pull request, and never returns a pass/fail verdict on your codebase.

The reasoning is deliberate. A legacy codebase is not *wrong* — it is **under-prepared**, and preparation is a
sequence of improvements, not a threshold to trip over. A tool that fails CI on day one teaches teams to disable
it. A tool that hands over an ordered list of blockers teaches them what to fix first, and lets them stop when
the remaining items stop mattering.

The audit is anchored to **Phase 1 (Bootstrap)** of the [agentic-readiness
framework](https://github.com/Nistapp/codebase-agentic-readiness-framework/blob/main/brownfield-legacy/Phased-Approach.md)
— the phase the framework itself calls a dramatic improvement on its own. Later phases are reported as
presence-level signals and never scored.

---

## What This Is (and Is Not)

| It **is** | It **is not** |
|---|---|
| A read-only scan producing a report | A gate that fails builds, PRs, or merges |
| A prioritised, evidence-backed backlog | A quality judgement about your team |
| Deterministic — same repo, same report | An LLM opinion; no model is called |
| Phase-anchored to the readiness framework | A substitute for the remediation work |
| Honest about what it could not verify | A completeness guarantee |

---

## Three Things the Report Tells You

1. **Blockers** — what makes agent work impossible or unsafe today: no runnable verification path, no
   non-interactive way to boot the project, an unpinned toolchain, no agent governance file, a CI-only gate.
2. **Degraders** — what makes agent work unreliable: competing configs for one concern, skipped tests, run
   instructions that no longer resolve, generated files committed in-tree, several agent-instruction files that
   disagree.
3. **Provenance** — the framework phase and requirement each finding maps to, with the file and line that
   produced it, so a finding can be argued with.

Every finding is phrased as **"an agent cannot *do X* today because *Y*"**. That phrasing is the point: it makes
the report usable as a work queue rather than a compliance checklist.

---

## What the Report Will Not Claim

Whether your index is *used*, whether your baselines are *adequate*, whether your suite is *trustworthy*,
whether your docs are *accurate*, whether your team will *honour* the gate. These appear as a separate,
explicitly named **unattested** list.

Absence of a finding is not evidence of quality — it is absence of evidence, and the report says so in its own
header. This is a direct response to the false-confidence risk the framework records: quality gates raise the
probability of correctness; they never guarantee it.

---

## Who This Is For

- **A team about to introduce coding agents into a legacy repository** and wondering where to start.
- **A consultancy taking an "agentic readiness" engagement**, where the report becomes the scope of work.
- **A maintainer** who wants an honest, re-runnable measure of whether the repository is getting better or
  drifting back.

If you are looking for a tool that decides whether a pull request may merge, this is the wrong tool. The
verification gate is the repository's own `check` verb; this audit is what tells you whether that verb is worth
trusting.

---

## Relationship to the Rest of the Toolchain

| Tool | Role |
|---|---|
| `codebase-agentic-readiness-framework` | The methodology. This audit implements Phase 1 of it. |
| `python-agentic-bootstrap` | Creates a *greenfield* project that is Phase-1-complete on commit #1. Also this audit's positive fixture. |
| `python-agentic-audit` (this) | Measures a *brownfield* project's distance from the same bar. |
| `codebase-memory-mcp` | The index both the audit probes and the agents query. |

Bootstrap and audit are two halves of one contract: **start ready**, or **measure the distance and close it**.

---

## Related Pages

- Next: [2. The Readiness Model](02-the-readiness-model.md)
- Deep-dives: [Glossary](../glossary.md) · [ADR Index](../README.md) · [Why These Checks](03-why-these-checks.md)
