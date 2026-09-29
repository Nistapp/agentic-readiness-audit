"""Command-line surface (stage S1). Argument parsing and dispatch only — no scan logic.

Exit codes (docs: The Readiness Model § 8):

====  ============================================================
  0   scan completed; no findings at or above the ``--fail-on`` threshold
  1   usage or input error — bad path, unreadable target, malformed rules
  2   findings at or above ``--fail-on``, or a regression against ``--baseline``
====  ============================================================

By default ``--fail-on`` is unset, so the first scan of a legacy repository always exits 0.
Turning this tool into a gate is a deliberate second step, never the default (ADR-0001).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audit import __ruleset_revision__, __version__

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FINDINGS = 2


class AuditUsageError(Exception):
    """Raised for bad input. Callers turn this into EXIT_USAGE, never a traceback."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit",
        description=(
            "Read-only agentic-readiness audit for an existing repository. "
            "Reports; does not gate."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The audit never writes inside <target>, never installs anything, and makes no\n"
            "network request unless a Tier-C probe is explicitly permitted.\n\n"
            "Docs: docs/architecture/README.md"
        ),
    )
    parser.add_argument("target", nargs="?", default=".", help="repository to scan (default: .)")
    parser.add_argument("--phase", type=int, default=1, help="highest framework phase to evaluate (default: 1)")
    parser.add_argument("--format", choices=("json", "md", "both"), default="both", help="report formats")
    parser.add_argument("--out", help="output path or directory; outside the target by default")
    parser.add_argument("--run-gates", action="store_true",
                        help="enable Tier-C probes (executes the target's own commands)")
    parser.add_argument("--allow-probe", action="append", default=[], metavar="VERB",
                        help="permit one probe verb; repeatable (required by --run-gates)")
    parser.add_argument("--timeout", type=int, default=300, metavar="SECONDS", help="per-probe timeout")
    parser.add_argument("--fail-on", choices=("BLOCKER", "DEGRADER", "COSMETIC"),
                        help="exit 2 when a finding at or above this severity exists (default: never)")
    parser.add_argument("--baseline", metavar="REPORT.JSON",
                        help="ratchet: exit 2 only when findings appear that the baseline did not have")
    parser.add_argument("--emit-baseline", action="store_true",
                        help="emit the remediation inputs the scan can derive; writes "
                             "constraints.draft.yaml beside the report (CON-04)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="extra path glob to exclude; repeatable")
    parser.add_argument("--max-files", type=int, default=250_000, help="hard cap on inspected files")
    parser.add_argument("--list-checks", action="store_true", help="print the check catalogue and exit")
    parser.add_argument("--verify-rules", action="store_true",
                        help="resolve every rule pack's framework anchor and exit")
    parser.add_argument("--framework", metavar="PATH",
                        help="local checkout of codebase-agentic-readiness-framework (for --verify-rules)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing report")
    parser.add_argument("--version", action="version", version=f"audit {__version__} (ruleset {__ruleset_revision__})")
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_checks:
        return _list_checks()
    if args.verify_rules:
        return _verify_rules(args.framework)
    if args.run_gates and not args.allow_probe:
        print("audit: --run-gates requires at least one --allow-probe VERB", file=sys.stderr)
        return EXIT_USAGE

    try:
        return _scan(args)
    except AuditUsageError as exc:
        print(f"audit: {exc}", file=sys.stderr)
        return EXIT_USAGE


def _list_checks() -> int:
    from audit.rules.registry import REGISTRY, scoreable

    width = max(len(spec.id) for spec in REGISTRY)
    print(f"{'id'.ljust(width)}  tier  severity   status       title")
    for spec in REGISTRY:
        print(f"{spec.id.ljust(width)}  {spec.tier:<4}  {spec.severity.value:<9}  "
              f"{spec.status:<11}  {spec.title}")
    informational = len(REGISTRY) - len(scoreable())
    print(f"\n{len(REGISTRY)} checks catalogued · {len(scoreable())} scoreable · "
          f"{informational} informational, blocked or emitter-only")
    return EXIT_OK


def _verify_rules(framework: str | None) -> int:
    from audit.rules.registry import REGISTRY, resolve_anchors

    if not framework:
        print("audit: --verify-rules needs --framework <path to codebase-agentic-readiness-framework>",
              file=sys.stderr)
        return EXIT_USAGE
    root = Path(framework).expanduser().resolve()
    if not root.is_dir():
        raise AuditUsageError(f"framework checkout not found: {root}")

    missing = resolve_anchors(REGISTRY, root)
    total = sum(1 for spec in REGISTRY if spec.anchor)
    if missing:
        print(f"audit: {len(missing)} of {total} anchors do not resolve against {root}", file=sys.stderr)
        for spec_id, anchor in missing:
            print(f"  ✗ {spec_id}: {anchor.file} § {anchor.heading!r}", file=sys.stderr)
        return EXIT_USAGE
    print(f"audit: all {total} framework anchors resolve against {root}")
    return EXIT_OK


def _scan(args: argparse.Namespace) -> int:
    """Wire the pipeline stages together. Stages are implemented incrementally."""
    from audit.evaluate import evaluate
    from audit.report import emit, resolve_out_path
    from audit.rules.checks import con
    from audit.scan import build_inventory
    from audit.stack import detect_stack
    from audit.target import resolve_target

    target = resolve_target(Path(args.target))
    inventory = build_inventory(target.path, extra_excludes=tuple(args.exclude), max_files=args.max_files)
    stack = detect_stack(inventory)

    # CON-04's emitter writes beside the report, so it is handed the same resolved --out path the
    # report writer uses. Reset every scan: a long-lived process must not inherit a previous target.
    con.set_emit_target(resolve_out_path(args, target.path) if args.emit_baseline else None)

    result = evaluate(target=target, inventory=inventory, stack=stack, args=args)
    emit(result, args=args)
    return result.exit_code(args.fail_on, args.baseline)
