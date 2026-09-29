"""HYG checks against their fixtures, and the invariant that they never move the score.

The `HYG` pack is informational: every check returns a real `CheckOutcome` so a reader sees the
whole picture, but no `HYG` verdict may enter `summary.phase1_score` or the blocker count. `HYG-07`
is the only time-sensitive rule; it dates the changelog from the repository's own git history and
returns `UNKNOWN` when git cannot answer, so these fixtures never need git.

`ScoreIsolationTests` proves the invariant twice: once in-process over the `AuditResult.score`
property, and once end to end by flipping a single `HYG` verdict while every scoreable check sees
exactly the same repository truth.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

from audit.evaluate import AuditResult, CheckOutcome                     # noqa: E402
from audit.findings import Severity, Verdict                             # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID                          # noqa: E402

HYG_IDS = tuple(f"HYG-{n:02d}" for n in range(1, 12))

#: fixture directory -> {check id: expected verdict}
FIXTURES: dict[str, dict[str, str]] = {
    "hyg-01-placeholder-readme": {"HYG-01": "FAIL", "HYG-10": "FAIL"},
    "hyg-10-no-license": {"HYG-01": "PASS", "HYG-10": "FAIL"},
    "hyg-minimal": {
        "HYG-01": "FAIL", "HYG-02": "FAIL", "HYG-03": "FAIL", "HYG-04": "FAIL",
        "HYG-05": "FAIL", "HYG-06": "FAIL", "HYG-07": "FAIL", "HYG-08": "FAIL",
        "HYG-09": "FAIL", "HYG-10": "FAIL", "HYG-11": "UNKNOWN",
    },
}


class HygFixtureTests(unittest.TestCase):
    def test_each_fixture_reports_its_documented_verdict(self):
        for name, expected in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                for check, verdict in expected.items():
                    self.assertEqual(verdicts[check], verdict, f"{name}: {check}")

    def test_placeholder_readme_is_rejected_as_a_stub(self):
        report = support.run_audit(support.fixture("hyg-01-placeholder-readme"))
        check = next(c for c in report["checks"] if c["id"] == "HYG-01")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("placeholder", check["detail"])

    def test_missing_license_names_the_root(self):
        report = support.run_audit(support.fixture("hyg-10-no-license"))
        check = next(c for c in report["checks"] if c["id"] == "HYG-10")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("license", check["detail"].lower())

    def test_branch_protection_is_unknown_without_a_recognised_provider(self):
        report = support.run_audit(support.fixture("hyg-minimal"))
        self.assertEqual(support.verdicts(report)["HYG-11"], "UNKNOWN")


class HygCatalogueTests(unittest.TestCase):
    def test_all_eleven_are_implemented_and_informational(self):
        for check in HYG_IDS:
            with self.subTest(check=check):
                spec = REGISTRY_BY_ID[check]
                self.assertFalse(spec.scored, f"{check} must never be scored")
                self.assertEqual(spec.status, "implemented", f"{check} status")

    def test_report_lists_hyg_checks_but_excludes_them_from_the_scoreable_count(self):
        report = support.run_audit(support.fixture("hyg-minimal"))
        reported = {c["id"] for c in report["checks"]}
        for check in HYG_IDS:
            self.assertIn(check, reported)
        # 69 catalogued, one blocked (CON-01), 14 informational/emitter-only ⇒ 54 scoreable.
        self.assertEqual(report["summary"]["checks_scoreable"], 54)


class ScoreIsolationTests(unittest.TestCase):
    def test_informational_outcomes_do_not_enter_auditresult_score(self):
        scored = CheckOutcome("DOC-01", "docs", "A", Severity.DEGRADER, 1,
                              Verdict.PASS, "implemented")

        def score_with(hyg_verdict: Verdict) -> float:
            info = CheckOutcome("HYG-01", "readme", "A", Severity.COSMETIC, 1,
                                hyg_verdict, "implemented")
            return AuditResult(None, None, None, None, [scored, info]).score

        baseline = AuditResult(None, None, None, None, [scored]).score
        self.assertEqual(score_with(Verdict.PASS), baseline)
        self.assertEqual(score_with(Verdict.FAIL), baseline)
        self.assertEqual(score_with(Verdict.UNKNOWN), baseline)

    def test_flipping_a_hyg_verdict_end_to_end_leaves_the_score_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "src/app.py", "print('hi')\n")
            support.write(root, "README.md", "# Stub\n\nTODO: write this README.\n")
            before = support.run_audit(root)
            self.assertEqual(support.verdicts(before)["HYG-01"], "FAIL")

            # Rewrite only the README with prose (no fenced commands, so no scoreable check sees a
            # difference) until the informational verdict flips.
            support.write(
                root, "README.md",
                "# Widget Service\n\nWidget Service exposes a small HTTP API for managing widgets. "
                "It is written for teams that need a dependable, boring service they can extend "
                "without reading the whole repository first.\n\n## Running it\n\nInstall Python "
                "3.11 or newer, then start the service from a checkout. Configuration lives in "
                "environment variables documented in the example environment file.\n",
            )
            after = support.run_audit(root)
            self.assertEqual(support.verdicts(after)["HYG-01"], "PASS")

        self.assertEqual(before["summary"]["phase1_score"], after["summary"]["phase1_score"])
        self.assertEqual(before["summary"]["blockers"], after["summary"]["blockers"])


if __name__ == "__main__":
    unittest.main()
