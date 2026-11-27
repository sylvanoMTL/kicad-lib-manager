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
        vars={},
        kicad_var_models=0,
        licence_text=licence_text(folder),
        warnings=tuple(warnings),
    )
