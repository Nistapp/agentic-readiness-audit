"""`AGT` pack — agent governance.

Implemented here: `AGT-01` (canonical instruction file), `AGT-02` (component coverage),
`AGT-03` (documentation contract), `AGT-04` (definition of done), `AGT-05` (six verbs named),
`AGT-06` (architectural boundaries), `AGT-07` (prohibitions), `AGT-08` (competing files + reach
matrix), `AGT-09` (branch and release boundary) and `AGT-10` (indirection).

`AGT-05` resolves its verbs through `CMD-01`'s resolver (`_common.resolve_verbs`) so the two checks
can never disagree: it is a `PASS` only when the entry instruction file names every framework verb
**and** those verbs resolve on a runner. Names without resolution is `PARTIAL`; neither is `FAIL`.
With no runner and no named verbs it degrades to `UNKNOWN`, deferring to `AGT-01` and `CMD-01`.

The content-contract checks (`03`, `04`, `06`, `07`, `09`) read the entry instruction file — the
canonical `AGENTS.md`, falling back to `CLAUDE.md` when the canonical file is absent. When no
instruction file exists they report `UNKNOWN`, not `FAIL`: the absence is already `AGT-01`'s finding
and piling on adds noise without adding information.

Anchor: Phased-Approach.md § Phase 1: Agentic Bootstrap.
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.checks._common import resolve_verbs, runner_commands
from audit.scan import Inventory
from audit.stack import VERBS
from audit.rules import variants as V
from audit.rules.payloads import (
    HarnessMatrix,
    Payload,
    Ratio,
    VerbEntry,
    VerbSurface,
)

#: An instruction file below this size, or matching a stub marker, is present but not governance.
MIN_INSTRUCTION_CHARS = 400
STUB_MARKERS = ("todo", "tbd", "placeholder", "lorem ipsum", "<describe", "coming soon",
                "fill this in")

#: All basenames that could be an instruction file, derived from the variant table.
def _instruction_basenames() -> set[str]:
    names: set[str] = set(V.CANONICAL_PATHS) | set(V.NON_CANONICAL_ALIASES) | set(V.OVERRIDE_PATHS)
    for harness in V.HARNESSES:
        for pattern in harness.paths:
            if "*" not in pattern:
                names.add(pattern)
    return names


INSTRUCTION_BASENAMES = _instruction_basenames()


def is_non_instruction(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, glob) for glob, _why in V.NON_INSTRUCTION_GLOBS)


def instruction_paths(inv: Inventory) -> set[str]:
    """Every path in the target that is plausibly an agent-instruction file.

    Excludes skill definitions, run state and harness config, which is what keeps this check from
    failing on every repository that happens to contain a `.opencode/` directory.
    """
    found: set[str] = set()
    for rel in inv.paths():
        if is_non_instruction(rel):
            continue
        base = rel.rsplit("/", 1)[-1]
        if base in INSTRUCTION_BASENAMES:
            found.add(rel)
            continue
        for harness in V.HARNESSES:
            for pattern in harness.paths:
                if "*" in pattern and fnmatch.fnmatch(rel, pattern):
                    found.add(rel)
    return found


def _rule_line_count(text: str) -> int:
    """Count lines that look like rules rather than headings, blanks or prose-only links."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        if stripped.startswith("|") and set(stripped) <= set("|-: "):
            continue
        count += 1
    return count


def _trivial_reason(text: str) -> str | None:
    if len(text.strip()) < MIN_INSTRUCTION_CHARS:
        return f"only {len(text.strip())} characters (minimum {MIN_INSTRUCTION_CHARS})"
    lowered = text.lower()
    for marker in STUB_MARKERS:
        if marker in lowered:
            return f"contains the placeholder marker {marker!r}"
    return None


# ---------------------------------------------------------------------------
# AGT-01 — instruction file present, canonical, non-trivial
# ---------------------------------------------------------------------------

