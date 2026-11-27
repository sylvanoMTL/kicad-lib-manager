"""The staging check decides, from files alone, whether a download may become a catalog library (Phase 17 plan 06).

Covers the refusals in their order with the UI-SPEC copy (CAT-03, D-13, D-23), Git LFS and links (T-15, T-16),
the submodule warning, the licence file, the name clashes that are listed and never renamed (CAT-08, D-20) and the
library counts the Add preview shows. Every tree is written into tmp_path; no git, no network.
"""

import os
from pathlib import Path

import pytest

from kicad_lib_manager.catalog import validate
from kicad_lib_manager.models import Issue, Severity

SYM = '(kicad_symbol_lib (symbol "S" (property "Reference" "U")))\n'
MOD = '(footprint "F" (layer "F.Cu"))\n'
LFS_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\n"
    "size 12345\n"
)

NO_LIBRARIES = "This repository holds no KiCad symbol or footprint libraries, so there is nothing to add."
KICAD5 = (
    "This repository only has libraries in the old KiCad 5 format (.lib files). "
    "The catalog adds libraries for KiCad 6 and newer."
)
PCM_ONLY = (
    "This repository only provides its libraries as a KiCad Plugin and Content Manager package, "
    "not as library files. Install it from KiCad (Plugin and Content Manager) instead."
)
LFS = "This library keeps its 3D models in Git LFS, which the catalog does not support. Nothing was added."


def _write(root: Path, files: dict[str, "str | bytes"]) -> Path:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="")
    return root


def _check(folder: Path, *, stock_fp=(), stock_sym=(), own=None, other_catalog=None):
    return validate.validate_staging(
        folder,
        stock_fp=set(stock_fp),
        stock_sym=set(stock_sym),
        own=own or {},
        other_catalog=other_catalog or {},
    )


