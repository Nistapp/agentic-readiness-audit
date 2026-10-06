"""Structured per-check payloads — the machine-readable half of a check outcome.

A check's headline lives in ``CheckOutcome.summary`` (one short human sentence). The *evidence
shape* — the exact missing verbs, the credential file×line matrix, the harness reach list — lives
here as a typed payload. The renderer dispatches on ``kind`` and never parses prose.

Every payload is a frozen dataclass deriving from :class:`Payload`; ``to_dict`` is implemented once
in the base using :func:`dataclasses.asdict`, so adding a field to a payload automatically surfaces
in the JSON report and therefore in the rendered Markdown. ``kind`` is a :class:`~typing.ClassVar`,
so it is excluded from ``asdict`` and injected by the base.

These classes are code, not a data file: a ``.pyz`` has no filesystem (ADR-0005 § 5), so the
structured facts must travel as executable Python, exactly like the instruction-variant table.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar


class Payload:
    """Base class for a typed check payload. Subclasses are frozen dataclasses."""

    kind: ClassVar[str] = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON report shape: ``{"kind": ..., <fields...>}``."""
        return {"kind": type(self).kind, **asdict(self)}


# ---------------------------------------------------------------------------
# verb surface — CMD-01, CMD-02, AGT-05, CI-02
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerbEntry:
    """One framework verb and where (if anywhere) it resolves."""

    verb: str
    resolved: bool
    runner: str | None = None
    command: str | None = None


@dataclass(frozen=True)
class VerbSurface(Payload):
    """The seven-verb command surface, verb by verb."""

    kind: ClassVar[str] = "verb_surface"
    verbs: tuple[VerbEntry, ...] = ()
    resolved_count: int = 0
    missing: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# environment keys — EXEC-04
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvKeys(Payload):
    """Referenced environment keys and which are absent from committed example files."""

    kind: ClassVar[str] = "env_keys"
    referenced: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    templates: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# secret shapes — SEC-01, SEC-03
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretShape:
    """One secret shape the ignore rules should cover."""

    label: str
    probe: str
    suggested: str
    covered: bool


@dataclass(frozen=True)
class SecretShapes(Payload):
    """Secret-shape coverage of the repository's ignore rules."""

    kind: ClassVar[str] = "secret_shapes"
    shapes: tuple[SecretShape, ...] = ()
    covered: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# credential matrix — SEC-02
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CredentialFile:
    """A tracked file holding credential-shaped lines; line numbers only, never values."""

    path: str
    lines: tuple[int, ...]


@dataclass(frozen=True)
class CredentialMatrix(Payload):
    """Every tracked file with credential-shaped lines, and the total line count."""

    kind: ClassVar[str] = "credential_matrix"
    total: int = 0
    source: str = ""
    files: tuple[CredentialFile, ...] = ()


# ---------------------------------------------------------------------------
# harness reach — AGT-08
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HarnessMatrix(Payload):
    """Which known agent harnesses can reach an instruction file."""

    kind: ClassVar[str] = "harness_matrix"
    reached: int = 0
    total: int = 0
    reached_tools: tuple[str, ...] = ()
    unreached_tools: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# ratio and counter — AGT-02, NAV-05, TST-01, TST-03, NAV-03
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ratio(Payload):
    """A numerator over a denominator, with the unit and the measurement method."""

    kind: ClassVar[str] = "ratio"
    numerator: int = 0
    denominator: int = 0
    unit: str = ""
    method: str = ""


@dataclass(frozen=True)
class Counter(Payload):
    """A single measured count, optionally broken down by category."""

    kind: ClassVar[str] = "counter"
    value: int = 0
    unit: str = ""
    breakdown: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# path list — CON-02, DOC-03
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathList(Payload):
    """A list of repository-relative paths, with an explicit truncation flag (never ``(+N more)``)."""

    kind: ClassVar[str] = "path_list"
    paths: tuple[str, ...] = ()
    truncated: bool = False


# ---------------------------------------------------------------------------
# mapping — EXEC-07, TOOL-01/02/03/04/05, BASE-01/02
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MappingEntry:
    """One key→value fact a check wants to surface in a table."""

    key: str
    value: str


@dataclass(frozen=True)
class Mapping(Payload):
    """An ordered set of key→value facts."""

    kind: ClassVar[str] = "mapping"
    entries: tuple[MappingEntry, ...] = ()
