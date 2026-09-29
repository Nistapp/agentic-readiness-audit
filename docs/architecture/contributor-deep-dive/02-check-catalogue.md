# Check Catalogue

> **Audience:** Engineers & Maintainers
> **Related ADRs:** [ADR-0003](../adrs/0003-component-depth-declared-depth-1.md) · [ADR-0004](../adrs/0004-no-llm-in-v1.md)
> **Status:** Live for the `IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`, `TOOL`, `CI`, `TST`, `BASE`, `CON` and `HYG` packs (the `CON-04` emitter included); every catalogued check is implemented save the blocked `CON-01`. This page is the design of record; `audit/rules/registry.py` is its executable form, and `python3 -m audit --list-checks` prints the current truth.

> [!IMPORTANT]
> **The executable rules live in code, not here.** This catalogue holds the id, tier, phase anchor, severity and
> evidence rule for every check — the rationale for each family is in
> [Why These Checks](../user-overview/03-why-these-checks.md). Any change to a check's semantics updates this page
> and its rule pack in the same change set.

---

## 1. Summary

| Group | Checks | Tier A | Tier B | Tier C |
|---|---|---|---|---|
| `IDX` Discovery & index | 3 | 2 | — | 1 |
| `AGT` Agent governance | 10 | 2 | 8 | — |
| `DOC` Documentation contract | 4 | 3 | 1 | — |
| `CMD` Command surface | 4 | — | 4 | — |
| `TOOL` Tooling | 6 | 3 | 3 | — |
| `CI` CI | 3 | — | 3 | — |
| `BASE` Baselines & ratchet | 4 | 2 | 2 | — |
| `CON` Constraints | 4 | — | 3 | — |
| `EXEC` Execution determinism | 7 | 2 | 5 | — |
| `TST` Tests | 5 | 2 | 2 | 1 |
| `NAV` Navigation | 3 | 1 | 2 | — |
| `SEC` Security hygiene | 3 | — | 3 | — |
| **Total catalogued** | **56** | **17** | **36** | **2** |

Plus **13 informational checks** (`NAV-04`, `NAV-05`, `HYG-01`–`HYG-11`), reported and never scored.

Of the 56: `CON-01` carries weight 0 in v1 (its artifact contract is undefined at framework level) and `CON-04` is
an emitter rather than a check, leaving **54 scoreable checks** in v1.

> [!NOTE]
> The tier columns sum to 55, not 56: `CON-04` is an emitter with no tier. The variant research added `AGT-10`.
> Earlier revisions of this table carried per-group tier splits that disagreed with their own rows — `--list-checks`
> is the executable truth, and a mismatch between it and this page is a defect in this page.

---

## 2. `IDX` — Discovery & Index

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `IDX-01` | `codebase-memory-mcp` registered for this repository | A | BLOCKER | A project- or user-level MCP config names the server and the target path | Implemented |
| `IDX-02` | An index exists for this checkout | A | BLOCKER | The index store contains a project whose root path resolves to the target | Implemented |
| `IDX-03` | Index freshness | C | DEGRADER | Indexed git SHA equals target `HEAD`; probe only | Implemented |

---

## 3. `AGT` — Agent Governance

Component-scoped: `AGT-02` reports a ratio over declared components; the remaining checks evaluate the root file
and are reported per component when a component-level file exists.

The pack is driven by **one data structure in code** — `audit/rules/variants.py` — recording every instruction-file
variant per harness with the documentation URL it came from and a `last_verified` date, plus the config-indirection
keys, the shadow pairs, and the globs that only *look* like instructions. A filename-only check is wrong in both
directions: it calls a `CLAUDE.md` repository ungoverned, and an `AGENTS.override.md` repository governed. The table
rots by design (Windsurf → Devin Desktop; Antigravity CLI replacing Gemini CLI), so every report carries a
`ruleset_hash` over the table and the catalogue — rot shows up in provenance instead of being inferred from a
suspicious verdict.

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `AGT-01` | Instruction file present, canonical, and non-trivial | A | BLOCKER | A canonical instruction file is present, over the minimum size, not a stub, not mis-cased, and not shadowed by an override in the same directory | Implemented |
| `AGT-02` | Component coverage | A | DEGRADER | `components with AGENTS.md / declared components`, as a `PARTIAL` ratio | Implemented |
| `AGT-03` | Documentation contract named | B | DEGRADER | Names `docs/`, names `docs/STYLE_GUIDE.md` as canonical, names `artefacts/` as off-limits | Implemented |
| `AGT-04` | Definition of done stated | B | DEGRADER | A doc-trigger sentence exists and names the same change set | Implemented |
| `AGT-05` | Six verbs named | B | DEGRADER | The command block lists `format`, `format:check`, `lint`, `typecheck`, `test`, `check`, `security` and they resolve in `CMD-01` | Implemented |
| `AGT-06` | Architectural boundaries declared | B | DEGRADER | At least two named boundary rules referencing real paths | Implemented |
| `AGT-07` | Do-not-do / deny rules present | B | DEGRADER | A prohibitions section exists and covers tests, generated files, default branch, secrets | Implemented |
| `AGT-08` | No competing instruction files; reach stated | B | DEGRADER | No variant file competes with the canonical one; shadow pairs reconciled; the harnesses that reach nothing are stated | Implemented |
| `AGT-09` | Branch and release boundary declared | B | DEGRADER | States which branches exist and whether an agent may tag or release | Implemented |
| `AGT-10` | Instruction indirection resolved | B | DEGRADER | A file the entry file defers to ("first read …") is named in a harness config (`.aider.conf.yml` `read:`, `opencode.json` `instructions`, `.codex/config.toml` `model_instructions_file`, `.gemini/settings.json` `context.fileName`) or inlined | Implemented |

