"""SEC security-hygiene checks against their one-defect fixtures.

`SEC-01` and `SEC-02` read git's tracked-file set, so their fixtures are copied into a temporary git
repository created inside the test's own temp directory — never the audit repo. The same fixtures
are also exercised *without* git to prove the tracked half degrades to `UNKNOWN`, never `PASS`.

The `SEC-02` fixture carries a clearly synthetic value; a test asserts that value never reaches the
report, only the path and line.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

#: fixture directory -> (check id under test, expected verdict, needs git, force-add .env)
FIXTURES: dict[str, tuple[str, str, bool, bool]] = {
    "sec-01-tracked-env": ("SEC-01", "FAIL", True, True),
    "sec-02-key-shaped": ("SEC-02", "FAIL", True, False),
    "sec-03-thin-ignore": ("SEC-03", "FAIL", False, False),
}

SEC_CHECKS = ("SEC-01", "SEC-02", "SEC-03")

#: The synthetic value in `sec-02-key-shaped/config.py`. Deliberately not a usable credential.
SYNTHETIC_SECRET = "sk-0123456789abcdefghij"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class SecFixtureTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool, force_env: bool = False) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
            if force_env:
                # `.env` is ignored by the compiled-in rule; force-add it so the tracked blocker
                # exists regardless of the ignore rules SEC-03 checks.
                self.assertEqual(_git(target, "add", "-f", ".env").returncode, 0)
        return target

    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected, needs_git, force_env) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=needs_git, force_env=force_env))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in SEC_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing,
                                 f"{name}: unexpected SEC FAILs {failing}")

    def test_sec_01_ok_passes_all_three(self):
        report = support.run_audit(self._prepare("sec-01-ok", git=True))
        verdicts = support.verdicts(report)
        for check in SEC_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"sec-01-ok: {check}")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        report = support.run_audit(self._prepare("sec-01-tracked-env", git=False))
        self.assertEqual(support.verdicts(report)["SEC-01"], "UNKNOWN",
                         "without git the tracked .env cannot be ruled out")


class Sec02ReportHygieneTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
        return target

    def test_the_matched_value_never_reaches_the_report(self):
        report = support.run_audit(self._prepare("sec-02-key-shaped", git=True))
        self.assertNotIn(SYNTHETIC_SECRET, json.dumps(report),
                         "SEC-02 leaked the matched value into the report")

        findings = [f for f in report["findings"] if f["check"] == "SEC-02"]
        self.assertTrue(findings, "SEC-02 failed without emitting a finding")
        for finding in findings:
            for evidence in finding["evidence"]:
                self.assertTrue(evidence["path"])
                self.assertIsNotNone(evidence["line"])
                self.assertNotIn(SYNTHETIC_SECRET, evidence.get("note") or "")

    def test_whole_inventory_fallback_is_stated_when_git_is_absent(self):
        report = support.run_audit(self._prepare("sec-02-key-shaped", git=False))
        check = next(c for c in report["checks"] if c["id"] == "SEC-02")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("tracked state unavailable", check["data"]["source"])


class Sec03CoverageTests(unittest.TestCase):
    def test_detail_names_covered_and_missing_shapes(self):
        report = support.run_audit(support.fixture("sec-03-thin-ignore"))
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(check["data"]["kind"], "secret_shapes")
        self.assertTrue(check["data"]["missing"], "no missing shapes were named")

    def test_comprehensive_ignore_passes_with_coverage_named(self):
        report = support.run_audit(support.fixture("sec-01-ok"))
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["data"]["missing"], [])
        self.assertTrue(check["data"]["covered"], "no covered shapes were named")


if __name__ == "__main__":
    unittest.main()
