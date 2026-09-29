# 0001. The Audit Reports; It Does Not Gate

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

The tool exists to tell a team what to improve so that AI coding agents can work effectively in an existing
repository. The immediate temptation is to make it a gate: fail the build when Phase 1 is incomplete. That
temptation is wrong for a brownfield tool, and it is wrong for a specific, observable reason.

A legacy repository is under-prepared, not broken. Every Phase-1 gap it has was earned over years of shipping
software, and none of them can be closed in a single pull request. A checker that fails on day one does not
produce a fix; it produces a disabled checker. The framework's own risk register already names the failure mode
that follows — teams learn to treat gates as obstacles rather than as safety nets, and constraint erosion
follows.

There is a second consideration. The audit cannot verify several Phase-1 properties at all: whether the index is
used, whether a baseline is adequate, whether a suite is trustworthy. A verdict that aggregates verified and
unverifiable properties into one pass/fail number would manufacture exactly the false confidence the framework
warns about.

---

## Decision

The audit **reports and never gates**:

1. A completed scan exits `0` regardless of what it found.
2. `--fail-on <severity>` exists but is unset by default, and is documented as the wrong default for brownfield
   adoption.
3. Regression detection is a **ratchet**: `--baseline <report.json>` exits `2` only when a finding is present
   that was absent from an accepted baseline. A repository that was never ready is not failing anything; a
   repository that stopped being ready is.
4. **Phase and severity are separate axes.** Phase is provenance (which framework requirement); severity is the
   work queue (blocker / degrader / cosmetic).
5. Every report prints an **unattested list** and never counts `UNKNOWN` as a pass, so the score cannot be read
   as a guarantee.
6. Nothing outside Phase 1 enters the score. Phases 2–4 signals and repository hygiene are reported and left
   numberless.

Implemented by the exit-code and scoring stages in `audit/evaluate.py` (`AuditResult.exit_code`); see
[The Readiness Model](../user-overview/02-the-readiness-model.md) § 8.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Fail the build on any Phase-1 gap (a true gate) | Unfixable in one change set; the predictable outcome is a disabled check, which is worse than no check. |
| No exit-code signalling at all — report only, always `0` | Removes the ratchet, and with it the only reason to re-run the audit after the first engagement. Debt would regress invisibly. |
| Fail on a score threshold (e.g. "below 80% fails") | A weighted score hides *which* property regressed. A diff of findings says what changed; a threshold says only that something did. |
| A pull-request comment bot only, no machine-readable output | Same report, but it withholds the JSON that the remediation pass consumes and makes regression diffing impossible. |
| Count `UNKNOWN` as a pass so the score stays clean | Converts missing evidence into apparent quality — the precise defect the framework calls false confidence (R8). |

---

## Consequences

### Positive

* The tool can be introduced in week one of an engagement without a political fight over a red build.
* The ratchet makes re-running it meaningful, which makes readiness a trend rather than a snapshot.
* The score is defensible in a client conversation: every point of it carries the evidence that produced it.

### Negative / Trade-offs

* Two-mode operation (report mode, ratchet mode) is more surface than a single gate, and the CI wiring is a
  deliberate second step rather than a one-line addition.
* A team that wants enforcement must accept the audit as a second, softer signal alongside its real gates — some
  will ask for the gate anyway, and the correct answer is the repository's own `check` verb, not this tool.
* Severity is a judgement encoded in the rule packs; a mis-severity finding is a defect that only human review
  catches.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
