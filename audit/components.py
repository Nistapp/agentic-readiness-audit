"""Stage S6 — component model.

Components are *declared* by build manifests, at depth 1. Directory nesting is not evidence of a
component: in a Java monolith ``src/main/java/com/acme/...`` is a package, and demanding
governance files for packages produces noise in exactly the repositories this tool targets.

Undeclared multi-app layouts are reported as *candidate* components — informational, never scored.
See ADR-0003.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from audit.scan import Inventory

#: Directories whose immediate children are likely components when nothing declares them.
CANDIDATE_ROOTS = ("apps", "services", "packages", "components", "modules", "libs", "workers")


@dataclass(frozen=True)
class Component:
    """A declared component: a path with a build manifest that a manifest declares as a member."""

    name: str
    path: str
    declared_by: str            # which manifest declared it
    manifest: str | None = None  # the component's own build manifest, if present

    @property
    def is_root(self) -> bool:
        return self.path in (".", "")


@dataclass
class ComponentModel:
    components: list[Component] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def declared(self) -> list[Component]:
        return self.components

    def coverage(self, predicate) -> tuple[int, int]:
        """(components satisfying predicate, total non-root components)."""
        members = [c for c in self.components if not c.is_root]
        if not members:
            return (1 if any(predicate(c) for c in self.components) else 0, 1)
        return (sum(1 for c in members if predicate(c)), len(members))


def _manifest_in(inv: Inventory, prefix: str) -> str | None:
    for candidate in ("package.json", "pyproject.toml", "pom.xml", "build.gradle",
                      "build.gradle.kts", "Cargo.toml", "go.mod"):
        rel = f"{prefix}/{candidate}".lstrip("./") if prefix != "." else candidate
        if inv.has(rel):
            return rel
    return None


def _expand_workspace_glob(inv: Inventory, pattern: str) -> list[str]:
    """Expand a workspace glob one level ('packages/*' -> existing immediate children)."""
    pattern = pattern.strip().rstrip("/")
    if not pattern:
        return []
    if pattern.endswith("/*"):
        parent = pattern[:-2]
        prefix = f"{parent}/" if parent else ""
        seen: set[str] = set()
        for rel in inv.paths():
            if rel.startswith(prefix) and "/" not in rel[len(prefix):]:
                seen.add(prefix.rstrip("/"))
            elif rel.startswith(prefix):
                child = rel[len(prefix):].split("/", 1)[0]
                seen.add(f"{prefix}{child}")
        return sorted(seen)
    return [pattern] if any(r == pattern or r.startswith(pattern + "/") for r in inv.paths()) else []


def detect_components(inv: Inventory) -> ComponentModel:
    model = ComponentModel()
    model.components.append(Component(name="(root)", path=".", declared_by="implicit",
                                      manifest=_manifest_in(inv, ".")))

    # -- Node / TypeScript workspaces ------------------------------------
    text = inv.read("package.json")
    if text:
        try:
            workspaces = json.loads(text).get("workspaces")
        except json.JSONDecodeError:
            workspaces = None
        globs = workspaces.get("packages", []) if isinstance(workspaces, dict) else (workspaces or [])
        for glob in globs if isinstance(globs, list) else []:
            for path in _expand_workspace_glob(inv, str(glob)):
                model.components.append(Component(name=PurePosixPath(path).name, path=path,
                                                  declared_by="package.json:workspaces",
                                                  manifest=_manifest_in(inv, path)))

    # -- pnpm-workspace.yaml (minimal list parse; no YAML parser in the stdlib) --
    pnpm = inv.read("pnpm-workspace.yaml")
    if pnpm:
        globs = re.findall(r"^\s*-\s*['\"]?([^'\"\n]+)['\"]?\s*$", pnpm, re.MULTILINE)
        for glob in globs:
            for path in _expand_workspace_glob(inv, glob):
                if not any(c.path == path for c in model.components):
                    model.components.append(Component(name=PurePosixPath(path).name, path=path,
                                                      declared_by="pnpm-workspace.yaml",
                                                      manifest=_manifest_in(inv, path)))

    # -- Maven multi-module ----------------------------------------------
    pom = inv.read("pom.xml")
    if pom:
        for module in re.findall(r"<module>\s*([^<\s]+)\s*</module>", pom):
            model.components.append(Component(name=module.strip("./").split("/")[-1],
                                              path=module.strip("./"),
                                              declared_by="pom.xml:<modules>",
                                              manifest=_manifest_in(inv, module.strip("./"))))

    # -- Gradle subprojects ----------------------------------------------
    for settings in ("settings.gradle", "settings.gradle.kts"):
        text = inv.read(settings)
        if not text:
            continue
        for raw in re.findall(r"include\s*\(?\s*([^\n)]+)", text):
            for quoted in re.findall(r"['\"]([^'\"]+)['\"]", raw):
                path = quoted.replace(":", "/").strip("/")
                if path and not any(c.path == path for c in model.components):
                    model.components.append(Component(name=path.split("/")[-1], path=path,
                                                      declared_by=f"{settings}:include",
                                                      manifest=_manifest_in(inv, path)))

    # -- go.work / Cargo workspace ---------------------------------------
    gowork = inv.read("go.work")
    if gowork:
        for path in re.findall(r"^\s*(?:use\s+)?\(?\s*(\./[^\s)]+)", gowork, re.MULTILINE):
            path = path.strip("./")
            model.components.append(Component(name=path.split("/")[-1], path=path,
                                              declared_by="go.work:use",
                                              manifest=_manifest_in(inv, path)))

    cargo = inv.read("Cargo.toml")
    if cargo:
        members = re.search(r"members\s*=\s*\[([^\]]*)\]", cargo, re.DOTALL)
        quoted_members = re.findall(r"['\"]([^'\"]+)['\"]", members.group(1)) if members else []
        for quoted in quoted_members:
            for path in _expand_workspace_glob(inv, quoted):
                model.components.append(Component(name=PurePosixPath(path).name, path=path,
                                                  declared_by="Cargo.toml:[workspace]",
                                                  manifest=_manifest_in(inv, path)))

    # -- Candidate components (informational only) ------------------------
    declared_paths = {c.path for c in model.components}
    for root in CANDIDATE_ROOTS:
        for rel in inv.paths():
            parts = rel.split("/")
            if len(parts) >= 2 and parts[0] == root:
                candidate = f"{root}/{parts[1]}"
                if candidate not in declared_paths and candidate not in model.candidates:
                    if _manifest_in(inv, candidate):
                        model.candidates.append(candidate)

    if not model.candidates and len(model.components) == 1:
        model.notes.append("single-root repository: no component declarations found")
    return model
