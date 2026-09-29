"""DOC and NAV checks against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly its DOC/NAV check. `doc-nav-ok` is the
governed fixture: the smallest repository that passes every scored DOC/NAV check. The audit runs as
a subprocess through `tests/support.py`, so the fixtures exercise the real end-to-end path.

`DOC-03` reads git's tracked-file set, so its fixture is copied into a temporary git repository
created inside the test's own temp directory — never the audit repo. Without git the check degrades
to `UNKNOWN`, never `PASS`.
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

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "doc-01-empty": ("DOC-01", "PARTIAL"),
    "doc-02-no-style-guide": ("DOC-02", "FAIL"),
    "doc-04-adr-unindexed": ("DOC-04", "PARTIAL"),
    "nav-01-no-manifest": ("NAV-01", "UNKNOWN"),
    "nav-02-no-entry": ("NAV-02", "FAIL"),
    "nav-03-red-flags": ("NAV-03", "PARTIAL"),
}

DOC_CHECKS = ("DOC-01", "DOC-02", "DOC-03", "DOC-04")
NAV_SCORED = ("NAV-01", "NAV-02", "NAV-03")
SCORED_CHECKS = DOC_CHECKS + NAV_SCORED


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class DocNavFixtureTests(unittest.TestCase):
    def test_each_fixture_reports_its_documented_verdict(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                self.assertEqual(support.verdicts(report)[check], expected, f"{name}: {check}")

    def test_governed_fixture_passes_every_scored_check(self):
        report = support.run_audit(support.fixture("doc-nav-ok"))
        verdicts = support.verdicts(report)
        for check in SCORED_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"doc-nav-ok: {check}")
        self.assertEqual(verdicts["NAV-04"], "PASS", "doc-nav-ok: NAV-04")

    def test_doc_01_empty_is_partial_not_fail(self):
        report = support.run_audit(support.fixture("doc-01-empty"))
        check = next(c for c in report["checks"] if c["id"] == "DOC-01")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no markdown", check["detail"])

    def test_doc_04_unindexed_names_the_missing_index(self):
        report = support.run_audit(support.fixture("doc-04-adr-unindexed"))
        check = next(c for c in report["checks"] if c["id"] == "DOC-04")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no index", check["detail"])

    def test_nav_03_reports_the_counts_and_never_fails(self):
        report = support.run_audit(support.fixture("nav-03-red-flags"))
        check = next(c for c in report["checks"] if c["id"] == "NAV-03")
        self.assertEqual(check["verdict"], "PARTIAL")
        for label in ("oversized", "catch-all", "binaries", "minified"):
            self.assertIn(label, check["detail"])

    def test_nav_05_informational_is_reported_without_crashing(self):
        report = support.run_audit(support.fixture("nav-01-no-manifest"))
        verdicts = support.verdicts(report)
        self.assertIn(verdicts["NAV-05"], ("PASS", "PARTIAL", "FAIL", "UNKNOWN"))
        check = next(c for c in report["checks"] if c["id"] == "NAV-05")
        self.assertIn("method", check["detail"])


class Doc03TrackedStateTests(unittest.TestCase):
    def _prepare(self, *, git: bool, force_add: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "doc-03-tracked-artefacts"
        shutil.copytree(support.fixture("doc-03-tracked-artefacts"), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
            if force_add:
                # The ignore rule keeps the file out of `git add -A`; force-add it so the tracked
                # defect DOC-03 exists regardless of the ignore rules.
                self.assertEqual(_git(target, "add", "-f", "artefacts/notes.md").returncode, 0)
        return target

    def test_tracked_scratch_fails_even_when_ignored(self):
        report = support.run_audit(self._prepare(git=True, force_add=True))
        self.assertEqual(support.verdicts(report)["DOC-03"], "FAIL")

    def test_ignored_and_untracked_scratch_passes(self):
        report = support.run_audit(self._prepare(git=True, force_add=False))
        self.assertEqual(support.verdicts(report)["DOC-03"], "PASS")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        report = support.run_audit(self._prepare(git=False, force_add=False))
        self.assertEqual(support.verdicts(report)["DOC-03"], "UNKNOWN",
                         "without git the tracked set cannot be ruled out")


if __name__ == "__main__":
    unittest.main()
