"""Report rendering tests — schema v2, the JSON↔Markdown contract.

The load-bearing property: the Markdown artifact is a pure function of the JSON report dict. These
tests render from the in-memory dict and from a JSON round-trip of that same dict and require the
two to be byte-identical, so a saved report can always be re-rendered.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support
from audit.report.md_writer import render_markdown_from_report

CHECK_KEYS = {"id", "pack", "title", "tier", "severity", "phase", "scored", "status",
              "verdict", "summary", "data"}


def _target() -> Path:
    """A throwaway repo with a runner (so CMD-01 has a surface) and a credential-shaped line."""
    tmp = Path(tempfile.mkdtemp(prefix="render-"))
    support.write(tmp, "package.json", json.dumps({
        "name": "demo",
        "scripts": {"format": "prettier --write .", "lint": "eslint .", "test": "jest"},
    }, indent=2))
    support.write(tmp, "src/a.ts", "export const apiKey = 'sk-abcdefghijklmnopqrstuvwxyz01';\n")
    return tmp


class SchemaV2Tests(unittest.TestCase):
    def test_schema_version_and_check_shape(self):
        report = support.run_audit(_target())
        self.assertEqual(report["schema_version"], "2")
        self.assertTrue(report["checks"])
        for check in report["checks"]:
            self.assertEqual(set(check.keys()), CHECK_KEYS, check["id"])

    def test_detail_is_gone(self):
        report = support.run_audit(_target())
        for check in report["checks"]:
            self.assertNotIn("detail", check)

    def test_structured_payloads_are_present(self):
        report = support.run_audit(_target())
        by_id = {c["id"]: c for c in report["checks"]}
        self.assertEqual(by_id["CMD-01"]["data"]["kind"], "verb_surface")
        self.assertEqual(by_id["SEC-02"]["data"]["kind"], "credential_matrix")
        self.assertTrue(by_id["SEC-02"]["data"]["total"] >= 1)


class RenderFromJsonTests(unittest.TestCase):
    def test_markdown_is_a_pure_function_of_the_report_dict(self):
        report = support.run_audit(_target())
        in_memory = render_markdown_from_report(report)
        round_tripped = render_markdown_from_report(json.loads(json.dumps(report)))
        self.assertEqual(in_memory, round_tripped)

    def test_render_is_deterministic(self):
        report = support.run_audit(_target())
        self.assertEqual(render_markdown_from_report(report),
                         render_markdown_from_report(report))

    def test_every_check_appears_in_the_appendix(self):
        report = support.run_audit(_target())
        markdown = render_markdown_from_report(report)
        for check in report["checks"]:
            self.assertIn(f"`{check['id']}`", markdown)

    def test_special_blocks_render_when_payloads_exist(self):
        report = support.run_audit(_target())
        markdown = render_markdown_from_report(report)
        self.assertIn("## Command surface", markdown)
        self.assertIn("## Credential-shaped lines", markdown)
        self.assertIn("## Missing secret-shape ignore rules", markdown)

    def test_unknown_ecosystem_omits_the_command_surface_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = support.run_audit(Path(tmp))
            markdown = render_markdown_from_report(report)
            self.assertNotIn("## Command surface", markdown)


if __name__ == "__main__":
    unittest.main()
