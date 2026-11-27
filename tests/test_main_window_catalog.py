"""The library catalog in the main window (Phase 17 plan 12; CAT-01, CAT-05, CAT-06, CAT-07, D-12, D-16, D-17, D-19, D-32).

Every test builds MainWindow on a scratch collection under tmp_path. The scan, the Git check and the update
check are fakes (no git process, no network); the catalog window gets a CatalogServices of fakes through the
CATALOG_SERVICES seam. Nothing is shown on the desktop (offscreen platform of the conftest).
"""

import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from kicad_lib_manager import main_window
from kicad_lib_manager.catalog import curated, manifest
from kicad_lib_manager.catalog import ops as catalog_ops
from kicad_lib_manager.catalog import status as catalog_status
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.catalog.ops import NetStatus
from kicad_lib_manager.catalog.status import Check, UpdateState
from kicad_lib_manager.collection import Source
from kicad_lib_manager.models import Issue, ScanResult, Severity
from kicad_lib_manager.widgets import catalog_dialog as cd

SHA = "a" * 40
NEWER = "b" * 40
NOW = datetime(2026, 11, 27, 12, 0, 0)
NET_OK = NetStatus(object(), (2, 50, 0), None, None)
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")

PLAIN_TEXT = "Library &Catalog..."
PLAIN_TIP = "Add, update or remove third-party KiCad libraries from GitHub"


def entry(id, *, commit=SHA):
    return CatalogEntry(
        id=id,
        url=f"https://github.com/acme/{id.lower()}.git",
        branch="main",
        commit=commit,
        licence_spdx="MIT",
        added_on="2026-11-20",
    )


def state(id, check, sha=None):
    return UpdateState(id, check, sha, NOW)


def write_collection(base: Path, entries=(), *, folders=None) -> Path:
    """A scratch collection with catalog.json for entries and an installed folder for each id in folders."""
    root = make_collection(base)
    for id in (folders if folders is not None else [e.id for e in entries]):
        make_third_party(root, id, {"a.kicad_sym": "(kicad_symbol_lib)"})
    if entries:
        assert manifest.save(root, Manifest(tuple(entries))) is None
    return root


def log_lines(window) -> list[str]:
    """The text of every log line, oldest first, without its time stamp."""
    return [line.split("] ", 1)[-1] for line in window._log._text.toPlainText().splitlines()]


def catalog_lines(window) -> list[str]:
    return [line for line in log_lines(window) if "catalog librar" in line]


@pytest.fixture
def harness(qtbot, monkeypatch, tmp_path):
    h = SimpleNamespace()
    h.scan_calls = []  # keyword arguments of every scan_all call
    h.scan_gate = None  # a scan waits on this event while it is set
    h.net = NET_OK
    h.net_calls = []
    h.check_calls = []  # SimpleNamespace(root, mf, cancel, thread) of every update check
    h.check_gate = None  # an update check waits on this event while it is set
    h.states_for = lambda root, mf: {}
    h.tmp_path = tmp_path

    config_base = tmp_path / "kicad_cfg"
    config_base.mkdir()
    fp_dir = tmp_path / "kicad_fp"
    fp_dir.mkdir()

    def fake_scan(root, progress=None, kicad_fp_dir=None, *, skip=None, checking=None, model_vars=None):
        h.scan_calls.append({"root": Path(root), "model_vars": model_vars})
        if h.scan_gate is not None:
            h.scan_gate.wait(10)
        return ScanResult()

    def fake_net_status(root, **kwargs):
        h.net_calls.append(Path(root))
        return h.net

    def fake_check_updates(root, mf, net, *, cancel=None, on_one=None, now=datetime.now):
        call = SimpleNamespace(root=Path(root), mf=mf, cancel=cancel, thread=threading.get_ident())
        h.check_calls.append(call)
        if h.check_gate is not None:
            h.check_gate.wait(10)
        return h.states_for(Path(root), mf)

    monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
    monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
    monkeypatch.setattr(main_window, "scan_all", fake_scan)
    monkeypatch.setattr(main_window, "kicad_running", lambda: [])
    monkeypatch.setattr(catalog_ops, "net_status", fake_net_status)
    monkeypatch.setattr(catalog_status, "check_updates", fake_check_updates)
    h.services = replace(
        cd.CatalogServices(),
        net_status=lambda root: h.net,
        clean_staging=lambda root: [],
        current_path_vars=lambda **kw: {},
        size_on_disk=lambda folder: 1,
        check_updates=fake_check_updates,
    )
    monkeypatch.setattr(main_window, "CATALOG_SERVICES", h.services, raising=False)

    def make(root=None, *, wait=True):
        if root is None:
            root = write_collection(tmp_path / "lib")
        window = main_window.MainWindow(root, Source.CHOSEN)
        qtbot.addWidget(window)
        if wait:
            qtbot.waitUntil(lambda: window._worker is None, timeout=30000)
        return window

    def settle(window):
        """Wait until the startup check (if one runs) has ended."""
        qtbot.waitUntil(lambda: window._catalog_check is None, timeout=10000)

    make.h = h
    make.settle = settle
    make.wait = lambda predicate: qtbot.waitUntil(lambda: bool(predicate()), timeout=10000)
    return make


