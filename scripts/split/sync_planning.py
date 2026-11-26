#!/usr/bin/env python3
"""Carry later planning changes from the private repository into the tool checkout (Phase 16, D-05).

Lists what changed under .planning/ between a tag and a ref (git diff --name-status), then, for every
path the allow-list keeps, copies the added or changed file at the ref into the tool checkout with
workstation paths scrubbed, and deletes the removed ones. Anything not under .planning/ or not kept
by the allow-list is reported as `skip <path>` and left alone. Nothing outside .planning/ of the
destination is ever touched. The script does not commit: the caller scans, commits and pushes.

It refuses (exit 2) when .planning/ of the destination has uncommitted changes, and it leaves a file
alone, printing `conflict <path>`, when the committed copy in the destination (HEAD, so a checkout that
converts line endings cannot matter) no longer matches what the scrubbed --since ref holds (someone edited
it there): a sync never overwrites or deletes such a file.

--since is the ref the destination was last brought to: the tag the tool repository was built from for the
first sync, then the --ref of the previous sync (a sync from an older ref reports every file the earlier
syncs changed as a conflict, because the destination no longer holds that older version).

Usage:
    python scripts/split/sync_planning.py --source DIR --ref REF --since TAG --dest DIR
        --allow-list FILE [--map OLD=NEW ...]

Output: one line per changed path in path order: `A <path>`, `M <path>`, `D <path>`, `skip <path>` or
`conflict <path>`. Exit codes: 0 done, 1 done but at least one conflict was left, 2 an unknown ref, a dirty
destination or unusable input. Stdlib only; never imports the application package.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from scrub import parse_map, scrub_bytes
from verify_export import AllowList, load_allow_list

PLANNING = ".planning"


class SyncError(Exception):
    """A refusal or failure; main() prints it and exits 2."""


def _git(repo: Path, *args: str) -> bytes:
    """Run git in repo and return stdout; raise SyncError on a failure."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except OSError as error:
        raise SyncError(f"cannot run git: {error}") from error
    if done.returncode != 0:
        reason = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise SyncError(f"git {args[0]} failed in {repo}: {reason[-1] if reason else 'no detail'}")
    return done.stdout


def _changes(source: Path, ref: str, since: str) -> list[tuple[str, str]]:
    """(status letter, path) for every path under .planning/ that differs between since and ref."""
    for name in (ref, since):
        try:
            _git(source, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")
        except SyncError as error:
            raise SyncError(f"unknown ref in {source}: {name}") from error
    raw = _git(source, "diff", "--name-status", "--no-renames", "-z", since, ref, "--", f"{PLANNING}/")
    tokens = [token for token in raw.decode("utf-8", errors="replace").split("\0") if token]
    pairs = list(zip(tokens[0::2], tokens[1::2], strict=False))
    return sorted(((status[0], path) for status, path in pairs), key=lambda pair: pair[1])


def _inside_planning(dest: Path, target: Path) -> bool:
    return (dest / PLANNING).resolve() in target.resolve().parents


def _require_clean_planning(dest: Path) -> None:
    """Refuse a destination whose .planning/ holds uncommitted work: a sync would overwrite it unseen."""
    dirty = _git(dest, "status", "--porcelain", "--", f"{PLANNING}/").decode("utf-8", errors="replace").strip()
    if dirty:
        shown = "; ".join(line.strip() for line in dirty.splitlines()[:5])
        raise SyncError(f"{PLANNING}/ of {dest} has uncommitted changes (commit or stash them first): {shown}")


def _committed(dest: Path, path: str) -> bytes | None:
    """The bytes of the file at HEAD of the destination (no line-ending conversion), or None when it is not committed."""
    try:
        return _git(dest, "show", f"HEAD:{path}")
    except SyncError:
        return None


def _edited_in_dest(source: Path, since: str, path: str, dest: Path, mapping: list[tuple[str, str]]) -> bool:
    """True when the committed destination copy is not the scrubbed since version (or is not committed)."""
    try:
        expected = scrub_bytes(_git(source, "show", f"{since}:{path}"), mapping)
    except SyncError:
        return False  # not in the since ref: a new file, judged by the caller
    return _committed(dest, path) != expected


def sync(
    source: Path, ref: str, since: str, dest: Path, allow: AllowList, mapping: list[tuple[str, str]]
) -> list[str]:
    """Apply the .planning/ delta between since and ref to dest; return the A/M/D/skip/conflict lines in path order."""
    source, dest = Path(source), Path(dest)
    if not dest.is_dir():
        raise SyncError(f"not a folder: {dest}")
    changes = _changes(source, ref, since)
    _require_clean_planning(dest)
    lines: list[str] = []
    for status, path in changes:
        target = dest / path
        if not path.startswith(f"{PLANNING}/") or not allow.allowed(path) or not _inside_planning(dest, target):
            lines.append(f"skip {path}")
        elif status in "MTD" and target.exists() and _edited_in_dest(source, since, path, dest, mapping):
            lines.append(f"conflict {path}")
        elif status == "A" and target.exists() and _committed(dest, path) != scrub_bytes(_git(source, "show", f"{ref}:{path}"), mapping):
            lines.append(f"conflict {path}")
        elif status in "AMT":
            data = _git(source, "show", f"{ref}:{path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(scrub_bytes(data, mapping))
            lines.append(f"{'M' if status == 'T' else status} {path}")
        elif status == "D":
            target.unlink(missing_ok=True)
            _prune_empty(target.parent, dest / PLANNING)
            lines.append(f"D {path}")
        else:
            lines.append(f"skip {path}")
    return lines


def _prune_empty(folder: Path, stop: Path) -> None:
    """Remove folder and its parents while they are empty, never `stop` itself."""
    stop = stop.resolve()
    while folder.is_dir() and stop in folder.resolve().parents and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Copy the scrubbed .planning/ delta between a tag and a ref into a tool checkout.")
    parser.add_argument("--source", type=Path, required=True, help="the private repository")
    parser.add_argument("--ref", required=True, help="the ref holding the newer planning files")
    parser.add_argument("--since", required=True, help="the ref the tool checkout was last brought to: the build tag for the first sync, then the --ref of the previous sync")
    parser.add_argument("--dest", type=Path, required=True, help="the tool checkout")
    parser.add_argument("--allow-list", type=Path, required=True, help="allow-list file")
    parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="folder to scrub from the text (repeatable)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        allow = load_allow_list(args.allow_list)
        mapping = parse_map(args.map)
        lines = sync(args.source, args.ref, args.since, args.dest, allow, mapping)
    except (OSError, ValueError, SyncError) as error:
        print(f"sync_planning: {error}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    conflicts = sum(1 for line in lines if line.startswith("conflict "))
    if conflicts:
        print(f"sync_planning: {conflicts} file(s) edited in the destination were left alone", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
