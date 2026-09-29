"""`SEC` pack — security hygiene.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables.

Implemented here: `SEC-01` … `SEC-03`.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **SEC-01** — the tracked `.env` half reads `audit.ignore.tracked_files`; the ignore half reads the
  ignore files directly (`audit.ignore.load_ignore_rules`), so a tracked `.env` that is *also*
  git-ignored is still seen. A tracked ``.env``/``.env.*`` (excluding committed templates such as
  ``.env.example``) is the blocker. No tracked `.env` but ignore rules that miss the shape is
  `PARTIAL`. When git cannot report the tracked set the blocker half is `UNKNOWN` — never `PASS`,
  and the tracked set is never inferred from the walk.
* **SEC-02** — a pattern scan of **tracked text files** for the credential shapes in
  :data:`audit.probes.REDACTION_PATTERNS`. Findings carry path and line only; the matched value is
  never placed in the report (AGENTS.md §9). With no tracked set the scan falls back to the whole
  inventory and says so in `detail`. Committed templates (``*.example``/``*.sample``/``*.template``)
  and lines whose value is an obvious placeholder are skipped by a deterministic rule, so a
  documentation file that quotes the shape does not fail the check.
* **SEC-03** — ignore rules must cover a documented set of key/certificate/credential shapes
  (:data:`_SECRET_SHAPES`). Every required shape covered is `PASS`; some is `PARTIAL`; none is
  `FAIL`. The covered labels are stated in `detail`.

Deliberate limits, recorded rather than hidden. Ignore matching is the documented subset in
``audit.ignore`` (anchoring and ``**`` are approximated), so a shape is only credited when one of the
probes actually matches. Content reads are bounded by ``audit.scan``; a tracked file that is binary,
oversized, or ignored out of the walk is not scanned, and SEC-02 says which set it scanned.
"""

from __future__ import annotations

import fnmatch
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import IgnoreRule, load_ignore_rules, tracked_files
from audit.probes import REDACTION_PATTERNS
from audit.scan import Inventory

#: Committed templates that legitimately hold key *names* without secrets.
_ENV_TEMPLATE_BASENAMES: frozenset[str] = frozenset({
    ".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults", "env.example",
})

#: Values that are obviously not a secret, so a documentation line quoting a shape does not fire.
_PLACEHOLDER_RE = re.compile(
    r"(?i)<[^>]+>|your[_-]|xxx+|changeme|change[_-]?me|replace|example|placeholder|redacted|"
    r"dummy|fake|todo|none|null|\.\.\.")

#: The ignore-rule shapes SEC-03 requires, as (label, representative path).
_SECRET_SHAPES: tuple[tuple[str, str], ...] = (
    ("dotenv", ".env"),
    ("dotenv variant", ".env.local"),
    ("ssh private key", "id_rsa"),
    ("PEM", "server.pem"),
    ("key", "server.key"),
    ("PKCS#12", "server.p12"),
    ("PFX", "server.pfx"),
    ("keystore", "app.keystore"),
    ("certificate (.crt)", "server.crt"),
    ("certificate (.cer)", "server.cer"),
    ("AWS credentials", ".aws/credentials"),
)

#: The `.env` shapes SEC-01 requires the ignore rules to cover.
_ENV_SHAPE_PROBES: tuple[tuple[str, str], ...] = (
    ("dotenv", ".env"),
    ("dotenv variant", ".env.local"),
)

_MAX_SECRET_FILES = 25


def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _is_env_name(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base in _ENV_TEMPLATE_BASENAMES:
        return False
    return base == ".env" or base.startswith(".env.")


def _is_template_file(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return base in _ENV_TEMPLATE_BASENAMES or base.endswith((".example", ".sample", ".template", ".dist"))


def _path_covered(rel: str, rules: list[IgnoreRule]) -> bool:
    """Whether any rule covers ``rel``, including a rule that names a parent directory."""
    base = rel.rsplit("/", 1)[-1]
    for rule in rules:
        pattern = rule.pattern.rstrip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(base, pattern):
            return True
        if fnmatch.fnmatch(rel, pattern + "/*") or fnmatch.fnmatch(rel, pattern + "/**"):
            return True
    return False


def _shape_coverage(rules: list[IgnoreRule],
                    probes: tuple[tuple[str, str], ...]) -> tuple[list[str], list[str]]:
    covered = [label for label, sample in probes if _path_covered(sample, rules)]
    missing = [label for label, sample in probes if not _path_covered(sample, rules)]
    return covered, missing


# ===========================================================================
# SEC-01 — .env untracked and ignored
# ===========================================================================

def check_sec01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = load_ignore_rules(target.path)
    covered, missing = _shape_coverage(rules, _ENV_SHAPE_PROBES)
    ignore_ok = not missing

    tracked = tracked_files(target.path)
    if tracked is None:
        ignore_note = ("ignore rules cover .env" if ignore_ok
                       else f"ignore rules miss {', '.join(missing)}")
        return _unknown(spec, f"git could not report tracked files, so a tracked .env cannot be "
                              f"ruled out ({ignore_note})")

    tracked_env = sorted(rel for rel in tracked if _is_env_name(rel))
    if tracked_env:
        return _outcome(spec, Verdict.FAIL, f"tracked: {', '.join(tracked_env)}", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "read the repository without a credential leak",
                    f"{', '.join(tracked_env)} is tracked by git"),
                evidence=[Evidence(rel) for rel in tracked_env],
                path=tracked_env[0],
                remediation="Untrack the environment file (git rm --cached), add its shape to "
                            ".gitignore, and rotate any value it held."),
        ])

    if ignore_ok:
        return _outcome(spec, Verdict.PASS, "no tracked .env and ignore rules cover the shape")

    return _outcome(spec, Verdict.PARTIAL,
                    f"no tracked .env, but ignore rules miss {', '.join(missing)}", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "trust that a future .env stays out of history",
                f"no ignore rule covers {', '.join(missing)}"),
            evidence=[Evidence(rule.source, note=rule.pattern)
                      for rule in rules[:8]],
            remediation="Add the .env shape (for example `.env` and `.env.*`) to .gitignore so an "
                        "environment file cannot be committed by accident."),
    ])


