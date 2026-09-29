"""`TOOL` pack — tooling.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables.

Implemented here: `TOOL-01` … `TOOL-06`.

The pack verifies that the tools an agent leans on are configured **and reachable through the command
surface**, not merely installed. Verb evidence comes from `audit.rules.checks._common.resolve_verbs`;
config evidence is a small, documented set of filenames per concern. A config file with no way to
invoke the tool is `PARTIAL`, never `PASS` — a formatter an agent cannot run is not a formatter.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **TOOL-01** — a formatter config file (prettier/black/ruff/dprint/config-in-package.json or
  pyproject) **and** a resolvable `format` write verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-02** — a linter config file (eslint/ruff/flake8/pylint/golangci/rubocop/biome) **and** a
  resolvable `lint` read-only verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-03** — language-appropriate strict configuration: `tsconfig.json`/`jsconfig.json`,
  `mypy`/`pyright` strict, or `.NET` `<Nullable>enable</Nullable>`. Configured but non-strict ⇒
  `PARTIAL`. An ecosystem with no strict-config concept in this table (go, rust, jvm, ruby, php) ⇒
  `UNKNOWN`. It never invents a type checker for an ecosystem that has none.
* **TOOL-04** — a resolved verb whose command runs a known dependency-audit tool (`npm audit`,
  `pip-audit`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`, …). The verb is the evidence;
  it is **not** run (that would be Tier C). A `security` verb that runs something else ⇒ `PARTIAL`.
* **TOOL-05** — a wired hook chain: `.pre-commit-config.yaml`, `lefthook.yml`, a declared
  `core.hooksPath`, or `.husky/` referenced by a `prepare`/install script. Present but unwired ⇒
  `PARTIAL`.
* **TOOL-06** — a commit-message rule: a commitlint config, a `commit-msg` hook, or an equivalent
  pre-commit/lefthook stage. Absent ⇒ `FAIL` (`COSMETIC`).

Deliberate limits, recorded rather than hidden. **Config detection is filename-based** against the
documented set below; a config that lives somewhere unexpected is not seen. **Verb resolution is
v1's**: only the runner manifests `_common` understands contribute verbs. When there is no
recognised ecosystem, no runner manifest, and no relevant config, the verdict is `UNKNOWN` — an
unrecognised repository is not proof of absence.
"""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import resolve_verbs, runner_commands
from audit.stack import extract_npm_scripts

#: Formatter configuration filenames, across the ecosystems the catalogue names.
_FORMATTER_CONFIG_NAMES: tuple[str, ...] = (
    ".prettierrc", ".prettierrc.json", ".prettierrc.json5", ".prettierrc.yml", ".prettierrc.yaml",
    ".prettierrc.toml", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs",
    "prettier.config.js", "prettier.config.cjs", "prettier.config.mjs",
    "biome.json", "biome.jsonc", ".dprint.json", "dprint.json",
    "ruff.toml", ".ruff.toml", "black.toml", ".black.toml",
    "rustfmt.toml", ".rustfmt.toml", ".clang-format",
    "pint.json", ".php-cs-fixer.php", ".php-cs-fixer.dist.php",
)

#: Linter configuration filenames.
_LINTER_CONFIG_NAMES: tuple[str, ...] = (
    ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.mjs",
    ".eslintrc.yml", ".eslintrc.yaml", "eslint.config.js", "eslint.config.cjs",
    "eslint.config.mjs", "eslint.config.ts", "biome.json", "biome.jsonc",
    "ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", "pylintrc",
    ".golangci.yml", ".golangci.yaml", ".golangci.toml", "clippy.toml", ".clippy.toml",
    ".rubocop.yml", "checkstyle.xml", ".stylelintrc", ".stylelintrc.json",
    "phpcs.xml", ".phpcs.xml",
)

#: Commit-message convention configuration filenames.
_COMMITLINT_CONFIG_NAMES: tuple[str, ...] = (
    "commitlint.config.js", "commitlint.config.cjs", "commitlint.config.mjs",
    "commitlint.config.ts", ".commitlintrc", ".commitlintrc.json", ".commitlintrc.js",
    ".commitlintrc.cjs", ".commitlintrc.yml", ".commitlintrc.yaml", ".commitlintrc.toml",
)

