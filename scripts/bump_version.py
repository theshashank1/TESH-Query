#!/usr/bin/env python3
"""
scripts/bump_version.py — Manual semantic version bump for TESH-Query.

Usage::

    python scripts/bump_version.py patch   # 2.0.0 → 2.0.1
    python scripts/bump_version.py minor   # 2.0.1 → 2.1.0
    python scripts/bump_version.py major   # 2.1.0 → 3.0.0
    python scripts/bump_version.py         # shows current version

What it does:
  1. Reads the current version from pyproject.toml
  2. Bumps the requested component
  3. Writes the new version back to pyproject.toml
  4. Creates a git tag  v{new_version}
  5. Commits the change
"""

import re
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def read_version() -> str:
    content = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        sys.exit("ERROR: Could not find version = \"...\" in pyproject.toml")
    return match.group(1)


def write_version(new_version: str) -> None:
    content = PYPROJECT.read_text(encoding="utf-8")
    updated = VERSION_RE.sub(f'version = "{new_version}"', content, count=1)
    PYPROJECT.write_text(updated, encoding="utf-8")


def bump(current: str, part: str) -> str:
    parts = current.split(".")
    if len(parts) != 3:
        sys.exit(f"ERROR: Expected semver (X.Y.Z), got: {current}")
    major, minor, patch = (int(p) for p in parts)
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        sys.exit(f"ERROR: Unknown bump type '{part}'. Use: major, minor, patch")


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ERROR running {' '.join(cmd)}:\n{result.stderr}")


def main() -> None:
    current = read_version()

    if len(sys.argv) < 2:
        print(f"Current version: {current}")
        print("Usage: python scripts/bump_version.py [major|minor|patch]")
        return

    part = sys.argv[1].lower()
    new_version = bump(current, part)

    print(f"Bumping {part}: {current} → {new_version}")
    write_version(new_version)
    print(f"  ✓ Updated pyproject.toml")

    run(["git", "add", "pyproject.toml"])
    run(["git", "commit", "pyproject.toml", "-m", f"chore: bump version to {new_version}"])
    print(f"  ✓ Committed")

    run(["git", "tag", f"v{new_version}"])
    print(f"  ✓ Tagged v{new_version}")

    print(f"\nTo push: git push && git push --tags")


if __name__ == "__main__":
    main()
