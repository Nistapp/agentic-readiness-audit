"""`DOC` pack — documentation contract.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables.

Implemented here: `DOC-01` … `DOC-04`. What each check reads, what makes a `PASS`, and the one place
``UNKNOWN`` is correct:

* **DOC-01** — a markdown file anywhere under `docs/` is the evidence. Absence of the directory is a
  real finding (`FAIL`), because a framework deliverable that does not exist is a fact, not an
  ambiguous one. `docs/` present with no markdown at all is `PARTIAL`. ``UNKNOWN`` is never used:
  the directory either has markdown or it does not.
* **DOC-02** — `docs/STYLE_GUIDE.md` present is the primary evidence; the entry instruction file
  naming it (the same reference `AGT-03` reads) is the second half. Present and named is `PASS`;
  present but unnamed is `PARTIAL`; absent is `FAIL`. `AGT-03` is **not** required to have passed.
* **DOC-03** — `artefacts/` (or `artifacts/`) present and matched by an ignore rule, with no tracked
  member, is `PASS`. No scratch directory in the inventory is `PASS` ("no scratch directory in
  use"). Present but unmatched by any ignore rule is `FAIL` — that half is knowable without git.
  When the directory is ignored but git cannot report the tracked set the check returns ``UNKNOWN``
  rather than infer it (the same degradation `SEC-01` uses).
* **DOC-04** — an ADR directory (`docs/architecture/adrs/` or `docs/adr/`) with numbered entries and
  an index (a `README.md`/`index.md` beside them, or the directory's parent README) that lists them.
  No directory is `FAIL`; entries without an index, or an index that omits some, is `PARTIAL`.

Deliberate limit, recorded rather than hidden: ignore matching is the documented subset in
``audit.ignore`` (anchoring and ``**`` approximated), and an empty `docs/` directory is only visible
through the filesystem, so DOC-01 consults the target directly for that one case.
"""

from __future__ import annotations

import fnmatch
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import load_ignore_rules, tracked_files
from audit.scan import Inventory
from audit.target import Target
from audit.rules.payloads import Payload

STYLE_GUIDE = "docs/STYLE_GUIDE.md"

#: Scratch directories the documentation contract keeps off-limits; both spellings are seen in the wild.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")

#: The two ADR locations the framework's own docs use.
_ADR_DIRS: tuple[str, ...] = ("docs/architecture/adrs", "docs/adr")

_ADR_FILE_RE = re.compile(r"^\d{3,4}-[A-Za-z0-9._-]+\.md$")


def _outcome(spec, verdict: Verdict, summary: str = "",
             findings: list[Finding] | None = None,
             data: Payload | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=summary, data=data, findings=findings or [])


