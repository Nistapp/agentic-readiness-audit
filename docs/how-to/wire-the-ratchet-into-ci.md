# How to Wire the Ratchet into CI

> **Goal:** Make the audit fail a build only when readiness regresses, never on the first scan of a legacy repository.
> **Audience:** Operators, engineers
> **Status:** The CLI ratchet is implemented (`--baseline` compares stable finding ids and exits `2` on a
> new one); wiring it into a CI job remains the operator's step. The command surface below is final.

---

## Prerequisites

- [ ] A committed baseline report from a scan you have reviewed and accepted
- [ ] CI that can check out the repository with full history access
- [ ] A decision about who is expected to act on a regression

---

## Why a ratchet and not a gate

A legacy repository is not failing anything by being unready. A red build on day one teaches a team to disable the
check, and a disabled check is worth less than no check at all. The ratchet inverts the question: not "are you
ready?" but "are you *less* ready than you were?" See [ADR-0001](../architecture/adrs/0001-report-not-a-gate.md).

---

## Step-by-Step Instructions

### Step 1: Commit an accepted baseline

```bash
python3 -m audit <target> --format json --out .audit/baseline.json
git add .audit/baseline.json && git commit -m "chore(audit): record agentic-readiness baseline"
```

The baseline records current findings. It is a statement of where you are, not of where you should be.

> [!NOTE]
> The ratchet compares **finding ids** — `check id + path` — not counts and not the score. A finding
> that is present now but absent from the baseline is a regression; moving or re-scoring existing
> findings is not. A baseline that cannot be read (missing, malformed) is itself reported as a
> regression rather than silently passing.

### Step 2: Add the CI job

```yaml
# .github/workflows/readiness-ratchet.yml
name: readiness-ratchet
on: [pull_request]
jobs:
  ratchet:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: python3 -m audit . --baseline .audit/baseline.json --format md --out .audit/current
      # exit 2 only on regression or on --fail-on threshold
```

> [!IMPORTANT]
> Do **not** add `--fail-on BLOCKER` here. That turns the audit into the gate it was designed not to be. The
> ratchet only fails when a finding appears that was absent from the accepted baseline.

### Step 3: Keep the baseline a reviewed artifact

Updating the baseline is a deliberate act, reviewed like any other infrastructure change. Two rules keep it
honest:

1. The baseline is only ever updated **downward** without review. Raising it — accepting a new finding as
   permanent — requires the same approval as weakening a test.
2. The baseline records provenance, so a baseline produced from a dirty tree or a different revision is
   detectable and must be rejected in review.

### Step 4: Run the ratchet periodically, not only on pull requests

Debt accumulates through merges that each look harmless. A scheduled weekly scan against the baseline catches
drift that no single pull request is responsible for.

```yaml
on:
  schedule: [{ cron: '0 3 * * 1' }]   # weekly, off-hours
```

---

## Verification

- A pull request that removes an `AGENTS.md` file or a lockfile fails the job with exit code `2`.
- A pull request with no readiness-relevant change passes with exit code `0`.
- The first run against a freshly committed baseline passes on an untouched repository.

```bash
python3 -m audit . --baseline .audit/baseline.json --format json --out /tmp/r.json; echo "exit=$?"
```

---

## Next

- [Hand findings to remediation](hand-findings-to-remediation.md)
- [The Readiness Model](../architecture/user-overview/02-the-readiness-model.md) — exit-code semantics
