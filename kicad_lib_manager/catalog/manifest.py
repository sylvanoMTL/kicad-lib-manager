"""catalog.json: the record of the third-party libraries cloned into ThirdParty/<id>/ (Phase 17, CAT-05, CAT-06, CAT-10).

One plain JSON file at the collection root, written atomically as UTF-8 with LF line endings and the same
bytes for the same catalog (entries sorted by id, fixed key order). The file is untrusted: it is hand
editable and may come from another machine, so load checks every field and gives one Issue, in plain words,
for the first problem it finds. Reading never raises: a missing file is an empty catalog. The folder of an
entry is derived (ThirdParty/<id>), never stored, so an edited file cannot point outside ThirdParty.
Qt-free.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .. import fsutil
from ..collection import CATALOG_FILE, THIRD_PARTY_DIR
from ..models import Issue, Severity
from . import urls

MANIFEST_NAME = CATALOG_FILE  # one name for the record file, shared with the collection checks
FORMAT = 1
MAX_MANIFEST_BYTES = 1024 * 1024

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_VAR_RE = re.compile(r"[A-Z][A-Z0-9_]{2,63}")
# names the catalog must never set: KiCad's own variables, the Plugin and Content Manager ones (KICAD<n>_3RD_PARTY and
# the per-version stock folders) and the two this app writes itself (CAT-10)
_KICAD_OWN = (
    re.compile(r"KICAD\d+_"),
    re.compile(r"KISYS"),
    re.compile(r".*_3RD_PARTY"),
    re.compile(r"KIPRJMOD"),
    re.compile(r"KICAD_(USER|SYSTEM)_TEMPLATE_DIR"),
    re.compile(r"KICAD_(CONFIG|DATA|STOCK_DATA|CACHE|STATE|DOCUMENTS)_HOME"),
    re.compile(r"KICAD_PATH"),
)
_APP_OWN = frozenset({"KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR"})
# KiCad exports its variables into its own process, so a name that matters to the system or to a program
# loader must not be settable from a downloaded catalog either
_SYSTEM_NAMES = frozenset(
    {
        "PATH", "PATHEXT", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
        "TEMP", "TMP", "TMPDIR", "COMSPEC", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "USERNAME", "SHELL",
        "PYTHONPATH", "PYTHONHOME", "NODE_OPTIONS",
    }
)
_SYSTEM_PREFIXES = ("LD_", "DYLD_", "PYTHON")
# KiCad's Plugin and Content Manager puts this in front of every library name it lists in the tables (D-33, D-34);
# the literal is used, KiCad's own setting for it is never read
PCM_PREFIX = "PCM_"


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    url: str
    branch: str
    commit: str = ""
    vars: dict[str, str] = field(default_factory=dict)
    licence_spdx: str | None = None
    acknowledged: bool = False
    acknowledged_on: str = ""
    added_on: str = ""
    known_dirty: tuple[str, ...] = ()
    name: str = ""  # the name the library was added with ("" for an entry written without one)
    nickname_prefix: str = ""  # the name rule decided at the check of the download: "" or PCM_PREFIX
    addon_id: str = ""  # KiCad's own id for a library added from its add-on list


@dataclass(frozen=True)
class Manifest:
    libraries: tuple[CatalogEntry, ...] = ()

    def find(self, id: str) -> CatalogEntry | None:
        """The entry with this id, compared case-insensitively."""
        key = id.casefold()
        return next((entry for entry in self.libraries if entry.id.casefold() == key), None)

    def with_entry(self, entry: CatalogEntry) -> "Manifest":
        """A copy with entry added, or replacing the entry of the same id."""
        key = entry.id.casefold()
        kept = tuple(e for e in self.libraries if e.id.casefold() != key)
        return Manifest((*kept, entry))


# ── Rules ────────────────────────────────────────────────────────────

def entry_folder(root: Path, entry_or_id: "CatalogEntry | str") -> Path:
    """root/ThirdParty/<id>: derived from the id, never read from the file."""
    id = entry_or_id if isinstance(entry_or_id, str) else entry_or_id.id
    return Path(root) / THIRD_PARTY_DIR / id


def valid_var_name(name: str) -> bool:
    """True for a variable name a library may set (WE_3DMODEL_DIR, SPARKFUN_KICAD_LIBRARY).

    KiCad's own names, the Plugin and Content Manager ones, this app's two and system names are refused (CAT-10).
    """
    if not isinstance(name, str) or _VAR_RE.fullmatch(name) is None:
        return False
    if name in _APP_OWN or name in _SYSTEM_NAMES or name.startswith(_SYSTEM_PREFIXES):
        return False
    return not any(pattern.match(name) for pattern in _KICAD_OWN)


def nickname_prefixes(mf: "Manifest") -> dict[str, str]:
    """Catalog id -> the prefix its library names get (PCM_PREFIX), for the entries that have one (D-34)."""
    return {entry.id: entry.nickname_prefix for entry in mf.libraries if entry.nickname_prefix}


def safe_var_folder(text: str) -> bool:
    """True for a folder inside a clone: relative, forward slashes, no .., no drive, no empty or dotted part."""
    if not isinstance(text, str):
        return False
    if text == "":
        return True
    if text.startswith("/") or "\\" in text or ":" in text or any(ord(ch) < 32 for ch in text):
        return False
    return all(part not in ("", ".", "..") and not part.endswith((".", " ")) for part in text.split("/"))


def path_vars(root: Path, entries) -> dict[str, str]:
    """VAR -> '<root>/ThirdParty/<id>/<folder>' with forward slashes, for the variables KiCad should get (CAT-06).

    A folder of '' maps to the clone itself, without a trailing slash. A name or folder the rules refuse is
    left out. Entries are taken in id order, so a variable two libraries both set gets the same value
    whatever order the entries come in.
    """
    base = str(root).replace("\\", "/")
    result: dict[str, str] = {}
    for entry in sorted(entries, key=lambda e: e.id.casefold()):
        clone = f"{base}/{THIRD_PARTY_DIR}/{entry.id}"
        for name, folder in entry.vars.items():
            if valid_var_name(name) and safe_var_folder(folder):
                result[name] = f"{clone}/{folder}" if folder else clone
    return result


# ── Reading ──────────────────────────────────────────────────────────

class _Refused(Exception):
    """Carries the plain-words reason a catalog.json cannot be used."""


def _refuse(text: str):
    raise _Refused(text)


def _is_date(text: str) -> bool:
    if _DATE_RE.fullmatch(text) is None:
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _id_label(raw: dict) -> str:
    """The id for a message when it is plain enough to show, else 'a library'."""
    id = raw.get("id")
    if isinstance(id, str) and id and len(id) <= 64 and id.isprintable():
        return id
    return "a library"


def _entry_from(raw, allow_file: bool) -> CatalogEntry:
    if not isinstance(raw, dict):
        _refuse("The library list holds an entry that is not a library record.")
    name = _id_label(raw)
    id = raw.get("id")
    if not urls.valid_id(id):
        if name == "a library":
            _refuse("A library in the list has no usable library name.")
        _refuse(f"The library name {name} cannot be used as a folder name.")
    url = raw.get("url")
    if not isinstance(url, str) or isinstance(urls.parse_github_url(url, allow_file=allow_file), Issue):
        _refuse(f"The web address of {name} is not a GitHub repository address.")
    branch = raw.get("branch")
    if not urls.valid_branch(branch):
        _refuse(f"The branch of {name} is not a branch name this app can use.")
    nickname_prefix = raw.get("nickname_prefix", "")
    if nickname_prefix not in ("", PCM_PREFIX):
        _refuse(f"{name} has a library-name rule this app does not know.")
    shown_name = raw.get("name", "")
    addon_id = raw.get("addon_id", "")
    commit = raw.get("commit", "")
    if not isinstance(commit, str) or (commit and _SHA_RE.fullmatch(commit) is None):
        _refuse(f"The version of {name} is not a 40-character version code.")
    raw_vars = raw.get("vars", {})
    if not isinstance(raw_vars, dict):
        _refuse(f"The path variables of {name} are not in a form this app understands.")
    for var, folder in raw_vars.items():
        if not valid_var_name(var):
            _refuse(f"{name} has a path variable that cannot be used.")
        if not isinstance(folder, str) or not safe_var_folder(folder):
            _refuse(f"{name} has a path variable that points outside its folder.")
    licence = raw.get("licence", {})
    spdx = licence.get("spdx") if isinstance(licence, dict) else None
    acknowledged = licence.get("acknowledged", False) if isinstance(licence, dict) else None
    acknowledged_on = licence.get("acknowledged_on", "") if isinstance(licence, dict) else None
    if (
        not isinstance(licence, dict)
        or not (spdx is None or (isinstance(spdx, str) and len(spdx) <= 64 and spdx.isprintable()))
        or not isinstance(acknowledged, bool)
        or not isinstance(acknowledged_on, str)
        or (acknowledged_on and not _is_date(acknowledged_on))
    ):
        _refuse(f"The licence record of {name} is not in a form this app understands.")
    added_on = raw.get("added_on", "")
    if not isinstance(added_on, str) or (added_on and not _is_date(added_on)):
        _refuse(f"The date {name} was added is not a date this app understands.")
    dirty = raw.get("known_dirty", [])
    if not isinstance(dirty, list) or not all(isinstance(p, str) and p and safe_var_folder(p) for p in dirty):
        _refuse(f"The list of changed files of {name} is not in a form this app understands.")
    return CatalogEntry(
        id=id,
        url=url,
        branch=branch,
        commit=commit,
        vars=dict(raw_vars),
        licence_spdx=spdx,
        acknowledged=acknowledged,
        acknowledged_on=acknowledged_on,
        added_on=added_on,
        known_dirty=tuple(dirty),
        name=shown_name if isinstance(shown_name, str) else "",
        nickname_prefix=nickname_prefix,
        addon_id=addon_id if isinstance(addon_id, str) else "",
    )


def _manifest_from(data, allow_file: bool) -> Manifest:
    if not isinstance(data, dict):
        _refuse(f"The library list {MANIFEST_NAME} is not in a form this app understands.")
    version = data.get("format")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        _refuse("The library list has no version number this app understands.")
    libraries = data.get("libraries")
    if not isinstance(libraries, list):
        _refuse(f"The library list {MANIFEST_NAME} holds no list of libraries.")
    entries = tuple(_entry_from(raw, allow_file) for raw in libraries)
    seen: dict[str, str] = {}
    for entry in entries:
        key = entry.id.casefold()
        if key in seen:
            _refuse(
                f"Two libraries in the list are called {seen[key]} and {entry.id}. Names that differ only in capital "
                "letters are the same folder on Windows."
            )
        seen[key] = entry.id
    return Manifest(entries)


def load(root: Path, *, allow_file: bool = False) -> Manifest | Issue:
    """Read root/catalog.json; a missing file is an empty Manifest, a bad one an Issue (never raises).

    A file larger than MAX_MANIFEST_BYTES is refused before it is parsed. A format number above FORMAT gives
    Issue catalog.newer_format: this app may read nothing from it and must not write it. allow_file is for tests
    that use a local repository as the upstream.
    """
    path = Path(root) / MANIFEST_NAME
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
    except FileNotFoundError:
        return Manifest()
    except OSError as e:
        return Issue(Severity.ERROR, "catalog.unreadable", f"The library list could not be read: {e.strerror or e}")
    if len(raw) > MAX_MANIFEST_BYTES:
        return Issue(Severity.ERROR, "catalog.unreadable", "The library list is larger than 1 MB, so it was not read.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return Issue(Severity.ERROR, "catalog.unreadable", f"The library list {MANIFEST_NAME} is not a text file this app can read.")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        data = None
    if isinstance(data, dict):
        version = data.get("format")
        if isinstance(version, int) and not isinstance(version, bool) and version > FORMAT:
            return Issue(
                Severity.ERROR,
                "catalog.newer_format",
                "The library list was written by a newer version of this app, so it is read-only here. "
                "Update the app to change it.",
            )
    try:
        return _manifest_from(data, allow_file)
    except _Refused as e:
        return Issue(Severity.ERROR, "catalog.unreadable", str(e))


# ── Writing ──────────────────────────────────────────────────────────

def _entry_to(entry: CatalogEntry) -> dict:
    return {
        "id": entry.id,
        "url": entry.url,
        "branch": entry.branch,
        "name": entry.name,
        "nickname_prefix": entry.nickname_prefix,
        "addon_id": entry.addon_id,
        "commit": entry.commit,
        "vars": dict(sorted(entry.vars.items())),
        "licence": {
            "spdx": entry.licence_spdx,
            "acknowledged": entry.acknowledged,
            "acknowledged_on": entry.acknowledged_on,
        },
        "added_on": entry.added_on,
        "known_dirty": list(entry.known_dirty),
    }


def save(root: Path, manifest: Manifest) -> Issue | None:
    """Write root/catalog.json atomically (entries sorted by id, fixed key order); an Issue on failure."""
    entries = sorted(manifest.libraries, key=lambda e: e.id.casefold())
    data = {"format": FORMAT, "libraries": [_entry_to(e) for e in entries]}
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return fsutil.atomic_write_text(Path(root) / MANIFEST_NAME, text)
