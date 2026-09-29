"""Rule-pack registry — one table, mirroring docs/architecture/contributor-deep-dive/02-check-catalogue.md.

The catalogue page is the design of record; this module is its executable form. A change to either
updates both in the same change set (enforced socially, and by the self-verification docstring in
the catalogue's § Adding a Check).

Three things live here and nowhere else:

* the **id → metadata** table (tier, severity, phase anchor, scored/not)
* **framework anchors**: the Phase-1 heading each pack traces back to, resolvable by ``--verify-rules``
* **applicability**: which packs apply to a detected stack, so an unsupported ecosystem degrades to
  ``UNKNOWN`` instead of passing silently
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from audit.findings import Severity, Verdict


@dataclass(frozen=True)
class Anchor:
    """A heading in the framework's documentation that justifies a pack."""

    file: str
    heading: str
    phase: int = 1


#: Where in the framework each pack comes from. Paths are relative to the framework repo root.
PACK_ANCHORS: dict[str, Anchor] = {
    "IDX": Anchor("brownfield-legacy/Phased-Approach.md", "Phase 1: Agentic Bootstrap"),
    "AGT": Anchor("brownfield-legacy/Phased-Approach.md", "Phase 1: Agentic Bootstrap"),
    "DOC": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "CMD": Anchor("brownfield-legacy/Phased-Approach.md", "Activities"),
    "TOOL": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "CI": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "BASE": Anchor("brownfield-legacy/Phased-Approach.md", "Activities"),
    "CON": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "EXEC": Anchor("brownfield-legacy/Phased-Approach.md", "Activities"),
    "TST": Anchor("brownfield-legacy/Phased-Approach.md", "Activities"),
    "NAV": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "SEC": Anchor("brownfield-legacy/Phased-Approach.md", "Key Deliverables"),
    "HYG": Anchor("brownfield-legacy/Phased-Approach.md", "Phase 1: Agentic Bootstrap"),
}

#: Packs whose id prefix does not equal the pack key.
_ID_PREFIX = {"EXEC": "EXEC"}


@dataclass
class CheckSpec:
    id: str
    title: str
    tier: str                       # A (artifact) | B (contract) | C (executed probe)
    severity: Severity
    evidence_rule: str
    phase: int = 1
    scored: bool = True
    ecosystems: tuple[str, ...] = ()  # empty = applies to every stack
    status: str = "planned"           # implemented | planned | blocked
    impl: Callable | None = None

    # -- convenience -----------------------------------------------------
    @property
    def pack(self) -> str:
        return self.id.split("-")[0]

    @property
    def anchor(self) -> Anchor | None:
        return PACK_ANCHORS.get(self.pack)

    def applies_to(self, stack) -> bool:
        return not self.ecosystems or bool(set(self.ecosystems) & stack.ecosystems)

    def run(self, **kwargs):
        """Execute the check, or report it honestly as unimplemented."""
        from audit.evaluate import CheckOutcome

        if self.status == "blocked":
            return CheckOutcome(self.id, self.title, self.tier, self.severity, self.phase,
                                Verdict.UNKNOWN, self.status,
                                detail="blocked: the framework defines no artifact contract for this "
                                       "deliverable, so it carries weight 0 in v1 (see CON-01)")
        if self.impl is None:
            return CheckOutcome(self.id, self.title, self.tier, self.severity, self.phase,
                                Verdict.UNKNOWN, self.status,
                                detail=f"not implemented in ruleset {_revision()}")
        return self.impl(spec=self, **kwargs)


def _revision() -> str:
    from audit import __ruleset_revision__
    return __ruleset_revision__


def _c(check_id: str, title: str, tier: str, sev: Severity, status: str = "planned",
       scored: bool = True, rule: str = "", ecosystems: tuple[str, ...] = ()) -> CheckSpec:
    return CheckSpec(id=check_id, title=title, tier=tier, severity=sev, evidence_rule=rule,
                     status=status, scored=scored, ecosystems=ecosystems)


_S = Severity

