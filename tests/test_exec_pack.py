"""EXEC execution-determinism checks against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly one `EXEC` check. The audit runs as a
subprocess through `tests/support.py`, so the fixtures exercise the real end-to-end path.

`EXEC-02` and `EXEC-05` read git's tracked-file set, so their fixture is copied into a temporary
git repository created inside the test's own temp directory — never the audit repo. The same
fixtures are also exercised *without* git to prove the checks degrade to `UNKNOWN`, never `PASS`.
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

#: fixture directory -> (check id under test, expected verdict, needs a git repository)
FIXTURES: dict[str, tuple[str, str, bool]] = {
    "exec-01-unpinned": ("EXEC-01", "FAIL", False),
    "exec-02-no-lockfile": ("EXEC-02", "FAIL", True),
    "exec-03-no-setup": ("EXEC-03", "FAIL", False),
    "exec-04-missing-env": ("EXEC-04", "FAIL", False),
    "exec-05-generated": ("EXEC-05", "FAIL", True),
    "exec-06-broken-command": ("EXEC-06", "FAIL", False),
    "exec-07-dual-lint": ("EXEC-07", "FAIL", False),
}

EXEC_CHECKS = tuple(f"EXEC-0{i}" for i in range(1, 8))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class ExecFixtureTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
        return target

    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected, git) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=git))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in EXEC_CHECKS if verdicts[cid] == "FAIL")
                self.assertEqual(failing, [check],
                                 f"{name}: unexpected EXEC FAILs {failing}")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        for name, _check in (("exec-02-no-lockfile", "EXEC-02"),
                             ("exec-05-generated", "EXEC-05")):
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=False))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[_check], "UNKNOWN",
                                 f"{name}: without git the check must not infer a tracked set")

    def test_a_broken_command_lists_its_evidence(self):
        report = support.run_audit(self._prepare("exec-06-broken-command", git=False))
        findings = [f for f in report["findings"] if f["check"] == "EXEC-06"]
        self.assertTrue(findings, "EXEC-06 failed without emitting a finding")
        self.assertTrue(any("does-not-exist" in (e.get("note") or "")
                            for f in findings for e in f["evidence"]),
                        "the unresolvable command is not named in the evidence")


if __name__ == "__main__":
    unittest.main()
