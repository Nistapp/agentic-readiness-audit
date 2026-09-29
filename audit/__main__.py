"""Process entry point.

Two invocations share this one function:

* ``python3 -m audit <target>``                (development, no install, no build)
* ``./dist/audit.pyz <target>``                (distribution, one file)

``main`` MUST be callable with no arguments: the zipapp-generated ``__main__.py`` shim and
a future ``console_scripts`` entry point both call ``main()``. Passing argv explicitly is
supported for tests. See docs/how-to/run-an-audit.md.
"""

from __future__ import annotations

import sys

from audit.cli import run


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
