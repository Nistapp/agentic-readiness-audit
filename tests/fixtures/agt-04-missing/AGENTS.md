# AGENTS.md

This file governs how AI coding agents work in this repository. Treat it as authoritative for agent
behaviour here, and review changes to it the same way you review code.

## 1. Architecture and boundaries

- Application code lives under `src/` and must not import test-only helpers.
- Tests live under `tests/` and must not be weakened to make a build go green.

## 2. Documentation contract

- `docs/` is the canonical home for permanent knowledge.
- `docs/STYLE_GUIDE.md` is the canonical authoring guide; link to it rather than restating it.
- `artefacts/` holds transient scratch documents and is not a source of truth.

## 3. Prohibitions

- Never weaken or skip a failing test to get green.
- Never commit generated build output.
- Never rewrite or force-push the default branch.
- Never commit secrets or credentials.

## 4. Branches and releases

- `main` is production and `dev` is active development; features branch from `dev`.
- Agents may open feature branches but must not tag or publish a release.
