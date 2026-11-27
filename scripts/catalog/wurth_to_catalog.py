#!/usr/bin/env python3
"""Remove the WurthElektronik submodule once Wurth is a catalog entry (Phase 17, CAT-12, D-24..D-27, D-30).

The owner first adds Wurth through the app's Library Catalog (a clone in ThirdParty/WurthElektronik, the
WE_3DMODEL_DIR question answered, ThirdParty/ in .gitignore, catalog.json written) and runs Generate Tables. This
script then turns the collection into the catalog layout in one commit:

    git bundle create <backup>/pre-wurth.bundle --all    (and git bundle verify)
    git tag <rollback tag>                               (lightweight, at HEAD)
    git submodule deinit -f -- WurthElektronik/KiCad-Library
    git rm -f -- WurthElektronik/KiCad-Library           (drops the gitlink and the .gitmodules section)
    remove the empty WurthElektronik folder
    move .git/modules/WurthElektronik to <backup>/wurth-modules     (moved, never deleted, D-27)
    write README.md and CLAUDE.md from scripts/catalog/collection/
    git add .gitignore catalog.json .gitmodules README.md CLAUDE.md, then one commit with --message

It prints the plan and writes nothing unless --apply is given. Before any write, in both modes, it refuses
(exit 1) unless: the repository is the collection's top folder on main; the only uncommitted tracked changes are
.gitignore, catalog.json, README.md and CLAUDE.md (and no other file is untracked and unignored); the index and
.gitmodules show the WurthElektronik/KiCad-Library gitlink and Custom; catalog.json has the WurthElektronik entry
whose ThirdParty folder has its own .git folder and an understood .git/config; ThirdParty is ignored; the rollback
tag does not exist; KiCad is not running; the newest KiCad config sets WE_3DMODEL_DIR to
<repo>/ThirdParty/WurthElektronik/3dmodels with forward slashes; the backup folder is outside the repository and
outside every git work tree and holds neither pre-wurth.bundle nor wurth-modules; and the three D-26 checks hold:
(1) the --before snapshot, with the Wurth paths moved to ThirdParty/WurthElektronik, compares identical to the
--after snapshot (uri_diff.compare); (2) the --after snapshot lists no missing entry; (3) every 3D model path the
catalog variable points at exists in the clone (catalog.validate.unresolved_models).

After the commit it checks that git submodule status lists only Custom at its previous commit, .gitmodules has no
Wurth section, nothing under WurthElektronik/ is tracked, catalog.json is tracked, git status is empty and
ThirdParty is ignored. It prints the way back (also in the dry run). For every older KiCad config folder that still
sets WE_3DMODEL_DIR it prints one line with the old and the new value; it never writes KiCad's files (D-30). It runs
only local git commands (the allow-list ALLOWED_GIT): no git clean, git push, git submodule update --remote or any
network command, and it never changes Custom.

Rehearsal (D-25): first run it on a `git clone --no-local` copy of the collection with --config-dir naming a scratch
KiCad config folder (the folder that holds the version folders such as 10.0), then on the checkout KiCad reads.

Usage:
    python scripts/catalog/wurth_to_catalog.py --repo DIR --before FILE --after FILE [--config-dir DIR]
        [--backup-dir DIR] [--rollback-tag NAME] [--apply --backup-dir DIR --message TEXT]

--before and --after are scripts/split/uri_diff.py snapshots taken before the Add and after Generate Tables.

Exit codes: 0 done (or dry run shown), 1 refused or a check failed, 2 unusable input.
"""

import argparse
import copy
import difflib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The app modules ship in the same repository as this script
TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from kicad_lib_manager.catalog import gitnet, manifest, validate  # noqa: E402
from kicad_lib_manager.kicad_process import kicad_running  # noqa: E402
from kicad_lib_manager.library_scanner import newest_version_dirs  # noqa: E402


