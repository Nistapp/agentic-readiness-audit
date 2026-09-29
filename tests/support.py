"""Shared test harness — imported by test modules without packaging ``tests/``.

``python3 -m unittest discover -s tests`` puts this directory on ``sys.path``, so every test module
can ``import support``. The helpers exist so the same fixture-write / subprocess-audit / report-read
pattern is not copy-pasted into every new pack's test file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


def write(root: Path, rel: str, text: str) -> Path:
    """Write ``text`` at ``root/rel``, creating parent directories. Returns the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_audit(target: Path, *, fmt: str = "json", extra_args: tuple[str, ...] = (),
              env: dict | None = None) -> dict:
    """Run ``python3 -m audit`` against ``target`` and return the parsed JSON report.

    The report is written to a temporary ``--out`` outside the target (the writer refuses to drop a
    report inside the repository it audits). Exit 0 is asserted: the audit reports, it does not gate.
    ``env`` entries are merged over the parent environment; machine-local checks (the IDX pack) use
    this to redirect ``HOME`` and ``AUDIT_INDEX_STORE`` at a constructed store.
    """
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "report.json"
        proc = subprocess.run(
            [sys.executable, "-m", "audit", str(target),
             "--format", fmt, "--out", str(out), *extra_args],
            cwd=str(REPO_ROOT), text=True, capture_output=True,
            env={**os.environ, **(env or {})},
        )
        if proc.returncode != 0:
            raise AssertionError(f"audit failed ({proc.returncode}): {proc.stderr}")
        if fmt != "json":
            return {"path": str(out), "stdout": proc.stdout}
        return json.loads(out.read_text(encoding="utf-8"))


def run_audit_process(target: Path, *, fmt: str = "json", extra_args: tuple[str, ...] = (),
                      out: Path | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the audit **without** asserting an exit code; return ``(process, out_path)``.

    Needed by the ratchet, where a non-zero exit is the behaviour under test. ``out`` should be a
    fresh path (the writer refuses to overwrite unless ``--force`` is passed).
    """
    out_path = Path(out) if out is not None else (
        Path(tempfile.mkdtemp(prefix="audit-out-")) / "report.json")
    proc = subprocess.run(
        [sys.executable, "-m", "audit", str(target),
         "--format", fmt, "--out", str(out_path), *extra_args],
        cwd=str(REPO_ROOT), text=True, capture_output=True,
    )
    return proc, out_path


def verdicts(report: dict) -> dict[str, str]:
    """``{check id: verdict}`` for every check reported."""
    return {c["id"]: c["verdict"] for c in report["checks"]}


def finding_checks(report: dict) -> set[str]:
    """The set of check ids that emitted at least one finding."""
    return {f["check"] for f in report["findings"]}


def fixture(name: str) -> Path:
    """Resolve ``tests/fixtures/<name>``."""
    return FIXTURES_DIR / name
