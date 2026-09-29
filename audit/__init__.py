"""python-agentic-audit — read-only agentic-readiness scanner for existing repositories.

SCOPE CONTRACT (stage S0). This tool:

* **never writes inside the target repository** — output goes to ``--out``, outside by default
* **never installs anything** — no package manager, no wrapper bootstrap, no dependency download
* **makes no network request by default** — probes that need one are excluded unless permitted
* **calls no LLM** — identical target + flags + ruleset produce an identical report
* **reports; it does not gate** — a completed scan exits 0 (see ADR-0001)

Entry point: ``audit.__main__:main``, callable with no arguments (the zipapp shim and
``console_scripts`` both call ``main()`` with no argv).

Design of record lives in ``docs/``; start at ``docs/architecture/README.md``.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Bumped whenever a rule pack, a check, or the instruction-variant table changes.
#: Recorded in every report's provenance block so a report can be attributed to an
#: exact catalogue revision (docs: Scan Engine & Tiering, § 7 Determinism).
__ruleset_revision__ = "2026-09-28.13"

#: Highest framework phase this build evaluates. Phase 1 only in v1.
__phase_ceiling__ = 1
