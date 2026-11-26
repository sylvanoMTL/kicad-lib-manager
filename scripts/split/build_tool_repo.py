#!/usr/bin/env python3
"""Build the public tool repository from a git ref of the private repository (Phase 16, D-02, D-05, D-13).

Steps, in order: refuse a destination that is not empty; resolve the ref; refuse an allowed gitlink;
export the tracked files of the ref that the allow-list names (git archive of the ref, never the
working tree, so untracked and ignored files cannot be swept in); scrub workstation paths in the
exported .planning/ text; check the result with verify_export; then git init on branch main, set the
local identity, core.hooksPath .githooks and core.autocrlf false, and make one commit.

The commit message keeps the Co-Authored-By trailer and carries no Claude-Session line or claude.ai
session URL (D-13): such lines in a given message are dropped here, and the tracked commit-msg hook
drops them in every later commit. This script never pushes and never talks to GitHub.

Usage:
    python scripts/split/build_tool_repo.py --source DIR --ref REF --dest DIR --allow-list FILE
        [--map OLD=NEW ...] --name NAME --email EMAIL [--message TEXT]

Exit codes: 0 built, 1 the export failed verification (the destination is cleaned up), 2 a refusal or
unusable input. Stdlib only; the script never imports the application package.
"""

import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from scrub import parse_map, scrub_tree
from verify_export import AllowList, export_files, load_allow_list, matches, verify

DEFAULT_MESSAGE = "Import the KiCad library manager\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"

# Assembled from pieces so this file never carries a session line of its own
_TRAILER = "Claude-" + "Session:"
_SESSION_URL = "claude.ai/" + "code/session"
_CHMOD_BATCH = 200


def _email_is_allowed(email: str) -> bool:
    """The pre-publish scan's own rule for a commit address (a noreply address or a reserved example domain)."""
    path = Path(__file__).resolve().parent.parent / "prepublish_scan.py"
    spec = importlib.util.spec_from_file_location("_prepublish_scan_for_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.is_allowed_email(email.strip())


class BuildError(Exception):
    """A refusal or failure; main() prints it and exits with `code`."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def _git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    """Run git in repo and return stdout; raise BuildError on a failure."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
            input=input,
            capture_output=True,
            check=False,
            stdin=None if input is not None else subprocess.DEVNULL,
        )
    except OSError as error:
        raise BuildError(f"cannot run git: {error}") from error
    if done.returncode != 0:
        reason = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise BuildError(f"git {args[0]} failed in {repo}: {reason[-1] if reason else 'no detail'}")
    return done.stdout


def clean_message(message: str) -> str:
    """The message without session-trailer lines and claude.ai session URL lines, ending in one newline."""
    # case-insensitive, like the commit-msg hook and the scan's session_trailer / session_url rules
    kept = [
        line
        for line in message.splitlines()
        if not line.lstrip().casefold().startswith(_TRAILER.casefold()) and _SESSION_URL not in line.casefold()
    ]
    return "\n".join(kept).rstrip("\n") + "\n"


def _tracked(source: Path, ref: str) -> list[tuple[str, str]]:
    """(mode, path) of every entry of the ref's tree."""
    raw = _git(source, "ls-tree", "-r", "-z", ref)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        head, _, path = record.decode("utf-8", errors="replace").partition("\t")
        entries.append((head.split()[0], path))
    return entries


