"""The path variables a download needs and the shared exact-case model check (Phase 17 plan 06; CAT-10, D-26, D-31).

detect_vars finds, for each non-KiCad ${VAR} the footprint models use, the clone folder where at least 80 % of the
variable's sampled model paths exist. KiCad's own variables and the Plugin and Content Manager ones are counted,
never mapped. Trees are written into tmp_path; no git, no network.
"""

from pathlib import Path

import pytest

from kicad_lib_manager.catalog import manifest, validate

SYM = '(kicad_symbol_lib (symbol "S" (property "Reference" "U")))\n'


def _mod(*models: str) -> str:
    body = "".join(f'  (model "{m}")\n' for m in models)
    return f'(footprint "A"\n{body})\n'


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    return root


def _mods(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.kicad_mod"))


def test_detect_vars_sparkfun_layout(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "footprints/Lib.pretty/a.kicad_mod": _mod("${SPARKFUN_KICAD_LIBRARY}/3dmodels/Lib.3dshapes/x.step"),
            "3dmodels/Lib.3dshapes/x.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"SPARKFUN_KICAD_LIBRARY": ""}, 0, 0)


def test_detect_vars_wurth_layout(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "footprints/Lib.pretty/a.kicad_mod": _mod("${WE_3DMODEL_DIR}/Lib.3dshapes/x.step"),
            "3dmodels/Lib.3dshapes/x.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"WE_3DMODEL_DIR": "3dmodels"}, 0, 0)


def test_detect_vars_four_ms_layout(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/a.kicad_mod": _mod("${KICAD_4MS_LIBS}/3dmodels/Lib.3dshapes/x.step"),
            "3dmodels/Lib.3dshapes/x.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"KICAD_4MS_LIBS": ""}, 0, 0)


def test_detect_vars_with_a_model_directly_in_the_folder(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"fp/Lib.pretty/a.kicad_mod": _mod("${MY_MODELS}/x.step"), "shapes/x.step": "solid"},
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"MY_MODELS": "shapes"}, 0, 0)


def test_detect_vars_keeps_variables_apart(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/a.kicad_mod": _mod("${AAA_DIR}/L.3dshapes/a.step", "${BBB_DIR}/L.3dshapes/b.step"),
            "one/L.3dshapes/a.step": "solid",
            "two/deeper/L.3dshapes/b.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"AAA_DIR": "one", "BBB_DIR": "two/deeper"}, 0, 0)


def test_kicad_and_pcm_variables_are_never_mapped(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/a.kicad_mod": _mod("${KICAD8_3RD_PARTY}/3dmodels/Lib.3dshapes/x.step"),
            "fp/Lib.pretty/b.kicad_mod": _mod("${KICAD10_3DMODEL_DIR}/Lib.3dshapes/y.step"),
            "3dmodels/Lib.3dshapes/x.step": "solid",
            "Lib.3dshapes/y.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({}, 1, 1)


def test_validate_staging_reports_the_variables_and_names_the_count(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "a.kicad_sym": SYM,
            "fp/Lib.pretty/a.kicad_mod": _mod("${KICAD8_3RD_PARTY}/x.step", "${WE_3DMODEL_DIR}/Lib.3dshapes/x.step"),
            "fp/Lib.pretty/b.kicad_mod": _mod("${KICAD10_3DMODEL_DIR}/y.step"),
            "3dmodels/Lib.3dshapes/x.step": "solid",
        },
    )
    report = validate.validate_staging(folder, stock_fp=set(), stock_sym=set(), own={}, other_catalog={})
    assert isinstance(report, validate.StagingReport)
    assert report.vars == {"WE_3DMODEL_DIR": "3dmodels"}
    assert (report.kicad_var_models, report.addon_folder_models) == (1, 1)
    lines = [w.text for w in report.warnings]
    assert "1 3D model uses KiCad's own path variables; it shows only in a matching KiCad version." in lines
    assert any("points into the add-on folder of KiCad's Plugin and Content Manager" in line for line in lines)


def test_validate_staging_says_one_model_in_the_singular(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"a.kicad_sym": SYM, "fp/Lib.pretty/a.kicad_mod": _mod("${KICAD8_3RD_PARTY}/x.step")},
    )
    report = validate.validate_staging(folder, stock_fp=set(), stock_sym=set(), own={}, other_catalog={})
    assert [w.text for w in report.warnings] == [
        "1 3D model points into the add-on folder of KiCad's Plugin and Content Manager; "
        "it shows only when that manager has installed this library too."
    ]


def test_validate_staging_without_variables_has_no_variable_warning(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "fp/Lib.pretty/a.kicad_mod": _mod()})
    report = validate.validate_staging(folder, stock_fp=set(), stock_sym=set(), own={}, other_catalog={})
    assert (report.vars, report.kicad_var_models, report.addon_folder_models, report.warnings) == ({}, 0, 0, ())


def _share_tree(tmp_path, present: int, total: int) -> Path:
    """total models of one variable, the first `present` of which exist under shapes/."""
    models = [f"${{SHARE_DIR}}/L.3dshapes/m{i}.step" for i in range(total)]
    files = {f"fp/Lib.pretty/m{i}.kicad_mod": _mod(models[i]) for i in range(total)}
    files.update({f"shapes/L.3dshapes/m{i}.step": "solid" for i in range(present)})
    return _write(tmp_path / f"d{present}of{total}", files)


def test_below_eighty_percent_is_not_mapped(tmp_path):
    folder = _share_tree(tmp_path, 7, 10)
    assert validate.detect_vars(folder, _mods(folder)) == ({}, 0, 0)


def test_eighty_percent_is_mapped(tmp_path):
    folder = _share_tree(tmp_path, 8, 10)
    assert validate.detect_vars(folder, _mods(folder)) == ({"SHARE_DIR": "shapes"}, 0, 0)


def test_a_variable_whose_models_are_nowhere_is_not_mapped(tmp_path):
    folder = _write(tmp_path / "d", {"fp/Lib.pretty/a.kicad_mod": _mod("${GONE_DIR}/L.3dshapes/x.step")})
    assert validate.detect_vars(folder, _mods(folder)) == ({}, 0, 0)


def test_a_model_found_in_two_places_maps_to_the_shorter_folder(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/a.kicad_mod": _mod("${TWIN_DIR}/L.3dshapes/x.step"),
            "copy/L.3dshapes/x.step": "solid",
            "L.3dshapes/x.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"TWIN_DIR": ""}, 0, 0)


def test_sampling_stays_at_200_paths_and_still_maps_a_big_library(tmp_path):
    assert validate.SAMPLE_LIMIT == 200
    assert validate.MIN_SHARE_PERCENT == 80
    folder = _share_tree(tmp_path, 450, 450)
    assert validate.detect_vars(folder, _mods(folder)) == ({"SHARE_DIR": "shapes"}, 0, 0)


def test_models_inside_dot_git_are_not_looked_at(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"fp/Lib.pretty/a.kicad_mod": _mod("${GIT_DIR_VAR}/L.3dshapes/x.step"), ".git/L.3dshapes/x.step": "solid"},
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({}, 0, 0)


def test_an_unreadable_footprint_is_skipped(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/bad.kicad_mod": "(footprint ",
            "fp/Lib.pretty/a.kicad_mod": _mod("${OK_DIR}/L.3dshapes/x.step"),
            "L.3dshapes/x.step": "solid",
        },
    )
    assert validate.detect_vars(folder, _mods(folder)) == ({"OK_DIR": ""}, 0, 0)


# -- the exact-case model check shared with the scanner --------------------------------------------


def test_unresolved_models_is_exact_case(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "fp/Lib.pretty/a.kicad_mod": _mod("${V_DIR}/R.STEP", "${V_DIR}/ok.step", "${OTHER_DIR}/never.step"),
            "shapes/r.step": "solid",
            "shapes/ok.step": "solid",
        },
    )
    assert validate.unresolved_models(folder, {"V_DIR": "shapes"}) == ["${V_DIR}/R.STEP"]


def test_unresolved_models_skips_dot_git(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"fp/Lib.pretty/a.kicad_mod": _mod("${V_DIR}/x.step"), ".git/dup/b.kicad_mod": _mod("${V_DIR}/gone.step")},
    )
    assert validate.unresolved_models(folder, {"V_DIR": ""}) == ["${V_DIR}/x.step"]


