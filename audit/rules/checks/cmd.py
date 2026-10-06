"""`CMD` pack — command surface.

Anchor: `brownfield-legacy/Phased-Approach.md` § Activities.

Implemented here: `CMD-01` … `CMD-04`.

The framework's standardized command surface is seven verbs on one runner. Each check reads the
runner manifests once through `audit.rules.checks._common`; this pack never reparses a manifest.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CMD-01** — every framework verb (`audit.stack.VERBS`) resolves, and resolves on **one** runner.
  `_common.resolve_all_verbs` is read in full, so a verb declared on two runners is visible as a
  stray second definition. Missing verbs ⇒ `FAIL`; verbs split across (or duplicated on) more than
  one runner ⇒ `PARTIAL` — the stray definition is `CMD-03`'s territory. With **no runner manifest
  at all** the verdict is `UNKNOWN`: an unrecognised ecosystem is not proof of absence.
* **CMD-02** — the `check` verb's body invokes a format-check, a typecheck and a test command.
  Indirection through another verb (`npm run format:check`) and documented tool equivalents
  (``prettier --check``, ``tsc --noEmit``, ``pytest``, …) both count. Some concerns present ⇒
  `PARTIAL`; none ⇒ `FAIL`; no runner ⇒ `UNKNOWN`.
* **CMD-03** — a second runner may define `check` only as a delegation to the first; a second runner
  that composes the gate itself is a finding. Detection is textual and deterministic: a delegating
  `check` invokes ``check`` through another runner. No runner ⇒ `UNKNOWN`.
* **CMD-04** — no read-only verb (`VERBS` minus `audit.probes.MUTATING_VERBS`) invokes a write verb.
  Both runner indirection (``npm run format``) and direct writer invocations (``prettier --write``,
  ``tsc`` without ``--noEmit``, ``rm -rf``) are detected, so a formatter's explicit-run write form is
  caught while its check form (``format:check``) is not. No runner ⇒ `UNKNOWN`.

Two deliberate limits, recorded rather than hidden. **Command parsing is textual**: shell operators
are split on, not interpreted, so a verb hidden inside a quoted string is not seen. **Runner
resolution is v1's**: only the manifests `_common` understands can contribute verbs, so an ecosystem
outside that set reports `UNKNOWN`, never a false `PASS`.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.probes import MUTATING_VERBS
from audit.rules.checks._common import (
    RUNNER_PRECEDENCE,
    VerbBinding,
    resolve_all_verbs,
    resolve_verbs,
    runner_commands,
)
from audit.stack import VERBS
from audit.rules.payloads import Payload, VerbEntry, VerbSurface

#: The three read-only concerns a `check` gate must compose, in catalogue order.
CONCERNS = ("format-check", "typecheck", "test")

#: Which resolved verb satisfies which concern. `lint` composes into `format:check` in the framework's
#: reference surface, so it is not a concern of its own here.
_CONCERN_OF_VERB = {"format:check": "format-check", "typecheck": "typecheck", "test": "test"}

#: The read-only verbs `check` and CI may compose: every framework verb except a write verb.
READ_ONLY_VERBS: tuple[str, ...] = tuple(v for v in VERBS if v not in MUTATING_VERBS)

_SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

_NPM_RE = re.compile(r"\b(?:npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)")
_YARN_RE = re.compile(r"\byarn\s+(?:run\s+)?([A-Za-z0-9:_-]+)")
_TASK_RE = re.compile(r"\b(?:make|task|just|mise)\s+(?:-\S+\s+)*([A-Za-z0-9:_-]+)")
_RUNNER_INVOCATIONS = (_NPM_RE, _YARN_RE, _TASK_RE)

#: Documented tool equivalents, used only when `check` calls a tool directly rather than a verb.
_DIRECT_CONCERN_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("format-check", (
        r"\bbiome\s+(?:ci|check)\b",
        r"\bprettier\b[^&|;]*--check\b",
        r"\bruff\s+format\b[^&|;]*--(?:check|diff)\b",
        r"\bruff\s+check\b",
        r"\bblack\b[^&|;]*--check\b",
        r"\bdprint\s+check\b",
        r"\bcargo\s+fmt\b[^&|;]*--check\b",
        r"\bgofmt\b[^&|;]*\s-l\b",
        r"\bdotnet\s+format\b[^&|;]*--verify-no-changes\b",
    )),
    ("typecheck", (
        r"\btsc\b", r"\bmypy\b", r"\bpyright\b", r"\bbasedpyright\b",
        r"\bcargo\s+check\b", r"\bgo\s+vet\b",
    )),
    ("test", (
        r"\bvitest\b", r"\bjest\b", r"\bmocha\b", r"\bpytest\b",
        r"python3?\s+-m\s+(?:unittest|pytest)", r"\bgo\s+test\b", r"\bcargo\s+test\b",
        r"\bdotnet\s+test\b", r"\brspec\b", r"\bphpunit\b", r"\btox\b",
    )),
)

#: Direct writer invocations, keyed by the write verb they represent. Only the check form is read, so
#: `format:check` is never mistaken for `format`.
_WRITER_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("format", (
        r"\bprettier\b[^&|;]*\s(?:--write|-w)\b",
        r"\bbiome\s+format\b",
        r"\bbiome\s+(?:check|format)\b[^&|;]*--write\b",
        r"\bruff\s+format\b(?![^&|;]*--(?:check|diff))",
        r"\bblack\b(?![^&|;]*--check)",
        r"\bgofmt\b[^&|;]*\s-w\b",
        r"\beslint\b[^&|;]*--fix\b",
        r"\bclippy\b[^&|;]*--fix\b",
        r"\bcargo\s+fmt\b(?![^&|;]*--check)",
    )),
    ("install", (
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:ci|install)\b",
        r"\bpip3?\s+install\b",
        r"\buv\s+(?:sync|pip)\b",
        r"\bcargo\s+(?:fetch|install)\b",
    )),
    ("build", (
        r"\bcargo\s+build\b", r"\btsc\b(?!\s+--noEmit)", r"\bdotnet\s+build\b",
    )),
    ("clean", (
        r"\brm\s+-rf?\b", r"\bshx\s+rm\b",
    )),
)


def _outcome(spec, verdict: Verdict, summary: str = "",
             findings: list[Finding] | None = None,
             data: Payload | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=summary, data=data, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _rank(runner: str) -> int:
    try:
        return RUNNER_PRECEDENCE.index(runner)
    except ValueError:
        return len(RUNNER_PRECEDENCE)


def _segments(command: str) -> list[str]:
    return [s for s in _SEGMENT_SPLIT.split(command) if s.strip()]


def _runner_target(segment: str) -> str | None:
    """The verb/script a segment invokes through a package manager, Make, or a task runner."""
    for pattern in _RUNNER_INVOCATIONS:
        match = pattern.search(segment)
        if match:
            return match.group(1)
    return None


def _ordered_runners(runners: set[str]) -> list[str]:
    return sorted(runners, key=_rank)


# ===========================================================================
# CMD-01 — six verbs resolvable on one runner
# ===========================================================================

def check_cmd01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _unknown(spec, "no recognised verb runner (package.json, Makefile, Taskfile, "
                              "pyproject, gradle, maven), so no verb can be resolved")

    bindings = resolve_all_verbs(inventory, stack)
    resolved = {verb: entries[0] for verb, entries in bindings.items()}
    missing = [verb for verb in VERBS if verb not in resolved]
    runners_used = _ordered_runners(
        {binding.runner for entries in bindings.values() for binding in entries})

    detail = "; ".join(
        f"{verb} -> {resolved[verb].runner}" if verb in resolved else f"{verb} -> missing"
        for verb in VERBS)

    surface = VerbSurface(
        verbs=tuple(
            VerbEntry(
                verb=verb,
                resolved=verb in resolved,
                runner=resolved[verb].runner if verb in resolved else None,
                command=resolved[verb].command if verb in resolved else None,
            )
            for verb in VERBS
        ),
        resolved_count=len(resolved),
        missing=tuple(missing),
    )

    if missing:
        return _outcome(spec, Verdict.FAIL, detail, [Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "run the standardized command surface literally",
                f"{len(missing)} of {len(VERBS)} framework verbs are not defined on any runner "
                f"({', '.join(missing)})"),
            evidence=[Evidence(runner) for runner, _cmds in declared],
            remediation="Define every verb (format, format:check, lint, typecheck, test, check, "
                        "security) as a script/target so an agent never has to invent a command.")],
            data=surface)

    if len(runners_used) > 1:
        return _outcome(spec, Verdict.PARTIAL, detail, [Finding(
            check=spec.id, severity=Severity.DEGRADER, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "find every verb on one runner",
                f"verbs resolve across {len(runners_used)} runners "
                f"({', '.join(runners_used)}), so no single runner is the contract"),
            evidence=[Evidence(resolved[verb].runner, note=verb) for verb in VERBS],
            remediation="Keep one runner as the authority for all verbs; reduce any second runner "
                        "to a delegation (see CMD-03).")], data=surface)

    return _outcome(spec, Verdict.PASS, detail, data=surface)


# ===========================================================================
# CMD-02 — check composes the read-only verbs
# ===========================================================================

def _composition_concerns(command: str, resolved: dict[str, VerbBinding]) -> set[str]:
    concerns: set[str] = set()
    for segment in _segments(command):
        target = _runner_target(segment)
        if target and target in resolved:
            concern = _CONCERN_OF_VERB.get(target)
            if concern:
                concerns.add(concern)
        for concern, patterns in _DIRECT_CONCERN_PATTERNS:
            if concern not in concerns and any(re.search(p, segment) for p in patterns):
                concerns.add(concern)
    return concerns


def check_cmd02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _unknown(spec, "no recognised verb runner, so no check verb can be read")

    resolved = resolve_verbs(inventory, stack)
    check = resolved.get("check")
    if check is None:
        return _outcome(spec, Verdict.FAIL, "the check verb is not defined on any runner",
                        [Finding(
                            check=spec.id, severity=spec.severity, phase=spec.phase,
                            verdict=Verdict.FAIL,
                            statement=statement(
                                "run one gate that composes the read-only verbs",
                                "no runner defines a check verb"),
                            remediation="Define check as format-check, then typecheck, then test.")])

    concerns = _composition_concerns(check.command, resolved)
    present = [c for c in CONCERNS if c in concerns]
    missing = [c for c in CONCERNS if c not in concerns]
    detail = (f"check ({check.runner}) composes: "
              + (", ".join(present) if present else "nothing"))

    if not missing:
        return _outcome(spec, Verdict.PASS, detail)

    verdict = Verdict.PARTIAL if present else Verdict.FAIL
    return _outcome(spec, verdict, detail + f" — missing {', '.join(missing)}", [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
        statement=statement(
            "trust one gate to verify the change set",
            f"the {check.runner} check verb does not invoke {', '.join(missing)}"),
        evidence=[Evidence(check.runner, note=check.command)],
        remediation="Make check invoke a format-check, a typecheck and the test suite, in that "
                    "order, so one command is the gate.")])


# ===========================================================================
# CMD-03 — no divergent second definition
# ===========================================================================

#: How a delegating `check` invokes the primary runner, per known primary.
_DELEGATION_PATTERNS: dict[str, re.Pattern] = {
    "package.json": re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?check\b"),
    "Makefile": re.compile(r"(?:\bmake\b|\$\(MAKE\))\s+check\b"),
    "Taskfile.yml": re.compile(r"\btask\s+check\b"),
    "Taskfile.yaml": re.compile(r"\btask\s+check\b"),
    "pyproject.toml": re.compile(r"\b(?:poe|task|taskipy|invoke)\s+check\b"),
    "build.gradle": re.compile(r"\b(?:\./gradlew|gradle)\s+check\b"),
    "build.gradle.kts": re.compile(r"\b(?:\./gradlew|gradle)\s+check\b"),
    "pom.xml": re.compile(r"\b(?:\./mvnw|mvn)\b[^&|;]*\bcheck\b"),
}


def _delegates_to(command: str, primary: str, secondary: str) -> bool:
    pattern = _DELEGATION_PATTERNS.get(primary)
    if pattern and pattern.search(command):
        return True
    for segment in _segments(command):
        target = _runner_target(segment)
        if target == "check":
            invoked = _invoked_runner(segment)
            if invoked != secondary:
                return True
    return False


def _invoked_runner(segment: str) -> str | None:
    if _NPM_RE.search(segment):
        return "package.json"
    if _YARN_RE.search(segment):
        return "package.json"
    if _TASK_RE.search(segment):
        return "Makefile"
    return None


def check_cmd03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _unknown(spec, "no recognised verb runner, so no second definition can be read")

    check_defs = [(runner, commands["check"])
                  for runner, commands in declared if "check" in commands]
    if len(check_defs) <= 1:
        detail = ("one runner defines the gate"
                  if check_defs else "no runner defines check, so there is nothing to diverge")
        return _outcome(spec, Verdict.PASS, detail)

    primary = _ordered_runners({runner for runner, _cmd in check_defs})[0]
    divergent = [(runner, command) for runner, command in check_defs
                 if runner != primary and not _delegates_to(command, primary, runner)]

    if not divergent:
        return _outcome(spec, Verdict.PASS,
                        f"{len(check_defs)} runners define check; all but {primary} delegate to it")

    detail = "; ".join(f"{runner} defines its own check" for runner, _cmd in divergent)
    return _outcome(spec, Verdict.FAIL, detail, [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement(
            "know which check definition is authoritative",
            f"{', '.join(runner for runner, _cmd in divergent)} compose the gate independently of "
            f"the primary runner {primary}"),
        evidence=[Evidence(runner, note=command) for runner, command in divergent],
        remediation=f"Make the second runner delegate to the {primary} check (for example "
                    f"`npm run check`), or delete its duplicate gate.")])


# ===========================================================================
# CMD-04 — write verbs separated from read-only verbs
# ===========================================================================

def _write_invocations(command: str) -> list[str]:
    found: set[str] = set()
    for segment in _segments(command):
        target = _runner_target(segment)
        if target in MUTATING_VERBS:
            found.add(target)
        for write_verb, patterns in _WRITER_PATTERNS:
            if any(re.search(p, segment, re.IGNORECASE) for p in patterns):
                found.add(write_verb)
    return sorted(found)


def check_cmd04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _unknown(spec, "no recognised verb runner, so read-only verbs cannot be read")

    resolved = resolve_verbs(inventory, stack)
    offenders: list[tuple[str, VerbBinding, list[str]]] = []
    for verb in READ_ONLY_VERBS:
        binding = resolved.get(verb)
        if binding is None:
            continue
        writes = _write_invocations(binding.command)
        if writes:
            offenders.append((verb, binding, writes))

    if not offenders:
        return _outcome(spec, Verdict.PASS,
                        "no read-only verb invokes a write verb")

    detail = "; ".join(f"{verb} -> {', '.join(writes)}"
                       for verb, _binding, writes in offenders)
    return _outcome(spec, Verdict.FAIL, detail, [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement(
            "verify a change set without mutating the working tree",
            f"{len(offenders)} read-only verb(s) invoke a write verb: {detail}"),
        evidence=[Evidence(binding.runner, note=command)
                  for _verb, binding, _writes in offenders for command in (binding.command,)],
        remediation="Keep write verbs (format, install, clean, build) out of verification verbs; "
                    "a gate composes the read-only form (format:check), never the writing one.")])


IMPLEMENTATIONS = {
    "CMD-01": check_cmd01,
    "CMD-02": check_cmd02,
    "CMD-03": check_cmd03,
    "CMD-04": check_cmd04,
}
