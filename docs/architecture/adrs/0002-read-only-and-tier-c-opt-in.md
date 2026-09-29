# 0002. Read-Only by Default; Tier-C Probes Are Opt-In

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

An audit runs inside a repository it does not own, usually one the operator has never run before. Three
properties of that situation drive this decision.

First, running a repository's own commands executes that repository's code with the operator's privileges. A
`test` script is arbitrary code; a `postinstall` hook is arbitrary code. "Just run their gates to see if they
pass" is a supply-chain decision, and it is not one a scanning tool may make silently on the operator's behalf.

Second, an audit on a legacy repository is often the first thing anyone has run against it from outside. Anything
it mutates — a lockfile, a build cache, a coverage directory — contaminates the evidence it was gathered to
produce, and the target may be a production checkout.

Third, the audit's own value depends on being safe to run anywhere, including in CI on a pull request from a fork
and on a client's machine under change control. A tool that must be trusted before it can be run has already lost.

---

## Decision

**Static scan by default; execution only by explicit request.**

1. **Never write to the target.** Output goes to stdout or to an `--out` path, outside the target by default, and
   never overwritten without `--force`.
2. **Never install anything** — no package manager, no wrapper bootstrap, no dependency download.
3. **No network requests by default.** Checks that need one (dependency CVE sources) are excluded unless
   explicitly permitted.
4. **Tier-C probes are off** unless `--run-gates` is passed, and each probe verb must be named in an
   `--allow-probe` allow-list. Only verbs the rule pack declares read-only are eligible.
5. **Per-probe timeout**, and the timeout itself is recorded as evidence rather than swallowed.
6. **Redaction at capture time**, not at render time: probe output is filtered for credential shapes before it
   can reach any structure the report writer touches.
7. **Sandboxing is the operator's responsibility**, and the docs say so plainly — the audit will not pretend to
   sandbox a target it cannot containerise without breaking rule 2.

Implemented by the probe runner in `audit/probes.py` (`ProbeSession.run`) and the output guard in `audit/report/__init__.py`;
see
[Scan Engine & Tiering](../contributor-deep-dive/01-scan-engine-and-tiering.md) § 6.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Run the target's gates always, for maximum signal | Executes untrusted code on open. Silent code execution is not a scan; it is a remote-execution feature with a report attached. |
| Never run probes at all | Loses the highest-signal check in the catalogue — whether the verification loop actually works today (`TST-02`) — which is close to the whole point of the tool. |
| Containerise the target automatically to make probes safe | Needs a container runtime the audit cannot assume and must not install, so it would break the "runs anywhere with Python" property. Kept as a documented operator step. |
| Install dependencies so probes can run | Mutates the target and defeats the reason the tool is stdlib-only: it must run *before* the project's toolchain exists. |
| Redact secrets when rendering the report | Captured output passes through scoring and the JSON model first; rendering-time redaction leaks into structures the renderer does not own. |

---

## Consequences

### Positive

* The audit is safe to point at any repository, including one nobody trusts yet.
* A first scan is genuinely zero-impact: no dirty working tree, no lockfile churn, no review noise.
* Probe results in a report are attributable to an explicit operator decision, which makes them defensible in a
  client engagement.

### Negative / Trade-offs

* Default scans are weaker than they could be: `TST-02` and `IDX-03` stay `UNKNOWN` until probes are enabled.
* The operator must make two decisions (`--run-gates`, which verbs) rather than one, and the tool must explain
  why in its own output rather than assuming the docs were read.
* Redaction at capture time is more code than a post-processing pass, and a redaction bug is a security defect
  rather than a cosmetic one.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
