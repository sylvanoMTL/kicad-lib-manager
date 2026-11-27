"""Scan Issue tests: nickname collision pass (D-01, HARD-08) and 3D model-path rules (D-18, D-19)."""

from pathlib import Path

import pytest
from corpusfixtures import corpus_path, corpus_root

from kicad_lib_manager import library_scanner
from kicad_lib_manager.library_scanner import scan_all
from kicad_lib_manager.models import (
    FootprintLibrary,
    Issue,
    ScanResult,
    Severity,
    SymbolLibrary,
)


def _sym(nickname: str, rel_path: str) -> SymbolLibrary:
    return SymbolLibrary(nickname, rel_path, rel_path.split("/")[0])


def _fp(nickname: str, rel_path: str) -> FootprintLibrary:
    return FootprintLibrary(nickname, rel_path, rel_path.split("/")[0])


_CUSTOM_SAME = "Custom/Symbols/Same.kicad_sym"
_WURTH_SAME = "WurthElektronik/KiCad-Library/symbols/Same.kicad_sym"


def test_symbol_collision_across_sources():
    a, b = _sym("Same", _CUSTOM_SAME), _sym("Same", _WURTH_SAME)
    issues = library_scanner.find_nickname_collisions([a, b], [])
    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, Issue)
    assert issue.severity is Severity.WARNING
    assert issue.code == "scan.nickname_collision"
    assert "Symbol" in issue.text
    assert _CUSTOM_SAME in issue.text and _WURTH_SAME in issue.text
    assert a.collision_peers == [_WURTH_SAME]
    assert b.collision_peers == [_CUSTOM_SAME]


def test_footprint_collision_is_separate_issue():
    a = _fp("Same", "Custom/Footprints/Same.pretty")
    b = _fp("Same", "WurthElektronik/KiCad-Library/fp/Same.pretty")
    issues = library_scanner.find_nickname_collisions([], [a, b])
    assert len(issues) == 1
    assert issues[0].code == "scan.nickname_collision"
    assert "Footprint" in issues[0].text
    assert a.collision_peers == [b.rel_path]
    assert b.collision_peers == [a.rel_path]


def test_symbol_and_footprint_with_same_nickname_do_not_collide():
    sym = _sym("Same", _CUSTOM_SAME)
    fp = _fp("Same", "Custom/Footprints/Same.pretty")
    assert library_scanner.find_nickname_collisions([sym], [fp]) == []
    assert sym.collision_peers == []
    assert fp.collision_peers == []


def test_same_source_different_folders_collide():
    a = _sym("A", "Custom/Symbols/A.kicad_sym")
    b = _sym("A", "Custom/Other/A.kicad_sym")
    issues = library_scanner.find_nickname_collisions([a, b], [])
    assert len(issues) == 1
    assert a.collision_peers == ["Custom/Other/A.kicad_sym"]
    assert b.collision_peers == ["Custom/Symbols/A.kicad_sym"]


def test_three_way_collision_one_issue_sorted_peers():
    paths = ["Custom/Z/A.kicad_sym", "Custom/B/A.kicad_sym", "Custom/M/A.kicad_sym"]
    libs = [_sym("A", p) for p in paths]
    issues = library_scanner.find_nickname_collisions(libs, [])
    assert len(issues) == 1
    for lib in libs:
        assert lib.collision_peers == sorted(p for p in paths if p != lib.rel_path)
        assert len(lib.collision_peers) == 2


def test_no_collision_returns_nothing_and_clears_stale_peers():
    a = _sym("A", "Custom/Symbols/A.kicad_sym")
    b = _sym("B", "Custom/Symbols/B.kicad_sym")
    a.collision_peers = ["stale/path"]
    f = _fp("F", "Custom/Footprints/F.pretty")
    f.collision_peers = ["stale/path"]
    assert library_scanner.find_nickname_collisions([a, b], [f]) == []
    assert a.collision_peers == [] and b.collision_peers == []
    assert f.collision_peers == []


