# Agentic readiness audit

> [!NOTE]
> This audit reports; it does not gate. A completed scan exits 0 unless a threshold or baseline
> was requested (ADR-0001). `UNKNOWN` and `ATTEST` earn no credit and are never rendered as passes.

## Provenance

| Field | Value |
|---|---|
| Target | `/home/kc/Projects/UDAN/Digital-Assistant-SDK` |
| Commit | `748797977412` on `dev` — **dirty working tree** |
| Tool | `python-agentic-audit` `0.1.0` |
| Ruleset | `2026-09-28.13` (hash `f320b6e4a8e8b7cc`) |
| Framework revision | — |
| Phase evaluated | 1 |
| Scanned | `2026-10-06T10:01:24+00:00` |
| Probes enabled | no |

## Scorecard

**Phase-1 score:** `0.44` (21 pass · 8 partial · 34 fail · 6 unknown · 0 attest)

### Verdict distribution (applicable checks)

| Verdict | Checks | Share | Earns credit | Meaning |
|---|--:|--:|:--:|---|
| PASS | 21 | 30.4% | yes | Evidence found; requirement met. |
| PARTIAL | 8 | 11.6% | no | Some of the requirement is met; the ratio is the useful number. |
| FAIL | 34 | 49.3% | no | Requirement not met; a finding is emitted. |
| UNKNOWN | 6 | 8.7% | no | Evidence could not be gathered. An open question about tool coverage. |
| ATTEST | 0 | 0.0% | no | Requires human attestation; not machine-verifiable. |
| **Total** | **69** | **100%** |  | 69 applicable checks |

### Findings by severity

| Severity | Findings | Fix window | Checks affected |
|---|--:|---|---|
| BLOCKER | 18 | Before any agent work | `CI-01`, `CMD-01`, `CMD-02`, `EXEC-01`, `EXEC-02`, `EXEC-03`, `EXEC-04`, `SEC-01`, `SEC-02` |
| DEGRADER | 18 | Schedule | `AGT-03`, `AGT-04`, `AGT-05`, `AGT-07`, `AGT-09`, `BASE-01`, `BASE-02`, `BASE-03`, `BASE-04`, `CON-03`, `DOC-01`, `DOC-02`, `DOC-03`, `SEC-03`, `TOOL-03`, `TOOL-04`, `TOOL-05`, `TST-04` |
| COSMETIC | 14 | Note and move on | `AGT-08`, `DOC-04`, `HYG-01`, `HYG-02`, `HYG-03`, `HYG-04`, `HYG-05`, `HYG-06`, `HYG-07`, `HYG-08`, `HYG-09`, `HYG-10`, `NAV-04`, `TOOL-06` |
| **Total** | **50** |  |  |

> [!IMPORTANT]
> **Coverage caveat.** 54 of 54 scoreable checks are implemented in this ruleset revision; every other check reports UNKNOWN and earns no credit, so this report understates readiness rather than certifying it

## Unattested

These are always listed, on every report. A completed scan cannot settle them; they are
printed so the score is never read as a guarantee.

| Property | What the scan cannot settle |
|---|---|
| `index-in-use` | Whether the codebase index is actually used during agent work. |
| `baseline-adequacy` | Whether the committed baseline or budget is adequate. |
| `suite-trustworthiness` | Whether the passing test suite actually catches regressions. |
| `doc-accuracy` | Whether the documentation matches the code it describes. |
| `gate-honoured` | Whether the gate is actually run and honoured before merge. |

## Command surface

The framework's seven verbs, resolved verb by verb on the target's runners.

| Verb | Resolved | Runner / evidence | Status |
|---|:--:|---|:--:|
| `format` | yes | `package.json` (`prettier --write "src/**/*.ts"`) | defined |
| `format:check` | **no** | — | **MISSING** |
| `lint` | yes | `package.json` (`eslint "src/**/*.ts"`) | defined |
| `typecheck` | **no** | — | **MISSING** |
| `test` | yes | `package.json` (`jest`) | defined |
| `check` | **no** | — | **MISSING** |
| `security` | **no** | — | **MISSING** |

**Concrete fixes**

