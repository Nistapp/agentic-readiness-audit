# 3. Why These Checks

> **Target Audience:** CTOs, engineering leads, architects, and anyone arguing about a finding.
> **Key Goal:** State the failure mode behind every check family, so a finding can be judged on its consequence rather than its authority.
> **Status:** Published — Page 3 of the User Overview; see [the index](../README.md).

---

## 1. The Selection Rule

A check earns its place in this audit only if its absence **changes what an agent can do, verify, or safely
touch**. "It is a good practice" is not sufficient; "a well-run team does it" is not sufficient. The failure
mode must be concrete and attributable to the agent's ability to work.

This is why the report is a *short* list compared to a general code-quality tool, and why the informational set
is kept numberless: a scored item is a claim that its absence costs agent effectiveness.

---

## 2. Discovery and Index (`IDX`)

An agent that cannot query structure reads files and burns context. Every downstream phase of the framework
depends on `codebase-memory-mcp`.

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `IDX-01` MCP registration | The index must be reachable from the harness the team actually uses | Agents fall back to `grep` and whole-file reads; token cost rises, accuracy falls |
| `IDX-02` Index exists for this path | An index of a different checkout is worse than none — it is confidently wrong | Agent reasons over structure that no longer exists |
| `IDX-03` Index freshness vs `HEAD` | Stale graph = stale context | Agent edits based on symbols that have moved or been deleted |

---

## 3. Agent Governance (`AGT`)

`AGENTS.md` is the only artifact an agent is guaranteed to read. Everything the team knows and has not written
down is invisible.

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `AGT-01` Root `AGENTS.md` | The entry point for every harness | Agent infers conventions from the code it happens to read first |
| `AGT-02` Per-component coverage | Monorepos have different rules per component | Agent applies one component's conventions to another |
| `AGT-03` Documentation contract named | Agents must know where permanent truth lives and what is off-limits | Agent treats scratch notes as architecture |
| `AGT-04` Definition of done stated | Docs must change in the same change set as the code | Specs drift within days |
| `AGT-05` Six verbs named | The agent must know the sanctioned verification path | Agent invents `npx vitest`; local and CI diverge |
| `AGT-06` Boundaries declared | Architecture rules must be stated, not inferred | Spaghetti edits across module boundaries |
| `AGT-07` Do-not-do / deny rules | Explicit prohibitions work; implicit ones do not | Agent weakens tests, edits generated files, commits to main |
| `AGT-08` No competing instruction files | `AGENTS.md` + `CLAUDE.md` + `.cursorrules` disagreeing is obeyed as ambiguity | Inconsistent behaviour across harnesses, untraceable |
| `AGT-09` Branch and release boundary | Agents must know whether they may tag, release, or push | Agent triggers a release it had no authority to cut |

---

## 4. Documentation Contract (`DOC`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `DOC-01` `docs/` exists | The declared home for permanent documentation must exist on day one | Documentation scatters; nothing is canonical |
| `DOC-02` `STYLE_GUIDE.md` exists | Agents need authoring rules they can cite instead of restating | Rules get restated per page and drift |
| `DOC-03` `artefacts/` exists and is ignored | Transient scratch must be separable and off-limits | Agent reads WIP notes as current requirements |
| `DOC-04` ADR directory and index | Architectural decisions need a location and a registry | Rationale lives in chat and pull requests; agents re-litigate settled decisions |

---

## 5. Command Surface (`CMD`)

One command surface, three consumers. This family is the core of Phase 1 and the most common brownfield failure.

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `CMD-01` Six verbs, one runner | The verbs are the contract; the runner is a local choice | No shared vocabulary for "how do I verify this" |
| `CMD-02` `check` composes the read-only verbs | A single pre-merge gate must exist and be the same one everywhere | Different people gate on different subsets |
| `CMD-03` No divergent second definition | A Makefile target that shells out is fine; a *competing* gate is not | Two answers to "is this green", silently |
| `CMD-04` Write verbs separated from read-only verbs | An agent must be able to verify without mutating | Agent runs a formatter as a "check" and dirties the tree |

---

## 6. Tooling (`TOOL`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `TOOL-01` Formatter configured | Formatting becomes free and non-negotiable | Every diff mixes style with substance; review noise |
| `TOOL-02` Linter configured | Catches classes of defect before tests exist | Agent regressions that tests cannot see |
| `TOOL-03` Type checker configured | The cheapest correctness gate there is | Interface drift discovered at runtime |
| `TOOL-04` Dependency/security scan | Third-party risk, and agents add dependencies | Vulnerability enters through the agent's own change |
| `TOOL-05` Local hook chain active | Enforcement must exist where the agent works | Rules that live only in CI are rules agents cannot honour |
| `TOOL-06` Commit convention enforced | Release automation reads commit messages | Version bumps and changelogs silently stop working |

---

## 7. CI (`CI`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `CI-01` Pipeline present, triggered on PRs | Verification must be automatic and independent of the author | "I ran the tests" is unverifiable |
| `CI-02` Local↔CI parity | The gate an agent *can* run must be the gate that *decides* | Agent optimises against a weaker local gate; rework at review |
| `CI-03` CI-only steps flagged | A step with no local equivalent is unreachable by an agent | Agent cannot reproduce the failure it is being failed on |