def test_unresolved_models_with_nothing_missing(tmp_path):
    folder = _write(tmp_path / "d", {"fp/Lib.pretty/a.kicad_mod": _mod("${V_DIR}/x.step"), "x.step": "solid"})
    assert validate.unresolved_models(folder, {"V_DIR": ""}) == []


# -- the private rules and the manifest rules agree -------------------------------------------------

VAR_NAMES = [
    "SPARKFUN_KICAD_LIBRARY",
    "WE_3DMODEL_DIR",
    "KICAD_4MS_LIBS",
    "KICAD_LIB_GITHUB",
    "CUSTOM_3DMODEL_DIR",
    "KICAD8_3RD_PARTY",
    "KICAD10_3DMODEL_DIR",
    "KICAD7_FOOTPRINT_DIR",
    "ESPRESSIF_3RD_PARTY",
    "KISYS3DMOD",
    "KISYSMOD",
    "KIPRJMOD",
    "KICAD_USER_TEMPLATE_DIR",
    "KICAD_SYSTEM_TEMPLATE_DIR",
    "KICAD_CONFIG_HOME",
    "KICAD_PATH",
    "PATH",
    "PYTHONPATH",
    "LD_PRELOAD",
    "DYLD_LIBRARY_PATH",
    "AB",
    "lower_case",
    "1ABC",
    "OK_NAME_9",
]


@pytest.mark.parametrize("name", VAR_NAMES)
def test_private_variable_rule_matches_the_manifest_rule(name):
    assert validate._mappable(name) == manifest.valid_var_name(name)


@pytest.mark.parametrize(
    "name",
    ["KICAD8_3RD_PARTY", "KICAD10_3DMODEL_DIR", "KICAD7_FOOTPRINT_DIR", "ESPRESSIF_3RD_PARTY", "KISYS3DMOD", "KIPRJMOD", "KICAD_PATH"],
)
def test_kicad_own_names_are_counted_not_mapped(name):
    assert validate._is_kicad_own(name)


@pytest.mark.parametrize("name", ["KICAD_4MS_LIBS", "SPARKFUN_KICAD_LIBRARY", "WE_3DMODEL_DIR"])
def test_a_name_that_only_looks_like_kicads_is_not_kicad_own(name):
    assert not validate._is_kicad_own(name)


FOLDERS = ["", "3dmodels", "a/b", "/abs", "a\\b", "C:/x", "..", "a/../b", "a//b", "./a", "a/.", "trail.", "sp ace ", "tab\there"]


@pytest.mark.parametrize("folder", FOLDERS)
def test_private_folder_rule_matches_the_manifest_rule(folder):
    assert validate._safe_folder(folder) == manifest.safe_var_folder(folder)