def test_collision_pass_is_idempotent():
    a, b = _sym("Same", _CUSTOM_SAME), _sym("Same", _WURTH_SAME)
    first = library_scanner.find_nickname_collisions([a, b], [])
    second = library_scanner.find_nickname_collisions([a, b], [])
    assert first == second
    assert a.collision_peers == [_WURTH_SAME]
    assert b.collision_peers == [_CUSTOM_SAME]


def test_collision_pass_never_changes_nickname():
    a, b = _sym("Same", _CUSTOM_SAME), _sym("Same", _WURTH_SAME)
    library_scanner.find_nickname_collisions([a, b], [])
    assert a.nickname == "Same" and b.nickname == "Same"


def test_scan_all_reports_collision_first(tmp_path: Path):
    for rel in (_CUSTOM_SAME, _WURTH_SAME):
        f = tmp_path / rel
        f.parent.mkdir(parents=True)
        f.write_bytes(b"(kicad_symbol_lib)\n")
    result = scan_all(tmp_path, kicad_fp_dir=tmp_path / "no_such_dir")
    assert len(result.symbol_libs) == 2
    assert {lib.rel_path for lib in result.symbol_libs} == {_CUSTOM_SAME, _WURTH_SAME}
    for lib in result.symbol_libs:
        assert len(lib.collision_peers) == 1
        assert lib.collision_peers[0] != lib.rel_path
    collisions = [i for i in result.issues if i.code == "scan.nickname_collision"]
    assert len(collisions) == 1
    assert result.issues[0].code == "scan.nickname_collision"


# ── 3D model-path rules (D-18, D-19) ────────────────────────────────────────

_CUSTOM_FP = "Custom/Footprints/F.pretty"
_WURTH_FP = "WurthElektronik/KiCad-Library/fp/W.pretty"


def _write_mod(root: Path, folder: str, name: str, *model_paths: str) -> str:
    """Write a footprint with the given model paths; return its repo-relative path."""
    models = "".join(f'  (model "{p}")\n' for p in model_paths)
    path = root / folder / f"{name}.kicad_mod"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f'(footprint "{name}"\n{models})\n'.encode("utf-8"))
    return path.relative_to(root).as_posix()


def _write_model_file(root: Path, rel: str) -> None:
    path = root / "Custom" / "3DModels" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ISO-10303-21;\n")


