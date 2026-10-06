"""`EXEC` pack — execution determinism.

Anchor: `brownfield-legacy/Phased-Approach.md` § Activities.

Implemented here: `EXEC-01` … `EXEC-07`.

What each check reads and what makes it ``UNKNOWN`` rather than ``FAIL``:

* **EXEC-01** — a toolchain pin appropriate to each **detected** ecosystem (``.nvmrc``, ``engines``,
  ``.python-version``/``requires-python``, ``gradlew``/``mvnw``, ``global.json``,
  ``rust-toolchain.toml``, the ``go`` directive). No recognised ecosystem ⇒ ``UNKNOWN``; an
  ecosystem with no pin in the table (php) is not asserted against.
* **EXEC-02** — the ecosystem's lockfile is **tracked** (``audit.ignore.tracked_files``) and its
  declared dependencies agree with the manifest. ``tracked_files`` returning ``None`` (not a git
  repository, git absent) makes the tracked half ``UNKNOWN`` — never a ``PASS``. Agreement is a
  best-effort stdlib parse; when a manifest or lockfile cannot be parsed reliably the tracked fact
  is reported and consistency is left ``PARTIAL``, never ``PASS`` by inference.
* **EXEC-03** — a devcontainer / compose file / Dockerfile / setup target-script, or a documented
  non-interactive install command in the fenced blocks of README/``AGENTS.md``. Present but
  undocumented ⇒ ``PARTIAL``. No recognised ecosystem ⇒ ``UNKNOWN``: with no build manifest there is
  no way to say what provisioning is expected.
* **EXEC-04** — a set difference: env keys referenced by source against keys declared in the
  committed example file. A documented allow-list of conventional CI/test/host variables lives in
  :data:`_ENV_ALLOWLIST` and :data:`_ENV_ALLOW_PREFIXES`; it is deterministic and kept in code.
* **EXEC-05** — files the scan classifies ``GENERATED`` (including vendored paths) are either
  untracked or carry a generated-file header. Tracked state unavailable ⇒ ``UNKNOWN``.
* **EXEC-06** — every shell command in a fenced README/``AGENTS.md`` block resolves to a
  known tool, a declared verb, an npm script, a Makefile target, a package binary, or a real path.
  Shell builtins and obvious placeholders are skipped, never failed. Line continuations are joined.
* **EXEC-07** — at most one authoritative config per concern (lint, format, test, types, security).
  Only repository-root configs are counted, so a monorepo's per-component configs are not mistaken
  for competition.

Known limitation, recorded rather than hidden: manifest↔lockfile consistency parsing for ecosystems
beyond node/python/rust/go is not attempted, so those ecosystems report the tracked fact and
``PARTIAL`` consistency. This is deliberately conservative — a false ``PASS`` on a stale lockfile is
worse than an honest ``PARTIAL``.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import tracked_files
from audit.rules.checks._common import extract_fenced_commands, resolve_verbs
from audit.scan import Inventory, Kind
from audit.stack import PACKAGE_MANAGERS, extract_npm_scripts, parse_makefile_targets
from audit.rules.payloads import EnvKeys, Payload


def _outcome(spec, verdict: Verdict, summary: str = "",
             findings: list[Finding] | None = None,
             data: Payload | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=summary, data=data, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


# ===========================================================================
# EXEC-01 — toolchain pinned / wrapper committed
# ===========================================================================

_PIN_FILES: dict[str, tuple[str, ...]] = {
    "node": (".nvmrc", ".node-version"),
    "python": (".python-version",),
    "jvm": ("gradlew", "mvnw"),
    "dotnet": ("global.json",),
    "rust": ("rust-toolchain.toml", "rust-toolchain"),
    "ruby": (".ruby-version",),
}
_PINNABLE = frozenset(_PIN_FILES) | {"go"}

#: A shared ``.tool-versions`` line counts for the ecosystem whose name follows it.
_TOOL_VERSIONS = {
    "node": re.compile(r"(?mi)^\s*(?:nodejs|node)\s+\S+"),
    "python": re.compile(r"(?mi)^\s*python\s+\S+"),
    "rust": re.compile(r"(?mi)^\s*rust\s+\S+"),
    "go": re.compile(r"(?mi)^\s*golang\s+\S+"),
}


def _pin_evidence(inv: Inventory, ecosystem: str) -> list[str]:
    evidence = [name for name in _PIN_FILES.get(ecosystem, ()) if inv.has(name)]

    if inv.has(".tool-versions"):
        pattern = _TOOL_VERSIONS.get(ecosystem)
        if pattern and pattern.search(inv.read(".tool-versions") or ""):
            evidence.append(".tool-versions")

    if ecosystem == "node" and inv.has("package.json"):
        try:
            engines = json.loads(inv.read("package.json") or "{}").get("engines")
        except (json.JSONDecodeError, AttributeError):
            engines = None
        if isinstance(engines, dict) and engines.get("node"):
            evidence.append("package.json (engines.node)")

    if ecosystem == "python" and inv.has("pyproject.toml"):
        if re.search(r"(?m)^\s*requires-python\s*=", inv.read("pyproject.toml") or ""):
            evidence.append("pyproject.toml (requires-python)")

    if ecosystem == "go" and inv.has("go.mod"):
        if re.search(r"(?m)^\s*go\s+\d", inv.read("go.mod") or ""):
            evidence.append("go.mod (go directive)")

    return sorted(dict.fromkeys(evidence))


def check_exec01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ecosystems = sorted(stack.ecosystems & _PINNABLE)
    if not ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no toolchain pin can be chosen")

    findings: list[Finding] = []
    pinned: list[str] = []
    unpinned: list[str] = []
    for ecosystem in ecosystems:
        evidence = _pin_evidence(inventory, ecosystem)
        if evidence:
            pinned.append(f"{ecosystem} ({', '.join(evidence)})")
            continue
        unpinned.append(ecosystem)
        findings.append(Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                f"reproduce the {ecosystem} toolchain",
                f"the detected {ecosystem} project pins no toolchain version"),
            remediation=f"Commit the pin appropriate to {ecosystem} — "
                        f"{', '.join(_PIN_FILES.get(ecosystem) or ('.tool-versions',))} "
                        f"— so the agent's runtime is the repository's, not the host's.",
        ))

    if findings:
        return _outcome(spec, Verdict.FAIL, f"unpinned: {', '.join(unpinned)}", findings)
    return _outcome(spec, Verdict.PASS, "pinned: " + "; ".join(pinned))


# ===========================================================================
# EXEC-02 — lockfile committed and consistent
# ===========================================================================

#: Ecosystem -> package managers whose files are lockfiles (manifest-as-lock entries are excluded).
_ECOSYSTEM_MANAGERS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "pnpm", "yarn", "bun"),
    "python": ("poetry", "uv", "pipenv"),
    "jvm": ("gradle",),
    "rust": ("cargo",),
    "go": ("gomod",),
    "ruby": ("bundler",),
    "php": ("composer",),
}


def _lockfiles_for(ecosystem: str) -> list[str]:
    return [f for manager in _ECOSYSTEM_MANAGERS.get(ecosystem, ())
            for f in PACKAGE_MANAGERS.get(manager, ())]


def _dependency_name(spec_text: str) -> str | None:
    match = re.match(r"^[A-Za-z0-9_.@/-]+", spec_text.strip())
    return match.group(0) if match else None


def _node_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("package.json")
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            deps |= set(block)
    return deps


def _toml_package_names(text: str) -> set[str]:
    names: set[str] = set()
    for block in re.finditer(r"(?ms)^\[\[package\]\]\s*\n(.*?)(?=^\[\[|\Z)", text):
        match = re.search(r"(?m)^\s*name\s*=\s*[\"']([^\"']+)[\"']", block.group(1))
        if match:
            names.add(match.group(1))
    return names


def _node_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    if lockfile == "package-lock.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        deps: set[str] = set()
        packages = data.get("packages")
        if isinstance(packages, dict):
            for key in packages:
                if key:
                    deps.add(key.rsplit("node_modules/", 1)[-1])
        legacy = data.get("dependencies")
        if isinstance(legacy, dict):
            deps |= set(legacy)
        return deps
    if lockfile == "pnpm-lock.yaml":
        deps = set(re.findall(
            r"(?m)^\s{2,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)@[^'\s:]+'?\s*:", text))
        deps |= set(re.findall(
            r"(?m)^\s{4,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)'?:\s*$", text))
        return deps or None
    if lockfile == "yarn.lock":
        deps = set(re.findall(r"(?m)^\"?((?:@[^/\"]+/)?[A-Za-z0-9._-]+)@", text))
        return deps or None
    return None


def _python_manifest_deps(inv: Inventory) -> set[str] | None:
    deps: set[str] = set()
    parsed = False
    text = inv.read("pyproject.toml")
    if text is not None:
        parsed = True
        for block in re.finditer(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text):
            for item in re.findall(r"[\"']([^\"']+)[\"']", block.group(1)):
                name = _dependency_name(item)
                if name:
                    deps.add(name)
        for block in re.finditer(
                r"(?ms)^\[tool\.poetry\.dependencies\]\s*\n(.*?)(?=^\[|\Z)", text):
            for line in block.group(1).splitlines():
                match = re.match(r"^([A-Za-z0-9_.-]+)\s*=", line.strip())
                if match and match.group(1).lower() != "python":
                    deps.add(match.group(1))
    for req in ("requirements.txt", "requirements-dev.txt"):
        req_text = inv.read(req)
        if req_text is None:
            continue
        parsed = True
        for line in req_text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            name = _dependency_name(line)
            if name:
                deps.add(name)
    return deps if parsed else None


def _python_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    if lockfile in ("poetry.lock", "uv.lock"):
        return _toml_package_names(text) or None
    if lockfile == "Pipfile.lock":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        deps: set[str] = set()
        for key in ("default", "develop"):
            block = data.get(key)
            if isinstance(block, dict):
                deps |= set(block)
        return deps or None
    return None


def _cargo_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("Cargo.toml")
    if text is None:
        return None
    deps: set[str] = set()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        header = re.match(r"^\[(.+)\]$", stripped)
        if header:
            in_deps = header.group(1).endswith("dependencies")
            continue
        if in_deps:
            match = re.match(r"^([A-Za-z0-9_-]+)\s*=", stripped)
            if match:
                deps.add(match.group(1))
    return deps


def _go_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("go.mod")
    if text is None:
        return None
    deps: set[str] = set()
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if stripped.startswith("require "):
            parts = stripped.split()
            if len(parts) >= 2:
                deps.add(parts[1])
            continue
        if in_block and stripped and not stripped.startswith("//"):
            parts = stripped.split()
            if parts:
                deps.add(parts[0])
    return deps


def _go_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    deps = {line.split()[0] for line in text.splitlines() if len(line.split()) >= 2}
    return deps or None


def _manifest_deps(inv: Inventory, ecosystem: str) -> set[str] | None:
    if ecosystem == "node":
        return _node_manifest_deps(inv)
    if ecosystem == "python":
        return _python_manifest_deps(inv)
    if ecosystem == "rust":
        return _cargo_manifest_deps(inv)
    if ecosystem == "go":
        return _go_manifest_deps(inv)
    return None


def _lock_deps(inv: Inventory, ecosystem: str, lockfile: str) -> set[str] | None:
    if ecosystem == "node":
        return _node_lock_deps(inv, lockfile)
    if ecosystem == "python":
        return _python_lock_deps(inv, lockfile)
    if ecosystem == "rust":
        text = inv.read(lockfile)
        return (_toml_package_names(text) or None) if text is not None else None
    if ecosystem == "go":
        return _go_lock_deps(inv, lockfile)
    return None


def _lock_consistency(inv: Inventory, ecosystem: str, lockfile: str) -> tuple[str, set[str]]:
    """Return ``(state, extras)`` where state is ok | mismatch | unverified."""
    manifest = _manifest_deps(inv, ecosystem)
    lock = _lock_deps(inv, ecosystem, lockfile)
    if manifest is None or lock is None:
        return "unverified", set()
    if not manifest:
        return "ok", set()
    if not lock:
        return "unverified", set()
    extras = manifest - lock
    return ("mismatch", extras) if extras else ("ok", set())


def check_exec02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ecosystems = sorted(stack.ecosystems & set(_ECOSYSTEM_MANAGERS))
    if not ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no lockfile is expected")

    tracked = tracked_files(target.path)
    if tracked is None:
        return _unknown(spec, "git could not report tracked files, so the lockfile's tracked "
                              "state is unknown")

    findings: list[Finding] = []
    verified: list[str] = []
    unverified: list[str] = []
    for ecosystem in ecosystems:
        candidates = [f for f in _lockfiles_for(ecosystem) if inventory.has(f)]
        tracked_candidates = sorted(f for f in candidates if f in tracked)
        if not candidates:
            findings.append(Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "install identical dependencies on every run",
                    f"the {ecosystem} project has no lockfile "
                    f"({', '.join(_lockfiles_for(ecosystem))}), so a fresh install resolves "
                    f"whatever versions are current"),
                remediation="Generate the lockfile with the project's package manager and commit it.",
            ))
            continue
        if not tracked_candidates:
            findings.append(Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "install identical dependencies on every run",
                    f"{', '.join(sorted(candidates))} exists but is not tracked, so a fresh "
                    f"checkout does not get it"),
                evidence=[Evidence(p) for p in sorted(candidates)],
                remediation="Commit the lockfile; add it to .gitignore only if the team has "
                            "deliberately chosen floating dependencies.",
            ))
            continue
        lockfile = tracked_candidates[0]
        state, extras = _lock_consistency(inventory, ecosystem, lockfile)
        if state == "mismatch":
            findings.append(Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "install identical dependencies on every run",
                    f"{lockfile} is tracked but omits manifest dependencies: "
                    f"{', '.join(sorted(extras)[:12])}"),
                evidence=[Evidence(lockfile, note="lockfile out of step with the manifest")],
                remediation="Re-run the package manager's install/lock step and commit the "
                            "updated lockfile.",
            ))
        elif state == "unverified":
            unverified.append(lockfile)
        else:
            verified.append(lockfile)

    if findings:
        verdict = Verdict.FAIL
    elif unverified:
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.PASS
    detail = "; ".join(filter(None, [
        f"tracked: {', '.join(verified)}" if verified else "",
        f"consistency unverified: {', '.join(unverified)}" if unverified else "",
    ]))
    return _outcome(spec, verdict, detail, findings)


# ===========================================================================
# EXEC-03 — non-interactive setup path
# ===========================================================================

_SETUP_FILES = (".devcontainer/devcontainer.json", ".devcontainer.json",
                "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
                "Dockerfile", "setup.sh", "bootstrap.sh", "dev-setup.sh")
_DOC_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")
_SETUP_TARGETS = ("setup", "bootstrap", "install", "dev", "dev-setup")


def _setup_signals(inv: Inventory) -> list[str]:
    signals = [name for name in _SETUP_FILES if inv.has(name)]
    signals += inv.match(".devcontainer/*.json")

    make_targets = parse_makefile_targets(inv)
    signals += [f"Makefile:{t}" for t in _SETUP_TARGETS if t in make_targets]

    scripts = extract_npm_scripts(inv)
    signals += [f"package.json:{t}" for t in _SETUP_TARGETS if t in scripts]
    return sorted(dict.fromkeys(signals))


_INSTALL_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "npm": frozenset({"install", "ci", "i"}),
    "pnpm": frozenset({"install", "i"}),
    "yarn": frozenset({"install"}),
    "bun": frozenset({"install"}),
    "pip": frozenset({"install"}), "pip3": frozenset({"install"}),
    "poetry": frozenset({"install"}), "pipenv": frozenset({"install", "sync"}),
    "uv": frozenset({"sync", "pip"}),
    "bundle": frozenset({"install"}), "gem": frozenset({"install"}),
    "composer": frozenset({"install"}),
    "make": frozenset(_SETUP_TARGETS), "task": frozenset(_SETUP_TARGETS),
    "cargo": frozenset({"fetch", "build"}),
    "go": frozenset({"mod", "build", "install"}),
    "dotnet": frozenset({"restore"}),
    "gradle": frozenset({"build", "assemble"}), "gradlew": frozenset({"build", "assemble"}),
    "mvn": frozenset({"install", "package"}), "mvnw": frozenset({"install", "package"}),
    "docker": frozenset({"compose", "build"}), "docker-compose": frozenset({"up", "build"}),
    "nvm": frozenset({"use"}),
}


def _tokenise(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens = tokens[1:]
    return tokens


def _documented_setup(inv: Inventory) -> list[str]:
    found: set[str] = set()
    for name in _DOC_FILES:
        text = inv.read(name)
        if not text:
            continue
        for _lang, _line, command in extract_fenced_commands(text):
            tokens = _tokenise(command)
            if not tokens:
                continue
            head = tokens[0].lstrip("./")
            subcommands = _INSTALL_SUBCOMMANDS.get(head)
            if subcommands and len(tokens) > 1 and tokens[1] in subcommands:
                found.add(f"{name}: {command}")
    return sorted(found)


def _is_documented(signal: str, text: str) -> bool:
    name = signal.split(":", 1)[1] if ":" in signal else signal
    name = name.rsplit("/", 1)[-1]
    if name.endswith((".json", ".yml", ".yaml", ".sh")):
        return name in text or signal in text
    return name in text


def check_exec03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not stack.ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no setup path can be characterised")

    doc_text = "\n".join(filter(None, (inventory.read(n) for n in _DOC_FILES)))
    documented_commands = _documented_setup(inventory)
    if documented_commands:
        return _outcome(spec, Verdict.PASS,
                        f"documented setup command: {documented_commands[0]}")

    signals = _setup_signals(inventory)
    documented = [s for s in signals if _is_documented(s, doc_text)]
    if documented:
        return _outcome(spec, Verdict.PASS,
                        f"documented setup artifact: {', '.join(documented)}")
    if signals:
        return _outcome(spec, Verdict.PARTIAL, f"present but undocumented: {', '.join(signals)}",
                        [Finding(
                            check=spec.id, severity=spec.severity, phase=spec.phase,
                            verdict=Verdict.PARTIAL,
                            statement=statement(
                                "provision the environment from the repository alone",
                                f"{', '.join(signals)} exists but no doc names it"),
                            evidence=[Evidence(s) for s in signals],
                            remediation="Reference the setup path in README.md or AGENTS.md so an "
                                        "agent finds it without guessing.")])

    return _outcome(spec, Verdict.FAIL, "no setup path found", [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement(
            "prepare the environment non-interactively",
            "no devcontainer, compose file, Dockerfile, setup target/script, or documented "
            "install command exists"),
        remediation="Add a committed setup path (a devcontainer, compose file, or a documented "
                    "install command in README.md) that runs with no prompts.")])


# ===========================================================================
# EXEC-04 — env-var inventory complete
# ===========================================================================

_SHELL_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
_CODE_ENV_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"os\.environ\.get\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    re.compile(r"os\.environ\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']\s*\]"),
    re.compile(r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    re.compile(r"(?<!os\.)\bgetenv\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"process\.env\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']\s*\]"),
    re.compile(r"ENV\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']\s*\]"),
)

#: Files where ``${VAR}`` is an environment reference rather than a language-level string
#: interpolation. Restricting the shell pattern to these is what keeps a TypeScript template
#: literal such as ``${PIPELINE_VERSION}`` from being misread as an undeclared secret. Deployment
#: YAML (compose, Terraform) is deliberately out of scope: its ``${VAR}`` references usually name
#: host/CI values, not repository environment requirements.
_SHELL_ENV_SUFFIXES = (".sh", ".bash", ".zsh", ".fish", ".ksh", ".ps1")
_SHELL_ENV_BASENAMES = ("Dockerfile",)

#: Conventional host/CI/test variables an agent never needs a template for. Kept in code so the
#: allow-list is deterministic and reviewable rather than a per-target heuristic.
_ENV_ALLOWLIST: frozenset[str] = frozenset({
    "CI", "HOME", "PATH", "PWD", "SHELL", "USER", "LANG", "LC_ALL", "TZ", "TERM", "TMPDIR",
    "NODE_ENV", "DEBUG", "LOG_LEVEL", "LOG_FORMAT", "VERBOSE", "PORT",
    "PYTHONPATH", "PYTHONUNBUFFERED", "VIRTUAL_ENV", "PYTHONHASHSEED",
    "FORCE_COLOR", "NO_COLOR", "COLUMNS", "LINES",
})
_ENV_ALLOW_PREFIXES: tuple[str, ...] = (
    "GITHUB_", "CI_", "RUNNER_", "ACTIONS_", "npm_config_", "NPM_CONFIG_",
    "VITEST_", "PYTEST_", "COVERAGE_",
)
_ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", "env.example")


def _is_shell_env_file(rel: str) -> bool:
    return (rel.endswith(_SHELL_ENV_SUFFIXES)
            or rel.rsplit("/", 1)[-1] in _SHELL_ENV_BASENAMES)


def _referenced_env_keys(inv: Inventory) -> set[str]:
    keys: set[str] = set()
    for path in inv.paths():
        if not _is_shell_env_file(path):
            continue
        text = inv.read(path)
        if text:
            keys |= {m.group(1) for m in _SHELL_ENV_PATTERN.finditer(text)}
    for pattern in _CODE_ENV_PATTERNS:
        for _rel, _line, text in inv.grep(pattern, kinds=(Kind.SOURCE, Kind.SCRIPT), limit=2000):
            keys |= {m.group(1) for m in pattern.finditer(text) if m.group(1)}
    return keys


def _declared_env_keys(inv: Inventory) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    files: list[str] = []
    for name in _ENV_EXAMPLE_FILES:
        text = inv.read(name)
        if text is None:
            continue
        files.append(name)
        for line in text.splitlines():
            match = re.match(r"^\s*(?:export\s+)?#?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if match:
                keys.add(match.group(1))
    return keys, files


def _env_allowed(key: str) -> bool:
    return key in _ENV_ALLOWLIST or key.startswith(_ENV_ALLOW_PREFIXES)


def check_exec04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    referenced = _referenced_env_keys(inventory)
    declared, files = _declared_env_keys(inventory)
    missing = sorted(k for k in referenced - declared if not _env_allowed(k))
    keys = EnvKeys(referenced=tuple(sorted(referenced)), missing=tuple(missing),
                   templates=tuple(files))

    if not missing:
        detail = (f"{len(referenced)} referenced key(s) declared"
                  if referenced else "no environment keys referenced")
        return _outcome(spec, Verdict.PASS, detail, data=keys)

    because = (f"{len(missing)} referenced key(s) are absent from "
               f"{', '.join(files) if files else 'any committed example file'}: "
               f"{', '.join(missing[:12])}")
    return _outcome(spec, Verdict.FAIL, because, [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement("know every variable the code needs before running it", because),
        evidence=[Evidence(f) for f in files] or [Evidence("(no example file)")],
        remediation="Add the missing keys to .env.example (values redacted) so the environment "
                    "can be provisioned without reading the source.")], data=keys)


# ===========================================================================
# EXEC-05 — no generated artifacts committed in-tree
# ===========================================================================

_GENERATED_HEADER_MARKERS = (
    "@generated", "do not edit", "generated by", "code generated",
    "auto-generated", "autogenerated", "this file is generated",
)


def _has_generated_header(text: str | None) -> bool:
    if text is None:
        return False
    head = "\n".join(text.splitlines()[:20]).lower()
    return any(marker in head for marker in _GENERATED_HEADER_MARKERS)


def check_exec05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_files(target.path)
    if tracked is None:
        return _unknown(spec, "git could not report tracked files, so generated-file state is "
                              "unknown")

    generated = sorted(f.rel for f in inventory.files
                       if f.kind is Kind.GENERATED and f.rel in tracked)
    if not generated:
        return _outcome(spec, Verdict.PASS, "no tracked generated or vendored paths")

    offenders = [rel for rel in generated if not _has_generated_header(inventory.read(rel))]
    if not offenders:
        return _outcome(spec, Verdict.PASS,
                        f"{len(generated)} tracked generated path(s) carry a generated header")

    because = (f"{len(offenders)} generated/vendored path(s) are tracked without a "
               f"generated-file header: {', '.join(offenders[:12])}")
    return _outcome(spec, Verdict.FAIL, because, [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement("edit tracked source without it being overwritten", because),
        evidence=[Evidence(p) for p in offenders[:12]],
        remediation="Untrack the generated output and ignore it, or add a generated-file header "
                    "(`@generated` / `DO NOT EDIT`) so agents know not to edit it.")])


# ===========================================================================
# EXEC-06 — documented commands resolve
# ===========================================================================

_KNOWN_TOOLS = frozenset({
    "python", "python3", "pip", "pip3", "poetry", "uv", "pipenv", "pytest", "tox", "ruff",
    "black", "mypy", "pyright", "flake8", "pylint", "isort",
    "node", "npm", "npx", "pnpm", "yarn", "bun", "corepack", "tsc", "vitest", "jest", "eslint",
    "biome", "prettier", "shx", "husky", "lint-staged", "commitlint", "semgrep",
    "go", "gofmt", "golangci-lint",
    "cargo", "rustc", "rustup", "clippy", "rustfmt",
    "java", "javac", "mvn", "gradle", "dotnet",
    "ruby", "gem", "bundle", "rake", "php", "composer",
    "git", "gh", "docker", "docker-compose", "podman", "kubectl", "helm", "terraform",
    "aws", "az", "gcloud",
    "make", "task", "just", "cmake", "ninja", "bash", "sh", "zsh", "fish", "shellcheck",
    "curl", "wget", "jq", "yq", "tar", "zip", "unzip", "gzip", "openssl", "ssh", "scp", "rsync",
    "mkdir", "cp", "mv", "rm", "ls", "cat", "touch", "chmod", "ln", "sed", "awk", "grep", "find",
    "xargs", "which", "command", "env", "echo", "printf", "head", "tail", "tee", "sort", "uniq",
    "wc", "diff", "sleep", "kill", "ps", "du", "df",
    "nvm", "fnm", "asdf", "mise", "volta", "sdk",
    "pre-commit", "lefthook",
    "opencode", "claude", "codex", "gemini", "aider", "copilot", "cursor", "windsurf", "amp",
    "crush", "pi", "goose", "audit",
})

_SHELL_KEYWORDS = frozenset({
    "cd", "export", "source", ".", "set", "unset", "alias", "if", "then", "else", "elif", "fi",
    "for", "while", "do", "done", "case", "esac", "function", "return", "local", "readonly",
    "declare", "eval", "trap", "umask", "ulimit", "wait", "jobs", "fg", "bg", "type", "hash",
    "pwd", "whoami", "id", "uname", "date", "hostname", "realpath", "dirname", "basename",
    "printenv", "true", "false", "exit", "yes", "no", "test", "[", "[[",
})

_STRIPPABLE_PREFIXES = frozenset({"sudo", "env", "time", "nohup", "command", "stdbuf"})


def _package_bins(inv: Inventory) -> set[str]:
    text = inv.read("package.json")
    if not text:
        return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    bins = data.get("bin")
    if isinstance(bins, str):
        return {str(data.get("name") or "").strip()} - {""}
    if isinstance(bins, dict):
        return set(bins)
    return set()


def _command_parts(command: str) -> list[str]:
    command = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command, maxsplit=1)[0]
    command = re.split(r"\s+2?>\s*", command, maxsplit=1)[0]
    return _tokenise(command)


def _resolves(inv: Inventory, tokens: list[str], verbs: dict, scripts: dict, make_targets: dict,
              bins: set[str]) -> bool:
    while tokens and tokens[0] in _STRIPPABLE_PREFIXES:
        tokens = tokens[1:]
    if not tokens:
        return True
    head = tokens[0]
    rest = tokens[1:]

    if head in _SHELL_KEYWORDS or head in _KNOWN_TOOLS:
        if head in {"npm", "pnpm", "bun"}:
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "yarn":
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "make":
            targets = [t for t in rest if not t.startswith("-") and "=" not in t]
            return all(t in make_targets for t in targets) if targets and make_targets else True
        return True

    if head in verbs:
        return True

    if head in bins:
        return True

    candidate = head[2:] if head.startswith("./") else head
    if "/" in candidate or head.startswith("./"):
        if inv.has(candidate) or any(f.rel == candidate or f.rel.startswith(candidate + "/")
                                     for f in inv.files):
            return True

    return False


def _logical_commands(entries: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    """Join trailing-backslash line continuations into one command.

    ``extract_fenced_commands`` reports each physical line; a multi-line invocation would otherwise
    present its continuation lines (``--out ...``) as commands in their own right.
    """
    merged: list[tuple[str, int, str]] = []
    for path, line, command in entries:
        if merged and merged[-1][0] == path and merged[-1][1] + 1 == line \
                and merged[-1][2].rstrip().endswith("\\"):
            prev_path, prev_line, prev = merged[-1]
            merged[-1] = (prev_path, prev_line, prev.rstrip().rstrip("\\").rstrip() + " " + command)
        else:
            merged.append((path, line, command))
    return merged


def check_exec06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    # The catalogue's evidence rule names README and AGENTS.md; docs/** fences routinely mix
    # languages (a Python snippet in a ```bash block), which is a documentation defect EXEC-06 is
    # not chartered to police.
    doc_paths = ["README.md", "AGENTS.md", "CLAUDE.md"]

    raw: list[tuple[str, int, str]] = []
    for name in doc_paths:
        text = inventory.read(name)
        if not text:
            continue
        raw.extend((name, line, command) for _lang, line, command in extract_fenced_commands(text))

    commands = _logical_commands(raw)
    seen: set[str] = set()
    unique: list[tuple[str, int, str]] = []
    for path, line, command in commands:
        if command in seen:
            continue
        seen.add(command)
        unique.append((path, line, command))

    if not unique:
        return _outcome(spec, Verdict.PASS, "no fenced shell commands documented")

    verbs = resolve_verbs(inventory, stack)
    scripts = extract_npm_scripts(inventory)
    make_targets = parse_makefile_targets(inventory)
    bins = _package_bins(inventory)

    unresolved: list[tuple[str, int, str]] = []
    for path, line, command in unique:
        if re.search(r"[<]|\.\.\.|\b(your[_-]|tbd|xxx|placeholder)\b", command, re.IGNORECASE):
            continue
        tokens = _command_parts(command)
        if not tokens:
            continue
        if not _resolves(inventory, tokens, verbs, scripts, make_targets, bins):
            unresolved.append((path, line, command))

    if not unresolved:
        return _outcome(spec, Verdict.PASS, f"{len(unique)} documented command(s) resolve")

    because = (f"{len(unresolved)} documented command(s) name no script, verb, or file: "
               + "; ".join(f"{cmd!r} ({path}:{line})" for path, line, cmd in unresolved[:8]))
    return _outcome(spec, Verdict.FAIL, because, [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement("run the documented commands literally", because),
        evidence=[Evidence(path, line=line, note=cmd) for path, line, cmd in unresolved[:12]],
        remediation="Fix the documented command to name a resolvable script, verb, or file — an "
                    "agent will run it exactly as written.")])


# ===========================================================================
# EXEC-07 — no competing configs for one concern
# ===========================================================================

_CONCERN_GLOBS: dict[str, tuple[str, ...]] = {
    "lint": ("eslint.config.*", ".eslintrc", ".eslintrc.*", "biome.json", "biome.jsonc",
             "ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", ".golangci.yml", ".golangci.yaml",
             "clippy.toml", ".stylelintrc", ".stylelintrc.*", "oxlint.json", ".oxlintrc.json"),
    "format": ("prettier.config.*", ".prettierrc", ".prettierrc.*", "biome.json", "biome.jsonc",
               ".clang-format", "rustfmt.toml", ".rustfmt.toml", "dprint.json"),
    "test": ("vitest.config.*", "jest.config.*", "pytest.ini", "tox.ini", ".mocharc.*",
             "karma.conf.js", "cypress.config.*"),
    "types": ("tsconfig.json", "jsconfig.json", "mypy.ini", ".mypy.ini", "pyrightconfig.json"),
    "security": (".gitleaks.toml", "semgrep.yml", ".semgrep.yml", ".snyk", "osv-scanner.toml",
                 ".bandit"),
}

#: Sections inside a root ``pyproject.toml`` that author a concern, matched per concern.
_PYPROJECT_SECTIONS: dict[str, tuple[str, ...]] = {
    "lint": (r"\[tool\.ruff\]", r"\[tool\.pylint\]", r"\[tool\.flake8\]"),
    "format": (r"\[tool\.black\]", r"\[tool\.ruff\.format\]"),
    "test": (r"\[tool\.pytest", r"\[tool\.tox\]"),
    "types": (r"\[tool\.mypy\]", r"\[tool\.pyright\]", r"\[tool\.basedpyright\]"),
    "security": (r"\[tool\.bandit\]",),
}


def _concern_configs(inv: Inventory) -> dict[str, list[str]]:
    roots = sorted(f.rel for f in inv.files if "/" not in f.rel)
    found: dict[str, list[str]] = {concern: [] for concern in _CONCERN_GLOBS}
    for concern, globs in _CONCERN_GLOBS.items():
        for rel in roots:
            if any(fnmatch.fnmatch(rel, glob) for glob in globs):
                found[concern].append(rel)
    pyproject = inv.read("pyproject.toml")
    if pyproject is not None:
        for concern, patterns in _PYPROJECT_SECTIONS.items():
            if any(re.search(pattern, pyproject) for pattern in patterns):
                found[concern].append("pyproject.toml")
    return found


def check_exec07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _concern_configs(inventory)
    competing = {concern: sorted(set(paths)) for concern, paths in found.items()
                 if len(set(paths)) > 1}
    if not competing:
        authored = {c: (paths[0] if paths else None) for c, paths in found.items() if paths}
        detail = "; ".join(f"{c}: {p}" for c, p in sorted(authored.items()))
        return _outcome(spec, Verdict.PASS, detail or "no concern configs found")

    because = "; ".join(f"{concern} ({', '.join(paths)})"
                        for concern, paths in sorted(competing.items()))
    return _outcome(spec, Verdict.FAIL, f"competing configs: {because}", [Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement("know which config wins for each concern",
                            f"{len(competing)} concern(s) have more than one config: {because}"),
        evidence=[Evidence(p) for _concern, paths in sorted(competing.items()) for p in paths],
        remediation="Keep one authoritative config per concern and document any deliberate "
                    "delegation, or delete the redundant config.")])


IMPLEMENTATIONS = {
    "EXEC-01": check_exec01,
    "EXEC-02": check_exec02,
    "EXEC-03": check_exec03,
    "EXEC-04": check_exec04,
    "EXEC-05": check_exec05,
    "EXEC-06": check_exec06,
    "EXEC-07": check_exec07,
}