def _load_uri_diff():
    path = TOOL_ROOT / "scripts" / "split" / "uri_diff.py"
    spec = importlib.util.spec_from_file_location("wurth_uri_diff", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wurth_uri_diff"] = module
    spec.loader.exec_module(module)
    return module


uri_diff = _load_uri_diff()

WURTH_ID = "WurthElektronik"
OLD_PATH = "WurthElektronik/KiCad-Library"
NEW_PATH = f"ThirdParty/{WURTH_ID}"
VAR = "WE_3DMODEL_DIR"
DEFAULT_TAG = "pre-wurth-catalog"
BRANCH = "main"
BUNDLE_NAME = "pre-wurth.bundle"
MODULES_NAME = "wurth-modules"
# The tracked files the owner or the app may have changed; README.md and CLAUDE.md are replaced from the templates
ALLOWED_DIRTY = (".gitignore", "catalog.json", "README.md", "CLAUDE.md")
DOCS = ("README.md", "CLAUDE.md")
STAGED = (".gitignore", "catalog.json", ".gitmodules", "README.md", "CLAUDE.md")
TEMPLATES = Path(__file__).resolve().parent / "collection"
PREFIX = "wurth_to_catalog:"

# The only git commands this script can start: local ones. The one place that starts git (_git) refuses the rest.
ALLOWED_GIT = frozenset(
    {
        "rev-parse", "symbolic-ref", "status", "ls-files", "ls-tree", "config", "bundle", "tag", "submodule", "rm",
        "add", "commit", "check-ignore", "check-ref-format", "cat-file",
    }
)
_SUBMODULE_COMMANDS = frozenset({"deinit", "status"})
_GITLINK_MODE = "160000"

_ROOT = r"(<LIB>/|\$\{KICAD_LIB_GITHUB\}/|\$\(KICAD_LIB_GITHUB\)/)"
_OLD_RE = re.compile(_ROOT + re.escape(OLD_PATH) + r"(?=/|$)")
_NEW_RE = re.compile(_ROOT + re.escape(NEW_PATH) + r"(?=/|$)")


@dataclass
class ConversionPlan:
    repo: Path | None = None
    branch: str | None = None
    head: str = ""
    custom_commit: str = ""
    module_dir: Path | None = None
    clone: Path | None = None
    new_value: str = ""
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # what the checks found, shown by the report
    steps: list[str] = field(default_factory=list)
    docs: dict[str, list[str]] = field(default_factory=dict)  # doc name -> unified diff against the template
    stale_lines: list[str] = field(default_factory=list)
    templates: dict[str, bytes] = field(default_factory=dict)


# -- git ----------------------------------------------------------------------------------------


def _git(repo: Path, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run one local git command in repo; a command outside ALLOWED_GIT is refused before anything starts."""
    if not args or args[0] not in ALLOWED_GIT or "--remote" in args:
        raise ValueError(f"git {' '.join(args[:2])} is not a command this script may run")
    if args[0] == "submodule" and (len(args) < 2 or args[1] not in _SUBMODULE_COMMANDS):
        raise ValueError(f"git {' '.join(args[:2])} is not a command this script may run")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, b"", f"git timed out after {timeout} s".encode())


def _text(done: subprocess.CompletedProcess) -> str:
    return done.stdout.decode("utf-8", errors="replace")


def _error(done: subprocess.CompletedProcess) -> str:
    return (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()


def _index(repo: Path) -> list[tuple[str, str, str]] | None:
    """(mode, sha, path) for every index entry, or None when git cannot answer."""
    done = _git(repo, "ls-files", "-s", "-z")
    if done.returncode != 0:
        return None
    found = []
    for item in _text(done).split("\0"):
        if not item:
            continue
        meta, _, path = item.partition("\t")
        parts = meta.split(" ")
        found.append((parts[0], parts[1] if len(parts) > 1 else "", path))
    return found


def _status(repo: Path, *, untracked: bool) -> list[tuple[str, str]] | None:
    """(XY, path) for every entry of git status; the untracked ones only when asked."""
    done = _git(repo, "status", "--porcelain", "-z", "--untracked-files=" + ("normal" if untracked else "no"))
    if done.returncode != 0:
        return None
    items = _text(done).split("\0")
    found = []
    i = 0
    while i < len(items):
        item = items[i]
        i += 1
        if not item:
            continue
        code, path = item[:2], item[3:]
        if "R" in code or "C" in code:
            i += 1  # the original path follows
        found.append((code, path))
    return found


def _gitmodules(repo: Path) -> dict[str, str] | None:
    """Submodule name -> path from .gitmodules, or None when it cannot be read."""
    done = _git(repo, "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$")
    if done.returncode not in (0, 1):
        return None
    found = {}
    for line in _text(done).splitlines():
        match = re.match(r"^submodule\.(.+)\.path (.+)$", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


# -- tree removal and move ----------------------------------------------------------------------


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_tree(folder: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(folder, onexc=_force_remove)
    else:
        shutil.rmtree(folder, onerror=_force_remove)


def _move_tree(source: Path, target: Path) -> str | None:
    """Move a folder; a rename first (same drive), else copy and remove. An error text, or None when it worked."""
    try:
        os.rename(source, target)
        return None
    except OSError:
        pass
    try:
        shutil.copytree(source, target)
        _remove_tree(source)
    except (OSError, shutil.Error) as error:
        return str(error)
    return None


def _inside(path: Path, folder: Path) -> bool:
    """True when path is folder or lies under it (both resolved, so a link cannot hide it)."""
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
    except ValueError:
        return False
    return True


# -- the pure helpers ---------------------------------------------------------------------------


def rewrite_snapshot(snap: dict) -> dict:
    """A copy of a uri_diff snapshot with the old Wurth folder replaced by ThirdParty/WurthElektronik in every
    string field of every entry (the root may be written <LIB> or ${KICAD_LIB_GITHUB}); nothing else changes."""
    result = copy.deepcopy(snap)
    for row in result.get("entries", []):
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = _OLD_RE.sub(lambda m: m.group(1) + NEW_PATH, value)
    return result


def stale_var_lines(config_base: Path, new_value: str) -> list[str]:
    """One line per KiCad config folder whose kicad_common.json sets WE_3DMODEL_DIR to something else (D-30).

    Read only: the files are never written.
    """
    lines = []
    for folder in newest_version_dirs(Path(config_base)):
        value = uri_diff.read_vars(folder).get(VAR)
        if value is None or value == new_value:
            continue
        lines.append(
            f"KiCad {folder.name} still sets {VAR} to {value}; set it to {new_value} in KiCad {folder.name} "
            "under Preferences > Configure Paths (this script never edits KiCad's settings)"
        )
    return lines


def doc_diff(old: str, new: str, name: str) -> list[str]:
    """The unified diff from the collection's current doc to the template; empty when they match line for line."""
    return list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), fromfile=f"a/{name}", tofile=f"b/{name} (template)", lineterm=""
        )
    )


