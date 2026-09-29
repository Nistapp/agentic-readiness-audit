"""Stage S4 — stack and layout detection.

Decides which rule packs apply to a target. Detection never guesses: an ecosystem this module
does not recognise produces ``UNKNOWN`` verdicts for the checks that need it, plus a visible note
in the report. Nothing is ever passed by omission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from audit.scan import Inventory, Kind

#: ecosystem -> (manifest globs, verb-runner hints)
ECOSYSTEM_SIGNALS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "node": (("package.json",), ("package.json",)),
    "python": (("pyproject.toml", "setup.py", "requirements*.txt", "Pipfile"), ("pyproject.toml", "Makefile")),
    "jvm": (("pom.xml", "build.gradle", "build.gradle.kts"), ("pom.xml", "build.gradle", "Makefile")),
    "go": (("go.mod",), ("Makefile",)),
    "rust": (("Cargo.toml",), ("Makefile",)),
    "dotnet": (("*.csproj", "*.sln"), ("*.sln",)),
    "ruby": (("Gemfile",), ("Rakefile", "Makefile")),
    "php": (("composer.json",), ("composer.json",)),
}

PACKAGE_MANAGERS: dict[str, tuple[str, ...]] = {
    "npm": ("package-lock.json",),
    "pnpm": ("pnpm-lock.yaml",),
    "yarn": ("yarn.lock",),
    "bun": ("bun.lockb",),
    "pip": ("requirements.txt",),
    "poetry": ("poetry.lock",),
    "uv": ("uv.lock",),
    "pipenv": ("Pipfile.lock",),
    "gradle": ("gradle.lockfile",),
    "maven": ("pom.xml",),
    "cargo": ("Cargo.lock",),
    "gomod": ("go.sum",),
    "bundler": ("Gemfile.lock",),
    "composer": ("composer.lock",),
}

CI_PROVIDERS: dict[str, tuple[str, ...]] = {
    "github": (".github/workflows/*.yml", ".github/workflows/*.yaml"),
    "gitlab": (".gitlab-ci.yml",),
    "jenkins": ("Jenkinsfile",),
    "azure": ("azure-pipelines.yml",),
    "circleci": (".circleci/config.yml",),
    "buildkite": (".buildkite/*.yml",),
}

TEST_FRAMEWORKS: dict[str, tuple[str, ...]] = {
    "vitest": ("vitest.config.ts", "vitest.config.js", "vitest.config.mts"),
    "jest": ("jest.config.js", "jest.config.ts", "jest.config.mjs"),
    "pytest": ("pytest.ini", "conftest.py"),
    "tox": ("tox.ini",),
    "junit": ("src/test/java/**",),
    "go-test": ("*_test.go",),
    "cargo-test": ("tests/*.rs",),
}

HOOK_MANAGERS: dict[str, tuple[str, ...]] = {
    "husky": (".husky/*",),
    "lefthook": ("lefthook.yml", "lefthook.yaml"),
    "pre-commit": (".pre-commit-config.yaml",),
    "gradle-hooks": (".githooks/*",),
}

VERB_RUNNERS = ("package.json", "Taskfile.yml", "Taskfile.yaml", "Makefile",
                "pyproject.toml", "build.gradle", "build.gradle.kts", "pom.xml")

#: The six verbs of the framework's standardized command surface.
VERBS = ("format", "format:check", "lint", "typecheck", "test", "check", "security")


@dataclass
class Stack:
    ecosystems: set[str] = field(default_factory=set)
    package_managers: set[str] = field(default_factory=set)
    ci_providers: set[str] = field(default_factory=set)
    test_frameworks: set[str] = field(default_factory=set)
    hook_managers: set[str] = field(default_factory=set)
    verb_runners: list[str] = field(default_factory=list)
    component_manifest_hint: str | None = None
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = []
        if self.ecosystems:
            parts.append("ecosystems: " + ", ".join(sorted(self.ecosystems)))
        if self.ci_providers:
            parts.append("ci: " + ", ".join(sorted(self.ci_providers)))
        return " · ".join(parts) or "stack not recognised"


def detect_stack(inv: Inventory) -> Stack:
    stack = Stack()
    names = {f.rel.split("/")[-1] for f in inv.files}

    for eco, (manifests, runners) in ECOSYSTEM_SIGNALS.items():
        for pattern in manifests:
            if "*" in pattern:
                if inv.match(pattern):
                    stack.ecosystems.add(eco)
                    break
            elif pattern in names or inv.has(pattern):
                stack.ecosystems.add(eco)
                break
        for runner in runners:
            if runner in names and runner in VERB_RUNNERS and runner not in stack.verb_runners:
                stack.verb_runners.append(runner)

    for name, signals in PACKAGE_MANAGERS.items():
        if any(inv.has(s) for s in signals):
            stack.package_managers.add(name)

    for provider, globs in CI_PROVIDERS.items():
        if inv.match(*globs):
            stack.ci_providers.add(provider)

    for framework, signals in TEST_FRAMEWORKS.items():
        if inv.match(*signals):
            stack.test_frameworks.add(framework)

    for manager, globs in HOOK_MANAGERS.items():
        if inv.match(*globs):
            stack.hook_managers.add(manager)

    if not stack.ecosystems:
        stack.notes.append("no recognised build manifest — stack-dependent checks report UNKNOWN")
    return stack


def extract_npm_scripts(inv: Inventory, manifest: str = "package.json") -> dict[str, str]:
    """Read the ``scripts`` map from an npm manifest. Returns {} when absent or unparsable."""
    import json

    text = inv.read(manifest)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


#: A framework verb is a valid Makefile target name, and ``format:check`` contains a colon that the
#: generic ``target:`` pattern would mis-split. Longest-first so ``format:check`` is matched before
#: ``format``.
_VERB_TARGETS: tuple[str, ...] = tuple(sorted(VERBS, key=len, reverse=True))


def parse_makefile_targets(inv: Inventory) -> dict[str, str]:
    """Collect ``target: recipe`` pairs from a Makefile (single-line recipes only).

    A target whose name is one of the framework verbs is matched explicitly first, so a colon-bearing
    verb such as ``format:check`` resolves as a single target rather than being split at the colon.
    """
    text = inv.read("Makefile")
    if not text:
        return {}
    targets: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("\t"):
            if current:
                targets[current] = (targets.get(current, "") + " " + line.strip()).strip()
            continue
        verb = next((v for v in _VERB_TARGETS
                     if line.startswith(v + ":") and not line.startswith(v + ":=")), None)
        if verb is not None:
            current = verb
            targets[verb] = line[len(verb) + 1:].strip()
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?!=)\s*(.*)$", line)
        if match:
            current = match.group(1)
            targets[current] = match.group(2).strip()
        else:
            current = None
    return targets
