"""The scan checks catalog 3D models, never enters ThirdParty/.staging and saves catalog.json in its fingerprint (CAT-05, CAT-06, D-06, D-26)."""

import os
from pathlib import Path

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection

from kicad_lib_manager import library_scanner, scan_cache
from kicad_lib_manager.library_scanner import (
    check_3d_model_paths,
    find_footprint_libs,
    find_symbol_libs,
    scan_all,
)
from kicad_lib_manager.models import Severity

SYM = '(kicad_symbol_lib (symbol "S" (property "Reference" "U")))\n'
MODEL_CODES = ("scan.model_missing", "scan.model_absolute", "scan.model_var", "scan.unreadable")


def _mod(*models: str) -> str:
    body = "".join(f'  (model "{m}")\n' for m in models)
    return f'(footprint "A"\n{body})\n'


@pytest.fixture
def nokicad(tmp_path):
    """A KiCad footprints folder that does not exist: no stock libraries, no real install is read."""
    return tmp_path / "nokicad" / "footprints"


def _model_lines(result):
    return [i for i in result.issues if i.code in MODEL_CODES]


def _lib(tmp_path, files):
    root = make_collection(tmp_path / "repo")
    make_third_party(root, "Lib", files)
    return root


# ── staging ──────────────────────────────────────────────────────────

def test_staging_is_never_scanned(tmp_path, nokicad):
    root = make_collection(tmp_path / "repo")
    make_third_party(root, "X", {"lib.kicad_sym": SYM, "fp.pretty/a.kicad_mod": _mod("C:/abs/a.step")})
    staging = root / "ThirdParty" / ".staging" / "X.ab12cd34"
    (staging / "fp.pretty").mkdir(parents=True)
    (staging / "lib.kicad_sym").write_text(SYM, encoding="utf-8")
    (staging / "fp.pretty" / "b.kicad_mod").write_text(_mod("C:/abs/b.step"), encoding="utf-8")

    assert [lib.rel_path for lib in find_symbol_libs(root)] == ["ThirdParty/X/lib.kicad_sym"]
    assert [lib.rel_path for lib in find_footprint_libs(root)] == [
        "Custom/Footprints/Atomic_Footprints.pretty", "ThirdParty/X/fp.pretty",
    ]
    assert {lib.source for lib in find_symbol_libs(root)} == {"X"}

    result = scan_all(root, kicad_fp_dir=nokicad)
    assert [lib.rel_path for lib in result.symbol_libs] == ["ThirdParty/X/lib.kicad_sym"]
    assert not any(".staging" in issue.text for issue in result.issues)

    fp = scan_cache.fingerprint(root, nokicad)
    assert any(key.startswith("ThirdParty/X/") for key in fp["files"])
    assert not any(".staging" in key for key in (*fp["files"], *fp["folders"]))


def test_a_clone_folder_named_staging_deeper_down_is_still_scanned(tmp_path):
    root = make_collection(tmp_path / "repo")
    make_third_party(root, "X", {".staging/lib.kicad_sym": SYM})
    assert [lib.rel_path for lib in find_symbol_libs(root)] == ["ThirdParty/X/.staging/lib.kicad_sym"]


# ── the variable model rule ──────────────────────────────────────────

def _lib_with_models(tmp_path):
    return _lib(tmp_path, {
        "footprints/A.pretty/A.kicad_mod": _mod(
            "${LIB_DIR}/3dmodels/A.3dshapes/r.step",
            "${LIB_DIR}/3dmodels/A.3dshapes/R.STEP",
        ),
        "3dmodels/A.3dshapes/r.step": "step",
    })


def test_var_model_found_and_missing(tmp_path, nokicad):
    root = _lib_with_models(tmp_path)

    result = scan_all(root, kicad_fp_dir=nokicad, model_vars={"Lib": {"LIB_DIR": ""}})

    lines = _model_lines(result)
    assert len(lines) == 1
    assert lines[0].severity is Severity.WARNING
    assert lines[0].code == "scan.model_missing"
    assert lines[0].text == (
        "[ThirdParty/Lib/footprints/A.pretty/A.kicad_mod] 3D model not found in ThirdParty/Lib "
        "(names are case-sensitive): ${LIB_DIR}/3dmodels/A.3dshapes/R.STEP"
    )

    assert _model_lines(scan_all(root, kicad_fp_dir=nokicad)) == []


def test_missing_model_names_the_folder_the_variable_points_at(tmp_path, nokicad):
    root = _lib(tmp_path, {
        "footprints/A.pretty/A.kicad_mod": _mod("${WE_3DMODEL_DIR}/x/gone.step"),
        "3dmodels/x/here.step": "step",
    })

    lines = _model_lines(scan_all(root, kicad_fp_dir=nokicad, model_vars={"Lib": {"WE_3DMODEL_DIR": "3dmodels"}}))

    assert [i.text for i in lines] == [
        "[ThirdParty/Lib/footprints/A.pretty/A.kicad_mod] 3D model not found in ThirdParty/Lib/3dmodels "
        "(names are case-sensitive): ${WE_3DMODEL_DIR}/x/gone.step"
    ]


def test_a_few_missing_models_stay_warnings(tmp_path, nokicad):
    root = _lib(tmp_path, {
        "fp.pretty/A.kicad_mod": _mod("${LIB_DIR}/a.step", "${LIB_DIR}/b.step"),
    })

    result = scan_all(root, kicad_fp_dir=nokicad, model_vars={"Lib": {"LIB_DIR": ""}})

    lines = _model_lines(result)
    assert len(lines) == 2
    assert {line.severity for line in lines} == {Severity.WARNING}
    assert not any(i.severity is Severity.ERROR for i in result.issues)