def way_back(repo: Path, module_dir: Path, backup_dir: Path, tag: str, *, include_move: bool) -> list[tuple]:
    """The steps that undo the conversion: ("move", from, to) and ("git", *args), run in the repository."""
    steps: list[tuple] = []
    if include_move:
        steps.append(("move", Path(backup_dir) / MODULES_NAME, Path(module_dir)))
    steps.append(("git", "checkout", tag, "--", ".gitmodules", ".gitignore", *DOCS, OLD_PATH))
    steps.append(("git", "submodule", "update", "--init", "--", OLD_PATH))
    return steps


def _default_config_base() -> Path | None:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "kicad" if appdata else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "kicad"
    return Path.home() / ".config" / "kicad"


def _same_value(a: str, b: str) -> bool:
    return a.lower() == b.lower() if sys.platform == "win32" else a == b


def _shown(items: list[str], limit: int = 5) -> str:
    text = "; ".join(items[:limit])
    return text + (f"; and {len(items) - limit} more" if len(items) > limit else "")


# -- plan ---------------------------------------------------------------------------------------


def _check_repository(repo: Path, tag: str, result: ConversionPlan) -> None:
    problems = result.problems
    head = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    result.branch = _text(head).strip() if head.returncode == 0 else None
    if result.branch != BRANCH:
        problems.append(f"the repository is not on {BRANCH} (HEAD is {result.branch or 'detached'})")
    now = _git(repo, "rev-parse", "--verify", "-q", "HEAD")
    result.head = _text(now).strip() if now.returncode == 0 else ""

    if _git(repo, "check-ref-format", f"refs/tags/{tag}").returncode != 0:
        problems.append(f"{tag} is not a usable tag name")
    elif _git(repo, "rev-parse", "--verify", "-q", f"refs/tags/{tag}").returncode == 0:
        problems.append(f"the rollback tag {tag} already exists; choose another name with --rollback-tag")

    tracked = _status(repo, untracked=False)
    if tracked is None:
        problems.append("git status failed")
    else:
        unexpected = [path for _, path in tracked if path not in ALLOWED_DIRTY]
        if unexpected:
            problems.append(f"uncommitted tracked changes: {_shown(unexpected)}")
    both = _status(repo, untracked=True)
    if both is not None:
        stray = [path for code, path in both if code == "??" and path not in ALLOWED_DIRTY]
        if stray:
            problems.append(
                f"untracked files that git status would still show after the conversion: {_shown(stray)}; "
                "commit, move or ignore them first"
            )

    entries = _index(repo)
    if entries is None:
        problems.append("git ls-files failed")
        entries = []
    links = {path: sha for mode, sha, path in entries if mode == _GITLINK_MODE}
    for link in (OLD_PATH, "Custom"):
        if link not in links:
            problems.append(f"no gitlink for {link} in the index")
    result.custom_commit = links.get("Custom", "")
    if not any(path == ".gitmodules" for _, _, path in entries):
        problems.append(".gitmodules is not tracked")
    names = _gitmodules(repo)
    if names is None:
        problems.append(".gitmodules cannot be read")
        return
    wurth_names = [name for name, path in names.items() if path == OLD_PATH]
    if not wurth_names:
        problems.append(f".gitmodules has no section for {OLD_PATH}")
        return
    top = wurth_names[0].split("/", 1)[0]
    custom_names = [name for name, path in names.items() if path == "Custom"]
    if any(name.split("/", 1)[0] == top for name in custom_names):
        problems.append(f"the module data of Custom and {OLD_PATH} share the folder modules/{top}; it cannot be moved")
    git_dir = _git(repo, "rev-parse", "--absolute-git-dir")
    if git_dir.returncode != 0:
        problems.append("git rev-parse --absolute-git-dir failed")
        return
    result.module_dir = Path(_text(git_dir).strip()) / "modules" / top
    if not result.module_dir.is_dir():
        problems.append(f"the module data {result.module_dir} is not a folder (is the submodule initialised?)")


