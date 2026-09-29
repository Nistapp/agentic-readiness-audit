# 0004. No LLM Calls in v1

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

Several checks in the catalogue are semantic at heart. Is `AGENTS.md` *accurate* about this codebase? Do the
documented commands describe what the team actually does? Is the test suite *trustworthy*, or does it assert
nothing? A model could offer an opinion on each of these in seconds, and the tool would look far more capable.

That appearance is the problem. An audit's output has to survive an argument. When a finding reads "an agent
cannot install reproducibly because no lockfile is committed", the reader can open the manifest and settle it.
When a finding reads "the governance file appears misleading", the reader has no way to test it, and neither does
the tool — the verdict is an opinion with the authority of a scanner behind it.

The framework's own risk register records both directions of this failure: hallucinated claims that propagate as
facts, and false confidence in automated gates. A tool whose entire purpose is honesty about readiness must not
manufacture either.

There is also a practical consideration. Reports are diffed against a baseline to detect regression. A report
whose content varies between runs cannot be diffed, regression-tested, or attributed to a revision of the rules.

---

## Decision

**Deterministic, standard-library only, no model in v1.**

1. No LLM calls, no network calls by default, no embedding of a model client.
2. Every check's evidence rule must be **falsifiable by inspection** — a reviewer applies it to a fixture and
   reaches the same verdict.
3. Semantic properties that cannot be computed become explicit `ATTEST` entries: listed, named, and left to a
   human. They are never guessed at and never scored.
4. Identical target, flags, and ruleset produce an identical report, differing only in the provenance timestamp.
5. Same constraint as the greenfield scaffolder, for the same reason: the tool must run before the target's
   toolchain exists, on a machine with nothing installed.

Prose generation — a `--narrate` mode that rewrites findings as readable paragraphs — is a **roadmap item**, and
would be restricted to prose. Verdicts are never model-produced. See
[Scan Engine & Tiering](../contributor-deep-dive/01-scan-engine-and-tiering.md) § 7.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| LLM-assist for the semantic checks (`AGT-03`, `AGT-06`, `TST-02`) | Non-reproducible reports cannot be diffed or regression-tested, and an opinion with a scanner's authority is worse than an honest `ATTEST`. |
| LLM for remediation prose only, verdicts still deterministic | Defensible, but v1 scope creep; held as `--narrate` on the roadmap rather than built now. |
| Heuristics that *approximate* the semantic checks | A pattern that guesses "the governance file is accurate" is a fabricated verdict with extra steps. |
| Embed a local model to keep it offline | Still non-deterministic across machines and versions, and breaks the "runs anywhere with Python" property. |
| Ask the model to *rank* findings by severity | Severity is a rule-pack attribute, reviewable and diffable. A model ranking would change between runs and make the work queue unstable. |

---

## Consequences

### Positive

* Every finding is arguable, and every score is traceable to evidence a reader can open.
* Reports are byte-stable and therefore diffable — which is what makes the ratchet in [ADR-0001](0001-report-not-a-gate.md) possible.
* The tool has no API key, no cost, no rate limit, and no data leaving the machine.

### Negative / Trade-offs

* The catalogue is weaker than it could be on genuinely semantic questions, and the `ATTEST` list will feel like
  a gap to users who expected the tool to answer them.
* Some checks are proxied by structural signals — doc-comment coverage instead of doc quality — and those proxies
  must be labelled as signals rather than verdicts.
* The `--narrate` roadmap item will need re-opening this ADR's boundary between prose and verdict when it lands.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
