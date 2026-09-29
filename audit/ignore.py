"""git-aware tracked-file access and a documented-subset ignore matcher.

Scope contract
--------------
This is a read-only helper layer for checks that need to know *which files matter*: which paths git
tracks (SEC-01/03, EXEC-05) and whether an ignore rule covers a path (DOC-03, CON-03). It never
writes to the target, never mutates a git repository, never installs anything, and makes no network
request.

Documented subset
-----------------
Ignore matching implements the same **documented subset** of gitignore semantics that
``audit.scan`` has always used, and deliberately does not overclaim:

* a rule is matched with :func:`fnmatch.fnmatch` against both the repository-relative path and the
  basename;
* **anchored** patterns (``/dist``) are not interpreted as anchored and may therefore fail to match
  the path they were written for;
* **negation** lines (``!keep``) are dropped entirely, so a later ``!`` cannot re-include a path;
* ``**`` is treated as a plain glob, not the gitignore "any depth" operator.

Callers that need certainty must treat a negative or ambiguous answer as ``UNKNOWN`` — never as
``PASS``. When git is unavailable, the target is not a repository, or the command fails,
:func:`tracked_files` returns ``None`` so callers degrade to ``UNKNOWN`` rather than infer.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Ignore files lifted from the target, in load order. Mirrors the historical set in ``audit.scan``.
IGNORE_FILE_NAMES: tuple[str, ...] = (
    ".gitignore", ".cbmignore", ".cursorignore", ".aiderignore", ".rooignore",
)


@dataclass(frozen=True)
class IgnoreRule:
    """One non-negated ignore line and the file it came from."""

    pattern: str
    source: str


def tracked_files(target: Path) -> set[str] | None:
    """Repository-relative paths git tracks under ``target``, or ``None`` when git cannot answer.

    ``None`` is a first-class answer: the target may not be a repository, git may be absent, or the
    command may fail. Callers must then degrade to ``UNKNOWN`` and never infer a tracked set.
    The command is invoked with an argument vector — no user input is ever passed through a shell.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "ls-files", "-z"],
            text=True, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return {entry for entry in proc.stdout.split("\0") if entry}


def load_ignore_rules(root: Path) -> list[IgnoreRule]:
    """Load the documented-subset rules from every ignore file present in ``root``.

    Behaviour is preserved from ``audit.scan``: blank lines and comments are skipped, and a leading
    ``!`` drops the line rather than being interpreted as negation.
    """
    rules: list[IgnoreRule] = []
    for name in IGNORE_FILE_NAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                rules.append(IgnoreRule(pattern=line.rstrip("/"), source=name))
    return rules


def ignore_patterns(root: Path) -> list[str]:
    """The bare patterns, for callers that only need the historical list shape."""
    return [rule.pattern for rule in load_ignore_rules(root)]


def matching_rules(rel: str, rules: list[IgnoreRule]) -> list[IgnoreRule]:
    """Every rule that covers ``rel``, carrying the ignore file each one came from.

    This is the "does any ignore file cover this path?" answer DOC-03 and CON-03 need.
    """
    base = os.path.basename(rel)
    return [rule for rule in rules
            if fnmatch.fnmatch(rel, rule.pattern) or fnmatch.fnmatch(base, rule.pattern)]


def is_ignored(rel: str, patterns: list[str]) -> bool:
    """Historical pattern matcher, unchanged, so ``audit.scan`` keeps walking exactly what it did."""
    base = os.path.basename(rel)
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) for p in patterns)
