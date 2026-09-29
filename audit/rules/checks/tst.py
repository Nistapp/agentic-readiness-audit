"""`TST` pack — tests.

Anchor: `brownfield-legacy/Phased-Approach.md` § Activities.

Implemented here: `TST-01` … `TST-05`.

The pack verifies that the test surface is *runnable and situated*: a test verb and a suite (TST-01),
a known suite status (TST-02, the only Tier-C probe in the pack), a skip/xfail census (TST-03), a
documented fast path (TST-04), and coverage reporting (TST-05). The test verb is read the same way
CMD/CI/TOOL read it — through `audit.rules.checks._common.resolve_verbs` — so the packs cannot drift.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **TST-01** — a resolvable `test` verb **and** at least one test file. A test file is a source file
  classified `audit.scan.Kind.TEST` by the scan hints (``test_``, ``_test.``, ``.test.``, ``.spec.``,
  ``tests/``, ``test/``, ``__tests__/``), restricted to test-source suffixes so a config file such as
  `tsconfig.test.json` or `vitest.config.ts` is never mistaken for a test. Verb without files, or files
  without a verb, is `PARTIAL` (the finding is `DEGRADER`: half the surface exists). Neither, with a
  recognised ecosystem, is `FAIL`; neither with **no** recognised ecosystem is `UNKNOWN` — an
  unrecognised repository is not proof of absence.
* **TST-02 (Tier C)** — the resolved `test` verb is run as a `ProbePlan(verb="test", read_only=True)`.
  The probe is refused unless `--run-gates` **and** `--allow-probe test`; a refusal is recorded in the
  report's `probes` array and the verdict is `UNKNOWN`, never an error (AGENTS.md §2.2, ADR-0002).
  Exit 0 is `PASS`, a non-zero exit is `FAIL`, and a timed-out or unpermitted probe is `UNKNOWN`.
  No mutating verb is ever constructed here.
* **TST-03** — a **census**, not a threshold: the count of skip, ignore and expected-failure markers in
  each readable test file, grouped by the language family that file belongs to (javascript/vitest/jest/
  mocha, python, go, rust, jvm). Zero markers is a `PASS`; no test file, or no readable test file,
  is `UNKNOWN`. This check never invents a maximum.
* **TST-04** — a single-test/subset invocation in a fenced shell block, read from the repository's
  entry documents (`README.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) via
  `_common.extract_fenced_commands`. `PASS` when one is documented; `FAIL` when the documents are
  readable but none shows one. With **no test file** there is no suite for a fast path to act on, so
  the verdict is `UNKNOWN` — a missing suite is TST-01's finding, not doubled here. The search scope is
  stated in `detail`.
* **TST-05** — coverage reporting configured for the test runner: a coverage config file, a
  `coverage` block in a runner config (`vitest`/`jest`/`vite`), a package script or resolved verb
  invoking a coverage tool (`--coverage`, `--cov`, `c8`, `nyc`, `jacoco`, `go test -cover`), or a
  `[tool.coverage]` section. Present is `PASS`; absent is `FAIL` (`COSMETIC`). Coverage is **not**
  run — that would be Tier C.

Deliberate limits, recorded rather than hidden. **Test-file discovery is the scan's classification**,
filtered to source suffixes; a suite laid out under none of the conventions above is not seen and
degrades to `UNKNOWN`, never a false `PASS`. **Marker patterns are language-family heuristics**, not a
parse — a marker inside a string literal is counted too, which is acceptable for a census. **Fast-path
and coverage detection are textual**, against a documented pattern set; a command hidden inside a
quoted string or an exotic runner is not seen.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.probes import ProbePlan
from audit.rules.checks._common import extract_fenced_commands, resolve_verbs
from audit.scan import Kind
from audit.stack import extract_npm_scripts

#: Suffixes a *test source* file can carry. A file classified ``Kind.TEST`` by a directory hint
#: (``test/``, ``tests/``) but carrying another suffix (``.json``) is configuration, not a test.
_TEST_SOURCE_SUFFIXES: tuple[str, ...] = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".rb", ".cs", ".php",
)

#: Framework-specific test-file globs, in addition to the scan's classification.
_FRAMEWORK_TEST_GLOBS: tuple[str, ...] = ("*_test.go", "tests/*.rs")

#: Entry documents read for a documented fast path, in fixed order.
_FASTPATH_DOCS: tuple[str, ...] = ("README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")

#: A single-test or subset invocation, per runner. Deliberately excludes a plain full-suite run
#: (``npm test``, ``pytest``), which is the gate TST-01 already covers.
_FASTPATH_PATTERNS: tuple[str, ...] = (
    r"\bpytest\b[^\n&|;]*\s-k\b",
    r"\bpytest\b[^\n&|;]*::[A-Za-z_]\w*",
    r"\bpython3?\s+-m\s+pytest\b[^\n&|;]*\s-k\b",
    r"\bnpm\s+(?:run\s+)?(?:test|t)\s+--\s+\S+",
    r"\b(?:pnpm|yarn|bun)\s+(?:run\s+)?(?:test|t)\s+(?:--\s+)?\S+",
    r"\b(?:npx\s+)?vitest\s+run\s+\S*(?:test|spec)\S*",
    r"\b(?:npx\s+)?jest\b[^\n&|;]*\s(?:-t|--testNamePattern)\b",
    r"\bgo\s+test\b[^\n&|;]*\s-run\b",
    r"\bcargo\s+test\b\s+[A-Za-z_]\w*",
    r"\b(?:\./)?(?:gradlew|gradle)\b[^\n&|;]*--tests\b",
    r"\bmvn\b[^\n&|;]*-Dtest=",
    r"\bdotnet\s+test\b[^\n&|;]*--filter\b",
    r"\bmocha\b[^\n&|;]*\s-g\b",
    r"\brspec\b[^\n&|;]*\S+\.rb(?::\d+)?",
    r"\btox\b[^\n&|;]*-e\b",
)
_FASTPATH_RE = re.compile("|".join(_FASTPATH_PATTERNS))

#: Coverage configuration filenames. Present at any depth is evidence.
_COVERAGE_FILES: tuple[str, ...] = (
    ".coveragerc", ".coveragerc.toml", ".nycrc", ".nycrc.json", ".nycrc.yml", ".nycrc.yaml",
    "nyc.config.js", "nyc.config.cjs", ".c8rc", ".c8rc.json", "codecov.yml", ".codecov.yml",
    ".codecov.yaml", "coveralls.yml", ".coveralls.yml",
)

#: A command that turns coverage on. Matched against package scripts and resolved verb commands.
_COVERAGE_TOOL_RE = re.compile(
    r"--(?:coverage|cov)\b|\b(?:c8|nyc|jacoco|cobertura|coveralls|codecov)\b"
    r"|\bgo\s+test\b[^\n&|;]*-cover\b"
)

#: Runner config globs that enable coverage through a config key rather than a script flag.
_COVERAGE_CONFIG_GLOBS: tuple[str, ...] = (
    "vitest.config.*", "jest.config.*", "vite.config.*", "karma.conf.*",
)
_COVERAGE_CONFIG_RE = re.compile(r"(?m)^\s*coverage\s*:|[\"']coverage[\"']\s*:")

#: Language family by source suffix, for the TST-03 census.
_FAMILY_BY_SUFFIX: dict[str, str] = {
    ".py": "python", ".go": "go", ".rs": "rust", ".java": "jvm", ".kt": "jvm",
    ".ts": "javascript", ".tsx": "javascript", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript",
}

_JS_MARKERS: tuple[str, ...] = (
    r"\b(?:it|test|describe)\.(?:skip|todo|failing|fails)\b",
    r"\b(?:xit|xtest|xdescribe)\b",
)

#: Skip / ignore / expected-failure markers by language family. Keys are families and, for
#: javascript, the test frameworks `stack.test_frameworks` can refine them to.
_MARKER_PATTERNS: dict[str, tuple[str, ...]] = {
    "javascript": _JS_MARKERS,
    "vitest": _JS_MARKERS,
    "jest": _JS_MARKERS,
    "mocha": (r"\b(?:it|describe)\.(?:skip|pending)\b", r"\b(?:xit|xdescribe)\b"),
    "python": (
        r"@pytest\.mark\.(?:skip|xfail)\b",
        r"@unittest\.(?:skip|skipIf|expectedFailure)\b",
        r"\bpytest\.skip\(",
        r"\bunittest\.SkipTest\b",
    ),
    "go": (r"\bt\.Skip(?:Now)?f?\(", r"\btesting\.Short\("),
    "rust": (r"#\[ignore\]",),
    "jvm": (r"@(?:Ignore|Disabled|DisabledOnOs)\b", r"\bassumeTrue\("),
}


def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence],
             remediation: str, severity: Severity | None = None) -> Finding:
    return Finding(check=spec.id, severity=severity or spec.severity, phase=spec.phase,
                   verdict=verdict, statement=statement(cannot, because), evidence=evidence,
                   remediation=remediation)


# ---------------------------------------------------------------------------
# shared readers
# ---------------------------------------------------------------------------

def _test_files(inventory) -> list[str]:
    """Test source files, per the scan's conventions plus the framework test globs."""
    files = {f.rel for f in inventory.files
             if f.kind is Kind.TEST and f.rel.lower().endswith(_TEST_SOURCE_SUFFIXES)}
    files.update(inventory.match(*_FRAMEWORK_TEST_GLOBS))
    return sorted(files)


