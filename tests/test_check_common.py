"""Tests for the private cross-pack helpers (``audit.rules.checks._common``)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                       # noqa: E402
from audit.rules.checks._common import (                             # noqa: E402
    extract_fenced_commands, resolve_verbs,
)
from audit.scan import build_inventory                               # noqa: E402
from audit.stack import detect_stack                                 # noqa: E402


class ResolveVerbsTests(unittest.TestCase):
    def _verbs(self, files: dict[str, str]):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        return resolve_verbs(inventory, detect_stack(inventory))

    def test_npm_scripts_resolve_with_runner_command_and_argv(self):
        verbs = self._verbs({"package.json": json.dumps(
            {"name": "x", "scripts": {"lint": "eslint .", "test": "vitest run"}})})
        self.assertEqual(verbs["lint"].runner, "package.json")
        self.assertEqual(verbs["lint"].command, "eslint .")
        self.assertEqual(verbs["lint"].argv, ("eslint", "."))
        self.assertEqual(verbs["test"].argv, ("vitest", "run"))

    def test_makefile_targets_resolve(self):
        verbs = self._verbs({"Makefile": "test:\n\tpytest -q\n\nlint:\n\truff check .\n"})
        self.assertEqual(verbs["test"].runner, "Makefile")
        self.assertEqual(verbs["test"].command, "pytest -q")
        self.assertEqual(verbs["lint"].command, "ruff check .")

    def test_taskfile_cmd_and_cmds_resolve(self):
        verbs = self._verbs({"Taskfile.yml": (
            "version: '3'\n"
            "tasks:\n"
            "  test:\n"
            "    cmds:\n"
            "      - pytest -q\n"
            "  lint:\n"
            "    cmd: ruff check .\n"
        )})
        self.assertEqual(verbs["test"].runner, "Taskfile.yml")
        self.assertEqual(verbs["test"].command, "pytest -q")
        self.assertEqual(verbs["lint"].command, "ruff check .")

    def test_pyproject_tool_tasks_resolve(self):
        verbs = self._verbs({"pyproject.toml": (
            "[project]\n"
            'name = "x"\n'
            "[tool.poe.tasks]\n"
            'test = "pytest -q"\n'
            'lint = { cmd = "ruff check ." }\n'
        )})
        self.assertEqual(verbs["test"].runner, "pyproject.toml")
        self.assertEqual(verbs["test"].command, "pytest -q")
        self.assertEqual(verbs["lint"].command, "ruff check .")

    def test_only_declared_verbs_are_returned(self):
        verbs = self._verbs({"package.json": json.dumps({"scripts": {"lint": "eslint ."}})})
        self.assertEqual(set(verbs), {"lint"})


class ExtractFencedCommandsTests(unittest.TestCase):
    def test_shell_blocks_yield_commands_with_line_numbers(self):
        text = (
            "intro\n"
            "```bash\n"
            "$ npm run lint\n"
            "npm test\n"
            "# a comment\n"
            "```\n"
        )
        self.assertEqual(
            extract_fenced_commands(text),
            [("bash", 3, "npm run lint"), ("bash", 4, "npm test")],
        )

    def test_console_output_lines_are_skipped(self):
        text = "```console\n$ npm run build\nadded 3 packages\n```\n"
        self.assertEqual(extract_fenced_commands(text), [("console", 2, "npm run build")])

    def test_non_shell_fences_are_ignored(self):
        text = '```json\n{"a": 1}\n```\n```python\nprint("x")\n```\n'
        self.assertEqual(extract_fenced_commands(text), [])


if __name__ == "__main__":
    unittest.main()