---

## 4. `DOC` — Documentation Contract

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `DOC-01` | `docs/` exists | A | DEGRADER | Directory present with at least one markdown file | Implemented |
| `DOC-02` | `docs/STYLE_GUIDE.md` exists | A | DEGRADER | File present; `AGT-03` must reference it | Implemented |
| `DOC-03` | `artefacts/` exists and is ignored | B | DEGRADER | Directory present and matched by an ignore rule; contents not tracked | Implemented |
| `DOC-04` | ADR directory and index | A | COSMETIC | An ADR directory exists with an index listing its files | Implemented |

---

## 5. `CMD` — Command Surface

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CMD-01` | Six verbs resolvable on one runner | B | BLOCKER | Each verb maps to a script in exactly one runner (package scripts, `Taskfile`, `Makefile`, `pyproject`, gradle, maven) | Implemented |
| `CMD-02` | `check` composes the read-only verbs | B | BLOCKER | The `check` definition invokes format-check, typecheck and test (or documented equivalents) | Implemented |
| `CMD-03` | No divergent second definition | B | DEGRADER | A second runner may delegate; it must not define its own composition of the gate | Implemented |
| `CMD-04` | Write verbs separated from read-only verbs | B | DEGRADER | A write verb is never invoked by a verification verb | Implemented |

---

## 6. `TOOL` — Tooling

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `TOOL-01` | Formatter configured | B | DEGRADER | A formatter config file and a resolvable write verb | Implemented |
| `TOOL-02` | Linter configured | B | DEGRADER | A linter config file and a resolvable read-only verb | Implemented |
| `TOOL-03` | Type checker configured | A | DEGRADER | Language-appropriate strict configuration (`tsconfig`, `mypy`/`pyright`, `global.json` nullable settings, etc.) | Implemented |
| `TOOL-04` | Dependency / security scan verb | A | DEGRADER | A resolvable verb performing a dependency-audit check | Implemented |
| `TOOL-05` | Local hook chain active | B | DEGRADER | Hook manager configured and wired (`core.hooksPath`, `.pre-commit-config.yaml`, `lefthook.yml`) | Implemented |
| `TOOL-06` | Commit convention enforced | A | COSMETIC | A commit-message hook or equivalent exists | Implemented |

---

## 7. `CI` — Continuous Integration

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CI-01` | Pipeline present, triggered on PRs | B | BLOCKER | A workflow file exists and declares a pull-request trigger | Implemented |
| `CI-02` | Local↔CI parity | B | BLOCKER | Set comparison of CI-invoked commands against the resolved verb set from `CMD-01` | Implemented |
| `CI-03` | CI-only steps flagged | B | DEGRADER | CI steps with no local equivalent are listed as findings | Implemented |

---

## 8. `BASE` — Baselines & Ratchet

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `BASE-01` | Baseline artifact exists | A | DEGRADER | A committed baseline or suppression file, or an equivalent documented mechanism | Implemented |
| `BASE-02` | Current violation counts measured | B | DEGRADER | The audit counts violations with the repository's own configured tooling where possible, and records the method used | Implemented |
| `BASE-03` | No-new-violations mechanism | B | DEGRADER | A committed ratchet — violation budget, suppression count, or comparison step | Implemented |
| `BASE-04` | Coverage floor configured | A | DEGRADER | A coverage threshold exists in test-runner configuration | Implemented |

---

## 9. `CON` — Constraints

