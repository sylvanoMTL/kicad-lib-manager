"""Add, Reinstall, Update and Remove a library of the catalog (Phase 17).

Update runs as plan_update (a download into the object store only) and apply_update (a reset to the previewed
commit), Remove as plan_remove and apply_remove. Add and Reinstall run as plan, stage (download and check) and
register:

plan_add / plan_reinstall refuse before any download (folder in the way, a path variable another library
owns, not enough disk space) and report what the licence page and the Add preview show. stage_add clones into
ThirdParty/.staging/<id>.<hex>/, watches the free disk space while it downloads and checks the download with
catalog.validate, so a refused or half-made download never sits in ThirdParty/<id>/ and is deleted on any
refusal. Only a checked download is renamed into place by register_add, which then lists it in catalog.json
and, when the collection is a git repository, adds the /ThirdParty/ line to its .gitignore. No step makes a
git commit or touches the collection's own repository (D-03), and nothing outside <collection>/ThirdParty,
<collection>/catalog.json and <collection>/.gitignore is written (CAT-10). Errors come back as Issues, never
raised. Qt-free.
"""

import math
import os
import secrets
import shutil
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .. import fsutil, gitops, kicad_process
from ..collection import STAGING_DIR, THIRD_PARTY_DIR
from ..models import Issue, Severity
from . import curated, githubapi, gitnet, licences, manifest, urls, validate
from .curated import CuratedEntry
from .githubapi import RepoInfo
from .gitnet import NetGit
from .licences import LicenceClass
from .manifest import CatalogEntry, Manifest
from .urls import RepoRef

NO_LIBRARIES_TEXT = validate.NO_LIBRARIES_TEXT
GITIGNORE_LINE = "/ThirdParty/"
# the spellings of that line which already keep ThirdParty out of the collection's git repository
_GITIGNORE_FORMS = frozenset({"/ThirdParty/", "ThirdParty/", "/ThirdParty", "ThirdParty"})
MB = 1024 * 1024
SPACE_FLOOR_MB = 500  # the smallest safety margin (D-15)
SPACE_MARGIN_PERCENT = 25  # the margin is the larger of the floor and this share of the space the library needs
SPACE_FACTOR = 6  # an Add by URL needs this many times GitHub's packed size plus the floor (RESEARCH C9)
_RENAME_TRIES = 10
_RENAME_DELAY = 0.1
_LICENCE_SETTLED = (LicenceClass.OPEN, LicenceClass.SHARE_ALIKE, LicenceClass.PROPRIETARY)
_MAX_CLASH_NAMES = 5


@dataclass(frozen=True)
class AddSource:
    """What to download: the library's id (its ThirdParty folder), name, address, branch and licence.

    vars is the path-variable map to record; detect_vars asks for the map found in the download instead (an
    Add by URL). proprietary and licence_known decide the licence class together with licence_spdx. licence_url is
    the page that holds the licence terms (from the curated entry); "" makes the licence page link to the repository.
    """

    id: str
    name: str
    url: str
    branch: str
    vars: dict
    licence_spdx: str | None
    proprietary: bool = False
    licence_known: bool = True
    detect_vars: bool = False
    licence_url: str = ""


@dataclass(frozen=True)
class NetStatus:
    """The git the catalog may use: net is None while a refusal stands; warning never stops anything."""

    net: NetGit | None
    version: tuple[int, ...] | None
    refusal: Issue | None
    warning: Issue | None


@dataclass(frozen=True)
class CheckedRepo:
    """A repository typed by address that passed the address, duplicate and GitHub checks (D-23, D-04).

    info is GitHub's answer, or None when it could not be read (info_issue says why); branch is the one to clone.
    """

    ref: RepoRef
    info: RepoInfo | None
    branch: str
    info_issue: Issue | None = None


@dataclass(frozen=True)
class AddPlan:
    """What the licence page and the Add preview show before anything is downloaded.

    size_mb is the size shown to the user, needs_mb the disk the finished library needs and margin_mb the safety
    margin kept free; all three are None when the size is unknown (no space check). licence is the class that
    decides the tick; licence_text_known is True when the licence was settled on the licence page, False when
    the preview must show the licence file. refusals stop the Add; kicad_open names running KiCad programs
    (a warning). gitignore is "" (no change), "append" or "create". acknowledged and acknowledged_on are the
    recorded confirmation of a Reinstall.
    """

    source: AddSource
    name: str
    folder: Path
    licence: LicenceClass
    licence_text_known: bool
    size_mb: int | None
    needs_mb: int | None
    margin_mb: int | None
    free_mb: int | None
    refusals: tuple[Issue, ...] = ()
    kicad_open: tuple[str, ...] = ()
    gitignore: str = ""
    reinstall: bool = False
    acknowledged_on: str = ""
    legacy_prefix: str | None = None
    acknowledged: bool = False


@dataclass(frozen=True)
class Staged:
    """A checked download waiting for register_add (or discard_staging).

    report is the staging check, known_dirty the casefolded paths git reports as changed right after the
    download (RESEARCH C8), vars the path variables to record (None: the source's own map).
    """

    source: AddSource
    folder: Path
    commit: str
    report: validate.StagingReport | None = None
    known_dirty: tuple[str, ...] = ()
    plan: AddPlan | None = None
    vars: dict | None = None


def library_folder(root: Path, id: str) -> Path:
    return Path(root) / THIRD_PARTY_DIR / id


def _display_name(id: str) -> str:
    """The curated name of a library id, else the id itself."""
    entry = curated.curated_by_id(id)
    return entry.name if entry is not None else id