def check_agt01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    present = instruction_paths(inventory)
    classified = V.classify_present(present)
    findings: list[Finding] = []
    detail_parts: list[str] = []

    canonical_root = "AGENTS.md" in present
    canonical_nested = sorted(p for p in present
                              if p.endswith("/AGENTS.md") and p != "AGENTS.md")
    mis_cased = V.mis_cased_canonical_candidates(present)
    aliases = classified["aliases"]
    overrides = classified["overrides"]
    vendor_only = classified["vendor_only"]

    if not present:
        findings.append(Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "learn the project's conventions",
                "no agent-instruction file exists anywhere in the repository"),
            remediation="Create AGENTS.md at the repository root using the framework template "
                        "(codebase-agentic-readiness-framework templates/AGENTS.md).",
        ))
    else:
        if canonical_root:
            text = inventory.read("AGENTS.md") or ""
            reason = _trivial_reason(text)
            if reason:
                findings.append(Finding(
                    check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                    statement=statement("work to this project's conventions",
                                        f"AGENTS.md exists but is a stub — {reason}"),
                    evidence=[Evidence("AGENTS.md", note=f"{_rule_line_count(text)} rule lines")],
                    remediation="Fill AGENTS.md from the framework template: verbs, boundaries, "
                                "definition of done, prohibitions.",
                ))
        if mis_cased:
            findings.append(Finding(
                check=spec.id, severity=Severity.BLOCKER, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "rely on the instruction file being found",
                    f"{', '.join(mis_cased)} differs from AGENTS.md only by case, and "
                    f"case-sensitive filesystems will not find it"),
                evidence=[Evidence(p) for p in mis_cased],
                remediation="Rename to AGENTS.md exactly (Warp also requires ALL CAPS).",
            ))
        if not canonical_root and (aliases or vendor_only):
            owner = ", ".join(sorted(set(
                tool for name in aliases for tool in V.NON_CANONICAL_ALIASES.get(name, ())
            ))) or "one harness"
            findings.append(Finding(
                check=spec.id, severity=Severity.DEGRADER, phase=spec.phase, verdict=Verdict.PARTIAL,
                statement=statement(
                    "share one set of project rules across harnesses",
                    f"instruction content lives only in vendor-specific files "
                    f"({', '.join(sorted(aliases + vendor_only))}) that {owner} reads"),
                remediation="Add AGENTS.md as the canonical file and reduce vendor files to a "
                            "one-line pointer, or a symlink where the harness supports it.",
            ))
        if overrides:
            for override in overrides:
                tool = V.OVERRIDE_PATHS.get(override, "some harness")
                findings.append(Finding(
                    check=spec.id, severity=Severity.DEGRADER, phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "rely on AGENTS.md in every directory",
                        f"{override} is present for {tool} and makes the AGENTS.md beside it inert"),
                    evidence=[Evidence(override)],
                    remediation="Delete the override, or make it a deliberate, documented superset.",
                ))
        if canonical_nested:
            detail_parts.append(f"{len(canonical_nested)} nested instruction file(s)")

    if not findings:
        verdict = Verdict.PASS
    else:
        verdict = Verdict.FAIL if any(f.verdict is Verdict.FAIL for f in findings) else Verdict.PARTIAL

    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary="; ".join(detail_parts), findings=findings)


# ---------------------------------------------------------------------------
# AGT-02 — component coverage
# ---------------------------------------------------------------------------

def check_agt02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    members = [c for c in components.declared if not c.is_root]
    if not members:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary="single-root repository: no component-level instruction files "
                                   "required")

    covered: list[str] = []
    uncovered: list[str] = []
    for component in members:
        candidate = f"{component.path}/AGENTS.md"
        if inventory.has(candidate) or any(
                p.endswith(f"{component.path}/AGENTS.md") for p in instruction_paths(inventory)):
            covered.append(component.path)
        else:
            uncovered.append(component.path)

    ratio = len(covered) / len(members)
    findings: list[Finding] = []
    if uncovered:
        findings.append(Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "get component-scoped rules when it enters a component",
                f"{len(uncovered)} of {len(members)} declared components have no AGENTS.md "
                f"({', '.join(uncovered[:6])}{'…' if len(uncovered) > 6 else ''}), so the root file "
                f"is the only guidance available"),
            remediation="Add a short AGENTS.md per component stating what is local to it — "
                        "ownership, entry points, test verb overrides.",
        ))
    verdict = Verdict.PASS if ratio == 1.0 else (Verdict.FAIL if ratio == 0 else Verdict.PARTIAL)
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=f"coverage {len(covered)}/{len(members)}",
                        data=Ratio(numerator=len(covered), denominator=len(members),
                                   unit="components", method="declared AGENTS.md per component"),
                        findings=findings)


# ---------------------------------------------------------------------------
# AGT-08 — competing instruction files + reach matrix
# ---------------------------------------------------------------------------

