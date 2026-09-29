"""AGT content-contract checks (AGT-03, 04, 06, 07, 09) against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly one check; `governed-minimal` passes all
five. The audit is run as a subprocess through `tests/support.py`, so the fixtures exercise the real
end-to-end path, not the check functions in isolation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "agt-03-incomplete": ("AGT-03", "PARTIAL"),
    "agt-04-missing": ("AGT-04", "FAIL"),
    "agt-06-thin": ("AGT-06", "PARTIAL"),
    "agt-07-missing-deny": ("AGT-07", "PARTIAL"),
    "agt-09-no-release": ("AGT-09", "PARTIAL"),
}

CONTENT_CHECKS = ("AGT-03", "AGT-04", "AGT-06", "AGT-07", "AGT-09")
AGT_CHECKS = tuple(f"AGT-{i:02d}" for i in range(1, 11))


class AgtFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = {cid for cid in AGT_CHECKS if verdicts[cid] == "FAIL"}
                expected_failing = {check} if expected == "FAIL" else set()
                self.assertEqual(failing, expected_failing,
                                 f"{name}: unexpected AGT content FAILs {failing - expected_failing}")

    def test_governed_minimal_passes_all_five(self):
        report = support.run_audit(support.fixture("governed-minimal"))
        verdicts = support.verdicts(report)
        for check in CONTENT_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"governed-minimal: {check}")


if __name__ == "__main__":
    unittest.main()