# -- the menu entry ------------------------------------------------------------------------------


def test_menu_entry_text_shortcut_place(harness):
    window = harness()
    file_menu = window._file_menu
    actions = file_menu.actions()
    at = actions.index(window._act_import)
    assert actions[at + 1] is window._act_catalog
    assert actions[at + 2].isSeparator()
    act = window._act_catalog
    assert act.text() == PLAIN_TEXT
    assert act.shortcut() == QKeySequence("Ctrl+Shift+L")
    assert QKeySequence.mnemonic(act.text()) == QKeySequence("Alt+C")
    assert act.toolTip() == PLAIN_TIP
    assert act.statusTip() == PLAIN_TIP
    assert act.isEnabled()


def test_menu_entry_is_enabled_while_a_scan_runs(harness):
    harness.h.scan_gate = threading.Event()
    try:
        window = harness(wait=False)
        assert window._worker is not None
        assert window._act_catalog.isEnabled()
    finally:
        harness.h.scan_gate.set()


# -- the one window ------------------------------------------------------------------------------


def test_one_window_raised_again(harness):
    window = harness()
    assert window._catalog is None
    window._act_catalog.trigger()
    first = window._catalog
    assert isinstance(first, cd.CatalogDialog)
    assert first.parent() is None
    assert first.isVisible()
    first.hide()
    window._act_catalog.trigger()
    assert window._catalog is first
    assert first.isVisible()
    window._open_catalog()
    assert window._catalog is first


def test_window_is_centred_over_the_main_window(harness):
    window = harness()
    window.show()
    window._open_catalog()
    dialog = window._catalog
    delta = dialog.frameGeometry().center() - window.frameGeometry().center()
    assert abs(delta.x()) <= 2 and abs(delta.y()) <= 2


def test_window_gets_the_guide_and_the_last_scan(harness):
    window = harness()
    window._open_catalog()
    dialog = window._catalog
    assert dialog._show_guide == window.show_guide
    assert dialog._scan is window._scan_result
    assert dialog._root == window._root


def test_window_signals_are_connected(harness, monkeypatch):
    window = harness()
    seen = []
    monkeypatch.setattr(window._log, "log", lambda text, level="info": seen.append((text, level)))
    window._open_catalog()
    dialog = window._catalog
    dialog.log_line.emit("hello from the catalog", "warning")
    assert ("hello from the catalog", "warning") in seen
    generated = []
    monkeypatch.setattr(window, "_on_generate", lambda: generated.append(True) or [])
    dialog.generate_requested.emit()
    assert generated == [True]


# -- the startup check and the count -------------------------------------------------------------


def two_libraries(tmp_path):
    return write_collection(tmp_path / "lib", [entry("SparkFun"), entry("WurthElektronik")])


def test_startup_check_counts_updates(harness):
    harness.h.states_for = lambda root, mf: {
        "SparkFun": state("SparkFun", Check.AVAILABLE, NEWER),
        "WurthElektronik": state("WurthElektronik", Check.AVAILABLE, NEWER),
    }
    window = harness(two_libraries(harness.h.tmp_path))
    harness.settle(window)
    act = window._act_catalog
    assert act.text() == "Library &Catalog... (2 updates)"
    assert act.toolTip() == "2 catalog libraries have updates. Open the catalog to see them."
    assert act.statusTip() == act.toolTip()
    assert catalog_lines(window) == [f"2 catalog libraries have updates: SparkFun, {WURTH.name}"]
    assert len(harness.h.check_calls) == 1
    assert harness.h.check_calls[0].thread != threading.get_ident()


