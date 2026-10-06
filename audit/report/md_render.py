"""Generic Markdown renderer over the report model.

Reads the schema-v2 report dict (see :mod:`audit.report.model`) and the template data in
:mod:`audit.report.presentation`. It never parses prose: every table cell comes from a named field,
and check-specific tables dispatch on a payload ``kind``. Adding a section or a column means editing
``presentation.py``; adding a genuinely new derived view means adding one builder here.
"""

from __future__ import annotations

from typing import Any, Callable

from audit.report import presentation as P


def _esc(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _table(headers: tuple[str, ...], rows: list[list[str]],
           aligns: tuple[str, ...] | None = None) -> list[str]:
    aligns = aligns or tuple("left" for _ in headers)
    sep = {"left": "---", "center": ":--:", "right": "--:"}
    out = ["| " + " | ".join(_esc(h) for h in headers) + " |",
           "|" + "|".join(sep[a] for a in aligns) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_esc(c) for c in row) + " |")
    return out


def _codes(items) -> str:
    return ", ".join(f"`{_esc(i)}`" for i in items)


def _pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.1%}" if denominator else "—"


def _checks_by_id(report: dict) -> dict[str, dict]:
    return {c["id"]: c for c in report["checks"]}


def _specifics(check: dict, finding: dict | None) -> str:
    """A short, concrete string for a finding row, derived from the check's payload."""
    data = check.get("data") or {}
    kind = data.get("kind")
    if kind == "verb_surface":
        missing = data.get("missing") or []
        if missing:
            return (f"Missing: {_codes(missing)} — "
                    f"{data.get('resolved_count', 0)} of {len(data.get('verbs') or [])} defined.")
        return f"All {len(data.get('verbs') or [])} verbs resolved."
    if kind == "env_keys":
        return f"Missing env keys: {_codes(data.get('missing') or [])}."
    if kind == "secret_shapes":
        return f"Missing: {', '.join(data.get('missing') or []) or 'none'}."
    if kind == "credential_matrix":
        if finding is not None:
            return f"{len(finding.get('evidence') or [])} credential-shaped line(s)."
        return f"{data.get('total', 0)} credential-shaped line(s)."
    if kind == "harness_matrix":
        unreached = data.get("unreached_tools") or []
        return (f"{data.get('reached', 0)}/{data.get('total', 0)} harnesses reached; "
                f"unreached: {', '.join(unreached) or 'none'}.")
    if kind == "ratio":
        return (f"{data.get('numerator', 0)}/{data.get('denominator', 0)} "
                f"{data.get('unit', '')} ({_pct(data.get('numerator', 0), data.get('denominator', 1))}).")
    if kind == "path_list":
        paths = data.get("paths") or []
        return f"{len(paths)} path(s): {', '.join(paths)}."
    if kind == "counter":
        return f"{data.get('value', 0)} {data.get('unit', '')}."
    if kind == "mapping":
        return "; ".join(f"{e['key']}={e['value']}" for e in data.get("entries") or []) or "—"
    return check.get("summary") or "—"


def _evidence_cell(evidence: list[dict]) -> str:
    if not evidence:
        return "—"
    parts = []
    for e in evidence:
        path = e.get("path") or "?"
        line = e.get("line")
        note = e.get("note")
        cell = f"`{path}:{line}`" if line else f"`{path}`"
        if note:
            cell += f" ({note})"
        parts.append(cell)
    return "<br>".join(parts)


# ---------------------------------------------------------------------------
# section builders
# ---------------------------------------------------------------------------


