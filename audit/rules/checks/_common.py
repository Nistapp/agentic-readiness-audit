"""Private cross-pack check helpers.

This module is **not** a rule pack. It defines no checks, contributes nothing to the catalogue, and
is deliberately absent from ``MODULE_NAMES`` in ``audit/rules/checks/__init__.py`` — so it is never
loaded by the registry and never appears in ``--list-checks``. Packs import it directly
(``from audit.rules.checks._common import ...``).

It exists only to answer questions more than one pack asks. The pair that motivated it:

* **"what verbs exist, and what does each run?"** — CMD-01, EXEC-06, CI-02, AGT-05, TOOL-01/02/04
  and TST-01 all need one answer, so it is computed once (``resolve_verbs``);
* **"which commands does the documentation actually show?"** — EXEC-06 and TST-04 both read fenced
  shell blocks (``extract_fenced_commands``).

Keep it small. If a helper is used by exactly one check it belongs in that pack, not here.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from audit.scan import Inventory
from audit.stack import (
    VERBS,
    Stack,
    extract_npm_scripts,
    parse_makefile_targets,
)


@dataclass(frozen=True)
class VerbBinding:
    """One resolved framework verb: where it is declared and what it runs.

    ``runner`` is the manifest the verb was read from, ``command`` is the raw string the runner
    declares, and ``argv`` is a best-effort tokenisation of it (shell operators are not interpreted).
    """

    verb: str
    runner: str
    command: str
    argv: tuple[str, ...]


#: Runner precedence when more than one manifest defines the same verb. Fixed and documented so a
#: target with both a Makefile and package.json resolves deterministically.
RUNNER_PRECEDENCE: tuple[str, ...] = (
    "package.json", "Makefile", "Taskfile.yml", "Taskfile.yaml", "pyproject.toml",
    "build.gradle", "build.gradle.kts", "pom.xml", "gradlew", "mvnw",
)


def resolve_all_verbs(inventory: Inventory, stack: Stack) -> dict[str, tuple[VerbBinding, ...]]:
    """Resolve **every** binding for every framework verb the target declares.

    Unlike :func:`resolve_verbs`, which collapses to the single highest-precedence binding per verb,
    this keeps the full list so a caller can tell that a verb is defined on more than one runner.
    Bindings for each verb are ordered by :data:`RUNNER_PRECEDENCE`. ``stack`` is accepted so callers
    can pass the detected stack even though resolution reads the inventory directly in v1.
    """
    candidates: dict[str, list[VerbBinding]] = {}
    for runner, commands in runner_commands(inventory):
        for verb in VERBS:
            command = commands.get(verb)
            if command:
                candidates.setdefault(verb, []).append(
                    VerbBinding(verb=verb, runner=runner, command=command,
                                argv=_split_argv(command))
                )
    return {verb: tuple(sorted(bindings, key=lambda b: _runner_rank(b.runner)))
            for verb, bindings in candidates.items()}


def resolve_verbs(inventory: Inventory, stack: Stack) -> dict[str, VerbBinding]:
    """Resolve every framework verb the target declares, keyed by verb name.

    Only verbs that are actually declared are returned; callers compare the result against
    :data:`audit.stack.VERBS` to find the missing ones. ``stack`` is accepted so callers can pass the
    detected stack even though resolution reads the inventory directly in v1.
    """
    return {verb: bindings[0]
            for verb, bindings in resolve_all_verbs(inventory, stack).items()}


def runner_commands(inventory: Inventory) -> tuple[tuple[str, dict[str, str]], ...]:
    """Every present verb runner and its declared ``{verb: command}`` map, in precedence order.

    A runner is present when its manifest is present, whether or not it declares any framework verb;
    callers that care about verb coverage read the map, callers that care about runners read the name.
    """
    return tuple(_runner_commands(inventory))


#: Fenced-code languages treated as shell for command extraction.
SHELL_FENCE_LANGS: frozenset[str] = frozenset({"bash", "sh", "shell", "console", "zsh"})

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)\s*([A-Za-z0-9_+-]*)\s*$")
_PROMPT_RE = re.compile(r"^\s*(?:\$|>|%|❯|PS>)\s+")


def extract_fenced_commands(text: str) -> list[tuple[str, int, str]]:
    """Extract shell commands from fenced ``bash``/``sh``/``shell``/``console`` blocks.

    Returns ``(language, line_no, command)`` with ``line_no`` 1-based within ``text``. A leading
    shell prompt is stripped; comment lines are skipped. In a ``console`` block a line without a
    prompt is treated as program output and skipped, since a transcript interleaves both.
    """
    commands: list[tuple[str, int, str]] = []
    language: str | None = None
    for line_no, raw in enumerate(text.splitlines(), start=1):
        fence = _FENCE_RE.match(raw)
        if fence:
            language = None if language is not None else fence.group(1).lower()
            continue
        if language is None or language not in SHELL_FENCE_LANGS:
            continue
        prompt = _PROMPT_RE.match(raw)
        command = _PROMPT_RE.sub("", raw).strip()
        if not command or command.startswith("#"):
            continue
        if language == "console" and prompt is None:
            continue
        commands.append((language, line_no, command))
    return commands


# ---------------------------------------------------------------------------
# runner readers
# ---------------------------------------------------------------------------

def _runner_commands(inventory: Inventory):
    """Yield ``(runner, {verb: command})`` for every manifest present, in precedence order."""
    if inventory.has("package.json"):
        yield "package.json", extract_npm_scripts(inventory)
    if inventory.has("Makefile"):
        yield "Makefile", parse_makefile_targets(inventory)
    for name in ("Taskfile.yml", "Taskfile.yaml"):
        if inventory.has(name):
            text = inventory.read(name)
            if text:
                yield name, _parse_taskfile(text)
    if inventory.has("pyproject.toml"):
        text = inventory.read("pyproject.toml")
        if text:
            yield "pyproject.toml", _parse_pyproject_tasks(text)
    for name in ("build.gradle", "build.gradle.kts"):
        if inventory.has(name):
            text = inventory.read(name)
            if text:
                yield name, _parse_gradle_tasks(text, inventory)
    if inventory.has("pom.xml"):
        text = inventory.read("pom.xml")
        if text:
            yield "pom.xml", _parse_maven_goals(text, inventory)


def _runner_rank(runner: str) -> int:
    try:
        return RUNNER_PRECEDENCE.index(runner)
    except ValueError:
        return len(RUNNER_PRECEDENCE)


def _split_argv(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return tuple(command.split())


# ---------------------------------------------------------------------------
# minimal, stdlib-only manifest parsers (deliberately crude — documented as such)
# ---------------------------------------------------------------------------

def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _parse_taskfile(text: str) -> dict[str, str]:
    """Minimal Taskfile reader: top-level ``tasks:`` mapping, ``cmd:`` scalar and ``cmds:`` list.

    No YAML library is available (stdlib only), so this understands the common shape and nothing
    exotic: anchors, ``includes``, templating and nested ``deps`` are not interpreted.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines)
                     if re.match(r"^tasks:\s*(#.*)?$", line))
    except StopIteration:
        return {}

    base = _indent(lines[start])
    tasks: dict[str, list[str]] = {}
    order: list[str] = []
    header_indent: int | None = None
    current: str | None = None

    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = _indent(line)
        if indent <= base:
            break
        if header_indent is None:
            header_indent = indent
        header = re.match(r"^([A-Za-z0-9_:-]+):\s*$", line.strip())
        if indent == header_indent and header:
            current = header.group(1)
            if current not in tasks:
                tasks[current] = []
                order.append(current)
            continue
        if current is None or indent <= header_indent:
            continue
        scalar = re.match(r"^cmd:\s*(.+)$", line.strip())
        if scalar:
            tasks[current].append(scalar.group(1).strip())
            continue
        item = re.match(r"^-\s*(.+)$", line.strip())
        if item:
            tasks[current].append(item.group(1).strip())

    return {name: " && ".join(tasks[name]) for name in order if tasks[name]}


