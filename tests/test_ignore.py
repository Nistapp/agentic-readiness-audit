"""Tests for the git-aware ignore engine (``audit.ignore``).

The temp git repository is created inside the test's own temporary directory — never the audit repo.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support                                                       # noqa: E402
from audit.ignore import (                                           # noqa: E402
    IgnoreRule, ignore_patterns, is_ignored, load_ignore_rules, matching_rules, tracked_files,
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class TrackedFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_tracked_set_on_a_real_repository(self):
        self.assertEqual(_git(self.root, "init").returncode, 0)
        support.write(self.root, "a.txt", "a\n")
        support.write(self.root, "src/b.py", "print(1)\n")
        self.assertEqual(_git(self.root, "add", "-A").returncode, 0)

        self.assertEqual(tracked_files(self.root), {"a.txt", "src/b.py"})

    def test_none_for_a_non_repository(self):
        support.write(self.root, "a.txt", "a\n")
        self.assertIsNone(tracked_files(self.root))

    def test_none_for_a_path_git_cannot_answer_for(self):
        self.assertIsNone(tracked_files(self.root / "does-not-exist"))


class IgnoreRuleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_matching_and_non_matching_patterns_name_their_source(self):
        support.write(self.root, ".gitignore", "*.log\nsecret.txt\n")
        support.write(self.root, ".cbmignore", "artefacts\n")
        rules = load_ignore_rules(self.root)

        hits = matching_rules("app.log", rules)
        self.assertEqual([(r.pattern, r.source) for r in hits], [("*.log", ".gitignore")])
        self.assertEqual(matching_rules("artefacts", rules),
                         [IgnoreRule("artefacts", ".cbmignore")])
        self.assertEqual(matching_rules("app.py", rules), [])

    def test_ignore_patterns_returns_the_historical_list_shape(self):
        support.write(self.root, ".gitignore", "node_modules\n.env\n")
        self.assertEqual(ignore_patterns(self.root), ["node_modules", ".env"])
        self.assertTrue(is_ignored("env", ["env"]))
        self.assertFalse(is_ignored("environment.py", ["env"]))

    def test_comments_and_blanks_are_skipped(self):
        support.write(self.root, ".gitignore", "# a comment\n\n  \n*.tmp\n")
        self.assertEqual(ignore_patterns(self.root), ["*.tmp"])


class DocumentedSubsetTests(unittest.TestCase):
    """Negation and anchoring are approximated; assert the *documented* outcome, not a wish."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_negation_lines_are_dropped_so_they_cannot_re_include(self):
        support.write(self.root, ".gitignore", "node_modules\n!node_modules/keep\n")
        rules = load_ignore_rules(self.root)
        self.assertEqual([r.pattern for r in rules], ["node_modules"])
        self.assertNotIn("!node_modules/keep", [r.pattern for r in rules])

    def test_anchored_patterns_are_not_treated_as_anchored(self):
        support.write(self.root, ".gitignore", "/build\n")
        rules = load_ignore_rules(self.root)
        self.assertEqual([r.pattern for r in rules], ["/build"])
        self.assertEqual(matching_rules("build", rules), [])


if __name__ == "__main__":
    unittest.main()