def check_agt08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    present = instruction_paths(inventory)
    classified = V.classify_present(present)
    competitors = [p for p in classified["vendor_only"] if p.strip("/") != ""]
    shadowed = classified["shadowed"]
    reached = classified["harnesses_reached"]
    missed = classified["harnesses_missed"]
    findings: list[Finding] = []

    if competitors:
        findings.append(Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "know which instruction file is authoritative",
                f"{len(competitors)} vendor-specific instruction files exist alongside the "
                f"canonical one ({', '.join(competitors[:8])}{'…' if len(competitors) > 8 else ''})"),
            evidence=[Evidence(p) for p in competitors[:12]],
            remediation="Keep AGENTS.md canonical; reduce each vendor file to a pointer at it, or "
                        "delete it if the harness reads AGENTS.md natively.",
        ))
    for winner, loser in shadowed:
        findings.append(Finding(
            check=spec.id, severity=Severity.DEGRADER, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "be sure that both files are read",
                f"{winner} shadows {loser} for the harness that defines the pair, so only one of "
                f"the two is ever loaded"),
            evidence=[Evidence(winner), Evidence(loser)],
            remediation="Reconcile the two files, or delete the shadowed one — a file nobody "
                        "reads still gets edited.",
        ))
    if missed and ("AGENTS.md" in present or competitors):
        findings.append(Finding(
            check=spec.id, severity=Severity.COSMETIC, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "assume every harness on the team sees the project rules",
                f"{len(reached)} of {len(reached) + len(missed)} known harnesses reach an "
                f"instruction file; {', '.join(missed[:8])}{'…' if len(missed) > 8 else ''} reach "
                f"nothing"),
            remediation="Either state the supported harnesses in AGENTS.md, or add the vendor "
                        "pointer files for the harnesses in use.",
        ))

    verdict = Verdict.FAIL if any(f.verdict is Verdict.FAIL for f in findings) else (
        Verdict.PARTIAL if findings else Verdict.PASS)
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status,
                        summary=f"{len(reached)}/{len(reached) + len(missed)} harnesses reached",
                        data=HarnessMatrix(reached=len(reached), total=len(reached) + len(missed),
                                           reached_tools=tuple(sorted(reached)),
                                           unreached_tools=tuple(sorted(missed))),
                        findings=findings)


# ---------------------------------------------------------------------------
# AGT-10 — indirection resolved
# ---------------------------------------------------------------------------

_REFERENCE_RE = re.compile(r"[`\"']?([A-Za-z0-9_./-]+\.(?:md|markdown|txt|yml|yaml|json|toml))[`\"']?")

#: The deferral pattern is deliberately narrow: "read this before you act", not any citation of
#: another file. A wider pattern flags legitimate prose — "refer to package.json for versions",
#: "every doc must follow docs/STYLE_GUIDE.md" — as indirection, and a check that fires on well
#: written instruction files is worse than no check. Calibrated against two real repositories
#: (agentic-tdd: no finding, correct; Digital-Assistant-Server: one finding, correct).
_DEFER_RE = re.compile(
    r"(?i)(first\s+(read|check|review|understand|study)|"
    r"read\s+[^.\n]{0,80}\s+first|"
    r"before\s+(you\s+|starting|beginning|making|editing|changing|any)[^.\n]{0,60}read|"
    r"start\s+by\s+reading|"
    r"refer\s+to\s+[^.\n]{0,60}\s+first)"
)

