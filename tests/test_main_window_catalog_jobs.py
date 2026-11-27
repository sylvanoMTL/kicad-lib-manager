"""What the main window does after a finished catalog job (Phase 17 plan 14; CAT-04, CAT-05, CAT-06, CAT-08, CAT-12, D-18, D-20, D-21, D-28).

Every test builds MainWindow on a scratch collection under tmp_path. The first scan is a fake that returns a prepared
ScanResult; scan_source and remove_source run for real on the synthetic ThirdParty folders. The catalog window is
the real one with fake services, and the jobs it would run are replaced by CatalogOutcome values it emits. KiCad's
settings are never touched: sync_kicad_path_vars and would_change_path_vars are fakes. No git, no network, nothing
shown on the desktop (offscreen platform of the conftest).
"""

import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from catalogfixtures import FOOTPRINT_TEXT, SYMBOL_TEXT, make_third_party
from PySide6.QtCore import Qt
from collectionfixtures import make_collection

from kicad_lib_manager import library_scanner, main_window
from kicad_lib_manager.catalog import manifest
from kicad_lib_manager.catalog import ops as catalog_ops
from kicad_lib_manager.catalog import status as catalog_status
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.catalog.ops import NetStatus
from kicad_lib_manager.collection import Source
from kicad_lib_manager.models import FootprintLibrary, FootprintRef, Issue, ScanResult, Severity, SymbolLibrary
from kicad_lib_manager.widgets import catalog_dialog as cd

NET_OK = NetStatus(object(), (2, 50, 0), None, None)
WURTH_OLD = "WurthElektronik/KiCad-Library/"
FOLDER = "ThirdParty/Acme"
DECLINED = "config.declined"


def sym_file(name: str) -> str:
    """A symbol library file whose one symbol is called name."""
    return SYMBOL_TEXT.replace("R_Demo", name)


def acme(root: Path, symbols=("Plain",), footprints=("Land",), id="Acme") -> Path:
    """Write ThirdParty/<id> with one symbol library per symbols name and one footprint library per footprints name."""
    files = {f"symbols/{name}.kicad_sym": sym_file(name) for name in symbols}
    files.update({f"footprints/{name}.pretty/R_0603.kicad_mod": FOOTPRINT_TEXT for name in footprints})
    return make_third_party(root, id, files)


def record(root: Path, id="Acme", **vars) -> None:
    """catalog.json with one entry whose KiCad path variables are vars (variable -> folder in the clone)."""
    entry = CatalogEntry(
        id=id, url=f"https://github.com/acme/{id.lower()}.git", branch="main", commit="a" * 40,
        vars=dict(vars), licence_spdx="MIT", added_on="2026-11-20",
    )
    assert manifest.save(root, Manifest((entry,))) is None


def old_sym(nickname, rel_path, *, selected=False, source="Custom") -> SymbolLibrary:
    return SymbolLibrary(nickname, rel_path, source, selected=selected)


def old_fp(nickname, rel_path, *, selected=False, source="Custom") -> FootprintLibrary:
    return FootprintLibrary(nickname, rel_path, source, selected=selected)


def outcome(kind="add", id="Acme", *, ok=True, vars=None, legacy_prefix=None, name=None):
    return cd.CatalogOutcome(kind, id, name or id, ok, 1, 1, (), dict(vars or {}), legacy_prefix, False)


def log_lines(window) -> list[str]:
    return [line.split("] ", 1)[-1] for line in window._log._text.toPlainText().splitlines()]


def ticked(window) -> dict[str, bool]:
    result = window._scan_result
    return {lib.rel_path: lib.selected for lib in (*result.symbol_libs, *result.footprint_libs)}


def tree_text(window) -> str:
    """Every cell of both library trees, one string."""
    cells = []

    def walk(item):
        cells.extend(item.text(column) for column in range(item.columnCount()))
        for index in range(item.childCount()):
            walk(item.child(index))

    for tree in (window._tree._sym_tree, window._tree._fp_tree):
        for index in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(index))
    return "\n".join(cells)


