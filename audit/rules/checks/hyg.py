"""`HYG` pack — repository hygiene (informational, never scored).

Anchor: `brownfield-legacy/Phased-Approach.md` § Phase 1: Agentic Bootstrap.

Implemented here: `HYG-01` … `HYG-11`. Every check reads its artifact through
:class:`audit.scan.Inventory`; none writes to the target and none runs a command in the target's
toolchain — `HYG-07` reads git metadata, read-only, through :func:`_git_output`.

Verdict contract for this pack — **absent artifacts are `FAIL`**. These checks are informational
(`scored=False` in the registry), so a `FAIL` is a reported fact and does not move the readiness
number. ``UNKNOWN`` is reserved for "the artifact is present but its quality cannot be settled":
an unreadable README, an undatable changelog, or an unrecognisable CI provider for branch
protection. It is never used merely because an artifact is absent.

* **HYG-01** — a root `README*` is the evidence. Present and at least
  :data:`MIN_README_CHARS` characters of body, free of a :data:`STUB_MARKERS` marker and not a bare
  title, is `PASS`. Present but below the bar is `FAIL` (with the file as evidence); present but
  unreadable (binary or oversized) is ``UNKNOWN``; absent is `FAIL`.
* **HYG-02** — `CODEOWNERS` at the root, under `.github/`, or under `docs/`.
* **HYG-03** — any `pull_request_template*` (case-insensitive), normally under `.github/`.
* **HYG-04** — at least one file under `.github/ISSUE_TEMPLATE/`, or `.github/ISSUE_TEMPLATE.md`.
* **HYG-05** — a `CONTRIBUTING*` document anywhere in the tree.
* **HYG-06** — a `SECURITY*` document anywhere in the tree.
* **HYG-07** — a `CHANGELOG*` document, **dated recently**. This is the only time-sensitive rule.
  Recency is derived from the repository's own git history, never from wall-clock time (AGENTS.md §5):
  the changelog's last commit date is compared with the `HEAD` commit date and is "recent" when it
  falls within :data:`RECENT_WINDOW`. When git cannot supply either date — no repository, git absent,
  or the changelog untracked — the verdict is ``UNKNOWN``, not ``FAIL`` and never ``date.today()``.
* **HYG-08** — a text/markdown document whose filename contains "release" (a release process or
  release-notes page). CI workflow files named `release.yml` are not documents and do not count.
* **HYG-09** — Dependabot or Renovate configuration at any of its conventional locations.
* **HYG-10** — a root license file: `LICENSE*`, `LICENCE*`, `COPYING*`, `COPYRIGHT*` or `UNLICENSE*`
  (case-insensitive, bare name or document suffix).
* **HYG-11** — branch protection declared as code, where the provider allows it. A
  `*branch-protection*`/`*branch_protection*` file, a `*branch_protection*` Terraform resource, or a
  document describing the provider's config is `PASS`. None found is `FAIL` when the CI provider is
  one that offers config-as-code (GitHub, GitLab); it is ``UNKNOWN`` when no such provider is
  recognised, because whether protection *can* be declared as code is provider-dependent.

Deliberate limit, recorded rather than hidden: "recently" is always relative to the repository's
latest commit, so an abandoned repository is judged on its own clock, not the audit machine's.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.scan import Inventory

#: A README below this many characters of trimmed text is present but not documentation.
MIN_README_CHARS = 200

#: Case-insensitive markers that make a README a stub rather than a description.
STUB_MARKERS = ("todo", "tbd", "placeholder", "lorem ipsum", "coming soon", "fill this in", "<describe")

#: Suffixes treated as documents for the presence checks that accept "any name plus a doc suffix".
_DOC_SUFFIXES = (".md", ".rst", ".txt", ".markdown", ".adoc")

#: How recent a changelog change must be, measured against the `HEAD` commit date — never wall clock.
RECENT_WINDOW = dt.timedelta(days=365)

#: CI providers that expose branch protection as configuration-as-code.
_PROTECTION_PROVIDERS = frozenset({"github", "gitlab"})

_DEPENDENCY_AUTOMATION = (
    ".github/dependabot.yml", ".github/dependabot.yaml", "dependabot.yml", "dependabot.yaml",
    "renovate.json", "renovate.json5", ".renovaterc", ".renovaterc.json",
    ".github/renovate.json", "renovate.config.js",
)


def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _finding(spec, verdict: Verdict, cannot: str, because: str, *,
             evidence: list[Evidence] | None = None, path: str | None = None,
             remediation: str | None = None) -> Finding:
    return Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
        statement=statement(cannot, because), evidence=evidence or [], path=path,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# artifact locators (all read the inventory; none touches the filesystem directly)
# ---------------------------------------------------------------------------

def _basename(rel: str) -> str:
    return rel.rsplit("/", 1)[-1]


def _present(inventory: Inventory, *names: str) -> list[str]:
    """Files whose path equals, or ends with, one of ``names`` (any depth)."""
    wanted = tuple(name.strip("/") for name in names)
    return sorted(f.rel for f in inventory.files
                  if f.rel.strip("/") in wanted
                  or any(f.rel.strip("/").endswith("/" + name) for name in wanted))


def _named_documents(inventory: Inventory, prefixes: tuple[str, ...], *,
                     root_only: bool = False) -> list[str]:
    """Files whose basename starts with a prefix and is a bare name or a document suffix."""
    out: list[str] = []
    for entry in inventory.files:
        if root_only and "/" in entry.rel:
            continue
        base = _basename(entry.rel).lower()
        if not any(base.startswith(prefix) for prefix in prefixes):
            continue
        if base.endswith(_DOC_SUFFIXES) or "." not in base:
            out.append(entry.rel)
    return sorted(out)


def _documents_containing(inventory: Inventory, needle: str) -> list[str]:
    return sorted(f.rel for f in inventory.files
                  if needle in _basename(f.rel).lower()
                  and _basename(f.rel).lower().endswith(_DOC_SUFFIXES))


def _git_output(target_path: Path, *args: str) -> str | None:
    """Run a read-only git query. ``None`` when git is absent, fails, or the path is not a repo."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target_path), *args],
            text=True, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _commit_date(target_path: Path, *pathspec: str) -> dt.datetime | None:
    """The committer date of the last commit touching ``pathspec`` (or ``HEAD``)."""
    raw = _git_output(target_path, "log", "-1", "--format=%cI", *pathspec)
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


