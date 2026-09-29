"""The baseline ratchet: exit 2 only on a finding the accepted baseline did not have.

The ratchet compares stable finding ids (`check id + path`), never counts or scores. These tests
exercise it end to end through the sanctioned command surface: emit a baseline, re-scan it clean
(exit 0), introduce one offending file, and assert the new finding id — and only it — is reported
and drives exit 2.
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


def _seeded_target(root: Path) -> Path:
    """A small, stable repository to baseline."""
    target = root / "target"
    target.mkdir()
    support.write(target, "AGENTS.md",
                  "# Rules\n\nAlways run the tests before every commit.\n" * 40)
    support.write(target, "package.json",
                  '{"name": "ratchet-target", "scripts": {"test": "vitest run"}}')
    return target


class RatchetTests(unittest.TestCase):
    def test_new_finding_is_reported_and_drives_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = _seeded_target(root)
            out_dir = root / "out"
            out_dir.mkdir()

            baseline = out_dir / "baseline.json"
            proc, _ = support.run_audit_process(target, out=baseline)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            baseline_ids = {f["id"] for f in json.loads(baseline.read_text())["findings"]}

            # A clean re-scan against its own baseline is not a regression.
            clean = out_dir / "clean.json"
            proc, _ = support.run_audit_process(target, out=clean,
                                                extra_args=("--baseline", str(baseline)))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(clean.read_text())["ratchet"]["regressions"], [])

            # One offending file: an unignored scratch directory. Both DOC-03 and CON-03 derive a
            # finding from it, so either (or both) may be the new id the ratchet reports.
            support.write(target, "artefacts/notes.md", "# scratch\n")

            current = out_dir / "current.json"
            proc, _ = support.run_audit_process(target, out=current,
                                                extra_args=("--baseline", str(baseline)))
            self.assertEqual(proc.returncode, 2, proc.stderr)

            report = json.loads(current.read_text())
            current_ids = {f["id"] for f in report["findings"]}
            expected = sorted(current_ids - baseline_ids)
            self.assertTrue(expected, "the offending file produced no new finding id")
            self.assertEqual(report["ratchet"]["regressions"], expected)
            self.assertTrue(all(fid.startswith(("DOC-03", "CON-03")) for fid in expected),
                            f"unexpected regressions: {expected}")

    def test_regression_list_is_sorted_and_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = _seeded_target(root)
            out_dir = root / "out"
            out_dir.mkdir()

            baseline = out_dir / "baseline.json"
            support.run_audit_process(target, out=baseline)
            support.write(target, "artefacts/notes.md", "# scratch\n")

            runs = []
            for index in range(2):
                current = out_dir / f"current-{index}.json"
                proc, _ = support.run_audit_process(target, out=current,
                                                    extra_args=("--baseline", str(baseline)))
                self.assertEqual(proc.returncode, 2, proc.stderr)
                runs.append(json.loads(current.read_text())["ratchet"]["regressions"])

            self.assertEqual(runs[0], runs[1])
            self.assertEqual(runs[0], sorted(runs[0]))

    def test_missing_baseline_is_a_reported_regression_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _seeded_target(Path(tmp))
            out = Path(tmp) / "report.json"
            missing = Path(tmp) / "nope.json"
            proc, _ = support.run_audit_process(target, out=out,
                                                extra_args=("--baseline", str(missing)))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            regressions = json.loads(out.read_text())["ratchet"]["regressions"]
            self.assertTrue(any("baseline not found" in entry for entry in regressions))

    def test_malformed_baseline_is_a_descriptive_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = _seeded_target(root)
            bad = root / "bad.json"
            bad.write_text("{ not json", encoding="utf-8")
            out = root / "report.json"
            proc, _ = support.run_audit_process(target, out=out,
                                                extra_args=("--baseline", str(bad)))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            regressions = json.loads(out.read_text())["ratchet"]["regressions"]
            self.assertEqual(len(regressions), 1)
            self.assertIn("baseline unreadable", regressions[0])


if __name__ == "__main__":
    unittest.main()