@pytest.fixture
def harness(qtbot, monkeypatch, tmp_path):
    h = SimpleNamespace()
    h.tmp_path = tmp_path
    h.first_scan = ScanResult  # a factory: every full scan builds a fresh result
    h.scan_calls = []
    h.source_calls = []  # (function name, thread id) of every scan_source / remove_source call
    h.source_gate = None  # scan_source and remove_source wait on this event while it is set
    h.synced = []  # extra_vars of every sync_kicad_path_vars call
    h.questions = []  # (title, text) of every question that would have opened
    h.would_change = True
    h.sync_issues = None

    config_base = tmp_path / "kicad_cfg"
    config_base.mkdir()
    fp_dir = tmp_path / "kicad_fp"
    fp_dir.mkdir()

    def fake_scan(root, progress=None, kicad_fp_dir=None, *, skip=None, checking=None, model_vars=None):
        h.scan_calls.append(Path(root))
        return h.first_scan()

    real_scan_source, real_remove_source = library_scanner.scan_source, library_scanner.remove_source

    def spy_scan_source(*args, **kwargs):
        h.source_calls.append(("scan_source", threading.get_ident(), args[2]))
        if h.source_gate is not None:
            h.source_gate.wait(10)
        return real_scan_source(*args, **kwargs)

    def spy_remove_source(*args, **kwargs):
        h.source_calls.append(("remove_source", threading.get_ident(), args[1]))
        if h.source_gate is not None:
            h.source_gate.wait(10)
        return real_remove_source(*args, **kwargs)

    def fake_sync(repo, *, running=None, confirm=None, extra_vars=None, **kwargs):
        h.synced.append(dict(extra_vars or {}))
        changes = [(var, None, value) for var, value in (extra_vars or {}).items()]
        if confirm is not None and not confirm(changes):
            return [Issue(Severity.INFO, DECLINED, "Left KiCad's settings as they were.")]
        return h.sync_issues or []

    monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
    monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
    monkeypatch.setattr(main_window, "scan_all", fake_scan)
    monkeypatch.setattr(main_window, "scan_source", spy_scan_source, raising=False)
    monkeypatch.setattr(main_window, "remove_source", spy_remove_source, raising=False)
    monkeypatch.setattr(main_window, "kicad_running", lambda: [])
    monkeypatch.setattr(main_window, "sync_kicad_path_vars", fake_sync)
    monkeypatch.setattr(main_window, "would_change_path_vars", lambda repo, **kw: h.would_change)
    monkeypatch.setattr(catalog_ops, "net_status", lambda root, **kw: NET_OK)
    monkeypatch.setattr(catalog_status, "check_updates", lambda *a, **kw: {})
    services = replace(
        cd.CatalogServices(),
        net_status=lambda root: NET_OK,
        clean_staging=lambda root: [],
        current_path_vars=lambda **kw: {},
        size_on_disk=lambda folder: 1,
        check_updates=lambda *a, **kw: {},
    )
    monkeypatch.setattr(main_window, "CATALOG_SERVICES", services, raising=False)

    def make(root=None):
        if root is None:
            root = make_collection(tmp_path / "lib")
        window = main_window.MainWindow(root, Source.CHOSEN)
        qtbot.addWidget(window)
        qtbot.waitUntil(lambda: window._worker is None, timeout=30000)
        window._open_catalog()
        monkeypatch.setattr(
            window, "_question",
            lambda title, text, buttons, default: h.questions.append((title, text)) or default,
        )
        return window

    def finish(window):
        """Wait until the catalog window has left its finishing state."""
        qtbot.waitUntil(lambda: not window._catalog.is_finishing() and window._worker is None, timeout=15000)

    def run(window, value):
        window._catalog.job_finished.emit(value)
        finish(window)

    make.h = h
    make.finish = finish
    make.run = run
    make.wait = lambda predicate: qtbot.waitUntil(lambda: bool(predicate()), timeout=15000)
    return make


# -- Add and Reinstall: the one-source rescan and the selection ------------------------------------