# ===========================================================================
# HYG-01 — README present and non-placeholder
# ===========================================================================

def _readme_reason(text: str) -> str | None:
    stripped = text.strip()
    if len(stripped) < MIN_README_CHARS:
        return f"only {len(stripped)} characters (minimum {MIN_README_CHARS})"
    lowered = stripped.lower()
    for marker in STUB_MARKERS:
        if marker in lowered:
            return f"contains the placeholder marker {marker!r}"
    body = [line.strip() for line in stripped.splitlines()
            if line.strip() and not line.strip().startswith("#")]
    if not body:
        return "a title with no body"
    return None


def check_hyg01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(f.rel for f in inventory.files
                   if "/" not in f.rel and _basename(f.rel).lower().startswith("readme"))
    if not found:
        return _outcome(spec, Verdict.FAIL, "no README at the repository root", [
            _finding(spec, Verdict.FAIL, "orient itself in this project in seconds",
                     "no README exists at the repository root",
                     remediation="Add a root README that says what the project is, how to run it, "
                                 "and how to contribute."),
        ])

    primary = min(found, key=lambda rel: (0 if _basename(rel).lower() == "readme.md" else 1,
                                          rel.lower()))
    text = inventory.read(primary)
    if text is None:
        return _outcome(spec, Verdict.UNKNOWN,
                        f"{primary} present but not readable as text (binary or oversized)")

    reason = _readme_reason(text)
    if reason is None:
        return _outcome(spec, Verdict.PASS, f"{primary} present and non-placeholder")

    return _outcome(spec, Verdict.FAIL, f"{primary} is a placeholder — {reason}", [
        _finding(spec, Verdict.FAIL, "learn what this project is",
                 f"{primary} exists but is a placeholder — {reason}",
                 evidence=[Evidence(primary)], path=primary,
                 remediation="Replace the stub with a description, a quick-start, and a link to "
                             "the documentation."),
    ])