def _instruction_text(inventory: Inventory) -> tuple[str, str]:
    """The entry instruction file and its text: canonical first, then the CLAUDE.md fallback."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = inventory.read(name)
        if text:
            return name, text
    return "", ""


def _has_exact(inventory: Inventory, rel: str) -> bool:
    """Exact path membership: unlike ``Inventory.has``, never a suffix match at any depth."""
    return any(f.rel == rel for f in inventory.files)


def _rule_covers(rel: str, rules) -> bool:
    """Whether an ignore rule covers ``rel``, including a rule that names a parent directory."""
    base = rel.rsplit("/", 1)[-1]
    for rule in rules:
        pattern = rule.pattern.rstrip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(base, pattern):
            return True
        if fnmatch.fnmatch(rel, pattern + "/*") or fnmatch.fnmatch(rel, pattern + "/**"):
            return True
    return False


def _rule_covers_root(root: str, rules) -> bool:
    """Whether a rule ignores a whole directory, including ``root/*`` and ``root/**`` forms."""
    for rule in rules:
        pattern = rule.pattern.strip().rstrip("/")
        core = pattern
        for suffix in ("/*", "/**"):
            if core.endswith(suffix):
                core = core[: -len(suffix)]
        core = core.rstrip("/")
        if core == root or fnmatch.fnmatch(root, pattern):
            return True
    return False


def _inventory_scratch(inventory: Inventory) -> list[str]:
    return sorted(f.rel for f in inventory.files
                  if f.rel.split("/", 1)[0] in _SCRATCH_ROOTS)


# ===========================================================================
# DOC-01 — docs/ exists with markdown
# ===========================================================================

def check_doc01(*, spec, target: Target, inventory, stack, components, session) -> CheckOutcome:
    markdown = sorted(f.rel for f in inventory.files
                      if f.rel.startswith("docs/") and f.rel.lower().endswith((".md", ".markdown")))
    if markdown:
        return _outcome(spec, Verdict.PASS, f"{len(markdown)} markdown file(s) under docs/")

    if (target.path / "docs").is_dir():
        return _outcome(spec, Verdict.PARTIAL, "docs/ exists but holds no markdown file", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
                statement=statement(
                    "read the project's documentation",
                    "docs/ exists but contains no markdown file"),
                evidence=[Evidence("docs/")],
                remediation="Add the canonical documentation pages to docs/ — a project overview "
                            "and the style guide at minimum."),
        ])

    return _outcome(spec, Verdict.FAIL, "no docs/ directory", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "find the project's documentation",
                "no docs/ directory exists in the repository"),
            remediation="Create docs/ as the canonical home for permanent knowledge, with "
                        "docs/STYLE_GUIDE.md holding the authoring rules."),
    ])


# ===========================================================================
# DOC-02 — docs/STYLE_GUIDE.md exists and is named
# ===========================================================================

def check_doc02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not _has_exact(inventory, STYLE_GUIDE):
        return _outcome(spec, Verdict.FAIL, f"{STYLE_GUIDE} is not present", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "find the canonical authoring rules for documentation",
                    f"{STYLE_GUIDE} does not exist"),
                remediation="Create docs/STYLE_GUIDE.md and name it from the instruction file so "
                            "writers have one set of authoring rules."),
        ])

    name, text = _instruction_text(inventory)
    if name and re.search(r"STYLE_GUIDE\.md", text):
        return _outcome(spec, Verdict.PASS, f"{STYLE_GUIDE} present and named in {name}")

    if name:
        why = f"{STYLE_GUIDE} exists but {name} does not name it"
    else:
        why = f"{STYLE_GUIDE} exists but no instruction file names it"
    return _outcome(spec, Verdict.PARTIAL, why, [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "know which authoring rules govern documentation",
                why),
            evidence=[Evidence(STYLE_GUIDE)],
            remediation=f"Name {STYLE_GUIDE} as canonical from the instruction file (see AGT-03)."),
    ])


# ===========================================================================
# DOC-03 — artefacts/ present and ignored
# ===========================================================================

def check_doc03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    scratch = _inventory_scratch(inventory)
    inventory_roots = {rel.split("/", 1)[0] for rel in scratch}
    fs_roots = {root for root in _SCRATCH_ROOTS if (target.path / root).is_dir()}
    present_roots = sorted(inventory_roots | fs_roots)

    tracked = tracked_files(target.path)
    tracked_scratch = sorted(
        rel for rel in (tracked or set()) if rel.split("/", 1)[0] in _SCRATCH_ROOTS
    )

    if not present_roots and not tracked_scratch:
        return _outcome(spec, Verdict.PASS, "no scratch directory in use")

    if tracked_scratch:
        return _outcome(spec, Verdict.FAIL, f"tracked: {', '.join(tracked_scratch[:8])}", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "treat the scratch directory as transient",
                    f"{len(tracked_scratch)} path(s) under {', '.join(present_roots or ['scratch'])}/"
                    f" are tracked by git"),
                evidence=[Evidence(rel) for rel in tracked_scratch[:12]],
                path=tracked_scratch[0],
                remediation="Untrack the scratch contents (git rm --cached) — the ignore rule only "
                            "keeps future files out."),
        ])

    rules = load_ignore_rules(target.path)
    covered = any(
        _rule_covers_root(root, rules)
        or any(_rule_covers(rel, rules) for rel in scratch if rel.startswith(root + "/"))
        for root in present_roots
    )
    if not covered:
        return _outcome(spec, Verdict.FAIL, f"{', '.join(present_roots)}/ present but not matched "
                                            f"by any ignore rule", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "rely on transient scratch staying out of the repository",
                    f"{', '.join(present_roots)}/ exists but no ignore rule covers it"),
                evidence=[Evidence(rel) for rel in scratch[:12]],
                remediation=f"Add `{present_roots[0]}/` to .gitignore so scratch documents cannot "
                            f"be committed and agents do not read them as source of truth."),
        ])

    if tracked is None:
        return _outcome(spec, Verdict.UNKNOWN,
                        f"ignore rules cover {', '.join(present_roots)}/, but git could not report "
                        f"the tracked set")

    return _outcome(spec, Verdict.PASS,
                    f"{', '.join(present_roots)}/ present, ignored, and untracked")


# ===========================================================================
# DOC-04 — ADR directory and index
# ===========================================================================

def _adr_dir(inventory: Inventory) -> str | None:
    for directory in _ADR_DIRS:
        if any(f.rel.startswith(directory + "/") for f in inventory.files):
            return directory
    return None


def _adr_entries(inventory: Inventory, directory: str) -> list[str]:
    return sorted(f.rel for f in inventory.files
                  if f.rel.startswith(directory + "/")
                  and _ADR_FILE_RE.match(f.rel.rsplit("/", 1)[-1]))


def _adr_index(inventory: Inventory, directory: str) -> str | None:
    """A README/index beside the ADRs, falling back to the parent directory's README."""
    for candidate in (f"{directory}/README.md", f"{directory}/index.md",
                      f"{directory}/_index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    parent = directory.rsplit("/", 1)[0]
    for candidate in (f"{parent}/README.md", f"{parent}/index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    return None


def check_doc04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    directory = _adr_dir(inventory)
    if directory is None:
        return _outcome(spec, Verdict.FAIL, "no ADR directory", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "find the decisions of record",
                    "no ADR directory (docs/architecture/adrs/ or docs/adr/) exists"),
                remediation="Add docs/architecture/adrs/ with NNNN-short-title.md files and a "
                            "README index that lists them."),
        ])

    entries = _adr_entries(inventory, directory)
    if not entries:
        return _outcome(spec, Verdict.PARTIAL, f"{directory}/ exists but holds no numbered ADR")

    index = _adr_index(inventory, directory)
    if index is None:
        return _outcome(spec, Verdict.PARTIAL,
                        f"{len(entries)} ADR(s) present but no index file", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
                statement=statement(
                    "discover the decisions of record from one page",
                    f"{directory}/ holds {len(entries)} ADR(s) but no index lists them"),
                evidence=[Evidence(rel) for rel in entries[:12]],
                remediation="Add a README (or index) beside the ADRs, or list them from the "
                            "architecture README."),
        ])

    text = inventory.read(index) or ""
    listed = [rel for rel in entries
              if rel.rsplit("/", 1)[-1] in text
              or re.search(rf"\b{rel.rsplit('/', 1)[-1][:4]}\b", text)]
    if len(listed) == len(entries):
        return _outcome(spec, Verdict.PASS, f"{len(entries)} ADR(s) indexed in {index}")

    return _outcome(spec, Verdict.PARTIAL,
                    f"{len(listed)}/{len(entries)} ADR(s) listed in {index}", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "find every decision of record",
                f"{index} lists {len(listed)} of {len(entries)} ADRs in {directory}/"),
            evidence=[Evidence(index)],
            remediation="Add a row to the ADR index for each entry, in the same change set that "
                        "adds the ADR."),
    ])


IMPLEMENTATIONS = {
    "DOC-01": check_doc01,
    "DOC-02": check_doc02,
    "DOC-03": check_doc03,
    "DOC-04": check_doc04,
}
