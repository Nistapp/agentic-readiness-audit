"""`BASE` pack — quality baselines and the no-new-violations ratchet.

Anchor: `brownfield-legacy/Phased-Approach.md` § Activities ("Establish quality baselines for
existing technical debt", "Enforce a **no new violations** policy") and § Key Deliverables
("Quality baselines | Config files | CI").

Implemented here: `BASE-01` … `BASE-04`.

The pack verifies that a repository has a **quality baseline** it can be measured against, that it
*measures* violations, that it refuses to let the count grow, and that it holds a coverage floor.
The audit never runs the target's tools (that would be Tier C); it reads the committed configuration
and artifacts, and records the method it used.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **BASE-01** — a committed baseline or suppression artifact (`.eslint-baseline*`,
  `.ruff-baseline*`, `.mypy-baseline*`, `baseline.json`, `coverage-baseline.*`, `.snyk`,
  `.gitleaksignore`, …), or an equivalent mechanism documented in `AGENTS.md`/`CLAUDE.md`. Tooling
  that could *produce* a baseline without one being committed is `PARTIAL`, not `PASS`.
* **BASE-02** — whether a violation **count** is committed. The only count this static scan can
  point at exactly is an explicit numeric budget (`--max-warnings N`, `max-issues`, a
  `violation budget`); a committed baseline artifact or a configured lint/type/security tool is a
  mechanism but not a count, so it is `PARTIAL`. The check **never** returns `FAIL`: the audit
  cannot run the target's tools, so it cannot prove no count exists. The `detail` always states the
  method used.
* **BASE-03** — a committed ratchet: a numeric violation budget, a baseline artifact that a CI
  workflow references (a comparison step), or a comparison step documented in the entry docs.
  A repository that has committed a baseline but does nothing that compares against it is `FAIL` —
  the debt is measured but not guarded. A repository with no measurement surface at all is
  `PARTIAL`: there is nothing yet for a ratchet to compare, so absence is not proof of the policy.
* **BASE-04** — a coverage threshold in test-runner configuration (`coverage.fail_under`,
  `--cov-fail-under`, `coverageThreshold`, vitest/jest `thresholds`). A threshold stated only in
  prose is `PARTIAL`. No threshold and no prose, in a recognised repository, is `FAIL`.

No recognised ecosystem and no configuration at all ⇒ every check returns `UNKNOWN`, never `PASS`.

Deliberate limits, recorded rather than hidden. **Artifacts are matched by name, not parsed** — a
`baseline.json` is evidence it exists, not proof it is current or adequate (`baseline-adequacy` is
on the unattested list). **A baseline does not count for BASE-02**, which asks specifically for a
number the audit can see without running a tool. The audit never executes a formatter, linter or
scanner; every verdict above is derived from committed text.

The ``AuditResult.regressions()`` ratchet this pack reports on lives in ``audit/evaluate.py``; it
compares stable finding ids (`check id + path`) against a previously emitted JSON report.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import resolve_verbs
from audit.scan import Inventory
from audit.stack import CI_PROVIDERS
from audit.rules.payloads import Payload

#: Baseline / suppression artifacts, matched by name at any depth. A `*baseline*` name is treated as
#: a baseline wherever it sits; this is a documented name set, not a content assertion.
_BASELINE_GLOBS: tuple[str, ...] = (
    ".eslint-baseline*", ".ruff-baseline*", ".mypy-baseline*",
    "baseline.json", "*baseline*.json", "*baseline*.xml",
    "coverage-baseline.*", "*.baseline", ".secrets.baseline",
    ".snyk", ".gitleaksignore",
)

#: Entry documents whose contents can satisfy the "documented equivalent mechanism" clause.
_DOCS: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")

#: A documented baseline/suppression *mechanism* (BASE-01), distinct from a comparison step (BASE-03).
_DOC_BASELINE_RE = re.compile(
    r"(?i)(?:quality\s+baseline|baseline\s+(?:file|report|artifact|artefact|count|json)"
    r"|no[- ]new[- ]violations?|violation\s+budget"
    r"|suppress(?:ion|ed)?\s+(?:file|list|count))"
)

#: A documented *comparison step* (BASE-03): the repo compares a scan against a baseline.
_DOC_RATCHET_RE = re.compile(
    r"(?i)(?:ratchet|no[- ]new[- ]violations?|violation\s+budget"
    r"|(?:compare|comparison|regression)[^\n]{0,48}baseline"
    r"|baseline[^\n]{0,48}(?:compare|comparison|regression))"
)

#: Files whose mere presence implies a violation-counting tool is configured.
_COUNTING_CONFIG_GLOBS: tuple[str, ...] = (
    ".eslintrc*", "eslint.config.*", "biome.json", "biome.jsonc",
    ".ruff.toml", "ruff.toml", ".flake8", "pylintrc", ".pylintrc",
    "mypy.ini", ".mypy.ini", ".golangci.yml", ".golangci.yaml",
    "clippy.toml", ".gitleaks.toml", ".snyk", "sonar-project.properties",
    ".semgrep.yml", ".semgrep.yaml",
)
_PYPROJECT_TOOL_RE = re.compile(r"(?m)^\[tool\.(?:ruff|mypy|pylint|bandit|pyright)\b")
_SETUP_CFG_TOOL_RE = re.compile(r"(?m)^\[(?:mypy|flake8|pylint|isort|bandit)\b")

#: An explicit numeric violation budget — the only count a static scan can point at exactly.
_BUDGET_RE = re.compile(
    r"--max-warnings(?:=|\s+)\d+"
    r"|\bmax[-_]?(?:warnings|issues|problems)\b\s*[:=]?\s*\d+"
    r"|\bviolation[-_]?budget\b\s*[:=]?\s*\d+"
)

#: Runner manifests read for a numeric budget in addition to the counting configs.
_RUNNER_MANIFESTS: tuple[str, ...] = (
    "package.json", "pyproject.toml", "Makefile", "Taskfile.yml", "Taskfile.yaml",
)

#: Configs that carry a coverage floor, and a runner config that enables it through a key.
_FLOOR_FILES: tuple[str, ...] = (
    ".coveragerc", ".coveragerc.toml", "setup.cfg", "tox.ini", "pytest.ini", "pyproject.toml",
)
_FLOOR_FILE_RE = re.compile(r"(?i)fail_under\s*[:=]\s*\d+|--cov-fail-under(?:=|\s+)\d+")

_COVERAGE_CONFIG_GLOBS: tuple[str, ...] = (
    "vitest.config.*", "jest.config.*", "vite.config.*", "karma.conf.*",
)
_COVERAGE_CONFIG_RE = re.compile(
    r"(?i)coverageThreshold|\bthresholds\b\s*[:=]|fail_under\s*[:=]\s*\d+"
    r"|--cov-fail-under(?:=|\s+)\d+"
)

_COVERAGE_PROSE_RE = re.compile(
    r"(?i)(?:coverage|covered)[^\n]{0,40}(?:threshold|minimum|fail|floor|at least|>=?)"
    r"|(?:threshold|minimum|at least)[^\n]{0,40}coverage"
    r"|\b\d{1,3}\s?%[^\n]{0,20}coverage|coverage[^\n]{0,20}\b\d{1,3}\s?%"
)


def _outcome(spec, verdict: Verdict, summary: str = "",
             findings: list[Finding] | None = None,
             data: Payload | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=summary, data=data, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence],
             remediation: str) -> Finding:
    return Finding(check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
                   statement=statement(cannot, because), evidence=evidence,
                   remediation=remediation)


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------

def _baseline_artifacts(inventory: Inventory) -> list[str]:
    found: set[str] = set()
    for pattern in _BASELINE_GLOBS:
        found.update(inventory.match(pattern))
    return sorted(found)


def _documented_baseline(inventory: Inventory) -> str | None:
    for rel in _DOCS:
        text = inventory.read(rel)
        if text and _DOC_BASELINE_RE.search(text):
            return rel
    return None


def _text_matches(inventory: Inventory, rel: str, pattern: re.Pattern[str]) -> bool:
    text = inventory.read(rel)
    return bool(text and pattern.search(text))


def _counting_tools(inventory: Inventory, stack) -> list[str]:
    """Configured lint / type-check / security tooling that could count violations."""
    found: set[str] = set()
    for pattern in _COUNTING_CONFIG_GLOBS:
        found.update(inventory.match(pattern))
    if _text_matches(inventory, "pyproject.toml", _PYPROJECT_TOOL_RE):
        found.add("pyproject.toml")
    for rel in ("setup.cfg", "tox.ini"):
        if _text_matches(inventory, rel, _SETUP_CFG_TOOL_RE):
            found.add(rel)
    verbs = resolve_verbs(inventory, stack)
    for verb in ("lint", "typecheck", "security"):
        binding = verbs.get(verb)
        if binding is not None:
            found.add(f"{binding.runner}:{binding.verb}")
    return sorted(found)


def _budget_evidence(inventory: Inventory, stack) -> list[str]:
    found: set[str] = set()
    for rel in _RUNNER_MANIFESTS:
        text = inventory.read(rel)
        if text and _BUDGET_RE.search(text):
            found.add(rel)
    for pattern in _COUNTING_CONFIG_GLOBS:
        for rel in inventory.match(pattern):
            text = inventory.read(rel)
            if text and _BUDGET_RE.search(text):
                found.add(rel)
    for binding in resolve_verbs(inventory, stack).values():
        if _BUDGET_RE.search(binding.command):
            found.add(f"{binding.runner}:{binding.verb}")
    return sorted(found)


def _ci_references_baseline(inventory: Inventory, names: set[str]) -> list[str]:
    found: set[str] = set()
    for _provider, globs in CI_PROVIDERS.items():
        for rel in inventory.match(*globs):
            text = inventory.read(rel)
            if text and any(name in text for name in names):
                found.add(rel)
    return sorted(found)


def _ratchet(inventory: Inventory, stack, budgets: list[str]) -> list[str]:
    """Every committed no-new-violations mechanism found, in a deterministic order."""
    if budgets:
        return [f"violation budget ({source})" for source in budgets]

    artifacts = _baseline_artifacts(inventory)
    if artifacts:
        names = {rel.rsplit("/", 1)[-1] for rel in artifacts}
        referenced = _ci_references_baseline(inventory, names)
        if referenced:
            return [f"baseline compared in CI ({rel})" for rel in referenced]

    documented = []
    for rel in _DOCS + ("README.md", "CONTRIBUTING.md"):
        text = inventory.read(rel)
        if text and _DOC_RATCHET_RE.search(text):
            documented.append(rel)
    return [f"comparison step documented in {rel}" for rel in sorted(set(documented))]


def _coverage_floor_config(inventory: Inventory, stack) -> list[str]:
    found: set[str] = set()
    for rel in _FLOOR_FILES:
        text = inventory.read(rel)
        if text and _FLOOR_FILE_RE.search(text):
            found.add(rel)
    package = inventory.read("package.json")
    if package and re.search(r"coverageThreshold|--cov-fail-under", package):
        found.add("package.json")
    for pattern in _COVERAGE_CONFIG_GLOBS:
        for rel in inventory.match(pattern):
            text = inventory.read(rel)
            if text and _COVERAGE_CONFIG_RE.search(_strip_js_comments(text)):
                found.add(rel)
    return sorted(found)


def _strip_js_comments(text: str) -> str:
    """Drop whole-line ``//`` comments so a commented-out threshold is not read as configuration."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def _coverage_prose(inventory: Inventory) -> list[str]:
    found: list[str] = []
    for rel in _DOCS + ("README.md", "CONTRIBUTING.md"):
        text = inventory.read(rel)
        if not text:
            continue
        for line in text.splitlines():
            if _COVERAGE_PROSE_RE.search(line):
                found.append(f"{rel}:{line.strip()[:80]}")
    return sorted(found)