def _check_catalog(repo: Path, result: ConversionPlan) -> manifest.CatalogEntry | None:
    problems = result.problems
    loaded = manifest.load(repo)
    if isinstance(loaded, manifest.Issue):
        problems.append(f"catalog.json cannot be used: {loaded.text}")
        return None
    entry = loaded.find(WURTH_ID)
    if entry is None:
        problems.append(f"catalog.json has no {WURTH_ID} entry; add Wurth through the app's Library Catalog first")
        return None
    clone = manifest.entry_folder(repo, entry)
    result.clone = clone
    if not clone.is_dir():
        problems.append(f"the catalog folder {clone} does not exist")
        return entry
    if not (clone / ".git").is_dir():
        problems.append(f"{clone} has no .git folder of its own")
    else:
        odd = gitnet.config_problems(clone)
        if odd:
            problems.append(f"unexpected git settings in {WURTH_ID}: {_shown(odd)}")
    if VAR not in entry.vars:
        problems.append(f"the {WURTH_ID} entry of catalog.json sets no {VAR}")
    else:
        result.new_value = manifest.path_vars(repo, [entry]).get(VAR, "")
        if not result.new_value:
            problems.append(f"the {VAR} of catalog.json is not a usable folder")
    return entry


def _check_kicad(config_dir: Path | None, result: ConversionPlan) -> None:
    problems = result.problems
    running = kicad_running()
    if running:
        problems.append(f"KiCad is running ({', '.join(running)}); close it first")
    base = Path(config_dir) if config_dir is not None else _default_config_base()
    versions = newest_version_dirs(base) if base is not None else []
    if not versions:
        problems.append(f"no KiCad configuration folder found under {base}; pass --config-dir")
        return
    if not result.new_value:
        return
    value = uri_diff.read_vars(versions[0]).get(VAR)
    if value is None or not _same_value(value, result.new_value):
        problems.append(
            f"{VAR} in KiCad {versions[0].name} is {value if value is not None else 'not set'}, "
            f"not {result.new_value} (use forward slashes; set it through the catalog's path variable question)"
        )
    result.stale_lines = stale_var_lines(base, result.new_value)


def _entry_rows(snap, pattern) -> list[dict]:
    return [
        row for row in snap.get("entries", [])
        if isinstance(row, dict) and any(isinstance(row.get(k), str) and pattern.search(row[k]) for k in ("uri", "resolved"))
    ]


