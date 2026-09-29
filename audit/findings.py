"""Stage S10 — the finding model.

Every finding is phrased as **"an agent cannot X today because Y"**. That phrasing is not style:
it is what makes the report usable as a work queue instead of a compliance checklist.

Finding ids are derived from ``check id + path`` and never from a counter, so two runs over the
same repository produce comparable findings and a baseline diff is meaningful.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Severity(str, enum.Enum):
    """Effect on agent work, independent of framework phase. Ordering is meaningful."""

    BLOCKER = "BLOCKER"      # agent work is impossible, unsafe, or unverifiable
    DEGRADER = "DEGRADER"    # agent work is possible but unreliable or wasteful
    COSMETIC = "COSMETIC"    # hygiene; changes little

    @property
    def rank(self) -> int:
        return {"BLOCKER": 0, "DEGRADER": 1, "COSMETIC": 2}[self.value]

    def at_least(self, other: "Severity") -> bool:
        return self.rank <= other.rank


class Verdict(str, enum.Enum):
    """Outcome of one check.

    ``UNKNOWN`` exists so an unsupported ecosystem degrades visibly instead of passing silently.
    A report that cannot be wrong is worthless.
    """

    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"      # ran, but could not gather evidence — never counted as a pass
    ATTEST = "ATTEST"        # not statically verifiable; requires a human


@dataclass(frozen=True)
class Evidence:
    path: str
    line: int | None = None
    note: str | None = None

    def render(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


@dataclass
class Finding:
    check: str
    severity: Severity
    phase: int
    verdict: Verdict
    statement: str
    evidence: list[Evidence] = field(default_factory=list)
    remediation: str | None = None
    path: str | None = None

    @property
    def id(self) -> str:
        suffix = f":{self.path}" if self.path else ""
        return f"{self.check}{suffix}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "check": self.check,
            "phase": self.phase,
            "severity": self.severity.value,
            "verdict": self.verdict.value,
            "statement": self.statement,
            "evidence": [{"path": e.path, "line": e.line, "note": e.note} for e in self.evidence],
            "remediation": self.remediation,
        }


def statement(cannot: str, because: str) -> str:
    """Build the report's sentence form. Keep the subject an agent, not the repository."""
    return f"An agent cannot {cannot} because {because}."
