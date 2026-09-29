"""The fixture matrix — one explicit expectation per fixture, checked end to end.

This is the Phase-14 consolidation of the per-pack fixture tests. It walks ``tests/fixtures/`` and
asserts, for every fixture directory, the verdict its README entry promises. The matrix is an
**explicit table**, not a wildcard guess: a new fixture with no row here fails
``test_every_fixture_is_accounted_for``.

Two rules the matrix makes mechanical:

* **One defect per fixture.** A fixture that fails three checks cannot tell you which rule broke.
  The per-pack tests already assert "exactly this check" within a pack; this test asserts the
  documented verdict for the row.
* **A positive fixture per pack.** ``test_governed_fixtures_pass_every_scoreable_check`` runs the
  positive fixtures and asserts that, between them, every scoreable check passes at least once.
  Two families are excluded by construction and named below, because their verdicts cannot be
  produced without executed probes or machine-local state (AGENTS.md §10.4: never fake a pass).

Fixtures whose target check reads git's tracked set are copied into a temporary git repository
created inside the test's temp directory — never the audit repo — and a tracked defect that an
ignore rule would hide is force-added, exactly as the owning pack tests do.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

from audit.rules.registry import REGISTRY, scoreable                     # noqa: E402

FIXTURES_DIR = support.FIXTURES_DIR

#: fixture directory -> {check id: expected verdict}. Every directory under tests/fixtures/ must
#: appear here (``test_every_fixture_is_accounted_for``).
MATRIX: dict[str, dict[str, str]] = {
    # -- AGT (content contract + competing files + indirection) -------------------------------
    "agt-01-missing": {"AGT-01": "FAIL", "AGT-08": "PASS"},
    "agt-01-stub": {"AGT-01": "FAIL"},
    "agt-01-mis-cased": {"AGT-01": "FAIL"},
    "agt-01-shadowed": {"AGT-01": "PARTIAL"},
    "agt-02-uncovered": {"AGT-02": "PARTIAL"},
    "agt-03-incomplete": {"AGT-03": "PARTIAL"},
    "agt-04-missing": {"AGT-04": "FAIL"},
    "agt-05-verbs-named-not-resolved": {"AGT-05": "PARTIAL"},
    "agt-05-ok": {"AGT-05": "PASS"},
    "agt-06-thin": {"AGT-06": "PARTIAL"},
    "agt-07-missing-deny": {"AGT-07": "PARTIAL"},
    "agt-08-competitor": {"AGT-08": "FAIL"},
    "agt-09-no-release": {"AGT-09": "PARTIAL"},
    "agt-10-deferred": {"AGT-10": "FAIL"},
    # -- DOC / NAV ----------------------------------------------------------------------------
    "doc-01-empty": {"DOC-01": "PARTIAL"},
    "doc-02-no-style-guide": {"DOC-02": "FAIL"},
    "doc-03-tracked-artefacts": {"DOC-03": "FAIL"},
    "doc-04-adr-unindexed": {"DOC-04": "PARTIAL"},
    "doc-nav-ok": {"DOC-01": "PASS", "DOC-02": "PASS", "DOC-03": "PASS", "DOC-04": "PASS",
                   "NAV-01": "PASS", "NAV-02": "PASS", "NAV-03": "PASS"},
    "nav-01-no-manifest": {"NAV-01": "UNKNOWN"},
    "nav-02-no-entry": {"NAV-02": "FAIL"},
    "nav-03-red-flags": {"NAV-03": "PARTIAL"},
    # -- CMD ----------------------------------------------------------------------------------
    "cmd-01-missing-verb": {"CMD-01": "FAIL"},
    "cmd-02-weak-check": {"CMD-02": "FAIL"},
    "cmd-03-divergent": {"CMD-03": "FAIL"},
    "cmd-04-write-in-check": {"CMD-04": "FAIL"},
    "cmd-ok-npm": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-make": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    # -- TOOL ---------------------------------------------------------------------------------
    "tool-01-no-formatter": {"TOOL-01": "FAIL"},
    "tool-02-no-linter": {"TOOL-02": "FAIL"},
    "tool-03-nonstrict-ts": {"TOOL-03": "PARTIAL"},
    "tool-04-no-audit-verb": {"TOOL-04": "FAIL"},
    "tool-05-unwired-hooks": {"TOOL-05": "PARTIAL"},
    "tool-06-no-commit-rule": {"TOOL-06": "FAIL"},
    "tool-ok-node": {"TOOL-01": "PASS", "TOOL-02": "PASS", "TOOL-03": "PASS",
                     "TOOL-04": "PASS", "TOOL-05": "PASS", "TOOL-06": "PASS"},
    # -- CI -----------------------------------------------------------------------------------
    "ci-01-no-pr-trigger": {"CI-01": "PARTIAL"},
    "ci-02-parity-break": {"CI-02": "FAIL"},
    "ci-03-ci-only-step": {"CI-03": "FAIL"},
    "ci-ok-gh": {"CI-01": "PASS", "CI-02": "PASS", "CI-03": "PASS"},
    # -- BASE ---------------------------------------------------------------------------------
    "base-01-no-baseline": {"BASE-01": "FAIL"},
    "base-02-no-count": {"BASE-02": "PARTIAL"},
    "base-03-no-ratchet": {"BASE-03": "FAIL"},
    "base-04-no-coverage-floor": {"BASE-04": "FAIL"},
    "base-ok": {"BASE-01": "PASS", "BASE-02": "PASS", "BASE-03": "PASS", "BASE-04": "PASS"},
    # -- CON ----------------------------------------------------------------------------------
    "con-02-unprotected-tests": {"CON-02": "FAIL"},
    "con-02-protected": {"CON-02": "PASS"},
    "con-03-artefacts-not-ignored": {"CON-03": "FAIL"},
    # -- EXEC ---------------------------------------------------------------------------------
    "exec-01-unpinned": {"EXEC-01": "FAIL"},
    "exec-02-no-lockfile": {"EXEC-02": "FAIL"},
    "exec-03-no-setup": {"EXEC-03": "FAIL"},
    "exec-04-missing-env": {"EXEC-04": "FAIL"},
    "exec-05-generated": {"EXEC-05": "FAIL"},
    "exec-06-broken-command": {"EXEC-06": "FAIL"},
    "exec-07-dual-lint": {"EXEC-07": "FAIL"},
    "exec-ok": {"EXEC-01": "PASS", "EXEC-02": "PASS", "EXEC-03": "PASS",
                "EXEC-04": "PASS", "EXEC-05": "PASS", "EXEC-06": "PASS", "EXEC-07": "PASS"},
    # -- TST ----------------------------------------------------------------------------------
    "tst-01-no-suite": {"TST-01": "PARTIAL"},
    "tst-03-skip-markers": {"TST-03": "PASS"},
    "tst-04-no-fastpath": {"TST-04": "FAIL"},
    "tst-05-no-coverage": {"TST-05": "FAIL"},
    # -- SEC ----------------------------------------------------------------------------------
    "sec-01-tracked-env": {"SEC-01": "FAIL"},
    "sec-02-key-shaped": {"SEC-02": "FAIL"},
    "sec-03-thin-ignore": {"SEC-03": "FAIL"},
    "sec-01-ok": {"SEC-01": "PASS", "SEC-02": "PASS", "SEC-03": "PASS"},
    # -- IDX (machine-local; run with an isolated HOME and an absent index store) --------------
    "idx-01-no-mcp-config": {"IDX-01": "FAIL"},
    "idx-02-no-index": {"IDX-02": "UNKNOWN", "IDX-03": "UNKNOWN"},
    # -- HYG (informational, reported never scored) -------------------------------------------
    "hyg-01-placeholder-readme": {"HYG-01": "FAIL", "HYG-10": "FAIL"},
    "hyg-10-no-license": {"HYG-01": "PASS", "HYG-10": "FAIL"},
    "hyg-minimal": {f"HYG-{n:02d}": "FAIL" for n in range(1, 11)} | {"HYG-11": "UNKNOWN"},
    # -- the AGT-content positive fixture -----------------------------------------------------
    "governed-minimal": {"AGT-01": "PASS", "AGT-02": "PASS", "AGT-03": "PASS", "AGT-04": "PASS",
                         "AGT-06": "PASS", "AGT-07": "PASS", "AGT-09": "PASS", "AGT-10": "PASS"},
}

#: Fixtures whose target reads git's tracked set; they are copied into a fresh git repository.
NEEDS_GIT = frozenset({
    "doc-03-tracked-artefacts", "exec-02-no-lockfile", "exec-05-generated", "exec-ok",
    "sec-01-ok", "sec-01-tracked-env", "sec-02-key-shaped", "con-03-artefacts-not-ignored",
})

#: Fixtures where an ignore rule hides the tracked defect; the defect is force-added after `add -A`.
FORCE_ADD: dict[str, str] = {
    "doc-03-tracked-artefacts": "artefacts/notes.md",
    "sec-01-tracked-env": ".env",
    "con-03-artefacts-not-ignored": "artefacts/notes.md",
}

#: Fixtures whose verdict depends on machine-local state; run with an isolated HOME and store.
NEEDS_ISOLATED_ENV = frozenset({"idx-01-no-mcp-config", "idx-02-no-index"})

#: Fixtures that are not the whole matrix: the empty directory has its own structural test.
NOT_IN_MATRIX = {
    "empty": "empty directory: exercised by test_empty_directory_reports_nothing_and_does_not_crash",
}

#: Positive fixtures whose union must cover every scoreable check. ``tst-03``/``tst-05`` are not
#: "ok" fixtures but are the only checked-in fixtures where TST-03/TST-04 pass, so they complete
#: the census rather than pretend the check is verified elsewhere.
GOVERNED_FIXTURES = (
    "cmd-ok-npm", "cmd-ok-make", "tool-ok-node", "ci-ok-gh", "base-ok", "doc-nav-ok",
    "sec-01-ok", "exec-ok", "governed-minimal", "agt-05-ok", "con-02-protected",
    "tst-03-skip-markers", "tst-05-no-coverage",
)

#: Scoreable checks that cannot PASS without executed Tier-C probes or machine-local state.
#: IDX-* assert the operator's harness and index store; TST-02 runs the suite to learn its status.
#: They are covered by their own tests (test_idx_pack.py, the positive fixture) and are never
#: faked as passes here.
PROBE_OR_ENVIRONMENT_SCOPED = frozenset({
    "IDX-01", "IDX-02", "IDX-03", "TST-02",
})


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def prepare(name: str) -> Path:
    """Copy a fixture into a temp dir and apply its declared git/env preparation."""
    fixture = support.fixture(name)
    if name not in NEEDS_GIT:
        return fixture
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / name
    shutil.copytree(fixture, target)
    assert _git(target, "init").returncode == 0
    assert _git(target, "add", "-A").returncode == 0
    forced = FORCE_ADD.get(name)
    if forced:
        assert _git(target, "add", "-f", forced).returncode == 0
    return target


def run(name: str) -> dict:
    target = prepare(name)
    env = None
    if name in NEEDS_ISOLATED_ENV:
        home = tempfile.mkdtemp()
        env = {"HOME": home, "AUDIT_INDEX_STORE": str(Path(home) / "absent-store")}
    return support.run_audit(target, env=env)


class FixtureMatrixTests(unittest.TestCase):
    def test_every_fixture_is_accounted_for(self):
        actual = {p.name for p in FIXTURES_DIR.iterdir() if p.is_dir()}
        declared = set(MATRIX) | set(NOT_IN_MATRIX)
        self.assertEqual(actual - declared, set(),
                         "fixture directories with no explicit matrix row")
        self.assertEqual(declared - actual, set(),
                         "matrix rows naming a fixture that does not exist")

    def test_each_fixture_reports_its_documented_verdict(self):
        for name in sorted(MATRIX):
            if not MATRIX[name]:
                continue
            with self.subTest(fixture=name):
                verdicts = support.verdicts(run(name))
                for check, expected in MATRIX[name].items():
                    self.assertEqual(verdicts.get(check), expected,
                                     f"{name}: {check} expected {expected}")

    def test_empty_directory_reports_nothing_and_does_not_crash(self):
        # A completed scan of an empty directory exits 0 (it reports, it does not gate) and emits a
        # verdict for every catalogued check without crashing. The blocker checks that a repository
        # must satisfy by *presence* fail; the checks that could only be satisfied by a repository
        # that does not exist (single-root coverage, no competitors) pass vacuously — that is the
        # documented behaviour, not a pass by omission (Scan Engine §9; AGENTS.md §10.4).
        report = support.run_audit(support.fixture("empty"))
        verdicts = support.verdicts(report)
        self.assertEqual(set(verdicts), {spec.id for spec in REGISTRY},
                         "the empty scan dropped or added checks")
        self.assertTrue(all(v in {"PASS", "PARTIAL", "FAIL", "UNKNOWN"} for v in verdicts.values()),
                        "the empty scan produced a non-verdict")
        self.assertEqual(verdicts["AGT-01"], "FAIL",
                         "an empty repository has no instruction file")
        blocker_fails = {c["id"] for c in report["checks"]
                         if c["verdict"] == "FAIL" and c["severity"] == "BLOCKER"}
        self.assertTrue(blocker_fails, "an empty repository satisfies no blocker")

    def test_governed_fixtures_pass_every_scoreable_check(self):
        passed: set[str] = set()
        for name in GOVERNED_FIXTURES:
            with self.subTest(fixture=name):
                report = run(name)
                passed |= {cid for cid, verdict in support.verdicts(report).items()
                           if verdict == "PASS" and cid not in PROBE_OR_ENVIRONMENT_SCOPED}

        required = {spec.id for spec in scoreable()} - PROBE_OR_ENVIRONMENT_SCOPED
        missing = sorted(required - passed)
        self.assertEqual(missing, [],
                         f"no governed fixture passes these scoreable checks: {missing}")


class DeterminismOverFixtureTests(unittest.TestCase):
    def test_a_multi_finding_fixture_is_byte_stable_across_runs(self):
        name = "hyg-minimal"
        first = run(name)
        second = run(name)
        self.assertGreaterEqual(len(first["findings"]), 2,
                                "pick a fixture with more than one finding")
        for report in (first, second):
            report["provenance"].pop("scanned_at", None)
        self.assertEqual(first, second, f"{name}: the report is not deterministic")


if __name__ == "__main__":
    unittest.main()