# ===========================================================================
# HYG-02 — CODEOWNERS
# ===========================================================================

def check_hyg02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, "CODEOWNERS")
    if found:
        return _outcome(spec, Verdict.PASS, f"CODEOWNERS present at {', '.join(found[:3])}")
    return _outcome(spec, Verdict.FAIL, "no CODEOWNERS file", [
        _finding(spec, Verdict.FAIL, "know who owns a path before changing it",
                 "no CODEOWNERS file exists at the root, under .github/, or under docs/",
                 remediation="Add .github/CODEOWNERS mapping paths to owners so review routing is "
                             "machine-readable."),
    ])


# ===========================================================================
# HYG-03 — pull-request template
# ===========================================================================

def check_hyg03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(f.rel for f in inventory.files
                   if _basename(f.rel).lower().startswith("pull_request_template"))
    if found:
        return _outcome(spec, Verdict.PASS, f"pull-request template present at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no pull-request template", [
        _finding(spec, Verdict.FAIL, "file a change with the information reviewers need",
                 "no .github/pull_request_template file exists",
                 remediation="Add .github/pull_request_template.md describing what a good change "
                             "records."),
    ])


# ===========================================================================
# HYG-04 — issue templates
# ===========================================================================

def check_hyg04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(f.rel for f in inventory.files
                   if f.rel.startswith(".github/ISSUE_TEMPLATE/")
                   or f.rel == ".github/ISSUE_TEMPLATE.md")
    if found:
        return _outcome(spec, Verdict.PASS, f"{len(found)} issue template(s) present")
    return _outcome(spec, Verdict.FAIL, "no issue templates", [
        _finding(spec, Verdict.FAIL, "report a bug or request in a structured way",
                 "no .github/ISSUE_TEMPLATE entry exists",
                 remediation="Add at least one file under .github/ISSUE_TEMPLATE/ (a bug report "
                             "and a feature request are a good start)."),
    ])


# ===========================================================================
# HYG-05 — CONTRIBUTING
# ===========================================================================

def check_hyg05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("contributing",))
    if found:
        return _outcome(spec, Verdict.PASS, f"CONTRIBUTING present at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no CONTRIBUTING document", [
        _finding(spec, Verdict.FAIL, "contribute without reverse-engineering the process",
                 "no CONTRIBUTING document exists",
                 remediation="Add CONTRIBUTING.md covering setup, the gate, and the review flow."),
    ])


# ===========================================================================
# HYG-06 — SECURITY
# ===========================================================================

def check_hyg06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("security",))
    if found:
        return _outcome(spec, Verdict.PASS, f"SECURITY present at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no SECURITY document", [
        _finding(spec, Verdict.FAIL, "report a vulnerability responsibly",
                 "no SECURITY document exists at the root, under .github/, or under docs/",
                 remediation="Add SECURITY.md with a private disclosure channel and a response "
                             "expectation."),
    ])


# ===========================================================================
# HYG-07 — CHANGELOG present and recent
# ===========================================================================

def check_hyg07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("changelog", "changes", "history"))
    if not found:
        return _outcome(spec, Verdict.FAIL, "no CHANGELOG document", [
            _finding(spec, Verdict.FAIL, "see what changed between two versions",
                     "no CHANGELOG (or CHANGES/HISTORY) document exists",
                     remediation="Add CHANGELOG.md and record notable changes under a version "
                                 "heading."),
        ])

    primary = found[0]
    head_date = _commit_date(target.path, "HEAD")
    changelog_date = _commit_date(target.path, "--", primary)
    if head_date is None or changelog_date is None:
        return _outcome(spec, Verdict.UNKNOWN,
                        f"{primary} present, but git could not date it against HEAD")

    age = head_date - changelog_date
    if age <= RECENT_WINDOW:
        return _outcome(spec, Verdict.PASS,
                        f"{primary} last changed {age.days} day(s) before HEAD")

    return _outcome(spec, Verdict.FAIL,
                    f"{primary} last changed {age.days} day(s) before HEAD "
                    f"(window {RECENT_WINDOW.days})", [
        _finding(spec, Verdict.FAIL, "trust that the changelog reflects the current release",
                 f"{primary} has not changed in {age.days} days of repository history",
                 evidence=[Evidence(primary)], path=primary,
                 remediation="Record the current release in the changelog in the same change set "
                             "that cuts it."),
    ])