#: Hook managers whose mere presence is a wired chain.
_WIRED_HOOK_FILES: tuple[str, ...] = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml")

#: Ecosystems for which this pack knows a strict type-check configuration.
_TYPECHECK_ECOSYSTEMS: frozenset[str] = frozenset({"node", "python", "dotnet"})

#: Dependency-audit invocations. The verb is evidence; it is never executed.
_AUDIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(re.compile(p) for p in (
    r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?audit\b",
    r"\bpip-audit\b", r"\bpip\s+audit\b", r"\bsafety\s+check\b",
    r"\bosv-scanner\b", r"\bcargo\s+audit\b", r"\bgovulncheck\b",
    r"\bsnyk\b", r"\btrivy\b", r"\bgrype\b",
    r"\bbundler-audit\b", r"\bbundle\s+audit\b", r"\bcomposer\s+audit\b",
    r"\baudit-ci\b", r"\bdotnet\s+list\s+package\b[^&|;]*--vulnerable\b",
))


def _outcome(spec, verdict: Verdict, detail: str = "",
             findings: list[Finding] | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, detail=detail, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _recognised(stack, inventory) -> bool:
    """Whether there is any basis to judge: a detected ecosystem or a recognised verb runner."""
    return bool(stack.ecosystems) or bool(runner_commands(inventory))


def _present(inventory, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if inventory.has(name)]


def _read_matches(inventory, rel: str, pattern: str) -> bool:
    text = inventory.read(rel)
    return bool(text and re.search(pattern, text))


def _finding(spec, cannot: str, because: str, verdict: Verdict,
             evidence: list[Evidence], remediation: str,
             path: str | None = None) -> Finding:
    return Finding(check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
                   statement=statement(cannot, because), evidence=evidence,
                   remediation=remediation, path=path)


def _manifest_evidence(inventory) -> list[Evidence]:
    """Real runner manifests as evidence, so an absence finding still cites concrete paths."""
    evidence = [Evidence(runner) for runner, _cmds in runner_commands(inventory)]
    return evidence or [Evidence("<repository>", note="detected ecosystem")]


# ===========================================================================
# config readers
# ===========================================================================

def _formatter_config(inventory) -> list[str]:
    found = _present(inventory, _FORMATTER_CONFIG_NAMES)
    if _read_matches(inventory, "pyproject.toml", r"(?m)^\[tool\.(?:black|ruff|autopep8|yapf)\]"):
        found.append("pyproject.toml [tool.*]")
    if _read_matches(inventory, "package.json", r'"prettier"\s*:'):
        found.append("package.json prettier")
    return found


def _linter_config(inventory) -> list[str]:
    found = _present(inventory, _LINTER_CONFIG_NAMES)
    if _read_matches(inventory, "pyproject.toml", r"(?m)^\[tool\.(?:ruff|pylint|flake8)\]"):
        found.append("pyproject.toml [tool.*]")
    if _read_matches(inventory, "package.json", r'"eslintConfig"\s*:'):
        found.append("package.json eslintConfig")
    return found


def _json_true(text: str, key: str) -> bool:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    options = data.get("compilerOptions")
    if isinstance(options, dict) and options.get(key) is True:
        return True
    return data.get(key) is True


def _typecheck_signals(inventory, stack) -> tuple[list[str], list[str]]:
    """Return ``(strict, nonstrict)`` config evidence for the strict type-checker check."""
    strict: list[str] = []
    nonstrict: list[str] = []

    for rel, key in (("tsconfig.json", "strict"), ("jsconfig.json", "checkJs")):
        text = inventory.read(rel)
        if text is None:
            continue
        (strict if _json_true(text, key) else nonstrict).append(f"{rel}:{key}")

    for rel in ("mypy.ini", ".mypy.ini"):
        if not inventory.has(rel):
            continue
        (strict if _read_matches(inventory, rel, r"(?im)^\s*strict\s*=\s*true")
         else nonstrict).append(rel)

    for rel, strict_re, present_re in (
        ("pyproject.toml", r"(?ms)^\[tool\.(?:mypy|pyright)\][^\[]*?"
                          r"(?:strict\s*=\s*true|typeCheckingMode\s*=\s*\"strict\")",
         r"(?m)^\[tool\.(?:mypy|pyright)\]"),
        ("setup.cfg", r"(?ms)^\[mypy\][^\[]*?strict\s*=\s*true", r"(?m)^\[mypy\]"),
    ):
        if not inventory.has(rel):
            continue
        if _read_matches(inventory, rel, strict_re):
            strict.append(f"{rel} [mypy/pyright]")
        elif _read_matches(inventory, rel, present_re):
            nonstrict.append(f"{rel} [mypy/pyright]")

    pyright = inventory.read("pyrightconfig.json")
    if pyright is not None:
        if re.search(r'"typeCheckingMode"\s*:\s*"strict"', pyright) or re.search(r'"strict"\s*:', pyright):
            strict.append("pyrightconfig.json")
        else:
            nonstrict.append("pyrightconfig.json")

    for rel in inventory.match("*.csproj") + inventory.match("Directory.Build.props",
                                                             "Directory.Build.targets"):
        text = inventory.read(rel)
        if not text:
            continue
        if re.search(r"<Nullable>\s*enable\s*</Nullable>", text, re.IGNORECASE):
            strict.append(f"{rel}:Nullable")
        elif "<Nullable>" in text:
            nonstrict.append(rel)
    if inventory.has("global.json"):
        nonstrict.append("global.json")

    binding = resolve_verbs(inventory, stack).get("typecheck")
    if binding and re.search(r"--strict\b", binding.command):
        strict.append(f"{binding.runner}:typecheck --strict")

    return strict, nonstrict


def _hook_wiring(inventory) -> tuple[list[str], list[str]]:
    """Return ``(wired, configured)`` hook-chain evidence."""
    wired = _present(inventory, _WIRED_HOOK_FILES)
    configured: list[str] = []

    hooks_path = inventory.grep(r"core\.hooksPath")
    if hooks_path:
        wired.append(f"{hooks_path[0][0]} core.hooksPath")

    githooks = inventory.match(".githooks/*")
    if githooks and not hooks_path:
        configured.append(".githooks/")

    husky = inventory.match(".husky/*")
    if husky:
        if _husky_referenced(inventory):
            wired.append(".husky/ (referenced)")
        else:
            configured.append(".husky/ (not referenced)")

    return wired, configured


def _husky_referenced(inventory) -> bool:
    scripts = extract_npm_scripts(inventory)
    return any("husky" in command for command in scripts.values())


def _commit_rule(inventory) -> list[str]:
    found = _present(inventory, _COMMITLINT_CONFIG_NAMES)
    if _read_matches(inventory, "package.json", r'"commitlint"\s*:'):
        found.append("package.json commitlint")
    for rel in (".husky/commit-msg", ".githooks/commit-msg"):
        if inventory.has(rel):
            found.append(rel)
    for rel in (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"):
        if _read_matches(inventory, rel, r"(?i)commit-msg|commitlint|conventional"):
            found.append(f"{rel}:commit-msg")
    return found


# ===========================================================================
# TOOL-01 — formatter configured
# ===========================================================================

def check_tool01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configs = _formatter_config(inventory)
    binding = resolve_verbs(inventory, stack).get("format")

    if configs and binding:
        return _outcome(spec, Verdict.PASS,
                        f"formatter {', '.join(configs)} + {binding.runner} format verb")

    if configs:
        return _outcome(spec, Verdict.PARTIAL,
                        f"formatter config present ({', '.join(configs)}) but no resolvable "
                        f"format write verb", [_finding(
            spec, "format a change set the same way every time",
            "a formatter is configured but no runner exposes a format verb",
            Verdict.PARTIAL,
            [Evidence(configs[0])],
            "Add a format verb (for example `prettier --write .`) to the runner so the configured "
            "formatter is reachable by name.")])

    if binding:
        return _outcome(spec, Verdict.PARTIAL,
                        f"format verb on {binding.runner} but no formatter config file", [_finding(
            spec, "format a change set the same way every time",
            "a format verb exists but no formatter configuration file is present",
            Verdict.PARTIAL, [Evidence(binding.runner, note=binding.command)],
            "Commit a formatter config (for example `.prettierrc.json`) so the tool's behaviour "
            "does not depend on defaults.")])

    if _recognised(stack, inventory):
        return _outcome(spec, Verdict.FAIL, "no formatter config and no format verb", [_finding(
            spec, "format a change set the same way every time",
            "no formatter is configured and no format verb is defined",
            Verdict.FAIL, [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
            "Add a formatter config and a format write verb (prettier, black, ruff format, …).")])

    return _unknown(spec, "no recognised ecosystem, runner manifest or formatter config, so a "
                          "formatter cannot be ruled out")


# ===========================================================================
# TOOL-02 — linter configured
# ===========================================================================

def check_tool02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configs = _linter_config(inventory)
    binding = resolve_verbs(inventory, stack).get("lint")

    if configs and binding:
        return _outcome(spec, Verdict.PASS,
                        f"linter {', '.join(configs)} + {binding.runner} lint verb")

    if configs:
        return _outcome(spec, Verdict.PARTIAL,
                        f"linter config present ({', '.join(configs)}) but no resolvable lint verb",
                        [_finding(
            spec, "catch lint regressions before they land",
            "a linter is configured but no runner exposes a lint verb",
            Verdict.PARTIAL, [Evidence(configs[0])],
            "Add a lint verb (for example `eslint .` or `ruff check`) to the runner so the "
            "configured linter is reachable by name.")])

    if binding:
        return _outcome(spec, Verdict.PARTIAL,
                        f"lint verb on {binding.runner} but no linter config file", [_finding(
            spec, "catch lint regressions before they land",
            "a lint verb exists but no linter configuration file is present",
            Verdict.PARTIAL, [Evidence(binding.runner, note=binding.command)],
            "Commit a linter config (for example `.eslintrc.json` or `[tool.ruff]`) so the rule set "
            "does not depend on defaults.")])

    if _recognised(stack, inventory):
        return _outcome(spec, Verdict.FAIL, "no linter config and no lint verb", [_finding(
            spec, "catch lint regressions before they land",
            "no linter is configured and no lint verb is defined",
            Verdict.FAIL, [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
            "Add a linter config and a lint read-only verb (eslint, ruff, flake8, golangci-lint, …).")])

    return _unknown(spec, "no recognised ecosystem, runner manifest or linter config, so a linter "
                          "cannot be ruled out")


# ===========================================================================
# TOOL-03 — type checker configured
# ===========================================================================

def check_tool03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    strict, nonstrict = _typecheck_signals(inventory, stack)

    if strict:
        return _outcome(spec, Verdict.PASS, f"strict config: {', '.join(sorted(set(strict)))}")

    if nonstrict:
        return _outcome(spec, Verdict.PARTIAL,
                        f"type checker configured but not strict: {', '.join(sorted(set(nonstrict)))}",
                        [_finding(
            spec, "trust the type checker to catch a whole class of defects",
            f"a type-check configuration exists but is not strict "
            f"({', '.join(sorted(set(nonstrict)))})",
            Verdict.PARTIAL,
            [Evidence(rel) for rel in sorted(set(nonstrict))],
            "Turn on strict mode (tsconfig `strict: true`, mypy `strict = true`, pyright "
            "`typeCheckingMode: \"strict\"`) so the checker's findings are trustworthy.")])

    if set(stack.ecosystems) & _TYPECHECK_ECOSYSTEMS:
        return _outcome(spec, Verdict.FAIL, "no strict type-check configuration", [_finding(
            spec, "trust the type checker to catch a whole class of defects",
            "no strict type-check configuration is present for the detected ecosystem "
            f"({', '.join(sorted(set(stack.ecosystems)))})",
            Verdict.FAIL, _manifest_evidence(inventory),
            "Add a strict type-check configuration (tsconfig.json strict, mypy/pyright strict, or "
            ".NET `<Nullable>enable</Nullable>`).")])

    return _unknown(spec, "no recognised strict type-check configuration and no ecosystem this "
                          "pack knows one for, so type-checking cannot be judged")


# ===========================================================================
# TOOL-04 — dependency / security scan verb
# ===========================================================================

def _is_audit_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in _AUDIT_PATTERNS)


def check_tool04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    bindings = resolve_verbs(inventory, stack)
    audits = [(verb, b) for verb, b in bindings.items() if _is_audit_command(b.command)]

    if audits:
        detail = "; ".join(f"{verb} -> {b.command}" for verb, b in sorted(audits))
        return _outcome(spec, Verdict.PASS, detail)

    security = bindings.get("security")
    if security is not None:
        return _outcome(spec, Verdict.PARTIAL,
                        f"security verb on {security.runner} runs no dependency audit "
                        f"({security.command})", [_finding(
            spec, "know whether a dependency carries a known vulnerability",
            "a security verb exists but it does not run a dependency-audit check",
            Verdict.PARTIAL, [Evidence(security.runner, note=security.command)],
            "Make the security verb run a dependency audit (npm audit, pip-audit, osv-scanner, "
            "cargo audit, govulncheck, snyk).")])

    if _recognised(stack, inventory):
        return _outcome(spec, Verdict.FAIL, "no verb runs a dependency audit", [_finding(
            spec, "know whether a dependency carries a known vulnerability",
            "no resolvable verb runs a dependency-audit check",
            Verdict.FAIL, [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
            "Add a dependency-audit verb (npm audit, pip-audit, osv-scanner, cargo audit, "
            "govulncheck, snyk).")])

    return _unknown(spec, "no recognised ecosystem, runner manifest or dependency-audit verb, so a "
                          "dependency scan cannot be ruled out")


# ===========================================================================
# TOOL-05 — local hook chain active
# ===========================================================================

def check_tool05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    wired, configured = _hook_wiring(inventory)

    if wired:
        return _outcome(spec, Verdict.PASS, f"wired: {', '.join(sorted(set(wired)))}")

    if configured:
        return _outcome(spec, Verdict.PARTIAL,
                        f"hooks present but not wired: {', '.join(sorted(set(configured)))}",
                        [_finding(
            spec, "rely on local hooks to run before a commit",
            f"a hook manager is present but not wired ({', '.join(sorted(set(configured)))})",
            Verdict.PARTIAL, [Evidence(rel.split(" ")[0]) for rel in sorted(set(configured))],
            "Wire the hooks: set `core.hooksPath`, add a `prepare`/install script, or commit a "
            "`.pre-commit-config.yaml`.")])

    if stack.ecosystems:
        return _outcome(spec, Verdict.FAIL, "no hook chain configured", [_finding(
            spec, "rely on local hooks to run before a commit",
            "no hook manager is configured",
            Verdict.FAIL, _manifest_evidence(inventory),
            "Adopt a hook manager (pre-commit, lefthook, husky) and wire it so checks run before a "
            "commit rather than only in CI.")])

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a hook chain "
                          "cannot be ruled out")


# ===========================================================================
# TOOL-06 — commit convention enforced
# ===========================================================================

def check_tool06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = _commit_rule(inventory)
    if rules:
        return _outcome(spec, Verdict.PASS, f"commit rule: {', '.join(sorted(set(rules)))}")

    wired, configured = _hook_wiring(inventory)
    if stack.ecosystems or wired or configured:
        return _outcome(spec, Verdict.FAIL, "no commit-message rule", [_finding(
            spec, "rely on a consistent commit-message convention",
            "no commitlint config, commit-msg hook, or equivalent exists",
            Verdict.FAIL,
            _manifest_evidence(inventory),
            "Add a commitlint config or a commit-msg hook so commit messages follow one "
            "convention.")])

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a commit "
                          "convention cannot be judged")


IMPLEMENTATIONS = {
    "TOOL-01": check_tool01,
    "TOOL-02": check_tool02,
    "TOOL-03": check_tool03,
    "TOOL-04": check_tool04,
    "TOOL-05": check_tool05,
    "TOOL-06": check_tool06,
}