def _recognised(inventory: Inventory, stack) -> bool:
    """Whether a recognised ecosystem or a project configuration exists at all."""
    if stack.ecosystems:
        return True
    for pattern in ("package.json", "pyproject.toml", "setup.py", "requirements*.txt", "Pipfile",
                    "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "Cargo.toml",
                    "Gemfile", "composer.json"):
        if inventory.match(pattern):
            return True
    return False


# ===========================================================================
# BASE-01 — baseline artifact exists
# ===========================================================================

def check_base01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    artifacts = _baseline_artifacts(inventory)
    documented = _documented_baseline(inventory)
    if artifacts or documented:
        evidence = artifacts or [documented or "<repository>"]
        return _outcome(spec, Verdict.PASS,
                        f"baseline/suppression mechanism present: "
                        f"{', '.join(evidence)}"
                        + ("" if artifacts else f" (documented in {documented})"))

    tools = _counting_tools(inventory, stack)
    if tools:
        return _outcome(spec, Verdict.PARTIAL,
                        f"quality tooling is configured but no baseline artifact is committed: "
                        f"{', '.join(tools[:6])}", [_finding(
            spec, "diff today's findings against an accepted baseline",
            "quality tooling is configured but no baseline or suppression artifact is committed",
            Verdict.PARTIAL, [Evidence(rel) for rel in tools[:6]],
            "Commit a baseline or suppression artifact (for example `baseline.json`, an "
            "eslint/ruff baseline, or `.gitleaksignore`), or document the equivalent mechanism in "
            "`AGENTS.md`.")])

    if _recognised(inventory, stack):
        return _outcome(spec, Verdict.FAIL, "no baseline or suppression artifact", [_finding(
            spec, "distinguish pre-existing debt from new debt",
            "no baseline or suppression artifact is committed",
            Verdict.FAIL, [Evidence("<repository>")],
            "Commit a baseline/suppression artifact, or document the equivalent mechanism in "
            "`AGENTS.md`.")])

    return _unknown(spec, "no recognised ecosystem or configuration, so a baseline cannot be ruled "
                          "out")