def _check_snapshots(before: dict, after: dict, entry, result: ConversionPlan) -> None:
    problems = result.problems
    old_rows, new_rows = _entry_rows(before, _OLD_RE), _entry_rows(after, _NEW_RE)
    if not old_rows:
        problems.append(f"the before snapshot holds no entry under {OLD_PATH}; take it before the Add")
    if not new_rows:
        problems.append(f"the after snapshot holds no entry under {NEW_PATH}; take it after Generate Tables")
    # check 1: the same nicknames, only the Wurth paths moved, nothing missing
    differences = uri_diff.compare(rewrite_snapshot(before), after)
    if differences:
        problems.append(
            f"check 1 failed: the before and after snapshots differ after the Wurth paths are moved "
            f"({len(differences)} differences): {_shown(differences)}"
        )
    # check 2: no enabled entry of the after snapshot is missing
    missing = [
        f"{row.get('table')} {row.get('name')} -> {row.get('resolved')}"
        for row in after.get("entries", [])
        if isinstance(row, dict) and row.get("expanded") and not row.get("exists") and not row.get("disabled")
    ]
    if missing:
        problems.append(f"check 2 failed: the after snapshot lists {len(missing)} missing libraries: {_shown(missing)}")
    for row in after.get("entries", []):
        if isinstance(row, dict) and row.get("expanded") and not row.get("exists") and row.get("disabled"):
            result.notes.append(f"note: disabled, file not found: {row.get('table')} {row.get('name')} -> {row.get('resolved')}")
    result.notes.append(
        f"snapshots: {len(old_rows)} entries under {OLD_PATH} before, {len(new_rows)} under {NEW_PATH} after; "
        f"check 1 (same libraries, only the Wurth paths moved) and check 2 (none missing) "
        f"{'failed' if differences or missing else 'passed'}"
    )
    # check 3: the model paths of the clone resolve with the catalog's variable
    if entry is not None and result.clone is not None and result.clone.is_dir():
        unresolved = validate.unresolved_models(result.clone, entry.vars)
        if unresolved:
            problems.append(
                f"check 3 failed: {len(unresolved)} 3D model paths of the {NEW_PATH} footprints do not exist in the clone: "
                f"{_shown(unresolved)}"
            )
        else:
            result.notes.append("check 3 passed: every 3D model path the catalog variable points at exists in the clone")


def _check_backup(repo: Path, backup_dir: Path | None, result: ConversionPlan) -> None:
    if backup_dir is None:
        return
    problems = result.problems
    backup = Path(backup_dir)
    if _inside(backup, repo):
        problems.append(f"the backup folder {backup} is inside the repository")
        return
    ancestor = backup
    while not ancestor.exists() and ancestor.parent != ancestor:
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        problems.append(f"{ancestor} is not a folder, so the backup folder {backup} cannot be made")
        return
    probe = _git(ancestor, "rev-parse", "--show-toplevel")
    if probe.returncode == 0:
        problems.append(f"the backup folder {backup} is inside the git work tree {_text(probe).strip()}; use a folder outside every repository")
    for name in (BUNDLE_NAME, MODULES_NAME):
        if (backup / name).exists():
            problems.append(f"{backup / name} already exists; the backup folder must not hold an earlier conversion")