#: The catalogue. Order here is the order in the report and in ``--list-checks``.
_CATALOGUE: tuple[CheckSpec, ...] = (
    # -- IDX ------------------------------------------------------------
    _c("IDX-01", "codebase-memory-mcp registered for this repository", "A", _S.BLOCKER),
    _c("IDX-02", "An index exists for this checkout", "A", _S.BLOCKER),
    _c("IDX-03", "Index freshness", "C", _S.DEGRADER),
    # -- AGT ------------------------------------------------------------
    _c("AGT-01", "Instruction file present, canonical, and non-trivial", "A", _S.BLOCKER),
    _c("AGT-02", "Component coverage by instruction files", "A", _S.DEGRADER),
    _c("AGT-03", "Documentation contract named", "B", _S.DEGRADER),
    _c("AGT-04", "Definition of done stated", "B", _S.DEGRADER),
    _c("AGT-05", "Six verbs named", "B", _S.DEGRADER),
    _c("AGT-06", "Architectural boundaries declared", "B", _S.DEGRADER),
    _c("AGT-07", "Do-not-do / deny rules present", "B", _S.DEGRADER),
    _c("AGT-08", "No competing instruction files, and the reach matrix is stated", "B", _S.DEGRADER),
    _c("AGT-09", "Branch and release boundary declared", "B", _S.DEGRADER),
    _c("AGT-10", "Instruction indirection resolved", "B", _S.DEGRADER),
    # -- DOC ------------------------------------------------------------
    _c("DOC-01", "docs/ exists", "A", _S.DEGRADER),
    _c("DOC-02", "docs/STYLE_GUIDE.md exists", "A", _S.DEGRADER),
    _c("DOC-03", "artefacts/ exists and is ignored", "B", _S.DEGRADER),
    _c("DOC-04", "ADR directory and index", "A", _S.COSMETIC),
    # -- CMD ------------------------------------------------------------
    _c("CMD-01", "Six verbs resolvable on one runner", "B", _S.BLOCKER),
    _c("CMD-02", "check composes the read-only verbs", "B", _S.BLOCKER),
    _c("CMD-03", "No divergent second definition", "B", _S.DEGRADER),
    _c("CMD-04", "Write verbs separated from read-only verbs", "B", _S.DEGRADER),
    # -- TOOL -----------------------------------------------------------
    _c("TOOL-01", "Formatter configured", "B", _S.DEGRADER),
    _c("TOOL-02", "Linter configured", "B", _S.DEGRADER),
    _c("TOOL-03", "Type checker configured", "A", _S.DEGRADER),
    _c("TOOL-04", "Dependency / security scan verb", "A", _S.DEGRADER),
    _c("TOOL-05", "Local hook chain active", "B", _S.DEGRADER),
    _c("TOOL-06", "Commit convention enforced", "A", _S.COSMETIC),
    # -- CI -------------------------------------------------------------
    _c("CI-01", "Pipeline present, triggered on PRs", "B", _S.BLOCKER),
    _c("CI-02", "Local↔CI parity", "B", _S.BLOCKER),
    _c("CI-03", "CI-only steps flagged", "B", _S.DEGRADER),
    # -- BASE -----------------------------------------------------------
    _c("BASE-01", "Baseline artifact exists", "A", _S.DEGRADER),
    _c("BASE-02", "Current violation counts measured", "B", _S.DEGRADER),
    _c("BASE-03", "No-new-violations mechanism", "B", _S.DEGRADER),
    _c("BASE-04", "Coverage floor configured", "A", _S.DEGRADER),
    # -- CON ------------------------------------------------------------
    _c("CON-01", "Allow/deny artifact present", "B", _S.BLOCKER, status="blocked", scored=False,
       rule="Blocked: the framework requires allow/deny lists in Phase 1 but defines no artifact "
            "name or schema. Weight 0 in v1; the audit emits a draft instead (CON-04)."),
    _c("CON-02", "Test directories protected", "B", _S.BLOCKER),
    _c("CON-03", "artefacts/ excluded from index and agent reads", "B", _S.DEGRADER),
    _c("CON-04", "Draft allow/deny emitted", "—", _S.COSMETIC, scored=False, status="planned",
       rule="Emitter, not a check: writes a draft list from the scan."),
    # -- EXEC -----------------------------------------------------------
    _c("EXEC-01", "Toolchain pinned / wrapper committed", "A", _S.BLOCKER),
    _c("EXEC-02", "Lockfile committed and consistent", "B", _S.BLOCKER),
    _c("EXEC-03", "Non-interactive setup path", "A", _S.BLOCKER),
    _c("EXEC-04", "Env-var inventory complete", "B", _S.BLOCKER),
    _c("EXEC-05", "No generated artifacts committed in-tree", "B", _S.DEGRADER),
    _c("EXEC-06", "Documented commands resolve", "B", _S.DEGRADER),
    _c("EXEC-07", "No competing configs for one concern", "B", _S.DEGRADER),
    # -- TST ------------------------------------------------------------
    _c("TST-01", "Test verb exists, suite non-empty", "A", _S.BLOCKER),
    _c("TST-02", "Suite status known", "C", _S.DEGRADER),
    _c("TST-03", "Skip / xfail census", "B", _S.DEGRADER),
    _c("TST-04", "Fast path documented", "B", _S.DEGRADER),
    _c("TST-05", "Coverage configuration present", "A", _S.COSMETIC),
    # -- NAV ------------------------------------------------------------
    _c("NAV-01", "Declared component boundaries", "A", _S.DEGRADER),
    _c("NAV-02", "Obvious entry points", "B", _S.DEGRADER),
    _c("NAV-03", "Structural red flags", "B", _S.COSMETIC),
    _c("NAV-04", "Architecture orientation artifact", "A", _S.COSMETIC, scored=False),
    _c("NAV-05", "Public-symbol documentation coverage", "B", _S.COSMETIC, scored=False),
    # -- SEC ------------------------------------------------------------
    _c("SEC-01", ".env untracked and ignored", "B", _S.BLOCKER),
    _c("SEC-02", "No key-shaped strings in tracked files", "B", _S.BLOCKER),
    _c("SEC-03", "Ignore patterns cover secret shapes", "B", _S.DEGRADER),
    # -- HYG (informational, never scored) -------------------------------
    _c("HYG-01", "README present and non-placeholder", "A", _S.COSMETIC, scored=False),
    _c("HYG-02", "CODEOWNERS present", "A", _S.COSMETIC, scored=False),
    _c("HYG-03", "Pull-request template present", "A", _S.COSMETIC, scored=False),
    _c("HYG-04", "Issue templates present", "A", _S.COSMETIC, scored=False),
    _c("HYG-05", "CONTRIBUTING present", "A", _S.COSMETIC, scored=False),
    _c("HYG-06", "SECURITY present", "A", _S.COSMETIC, scored=False),
    _c("HYG-07", "CHANGELOG present and recent", "A", _S.COSMETIC, scored=False),
    _c("HYG-08", "Release process documented", "A", _S.COSMETIC, scored=False),
    _c("HYG-09", "Dependency update automation configured", "A", _S.COSMETIC, scored=False),
    _c("HYG-10", "License present", "A", _S.COSMETIC, scored=False),
    _c("HYG-11", "Branch protection declared as code", "B", _S.COSMETIC, scored=False),
)


