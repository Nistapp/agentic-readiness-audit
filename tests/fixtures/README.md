# Test fixtures

One directory per check id, each a **minimal repository that fails exactly that check and nothing else**.
The catalogue's § Adding a Check makes this a merge requirement: no fixture, no check.

Current state: the fixture matrix is complete and consolidated by `../test_fixture_matrix.py`, which
carries one explicit expected verdict per fixture and asserts the positive fixtures collectively pass
every scoreable check. The `AGT` content-contract checks (`AGT-03`, `04`, `06`, `07`, `09`) and
`AGT-05` are exercised by `../test_agt_pack.py` and `../test_cmd_pack.py`; the earlier `AGT` checks
(`01`, `02`, `08`, `10`) now have their own fixtures below. The `EXEC` checks (`EXEC-01`…`07`) are
exercised by `../test_exec_pack.py`; the `CMD` checks (`CMD-01`…`04`) by `../test_cmd_pack.py`; and
the `SEC` checks (`SEC-01`…`03`) by `../test_sec_pack.py`, against the fixtures below. The `DOC` and
`NAV` checks (`DOC-01`…`04`, `NAV-01`…`05`) are exercised by `../test_doc_nav_pack.py`. The `TOOL`
checks (`TOOL-01`…`06`) are exercised by `../test_tool_pack.py`; the `CI` checks (`CI-01`…`03`) by
`../test_ci_pack.py`; the `TST` checks (`TST-01`…`05`) by `../test_tst_pack.py`; the `BASE` checks
(`BASE-01`…`04`) by `../test_base_pack.py`, with the ratchet exercised end to end by
`../test_ratchet.py`; the `CON` checks (`CON-02`, `CON-03`) plus the `CON-04` emitter by
`../test_con_pack.py`; and the informational `HYG` checks (`HYG-01`…`11`) by
`../test_hyg_pack.py`.

## Convention