# ===========================================================================
# HYG-08 — release document
# ===========================================================================

def check_hyg08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _documents_containing(inventory, "release")
    if found:
        return _outcome(spec, Verdict.PASS, f"release document present at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no release document", [
        _finding(spec, Verdict.FAIL, "know how a release is cut",
                 "no text or markdown document describing the release process exists",
                 remediation="Add docs/releasing.md (or RELEASE.md) describing how a version is "
                             "cut and published."),
    ])


# ===========================================================================
# HYG-09 — dependency update automation
# ===========================================================================

def check_hyg09(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, *_DEPENDENCY_AUTOMATION)
    if found:
        return _outcome(spec, Verdict.PASS, f"dependency automation configured at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no dependency update automation", [
        _finding(spec, Verdict.FAIL, "keep dependencies patched without manual sweeps",
                 "no Dependabot or Renovate configuration exists",
                 remediation="Add .github/dependabot.yml (or renovate.json) with an update "
                             "schedule."),
    ])


# ===========================================================================
# HYG-10 — license
# ===========================================================================

def check_hyg10(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("license", "licence", "copying", "copyright", "unlicense"),
                             root_only=True)
    if found:
        return _outcome(spec, Verdict.PASS, f"license present at {found[0]}")
    return _outcome(spec, Verdict.FAIL, "no license file at the repository root", [
        _finding(spec, Verdict.FAIL, "know the terms under which the code may be used",
                 "no LICENSE (or COPYING) file exists at the repository root",
                 remediation="Add a LICENSE file; choose one deliberately rather than defaulting "
                             "to all rights reserved."),
    ])


# ===========================================================================
# HYG-11 — branch protection declared as code
# ===========================================================================

def _branch_protection_config(inventory: Inventory) -> list[str]:
    named = [f.rel for f in inventory.files
             if "branch-protection" in f.rel.lower() or "branch_protection" in f.rel.lower()]
    terraform = sorted(rel for rel in inventory.with_suffix(".tf")
                       if "branch_protection" in (inventory.read(rel) or "").lower())
    return sorted(set(named) | set(terraform))


def check_hyg11(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    config = _branch_protection_config(inventory)
    if config:
        return _outcome(spec, Verdict.PASS, f"branch protection declared as code at {config[0]}")

    recognised = sorted(_PROTECTION_PROVIDERS & set(stack.ci_providers))
    if recognised:
        return _outcome(spec, Verdict.FAIL,
                        f"{', '.join(recognised)} offers branch protection as code, none found", [
            _finding(spec, Verdict.FAIL, "reproduce the protected-branch rules as code",
                     f"the {', '.join(recognised)} provider is detected but no branch-protection "
                     f"configuration exists",
                     remediation="Declare branch protection in code (a Terraform resource or "
                                 ".github/branch-protection) so it is reviewed like any other "
                                 "change."),
        ])

    return _outcome(spec, Verdict.UNKNOWN,
                    "no CI provider recognised; whether branch protection can be declared as code "
                    "is provider-dependent")


IMPLEMENTATIONS = {
    "HYG-01": check_hyg01,
    "HYG-02": check_hyg02,
    "HYG-03": check_hyg03,
    "HYG-04": check_hyg04,
    "HYG-05": check_hyg05,
    "HYG-06": check_hyg06,
    "HYG-07": check_hyg07,
    "HYG-08": check_hyg08,
    "HYG-09": check_hyg09,
    "HYG-10": check_hyg10,
    "HYG-11": check_hyg11,
}
