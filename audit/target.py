"""Stage S2 — target guard and provenance capture.

The audit runs inside repositories it does not own. This stage is the only place that decides
whether a path may be scanned at all, and it records the provenance every report carries so a
report can be attributed to an exact commit rather than to "some time last week".
"""

from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass
from pathlib import Path

from audit.cli import AuditUsageError

#: Directories that are never descended into, regardless of ignore files. Vendored and build
#: output are the two largest sources of false findings in a brownfield scan.
HARD_EXCLUDE_DIRS = frozenset({
    ".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv",
    "__pycache__", ".next", ".nuxt", ".cache", "coverage", ".gradle", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".terraform",
})


@dataclass(frozen=True)
class Target:
    """A resolved, validated scan target plus its git provenance."""

    path: Path
    is_git: bool
    git_sha: str | None
    git_branch: str | None
    git_dirty: bool
    scanned_at: str

    @property
    def is_dirty(self) -> bool:
        return self.git_dirty


def _git(path: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def resolve_target(path: Path) -> Target:
    """Validate the target and capture provenance. Raises AuditUsageError on bad input.

    Refuses rather than guesses: a scan of the wrong directory produces a report that looks
    authoritative and is about something else entirely.
    """
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise AuditUsageError(f"target does not exist: {resolved}")
    if not resolved.is_dir():
        raise AuditUsageError(f"target is not a directory: {resolved}")
    if resolved == Path(resolved.anchor):
        raise AuditUsageError("refusing to scan a filesystem root")
    if not any(resolved.iterdir()):
        # Not an error: an empty directory is a legitimate, maximally-unready target and a
        # fixture in the test suite. Reported as such rather than refused.
        pass

    is_git = (resolved / ".git").exists() or _git(resolved, "rev-parse", "--git-dir") is not None
    sha = _git(resolved, "rev-parse", "HEAD") if is_git else None
    branch = _git(resolved, "rev-parse", "--abbrev-ref", "HEAD") if is_git else None
    status = _git(resolved, "status", "--porcelain") if is_git else None

    return Target(
        path=resolved,
        is_git=is_git,
        git_sha=sha,
        git_branch=branch,
        git_dirty=bool(status),
        scanned_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
