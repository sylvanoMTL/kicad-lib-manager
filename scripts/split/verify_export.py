#!/usr/bin/env python3
"""Export checker for the tool repository (Phase 16, D-02, D-16).

Checks a folder holding the exported tool tree against the allow-list: every file must be named by
the list, nothing from the hard-deny list may be present, every required entry must match at least
one file, and the export must not be empty. The allow-list file holds include lines (a line ending
in "/" is a folder prefix that matches whole path segments, any other line is one file) and "!"
lines that exclude a prefix or file inside an included one; "#" lines and blank lines are ignored.

Usage:
    python scripts/split/verify_export.py DIR --allow-list FILE

Output: one problem per line, then `verify_export: ok (<n> files)` or `verify_export: <k> problem(s)`.
Exit codes: 0 clean, 1 problems, 2 a missing folder or allow-list. Stdlib only; the script never
imports the application package. The `.git/` folder at the top of DIR is ignored.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Paths that never leave the private repository, whatever the allow-list says
HARD_DENY_PREFIXES = (
    "Custom/",
    "WurthElektronik/",
    "downloaded_examples/",
    "reports/",
    "research_notes/",
    ".planning/milestones/",
    ".planning/quick/",
    ".planning/debug/",
)
HARD_DENY_NAMES = (".gitmodules", ".planning/MILESTONES.md", ".planning/RETROSPECTIVE.md")

HARD_DENY = (*HARD_DENY_PREFIXES, *HARD_DENY_NAMES)

# Entries that must match at least one exported file
REQUIRED = (
    "kicad_lib_manager/",
    "kicad_lib_manager.py",
    "tests/",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "LICENSE",
    "README.md",
    "CLAUDE.md",
    "scripts/",
    ".github/",
)


def _norm(rel: str) -> str:
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def matches(rel: str, entry: str) -> bool:
    """A folder entry (trailing "/") matches whole path segments, a file entry only itself."""
    return rel.startswith(entry) if entry.endswith("/") else rel == entry


def hard_denied(rel: str) -> bool:
    return any(matches(_norm(rel), entry) for entry in HARD_DENY)


@dataclass(frozen=True)
class AllowList:
    includes: tuple[str, ...]
    excludes: tuple[str, ...] = ()

    def allowed(self, rel: str) -> bool:
        """True when an include names the path, no exclusion does and the hard-deny list does not."""
        rel = _norm(rel)
        if hard_denied(rel) or any(matches(rel, entry) for entry in self.excludes):
            return False
        return any(matches(rel, entry) for entry in self.includes)


def parse_allow_list(text: str) -> AllowList:
    includes: list[str] = []
    excludes: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        exclusion = line.startswith("!")
        entry = _norm(line[1:].strip() if exclusion else line)
        if not entry or entry.startswith("/") or ".." in entry.split("/"):
            raise ValueError(f"allow-list line {number}: not a repository-relative path")
        (excludes if exclusion else includes).append(entry)
    return AllowList(tuple(includes), tuple(excludes))


def load_allow_list(path: Path) -> AllowList:
    return parse_allow_list(Path(path).read_text(encoding="utf-8"))


def export_files(root: Path) -> list[str]:
    """Every file under root as a forward-slash relative path, the top-level .git folder left out."""
    found: list[str] = []
    for folder, dirs, files in os.walk(root):
        here = Path(folder)
        if here == root:
            dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            found.append((here / name).relative_to(root).as_posix())
    return sorted(found)


def verify(root: Path, allow: AllowList) -> list[str]:
    """Problem lines for the exported tree under root; an empty list means the export is acceptable."""
    files = export_files(Path(root))
    if not files:
        return ["the export is empty"]
    problems: list[str] = []
    for rel in files:
        if hard_denied(rel):
            problems.append(f"{rel}: never exported (hard-deny list)")
        elif not allow.allowed(rel):
            problems.append(f"{rel}: not in the allow-list")
    for entry in REQUIRED:
        if not any(matches(rel, entry) for rel in files):
            problems.append(f"required entry {entry} matched no file")
    return problems


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check an exported tool tree against the allow-list.")
    parser.add_argument("export", type=Path, help="folder holding the exported tree")
    parser.add_argument("--allow-list", type=Path, required=True, help="allow-list file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.export.is_dir():
        print(f"verify_export: not a folder: {args.export}", file=sys.stderr)
        return 2
    try:
        allow = load_allow_list(args.allow_list)
    except (OSError, ValueError) as error:
        print(f"verify_export: cannot read the allow-list: {error}", file=sys.stderr)
        return 2
    problems = verify(args.export, allow)
    for line in problems:
        print(line)
    if problems:
        print(f"verify_export: {len(problems)} problem(s)")
        return 1
    print(f"verify_export: ok ({len(export_files(args.export))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
