"""JSON report writer — serialises the schema-v2 report model.

The model (:mod:`audit.report.model`) owns the schema; this module is the file-facing name for it.
Kept as a separate module so ``audit/report/__init__.py`` and tests read symmetrically with
:mod:`audit.report.md_writer`.
"""

from __future__ import annotations

import argparse
from typing import Any

from audit.evaluate import AuditResult
from audit.report.model import build_report


def render_json(result: AuditResult, args: argparse.Namespace) -> dict[str, Any]:
    """Build the canonical report dict (schema v2)."""
    return build_report(result, args)
