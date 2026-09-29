# AGENTS.md

> **Adapted from:** the greenfield-bootstrap `AGENTS.md` template v1.1.0, retargeted from npm/TypeScript
> to this stdlib-only Python project.
> **Purpose:** This file governs how AI coding agents (Antigravity, Claude Code, Gemini CLI, opencode, etc.)
> work inside this repository.
> **Action:** Treat it as authoritative for agent behaviour here. Changes to it are code changes — review
> them the same way.

---

## 1. Project Overview

`python-agentic-audit` is a **read-only agentic-readiness scanner for existing repositories**. It is the
brownfield half of the agentic-readiness toolchain: `python-agentic-bootstrap` proves a new project *starts*
ready; this audit measures how far an existing repository is from the same bar and reports an ordered backlog.

It is written in **Python 3.11+ using the standard library only**, with **no install step** — a fresh clone
runs `python3 -m audit <target>` immediately. That constraint is not stylistic: the audit must run before the
target's toolchain exists and on a machine where nothing is installed.

**Key Design Invariants:**

- **Reports, does not gate.** A completed scan exits `0` whatever it finds; exit `2` only with `--fail-on`
  or a `--baseline` regression (ADR-0001).
- **Read-only on the target.** Output goes to `--out`; the writer refuses when the CWD is inside the target
  (ADR-0002).
- **Deterministic.** No LLM, no network by default. Same target + flags + ruleset ⇒ identical report,
  differing only in the provenance timestamp (ADR-0004).
- **`UNKNOWN` and `ATTEST` earn no credit** and are never rendered as passes. Absence of evidence is not a
  pass.
- **Standard library only.** No third-party import may ever be added to `audit/` or `tools/`.
- **Zero specification drift.** Code and the architecture specs stay synchronized in the same change set.
- **Empirical grounding.** Never document an aspirational feature as an existing fact; `UNKNOWN` is stated as
  `UNKNOWN`.

---

## 2. Architectural Boundaries

Agents MUST respect the following structural rules.

### 2.1 Pipeline modules (`audit/`)

| Module | Responsibility |
|---|---|
| `audit/__main__.py` | Process entry point: `main(argv=None) -> int`, callable with no arguments (zipapp shim + future console script). |
| `audit/cli.py` | Argument surface and exit codes only — no scan logic. |
| `audit/target.py` | Target guard and git provenance capture. |
| `audit/scan.py` | Bounded traversal, file classification, bounded content reads, grep. |
| `audit/stack.py` | Ecosystem / package manager / CI / test-framework / hook detection. |
| `audit/components.py` | Declared components (depth 1) plus candidate components. |
| `audit/probes.py` | Tier-C runner: allow-list, timeouts, **capture-time** redaction. |
| `audit/evaluate.py` | Verdicts, scoring, exit codes, the unattested list, provenance. |
| `audit/findings.py` | Severity ordering, the finding model, the "An agent cannot X because Y" sentence form. |
| `audit/rules/registry.py` | The check catalogue, framework anchors, `ruleset_hash()`. |
| `audit/rules/variants.py` | **The** instruction-variant table — one data structure, in code. |
| `audit/rules/checks/` | One module per check pack; each exposes an `IMPLEMENTATIONS` dict. |
| `audit/report/` | JSON and Markdown writers. |
| `tools/build.py` | Zipapp builder producing `dist/audit.pyz`. |
| `tests/` | Stdlib `unittest` suite and fixtures. |

### 2.2 Hard boundary rules

1. **Core logic never writes to the target.** Every artifact goes to `--out`, which must be outside the
   target. The writer refuses to drop a report inside the repository it audits.
2. **Tier-C probes are opt-in by construction.** A probe runs only when `--run-gates` is set **and** the
   verb is named in `--allow-probe`. There is no default probe.
3. **No third-party dependency.** `audit/` and `tools/` import from the standard library only. A data file
   cannot ship inside a `.pyz` via `Path(__file__)` — that is why `variants.py` is code, and it stays code.
4. **The framework is normative.** Where this tool's docs and
   `codebase-agentic-readiness-framework` disagree, **the framework wins and this tool has a defect**.
   Resolve it here, never by weakening the tool.
5. **Findings carry evidence.** No verdict without the evidence that produced it. `UNKNOWN` is used when
   evidence cannot be gathered — it is never upgraded to `PASS` for convenience.

---

## 3. Tech Stack & Tooling

