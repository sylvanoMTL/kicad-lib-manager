"""Rescanning or dropping one catalog source gives what a full scan gives (D-18, D-21, CAT-05, CAT-08)."""

import copy
import shutil

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection

from kicad_lib_manager import library_scanner
from kicad_lib_manager.library_scanner import scan_all
from kicad_lib_manager.models import Issue, ScanResult

MODEL_VARS = {"Lib": {"LIB_DIR": ""}}


def _sym(*footprints: str) -> str:
    props = "".join(f'(property "Footprint" "{fp}")' for fp in footprints)
    return f'(kicad_symbol_lib (symbol "S" {props}))\n'


def _mod(*models: str) -> str:
    body = "".join(f'  (model "{m}")\n' for m in models)
    return f'(footprint "A"\n{body})\n'


LIB_FILES = {
    "symbols/Alpha.kicad_sym": _sym("Lib_FP:X", "Nowhere:Y"),
    "symbols/Beta.kicad_sym": _sym("Lib_FP:Z"),
    "footprints/Lib_FP.pretty/A.kicad_mod": _mod("${LIB_DIR}/models/gone.step", "${LIB_DIR}/models/here.step"),
    "models/here.step": "step",
}


@pytest.fixture
def nokicad(tmp_path):
    return tmp_path / "nokicad" / "footprints"


@pytest.fixture
def root(tmp_path):
    root = make_collection(tmp_path / "repo")
    (root / "Custom" / "Symbols" / "Shared.kicad_sym").write_text(_sym(), encoding="utf-8")
    return root


def _key(issue: Issue):
    return (issue.severity.value, issue.code, issue.text)


def _same_as_full_scan(got, full: ScanResult) -> None:
    assert isinstance(got, ScanResult), got
    assert got.symbol_libs == full.symbol_libs
    assert got.footprint_libs == full.footprint_libs
    assert sorted(got.issues, key=_key) == sorted(full.issues, key=_key)
    assert got.skipped_sources == full.skipped_sources
    assert got.models_unchecked == full.models_unchecked


def test_scan_source_equals_full_scan_after_add(root, nokicad):
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    make_third_party(root, "Lib", LIB_FILES)

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad, model_vars=MODEL_VARS)

    full = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    _same_as_full_scan(got, full)
    assert {lib.nickname for lib in got.symbol_libs} == {"Shared", "Alpha", "Beta"}
    assert any(i.code == "scan.model_missing" and "gone.step" in i.text for i in got.issues)
    assert any(i.code == "scan.footprint_lib_missing" and "Nowhere" in i.text for i in got.issues)


def test_scan_source_after_update_replaces_the_source(root, nokicad):
    make_third_party(root, "Lib", {"symbols/Old.kicad_sym": _sym("Nowhere:Y")})
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    assert any("Nowhere" in i.text for i in previous.issues)
    shutil.rmtree(root / "ThirdParty" / "Lib" / "symbols")
    make_third_party(root, "Lib", {"symbols/New.kicad_sym": _sym()})

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad, model_vars=MODEL_VARS)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS))
    assert "Old" not in {lib.nickname for lib in got.symbol_libs}
    assert not any("Nowhere" in i.text for i in got.issues)


def test_scan_source_collision_with_custom(root, nokicad):
    previous = scan_all(root, kicad_fp_dir=nokicad)
    make_third_party(root, "Lib", {"symbols/Shared.kicad_sym": _sym()})

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad))
    peers = {lib.rel_path: lib.collision_peers for lib in got.symbol_libs}
    assert peers == {
        "Custom/Symbols/Shared.kicad_sym": ["ThirdParty/Lib/symbols/Shared.kicad_sym"],
        "ThirdParty/Lib/symbols/Shared.kicad_sym": ["Custom/Symbols/Shared.kicad_sym"],
    }
    assert any(i.code == "scan.nickname_collision" for i in got.issues)


