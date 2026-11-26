#!/usr/bin/env python3
"""Workstation-path scrub for the planning text exported to the public tool repository (Phase 16, D-05).

Each --map OLD=NEW replaces the folder OLD in its forward-slash, backslash and git-bash (/c/...)
spellings, case-insensitively, with NEW; an empty NEW makes the path repo-relative (the separator
after it goes too). Three generic rules then run on whatever is left: a drive-letter or git-bash
user home path becomes <home>, a drive-letter or git-bash path into the repositories folder becomes
<repos-folder>, and the person's name in a pytest temp folder becomes the placeholder <user>. The scrub is
idempotent, keeps line endings, and leaves a text without such paths byte-identical.

No workstation path is written into this file: the generic rules are patterns, and the specific
folders arrive through --map.

Usage:
    python scripts/split/scrub.py --root DIR [--prefix PREFIX ...] [--map OLD=NEW ...]

--prefix names a file or folder under --root (default .planning); text files under it are rewritten
in place (UTF-8; a file with a NUL in its first 8192 bytes, or one that is not UTF-8, is skipped)
and the changed paths are printed. Exit codes: 0 done, 2 unusable input. Stdlib only.
"""

import argparse
import re
import sys
from pathlib import Path

BINARY_PROBE_BYTES = 8192

# One path separator: a doubled backslash (as in JSON text) counts as one
_SEP = r"(?:\\\\|[\\/])"
# After a path: a separator (kept in the match so an empty NEW can drop it) or the end of a folder name
_TAIL = r"(?:(?P<sep>\\\\|[\\/])|(?![\w.\-]))"

# Names assembled from pieces so this file never matches the scan's own rules
_USERS = "Users"
_REPOS = "Git_Repo" + "_Clones"
_PYTEST_OF = "pytest" + "-of-"
# a user folder name, or a placeholder in angle brackets such as the one a document uses to describe the pattern
_NAME = r"(?:<[^<>\s]+>|[^\\/\s\"'<>|:*?`]+)"

# A line break quoted as backslash-n, -r or -t (JSON, logs) hides the start of a path behind its letter
_AFTER_ESCAPE = r"(?<=\\[nrt])"
_BEFORE_DRIVE = r"(?:(?<![A-Za-z0-9_.])|" + _AFTER_ESCAPE + ")"
_BEFORE_GITBASH = r"(?:(?<![\w.\-/\\])|" + _AFTER_ESCAPE + ")"
# drive letter with a colon or its URL-encoded form, git-bash and WSL (/mnt/c/) spellings, and a UNC share
_DRIVE = _BEFORE_DRIVE + r"[a-z](?::|%3a)" + _SEP + "+"
_GITBASH = _BEFORE_GITBASH + "(?:/mnt)?/[a-z]/"
_UNC = r"(?<![\w\\])\\\\[^\\/\s\"'<>|:*?`]+\\[^\\/\s\"'<>|:*?`]+\\"

_HOME_RE = re.compile(r"(?i)(?:" + _DRIVE + "|" + _GITBASH + "|" + _UNC + ")" + _USERS + _SEP + "+" + _NAME)
_REPOS_RE = re.compile(r"(?i)(?:" + _DRIVE + "|" + _GITBASH + ")" + _REPOS + r"(?![\w.\-])")
_PYTEST_RE = re.compile(r"(?i)" + re.escape(_PYTEST_OF) + r"(?!runner\b)[^\s\\/]+")


def parse_map(items: list[str]) -> list[tuple[str, str]]:
    """OLD=NEW items as (old, new) pairs, the longest OLD first so a nested folder wins over its parent."""
    pairs: list[tuple[str, str]] = []
    for item in items:
        old, sep, new = item.partition("=")
        old = old.strip().replace("\\", "/").rstrip("/")
        if not sep or not old:
            raise ValueError(f"not an OLD=NEW pair: {item!r}")
        pairs.append((old, new))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def _path_patterns(old: str) -> list[re.Pattern]:
    """Regexes for one mapped folder: the drive-letter spelling (both slash styles) and the git-bash spelling."""
    drive = re.match(r"^([A-Za-z]):/(.*)$", old) or re.match(r"^/([A-Za-z])/(.*)$", old)
    if not drive:
        segments = [part for part in old.split("/") if part]
        body = "".join(_SEP + re.escape(part) for part in segments)
        return [re.compile(r"(?i)(?<![\w.\-])" + body + _TAIL)]
    letter = drive.group(1)
    segments = [part for part in drive.group(2).split("/") if part]
    tail = "".join(_SEP + re.escape(part) for part in segments)
    return [
        re.compile(r"(?i)" + _BEFORE_DRIVE + re.escape(letter + ":") + tail + _TAIL),
        re.compile(r"(?i)" + _BEFORE_GITBASH + re.escape("/" + letter) + tail + _TAIL),
    ]


def _replacement(new: str):
    def replace(match: re.Match) -> str:
        sep = match.group("sep") or ""
        return new + sep if new else ""

    return replace


def scrub_text(text: str, mapping: list[tuple[str, str]]) -> str:
    """The text with every mapped folder, then the generic home, repos-folder and pytest-of paths replaced."""
    for old, new in mapping:
        for pattern in _path_patterns(old):
            text = pattern.sub(_replacement(new), text)
    text = _HOME_RE.sub("<home>", text)
    text = _REPOS_RE.sub("<repos-folder>", text)
    return _PYTEST_RE.sub(_PYTEST_OF + "<user>", text)


def scrub_bytes(data: bytes, mapping: list[tuple[str, str]]) -> bytes:
    """scrub_text on UTF-8 bytes; binary data (a NUL early on) and bytes that are not UTF-8 come back unchanged."""
    if b"\x00" in data[:BINARY_PROBE_BYTES]:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return scrub_text(text, mapping).encode("utf-8")


def _files_under(root: Path, prefix: str) -> list[Path]:
    start = root / prefix
    if start.is_file():
        return [start]
    if not start.is_dir():
        return []
    return sorted(path for path in start.rglob("*") if path.is_file() and ".git" not in path.relative_to(root).parts)


def scrub_tree(root: Path, prefixes: list[str], mapping: list[tuple[str, str]]) -> list[str]:
    """Rewrite the text files under each prefix in place; return the changed paths relative to root."""
    root = Path(root)
    changed: list[str] = []
    seen: set[Path] = set()
    for prefix in prefixes:
        for path in _files_under(root, prefix):
            if path in seen:
                continue
            seen.add(path)
            data = path.read_bytes()
            scrubbed = scrub_bytes(data, mapping)
            if scrubbed != data:
                path.write_bytes(scrubbed)
                changed.append(path.relative_to(root).as_posix())
    return sorted(changed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrub workstation paths from exported planning text.")
    parser.add_argument("--root", type=Path, required=True, help="folder holding the exported tree")
    parser.add_argument("--prefix", action="append", default=None, help="file or folder under --root (default .planning)")
    parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="folder to replace (repeatable)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.root.is_dir():
        print(f"scrub: not a folder: {args.root}", file=sys.stderr)
        return 2
    try:
        mapping = parse_map(args.map)
    except ValueError as error:
        print(f"scrub: {error}", file=sys.stderr)
        return 2
    for rel in scrub_tree(args.root, args.prefix or [".planning"], mapping):
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