| Concern | Tool | Rule |
|---|---|---|
| Language | Python 3.11+ | Standard library only; `from __future__ import annotations`. |
| Runtime | `python3` | No install step: `python3 -m audit <target>` from a fresh clone. |
| Tests | stdlib `unittest` | `python3 -m unittest discover -s tests`. No pytest dependency. |
| Build | `zipapp` | `python3 tools/build.py` → `dist/audit.pyz`; source tree is the artifact of record. |
| Index | `codebase-memory-mcp` | Mandatory for structural queries (see §4). |
| Docs | Diátaxis + `docs/STYLE_GUIDE.md` | The style guide is canonical (see §8). |

### 3.1 Standardized command surface

The framework's **six verbs** are the contract; the runner is a local choice. This repository has **not yet
wired a runner** (`Makefile` / `Taskfile` / package scripts), and it is stdlib-only — so the formatter,
linter, type-checker and security verbs have **no implementation here yet**. They are listed because the
contract names them, and each is marked with its current status. Do not invent an ad-hoc command in place of
a missing verb; say the verb is not yet wired.

| Verb | Status in this repository |
|---|---|
| `format` | Not yet wired — stdlib-only, no formatter dependency. |
| `format:check` | Not yet wired. |
| `lint` | Not yet wired. |
| `typecheck` | Not yet wired — no static type-checker dependency. |
| `test` | **Wired:** `python3 -m unittest discover -s tests`. |
| `check` | Not yet wired as one verb; until a runner exists, compose `test` + `--verify-rules` + build. |
| `security` | Not yet wired — stdlib-only, no dependency-CVE tooling. |

Commands that **do** work today, and are the sanctioned way to verify work here:

```bash
python3 -m unittest discover -s tests                                   # the test suite
python3 -m audit --list-checks                                          # catalogue: implemented vs planned
python3 -m audit --verify-rules --framework <path-to-framework>         # every anchor must resolve
python3 tools/build.py && ./dist/audit.pyz --list-checks                # the single-file distributable
```

> [!IMPORTANT]
> Once a runner is added, CI MUST invoke the identical script names a human or agent runs locally. A gate
> with no local equivalent cannot be honoured by an agent.

---

## 4. Codebase-Memory-MCP Integration

`codebase-memory-mcp` is mandatory. Use it proactively before reading full files.

**Priority Order:**

1. `get_architecture` — understand the structure.
2. `search_graph` / `query_graph` — find symbols and relationships.
3. `trace_path` — understand call chains.
4. `get_code_snippet` — read specific function bodies.
5. `detect_changes` — check the blast radius and index freshness after edits.

**File Reading Policy:**

- Prefer querying by symbol name over opening whole files.
- **`artefacts/` is prohibited.** It holds transient, unverified scratch documents. Agents MUST NOT crawl,
  glob, grep, or read files there, and MUST NOT treat its contents as architectural source of truth. Access
  is permitted only when a human passes a specific file path in their prompt.
- The index excludes `artefacts/`, `dist/` and `__pycache__/` by design; that is not a coverage failure.

---

## 5. Coding Standards

- **Types:** annotate public functions and return types (PEP 484 / PEP 604). Use `from __future__ import
  annotations`. No untyped pass-through.
- **No third-party imports** anywhere in `audit/` or `tools/`. If a capability needs a library, it does not
  ship in v1.
- **Determinism is a requirement, not a nicety:** sort traversal and check evaluation; never use wall-clock
  time inside a verdict; derive finding ids from `check id + path`, never from a counter.
- **Scope-contract docstrings:** modules that define a pipeline stage state their responsibility and failure
  behaviour in the module docstring, matching `docs/architecture/contributor-deep-dive/01-scan-engine-and-tiering.md`.
- **Errors:** raise `AuditUsageError` for bad input; the CLI converts it to exit code `1` with a message,
  never a traceback.
- **Naming:** files `snake_case.py`; private helpers prefixed `_`; check ids keep the catalogue's
  `PACK-NN` form.
- **Comments:** do not add comments unless they explain non-obvious *why*, not *what*.

---

## 6. Testing Standards

- **Framework:** stdlib `unittest` (import from `unittest`, not `pytest`).
- **Location:** `tests/`, mirroring the source layout; fixtures under `tests/fixtures/`.
- **Fixtures:** one directory per check id, each a minimal repository that fails **exactly one** check.
  The catalogue's § Adding a Check makes this a merge requirement: **no fixture, no check.**
- **Positive fixture:** a freshly generated `python-agentic-bootstrap` scaffold, **generated in the test run,
  never vendored**. If a scaffold ever fails this audit, one of the two tools is wrong — that is a defect to
  fix, not a false positive to tune away.
