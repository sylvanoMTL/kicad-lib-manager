"""The library collection contract (Phase 15): folder names, sources, the folder check and the resolve order. Qt-free."""

import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from . import gitops
from .gitops import GitContext
from .models import Issue, Severity

OWN_DIR = "Custom"
SYMBOLS_DIR = "Symbols"
FOOTPRINTS_DIR = "Footprints"
MODELS_DIR = "3DModels"
SHARED_FOOTPRINT_LIBRARY = "Atomic_Footprints"
THIRD_PARTY_DIR = "ThirdParty"
PATH_LENGTH_WARNING = 100
# The folder the app's code lives in: a new collection is refused inside it, it is never a library folder
APP_DIR = Path(__file__).resolve().parent.parent


# ── Folder identity ─────────────────────────────────────────────────────────

def folder_key(value) -> str:
    """Comparison key of a folder: resolved, normalised separators, case-insensitive on Windows."""
    return os.path.normcase(os.path.normpath(str(Path(str(value).strip()).resolve())))


def absolute_folder(value) -> Path:
    """The folder as an absolute path, without touching the disk (a slow or missing drive must not block here).

    A relative folder would be saved, offered to KiCad as KICAD_LIB_GITHUB and compared against the
    working directory of the moment, so every folder that becomes the library folder passes through
    here. A blank text stays Path("") (it is never the working directory).
    """
    text = str(value).strip()
    return Path(os.path.abspath(text)) if text else Path("")


def same_folder(a, b) -> bool:
    """True when a and b name the same folder (same rule as kicad_setup.same_folder)."""
    return folder_key(a) == folder_key(b)


def spelling_key(value) -> str:
    """Comparison key of a folder text that never touches the disk, so a slow or missing drive cannot block it.

    Unlike folder_key it does not follow links or short names; use it where the GUI thread compares folders.
    """
    return os.path.normcase(os.path.normpath(os.path.abspath(str(value).strip())))


def same_spelling(a, b) -> bool:
    """True when a and b are the same folder text after normalising (no disk access)."""
    return spelling_key(a) == spelling_key(b)


def _holds_parts(folder: Path) -> bool:
    """True when folder holds a Symbols or a Footprints folder."""
    try:
        return (folder / SYMBOLS_DIR).is_dir() or (folder / FOOTPRINTS_DIR).is_dir()
    except OSError:
        return False


def is_collection(folder: Path) -> bool:
    """A collection is a folder whose Custom folder holds Symbols or Footprints."""
    try:
        own = Path(folder) / OWN_DIR
        return own.is_dir() and _holds_parts(own)
    except OSError:
        return False


def source_of(rel_path: str) -> str:
    """The source of a forward-slash repo-relative path: its first segment, or the id under ThirdParty."""
    parts = rel_path.split("/") if rel_path else []
    if parts and parts[0] == THIRD_PARTY_DIR and len(parts) > 1 and parts[1]:
        return parts[1]
    if parts and parts[0]:
        return parts[0]
    return "Unknown"


class Source(Enum):
    """Where the library folder came from; the values are the tag texts of the main window."""
    CLI = "set by --library-root"
    ENV = "set by KICAD_LIBMGR_ROOT"
    CHOSEN = "your choice"
    KICAD = "KiCad's folder"


# ── The folder check ────────────────────────────────────────────────────────

_GLYPHS = {"pass": "✓", "fail": "✖", "warn": "⚠"}


@dataclass(frozen=True)
class CheckRow:
    kind: str  # "pass" | "fail" | "warn" | "plain"
    text: str
    hint: str = ""  # the muted suffix

    @property
    def shown(self) -> str:
        glyph = _GLYPHS.get(self.kind)
        return f"{glyph} {self.text}" if glyph else self.text


@dataclass(frozen=True)
class FolderCheck:
    path: Path
    rows: tuple[CheckRow, ...]
    # collection, current, empty, missing, file, not_writable, drive_root, custom_folder,
    # not_collection, no_answer
    state: str
    length: int

    @property
    def usable(self) -> bool:
        return self.state in ("collection", "current")

    @property
    def can_create_here(self) -> bool:
        return self.state == "empty"

    @property
    def reason(self) -> str:
        for row in self.rows:
            if row.kind == "fail":
                return row.text
        return ""


def _fail(path: Path, rows: list[CheckRow], state: str, text: str, length: int) -> FolderCheck:
    rows.append(CheckRow("fail", text))
    return FolderCheck(path, tuple(rows), state, length)


