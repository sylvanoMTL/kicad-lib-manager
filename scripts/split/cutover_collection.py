#!/usr/bin/env python3
"""Make the collection's remove-code commit (Phase 16, D-01, D-07, D-21).

After the split the app code lives in sylvanoMTL/kicad-lib-manager and the collection keeps only
the Custom and WurthElektronik/KiCad-Library gitlinks, .gitmodules, .gitignore and its own README.md
and CLAUDE.md. This script turns today's repository into that, in one commit:

    git rm -r --cached downloaded_examples      (the vendor samples stay on disk, untracked)
    git rm -r <each REMOVE entry in the index>  (an explicit list, never "." or a KEEP path)
    write README.md, CLAUDE.md and .gitignore from scripts/split/collection/
    git add those three, git commit

It prints the plan and writes nothing unless --apply is given. Before any write, in both modes, it
refuses (exit 1) when the repository is not on main, has uncommitted tracked changes, lacks either
gitlink, or tracks a path outside the REMOVE, UNTRACK and KEEP lists. After the commit it checks that
the tree holds exactly the kept files, that both gitlinks kept their SHAs and that .gitmodules and the
remote URL are unchanged. It never runs git clean, git reset or git push, and deletes a leftover code
folder only when what is left in it is cache content.

Usage:
    python scripts/split/cutover_collection.py --repo DIR [--apply] [--message TEXT]

Exit codes: 0 done (or dry run shown), 1 refused or a check failed, 2 unusable input.
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Code and project files that leave the collection (top-level entries; README.md and CLAUDE.md are
# replaced from the templates in the same commit)
REMOVE = (
    "kicad_lib_manager",
    "kicad_lib_manager.py",
    "tests",
    "scripts",
    ".githooks",
    ".github",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    ".planning",
    "reports",
    "research_notes",
    ".gitattributes",
    "LICENSE",
    "README.md",
    "CLAUDE.md",
)
# Leave the index, stay on disk (licence-restricted vendor downloads)
UNTRACK = ("downloaded_examples",)
# What the collection tracks afterwards besides the written files: the two gitlinks, .gitmodules, .gitignore
KEEP = (".gitignore", ".gitmodules", "Custom", "WurthElektronik/KiCad-Library")
GITLINKS = ("Custom", "WurthElektronik/KiCad-Library")
# target file in the collection -> template under scripts/split/collection/
WRITE = {"README.md": "README.md", "CLAUDE.md": "CLAUDE.md", ".gitignore": "gitignore"}
CACHE_NAMES = ("__pycache__", ".pytest_cache")
DEFAULT_MESSAGE = "Remove the app code: the library manager now lives in sylvanoMTL/kicad-lib-manager"
BRANCH = "main"

TEMPLATES = Path(__file__).resolve().parent / "collection"
_GITLINK_MODE = "160000"


@dataclass
class CutoverPlan:
    repo: Path
    branch: str | None = None
    remove: dict[str, int] = field(default_factory=dict)  # REMOVE entry in the index -> tracked file count
    untrack: dict[str, int] = field(default_factory=dict)  # UNTRACK entry in the index -> tracked file count
    kept: list[str] = field(default_factory=list)  # tracked KEEP paths
    gitlinks: dict[str, str] = field(default_factory=dict)  # gitlink path -> SHA at HEAD
    gitmodules: bytes | None = None
    remote_url: str | None = None
    # the template files, read before anything is removed (they may live inside the folder that is about to be cleared)
    templates: dict[str, bytes] = field(default_factory=dict)
    # REMOVE folders that hold files the index does not track -> the ones that are not cache content
    leftovers: dict[str, list[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


# -- git ----------------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=env, timeout=600)


def _text(done: subprocess.CompletedProcess) -> str:
    return done.stdout.decode("utf-8", errors="replace")


def _error(done: subprocess.CompletedProcess) -> str:
    return (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()


def _index(repo: Path) -> list[tuple[str, str]] | None:
    """(mode, path) for every index entry, or None when git cannot answer."""
    done = _git(repo, "ls-files", "-s", "-z")
    if done.returncode != 0:
        return None
    found = []
    for item in done.stdout.decode("utf-8", errors="replace").split("\0"):
        if not item:
            continue
        meta, _, path = item.partition("\t")
        found.append((meta.split(" ")[0], path))
    return found


def _head_tree(repo: Path, *paths: str) -> dict[str, tuple[str, str]]:
    """path -> (mode, sha) for the given paths at HEAD."""
    done = _git(repo, "ls-tree", "HEAD", "--", *paths)
    return _parse_tree(_text(done)) if done.returncode == 0 else {}


def _head_files(repo: Path) -> dict[str, tuple[str, str]]:
    """path -> (mode, sha) for every entry of HEAD's tree, recursively."""
    done = _git(repo, "ls-tree", "-r", "HEAD")
    return _parse_tree(_text(done)) if done.returncode == 0 else {}


def _parse_tree(text: str) -> dict[str, tuple[str, str]]:
    found = {}
    for line in text.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split(" ")
        if len(parts) == 3 and path:
            found[path] = (parts[0], parts[2])
    return found