# ── Space ────────────────────────────────────────────────────────────

def _format_mb(mb: int) -> str:
    if mb < 1000:
        return f"{mb} MB"
    text = f"{mb / 1000:.1f}".rstrip("0").rstrip(".")
    return f"{text} GB"


def _drive(root: Path) -> str:
    return Path(root).resolve().anchor.rstrip("\\/") or "/"


def _free_mb(free_space: Callable, root: Path) -> int | None:
    """Free disk space at root in whole MB, or None when the system cannot say."""
    try:
        return int(free_space(root).free) // MB
    except (OSError, ValueError, AttributeError):
        return None


def _margin_mb(needs_mb: int) -> int:
    return max(SPACE_FLOOR_MB, math.ceil(needs_mb * SPACE_MARGIN_PERCENT / 100))


def _no_space(root: Path, name: str, needs_mb: int | None, margin_mb: int, free_mb: int) -> Issue:
    drive = _drive(root)
    if needs_mb is None:
        text = (
            f"There is not enough free space on {drive} for {name}. The download needs a safety margin of "
            f"{_format_mb(margin_mb)}, and {drive} has {_format_mb(free_mb)} free. Free some space, then try again."
        )
    else:
        text = (
            f"There is not enough free space on {drive} for {name}. It needs about {_format_mb(needs_mb)} plus a "
            f"safety margin of {_format_mb(margin_mb)}, and {drive} has {_format_mb(free_mb)} free. "
            "Free some space, then try again."
        )
    return Issue(Severity.ERROR, "catalog.no_space", text)


# ── Checks ───────────────────────────────────────────────────────────

def _already_listed(name: str) -> Issue:
    return Issue(
        Severity.ERROR,
        "catalog.already_listed",
        f"This library is already in your catalog as {name}. Select it in the list.",
    )


def _folder_exists(name: str) -> Issue:
    return Issue(Severity.ERROR, "catalog.folder_exists", f"{name} is already in your library folder.")


def _existing_folder(root: Path, id: str) -> str | None:
    """The name of the ThirdParty folder that has this id (letter case ignored, as on Windows), else None."""
    try:
        names = [p.name for p in (Path(root) / THIRD_PARTY_DIR).iterdir()]
    except OSError:
        return None
    key = id.casefold()
    return next((name for name in names if name.casefold() == key), None)


def _var_conflict(mf: Manifest, id: str, names) -> Issue | None:
    """Refuse a path variable that another catalog library already sets for its own folder (CAT-06)."""
    for name in sorted(names):
        for entry in sorted(mf.libraries, key=lambda e: e.id.casefold()):
            if entry.id.casefold() != id.casefold() and name in entry.vars:
                other = _display_name(entry.id)
                return Issue(
                    Severity.ERROR,
                    "catalog.var_in_use",
                    f"This library needs the path variable {name}, which {other} already uses for its own folder. "
                    f"Remove {other} first, then add this library.",
                )
    return None


def _gitignore_state(root: Path) -> str:
    """"" when the collection is not a git repository or the line is there (or the file cannot be read), else "append" or "create"."""
    root = Path(root)
    if not (root / ".git").exists():
        return ""
    path = root / ".gitignore"
    if not path.exists():
        return "create"
    source = fsutil.read_source(path)
    if isinstance(source, Issue):
        return ""
    present = any(line.strip() in _GITIGNORE_FORMS for line in source.text.splitlines())
    return "" if present else "append"


def _write_gitignore(root: Path) -> list[Issue]:
    """Add the /ThirdParty/ line, keeping the file's line endings and BOM; a failure is a warning only."""
    path = Path(root) / ".gitignore"
    bom, eol, text = False, "\n", ""
    if path.exists():
        source = fsutil.read_source(path)
        if isinstance(source, Issue):
            return [Issue(Severity.WARNING, "catalog.gitignore_failed", f"Could not add the line {GITIGNORE_LINE} to .gitignore: {source.text}")]
        bom, eol, text = source.bom, source.eol, source.text
    if text and not text.endswith(("\n", "\r")):
        text += eol
    failure = fsutil.atomic_write_text(path, text + GITIGNORE_LINE + eol, bom=bom)
    if failure is not None:
        return [Issue(Severity.WARNING, "catalog.gitignore_failed", f"Could not add the line {GITIGNORE_LINE} to .gitignore: {failure.text}")]
    return [Issue(Severity.INFO, "catalog.gitignore_changed", f"Added the line {GITIGNORE_LINE} to {Path(root).as_posix()}/.gitignore.")]


def net_status(
    root: Path,
    *,
    which: Callable[[str], str | None] | None = None,
    version: Callable[[Path], tuple[int, ...] | None] | None = None,
) -> NetStatus:
    """Find git for the catalog and judge its version: a refusal below 2.32, a warning below 2.49.1 (D-11, D-29).

    version(exe) answers the version for a test; the default asks git. A git that cannot say its version is
    treated as missing.
    """
    exe = gitops.find_git(root, which=which)
    if isinstance(exe, Issue):
        refusal = gitnet.version_issues(None)[0] if exe.code == "git.not_found" else exe
        return NetStatus(None, None, refusal, None)
    found = version(exe) if version is not None else gitops.git_version(gitops.GitContext(exe))
    refusal, warning = gitnet.version_issues(found)
    return NetStatus(None if refusal is not None else NetGit(exe), found, refusal, warning)