def _provenance(report: dict) -> list[str]:
    prov = report["provenance"]
    dirty = " — **dirty working tree**" if prov.get("git_dirty") else ""
    rows = [
        ["Target", f"`{prov['target']}`"],
        ["Commit", f"`{str(prov.get('git_sha') or '')[:12]}` on `{prov.get('git_branch')}`{dirty}"],
        ["Tool", f"`{prov['tool']}` `{prov['version']}`"],
        ["Ruleset", f"`{prov['ruleset_revision']}` (hash `{prov['ruleset_hash']}`)"],
        ["Framework revision", f"`{prov['framework_revision']}`" if prov.get("framework_revision") else "—"],
        ["Phase evaluated", f"{prov.get('phase', 1)}"],
        ["Scanned", f"`{prov['scanned_at']}`"],
        ["Probes enabled", "yes" if prov.get("probes_enabled") else "no"],
    ]
    return _table(("Field", "Value"), rows)


def _scorecard(report: dict) -> list[str]:
    summary = report["summary"]
    counts = summary["checks"]
    applicable = summary.get("checks_applicable", 0)
    out = [f"**Phase-1 score:** `{summary['phase1_score']:.2f}` "
           f"({counts['pass']} pass · {counts['partial']} partial · {counts['fail']} fail · "
           f"{counts['unknown']} unknown · {counts['attest']} attest)", ""]

    out.append("### Verdict distribution (applicable checks)")
    out.append("")
    rows = [[label, str(counts.get(key, 0)), _pct(counts.get(key, 0), applicable), credit, meaning]
            for label, key, credit, meaning in P.VERDICT_ROWS]
    rows.append(["**Total**", f"**{sum(counts.values())}**", "**100%**", "", f"{applicable} applicable checks"])
    out += _table(("Verdict", "Checks", "Share", "Earns credit", "Meaning"), rows,
                  ("left", "right", "right", "center", "left"))
    out.append("")

    out.append("### Findings by severity")
    out.append("")
    findings = report["findings"]
    rows = []
    for severity, window in P.SEVERITY_ROWS:
        group = [f for f in findings if f["severity"] == severity]
        affected = sorted({f["check"] for f in group})
        rows.append([severity, str(len(group)), window, _codes(affected) if affected else "—"])
    rows.append(["**Total**", f"**{len(findings)}**", "", ""])
    out += _table(("Severity", "Findings", "Fix window", "Checks affected"), rows,
                  ("left", "right", "left", "left"))
    out.append("")

    out.append("> [!IMPORTANT]")
    out.append(f"> **Coverage caveat.** {summary['coverage_note']}")
    return out


def _unattested(report: dict) -> list[str]:
    items = report["unattested"]
    out = ["These are always listed, on every report. A completed scan cannot settle them; they are",
           "printed so the score is never read as a guarantee.", ""]
    rows = [[f"`{item}`", P.UNATTESTED_MEANINGS.get(item, "—")] for item in items]
    out += _table(("Property", "What the scan cannot settle"), rows)
    return out


def _checks_with_kind(report: dict, kind: str) -> list[dict]:
    return [c for c in report["checks"] if (c.get("data") or {}).get("kind") == kind]


def _verb_surface_block(report: dict) -> list[str] | None:
    check = _checks_by_id(report).get("CMD-01")
    data = (check or {}).get("data") or {}
    if data.get("kind") != "verb_surface":
        return None
    out = ["The framework's seven verbs, resolved verb by verb on the target's runners.", ""]
    rows = []
    for entry in data.get("verbs") or []:
        runner = (f"`{entry['runner']}`" + (f" (`{entry['command']}`)" if entry.get("command") else "")
                  ) if entry.get("runner") else "—"
        rows.append([f"`{entry['verb']}`", "yes" if entry["resolved"] else "**no**",
                     runner, "defined" if entry["resolved"] else "**MISSING**"])
    out += _table(("Verb", "Resolved", "Runner / evidence", "Status"), rows,
                  ("left", "center", "left", "center"))
    out.append("")

    fixes = [f for f in report["findings"] if f["check"] in {"CMD-01", "CMD-02", "AGT-05"}]
    if fixes:
        out.append("**Concrete fixes**")
        out.append("")
        for finding in fixes:
            out.append(f"- `{finding['check']}` — {finding['remediation']}")
    return out


