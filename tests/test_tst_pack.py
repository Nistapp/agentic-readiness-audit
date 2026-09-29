"""TST test-surface checks against their one-defect fixtures.

Each fixture is a small node project that isolates one TST defect; the inline cases cover the
verdict floors and the probe contract. `tst-03-skip-markers` is a census, so it passes with a
non-zero count rather than failing — the test asserts the count, not a threshold.

The probe (`TST-02`) is exercised twice: refused by default (the audit must run no probe unless
`--run-gates` + `--allow-probe` are passed), and permitted against a trivially safe temp repo. The
target's real test runner is never invoked outside a temp fixture.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

TST_CHECKS = ("TST-01", "TST-02", "TST-03", "TST-04", "TST-05")

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "tst-01-no-suite": ("TST-01", "PARTIAL"),
    "tst-04-no-fastpath": ("TST-04", "FAIL"),
    "tst-05-no-coverage": ("TST-05", "FAIL"),
}


class TstFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in TST_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing,
                                 f"{name}: unexpected TST FAILs {failing}")

    def test_skip_marker_fixture_is_a_nonzero_census(self):
        report = support.run_audit(support.fixture("tst-03-skip-markers"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["TST-03"], "PASS")

        detail = next(c["detail"] for c in report["checks"] if c["id"] == "TST-03")
        self.assertIn("total 3", detail, f"census did not count the markers: {detail}")


class TstInlineTests(unittest.TestCase):
    def _scan(self, files: dict[str, str], *, extra_args: tuple[str, ...] = ()) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root, extra_args=extra_args)

    def test_suite_without_a_verb_is_partial(self):
        report = self._scan({"test/app.test.ts": "import { it } from 'vitest';\n"})
        self.assertEqual(support.verdicts(report)["TST-01"], "PARTIAL")

    def test_no_verb_and_no_suite_in_a_known_ecosystem_is_fail(self):
        report = self._scan({"package.json": json.dumps({"scripts": {"lint": "eslint ."}})})
        self.assertEqual(support.verdicts(report)["TST-01"], "FAIL")

    def test_unrecognised_repository_is_unknown_not_fail(self):
        report = self._scan({"notes.txt": "nothing executable here\n"})
        self.assertEqual(support.verdicts(report)["TST-01"], "UNKNOWN")

    def test_fully_tooled_repository_passes_the_artifact_checks(self):
        report = self._scan({
            "package.json": json.dumps({"scripts": {"test": "vitest run --coverage"}}),
            "test/app.test.ts": "import { expect, it } from 'vitest';\n"
                                "it('adds', () => expect(1 + 1).toBe(2));\n",
            "README.md": "# x\n\n```bash\nnpx vitest run test/app.test.ts\n```\n",
        })
        verdicts = support.verdicts(report)
        for check in ("TST-01", "TST-03", "TST-04", "TST-05"):
            self.assertEqual(verdicts[check], "PASS", check)

    def test_coverage_config_file_is_pass(self):
        report = self._scan({".coveragerc": "[run]\nbranch = true\n"})
        self.assertEqual(support.verdicts(report)["TST-05"], "PASS")

    def test_fastpath_is_unknown_without_a_suite(self):
        report = self._scan({"README.md": "# x\n\n```bash\nnpm test -- foo\n```\n"})
        self.assertEqual(support.verdicts(report)["TST-04"], "UNKNOWN")

    def test_probe_is_refused_and_recorded_by_default(self):
        report = self._scan({"package.json": json.dumps({"scripts": {"test": "vitest run"}})})
        self.assertEqual(support.verdicts(report)["TST-02"], "UNKNOWN")

        probes = [p for p in report["probes"] if p["verb"] == "test"]
        self.assertTrue(probes, "the refused test probe is not recorded")
        self.assertIsNotNone(probes[0]["refused_reason"])
        self.assertIsNone(probes[0]["exit_code"])

    def test_permitted_probe_runs_a_safe_command_and_passes(self):
        report = self._scan(
            {"package.json": json.dumps({"scripts": {"test": "python3 -c \"pass\""}})},
            extra_args=("--run-gates", "--allow-probe", "test"),
        )
        self.assertEqual(support.verdicts(report)["TST-02"], "PASS")

        probes = [p for p in report["probes"] if p["verb"] == "test"]
        self.assertTrue(probes)
        self.assertEqual(probes[0]["exit_code"], 0)
        self.assertIsNone(probes[0]["refused_reason"])


if __name__ == "__main__":
    unittest.main()