# ===========================================================================
# SEC-02 — no key-shaped strings in tracked files
# ===========================================================================

#: The keyword-assignment redaction pattern is the one that can over-fire: `id-token: write` in a CI
#: workflow is a permission, not a credential. The purely shape-based patterns (sk-, ghp_, AKIA,
#: BEGIN PRIVATE KEY, Bearer) are unambiguous and always fire.
_KEYWORD_PATTERN = next(p for p in REDACTION_PATTERNS if "api" in p.pattern)
_SHAPE_PATTERNS = tuple(p for p in REDACTION_PATTERNS if p is not _KEYWORD_PATTERN)

_ASSIGNMENT_RE = re.compile(r"[:=]\s*(.+)$")
_SECRET_VALUE_CHARSET_RE = re.compile(r"[0-9A-Z]|[^A-Za-z0-9\s]")


def _looks_secret_value(raw: str) -> bool:
    """A deterministic value guard for the keyword pattern.

    A real secret value is long and mixes case, digits, or symbols. A bare keyword such as ``write``,
    ``read`` or ``true`` — the shape of a CI permission — is neither. This is what keeps a legitimate
    ``id-token: write`` from being read as a credential.
    """
    value = raw.strip().strip("\"'").strip()
    if len(value) < 12:
        return False
    if value.lower() in {"write", "read", "true", "false", "none", "null"}:
        return False
    return bool(_SECRET_VALUE_CHARSET_RE.search(value))


def _line_is_secret(line: str) -> bool:
    if any(pattern.search(line) for pattern in _SHAPE_PATTERNS):
        return True
    match = _KEYWORD_PATTERN.search(line)
    if not match:
        return False
    assignment = _ASSIGNMENT_RE.search(match.group(0))
    return bool(assignment) and _looks_secret_value(assignment.group(1))


def _scan_secrets(inventory: Inventory,
                  tracked: set[str] | None) -> tuple[str, list[tuple[str, int]]]:
    if tracked is None:
        scan_rels = sorted(f.rel for f in inventory.files if f.has_text)
        source = "whole inventory (tracked state unavailable)"
    else:
        scan_rels = sorted(f.rel for f in inventory.files if f.has_text and f.rel in tracked)
        source = "tracked text files"

    hits: set[tuple[str, int]] = set()
    for rel in scan_rels:
        if _is_template_file(rel):
            continue
        text = inventory.read(rel)
        if not text:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not _line_is_secret(line):
                continue
            if _PLACEHOLDER_RE.search(line):
                continue
            hits.add((rel, line_no))
    return source, sorted(hits)


def check_sec02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_files(target.path)
    source, hits = _scan_secrets(inventory, tracked)

    if not hits:
        return _outcome(spec, Verdict.PASS,
                        f"no credential-shaped strings in {source}")

    by_file: dict[str, list[int]] = {}
    for rel, line in hits:
        by_file.setdefault(rel, []).append(line)

    findings: list[Finding] = []
    for rel in sorted(by_file)[:_MAX_SECRET_FILES]:
        findings.append(Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "keep credentials out of the repository and its history",
                f"{rel} contains {len(by_file[rel])} credential-shaped line(s)"),
            evidence=[Evidence(rel, line=line, note="credential-shaped string")
                      for line in by_file[rel]],
            path=rel,
            remediation="Remove the value from the file and its history, load it from the "
                        "environment, and rotate the credential. The report never records the "
                        "value itself."))

    because = (f"{len(hits)} credential-shaped line(s) across {len(by_file)} file(s) in {source}")
    return _outcome(spec, Verdict.FAIL, because, findings)


# ===========================================================================
# SEC-03 — ignore patterns cover secret shapes
# ===========================================================================

def check_sec03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = load_ignore_rules(target.path)
    if not rules:
        return _outcome(spec, Verdict.FAIL, "no ignore rules exist", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "rely on the repository to keep secret shapes out",
                    "no .gitignore (or equivalent ignore file) exists"),
                remediation="Add a .gitignore covering secrets (.env*, *.pem, *.key, *.p12, "
                            "*.pfx, *.keystore, id_rsa*, *.crt, *.cer, .aws/*).")])

    covered, missing = _shape_coverage(rules, _SECRET_SHAPES)
    detail = (f"covered: {', '.join(covered)}" if covered else "no secret shapes covered")
    if not missing:
        return _outcome(spec, Verdict.PASS, detail)

    verdict = Verdict.PARTIAL if covered else Verdict.FAIL
    return _outcome(spec, verdict, f"{detail}; missing: {', '.join(missing)}", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
            statement=statement(
                "trust that secret shapes cannot be committed",
                f"ignore rules do not cover {', '.join(missing)}"),
            evidence=[Evidence(rule.source, note=rule.pattern) for rule in rules[:8]],
            remediation="Add the missing shapes to .gitignore — for example `.env.*`, `*.pem`, "
                        "`*.key`, `*.p12`, `*.pfx`, `*.keystore`, `id_rsa*`, `*.crt`, `*.cer`, "
                        "`.aws/*`."),
    ])


IMPLEMENTATIONS = {
    "SEC-01": check_sec01,
    "SEC-02": check_sec02,
    "SEC-03": check_sec03,
}
