"""Stage S8 — Tier-C probe runner.

Executing a repository's own commands executes that repository's code. That is a supply-chain
decision, and this module never makes it on the operator's behalf (ADR-0002):

* disabled unless the caller passes an explicit verb allow-list
* never installs anything
* one timeout per probe, and the timeout itself is recorded as evidence
* captured output is redacted for credential shapes **at capture time**, never at render time
* only verbs the rule pack declares read-only are eligible
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Verbs that mutate the working tree or the environment. Never probe-eligible.
MUTATING_VERBS = frozenset({"format", "install", "clean", "build"})

REDACTION_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._\-]{16,}"),
)

OUTPUT_TAIL_LINES = 40


@dataclass
class ProbeResult:
    verb: str
    command: list[str]
    exit_code: int | None
    duration_s: float
    timed_out: bool = False
    output_tail: str = ""
    refused_reason: str | None = None
    redactions: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.refused_reason


@dataclass
class ProbePlan:
    verb: str
    command: list[str]
    read_only: bool = True


def redact(text: str) -> tuple[str, int]:
    """Redact credential-shaped substrings. Returns (clean_text, redaction_count)."""
    count = 0
    for pattern in REDACTION_PATTERNS:
        text, n = pattern.subn("[REDACTED]", text)
        count += n
    return text, count


def eligible(plan: ProbePlan, allow: tuple[str, ...]) -> tuple[bool, str | None]:
    if plan.verb not in allow:
        return False, f"verb {plan.verb!r} not in --allow-probe list"
    if plan.verb in MUTATING_VERBS:
        return False, f"verb {plan.verb!r} is declared mutating and is never probe-eligible"
    if not plan.read_only:
        return False, f"verb {plan.verb!r} is not declared read-only by its rule pack"
    return True, None


def run_plan(plan: ProbePlan, *, allow: tuple[str, ...], cwd: Path,
             timeout: int = 300) -> ProbeResult:
    """Run one probe. Refusals are recorded as evidence, never as exceptions."""
    permitted, reason = eligible(plan, allow)
    if not permitted:
        return ProbeResult(plan.verb, plan.command, None, 0.0, refused_reason=reason)

    started = time.monotonic()
    try:
        proc = subprocess.run(plan.command, cwd=str(cwd), text=True, capture_output=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        clean, redactions = redact(partial)
        return ProbeResult(plan.verb, plan.command, None, time.monotonic() - started,
                           timed_out=True,
                           output_tail="\n".join(clean.splitlines()[-OUTPUT_TAIL_LINES:]),
                           redactions=redactions)
    except OSError as exc:
        return ProbeResult(plan.verb, plan.command, None, time.monotonic() - started,
                           refused_reason=f"could not execute: {exc}")

    combined = (proc.stdout or "") + (proc.stderr or "")
    clean, redactions = redact(combined)
    return ProbeResult(plan.verb, plan.command, proc.returncode, time.monotonic() - started,
                       output_tail="\n".join(clean.splitlines()[-OUTPUT_TAIL_LINES:]),
                       redactions=redactions)


@dataclass
class ProbeSession:
    """Runs at most one probe per verb, and only what the operator permitted."""

    cwd: Path
    allow: tuple[str, ...] = ()
    timeout: int = 300
    enabled: bool = False
    results: list[ProbeResult] = field(default_factory=list)

    def run(self, plan: ProbePlan) -> ProbeResult:
        if not self.enabled:
            result = ProbeResult(plan.verb, plan.command, None, 0.0,
                                 refused_reason="probes disabled (pass --run-gates)")
            self.results.append(result)
            return result
        result = run_plan(plan, allow=self.allow, cwd=self.cwd, timeout=self.timeout)
        self.results.append(result)
        return result
