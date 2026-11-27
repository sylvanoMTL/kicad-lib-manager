"""The staging check of the library catalog (Phase 17 plan 06; CAT-02, CAT-03, CAT-08, CAT-10, D-13, D-20, D-23).

Decides from files alone whether a download may become a catalog library, and what the Add preview shows
about it. Nothing from the download is run, imported or opened as code: every file is only listed, sized or
read as text, and links are never followed. Qt-free.

Refusals come in a fixed order and stop at the first one: no KiCad libraries, KiCad 5 only, Plugin and
Content Manager only, Git LFS, a symbolic link or junction. Their texts are the refusal copy of the catalog
UI contract.
"""

import json
import os
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .. import kicad_files, library_scanner
from ..models import Issue, Severity

NO_LIBRARIES_TEXT = "This repository holds no KiCad symbol or footprint libraries, so there is nothing to add."
KICAD5_TEXT = (
    "This repository only has libraries in the old KiCad 5 format (.lib files). "
    "The catalog adds libraries for KiCad 6 and newer."
)
PCM_ONLY_TEXT = (
    "This repository only provides its libraries as a KiCad Plugin and Content Manager package, "
    "not as library files. Install it from KiCad (Plugin and Content Manager) instead."
)
LFS_TEXT = (
    "This library keeps its 3D models in Git LFS, "
    "which the catalog does not support. Nothing was added."
)
KICAD_VARS_TEXT = "{n} 3D models use KiCad's own path variables; they show only in a matching KiCad version."
KICAD_VARS_ONE_TEXT = "1 3D model uses KiCad's own path variables; it shows only in a matching KiCad version."
SUBMODULES_TEXT = "This repository uses Git submodules; submodules are not downloaded, so what they hold is missing."

MAX_LICENCE_BYTES = 64 * 1024
LICENCE_CUT_NOTE = "\n\n[The rest of the licence file is not shown.]"
# a Git LFS pointer file is tiny and starts with this line
LFS_POINTER_HEAD = b"version https://git-lfs.github.com/spec/v1"
LFS_POINTER_MAX = 1024
_LFS_ATTR_RE = re.compile(r"(?:^|\s)filter=lfs(?:\s|$)")
_MAX_ATTR_BYTES = 64 * 1024
_MAX_METADATA_BYTES = 64 * 1024
# licence files at the root, in the order they are looked for
_LICENCE_PREFIXES = ("license", "licence", "unlicense", "copying")
# files that do not count as content when a download holds nothing but .zip packages
_DOC_PREFIXES = ("readme", "license", "licence", "unlicense", "copying", "changelog")
_DOT_FILES = frozenset({".gitignore", ".gitattributes", ".gitmodules", ".editorconfig"})
_PCM_NAMES = frozenset({"repository.json", "packages.json"})

# a variable's folder is the one where at least this share of its sampled model paths exist
MIN_SHARE_PERCENT = 80
SAMPLE_LIMIT = 200
_VAR_MODEL_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}/(.*)", re.DOTALL)
# Module-private copies of the catalog.manifest variable rules (catalog.validate may not import it); the tests pin both
# copies to the same cases. KiCad's own variables and the Plugin and Content Manager ones are never mapped (CAT-10).
_VAR_RE = re.compile(r"[A-Z][A-Z0-9_]{2,63}")
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
_SYSTEM_NAMES = frozenset(
    {
        "PATH", "PATHEXT", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
        "TEMP", "TMP", "TMPDIR", "COMSPEC", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "USERNAME", "SHELL",
        "PYTHONPATH", "PYTHONHOME", "NODE_OPTIONS",
    }
)
_SYSTEM_PREFIXES = ("LD_", "DYLD_", "PYTHON")

KIND_SYMBOL = "Symbol"
KIND_FOOTPRINT = "Footprint"
CLASHES_STOCK = "a KiCad library"


@dataclass(frozen=True)
class Collision:
    """A library of the download whose nickname another library already uses."""

    nickname: str
    kind: str  # "Symbol" or "Footprint"
    clashes_with: str  # "a KiCad library", "your Atomic_ libraries", "your Custom libraries" or a catalog name


@dataclass(frozen=True)
class StagingReport:
    """What the Add preview shows about an accepted download."""

    symbol_libs: tuple[str, ...]  # nicknames, sorted
    footprint_libs: tuple[str, ...]
    collisions: tuple[Collision, ...]
    vars: dict[str, str]  # non-KiCad path variable -> clone folder the models are under ('' = the clone itself)
    kicad_var_models: int  # models that use KiCad's own variables, never mapped
    licence_text: str | None
    warnings: tuple[Issue, ...]


