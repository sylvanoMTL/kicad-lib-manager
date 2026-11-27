"""Third-party libraries are catalog entries at ThirdParty/<id>, not a hard-coded vendor folder (plan 17-08).

Assumption-delta decision of the plan: promote. The catalog id is the identity of every third-party source
(collection.source_of names it); the WurthElektronik folder is demoted to a legacy variant. Inside
kicad_lib_manager/ only three modules may still name the vendor: catalog/curated.py (the curated entry and its
legacy folder), importer/verify.py (the legacy name search while that folder exists) and widgets/help_dialog.py
(User Guide text). test_only_known_modules_name_wurth goes red the moment another module hard-codes it again.

The corpus test is D-26 check 3 as a standing test: the Wurth library of the owner's collection has no model path
that a mapped variable points at and that is missing. It is read-only and opt-in (KICAD_TEST_CORPUS).
"""

from pathlib import Path

import pytest
from corpusfixtures import corpus_path

from kicad_lib_manager.catalog import manifest
from kicad_lib_manager.catalog.curated import curated_by_id
from kicad_lib_manager.catalog.validate import unresolved_models
from kicad_lib_manager.models import Issue

PACKAGE = Path(__file__).resolve().parent.parent / "kicad_lib_manager"
VENDOR = "WurthElektronik"
ALLOWED = {"catalog/curated.py", "importer/verify.py", "widgets/help_dialog.py"}


def modules_naming(sources: dict[str, str]) -> list[str]:
    """The relative paths (posix) of the sources whose text contains the vendor folder name, any letter case."""
    return sorted(name for name, text in sources.items() if VENDOR.casefold() in text.casefold())


def _package_sources() -> dict[str, str]:
    return {
        path.relative_to(PACKAGE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE.rglob("*.py"))
    }


def test_only_known_modules_name_wurth():
    found = set(modules_naming(_package_sources()))
    assert found <= ALLOWED, (
        "these modules hard-code the vendor folder; key on the catalog id through collection.source_of instead: "
        + ", ".join(sorted(found - ALLOWED))
    )


def test_the_invariant_sees_a_planted_vendor_name():
    sources = {"a.py": "x = 1", "b/c.py": 'FOLDER = "wurthelektronik"', "d.py": "# " + VENDOR}
    assert modules_naming(sources) == ["b/c.py", "d.py"]
    assert modules_naming({"a.py": "SPARKFUN = 1"}) == []


@pytest.mark.corpus
@pytest.mark.slow
def test_corpus_wurth_models_resolve():
    root = corpus_path()
    loaded = manifest.load(root)
    assert not isinstance(loaded, Issue), f"catalog.json of the corpus collection: {loaded.text}"
    entry = next((e for e in loaded.libraries if e.id.casefold() == VENDOR.casefold()), None)
    clone = manifest.entry_folder(root, VENDOR)
    if entry is not None and clone.is_dir():
        folder, variables = clone, dict(entry.vars)
    else:
        curated = curated_by_id(VENDOR)
        assert curated is not None and curated.legacy_prefix, "the curated Wurth entry has no legacy folder"
        folder, variables = root / curated.legacy_prefix.strip("/"), dict(curated.vars)
        assert folder.is_dir(), (
            f"the corpus collection has neither the ThirdParty/{VENDOR} clone ({clone}) "
            f"nor the legacy folder ({folder})"
        )
    missing = unresolved_models(folder, variables)
    assert missing == [], f"{len(missing)} model paths do not resolve in {folder.name}: {missing[:10]}"