def _make_link(target: Path, link: Path) -> None:
    """A symbolic link where the platform allows it, else a directory junction (Windows)."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def _refused(result, code: str, text: str) -> None:
    assert isinstance(result, Issue), result
    assert result.severity is Severity.ERROR
    assert (result.code, result.text) == (code, text)


# -- refusals, one by one ----------------------------------------------------------


def test_no_libraries_is_refused(tmp_path):
    _refused(_check(_write(tmp_path / "d", {"README.md": "hello"})), "catalog.no_libraries", NO_LIBRARIES)


def test_kicad5_only_is_refused(tmp_path):
    folder = _write(tmp_path / "d", {"a.lib": "EESchema-LIBRARY\n", "a.dcm": "EESchema-DOCLIB\n"})
    _refused(_check(folder), "catalog.kicad5_only", KICAD5)


def test_libraries_plus_lib_files_pass(tmp_path):
    folder = _write(tmp_path / "d", {"a.lib": "x", "a.kicad_sym": SYM, "p.pretty/f.kicad_mod": MOD})
    report = _check(folder)
    assert isinstance(report, validate.StagingReport), report


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({"metadata.json": '{"$schema": "https://go.kicad.org/pcm/schemas/v1"}'}, id="metadata-json"),
        pytest.param({"repository.json": "{}"}, id="repository-json"),
        pytest.param({"packages.json": "{}"}, id="packages-json"),
        pytest.param({"lib.zip": b"PK\x03\x04", "README.md": "x"}, id="only-a-zip"),
    ],
)
def test_pcm_only_is_refused(tmp_path, files):
    _refused(_check(_write(tmp_path / "d", files)), "catalog.pcm_only", PCM_ONLY)


def test_metadata_json_without_a_kicad_schema_is_not_a_pcm_marker(tmp_path):
    folder = _write(tmp_path / "d", {"metadata.json": '{"$schema": "https://example.org/other"}'})
    _refused(_check(folder), "catalog.no_libraries", NO_LIBRARIES)


def test_a_zip_beside_other_content_is_not_a_pcm_marker(tmp_path):
    folder = _write(tmp_path / "d", {"lib.zip": b"PK\x03\x04", "tool.py": "print(1)\n"})
    _refused(_check(folder), "catalog.no_libraries", NO_LIBRARIES)


def test_lfs_is_refused(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"a.kicad_sym": SYM, ".gitattributes": "*.step filter=lfs diff=lfs merge=lfs -text\n"},
    )
    _refused(_check(folder), "catalog.lfs", LFS)


def test_lfs_in_a_nested_gitattributes_is_refused(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"a.kicad_sym": SYM, "3d/.gitattributes": "# models\n*.wrl filter=lfs -text\n"},
    )
    _refused(_check(folder), "catalog.lfs", LFS)


def test_gitattributes_without_lfs_is_fine(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, ".gitattributes": "* text=auto\n"})
    assert isinstance(_check(folder), validate.StagingReport)


def test_lfs_pointer_file_is_refused(tmp_path):
    assert 100 < len(LFS_POINTER) < 1024
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "3dmodels/x.step": LFS_POINTER})
    _refused(_check(folder), "catalog.lfs", LFS)


def test_a_big_file_that_starts_like_a_pointer_is_not_lfs(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "doc.txt": LFS_POINTER + "x" * 2000})
    assert isinstance(_check(folder), validate.StagingReport)


def test_lfs_markers_inside_dot_git_are_ignored(tmp_path):
    folder = _write(
        tmp_path / "d",
        {"a.kicad_sym": SYM, ".git/objects/pointer": LFS_POINTER, ".git/x.kicad_sym": SYM},
    )
    report = _check(folder)
    assert isinstance(report, validate.StagingReport)
    assert report.symbol_libs == ("a",)


def test_symlink_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x", encoding="utf-8")
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM})
    _make_link(outside, folder / "shortcut")
    result = _check(folder)
    assert isinstance(result, Issue) and result.code == "catalog.link", result
    assert result.severity is Severity.ERROR
    assert "shortcut" in result.text
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "x"


def test_refusal_order(tmp_path):
    # no libraries beats LFS
    folder = _write(tmp_path / "a", {"README.md": "x", ".gitattributes": "*.step filter=lfs\n"})
    assert _check(folder).code == "catalog.no_libraries"
    # KiCad 5 only beats LFS
    folder = _write(tmp_path / "b", {"a.lib": "x", ".gitattributes": "*.step filter=lfs\n"})
    assert _check(folder).code == "catalog.kicad5_only"
    # LFS beats a link
    folder = _write(tmp_path / "c", {"a.kicad_sym": SYM, ".gitattributes": "*.step filter=lfs\n"})
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_link(outside, folder / "shortcut")
    assert _check(folder).code == "catalog.lfs"


def test_the_download_is_never_executed_or_changed(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "setup.py": "raise SystemExit('ran')\n", "conftest.py": "1/0\n"})
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    assert isinstance(_check(folder), validate.StagingReport)
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before
    assert not list(folder.rglob("__pycache__"))


# -- accepted libraries ---------------------------------------------------------------


def test_one_symbol_library_is_enough(tmp_path):
    report = _check(_write(tmp_path / "d", {"only.kicad_sym": SYM}))
    assert isinstance(report, validate.StagingReport)
    assert (report.symbol_libs, report.footprint_libs) == (("only",), ())


def test_one_footprint_library_is_enough(tmp_path):
    report = _check(_write(tmp_path / "d", {"only.pretty/a.kicad_mod": MOD}))
    assert isinstance(report, validate.StagingReport)
    assert (report.symbol_libs, report.footprint_libs) == ((), ("only",))


def test_counts(tmp_path):
    folder = _write(
        tmp_path / "d",
        {
            "b.kicad_sym": SYM,
            "sub/a.kicad_sym": SYM,
            "x.pretty/1.kicad_mod": MOD,
            "deep/er/y.pretty/2.kicad_mod": MOD,
            "z.pretty/3.kicad_mod": MOD,
        },
    )
    report = _check(folder)
    assert report.symbol_libs == ("a", "b")
    assert report.footprint_libs == ("x", "y", "z")


def test_gitmodules_warns(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, ".gitmodules": '[submodule "x"]\n\tpath = x\n\turl = https://example.org/x\n'})
    report = _check(folder)
    assert isinstance(report, validate.StagingReport)
    assert any("submodules are not downloaded" in w.text for w in report.warnings)
    assert all(w.severity is Severity.WARNING for w in report.warnings)


def test_no_gitmodules_no_warning(tmp_path):
    report = _check(_write(tmp_path / "d", {"a.kicad_sym": SYM}))
    assert report.warnings == ()


# -- the licence file ------------------------------------------------------------------


def test_licence_file_is_read(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "LICENSE.md": "MIT License\n\nPermission is hereby granted\n"})
    assert validate.licence_text(folder) == "MIT License\n\nPermission is hereby granted\n"
    assert _check(folder).licence_text == "MIT License\n\nPermission is hereby granted\n"


def test_licence_file_name_is_case_insensitive_and_licence_comes_first(tmp_path):
    folder = _write(tmp_path / "d", {"copying.txt": "gpl", "License": "mit", "UNLICENSE": "public domain"})
    assert validate.licence_text(folder) == "mit"
    folder = _write(tmp_path / "e", {"copying.txt": "gpl", "UNLICENSE": "public domain"})
    assert validate.licence_text(folder) == "public domain"
    folder = _write(tmp_path / "f", {"COPYING": "gpl"})
    assert validate.licence_text(folder) == "gpl"


def test_licence_text_is_cut_at_64_kb(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "LICENSE": "x" * 100_000})
    text = validate.licence_text(folder)
    assert text.startswith("x" * 65536)
    assert not text.startswith("x" * 65537)
    assert len(text) < 65536 + 300
    assert "not shown" in text[65536:]


def test_no_licence_file(tmp_path):
    folder = _write(tmp_path / "d", {"a.kicad_sym": SYM, "docs/LICENSE": "not at the root"})
    assert validate.licence_text(folder) is None
    assert _check(folder).licence_text is None


def test_licence_text_survives_odd_bytes(tmp_path):
    folder = _write(tmp_path / "d", {"LICENSE": b"caf\xe9 licence"})
    text = validate.licence_text(folder)
    assert text is not None and text.endswith(" licence")


# -- collisions (D-20, CAT-08) ------------------------------------------------------------


def _collision_tree(tmp_path):
    return _write(
        tmp_path / "d",
        {
            "Device.kicad_sym": SYM,
            "Atomic_Device.kicad_sym": SYM,
            "MyLib.kicad_sym": SYM,
            "Fine.kicad_sym": SYM,
            "Resistor_SMD.pretty/1.kicad_mod": MOD,
            "Quiet.pretty/1.kicad_mod": MOD,
        },
    )


def test_collisions_listed_never_renamed(tmp_path):
    folder = _collision_tree(tmp_path)
    before = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))
    report = _check(
        folder,
        stock_sym={"Device"},
        stock_fp={"Resistor_SMD"},
        own={"Atomic_Device": "your Atomic_ libraries"},
        other_catalog={"MyLib": "Other"},
    )
    assert isinstance(report, validate.StagingReport)
    rows = {(c.nickname, c.kind, c.clashes_with) for c in report.collisions}
    assert rows == {
        ("Device", "Symbol", "a KiCad library"),
        ("Resistor_SMD", "Footprint", "a KiCad library"),
        ("Atomic_Device", "Symbol", "your Atomic_ libraries"),
        ("MyLib", "Symbol", "Other"),
    }
    assert len(report.collisions) == 4
    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")) == before


def test_stock_names_clash_only_within_their_own_kind(tmp_path):
    folder = _write(tmp_path / "d", {"Device.kicad_sym": SYM, "Device.pretty/1.kicad_mod": MOD})
    report = _check(folder, stock_fp={"Device"})
    assert [(c.nickname, c.kind) for c in report.collisions] == [("Device", "Footprint")]


def test_find_collisions_is_public_and_sorted(tmp_path):
    rows = validate.find_collisions(
        ("Zed", "Device"),
        ("Resistor_SMD",),
        stock_fp={"Resistor_SMD"},
        stock_sym={"Device", "Zed"},
        own={},
        other_catalog={},
    )
    assert [(c.nickname, c.kind) for c in rows] == [("Device", "Symbol"), ("Zed", "Symbol"), ("Resistor_SMD", "Footprint")]


def test_a_library_that_clashes_twice_is_one_row(tmp_path):
    rows = validate.find_collisions(
        ("Device",),
        (),
        stock_fp=set(),
        stock_sym={"Device"},
        own={"Device": "your Custom libraries"},
        other_catalog={"Device": "Other"},
    )
    assert [(c.nickname, c.clashes_with) for c in rows] == [("Device", "a KiCad library")]


def test_no_collisions(tmp_path):
    report = _check(_write(tmp_path / "d", {"a.kicad_sym": SYM}), stock_sym={"Other"})
    assert report.collisions == ()
