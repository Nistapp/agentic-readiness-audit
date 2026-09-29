"""`CON` pack — constraints.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables ("Allow/deny lists").

Implemented here: `CON-02`, `CON-03`, and the `CON-04` emitter. `CON-01` is deliberately **not**
touched: the framework requires initial allow/deny lists as a Phase-1 deliverable but defines no
artifact name or schema, so the registry keeps it `blocked` with weight 0. This pack does not invent
an artifact contract, and it does not require one.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CON-02** — *test directories protected*. Test directories are located from the scan (a directory
  segment named ``test``/``tests``/``spec``/``specs``/``__tests__``) plus the filesystem. A
  dedicated constraint / allow-deny file — a documented name set of agent ignore files
  (``.cursorignore``, ``.aiderignore``, …) and explicit constraint files
  (``constraints.yaml``/``.json``, ``allowlist.txt``/``denylist.txt``) — that denies every test
  directory is a `PASS`; one that denies only some is `PARTIAL`; one that denies none is `FAIL`.
  With **no** constraint file the premise is absent, so the check never passes: ignore rules or a
  CI guard that protects the test
  directories is a `PARTIAL` (the mechanism is named), and nothing at all is `UNKNOWN`. Because
  CON-01 defines no artifact, this check is deliberately artifact-agnostic and never requires one.
* **CON-03** — *`artefacts/` excluded from the index and agent reads*. Candidate roots are the
  scratch spellings (``artefacts``, ``artifacts``) and the agent/tool state directories
  (``.codebase-memory``, ``.opencode``, ``.agentic-tdd``). A root that exists is covered when an
  ignore rule matches it; a **tracked** member of any root is a `FAIL`. When the roots are covered
  but git cannot report the tracked set, the untracked half is `UNKNOWN` — never inferred — while
  the rule-coverage half still evaluates (the same degradation `SEC-01`/`DOC-03` use).
* **CON-04** — the emitter, not a scored check. It returns a `CheckOutcome` like every other check,
  but it becomes `PASS` only when the operator asked for the draft with ``--emit-baseline``; without
  the flag it is `UNKNOWN`, and it is refused outright if the resolved output would land inside the
  target (ADR-0002). The draft is deterministic: fixed sections, sorted entries.

CON-04's output location is a contract choice not yet ratified by the framework (the framework
defines no artifact contract — see CON-01). The least-surprising option is taken: the same ``--out``
directory the report is written to, gated by the already-reserved ``--emit-baseline`` flag, with the
filename the remediation how-to already names (``docs/how-to/hand-findings-to-remediation.md``).
The emitter writes to a module-level target set by the CLI before the scan; nothing else reads it.

Deliberate limits, recorded rather than hidden. Ignore matching is the documented subset in
``audit.ignore`` (anchoring and ``**`` approximated). Constraint-file detection is a documented
**root-level** name set, not a schema; a constraint file under an unrecognised name, format or
depth is not seen and degrades to the ignore/CI fallback. Test-directory discovery is
directory-based; a suite laid out as loose ``*_test.py`` files with no test-named directory is not
seen and degrades to `UNKNOWN`. CI
protection is a textual heuristic (a workflow line that names a test directory together with a
deny/protect keyword). The emitter writes exactly one artifact (``constraints.draft.yaml``); the
other S12 remediation inputs are out of scope for this pack.
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import load_ignore_rules, tracked_files
from audit.scan import Inventory, Kind
from audit.target import Target

#: Constraint / allow-deny files, matched at the repository root. A documented name set, not a
#: schema: the framework names no artifact (CON-01), so the pack recognises the common spellings.
_CONSTRAINT_FILES: tuple[str, ...] = (
    ".agentignore", ".aiignore", ".cursorignore", ".aiderignore", ".rooignore",
    ".codeiumignore", ".copilotignore", ".geminiignore", ".claudeignore",
    ".codebaseignore", ".agenticignore",
    "constraints.yaml", "constraints.yml", "constraints.json",
    "constraints.draft.yaml",
    "allowlist.txt", "denylist.txt", "allowlist", "denylist",
)

#: Directory names that make a directory a test directory.
_TEST_DIR_NAMES: frozenset[str] = frozenset({"test", "tests", "spec", "specs", "__tests__"})

#: Scratch spellings and agent/tool state directories CON-03 requires to be ignored.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")
_STATE_ROOTS: tuple[str, ...] = (".codebase-memory", ".opencode", ".agentic-tdd")
_CON_ROOTS: tuple[str, ...] = _SCRATCH_ROOTS + _STATE_ROOTS

#: CI workflow locations read for a textual protect-guard, and the guard keyword.
_CI_FILES: tuple[str, ...] = (
    ".github/workflows/*.yml", ".github/workflows/*.yaml",
    ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml", ".circleci/config.yml",
)
_CI_PROTECT_RE = re.compile(r"(?i)\b(?:deny|denied|forbid|protect(?:ed|ion)?|read[- ]?only"
                            r"|no[- ]?edit|immutable)\b")

#: The draft artifact CON-04 writes, beside the report under ``--out``.
DRAFT_FILENAME = "constraints.draft.yaml"

# ---------------------------------------------------------------------------
# CON-04 emit target, configured once per process by the CLI before evaluation
# ---------------------------------------------------------------------------

_EMIT_TARGET: Path | None = None


def set_emit_target(out_path: Path | None) -> None:
    """Record where the emitter may write for this run; ``None`` disables it.

    Called by ``audit.cli`` before checks run, from the same ``--out`` resolution the report
    writer uses. It is the only module state in the pack, it is set once per process, and it is
    reset on every scan so a long-lived process cannot inherit a previous run's target.
    """
    global _EMIT_TARGET
    _EMIT_TARGET = out_path


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence],
             remediation: str) -> Finding:
    return Finding(check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
                   statement=statement(cannot, because), evidence=evidence,
                   remediation=remediation)


def _pattern_covers(rel: str, pattern: str) -> bool:
    """Whether one ignore/constraint pattern covers a directory path ``rel``.

    Mirrors the documented subset: a rule may name the directory itself (``artefacts``), its glob
    (``artefacts/*``) or its descendants. Anchoring and ``**`` are not interpreted.
    """
    p = pattern.strip().rstrip("/")
    if not p:
        return False
    core = p
    for suffix in ("/*", "/**"):
        if core.endswith(suffix):
            core = core[: -len(suffix)]
    core = core.rstrip("/")
    return (rel == core or fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, core)
            or fnmatch.fnmatch(rel, core + "/*") or fnmatch.fnmatch(rel, core + "/**"))


def _covered(rel: str, patterns: list[str]) -> bool:
    return any(_pattern_covers(rel, pattern) for pattern in patterns)


def _constraint_files(inventory: Inventory) -> list[str]:
    """Constraint/allow-deny files at the repository root.

    Root-level by design, mirroring ``audit.ignore.load_ignore_rules``: the framework names no
    location, the root is the least-surprising convention, and it keeps a nested fixture's ignore
    file from being read as a top-level governance artifact. A nested constraint file is not seen
    (a documented limit) and degrades to the ignore/CI fallback.
    """
    present = {entry.rel for entry in inventory.files}
    return sorted(name for name in _CONSTRAINT_FILES if name in present)


def _patterns_in(text: str) -> list[str]:
    """Best-effort patterns from a constraint file's lines (ignore-style or YAML list entries).

    Not a parser: comments are dropped, list/bullet markers and quotes are stripped, and a line
    is split on the YAML flow delimiters so ``deny: [tests, src]`` yields both entries.
    """
    patterns: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        for token in re.split(r"[,\[\]{}]", line):
            token = token.strip().strip("'\"").lstrip("-*").strip().strip("'\"")
            if token:
                patterns.append(token)
    return patterns


def _describe(roots: list[str], limit: int = 8) -> str:
    """A bounded, deterministic rendering of a root list for details and findings."""
    shown = ", ".join(root + "/" for root in roots[:limit])
    extra = len(roots) - limit
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def _test_roots(target: Target, inventory: Inventory) -> list[str]:
    """Every test directory: a filesystem root plus any directory segment named in the scan."""
    roots: set[str] = {name for name in _TEST_DIR_NAMES if (target.path / name).is_dir()}
    for entry in inventory.files:
        parts = entry.rel.split("/")
        for index, part in enumerate(parts[:-1]):
            if part in _TEST_DIR_NAMES:
                roots.add("/".join(parts[: index + 1]))
    return sorted(roots)


def _present_roots(target: Target, inventory: Inventory) -> list[str]:
    """The candidate scratch/state roots that exist, from the filesystem and from the scan."""
    present = {root for root in _CON_ROOTS if (target.path / root).is_dir()}
    present.update(entry.rel.split("/", 1)[0] for entry in inventory.files)
    return sorted(root for root in present if root in _CON_ROOTS)


# ===========================================================================
# CON-02 — test directories protected
# ===========================================================================

def _ci_protection(inventory: Inventory, test_roots: list[str]) -> list[str]:
    """CI workflow files with a line naming a test directory and a deny/protect keyword."""
    names = {root.rsplit("/", 1)[-1] for root in test_roots}
    hits: set[str] = set()
    for pattern in _CI_FILES:
        for rel in inventory.match(pattern):
            text = inventory.read(rel)
            if not text:
                continue
            for line in text.splitlines():
                if _CI_PROTECT_RE.search(line) and any(name in line for name in names):
                    hits.add(rel)
                    break
    return sorted(hits)


def check_con02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    test_roots = _test_roots(target, inventory)
    if not test_roots:
        return _unknown(spec, "no test directories detected, so there is nothing for a deny list "
                              "to protect")

    listed = _describe(test_roots)
    files = _constraint_files(inventory)

    if files:
        patterns: list[str] = []
        for rel in files:
            patterns.extend(_patterns_in(inventory.read(rel) or ""))
        covered = [root for root in test_roots if _covered(root, patterns)]
        uncovered = [root for root in test_roots if not _covered(root, patterns)]

        if not uncovered:
            return _outcome(spec, Verdict.PASS,
                            f"constraint file denies the test directories ({listed}): "
                            f"{', '.join(files)}")
        if covered:
            return _outcome(spec, Verdict.PARTIAL,
                            f"constraint file covers {_describe(covered)} but not "
                            f"{_describe(uncovered)}", [_finding(
                spec, "rely on the deny list to keep test directories out of an agent's reach",
                f"the constraint file(s) {', '.join(files)} do not deny {_describe(uncovered)}",
                Verdict.PARTIAL, [Evidence(rel) for rel in files],
                f"Add {_describe(uncovered)} to the constraint/deny list.")])
        return _outcome(spec, Verdict.FAIL,
                        f"a constraint file exists but denies none of the test directories "
                        f"({listed})", [_finding(
            spec, "trust that a failing test is not rewritten to pass",
            f"the constraint file(s) {', '.join(files)} do not deny any test directory",
            Verdict.FAIL, [Evidence(rel) for rel in files],
            f"Add {listed} to the constraint/deny list so test edits are bounded and reviewed.")])

    rules = load_ignore_rules(target.path)
    rule_patterns = [rule.pattern for rule in rules]
    ignored = [root for root in test_roots if _covered(root, rule_patterns)]
    ci = _ci_protection(inventory, test_roots)
    mechanisms: list[str] = []
    if ignored:
        sources = sorted({rule.source for rule in rules
                          if any(_pattern_covers(root, rule.pattern) for root in ignored)})
        mechanisms.append(f"ignore rules ({', '.join(sources)})")
    if ci:
        mechanisms.append(f"CI guard ({', '.join(ci)})")

    if mechanisms:
        return _outcome(spec, Verdict.PARTIAL,
                        f"no dedicated constraint file; test directories protected by "
                        f"{'; '.join(mechanisms)}", [_finding(
            spec, "point at one first-class deny list for test directories",
            f"no constraint file exists; protection is indirect ({'; '.join(mechanisms)})",
            Verdict.PARTIAL,
            [Evidence(ci[0] if ci else (rules[0].source if rules else "<repository>"))],
            "Add a constraint/allow-deny file that names the test directories explicitly.")])

    return _unknown(spec, f"no constraint file protects the test directories ({listed}), and no "
                          f"ignore rule or CI guard does either")


# ===========================================================================
# CON-03 — artefacts/ and agent state excluded from index and reads
# ===========================================================================

def check_con03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_files(target.path)
    tracked_members = sorted(rel for rel in (tracked or set())
                             if rel.split("/", 1)[0] in _CON_ROOTS)

    if tracked_members:
        roots = sorted({rel.split("/", 1)[0] for rel in tracked_members})
        return _outcome(spec, Verdict.FAIL,
                        f"tracked: {', '.join(tracked_members[:8])}", [_finding(
            spec, "treat scratch and agent-state directories as transient",
            f"{len(tracked_members)} path(s) under {', '.join(roots)}/ are tracked by git",
            Verdict.FAIL, [Evidence(rel) for rel in tracked_members[:12]],
            "Untrack the contents (git rm --cached) — an ignore rule only keeps future files "
            "out.")])

    present = _present_roots(target, inventory)
    if not present:
        return _outcome(spec, Verdict.PASS, "no scratch or agent-state directory in use")

    rules = load_ignore_rules(target.path)
    patterns = [rule.pattern for rule in rules]
    covered = [root for root in present if _covered(root, patterns)]
    uncovered = [root for root in present if not _covered(root, patterns)]

    if uncovered and not covered:
        return _outcome(spec, Verdict.FAIL,
                        f"{', '.join(root + '/' for root in uncovered)} present but matched by no "
                        f"ignore rule", [_finding(
            spec, "keep scratch and agent-state directories out of the index and out of reads",
            f"{', '.join(root + '/' for root in uncovered)} exists but no ignore rule covers it",
            Verdict.FAIL, [Evidence(root + "/") for root in uncovered],
            f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore so agents and the "
            f"index do not read transient state as source of truth.")])

    if uncovered:
        return _outcome(spec, Verdict.PARTIAL,
                        f"ignore rules cover {', '.join(root + '/' for root in covered)} but not "
                        f"{', '.join(root + '/' for root in uncovered)}", [_finding(
            spec, "keep every scratch and agent-state directory out of the index and reads",
            f"ignore rules do not cover {', '.join(root + '/' for root in uncovered)}",
            Verdict.PARTIAL, [Evidence(root + "/") for root in uncovered],
            f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore.")])

    if tracked is None:
        covered_list = ", ".join(root + "/" for root in covered)
        return _unknown(spec, f"ignore rules cover {covered_list}, but git could not report the "
                              f"tracked set")

    return _outcome(spec, Verdict.PASS,
                    f"{', '.join(root + '/' for root in covered)} present, ignored, and untracked")


# ===========================================================================
# CON-04 — draft allow/deny emitter (not scored)
# ===========================================================================

#: Canonical deny patterns per draft section. Emitted verbatim so the draft is useful even where the
#: scan observed no instance of a category.
_DRAFT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("secrets", (".aws/*", ".env", ".env.*", "id_rsa*", "*.cer", "*.crt", "*.key",
                 "*.keystore", "*.p12", "*.pem", "*.pfx")),
    ("migrations", ("alembic/versions/", "db/migrate/", "flyway/", "liquibase/",
                    "migration/", "migrations/", "prisma/migrations/")),
    ("generated", ("build/", "dist/", "generated/", "vendor/", "*.designer.cs", "*.g.cs",
                   "*.min.css", "*.min.js", "*.pb.go")),
    ("tests", ("__tests__/", "spec/", "specs/", "test/", "tests/")),
    ("iac", ("*.tf", "*.tf.json", "*.tfstate", "*.tfvars", "ansible/", "charts/", "helm/",
             "k8s/", "kubernetes/")),
    ("production", ("**/prod/**", "**/production/**", "environments/prod/",
                    "environments/production/")),
)

_GENERATED_DIRS: frozenset[str] = frozenset({"build", "dist", "generated", "vendor"})
_IAC_DIRS: frozenset[str] = frozenset({"ansible", "charts", "helm", "k8s", "kubernetes"})
_MIGRATION_DIRS: frozenset[str] = frozenset({"migration", "migrations"})


def _is_secret_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base == ".env" or base.startswith(".env.") or base.startswith("id_rsa"):
        return True
    if base.endswith((".cer", ".crt", ".key", ".keystore", ".p12", ".pem", ".pfx")):
        return True
    return rel.startswith(".aws/")


def _is_generated_path(entry) -> bool:
    if entry.kind is Kind.GENERATED:
        return True
    base = entry.rel.rsplit("/", 1)[-1]
    if base.endswith((".designer.cs", ".g.cs", ".min.css", ".min.js", ".pb.go")):
        return True
    return any(part in _GENERATED_DIRS for part in entry.rel.split("/")[:-1])


def _is_migration_path(rel: str) -> bool:
    parts = rel.split("/")
    if any(part in _MIGRATION_DIRS for part in parts[:-1]):
        return True
    return rel.startswith(("alembic/versions/", "prisma/migrations/", "db/migrate/"))


def _is_iac_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base.endswith((".tf", ".tfvars", ".tfstate")) or base.endswith(".tf.json"):
        return True
    return any(part in _IAC_DIRS for part in rel.split("/")[:-1])


def _is_production_path(rel: str) -> bool:
    return any(part.lower() in {"prod", "production"} for part in rel.split("/")[:-1])


def _is_test_path(entry) -> bool:
    return any(part in _TEST_DIR_NAMES for part in entry.rel.split("/")[:-1])


_DRAFT_MATCHERS = {
    "secrets": lambda entry: _is_secret_path(entry.rel),
    "migrations": lambda entry: _is_migration_path(entry.rel),
    "generated": _is_generated_path,
    "tests": _is_test_path,
    "iac": lambda entry: _is_iac_path(entry.rel),
    "production": lambda entry: _is_production_path(entry.rel),
}


def _allow_roots(inventory: Inventory) -> list[str]:
    """Top-level roots that hold no denied path: the draft's read-allowed surface."""
    denied: set[str] = set()
    for entry in inventory.files:
        if any(matcher(entry) for matcher in _DRAFT_MATCHERS.values()):
            denied.add(entry.rel.split("/", 1)[0])
    roots = {entry.rel.split("/", 1)[0] for entry in inventory.files if "/" in entry.rel}
    return [f"{root}/" for root in sorted(roots)
            if not root.startswith(".") and root not in denied and root != "node_modules"]


def build_constraint_draft(inventory: Inventory) -> str:
    """The deterministic YAML text of the draft allow/deny list (CON-04).

    Sections are fixed and entries are sorted, so the same target always yields the same bytes.
    """
    lines = [
        "# Generated by python-agentic-audit (CON-04) — DRAFT, review before use.",
        "# The readiness framework defines no schema for allow/deny lists; this is a",
        "# starting point derived deterministically from the scan. Treat it as reviewed",
        "# infrastructure, not a conformance claim.",
        "version: 1",
        "deny:",
    ]
    for name, canonical in _DRAFT_PATTERNS:
        observed = [entry.rel for entry in inventory.files if _DRAFT_MATCHERS[name](entry)]
        entries = sorted(set(canonical) | set(observed))
        lines.append(f"  {name}:")
        lines.extend(f"    - {json.dumps(entry)}" for entry in entries)

    lines.append("allow:")
    allow = _allow_roots(inventory)
    if allow:
        lines.extend(f"  - {json.dumps(entry)}" for entry in allow)
    else:
        lines.append("  []")
    return "\n".join(lines) + "\n"


def _write_constraint_draft(target: Target, out_path: Path, text: str) -> Path | None:
    """Write the draft beside the report. Returns the path, or None if it would land in-target."""
    out_dir = out_path.parent
    try:
        out_dir.resolve().relative_to(target.path.resolve())
    except ValueError:
        pass
    else:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / DRAFT_FILENAME
    path.write_text(text, encoding="utf-8")
    return path


def check_con04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if _EMIT_TARGET is None:
        return _unknown(spec, "draft not emitted; pass --emit-baseline to write "
                              f"{DRAFT_FILENAME} beside the report")

    draft = build_constraint_draft(inventory)
    written = _write_constraint_draft(target, _EMIT_TARGET, draft)
    if written is None:
        return _unknown(spec, f"refusing to emit inside the target ({_EMIT_TARGET.parent}); pass "
                              f"an --out outside the repository")

    return _outcome(spec, Verdict.PASS, f"draft allow/deny list written: {written}")


IMPLEMENTATIONS = {
    "CON-02": check_con02,
    "CON-03": check_con03,
    "CON-04": check_con04,
}