def _check_templates(repo: Path, result: ConversionPlan) -> None:
    problems = result.problems
    if _inside(TEMPLATES, repo):
        problems.append(f"the templates ({TEMPLATES}) are inside the repository being converted; run the script from the tool checkout")
        return
    for name in DOCS:
        try:
            data = (TEMPLATES / name).read_bytes()
        except OSError:
            problems.append(f"the template {name} is missing or unreadable under {TEMPLATES}")
            continue
        result.templates[name] = data
        try:
            current = (repo / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            current = ""
        result.docs[name] = doc_diff(current, data.decode("utf-8", errors="replace"), name)


def _steps(repo: Path, result: ConversionPlan, backup_dir: Path | None, tag: str) -> list[str]:
    backup = Path(backup_dir) if backup_dir is not None else Path("<backup folder>")
    return [
        f"git bundle create {backup / BUNDLE_NAME} --all",
        f"git bundle verify {backup / BUNDLE_NAME}",
        f"git tag {tag}   (lightweight, at {result.head[:12]})",
        f"git submodule deinit -f -- {OLD_PATH}",
        f"git rm -f -- {OLD_PATH}   (removes the gitlink, its files and the .gitmodules section)",
        "remove the empty WurthElektronik folder",
        f"move the module data {result.module_dir} to {backup / MODULES_NAME}",
        f"write README.md and CLAUDE.md from {TEMPLATES}",
        f"git add -- {' '.join(STAGED)}",
        "git commit with --message",
    ]


def plan(
    repo: Path,
    before: dict,
    after: dict,
    *,
    config_dir: Path | None = None,
    backup_dir: Path | None = None,
    tag: str = DEFAULT_TAG,
) -> ConversionPlan:
    """What the conversion would do, and every reason it must not run. Writes nothing."""
    repo = Path(repo)
    result = ConversionPlan(repo=repo)
    _check_repository(repo, tag, result)
    entry = _check_catalog(repo, result)
    _check_kicad(config_dir, result)
    _check_snapshots(before, after, entry, result)
    if _git(repo, "check-ignore", "-q", "ThirdParty").returncode != 0:
        result.problems.append(
            "ThirdParty is not ignored; add the line ThirdParty/ to .gitignore (the app writes it with the first catalog download)"
        )
    _check_backup(repo, backup_dir, result)
    _check_templates(repo, result)
    result.steps = _steps(repo, result, backup_dir, tag)
    return result


# -- apply --------------------------------------------------------------------------------------


def _print_way_back(repo: Path, plan_: ConversionPlan, backup_dir: Path | None, tag: str, *, include_move: bool = True) -> None:
    backup = Path(backup_dir) if backup_dir is not None else Path("<backup folder>")
    module_dir = plan_.module_dir if plan_.module_dir is not None else Path(repo) / ".git" / "modules" / "<module folder>"
    print(f"{PREFIX} the way back (nothing here runs by itself; close KiCad first):")
    number = 1
    for step in way_back(repo, module_dir, backup, tag, include_move=include_move):
        if step[0] == "move":
            print(f"{PREFIX}   {number}. move {step[1]} {step[2]}")
        else:
            note = "   (no download: the objects are local)" if step[1] == "submodule" else ""
            print(f"{PREFIX}   {number}. git -C {repo} {' '.join(step[1:])}{note}")
        number += 1
    print(f"{PREFIX}   {number}. commit the restored files in {repo}")
    print(f"{PREFIX}   {number + 1}. restore kicad_common.json from the app's backup folder (kicad_common/<version>/kicad_common.json_backup_N)")
    print(f"{PREFIX}      or set {VAR} back in KiCad under Preferences > Configure Paths")
    print(f"{PREFIX}   {number + 2}. File > Restore Backup (Ctrl+R) in the app restores the previous library tables")
    print(f"{PREFIX}   last resort: {Path(backup) / BUNDLE_NAME} holds every ref of the repository (git clone it)")


def _run(repo: Path, plan_: ConversionPlan, backup: Path, tag: str, *args: str, changed: bool = True, timeout: int = 600) -> bool:
    done = _git(repo, *args, timeout=timeout)
    if done.returncode != 0:
        print(f"{PREFIX} git {' '.join(args[:3])} failed: {_error(done)}")
        _stop(repo, plan_, backup, tag, changed=changed)
        return False
    return True


def _stop(repo: Path, plan_: ConversionPlan, backup: Path, tag: str, *, changed: bool = True) -> None:
    if not changed:
        print(f"{PREFIX} stopped before any change to the repository; nothing needs undoing")
        return
    print(f"{PREFIX} stopped at the step above; no later step ran and nothing was pushed")
    _print_way_back(repo, plan_, backup, tag, include_move=(backup / MODULES_NAME).exists())


def _post_checks(repo: Path, plan_: ConversionPlan) -> list[str]:
    wrong = []
    status = _git(repo, "submodule", "status")
    listed = [m.group(1) for m in re.finditer(r"^[ +\-U]?[0-9a-f]+ (\S+)", _text(status), re.MULTILINE)]
    if status.returncode != 0 or listed != ["Custom"]:
        wrong.append(f"git submodule status lists {listed}, expected only Custom")
    links = {path: sha for mode, sha, path in (_index(repo) or []) if mode == _GITLINK_MODE}
    if links.get("Custom") != plan_.custom_commit:
        wrong.append(f"the Custom gitlink was {plan_.custom_commit} and is now {links.get('Custom')}")
    try:
        text = (repo / ".gitmodules").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
        wrong.append(".gitmodules cannot be read after the commit")
    if "WurthElektronik" in text:
        wrong.append(".gitmodules still has a Wurth section")
    left = _text(_git(repo, "ls-files", "--", "WurthElektronik")).split()
    if left:
        wrong.append(f"still tracked under WurthElektronik/: {_shown(left)}")
    if _git(repo, "ls-files", "--error-unmatch", "catalog.json").returncode != 0:
        wrong.append("catalog.json is not tracked")
    dirty = _text(_git(repo, "status", "--porcelain")).strip()
    if dirty:
        wrong.append(f"git status is not empty: {_shown(dirty.splitlines())}")
    if _git(repo, "check-ignore", "-q", "ThirdParty").returncode != 0:
        wrong.append("ThirdParty is not ignored")
    return wrong


def apply(repo: Path, plan_: ConversionPlan, *, backup_dir: Path, tag: str, message: str) -> int:
    """Run the plan in the fixed order, stopping at the first failure with the way back printed."""
    repo, backup = Path(repo), Path(backup_dir)
    if plan_.problems:
        for problem in plan_.problems:
            print(f"{PREFIX} refused: {problem}")
        return 1
    bundle, moved = backup / BUNDLE_NAME, backup / MODULES_NAME
    try:
        backup.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"{PREFIX} cannot make the backup folder {backup}: {error}")
        return 1
    if not _run(repo, plan_, backup, tag, "bundle", "create", str(bundle), "--all", changed=False, timeout=1800):
        return 1
    if not _run(repo, plan_, backup, tag, "bundle", "verify", str(bundle), changed=False, timeout=1800):
        return 1
    print(f"{PREFIX} bundle written and verified: {bundle}")
    if not _run(repo, plan_, backup, tag, "tag", tag):
        return 1
    print(f"{PREFIX} rollback tag {tag} set at {plan_.head}")
    if not _run(repo, plan_, backup, tag, "submodule", "deinit", "-f", "--", OLD_PATH):
        return 1
    if not _run(repo, plan_, backup, tag, "rm", "-f", "-q", "--", OLD_PATH, timeout=3600):
        return 1
    print(f"{PREFIX} removed the gitlink {OLD_PATH} and its .gitmodules section")
    leftover = repo / "WurthElektronik"
    if leftover.is_dir() and not leftover.is_symlink():
        try:
            leftover.rmdir()
            print(f"{PREFIX} removed the empty folder {leftover}")
        except OSError:
            print(f"{PREFIX} left {leftover} in place: it is not empty")
    error = _move_tree(plan_.module_dir, moved)
    if error is not None:
        print(f"{PREFIX} cannot move the module data {plan_.module_dir} to {moved}: {error}")
        _stop(repo, plan_, backup, tag)
        return 1
    print(f"{PREFIX} moved the module data to {moved} (delete it by hand later)")
    for name in DOCS:
        try:
            (repo / name).write_bytes(plan_.templates[name])
        except OSError as error:
            print(f"{PREFIX} cannot write {name}: {error}")
            _stop(repo, plan_, backup, tag)
            return 1
    if not _run(repo, plan_, backup, tag, "add", "--", *STAGED):
        return 1
    if not _run(repo, plan_, backup, tag, "commit", "-q", "-m", message):
        return 1
    wrong = _post_checks(repo, plan_)
    if wrong:
        for line in wrong:
            print(f"{PREFIX} CHECK FAILED: {line}")
        print(f"{PREFIX} the commit exists locally and nothing was pushed; undo it with the way back below if this is wrong")
        _print_way_back(repo, plan_, backup, tag)
        return 1
    print(f"{PREFIX} committed on {plan_.branch}: {message}")
    print(
        f"{PREFIX} checked: only Custom is a submodule (unchanged), .gitmodules has no Wurth section, nothing under "
        f"WurthElektronik/ is tracked, catalog.json is tracked, git status is empty, ThirdParty is ignored"
    )
    for line in plan_.stale_lines:
        print(f"{PREFIX} {line}")
    _print_way_back(repo, plan_, backup, tag)
    return 0


