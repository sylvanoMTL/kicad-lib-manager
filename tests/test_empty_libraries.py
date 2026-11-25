"""Empty libraries: the scan flags a library that holds nothing, and the saved scan carries the flag (Phase 15 gap 2)."""

import json

import pytest
from collectionfixtures import recording_git

from kicad_lib_manager import collection, scan_cache
from kicad_lib_manager.library_scanner import find_footprint_libs, find_symbol_libs, scan_all
from kicad_lib_manager.models import FootprintLibrary, ScanResult, SymbolLibrary

NO_SYMBOLS = '(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor"))\n'
ONE_SYMBOL = (
    '(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'
    '  (symbol "R1" (property "Reference" "R" (at 0 0 0)))\n)\n'
)


@pytest.fixture
def skeleton(tmp_path):
    """The real New Collection skeleton; git is answered by a recorder, so no process starts."""
    ctx, _calls = recording_git({"--version": (0, "git version 2.49.0.windows.1"), "init": (0, "")})
    target = tmp_path / "lib"
    issues = collection.create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert issues == []
    return target


def test_skeleton_scan_holds_nothing(skeleton):
    result = scan_all(skeleton)
    assert result.symbol_libs == []
    assert [(lib.nickname, lib.empty) for lib in result.footprint_libs] == [("Atomic_Footprints", True)]
    assert result.holds_nothing is True


def test_footprint_library_with_a_footprint_is_not_empty(skeleton):
    pretty = skeleton / "Custom" / "Footprints" / "Atomic_Footprints.pretty"
    (pretty / "X.kicad_mod").write_text('(footprint "X")\n', encoding="utf-8")
    libs = find_footprint_libs(skeleton)
    assert [lib.empty for lib in libs] == [False]
    assert scan_all(skeleton).holds_nothing is False


def test_footprint_library_footprint_suffix_is_case_insensitive(skeleton):
    pretty = skeleton / "Custom" / "Footprints" / "Atomic_Footprints.pretty"
    (pretty / "X.KICAD_MOD").write_text('(footprint "X")\n', encoding="utf-8")
    assert find_footprint_libs(skeleton)[0].empty is False


def test_symbol_library_without_a_symbol_is_empty(tmp_path):
    (tmp_path / "Custom" / "Symbols").mkdir(parents=True)
    (tmp_path / "Custom" / "Symbols" / "Atomic_None.kicad_sym").write_text(NO_SYMBOLS, encoding="utf-8")
    (tmp_path / "Custom" / "Symbols" / "Atomic_One.kicad_sym").write_text(ONE_SYMBOL, encoding="utf-8")
    libs = {lib.nickname: lib.empty for lib in find_symbol_libs(tmp_path)}
    assert libs == {"Atomic_None": True, "Atomic_One": False}


def test_unreadable_library_counts_as_not_empty(tmp_path):
    (tmp_path / "Custom" / "Symbols").mkdir(parents=True)
    # not valid UTF-8: the file cannot be read as text
    (tmp_path / "Custom" / "Symbols" / "Atomic_Bad.kicad_sym").write_bytes(b"\xff\xfe\x00(symbol")
    assert [lib.empty for lib in find_symbol_libs(tmp_path)] == [False]


def test_holds_nothing_truth_table():
    assert ScanResult().holds_nothing is True
    only_empty = ScanResult(
        symbol_libs=[SymbolLibrary("A", "Custom/A.kicad_sym", "Custom", empty=True)],
        footprint_libs=[FootprintLibrary("B", "Custom/B.pretty", "Custom", empty=True)],
    )
    assert only_empty.holds_nothing is True
    with_symbol = ScanResult(
        symbol_libs=[SymbolLibrary("A", "Custom/A.kicad_sym", "Custom", empty=True),
                     SymbolLibrary("C", "Custom/C.kicad_sym", "Custom", empty=False)],
    )
    assert with_symbol.holds_nothing is False
    with_footprint = ScanResult(footprint_libs=[FootprintLibrary("B", "Custom/B.pretty", "Custom", empty=False)])
    assert with_footprint.holds_nothing is False
    # built without the flag: not empty
    assert SymbolLibrary("A", "a", "Custom").empty is False
    assert FootprintLibrary("B", "b", "Custom").empty is False
    assert ScanResult(symbol_libs=[SymbolLibrary("A", "a", "Custom")]).holds_nothing is False


def test_cache_round_trip_keeps_the_empty_flags():
    result = ScanResult(
        symbol_libs=[SymbolLibrary("A", "Custom/A.kicad_sym", "Custom", empty=True),
                     SymbolLibrary("C", "Custom/C.kicad_sym", "Custom", empty=False)],
        footprint_libs=[FootprintLibrary("B", "Custom/B.pretty", "Custom", empty=True),
                        FootprintLibrary("D", "Custom/D.pretty", "Custom", empty=False)],
    )
    back = scan_cache.decode_result(json.loads(json.dumps(scan_cache.encode_result(result))))
    assert [lib.empty for lib in back.symbol_libs] == [True, False]
    assert [lib.empty for lib in back.footprint_libs] == [True, False]
    assert back.holds_nothing is False
    assert back == result


def test_cache_decode_rejects_a_non_boolean_empty_flag():
    data = json.loads(json.dumps(scan_cache.encode_result(
        ScanResult(footprint_libs=[FootprintLibrary("B", "Custom/B.pretty", "Custom", empty=True)])
    )))
    data["footprint_libs"][0]["empty"] = "yes"
    with pytest.raises((ValueError, TypeError, KeyError)):
        scan_cache.decode_result(data)


def test_older_cache_format_is_not_reused(skeleton, tmp_path):
    cache_file = tmp_path / "state" / "scan_cache" / "abc.json"
    fp = scan_cache.fingerprint(skeleton, None)
    assert scan_cache.save(cache_file, skeleton, None, fp, scan_all(skeleton)) is None
    assert scan_cache.load_fresh(cache_file, skeleton, None).result is not None

    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["format"] = 2
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    check = scan_cache.load_fresh(cache_file, skeleton, None)
    assert check.result is None
    assert check.note.code == "cache.other_version"