def check_repository(
    root: Path,
    text: str,
    mf: Manifest,
    net: NetGit,
    *,
    repo_info: Callable = githubapi.repo_info,
    cancel=None,
) -> CheckedRepo | Issue:
    """Check a typed address before the licence page: the address, a repository already known, GitHub's answer.

    The curated list and the catalog are compared by repository (letter case ignored), so the same library under
    another spelling is refused. GitHub saying not found or private is refused; GitHub not answering is not (D-04):
    the default branch then comes from the repository itself (ls-remote --symref) and the size and licence stay
    unknown.
    """
    ref = urls.parse_github_url(text, allow_file=net.allow_file)
    if isinstance(ref, Issue):
        return ref
    key = urls.repo_key(ref.https_url)
    for entry in mf.libraries:
        if urls.repo_key(entry.url) == key:
            return _already_listed(_display_name(entry.id))
    for known in curated.CURATED:
        if urls.repo_key(known.url) == key:
            return _already_listed(known.name)
    info: RepoInfo | None = None
    info_issue: Issue | None = None
    if ref.owner:  # a file:// address (tests) has no GitHub page to ask
        answer = repo_info(ref.owner, ref.repo)
        if isinstance(answer, Issue):
            if answer.code == "api.not_found":
                return answer
            info_issue = answer
        else:
            info = answer
    branch = info.default_branch if info is not None else ""
    if info is not None and not urls.valid_branch(branch):
        info, info_issue, branch = None, Issue(Severity.ERROR, "api.unknown", githubapi.ODD_TEXT), ""
    if info is None:
        if info_issue is None:
            info_issue = Issue(Severity.ERROR, "api.unknown", githubapi.ODD_TEXT)
        found = gitnet.default_branch(net, ref.https_url, cancel=cancel)
        if isinstance(found, Issue):
            return found
        branch = found[0]
        if not urls.valid_branch(branch):
            return Issue(Severity.ERROR, "catalog.bad_branch", "This repository's default branch has a name the catalog cannot use.")
    return CheckedRepo(ref, info, branch, info_issue)


# ── Plan ─────────────────────────────────────────────────────────────

def _curated_source(entry: CuratedEntry) -> AddSource:
    return AddSource(
        entry.id, entry.name, entry.url, entry.branch, dict(entry.vars), entry.licence_spdx, proprietary=entry.proprietary,
        licence_url=entry.licence_url,
    )


def _checked_source(checked: CheckedRepo) -> AddSource:
    info = checked.info
    return AddSource(
        checked.ref.default_id,
        checked.ref.default_id,
        checked.ref.https_url,
        checked.branch,
        {},
        info.spdx if info is not None else None,
        licence_known=info is not None,
        detect_vars=True,
    )


def _plan(
    root: Path,
    mf: Manifest,
    source: AddSource,
    *,
    size_mb: int | None,
    needs_mb: int | None,
    legacy_prefix: str | None,
    reinstall: bool,
    entry: CatalogEntry | None,
    free_space: Callable,
    running: Callable[[], list[str]],
) -> AddPlan:
    folder = library_folder(root, source.id)
    licence = licences.licence_class(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)
    margin = _margin_mb(needs_mb) if needs_mb is not None else None
    free = _free_mb(free_space, root)
    existing = _existing_folder(root, source.id)
    refusals: list[Issue] = []
    if not reinstall and mf.find(source.id) is not None:
        refusals.append(_already_listed(_display_name(source.id)))
    elif not reinstall and existing is not None:
        refusals.append(
            Issue(
                Severity.ERROR,
                "catalog.unlisted_in_way",
                f"The folder {existing} already exists in ThirdParty but is not in the catalog. Remove it first "
                '(it is listed as "Problem: not in the catalog"), then add the library again.',
            )
        )
    elif reinstall and existing is not None:
        refusals.append(_folder_exists(source.name))
    else:
        conflict = _var_conflict(mf, source.id, source.vars)
        if conflict is not None:
            refusals.append(conflict)
        elif needs_mb is not None and free is not None and free < needs_mb + margin:
            refusals.append(_no_space(root, source.name, needs_mb, margin, free))
    return AddPlan(
        source=source,
        name=source.name,
        folder=folder,
        licence=licence,
        licence_text_known=licence in _LICENCE_SETTLED,
        size_mb=size_mb,
        needs_mb=needs_mb,
        margin_mb=margin,
        free_mb=free,
        refusals=tuple(refusals),
        kicad_open=tuple(running()),
        gitignore=_gitignore_state(root),
        reinstall=reinstall,
        acknowledged_on=entry.acknowledged_on if entry is not None else "",
        legacy_prefix=legacy_prefix,
        acknowledged=entry.acknowledged if entry is not None else False,
    )


def plan_add(
    root: Path,
    source: CuratedEntry | CheckedRepo,
    mf: Manifest,
    *,
    free_space: Callable = shutil.disk_usage,
    running: Callable[[], list[str]] = kicad_process.kicad_running,
) -> AddPlan:
    """The plan for adding a curated library or a checked repository; refusals stop it before any download.

    The space a library needs is its measured install size when curated, else 6 x GitHub's size (rounded up to
    whole MB) + 500 MB; the margin kept free is the larger of 500 MB and 25 % of that (D-15). An unknown size
    makes no space check. KiCad running only fills kicad_open (D-14).
    """
    if isinstance(source, CheckedRepo):
        info = source.info
        size = math.ceil(info.size_kb / 1024) if info is not None else None
        return _plan(
            root, mf, _checked_source(source),
            size_mb=size,
            needs_mb=None if size is None else SPACE_FACTOR * size + SPACE_FLOOR_MB,
            legacy_prefix=None, reinstall=False, entry=None, free_space=free_space, running=running,
        )  # fmt: skip
    return _plan(
        root, mf, _curated_source(source),
        size_mb=source.size_mb, needs_mb=source.install_mb, legacy_prefix=source.legacy_prefix,
        reinstall=False, entry=None, free_space=free_space, running=running,
    )  # fmt: skip


