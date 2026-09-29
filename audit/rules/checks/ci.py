"""`CI` pack — continuous integration.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables. The normative sentence is the
one-command-surface note in the Phase 1 activities block.

Implemented here: `CI-01` … `CI-03`.

The pack verifies that a repository's CI is *the same command surface* an agent runs locally, not a
second, secret one. Workflow files are read through `audit.scan`; the local verbs they are compared
against come from `audit.rules.checks._common`.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CI-01** — a workflow file exists (`audit.stack.CI_PROVIDERS` globs) **and** at least one of them
  declares a pull-request trigger (GitHub `pull_request`/`pull_request_target`, GitLab
  `merge_request`, Azure `pr:`, Jenkins `changeRequest`). Workflows present but no such trigger ⇒
  `PARTIAL`. No workflow file at all ⇒ `FAIL` — a PR-triggered pipeline is a Phase-1 deliverable.
* **CI-02** — the set of framework verbs (`audit.stack.VERBS`) the workflows invoke, against the
  verbs `CMD-01` resolves locally. A CI command whose verb has no local definition is a parity
  break ⇒ `FAIL`. The read-only local verbs the CI never exercises are reported in `detail` but do
  not fail the check, because CI may legitimately delegate to the composed `check` gate. With **no
  resolvable local verb** there is nothing to compare ⇒ `UNKNOWN`.
* **CI-03** — every CI command that invokes a runner target (`npm run <x>`, `make <x>`, …) with no
  local runner entry is listed as a finding, so an agent can see which CI steps it cannot reproduce.
  Framework-verb invocations are `CI-02`'s subject and are not repeated here; package-manager
  plumbing (`npm ci`, `npm publish`) and shell automation (`gh`, `echo`) are not project tools and
  are ignored. No findings ⇒ `PASS`.

Deliberate limits, recorded rather than hidden. **YAML is not parsed.** This module is a minimal,
documented text scan: it recognises `run:` / `script:` / `command:` scalar and block-scalar steps,
splits them on shell operators, and matches triggers by pattern. Anchors, expressions, `uses:`
steps, matrix expansion and full YAML semantics are out of scope, so a command hidden inside an
expression is not seen. **Verb mapping is textual**, reusing the runner-indirection idea from
`CMD-01`; an ecosystem outside that set is not mapped. Neither limit produces a `PASS` by guessing:
an unmapped command is simply not counted as evidence.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.probes import MUTATING_VERBS
from audit.rules.checks._common import resolve_verbs, runner_commands
from audit.stack import CI_PROVIDERS, VERBS

#: The read-only verbs a CI pipeline may be expected to exercise (everything but a write verb).
READ_ONLY_VERBS: tuple[str, ...] = tuple(v for v in VERBS if v not in MUTATING_VERBS)

#: Pull-request trigger patterns, per CI provider. Matched against the raw workflow text.
_PR_TRIGGER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "github": (re.compile(r"(?m)^\s*pull_request(?:_target)?\s*:"),
               re.compile(r"\bon\s*:\s*\[[^\]]*pull_request")),
    "gitlab": (re.compile(r"merge_request", re.IGNORECASE),),
    "azure": (re.compile(r"(?m)^\s*pr\s*:"),),
    "jenkins": (re.compile(r"changeRequest", re.IGNORECASE),),
}

#: Step keys that carry commands, across the workflow dialects this scan understands.
_STEP_KEY_RE = re.compile(r"^(\s*)(?:-\s+)?(run|script|command|commands|bash)\s*:\s*(.*)$")
_BLOCK_SCALAR_VALUES = frozenset({"|", "|-", "|+", ">", ">-", ">+", ""})
_COMMAND_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

#: Runner indirection: how a command names a verb/script through its runner.
_NPM_RE = re.compile(r"\b(?:npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_.-]+)")
_YARN_RE = re.compile(r"\byarn\s+(?:run\s+)?([A-Za-z0-9:_.-]+)")
_TASK_RE = re.compile(r"\b(?:make|task|just|mise)\s+(?:-\S+\s+)*([A-Za-z0-9:_.-]+)")
_GRADLE_RE = re.compile(r"\b(?:\./)?(?:gradlew|gradle)\s+([A-Za-z0-9:_.-]+)")
_RUNNER_TARGET_RES = (_NPM_RE, _YARN_RE, _TASK_RE, _GRADLE_RE)

#: Direct tool invocations, mapped to the framework verb they satisfy. `format:check` precedes
#: `format` and `security` precedes the rest so the more specific form wins.
_DIRECT_VERB_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (verb, tuple(re.compile(p) for p in patterns))
    for verb, patterns in (
        ("format:check", (
            r"\bprettier\b[^&|;]*--check\b", r"\bruff\s+format\b[^&|;]*--(?:check|diff)\b",
            r"\bbiome\s+ci\b", r"\bblack\b[^&|;]*--check\b",
            r"\bcargo\s+fmt\b[^&|;]*--check\b",
            r"\bdotnet\s+format\b[^&|;]*--verify-no-changes\b",
        )),
        ("format", (
            r"\bprettier\b[^&|;]*(?:--write|-w)\b", r"\bruff\s+format\b", r"\bbiome\s+format\b",
            r"\bblack\b", r"\bgofmt\b[^&|;]*\s-w\b", r"\bcargo\s+fmt\b",
        )),
        ("typecheck", (
            r"\btsc\b", r"\bmypy\b", r"\bpyright\b", r"\bbasedpyright\b",
            r"\bcargo\s+check\b", r"\bgo\s+vet\b",
        )),
        ("lint", (
            r"\beslint\b", r"\bruff\s+check\b", r"\bflake8\b", r"\bpylint\b",
            r"\bgolangci-lint\b", r"\bclippy\b", r"\brubocop\b",
            r"\bbiome\s+(?:check|lint)\b", r"\bstylelint\b",
        )),
        ("test", (
            r"\bvitest\b", r"\bjest\b", r"\bmocha\b", r"\bpytest\b",
            r"python3?\s+-m\s+(?:unittest|pytest)", r"\bgo\s+test\b", r"\bcargo\s+test\b",
            r"\bdotnet\s+test\b", r"\brspec\b", r"\bphpunit\b",
        )),
        ("security", (
            r"\bnpm\s+audit\b", r"\b(?:pnpm|yarn|bun)\s+audit\b", r"\bpip-audit\b",
            r"\bsafety\s+check\b", r"\bosv-scanner\b", r"\bcargo\s+audit\b",
            r"\bgovulncheck\b", r"\bsnyk\b", r"\btrivy\b", r"\bgrype\b",
            r"\bbundler-audit\b", r"\bcomposer\s+audit\b", r"\baudit-ci\b",
        )),
    )
)

#: Package-manager subcommands that are tooling, not project scripts. Never flagged as CI-only.
_PM_BUILTINS: frozenset[str] = frozenset({
    "ci", "install", "i", "publish", "pack", "version", "exec", "init", "link", "dedupe",
    "prune", "update", "outdated", "ls", "why", "config", "cache", "login", "logout", "whoami",
    "doctor", "help", "start", "stop", "restart", "add", "remove", "uninstall",
})


def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(spec, cannot: str, because: str, verdict: Verdict,
             evidence: list[Evidence], remediation: str) -> Finding:
    return Finding(check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
                   statement=statement(cannot, because), evidence=evidence, remediation=remediation)


# ---------------------------------------------------------------------------
# workflow discovery and a minimal, documented YAML scan
# ---------------------------------------------------------------------------

def _workflows(inventory) -> list[tuple[str, str]]:
    """Every present workflow file as ``(provider, rel)``, in provider order then path order."""
    found: list[tuple[str, str]] = []
    for provider, globs in CI_PROVIDERS.items():
        for rel in sorted(inventory.match(*globs)):
            found.append((provider, rel))
    return found


def _has_pr_trigger(provider: str, text: str) -> bool:
    patterns = _PR_TRIGGER_PATTERNS.get(provider)
    if not patterns:
        # circleci / buildkite declare triggers in the VCS integration, not the checked-in file.
        return False
    return any(pattern.search(text) for pattern in patterns)


def _split_commands(raw: str) -> list[str]:
    command = raw.strip()
    if command.startswith("- "):
        command = command[2:].strip()
    if not command or command.startswith("#"):
        return []
    return [part for part in (p.strip() for p in _COMMAND_SPLIT_RE.split(command)) if part]


def _iter_run_commands(text: str) -> list[tuple[int, str]]:
    """Extract ``(line_no, command)`` from run-style steps. A minimal, documented text scan."""
    lines = text.splitlines()
    commands: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = _STEP_KEY_RE.match(lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        value = match.group(3).strip()
        if value and value not in _BLOCK_SCALAR_VALUES:
            commands.extend((index + 1, cmd) for cmd in _split_commands(value))
            index += 1
            continue
        # Block scalar (or a list under `script:`/`commands:`): collect the indented body.
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if candidate.strip() == "":
                body.append("")
                cursor += 1
                continue
            if len(candidate) - len(candidate.lstrip()) <= indent:
                break
            body.append(candidate)
            cursor += 1
        for offset, raw in enumerate(body, start=index + 2):
            commands.extend((offset, cmd) for cmd in _split_commands(raw))
        index = cursor
    return commands


def _runner_target(command: str) -> str | None:
    for pattern in _RUNNER_TARGET_RES:
        match = pattern.search(command)
        if match:
            return match.group(1)
    return None


def _command_verb(command: str) -> str | None:
    """The framework verb a command invokes, by runner indirection or direct tool, else ``None``."""
    target = _runner_target(command)
    if target in VERBS:
        return target
    for verb, patterns in _DIRECT_VERB_PATTERNS:
        if any(pattern.search(command) for pattern in patterns):
            return verb
    return None


def _all_run_commands(inventory, workflows) -> list[tuple[str, int, str]]:
    """Every ``(rel, line_no, command)`` across the workflows, deterministically ordered."""
    out: list[tuple[str, int, str]] = []
    for _provider, rel in workflows:
        text = inventory.read(rel)
        if text:
            out.extend((rel, line, command) for line, command in _iter_run_commands(text))
    return out


# ===========================================================================
# CI-01 — pipeline present, triggered on PRs
# ===========================================================================

def check_ci01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    workflows = _workflows(inventory)
    if not workflows:
        providers = ", ".join(sorted(stack.ci_providers)) or "none"
        return _outcome(spec, Verdict.FAIL,
                        f"no CI workflow file (detected providers: {providers})", [_finding(
            spec, "rely on CI to verify a change set",
            "no CI workflow file exists",
            Verdict.FAIL,
            [Evidence(rel) for rel in sorted(inventory.paths())[:1]] or [Evidence("<repository>")],
            "Add a PR-triggered workflow (for example .github/workflows/ci.yml) that runs the same "
            "verbs the local command surface defines.")])

    triggered = [(provider, rel) for provider, rel in workflows
                 if _has_pr_trigger(provider, inventory.read(rel) or "")]
    if triggered:
        detail = "; ".join(f"{rel} ({provider})" for provider, rel in triggered)
        return _outcome(spec, Verdict.PASS, f"PR-triggered: {detail}")

    providers = ", ".join(sorted({provider for provider, _rel in workflows}))
    return _outcome(spec, Verdict.PARTIAL,
                    f"{len(workflows)} workflow(s) ({providers}) but none declares a PR trigger",
                    [_finding(
        spec, "trust CI to run before a change reaches the default branch",
        "workflow files exist but none declares a pull-request trigger",
        Verdict.PARTIAL, [Evidence(rel) for _provider, rel in workflows],
        "Add a pull-request trigger (GitHub `on: pull_request`, GitLab `merge_request`, …) so the "
        "pipeline runs on the PR rather than only after merge.")])


# ===========================================================================
# CI-02 — local↔CI parity
# ===========================================================================

def check_ci02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local = resolve_verbs(inventory, stack)
    if not local:
        return _unknown(spec, "no local verb resolves on any runner, so CI cannot be compared to it")

    commands = _all_run_commands(inventory, _workflows(inventory))
    ci_verbs = {verb for _rel, _line, command in commands
                if (verb := _command_verb(command)) is not None}

    extra = sorted(verb for verb in ci_verbs if verb not in local)
    missing = sorted(verb for verb in READ_ONLY_VERBS
                     if verb in local and verb not in ci_verbs)

    detail = (f"CI verbs: {', '.join(sorted(ci_verbs)) or 'none'}; "
              f"local read-only verbs not exercised: {', '.join(missing) or 'none'}")

    if extra:
        return _outcome(spec, Verdict.FAIL, detail, [_finding(
            spec, "run the same command surface locally that CI runs",
            f"CI invokes framework verb(s) with no local definition: {', '.join(extra)}",
            Verdict.FAIL,
            [Evidence(rel, line=line, note=command)
             for rel, line, command in commands if _command_verb(command) in extra],
            "Define the missing verb(s) on the local runner, or stop invoking them from CI, so the "
            "two surfaces agree.")])

    return _outcome(spec, Verdict.PASS, detail)


# ===========================================================================
# CI-03 — CI-only steps flagged
# ===========================================================================

def check_ci03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local_targets: set[str] = set()
    for _runner, commands in runner_commands(inventory):
        local_targets.update(commands)

    findings: list[Finding] = []
    for rel, line, command in _all_run_commands(inventory, _workflows(inventory)):
        if _command_verb(command) is not None:
            continue                                # CI-02's subject, not repeated here
        target = _runner_target(command)
        if target is None or target in _PM_BUILTINS or target in local_targets:
            continue
        findings.append(_finding(
            spec, "reproduce a CI step on the local command surface",
            f"{rel}:{line} runs `{command}` with no local runner entry for `{target}`",
            Verdict.FAIL, [Evidence(rel, line=line, note=command)],
            f"Add a local script/target for `{target}`, or document why the step is CI-only."))

    if not findings:
        return _outcome(spec, Verdict.PASS, "no CI-only steps")
    return _outcome(spec, Verdict.FAIL, f"{len(findings)} CI-only step(s)", findings)


IMPLEMENTATIONS = {
    "CI-01": check_ci01,
    "CI-02": check_ci02,
    "CI-03": check_ci03,
}
