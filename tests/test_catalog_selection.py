"""Preselection of a catalog source's libraries after a job (Phase 17 plan 14; CAT-05, CAT-08, CAT-12, D-20, D-28).

preselect_source works on plain ScanResult objects, so these tests need no window, no disk and no git.
"""

from kicad_lib_manager.catalog.selection import SelectionChange, preselect_source
from kicad_lib_manager.models import FootprintLibrary, ScanResult, SymbolLibrary

# Fake folder names: the tests read no repository data
NEW = "ThirdParty/Acme"
WURTH_NEW = "ThirdParty/WurthElektronik"
WURTH_OLD = "WurthElektronik/KiCad-Library/"


def sym(rel_path, *, selected=False, peers=(), source="Acme"):
    nickname = rel_path.rsplit("/", 1)[-1].removesuffix(".kicad_sym")
    return SymbolLibrary(nickname, rel_path, source, selected=selected, collision_peers=list(peers))


def fp(rel_path, *, selected=False, peers=(), source="Acme"):
    nickname = rel_path.rsplit("/", 1)[-1].removesuffix(".pretty")
    return FootprintLibrary(nickname, rel_path, source, selected=selected, collision_peers=list(peers))


def state(result):
    return {lib.rel_path: lib.selected for lib in (*result.symbol_libs, *result.footprint_libs)}


def test_add_ticks_the_source_except_clashes():
    result = ScanResult(
        symbol_libs=[
            sym(f"{NEW}/symbols/Plain.kicad_sym"),
            sym(f"{NEW}/symbols/Clash.kicad_sym", peers=["Custom/Symbols/Clash.kicad_sym"]),
            sym("Custom/Symbols/Clash.kicad_sym", selected=True, source="Custom"),
            sym("Other/Elsewhere.kicad_sym", source="Other"),
        ],
        footprint_libs=[fp(f"{NEW}/footprints/Land.pretty")],
    )

    change = preselect_source(result, NEW)

    assert state(result) == {
        f"{NEW}/symbols/Plain.kicad_sym": True,
        f"{NEW}/symbols/Clash.kicad_sym": False,
        "Custom/Symbols/Clash.kicad_sym": True,  # another source: untouched
        "Other/Elsewhere.kicad_sym": False,  # another source: untouched
        f"{NEW}/footprints/Land.pretty": True,
    }
    assert change == SelectionChange(selected=2, unticked=("Clash",), moved=0)


def test_update_ticks_only_new_libraries():
    staying_off = f"{NEW}/symbols/StayOff.kicad_sym"
    staying_on = f"{NEW}/symbols/StayOn.kicad_sym"
    fresh = f"{NEW}/symbols/Fresh.kicad_sym"
    fresh_clash = f"{NEW}/symbols/FreshClash.kicad_sym"
    result = ScanResult(symbol_libs=[
        sym(staying_off), sym(staying_on, selected=True), sym(fresh),
        sym(fresh_clash, peers=["Custom/Symbols/FreshClash.kicad_sym"]),
    ])

    change = preselect_source(result, NEW, only={fresh, fresh_clash})

    assert state(result) == {staying_off: False, staying_on: True, fresh: True, fresh_clash: False}
    assert change.selected == 1
    assert change.unticked == ("FreshClash",)


def test_legacy_twins_move_their_tick():
    old_a = f"{WURTH_OLD}symbols/A.kicad_sym"
    new_a = f"{WURTH_NEW}/symbols/A.kicad_sym"
    old_b = f"{WURTH_OLD}symbols/B.kicad_sym"
    new_b = f"{WURTH_NEW}/symbols/B.kicad_sym"
    old_fp = f"{WURTH_OLD}footprints/F.pretty"
    new_fp = f"{WURTH_NEW}/footprints/F.pretty"
    result = ScanResult(
        symbol_libs=[
            sym(old_a, selected=True, peers=[new_a], source="Wurth"),
            sym(new_a, peers=[old_a], source="Wurth"),
            sym(old_b, selected=False, peers=[new_b], source="Wurth"),
            sym(new_b, peers=[old_b], source="Wurth"),
        ],
        footprint_libs=[
            fp(old_fp, selected=True, peers=[new_fp], source="Wurth"),
            fp(new_fp, peers=[old_fp], source="Wurth"),
        ],
    )

    change = preselect_source(result, WURTH_NEW, legacy_prefix=WURTH_OLD)

    assert state(result) == {
        old_a: False, new_a: True,
        old_b: False, new_b: False,  # an unticked twin keeps the new one unticked even though it collides
        old_fp: False, new_fp: True,
    }
    assert change.moved == 2
    assert change.selected == 2
    assert change.unticked == ()


def test_no_twin_ticked_changes_nothing_extra():
    old_a = f"{WURTH_OLD}symbols/A.kicad_sym"
    new_a = f"{WURTH_NEW}/symbols/A.kicad_sym"
    result = ScanResult(symbol_libs=[
        sym(old_a, peers=[new_a], source="Wurth"),
        sym(new_a, peers=[old_a], source="Wurth"),
    ])

    change = preselect_source(result, WURTH_NEW, legacy_prefix=WURTH_OLD)

    assert state(result) == {old_a: False, new_a: False}
    assert change.moved == 0
    assert change.selected == 0


def test_legacy_prefix_without_slash_and_library_without_twin():
    old_a = f"{WURTH_OLD}symbols/A.kicad_sym"
    new_a = f"{WURTH_NEW}/symbols/A.kicad_sym"
    lone = f"{WURTH_NEW}/symbols/Lone.kicad_sym"
    result = ScanResult(symbol_libs=[
        sym(old_a, selected=True, peers=[new_a], source="Wurth"),
        sym(new_a, peers=[old_a], source="Wurth"),
        sym(lone, source="Wurth"),
    ])

    change = preselect_source(result, WURTH_NEW, legacy_prefix=WURTH_OLD.rstrip("/"))

    assert state(result) == {old_a: False, new_a: True, lone: True}
    assert change.moved == 1
    assert change.selected == 2


def test_never_renames():
    result = ScanResult(
        symbol_libs=[sym(f"{NEW}/symbols/Clash.kicad_sym", peers=["Custom/Symbols/Clash.kicad_sym"])],
        footprint_libs=[fp(f"{NEW}/footprints/Land.pretty")],
    )

    preselect_source(result, NEW)

    assert [lib.nickname for lib in result.symbol_libs] == ["Clash"]
    assert [lib.nickname for lib in result.footprint_libs] == ["Land"]
    assert result.symbol_libs[0].rel_path == f"{NEW}/symbols/Clash.kicad_sym"


def test_folder_prefix_needs_the_slash():
    # ThirdParty/AcmeMore is another source, never part of ThirdParty/Acme
    other = f"{NEW}More/symbols/X.kicad_sym"
    result = ScanResult(symbol_libs=[sym(other)])

    change = preselect_source(result, NEW)

    assert state(result) == {other: False}
    assert change.selected == 0


def test_same_nickname_clash_names_are_listed_once():
    a = f"{NEW}/symbols/A/Dup.kicad_sym"
    b = f"{NEW}/symbols/B/Dup.kicad_sym"
    result = ScanResult(
        symbol_libs=[sym(a, peers=[b]), sym(b, peers=[a])],
        footprint_libs=[fp(f"{NEW}/footprints/Dup.pretty", peers=["Custom/Footprints/Dup.pretty"])],
    )

    change = preselect_source(result, NEW)

    assert change.selected == 0
    assert change.unticked == ("Dup",)
