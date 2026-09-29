"""CMD command-surface checks and the deferred AGT-05 against their one-defect fixtures.

Each defect fixture is a minimal repository that fails exactly one `CMD` check; the two `cmd-ok-*`
fixtures prove runner-independence by resolving all seven verbs on, respectively, npm scripts and a
Makefile. The audit runs as a subprocess through `tests/support.py`, so the fixtures exercise the
real end-to-end path.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "cmd-01-missing-verb": ("CMD-01", "FAIL"),
    "cmd-02-weak-check": ("CMD-02", "FAIL"),
    "cmd-03-divergent": ("CMD-03", "FAIL"),
    "cmd-04-write-in-check": ("CMD-04", "FAIL"),
}

CMD_CHECKS = ("CMD-01", "CMD-02", "CMD-03", "CMD-04")

VERBS = ("format", "format:check", "lint", "typecheck", "test", "check", "security")


class CmdFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in CMD_CHECKS if verdicts[cid] == "FAIL")
                self.assertEqual(failing, [check],
                                 f"{name}: unexpected CMD FAILs {failing}")

    def test_all_seven_verbs_on_one_runner_passes_for_npm_and_make(self):
        # Two runners, the same seven verbs: CMD-01 must pass on both. This is the check that the
        # implementation is runner-independent rather than npm-specific.
        for name in ("cmd-ok-npm", "cmd-ok-make"):
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                for check in CMD_CHECKS:
                    self.assertEqual(verdicts[check], "PASS", f"{name}: {check}")

    def test_write_in_check_names_the_write_verb(self):
        report = support.run_audit(support.fixture("cmd-04-write-in-check"))
        findings = [f for f in report["findings"] if f["check"] == "CMD-04"]
        self.assertTrue(findings, "CMD-04 failed without emitting a finding")
        self.assertIn("format", findings[0]["statement"].lower())


class CmdUnknownTests(unittest.TestCase):
    def test_no_runner_is_unknown_never_fail(self):
        # An unrecognised ecosystem is not proof that the verb surface is absent.
        report = support.run_audit(support.fixture("agt-05-verbs-named-not-resolved"))
        verdicts = support.verdicts(report)
        for check in CMD_CHECKS:
            self.assertEqual(verdicts[check], "UNKNOWN", check)

    def test_check_that_composes_only_some_verbs_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "package.json", (
                '{"name":"partial","scripts":{"format":"prettier --write .",'
                '"format:check":"prettier --check .","lint":"eslint .",'
                '"typecheck":"tsc --noEmit","test":"vitest run",'
                '"check":"npm run typecheck && npm test",'
                '"security":"npm audit"}}'))
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CMD-02"], "PARTIAL")


class Agt05Tests(unittest.TestCase):
    def test_named_without_a_runner_is_partial_not_fail(self):
        report = support.run_audit(support.fixture("agt-05-verbs-named-not-resolved"))
        self.assertEqual(support.verdicts(report)["AGT-05"], "PARTIAL")

    def test_named_and_resolved_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "AGENTS.md", (
                "# Rules\n\n" + "Always run the tests before committing.\n" * 20
                + "\nVerbs: " + ", ".join(VERBS) + "\n"))
            support.write(root, "package.json", (
                '{"name":"x","scripts":{"format":"prettier --write .",'
                '"format:check":"prettier --check .","lint":"eslint .",'
                '"typecheck":"tsc --noEmit","test":"vitest run",'
                '"check":"npm run format:check && npm run typecheck && npm test",'
                '"security":"npm audit"}}'))
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["AGT-05"], "PASS")


if __name__ == "__main__":
    unittest.main()
