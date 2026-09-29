# AGENTS.md

This file governs how AI coding agents work in this repository. Treat it as authoritative for
agent behaviour here, and review changes to it the same way you review code.

## Commands

Run the project's own commands; never invent a new one. Every framework verb is defined on the npm
runner and named here so the instruction and the manifest agree:

- `format` rewrites files in place.
- `format:check` verifies formatting without writing.
- `lint` runs the linter.
- `typecheck` runs the compiler with no emit.
- `test` runs the suite.
- `check` composes the read-only verbs and is the gate.
- `security` runs the dependency audit.

## Prohibitions

- Never weaken or skip a failing test to get green.
- Never commit generated build output.
- Never commit secrets or credentials.
