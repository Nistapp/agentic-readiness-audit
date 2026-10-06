# 0007. The JSON Report Is the Render Contract; the Markdown Is a Template Over It

* **Status:** Accepted
* **Date:** 2026-09-30
* **Last reviewed:** 2026-09-30
* **Deciders:** [@nistapp]

---

## Context

The audit emits two artifacts from one run: a machine-readable JSON report and a human Markdown page.
They were written by two independent functions (`render_json` and `render_markdown`) that each walked
the in-memory `AuditResult` separately. Nothing forced them to agree, the Markdown carried only prose
findings, and every check's structured facts — the missing verbs, the credential file×line matrix, the
harness reach list — were flattened into one human `detail` string that no renderer could turn into a
table.

Three forces pushed for a change:

1. **The Markdown should evolve quickly.** Formatting is the artifact most likely to be iterated on;
   it should not require touching the verdict engine or every check pack.
2. **The two artifacts must not drift.** A JSON that says one thing and a Markdown that says another
   is worse than either alone.
3. **Specifics must survive.** "Define every verb" is not actionable; "missing `format:check`,
   `typecheck`, `check`, `security`" is.

A naive answer is a separate `.md` template file. That is unavailable: a `.pyz` has no filesystem, so
a shipped data file cannot be read via `Path(__file__)` (ADR-0005 § 5) — the same reason the
instruction-variant table is code.

---

## Decision

**One report dict is the source of truth; both artifacts are rendered from it, and the template is
code.**

1. **Schema v2 is the render contract.** `audit/report/model.py` defines and builds it. `checks[]`
   carries, per check: `id`, `pack`, `title`, `tier`, `severity`, `phase`, `scored`, `status`,
   `verdict`, `summary`, and a typed `data` payload. The old `checks[].detail` string is removed.
2. **Structured payloads, not prose.** `audit/rules/payloads.py` defines frozen, `kind`-discriminated
   dataclasses (`verb_surface`, `credential_matrix`, `secret_shapes`, `env_keys`, `harness_matrix`,
   `ratio`, `counter`, `path_list`, `mapping`). A check emits `summary` (one short sentence) plus an
   optional `Payload`; the JSON carries `data.to_dict()`. The renderer dispatches on `kind` and never
   parses a string.
3. **The template is code.** `audit/report/presentation.py` holds the section order, table columns,
   and all editorial wording (verdict meanings, severity fix windows, unattested meanings). Editorial
   text lives here, never in the JSON.
4. **A generic renderer.** `audit/report/md_render.py` turns any schema-v2 dict into Markdown.
   `render_markdown(report: dict) -> str` can re-render a saved `audit-report.json`; the CLI builds
   one dict and feeds both writers.
5. **The scaffold is deliberately left alone.** `audit/report/` gains a presentation layer and a
   generic engine; the check packs keep their verdict logic. Adding a new derived view is one builder
   plus one template entry.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep two independent writers over `AuditResult` | They can disagree; the Markdown cannot be re-rendered from a saved report; formatting changes touch both paths. |
| A standalone `.md` template file | A `.pyz` has no filesystem; the template must be code or shipped via `importlib.resources`, which ADR-0005 § 5 rejects. |
| A bespoke Mustache/Jinja-style template language | A parser and engine to maintain, third-party or hand-rolled, to solve a problem a data structure already solves. Contradicts ADR-0005's "code, not data" reasoning. |
| Keep `detail` and parse it in the renderer | Prose parsing is brittle, lossy, and re-introduces the coupling the change exists to remove. |
| Carry structured data in a side table keyed by check id | Splits the fact from the check that produced it; a check's evidence would live outside its outcome. |

---

## Consequences

### Positive

* The Markdown is a pure function of the JSON; `render_markdown(report_json)` re-renders any saved
  report, and the two artifacts cannot drift.
* Formatting changes are confined to `presentation.py` and `md_render.py`; the packs and the verdict
  engine are untouched.
* Specifics are typed and complete: `path_list` carries the full list (no `(+9 more)` truncation), and
  `credential_matrix` carries every file×line without recording a value.
* New payload kinds and new table blocks have one obvious home each.

### Negative / Trade-offs

* Every check that wants a dedicated table must populate a payload; checks without one fall back to
  their `summary`. This is incremental work, deliberately not done for every check at once.
* The schema is versioned (`schema_version: "2"`) and `detail` is gone, so any external consumer of
  the v1 JSON must be updated. The project is pre-release, so this was taken now rather than later.
* The template is code, not a document a non-programmer edits. That is the ADR-0005 trade the project
  has already accepted.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