#: Config keys that name an instruction file elsewhere, and how to read them.
def _configured_targets(inventory: Inventory) -> dict[str, list[str]]:
    """Instruction files named by harness configuration, per config file.

    Only the formats this project can parse without a third-party parser are read. Anything else
    is reported as unparsed rather than assumed absent.
    """
    configured: dict[str, list[str]] = {}

    aider = inventory.read(".aider.conf.yml")
    if aider:
        targets: list[str] = []
        inline = re.search(r"^\s*read:\s*\[(.*?)\]", aider, re.MULTILINE | re.DOTALL)
        block = re.search(r"^\s*read:\s*\n((?:\s*-\s*.*\n?)+)", aider, re.MULTILINE)
        if inline:
            targets += [m.strip() for m in re.findall(r"['\"]([^'\"]+)['\"]", inline.group(1))]
        if block:
            targets += re.findall(r"-\s*['\"]?([^'\"\n]+)['\"]?", block.group(1))
        configured[".aider.conf.yml"] = [t.strip() for t in targets if t.strip()]

    codex = inventory.read(".codex/config.toml")
    if codex:
        targets = []
        for key in ("project_doc_fallback_filenames", "model_instructions_file",
                    "experimental_instructions_file"):
            match = re.search(rf"{key}\s*=\s*(.+)", codex)
            if match:
                targets += re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
        configured[".codex/config.toml"] = targets

    gemini = inventory.read(".gemini/settings.json")
    if gemini:
        targets = []
        try:
            data = json.loads(gemini)
            names = data.get("context", {}).get("fileName") or data.get("contextFileName")
            targets = [names] if isinstance(names, str) else list(names or [])
        except (json.JSONDecodeError, AttributeError):
            targets = []
        configured[".gemini/settings.json"] = targets

    opencode = inventory.read("opencode.json")
    if opencode:
        targets = []
        try:
            instructions = json.loads(opencode).get("instructions", [])
            targets = [i for i in instructions if isinstance(i, str) and not i.startswith("http")]
        except (json.JSONDecodeError, AttributeError):
            targets = []
        configured["opencode.json"] = targets

    return configured


def check_agt10(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    findings: list[Finding] = []
    configured = _configured_targets(inventory)
    detail: list[str] = []

    # 1. a configured pointer that names a file which does not exist
    for config_file, targets in configured.items():
        for name in targets:
            rel = name.strip().lstrip("./")
            if "*" in rel:
                if not inventory.match(rel):
                    findings.append(_broken_pointer(spec, config_file, name))
                continue
            if not inventory.has(rel):
                findings.append(_broken_pointer(spec, config_file, name))
    if configured:
        detail.append(f"{len(configured)} config file(s) name instruction targets")

    # 2. deferral inside the entry file: rules live in another file, unnamed by any config
    entry = inventory.read("AGENTS.md") or inventory.read("CLAUDE.md") or ""
    if entry:
        named_elsewhere = {t.strip().lstrip("./") for targets in configured.values() for t in targets}
        deferred: list[str] = []
        for line in entry.splitlines():
            if not _DEFER_RE.search(line):
                continue
            for reference in _REFERENCE_RE.findall(line):
                candidate = reference.lstrip("./")
                if candidate in {"AGENTS.md", "CLAUDE.md"}:
                    continue
                if inventory.has(candidate) and candidate not in named_elsewhere:
                    deferred.append(candidate)
        if deferred:
            findings.append(Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement(
                    "trust that the referenced rules are actually loaded",
                    f"the instruction file defers its content to {', '.join(sorted(set(deferred)))} "
                    f"and no harness configuration names that file, so loading depends on the agent "
                    f"choosing to follow the pointer"),
                evidence=[Evidence("AGENTS.md",
                                   note="deferral found: " + ", ".join(sorted(set(deferred))))],
                remediation="Inline the rules that must always apply, or name the referenced file "
                            "in each harness's config (aider read:, opencode.json instructions, "
                            "Codex model_instructions_file).",
            ))
        if not _rule_line_count(entry) > 0:
            detail.append("instruction file has no rule lines")

    verdict = Verdict.FAIL if findings else Verdict.PASS
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary="; ".join(detail), findings=findings)


def _broken_pointer(spec, config_file: str, name: str) -> Finding:
    return Finding(
        check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
        statement=statement(
            "receive project instructions from the configured file",
            f"{config_file} points at {name!r}, which does not exist in the repository"),
        evidence=[Evidence(config_file, note=f"missing target: {name}")],
        remediation=f"Create {name}, or remove the stale entry from {config_file}.",
    )


# ---------------------------------------------------------------------------
# Shared readers for the content-contract checks (AGT-03, 04, 06, 07, 09)
# ---------------------------------------------------------------------------

def _entry(inventory: Inventory) -> tuple[str, str]:
    """The entry instruction file and its text: canonical first, else the CLAUDE.md fallback."""
    for name in (*V.CANONICAL_PATHS, "CLAUDE.md"):
        text = inventory.read(name)
        if text:
            return name, text
    return "", ""


def _unknown(spec, reason: str) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                        Verdict.UNKNOWN, spec.status, summary=reason)


def _first_line(text: str, pattern: re.Pattern) -> int | None:
    for no, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return no
    return None


