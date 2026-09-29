"""The positive fixture: a freshly scaffolded project must not fail the implemented checks.

``python-agentic-bootstrap``'s scaffold is Phase-1-complete by construction, so it is the natural
positive fixture for this audit. It is **generated in the test run, never vendored**: a vendored copy
stops being evidence the moment the scaffolder changes. If a scaffold ever fails a **scoreable**
check, one of the two tools is wrong — that is a defect, not a false positive to tune away. The
informational checks (`HYG`, `NAV-04`/`05`) are reported but never scored, and the scaffold
deliberately leaves a license, branch protection and release automation to the adopter, so they are
outside this contract.

The scaffolder is located from ``AUDIT_BOOTSTRAP`` or the known sibling path. When it is absent the
test **fails loudly** rather than skipping (AGENTS.md §10.13 forbids weakening a test to get green).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                           # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID                          # noqa: E402

SCAFFOLDER_ENV = "AUDIT_BOOTSTRAP"
KNOWN_SCAFFOLDER = (Path.home() / "Projects" / "Nistapp-agentic-frameworks" / "agentic-bootstrap"
                    / "python-agentic-bootstrap" / "bootstrap.py")

#: The IDX checks assert properties of the operator's harness and index store, not repository
#: content: a freshly generated scaffold in a temporary directory carries no project-level MCP
#: config and no persistent index. They are exercised against constructed stores in
#: ``test_idx_pack.py``, so the content fixture does not assert them.
ENVIRONMENT_SCOPED = frozenset({"IDX-01", "IDX-02", "IDX-03"})


def locate_scaffolder() -> Path:
    override = os.environ.get(SCAFFOLDER_ENV)
    return Path(override).expanduser() if override else KNOWN_SCAFFOLDER


class PositiveFixtureTests(unittest.TestCase):
    def test_generated_scaffold_fails_no_implemented_check(self):
        scaffolder = locate_scaffolder()
        if not scaffolder.is_file():
            self.fail(
                f"scaffolder not found at {scaffolder}. The positive fixture is generated, never "
                f"vendored, and must not be skipped; set {SCAFFOLDER_ENV} to bootstrap.py."
            )

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "scaffold"
            target.mkdir()
            proc = subprocess.run(
                [sys.executable, str(scaffolder), str(target), "--no-git"],
                text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, f"scaffolder failed:\n{proc.stderr}")

            # run_audit asserts exit 0 — a completed scan reports; it does not gate.
            report = support.run_audit(target)

        implemented = {c["id"] for c in report["checks"] if c["status"] == "implemented"}
        implemented -= ENVIRONMENT_SCOPED
        self.assertTrue(implemented, "no implemented checks ran; the harness is not exercising anything")

        # The positive-fixture contract is about readiness: a scaffold must score 1.0 with zero
        # blockers. Informational checks (HYG, NAV-04/05) are reported but never scored, and the
        # scaffold deliberately leaves a license, branch protection and release automation to the
        # adopter — so they are out of scope for this assertion by construction.
        scoreable = {check for check in implemented if REGISTRY_BY_ID[check].scored}

        verdicts = support.verdicts(report)
        failing = sorted(check for check in scoreable if verdicts[check] == "FAIL")
        self.assertEqual(failing, [], f"a freshly scaffolded project fails {failing}")

        blockers = [f for f in report["findings"]
                    if f["check"] in scoreable and f["severity"] == "BLOCKER"]
        self.assertEqual(blockers, [], f"BLOCKER findings among scoreable checks: {blockers}")

        # Informational checks are still reported, not dropped from the report.
        reported = {c["id"] for c in report["checks"]}
        informational = {"HYG-%02d" % n for n in range(1, 12)} | {"NAV-04", "NAV-05"}
        self.assertTrue(informational <= reported, f"informational checks missing: {informational - reported}")


if __name__ == "__main__":
    unittest.main()
