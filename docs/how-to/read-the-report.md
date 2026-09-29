# How to Read the Report

> **Goal:** Turn an audit report into an ordered work queue without over-reading the score.
> **Audience:** CTOs, engineering leads, engineers
> **Status:** Live for the implemented packs (`AGT`, `EXEC`, `CMD`, `SEC`, `TOOL`, `CI`); the report shape below is what the tool emits today.

---

## Prerequisites

- [ ] A completed scan ([Run an audit](run-an-audit.md))
- [ ] Both outputs: the Markdown page for reading, the JSON for filtering

---

## Step-by-Step Instructions

### Step 1: Read the provenance block first

It tells you what the report is *about*: the target path, git SHA, whether the tree was dirty, the tool version,
and the framework revision whose rules were applied. A report against a dirty tree or the wrong revision is a
report about a different repository.

### Step 2: Read the blockers, and stop there

The Markdown report orders findings by severity first, then by the failing check's weight. Blockers are the only
section that requires action before onboarding an agent; degraders can be scheduled, cosmetics can be ignored
indefinitely.

| Severity | What to do |
|---|---|
| **BLOCKER** | Fix before any agent work. These are the findings that make agent output unverifiable or the repository unsafe to touch. |
| **DEGRADER** | Schedule. Each one costs accuracy or tokens on every task. |
| **COSMETIC** | Note and move on. |

### Step 3: Read the unattested list

Five properties are listed as unattested on every report, always: whether the index is *used*, whether baselines
are *adequate*, whether the suite is *trustworthy*, whether docs are *accurate*, whether the gate will be
*honoured*. These are the items a scan cannot settle, and they are printed so the score is never read as a
guarantee.

> [!IMPORTANT]
> Absence of a finding is not evidence of quality. A check that could not gather evidence is `UNKNOWN`, and
> `UNKNOWN` is never counted as a pass. If the report shows `UNKNOWN` items, treat them as open questions about
> the *tool's* coverage, not about the repository.

### Step 4: Read `PARTIAL` findings as ratios

A per-component check reports as `PARTIAL` with a ratio, because a monorepo where 3 of 7 components have
governance is not "passing" or "failing" — it is 43% done, and the ratio is the useful number.

### Step 5: Filter the JSON for work assignment

```bash
# Everything a specific team should look at
python3 -c "
import json
d = json.load(open('audit-report.json'))
for f in d['findings']:
    if f['severity'] == 'BLOCKER':
        print(f\"{f['check']:<8} {f['statement']}\")
        print(f\"         evidence: {f['evidence'][0]['path']}\")
"
```

---

## Verification

You have read the report correctly if you can answer, without opening the JSON: how many blockers exist, which
requirement each one maps to, and which properties the scan could not verify.

---

## Next

- [Hand findings to remediation](hand-findings-to-remediation.md)
