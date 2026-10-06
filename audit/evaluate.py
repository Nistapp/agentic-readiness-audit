"""Stage S9 — verdict engine and scoring.

Two axes, never merged: **phase** (which framework requirement — provenance) and **severity**
(what it costs today — the work queue). Scoring covers Phase 1 only; Phases 2–4 signals and the
repository-hygiene set are reported and left numberless.

Weight model: severity weight classes (BLOCKER 3, DEGRADER 2, COSMETIC 1), normalised over the
checks that actually apply to this target. A per-check weight table was rejected: 50-odd invented
numbers would look precise and mean nothing. Open question for review — see the handoff.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from audit import __ruleset_revision__, __version__
from audit.components import ComponentModel, detect_components
from audit.findings import Finding, Severity, Verdict
from audit.probes import ProbeSession
from audit.rules.payloads import Payload
from audit.scan import Inventory
from audit.stack import Stack
from audit.target import Target

#: Properties no static scan can settle. Listed on every report, always (Risks R8).
UNATTESTED_ITEMS: tuple[str, ...] = (
    "index-in-use",
    "baseline-adequacy",
    "suite-trustworthiness",
    "doc-accuracy",
    "gate-honoured",
)

SEVERITY_WEIGHT = {Severity.BLOCKER: 3, Severity.DEGRADER: 2, Severity.COSMETIC: 1}

#: Partial verdicts earn half credit. UNKNOWN and ATTEST earn none — never a pass by omission.
VERDICT_CREDIT = {
    Verdict.PASS: 1.0,
    Verdict.PARTIAL: 0.5,
    Verdict.FAIL: 0.0,
    Verdict.UNKNOWN: 0.0,
    Verdict.ATTEST: 0.0,
}


@dataclass
class CheckOutcome:
    check: str
    title: str
    tier: str
    severity: Severity
    phase: int
    verdict: Verdict
    status: str                     # implemented | planned | blocked
    summary: str = ""               # one short human sentence (the appendix headline)
    data: Payload | None = None     # typed structured facts; renderer dispatches on .kind
    findings: list[Finding] = field(default_factory=list)


@dataclass
class AuditResult:
    target: Target
    stack: Stack
    inventory: Inventory
    components: ComponentModel
    outcomes: list[CheckOutcome]
    not_applicable: list[str] = field(default_factory=list)
    unattested: list[str] = field(default_factory=lambda: list(UNATTESTED_ITEMS))
    probes: list = field(default_factory=list)

    # -- derived views ---------------------------------------------------
    @property
    def findings(self) -> list[Finding]:
        return sorted(
            (f for o in self.outcomes for f in o.findings),
            key=lambda f: (f.severity.rank, f.check, f.id),
        )

    @property
    def implemented(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "implemented")

    @property
    def scored_outcomes(self) -> list[CheckOutcome]:
        """Outcomes that the score actually covers: scoreable, not blocked, not informational."""
        from audit.rules.registry import REGISTRY_BY_ID

        return [o for o in self.outcomes
                if REGISTRY_BY_ID[o.check].scored and REGISTRY_BY_ID[o.check].status != "blocked"]

    @property
    def score(self) -> float:
        """Phase-1 score over the scoreable checks only.

        Informational outcomes (``scored=False``, e.g. ``NAV-04``/``NAV-05`` and every ``HYG``
        check) are reported alongside the score but never enter it — they are numberless by design,
        so a PASS there cannot flatter the number and a FAIL cannot depress it.
        """
        applicable = [o for o in self.scored_outcomes if o.verdict is not Verdict.ATTEST]
        if not applicable:
            return 0.0
        earned = sum(SEVERITY_WEIGHT[o.severity] * VERDICT_CREDIT[o.verdict] for o in applicable)
        possible = sum(SEVERITY_WEIGHT[o.severity] for o in applicable)
        return round(earned / possible, 4) if possible else 0.0

    def counts(self, verdict: Verdict) -> int:
        return sum(1 for o in self.outcomes if o.verdict is verdict)

    def exit_code(self, fail_on: str | None, baseline: str | None) -> int:
        """0 by default. 2 only when the operator asked for a threshold or a ratchet (ADR-0001)."""
        if fail_on:
            threshold = Severity(fail_on)
            if any(f.severity.at_least(threshold) for f in self.findings):
                return 2
        if baseline:
            if self.regressions(baseline):
                return 2
        return 0

    def regressions(self, baseline_path: str) -> list[str]:
        """Finding ids present now that an accepted baseline report did not have.

        The baseline is a previously emitted audit JSON report; comparison is by the stable finding
        id (``check id + path``), never by count or score, so re-ordering or re-scoring changes
        nothing. Returns a sorted, deterministic list. A missing or malformed baseline yields a
        single descriptive entry rather than a crash or a silent empty list.
        """
        path = Path(baseline_path)
        if not path.exists():
            return [f"baseline not found: {baseline_path}"]
        try:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            baseline_ids = {str(finding["id"]) for finding in data["findings"]}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return [f"baseline unreadable: {baseline_path} ({type(exc).__name__})"]

        current_ids = {finding.id for finding in self.findings}
        return sorted(current_ids - baseline_ids)


def evaluate(*, target: Target, inventory: Inventory, stack: Stack,
             args: argparse.Namespace) -> AuditResult:
    """Run every applicable check. Unimplemented checks report UNKNOWN, never PASS."""
    from audit.rules.registry import applicable_checks

    session = ProbeSession(cwd=target.path, allow=tuple(args.allow_probe),
                           timeout=args.timeout, enabled=bool(args.run_gates))
    components = detect_components(inventory)

    outcomes: list[CheckOutcome] = []
    not_applicable: list[str] = []
    for spec in applicable_checks(stack):
        outcome = spec.run(target=target, inventory=inventory, stack=stack,
                           components=components, session=session)
        outcomes.append(outcome)

    catalogued = {spec.id for spec in applicable_checks(stack)}
    from audit.rules.registry import REGISTRY
    not_applicable = [spec.id for spec in REGISTRY if spec.id not in catalogued]

    return AuditResult(target=target, stack=stack, inventory=inventory, components=components,
                       outcomes=outcomes, not_applicable=not_applicable,
                       probes=session.results)


def provenance(target: Target, args: argparse.Namespace) -> dict:
    return {
        "tool": "python-agentic-audit",
        "version": __version__,
        "ruleset_revision": __ruleset_revision__,
        "target": str(target.path),
        "git_sha": target.git_sha,
        "git_branch": target.git_branch,
        "git_dirty": target.git_dirty,
        "scanned_at": target.scanned_at,
        "phase": args.phase,
        "probes_enabled": bool(args.run_gates),
    }