def plan_reinstall(
    root: Path,
    entry: CatalogEntry,
    mf: Manifest,
    *,
    free_space: Callable = shutil.disk_usage,
    running: Callable[[], list[str]] = kicad_process.kicad_running,
) -> AddPlan:
    """The plan for downloading a listed library whose folder is missing again, from the recorded address and branch (D-05)."""
    known = curated.curated_by_id(entry.id)
    source = AddSource(
        entry.id,
        known.name if known is not None else entry.id,
        entry.url,
        entry.branch,
        dict(entry.vars),
        entry.licence_spdx,
        proprietary=known.proprietary if known is not None else False,
        licence_url=known.licence_url if known is not None else "",
    )
    return _plan(
        root, mf, source,
        size_mb=known.size_mb if known is not None else None,
        needs_mb=known.install_mb if known is not None else None,
        legacy_prefix=known.legacy_prefix if known is not None else None,
        reinstall=True, entry=entry, free_space=free_space, running=running,
    )  # fmt: skip


# ── Stage ────────────────────────────────────────────────────────────

class _Stop:
    """The cancel object the runner polls: set by the user's cancel or by the free space falling too low."""

    def __init__(self, cancel):
        self._cancel = cancel
        self.low_free_mb: int | None = None

    def is_set(self) -> bool:
        return self.low_free_mb is not None or (self._cancel is not None and self._cancel.is_set())


def _bare_plan(root: Path, source: AddSource) -> AddPlan:
    """A plan for a source handed in without one: no refusal is judged, only the folder is derived."""
    licence = licences.licence_class(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)
    return AddPlan(source, source.name, library_folder(root, source.id), licence, licence in _LICENCE_SETTLED, None, None, None, None)


def _baseline(net: NetGit, folder: Path) -> tuple[tuple[str, ...], Issue | None]:
    """The casefolded paths git lists as changed right after the download (RESEARCH C8), and a warning when it could not say."""
    entries = gitnet.status_entries(net, folder)
    if isinstance(entries, Issue):
        return (), Issue(
            Severity.WARNING,
            "catalog.status_unread",
            "The downloaded files could not be checked for changes. A later update may refuse until they are.",
        )
    kept: list[str] = []
    for path in entries:
        key = path.casefold()
        if key and manifest.safe_var_folder(key) and key not in kept:
            kept.append(key)
    return tuple(kept), None


def stage_add(
    root: Path,
    plan: AddPlan | AddSource,
    net: NetGit,
    *,
    progress: Callable[[str, int | None], None] | None = None,
    cancel=None,
    stock_fp: Collection[str] = frozenset(),
    stock_sym: Collection[str] = frozenset(),
    own: Mapping[str, str] | None = None,
    other_catalog: Mapping[str, str] | None = None,
    free_space: Callable = shutil.disk_usage,
    check_progress: Callable[[int, int], None] | None = None,
) -> Staged | Issue:
    """Download plan.source into ThirdParty/.staging/<id>.<hex>/ and check it; any refusal or failure deletes it.

    A plan with refusals is returned as its first refusal without starting git. The free space is read after
    every progress line; below the plan's margin (500 MB when the size is unknown) the download is stopped with
    the same refusal as the plan. The check is catalog.validate; own and other_catalog name the libraries whose
    nicknames the download may clash with (they only fill the report). check_progress(done, total) counts the
    footprint files the check has read; it runs on the thread that called stage_add, after the download.
    """
    if isinstance(plan, AddSource):
        plan = _bare_plan(root, plan)
    if plan.refusals:
        return plan.refusals[0]
    source = plan.source
    if library_folder(root, source.id).exists():
        return _folder_exists(source.name)
    inside = Path(root) / THIRD_PARTY_DIR
    staging_root = inside / STAGING_DIR
    try:
        staging_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return Issue(Severity.ERROR, "catalog.write_failed", f"Could not create the download folder: {e.strerror or e}")
    folder = staging_root / f"{source.id}.{secrets.token_hex(4)}"

    def fail(issue: Issue) -> Issue:
        fsutil.remove_tree(folder, inside=inside)  # a leftover is cleaned up by clean_staging
        return issue

    margin = plan.margin_mb if plan.margin_mb is not None else SPACE_FLOOR_MB
    stop = _Stop(cancel)

    def watch(text: str, percent: int | None) -> None:
        if progress is not None:
            progress(text, percent)
        free = _free_mb(free_space, root)
        if free is not None and free < margin:
            stop.low_free_mb = free

    run = gitnet.clone_shallow(net, source.url, source.branch, folder, progress=watch, cancel=stop)
    if stop.low_free_mb is not None:
        return fail(_no_space(root, plan.name, plan.needs_mb, margin, stop.low_free_mb))
    if isinstance(run, Issue):
        return fail(run)
    report = validate.validate_staging(
        folder,
        stock_fp=stock_fp,
        stock_sym=stock_sym,
        own=own or {},
        other_catalog=other_catalog or {},
        progress=check_progress,
    )
    if isinstance(report, Issue):
        return fail(report)
    current = manifest.load(root, allow_file=net.allow_file)
    if isinstance(current, Issue):
        return fail(current)
    variables = dict(report.vars) if source.detect_vars else dict(source.vars)
    conflict = _var_conflict(current, source.id, variables)
    if conflict is not None:
        return fail(conflict)
    commit = gitnet.head_commit(net, folder)
    if isinstance(commit, Issue):
        return fail(commit)
    dirty, unread = _baseline(net, folder)
    if unread is not None:
        report = replace(report, warnings=(*report.warnings, unread))
    return Staged(source, folder, commit, report, dirty, plan, variables)