def _safe_member_path(name: str) -> str:
    posix = PurePosixPath(name.replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts or (posix.parts and ":" in posix.parts[0]):
        raise BuildError(f"the archive holds an unsafe path: {name}")
    return posix.as_posix()


def _export(source: Path, ref: str, dest: Path, allow: AllowList, pathspecs: list[str]) -> tuple[list[str], list[str]]:
    """Write the allowed members of `git archive ref -- pathspecs` under dest; return (files, executable files)."""
    written: list[str] = []
    executable: list[str] = []
    dest_root = dest.resolve()
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(
            ["git", "-C", str(source), "archive", "--format=tar", ref, "--", *pathspecs],
            stdout=subprocess.PIPE,
            stderr=errors,
            stdin=subprocess.DEVNULL,
        )
        try:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
                for member in archive:
                    if member.isdir():
                        continue
                    if member.issym() or member.islnk() or not member.isfile():
                        raise BuildError(f"the archive holds a link or special file: {member.name}")
                    rel = _safe_member_path(member.name)
                    if not allow.allowed(rel):
                        continue
                    target = dest / rel
                    if dest_root not in target.resolve().parents:
                        raise BuildError(f"the archive holds a path outside the destination: {member.name}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
                    written.append(rel)
                    if member.mode & 0o111:
                        executable.append(rel)
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
            code = proc.wait()
        if code != 0:
            errors.seek(0)
            reason = errors.read().decode("utf-8", errors="replace").strip().splitlines()
            raise BuildError(f"git archive failed: {reason[-1] if reason else 'no detail'}")
    return sorted(written), sorted(executable)


def _force_remove(func, path, _error) -> None:
    """rmtree error handler: git's object files are read-only on Windows, so make them writable and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _rmtree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_remove)
    else:
        shutil.rmtree(path, onerror=_force_remove)


def _clear(dest: Path, created: bool) -> None:
    """Remove what a failed build wrote (the destination was empty or absent when it started)."""
    if created:
        _rmtree(dest)
        return
    for child in dest.iterdir():
        if child.is_dir():
            _rmtree(child)
        else:
            child.unlink(missing_ok=True)


def build(
    source: Path,
    ref: str,
    dest: Path,
    allow: AllowList,
    *,
    mapping: list[tuple[str, str]],
    name: str,
    email: str,
    message: str = DEFAULT_MESSAGE,
    allow_any_email: bool = False,
) -> list[str]:
    """Export, scrub, verify and commit the tool repository in dest; return summary lines.

    The email goes into the first public commit, so it must pass the scan's own address rule
    (a noreply address or a reserved example domain) unless allow_any_email is set.
    """
    source, dest = Path(source), Path(dest)
    if not allow_any_email and not _email_is_allowed(email):
        raise BuildError(
            "the commit email is not a noreply address (GitHub's id+name@users.noreply.github.com form is expected); "
            "pass --allow-any-email to use it anyway"
        )
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise BuildError(f"destination is not empty: {dest}")
    try:
        _git(source, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except BuildError as error:
        raise BuildError(f"unknown ref in {source}: {ref}") from error

    entries = _tracked(source, ref)
    for mode, path in entries:
        if mode == "160000" and (allow.allowed(path) or allow.allowed(path + "/x")):
            raise BuildError(f"an allowed path is a gitlink (submodule), not a file tree: {path}")
    paths = [path for mode, path in entries if mode != "160000"]
    pathspecs = [entry for entry in allow.includes if any(matches(path, entry) for path in paths)]
    if not pathspecs:
        raise BuildError(f"no allow-listed path exists in {ref}")

    created = not dest.exists()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        files, executable = _export(source, ref, dest, allow, pathspecs)
        scrub_tree(dest, [".planning"], mapping)
        problems = verify(dest, allow)
        if problems:
            raise BuildError("the export failed verification:\n" + "\n".join(problems), code=1)
        sha = _commit(dest, files, executable, name, email, message)
    except BuildError:
        _clear(dest, created)
        raise
    except OSError as error:
        _clear(dest, created)
        raise BuildError(f"cannot write the export: {error}") from error

    counts: dict[str, int] = {}
    for rel in files:
        top = rel.split("/", 1)[0]
        counts[top] = counts.get(top, 0) + 1
    lines = [f"exported {len(files)} files from {ref} into {dest}"]
    lines += [f"  {top}: {count}" for top, count in sorted(counts.items())]
    lines.append(f"committed {sha[:12]} on main")
    return lines


def _commit(dest: Path, files: list[str], executable: list[str], name: str, email: str, message: str) -> str:
    """git init, local config, add everything, mark the executables, one commit; return the commit id."""
    _git(dest, "init", "-q", "-b", "main")
    for key, value in (
        ("user.name", name),
        ("user.email", email),
        ("core.hooksPath", ".githooks"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        _git(dest, "config", key, value)
    _git(dest, "add", "-A")
    tracked = set(_git(dest, "ls-files", "-z").decode("utf-8", errors="replace").split("\0")) - {""}
    left_out = sorted(set(export_files(dest)) - tracked)
    if left_out:
        raise BuildError("files not committed (ignored by the exported .gitignore?): " + ", ".join(left_out))
    for start in range(0, len(executable), _CHMOD_BATCH):
        _git(dest, "update-index", "--chmod=+x", "--", *executable[start : start + _CHMOD_BATCH])
    _git(dest, "commit", "-q", "-F", "-", input=clean_message(message).encode("utf-8"))
    return _git(dest, "rev-parse", "HEAD").decode("ascii").strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the tool repository from an allow-listed export of a git ref.")
    parser.add_argument("--source", type=Path, required=True, help="the private repository")
    parser.add_argument("--ref", required=True, help="the ref (tag or commit) to export")
    parser.add_argument("--dest", type=Path, required=True, help="the new repository folder (absent or empty)")
    parser.add_argument("--allow-list", type=Path, required=True, help="allow-list file")
    parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="folder to scrub from .planning text (repeatable)")
    parser.add_argument("--name", required=True, help="commit author and committer name")
    parser.add_argument("--email", required=True, help="commit author and committer email")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="first commit message")
    parser.add_argument("--allow-any-email", action="store_true", help="accept an email the pre-publish scan would not allow-list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        allow = load_allow_list(args.allow_list)
        mapping = parse_map(args.map)
        lines = build(
            args.source,
            args.ref,
            args.dest,
            allow,
            mapping=mapping,
            name=args.name,
            email=args.email,
            message=args.message,
            allow_any_email=args.allow_any_email,
        )
    except (OSError, ValueError) as error:
        print(f"build_tool_repo: {error}", file=sys.stderr)
        return 2
    except BuildError as error:
        print(f"build_tool_repo: {error}", file=sys.stderr)
        return error.code
    for line in lines:
        print(line)
    print("build_tool_repo: next, in the new clone: git config prepublish.denyTermsFile <your deny-terms file>, so the push scan knows your names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
