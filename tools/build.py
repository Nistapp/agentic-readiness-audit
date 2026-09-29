#!/usr/bin/env python3
"""Build the single-file distributable: dist/audit.pyz.

The package tree is the source of truth; this produces the one artifact you hand to someone else.
It needs nothing but the standard library, which is the entire reason the tool ships this way — it
must run on a machine where nothing is installed and the target's toolchain does not exist yet.

    python3 tools/build.py            # build, print size and the archive entry point
    ./dist/audit.pyz <target>         # run it

Two constraints come from zipapp and are easy to get wrong:

1. the archive root needs an entry point — passing ``main=`` makes zipapp generate a root
   ``__main__.py`` shim, so the package tree itself needs no root-level file
2. that shim calls ``main()`` with **no arguments**, exactly like a console script, which is why
   ``audit.__main__.main`` accepts ``argv=None``

Excluded from the archive: tests, docs, dist and bytecode. Nothing inside a .pyz can be read with
``Path(__file__)`` — the archive is not a directory — so shipped data must go through
``importlib.resources``. This project keeps its tables in code, so it has no such data file.
"""

from __future__ import annotations

import sys
import zipapp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist"
ARCHIVE = DIST / "audit.pyz"
ENTRY_POINT = "audit.__main__:main"

EXCLUDED_PREFIXES = ("tests/", "docs/", "dist/", "tools/", ".git/")


def _filter(path: Path) -> bool:
    rel = path.as_posix()
    if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    if "__pycache__" in rel or rel.endswith((".pyc", ".pyo")):
        return False
    return True


def main() -> int:
    if sys.version_info < (3, 9):
        print("audit: needs Python 3.9+ to build", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()

    zipapp.create_archive(
        source=REPO_ROOT,
        target=ARCHIVE,
        interpreter="/usr/bin/env python3",
        main=ENTRY_POINT,
        filter=_filter,
        compressed=True,
    )
    ARCHIVE.chmod(0o755)

    size = ARCHIVE.stat().st_size
    print(f"built {ARCHIVE.relative_to(REPO_ROOT)}  ({size:,} bytes)")
    print(f"entry point: {ENTRY_POINT}   run: ./dist/audit.pyz <target>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
