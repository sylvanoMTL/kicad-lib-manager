"""Variable names and folders of the catalog (Phase 17 plan 04; CAT-06, CAT-10).

KiCad's own and Plugin and Content Manager variables must never be written by the catalog.
"""

from pathlib import Path

import pytest

from kicad_lib_manager.catalog.manifest import CatalogEntry, path_vars, safe_var_folder, valid_var_name


@pytest.mark.parametrize(
    "name",
    ["WE_3DMODEL_DIR", "SPARKFUN_KICAD_LIBRARY", "KICAD_4MS_LIBS", "ABC", "MY_LIBS_2", "A" + "B" * 63],
)
def test_library_variables_are_accepted(name):
    assert valid_var_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "KICAD9_3RD_PARTY",
        "KICAD8_3RD_PARTY",
        "KICAD10_3DMODEL_DIR",
        "KICAD6_FOOTPRINT_DIR",
        "KICAD_3RD_PARTY",
        "MYLIB_3RD_PARTY",
        "KISYS3DMOD",
        "KISYSMOD",
        "KIPRJMOD",
        "KICAD_USER_TEMPLATE_DIR",
        "KICAD_SYSTEM_TEMPLATE_DIR",
        "KICAD_CONFIG_HOME",
        "KICAD_PATH",
        "KICAD_LIB_GITHUB",
        "CUSTOM_3DMODEL_DIR",
        "PATH",
        "PATHEXT",
        "APPDATA",
        "USERPROFILE",
        "COMSPEC",
        "LD_PRELOAD",
        "DYLD_LIBRARY_PATH",
        "PYTHONPATH",
        "we_3dmodel_dir",
        "We_3dmodel_dir",
        "AB",
        "A" + "B" * 64,
        "",
        "1ABC",
        "_ABC",
        "A-B-C",
        "A B C",
        "ABC\n",
    ],
)
def test_kicad_pcm_and_system_variables_are_refused(name):
    assert valid_var_name(name) is False


def test_valid_var_name_refuses_non_text():
    assert valid_var_name(None) is False  # type: ignore[arg-type]
    assert valid_var_name(7) is False  # type: ignore[arg-type]


@pytest.mark.parametrize("folder", ["", "3dmodels", "a/b", "3dmodels/x.3dshapes", "a b/c"])
def test_safe_folders_are_accepted(folder):
    assert safe_var_folder(folder) is True


@pytest.mark.parametrize(
    "folder",
    ["..", "../x", "a/..", "a/../b", "/x", "C:/x", "C:", "a:b", "a\\b", "a//b", "a/", ".", "a/./b", "a.", "a /b", "a\nb", "x\x00"],
)
def test_unsafe_folders_are_refused(folder):
    assert safe_var_folder(folder) is False


def test_safe_folder_refuses_non_text():
    assert safe_var_folder(None) is False  # type: ignore[arg-type]


def _root() -> Path:
    return Path("scratch") / "collection"


def test_path_vars_give_forward_slash_values_under_third_party():
    entries = [CatalogEntry(id="WurthElektronik", url="u", branch="b", vars={"WE_3DMODEL_DIR": "3dmodels"})]
    result = path_vars(Path("C:\\lib\\col"), entries)
    assert result == {"WE_3DMODEL_DIR": "C:/lib/col/ThirdParty/WurthElektronik/3dmodels"}
    assert "\\" not in result["WE_3DMODEL_DIR"]


def test_an_empty_folder_maps_to_the_clone_root_without_a_trailing_slash():
    entries = [CatalogEntry(id="SparkFun", url="u", branch="b", vars={"SPARKFUN_KICAD_LIBRARY": ""})]
    value = path_vars(Path("C:\\lib\\col"), entries)["SPARKFUN_KICAD_LIBRARY"]
    assert value == "C:/lib/col/ThirdParty/SparkFun"
    assert not value.endswith("/")


def test_path_vars_of_nothing_is_empty():
    assert path_vars(_root(), []) == {}
    assert path_vars(_root(), [CatalogEntry(id="Demo", url="u", branch="b")]) == {}


def test_path_vars_is_deterministic_whatever_the_entry_order():
    a = CatalogEntry(id="alpha", url="u", branch="b", vars={"SAME_VAR": "x"})
    b = CatalogEntry(id="Beta", url="u", branch="b", vars={"SAME_VAR": "y", "OTHER_VAR": ""})
    assert path_vars(_root(), [a, b]) == path_vars(_root(), [b, a])


def test_path_vars_skips_a_variable_the_rules_refuse():
    entry = CatalogEntry(id="Demo", url="u", branch="b", vars={"KICAD9_3RD_PARTY": "", "OK_VAR": "x", "BAD_DIR": "../x"})
    assert path_vars(_root(), [entry]) == {"OK_VAR": f"{(_root().as_posix())}/ThirdParty/Demo/x"}
