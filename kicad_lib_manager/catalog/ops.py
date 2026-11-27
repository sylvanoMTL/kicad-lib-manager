"""Add a library to the catalog in two steps (Phase 17): stage_add downloads and checks, register_add records.

stage_add clones into ThirdParty/.staging/<id>.<hex>/, so a half-made or refused download never sits in
ThirdParty/<id>/. Only a checked download is renamed into place by register_add, which then lists it in
catalog.json. Neither step makes a git commit or touches the collection's own repository (D-03). Errors come
back as Issues, never raised. Qt-free.
"""

import os
import secrets
import shutil
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..collection import THIRD_PARTY_DIR
from ..models import Issue, Severity
from . import gitnet, manifest
from .gitnet import NetGit
from .manifest import CatalogEntry

STAGING_DIR = ".staging"
NO_LIBRARIES_TEXT = "This repository holds no KiCad symbol or footprint libraries, so there is nothing to add."
_RENAME_TRIES = 10
_RENAME_DELAY = 0.1


@dataclass(frozen=True)
class AddSource:
    id: str
    name: str
    url: str
    branch: str
    vars: dict
    licence_spdx: str | None


@dataclass(frozen=True)
class Staged:
    source: AddSource
    folder: Path
    commit: str


def library_folder(root: Path, id: str) -> Path:
    return Path(root) / THIRD_PARTY_DIR / id


def _force_remove(func, path, _exc):
    """Clear the read-only bit and retry: files inside .git are read-only on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_tree(folder: Path) -> None:
    """Delete a folder with everything in it, read-only files included, retrying while another program holds a file."""
    for attempt in range(_RENAME_TRIES):
        if not folder.exists():
            return
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(folder, onexc=_force_remove)
            else:
                shutil.rmtree(folder, onerror=_force_remove)
        except PermissionError:
            time.sleep(_RENAME_DELAY * (attempt + 1))
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(_RENAME_DELAY)


def _holds_libraries(folder: Path) -> bool:
    """True when folder holds a .kicad_sym file or a .pretty folder somewhere outside .git."""
    for _, dirs, files in os.walk(folder):
        if ".git" in dirs:
            dirs.remove(".git")
        if any(name.lower().endswith(".kicad_sym") for name in files):
            return True
        if any(name.lower().endswith(".pretty") for name in dirs):
            return True
    return False


def stage_add(root: Path, source: AddSource, net: NetGit, *, progress=None, cancel=None) -> Staged | Issue:
    """Download source into ThirdParty/.staging/<id>.<hex>/ and check it holds KiCad libraries.

    Any refusal or failure deletes the staging folder and is returned as an Issue.
    """
    if library_folder(root, source.id).exists():
        return Issue(Severity.ERROR, "catalog.folder_exists", f"{source.name} is already in your library folder.")
    staging_root = Path(root) / THIRD_PARTY_DIR / STAGING_DIR
    try:
        staging_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return Issue(Severity.ERROR, "catalog.write_failed", f"Could not create the download folder: {e.strerror or e}")
    folder = staging_root / f"{source.id}.{secrets.token_hex(4)}"

    def fail(issue: Issue) -> Issue:
        _remove_tree(folder)
        return issue

    run = gitnet.clone_shallow(net, source.url, source.branch, folder, progress=progress, cancel=cancel)
    if isinstance(run, Issue):
        return fail(run)
    if not _holds_libraries(folder):
        return fail(Issue(Severity.ERROR, "catalog.no_libraries", NO_LIBRARIES_TEXT))
    commit = gitnet.head_commit(net, folder)
    if isinstance(commit, Issue):
        return fail(commit)
    return Staged(source, folder, commit)


def _move(source: Path, target: Path) -> Issue | None:
    """os.replace, retried while another program (a virus scanner) holds a file."""
    error: OSError | None = None
    for _ in range(_RENAME_TRIES):
        try:
            os.replace(source, target)
            return None
        except PermissionError as e:
            error = e
            time.sleep(_RENAME_DELAY)
        except OSError as e:
            error = e
            break
    return Issue(Severity.ERROR, "catalog.move_failed", f"Could not move the download into place: {(error and error.strerror) or error}")


def register_add(root: Path, staged: Staged, *, acknowledged: bool = False, acknowledged_on: str = "") -> list[Issue]:
    """Move the staged download to ThirdParty/<id>/ and list it in catalog.json; no git command runs."""
    source = staged.source
    target = library_folder(root, source.id)
    if target.exists():
        return [Issue(Severity.ERROR, "catalog.folder_exists", f"{source.name} is already in your library folder.")]
    moved = _move(staged.folder, target)
    if moved is not None:
        return [moved]

    def back(issue: Issue) -> list[Issue]:
        # put the folder back so a retry or a discard still finds it
        _move(target, staged.folder)
        return [issue]

    current = manifest.load(root)
    if isinstance(current, Issue):
        return back(current)
    entry = CatalogEntry(
        id=source.id,
        url=source.url,
        branch=source.branch,
        commit=staged.commit,
        vars=dict(source.vars),
        licence_spdx=source.licence_spdx,
        acknowledged=acknowledged,
        acknowledged_on=acknowledged_on,
    )
    saved = manifest.save(root, current.with_entry(entry))
    if saved is not None:
        return back(saved)
    return [Issue(Severity.SUCCESS, "catalog.added", f"Added {source.name} to the catalog.")]


def discard_staging(staged: Staged) -> None:
    """Delete a download that was not registered."""
    _remove_tree(staged.folder)
