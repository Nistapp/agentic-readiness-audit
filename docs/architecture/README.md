# Architecture Documentation

> **Status:** v1 complete — the `audit/` package runs, and every pack (`IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`, `TOOL`, `CI`, `TST`, `BASE`, `CON` and the informational `HYG` set) is live. All 54 scoreable checks are implemented; only the blocked `CON-01` is not evaluated, and Tier-C probe checks report `UNKNOWN` unless probes are permitted. Pages below describe the design of record and the current implementation state. See [`docs/STYLE_GUIDE.md`](../STYLE_GUIDE.md) § 1.3 (Empirical Grounding).

## ADR Index

| # | Title | Status | Date |
|---|---|---|---|
| [0001](adrs/0001-report-not-a-gate.md) | The Audit Reports; It Does Not Gate | Accepted | 2026-09-28 |
| [0002](adrs/0002-read-only-and-tier-c-opt-in.md) | Read-Only by Default; Tier-C Probes Are Opt-In | Accepted | 2026-09-28 |
| [0003](adrs/0003-component-depth-declared-depth-1.md) | Component Depth: Declared Components, Depth 1 | Accepted | 2026-09-28 |
| [0004](adrs/0004-no-llm-in-v1.md) | No LLM Calls in v1 | Accepted | 2026-09-28 |
| [0005](adrs/0005-module-layout-and-zipapp-distribution.md) | Module Layout and Zipapp Distribution | Accepted | 2026-09-28 |
| [0006](adrs/0006-private-check-helpers-and-ignore-engine.md) | Private Check Helpers and the Ignore Engine | Accepted | 2026-09-28 |

## Key Documents

| Document | Purpose |
|---|---|
| [glossary.md](glossary.md) | Canonical definitions of audit and readiness terms |

## User Overview (Evaluator / Adopter Track)

| Page | Purpose | Status |
|---|---|---|
| [1. Purpose & Non-Goals](user-overview/01-purpose-and-non-goals.md) | What the audit is, what it refuses to be, and how to read its output | Published |
| [2. The Readiness Model](user-overview/02-the-readiness-model.md) | Phases, tiers, verdicts, severity, and what the score does and does not mean | Published |
| [3. Why These Checks](user-overview/03-why-these-checks.md) | The failure mode behind every check family | Published |

## Contributor Deep Dive

| Page | Purpose | Status |
|---|---|---|
| [1. Scan Engine & Tiering](contributor-deep-dive/01-scan-engine-and-tiering.md) | Pipeline stages, bounded traversal, stage contracts, determinism, self-verification | Published |
| [2. Check Catalogue](contributor-deep-dive/02-check-catalogue.md) | Every check: id, tier, phase, severity, evidence rule, implementation status | Published |

## How-To (Task Track)

| Page | Purpose | Status |
|---|---|---|
| [Run an audit](../how-to/run-an-audit.md) | Produce a report against a target repository | Published (design) |
| [Read the report](../how-to/read-the-report.md) | Turn a report into an ordered work queue | Published (design) |
| [Hand findings to remediation](../how-to/hand-findings-to-remediation.md) | Feed the report into the remediation pass | Published (design) |
| [Wire the ratchet into CI](../how-to/wire-the-ratchet-into-ci.md) | Fail only on regression, never on the first scan | Published (design) |

> [!TIP]
> When adding a new ADR, assign the next sequence number and add a row to the index table above before merging.

## Framework Dependencies

This tool implements Phase 1 of an external methodology. Its normative source is
`codebase-agentic-readiness-framework` (see the [Phased Approach](https://github.com/Nistapp/codebase-agentic-readiness-framework/blob/main/brownfield-legacy/Phased-Approach.md)).
Where the two disagree, the framework wins and this tool has a defect.

Local checkout: `~/Projects/Nistapp-agentic-frameworks/codebase-agentic-readiness-framework` (or any clone —
`--framework <path>` points the rule-anchor check at it).