---

## 8. Baselines and the Ratchet (`BASE`)

Brownfield repositories arrive with debt. The framework's answer is not "fix it" but "freeze it and do not add
to it".

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `BASE-01` Baseline artifact | Instrumentation must land before gates can be enforced | Gates cannot be turned on without mass failure |
| `BASE-02` Current violation counts measured | The baseline must be a number, not an impression | No way to tell whether debt is growing |
| `BASE-03` No-new-violations mechanism | The policy must be executable, not aspirational | Every change adds a little debt |
| `BASE-04` Coverage floor | The most common form of the ratchet | Coverage decays invisibly |

---

## 9. Constraints (`CON`)

Constraint Engineering is what bounds the blast radius. Phase 1 establishes the initial lists.

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `CON-01` Allow/deny artifact | Agents cannot respect boundaries that are only in someone's head | Unbounded edits |
| `CON-02` Test directories protected | Tests are the safety net; an agent that may edit them is not gated | Agent makes the failure disappear instead of fixing it |
| `CON-03` `artefacts/` excluded from the index | Scratch must not become context | WIP notes pollute every agent session |
| `CON-04` Draft list emitted | The scan knows what is dangerous in *this* repository | Every adoption starts from a generic template that fits nobody |

---

## 10. Execution Determinism (`EXEC`)

Where brownfield repositories fail hardest, and where the framework's Phase 1 is thinnest.

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `EXEC-01` Toolchain pinned / wrapper committed | The agent's toolchain must be the repository's, not the host's | Gate passes locally, fails in CI; unreproducible builds |
| `EXEC-02` Lockfile committed and consistent | Every run must resolve identical dependencies | Non-deterministic installs; "works on my machine" for the agent too |
| `EXEC-03` Non-interactive setup path | Agents cannot answer prompts or provision a database | Agent is blocked before it can run anything |
| `EXEC-04` Env-var inventory complete | Missing variables fail at runtime, mid-task | Agent debugs an environment problem it cannot see |
| `EXEC-05` No generated artifacts committed in-tree | Agents edit files that are regenerated | Work silently discarded after review |
| `EXEC-06` Documented commands resolve | Agents obey written instructions literally | The most expensive brownfield trap there is |
| `EXEC-07` No competing configs for one concern | One question, one authority | Agent picks the config that happens to match the first result |

---

## 11. Tests (`TST`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `TST-01` Test verb exists, suite non-empty | Verification is the single biggest lever on agent output | Every agent change is unverified |
| `TST-02` Suite status known | Whether it is green *today* determines what can be attempted | Agent inherits a red baseline and cannot tell its regressions from yours |
| `TST-03` Skip/xfail census | The fingerprint of tests weakened to reach green | Regressions pass the gate that was supposed to catch them |
| `TST-04` Fast path documented | Agent iteration speed is the workflow | Agent waits 40 minutes per attempt, or stops running tests |
| `TST-05` Coverage configuration | The ratchet needs a shape | No floor to hold |

---

## 12. Navigation (`NAV`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `NAV-01` Declared component boundaries | Constraint Engineering needs bounded components | Blast radius cannot be scoped or reviewed |
| `NAV-02` Obvious entry points | Agents must find where execution begins | Agent edits dead code that looks live |
| `NAV-03` Structural red flags | Largest files, `utils/` catch-alls, checked-in binaries | Agents are drawn to the worst places in the codebase |
| `NAV-04` Architecture orientation artifact *(informational)* | Gives the agent a map before it explores | Slower orientation; more redundant exploration |
| `NAV-05` Public-symbol documentation coverage *(informational)* | Phase 2 territory; reported as a signal only | Agent must read bodies to learn signatures |

---

## 13. Security Hygiene (`SEC`)

| Check | Why it matters | Failure mode without it |
|---|---|---|
| `SEC-01` `.env` untracked and ignored | Agent context is transmitted and logged | Credential exposure through the tool added for safety |
| `SEC-02` No key-shaped strings in tracked files | Same, for hardcoded values | Secrets in transcripts and reports |
| `SEC-03` Ignore patterns cover secret shapes | The guard must exist before the accident | A single careless commit becomes permanent history |

---

## 14. Hygiene (Informational, Never Scored)

README, CODEOWNERS, PR and issue templates, CONTRIBUTING, SECURITY, CHANGELOG, release process, dependency
updates, license, branch protection. These are how a *team* operates. They are reported because a client
engagement needs the whole picture, and left numberless because an agent does not read any of them before
deciding what to edit.

One exception bridges the two: where CODEOWNERS names paths that the audit would also place on a deny list,
that consistency is reported as a note — review routing and scope lockdown should not disagree.

---

## Related Pages

- Previous: [2. The Readiness Model](02-the-readiness-model.md)
- Implementation detail: [Check Catalogue](../contributor-deep-dive/02-check-catalogue.md)
- Method: [Phased Approach — Phase 1](https://github.com/Nistapp/codebase-agentic-readiness-framework/blob/main/brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)
