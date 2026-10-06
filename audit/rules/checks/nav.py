"""`NAV` pack — navigation.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables.

Implemented here: `NAV-01` … `NAV-05`. The first three are scored; `NAV-04` and `NAV-05` are
informational (`scored=False` in the registry) and are reported but earn no credit.

* **NAV-01** — at least one non-root component declared by a build manifest is `PASS`. A single-root
  repository that still declares a manifest is `PASS` (the boundary exists, it is just the root).
  Candidate components (undeclared multi-app layouts) are `PARTIAL`, because the layout exists but
  nothing declares it. Nothing at all is ``UNKNOWN``, not `FAIL`: an unrecognised ecosystem is not
  proof that boundaries are absent.
* **NAV-02** — a language-appropriate entry point (npm `main`/`bin`/`exports`, an `__main__` or
  `if __name__ == "__main__"`, JVM `main`, Go/Rust `func main`, a `bin/` script) is `PASS`. A
  recognised ecosystem with none is `FAIL`; no recognised ecosystem is ``UNKNOWN``.
* **NAV-03** — a census, never a verdict on heuristics: oversized files, catch-all directories,
  checked-in binaries and minified assets. All-zero is `PASS`; any count is `PARTIAL`, with the
  counts and the documented thresholds in `detail`. It never `FAIL`s.
* **NAV-04** — informational: `docs/architecture/`, an ADR directory, or a diagram exists.
* **NAV-05** — informational docstring census over public symbols. The method is stated in `detail`;
  when "public" cannot be defined for the files present the check is ``UNKNOWN``.

Deliberate limits, recorded rather than hidden. NAV-02 reads a fixed, documented set of entry-point
signals per ecosystem rather than resolving one semantically. NAV-05 is a best-effort static
approximation of "public": module-level names not starting with an underscore (Python) or exported
declarations (TypeScript/JavaScript); it never executes or reflects.
"""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.scan import Inventory, Kind
from audit.rules.payloads import Payload, Ratio

#: Files larger than this are counted as oversized (NAV-03). Documented, not tuned.
LARGE_FILE_BYTES = 512 * 1024

#: A directory holding more than this many immediate files is a catch-all (NAV-03). Documented.
CATCH_ALL_FILES = 50


def _outcome(spec, verdict: Verdict, summary: str = "",
             findings: list[Finding] | None = None,
             data: Payload | None = None) -> CheckOutcome:
    return CheckOutcome(spec.id, spec.title, spec.tier, spec.severity, spec.phase, verdict,
                        spec.status, summary=summary, data=data, findings=findings or [])


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _has_exact(inventory: Inventory, rel: str) -> bool:
    """Exact path membership: unlike ``Inventory.has``, never a suffix match at any depth."""
    return any(f.rel == rel for f in inventory.files)


# ===========================================================================
# NAV-01 — declared component boundaries
# ===========================================================================

def check_nav01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    members = [c for c in components.declared if not c.is_root]
    if members:
        detail = ", ".join(f"{c.path} (by {c.declared_by})" for c in members[:6])
        return _outcome(spec, Verdict.PASS,
                        f"{len(members)} declared component(s): {detail}")

    if components.candidates:
        return _outcome(spec, Verdict.PARTIAL,
                        f"{len(components.candidates)} candidate component(s), none declared", [
            Finding(
                check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
                statement=statement(
                    "scope work to a bounded component",
                    f"{', '.join(components.candidates[:6])} look like components but no build "
                    f"manifest declares them"),
                evidence=[Evidence(path) for path in components.candidates[:12]],
                remediation="Declare the components in a workspace manifest (npm workspaces, "
                            "pnpm-workspace.yaml, Maven modules, Gradle includes) so blast radius "
                            "is scoped."),
        ])

    root = next((c for c in components.declared if c.is_root), None)
    if root is not None and root.manifest:
        return _outcome(spec, Verdict.PASS,
                        f"single-root repository declares {root.manifest}")

    return _unknown(spec, "no build manifest declares a component; stack not recognised")


# ===========================================================================
# NAV-02 — obvious entry points
# ===========================================================================

_NODE_INDEX_FILES = (
    "index.js", "index.ts", "index.mjs", "index.cjs",
    "src/index.js", "src/index.ts", "src/index.mjs",
    "server.js", "server.ts", "src/server.js", "src/server.ts",
    "main.js", "main.ts", "main.mjs", "main.cjs", "src/main.js", "src/main.ts",
    "app.js", "app.ts", "src/app.js", "src/app.ts",
)

_ENTRY_NAMES: dict[str, tuple[str, ...]] = {
    "dotnet": ("Program.cs", "program.cs", "src/Program.cs"),
    "ruby": ("config.ru", "app.rb", "main.rb", "bin/rails", "bin/setup"),
    "php": ("index.php", "public/index.php", "bin/console"),
}