# ---------------------------------------------------------------------------
# AGT-03 — documentation contract named
# ---------------------------------------------------------------------------

_DOCS_NAME_RE = re.compile(r"(?<![\w/])docs/|\bdocs\b")
_STYLE_GUIDE_RE = re.compile(r"STYLE_GUIDE\.md")
_SCRATCH_DIR_RE = re.compile(r"\bartefacts?/|\bartifacts?/")


def check_agt03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    wanted = {
        "docs/": _first_line(text, _DOCS_NAME_RE),
        "docs/STYLE_GUIDE.md": _first_line(text, _STYLE_GUIDE_RE),
        "artefacts/": _first_line(text, _SCRATCH_DIR_RE),
    }
    missing = [label for label, line in wanted.items() if line is None]
    if not missing:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary="docs/, the style guide and the scratch contract are named")

    covered = {label: line for label, line in wanted.items() if line is not None}
    verdict = Verdict.PARTIAL if covered else Verdict.FAIL
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict, spec.status,
        summary=f"does not name {', '.join(missing)}",
        findings=[Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
            statement=statement(
                "know where permanent and scratch documentation live",
                f"{name} does not name {', '.join(missing)}"),
            evidence=[Evidence(name, line=line, note=label) for label, line in covered.items()],
            remediation="Name docs/ as the canonical home for permanent knowledge, "
                        "docs/STYLE_GUIDE.md as the authoring rules, and artefacts/ as off-limits "
                        "scratch."),
        ])


# ---------------------------------------------------------------------------
# AGT-04 — definition of done stated
# ---------------------------------------------------------------------------

_CHANGE_SET_RE = re.compile(r"(?i)\bsame changeset\b|\bsame change set\b")
_DOD_TRIGGER_RE = re.compile(
    r"(?i)\b(public interface|observable behaviou?r|architecture|\badr\b|documentation|docs)\b")


def check_agt04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    lines = text.splitlines()
    change_line: int | None = None
    tied_line: int | None = None
    for no, line in enumerate(lines, start=1):
        if not _CHANGE_SET_RE.search(line):
            continue
        change_line = change_line or no
        window = "\n".join(lines[max(0, no - 3):no + 2])
        if _DOD_TRIGGER_RE.search(window):
            tied_line = no
            break

    if tied_line:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary="definition of done ties a doc trigger to the same change set")

    if change_line:
        why = ("the same-change-set rule is stated but names no documentation trigger (public "
               "interface, observable behaviour, architecture or an ADR)")
    else:
        why = "no definition-of-done sentence ties a documentation trigger to the same change set"
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, Verdict.FAIL, spec.status,
        summary=why,
        findings=[Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement("keep code and its documentation in step", why),
            evidence=[Evidence(name, line=change_line)] if change_line else [],
            remediation="State that a change altering a public interface, observable behaviour, "
                        "architecture, a check's semantics or an ADR updates the affected docs and "
                        "the ADR index in the same change set."),
        ])


# ---------------------------------------------------------------------------
# AGT-05 — six verbs named, and they resolve
# ---------------------------------------------------------------------------

def _mentioned_verbs(text: str) -> set[str]:
    """Which framework verbs the instruction file names, as whole tokens.

    The lookarounds keep ``format`` from being found inside ``format:check`` and ``test`` from being
    found inside ``tests``: a verb is named only when it stands as itself.
    """
    found: set[str] = set()
    for verb in VERBS:
        pattern = re.compile(r"(?<![\w:-])" + re.escape(verb) + r"(?![\w:-])")
        if pattern.search(text):
            found.add(verb)
    return found


def _verb_binding_surface(resolved: dict) -> VerbSurface:
    return VerbSurface(
        verbs=tuple(
            VerbEntry(
                verb=v,
                resolved=v in resolved,
                runner=resolved[v].runner if v in resolved else None,
                command=resolved[v].command if v in resolved else None,
            )
            for v in VERBS
        ),
        resolved_count=len(resolved),
        missing=tuple(v for v in VERBS if v not in resolved),
    )