@dataclass
class _Tree:
    """One pass over a download."""

    symbol_libs: list[str]
    footprint_libs: list[str]
    mod_files: list[Path]
    lib_files: int = 0
    zips: int = 0
    other_files: int = 0
    pcm_candidates: list[Path] = field(default_factory=list)
    lfs: bool = False
    links: list[str] = field(default_factory=list)
    gitmodules: bool = False


def _is_link(path: Path) -> bool:
    """True for a symbolic link or, on Windows, a junction; neither is ever followed."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def _issue(code: str, text: str) -> Issue:
    return Issue(Severity.ERROR, code, text)


def _read_head(path: Path, limit: int) -> bytes | None:
    try:
        with open(path, "rb") as handle:
            return handle.read(limit)
    except OSError:
        return None


def _holds_lfs_attr(path: Path) -> bool:
    data = _read_head(path, _MAX_ATTR_BYTES)
    if data is None:
        return False
    for line in data.decode("utf-8", errors="replace").splitlines():
        text = line.strip()
        if text and not text.startswith("#") and _LFS_ATTR_RE.search(text):
            return True
    return False


def _is_lfs_pointer(path: Path) -> bool:
    try:
        if path.stat().st_size >= LFS_POINTER_MAX:
            return False
    except OSError:
        return False
    head = _read_head(path, 100)
    return head is not None and head.startswith(LFS_POINTER_HEAD)


def _nickname_key(text: str) -> tuple[str, str]:
    return (text.casefold(), text)


def _is_doc(name: str) -> bool:
    low = name.casefold()
    return low in _DOT_FILES or low.startswith(_DOC_PREFIXES)


def _walk(folder: Path) -> _Tree:
    """List a download: its libraries, footprint files, markers and links. .git is never entered."""
    tree = _Tree([], [], [])
    for current, dirnames, filenames in os.walk(folder):
        here = Path(current)
        keep = []
        for name in dirnames:
            if name == ".git":
                continue
            if _is_link(here / name):
                tree.links.append((here / name).relative_to(folder).as_posix())
                continue
            keep.append(name)
            if name.casefold().endswith(".pretty"):
                tree.footprint_libs.append(name[: -len(".pretty")])
        dirnames[:] = keep
        for name in filenames:
            path = here / name
            if name == ".git":
                continue
            if _is_link(path):
                tree.links.append(path.relative_to(folder).as_posix())
                continue
            low = name.casefold()
            if low.endswith(".kicad_sym"):
                tree.symbol_libs.append(name[: -len(".kicad_sym")])
            elif low.endswith(".kicad_mod"):
                tree.mod_files.append(path)
            elif low.endswith(".lib"):
                tree.lib_files += 1
            if low == ".gitattributes" and _holds_lfs_attr(path):
                tree.lfs = True
            elif low == ".gitmodules":
                tree.gitmodules = True
            if low in _PCM_NAMES or low == "metadata.json":
                tree.pcm_candidates.append(path)
            if low.endswith(".zip"):
                tree.zips += 1
            elif not _is_doc(name) and not low.endswith((".kicad_sym", ".kicad_mod", ".lib", ".dcm")):
                tree.other_files += 1
            if not tree.lfs and _is_lfs_pointer(path):
                tree.lfs = True
    tree.symbol_libs.sort(key=_nickname_key)
    tree.footprint_libs.sort(key=_nickname_key)
    tree.mod_files.sort()
    return tree


def _has_pcm_marker(tree: _Tree) -> bool:
    """A metadata.json that names a KiCad schema, repository.json, packages.json, or a .zip as the only content."""
    for path in tree.pcm_candidates:
        if path.name.casefold() in _PCM_NAMES:
            return True
        data = _read_head(path, _MAX_METADATA_BYTES)
        if data is None:
            continue
        try:
            schema = json.loads(data.decode("utf-8", errors="replace")).get("$schema")
        except (ValueError, AttributeError):
            continue
        if isinstance(schema, str) and "kicad" in schema.casefold():
            return True
    return tree.zips > 0 and tree.other_files == 0


def licence_text(folder: Path) -> str | None:
    """The text of the root licence file (LICENSE*, UNLICENSE*, COPYING*), cut at 64 KB with a note; None if absent."""
    try:
        names = sorted(os.listdir(folder), key=_nickname_key)
    except OSError:
        return None
    for prefix in _LICENCE_PREFIXES:
        for name in names:
            path = Path(folder) / name
            if not name.casefold().startswith(prefix) or _is_link(path) or not path.is_file():
                continue
            data = _read_head(path, MAX_LICENCE_BYTES + 1)
            if data is None:
                continue
            cut = len(data) > MAX_LICENCE_BYTES
            text = data[:MAX_LICENCE_BYTES].decode("utf-8", errors="replace").lstrip("﻿")
            text = text.replace("\r\n", "\n")
            return text + LICENCE_CUT_NOTE if cut else text
    return None


def _is_kicad_own(name: str) -> bool:
    """True for a variable KiCad or its Plugin and Content Manager sets (KICAD8_3RD_PARTY, KISYS3DMOD, ...)."""
    return any(pattern.match(name) for pattern in _KICAD_OWN)


def _mappable(name: str) -> bool:
    """True for a variable name a library may map to a folder; the rule of catalog.manifest.valid_var_name."""
    if _VAR_RE.fullmatch(name) is None:
        return False
    if name in _APP_OWN or name in _SYSTEM_NAMES or name.startswith(_SYSTEM_PREFIXES):
        return False
    return not _is_kicad_own(name)


def _safe_folder(text: str) -> bool:
    """True for a folder inside a clone: relative, forward slashes, no .., no drive, no empty or dotted part."""
    if text == "":
        return True
    if text.startswith("/") or "\\" in text or ":" in text or any(ord(ch) < 32 for ch in text):
        return False
    return all(part not in ("", ".", "..") and not part.endswith((".", " ")) for part in text.split("/"))


def _clone_files(folder: Path) -> list[str]:
    """Every file of the clone as a forward-slash relative path; .git is skipped and links are never followed."""
    found: list[str] = []
    for current, dirnames, filenames in os.walk(folder):
        here = Path(current)
        dirnames[:] = [d for d in dirnames if d != ".git" and not _is_link(here / d)]
        base = here.relative_to(folder)
        found.extend((base / n).as_posix() for n in filenames if n != ".git" and not _is_link(here / n))
    return found


def _index(files: list[str]) -> dict[str, list[str]]:
    """Clone files by their last path component and by their last two (<x>.3dshapes/<file>)."""
    index: dict[str, list[str]] = {}
    for rel in files:
        parts = rel.split("/")
        index.setdefault(parts[-1], []).append(rel)
        if len(parts) > 1:
            index.setdefault("/".join(parts[-2:]), []).append(rel)
    return index


def _sample(paths: set[str]) -> list[str]:
    """At most SAMPLE_LIMIT of the paths, spread evenly over the sorted list."""
    ordered = sorted(paths)
    step = -(-len(ordered) // SAMPLE_LIMIT)
    return ordered[::step] if step > 1 else ordered


def _folders_of(rest: str, index: dict[str, list[str]]) -> set[str]:
    """The clone folders under which the model path `rest` exists (exact letter case)."""
    parts = rest.split("/")
    if not rest or any(part in ("", ".", "..") for part in parts):
        return set()
    found: set[str] = set()
    for rel in index.get("/".join(parts[-2:]), ()):
        if rel == rest:
            found.add("")
        elif rel.endswith("/" + rest):
            found.add(rel[: -len(rest) - 1])
    return {folder for folder in found if _safe_folder(folder)}


def detect_vars(folder: Path, footprint_files: list[Path]) -> tuple[dict[str, str], int]:
    """The path variables the footprint models need, and how many models use KiCad's own variables (CAT-10).

    For each non-KiCad ${VAR}/rest model path, looks for `rest` in the clone and takes the folder that holds
    at least MIN_SHARE_PERCENT % of up to SAMPLE_LIMIT sampled paths of that variable (the shorter folder when two
    tie). The result maps VAR to that clone-relative folder ('' is the clone itself). Variables of KiCad and of
    the Plugin and Content Manager are counted, never mapped. A variable with no such folder is left out.
    """
    wanted: dict[str, set[str]] = {}
    kicad_models = 0
    for mod_file in footprint_files:
        loaded = kicad_files.load(mod_file)
        if isinstance(loaded, Issue):
            continue
        name = kicad_files.footprint_name(loaded.root)
        if name is None:
            continue
        for model in kicad_files.find_models(name.node):
            match = _VAR_MODEL_RE.match(model.path)
            if match is None:
                continue
            var, rest = match.groups()
            if _is_kicad_own(var):
                kicad_models += 1
            elif _mappable(var):
                wanted.setdefault(var, set()).add(rest)
    if not wanted:
        return {}, kicad_models
    index = _index(_clone_files(Path(folder)))
    mapping: dict[str, str] = {}
    for var, rests in sorted(wanted.items()):
        sample = _sample(rests)
        votes: dict[str, int] = {}
        for rest in sample:
            for where in _folders_of(rest, index):
                votes[where] = votes.get(where, 0) + 1
        # most paths first; on a tie the shorter folder, then the name, so the answer never depends on file order
        ranked = sorted(votes.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
        if ranked and ranked[0][1] * 100 >= MIN_SHARE_PERCENT * len(sample):
            mapping[var] = ranked[0][0]
    return mapping, kicad_models


def unresolved_models(folder: Path, vars: Mapping[str, str]) -> list[str]:
    """The model paths of the clone's footprints that a mapped variable points at and that do not exist.

    Names are compared exactly, case included, by library_scanner.unresolved_var_models: the dialog, the scan rule
    and the conversion script share this one check (D-26 check 3, D-31).
    """
    folder = Path(folder)
    mod_files = sorted(folder / rel for rel in _clone_files(folder) if rel.casefold().endswith(".kicad_mod"))
    return library_scanner.unresolved_var_models(folder, mod_files, vars)


def find_collisions(
    symbol_libs: Collection[str],
    footprint_libs: Collection[str],
    *,
    stock_fp: Collection[str],
    stock_sym: Collection[str],
    own: Mapping[str, str],
    other_catalog: Mapping[str, str],
) -> tuple[Collision, ...]:
    """The libraries of a download whose nickname another library already has (D-20, CAT-08).

    Symbol libraries meet KiCad's stock symbol libraries and footprint libraries its stock footprint libraries;
    own (Atomic_ and Custom libraries, nickname -> wording) and other_catalog (nickname -> catalog name) are
    compared by nickname alone. A library that clashes with several gets one row, the first of those three.
    Nothing is renamed. Symbols come first, each kind sorted by nickname.
    """
    rows: list[Collision] = []
    for kind, nicknames, stock in ((KIND_SYMBOL, symbol_libs, stock_sym), (KIND_FOOTPRINT, footprint_libs, stock_fp)):
        for nickname in sorted(set(nicknames), key=_nickname_key):
            if nickname in stock:
                rows.append(Collision(nickname, kind, CLASHES_STOCK))
            elif nickname in own:
                rows.append(Collision(nickname, kind, own[nickname]))
            elif nickname in other_catalog:
                rows.append(Collision(nickname, kind, other_catalog[nickname]))
    return tuple(rows)


def validate_staging(
    folder: Path,
    *,
    stock_fp: Collection[str],
    stock_sym: Collection[str],
    own: Mapping[str, str],
    other_catalog: Mapping[str, str],
) -> "StagingReport | Issue":
    """Check a downloaded folder: an Issue (the first refusal) or the report the Add preview shows.

    Reads files only. own maps a nickname of the collection's own libraries to the wording of the clash
    ("your Atomic_ libraries", "your Custom libraries"); other_catalog maps a nickname to the catalog
    library that has it.
    """
    folder = Path(folder)
    tree = _walk(folder)
    if not tree.symbol_libs and not tree.footprint_libs:
        if tree.lib_files:
            return _issue("catalog.kicad5_only", KICAD5_TEXT)
        if _has_pcm_marker(tree):
            return _issue("catalog.pcm_only", PCM_ONLY_TEXT)
        return _issue("catalog.no_libraries", NO_LIBRARIES_TEXT)
    if tree.lfs:
        return _issue("catalog.lfs", LFS_TEXT)
    if tree.links:
        return _issue(
            "catalog.link",
            f"This download contains a shortcut to another folder ({tree.links[0]}), "
            "which the catalog does not accept. Nothing was added.",
        )
    warnings: list[Issue] = []
    if tree.gitmodules:
        warnings.append(Issue(Severity.WARNING, "catalog.submodules", SUBMODULES_TEXT))
    needed_vars, kicad_var_models = detect_vars(folder, tree.mod_files)
    if kicad_var_models == 1:
        warnings.append(Issue(Severity.WARNING, "catalog.kicad_vars", KICAD_VARS_ONE_TEXT))
    elif kicad_var_models:
        warnings.append(Issue(Severity.WARNING, "catalog.kicad_vars", KICAD_VARS_TEXT.format(n=kicad_var_models)))
    return StagingReport(
        symbol_libs=tuple(tree.symbol_libs),
        footprint_libs=tuple(tree.footprint_libs),
        collisions=find_collisions(
            tree.symbol_libs,
            tree.footprint_libs,
            stock_fp=stock_fp,
            stock_sym=stock_sym,
            own=own,
            other_catalog=other_catalog,
        ),
        vars=needed_vars,
        kicad_var_models=kicad_var_models,
        licence_text=licence_text(folder),
        warnings=tuple(warnings),
    )
