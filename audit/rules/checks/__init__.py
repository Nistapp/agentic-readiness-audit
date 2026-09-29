"""Rule-pack implementations, one module per pack.

The registry wires checks to implementations by id. A pack module that has not been written yet is
simply absent: its checks stay ``planned`` and report ``UNKNOWN``. Implementations are imported
without a blanket ``try/except ImportError`` — a broken implementation must fail loudly, not
silently downgrade a check to "planned" and quietly stop scanning for it.
"""

from __future__ import annotations

import importlib
import importlib.util

MODULE_NAMES: tuple[str, ...] = (
    "idx", "agt", "doc", "cmd", "tool", "ci",
    "base", "con", "execution", "tst", "nav", "sec", "hyg",
)

IMPLEMENTATIONS: dict[str, object] = {}


def _load() -> dict[str, object]:
    found: dict[str, object] = {}
    for name in MODULE_NAMES:
        dotted = f"audit.rules.checks.{name}"
        if importlib.util.find_spec(dotted) is None:
            continue
        module = importlib.import_module(dotted)
        found.update(getattr(module, "IMPLEMENTATIONS", {}))
    return found


IMPLEMENTATIONS.update(_load())
