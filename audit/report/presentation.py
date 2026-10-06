"""The Markdown template, as code.

A ``.pyz`` has no filesystem (ADR-0005 § 5), so the template is a Python data structure rather than
a shipped ``.md`` file — the same reason the instruction-variant table is code. Editing the report's
shape means editing this module (sections, columns, ordering, editorial wording); the rendering
engine in :mod:`audit.report.md_render` does not change.

Editorial text — the meaning of a verdict, the fix window of a severity, the meaning of an
unattested property — lives here, never in the JSON. The JSON carries facts; this module carries the
words the report uses to explain them.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Verdict rows for the scorecard: (label, json key, earns credit, meaning).
VERDICT_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("PASS", "pass", "yes", "Evidence found; requirement met."),
    ("PARTIAL", "partial", "no", "Some of the requirement is met; the ratio is the useful number."),
    ("FAIL", "fail", "no", "Requirement not met; a finding is emitted."),
    ("UNKNOWN", "unknown", "no", "Evidence could not be gathered. An open question about tool coverage."),
    ("ATTEST", "attest", "no", "Requires human attestation; not machine-verifiable."),
)

#: Severity rows: (label, fix window).
SEVERITY_ROWS: tuple[tuple[str, str], ...] = (
    ("BLOCKER", "Before any agent work"),
    ("DEGRADER", "Schedule"),
    ("COSMETIC", "Note and move on"),
)

#: What each unattested property means, in the report's own words.
UNATTESTED_MEANINGS: dict[str, str] = {
    "index-in-use": "Whether the codebase index is actually used during agent work.",
    "baseline-adequacy": "Whether the committed baseline or budget is adequate.",
    "suite-trustworthiness": "Whether the passing test suite actually catches regressions.",
    "doc-accuracy": "Whether the documentation matches the code it describes.",
    "gate-honoured": "Whether the gate is actually run and honoured before merge.",
}

#: Findings table columns.
FINDINGS_COLUMNS: tuple[str, ...] = ("Check", "Title", "Verdict", "Specifics", "Evidence", "Fix")
FINDINGS_ALIGN: tuple[str, ...] = ("left", "left", "center", "left", "left", "left")

#: Appendix full-check table columns.
APPENDIX_COLUMNS: tuple[str, ...] = ("ID", "Title", "Severity", "Tier", "Verdict", "Status", "Detail")
APPENDIX_ALIGN: tuple[str, ...] = ("left", "left", "left", "center", "center", "left", "left")

#: The title of the command-surface block, keyed by the payload kind that triggers it.
SPECIAL_BLOCKS: tuple[tuple[str, str], ...] = (
    ("verb_surface", "Command surface (CMD)"),
    ("credential_matrix", "Credential-shaped lines (SEC-02)"),
    ("secret_shapes", "Missing secret-shape ignore rules (SEC-01, SEC-03)"),
)


@dataclass(frozen=True)
class SectionSpec:
    """One top-level section: its heading and the builder that renders its body."""

    heading: str
    builder: str


#: The report's section order. ``<severity>`` expands to the findings table per severity; the rest
#: map to builders in :mod:`audit.report.md_render`.
SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec("Provenance", "provenance"),
    SectionSpec("Scorecard", "scorecard"),
    SectionSpec("Unattested", "unattested"),
    SectionSpec("Command surface", "special:verb_surface"),
    SectionSpec("Credential-shaped lines", "special:credential_matrix"),
    SectionSpec("Missing secret-shape ignore rules", "special:secret_shapes"),
    SectionSpec("Findings — Blocker", "findings:BLOCKER"),
    SectionSpec("Findings — Degrader", "findings:DEGRADER"),
    SectionSpec("Findings — Cosmetic", "findings:COSMETIC"),
    SectionSpec("Appendix — full check results", "appendix"),
    SectionSpec("Not applicable to this target", "not_applicable"),
    SectionSpec("Structural context", "structural"),
)