def _is_empty(folder: Path) -> bool:
    try:
        return not any(folder.iterdir())
    except OSError:
        return False


def check_folder(path: "Path | str", *, current: Path | None = None) -> FolderCheck:
    """Check a folder for use as the library folder: exists, writable, layout, path length.

    Rows come in that order and stop at the first failure. A blank text is a missing
    folder (Path("") would be the working directory).
    """
    blank = isinstance(path, str) and not path.strip()
    folder = absolute_folder(path)
    length = len(str(folder)) if not blank else 0
    rows: list[CheckRow] = []

    # 1. exists
    try:
        if blank or not folder.exists():
            return _fail(folder, rows, "missing", "This folder does not exist. Choose another folder.", length)
        if not folder.is_dir():
            return _fail(folder, rows, "file", "This is a file, not a folder. Choose a folder.", length)
    except OSError:
        return _fail(folder, rows, "missing", "This folder does not exist. Choose another folder.", length)
    rows.append(CheckRow("pass", "This folder exists"))

    # 2. writable: decided by creating a temporary file, never os.access
    try:
        with tempfile.TemporaryFile(dir=folder):
            pass
    except OSError:
        return _fail(
            folder, rows, "not_writable",
            "You cannot write to this folder. Choose one you can write to.", length,
        )
    rows.append(CheckRow("pass", "You can write to this folder"))

    # 3. layout
    collection = is_collection(folder)
    if collection and current is not None and same_folder(folder, current):
        rows.append(CheckRow("plain", "You are already using this library folder."))
        return FolderCheck(folder, tuple(rows), "current", length)
    if collection:
        rows.append(CheckRow("pass", "It is a library collection", " (Custom holds Symbols or Footprints)"))
        state = "collection"
    elif _is_empty(folder):
        if folder.parent == folder:
            return _fail(
                folder, rows, "drive_root",
                f"{folder} is a whole drive. A collection needs its own folder: "
                "choose or create a folder inside it.",
                length,
            )
        rows.append(CheckRow(
            "plain",
            "This folder is empty, so it is not a library collection yet. "
            "Press New Library Collection... to start one in it.",
        ))
        return FolderCheck(folder, tuple(rows), "empty", length)
    elif folder.name.lower() == OWN_DIR.lower() and _holds_parts(folder):
        return _fail(
            folder, rows, "custom_folder",
            f"This looks like the Custom folder of a collection. Choose its parent folder instead: {folder.parent}.",
            length,
        )
    else:
        return _fail(
            folder, rows, "not_collection",
            "This is not a library collection: it has no Custom folder with Symbols or Footprints inside. "
            "To start a new collection, use New Library Collection... with an empty or new folder.",
            length,
        )

    # 4. path length, only for a collection
    if length > PATH_LENGTH_WARNING:
        rows.append(CheckRow(
            "warn",
            f"The path is {length} characters long. KiCad and git can fail on long Windows paths. "
            "A shorter folder such as C:/KiCad_Libraries is safer.",
        ))
    return FolderCheck(folder, tuple(rows), state, length)


def no_answer(path: "Path | str") -> FolderCheck:
    """The check result for a folder whose drive did not answer in time."""
    folder = absolute_folder(path)
    row = CheckRow("fail", "The drive did not answer within 5 seconds.")
    return FolderCheck(folder, (row,), "no_answer", len(str(folder)))


# ── The resolve order ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Candidate:
    path: "Path | str"  # a blank string stays blank: it is never the working directory
    source: Source


@dataclass(frozen=True)
class Resolution:
    root: Path | None
    source: Source | None
    notes: tuple[Issue, ...] = ()
    fatal: str | None = None
    notice: str | None = None


def _chosen_note(chosen: Candidate, result: FolderCheck, nxt: Candidate | None) -> tuple[Issue, str | None]:
    """The note for a skipped CHOSEN folder, and the first-run notice when nothing else won."""
    missing = result.state == "missing"
    if missing:
        head = f"The library folder you chose earlier no longer exists: {chosen.path}."
    else:
        head = f"The library folder you chose earlier cannot be used ({result.reason}): {chosen.path}."
    if nxt is None:
        text = f"{head} Choose a library folder to continue."
        if missing:
            notice = f"The library folder you used before is gone: {chosen.path}."
        else:
            notice = f"The library folder you used before cannot be used ({result.reason}): {chosen.path}."
        return Issue(Severity.WARNING, "library.chosen_skipped", text), notice
    where = f"KiCad's folder ({nxt.path})"
    return Issue(Severity.WARNING, "library.chosen_skipped", f"{head} Using {where} instead."), None