def _family_for(rel: str, stack) -> str:
    base = rel.rsplit("/", 1)[-1]
    suffix = "." + base.rsplit(".", 1)[1] if "." in base else ""
    family = _FAMILY_BY_SUFFIX.get(suffix, "")
    if family == "javascript":
        for candidate in ("vitest", "jest", "mocha"):
            if candidate in stack.test_frameworks:
                return candidate
    return family


# ===========================================================================
# TST-01 — test verb and a non-empty suite
# ===========================================================================

def check_tst01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    binding = resolve_verbs(inventory, stack).get("test")
    files = _test_files(inventory)

    if binding and files:
        return _outcome(spec, Verdict.PASS,
                        f"test verb on {binding.runner} ({binding.command}); "
                        f"{len(files)} test file(s)")

    if binding and not files:
        return _outcome(spec, Verdict.PARTIAL,
                        f"test verb on {binding.runner} ({binding.command}) but no test file matches "
                        f"the framework conventions", [_finding(
            spec, "run a real suite rather than an empty one",
            "a test verb resolves but no test file exists yet",
            Verdict.PARTIAL, [Evidence(binding.runner, note=binding.command)],
            "Add a test file (for example `test/` or `src/**/*.test.ts`) so the test verb runs a "
            "real suite, not an empty one.",
            severity=Severity.DEGRADER)])

    if files and not binding:
        return _outcome(spec, Verdict.PARTIAL,
                        f"{len(files)} test file(s) but no resolvable test verb", [_finding(
            spec, "run the suite by name",
            "test files exist but no runner exposes a test verb",
            Verdict.PARTIAL, [Evidence(rel) for rel in files[:12]],
            "Define a test verb on the runner (for example `npm test`, a Makefile `test` target, or "
            "`pytest`) so the suite is reachable without inventing a command.",
            severity=Severity.DEGRADER)])

    if stack.ecosystems:
        return _outcome(spec, Verdict.FAIL, "no test verb and no test file", [_finding(
            spec, "run the test suite",
            "no test verb resolves and no test file exists",
            Verdict.FAIL, [Evidence(rel) for rel in sorted(inventory.paths())[:1]]
            or [Evidence("<repository>")],
            "Add a test verb and at least one test file so a change set can be verified.")])

    return _unknown(spec, "no recognised ecosystem, no test verb and no test file, so a suite cannot "
                          "be ruled out")


