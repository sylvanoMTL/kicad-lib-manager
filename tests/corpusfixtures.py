"""The corpus gate's environment, read by tests/conftest.py and the corpus-marked tests (plain helper module, not collected).

KICAD_TEST_CORPUS names a library collection (a folder that holds Custom/). The tests marked corpus read the real vendor
samples, the Wurth corpus and the live Custom/ of that collection; without it they are deselected with a printed count.
Qt-free: stdlib and pathlib only.
"""

import os
from pathlib import Path

CORPUS_ENV = "KICAD_TEST_CORPUS"
# Set (not blank, not "0") to behave like a runner without KiCad: needs_kicad tests are deselected and the scanner
# finds no KiCad install when it is asked without a base folder
HIDE_KICAD_ENV = "KICAD_TEST_HIDE_KICAD"
# What corpus_path returns without a corpus: a path that never exists, so a corpus-marked module can build its
# module-level constants at import time even though its tests are then deselected
NO_CORPUS = Path("KICAD_TEST_CORPUS-is-not-set")


def corpus_raw() -> str:
    """The KICAD_TEST_CORPUS value as set ("" when unset), unstripped, for messages."""
    return os.environ.get(CORPUS_ENV, "")


def corpus_root() -> Path | None:
    """The collection folder named by KICAD_TEST_CORPUS; None when it is unset or blank. Nothing is validated here."""
    raw = corpus_raw().strip()
    if not raw:
        return None
    return Path(raw).resolve()


def corpus_problem() -> str | None:
    """Why KICAD_TEST_CORPUS is not a library collection ("no such folder", ...), or None when it is unset or fine."""
    root = corpus_root()
    if root is None:
        return None
    if not root.exists():
        return "no such folder"
    if not root.is_dir():
        return "not a folder"
    if not (root / "Custom").is_dir():
        return "it has no Custom folder"
    return None


def corpus_path(*parts: str) -> Path:
    """A path under the corpus collection, or under NO_CORPUS (which does not exist) when no corpus is set."""
    root = corpus_root()
    return (root if root is not None else NO_CORPUS).joinpath(*parts)


def kicad_hidden() -> bool:
    """True when KICAD_TEST_HIDE_KICAD is set to something other than blank or 0."""
    return os.environ.get(HIDE_KICAD_ENV, "").strip() not in ("", "0")


def kicad_found() -> bool:
    """True when an installed KiCad's stock footprints folder and its sibling symbols folder exist (and KiCad is not hidden)."""
    if kicad_hidden():
        return False
    # Lazy: the hide wrapper installed by tests/conftest.py is on the module by now, and a collection that never asks stays light
    from kicad_lib_manager.library_scanner import find_kicad_footprint_dir

    footprints = find_kicad_footprint_dir()
    return footprints is not None and (footprints.parent / "symbols").is_dir()