# ===========================================================================
# BASE-02 — current violation counts measured
# ===========================================================================

_METHOD = "static configuration scan; the target's own tools are never run"


def check_base02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    budgets = _budget_evidence(inventory, stack)
    if budgets:
        return _outcome(spec, Verdict.PASS,
                        f"violation count configured: {', '.join(budgets)}; method: {_METHOD}")

    surface = sorted(set(_counting_tools(inventory, stack)) | set(_baseline_artifacts(inventory)))
    if surface:
        return _outcome(spec, Verdict.PARTIAL,
                        f"counting surface present but no committed count/budget: "
                        f"{', '.join(surface[:6])}; method: {_METHOD}", [_finding(
            spec, "state how many violations exist today",
            "a counting surface exists but no numeric violation budget or count is committed",
            Verdict.PARTIAL, [Evidence(rel) for rel in surface[:6]],
            "Commit the count or configure a budget (`--max-warnings N`, `max-issues`, or a "
            "`violation budget`) so a regression has a baseline number to compare against.")])

    if _recognised(inventory, stack):
        return _outcome(spec, Verdict.PARTIAL,
                        f"no violation-count mechanism found; method: {_METHOD}", [_finding(
            spec, "state how many violations exist today",
            "no violation-counting tooling, budget or artifact is configured",
            Verdict.PARTIAL, [Evidence("<repository>")],
            "Add linters/type-checkers/security scanners and commit the count they produce, so "
            "debt is measured rather than guessed.")])

    return _unknown(spec, "no recognised ecosystem or counting configuration, so a count cannot be "
                          "ruled out")


