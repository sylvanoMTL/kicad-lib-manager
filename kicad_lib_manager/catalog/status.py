"""The status of every row of the library catalog and the update check (Phase 17; CAT-01, CAT-07, D-02, D-05, D-06, D-12, D-19, D-31, D-32).

row_statuses turns the curated list, the catalog.json record and the folders of ThirdParty into one row per
library with exactly one state; the window (plan 17-11) owns the texts, glyphs and colours, this module only
returns states. check_updates asks each installed library's remote for the commit of its branch (ls-remote:
nothing is downloaded and nothing is written) and sorts the answer into one of four outcomes; offline is
unknown, never an error. A few missing upstream 3D models never change a state (D-31): the scan's warnings are
not read here at all. Qt-free.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..collection import STAGING_DIR, THIRD_PARTY_DIR
from ..models import Issue
from . import curated as curated_list
from . import gitnet, licences, manifest, names
from .curated import CuratedEntry
from .licences import LicenceClass
from .manifest import CatalogEntry, Manifest

MB_PER_GB = 1000  # sizes are shown in decimal units, like the rest of the catalog
_MAX_LINE_NAMES = 4


class State(Enum):
    NOT_INSTALLED = "not installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update available"
    FOLDER_MISSING = "folder missing"  # listed in catalog.json, folder gone (D-05)
    NOT_IN_CATALOG = "not in the catalog"  # a ThirdParty folder the record does not list (D-06)
    UNKNOWN = "unknown"  # catalog.json cannot be read (D-02)


class Check(Enum):
    NOT_CHECKED = "not checked"
    CURRENT = "current"
    AVAILABLE = "available"
    BRANCH_GONE = "branch gone"
    UNKNOWN = "unknown"  # GitHub could not be reached, or took too long


@dataclass(frozen=True)
class UpdateState:
    """The outcome of one update check: remote_sha is the commit the branch points at, None when it is not known."""

    id: str
    check: Check
    remote_sha: str | None
    checked_at: datetime | None


@dataclass(frozen=True)
class Row:
    """One row of the list. entry is the catalog record (None when not listed), curated the curated entry or None."""

    id: str
    name: str
    state: State
    licence_label: str
    licence_class: LicenceClass
    size_mb: int | None
    size_text: str
    entry: CatalogEntry | None
    curated: CuratedEntry | None
    folder: Path
    update: UpdateState | None


def size_text(mb: int | None) -> str:
    """`{n} MB` below 1000 MB, `{x.x} GB` from 1000 MB, `Unknown` when no size is known."""
    if mb is None:
        return "Unknown"
    if mb < MB_PER_GB:
        return f"{mb} MB"
    return f"{mb / MB_PER_GB:.1f} GB"


def _is_update(entry: CatalogEntry, update: UpdateState | None) -> bool:
    """True when the check found a commit that differs from the recorded one."""
    return (
        update is not None
        and update.check is Check.AVAILABLE
        and bool(update.remote_sha)
        and update.remote_sha != entry.commit
    )


def _folders(root: Path) -> dict[str, str]:
    """casefolded name -> name of every folder of ThirdParty, without .staging and dot folders."""
    try:
        children = list((Path(root) / THIRD_PARTY_DIR).iterdir())
    except OSError:
        return {}
    found: dict[str, str] = {}
    for child in children:
        if child.name == STAGING_DIR or child.name.startswith(".") or not child.is_dir():
            continue
        found[child.name.casefold()] = child.name
    return found


def row_statuses(
    root: Path,
    mf: "Manifest | Issue",
    *,
    curated: Iterable[CuratedEntry] = curated_list.CURATED,
    updates: Mapping[str, UpdateState] | None = None,
) -> list[Row]:
    """One row per curated library, per catalog entry that is not curated and per ThirdParty folder the record does not list.

    Never a row for .staging or a dot folder. Rows are sorted by name, case-insensitive, then id, so a status that
    changes never moves a row. mf may be the Issue catalog.json gave (D-02): every row is then UNKNOWN. updates
    holds the last update check per id; it only decides UPDATE_AVAILABLE (the remote differs from the recorded commit).
    """
    third = Path(root) / THIRD_PARTY_DIR
    folders = _folders(root)
    readable = not isinstance(mf, Issue)
    entries: tuple[CatalogEntry, ...] = mf.libraries if readable else ()
    updates = updates or {}
    rows: list[Row] = []
    seen: set[str] = set()

    def add(id: str, name: str, entry: CatalogEntry | None, known: CuratedEntry | None) -> None:
        key = id.casefold()
        seen.add(key)
        disk = folders.get(key)
        update = updates.get(id)
        if not readable:
            state = State.UNKNOWN
        elif entry is None:
            state = State.NOT_IN_CATALOG if disk is not None else State.NOT_INSTALLED
        elif disk is None:
            state = State.FOLDER_MISSING
        elif _is_update(entry, update):
            state = State.UPDATE_AVAILABLE
        else:
            state = State.INSTALLED
        proprietary = known.proprietary if known is not None else False
        if entry is not None:
            spdx, settled = entry.licence_spdx, True
        elif known is not None:
            spdx, settled = known.licence_spdx, True
        else:
            spdx, settled = None, False  # an unlisted folder: nothing is known about its licence
        size = known.size_mb if known is not None else None
        rows.append(
            Row(
                id=id,
                name=name,
                state=state,
                licence_label=licences.licence_label(spdx, proprietary=proprietary, known=settled),
                licence_class=licences.licence_class(spdx, proprietary=proprietary, known=settled),
                size_mb=size,
                size_text=size_text(size),
                entry=entry,
                curated=known,
                folder=third / (disk or id),
                update=update,
            )
        )

    for known in curated:
        add(known.id, known.name, next((e for e in entries if e.id.casefold() == known.id.casefold()), None), known)
    for entry in entries:
        if entry.id.casefold() not in seen:
            add(entry.id, names.display_name(entry.id, entry, curated=curated), entry, None)
    for key, name in folders.items():
        if key not in seen:
            add(name, name, None, None)
    rows.sort(key=lambda row: (row.name.casefold(), row.id.casefold()))
    return rows


# ── The update check ─────────────────────────────────────────────────

def _checked(entry: CatalogEntry, check: Check, sha: str | None, now: Callable[[], datetime]) -> UpdateState:
    return UpdateState(entry.id, check, sha, now() if check is not Check.NOT_CHECKED else None)


def check_updates(
    root: Path,
    mf: Manifest,
    net: gitnet.NetGit,
    *,
    cancel=None,
    on_one: Callable[[str, UpdateState], None] | None = None,
    now: Callable[[], datetime] = datetime.now,
) -> dict[str, UpdateState]:
    """One ls-remote per installed entry that has a folder; nothing is downloaded and no file is written (D-12, CAT-07).

    Each entry gives CURRENT (the remote commit equals the recorded one), AVAILABLE, BRANCH_GONE or UNKNOWN (the
    repository could not be reached) with this session's time. After the first timeout the remaining entries are
    UNKNOWN without asking (offline, D-32); once cancel is set the remaining ones are NOT_CHECKED. on_one(id, state)
    is called after each entry.
    """
    state: dict[str, UpdateState] = {}
    pending = sorted(
        (entry for entry in mf.libraries if manifest.entry_folder(root, entry).is_dir()),
        key=lambda entry: entry.id.casefold(),
    )
    offline = False
    stopped = False
    for entry in pending:
        if not stopped and cancel is not None and cancel.is_set():
            stopped = True
        if stopped:
            outcome = _checked(entry, Check.NOT_CHECKED, None, now)
        elif offline:
            outcome = _checked(entry, Check.UNKNOWN, None, now)
        else:
            try:
                head = gitnet.ls_remote(net, entry.url, entry.branch, cancel=cancel)
            except ValueError:  # a branch name git could read as an option
                head = None
            if isinstance(head, gitnet.RemoteHead):
                same = head.sha == entry.commit
                outcome = _checked(entry, Check.CURRENT if same else Check.AVAILABLE, head.sha, now)
            elif head is None:
                outcome = _checked(entry, Check.UNKNOWN, None, now)
            elif head.code == "git.branch_missing":
                outcome = _checked(entry, Check.BRANCH_GONE, None, now)
            elif head.code == "git.cancelled":
                stopped = True
                outcome = _checked(entry, Check.NOT_CHECKED, None, now)
            else:
                offline = offline or head.code == "git.timeout"
                outcome = _checked(entry, Check.UNKNOWN, None, now)
        state[entry.id] = outcome
        if on_one is not None:
            on_one(entry.id, outcome)
    return state


def update_count(states: Mapping[str, UpdateState], mf: Manifest) -> int:
    """How many listed libraries have a newer version according to states."""
    return sum(1 for entry in mf.libraries if _is_update(entry, states.get(entry.id)))


def updates_line(names: list[str]) -> str | None:
    """The one log line of a check that found updates (D-19), or None for none: the first 4 names, then "and {n} more"."""
    if not names:
        return None
    if len(names) == 1:
        return f"1 catalog library has an update: {names[0]}"
    shown = ", ".join(names[:_MAX_LINE_NAMES])
    if len(names) > _MAX_LINE_NAMES:
        shown += f" and {len(names) - _MAX_LINE_NAMES} more"
    return f"{len(names)} catalog libraries have updates: {shown}"