```
fixtures/
  agt-01-missing/            no instruction file at all           -> AGT-01 FAIL
  agt-01-stub/               AGENTS.md present, 80 characters     -> AGT-01 FAIL (stub)
  agt-01-mis-cased/          agents.md only                       -> AGT-01 FAIL (case)
  agt-01-shadowed/           AGENTS.md + AGENTS.override.md       -> AGT-01 PARTIAL (override)
  agt-02-uncovered/          two declared workspaces, one AGENTS.md -> AGT-02 PARTIAL
  agt-03-incomplete/         docs/ named, no style guide or scratch contract -> AGT-03 PARTIAL
  agt-04-missing/            no definition-of-done section        -> AGT-04 FAIL
  agt-06-thin/               one boundary rule naming a real path -> AGT-06 PARTIAL
  agt-07-missing-deny/       prohibitions cover tests only        -> AGT-07 PARTIAL
  agt-08-competitor/         AGENTS.md + CLAUDE.md                -> AGT-08 FAIL
  agt-09-no-release/         branches stated, no release boundary -> AGT-09 PARTIAL
  agt-10-deferred/           AGENTS.md defers to CONVENTIONS.md   -> AGT-10 FAIL
  agt-05-verbs-named-not-resolved/ AGENTS.md names all verbs, no runner -> AGT-05 PARTIAL
  agt-05-ok/                 all verbs named and resolved on a runner -> AGT-05 PASS
  cmd-01-missing-verb/       six verbs on npm, security missing    -> CMD-01 FAIL
  cmd-02-weak-check/         check runs only lint, not the gate   -> CMD-02 FAIL
  cmd-03-divergent/          Makefile composes its own check      -> CMD-03 FAIL
  cmd-04-write-in-check/     check invokes the writing format verb -> CMD-04 FAIL
  cmd-ok-npm/                all seven verbs as npm scripts        -> CMD-01…04 PASS
  cmd-ok-make/               all seven verbs as Makefile targets   -> CMD-01…04 PASS
  sec-01-tracked-env/        tracked .env, comprehensive ignore (needs git) -> SEC-01 FAIL
  sec-02-key-shaped/         synthetic sk- value in a source file (needs git) -> SEC-02 FAIL
  sec-03-thin-ignore/        ignore rules cover no secret shapes   -> SEC-03 FAIL
  sec-01-ok/                 .env present but untracked + ignored (needs git) -> SEC-01…03 PASS
  exec-01-unpinned/          node project, no toolchain pin       -> EXEC-01 FAIL
  exec-02-no-lockfile/       node project, no lockfile (needs git) -> EXEC-02 FAIL
  exec-03-no-setup/          node project, no setup path          -> EXEC-03 FAIL
  exec-04-missing-env/       source reads an undeclared env var    -> EXEC-04 FAIL
  exec-05-generated/         tracked generated file, no header (needs git) -> EXEC-05 FAIL
  exec-06-broken-command/    README runs an npm script that is not declared -> EXEC-06 FAIL
  exec-07-dual-lint/         .eslintrc.json + biome.json compete  -> EXEC-07 FAIL
  exec-ok/                   the smallest node repository passing every EXEC check (needs git)
  doc-01-empty/              docs/ present, no markdown page      -> DOC-01 PARTIAL
  doc-02-no-style-guide/     docs/ present, no STYLE_GUIDE.md     -> DOC-02 FAIL
  doc-03-tracked-artefacts/  artefacts/ ignored but force-added (needs git) -> DOC-03 FAIL
  doc-04-adr-unindexed/      an ADR with no index                 -> DOC-04 PARTIAL
  nav-01-no-manifest/        source but no build manifest         -> NAV-01 UNKNOWN
  nav-02-no-entry/           node manifest with no entry point    -> NAV-02 FAIL
  nav-03-red-flags/          a checked-in binary and a minified asset -> NAV-03 PARTIAL
  doc-nav-ok/                the smallest repository passing every scored DOC/NAV check
  tool-01-no-formatter/      node project, no formatter config or verb -> TOOL-01 FAIL
  tool-02-no-linter/         node project, no linter config or verb  -> TOOL-02 FAIL
  tool-03-nonstrict-ts/      tsconfig.json strict: false             -> TOOL-03 PARTIAL
  tool-04-no-audit-verb/     node project, no dependency-audit verb -> TOOL-04 FAIL
  tool-05-unwired-hooks/     .husky/ present but never referenced   -> TOOL-05 PARTIAL
  tool-06-no-commit-rule/    wired hooks, no commit-message rule    -> TOOL-06 FAIL
  tool-ok-node/              the smallest node repository passing every TOOL check
  ci-01-no-pr-trigger/       workflow without a pull-request trigger -> CI-01 PARTIAL
  ci-02-parity-break/        CI runs a framework verb with no local script -> CI-02 FAIL
  ci-03-ci-only-step/        CI runs `npm run deploy` with no local script -> CI-03 FAIL
  ci-ok-gh/                  a PR-triggered GitHub workflow calling the local verbs
  tst-01-no-suite/           test files but no resolvable test verb -> TST-01 PARTIAL
  tst-03-skip-markers/       a suite with skip/todo markers -> TST-03 PASS (non-zero census)
  tst-04-no-fastpath/        docs show the full suite only -> TST-04 FAIL
  tst-05-no-coverage/        suite and fast path, no coverage config -> TST-05 FAIL
  base-01-no-baseline/       tooling but no committed baseline       -> BASE-01 FAIL
  base-02-no-count/          baseline + tooling, no numeric budget    -> BASE-02 PARTIAL
  base-03-no-ratchet/        baseline committed but never compared    -> BASE-03 FAIL
  base-04-no-coverage-floor/ ratchet present, no coverage threshold   -> BASE-04 FAIL
  base-ok/                   baseline + budget + ratchet + floor      -> BASE-01…04 PASS
  con-02-unprotected-tests/  a constraint file that omits test dirs   -> CON-02 FAIL
  con-02-protected/          a denylist naming the test directory      -> CON-02 PASS
  con-03-artefacts-not-ignored/ artefacts/ present, no ignore rule      -> CON-03 FAIL
  hyg-01-placeholder-readme/ README is a TODO stub                      -> HYG-01 FAIL
  hyg-10-no-license/         real README, no LICENSE at the root         -> HYG-10 FAIL
  hyg-minimal/               no hygiene artifacts at all                 -> HYG-01…10 FAIL, HYG-11 UNKNOWN
  governed-minimal/          the smallest repository that passes every implemented AGT content check, plus its cross-pack neighbours exercised by the matrix test
```

An empty directory cannot be checked in — git does not track them — so the empty-repository case is
built at runtime by `test_empty_directory_reports_nothing_and_does_not_crash`.

Two rules for a fixture:

1. **One defect per fixture.** A fixture that fails three checks cannot tell you which rule broke.
2. **Checked in, not generated** — except the positive fixture below, which must not be a copy.

## The positive fixture

`python-agentic-bootstrap` is the positive fixture: a freshly scaffolded project is Phase-1-complete by
construction, so it must score 1.0 with zero blockers. Generate it in the test run rather than vendoring a copy —
a vendored copy stops being evidence the moment the scaffolder changes.

> [!IMPORTANT]
> If a scaffolded project ever fails this audit, one of the two tools is wrong. That is a defect worth catching
> immediately, not a false positive to be tuned away. See
> [Scan Engine & Tiering](../../docs/architecture/contributor-deep-dive/01-scan-engine-and-tiering.md) § 9.
