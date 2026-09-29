# 0005. Module Layout and Zipapp Distribution

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

The audit began as a single-file design, inheriting `python-agentic-bootstrap`'s `DESIGN.md` rule verbatim: *"a
single Python file, standard library only"*. That rule was justified for the scaffolder on two grounds — the whole
job is directory creation plus string substitution, and a single file needs no build step, so the tool runs before
the target's toolchain exists.

The second ground is a real requirement and does not change here. The first does not survive contact with this
tool: the audit's own design is ~50 checks, four pipeline stages of traversal and classification, per-ecosystem
component detection, a ~45-entry instruction-variant table, a probe runner and two report writers — an order of
magnitude more code than the scaffolder. One file of that size is hard to navigate, impossible to unit-test by
stage, and produces tracebacks that name a single line number in a single file for every failure.

The question raised was whether the code can be split into modules and then *compiled* into a single executable,
as in C. Python's answer is different in kind: a module tree can be packed into one **archive** that runs anywhere
Python runs, but it cannot be **compiled** into a machine-code binary without a C toolchain or bundling an
interpreter — both of which cost the property that motivates the rule in the first place.

---

## Decision

**The package tree is the source of truth; a zipapp is the distributable.**

1. **Package layout**: `audit/` at the repository root, one module per pipeline stage, one module per check family
   under `audit/rules/checks/`, report writers under `audit/report/`.
2. **No install step, ever, to run the tool**: `python3 -m audit <target>` works from a fresh clone with no
   virtualenv, no `pip install`, no `PYTHONPATH`. This is why there is no `src/` layout. Nothing outside the
   standard library is imported.
3. **One artifact for distribution**: `python3 tools/build.py` produces `dist/audit.pyz` using the standard
   library's `zipapp`. It runs as `./dist/audit.pyz <target>`, on any machine with Python 3.9+, with no
   dependencies. `dist/` is gitignored — a zip is not reviewable in a diff and must never become a second source
   of truth.
4. **Entry-point contract**: `audit.__main__.main(argv: list[str] | None = None) -> int`. The zipapp-generated
   shim and a future `console_scripts` entry point both call `main()` with **no arguments**; passing argv is the
   test path. One function serves all three callers.
5. **Tables stay in code, not in data files.** `audit/rules/variants.py` is a Python data structure rather than
   JSON or YAML. A `.pyz` is not a filesystem: `Path(__file__).parent` does not exist inside it, and a shipped
   data file would have to be read through `importlib.resources`. Keeping the variant table as code removes that
   class of bug and keeps the table greppable.
6. **Determinism is preserved** by hashing the *content* of the catalogue and the variant table (`ruleset_hash`),
   not by hashing files or their paths, so the report is identical whether produced from the tree or the archive.
7. **The scaffolder is deliberately left alone.** `bootstrap.py` stays a single file: it is ~518 lines, verified,
   and shipping it a second convention would be churn without benefit. The shared constraint between the two
   tools is *"standard library only, no build step to run"* — not *"one file"*.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep one large `audit.py` | Inherited rule, but its justification (a small script) does not hold at 10× the size. Cost is permanent: no per-stage tests, unrunnable tracebacks, painful review. |
| PyInstaller / cx_Freeze | Produces a per-OS binary that bundles an interpreter (10–30 MB), needs third-party tooling at build time, and trips antivirus heuristics. Breaks "runs anywhere with Python", which is the reason the tool ships as a script. |
| Nuitka (the literal C analogy) | Compiles to a per-OS, per-arch binary and needs a C toolchain plus slow builds. Same objection, more machinery. An audit must run on a laptop, a CI runner and a client's machine without a build matrix. |
| shiv / pex | Single-file executables, but third-party and only earn their keep by resolving dependencies. This project has none, so they add a dependency to solve a problem it does not have. |
| A build step that concatenates modules into one `.py` | Fragile (import ordering, name collisions, `__main__` handling), loses real tracebacks, and is a bespoke build system to maintain. |
| `src/` layout with `pip install -e .` | Requires an install step before the tool can run at all, which contradicts the constraint that the audit must work before the target's toolchain exists. |
| A `pyproject.toml` and PyPI packaging in v1 | Adds setuptools to a tool whose distinguishing property is having no dependencies. Distribution is roadmap v2's TypeScript npm package; v1 ships an archive attached to a release. |
| Commit `dist/audit.pyz` to the repository | An unreviewable binary in git, and a second source of truth that will silently disagree with the code. |

---

## Consequences

### Positive

* Module boundaries match failure domains: a failing check is a file, a broken family is a module, and
  `--list-checks` reads the registry rather than a hand-maintained list.
* Test fixtures become mechanical — one deliberately broken repository per check — because checks are individually
  importable and callable.
* The single-file artifact still exists for the consumer who wants it, without a build matrix.
* The ruleset hash covers the variant table, so a rotted table (a rebranded harness, a renamed rule directory) is
  visible in provenance rather than inferred from a strange verdict.

### Negative / Trade-offs

* Distribution now has a build step, though running does not. Two entry paths must both stay tested —
  `python3 -m audit` and `./dist/audit.pyz`; the test suite builds the archive and runs it.
* A `.pyz` cannot be read with `Path(__file__)`, so any future data file must go through `importlib.resources`.
  Considered acceptable, and the reason tables stay in code.
* The package name `audit` is generic; a consumer importing it must be aware of the shadowing risk if they ship
  their own `audit` module. The command interface is the supported surface, not the import path.
* Two conventions now exist across the two sibling tools. This is a deliberate, recorded divergence, not drift:
  the shared rule is the constraint that matters and the file-count rule was never the point.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