> [!WARNING]
> `CON-01` is **blocked**: the framework requires initial Constraint Engineering allow/deny lists as a Phase-1
> deliverable but defines no artifact name or schema for them anywhere in the framework or its templates. Until
> that contract exists this check carries weight 0 and the audit instead *emits* a draft list derived from the
> scan (`CON-04`).

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CON-01` | Allow/deny artifact present | B | BLOCKER | A machine-readable constraint file exists in the documented location | **Blocked — weight 0 in v1** |
| `CON-02` | Test directories protected | B | BLOCKER | Test paths appear on the deny list, or the constraint file excludes them | Implemented |
| `CON-03` | `artefacts/` excluded from index and agent reads | B | DEGRADER | Ignore rules cover `artefacts/`, `artifacts/`, and the tool's own state directory | Implemented |
| `CON-04` | Draft allow/deny emitted | Emitter | — | Writes a draft from the scan: secrets, migrations, generated code, test dirs, IaC, production manifests | Implemented (not scored) |

---

## 10. `EXEC` — Execution Determinism

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `EXEC-01` | Toolchain pinned / wrapper committed | A | BLOCKER | `.nvmrc`/`engines`, `.tool-versions`, `requires-python`, `global.json`, `gradlew`, `mvnw` — at least one appropriate to the detected stack | Implemented |
| `EXEC-02` | Lockfile committed and consistent | B | BLOCKER | Lockfile tracked, and its declared dependencies agree with the manifest | Implemented |
| `EXEC-03` | Non-interactive setup path | A | BLOCKER | A devcontainer, compose file, or setup target/script exists and is documented | Implemented |
| `EXEC-04` | Env-var inventory complete | B | BLOCKER | Set difference of env keys referenced in source against keys in the committed example file | Implemented |
| `EXEC-05` | No generated artifacts committed in-tree | B | DEGRADER | Generated or vendored paths are either untracked or carry a generated-file header | Implemented |
| `EXEC-06` | Documented commands resolve | B | DEGRADER | Every fenced command in README and `AGENTS.md` resolves to a real script, verb, or file | Implemented |
| `EXEC-07` | No competing configs for one concern | B | DEGRADER | At most one authoritative config per concern (lint, format, test, types) | Implemented |

---

## 11. `TST` — Tests

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `TST-01` | Test verb exists, suite non-empty | A | BLOCKER | A resolvable test verb and at least one test file matching the framework's conventions | Implemented |
| `TST-02` | Suite status known | C | DEGRADER | The test verb is run and its exit code recorded; probe only | Implemented |
| `TST-03` | Skip / xfail census | B | DEGRADER | Count of skip, ignore, and expected-failure markers, per test framework | Implemented |
| `TST-04` | Fast path documented | B | DEGRADER | A documented single-test or subset invocation exists | Implemented |
| `TST-05` | Coverage configuration present | A | COSMETIC | Coverage reporting configured in the test runner | Implemented |

---

## 12. `NAV` — Navigation

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `NAV-01` | Declared component boundaries | A | DEGRADER | At least one component declared in a build manifest | Implemented |
| `NAV-02` | Obvious entry points | B | DEGRADER | An entry point is declared (`bin`, `main`, `__main__`, `Application`, `func main`) | Implemented |
| `NAV-03` | Structural red flags | B | COSMETIC | Counts of oversized files, catch-all directories, checked-in binaries, minified assets | Implemented |
| `NAV-04` | Architecture orientation artifact | A | *informational* | `docs/architecture/`, an ADR directory, or a diagram exists | Implemented |
| `NAV-05` | Public-symbol documentation coverage | B | *informational* | Fraction of public symbols carrying a doc comment or docstring | Implemented |

---

## 13. `SEC` — Security Hygiene

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `SEC-01` | `.env` untracked and ignored | B | BLOCKER | No tracked `.env`, and ignore rules cover `.env` shapes | Implemented |
| `SEC-02` | No key-shaped strings in tracked files | B | BLOCKER | Pattern scan of tracked text files for credential shapes; matches reported by path and line only | Implemented |
| `SEC-03` | Ignore patterns cover secret shapes | B | DEGRADER | Ignore rules include key, certificate, and credential extensions | Implemented |

---

## 14. Informational Checks (Reported, Never Scored)

| ID | Check | Tier | Evidence rule | Status |
|---|---|---|---|---|
| `HYG-01` | README | A | Present, non-placeholder | Implemented |
| `HYG-02` | CODEOWNERS | A | Present; paths noted for consistency against the draft deny list | Implemented |
| `HYG-03` | Pull-request template | A | Present | Implemented |
| `HYG-04` | Issue templates | A | At least one present | Implemented |
| `HYG-05` | CONTRIBUTING | A | Present | Implemented |
| `HYG-06` | SECURITY | A | Present | Implemented |
| `HYG-07` | CHANGELOG | A | Present and dated recently | Implemented |
| `HYG-08` | Release process documented | A | A release document exists | Implemented |
| `HYG-09` | Dependency update automation | A | Dependabot, Renovate, or equivalent configured | Implemented |
| `HYG-10` | License | A | A license file exists | Implemented |
| `HYG-11` | Branch protection | B | Protection declared by configuration-as-code where the provider allows | Implemented |

---

## 15. Adding a Check

1. Assign the next id in the appropriate group.
2. State tier, phase anchor, severity, and a **falsifiable** evidence rule — one that a reviewer can apply to a
   fixture and reach the same verdict.
3. Add the failure mode to [Why These Checks](../user-overview/03-why-these-checks.md). No failure mode, no check.
4. Add a broken fixture that fails exactly this check and nothing else.
5. Add the row to the summary table and to the pack's framework anchor before merging.

---

## Related Pages

- Previous: [Scan Engine & Tiering](01-scan-engine-and-tiering.md)
- Rationale: [Why These Checks](../user-overview/03-why-these-checks.md) · [The Readiness Model](../user-overview/02-the-readiness-model.md)
