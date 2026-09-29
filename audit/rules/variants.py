"""Instruction-file variant table — ONE data structure, in code, with sources.

A scan that only looks for ``AGENTS.md`` produces two errors in opposite directions: it reports
"ungoverned" for a repository whose rules live in ``CLAUDE.md``, and "governed" for one whose
``AGENTS.md`` is inert because a sibling override file shadows it. This module is the single
source of truth for the variant space, kept in code (not JSON) so it stays greppable, importable,
and packable into a zipapp without filesystem access.

Every entry carries the documentation URL it came from and a ``last_verified`` date. The table
rots: harnesses rebrand and rename (Windsurf → Devin Desktop) and vendors ship new formats. The
report's provenance block carries ``ruleset_revision`` so a report can be attributed to an exact
revision of this table, and a stale table is visible rather than silent.

Research basis: vendor documentation for each harness, consolidated 2026-09-28. Claims marked
``verified=False`` are derived from secondary evidence and must be spot-checked before any
behaviour depends on them.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from typing import Literal

LAST_VERIFIED = "2026-09-28"

AgentsMdSupport = Literal["native", "fallback", "only-if-configured", "no"]


@dataclass(frozen=True)
class Harness:
    """How one harness obtains its repository instructions."""

    tool: str
    #: does it read AGENTS.md, and does it need configuration first?
    agents_md: AgentsMdSupport
    #: does it read AGENTS.md in subdirectories, or root only?
    nested: bool
    #: this harness's own instruction paths (globs, POSIX, relative to the repo root)
    paths: tuple[str, ...] = ()
    #: config files that can redirect or rename its instruction file
    config: tuple[str, ...] = ()
    doc_url: str = ""
    verified: bool = True
    note: str = ""


#: The canonical file, and the aliases that are NOT the standard.
CANONICAL_PATHS: tuple[str, ...] = ("AGENTS.md",)

#: Read as fallbacks by some harnesses, but NOT part of the AGENTS.md standard. The standard's own
#: migration advice is `mv AGENT.md AGENTS.md && ln -s AGENTS.md AGENT.md`.
NON_CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "AGENT.md": ("Zed", "Amp", "Devin", "Roo Code"),
    ".rules": ("Zed",),
    "AGENTS.local.md": ("Devin",),
}

#: A per-directory override that makes the sibling AGENTS.md inert. Reported separately, never
#: counted as "governed" (docs: Check Catalogue § AGT).
OVERRIDE_PATHS: dict[str, str] = {
    "AGENTS.override.md": "OpenAI Codex CLI",
}

HARNESSES: tuple[Harness, ...] = (
    # ---- first-party vendors -------------------------------------------
    Harness("OpenAI Codex CLI", "native", True,
            paths=("AGENTS.md", "AGENTS.override.md"),
            config=(".codex/config.toml",),
            doc_url="https://developers.openai.com/codex/agent-configuration/agents-md",
            note="Walks project root → cwd, at most one file per directory; AGENTS.override.md wins "
                 "and makes AGENTS.md inert there. Concatenated cap 32 KiB (project_doc_max_bytes)."),
    Harness("Anthropic Claude Code", "fallback", True,
            paths=("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md", ".claude/rules/**/*.md",
                   ".claude/AGENTS.md"),
            config=(".claude/settings.json",),
            doc_url="https://code.claude.com/docs/en/memory",
            verified=False,
            note="Documentation is self-contradictory: the memory page says AGENTS.md may load "
                 "'on its own or alongside CLAUDE.md', while the row behaviour is config-gated "
                 "(pluginConfigs['agents-md@builtin']). Treat CLAUDE.md + AGENTS.md coexisting as "
                 "drift risk regardless of which loads today."),
    Harness("Google Gemini CLI", "only-if-configured", True,
            paths=("GEMINI.md",),
            config=(".gemini/settings.json",),
            doc_url="https://geminicli.com/docs/reference/configuration/",
            note="context.fileName defaults to GEMINI.md. Note the product was replaced by "
                 "Antigravity CLI for unpaid/Google One tiers on 2026-06-18."),
    Harness("Jules (Google)", "native", False,
            paths=("AGENTS.md",),
            doc_url="https://jules.google/docs/",
            verified=False,
            note="Documented as repository-root only; nested support unconfirmed."),
    Harness("GitHub Copilot / VS Code", "native", True,
            paths=(".github/copilot-instructions.md", ".github/instructions/**/*.instructions.md",
                   "CLAUDE.md", "GEMINI.md"),
            config=(".vscode/settings.json",),
            doc_url="https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions",
            note="Nested AGENTS.md support is DISABLED by default in VS Code "
                 "(chat.useNestedAgentsMdFiles). Organisation-level instructions live in the web UI, "
                 "so no repo file evidences them."),

    # ---- IDE / editor agents -------------------------------------------
    Harness("Cursor", "native", True,
            paths=(".cursor/rules/**/*.mdc", ".cursorrules"),
            doc_url="https://cursor.com/docs/rules",
            note="Plain .md inside .cursor/rules is silently IGNORED — .mdc with frontmatter is "
                 "required. .cursorrules is legacy and no longer vendor-documented."),
    Harness("Windsurf / Devin Desktop", "native", True,
            paths=(".devin/rules/**/*.md", ".devin/global_rules.md", ".windsurf/rules/**/*.md",
                   ".windsurfrules"),
            doc_url="https://docs.devin.ai/desktop/cascade/memories",
            note="Rebranded: .devin/ is preferred and shadows .windsurf/. AGENTS.md matching is "
                 "case-insensitive here."),
    Harness("Zed", "native", False,
            paths=("AGENT.md", ".rules", ".cursorrules", ".windsurfrules", ".clinerules",
                   ".github/copilot-instructions.md", "CLAUDE.md", "GEMINI.md"),
            doc_url="https://zed.dev/docs/ai/instructions",
            note="Uses the FIRST matching file in its documented order — it does not merge them."),
    Harness("Continue", "no", False,
            paths=(".continue/rules/**/*.md",),
            doc_url="https://docs.continue.dev/customize/rules",
            note="No documented AGENTS.md support (open feature request)."),
    Harness("Cline", "native", False,
            paths=(".clinerules/**", ".cline/rules/**", ".clinerules", ".cursorrules",
                   ".windsurfrules"),
            doc_url="https://docs.cline.bot/customization/cline-rules",
            note="Both .clinerules/ and .cline/rules/ are searched; single-file .clinerules is the "
                 "historical format."),
    Harness("Roo Code", "native", False,
            paths=(".roo/rules/**", ".roo/rules-*/**", ".roorules", ".roorules-*", ".clinerules"),
            doc_url="https://roocodeinc.github.io/Roo-Code/features/custom-instructions",
            note="Workspace root ONLY — no nested discovery. A non-empty .roo/rules/ makes "
                 ".roorules and .clinerules inert."),
    Harness("JetBrains Junie", "native", False,
            paths=(".junie/AGENTS.md", ".junie/guidelines.md", ".junie/rules/*.md",
                   ".junie/playbook.md"),
            doc_url="https://junie.jetbrains.com/docs/guidelines-and-memory.html"),
    Harness("Amazon Q Developer", "no", False,
            paths=(".amazonq/rules/**/*.md", "AmazonQ.md"),
            doc_url="https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/context-project-rules.html",
            note="Markdown only, project root. AGENTS.md support is an open feature request."),
    Harness("Kiro (AWS)", "native", True,
            paths=(".kiro/steering/**/*.md",),
            doc_url="https://kiro.dev/docs/steering/",
            note="Custom agents only see steering if the agent JSON lists it under resources."),
    Harness("Trae", "native", False,
            paths=(".trae/rules/**/*.md", "CLAUDE.md", "CLAUDE.local.md"),
            doc_url="https://docs.trae.ai/ide/rules"),
    Harness("Augment Code", "native", True,
            paths=(".augment/rules/**/*.md", ".augment-guidelines", "CLAUDE.md"),
            doc_url="https://docs.augmentcode.com/setup-augment/guidelines",
            note="Only AGENTS.md and CLAUDE.md are discovered hierarchically; .augment/rules is "
                 "workspace-root only."),
    Harness("Firebase Studio (ex-IDX)", "native", False,
            paths=(".idx/airules.md", "GEMINI.md", ".gemini/styleguide.md"),
            doc_url="https://firebase.google.com/docs/studio/set-up-gemini#custom-instructions",
            note="Precedence: .idx/airules.md > GEMINI.md > .gemini/styleguide.md > AGENTS.md. "
                 "Sunsetting 2027-03-22."),

    # ---- CLI / terminal agents -----------------------------------------
    Harness("opencode", "native", True,
            paths=("AGENTS.md", "CLAUDE.md"),
            config=("opencode.json",),
            doc_url="https://opencode.ai/docs/rules/",
            note="AGENTS.md wins; CLAUDE.md is a fallback only when no AGENTS.md exists. "
                 "opencode.json `instructions` can add paths, globs and URLs."),
    Harness("Sourcegraph Amp", "native", True,
            paths=("AGENTS.md", "AGENT.md", "CLAUDE.md"),
            doc_url="https://ampcode.com/docs/customize/agents-md",
            note="AGENT.md / CLAUDE.md are per-directory fallbacks when that directory has no "
                 "AGENTS.md."),
    Harness("Warp", "native", True,
            paths=("AGENTS.md", "WARP.md", "CLAUDE.md", ".cursorrules", "AGENT.md", "GEMINI.md",
                   ".clinerules", ".windsurfrules", ".github/copilot-instructions.md"),
            doc_url="https://docs.warp.dev/agents/capabilities/rules/",
            note="Filename MUST be all caps. Where both exist in one directory, WARP.md wins. "
                 "Other vendor files are linked to AGENTS.md by `/init`, not read natively."),
    Harness("Goose (Block)", "native", True,
            paths=("AGENTS.md", ".goosehints"),
            doc_url="https://goose-docs.ai/docs/guides/context-engineering/using-goosehints/",
            note="Default CONTEXT_FILE_NAMES is [AGENTS.md, .goosehints]; overridable by env var."),
    Harness("Charm Crush", "native", False,
            paths=("AGENTS.md", "CRUSH.md"),
            doc_url="https://github.com/charmbracelet/crush",
            note="Project context file name is set at init (option initialize-as), so it can be "
                 "renamed to something else entirely."),
    Harness("Replit Agent", "no", False,
            paths=("replit.md",),
            doc_url="https://docs.replit.com/features/project-setup/replit-dot-md",
            note="Project root ONLY; subdirectories are not detected, and Replit states the file "
                 "does not apply to other tools."),
    Harness("Devin (Cognition)", "native", True,
            paths=("AGENTS.md", "AGENTS.local.md", "AGENT.md", "CLAUDE.md", ".windsurfrules",
                   ".devin/rules/**/*.md", ".devin/global_rules.md"),
            config=(".devin/config.json",),
            doc_url="https://docs.devin.ai/cli/extensibility/rules",
            note="The most permissive importer: read_config_from can opt into other tools' rules."),
    Harness("Aider", "only-if-configured", False,
            paths=("CONVENTIONS.md",),
            config=(".aider.conf.yml",),
            doc_url="https://aider.chat/docs/usage/conventions.html",
            note="Aider has NO fixed instruction filename — it loads whatever `read:` names. "
                 "CONVENTIONS.md is documentation convention, not auto-detection."),
    Harness("Bolt (StackBlitz)", "native", False,
            paths=("agents.md",),
            doc_url="https://support.bolt.new/best-practices/manage-context",
            verified=False,
            note="Help centre spells it lowercase; case sensitivity unverified."),
    Harness("Qwen Code", "no", True,
            paths=("QWEN.md",),
            doc_url="https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/",
            verified=False),
    Harness("Void", "no", False,
            paths=(".voidrules",),
            doc_url="https://github.com/voideditor/void/issues/643",
            verified=False,
            note="Repository archived 2026-06-02; format may be dead."),
)

#: Config keys that point at a differently-named instruction file. A filename-only detector is
#: wrong here, and this is a real pattern in the wild (see the AGT-10 check).
CONFIG_INDIRECTION: tuple[tuple[str, str, str, str], ...] = (
    (".aider.conf.yml", "read:", "names the files Aider always loads", "https://aider.chat/docs/config/aider_conf.html"),
    (".codex/config.toml", "project_doc_fallback_filenames", "renames/replaces the instruction file", "https://developers.openai.com/codex/config-reference"),
    (".codex/config.toml", "model_instructions_file", "a path that replaces AGENTS.md entirely", "https://developers.openai.com/codex/config-reference"),
    (".gemini/settings.json", "context.fileName", "renames the context file (string or array)", "https://geminicli.com/docs/reference/configuration/"),
    ("opencode.json", "instructions", "adds paths, globs or URLs alongside AGENTS.md", "https://opencode.ai/docs/config/"),
    (".crushrc", "initialize-as / global-context-path", "renames or relocates the context file", "https://github.com/charmbracelet/crush"),
    (".devin/config.json", "read_config_from", "opts into other harnesses' rule files", "https://docs.devin.ai/cli/extensibility/rules"),
    (".vscode/settings.json", "chat.useAgentsMdFile / chat.useNestedAgentsMdFiles", "gates whether AGENTS.md and nested files are read at all", "https://code.visualstudio.com/docs/agent-customization/custom-instructions"),
    ("env CONTEXT_FILE_NAMES", "(environment)", "Goose: JSON array replacing [AGENTS.md, .goosehints]", "https://goose-docs.ai/docs/guides/context-engineering/using-goosehints/"),
)

#: Pairs where the presence of one file changes whether the other is read at all. Report these
#: explicitly: a repo can carry both files while only one is ever consumed.
SHADOW_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("AGENTS.override.md", "AGENTS.md", "Codex: the override wins per directory; AGENTS.md there is inert",
     "https://developers.openai.com/codex/agent-configuration/agents-md"),
    ("CLAUDE.md", "AGENTS.md", "Claude Code may read only CLAUDE.md when it is present",
     "https://code.claude.com/docs/en/memory"),
    ("WARP.md", "AGENTS.md", "Warp: WARP.md wins in the same directory",
     "https://docs.warp.dev/agents/capabilities/rules/"),
    (".roo/rules/**", ".roorules", "Roo: a non-empty .roo/rules makes the single-file forms inert",
     "https://roocodeinc.github.io/Roo-Code/features/custom-instructions"),
    (".devin/rules/**", ".windsurf/rules/**", "Devin: .devin/ shadows .windsurf/",
     "https://docs.devin.ai/cli/extensibility/rules"),
    (".cursor/rules/**/*.mdc", ".cursorrules", "Cursor: legacy single file is superseded",
     "https://cursor.com/docs/rules"),
    (".idx/airules.md", "AGENTS.md", "Firebase Studio: precedence chain ends at AGENTS.md",
     "https://firebase.google.com/docs/studio/set-up-gemini#custom-instructions"),
)

#: Directories and files that look like instructions but are not. Flagging these produces noise on
#: every repository that uses the harness in question.
NON_INSTRUCTION_GLOBS: tuple[tuple[str, str], ...] = (
    (".opencode/**", "opencode tool state (node_modules, logs, agent definitions)"),
    (".agentic-tdd/**", "pipeline run state, logs and per-run config"),
    (".codex/rules/*.rules", "Starlark command-approval rules, not prose instructions"),
    (".codex/config.toml", "harness config"),
    (".codex/hooks.json", "harness hooks"),
    (".github/prompts/*.prompt.md", "reusable prompts, not always-on instructions"),
    (".github/agents/*.md", "Copilot custom agent definitions"),
    (".github/skills/*/SKILL.md", "skill definition, loaded on demand"),
    (".claude/skills/*/SKILL.md", "skill definition, loaded on demand"),
    (".agents/skills/*/SKILL.md", "skill definition, loaded on demand"),
    (".amazonq/cli-agents/*.json", "agent configuration"),
    (".amazonq/rules/memory-bank/*.md", "generated repository summary, not authored instructions"),
)

#: Ignore-file conventions. These are exclusion semantics, not instructions — they matter to
#: CON-03 (artefacts excluded from the index) and EXEC-05, not to AGT.
IGNORE_FILES: tuple[tuple[str, str, str], ...] = (
    ("codebase-memory-mcp", ".cbmignore", "https://github.com/nicobailon/codebase-memory-mcp"),
    ("Cursor", ".cursorignore", "https://cursor.com/docs/reference/ignore-file"),
    ("Cursor", ".cursorindexingignore", "https://cursor.com/docs/reference/ignore-file"),
    ("Roo Code", ".rooignore", "https://roocodeinc.github.io/Roo-Code/features/rooignore/"),
    ("Cline", ".clineignore", "https://docs.cline.bot/customization/clineignore"),
    ("Aider", ".aiderignore", "https://aider.chat/docs/config/aider_conf.html"),
    ("Gemini CLI", ".geminiignore", "https://geminicli.com/docs/cli/gemini-ignore/"),
    ("Gemini Code Assist", ".aiexclude", "https://docs.cloud.google.com/gemini/docs/codeassist/create-aiexclude-file"),
    ("JetBrains AI Assistant", ".aiignore", "https://www.jetbrains.com/help/ai-assistant/disable-ai-assistant.html"),
    ("Continue", ".continueignore", "https://docs.continue.dev/reference/deprecated-codebase"),
    ("Charm Crush", ".crushignore", "https://github.com/charmbracelet/crush#ignoring-files"),
    ("Devin / Windsurf", ".codeiumignore", "https://docs.devin.ai/cli/extensibility/rules"),
    ("Goose", ".gooseignore", "https://github.com/block/goose/issues/1782"),
)

#: Harnesses that read *only* the canonical file. Used to state the consequence of vendor-only
#: governance: "these harnesses get nothing here".
AGENTS_MD_NATIVE_TOOLS: tuple[str, ...] = tuple(
    h.tool for h in HARNESSES if h.agents_md == "native"
)


# ---------------------------------------------------------------------------
# derived helpers — pure functions over a set of present paths
# ---------------------------------------------------------------------------

def harness_paths(harness: Harness) -> tuple[str, ...]:
    """All instruction paths this harness reads, including the canonical file if it reads it."""
    paths = list(harness.paths)
    if harness.agents_md == "native":
        paths.append("AGENTS.md")
    return tuple(paths)


def _matches(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or rel == p.strip("*/")
               or fnmatch.fnmatch(rel, p.replace("**/", "")) for p in patterns)


def classify_present(present: set[str]) -> dict[str, object]:
    """Classify the instruction files present in a repository.

    Returns a dict with: canonical, aliases, overrides, vendor_only, shadowed, harnesses_reached,
    harnesses_missed. Pure function — no inventory object, so it is trivially testable.

    Classification is by **basename**, so a component-scoped `packages/api/AGENTS.md` is canonical,
    not a competing vendor file. A nested canonical file is component coverage (`AGT-02`), never a
    competitor (`AGT-08`).
    """
    canonical = sorted(p for p in present if os.path.basename(p) in CANONICAL_PATHS)
    aliases = sorted(p for p in present if os.path.basename(p) in NON_CANONICAL_ALIASES)
    overrides = sorted(p for p in present if os.path.basename(p) in OVERRIDE_PATHS)
    vendor = sorted(p for p in present
                    if os.path.basename(p) not in CANONICAL_PATHS
                    and os.path.basename(p) not in NON_CANONICAL_ALIASES
                    and os.path.basename(p) not in OVERRIDE_PATHS)

    # a vendor file is "shadowed" when a higher-precedence file for the same harness is present
    shadowed: list[tuple[str, str]] = []
    for winner, loser, _why, _url in SHADOW_PAIRS:
        if any(_matches(p, (winner,)) for p in present) and any(_matches(p, (loser,)) for p in present):
            shadowed.append((winner, loser))

    reached, missed = [], []
    for harness in HARNESSES:
        if any(_matches(p, harness_paths(harness)) for p in present):
            reached.append(harness.tool)
        else:
            missed.append(harness.tool)

    return {
        "canonical": canonical,
        "aliases": aliases,
        "overrides": overrides,
        "vendor_only": [p for p in vendor if p not in canonical],
        "shadowed": shadowed,
        "harnesses_reached": sorted(reached),
        "harnesses_missed": sorted(missed),
    }


def mis_cased_canonical_candidates(present: set[str]) -> list[str]:
    """Files whose name matches AGENTS.md case-insensitively but not exactly.

    On a case-sensitive filesystem (every Linux CI box) ``agents.md`` is a different file from
    ``AGENTS.md``: such a repository is governed on the author's Mac and silently ungoverned on
    Linux. Warp additionally requires ALL CAPS; Bolt's own docs spell it lowercase.
    """
    return sorted(p for p in present
                  if p.lower() in {c.lower() for c in CANONICAL_PATHS} and p not in CANONICAL_PATHS)
