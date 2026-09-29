# AGENTS.md

Agents must first read and understand the existing conventions (CONVENTIONS.md) before making any change to this repository.

## Architecture and boundaries

- Application code lives under `src/` and must not import test-only helpers.
- Tests live under `tests/` and must not be weakened to make a build go green.

## Prohibitions

- Never weaken or skip a failing test to get green.
- Never commit generated build output.
- Never commit secrets or credentials.

## Branches and releases

- `main` is production and `dev` is active development; features branch from `dev`.
