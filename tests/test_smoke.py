"""Smoke and contract tests — stdlib ``unittest``, so the suite runs with no install step.

    python3 -m unittest discover -s tests -v

The suite deliberately starts with the pieces that are implemented (scan, variant classifier, AGT
pack) and with the two structural invariants that are cheap to check and expensive to discover
broken: determinism, and the zipapp entry-point contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

import support                                                           # noqa: E402
from audit.rules import variants as V                                     # noqa: E402
from audit.rules.registry import REGISTRY, ruleset_hash                   # noqa: E402
from audit.scan import Kind, build_inventory                              # noqa: E402
from audit.stack import detect_stack                                      # noqa: E402


class CatalogueContractTests(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [spec.id for spec in REGISTRY]
        self.assertEqual(len(ids), len(set(ids)), "duplicate check ids in the registry")

    def test_catalogue_size_matches_the_documented_counts(self):
        from audit.rules.registry import informational, scoreable
        self.assertEqual(len(REGISTRY), 69, "catalogue drifted from the documented 69 rows")
        self.assertEqual(len(scoreable()), 54, "scoreable count drifted from the documented 54")
        self.assertEqual(len(informational()), 15, "informational count drifted from 15")

    def test_every_spec_has_a_tier(self):
        for spec in REGISTRY:
            self.assertIn(spec.tier, ("A", "B", "C", "—"), f"{spec.id} has tier {spec.tier!r}")

    def test_ruleset_hash_is_stable_within_a_run(self):
        self.assertEqual(ruleset_hash(), ruleset_hash())
        self.assertEqual(len(ruleset_hash()), 16)


class VariantTableTests(unittest.TestCase):
    def test_every_harness_carries_a_doc_url(self):
        for harness in V.HARNESSES:
            self.assertTrue(harness.doc_url.startswith("http"), f"{harness.tool} has no doc URL")

    def test_canonical_file_is_reported_as_canonical(self):
        result = V.classify_present({"AGENTS.md"})
        self.assertEqual(result["canonical"], ["AGENTS.md"])

    def test_vendor_only_repository_is_not_called_governed(self):
        result = V.classify_present({"CLAUDE.md"})
        self.assertEqual(result["canonical"], [])
        self.assertIn("Anthropic Claude Code", result["harnesses_reached"])

    def test_mis_cased_canonical_is_detected(self):
        self.assertEqual(V.mis_cased_canonical_candidates({"agents.md"}), ["agents.md"])

    def test_override_is_not_counted_as_canonical(self):
        result = V.classify_present({"AGENTS.md", "AGENTS.override.md"})
        self.assertEqual(result["overrides"], ["AGENTS.override.md"])

    def test_nested_canonical_file_is_coverage_not_a_competitor(self):
        result = V.classify_present({"AGENTS.md", "packages/api/AGENTS.md"})
        self.assertEqual(result["canonical"], ["AGENTS.md", "packages/api/AGENTS.md"])
        self.assertEqual(result["vendor_only"], [])


class ScanEngineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        support.write(self.root, "AGENTS.md", "# Rules\n\n" + "Always run the tests.\n" * 40)
        support.write(self.root, "src/app.py", "print('hi')\n")
        support.write(self.root, "node_modules/dep/index.js", "module.exports = 1\n")
        support.write(self.root, ".gitignore", "node_modules\n.env\n")
        (self.root / "bin.dat").write_bytes(b"\x00\x01\x02")

    def tearDown(self):
        self._tmp.cleanup()

    def test_hard_excluded_directories_are_not_walked(self):
        inv = build_inventory(self.root)
        self.assertFalse(any(f.rel.startswith("node_modules/") for f in inv.files))

    def test_binary_files_are_inventoried_without_text(self):
        inv = build_inventory(self.root)
        entry = next(f for f in inv.files if f.rel == "bin.dat")
        self.assertIs(entry.kind, Kind.BINARY)
        self.assertFalse(entry.has_text)

    def test_content_read_is_available_for_text(self):
        inv = build_inventory(self.root)
        self.assertIn("Always run the tests.", inv.read("AGENTS.md") or "")

    def test_grep_reports_path_and_line(self):
        inv = build_inventory(self.root)
        hits = inv.grep(r"run the tests")
        self.assertEqual(hits[0][0], "AGENTS.md")
        self.assertEqual(hits[0][1], 3)

    def test_stack_detection_reports_unknown_rather_than_guessing(self):
        stack = detect_stack(build_inventory(self.root))
        self.assertEqual(stack.ecosystems, set())
        self.assertTrue(stack.notes)


class AgtPackTests(unittest.TestCase):
    """The AGT pack is the first implemented family; it is also the harness-behaviour canary."""

    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root)

    def test_repository_without_instruction_file_fails_agt01(self):
        report = self._scan({"src/app.py": "print(1)\n"})
        findings = {f["check"] for f in report["findings"]}
        self.assertIn("AGT-01", findings)

    def test_governed_repository_passes_agt01(self):
        report = self._scan({"AGENTS.md": "# Rules\n\n" + "Run the tests before every commit.\n" * 40})
        verdicts = {c["id"]: c["verdict"] for c in report["checks"]}
        self.assertEqual(verdicts["AGT-01"], "PASS")

    def test_alias_only_repository_is_partial_not_pass(self):
        report = self._scan({"AGENT.md": "# Rules\n\n" + "Run the tests.\n" * 40})
        verdicts = {c["id"]: c["verdict"] for c in report["checks"]}
        self.assertEqual(verdicts["AGT-01"], "PARTIAL")

    def test_deferring_instruction_file_fails_agt10(self):
        report = self._scan({
            "AGENTS.md": "# Rules\n\nfirst read and understand the existing conventions "
                         "(CONVENTIONS.md)\n" * 20,
            "CONVENTIONS.md": "# Conventions\n\n" + "Use tabs.\n" * 40,
        })
        verdicts = {c["id"]: c["verdict"] for c in report["checks"]}
        self.assertEqual(verdicts["AGT-10"], "FAIL")

    def test_an_unimplemented_check_is_unknown_never_pass(self):
        # Every catalogue check is implemented today, so the no-pass-by-omission guard is exercised
        # at the mechanism: a spec with no implementation must report UNKNOWN, never PASS.
        from audit.findings import Severity, Verdict
        from audit.rules.registry import CheckSpec

        spec = CheckSpec(id="ZZZ-01", title="hypothetical", tier="A",
                         severity=Severity.COSMETIC, evidence_rule="", status="planned")
        outcome = spec.run(target=None, inventory=None, stack=None, components=None, session=None)
        self.assertEqual(outcome.verdict, Verdict.UNKNOWN)
        self.assertEqual(outcome.status, "planned")


class DeterminismTests(unittest.TestCase):
    def test_two_runs_differ_only_in_provenance_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "AGENTS.md", "# Rules\n\n" + "Run the tests.\n" * 40)
            support.write(root, "package.json", json.dumps({"name": "x", "scripts": {"test": "vitest"}}))
            first = support.run_audit(root)
            second = support.run_audit(root)

        for report in (first, second):
            report["provenance"].pop("scanned_at", None)
        self.assertEqual(first, second, "the report is not deterministic")


class ZipappContractTests(unittest.TestCase):
    def test_archive_builds_and_runs(self):
        build = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "build.py")],
                               cwd=str(REPO_ROOT), text=True, capture_output=True)
        self.assertEqual(build.returncode, 0, build.stderr)

        archive = REPO_ROOT / "dist" / "audit.pyz"
        self.assertTrue(archive.is_file())

        run = subprocess.run([str(archive), "--list-checks"], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("checks catalogued", run.stdout)


if __name__ == "__main__":
    unittest.main()