def test_startup_check_singular_forms(harness):
    harness.h.states_for = lambda root, mf: {
        "SparkFun": state("SparkFun", Check.AVAILABLE, NEWER),
        "WurthElektronik": state("WurthElektronik", Check.CURRENT, SHA),
    }
    window = harness(two_libraries(harness.h.tmp_path))
    harness.settle(window)
    act = window._act_catalog
    assert act.text() == "Library &Catalog... (1 update)"
    assert act.toolTip() == "1 catalog library has an update. Open the catalog to see it."
    assert catalog_lines(window) == ["1 catalog library has an update: SparkFun"]


def test_offline_start_is_silent(harness):
    harness.h.states_for = lambda root, mf: {
        "SparkFun": state("SparkFun", Check.UNKNOWN),
        "WurthElektronik": state("WurthElektronik", Check.UNKNOWN),
    }
    window = harness(two_libraries(harness.h.tmp_path))
    harness.settle(window)
    assert len(harness.h.check_calls) == 1
    assert window._act_catalog.text() == PLAIN_TEXT
    assert window._act_catalog.toolTip() == PLAIN_TIP
    assert catalog_lines(window) == []
    assert not any(line.startswith("Could not check") for line in log_lines(window))


def test_up_to_date_start_is_silent(harness):
    harness.h.states_for = lambda root, mf: {
        "SparkFun": state("SparkFun", Check.CURRENT, SHA),
        "WurthElektronik": state("WurthElektronik", Check.CURRENT, SHA),
    }
    window = harness(two_libraries(harness.h.tmp_path))
    harness.settle(window)
    assert window._act_catalog.text() == PLAIN_TEXT
    assert catalog_lines(window) == []


def test_startup_states_reach_an_open_window(harness):
    harness.h.check_gate = threading.Event()
    harness.h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)}
    window = harness(write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")]))
    window._open_catalog()
    dialog = window._catalog
    harness.wait(lambda: harness.h.check_calls)
    assert dialog._external_check
    harness.h.check_gate.set()
    harness.settle(window)
    assert not dialog._external_check
    assert dialog._updates["SparkFun"].check is Check.AVAILABLE


def test_window_opened_later_gets_the_states(harness):
    harness.h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)}
    window = harness(write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")]))
    harness.settle(window)
    window._open_catalog()
    assert window._catalog._updates["SparkFun"].check is Check.AVAILABLE


@pytest.mark.parametrize("case", ["nothing_installed", "folder_missing", "git_missing", "record_unreadable"])
def test_check_not_started_when_nothing_installed_or_git_missing(harness, case):
    root = harness.h.tmp_path / "lib"
    if case == "nothing_installed":
        write_collection(root)
    elif case == "folder_missing":
        write_collection(root, [entry("SparkFun")], folders=[])
    elif case == "git_missing":
        write_collection(root, [entry("SparkFun")])
        harness.h.net = NetStatus(None, None, Issue(Severity.ERROR, "git.not_found", "Git was not found."), None)
    else:
        write_collection(root)
        (root / "catalog.json").write_text("{ not json", encoding="utf-8")
    window = harness(root)
    harness.settle(window)
    QTest.qWait(150)
    assert harness.h.check_calls == []
    if case != "git_missing":
        assert harness.h.net_calls == []
    assert window._act_catalog.text() == PLAIN_TEXT
    assert catalog_lines(window) == []


def test_only_one_check_runs_at_a_time(harness):
    harness.h.check_gate = threading.Event()
    window = harness(write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")]))
    harness.wait(lambda: harness.h.check_calls)
    window._start_catalog_check()
    window._start_catalog_check()
    harness.h.check_gate.set()
    harness.settle(window)
    assert len(harness.h.check_calls) == 1


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_check_writes_nothing(harness):
    harness.h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)}
    root = write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")])
    before_bytes = (root / "catalog.json").read_bytes()
    before = snapshot(root)
    window = harness(root)
    harness.settle(window)
    assert harness.h.check_calls
    assert (root / "catalog.json").read_bytes() == before_bytes
    assert snapshot(root) == before
    assert window._catalog_states["SparkFun"].check is Check.AVAILABLE  # in memory only