def test_rule_applies_only_inside_the_clone(tmp_path, nokicad):
    root = make_collection(tmp_path / "repo")
    old = root / "WurthElektronik" / "KiCad-Library" / "x.pretty"
    old.mkdir(parents=True)
    (old / "A.kicad_mod").write_text(_mod("${WE_3DMODEL_DIR}/gone.step"), encoding="utf-8")
    make_third_party(root, "WurthElektronik", {"x.pretty/A.kicad_mod": _mod("${WE_3DMODEL_DIR}/gone.step")})
    model_vars = {"WurthElektronik": {"WE_3DMODEL_DIR": "3dmodels"}}

    lines = _model_lines(scan_all(root, kicad_fp_dir=nokicad, model_vars=model_vars))

    assert [line.text.split("]")[0] for line in lines] == ["[ThirdParty/WurthElektronik/x.pretty/A.kicad_mod"]


def test_kicad_own_and_unmapped_variables_are_not_checked(tmp_path, nokicad):
    root = _lib(tmp_path, {
        "fp.pretty/A.kicad_mod": _mod("${KICAD10_3DMODEL_DIR}/x.step", "${OTHER}/y.step"),
    })

    result = scan_all(root, kicad_fp_dir=nokicad, model_vars={"Lib": {"LIB_DIR": ""}})

    assert _model_lines(result) == []


def test_a_source_without_variables_is_not_checked(tmp_path, nokicad):
    root = _lib(tmp_path, {"fp.pretty/A.kicad_mod": _mod("${LIB_DIR}/gone.step")})

    assert _model_lines(scan_all(root, kicad_fp_dir=nokicad, model_vars={"Other": {"LIB_DIR": ""}})) == []


def test_kicad_embed_is_not_absolute(tmp_path, nokicad):
    root = _lib(tmp_path, {
        "fp.pretty/E.kicad_mod": _mod("kicad-embed://R_0603.step"),
        "fp.pretty/F.kicad_mod": _mod("C:/x/y.step"),
    })

    lines = _model_lines(scan_all(root, kicad_fp_dir=nokicad))

    assert [line.code for line in lines] == ["scan.model_absolute"]
    assert "C:/x/y.step" in lines[0].text
    assert not any("kicad-embed" in line.text for line in lines)


def test_unresolved_var_models_helper(tmp_path):
    root = _lib_with_models(tmp_path)
    clone = root / "ThirdParty" / "Lib"
    files = [clone / "footprints" / "A.pretty" / "A.kicad_mod"]

    assert library_scanner.unresolved_var_models(clone, files, {"LIB_DIR": ""}) == ["${LIB_DIR}/3dmodels/A.3dshapes/R.STEP"]
    assert library_scanner.unresolved_var_models(clone, files, {"OTHER": ""}) == []
    assert library_scanner.unresolved_var_models(clone, [], {"LIB_DIR": ""}) == []


def test_the_model_check_names_are_exact_even_where_the_file_system_is_not(tmp_path):
    root = _lib_with_models(tmp_path)
    clone = root / "ThirdParty" / "Lib"
    folder = clone / "footprints" / "A.pretty"
    (folder / "A.kicad_mod").write_text(_mod("${LIB_DIR}/3DMODELS/A.3dshapes/r.step"), encoding="utf-8")

    assert library_scanner.unresolved_var_models(clone, [folder / "A.kicad_mod"], {"LIB_DIR": ""}) == [
        "${LIB_DIR}/3DMODELS/A.3dshapes/r.step"
    ]


def test_scan_all_threads_model_vars(tmp_path, nokicad):
    root = _lib_with_models(tmp_path)
    model_vars = {"Lib": {"LIB_DIR": ""}}

    full = _model_lines(scan_all(root, kicad_fp_dir=nokicad, model_vars=model_vars))
    direct = check_3d_model_paths(root, model_vars=model_vars)

    assert full and [(i.code, i.text) for i in full] == [(i.code, i.text) for i in direct]


# ── the saved scan ───────────────────────────────────────────────────

def test_catalog_json_changes_the_fingerprint(tmp_path, nokicad):
    root = make_collection(tmp_path / "repo")
    base = scan_cache.fingerprint(root, nokicad)
    assert "catalog.json" not in base["files"]

    catalog = root / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    first = scan_cache.fingerprint(root, nokicad)
    assert first != base
    assert "catalog.json" in first["files"]

    catalog.write_text('{"version": 1}', encoding="utf-8")
    assert scan_cache.fingerprint(root, nokicad) != first


# ── stock symbol libraries ───────────────────────────────────────────

def test_stock_symbol_nicknames(tmp_path):
    share = tmp_path / "share"
    (share / "footprints").mkdir(parents=True)
    (share / "symbols").mkdir()
    (share / "symbols" / "Device.kicad_sym").write_text(SYM, encoding="utf-8")
    (share / "symbols" / "notes.txt").write_text("x", encoding="utf-8")

    assert library_scanner.get_kicad_default_sym_nicknames(share / "footprints") == {"Device"}


def test_no_stock_symbols_folder_gives_an_empty_set(tmp_path):
    (tmp_path / "share" / "footprints").mkdir(parents=True)

    assert library_scanner.get_kicad_default_sym_nicknames(tmp_path / "share" / "footprints") == set()
    assert library_scanner.get_kicad_default_sym_nicknames(tmp_path / "missing" / "footprints") == set()


def test_walk_does_not_follow_into_staging_with_a_relative_root(tmp_path, monkeypatch, nokicad):
    root = make_collection(tmp_path / "repo")
    staging = root / "ThirdParty" / ".staging" / "X.ab12cd34"
    staging.mkdir(parents=True)
    (staging / "lib.kicad_sym").write_text(SYM, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert find_symbol_libs(Path("repo")) == []
    assert os.path.isdir(staging)
