# AGENTS.md

This repository is the minimal governed fixture for the DOC and NAV checks. It exists so the test
suite can prove that a small repository can satisfy the documentation contract and the navigation
signals without a large amount of scaffolding.

## Documentation

Permanent knowledge lives in `docs/`. Authoring rules live in `docs/STYLE_GUIDE.md`, which is
canonical. Transient scratch belongs in `artefacts/`, which is off-limits to agents.

## Boundaries

- Application code lives in `src/`.
- Tests live in `tests/`.

## Prohibitions

- Never edit tests to make a failing check pass.
- Never commit generated build output or secrets such as `.env`.
- Never push to the default branch.