# -- command line -------------------------------------------------------------------------------


def _read_snapshot(path: str) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"{PREFIX} cannot read the snapshot {path}: {error}")
        return None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        print(f"{PREFIX} {path} is not a uri_diff snapshot")
        return None
    return data


def _report(plan_: ConversionPlan, backup_dir: Path | None, tag: str) -> None:
    print(f"{PREFIX} dry run on {plan_.repo} (branch {plan_.branch}, HEAD {plan_.head[:12]})")
    print(f"{PREFIX} the checks passed:")
    print("  KiCad is not running")
    print(f"  {VAR} in the newest KiCad config is {plan_.new_value}")
    for note in plan_.notes:
        print(f"  {note}")
    print(f"{PREFIX} --apply runs these steps, in this order, and stops at the first failure:")
    for number, step in enumerate(plan_.steps, start=1):
        print(f"  {number}. {step}")
    print(f"{PREFIX} the commit will hold: {', '.join(STAGED)} and the removal of the gitlink {OLD_PATH}")
    for name, diff in plan_.docs.items():
        if diff:
            print(f"{PREFIX} {name} changes as follows (current file against the template):")
            for line in diff:
                print(f"    {line}")
        else:
            print(f"{PREFIX} {name} already matches the template")
    for line in plan_.stale_lines:
        print(f"{PREFIX} {line}")
    _print_way_back(plan_.repo, plan_, backup_dir, tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replace the WurthElektronik submodule by the catalog entry (dry run unless --apply)")
    parser.add_argument("--repo", required=True, help="the top folder of the collection checkout")
    parser.add_argument("--before", required=True, help="uri_diff snapshot taken before Wurth was added to the catalog")
    parser.add_argument("--after", required=True, help="uri_diff snapshot taken after Generate Tables used the catalog folder")
    parser.add_argument("--config-dir", help="the folder holding KiCad's version folders (default: KiCad's own config folder)")
    parser.add_argument("--backup-dir", help="folder outside every repository for the bundle and the moved module data")
    parser.add_argument("--rollback-tag", default=DEFAULT_TAG, help=f"tag set at HEAD before any change (default {DEFAULT_TAG})")
    parser.add_argument("--message", help="the commit message (required with --apply)")
    parser.add_argument("--apply", action="store_true", help="convert; without it the plan is only printed")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    if args.apply and not args.backup_dir:
        print(f"{PREFIX} --apply needs --backup-dir DIR (outside every repository: the bundle and the module data go there)")
        return 2
    if args.apply and not (args.message and args.message.strip()):
        print(f"{PREFIX} --apply needs --message TEXT (the commit message)")
        return 2
    repo = Path(os.path.abspath(args.repo))
    if not repo.is_dir():
        print(f"{PREFIX} {repo} is not a folder")
        return 2
    before, after = _read_snapshot(args.before), _read_snapshot(args.after)
    if before is None or after is None:
        return 2
    try:
        top = _git(repo, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError) as error:
        print(f"{PREFIX} git cannot run: {error}")
        return 2
    if top.returncode != 0:
        print(f"{PREFIX} {repo} is not a git repository")
        return 2
    if not os.path.samefile(_text(top).strip(), repo):
        print(f"{PREFIX} --repo must be the top folder of the repository ({_text(top).strip()})")
        return 2
    backup = Path(os.path.abspath(args.backup_dir)) if args.backup_dir else None
    found = plan(repo, before, after, config_dir=args.config_dir, backup_dir=backup, tag=args.rollback_tag)
    if found.problems:
        for problem in found.problems:
            print(f"{PREFIX} refused: {problem}")
        print(f"{PREFIX} nothing was written")
        return 1
    if not args.apply:
        _report(found, backup, args.rollback_tag)
        if backup is None:
            print(f"{PREFIX} no backup folder checked yet: pass --backup-dir DIR to check it")
        print(f"{PREFIX} dry run only, nothing was written; run again with --apply --backup-dir DIR --message TEXT to convert")
        return 0
    return apply(repo, found, backup_dir=backup, tag=args.rollback_tag, message=args.message)


if __name__ == "__main__":
    raise SystemExit(main())