- **Load-bearing tests:** determinism (two full reports differ only by timestamp) and the zipapp
  entry-point contract (`main` callable with no arguments) must not be weakened.
- **Pass rate:** 100% required. Never `.skip` or comment out a failing test; never relax an assertion to get
  green.
- **Gate:** run the test command in §3.1 before proposing a change.

---

## 7. Git Conventions

> [!NOTE]
> This repository is **not yet a git repository**. `git init` happens only on KC's explicit instruction
> (handoff §6.5). The first commit is the doc set + code + tests together, with `.gitignore` covering
> `dist/` and `artefacts/`.

- **Branching (intended):** `main` = production, `dev` = active development, feature branches
  `feat/<slug>`, `fix/<slug>`, `refactor/<slug>`. PRs to `main` originate from `dev`.
- **Commits (Conventional Commits):** `<type>(<scope>): <description>` with types `feat`, `fix`, `refactor`,
  `test`, `docs`, `chore`, `ci`, `perf`, `revert`.
- **Agent commits:** `chore(ai): pass-[N] - <description>`.
- **Never commit unless explicitly asked.** Do not update git config, force-push, or create empty commits.

---

## 8. Documentation Contract

- **Single source of truth:** `docs/` is the sole canonical home for permanent knowledge. `artefacts/` is
  transient scratch (see §4).
- **Canonical rules:** `docs/STYLE_GUIDE.md` holds the authoring rules. Link to it; do **not** restate its
  rules elsewhere, because restated rules drift.
- **Doc router:** `docs/architecture/README.md` is the entry point and the ADR index.
- **Categories (Diátaxis):** tutorial, how-to, reference, explanation; architecture material lives under
  `docs/architecture/`.
- **ADRs:** `docs/architecture/adrs/NNNN-short-title.md`, created from
  `docs/templates/adr-template.md`, indexed in `docs/architecture/README.md`. Revise in place — there is no
  `Superseded` or `Deprecated` status, no tombstones, and a retired sequence number is never reused.
- **Definition of done:** when a change alters a public interface, observable behaviour, architecture, a
  check's semantics, or an ADR, update the affected documentation pages, their source line anchors, and the
  ADR index **in the same change set**. Pure internal refactors with no documentation impact are exempt.
- **No restating the framework:** `codebase-agentic-readiness-framework` is the external source of truth.
  Cite it by phase and section and link to it; never copy its prose into `docs/`.
- **Empirical grounding:** never document a check as implemented while it exists only in the catalogue. The
  catalogue is the design; the implementation status column is the fact.

---

## 9. Environment & Secrets

- **Secrets never enter a report.** Redaction happens at capture time in `audit/probes.py`, not at render
  time. Never move redaction later in the pipeline.
- Secrets belong in `.env` (never committed); templates belong in `.env.example`.
- Never log, echo, or print the contents of `.env` or any sensitive variable.
- **No network by default.** Probes that need one are excluded unless explicitly permitted with
  `--allow-probe`.
- No real credential-shaped values in fixtures or test data.

---

## 10. Explicit "Do Not Do" Rules

1. ❌ **Do not** write, or cause a write, anywhere inside the scanned target. Output goes to `--out`.
2. ❌ **Do not** run a Tier-C probe without `--run-gates` **and** an explicit `--allow-probe` verb.
3. ❌ **Do not** add a third-party import to `audit/` or `tools/`. Standard library only.
4. ❌ **Do not** treat `UNKNOWN` or `ATTEST` as a pass, in code or in prose.
5. ❌ **Do not** call an LLM or make a network request by default. Determinism depends on this.
6. ❌ **Do not** move secret redaction out of capture time.
7. ❌ **Do not** read, grep, or glob `artefacts/` unless a human passes an explicit file path.
8. ❌ **Do not** document aspirational features as existing facts. Tag what is missing as `UNKNOWN`.
9. ❌ **Do not** restate `docs/STYLE_GUIDE.md` or the readiness framework — link to them.
10. ❌ **Do not** document a check as implemented while it is only in the catalogue.
11. ❌ **Do not** merge a check without its one-defect fixture (no fixture, no check).
12. ❌ **Do not** reuse a retired ADR number, or leave a `Superseded` / `Deprecated` tombstone.
13. ❌ **Do not** weaken, `.skip`, or comment out a failing test to get green.
14. ❌ **Do not** commit, `git init`, or push unless KC explicitly asks.
15. ❌ **Do not** verify work with an ad-hoc command; use the sanctioned surface in §3.1.
