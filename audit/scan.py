"""Stage S3 — bounded traversal and inventory.

Unbounded traversal is how a scanning tool becomes unusable on the repositories that need it
most. This module walks the target once, produces metadata only (never holding file contents in
memory), and record's every path it chose not to inspect.

Known limitation, deliberately recorded rather than hidden: ignore-pattern matching implements a
documented subset of gitignore semantics (anchored patterns, negation and `**` are approximated).
Checks that depend on ignore certainty must therefore report ``UNKNOWN`` rather than ``PASS`` when
they cannot be sure — see docs/architecture/contributor-deep-dive/01-scan-engine-and-tiering.md § 3.
"""

from __future__ import annotations

import enum
import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from audit.ignore import ignore_patterns, is_ignored
from audit.target import HARD_EXCLUDE_DIRS

#: Files larger than this are inventoried but their content is never read for content checks.
CONTENT_READ_LIMIT = 256 * 1024

#: Bytes sniffed to decide whether a file is binary.
BINARY_SNIFF = 8192


class Kind(str, enum.Enum):
    """Coarse classification that drives which checks look at a file."""

    MANIFEST = "manifest"
    BUILD = "build"
    CONFIG = "config"
    SOURCE = "source"
    TEST = "test"
    DOC = "doc"
    CI = "ci"
    SCRIPT = "script"
    GENERATED = "generated"
    BINARY = "binary"
    OTHER = "other"


_NAME_KINDS: dict[str, Kind] = {
    "package.json": Kind.MANIFEST, "pyproject.toml": Kind.MANIFEST, "setup.py": Kind.MANIFEST,
    "requirements.txt": Kind.MANIFEST, "Pipfile": Kind.MANIFEST, "pom.xml": Kind.BUILD,
    "build.gradle": Kind.BUILD, "build.gradle.kts": Kind.BUILD, "settings.gradle": Kind.BUILD,
    "go.mod": Kind.MANIFEST, "Cargo.toml": Kind.MANIFEST, "Gemfile": Kind.MANIFEST,
    "composer.json": Kind.MANIFEST, "Makefile": Kind.BUILD, "Taskfile.yml": Kind.BUILD,
    "Taskfile.yaml": Kind.BUILD, "gradlew": Kind.SCRIPT, "mvnw": Kind.SCRIPT,
    ".env.example": Kind.CONFIG, ".nvmrc": Kind.CONFIG, ".tool-versions": Kind.CONFIG,
    ".editorconfig": Kind.CONFIG, ".aider.conf.yml": Kind.CONFIG, "opencode.json": Kind.CONFIG,
}

_SUFFIX_KINDS: dict[str, Kind] = {
    ".md": Kind.DOC, ".rst": Kind.DOC, ".txt": Kind.DOC,
    ".py": Kind.SOURCE, ".ts": Kind.SOURCE, ".tsx": Kind.SOURCE, ".js": Kind.SOURCE,
    ".jsx": Kind.SOURCE, ".java": Kind.SOURCE, ".kt": Kind.SOURCE, ".go": Kind.SOURCE,
    ".rs": Kind.SOURCE, ".rb": Kind.SOURCE, ".cs": Kind.SOURCE, ".php": Kind.SOURCE,
    ".sh": Kind.SCRIPT, ".bash": Kind.SCRIPT, ".ps1": Kind.SCRIPT,
    ".json": Kind.CONFIG, ".yaml": Kind.CONFIG, ".yml": Kind.CONFIG, ".toml": Kind.CONFIG,
    ".ini": Kind.CONFIG, ".cfg": Kind.CONFIG, ".properties": Kind.CONFIG,
    ".min.js": Kind.GENERATED, ".map": Kind.GENERATED, ".pb.go": Kind.GENERATED,
}

_TEST_HINTS = ("test_", "_test.", ".test.", ".spec.", "tests/", "test/", "__tests__/")

_GENERATED_HINTS = ("dist/", "build/", "generated/", ".g.cs", ".designer.cs", ".pb.go",
                    ".lock.gen", "vendor/", ".min.css", ".min.js")


@dataclass(frozen=True)
class FileEntry:
    rel: str
    size: int
    kind: Kind
    has_text: bool