def discard_staging(staged: Staged) -> Issue | None:
    """Delete a download that was not registered; a folder that is not a staging folder is left alone."""
    folder = Path(staged.folder)
    if folder.parent.name != STAGING_DIR or folder.parent.parent.name != THIRD_PARTY_DIR:
        return Issue(Severity.ERROR, "fs.remove_outside", f"{folder.name} is not a download folder, so it was left alone.")
    return fsutil.remove_tree(folder, inside=folder.parent.parent)


def clean_staging(root: Path, *, older_than_s: float = 3600.0, now: Callable[[], float] = time.time) -> list[Issue]:
    """Delete leftovers in ThirdParty/.staging older than older_than_s, silently (D-06).

    A younger folder may belong to another running copy of the app and is left alone. Only a deletion that
    failed gives an Issue; the next start tries again.
    """
    inside = Path(root) / THIRD_PARTY_DIR
    try:
        children = list((inside / STAGING_DIR).iterdir())
    except OSError:
        return []
    limit = now() - older_than_s
    issues: list[Issue] = []
    for child in children:
        try:
            if not child.is_dir() or child.stat().st_mtime > limit:
                continue
        except OSError:
            continue
        failure = fsutil.remove_tree(child, inside=inside)
        if failure is not None:
            issues.append(failure)
    return issues


# ── Register ─────────────────────────────────────────────────────────

def _try_move(source: Path, target: Path) -> OSError | None:
    """os.replace, retried while another program (a virus scanner) holds a file; the last error, or None on success."""
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
    return error


def _move(source: Path, target: Path) -> Issue | None:
    error = _try_move(source, target)
    if error is None:
        return None
    return Issue(Severity.ERROR, "catalog.move_failed", f"Could not move the download into place: {error.strerror or error}")


def _clash_warning(name: str, report: validate.StagingReport) -> Issue:
    names = sorted({c.nickname for c in report.collisions}, key=str.casefold)
    shown = ", ".join(names[:_MAX_CLASH_NAMES])
    if len(names) > _MAX_CLASH_NAMES:
        shown += f" and {len(names) - _MAX_CLASH_NAMES} more"
    return Issue(
        Severity.WARNING,
        "catalog.name_clashes",
        f"{len(report.collisions)} libraries of {name} have the same name as libraries you already have and start unticked: {shown}.",
    )


def register_add(
    root: Path,
    staged: Staged,
    *,
    acknowledged: bool = False,
    today: str | None = None,
    allow_file: bool = False,
) -> list[Issue]:
    """Move the staged download to ThirdParty/<id>/ and list it in catalog.json; no git command runs.

    A licence that needs the tick is refused unless acknowledged (a Reinstall counts the confirmation already
    recorded). The record is read before anything moves and written after; when it cannot be written the folder
    moves back. For a Reinstall the recorded acknowledgement, its date and the day it was added are kept and only
    the commit changes. today is the date to record (default: today). allow_file lets a test whose catalog lists a
    file:// upstream read it.
    """
    source = staged.source
    plan = staged.plan
    name = plan.name if plan is not None else source.name
    allow_file = allow_file or source.url.casefold().startswith("file:")
    current = manifest.load(root, allow_file=allow_file)
    if isinstance(current, Issue):
        return [current]
    previous = current.find(source.id) if plan is not None and plan.reinstall else None
    confirmed = acknowledged or (previous is not None and previous.acknowledged)
    licence = licences.licence_class(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)
    if licences.needs_tick(licence) and not confirmed:
        return [
            Issue(
                Severity.ERROR,
                "catalog.licence_not_acknowledged",
                "Tick the box to confirm you have read the licence terms.",
            )
        ]
    target = library_folder(root, source.id)
    if target.exists():
        return [_folder_exists(name)]
    variables = dict(staged.vars) if staged.vars is not None else dict(source.vars)
    conflict = _var_conflict(current, source.id, variables)
    if conflict is not None:
        return [conflict]
    moved = _move(staged.folder, target)
    if moved is not None:
        return [moved]

    day = today or date.today().isoformat()
    if previous is not None and previous.acknowledged:
        acknowledged_on = previous.acknowledged_on
    else:
        acknowledged_on = day if confirmed else ""
    entry = CatalogEntry(
        id=source.id,
        url=source.url,
        branch=source.branch,
        commit=staged.commit,
        vars=variables,
        licence_spdx=source.licence_spdx,
        acknowledged=confirmed,
        acknowledged_on=acknowledged_on,
        added_on=(previous.added_on if previous is not None else "") or day,
        known_dirty=tuple(staged.known_dirty),
    )
    saved = manifest.save(root, current.with_entry(entry))
    if saved is not None:
        _move(target, staged.folder)  # put the folder back so a retry or a discard still finds it
        return [saved]

    report = staged.report
    counts = f"{len(report.symbol_libs)} symbol libraries, {len(report.footprint_libs)} footprint libraries" if report else ""
    if previous is not None:
        text = f"Reinstalled {name}: {counts}." if counts else f"Reinstalled {name}."
        issues = [Issue(Severity.SUCCESS, "catalog.reinstalled", text)]
    else:
        text = f"Added {name} to the catalog: {counts}." if counts else f"Added {name} to the catalog."
        issues = [Issue(Severity.SUCCESS, "catalog.added", text)]
    if report is not None:
        issues.extend(report.warnings)
        if report.collisions:
            issues.append(_clash_warning(name, report))
    if (Path(root) / ".git").exists():
        if _gitignore_state(root):
            issues.extend(_write_gitignore(root))
        issues.append(
            Issue(
                Severity.INFO,
                "catalog.record_changed",
                f"{manifest.MANIFEST_NAME} in {Path(root).as_posix()} changed. The app does not commit it for you.",
            )
        )
    return issues