def _credential_matrix_block(report: dict) -> list[str] | None:
    checks = _checks_with_kind(report, "credential_matrix")
    data = checks[0]["data"] if checks else None
    matrix = data if data and data.get("total") else None
    if not matrix:
        return None
    out = [f"{matrix['total']} credential-shaped line(s) across {len(matrix['files'])} tracked "
           f"file(s) in {matrix.get('source') or 'the repository'}. The report never records the "
           f"value itself.", ""]
    rows = [[f"`{f['path']}`", ", ".join(str(n) for n in f["lines"]), str(len(f["lines"]))]
            for f in matrix["files"]]
    rows.append(["**Total**", "", f"**{matrix['total']}**"])
    out += _table(("File", "Lines", "Count"), rows, ("left", "left", "right"))
    return out


def _secret_shapes_block(report: dict) -> list[str] | None:
    merged: dict[str, dict] = {}
    for check in _checks_with_kind(report, "secret_shapes"):
        for shape in (check["data"].get("shapes") or []):
            merged.setdefault(shape["label"], shape)
    if not merged:
        return None
    rows = [[shape["label"], "covered" if shape["covered"] else "**missing**",
             f"`{shape['suggested']}`" if shape.get("suggested") else "—"]
            for shape in merged.values()]
    return _table(("Shape", "Status", "Suggested `.gitignore` entry"), rows,
                  ("left", "center", "left"))


def _findings(report: dict, severity: str) -> list[str]:
    group = [f for f in report["findings"] if f["severity"] == severity]
    if not group:
        return []
    by_id = _checks_by_id(report)
    rows = []
    for finding in group:
        check = by_id.get(finding["check"], {})
        rows.append([
            f"`{finding['check']}`",
            check.get("title", "—"),
            finding["verdict"],
            _specifics(check, finding),
            _evidence_cell(finding.get("evidence") or []),
            finding.get("remediation") or "—",
        ])
    out = _table(P.FINDINGS_COLUMNS, rows, P.FINDINGS_ALIGN)
    return out


def _appendix(report: dict) -> list[str]:
    checks = report["checks"]
    summary = report["summary"]
    out = [f"All {len(checks)} checks in the catalogue, grouped by pack, including the "
           f"{summary['checks']['pass']} passes and {summary['checks']['unknown']} unknowns the "
           f"findings tables omit. `{summary['checks_implemented']}` of "
           f"`{summary['checks_applicable']}` applicable checks are implemented in this ruleset; "
           f"`{summary['checks_scoreable']}` are scoreable.", ""]
    last_pack = None
    rows: list[list[str]] = []
    for check in checks:
        pack = check.get("pack") or check["id"].split("-")[0]
        if pack != last_pack:
            if rows:
                out += _table(P.APPENDIX_COLUMNS, rows, P.APPENDIX_ALIGN)
                out.append("")
            out.append(f"### {pack}")
            out.append("")
            rows = []
            last_pack = pack
        rows.append([f"`{check['id']}`", check["title"], check["severity"], check["tier"],
                     check["verdict"], check["status"], check.get("summary") or "—"])
    if rows:
        out += _table(P.APPENDIX_COLUMNS, rows, P.APPENDIX_ALIGN)
    return out


def _not_applicable(report: dict) -> list[str]:
    items = report.get("not_applicable") or []
    if not items:
        return []
    return ["These catalogue checks do not apply to the detected stack, so they are neither passed "
            "nor failed.", "", _codes(items)]