def test_custom_model_kiprjmod_path_gives_model_var(tmp_path):
    rel = _write_mod(tmp_path, _CUSTOM_FP, "a", "${KIPRJMOD}/Custom/3DModels/a.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert issues[0].code == "scan.model_var"
    assert issues[0].text.startswith(f"[{rel}] ")
    assert "${KIPRJMOD}/Custom/3DModels/a.step" in issues[0].text


def test_custom_model_absolute_path_gives_model_var(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "e", "C:/abs/e.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert [i.code for i in issues] == ["scan.model_var"]


def test_custom_model_present_is_quiet(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "b", "${CUSTOM_3DMODEL_DIR}/b.step")
    _write_model_file(tmp_path, "b.step")
    assert library_scanner.check_3d_model_paths(tmp_path) == []


def test_custom_model_case_mismatch_gives_model_missing(tmp_path):
    rel = _write_mod(tmp_path, _CUSTOM_FP, "c", "${CUSTOM_3DMODEL_DIR}/c.STEP")
    _write_model_file(tmp_path, "c.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert issues[0].code == "scan.model_missing"
    assert issues[0].text.startswith(f"[{rel}] ")
    assert "c.STEP" in issues[0].text


def test_custom_model_in_subfolder_is_quiet(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "d", "${CUSTOM_3DMODEL_DIR}/sub/d.stp")
    _write_model_file(tmp_path, "sub/d.stp")
    assert library_scanner.check_3d_model_paths(tmp_path) == []


def test_custom_footprint_with_one_good_one_missing_model_gives_one_issue(tmp_path):
    _write_mod(
        tmp_path, _CUSTOM_FP, "g",
        "${CUSTOM_3DMODEL_DIR}/good.step", "${CUSTOM_3DMODEL_DIR}/gone.step",
    )
    _write_model_file(tmp_path, "good.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert [i.code for i in issues] == ["scan.model_missing"]
    assert "gone.step" in issues[0].text


def test_custom_model_without_3dmodels_folder_is_missing(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "n", "${CUSTOM_3DMODEL_DIR}/n.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert [i.code for i in issues] == ["scan.model_missing"]


@pytest.mark.parametrize(
    "path",
    ["${WE_3DMODEL_DIR}/w.step", "${KICAD9_3DMODEL_DIR}/x.step", "w.step"],
    ids=["we-var", "kicad-var", "bare-name"],
)
def test_other_source_model_paths_stay_quiet(tmp_path, path):
    _write_mod(tmp_path, _WURTH_FP, "w", path)
    assert library_scanner.check_3d_model_paths(tmp_path) == []


def test_other_source_absolute_model_gives_model_absolute(tmp_path):
    rel = _write_mod(tmp_path, _WURTH_FP, "w", "C:/abs/w.step")
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert issues[0].code == "scan.model_absolute"
    assert issues[0].text.startswith(f"[{rel}] ")


def test_unreadable_footprint_warns_and_scan_continues(tmp_path):
    bad = tmp_path / _CUSTOM_FP / "bad.kicad_mod"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b'(footprint "bad"\n  (model "x.step"\n')
    rel_ok = _write_mod(tmp_path, _CUSTOM_FP, "ok", "${KIPRJMOD}/ok.step")

    issues = library_scanner.check_3d_model_paths(tmp_path)

    unreadable = [i for i in issues if i.code == "scan.unreadable"]
    assert len(unreadable) == 1
    assert unreadable[0].severity is Severity.WARNING
    assert unreadable[0].text.startswith(f"[{_CUSTOM_FP}/bad.kicad_mod] ")
    assert [i.code for i in issues if i.text.startswith(f"[{rel_ok}] ")] == ["scan.model_var"]


def test_footprint_without_models_gives_nothing(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "none")
    assert library_scanner.check_3d_model_paths(tmp_path) == []


def test_model_issue_text_starts_with_repo_relative_path(tmp_path):
    rels = [
        _write_mod(tmp_path, _CUSTOM_FP, "a", "${KIPRJMOD}/a.step"),
        _write_mod(tmp_path, _CUSTOM_FP, "b", "${CUSTOM_3DMODEL_DIR}/b.step"),
        _write_mod(tmp_path, _WURTH_FP, "w", "D:/abs/w.step"),
    ]
    issues = library_scanner.check_3d_model_paths(tmp_path)
    assert len(issues) == 3
    for issue in issues:
        assert any(issue.text.startswith(f"[{rel}] ") for rel in rels)


def test_scan_all_includes_model_issues(tmp_path):
    _write_mod(tmp_path, _CUSTOM_FP, "a", "${KIPRJMOD}/a.step")
    result = scan_all(tmp_path, kicad_fp_dir=tmp_path / "no_such_dir")
    assert [i.code for i in result.issues if i.severity is not Severity.INFO] == ["scan.model_var"]
    # This tmp tree has a Custom/ footprint library and is not a git checkout
    assert [i.code for i in result.issues if i.code == "scan.changes_skipped"] == ["scan.changes_skipped"]


def test_scanner_no_longer_exposes_model_regex():
    assert not hasattr(library_scanner, "MODEL_RE")
    assert library_scanner.CUSTOM_MODEL_PREFIX == "${CUSTOM_3DMODEL_DIR}/"


# among the 50 slowest in BASELINE.md: 12.42 s
@pytest.mark.slow
@pytest.mark.corpus
def test_live_custom_model_findings_are_zero():
    assert corpus_path("Custom", "Footprints").is_dir(), "the corpus collection has no Custom/Footprints"
    issues = library_scanner.check_3d_model_paths(corpus_root())
    custom = [
        i for i in issues
        if i.code.startswith("scan.model_") and i.text.startswith("[Custom/")
    ]
    assert custom == []


@pytest.mark.wurth
def test_wurth_model_paths_stay_quiet():
    wurth = corpus_path("WurthElektronik")
    assert any(wurth.rglob("*.kicad_mod")), "the corpus collection has no WurthElektronik footprints"
    issues = library_scanner.check_3d_model_paths(corpus_root())
    wurth_issues = [i for i in issues if i.text.startswith("[WurthElektronik/")]
    assert not [i for i in wurth_issues if i.code in ("scan.model_var", "scan.model_missing")]
    assert not [i for i in wurth_issues if "${WE_3DMODEL_DIR}" in i.text]


# -- one line per catalog library and kind (Phase 17 plan 23, owner finding 3 of 17-17) ---------------

_ALT_NAMES = {"Alt": "Alternate KiCad Library"}


def _model_issue(code: str, rel: str, text: str) -> Issue:
    return Issue(Severity.WARNING, code, f"[{rel}] {text}")


def _absolute(n: int, source: str = "Alt") -> list[Issue]:
    return [
        _model_issue(
            "scan.model_absolute", f"ThirdParty/{source}/footprints/F{i}.pretty/P{i}.kicad_mod",
            f"Absolute/non-variable 3D model path: C:/Old/models/m{i}.step",
        )
        for i in range(1, n + 1)
    ]


def test_catalog_model_lines_are_summarized():
    issues = _absolute(7)

    got = library_scanner.summarize_catalog_lines(issues, ScanResult(), _ALT_NAMES)

    assert len(got) == 1
    assert got[0].severity is Severity.WARNING
    assert got[0].code == "scan.catalog_summary"
    assert got[0].text == (
        "Alternate KiCad Library: 7 footprints point their 3D model at a fixed folder instead of a path variable, "
        "for example C:/Old/models/m1.step, C:/Old/models/m2.step, C:/Old/models/m3.step, "
        "C:/Old/models/m4.step, C:/Old/models/m5.step and 2 more."
    )
    single = library_scanner.summarize_catalog_lines(_absolute(1), ScanResult(), _ALT_NAMES)
    assert [i.text for i in single] == [
        "Alternate KiCad Library: 1 footprint points its 3D model at a fixed folder instead of a path variable: "
        "C:/Old/models/m1.step."
    ]


def test_thousands_use_separators():
    got = library_scanner.summarize_catalog_lines(_absolute(6904), ScanResult(), _ALT_NAMES)

    assert got[0].text.startswith("Alternate KiCad Library: 6,904 footprints point their 3D model")
    assert got[0].text.endswith("and 6,899 more.")


def test_missing_models_and_unreadable_files():
    missing = [
        _model_issue(
            "scan.model_missing", f"ThirdParty/Alt/footprints/F{i}.pretty/P.kicad_mod",
            f"3D model not found in ThirdParty/Alt (names are case-sensitive): ${{ALT_DIR}}/m{i}.step",
        )
        for i in (1, 2)
    ]
    unreadable = [
        _model_issue("scan.unreadable", f"ThirdParty/Alt/footprints/F{i}.pretty/Bad{i}.kicad_mod", "Could not read: bad")
        for i in (1, 2, 3)
    ]

    got = library_scanner.summarize_catalog_lines(missing + unreadable, ScanResult(), _ALT_NAMES)

    assert [i.text for i in got] == [
        "Alternate KiCad Library: 2 3D models were not found (names are case-sensitive), "
        "for example ${ALT_DIR}/m1.step, ${ALT_DIR}/m2.step.",
        "Alternate KiCad Library: 3 footprint files could not be read, for example "
        "footprints/F1.pretty/Bad1.kicad_mod, footprints/F2.pretty/Bad2.kicad_mod, footprints/F3.pretty/Bad3.kicad_mod.",
    ]
    one = library_scanner.summarize_catalog_lines(missing[:1] + unreadable[:1], ScanResult(), _ALT_NAMES)
    assert [i.text for i in one] == [
        "Alternate KiCad Library: 1 3D model was not found (names are case-sensitive): ${ALT_DIR}/m1.step.",
        "Alternate KiCad Library: 1 footprint file could not be read: footprints/F1.pretty/Bad1.kicad_mod.",
    ]


def _link(nickname: str, lib: str, fp: str = "X") -> Issue:
    return Issue(
        Severity.WARNING, "scan.footprint_lib_missing",
        f"[{nickname}] Footprint library '{lib}' not found in repo or KiCad defaults (referenced by {fp})",
    )


def test_missing_footprint_links_are_summarized():
    scan = ScanResult(symbol_libs=[
        SymbolLibrary("Espressif", "ThirdParty/Espressif/symbols/Espressif.kicad_sym", "Espressif"),
    ])
    issues = [_link("Espressif", "PCM_Espressif", f"F{i}") for i in range(51)]

    got = library_scanner.summarize_catalog_lines(issues, scan, {})

    assert [i.text for i in got] == [
        "Espressif: 51 footprint links point to footprint libraries that are not in your collection "
        "or in KiCad's own libraries: PCM_Espressif."
    ]
    assert got[0].code == "scan.catalog_summary"
    one = library_scanner.summarize_catalog_lines(issues[:1], scan, {})
    assert [i.text for i in one] == [
        "Espressif: 1 footprint link points to a footprint library that is not in your collection "
        "or in KiCad's own libraries: PCM_Espressif."
    ]
    # a symbol library whose nickname is also used outside that source keeps its own lines
    shared = ScanResult(symbol_libs=[
        *scan.symbol_libs, SymbolLibrary("Espressif", "Custom/Symbols/Espressif.kicad_sym", "Custom"),
    ])
    assert library_scanner.summarize_catalog_lines(issues, shared, {}) == issues


def test_other_lines_are_untouched():
    scan = ScanResult(symbol_libs=[SymbolLibrary("S", "ThirdParty/Alt/symbols/S.kicad_sym", "Alt")])
    custom = _model_issue(
        "scan.model_absolute", "Custom/Footprints/X.pretty/Y.kicad_mod", "Absolute/non-variable 3D model path: C:/z.step"
    )
    collision = Issue(Severity.WARNING, "scan.nickname_collision", "[Same] Symbol library nickname is used by a, b")
    info = Issue(Severity.INFO, "scan.models_skipped", "3D model paths were not checked")
    issues = [collision, *_absolute(3), custom, info]
    snapshot = list(issues)

    got = library_scanner.summarize_catalog_lines(issues, scan, {})

    # the summary sits where the first catalog line was; every other line keeps its text and order
    assert [i.code for i in got] == ["scan.nickname_collision", "scan.catalog_summary", "scan.model_absolute", "scan.models_skipped"]
    assert got[0] is collision and got[2] is custom and got[3] is info
    # a source with no names entry is named by its folder
    assert got[1].text.startswith("Alt: 3 footprints point their 3D model")
    assert issues == snapshot  # the input list is not changed


def test_two_sources_get_one_line_each_at_their_first_line():
    issues = [*_absolute(2, "Alt")[:1], *_absolute(2, "Beta")[:1], *_absolute(2, "Alt")[1:]]

    got = library_scanner.summarize_catalog_lines(issues, ScanResult(), {"Alt": "A", "Beta": "B"})

    assert [i.text.split(":")[0] for i in got] == ["A", "B"]
