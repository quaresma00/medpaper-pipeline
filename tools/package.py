#!/usr/bin/env python3
"""Build a self-contained, transferable bundle per agent IDE.

    python tools/package.py                 # all targets -> dist/
    python tools/package.py --target codex
    python tools/package.py --no-zip        # directories only

Each bundle carries the whole workflow (pipeline/, tools/, reference/) plus only the
adapter files that IDE reads, plus an install guide written for that IDE. Nothing is
shared between bundles at runtime, so a bundle can be dropped into any machine and run.

Deliberately excluded: .venv (platform-specific), project/ (run data), dist/, git
metadata, caches, and the other IDEs' adapter files - a Codex bundle containing .kiro/
only invites confusion.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

# Carried by every bundle.
CORE_DIRS = ["pipeline", "reference", "tools"]
CORE_FILES = ["README.md", "requirements.txt", "bootstrap.py", "workflow.md", "LICENSE"]

# Adapter paths per target. `.agents/skills` is the skill source of truth and is shared by
# Codex and the Antigravity CLI, so both bundles carry it.
TARGETS: dict[str, dict] = {
    "codex": {
        "label": "OpenAI Codex",
        "paths": ["AGENTS.md", ".agents/AGENTS.md", ".agents/skills"],
        "guide": "INSTALL-CODEX.md",
    },
    "antigravity": {
        "label": "Google Antigravity",
        "paths": ["AGENTS.md", ".agents/AGENTS.md", ".agents/skills",
                  ".agent/rules", ".agent/workflows"],
        "guide": "INSTALL-ANTIGRAVITY.md",
    },
    "kiro": {
        "label": "Kiro",
        "paths": [".kiro/steering", ".kiro/skills", ".kiro/hooks", ".agents/skills"],
        "guide": "INSTALL-KIRO.md",
    },
    "claude": {
        "label": "Claude Code",
        "paths": ["CLAUDE.md", ".claude/skills", ".agents/skills"],
        "guide": "INSTALL-CLAUDE.md",
    },
}

EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                 ".git", ".venv", "dist", "project", "node_modules", ".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}


def keep(path: Path) -> bool:
    if any(part in EXCLUDE_NAMES for part in path.parts):
        return False
    return path.suffix not in EXCLUDE_SUFFIXES


def copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file() or not keep(p.relative_to(ROOT)):
            continue
        target = dst / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    return n


def copy_path(rel: str, dst: Path) -> int:
    src = ROOT / rel
    if not src.exists():
        print(f"    !! missing, skipped: {rel}")
        return 0
    if src.is_dir():
        return copy_tree(src, dst)
    if not keep(Path(rel)):
        return 0
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return 1


def build(name: str, make_zip: bool) -> Path:
    spec = TARGETS[name]
    out = DIST / f"medpaper-{name}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    total = 0
    for rel in CORE_DIRS:
        total += copy_path(rel, out)
    for rel in CORE_FILES:
        total += copy_path(rel, out)
    for rel in spec["paths"]:
        total += copy_path(rel, out)

    guide = ROOT / "docs" / spec["guide"]
    if guide.exists():
        shutil.copy2(guide, out / spec["guide"])
        total += 1
    else:
        print(f"    !! install guide missing: docs/{spec['guide']}")

    # A project skeleton so the first `wf init` has somewhere to land, without shipping
    # anyone's run data.
    (out / "project").mkdir(exist_ok=True)
    (out / "project" / ".gitkeep").touch()

    # Marks which IDE this bundle is for, so install_adapters.py syncs only that target and
    # does not litter a Codex bundle with .kiro/ and .claude/.
    (out / ".medpaper-target").write_text(name + "\n", encoding="utf-8")
    total += 1

    print(f"  {name:<12} {total:>4} files -> {out.relative_to(ROOT).as_posix()}/")

    if make_zip:
        zpath = DIST / f"medpaper-{name}.zip"
        if zpath.exists():
            zpath.unlink()
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    zf.write(p, Path(f"medpaper-{name}") / p.relative_to(out))
        size = zpath.stat().st_size / 1024
        print(f"  {'':<12} {'':>4}    {zpath.name}  ({size:,.0f} KB)")
    return out


def verify(out: Path, name: str) -> bool:
    """A bundle is only useful if its driver runs from inside it."""
    import subprocess
    problems = []
    for must in ("pipeline/pipeline.toml", "tools/wf.py", "reference/archetypes.toml",
                 "requirements.txt", "bootstrap.py"):
        if not (out / must).exists():
            problems.append(f"missing {must}")
    cards = len(list((out / "pipeline" / "stages").glob("*.md"))) if (out / "pipeline" / "stages").exists() else 0
    if cards < 20:
        problems.append(f"only {cards} stage cards")

    # Run the driver from inside the bundle with the environment cleared of any
    # MEDPAPER_* overrides, so this proves the bundle is genuinely self-locating.
    import os
    import re
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEDPAPER_")}
    proc = subprocess.run([sys.executable, "tools/wf.py", "doctor"], cwd=out, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    out_txt = (proc.stdout or "") + (proc.stderr or "")
    if not re.search(r"stage cards\s+ok\s+(\d+)/\1", out_txt):
        problems.append("driver could not resolve the stage cards inside the bundle")
    if not re.search(r"gate checks\s+ok", out_txt):
        problems.append("gate checks did not resolve inside the bundle")
    m = re.search(r"stage cards\s+ok\s+(\d+)/(\d+)", out_txt)
    if m:
        cards = int(m.group(1))

    for rel in TARGETS[name]["paths"]:
        if not (out / rel).exists():
            problems.append(f"adapter missing: {rel}")

    if problems:
        print(f"    VERIFY FAILED: {'; '.join(problems)}")
        return False
    print(f"    verified: {cards} stage cards, driver runs standalone, adapters present")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="build transferable bundles")
    ap.add_argument("--target", action="append", default=[], choices=sorted(TARGETS))
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--clean", action="store_true", help="remove dist/ first")
    args = ap.parse_args()

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(exist_ok=True)

    names = args.target or sorted(TARGETS)
    print(f"building {len(names)} bundle(s) into {DIST.relative_to(ROOT).as_posix()}/\n")
    bad = 0
    for name in names:
        out = build(name, not args.no_zip)
        if not verify(out, name):
            bad += 1
    print()
    if bad:
        print(f"{bad} bundle(s) failed verification")
        return 2
    print("all bundles verified. Each one is standalone: unzip, run bootstrap.py, done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