@dataclass
class Inventory:
    """Metadata for every inspected file, plus a record of what was skipped."""

    root: Path
    files: list[FileEntry] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    truncated: bool = False

    # -- lookups ---------------------------------------------------------
    def paths(self, kind: Kind | None = None) -> list[str]:
        return [f.rel for f in self.files if kind is None or f.kind is kind]

    def has(self, rel: str) -> bool:
        rel = rel.strip("/")
        return any(f.rel == rel or f.rel.endswith("/" + rel) for f in self.files)

    def match(self, *patterns: str) -> list[str]:
        out: list[str] = []
        for f in self.files:
            if any(fnmatch.fnmatch(f.rel, p) or fnmatch.fnmatch(os.path.basename(f.rel), p)
                   for p in patterns):
                out.append(f.rel)
        return out

    def with_suffix(self, *suffixes: str) -> list[str]:
        return [f.rel for f in self.files if f.rel.endswith(suffixes)]

    # -- content ---------------------------------------------------------
    def read(self, rel: str, limit: int = CONTENT_READ_LIMIT) -> str | None:
        """Read one file, bounded. Returns None for binary, oversized or unreadable files."""
        entry = next((f for f in self.files if f.rel == rel), None)
        if entry is None or not entry.has_text or entry.size > limit:
            return None
        try:
            return (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def grep(self, pattern, *, kinds: tuple[Kind, ...] | None = None,
             limit: int = 200) -> list[tuple[str, int, str]]:
        """Dot-less search across eligible text files. Returns (rel, line_no, line)."""
        import re

        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        hits: list[tuple[str, int, str]] = []
        for entry in self.files:
            if kinds and entry.kind not in kinds:
                continue
            if not entry.has_text or entry.size > CONTENT_READ_LIMIT:
                continue
            text = self.read(entry.rel)
            if not text:
                continue
            for no, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append((entry.rel, no, line.strip()[:240]))
                    if len(hits) >= limit:
                        return hits
        return hits


def _classify(rel: str) -> Kind:
    base = os.path.basename(rel)
    if base in _NAME_KINDS:
        return _NAME_KINDS[base]
    if rel.startswith(".github/workflows/") or base in (".gitlab-ci.yml", "Jenkinsfile",
                                                        "azure-pipelines.yml", ".circleci"):
        return Kind.CI
    lowered = rel.lower()
    if any(h in lowered for h in _GENERATED_HINTS):
        return Kind.GENERATED
    if any(h in lowered for h in _TEST_HINTS):
        return Kind.TEST
    for suffix in sorted(_SUFFIX_KINDS, key=len, reverse=True):
        if rel.endswith(suffix):
            return _SUFFIX_KINDS[suffix]
    return Kind.OTHER


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(BINARY_SNIFF)
    except OSError:
        return True


def build_inventory(root: Path, *, extra_excludes: tuple[str, ...] = (),
                    max_files: int = 250_000, max_depth: int = 24) -> Inventory:
    """Walk the target once. Never follows symlinks; never leaves ``root``."""
    root = root.resolve()
    patterns = ignore_patterns(root)
    inv = Inventory(root=root)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        if depth >= max_depth:
            inv.skipped.append((str(current.relative_to(root)), "max-depth"))
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in sorted(dirnames)
                       if d not in HARD_EXCLUDE_DIRS and not is_ignored(
                           (current / d).relative_to(root).as_posix(), patterns)]

        for name in sorted(filenames):
            if len(inv.files) >= max_files:
                inv.truncated = True
                break
            path = current / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                inv.skipped.append((rel, "symlink"))
                continue
            if is_ignored(rel, patterns) or any(fnmatch.fnmatch(rel, p) for p in extra_excludes):
                inv.skipped.append((rel, "ignored"))
                continue
            try:
                size = path.stat().st_size
            except OSError:
                inv.skipped.append((rel, "unreadable"))
                continue
            if size == 0:
                inv.files.append(FileEntry(rel, 0, _classify(rel), has_text=True))
                continue
            binary = _looks_binary(path)
            inv.files.append(FileEntry(
                rel=rel,
                size=size,
                kind=Kind.BINARY if binary else _classify(rel),
                has_text=not binary,
            ))
        if inv.truncated:
            break

    return inv
