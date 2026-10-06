"""Report model — schema v2, the single serialisable shape both writers consume.

The JSON report is the render contract. :func:`build_report` turns an :class:`AuditResult` into one
dict; the JSON writer serialises that dict and the Markdown writer renders the *same* dict, so the
two artifacts can never disagree. :func:`read_report` parses a saved report back into that dict, so
any past report can be re-rendered with the current template.

Why v2 replaced v1's ``checks[].detail`` string: a renderer cannot build a table from prose. Each
check now emits a short human ``summary`` plus a typed ``data`` payload (see
``audit.rules.payloads``) whose ``kind`` the template dispatches on. There is no prose parsing in the
render path.

Schema (v2)::

    {
      "schema_version": "2",
      "provenance": {...},                 # provenance() + framework_revision + ruleset_hash
      "summary": {...},                    # scores, verdict counts, severity counts, caveat
      "checks": [ {id, pack, title, tier, severity, phase, scored, status, verdict,
                   summary, data:{kind,...}} ],
      "findings": [ {id, check, phase, severity, verdict, statement, evidence[], remediation} ],
      "components": [...], "candidate_components": [...],
      "stack": {...}, "inventory": {...}, "probes": [...],
      "unattested": [...], "not_applicable": [...],
      "ratchet": {...}                     # only with --baseline
    }
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from audit.evaluate import AuditResult, UNATTESTED_ITEMS, provenance
from audit.findings import Severity, Verdict

SCHEMA_VERSION = "2"


def _framework_revision(args: argparse.Namespace) -> str | None:
    root = getattr(args, "framework", None)
    if not root:
        return None
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def build_report(result: AuditResult, args: argparse.Namespace) -> dict[str, Any]:
    """Build the canonical report dict (schema v2) from a completed audit."""
    from audit.rules.registry import REGISTRY_BY_ID, ruleset_hash

    prov = provenance(result.target, args)
    prov["framework_revision"] = _framework_revision(args)
    prov["ruleset_hash"] = ruleset_hash()

    counts = {v.value.lower(): result.counts(v) for v in Verdict}

    checks = []
    for outcome in result.outcomes:
        spec = REGISTRY_BY_ID[outcome.check]
        checks.append({
            "id": outcome.check,
            "pack": outcome.check.split("-")[0],
            "title": outcome.title,
            "tier": outcome.tier,
            "severity": outcome.severity.value,
            "phase": outcome.phase,
            "scored": spec.scored,
            "status": outcome.status,
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "data": outcome.data.to_dict() if outcome.data is not None else {},
        })

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "provenance": prov,
        "summary": {
            "phase1_score": result.score,
            "blockers": sum(1 for f in result.findings if f.severity is Severity.BLOCKER),
            "degraders": sum(1 for f in result.findings if f.severity is Severity.DEGRADER),
            "cosmetic": sum(1 for f in result.findings if f.severity is Severity.COSMETIC),
            "checks": counts,
            "checks_implemented": result.implemented,
            "checks_scoreable": len(result.scored_outcomes),
            "checks_applicable": len(result.outcomes),
            "coverage_note": (
                f"{sum(1 for o in result.scored_outcomes if o.status == 'implemented')} of "
                f"{len(result.scored_outcomes)} scoreable checks are implemented in this ruleset "
                f"revision; every other check reports UNKNOWN and earns no credit, so this report "
                f"understates readiness rather than certifying it"
            ),
        },
        "stack": {
            "ecosystems": sorted(result.stack.ecosystems),
            "package_managers": sorted(result.stack.package_managers),
            "ci_providers": sorted(result.stack.ci_providers),
            "test_frameworks": sorted(result.stack.test_frameworks),
            "hook_managers": sorted(result.stack.hook_managers),
            "notes": result.stack.notes,
        },
        "inventory": {
            "files_inspected": len(result.inventory.files),
            "files_skipped": len(result.inventory.skipped),
            "truncated": result.inventory.truncated,
        },
        "components": [
            {
                "name": c.name,
                "path": c.path,
                "declared": True,
                "declared_by": c.declared_by,
                "manifest": c.manifest,
                "agents_md": "present" if result.inventory.has(
                    f"{c.path}/AGENTS.md".lstrip("./")) else "missing",
            }
            for c in result.components.declared
        ],
        "candidate_components": result.components.candidates,
        "findings": [f.to_dict() for f in result.findings],
        "checks": checks,
        "unattested": list(UNATTESTED_ITEMS),
        "not_applicable": sorted(result.not_applicable),
        "probes": [
            {
                "verb": p.verb,
                "command": p.command,
                "exit_code": p.exit_code,
                "timed_out": p.timed_out,
                "duration_s": round(p.duration_s, 3),
                "refused_reason": p.refused_reason,
                "redactions": p.redactions,
                "output_tail": p.output_tail,
            }
            for p in result.probes
        ],
    }

    baseline = getattr(args, "baseline", None)
    if baseline:
        report["ratchet"] = {
            "baseline": baseline,
            "regressions": result.regressions(baseline),
        }
    return report


def read_report(path: str | Path) -> dict[str, Any]:
    """Read a saved JSON report back into the model dict (for re-rendering)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