# ── Update ───────────────────────────────────────────────────────────

_MAX_NAMES = 5


def _name_list(names, limit: int = _MAX_NAMES) -> str:
    """The names joined with commas, at most limit of them, then "and {m} more"."""
    shown = ", ".join(names[:limit])
    return f"{shown} and {len(names) - limit} more" if len(names) > limit else shown


def _typed_names(paths) -> set[tuple[str, str]]:
    """The libraries in a list of file paths as (kind, name): "sym" for a .kicad_sym file's stem, "fp" for a .pretty folder that holds a .kicad_mod."""
    found: set[tuple[str, str]] = set()
    for path in paths:
        parts = str(path).split("/")
        leaf = parts[-1]
        low = leaf.casefold()
        if low.endswith(".kicad_sym"):
            found.add(("sym", leaf[: -len(".kicad_sym")]))
        elif low.endswith(".kicad_mod") and len(parts) > 1 and parts[-2].casefold().endswith(".pretty"):
            found.add(("fp", parts[-2][: -len(".pretty")]))
    return found


def _library_names(paths) -> set[str]:
    """The library names in a list of file paths (a symbol library and a footprint library of one name count once)."""
    return {name for _kind, name in _typed_names(paths)}


@dataclass(frozen=True)
class UpdatePlan:
    """What the Update preview shows: the clone's HEAD (old) and the fetched commit (new) of the recorded branch.

    files_changed counts the files that differ, added and removed are the library names that appear or leave,
    dirty the files changed inside the folder since it was added (git status minus the recorded baseline) and
    current is True when old and new are the same commit. refusal stops the update (changed files, Git LFS in
    the new version); kicad_open names running KiCad programs (a warning).
    """

    entry: CatalogEntry
    name: str
    folder: Path
    old: str
    new: str
    files_changed: int
    added: tuple[str, ...]
    removed: tuple[str, ...]
    dirty: tuple[str, ...]
    current: bool
    kicad_open: tuple[str, ...]
    refusal: Issue | None


def _clone_problem(folder: Path, name: str) -> Issue | None:
    """Refuse a missing folder or a clone whose git settings the app did not write, before any git runs (D-11, Pitfall 4)."""
    if not Path(folder).is_dir():
        return Issue(
            Severity.ERROR,
            "catalog.folder_missing",
            f"The folder {Path(folder).as_posix()} is missing. Reinstall {name} to download it again.",
        )
    problems = gitnet.config_problems(folder)
    if problems:
        return Issue(
            Severity.ERROR,
            "catalog.unexpected_settings",
            f"{name} cannot be updated: its download folder has git settings the app did not write "
            f"({_name_list(problems, 3)}). Remove {name} and add it again.",
        )
    return None


def _dirty_issue(name: str, folder: Path) -> Issue:
    return Issue(
        Severity.ERROR,
        "catalog.dirty",
        f"{name} cannot be updated: files in {Path(folder).as_posix()} were changed after it was added. "
        "Catalog libraries are managed copies, and an update would overwrite your changes. "
        "Keep your own changes in Custom/ instead.",
    )


def _dirty_files(net: NetGit, folder: Path, known_dirty) -> tuple[str, ...] | Issue:
    """The changed or untracked files of a clone, without the baseline of files git lists right after the download."""
    entries = gitnet.status_entries(net, folder)
    if isinstance(entries, Issue):
        return entries
    known = {path.casefold() for path in known_dirty}
    return tuple(path for path in entries if path.casefold() not in known)


def _lfs_issue(name: str) -> Issue:
    return Issue(
        Severity.ERROR,
        "catalog.lfs",
        f"{name} cannot be updated: the new version keeps its 3D models in Git LFS, which the catalog does not "
        "support. Nothing was changed.",
    )


def _uses_lfs(net: NetGit, folder: Path, sha: str, paths) -> bool:
    """True when any .gitattributes of the commit routes a file through the LFS filter (read from git, never checked out)."""
    for path in paths:
        if path.split("/")[-1].casefold() != ".gitattributes":
            continue
        data = gitnet.read_blob(net, folder, sha, path)
        if data is not None and validate.lfs_attributes(data):
            return True
    return False


def _record_changed(root: Path) -> Issue:
    return Issue(
        Severity.INFO,
        "catalog.record_changed",
        f"{manifest.MANIFEST_NAME} in {Path(root).as_posix()} changed. The app does not commit it for you.",
    )


