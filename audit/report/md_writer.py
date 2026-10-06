"""Markdown report writer — renders the JSON report model (schema v2) to Markdown.

The Markdown artifact is a pure function of the report dict, so it can be produced from an
in-memory run or re-rendered from a saved ``audit-report.json`` (:func:`render_markdown_from_report`).
Formatting lives in the template (:mod:`audit.report.presentation`) and the engine
(:mod:`audit.report.md_render`).
"""

from __future__ import annotations

from typing import Any

from audit.report.md_render import render_markdown


def render_markdown_from_report(report: dict[str, Any]) -> str:
    """Render any schema-v2 report dict — in memory or read from disk — to Markdown."""
    return render_markdown(report)