- `CMD-01` — Define every verb (format, format:check, lint, typecheck, test, check, security) as a script/target so an agent never has to invent a command.
- `CMD-02` — Define check as format-check, then typecheck, then test.
- `AGT-05` — List all seven verbs in AGENTS.md and define each on one runner so the instruction and the manifest agree.

## Credential-shaped lines

16 credential-shaped line(s) across 10 tracked file(s) in tracked text files. The report never records the value itself.

| File | Lines | Count |
|---|---|--:|
| `src/config/constants.ts` | 164 | 1 |
| `src/services/AuthManager.ts` | 104, 189 | 2 |
| `src/services/__tests__/AuthManager.test.ts` | 37, 66 | 2 |
| `src/services/__tests__/TranslateService.test.ts` | 20 | 1 |
| `src/services/__tests__/apiClient.test.ts` | 151, 173, 189, 208 | 4 |
| `src/services/apiClient.ts` | 113, 128 | 2 |
| `src/util/user/UDABindAccount.ts` | 25 | 1 |
| `src/util/user/__tests__/AuthDataConfig.test.ts` | 130 | 1 |
| `src/util/user/__tests__/UDABindAccount.test.ts` | 84 | 1 |
| `src/util/user/__tests__/UDASendSessionData.test.ts` | 33 | 1 |
| **Total** |  | **16** |

## Missing secret-shape ignore rules

| Shape | Status | Suggested `.gitignore` entry |
|---|:--:|---|
| dotenv | **missing** | `.env` |
| dotenv variant | **missing** | `.env.*` |
| ssh private key | **missing** | `id_rsa*` |
| PEM | **missing** | `*.pem` |
| key | **missing** | `*.key` |
| PKCS#12 | **missing** | `*.p12` |
| PFX | **missing** | `*.pfx` |
| keystore | **missing** | `*.keystore` |
| certificate (.crt) | **missing** | `*.crt` |
| certificate (.cer) | **missing** | `*.cer` |
| AWS credentials | **missing** | `.aws/*` |

## Findings — Blocker

