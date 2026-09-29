# Agents

This file governs how AI coding agents work in this repository. Treat it as authoritative for
agent behaviour here, and review changes to it the same way you review code.

## Architecture and boundaries

- Application code lives under `src/` and must not import test-only helpers.
- Tests live under `tests/` and must not be weakened to make a build go green.

## Prohibitions

- Never weaken or skip a failing test to get green.
- Never commit generated build output.
- Never commit secrets or credentials.

## Branches and releases

- `main` is production and `dev` is active development; features branch from `dev`.
- Agents may open feature branches but must not tag or publish a release.