def test_add_rescans_the_source_and_ticks(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    h.first_scan = lambda: ScanResult(symbol_libs=[
        old_sym("Clash", "Custom/Symbols/Clash.kicad_sym", selected=True),
    ])
    window = harness(root)
    h.scan_calls.clear()
    cache = main_window.scan_cache_file(root)
    assert FOLDER not in cache.read_text(encoding="utf-8")
    acme(root, symbols=("Plain", "Clash"))  # the Add has just written the folder
    progress_before = window._progress

    harness.run(window, outcome("add"))

    # one source read on a worker, no full scan, no Loading Libraries window
    assert [(name, folder) for name, _thread, folder in h.source_calls] == [("scan_source", FOLDER)]
    assert h.source_calls[0][1] != threading.get_ident()
    assert h.scan_calls == []
    assert window._progress is progress_before  # no new Loading Libraries window
    # the new libraries are ticked except the one that shares a nickname with another; nothing renamed
    assert ticked(window) == {
        "Custom/Symbols/Clash.kicad_sym": True,
        f"{FOLDER}/symbols/Plain.kicad_sym": True,
        f"{FOLDER}/symbols/Clash.kicad_sym": False,
        f"{FOLDER}/footprints/Land.pretty": True,
    }
    assert sorted(lib.nickname for lib in window._scan_result.symbol_libs) == ["Clash", "Clash", "Plain"]
    assert "Plain" in tree_text(window)
    # the catalog window got the new scan, the saved scan was rewritten
    assert window._catalog._scan is window._scan_result
    assert FOLDER in cache.read_text(encoding="utf-8")
    # the clash line is the catalog window's (ops writes it once); the main window adds none of its own
    assert not [line for line in log_lines(window) if "same name as libraries you already have" in line]
    # the one-source rescan ends with one line
    assert [line for line in log_lines(window) if line.startswith("Rescanned Acme")] != []


def test_clash_line_is_logged_once(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, symbols=("Clash",))
    h.first_scan = lambda: ScanResult(symbol_libs=[old_sym("Clash", "Custom/Symbols/Clash.kicad_sym")])
    window = harness(root)
    line = "1 libraries of Acme have the same name as libraries you already have and start unticked: Clash."

    window._catalog.log_line.emit(line, "warning")  # what the catalog window forwards from ops
    harness.run(window, outcome("add"))

    assert log_lines(window).count(line) == 1


def test_full_scan_when_source_rescan_is_not_possible(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, symbols=("Plain", "Clash"))
    h.first_scan = lambda: ScanResult(symbol_libs=[old_sym("Clash", "Custom/Symbols/Clash.kicad_sym", selected=True)])
    window = harness(root)
    # no earlier scan: scan_source answers rescan.full_needed and the full scan runs instead
    window._scan_result = None
    h.scan_calls.clear()
    h.first_scan = lambda: ScanResult(symbol_libs=[
        old_sym("Clash", "Custom/Symbols/Clash.kicad_sym"),
        SymbolLibrary("Plain", f"{FOLDER}/symbols/Plain.kicad_sym", "Acme"),
        SymbolLibrary("Clash", f"{FOLDER}/symbols/Clash.kicad_sym", "Acme",
                      collision_peers=["Custom/Symbols/Clash.kicad_sym"]),
    ])

    harness.run(window, outcome("add"))

    assert [name for name, _thread, _folder in h.source_calls] == ["scan_source"]
    assert len(h.scan_calls) == 1  # the full scan ran instead
    # the same selection rules afterwards
    assert ticked(window) == {
        "Custom/Symbols/Clash.kicad_sym": False,
        f"{FOLDER}/symbols/Plain.kicad_sym": True,
        f"{FOLDER}/symbols/Clash.kicad_sym": False,
    }


def test_wurth_selection_carries_over(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, id="WurthElektronik", symbols=("A", "B"), footprints=("F",))
    wurth_new = "ThirdParty/WurthElektronik"
    h.first_scan = lambda: ScanResult(
        symbol_libs=[
            old_sym("A", f"{WURTH_OLD}symbols/A.kicad_sym", selected=True, source="WurthElektronik"),
            old_sym("B", f"{WURTH_OLD}symbols/B.kicad_sym", selected=False, source="WurthElektronik"),
        ],
        footprint_libs=[old_fp("F", f"{WURTH_OLD}footprints/F.pretty", selected=True, source="WurthElektronik")],
    )
    window = harness(root)

    harness.run(window, outcome("add", "WurthElektronik", legacy_prefix=WURTH_OLD))

    assert ticked(window) == {
        f"{WURTH_OLD}symbols/A.kicad_sym": False,
        f"{WURTH_OLD}symbols/B.kicad_sym": False,
        f"{WURTH_OLD}footprints/F.pretty": False,
        f"{wurth_new}/symbols/A.kicad_sym": True,
        f"{wurth_new}/symbols/B.kicad_sym": False,
        f"{wurth_new}/footprints/F.pretty": True,
    }
    lines = log_lines(window)
    assert (
        "Moved 2 selected libraries from WurthElektronik/KiCad-Library to ThirdParty/WurthElektronik. "
        "Generate Tables rewrites their entries."
    ) in lines
    assert sum(line.startswith("Moved ") for line in lines) == 1


def test_wurth_carry_over_with_nothing_ticked_writes_no_line(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, id="WurthElektronik", symbols=("A",), footprints=())
    h.first_scan = lambda: ScanResult(symbol_libs=[
        old_sym("A", f"{WURTH_OLD}symbols/A.kicad_sym", source="WurthElektronik"),
    ])
    window = harness(root)

    harness.run(window, outcome("add", "WurthElektronik", legacy_prefix=WURTH_OLD))

    assert not [line for line in log_lines(window) if line.startswith("Moved ")]
    assert ticked(window)["ThirdParty/WurthElektronik/symbols/A.kicad_sym"] is False


def test_legacy_prefix_comes_from_the_curated_entry_when_the_outcome_has_none(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, id="WurthElektronik", symbols=("A",), footprints=())
    h.first_scan = lambda: ScanResult(symbol_libs=[
        old_sym("A", f"{WURTH_OLD}symbols/A.kicad_sym", selected=True, source="WurthElektronik"),
    ])
    window = harness(root)

    harness.run(window, outcome("reinstall", "WurthElektronik"))

    assert ticked(window)["ThirdParty/WurthElektronik/symbols/A.kicad_sym"] is True
    assert ticked(window)[f"{WURTH_OLD}symbols/A.kicad_sym"] is False


# -- the path variable question --------------------------------------------------------------------


def test_path_variable_question_after_add(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    record(root, ACME_3D="3dmodels")
    window = harness(root)

    harness.run(window, outcome("add", vars={"ACME_3D": "3dmodels"}))

    # the existing question, with the catalog variables as extra_vars; No writes nothing
    assert [title for title, _text in h.questions] == ["Change KiCad path variables?"]
    assert "ACME_3D" in h.questions[0][1]
    assert len(h.synced) == 1 and set(h.synced[0]) == {"ACME_3D"}
    assert any(line.startswith("KiCad") and "will offer the change again" in line for line in log_lines(window))
    assert not window._path_var_busy


def test_no_question_when_nothing_would_change_or_no_variable_is_needed(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    record(root, ACME_3D="3dmodels")
    window = harness(root)

    h.would_change = False
    harness.run(window, outcome("add", vars={"ACME_3D": "3dmodels"}))  # KiCad already holds the right folder
    h.would_change = True
    harness.run(window, outcome("reinstall", vars={}))  # the library needs no variable
    harness.run(window, outcome("update", vars={"ACME_3D": "3dmodels"}))  # an update asks nothing

    assert h.questions == []
    assert h.synced == []


# -- the finishing state ---------------------------------------------------------------------------


def test_finishing_state_spans_rescan_and_question(harness, monkeypatch):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    record(root, ACME_3D="3dmodels")
    window = harness(root)
    dialog = window._catalog
    seen = []
    real = dialog.set_finishing
    monkeypatch.setattr(dialog, "set_finishing", lambda on: seen.append(bool(on)) or real(on))
    during = {}

    def question(title, text, buttons, default):
        during["finishing"] = dialog.is_finishing()
        during["refusal"] = window._switch_refusal()
        return default

    monkeypatch.setattr(window, "_question", question)
    h.source_gate = threading.Event()

    dialog.job_finished.emit(outcome("add", vars={"ACME_3D": "3dmodels"}))
    # while the source is read: finishing, a folder switch is refused
    assert dialog.is_finishing()
    assert window._switch_refusal() is not None
    h.source_gate.set()
    harness.finish(window)

    assert during["finishing"] is True
    assert during["refusal"] is not None
    assert seen == [True, False]
    assert window._switch_refusal() is None


def test_finishing_ends_after_a_failed_source_read(harness, monkeypatch):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)

    def broken(*args, **kwargs):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(main_window, "scan_source", broken, raising=False)
    harness.run(window, outcome("add"))

    assert not window._catalog.is_finishing()
    assert any("Library catalog step failed:" in line and "disk gone" in line for line in log_lines(window))
    assert len(h.scan_calls) == 2  # startup, then the full scan that replaces the failed read


# -- Update and Remove -----------------------------------------------------------------------------


def test_update_keeps_ticks_and_ticks_new(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, symbols=("StayOn", "StayOff", "Fresh"), footprints=())
    h.first_scan = lambda: ScanResult(symbol_libs=[
        SymbolLibrary("StayOn", f"{FOLDER}/symbols/StayOn.kicad_sym", "Acme", selected=True),
        SymbolLibrary("StayOff", f"{FOLDER}/symbols/StayOff.kicad_sym", "Acme", selected=False),
        SymbolLibrary("Gone", f"{FOLDER}/symbols/Gone.kicad_sym", "Acme", selected=True),
    ])
    window = harness(root)

    harness.run(window, outcome("update"))

    assert ticked(window) == {
        f"{FOLDER}/symbols/StayOn.kicad_sym": True,
        f"{FOLDER}/symbols/StayOff.kicad_sym": False,
        f"{FOLDER}/symbols/Fresh.kicad_sym": True,
    }
    assert f"Dropped 1 selections for libraries no longer found: {FOLDER}/symbols/Gone.kicad_sym" in log_lines(window)
    assert h.questions == []  # an update never asks about path variables


def test_remove_drops_the_source(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    h.first_scan = lambda: ScanResult(
        symbol_libs=[
            old_sym("Mine", "Custom/Symbols/Mine.kicad_sym", selected=True),
            SymbolLibrary("Plain", f"{FOLDER}/symbols/Plain.kicad_sym", "Acme", selected=True),
        ],
        footprint_libs=[FootprintLibrary("Land", f"{FOLDER}/footprints/Land.pretty", "Acme", selected=True)],
    )
    window = harness(root)
    (root / "sym-lib-table").write_bytes(
        b"(sym_lib_table\r\n  (version 7)\r\n"
        b'  (lib (name "Plain")(type "KiCad")(uri "${KICAD_LIB_GITHUB}/ThirdParty/Acme/symbols/Plain.kicad_sym")'
        b'(options "")(descr ""))\r\n)\r\n'
    )

    harness.run(window, outcome("remove"))

    assert [name for name, _thread, _folder in h.source_calls] == ["remove_source"]
    assert ticked(window) == {"Custom/Symbols/Mine.kicad_sym": True}
    assert "Plain" not in tree_text(window)
    # path variables are not unset and nothing is asked
    assert h.questions == [] and h.synced == []
    # the next Generate Tables drops the managed entry through the existing merge
    window._on_generate()
    harness.wait(lambda: not window._path_var_busy)
    assert any("removed" in line.lower() and "Plain" in line for line in log_lines(window))
    assert b"Plain" not in (root / "sym-lib-table").read_bytes()


def test_update_clashes_start_unticked_and_say_so(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root, symbols=("Clash",), footprints=())
    h.first_scan = lambda: ScanResult(symbol_libs=[old_sym("Clash", "Custom/Symbols/Clash.kicad_sym", selected=True)])
    window = harness(root)

    harness.run(window, outcome("update"))

    assert ticked(window)[f"{FOLDER}/symbols/Clash.kicad_sym"] is False
    assert "1 libraries of Acme have the same name as libraries you already have and start unticked: Clash." in log_lines(window)


# -- the catalog window's buttons ------------------------------------------------------------------


def test_set_path_variables_button_runs_the_question(harness):
    h = harness.h
    window = harness()
    window._catalog.path_vars_requested.emit("Acme")
    harness.wait(lambda: not window._path_var_busy)
    assert len(h.synced) == 1


def test_generate_button_runs_generate(harness, monkeypatch):
    window = harness()
    seen = []
    monkeypatch.setattr(window, "_on_generate", lambda: seen.append(True) or [])
    window._catalog.generate_requested.emit()
    assert seen == [True]


def test_catalog_window_has_scan_and_footprint_folder(harness, monkeypatch):
    h = harness.h
    h.first_scan = lambda: ScanResult(symbol_libs=[old_sym("Mine", "Custom/Symbols/Mine.kicad_sym")])
    window = harness()
    dialog = window._catalog
    assert dialog._scan is window._scan_result
    assert window._kicad_fp_dir is not None
    assert dialog._kicad_fp_dir == window._kicad_fp_dir

    new_folder = h.tmp_path / "other_fp"
    new_folder.mkdir()
    monkeypatch.setattr(main_window.QFileDialog, "getExistingDirectory", lambda *a, **k: str(new_folder))
    window._on_set_kicad_path()
    harness.wait(lambda: window._worker is None)
    assert dialog._kicad_fp_dir == new_folder
    assert dialog._scan is window._scan_result


# -- the log (C14) ---------------------------------------------------------------------------------


def test_failed_job_logs_one_error_and_raw_text(harness):
    h = harness.h
    window = harness()
    before = len(log_lines(window))

    dialog = window._catalog
    dialog.log_line.emit("Could not add Acme: the download failed.", "error")  # what the catalog window logs
    dialog.log_line.emit("Library catalog step failed: git exited with 128", "error")
    dialog.job_finished.emit(outcome("add", ok=False))
    harness.finish(window)

    new = log_lines(window)[before:]
    assert new == ["Could not add Acme: the download failed.", "Library catalog step failed: git exited with 128"]
    assert h.source_calls == []  # a failed job rescans nothing
    assert not dialog.is_finishing()


def test_no_log_line_while_job_runs(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    h.source_gate = threading.Event()
    before = log_lines(window)

    window._catalog.job_finished.emit(outcome("add"))
    assert window._catalog.is_finishing()
    assert log_lines(window) == before  # the rescan is silent until it ends
    h.source_gate.set()
    harness.finish(window)

    assert len(log_lines(window)) > len(before)


def test_name_lists_are_capped(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    names = [f"Clash{n}" for n in range(7)]
    acme(root, symbols=names, footprints=())
    h.first_scan = lambda: ScanResult(
        symbol_libs=[
            *[old_sym(name, f"Custom/Symbols/{name}.kicad_sym") for name in names],
            *[SymbolLibrary(f"Old{n}", f"{FOLDER}/symbols/Old{n}.kicad_sym", "Acme", selected=True) for n in range(7)],
        ],
    )
    window = harness(root)

    harness.run(window, outcome("update"))

    lines = log_lines(window)
    clash = next(line for line in lines if "start unticked" in line)
    assert clash.endswith("Clash0, Clash1, Clash2, Clash3, Clash4 and 2 more.")
    assert clash.startswith("7 libraries of Acme")
    dropped = next(line for line in lines if line.startswith("Dropped 7 selections"))
    assert dropped.count(".kicad_sym") == 5
    assert dropped.endswith("and 2 more")


# -- the refreshing state over the trees (owner finding 2 of 17-17) --------------------------------


def test_refresh_overlay_during_the_source_read(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    h.source_gate = threading.Event()
    overlay = window._refresh_overlay
    assert not overlay.isVisibleTo(window)

    window._catalog.job_finished.emit(outcome("add"))

    assert overlay.isVisibleTo(window)
    assert overlay.text() == "Refreshing the library list after adding Acme. Large libraries can take a minute."
    assert not window._tree.isEnabled()
    assert not window._generate_btn.isEnabled()
    worker = window._catalog_workers[0]
    worker.progress.emit(4210, 11050)
    assert overlay.count_text() == "4,210 of 11,050 files"
    assert (overlay.bar_value(), overlay.bar_maximum()) == (38, 100)

    h.source_gate.set()
    harness.finish(window)

    assert not overlay.isVisibleTo(window)
    assert window._tree.isEnabled()


def test_refresh_disables_the_list_controls(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    controls = (window._select_all_btn, window._deselect_all_btn, window._tree, window._generate_btn)
    before = [control.isEnabled() for control in controls]
    tip = window._generate_btn.toolTip()
    assert before == [True, True, True, True]
    h.source_gate = threading.Event()

    window._catalog.job_finished.emit(outcome("add"))

    assert not any(control.isEnabled() for control in controls)
    assert window._generate_btn.toolTip() == main_window._WAIT_FOR_CATALOG
    h.source_gate.set()
    harness.finish(window)

    assert [control.isEnabled() for control in controls] == before
    assert window._generate_btn.toolTip() == tip


def test_refresh_controls_stay_off_while_a_scan_runs(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)

    window._set_scan_running(True)

    assert not window._select_all_btn.isEnabled()
    assert not window._deselect_all_btn.isEnabled()
    window._set_scan_running(False)
    assert window._select_all_btn.isEnabled()


@pytest.mark.parametrize("how", ["fallback", "failure"])
def test_refresh_ends_on_fallback_and_failure(harness, monkeypatch, how):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    if how == "fallback":
        window._scan_result = None  # no earlier scan: the read answers 'run the full scan'
    else:
        def boom(*args, **kwargs):
            raise RuntimeError("disk gone")

        monkeypatch.setattr(main_window, "scan_source", boom)
    seen = []
    real_start = window._start_scan

    def start_scan(*args, **kwargs):
        seen.append((window._refresh_overlay.isHidden(), window._tree.isEnabled()))
        return real_start(*args, **kwargs)

    monkeypatch.setattr(window, "_start_scan", start_scan)
    h.source_gate = threading.Event()

    window._catalog.job_finished.emit(outcome("add"))
    assert not window._refresh_overlay.isHidden()
    h.source_gate.set()
    harness.finish(window)

    # hidden, and the trees usable again, before the Loading Libraries window's scan started
    assert seen and seen[0] == (True, True)
    assert window._refresh_overlay.isHidden()
    assert window._tree.isEnabled()


@pytest.mark.parametrize(("kind", "verb"), [("update", "updating"), ("remove", "removing"), ("reinstall", "reinstalling")])
def test_refresh_for_update_and_remove(harness, kind, verb):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    h.source_gate = threading.Event()

    window._catalog.job_finished.emit(outcome(kind))

    assert window._refresh_overlay.text() == (
        f"Refreshing the library list after {verb} Acme. Large libraries can take a minute."
    )
    h.source_gate.set()
    harness.finish(window)
    assert window._refresh_overlay.isHidden()


def test_progress_is_throttled_to_whole_percents(qtbot, tmp_path):
    worker = main_window.CatalogRescanWorker(tmp_path, None, None, "add", "ThirdParty/Big")
    counts = []
    worker.progress.connect(lambda done, total: counts.append((done, total)))

    for done in range(0, 11051):
        worker._report(done, 11050)

    assert len(counts) <= 102
    assert counts[0] == (0, 11050)
    assert counts[-1] == (11050, 11050)
    assert [done for done, _total in counts] == sorted(done for done, _total in counts)


def test_close_stops_the_wheel(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    acme(root)
    window = harness(root)
    window.show()
    wheel = window._refresh_overlay.wheel

    # closing while the read runs waits for the job, then closes; the wheel is off by then
    h.source_gate = threading.Event()
    window._catalog.job_finished.emit(outcome("add"))
    assert wheel.is_spinning()
    window.close()
    h.source_gate.set()
    harness.wait(lambda: not window.isVisible())
    assert not wheel.is_spinning()


def test_close_with_the_overlay_showing_stops_the_wheel(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    window = harness(root)
    window.show()
    window._refresh_overlay.show_for("add", "Acme")
    wheel = window._refresh_overlay.wheel
    assert wheel.is_spinning()

    window.close()

    assert not window.isVisible()
    assert not wheel.is_spinning()


# -- the log and the trees name a catalog library the way the catalog does (owner findings 3 and 6) ---


ABSOLUTE_MODEL_FOOTPRINT = '(footprint "A"\n  (model "C:/Old/models/m{n}.step")\n)\n'


def record_by_address(root: Path, id: str, url: str) -> None:
    entry = CatalogEntry(
        id=id, url=url, branch="main", commit="a" * 40, vars={}, licence_spdx="MIT", added_on="2026-11-20",
    )
    assert manifest.save(root, Manifest((entry,))) is None


def test_log_shows_one_line_per_catalog_library(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    record_by_address(root, "Acme", "https://github.com/acme/acme.git")
    raw = [
        Issue(
            Severity.WARNING, "scan.model_absolute",
            f"[ThirdParty/Acme/footprints/Old.pretty/P{n}.kicad_mod] Absolute/non-variable 3D model path: C:/Old/models/m{n}.step",
        )
        for n in range(300)
    ]
    h.first_scan = lambda: ScanResult(issues=list(raw))

    window = harness(root)

    # the first scan writes one summary line for the library and keeps every issue in the result
    summary = [line for line in log_lines(window) if line.startswith("acme/acme:")]
    assert len(summary) == 1
    assert summary[0].startswith(
        "acme/acme: 300 footprints point their 3D model at a fixed folder instead of a path variable, for example "
    )
    assert not [line for line in log_lines(window) if "Absolute/non-variable" in line]
    assert len(window._scan_result.issues) == 300

    # a rescan of the source counts the raw lines, and writes one summary line for them
    files = {f"footprints/F.pretty/P{n}.kicad_mod": ABSOLUTE_MODEL_FOOTPRINT.format(n=n) for n in range(300)}
    make_third_party(root, "Acme", files)
    harness.run(window, outcome("add", name="acme/acme"))

    lines = log_lines(window)
    assert "Rescanned acme/acme: 300 warnings" in lines
    assert len([line for line in lines if line.startswith("acme/acme: 300 footprints")]) == 2
    assert not [line for line in lines if "Absolute/non-variable" in line]
    assert sum(1 for i in window._scan_result.issues if i.code == "scan.model_absolute") == 300


def test_trees_show_catalog_names(harness):
    h = harness.h
    root = make_collection(h.tmp_path / "lib")
    record_by_address(root, "4ms-4ms-kicad-lib", "https://github.com/4ms/4ms-kicad-lib.git")
    base = "ThirdParty/4ms-4ms-kicad-lib"
    h.first_scan = lambda: ScanResult(
        symbol_libs=[
            SymbolLibrary("Mine", "Custom/Symbols/Mine.kicad_sym", "Custom"),
            SymbolLibrary(
                "Four", f"{base}/symbols/Four.kicad_sym", "4ms-4ms-kicad-lib",
                footprint_refs=[FootprintRef("Four_FP", "X", True)],
            ),
        ],
        footprint_libs=[
            FootprintLibrary("Four_FP", f"{base}/footprints/Four_FP.pretty", "4ms-4ms-kicad-lib"),
            FootprintLibrary("Mine_FP", "Custom/Footprints/Mine_FP.pretty", "Custom"),
        ],
    )

    window = harness(root)

    sym_tree, fp_tree = window._tree._sym_tree, window._tree._fp_tree
    for tree in (sym_tree, fp_tree):
        headers = sorted(tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount()))
        assert headers == ["4ms/4ms-kicad-lib", "Custom"]
        for i in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(i)
            for j in range(group.childCount()):
                assert group.child(j).text(1) == group.text(0)
    assert "4ms-4ms-kicad-lib" not in tree_text(window)

    # ticking the header ticks exactly that source's libraries (and the footprint they link)
    group = next(
        sym_tree.topLevelItem(i) for i in range(sym_tree.topLevelItemCount())
        if sym_tree.topLevelItem(i).text(0) == "4ms/4ms-kicad-lib"
    )
    group.setCheckState(0, Qt.CheckState.Checked)

    assert ticked(window) == {
        "Custom/Symbols/Mine.kicad_sym": False,
        f"{base}/symbols/Four.kicad_sym": True,
        f"{base}/footprints/Four_FP.pretty": True,
        "Custom/Footprints/Mine_FP.pretty": False,
    }