def test_a_clone_folder_named_like_a_skipped_folder_is_part_of_the_source(root, nokicad):
    previous = scan_all(root, kicad_fp_dir=nokicad)
    make_third_party(root, "Lib", {"tests/Extra.kicad_sym": _sym(), "env/Other.kicad_sym": _sym()})

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad))
    assert {lib.nickname for lib in got.symbol_libs} == {"Shared", "Extra", "Other"}


@pytest.mark.parametrize("source_dir", [
    "Custom", "ThirdParty", "ThirdParty/.staging", "ThirdParty/a/b", "ThirdParty/", "", "Custom/Symbols",
    "ThirdParty\\Lib",
])
def test_scan_source_refuses(root, nokicad, source_dir):
    make_third_party(root, "Lib", LIB_FILES)
    previous = scan_all(root, kicad_fp_dir=nokicad)

    got = library_scanner.scan_source(root, previous, source_dir, nokicad)

    assert isinstance(got, Issue) and got.code == "rescan.full_needed"


def test_scan_source_without_a_previous_scan_needs_a_full_scan(root, nokicad):
    make_third_party(root, "Lib", LIB_FILES)

    got = library_scanner.scan_source(root, None, "ThirdParty/Lib", nokicad)

    assert isinstance(got, Issue) and got.code == "rescan.full_needed"


def test_scan_source_of_a_folder_that_is_gone_needs_a_full_scan(root, nokicad):
    previous = scan_all(root, kicad_fp_dir=nokicad)

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad)

    assert isinstance(got, Issue) and got.code == "rescan.full_needed"


def test_remove_source_equals_full_scan_after_delete(root, nokicad):
    make_third_party(root, "Lib", {**LIB_FILES, "symbols/Shared.kicad_sym": _sym()})
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    assert any(i.code == "scan.nickname_collision" for i in previous.issues)
    shutil.rmtree(root / "ThirdParty" / "Lib")

    got = library_scanner.remove_source(previous, "ThirdParty/Lib", nokicad)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS))
    assert [lib.nickname for lib in got.symbol_libs] == ["Shared"]
    assert got.symbol_libs[0].collision_peers == []
    assert not any(i.code == "scan.nickname_collision" for i in got.issues)


def test_remove_source_leaves_the_other_sources_alone(root, nokicad):
    make_third_party(root, "Lib", LIB_FILES)
    make_third_party(root, "Other", {"symbols/Gamma.kicad_sym": _sym("Lib_FP:Z")})
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    shutil.rmtree(root / "ThirdParty" / "Lib")

    got = library_scanner.remove_source(previous, "ThirdParty/Lib", nokicad)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS))
    # the link of Gamma to the removed footprint library is a miss again
    assert any(i.code == "scan.footprint_lib_missing" and "Gamma" in i.text for i in got.issues)


def test_remove_source_refuses_to_drop_anything_else(root, nokicad):
    previous = scan_all(root, kicad_fp_dir=nokicad)

    for source_dir in ("Custom", "ThirdParty", "ThirdParty/.staging", ""):
        got = library_scanner.remove_source(previous, source_dir, nokicad)
        assert got == previous


def test_previous_is_never_mutated(root, nokicad):
    make_third_party(root, "Lib", {**LIB_FILES, "symbols/Shared.kicad_sym": _sym()})
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS)
    snapshot = copy.deepcopy(previous)

    library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad, model_vars=MODEL_VARS)
    assert previous == snapshot

    library_scanner.remove_source(previous, "ThirdParty/Lib", nokicad)
    assert previous == snapshot


def test_a_skipped_source_is_checked_again_by_scan_source(root, nokicad):
    make_third_party(root, "Lib", LIB_FILES)
    previous = scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS, skip=lambda source: source == "Lib")
    assert previous.skipped_sources == ["Lib"]

    got = library_scanner.scan_source(root, previous, "ThirdParty/Lib", nokicad, model_vars=MODEL_VARS)

    _same_as_full_scan(got, scan_all(root, kicad_fp_dir=nokicad, model_vars=MODEL_VARS))
    assert got.skipped_sources == []
    assert not any(i.code == "scan.models_skipped" for i in got.issues)