# ===========================================================================
# TST-02 — suite status (Tier C)
# ===========================================================================

def check_tst02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    binding = resolve_verbs(inventory, stack).get("test")
    if binding is None:
        return _unknown(spec, "no test verb resolves on any runner, so the suite cannot be run")

    plan = ProbePlan(verb="test", command=list(binding.argv), read_only=True)
    result = session.run(plan)

    if result.refused_reason:
        return _unknown(spec, f"probe not run: {result.refused_reason}")
    if result.timed_out:
        return _unknown(spec, "test probe timed out; suite status unknown")
    if result.exit_code == 0:
        return _outcome(spec, Verdict.PASS, f"test verb exited 0 in {result.duration_s:.2f}s")

    return _outcome(spec, Verdict.FAIL, f"test verb exited {result.exit_code}", [_finding(
        spec, "trust the suite to verify a change set",
        f"the test verb ({' '.join(plan.command)}) exited {result.exit_code}",
        Verdict.FAIL, [Evidence(binding.runner, note=binding.command)],
        "Make the test verb exit 0 before relying on it as a gate.")])


# ===========================================================================
# TST-03 — skip / xfail census
# ===========================================================================

def check_tst03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    files = _test_files(inventory)
    if not files:
        return _unknown(spec, "no test file is present, so there is no skip/xfail census to take")

    counts: dict[str, int] = {}
    readable = 0
    for rel in files:
        text = inventory.read(rel)
        if text is None:
            continue
        readable += 1
        family = _family_for(rel, stack)
        patterns = _MARKER_PATTERNS.get(family)
        if not patterns:
            continue
        found = sum(1 for pattern in patterns for _ in re.finditer(pattern, text))
        if found:
            counts[family] = counts.get(family, 0) + found

    if readable == 0:
        return _unknown(spec, "no test file could be read for a skip/xfail census")

    total = sum(counts.values())
    breakdown = ", ".join(f"{family} {count}" for family, count in sorted(counts.items()))
    detail = (f"skip/xfail census across {readable} test file(s): "
              f"{breakdown or 'no markers'}; total {total}")
    return _outcome(spec, Verdict.PASS, detail)