def plan_update(
    root: Path,
    entry: CatalogEntry,
    net: NetGit,
    *,
    progress: Callable[[str, int | None], None] | None = None,
    cancel=None,
    running: Callable[[], list[str]] = kicad_process.kicad_running,
) -> UpdatePlan | Issue:
    """Look for a newer version of a listed library without changing any file in its folder (D-07, D-08).

    Order: a missing folder or unexpected git settings (an Issue, before git runs), the clean-tree check (a plan
    with dirty files and a refusal), then the download of the recorded address and branch at depth 1 into the
    object store only. old is the clone's HEAD, new the fetched commit; the plan lists the files changed and the
    library names added and removed from the two trees, and refuses when the new version brings Git LFS.
    """
    folder = manifest.entry_folder(root, entry)
    name = _display_name(entry.id)
    problem = _clone_problem(folder, name)
    if problem is not None:
        return problem
    dirty = _dirty_files(net, folder, entry.known_dirty)
    if isinstance(dirty, Issue):
        return dirty
    open_programs = tuple(running())
    if dirty:
        return UpdatePlan(
            entry, name, folder, entry.commit, "", 0, (), (), dirty, False, open_programs, _dirty_issue(name, folder)
        )
    old = gitnet.head_commit(net, folder)
    if isinstance(old, Issue):
        return old
    new = gitnet.fetch_shallow(net, folder, entry.url, entry.branch, progress=progress, cancel=cancel)
    if isinstance(new, Issue):
        return new
    if new == old:
        return UpdatePlan(entry, name, folder, old, new, 0, (), (), (), True, open_programs, None)
    changed = gitnet.changed_paths(net, folder, new)
    if isinstance(changed, Issue):
        return changed
    before = gitnet.tree_paths(net, folder, "HEAD")
    if isinstance(before, Issue):
        return before
    after = gitnet.tree_paths(net, folder, new)
    if isinstance(after, Issue):
        return after
    # compared as (kind, name): a footprint library that leaves is reported even when a symbol library keeps its name
    typed_before, typed_after = _typed_names(before), _typed_names(after)
    refusal = _lfs_issue(name) if _uses_lfs(net, folder, new, after) else None
    return UpdatePlan(
        entry, name, folder, old, new, len(changed),
        tuple(sorted({n for _k, n in typed_after - typed_before}, key=str.casefold)),
        tuple(sorted({n for _k, n in typed_before - typed_after}, key=str.casefold)),
        (), False, open_programs, refusal,
    )  # fmt: skip


def apply_update(root: Path, plan: UpdatePlan, net: NetGit, *, cancel=None) -> list[Issue]:
    """Move the clone to the commit that was previewed (plan.new), never to a newer one (T-17-27).

    The clean tree, the git settings and the LFS rule are checked again right before the reset; an update stopped
    before the reset leaves every file as it was. A clone that already is at plan.new gets no reset. The entry's
    commit and the baseline of files git lists as changed are rewritten from the state after the reset.
    """
    if plan.refusal is not None:
        return [plan.refusal]
    entry, folder, name = plan.entry, plan.folder, plan.name
    problem = _clone_problem(folder, name)
    if problem is not None:
        return [problem]
    current = manifest.load(root, allow_file=net.allow_file)
    if isinstance(current, Issue):
        return [current]
    listed = current.find(entry.id)
    if listed is None:
        return [Issue(Severity.ERROR, "catalog.not_listed", f"{name} is no longer in the catalog, so it was not updated.")]
    head = gitnet.head_commit(net, folder)
    if isinstance(head, Issue):
        return [head]
    baseline = tuple(listed.known_dirty)
    if head != plan.new:
        dirty = _dirty_files(net, folder, listed.known_dirty)
        if isinstance(dirty, Issue):
            return [dirty]
        if dirty:
            return [_dirty_issue(name, folder)]
        paths = gitnet.tree_paths(net, folder, plan.new)
        if isinstance(paths, Issue):
            return [paths]
        if _uses_lfs(net, folder, plan.new, paths):
            return [_lfs_issue(name)]
        if cancel is not None and cancel.is_set():
            return [Issue(Severity.INFO, "git.cancelled", "Stopped.")]
        reset = gitnet.reset_hard(net, folder, plan.new)
        if isinstance(reset, Issue):
            return [reset]
        fresh, unread = _baseline(net, folder)
        if unread is None:
            baseline = fresh
    if listed.commit != plan.new or baseline != tuple(listed.known_dirty):
        saved = manifest.save(root, current.with_entry(replace(listed, commit=plan.new, known_dirty=baseline)))
        if saved is not None:
            return [saved]
    issues = [
        Issue(
            Severity.SUCCESS,
            "catalog.updated",
            f"Updated {name} to {plan.new[:7]}: {len(plan.added)} libraries added, {len(plan.removed)} removed.",
        )
    ]
    if plan.removed:
        issues.append(
            Issue(
                Severity.WARNING,
                "catalog.update_removed",
                f"Update of {name} removed {len(plan.removed)} libraries: {_name_list(plan.removed)}. "
                "Projects that use them lose those parts.",
            )
        )
    if (Path(root) / ".git").exists():
        issues.append(_record_changed(root))
    return issues


# ── Remove ───────────────────────────────────────────────────────────

def size_on_disk(folder: Path) -> int:
    """The bytes of every file below folder, links not followed; 0 for a folder that is not there."""
    total = 0
    for current, _dirs, files in os.walk(folder, followlinks=False):
        for leaf in files:
            try:
                total += os.lstat(os.path.join(current, leaf)).st_size
            except OSError:
                continue
    return total


@dataclass(frozen=True)
class RemovePlan:
    """What the Remove page shows: the folder, its size, the libraries that leave the scan and the variables it used.

    exists is False for a listed library whose folder is already gone (only the entry is removed); listed is False
    for a ThirdParty folder the catalog does not list (the folder is deleted, the catalog is not changed).
    """

    id: str
    name: str
    folder: Path
    exists: bool
    size_bytes: int
    nicknames: tuple[str, ...]
    vars: tuple[str, ...]
    listed: bool
    kicad_open: tuple[str, ...]


