"""TOOL tooling checks against their one-defect fixtures.

Every fixture is a small node project that fails exactly one TOOL check (or returns `PARTIAL` for the
non-strict and unwired-hooks cases); `tool-ok-node` passes all six. The inline cases cover the
verdicts the fixtures deliberately avoid — a config with no verb, a `security` verb that runs no
audit, `core.hooksPath` wiring, and the no-ecosystem `UNKNOWN` floor.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

TOOL_CHECKS = ("TOOL-01", "TOOL-02", "TOOL-03", "TOOL-04", "TOOL-05", "TOOL-06")

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "tool-01-no-formatter": ("TOOL-01", "FAIL"),
    "tool-02-no-linter": ("TOOL-02", "FAIL"),
    "tool-03-nonstrict-ts": ("TOOL-03", "PARTIAL"),
    "tool-04-no-audit-verb": ("TOOL-04", "FAIL"),
    "tool-05-unwired-hooks": ("TOOL-05", "PARTIAL"),
    "tool-06-no-commit-rule": ("TOOL-06", "FAIL"),
}


class ToolFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in TOOL_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing,
                                 f"{name}: unexpected TOOL FAILs {failing}")

    def test_positive_fixture_passes_all_six(self):
        report = support.run_audit(support.fixture("tool-ok-node"))
        verdicts = support.verdicts(report)
        for check in TOOL_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"tool-ok-node: {check}")


class ToolInlineTests(unittest.TestCase):
    """Cases where the verdict is the point and a whole fixture directory would be noise."""

    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root)

    def test_formatter_config_without_a_verb_is_partial(self):
        report = self._scan({".prettierrc.json": '{"singleQuote": true}\n'})
        self.assertEqual(support.verdicts(report)["TOOL-01"], "PARTIAL")

    def test_security_verb_that_runs_no_audit_is_partial(self):
        report = self._scan({"package.json": '{"scripts": {"security": "echo checked"}}'})
        self.assertEqual(support.verdicts(report)["TOOL-04"], "PARTIAL")

    def test_core_hookspath_wires_the_chain(self):
        report = self._scan({
            "package.json": '{"scripts": {"prepare": "git config core.hooksPath .githooks"}}',
            ".githooks/pre-commit": "#!/bin/sh\n",
        })
        self.assertEqual(support.verdicts(report)["TOOL-05"], "PASS")

    def test_python_strict_mypy_is_pass(self):
        report = self._scan({
            "pyproject.toml": "[tool.mypy]\nstrict = true\n",
        })
        self.assertEqual(support.verdicts(report)["TOOL-03"], "PASS")

    def test_no_ecosystem_and_no_config_is_unknown_not_fail(self):
        report = self._scan({"notes.txt": "nothing executable here\n"})
        verdicts = support.verdicts(report)
        for check in TOOL_CHECKS:
            self.assertIn(verdicts[check], ("UNKNOWN", "PASS"), f"{check} guessed")


if __name__ == "__main__":
    unittest.main()
