# Glossary

Canonical definitions of domain terms used in this project. Both humans and AI agents should use these terms
consistently. Terms inherited from the readiness framework are cited, not redefined.

---

| Term | Definition |
|---|---|
| **Agentic Readiness** | The state in which a codebase gives AI coding agents reliable context, bounded scope, a deterministic verification loop, and executable quality gates. Defined by the framework: [Phases 1–4](https://github.com/Nistapp/codebase-agentic-readiness-framework/blob/main/brownfield-legacy/Phased-Approach.md). |
| **Phase (1–4)** | The mandatory, sequential foundation phases of the readiness framework: Bootstrap, Source Docs, Agent Docs, Contracts & Baselines. Phase 1 is the scope of this audit's score. |
| **Phase (5–7)** | Post-readiness roadmap activities (Refactoring, Human Docs, Spec-Driven Development). Out of scope for this tool — reported, never scored. |
| **Tier** | How a check obtains its evidence. **Tier A** — artifact existence. **Tier B** — content and cross-artifact invariants (parse/regex/set-difference). **Tier C** — executed probes against the target. |
| **Verdict** | The outcome of one check: `PASS`, `PARTIAL`, `FAIL`, `UNKNOWN`, or `ATTEST`. `UNKNOWN` means the check could not gather evidence. `ATTEST` means the property is not statically verifiable and requires human confirmation. |
| **Severity** | The effect of a finding on agent work, independent of framework phase: **BLOCKER** (agent work is impossible or unsafe), **DEGRADER** (possible but unreliable), **COSMETIC** (hygiene). |
| **Finding** | One reportable gap: a stable id, the check that produced it, evidence (`path:line`), severity, and a remediation hint. |
| **Check ID** | The stable identifier for a check in the catalogue, e.g. `EXEC-02`. Cited in findings, docs, and tests so a verdict can be traced to its rule. |
| **Rule pack** | The declarative record for a check: id, phase, ecosystems, tier, weight, severity, and the framework anchor it implements. Rules are data; the scan engine is behaviour. |
| **Scan engine** | The bounded, read-only traversal that inventories the target — file classification, exclusion rules, size limits, and provenance hashes. |
| **Stack detector** | The stage that identifies languages, build manifests, test frameworks, CI provider, and component layout from the target's manifests. It decides which rule packs apply. |
| **Declared component** | A component named by a build manifest: `workspaces`, `pnpm-workspace.yaml`, maven `<modules>`, gradle `include(...)`, `go.work use`, Cargo `[workspace] members`, Nx `project.json`. The only kind of component that is scored. |
| **Candidate component (undeclared)** | A directory that looks like a component (a second manifest, an app or service folder) with no workspace declaration naming it. Reported as informational and never scored. |
| **Component depth** | How far the audit walks the component tree when checking per-component governance coverage. This tool walks depth 1 over declared components — see [ADR-0003](adrs/0003-component-depth-declared-depth-1.md). |
| **Six verbs** | The standardized command surface of the framework: `format`, `format:check`, `lint`, `typecheck`, `test`, `check`, `security`. The verbs are the contract; the runner (package scripts, Taskfile, Makefile) is a local choice. |
| **Local↔CI parity** | The invariant that CI invokes the identical command names a human or agent runs locally. A CI-only step is a gate no agent can honour. |
| **Documentation contract** | The rule set `AGENTS.md` must name: `docs/` is the single source of truth, `docs/STYLE_GUIDE.md` is canonical, `artefacts/` is transient and off-limits to agents. |
| **Definition of done (doc trigger)** | A change that alters a public interface, observable behaviour, architecture, or an ADR updates the affected doc pages, their anchors, and the ADR index in the same change set. |
| **Quality baseline** | The recorded, current technical-debt state of a repository (violation counts, coverage floor) that later changes are measured against. |
| **Ratchet** | The "no new violations" mechanism that fails a change only when it makes a baseline worse. The audit's own `--baseline` mode is a ratchet over readiness findings. |
| **Index freshness** | Whether the `codebase-memory-mcp` index for the target reflects the current commit. Reported as a probe result, never inferred from file presence alone. |
| **Attested item** | A Phase-1 property that the audit cannot verify mechanically — whether the index is used, whether a baseline is adequate, whether a suite is trustworthy, whether docs are accurate. Listed explicitly so the report never implies more than it proved. |
| **Provenance (report)** | The header block of every report: tool version, framework revision cited, target git SHA and dirty state, timestamp, and rule-set hash. |
| **Report, not gate** | The governing principle of this tool: it produces an ordered backlog and never fails a build, a PR, or a merge. See [ADR-0001](adrs/0001-report-not-a-gate.md). |
| **Instruction variant** | Any file a harness reads for repository instructions: canonical (`AGENTS.md`) or vendor-specific (`CLAUDE.md`, `.cursor/rules/**/*.mdc`, `GEMINI.md`, `.goosehints`, …). Tabulated in code in `audit/rules/variants.py` with a documentation URL and `last_verified` date per harness. |
| **Instruction indirection** | A config that renames or relocates the instruction file (`.aider.conf.yml` `read:`, `opencode.json` `instructions`, `.codex/config.toml` `model_instructions_file`, `.gemini/settings.json` `context.fileName`), or an instruction file that defers its content to another file. Detected by `AGT-10`. |
| **Shadow pair** | Two instruction files where one stops the other from being read: `AGENTS.override.md` over `AGENTS.md` (Codex), `WARP.md` over `AGENTS.md`, `.devin/rules/` over `.windsurf/rules/`. A repository can carry both while only one is ever consumed. |
| **Reach matrix** | Which known harnesses find an instruction file in this repository and which find nothing. Context for `AGT-08`; informational, never scored. |
| **Rule-set hash** | `sha256` over the check catalogue and the instruction-variant table, recorded in every report's provenance. Two reports with different hashes were produced by different rules. |
| **Instruction file** | The repository-scoped file an agent loads before working — `AGENTS.md` canonically. Harness *global* instruction files are outside the repository and are never scored. |
| *Add terms as they emerge* | — |