def _disk_paths(folder: Path) -> list[str]:
    paths: list[str] = []
    for current, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if d != ".git"]
        for leaf in files:
            paths.append((Path(current) / leaf).relative_to(folder).as_posix())
    return paths


def plan_remove(
    root: Path,
    target_id: str,
    mf: Manifest,
    *,
    scan=None,
    running: Callable[[], list[str]] = kicad_process.kicad_running,
) -> RemovePlan:
    """The plan for removing a listed library or an unlisted ThirdParty folder (D-21, D-06, D-05).

    The library names come from the last scan when given (the libraries whose files sit in the folder), else
    from the files on disk.
    """
    entry = mf.find(target_id)
    existing = _existing_folder(root, target_id)
    folder = Path(root) / THIRD_PARTY_DIR / (existing or (entry.id if entry is not None else target_id))
    exists = existing is not None and folder.is_dir()
    if scan is not None:
        prefix = f"{THIRD_PARTY_DIR}/{folder.name}/".casefold()
        found = {
            lib.nickname
            for lib in [*scan.symbol_libs, *scan.footprint_libs]
            if lib.rel_path.replace("\\", "/").casefold().startswith(prefix)
        }
    else:
        found = _library_names(_disk_paths(folder)) if exists else set()
    return RemovePlan(
        id=entry.id if entry is not None else folder.name,
        name=_display_name(entry.id if entry is not None else folder.name),
        folder=folder,
        exists=exists,
        size_bytes=size_on_disk(folder) if exists else 0,
        nicknames=tuple(sorted(found, key=str.casefold)),
        vars=tuple(sorted(entry.vars)) if entry is not None else (),
        listed=entry is not None,
        kicad_open=tuple(running()),
    )


def _remove_failed(name: str, folder: Path, reason: str, *, listed: bool = True) -> Issue:
    text = f"Could not remove {name}: {reason}. Close anything that uses files in {Path(folder).as_posix()}, then try again."
    if listed:
        text += " The catalog entry was kept."
    return Issue(Severity.ERROR, "catalog.remove_failed", text)


# A failed Remove keeps the catalog entry (decided: CONTEXT is silent, the UI-SPEC copy says "The catalog entry
# was kept."): the folder is renamed into ThirdParty/.staging first, so a file in use stops the Remove before
# anything else changes; then the entry is removed (a failed save moves the folder back) and the renamed folder
# is deleted last. A delete that fails leaves a leftover in .staging that clean_staging removes later, so an
# interrupted Remove leaves either the library installed with its entry or the entry gone (D-21).
def apply_remove(root: Path, plan: RemovePlan, *, allow_file: bool = False) -> list[Issue]:
    """Delete the folder of plan and remove its catalog entry; allow_file lets a test whose catalog lists a file:// upstream read it.

    Only a direct child of ThirdParty is ever removed, never .staging or a dot folder. Path variables are never
    unset (D-21). The collection's own folders and KiCad's files are never touched (CAT-10).
    """
    third = Path(root) / THIRD_PARTY_DIR
    folder, name = Path(plan.folder), plan.name
    if folder.parent != third or folder.name in ("", ".", "..", STAGING_DIR) or folder.name.startswith("."):
        return [
            Issue(
                Severity.ERROR,
                "catalog.remove_failed",
                f"Could not remove {name}: {folder.name or 'that folder'} is not a library folder of the catalog, so it was left alone.",
            )
        ]
    current = manifest.load(root, allow_file=allow_file)
    if isinstance(current, Issue):
        return [current]
    entry = current.find(plan.id)
    listed = entry is not None
    renamed: Path | None = None
    if os.path.lexists(folder):
        staging = third / STAGING_DIR
        try:
            staging.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return [_remove_failed(name, folder, e.strerror or str(e), listed=listed)]
        renamed = staging / f"{folder.name}.removing.{secrets.token_hex(4)}"
        error = _try_move(folder, renamed)
        if error is not None:
            return [_remove_failed(name, folder, error.strerror or str(error), listed=listed)]
    if entry is not None:
        remaining = Manifest(tuple(e for e in current.libraries if e.id.casefold() != entry.id.casefold()))
        saved = manifest.save(root, remaining)
        if saved is not None:
            issues = [_remove_failed(name, folder, "the catalog record could not be written"), saved]
            if renamed is not None and _try_move(renamed, folder) is not None:
                issues.append(
                    Issue(
                        Severity.WARNING,
                        "catalog.remove_leftover",
                        f"The files of {name} could not be moved back to {folder.as_posix()}. They are in "
                        f"{THIRD_PARTY_DIR}/{STAGING_DIR}. Reinstall {name} to download it again.",
                    )
                )
            return issues
    what = f"Removed {name} from the catalog." if listed else f"Removed the folder {name}."
    issues = [
        Issue(
            Severity.SUCCESS,
            "catalog.removed",
            f"{what} Generate Tables drops its libraries from your KiCad library tables.",
        )
    ]
    if renamed is not None:
        failure = fsutil.remove_tree(renamed, inside=third)
        if failure is not None:
            issues.append(
                Issue(
                    Severity.WARNING,
                    "catalog.remove_leftover",
                    f"Part of {name} could not be deleted yet ({failure.text}). It is in {THIRD_PARTY_DIR}/{STAGING_DIR} "
                    "and is deleted the next time the catalog starts.",
                )
            )
    if listed and (Path(root) / ".git").exists():
        issues.append(_record_changed(root))
    return issues