def _node_entry(inventory: Inventory) -> list[str]:
    found: list[str] = []
    text = inventory.read("package.json")
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            if data.get("main"):
                found.append(f"package.json:main={data['main']}")
            if data.get("bin"):
                found.append("package.json:bin")
            if data.get("exports"):
                found.append("package.json:exports")
    for rel in _NODE_INDEX_FILES:
        if _has_exact(inventory, rel):
            found.append(rel)
    return found


def _python_entry(inventory: Inventory) -> list[str]:
    found: list[str] = []
    for entry in inventory.files:
        if entry.rel.endswith("__main__.py"):
            found.append(entry.rel)
    for rel in ("main.py", "app.py", "src/main.py", "src/app.py", "manage.py"):
        if _has_exact(inventory, rel):
            found.append(rel)
    hits = inventory.grep(r"if\s+__name__\s*==\s*['\"]__main__['\"]",
                          kinds=(Kind.SOURCE, Kind.SCRIPT), limit=10)
    found += [rel for rel, _line, _text in hits if rel not in found]
    for manifest in ("pyproject.toml", "setup.py", "setup.cfg"):
        text = inventory.read(manifest)
        if text and re.search(r"(?i)console_scripts|\[project\.scripts\]|entry_points", text):
            found.append(f"{manifest}:entry point")
    return found


def _grep_sources(inventory: Inventory, pattern: str, limit: int = 10) -> list[str]:
    return [rel for rel, _line, _text in inventory.grep(pattern, kinds=(Kind.SOURCE,), limit=limit)]


def _jvm_entry(inventory: Inventory) -> list[str]:
    return _grep_sources(inventory, r"public\s+static\s+void\s+main\s*\(|fun\s+main\s*\(|"
                                    r"@SpringBootApplication")


def _go_entry(inventory: Inventory) -> list[str]:
    return _grep_sources(inventory, r"^func\s+main\s*\(")


def _rust_entry(inventory: Inventory) -> list[str]:
    found: list[str] = []
    for rel in ("src/main.rs", "src/bin/main.rs", "main.rs"):
        if _has_exact(inventory, rel):
            found.append(rel)
    cargo = inventory.read("Cargo.toml")
    if cargo and re.search(r"\[\[\s*bin\s*\]\]", cargo):
        found.append("Cargo.toml:[[bin]]")
    return found


_DETECTORS = {
    "node": _node_entry,
    "python": _python_entry,
    "jvm": _jvm_entry,
    "go": _go_entry,
    "rust": _rust_entry,
}


def _entry_points(inventory: Inventory, ecosystems: set[str]) -> list[str]:
    found: list[str] = []
    for eco in sorted(ecosystems):
        detector = _DETECTORS.get(eco)
        if detector:
            found += detector(inventory)
        for rel in _ENTRY_NAMES.get(eco, ()):
            if _has_exact(inventory, rel):
                found.append(rel)
    seen: set[str] = set()
    unique: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def check_nav02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not stack.ecosystems:
        return _unknown(spec, "no recognised ecosystem, so an entry point cannot be located")

    found = _entry_points(inventory, stack.ecosystems)
    ecosystems = ", ".join(sorted(stack.ecosystems))
    if found:
        return _outcome(spec, Verdict.PASS,
                        f"entry point(s): {', '.join(found[:6])}")

    return _outcome(spec, Verdict.FAIL,
                    f"no entry point found for {ecosystems}", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "find where execution begins",
                f"the {ecosystems} project declares no entry point (main, bin, __main__, "
                f"Application or func main)"),
            remediation="Declare the entry point in the manifest (package.json main/bin, "
                        "pyproject scripts, a Gradle main class) or name the executable file so "
                        "an agent can tell live code from dead code."),
    ])


# ===========================================================================
# NAV-03 — structural red flags (informational counts, never FAIL)
# ===========================================================================

def check_nav03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    oversized = sorted(f.rel for f in inventory.files if f.size > LARGE_FILE_BYTES)
    binaries = sorted(f.rel for f in inventory.files if f.kind is Kind.BINARY)
    minified = sorted(f.rel for f in inventory.files
                      if f.kind is Kind.GENERATED and ".min." in f.rel.lower())

    per_dir: dict[str, int] = {}
    for entry in inventory.files:
        parent = entry.rel.rsplit("/", 1)[0] if "/" in entry.rel else "."
        per_dir[parent] = per_dir.get(parent, 0) + 1
    catch_all = sorted(directory for directory, count in per_dir.items()
                       if count > CATCH_ALL_FILES)

    detail = (f"oversized(>{LARGE_FILE_BYTES} B): {len(oversized)}; "
              f"catch-all dirs(>{CATCH_ALL_FILES} files): {len(catch_all)}; "
              f"binaries: {len(binaries)}; minified: {len(minified)}")
    flags = oversized + catch_all + binaries + minified
    if not flags:
        return _outcome(spec, Verdict.PASS, detail)

    return _outcome(spec, Verdict.PARTIAL, detail, [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.PARTIAL,
            statement=statement(
                "work in a codebase without obvious structural traps",
                f"{len(oversized)} oversized file(s), {len(catch_all)} catch-all director(y/ies), "
                f"{len(binaries)} checked-in binary file(s) and {len(minified)} minified asset(s)"),
            evidence=[Evidence(rel) for rel in (oversized + catch_all + binaries + minified)[:12]],
            remediation="Split oversized files, break up catch-all directories, and keep binaries "
                        "and minified assets out of the tree (generate them in the build)."),
    ])