| Check | Title | Verdict | Specifics | Evidence | Fix |
|---|---|:--:|---|---|---|
| `CI-01` | Pipeline present, triggered on PRs | FAIL | no CI workflow file (detected providers: none) | `.env` | Add a PR-triggered workflow (for example .github/workflows/ci.yml) that runs the same verbs the local command surface defines. |
| `CMD-01` | Six verbs resolvable on one runner | FAIL | Missing: `format:check`, `typecheck`, `check`, `security` — 3 of 7 defined. | `package.json` | Define every verb (format, format:check, lint, typecheck, test, check, security) as a script/target so an agent never has to invent a command. |
| `CMD-02` | check composes the read-only verbs | FAIL | the check verb is not defined on any runner | — | Define check as format-check, then typecheck, then test. |
| `EXEC-01` | Toolchain pinned / wrapper committed | FAIL | unpinned: node | — | Commit the pin appropriate to node — .nvmrc, .node-version — so the agent's runtime is the repository's, not the host's. |
| `EXEC-02` | Lockfile committed and consistent | FAIL | — | — | Generate the lockfile with the project's package manager and commit it. |
| `EXEC-03` | Non-interactive setup path | FAIL | no setup path found | — | Add a committed setup path (a devcontainer, compose file, or a documented install command in README.md) that runs with no prompts. |
| `EXEC-04` | Env-var inventory complete | FAIL | Missing env keys: `UDA_LOG_LEVEL`, `UDA_LOG_LEVELN`. | `(no example file)` | Add the missing keys to .env.example (values redacted) so the environment can be provisioned without reading the source. |
| `SEC-01` | .env untracked and ignored | PARTIAL | Missing: dotenv, dotenv variant. | `.gitignore` (node_modules)<br>`.gitignore` (dist)<br>`.gitignore` (build)<br>`.gitignore` (environments)<br>`.gitignore` (coverage)<br>`.gitignore` (.jest-cache)<br>`.gitignore` (.DS_Store)<br>`.gitignore` (.vscode) | Add the .env shape (for example `.env` and `.env.*`) to .gitignore so an environment file cannot be committed by accident. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/config/constants.ts:164` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 2 credential-shaped line(s). | `src/services/AuthManager.ts:104` (credential-shaped string)<br>`src/services/AuthManager.ts:189` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 2 credential-shaped line(s). | `src/services/__tests__/AuthManager.test.ts:37` (credential-shaped string)<br>`src/services/__tests__/AuthManager.test.ts:66` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/services/__tests__/TranslateService.test.ts:20` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 4 credential-shaped line(s). | `src/services/__tests__/apiClient.test.ts:151` (credential-shaped string)<br>`src/services/__tests__/apiClient.test.ts:173` (credential-shaped string)<br>`src/services/__tests__/apiClient.test.ts:189` (credential-shaped string)<br>`src/services/__tests__/apiClient.test.ts:208` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 2 credential-shaped line(s). | `src/services/apiClient.ts:113` (credential-shaped string)<br>`src/services/apiClient.ts:128` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/util/user/UDABindAccount.ts:25` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/util/user/__tests__/AuthDataConfig.test.ts:130` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/util/user/__tests__/UDABindAccount.test.ts:84` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 1 credential-shaped line(s). | `src/util/user/__tests__/UDASendSessionData.test.ts:33` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. The report never records the value itself. |

## Findings — Degrader

| Check | Title | Verdict | Specifics | Evidence | Fix |
|---|---|:--:|---|---|---|
| `AGT-03` | Documentation contract named | FAIL | does not name docs/, docs/STYLE_GUIDE.md, artefacts/ | — | Name docs/ as the canonical home for permanent knowledge, docs/STYLE_GUIDE.md as the authoring rules, and artefacts/ as off-limits scratch. |
| `AGT-04` | Definition of done stated | FAIL | no definition-of-done sentence ties a documentation trigger to the same change set | — | State that a change altering a public interface, observable behaviour, architecture, a check's semantics or an ADR updates the affected docs and the ADR index in the same change set. |
| `AGT-05` | Six verbs named | FAIL | Missing: `format:check`, `typecheck`, `check`, `security` — 3 of 7 defined. | — | List all seven verbs in AGENTS.md and define each on one runner so the instruction and the manifest agree. |
| `AGT-07` | Do-not-do / deny rules present | FAIL | no prohibitions section | `AGENTS.md` | Add an explicit prohibitions section covering tests, generated files, the default branch and secrets. |
| `AGT-09` | Branch and release boundary declared | PARTIAL | the branch model is stated but nothing says whether an agent may tag or release | `AGENTS.md:30` | State the branches that exist (for example main and dev) and whether an agent may tag or publish a release. |
| `BASE-01` | Baseline artifact exists | PARTIAL | quality tooling is configured but no baseline artifact is committed: .eslintrc.js, package.json:lint | `.eslintrc.js`<br>`package.json:lint` | Commit a baseline or suppression artifact (for example `baseline.json`, an eslint/ruff baseline, or `.gitleaksignore`), or document the equivalent mechanism in `AGENTS.md`. |
| `BASE-02` | Current violation counts measured | PARTIAL | counting surface present but no committed count/budget: .eslintrc.js, package.json:lint; method: static configuration scan; the target's own tools are never run | `.eslintrc.js`<br>`package.json:lint` | Commit the count or configure a budget (`--max-warnings N`, `max-issues`, or a `violation budget`) so a regression has a baseline number to compare against. |
| `BASE-03` | No-new-violations mechanism | PARTIAL | no ratchet and no baseline yet, so there is nothing to compare against | `<repository>` | Once a baseline exists, wire a comparison step (the audit's own `--baseline REPORT.JSON` is the reference pattern) so new findings fail the build. |
| `BASE-04` | Coverage floor configured | FAIL | no coverage threshold configured | `<repository>` | Configure a coverage floor for the test runner so a drop fails the gate. |
| `CON-03` | artefacts/ excluded from index and agent reads | FAIL | artefacts/ present but matched by no ignore rule | `artefacts/` | Add artefacts/ to .gitignore so agents and the index do not read transient state as source of truth. |
| `DOC-01` | docs/ exists | FAIL | no docs/ directory | — | Create docs/ as the canonical home for permanent knowledge, with docs/STYLE_GUIDE.md holding the authoring rules. |
| `DOC-02` | docs/STYLE_GUIDE.md exists | FAIL | docs/STYLE_GUIDE.md is not present | — | Create docs/STYLE_GUIDE.md and name it from the instruction file so writers have one set of authoring rules. |
| `DOC-03` | artefacts/ exists and is ignored | FAIL | artefacts/ present but not matched by any ignore rule | `artefacts/.gitignore`<br>`artefacts/Misc.txt`<br>`artefacts/refactoring-plan.md` | Add `artefacts/` to .gitignore so scratch documents cannot be committed and agents do not read them as source of truth. |
| `SEC-03` | Ignore patterns cover secret shapes | FAIL | Missing: dotenv, dotenv variant, ssh private key, PEM, key, PKCS#12, PFX, keystore, certificate (.crt), certificate (.cer), AWS credentials. | `.gitignore` (node_modules)<br>`.gitignore` (dist)<br>`.gitignore` (build)<br>`.gitignore` (environments)<br>`.gitignore` (coverage)<br>`.gitignore` (.jest-cache)<br>`.gitignore` (.DS_Store)<br>`.gitignore` (.vscode) | Add the missing shapes to .gitignore — for example `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`, `id_rsa*`, `*.crt`, `*.cer`, `.aws/*`. |
| `TOOL-03` | Type checker configured | PARTIAL | type checker configured but not strict: tsconfig.json:strict | `tsconfig.json:strict` | Turn on strict mode (tsconfig `strict: true`, mypy `strict = true`, pyright `typeCheckingMode: "strict"`) so the checker's findings are trustworthy. |
| `TOOL-04` | Dependency / security scan verb | FAIL | no verb runs a dependency audit | `package.json` | Add a dependency-audit verb (npm audit, pip-audit, osv-scanner, cargo audit, govulncheck, snyk). |
| `TOOL-05` | Local hook chain active | FAIL | no hook chain configured | `package.json` | Adopt a hook manager (pre-commit, lefthook, husky) and wire it so checks run before a commit rather than only in CI. |
| `TST-04` | Fast path documented | FAIL | no single-test/subset invocation in fenced shell blocks (scope: AGENTS.md) | `AGENTS.md` | Document a fast path (for example `pytest -k <name>`, `npm test -- <name>`, or `go test -run <name>`) in a fenced shell block. |

## Findings — Cosmetic

| Check | Title | Verdict | Specifics | Evidence | Fix |
|---|---|:--:|---|---|---|
| `AGT-08` | No competing instruction files, and the reach matrix is stated | PARTIAL | 20/28 harnesses reached; unreached: Aider, Amazon Q Developer, Anthropic Claude Code, Continue, Google Gemini CLI, Qwen Code, Replit Agent, Void. | — | Either state the supported harnesses in AGENTS.md, or add the vendor pointer files for the harnesses in use. |
| `DOC-04` | ADR directory and index | FAIL | no ADR directory | — | Add docs/architecture/adrs/ with NNNN-short-title.md files and a README index that lists them. |
| `HYG-01` | README present and non-placeholder | FAIL | no README at the repository root | — | Add a root README that says what the project is, how to run it, and how to contribute. |
| `HYG-02` | CODEOWNERS present | FAIL | no CODEOWNERS file | — | Add .github/CODEOWNERS mapping paths to owners so review routing is machine-readable. |
| `HYG-03` | Pull-request template present | FAIL | no pull-request template | — | Add .github/pull_request_template.md describing what a good change records. |
| `HYG-04` | Issue templates present | FAIL | no issue templates | — | Add at least one file under .github/ISSUE_TEMPLATE/ (a bug report and a feature request are a good start). |
| `HYG-05` | CONTRIBUTING present | FAIL | no CONTRIBUTING document | — | Add CONTRIBUTING.md covering setup, the gate, and the review flow. |
| `HYG-06` | SECURITY present | FAIL | no SECURITY document | — | Add SECURITY.md with a private disclosure channel and a response expectation. |
| `HYG-07` | CHANGELOG present and recent | FAIL | no CHANGELOG document | — | Add CHANGELOG.md and record notable changes under a version heading. |
| `HYG-08` | Release process documented | FAIL | no release document | — | Add docs/releasing.md (or RELEASE.md) describing how a version is cut and published. |
| `HYG-09` | Dependency update automation configured | FAIL | no dependency update automation | — | Add .github/dependabot.yml (or renovate.json) with an update schedule. |
| `HYG-10` | License present | FAIL | no license file at the repository root | — | Add a LICENSE file; choose one deliberately rather than defaulting to all rights reserved. |
| `NAV-04` | Architecture orientation artifact | FAIL | no architecture orientation artifact | — | Add a short architecture page (with a diagram) so an agent can orient before it explores. |
| `TOOL-06` | Commit convention enforced | FAIL | no commit-message rule | `package.json` | Add a commitlint config or a commit-msg hook so commit messages follow one convention. |

## Appendix — full check results

All 69 checks in the catalogue, grouped by pack, including the 21 passes and 6 unknowns the findings tables omit. `68` of `69` applicable checks are implemented in this ruleset; `54` are scoreable.

### IDX

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `IDX-01` | codebase-memory-mcp registered for this repository | BLOCKER | A | PASS | implemented | codebase-memory-mcp registered in: /home/kc/.config/opencode/opencode.jsonc (user) |
| `IDX-02` | An index exists for this checkout | BLOCKER | A | PASS | implemented | index store /home/kc/.cache/codebase-memory-mcp contains a project rooted at /home/kc/Projects/UDAN/Digital-Assistant-SDK |
| `IDX-03` | Index freshness | DEGRADER | C | UNKNOWN | implemented | index freshness is a Tier-C probe; re-run with --run-gates to compare the indexed revision against HEAD |

### AGT

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `AGT-01` | Instruction file present, canonical, and non-trivial | BLOCKER | A | PASS | implemented | — |
| `AGT-02` | Component coverage by instruction files | DEGRADER | A | PASS | implemented | single-root repository: no component-level instruction files required |
| `AGT-03` | Documentation contract named | DEGRADER | B | FAIL | implemented | does not name docs/, docs/STYLE_GUIDE.md, artefacts/ |
| `AGT-04` | Definition of done stated | DEGRADER | B | FAIL | implemented | no definition-of-done sentence ties a documentation trigger to the same change set |
| `AGT-05` | Six verbs named | DEGRADER | B | FAIL | implemented | not named: format:check, security; not resolved: format:check, typecheck, check, security |
| `AGT-06` | Architectural boundaries declared | DEGRADER | B | PASS | implemented | 3 boundary rules reference real paths |
| `AGT-07` | Do-not-do / deny rules present | DEGRADER | B | FAIL | implemented | no prohibitions section |
| `AGT-08` | No competing instruction files, and the reach matrix is stated | DEGRADER | B | PARTIAL | implemented | 20/28 harnesses reached |
| `AGT-09` | Branch and release boundary declared | DEGRADER | B | PARTIAL | implemented | the branch model is stated but nothing says whether an agent may tag or release |
| `AGT-10` | Instruction indirection resolved | DEGRADER | B | PASS | implemented | — |

### DOC

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `DOC-01` | docs/ exists | DEGRADER | A | FAIL | implemented | no docs/ directory |
| `DOC-02` | docs/STYLE_GUIDE.md exists | DEGRADER | A | FAIL | implemented | docs/STYLE_GUIDE.md is not present |
| `DOC-03` | artefacts/ exists and is ignored | DEGRADER | B | FAIL | implemented | artefacts/ present but not matched by any ignore rule |
| `DOC-04` | ADR directory and index | COSMETIC | A | FAIL | implemented | no ADR directory |

### CMD

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `CMD-01` | Six verbs resolvable on one runner | BLOCKER | B | FAIL | implemented | format -> package.json; format:check -> missing; lint -> package.json; typecheck -> missing; test -> package.json; check -> missing; security -> missing |
| `CMD-02` | check composes the read-only verbs | BLOCKER | B | FAIL | implemented | the check verb is not defined on any runner |
| `CMD-03` | No divergent second definition | DEGRADER | B | PASS | implemented | no runner defines check, so there is nothing to diverge |
| `CMD-04` | Write verbs separated from read-only verbs | DEGRADER | B | PASS | implemented | no read-only verb invokes a write verb |

### TOOL

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `TOOL-01` | Formatter configured | DEGRADER | B | PASS | implemented | formatter .prettierrc.js, package.json prettier + package.json format verb |
| `TOOL-02` | Linter configured | DEGRADER | B | PASS | implemented | linter .eslintrc.js + package.json lint verb |
| `TOOL-03` | Type checker configured | DEGRADER | A | PARTIAL | implemented | type checker configured but not strict: tsconfig.json:strict |
| `TOOL-04` | Dependency / security scan verb | DEGRADER | A | FAIL | implemented | no verb runs a dependency audit |
| `TOOL-05` | Local hook chain active | DEGRADER | B | FAIL | implemented | no hook chain configured |
| `TOOL-06` | Commit convention enforced | COSMETIC | A | FAIL | implemented | no commit-message rule |

### CI

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `CI-01` | Pipeline present, triggered on PRs | BLOCKER | B | FAIL | implemented | no CI workflow file (detected providers: none) |
| `CI-02` | Local↔CI parity | BLOCKER | B | PASS | implemented | CI verbs: none; local read-only verbs not exercised: lint, test |
| `CI-03` | CI-only steps flagged | DEGRADER | B | PASS | implemented | no CI-only steps |

### BASE

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `BASE-01` | Baseline artifact exists | DEGRADER | A | PARTIAL | implemented | quality tooling is configured but no baseline artifact is committed: .eslintrc.js, package.json:lint |
| `BASE-02` | Current violation counts measured | DEGRADER | B | PARTIAL | implemented | counting surface present but no committed count/budget: .eslintrc.js, package.json:lint; method: static configuration scan; the target's own tools are never run |
| `BASE-03` | No-new-violations mechanism | DEGRADER | B | PARTIAL | implemented | no ratchet and no baseline yet, so there is nothing to compare against |
| `BASE-04` | Coverage floor configured | DEGRADER | A | FAIL | implemented | no coverage threshold configured |

### CON

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `CON-01` | Allow/deny artifact present | BLOCKER | B | UNKNOWN | blocked | blocked: the framework defines no artifact contract for this deliverable, so it carries weight 0 in v1 (see CON-01) |
| `CON-02` | Test directories protected | BLOCKER | B | UNKNOWN | implemented | no constraint file protects the test directories (src/services/__tests__/, src/store/middleware/__tests__/, src/store/slices/__tests__/, src/store/utils/__tests__/, src/util/__tests__/, src/util/browser/__tests__/, src/util/error/__tests__/, src/util/headers/__tests__/ (+9 more)), and no ignore rule or CI guard does either |
| `CON-03` | artefacts/ excluded from index and agent reads | DEGRADER | B | FAIL | implemented | artefacts/ present but matched by no ignore rule |
| `CON-04` | Draft allow/deny emitted | COSMETIC | — | UNKNOWN | implemented | draft not emitted; pass --emit-baseline to write constraints.draft.yaml beside the report |

### EXEC

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `EXEC-01` | Toolchain pinned / wrapper committed | BLOCKER | A | FAIL | implemented | unpinned: node |
| `EXEC-02` | Lockfile committed and consistent | BLOCKER | B | FAIL | implemented | — |
| `EXEC-03` | Non-interactive setup path | BLOCKER | A | FAIL | implemented | no setup path found |
| `EXEC-04` | Env-var inventory complete | BLOCKER | B | FAIL | implemented | 2 referenced key(s) are absent from any committed example file: UDA_LOG_LEVEL, UDA_LOG_LEVELN |
| `EXEC-05` | No generated artifacts committed in-tree | DEGRADER | B | PASS | implemented | no tracked generated or vendored paths |
| `EXEC-06` | Documented commands resolve | DEGRADER | B | PASS | implemented | no fenced shell commands documented |
| `EXEC-07` | No competing configs for one concern | DEGRADER | B | PASS | implemented | format: .prettierrc.js; lint: .eslintrc.js; test: jest.config.ts; types: tsconfig.json |

### TST

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `TST-01` | Test verb exists, suite non-empty | BLOCKER | A | PASS | implemented | test verb on package.json (jest); 103 test file(s) |
| `TST-02` | Suite status known | DEGRADER | C | UNKNOWN | implemented | probe not run: probes disabled (pass --run-gates) |
| `TST-03` | Skip / xfail census | DEGRADER | B | PASS | implemented | skip/xfail census across 103 test file(s): no markers; total 0 |
| `TST-04` | Fast path documented | DEGRADER | B | FAIL | implemented | no single-test/subset invocation in fenced shell blocks (scope: AGENTS.md) |
| `TST-05` | Coverage configuration present | COSMETIC | A | PASS | implemented | coverage configured: package.json script |

### NAV

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `NAV-01` | Declared component boundaries | DEGRADER | A | PASS | implemented | single-root repository declares package.json |
| `NAV-02` | Obvious entry points | DEGRADER | B | PASS | implemented | entry point(s): package.json:main=./dist/index.cjs.js, package.json:exports, src/index.ts |
| `NAV-03` | Structural red flags | COSMETIC | B | PASS | implemented | oversized(>524288 B): 0; catch-all dirs(>50 files): 0; binaries: 0; minified: 0 |
| `NAV-04` | Architecture orientation artifact | COSMETIC | A | FAIL | implemented | no architecture orientation artifact |
| `NAV-05` | Public-symbol documentation coverage | COSMETIC | B | PARTIAL | implemented | 161/220 public symbols documented (73%); method: typescript: exported declarations |

### SEC

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `SEC-01` | .env untracked and ignored | BLOCKER | B | PARTIAL | implemented | no tracked .env, but ignore rules miss dotenv, dotenv variant |
| `SEC-02` | No key-shaped strings in tracked files | BLOCKER | B | FAIL | implemented | 16 credential-shaped line(s) across 10 file(s) in tracked text files |
| `SEC-03` | Ignore patterns cover secret shapes | DEGRADER | B | FAIL | implemented | no secret shapes covered; missing: dotenv, dotenv variant, ssh private key, PEM, key, PKCS#12, PFX, keystore, certificate (.crt), certificate (.cer), AWS credentials |

### HYG

| ID | Title | Severity | Tier | Verdict | Status | Detail |
|---|---|---|:--:|:--:|---|---|
| `HYG-01` | README present and non-placeholder | COSMETIC | A | FAIL | implemented | no README at the repository root |
| `HYG-02` | CODEOWNERS present | COSMETIC | A | FAIL | implemented | no CODEOWNERS file |
| `HYG-03` | Pull-request template present | COSMETIC | A | FAIL | implemented | no pull-request template |
| `HYG-04` | Issue templates present | COSMETIC | A | FAIL | implemented | no issue templates |
| `HYG-05` | CONTRIBUTING present | COSMETIC | A | FAIL | implemented | no CONTRIBUTING document |
| `HYG-06` | SECURITY present | COSMETIC | A | FAIL | implemented | no SECURITY document |
| `HYG-07` | CHANGELOG present and recent | COSMETIC | A | FAIL | implemented | no CHANGELOG document |
| `HYG-08` | Release process documented | COSMETIC | A | FAIL | implemented | no release document |
| `HYG-09` | Dependency update automation configured | COSMETIC | A | FAIL | implemented | no dependency update automation |
| `HYG-10` | License present | COSMETIC | A | FAIL | implemented | no license file at the repository root |
| `HYG-11` | Branch protection declared as code | COSMETIC | B | UNKNOWN | implemented | no CI provider recognised; whether branch protection can be declared as code is provider-dependent |

## Structural context

### Components

Single-root repository — no component declarations found.

### Scan coverage

| Metric | Value |
|---|---|
| Files inspected | 259 |
| Files skipped | 1 |
| Traversal truncated | no |
| Ecosystems | node |
| Package managers | — |
| Test frameworks | jest |
| CI providers | — |
| Hook managers | — |

### Probes

| Verb | Command | State | Duration | Redactions | Timed out | Output |
|---|---|---|--:|--:|:--:|---|
| `test` | `jest` | refused: probes disabled (pass --run-gates) | 0.0s | 0 | no | — |

---

Docs: `docs/architecture/README.md` · check catalogue: `docs/architecture/contributor-deep-dive/02-check-catalogue.md`
