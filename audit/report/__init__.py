"""Stage S11 — report writers.

The report is the product. Two properties matter more than formatting:

* **The score is never presented alone.** The blockers and the unattested list travel with it
  (docs: The Readiness Model § 6), because a number without its caveats is the failure mode this
  design exists to prevent.
* **The report says which checks were not implemented.** A scan that silently omits half the
  catalogue looks identical to a scan that found nothing wrong.

Default output path is the current working directory. If the CWD is inside the target, the writer
refuses unless ``--out`` is given: a scanner that drops a file into the repository it is auditing
has broken the read-only invariant (ADR-0002).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audit.evaluate import AuditResult


class ReportWriteError(Exception):
    """Raised when the report cannot be written where the operator asked."""


def _resolve_out(args: argparse.Namespace, target_path: Path) -> Path:
    if args.out:
        out = Path(args.out).expanduser()
        if out.is_dir():
            return out / "audit-report.json"
        return out

    cwd = Path.cwd().resolve()
    try:
        cwd.relative_to(target_path)
    except ValueError:
        return cwd / "audit-report.json"
    raise ReportWriteError(
        "refusing to write the report inside the target — run from elsewhere or pass --out"
    )


def resolve_out_path(args: argparse.Namespace, target_path: Path) -> Path:
    """The report path the run will write to, resolved before checks run.

    The ``CON-04`` emitter needs the same ``--out`` location the report uses, so resolution is
    exposed here rather than duplicated. Raises ``ReportWriteError`` under the same condition
    ``emit`` would.
    """
    return _resolve_out(args, target_path)


def emit(result: AuditResult, *, args: argparse.Namespace) -> None:
    from audit.report.json_writer import render_json
    from audit.report.md_writer import render_markdown

    payload: dict | str | None = None
    if args.format in ("json", "both"):
        payload = render_json(result, args)
    markdown = render_markdown(result, args) if args.format in ("md", "both") else None

    out_path = _resolve_out(args, result.target.path)
    if out_path.exists() and not args.force and args.format != "md":
        raise ReportWriteError(f"{out_path} exists — pass --force to overwrite")

    if markdown is not None:
        if args.format == "md" or markdown and not args.out:
            print(markdown)

    if payload is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nreport written: {out_path}", file=sys.stderr)
        if args.format == "both" and args.out:
            md_path = out_path.with_suffix(".md")
            md_path.write_text(markdown or "", encoding="utf-8")
            print(f"report written: {md_path}", file=sys.stderr)