def _parse_pyproject_tasks(text: str) -> dict[str, str]:
    """Minimal pyproject reader for task runners (``[tool.poe.tasks]``, ``[tool.taskipy.tasks]``).

    Reads any ``[tool.<runner>.tasks]`` section, accepting ``name = "cmd"`` and
    ``name = { cmd = "cmd" }``. A TOML parser is not in the standard library, so this is deliberately
    shallow and ignores everything else in the file.
    """
    tasks: dict[str, str] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = re.match(r"^\[([^\]]+)\]$", line)
        if header:
            section = header.group(1)
            continue
        if not section or not section.startswith("tool.") or not section.endswith(".tasks"):
            continue
        scalar = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"', line)
        if scalar:
            tasks[scalar.group(1)] = scalar.group(2)
            continue
        table = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*\{(.*)\}\s*$", line)
        if table:
            command = re.search(r'(?:cmd|command|script)\s*[:=]\s*["\']([^"\']+)["\']',
                                table.group(2))
            if command:
                tasks[table.group(1)] = command.group(1)
    return tasks


_GRADLE_TASK_PATTERNS = (
    re.compile(r"\btasks\.register\(\s*['\"]([A-Za-z0-9_:-]+)['\"]"),
    re.compile(r"\bregister\(\s*['\"]([A-Za-z0-9_:-]+)['\"]"),
    re.compile(r"^\s*task\s+([A-Za-z0-9_:-]+)"),
)


def _parse_gradle_tasks(text: str, inventory: Inventory) -> dict[str, str]:
    """Declared Gradle task names, invoked through the committed wrapper when one exists.

    Gradle has no verb table: a verb resolves only when the build file registers a task of that
    name. Conventional lifecycle tasks that Gradle provides implicitly are not invented here.
    """
    names: set[str] = set()
    for line in text.splitlines():
        for pattern in _GRADLE_TASK_PATTERNS:
            match = pattern.search(line)
            if match:
                names.add(match.group(1))
    launcher = "./gradlew" if inventory.has("gradlew") else "gradle"
    return {name: f"{launcher} {name}" for name in sorted(names)}


_MAVEN_GOAL_RE = re.compile(r"<goal>([A-Za-z0-9_:-]+)</goal>")


def _parse_maven_goals(text: str, inventory: Inventory) -> dict[str, str]:
    """Declared Maven plugin goals, invoked through the committed wrapper when one exists.

    As with Gradle, only explicitly declared goals resolve; the Maven lifecycle is not assumed.
    """
    names = sorted(set(_MAVEN_GOAL_RE.findall(text)))
    launcher = "./mvnw" if inventory.has("mvnw") else "mvn"
    return {name: f"{launcher} {name}" for name in names}