def _structural(report: dict) -> list[str]:
    out = ["### Components", ""]
    components = report["components"]
    if not components or (len(components) == 1 and components[0]["name"] == "(root)"):
        out.append("Single-root repository — no component declarations found.")
    else:
        rows = [[c["name"], f"`{c['path']}`", "yes" if c["declared"] else "no", c["declared_by"],
                 f"`{c['manifest']}`" if c.get("manifest") else "—", c["agents_md"]]
                for c in components]
        out += _table(("Component", "Path", "Declared", "Declared by", "Manifest", "AGENTS.md"),
                      rows, ("left", "left", "center", "left", "left", "center"))
    candidates = report.get("candidate_components") or []
    if candidates:
        out.append("")
        out.append(f"Candidate components (not declared, informational): "
                   f"{_codes(candidates)}")
    out.append("")

    inv, stack = report["inventory"], report["stack"]
    out.append("### Scan coverage")
    out.append("")
    out += _table(("Metric", "Value"), [
        ["Files inspected", str(inv["files_inspected"])],
        ["Files skipped", str(inv["files_skipped"])],
        ["Traversal truncated", "yes" if inv["truncated"] else "no"],
        ["Ecosystems", ", ".join(stack["ecosystems"]) or "—"],
        ["Package managers", ", ".join(stack["package_managers"]) or "—"],
        ["Test frameworks", ", ".join(stack["test_frameworks"]) or "—"],
        ["CI providers", ", ".join(stack["ci_providers"]) or "—"],
        ["Hook managers", ", ".join(stack["hook_managers"]) or "—"],
    ])
    out.append("")

    out.append("### Probes")
    out.append("")
    probes = report["probes"]
    if not probes:
        out.append("No probes were configured or run.")
    else:
        rows = []
        for probe in probes:
            state = ("refused: " + probe["refused_reason"]) if probe.get("refused_reason") else (
                "timed out" if probe["timed_out"] else f"exit {probe['exit_code']}")
            command = " ".join(probe["command"]) if probe.get("command") else "—"
            rows.append([f"`{probe['verb']}`", f"`{command}`", state,
                         f"{probe['duration_s']:.1f}s", str(probe["redactions"]),
                         "yes" if probe["timed_out"] else "no", probe.get("output_tail") or "—"])
        out += _table(("Verb", "Command", "State", "Duration", "Redactions", "Timed out", "Output"),
                      rows, ("left", "left", "left", "right", "right", "center", "left"))
    return out


def _ratchet(report: dict) -> list[str]:
    ratchet = report.get("ratchet")
    if not ratchet:
        return []
    out = [f"- Baseline: `{ratchet['baseline']}`"]
    regressions = ratchet.get("regressions") or []
    if regressions:
        out.append(f"- Regressions against the baseline ({len(regressions)}):")
        out += [f"  - `{r}`" for r in regressions]
    else:
        out.append("- No findings beyond the baseline.")
    return out


_BUILDERS: dict[str, Callable[[dict], list[str] | None]] = {
    "provenance": _provenance,
    "scorecard": _scorecard,
    "unattested": _unattested,
    "special:verb_surface": _verb_surface_block,
    "special:credential_matrix": _credential_matrix_block,
    "special:secret_shapes": _secret_shapes_block,
    "appendix": _appendix,
    "not_applicable": _not_applicable,
    "structural": _structural,
}


def render_markdown(report: dict[str, Any]) -> str:
    """Render the schema-v2 report dict to the human Markdown artifact."""
    lines: list[str] = ["# Agentic readiness audit", ""]
    lines.append("> [!NOTE]")
    lines.append("> This audit reports; it does not gate. A completed scan exits 0 unless a threshold "
                 "or baseline")
    lines.append("> was requested (ADR-0001). `UNKNOWN` and `ATTEST` earn no credit and are never "
                 "rendered as passes.")
    lines.append("")

    for section in P.SECTIONS:
        builder = section.builder
        if builder.startswith("findings:"):
            body = _findings(report, builder.split(":", 1)[1])
            heading = section.heading
        else:
            body = _BUILDERS[builder](report)
            heading = section.heading
        if body is None or (isinstance(body, list) and not body):
            continue
        lines.append(f"## {heading}")
        lines.append("")
        lines += body
        lines.append("")

    ratchet = _ratchet(report)
    if ratchet:
        lines.append("## Ratchet")
        lines.append("")
        lines += ratchet
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Docs: `docs/architecture/README.md` · check catalogue: "
                 "`docs/architecture/contributor-deep-dive/02-check-catalogue.md`")
    return "\n".join(lines) + "\n"
