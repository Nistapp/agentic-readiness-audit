# python-agentic-audit

> **Status:** v1 complete — the `audit/` package runs end to end, and the `IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`, `TOOL`, `CI`, `TST`, `BASE`, `CON` and `HYG` packs are live. All 54 scoreable checks are implemented; only the blocked `CON-01` is not evaluated, and the informational `HYG` set is reported with no credit. The fixture matrix covers every check, and a freshly generated `python-agentic-bootstrap` scaffold fails no implemented check. The documentation in [`docs/`](docs/) remains the design of record.

`python-agentic-audit` scans an existing repository and reports what to improve so that **AI coding agents can
work in it effectively**. It is the brownfield half of the agentic-readiness toolchain: `python-agentic-bootstrap`
proves a new project *starts* ready; this audit measures how far an existing one is from the same bar.

**It reports; it does not gate.** A completed scan exits `0` whatever it finds. Regression detection is a ratchet
against an accepted baseline, so it is safe to introduce into a legacy repository on day one.

---

## Scope

| Scored | Reported, never scored | Never claimed |
|---|---|---|
| Phase 1 (Bootstrap) of the readiness framework — 54 scoreable checks (69 catalogued, 15 informational, blocked or emitter-only) | Phase 2–4 presence signals, repository hygiene | Whether the index is used, whether baselines are adequate, whether the suite is trustworthy, whether docs are accurate, whether the gate will be honoured |

Two axes are always reported separately: **phase** (which framework requirement — provenance) and **severity**
(blocker / degrader / cosmetic — the work queue).

---

## Non-Goals

- Not a gate, a linter, a security scanner, or a coverage tool.
- Not a code-quality score. Readiness and quality are different axes.
- Not an LLM: no model is called, so the same repository and flags produce the same report.
- Not a rewriter. It never modifies the target.

---

## Quick Start

```bash
# from a checkout of this repo — no install step, no dependencies
python3 -m audit <target> --format both --out ../audit-out/<name>

# add executed probes, explicitly and with a time budget
python3 -m audit <target> --run-gates --allow-probe check --allow-probe test --timeout 600

# what is implemented right now, and whether every rule still traces to the framework
python3 -m audit --list-checks
python3 -m audit --verify-rules --framework ~/Projects/Nistapp-agentic-frameworks/codebase-agentic-readiness-framework

# tests, and the single-file distributable
python3 -m unittest discover -s tests
python3 tools/build.py && ./dist/audit.pyz <target>
```

Full walkthrough: [How to run an audit](docs/how-to/run-an-audit.md).

---

## Layout

```
audit/                     the tool: standard library only, no install step
  __main__.py              main(argv=None) -> int   ·  python3 -m audit <target>
  cli.py                   argument surface and exit codes
  target.py                target guard + provenance capture
  scan.py                  bounded traversal, classification, bounded reads
  stack.py                 ecosystem / CI / test-runner detection
  components.py            declared components (depth 1) + candidate components
  probes.py                Tier-C runner: allow-list, timeouts, capture-time redaction
  evaluate.py              verdicts, scoring, exit codes, the unattested list
  findings.py              finding model, severity ordering, sentence form
  rules/
    variants.py            THE instruction-variant table (one data structure, in code)
    registry.py            check catalogue + framework anchors + ruleset hash
    checks/                one module per check family; idx.py, agt.py, execution.py, cmd.py, sec.py, doc.py, nav.py, tool.py, ci.py, tst.py, base.py, con.py and hyg.py are implemented
  report/                  JSON and Markdown writers
tools/build.py             python3 tools/build.py  ->  dist/audit.pyz
tests/                     stdlib unittest suite + fixtures
docs/                      the design of record, and the source of the doc-link checker
```

Running the tool needs nothing installed. Building the single-file distributable needs nothing but Python, and
produces an archive that runs anywhere Python does — see
[ADR-0005](docs/architecture/adrs/0005-module-layout-and-zipapp-distribution.md).

---

## Documentation

Start at the **[architecture index and doc router](docs/architecture/README.md)**.

| Track | Entry point | Audience |
|---|---|---|
| Purpose & non-goals | [1. Purpose & Non-Goals](docs/architecture/user-overview/01-purpose-and-non-goals.md) | Evaluators, CTOs, clients |
| The readiness model | [2. The Readiness Model](docs/architecture/user-overview/02-the-readiness-model.md) | Anyone reading a report |
| Why these checks | [3. Why These Checks](docs/architecture/user-overview/03-why-these-checks.md) | Anyone arguing with a finding |
| Scan engine & tiering | [Contributor Deep Dive 1](docs/architecture/contributor-deep-dive/01-scan-engine-and-tiering.md) | Engineers |
| Check catalogue | [Contributor Deep Dive 2](docs/architecture/contributor-deep-dive/02-check-catalogue.md) | Engineers |
| Decisions of record | [ADR index](docs/architecture/README.md#adr-index) | Everyone |
| Authoring rules | [STYLE_GUIDE.md](docs/STYLE_GUIDE.md) | Writers, documentation agents |

All documentation follows [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md), which is canonical.

---

## Dependencies

| Dependency | Role |
|---|---|
| Python 3.11+ | Runtime. Standard library only — nothing to install, so the audit runs before the target's toolchain exists. |
| `codebase-agentic-readiness-framework` | The methodology. Rule packs cite its Phase 1 anchors; where the two disagree, the framework wins. |
| `codebase-memory-mcp` | The index the audit probes and the agents query. |

---

## Roadmap

| Version | Scope |
|---|---|
| v1 | Python, deterministic, Phase-1 scoring, tiers A–C, JSON + Markdown reports, baseline ratchet, self-verification fixtures. **Current state:** all packs live — `IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`, `TOOL`, `CI`, `TST`, `BASE`, `CON` and the informational `HYG` set (54 of 54 scoreable checks, plus 13 informational reported and never scored; only the blocked `CON-01` is not evaluated) |
| v2 | TypeScript npm package with the same contract, matching the scaffolder's distribution path |
| v3 | `--narrate` (prose only, never verdicts), Phase 2–4 rule packs with real depth, non-JS/TS ecosystem packs |

---

## License

Not yet chosen — no license field is claimed until one is.
