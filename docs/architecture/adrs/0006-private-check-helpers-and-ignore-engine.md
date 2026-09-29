# 0006. Private Check Helpers and the Ignore Engine

* **Status:** Accepted
* **Date:** 2026-09-28
* **Last reviewed:** 2026-09-28
* **Deciders:** [@nistapp]

---

## Context

ADR-0005 fixed the package layout: one module per pipeline stage under `audit/`, one module per check
family under `audit/rules/checks/`. That works for behaviour that belongs to a single stage or a
single pack. Two cross-cutting concerns do not fit it:

1. **Tracked-file and ignore certainty.** `SEC-01`, `SEC-03`, `DOC-03`, `EXEC-05` and `CON-03` all
   need to know which files git tracks and whether an ignore rule covers a path. The only matching
   that existed lived inside `audit/scan.py` as a non-git-aware approximation, and it was not
   reusable without also changing what the walk skips.
2. **Verb resolution and documented commands.** `CMD-01`, `EXEC-06`, `CI-02`, `AGT-05`,
   `TOOL-01/02/04` and `TST-01/04` all ask "what verbs exist, what does each run, and which commands
   does the documentation show?". Answering that per pack guarantees several divergent answers.

Duplicating either concern across packs is the classic path to disagreement: two checks reading the
same manifest by two slightly different rules will one day disagree in the same report.

---

## Decision

**Two internal helper modules, no new pipeline stage and no new rule pack.**

1. **`audit/ignore.py`** owns the git-aware tracked-file accessor and the documented-subset ignore
   matcher. `tracked_files()` returns `None` — never an empty set — when the target is not a
   repository or git fails, so callers degrade to `UNKNOWN` rather than infer. Ignore matching keeps
   the historical behaviour exactly, so `audit/scan.py` continues to walk precisely what it walked
   before; the semantics are a **documented subset** (anchored patterns, negation and `**` are
   approximated; `UNKNOWN`, never `PASS`, when certainty is unavailable).
2. **`audit/rules/checks/_common.py`** is a **private** module holding the shared verb resolver
   (`resolve_verbs`) and fenced-command extractor (`extract_fenced_commands`). It is deliberately
   **absent from `MODULE_NAMES`** in `audit/rules/checks/__init__.py`: the registry must not load it,
   because it defines no `IMPLEMENTATIONS` and is not a pack. Packs import it directly.
3. **These are internal helpers with no public contract and no rule-pack status.** They are not part
   of the CLI, the catalogue, or `ruleset_hash`, and nothing outside `audit/` may depend on them.
   They may be reshaped when real usage in units 03–13 shows which helpers are genuinely shared; a
   thin `_common.py` beats a speculative one.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Duplicate the logic in each pack | Guarantees drift: two checks reading one manifest under two subtly different rules will eventually disagree in one report. |
| Make ignore logic a new pipeline stage (S3.5) | It is not a stage — it is a query over traversal. A stage would couple `scan.py`'s walk to a separately-versioned semantic and risk shifting every existing verdict. |
| Fold the helpers into `audit/stack.py` or `audit/components.py` | Wrong responsibility: stack detection classifies ecosystems, it does not resolve the verbs or read ignore files. |
| Add `_common` to `MODULE_NAMES` so the registry loads it | The registry wires checks to implementations; a module with no `IMPLEMENTATIONS` has no place there, and listing it would imply rule-pack status it does not have. |
| Depend on a gitignore-parsing / YAML / TOML library | Violates the stdlib-only constraint that lets the audit run before the target's toolchain exists (ADR-0005). |
| Make the helpers a public, semver'd API | No external consumer exists; a public contract here would freeze crude, deliberately-partial parsers before they have been shaped by use. |

---

## Consequences

### Positive

* One answer to "what verbs exist?" and one to "does an ignore rule cover this path?", shared by every
  pack that asks, so the answers cannot diverge within a report.
* `tracked_files()` returning `None` makes "git could not answer" a representable state, which keeps
  the `UNKNOWN`-never-`PASS` invariant (ADR-0004 line of reasoning) enforceable at the call site.
* `MODULE_NAMES` keeps meaning "one entry per rule pack", and `--list-checks` is unaffected because
  the helper module adds no checks.

### Negative / Trade-offs

* Two helper modules now exist that ADR-0005's stage/pack map does not name. They are infrastructure,
  not stages or packs, and this ADR is where that distinction is recorded.
* The Taskfile and pyproject readers are deliberately shallow (no YAML/TOML library). They are
  documented as crude and are expected to be refined as implementation units adopt them.
* Because there is no public contract, a helper signature may change without a deprecation path.
  That is intentional for internal code exercised only by this repository's own test suite.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/NNNN-title.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