# ===========================================================================
# BASE-03 — no-new-violations mechanism
# ===========================================================================

def check_base03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ratchet = _ratchet(inventory, stack, _budget_evidence(inventory, stack))
    if ratchet:
        return _outcome(spec, Verdict.PASS, f"ratchet present: {', '.join(ratchet)}")

    artifacts = _baseline_artifacts(inventory)
    if artifacts:
        return _outcome(spec, Verdict.FAIL,
                        f"baseline present but never compared against: {', '.join(artifacts)}",
                        [_finding(
            spec, "stop the violation count from growing",
            f"a baseline is committed ({', '.join(artifacts)}) but nothing compares against it",
            Verdict.FAIL, [Evidence(rel) for rel in artifacts],
            "Add a comparison step — a CI job that runs `--baseline <report>`, a violation budget "
            "in config, or a documented no-new-violations procedure — so the baseline is enforced.")])

    if _recognised(inventory, stack):
        return _outcome(spec, Verdict.PARTIAL,
                        "no ratchet and no baseline yet, so there is nothing to compare against",
                        [_finding(
            spec, "stop the violation count from growing",
            "no baseline, budget or comparison step exists, so the count is not guarded",
            Verdict.PARTIAL, [Evidence("<repository>")],
            "Once a baseline exists, wire a comparison step (the audit's own `--baseline REPORT.JSON` "
            "is the reference pattern) so new findings fail the build.")])

    return _unknown(spec, "no recognised ecosystem or configuration, so a ratchet cannot be ruled "
                          "out")


# ===========================================================================
# BASE-04 — coverage floor configured
# ===========================================================================

def check_base04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configured = _coverage_floor_config(inventory, stack)
    if configured:
        return _outcome(spec, Verdict.PASS,
                        f"coverage threshold configured: {', '.join(configured)}")

    prose = _coverage_prose(inventory)
    if prose:
        return _outcome(spec, Verdict.PARTIAL,
                        f"coverage threshold stated in prose only: {'; '.join(prose[:4])}",
                        [_finding(
            spec, "know when coverage drops below an agreed floor",
            "a coverage threshold is described in prose but not configured in the test runner",
            Verdict.PARTIAL, [Evidence(entry.split(":", 1)[0]) for entry in prose[:4]],
            "Move the threshold into test-runner configuration (`coverage.fail_under`, "
            "`--cov-fail-under`, `coverageThreshold`, or a vitest/jest `thresholds` block).")])

    if _recognised(inventory, stack):
        return _outcome(spec, Verdict.FAIL, "no coverage threshold configured", [_finding(
            spec, "know when coverage drops below an agreed floor",
            "no coverage threshold is configured in the test runner",
            Verdict.FAIL, [Evidence("<repository>")],
            "Configure a coverage floor for the test runner so a drop fails the gate.")])

    return _unknown(spec, "no recognised ecosystem or test-runner configuration, so a coverage "
                          "floor cannot be ruled out")


IMPLEMENTATIONS = {
    "BASE-01": check_base01,
    "BASE-02": check_base02,
    "BASE-03": check_base03,
    "BASE-04": check_base04,
}