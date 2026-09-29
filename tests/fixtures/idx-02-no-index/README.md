# idx-02-no-index

A minimal repository that *does* register `codebase-memory-mcp` (project-level `opencode.json`) but
has no index store in the environment the test supplies. `IDX-02` must be `UNKNOWN` when the store
cannot be located, and `FAIL`/`PASS` against constructed stores — never a machine-specific verdict.