def check_agt05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    named = _mentioned_verbs(text)
    missing_names = [v for v in VERBS if v not in named]
    names_complete = not missing_names

    # Resolution half. With no runner manifest the resolution evidence is *unavailable*, not
    # negative: CMD-01 reports UNKNOWN in that case too, so this check degrades rather than piling
    # a second failure onto an unrecognised ecosystem.
    if not runner_commands(inventory):
        if names_complete:
            return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                                Verdict.PARTIAL, spec.status,
                                summary=f"all {len(VERBS)} verbs named, but no runner defines them",
                                data=_verb_binding_surface({}),
                                findings=[Finding(
                                    check=spec.id, severity=Severity.DEGRADER, phase=spec.phase,
                                    verdict=Verdict.PARTIAL,
                                    statement=statement(
                                        "run the named verbs",
                                        f"{name or 'the instruction file'} names every verb but no "
                                        f"runner manifest defines them"),
                                    evidence=[Evidence(name)] if name else [],
                                    remediation="Add the verbs to a runner (package.json scripts, "
                                                "a Makefile, a Taskfile) so the names execute.")])
        return _unknown(spec, "no verb runner and no complete verb list to resolve; CMD-01 owns "
                              "the missing-runner finding")

    resolved = resolve_verbs(inventory, stack)
    missing_resolution = [v for v in VERBS if v not in resolved]
    resolves_complete = not missing_resolution

    if names_complete and resolves_complete:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary=f"all {len(VERBS)} verbs named in {name or 'the entry file'} "
                                   f"and resolved on a runner",
                            data=_verb_binding_surface(resolved))

    verdict = Verdict.PARTIAL if (names_complete or resolves_complete) else Verdict.FAIL
    because = []
    if missing_names:
        because.append(f"not named: {', '.join(missing_names)}")
    if missing_resolution:
        because.append(f"not resolved: {', '.join(missing_resolution)}")
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary="; ".join(because),
                        data=_verb_binding_surface(resolved),
                        findings=[Finding(
                            check=spec.id, severity=spec.severity, phase=spec.phase,
                            verdict=verdict,
                            statement=statement(
                                "use the project's own commands instead of inventing them",
                                "; ".join(because)),
                            remediation="List all seven verbs in AGENTS.md and define each on one "
                                        "runner so the instruction and the manifest agree.")])


# ---------------------------------------------------------------------------
# AGT-06 — architectural boundaries declared
# ---------------------------------------------------------------------------

_BOUNDARY_CONTEXT_RE = re.compile(
    r"(?i)\b(must|never|only|prohibit|forbidden|boundar|module|owns?|responsible|responsibility|"
    r"import|depend|layer|allow|deny|exclude|separate|isolat)\b")
_PATH_TOKEN_RE = re.compile(
    r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+)`"
    r"|(?<![\w/`])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+)")


def _path_is_real(inventory: Inventory, token: str) -> bool:
    """True when a mentioned path resolves to a file or a directory prefix in the target."""
    token = token.strip("`").lstrip("./").rstrip("/")
    if not token:
        return False
    if inventory.has(token):
        return True
    return any(f.rel == token or f.rel.startswith(token + "/") for f in inventory.files)


def check_agt06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    referenced: dict[str, int] = {}
    for no, line in enumerate(text.splitlines(), start=1):
        if not _BOUNDARY_CONTEXT_RE.search(line):
            continue
        for match in _PATH_TOKEN_RE.finditer(line):
            token = match.group(1) or match.group(2)
            if _path_is_real(inventory, token):
                referenced.setdefault(token.strip("`").rstrip("/"), no)

    count = len(referenced)
    if count >= 2:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary=f"{count} boundary rules reference real paths")

    verdict = Verdict.PARTIAL if count == 1 else Verdict.FAIL
    why = (f"only {count} boundary rule references a path that exists in this repository"
           if count else "no boundary rule references a path that exists in this repository")
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict, spec.status,
        summary=why,
        findings=[Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
            statement=statement("learn where code may live and what may cross a boundary", why),
            evidence=[Evidence(name, line=line, note=token)
                      for token, line in referenced.items()],
            remediation="State at least two boundaries as rules naming real paths — for example "
                        "where application code lives and where tests live."),
        ])


# ---------------------------------------------------------------------------
# AGT-07 — prohibitions / do-not-do rules
# ---------------------------------------------------------------------------

_PROHIBITION_HEADING_RE = re.compile(
    r"(?i)\b(do[- ]?not|don't|prohibit\w*|deny|forbidden|never|no[- ]?go)\b")