# ===========================================================================
# NAV-04 — architecture orientation artifact (informational)
# ===========================================================================

_DIAGRAM_SUFFIXES = (".mmd", ".puml", ".drawio", ".excalidraw", ".svg", ".png")


def check_nav04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    has_arch = any(f.rel.startswith("docs/architecture/") for f in inventory.files)
    has_adr = any(f.rel.startswith(("docs/architecture/adrs/", "docs/adr/"))
                  for f in inventory.files)
    diagrams = sorted(f.rel for f in inventory.files
                      if f.rel.lower().endswith(_DIAGRAM_SUFFIXES))

    if has_arch or has_adr or diagrams:
        parts = []
        if has_arch:
            parts.append("docs/architecture/")
        if has_adr:
            parts.append("an ADR directory")
        if diagrams:
            parts.append(f"{len(diagrams)} diagram(s)")
        return _outcome(spec, Verdict.PASS, "; ".join(parts))

    return _outcome(spec, Verdict.FAIL, "no architecture orientation artifact", [
        Finding(
            check=spec.id, severity=spec.severity, phase=spec.phase, verdict=Verdict.FAIL,
            statement=statement(
                "orient itself from a map instead of exploring blindly",
                "no docs/architecture/, ADR directory or diagram exists"),
            remediation="Add a short architecture page (with a diagram) so an agent can orient "
                        "before it explores."),
    ])


# ===========================================================================
# NAV-05 — public-symbol documentation coverage (informational)
# ===========================================================================

_PY_PUBLIC_RE = re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)|^class\s+([A-Za-z_]\w*)")
_TS_EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)")
_TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _language(inventory: Inventory, stack) -> str | None:
    counts = {"python": 0, "typescript": 0}
    for entry in inventory.files:
        if entry.rel.endswith(".py"):
            counts["python"] += 1
        elif entry.rel.endswith(_TS_SUFFIXES):
            counts["typescript"] += 1
    if "python" in stack.ecosystems and counts["python"]:
        return "python"
    if "node" in stack.ecosystems and counts["typescript"]:
        return "typescript"
    if counts["python"] >= counts["typescript"] and counts["python"]:
        return "python"
    if counts["typescript"]:
        return "typescript"
    return None


def _next_code_line(lines: list[str], start: int) -> str | None:
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    return lines[index] if index < len(lines) else None


def _python_census(inventory: Inventory) -> tuple[int, int]:
    total = documented = 0
    for entry in inventory.files:
        if not entry.rel.endswith(".py") or not entry.has_text:
            continue
        lines = (inventory.read(entry.rel) or "").splitlines()
        for index, line in enumerate(lines):
            match = _PY_PUBLIC_RE.match(line)
            if not match:
                continue
            name = match.group(1) or match.group(2)
            if name.startswith("_"):
                continue
            total += 1
            following = _next_code_line(lines, index + 1)
            if following is not None and following.lstrip().startswith(('"""', "'''")):
                documented += 1
    return total, documented


def _ts_census(inventory: Inventory) -> tuple[int, int]:
    total = documented = 0
    for entry in inventory.files:
        if not entry.rel.endswith(_TS_SUFFIXES) or not entry.has_text:
            continue
        lines = (inventory.read(entry.rel) or "").splitlines()
        for index, line in enumerate(lines):
            if not _TS_EXPORT_RE.match(line):
                continue
            total += 1
            cursor = index - 1
            while cursor >= 0 and not lines[cursor].strip():
                cursor -= 1
            if cursor >= 0 and lines[cursor].strip().endswith("*/"):
                while cursor >= 0 and "/**" not in lines[cursor]:
                    cursor -= 1
                if cursor >= 0:
                    documented += 1
    return total, documented


def check_nav05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    language = _language(inventory, stack)
    if language is None:
        return _unknown(spec, "no recognised source language, so 'public' cannot be defined")

    total, documented = (_python_census(inventory) if language == "python"
                         else _ts_census(inventory))
    method = (f"python: module-level def/class not starting with '_'"
              if language == "python" else "typescript: exported declarations")
    if total == 0:
        return _unknown(spec, f"{language}: no public symbols detected ({method})")

    ratio = documented / total
    detail = f"{documented}/{total} public symbols documented ({ratio:.0%}); method: {method}"
    verdict = Verdict.PASS if documented == total else Verdict.PARTIAL
    return _outcome(spec, verdict, detail,
                    data=Ratio(numerator=documented, denominator=total,
                               unit="public symbols", method=method))


IMPLEMENTATIONS = {
    "NAV-01": check_nav01,
    "NAV-02": check_nav02,
    "NAV-03": check_nav03,
    "NAV-04": check_nav04,
    "NAV-05": check_nav05,
}