def _remote_url(repo: Path) -> str | None:
    done = _git(repo, "config", "--get", "remote.origin.url")
    return _text(done).strip() if done.returncode == 0 else None


# -- cache leftovers ----------------------------------------------------------------------------


def is_cache_path(rel: str) -> bool:
    """True for a file under a __pycache__ or .pytest_cache folder (rel is posix, from the repo root)."""
    return any(part in CACHE_NAMES for part in rel.split("/")[:-1])


def _disk_files(repo: Path, folder: str) -> list[str]:
    """Every file under repo/folder as a posix path from the repo root; a symlink counts as one file."""
    found = []
    for root, dirs, files in os.walk(repo / folder, followlinks=False):
        for name in list(dirs):
            if (Path(root) / name).is_symlink():
                dirs.remove(name)
                files.append(name)
        for name in files:
            found.append((Path(root) / name).relative_to(repo).as_posix())
    return sorted(found)


def _is_cache_leftover(repo: Path, rel: str) -> bool:
    return is_cache_path(rel) and not (repo / rel).is_symlink()


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_tree(folder: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(folder, onexc=_force_remove)
    else:
        shutil.rmtree(folder, onerror=_force_remove)


# -- plan ---------------------------------------------------------------------------------------


def _inside(path: Path, folder: Path) -> bool:
    """True when path is folder or lies under it (both resolved, so a link cannot hide it)."""
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
    except ValueError:
        return False
    return True


def plan(repo: Path) -> CutoverPlan:
    """What the cutover would do, and every reason it must not run. Writes nothing."""
    repo = Path(repo)
    result = CutoverPlan(repo=repo)
    problems = result.problems

    head = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    result.branch = _text(head).strip() if head.returncode == 0 else None
    if result.branch != BRANCH:
        problems.append(f"the repository is not on {BRANCH} (HEAD is {result.branch or 'detached'})")

    status = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        problems.append(f"git status failed: {_error(status)}")
    elif _text(status).strip():
        shown = "; ".join(line.strip() for line in _text(status).strip().splitlines()[:5])
        problems.append(f"uncommitted tracked changes: {shown}")

    entries = _index(repo)
    if entries is None:
        problems.append("git ls-files failed")
        entries = []
    tracked = {path for _, path in entries}
    for mode, path in entries:
        top = path.split("/", 1)[0]
        if any(path == keep or path.startswith(keep + "/") for keep in KEEP):
            result.kept.append(path)
        elif top in REMOVE:
            result.remove[top] = result.remove.get(top, 0) + 1
        elif top in UNTRACK:
            result.untrack[top] = result.untrack.get(top, 0) + 1
        else:
            problems.append(f"{path} is tracked but is outside the remove, untrack and keep lists")

    head_links = _head_tree(repo, *GITLINKS)
    for link in GITLINKS:
        found = head_links.get(link)
        if found is None or found[0] != _GITLINK_MODE:
            problems.append(f"no gitlink for {link} at HEAD")
        else:
            result.gitlinks[link] = found[1]
    if ".gitmodules" not in tracked:
        problems.append(".gitmodules is not tracked")
    try:
        result.gitmodules = (repo / ".gitmodules").read_bytes()
    except OSError:
        problems.append(".gitmodules cannot be read")
    result.remote_url = _remote_url(repo)

    if _inside(TEMPLATES, repo):
        problems.append(f"the templates ({TEMPLATES}) are inside the repository that is being cut over; run the script from the tool checkout")
    for target, template in WRITE.items():
        try:
            result.templates[target] = (TEMPLATES / template).read_bytes()
        except OSError:
            problems.append(f"the template {template} is missing or unreadable under {TEMPLATES}")

    for entry in REMOVE:
        folder = repo / entry
        if folder.is_dir() and not folder.is_symlink():
            extra = [rel for rel in _disk_files(repo, entry) if rel not in tracked]
            if extra:
                result.leftovers[entry] = [rel for rel in extra if not _is_cache_leftover(repo, rel)]
    return result


# -- apply --------------------------------------------------------------------------------------


def _print_way_back(repo: Path) -> None:
    print("cutover: stopped; nothing was pushed. Staged removals can be undone with:")
    print(f"cutover:   git -C {repo} reset -q && git -C {repo} checkout -- .")
    print("cutover: the pre-split bundle and tag restore the previous state if that is not enough.")


def _run(repo: Path, *args: str) -> bool:
    done = _git(repo, *args)
    if done.returncode != 0:
        print(f"cutover: git {' '.join(args[:3])} failed: {_error(done)}")
        _print_way_back(repo)
        return False
    return True


def _post_checks(repo: Path, before: CutoverPlan) -> list[str]:
    wrong = []
    expected = {*WRITE, ".gitmodules", *GITLINKS}
    tree = _head_files(repo)
    if set(tree) != expected:
        wrong.append(f"tree differs: extra {sorted(set(tree) - expected)}, missing {sorted(expected - set(tree))}")
    for link, sha in before.gitlinks.items():
        now = tree.get(link)
        if now is None or now[0] != _GITLINK_MODE or now[1] != sha:
            wrong.append(f"gitlink {link} was {sha} and is now {now[1] if now else 'absent'}")
    try:
        if (repo / ".gitmodules").read_bytes() != before.gitmodules:
            wrong.append(".gitmodules bytes changed")
    except OSError:
        wrong.append(".gitmodules cannot be read after the commit")
    if _remote_url(repo) != before.remote_url:
        wrong.append(f"remote.origin.url was {before.remote_url!r} and is now {_remote_url(repo)!r}")
    return wrong


def _clean_leftovers(repo: Path) -> None:
    """Remove REMOVE folders that hold only cache content; report the others and keep them."""
    for entry in REMOVE:
        folder = repo / entry
        if not folder.exists():
            continue
        if folder.is_symlink() or not folder.is_dir():
            print(f"cutover: leftover kept: {entry} is not a plain folder")
            continue
        others = [rel for rel in _disk_files(repo, entry) if not _is_cache_leftover(repo, rel)]
        if others:
            shown = ", ".join(others[:10]) + (f" and {len(others) - 10} more" if len(others) > 10 else "")
            print(f"cutover: leftover kept: {entry} still holds {shown}")
        else:
            _remove_tree(folder)
            print(f"cutover: leftover removed: {entry} (cache content only)")


def apply(repo: Path, plan_: CutoverPlan, message: str) -> int:
    """Run the plan: untrack, remove, write the templates, commit, check, then tidy cache leftovers."""
    repo = Path(repo)
    if plan_.problems:
        for problem in plan_.problems:
            print(f"cutover: refused: {problem}")
        return 1
    if plan_.untrack and not _run(repo, "rm", "-r", "-q", "--cached", "--", *plan_.untrack):
        return 1
    if plan_.remove and not _run(repo, "rm", "-r", "-q", "--", *plan_.remove):
        return 1
    for target in WRITE:
        try:
            (repo / target).write_bytes(plan_.templates[target])
        except OSError as error:
            print(f"cutover: cannot write {target}: {error}")
            _print_way_back(repo)
            return 1
    if not _run(repo, "add", "--", *WRITE):
        return 1
    if not _run(repo, "commit", "-q", "-m", message):
        return 1
    wrong = _post_checks(repo, plan_)
    if wrong:
        for line in wrong:
            print(f"cutover: CHECK FAILED: {line}")
        print("cutover: the commit exists locally; restore from the pre-split bundle or tag if this is wrong")
        return 1
    print(f"cutover: committed on {plan_.branch}: {message}")
    print("cutover: checked: tree, both gitlink SHAs, .gitmodules bytes and remote URL are unchanged")
    _clean_leftovers(repo)
    return 0


# -- command line -------------------------------------------------------------------------------


def _report(plan_: CutoverPlan, apply_: bool) -> None:
    mode = "apply" if apply_ else "dry run"
    print(f"cutover: {mode} on {plan_.repo} (branch {plan_.branch})")
    print("cutover: git rm -r (explicit list):")
    for entry in REMOVE:
        if entry in plan_.remove:
            print(f"  remove: {entry} ({plan_.remove[entry]} tracked files)")
    print("cutover: git rm -r --cached (the files stay on disk, untracked):")
    for entry, count in plan_.untrack.items():
        print(f"  untrack: {entry} ({count} tracked files)")
    print("cutover: written from the templates:")
    for target, template in WRITE.items():
        print(f"  write: {target} <- scripts/split/collection/{template}")
    print("cutover: kept as they are:")
    for link, sha in plan_.gitlinks.items():
        print(f"  gitlink: {link} {sha}")
    print("  kept: .gitmodules (bytes unchanged)")
    for entry, others in plan_.leftovers.items():
        if others:
            print(f"cutover: leftover that will stay: {entry} holds {', '.join(others[:10])}")
        else:
            print(f"cutover: leftover folder removed afterwards: {entry} (cache content only)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make the collection's remove-code commit (dry run unless --apply)")
    parser.add_argument("--repo", required=True, help="the top folder of the collection checkout")
    parser.add_argument("--apply", action="store_true", help="make the commit; without it the plan is only printed")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="the commit message")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"cutover: {repo} is not a folder")
        return 2
    try:
        top = _git(repo, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError) as error:
        print(f"cutover: git cannot run: {error}")
        return 2
    if top.returncode != 0:
        print(f"cutover: {repo} is not a git repository")
        return 2
    if not os.path.samefile(_text(top).strip(), repo):
        print(f"cutover: --repo must be the top folder of the repository ({_text(top).strip()})")
        return 2
    if not args.message.strip():
        print("cutover: --message must not be empty")
        return 2
    found = plan(repo)
    if found.problems:
        for problem in found.problems:
            print(f"cutover: refused: {problem}")
        print("cutover: nothing was written")
        return 1
    _report(found, args.apply)
    if not args.apply:
        print("cutover: dry run only, nothing was written; run again with --apply to make the commit")
        return 0
    return apply(repo, found, args.message)


if __name__ == "__main__":
    raise SystemExit(main())
