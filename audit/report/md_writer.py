"""Markdown report writer — the human artifact, ordered by severity, never by check id."""

from __future__ import annotations

import argparse

from audit.evaluate import AuditResult, UNATTESTED_ITEMS, provenance
from audit.findings import Severity, Verdict

_SEV_ORDER = (Severity.BLOCKER, Severity.DEGRADER, Severity.COSMETIC)


def render_markdown(result: AuditResult, args: argparse.Namespace) -> str:
    prov = provenance(result.target, args)
    lines: list[str] = []

    lines.append("# Agentic readiness audit")
    lines.append("")
    lines.append(f"**Target:** `{prov['target']}`  ")
    if prov["git_sha"]:
        dirty = " (dirty working tree)" if prov["git_dirty"] else ""
        lines.append(f"**Commit:** `{prov['git_sha'][:12]}` on `{prov['git_branch']}`{dirty}  ")
    lines.append(f"**Tool:** python-agentic-audit {prov['version']} · ruleset {prov['ruleset_revision']}  ")
    lines.append(f"**Scanned:** {prov['scanned_at']}  ")
    lines.append(f"**Phase evaluated:** 1 (Bootstrap)  ")
    lines.append("")

    # -- the three things that must travel together (Readiness Model § 6) ----
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- **Phase-1 score:** {result.score:.2f} "
                 f"({result.counts(Verdict.PASS)} pass · {result.counts(Verdict.PARTIAL)} partial · "
                 f"{result.counts(Verdict.FAIL)} fail · {result.counts(Verdict.UNKNOWN)} unknown)")
    lines.append(f"- **Blockers:** {sum(1 for f in result.findings if f.severity is Severity.BLOCKER)}")
    lines.append(f"- **Not attested by this scan:** {', '.join(UNATTESTED_ITEMS)}")
    lines.append("")

    implemented, total = result.implemented, len(result.outcomes)
    scored_implemented = sum(1 for o in result.scored_outcomes if o.status == "implemented")
    if scored_implemented < len(result.scored_outcomes):
        lines.append(f"> **Coverage caveat.** {scored_implemented} of {len(result.scored_outcomes)} "
                     f"scoreable checks are implemented in ruleset {prov['ruleset_revision']}. Everything "
                     f"else reports `UNKNOWN` and earns no credit — this report understates readiness, it "
                     f"does not certify it.")
        lines.append("")
    lines.append("> This audit reports; it does not gate. A completed scan exits 0 unless a "
                 "threshold or baseline was requested (ADR-0001).")
    lines.append("")

    # -- findings, by severity --------------------------------------------
    if not result.findings:
        lines.append("## Findings")
        lines.append("")
        lines.append("No findings at any severity.")
        lines.append("")
    for severity in _SEV_ORDER:
        group = [f for f in result.findings if f.severity is severity]
        if not group:
            continue
        lines.append(f"## {severity.value.title()} ({len(group)})")
        lines.append("")
        for finding in group:
            lines.append(f"- **`{finding.check}`** — {finding.statement}")
            if finding.evidence:
                rendered = ", ".join(f"`{e.render()}`" for e in finding.evidence[:6])
                lines.append(f"  - Evidence: {rendered}")
            if finding.remediation:
                lines.append(f"  - Fix: {finding.remediation}")
        lines.append("")

    # -- structural context ------------------------------------------------
    lines.append("## Components")
    lines.append("")
    if len(result.components.declared) <= 1 and not result.components.candidates:
        lines.append("Single-root repository — no component declarations found.")
    else:
        lines.append("| Component | Declared by | Manifest | AGENTS.md |")
        lines.append("|---|---|---|---|")
        for component in result.components.declared:
            agents = "present" if result.inventory.has(
                f"{component.path}/AGENTS.md".lstrip("./")) else "missing"
            lines.append(f"| `{component.path}` | {component.declared_by} | "
                         f"{component.manifest or '—'} | {agents} |")
        if result.components.candidates:
            lines.append("")
            lines.append(f"Candidate components (not declared, informational): "
                         f"{', '.join('`' + c + '`' for c in result.components.candidates)}")
    lines.append("")

    lines.append("## Scan coverage")
    lines.append("")
    lines.append(f"- Files inspected: {len(result.inventory.files)}")
    lines.append(f"- Files skipped: {len(result.inventory.skipped)}")
    lines.append(f"- Traversal truncated: {'yes' if result.inventory.truncated else 'no'}")
    lines.append(f"- Stack: {result.stack.describe()}")
    if result.stack.notes:
        for note in result.stack.notes:
            lines.append(f"  - {note}")
    lines.append("")

    if result.not_applicable:
        lines.append("## Not applicable to this target")
        lines.append("")
        lines.append(", ".join(f"`{c}`" for c in sorted(result.not_applicable)))
        lines.append("")

    if result.probes:
        lines.append("## Probes")
        lines.append("")
        for probe in result.probes:
            state = ("refused: " + probe.refused_reason) if probe.refused_reason else (
                "timed out" if probe.timed_out else f"exit {probe.exit_code}")
            lines.append(f"- `{probe.verb}`: {state} ({probe.duration_s:.1f}s)")
        lines.append("")

    baseline = getattr(args, "baseline", None)
    if baseline:
        regressions = result.regressions(baseline)
        lines.append("## Ratchet")
        lines.append("")
        lines.append(f"- Baseline: `{baseline}`")
        if regressions:
            lines.append(f"- Regressions against the baseline ({len(regressions)}):")
            for finding_id in regressions:
                lines.append(f"  - `{finding_id}`")
        else:
            lines.append("- No findings beyond the baseline.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Docs: `docs/architecture/README.md` · "
                 "check catalogue: `docs/architecture/contributor-deep-dive/02-check-catalogue.md`")
    return "\n".join(lines) + "\n"