def resolve_library_root(
    candidates: Iterable[Candidate],
    check: Callable[["Path | str"], FolderCheck] = check_folder,
) -> Resolution:
    """Pick the library folder: the first candidate that passes the check, in the order given.

    A failing CLI or ENV candidate is fatal and never falls back to another folder.
    A failing CHOSEN or KICAD candidate is skipped with a warning note.
    """
    notes: list[Issue] = []
    held: tuple[Candidate, FolderCheck] | None = None
    for candidate in candidates:
        result = check(candidate.path)
        if result.usable:
            if held is not None:
                note, _ = _chosen_note(held[0], held[1], candidate)
                notes.append(note)
            return Resolution(absolute_folder(candidate.path), candidate.source, tuple(notes))
        if candidate.source is Source.CLI:
            return Resolution(None, None, tuple(notes), fatal=f"--library-root: {candidate.path} cannot be used: {result.reason}")
        if candidate.source is Source.ENV:
            return Resolution(None, None, tuple(notes), fatal=f"KICAD_LIBMGR_ROOT: {candidate.path} cannot be used: {result.reason}")
        if candidate.source is Source.CHOSEN:
            held = (candidate, result)
        elif candidate.source is Source.KICAD:
            notes.append(Issue(
                Severity.WARNING, "library.kicad_skipped",
                f"Not using KiCad's folder {candidate.path}: {result.reason}",
            ))
    notice = None
    if held is not None:
        note, notice = _chosen_note(held[0], held[1], None)
        notes.append(note)
    return Resolution(None, None, tuple(notes), notice=notice)


# ── A new collection (ROOT-06, D4) ──────────────────────────────────────────

GITIGNORE_TEXT = "\n".join([
    "# KiCad temporary and backup files",
    "*.bak",
    "*.bck",
    "*-backups",
    "*.kicad_prl",
    "*~",
    "_autosave-*",
    "*.tmp",
    "fp-info-cache",
    "~*.lck",
    "\\#auto_saved_files#",
    "",
])

README_TEXT = "\n".join([
    "# KiCad library collection",
    "",
    "This folder holds your own KiCad parts.",
    "",
    "- `Symbols/` holds one `Atomic_<KiCad symbol library>.kicad_sym` file per category, such as `Atomic_Connector`.",
    "- `Footprints/Atomic_Footprints.pretty/` holds every footprint.",
    "- `3DModels/` holds the 3D models, one `<MPN>.<ext>` file per part, linked as `${CUSTOM_3DMODEL_DIR}/<file>`.",
    "",
    "Every part in an `Atomic_` library follows the atomic rule:",
    "",
    "- `MPN` and `Manufacturer` are set",
    "- `Footprint` resolves to exactly one `Lib:FP`",
    "- `Value` is the `MPN`",
    "- `Datasheet` and `Description` are set",
    "- its 3D model file exists",
    "",
    "This folder is its own git repository on branch main. Nothing was committed when it was created: "
    "commit your first part from the import window.",
    "",
])

_CHARS_TEXT = 'A folder name cannot contain \\ / : * ? " < > | or end with a space or a dot.'
_BAD_CHARS = frozenset('\\/:*?"<>|')
_GIT_NAME_TEXT = (
    "A collection cannot be named .git: git keeps its own data in a folder with that name. Choose another name."
)
_LEADING_SPACE_TEXT = "A folder name cannot start with a space. Choose another name."
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{n}" for n in (*range(1, 10), "¹", "²", "³")}
    | {f"LPT{n}" for n in (*range(1, 10), "¹", "²", "³")}
)
_DRIVE_ROOT_TEXT = "{path} is a whole drive. A collection needs its own folder: choose or create a folder inside it."
_GIT_MISSING_TEXT = (
    "Git was not found. A collection needs Git to commit your parts. Install Git for Windows, then try again."
)