def test_switch_cancels_check_and_drops_late_result(harness):
    h = harness.h
    h.check_gate = threading.Event()
    h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)}
    window = harness(write_collection(h.tmp_path / "lib", [entry("SparkFun")]))
    harness.wait(lambda: h.check_calls)
    old_cancel = h.check_calls[0].cancel
    assert not old_cancel.is_set()
    other = write_collection(h.tmp_path / "other", [entry("SparkFun")])
    h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.CURRENT, SHA)}
    assert window._switch_root(other, Source.CHOSEN)
    assert old_cancel.is_set()
    assert window._catalog_states == {}
    assert window._act_catalog.text() == PLAIN_TEXT
    h.check_gate.set()  # the old check answers late with an update; it must change nothing
    harness.wait(lambda: len(h.check_calls) == 2)
    harness.settle(window)
    assert h.check_calls[1].root == other
    assert window._act_catalog.text() == PLAIN_TEXT
    assert catalog_lines(window) == []
    assert window._catalog_states["SparkFun"].check is Check.CURRENT


def test_switch_tells_an_open_window_the_new_folder(harness):
    window = harness()
    window._open_catalog()
    dialog = window._catalog
    other = write_collection(harness.h.tmp_path / "other")
    assert window._switch_root(other, Source.CHOSEN)
    assert dialog._root == other
    assert not dialog._external_check


def test_count_recomputed_on_manual_check_and_job_end(harness):
    root = write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")])
    window = harness(root)
    harness.settle(window)
    window._open_catalog()
    dialog = window._catalog
    dialog.update_states_changed.emit({"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)})
    assert window._act_catalog.text() == "Library &Catalog... (1 update)"
    # an Update installs the newer commit: the same states no longer count
    assert manifest.save(root, Manifest((entry("SparkFun", commit=NEWER),))) is None
    dialog.job_finished.emit(None)
    assert window._act_catalog.text() == PLAIN_TEXT
    assert window._act_catalog.toolTip() == PLAIN_TIP
    # a manual check is not a startup check: no log line from the main window
    assert catalog_lines(window) == []


def test_only_libraries_confirmed_to_have_an_update_count(harness):
    root = write_collection(harness.h.tmp_path / "lib", [entry("SparkFun"), entry("WurthElektronik")])
    window = harness(root)
    harness.settle(window)
    window._catalog_window().update_states_changed.emit({
        "SparkFun": state("SparkFun", Check.UNKNOWN),
        "WurthElektronik": state("WurthElektronik", Check.BRANCH_GONE),
    })
    assert window._act_catalog.text() == PLAIN_TEXT


@pytest.mark.parametrize(
    "count, text",
    [
        (0, "Library &Catalog..."),
        (1, "Library &Catalog... (1 update)"),
        (2, "Library &Catalog... (2 updates)"),
        (12, "Library &Catalog... (12 updates)"),
    ],
)
def test_menu_text_zero_one_many(harness, count, text):
    entries = [entry(f"Lib{n:02d}") for n in range(count)]
    root = write_collection(harness.h.tmp_path / "lib", entries)
    window = harness(root)
    harness.settle(window)
    window._catalog_states = {e.id: state(e.id, Check.AVAILABLE, NEWER) for e in entries}
    window._refresh_catalog_action()
    assert window._act_catalog.text() == text


def test_menu_fits_twelve_updates(harness):
    entries = [entry(f"Lib{n:02d}") for n in range(12)]
    root = write_collection(harness.h.tmp_path / "lib", entries)
    window = harness(root)
    harness.settle(window)
    window._catalog_states = {e.id: state(e.id, Check.AVAILABLE, NEWER) for e in entries}
    window._refresh_catalog_action()
    menu = window._file_menu
    assert menu.minimumWidth() == 350
    menu.ensurePolished()
    menu.resize(menu.sizeHint())
    assert menu.width() >= 350
    geometry = menu.actionGeometry(window._act_catalog)
    assert geometry.width() <= menu.width()
    assert geometry.right() <= menu.width()


def test_no_popup_for_an_update(harness, monkeypatch):
    popups = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: popups.append(self.text()) or 0)
    monkeypatch.setattr(main_window.MainWindow, "_question", lambda *a, **k: popups.append("question"))
    harness.h.states_for = lambda root, mf: {"SparkFun": state("SparkFun", Check.AVAILABLE, NEWER)}
    window = harness(write_collection(harness.h.tmp_path / "lib", [entry("SparkFun")]))
    harness.settle(window)
    assert popups == []
