"""JSON report writer — the machine-readable artifact (schema in Scan Engine & Tiering § 8)."""

from __future__ import annotations

import argparse
import subprocess

from audit.evaluate import AuditResult, UNATTESTED_ITEMS, provenance
from audit.findings import Severity, Verdict


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


def render_json(result: AuditResult, args: argparse.Namespace) -> dict:
    from audit.rules.registry import ruleset_hash

    prov = provenance(result.target, args)
    prov["framework_revision"] = _framework_revision(args)
    prov["ruleset_hash"] = ruleset_hash()

    checks = {v.value.lower(): result.counts(v) for v in Verdict}

    implemented = result.implemented
    total = len(result.outcomes)

    report = {
        "provenance": prov,
        "summary": {
            "phase1_score": result.score,
            "blockers": sum(1 for f in result.findings if f.severity is Severity.BLOCKER),
            "degraders": sum(1 for f in result.findings if f.severity is Severity.DEGRADER),
            "cosmetic": sum(1 for f in result.findings if f.severity is Severity.COSMETIC),
            "checks": checks,
            "checks_implemented": implemented,
            "checks_scoreable": len(result.scored_outcomes),
            "checks_applicable": total,
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
        "checks": [
            {
                "id": o.check,
                "title": o.title,
                "tier": o.tier,
                "severity": o.severity.value,
                "verdict": o.verdict.value,
                "status": o.status,
                "detail": o.detail,
            }
            for o in result.outcomes
        ],
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
