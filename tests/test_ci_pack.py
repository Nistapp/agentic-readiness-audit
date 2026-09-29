"""CI checks against their one-defect fixtures.

Each fixture is a small node project plus a GitHub workflow that isolates one CI defect;
`ci-ok-gh` passes all three. The inline cases cover the `UNKNOWN` floor (no local verbs), a
non-GitHub PR trigger, and the minimal YAML scan reading a block-scalar step.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

CI_CHECKS = ("CI-01", "CI-02", "CI-03")

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "ci-01-no-pr-trigger": ("CI-01", "PARTIAL"),
    "ci-02-parity-break": ("CI-02", "FAIL"),
    "ci-03-ci-only-step": ("CI-03", "FAIL"),
}


class CiFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in CI_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing,
                                 f"{name}: unexpected CI FAILs {failing}")

    def test_positive_fixture_passes_all_three(self):
        report = support.run_audit(support.fixture("ci-ok-gh"))
        verdicts = support.verdicts(report)
        for check in CI_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"ci-ok-gh: {check}")


class CiInlineTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root)

    def test_no_workflow_is_a_fail(self):
        report = self._scan({"package.json": '{"scripts": {"check": "true"}}'})
        self.assertEqual(support.verdicts(report)["CI-01"], "FAIL")

    def test_ci_without_local_verbs_is_unknown_not_pass(self):
        report = self._scan({
            ".github/workflows/ci.yml": "on:\n  pull_request:\njobs:\n  b:\n    steps:\n"
                                        "      - run: npm run check\n",
        })
        self.assertEqual(support.verdicts(report)["CI-02"], "UNKNOWN")

    def test_gitlab_merge_request_trigger_counts(self):
        report = self._scan({
            ".gitlab-ci.yml": ("test:\n  script:\n    - npm run check\n"
                               "  rules:\n    - if: $CI_MERGE_REQUEST_IID\n"),
            "package.json": '{"scripts": {"check": "true"}}',
        })
        self.assertEqual(support.verdicts(report)["CI-01"], "PASS")

    def test_block_scalar_step_is_parsed(self):
        report = self._scan({
            ".github/workflows/ci.yml": ("on:\n  pull_request:\njobs:\n  b:\n    steps:\n"
                                         "      - run: |\n          npm ci\n          npm run check\n"),
            "package.json": '{"scripts": {"check": "true"}}',
        })
        self.assertEqual(support.verdicts(report)["CI-02"], "PASS")
        self.assertEqual(support.verdicts(report)["CI-03"], "PASS")


if __name__ == "__main__":
    unittest.main()