_PROHIBITION_LINE_RE = re.compile(
    r"(?i)\b(never|do not|don't|must not|mustn't|prohibit(?:ed)?|forbidden|off-limits)\b|❌")

#: The four concerns the framework names for the prohibitions list. Generated build output and
#: transient scratch are treated together: both are machine-produced and must not be hand-edited.
_AGT07_CONCERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("tests", re.compile(r"(?i)\b(tests?|skip|xfail)\b")),
    ("generated files", re.compile(
        r"(?i)(generated|build output|vendored|artefacts?/|artifacts?/|dist/|__pycache__|"
        r"committed artifact)")),
    ("the default branch", re.compile(
        r"(?i)(default branch|force-?push|rewrite history|protected branch|\bpush\b|\bmain\b)")),
    ("secrets", re.compile(r"(?i)(secret|credential|api[ -]?key|\.env|redaction|token)")),
)


def _has_prohibition_section(text: str) -> bool:
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match and _PROHIBITION_HEADING_RE.search(match.group(2)):
            return True
    return False


def check_agt07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    if not _has_prohibition_section(text):
        return CheckOutcome(
            spec.id, spec.title, spec.tier, spec.severity, spec.phase, Verdict.FAIL, spec.status,
            summary="no prohibitions section",
            findings=[Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
                statement=statement("rely on an explicit do-not list",
                                    f"{name} has no prohibitions section"),
                evidence=[Evidence(name)],
                remediation="Add an explicit prohibitions section covering tests, generated files, "
                            "the default branch and secrets.")])

    covered: dict[str, int] = {}
    for no, line in enumerate(text.splitlines(), start=1):
        if not _PROHIBITION_LINE_RE.search(line):
            continue
        for label, pattern in _AGT07_CONCERNS:
            if label not in covered and pattern.search(line):
                covered[label] = no

    missing = [label for label, _ in _AGT07_CONCERNS if label not in covered]
    if not missing:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary="prohibitions cover tests, generated files, the default branch "
                                   "and secrets")

    verdict = Verdict.PARTIAL if covered else Verdict.FAIL
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict, spec.status,
        summary=f"not covered: {', '.join(missing)}",
        findings=[Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
            statement=statement(
                "rely on an explicit do-not list",
                f"{name} does not prohibit edits to {', '.join(missing)}"),
            evidence=[Evidence(name, line=line, note=label) for label, line in covered.items()],
            remediation="Add an explicit prohibition for each of: tests, generated files, the "
                        "default branch and secrets."),
        ])


# ---------------------------------------------------------------------------
# AGT-09 — branch and release boundary
# ---------------------------------------------------------------------------

_BRANCH_RE = re.compile(r"(?i)\b(branch(?:es|ing)?|main|dev|trunk)\b")
#: "release" is read broadly: an explicit restriction on pushing, tagging or publishing bounds what
#: an agent may release, so any of these counts as the release half of the boundary.
_RELEASE_RE = re.compile(r"(?i)\b(tag|release|publish|deploy|push)\b")


def check_agt09(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = _entry(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    branch_line = _first_line(text, _BRANCH_RE)
    release_line = _first_line(text, _RELEASE_RE)

    if branch_line and release_line:
        return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase,
                            Verdict.PASS, spec.status,
                            summary="the branch model and the release boundary are stated")
    if branch_line:
        verdict = Verdict.PARTIAL
        why = "the branch model is stated but nothing says whether an agent may tag or release"
    elif release_line:
        verdict = Verdict.PARTIAL
        why = "a release boundary is stated but the branches that exist are not"
    else:
        verdict = Verdict.FAIL
        why = "neither the branch model nor the release boundary is stated"

    evidence = [Evidence(name, line=line)
                for line in (branch_line, release_line) if line]
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict, spec.status,
        summary=why,
        findings=[Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=verdict,
            statement=statement("know which branch to work on and whether it may cut a release", why),
            evidence=evidence,
            remediation="State the branches that exist (for example main and dev) and whether an "
                        "agent may tag or publish a release."),
        ])


IMPLEMENTATIONS = {
    "AGT-01": check_agt01,
    "AGT-02": check_agt02,
    "AGT-03": check_agt03,
    "AGT-04": check_agt04,
    "AGT-05": check_agt05,
    "AGT-06": check_agt06,
    "AGT-07": check_agt07,
    "AGT-08": check_agt08,
    "AGT-09": check_agt09,
    "AGT-10": check_agt10,
}