# ===========================================================================
# TST-04 — fast path documented
# ===========================================================================

def check_tst04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    files = _test_files(inventory)
    if not files:
        return _unknown(spec, "no test file is present, so there is no suite for a fast path to act "
                              "on (see TST-01)")

    docs = [rel for rel in _FASTPATH_DOCS if inventory.has(rel)]
    scope = ", ".join(docs) if docs else f"{', '.join(_FASTPATH_DOCS)} (none present)"

    for rel in docs:
        text = inventory.read(rel)
        if not text:
            continue
        for _language, line, command in extract_fenced_commands(text):
            if _FASTPATH_RE.search(command):
                return _outcome(spec, Verdict.PASS,
                                f"fast path documented: {rel}:{line} `{command}` (scope: {scope})")

    return _outcome(spec, Verdict.FAIL,
                    f"no single-test/subset invocation in fenced shell blocks (scope: {scope})",
                    [_finding(
                        spec, "run one test or a subset without the whole suite",
                        f"none of the entry documents shows a single-test or subset invocation "
                        f"(scope: {scope})",
                        Verdict.FAIL, [Evidence(rel) for rel in docs] or [Evidence("<repository>")],
                        "Document a fast path (for example `pytest -k <name>`, "
                        "`npm test -- <name>`, or `go test -run <name>`) in a fenced shell block.")])


# ===========================================================================
# TST-05 — coverage configuration
# ===========================================================================

def _coverage_evidence(inventory, stack) -> list[str]:
    found = [name for name in _COVERAGE_FILES if inventory.has(name)]

    if any(_COVERAGE_TOOL_RE.search(command)
           for command in extract_npm_scripts(inventory).values()):
        found.append("package.json script")
    if _read_matches(inventory, "pyproject.toml", r"(?ms)^\[tool\.coverage"):
        found.append("pyproject.toml [tool.coverage]")
    for rel, pattern in (("setup.cfg", r"(?m)^\[coverage"),
                         ("tox.ini", r"(?m)^\[coverage"),
                         ("pytest.ini", r"--cov\b"),
                         ("pom.xml", r"jacoco"),
                         ("build.gradle", r"jacoco"),
                         ("build.gradle.kts", r"jacoco")):
        if _read_matches(inventory, rel, pattern):
            found.append(rel)

    for glob in _COVERAGE_CONFIG_GLOBS:
        for rel in inventory.match(glob):
            text = inventory.read(rel)
            if text and _COVERAGE_CONFIG_RE.search(text):
                found.append(rel)

    for binding in resolve_verbs(inventory, stack).values():
        if _COVERAGE_TOOL_RE.search(binding.command):
            found.append(f"{binding.runner}:{binding.verb}")

    return sorted(set(found))


def _read_matches(inventory, rel: str, pattern: str) -> bool:
    text = inventory.read(rel)
    return bool(text and re.search(pattern, text))


def check_tst05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    evidence = _coverage_evidence(inventory, stack)
    if evidence:
        return _outcome(spec, Verdict.PASS, f"coverage configured: {', '.join(evidence)}")

    return _outcome(spec, Verdict.FAIL, "no coverage configuration", [_finding(
        spec, "see how much of the code the suite actually covers",
        "no coverage configuration or coverage-invoking command is present",
        Verdict.FAIL, [Evidence("<repository>")],
        "Configure coverage for the test runner (a `coverage` block, `.coveragerc`/`.nycrc`, "
        "`--coverage`/`--cov`, or `go test -cover`).")])


IMPLEMENTATIONS = {
    "TST-01": check_tst01,
    "TST-02": check_tst02,
    "TST-03": check_tst03,
    "TST-04": check_tst04,
    "TST-05": check_tst05,
}