def _attach_implementations(specs: tuple[CheckSpec, ...]) -> tuple[CheckSpec, ...]:
    """Wire implemented checks from audit/rules/checks/*. Nothing implemented ⇒ all planned."""
    try:
        from audit.rules.checks import IMPLEMENTATIONS
    except ImportError:      # a partially built tree must still list and run
        return specs

    for spec in specs:
        impl = IMPLEMENTATIONS.get(spec.id)
        if impl is not None:
            spec.impl = impl
            if spec.status == "planned":
                spec.status = "implemented"
    return specs


REGISTRY: tuple[CheckSpec, ...] = _attach_implementations(_CATALOGUE)

REGISTRY_BY_ID: dict[str, CheckSpec] = {spec.id: spec for spec in REGISTRY}


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

def applicable_checks(stack) -> list[CheckSpec]:
    return [spec for spec in REGISTRY if spec.applies_to(stack)]


def scoreable() -> list[CheckSpec]:
    return [s for s in REGISTRY if s.scored and s.status != "blocked"]


def informational() -> list[CheckSpec]:
    return [s for s in REGISTRY if not s.scored]


def tier_histogram(specs=None) -> dict[str, int]:
    out: dict[str, int] = {}
    for spec in specs or REGISTRY:
        out[spec.tier] = out.get(spec.tier, 0) + 1
    return out


# ---------------------------------------------------------------------------
# framework anchor resolution (--verify-rules)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def _normalise(text: str) -> str:
    """Strip markdown decoration and emoji so anchors survive cosmetic edits to the framework."""
    text = re.sub(r"[*_`#]", "", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2600-\u27BF\uFE0F]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def resolve_anchors(specs, framework_root: Path) -> list[tuple[str, Anchor]]:
    """Return the (pack, anchor) pairs whose heading is not found. Empty ⇒ all resolve."""
    headings: dict[str, set[str]] = {}
    missing: list[tuple[str, Anchor]] = []
    for pack, anchor in PACK_ANCHORS.items():
        if pack not in {s.pack for s in specs}:
            continue
        if anchor.file not in headings:
            path = framework_root / anchor.file
            if not path.is_file():
                missing.append((pack, anchor))
                headings[anchor.file] = set()
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            headings[anchor.file] = {
                _normalise(match.group(1)) for match in _HEADING_RE.finditer(text)
            }
        wanted = _normalise(anchor.heading)
        if not any(wanted in heading for heading in headings[anchor.file]):
            missing.append((pack, anchor))
    return missing


# ---------------------------------------------------------------------------
# ruleset identity (recorded in every report's provenance)
# ---------------------------------------------------------------------------

def ruleset_hash() -> str:
    """SHA-256 over the catalogue and the instruction-variant table.

    Two reports with different hashes were produced by different rules; that is the whole point.
    Changing a variant table entry changes the hash, so a silently rotted table is visible in the
    report rather than inferred from a suspicious verdict.
    """
    import hashlib

    import audit.rules.variants as variants

    parts = [f"{s.id}|{s.tier}|{s.severity.value}|{int(s.scored)}|{s.status}|{s.evidence_rule}"
             for s in REGISTRY]
    for harness in variants.HARNESSES:
        parts.append(f"H|{harness.tool}|{harness.agents_md}|{int(harness.nested)}"
                     f"|{','.join(harness.paths)}|{harness.doc_url}")
    for row in variants.SHADOW_PAIRS:
        parts.append("S|" + "|".join(row))
    for row in variants.CONFIG_INDIRECTION:
        parts.append("I|" + "|".join(row))
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
