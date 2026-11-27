"""Which libraries of a catalog source start ticked after an Add, Reinstall or Update (CAT-05, CAT-08, CAT-12, D-20, D-28).

Qt-free and disk-free: it only changes the selected flags of a ScanResult the main window owns.

The rule: every library of the source starts ticked, except one that shares its nickname with another library
(it starts unticked, nothing is ever renamed). A curated library that replaces an older folder (its
legacy_prefix, for example the Wurth submodule) moves the owner's ticks instead: a library whose twin
<legacy_prefix><rest> was ticked is ticked and the twin unticked, so one Generate Tables rewrites the entries
that pointed into the old folder.
"""

from dataclasses import dataclass

from ..models import ScanResult


@dataclass(frozen=True)
class SelectionChange:
    """What preselect_source did: libraries of the source ticked now, nicknames left unticked, ticks moved off twins."""

    selected: int
    unticked: tuple[str, ...]
    moved: int


def preselect_source(
    result: ScanResult,
    folder: str,
    *,
    legacy_prefix: str | None = None,
    only: set[str] | frozenset[str] | None = None,
) -> SelectionChange:
    """Tick the libraries under folder (ThirdParty/<id>) in result; only limits it to those rel_paths.

    A library with a twin at legacy_prefix + <its path below folder> takes the twin's tick and the twin is unticked
    (counted in moved); an unticked twin leaves the new library as it is. Without a twin, a library with
    collision_peers is unticked and its nickname listed, any other is ticked. Only result is changed.
    """
    prefix = folder.rstrip("/") + "/"
    legacy = legacy_prefix.rstrip("/") + "/" if legacy_prefix else None
    selected = 0
    moved = 0
    unticked: list[str] = []
    for libs in (result.symbol_libs, result.footprint_libs):
        by_path = {lib.rel_path: lib for lib in libs}
        for lib in sorted(libs, key=lambda item: item.rel_path):
            if not lib.rel_path.startswith(prefix) or (only is not None and lib.rel_path not in only):
                continue
            twin = by_path.get(legacy + lib.rel_path[len(prefix):]) if legacy else None
            if twin is not None and twin is not lib:
                if twin.selected:
                    lib.selected = True
                    twin.selected = False
                    moved += 1
            elif lib.collision_peers:
                lib.selected = False
                if lib.nickname not in unticked:
                    unticked.append(lib.nickname)
            else:
                lib.selected = True
            if lib.selected:
                selected += 1
    return SelectionChange(selected, tuple(unticked), moved)