def validate_collection_name(name: str) -> CheckRow | None:
    """The failing row for a collection folder name, or None when the name is fine on every platform."""
    if not name.strip():
        return CheckRow("fail", "Enter a name for the collection folder.")
    if any(ch in _BAD_CHARS or ord(ch) < 32 for ch in name) or name[-1] in " .":
        return CheckRow("fail", _CHARS_TEXT)
    if name.lower() == ".git":  # every walker prunes a .git folder, so such a collection could never be scanned
        return CheckRow("fail", _GIT_NAME_TEXT)
    if name[0] == " ":
        return CheckRow("fail", _LEADING_SPACE_TEXT)
    if name.split(".", 1)[0].upper() in _RESERVED_NAMES:
        return CheckRow("fail", f"{name} is a reserved name in Windows. Choose another name.")
    return None


def program_files_folders(environ=None) -> list[str]:
    """The Program Files folders named by %ProgramFiles%, %ProgramFiles(x86)% and %ProgramW6432%, when set."""
    env = {str(key).upper(): value for key, value in (os.environ if environ is None else environ).items()}
    found = (env.get(var.upper(), "") for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"))
    return [value for value in found if value and value.strip()]


def _inside(path, folder) -> bool:
    """True when path is folder or lies below it; compared on whole path parts, never on a text prefix."""
    key, base = folder_key(path), folder_key(folder)
    if key == base:
        return True
    return key.startswith(base if base.endswith(os.sep) else base + os.sep)


@dataclass(frozen=True)
class NewCollectionCheck:
    target: Path | None
    rows: tuple[CheckRow, ...]
    existing_empty: bool = False  # the target exists, is empty and will be used

    @property
    def blocked(self) -> bool:
        return any(row.kind == "fail" for row in self.rows)


def check_new_collection(
    parent: "Path | str",
    name: str,
    *,
    git_found: bool,
    app_dir: Path = APP_DIR,
    environ=None,
) -> NewCollectionCheck:
    """The issue rows (UI-SPEC rows 1 to 11, in that order) for creating collection `name` inside `parent`."""
    rows: list[CheckRow] = []
    if not git_found:
        rows.append(CheckRow("fail", _GIT_MISSING_TEXT))

    # 2 and 3: the parent
    parent_text = str(parent).strip()
    folder = absolute_folder(parent_text) if parent_text else None
    try:
        parent_ok = folder is not None and folder.is_dir()
    except OSError:
        parent_ok = False
    if not parent_ok:
        rows.append(CheckRow("fail", "The parent folder does not exist. Choose an existing folder."))
    else:
        try:
            with tempfile.TemporaryFile(dir=folder):
                pass
        except OSError:
            rows.append(CheckRow("fail", f"You cannot write to {folder}. Choose a folder you can write to."))

    # 4 and 5: the name
    name_row = validate_collection_name(name)
    if name_row is not None:
        rows.append(name_row)
    if not parent_ok or name_row is not None:
        return NewCollectionCheck(None, tuple(rows))

    target = folder / name
    if folder_key(target.parent) != folder_key(folder):  # a name must never leave the parent folder
        rows.append(CheckRow("fail", _CHARS_TEXT))
        return NewCollectionCheck(None, tuple(rows))

    # 6 and 7: places a program cannot or must not write
    if any(_inside(target, pf) for pf in program_files_folders(environ)):
        rows.append(CheckRow(
            "fail",
            f"{target} is inside Program Files, which programs cannot normally write to. "
            "Choose a folder in your Documents or on another drive.",
        ))
    if _inside(target, app_dir):
        rows.append(CheckRow("fail", f"{target} is inside the app's own folder ({app_dir}). Choose another location."))

    # 8 to 10: what the target already is
    existing_empty = False
    try:
        if target.is_dir():
            if _is_empty(target):
                existing_empty = True
            elif is_collection(target):
                rows.append(CheckRow(
                    "fail",
                    f"{target} already holds a library collection. Use File > Open Library Collection... to open it.",
                ))
            else:
                rows.append(CheckRow("fail", f"{target} is not empty. Choose an empty folder or a new name."))
        elif target.exists():
            rows.append(CheckRow("fail", f"{target} is a file. Choose another name."))
    except OSError:
        rows.append(CheckRow("fail", f"{target} is not empty. Choose an empty folder or a new name."))
    if existing_empty:
        rows.append(CheckRow("plain", "This folder already exists and is empty. It will be used."))

    # 11: the path length warns only
    length = len(str(target))
    if length > PATH_LENGTH_WARNING:
        rows.append(CheckRow(
            "warn",
            f"The path is {length} characters long. KiCad and git can fail on long Windows paths. "
            "A shorter folder such as C:/KiCad_Libraries is safer.",
        ))
    return NewCollectionCheck(target, tuple(rows), existing_empty)


def _force_remove(func, path, _exc):
    """Clear the read-only bit and retry: files inside .git are read-only on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_tree(folder: Path) -> None:
    """Delete a folder with everything in it, read-only files included (a plain rmtree fails on .git)."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(folder, onexc=_force_remove)
    else:
        shutil.rmtree(folder, onerror=_force_remove)


def _write_new(path: Path, data: bytes) -> None:
    """Create a file that must not exist yet (never overwrites) and write data to it."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o666)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _failure_reason(error: OSError) -> str:
    text = error.strerror or str(error)
    return f"{text} ({error.filename})" if error.filename else text


def _cleanup(created: list[Path], *, empty_only: Path | None = None) -> bool:
    """Remove this call's own paths in reverse order; True when every one is gone.

    The folder `empty_only` goes only when nothing else is in it: something written there by another
    program (a sync client, an editor) is not ours to delete.
    """
    for path in reversed(created):
        try:
            if empty_only is not None and path == empty_only:
                path.rmdir()
            elif path.is_dir() and not path.is_symlink():
                _remove_tree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass
    return not any(path.exists() for path in created)


def create_collection(
    target: Path,
    ctx: GitContext,
    *,
    app_dir: Path = APP_DIR,
    environ=None,
) -> list[Issue]:
    """Create an empty collection at target: the Custom skeleton, then git init inside Custom. Nothing is committed (D4).

    Returns no issues on success. A refusal returns before anything is created; a failure removes
    everything this call created (a target folder that existed before is kept).
    """
    target = absolute_folder(target)
    if target.parent == target:
        return [Issue(Severity.ERROR, "collection.refused", _DRIVE_ROOT_TEXT.format(path=target))]
    check = check_new_collection(target.parent, target.name, git_found=True, app_dir=app_dir, environ=environ)
    for row in check.rows:
        if row.kind == "fail":
            return [Issue(Severity.ERROR, "collection.refused", row.text)]
    version = gitops.git_version(ctx)
    if version is None:
        return [Issue(Severity.ERROR, "collection.git_missing", _GIT_MISSING_TEXT)]
    if version < gitops.INIT_MIN_VERSION:
        found = ".".join(str(part) for part in version)
        return [Issue(
            Severity.ERROR, "collection.git_too_old",
            f"Git 2.28 or newer is needed to create a collection (found {found}). Update Git for Windows, then try again.",
        )]

    own = target / OWN_DIR
    pretty = own / FOOTPRINTS_DIR / f"{SHARED_FOOTPRINT_LIBRARY}.pretty"
    folders = [own, own / SYMBOLS_DIR, own / FOOTPRINTS_DIR, pretty, own / MODELS_DIR]
    files = [
        (own / SYMBOLS_DIR / ".gitkeep", b""),
        (pretty / ".gitkeep", b""),
        (own / MODELS_DIR / ".gitkeep", b""),
        (own / ".gitignore", GITIGNORE_TEXT.encode("utf-8")),
        (own / "README.md", README_TEXT.encode("utf-8")),
    ]
    created: list[Path] = []
    made_target: Path | None = None
    reason = ""
    try:
        if not target.exists():
            target.mkdir()
            created.append(target)
            made_target = target
        for folder in folders:
            folder.mkdir()  # never exist_ok: a folder that is already there is not ours to fill
            created.append(folder)
        for path, data in files:
            _write_new(path, data)
            created.append(path)
        done = gitops.init_repository(ctx, own)
        if isinstance(done, Issue):
            reason = done.text
        elif done.returncode != 0:
            reason = done.output or f"git init exited with code {done.returncode}"
    except OSError as e:
        reason = _failure_reason(e)
    except Exception as e:  # anything unexpected must still clean up what this call created
        reason = f"{type(e).__name__}: {e}"
    if not reason:
        return []

    issues = [Issue(
        Severity.ERROR, "collection.create_failed",
        f"Could not create the collection: {reason.strip().removesuffix('.')}. "
        "Choose another name or folder, then try again.",
    )]
    if not _cleanup(created, empty_only=made_target):
        issues.append(Issue(
            Severity.ERROR, "collection.leftovers",
            f"Some folders were left behind in {target}. Delete them and try again.",
        ))
    return issues
