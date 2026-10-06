"""CON checks and the CON-04 emitter.

`CON-01` stays blocked by design and is asserted to remain so. `CON-02` is exercised against its
one-defect fixture and against inline repositories that add a real constraint file, an indirect
ignore-rule mechanism, and nothing at all. `CON-03`'s tracked half needs git, so those fixtures are
copied into a temporary git repository — never the audit repo. `CON-04` is an emitter, asserted end
to end: the draft is written outside the target, is deterministic, and is absent unless requested.
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

CON_CHECKS = ("CON-01", "CON-02", "CON-03", "CON-04")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class ConFixtureTests(unittest.TestCase):
    def test_con02_fixture_fails_exactly_its_check(self):
        report = support.run_audit(support.fixture("con-02-unprotected-tests"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["CON-02"], "FAIL")
        failing = sorted(cid for cid in CON_CHECKS if verdicts[cid] == "FAIL")
        self.assertEqual(failing, ["CON-02"], f"unexpected CON FAILs {failing}")

    def test_con03_fixture_fails_exactly_its_check(self):
        report = support.run_audit(support.fixture("con-03-artefacts-not-ignored"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["CON-03"], "FAIL")
        failing = sorted(cid for cid in CON_CHECKS if verdicts[cid] == "FAIL")
        self.assertEqual(failing, ["CON-03"], f"unexpected CON FAILs {failing}")

    def test_con01_stays_blocked(self):
        report = support.run_audit(support.fixture("con-02-unprotected-tests"))
        check = next(c for c in report["checks"] if c["id"] == "CON-01")
        self.assertEqual(check["status"], "blocked")
        self.assertEqual(check["verdict"], "UNKNOWN")


class Con02Tests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            (root / "tests").mkdir(exist_ok=True)
            support.write(root, "tests/test_app.py", "def test_x():\n    assert True\n")
            return support.run_audit(root)

    def test_dedicated_constraint_file_denying_tests_passes(self):
        report = self._scan({".cursorignore": "tests/\nnode_modules/\n"})
        self.assertEqual(support.verdicts(report)["CON-02"], "PASS")

    def test_no_constraint_file_but_ignore_rule_is_partial(self):
        report = self._scan({".gitignore": "tests/\nnode_modules/\n"})
        check = next(c for c in report["checks"] if c["id"] == "CON-02")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("ignore rules", check["summary"])

    def test_no_protection_at_all_is_unknown_never_pass(self):
        report = self._scan({"app.py": "print(1)\n"})
        self.assertEqual(support.verdicts(report)["CON-02"], "UNKNOWN")

    def test_no_test_directory_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "app.py", "print(1)\n")
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CON-02"], "UNKNOWN")


class Con03Tests(unittest.TestCase):
    def _repo(self, *, tracked_scratch: bool, ignore: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "repo"
        shutil.copytree(support.fixture("con-03-artefacts-not-ignored"), target)
        (target / ".gitignore").write_text(ignore, encoding="utf-8")
        self.assertEqual(_git(target, "init").returncode, 0)
        self.assertEqual(_git(target, "add", "-A").returncode, 0)
        if tracked_scratch:
            self.assertEqual(_git(target, "add", "-f", "artefacts/notes.md").returncode, 0)
        return target

    IGNORE = "artefacts/\nartifacts/\n.codebase-memory/\n.opencode/\n.agentic-tdd/\n"

    def test_covered_and_untracked_passes(self):
        report = support.run_audit(self._repo(tracked_scratch=False, ignore=self.IGNORE))
        self.assertEqual(support.verdicts(report)["CON-03"], "PASS")

    def test_force_added_scratch_file_fails(self):
        report = support.run_audit(self._repo(tracked_scratch=True, ignore=self.IGNORE))
        self.assertEqual(support.verdicts(report)["CON-03"], "FAIL")

    def test_covered_but_git_unavailable_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, ".gitignore", self.IGNORE)
            support.write(root, "artefacts/notes.md", "# scratch\n")
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CON-03"], "UNKNOWN")


class Con04EmitterTests(unittest.TestCase):
    def _target(self, root: Path) -> Path:
        target = root / "target"
        support.write(target, "src/app.py", "print(1)\n")
        support.write(target, "tests/test_app.py", "def test_x():\n    assert True\n")
        support.write(target, "migrations/001_init.sql", "CREATE TABLE t;\n")
        support.write(target, "dist/app.min.js", "min\n")
        support.write(target, "infra/main.tf", 'resource "x" "y" {}\n')
        support.write(target, "env/prod/config.yaml", "x: 1\n")
        support.write(target, ".env", "SECRET=value\n")
        return target

    def test_draft_is_written_beside_the_report_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = root / "out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
            self.assertEqual(proc.returncode, 0, proc.stderr)

            draft = out.parent / "constraints.draft.yaml"
            self.assertTrue(draft.is_file(), "the emitter produced no draft")
            self.assertFalse(draft.resolve().is_relative_to(target.resolve()),
                             "the emitter wrote inside the target")

            text = draft.read_text(encoding="utf-8")
            for section in ("deny:", "secrets:", "migrations:", "generated:", "tests:", "iac:",
                            "production:", "allow:"):
                self.assertIn(section, text)

            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "PASS")
            self.assertIn(str(draft), check["summary"])

    def test_emitter_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            drafts = []
            for index in range(2):
                out = root / f"out-{index}" / "report.json"
                support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
                drafts.append((out.parent / "constraints.draft.yaml").read_text(encoding="utf-8"))
            self.assertEqual(drafts[0], drafts[1])

    def test_no_draft_without_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = root / "out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((out.parent / "constraints.draft.yaml").exists())
            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "UNKNOWN")

    def test_refuses_to_emit_inside_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = target / "audit-out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((target / "audit-out" / "constraints.draft.yaml").exists())
            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
