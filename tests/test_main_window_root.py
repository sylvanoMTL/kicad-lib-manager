"""Offscreen MainWindow tests for the library folder: title, Library folder row, source tag, startup notes.

Own harness (tests do not import from other test modules): the folder, the KiCad config base and the
scan are all replaced before the window exists, so nothing reads or writes the owner's real settings,
KiCad config or live Custom/. Later Phase 15 plans add their window tests to this module and reuse
`make_root_window`.
"""

import json
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest
from collectionfixtures import make_collection, recording_git
from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from kicad_lib_manager import kicad_setup, library_scanner, main_window, settings
from kicad_lib_manager.library_scanner import ConfirmAnswer
from kicad_lib_manager.widgets.theme import AMBER, MUTED
from kicad_lib_manager.collection import PATH_LENGTH_WARNING, Source, check_folder, create_collection
from kicad_lib_manager.models import Issue, ScanResult, Severity, SymbolLibrary
from kicad_lib_manager.table_generator import write_tables
from kicad_lib_manager.widgets.log_panel import COLORS


@pytest.fixture
def make_root_window(qtbot, monkeypatch, tmp_path):
    config_base = tmp_path / "kicad_cfg"
    config_base.mkdir()
    fp_dir = tmp_path / "kicad_fp"
    fp_dir.mkdir()
    calls = []
    checks = []  # (folder, thread id) of every folder check

    def fake_scan(root, progress=None, kicad_fp_dir=None, *, skip=None, checking=None, model_vars=None, prefixes=None):
        calls.append(Path(root))
        if make.gate is not None:
            make.gate.wait(10)
        outcome = make.result_for(Path(root))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def fake_check(path, *, current=None):
        checks.append((Path(path), threading.get_ident()))
        gate = make.check_gates.get(str(path))
        if gate is not None:
            gate.wait(10)
        return check_folder(path, current=current)

    monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
    monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
    monkeypatch.setattr(main_window, "scan_all", fake_scan)
    monkeypatch.setattr(main_window, "check_folder", fake_check)
    # The path-variable sync reads and writes the same tmp KiCad tree the window's predicate reads
    def fake_sync(repo_root, **kwargs):
        kwargs.setdefault("running", lambda: [])
        return library_scanner.sync_kicad_path_vars(
            repo_root, **kwargs, config_base=config_base, backup_root=tmp_path / "backups"
        )

    questions = []  # (title, text) of every "Change KiCad path variables?" question
    kicad_open = []  # (changes, names) of every KiCad-open question

    def fake_question(self, title, text, buttons, default):
        questions.append((title, text))
        return make.answer

    def fake_ask_kicad_open(self, changes, names):
        kicad_open.append((list(changes), list(names)))
        return make.kicad_answer

    monkeypatch.setattr(main_window, "sync_kicad_path_vars", fake_sync)
    monkeypatch.setattr(main_window, "kicad_running", lambda: list(make.running))
    monkeypatch.setattr(main_window.MainWindow, "_question", fake_question)
    monkeypatch.setattr(main_window.MainWindow, "_ask_kicad_open", fake_ask_kicad_open)

    def make(root=None, source=Source.CHOSEN, notes=(), wait=True, switched=False):
        if root is None:
            root = make_collection(tmp_path / "lib")
        window = main_window.MainWindow(root, source, startup_notes=notes, switched=switched)
        qtbot.addWidget(window)
        if wait:
            qtbot.waitUntil(lambda: window._worker is None, timeout=30000)
        return window

    make.questions = questions
    make.kicad_open = kicad_open
    make.answer = QMessageBox.StandardButton.No
    make.kicad_answer = ConfirmAnswer.DECLINE
    make.running = []  # the KiCad programs the open check finds
    make.scan_calls = calls
    make.config_base = config_base
    make.checks = checks
    make.tmp_path = tmp_path
    # A scan waits on make.gate while it is set; a folder check waits on make.check_gates[str(path)]
    make.gate = None
    make.check_gates = {}
    # The scan result (or the exception to raise) for a folder; fresh objects on every call
    make.result_for = lambda root: ScanResult()
    return make


def log_lines(window) -> list[str]:
    """The text of every log line, oldest first, without its time stamp."""
    return [line.split("] ", 1)[-1] for line in window._log._text.toPlainText().splitlines()]


def test_title_and_row_show_the_folder(make_root_window):
    root = make_collection(make_root_window.tmp_path / "My Parts")
    window = make_root_window(root)
    assert window.windowTitle() == "My Parts - KiCad External Lib Manager"
    assert window._root_path.full_text() == str(root)
    assert window._root_path.toolTip() == str(root)
    assert window._root_path.accessibleName() == "Library folder"
    assert make_root_window.scan_calls == [root]
    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "Library folder:" in labels


@pytest.mark.parametrize("source", list(Source))
def test_row_tag_names_the_source(make_root_window, source):
    window = make_root_window(source=source)
    assert window._root_tag.text() == source.value


def test_folder_with_ampersand_is_shown_as_typed(make_root_window):
    root = make_collection(make_root_window.tmp_path / "R&D Parts")
    window = make_root_window(root)
    assert window.windowTitle().startswith("R&D Parts - ")
    assert window._root_path.full_text().endswith("R&D Parts")
    # Plain text: an ampersand is no mnemonic
    assert "R&D Parts" in window._root_path.text() or "…" in window._root_path.text()


def test_long_path_is_elided_not_widening(make_root_window):
    short = make_root_window()
    width_before = short.minimumSizeHint().width()
    root = make_root_window.tmp_path / ("deep" * 50)
    make_collection(root)
    long_root = root
    window = make_root_window(long_root)
    assert len(str(long_root)) > 150
    assert window._root_path.full_text() == str(long_root)
    assert window._root_path.toolTip() == str(long_root)
    assert window.minimumSizeHint().width() <= max(width_before, 1) + 50


def test_held_notes_are_logged_first_in_order(make_root_window):
    notes = [
        Issue(Severity.WARNING, "library.kicad_skipped", "first note"),
        Issue(Severity.WARNING, "library.chosen_skipped", "second note"),
    ]
    window = make_root_window(notes=notes)
    lines = log_lines(window)
    assert lines[0] == "first note"
    assert lines[1] == "second note"
    assert lines[2].startswith("Library folder: ")


def test_library_folder_info_line(make_root_window):
    root = make_collection(make_root_window.tmp_path / "lib")
    window = make_root_window(root, Source.CLI)
    assert f"Library folder: {root} (set by --library-root)" in log_lines(window)


def test_length_warning_logged_over_threshold(make_root_window, monkeypatch):
    root = make_collection(make_root_window.tmp_path / ("x" * 120))
    window = make_root_window(root)
    n = len(str(root))
    assert n > PATH_LENGTH_WARNING
    assert (
        f"The library folder path is {n} characters long. Long paths can break KiCad and git on Windows."
    ) in log_lines(window)
    assert COLORS["warning"].lower() in window._log._text.toHtml().lower()
    # At or under the limit: no warning (the limit is lifted, a tmp_path can be long already)
    monkeypatch.setattr(main_window, "PATH_LENGTH_WARNING", len(str(root)))
    short = make_root_window(make_collection(make_root_window.tmp_path / "s"))
    assert not [line for line in log_lines(short) if "characters long" in line]


# -- Plan 15-07 Task 1: _switch_root, the busy guard and the Recent Library Folders submenu --------------


def other_collection(make, name):
    return make_collection(make.tmp_path / name)


def settle_scan(qtbot, window):
    qtbot.waitUntil(lambda: window._worker is None, timeout=30000)


def settle_checks(qtbot, window):
    qtbot.waitUntil(lambda: all(task.is_done() for task in window._root_checks), timeout=30000)
    qtbot.wait(30)


def file_menu(window):
    return window.menuBar().actions()[0].menu()


def test_switch_rescans_new_folder(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert make_root_window.scan_calls == [a, b]
    assert make_root_window.checks[-1][0] == b
    assert make_root_window.checks[-1][1] != threading.get_ident()
    assert window._source is Source.CHOSEN
    assert window.windowTitle() == "b - KiCad External Lib Manager"
    assert window._root_path.full_text() == str(b)
    assert window._root_tag.text() == Source.CHOSEN.value
    assert settings.load_library_root() == b
    assert settings.load_library_recent()[0] == str(b)
    assert f"Library folder: {b} (your choice)" in log_lines(window)


def test_switch_blanks_the_trees_until_the_scan_ends(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    make_root_window.result_for = lambda root: ScanResult(
        symbol_libs=[SymbolLibrary("X", "Custom/Symbols/X.kicad_sym", "Custom")]
    )
    window = make_root_window(a)
    assert window._tree._sym_tree.topLevelItemCount() > 0
    make_root_window.gate = threading.Event()
    try:
        assert window._switch_root(b, Source.CHOSEN) is True
        # at once: the row and the title show the new folder, both trees are blank
        assert window._root_path.full_text() == str(b)
        assert window.windowTitle().startswith("b - ")
        assert window._tree._sym_tree.topLevelItemCount() == 0
        assert window._scan_result is None
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._tree._sym_tree.topLevelItemCount() > 0


def test_switch_starts_fresh_selection(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    dest = make_root_window.tmp_path / "dest"
    dest.mkdir()

    def result(root):
        return ScanResult(symbol_libs=[
            SymbolLibrary("Listed", "Custom/Symbols/Listed.kicad_sym", "Custom"),
            SymbolLibrary("Other", "Custom/Symbols/Other.kicad_sym", "Custom"),
        ])

    make_root_window.result_for = result
    write_tables(dest, [SymbolLibrary("Listed", "Custom/Symbols/Listed.kicad_sym", "Custom", selected=True)], [])
    window = make_root_window(a)
    window._use_destination(str(dest))
    for lib in window._scan_result.symbol_libs:
        lib.selected = True
    before = len(log_lines(window))

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    chosen = {lib.nickname: lib.selected for lib in window._scan_result.symbol_libs}
    assert chosen == {"Listed": True, "Other": False}
    assert not [line for line in log_lines(window)[before:] if line.startswith("Kept ")]
    assert any(line.startswith("Pre-selected 1 symbol") for line in log_lines(window)[before:])


def switch_to(qtbot, window, folder, source=Source.CHOSEN):
    window._request_switch(folder, source)
    qtbot.waitUntil(lambda: window._root == folder and window._worker is None, timeout=30000)


def test_destination_follows_a_switch_from_the_old_folder(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    settings.add_dest_to_history(str(a))
    window = make_root_window(a)
    assert window._dest_combo.currentText() == str(a)

    switch_to(qtbot, window, b)

    assert window._dest_combo.currentText() == str(b)
    assert settings.load_dest_history()[0] == str(b)
    assert settings.load_dest_history()[1:] == [str(a)]


def test_destination_follows_a_switch_with_an_empty_history(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    assert settings.load_dest_history() == []
    assert window._dest_combo.currentText() == str(a)

    switch_to(qtbot, window, b)

    assert window._dest_combo.currentText() == str(b)
    assert settings.load_dest_history() == [str(b)]


def test_destination_follows_a_switch_from_a_blank_box(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._dest_combo.setEditText("   ")

    switch_to(qtbot, window, b)

    assert window._dest_combo.currentText() == str(b)
    assert settings.load_dest_history()[0] == str(b)


def test_a_switch_does_not_stat_a_dead_history_entry_on_the_gui_thread(qtbot, make_root_window, monkeypatch):
    """Code review WR-08: a Destination history entry on a dead drive must not stall the switch."""
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    dead = other_collection(make_root_window, "dead")
    gone = other_collection(make_root_window, "gone")
    for entry in (dead, gone, a):  # newest first: a, gone, dead
        settings.add_dest_to_history(str(entry))
    shutil.rmtree(gone)
    window = make_root_window(a)
    assert window._dest_combo.currentText() == str(a)
    gui = threading.get_ident()
    gate = threading.Event()
    seen = []  # (folder name, on the GUI thread)
    real_is_dir = Path.is_dir

    def is_dir(self):
        if self.name in ("dead", "gone"):
            seen.append((self.name, threading.get_ident() == gui))
            gate.wait(10)  # a disconnected drive: the answer takes a long time
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    try:
        started = time.monotonic()
        assert window._switch_root(b, Source.CHOSEN) is True
        assert time.monotonic() - started < 2.0
        # Shown at once from the saved history; nothing is known to be gone yet
        assert window._dest_combo.currentText() == str(b)
        assert [window._dest_combo.itemText(i) for i in range(window._dest_combo.count())][:2] == [str(b), str(a)]
        qtbot.waitUntil(lambda: bool(seen), timeout=30000)
    finally:
        gate.set()
    # The gone entry is dropped once the worker has answered
    qtbot.waitUntil(
        lambda: [window._dest_combo.itemText(i) for i in range(window._dest_combo.count())]
        == [str(b), str(a), str(dead)],
        timeout=30000,
    )
    assert seen and not any(on_gui for _name, on_gui in seen)
    assert window._dest_combo.currentText() == str(b)
    qtbot.waitUntil(lambda: window._worker is None, timeout=30000)


def test_destination_elsewhere_stays_on_a_switch(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    project = make_root_window.tmp_path / "project"
    project.mkdir()
    settings.add_dest_to_history(str(project))
    window = make_root_window(a)
    assert window._dest_combo.currentText() == str(project)
    history = settings.load_dest_history()

    switch_to(qtbot, window, b)

    assert window._dest_combo.currentText() == str(project)
    assert settings.load_dest_history() == history


def test_destination_follows_use_kicads_folder(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    settings.add_dest_to_history(str(a))
    window = make_root_window(a)

    switch_to(qtbot, window, b, Source.KICAD)

    assert window._source is Source.KICAD
    assert window._dest_combo.currentText() == str(b)
    assert settings.load_dest_history()[0] == str(b)


def test_refused_switch_leaves_the_destination(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    settings.add_dest_to_history(str(a))
    window = make_root_window(a)
    history = settings.load_dest_history()
    window._import_dialog = object()
    try:
        window._request_switch(b, Source.CHOSEN)
        qtbot.wait(50)
        assert window._switch_root(b, Source.CHOSEN) is False
    finally:
        window._import_dialog = None
    assert window._root == a
    assert window._dest_combo.currentText() == str(a)
    assert settings.load_dest_history() == history


def test_followed_destination_is_used_for_preselection(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    make_root_window.result_for = lambda root: ScanResult(symbol_libs=[
        SymbolLibrary("Listed", "Custom/Symbols/Listed.kicad_sym", "Custom"),
        SymbolLibrary("Other", "Custom/Symbols/Other.kicad_sym", "Custom"),
    ])
    write_tables(b, [SymbolLibrary("Listed", "Custom/Symbols/Listed.kicad_sym", "Custom", selected=True)], [])
    window = make_root_window(a)

    switch_to(qtbot, window, b)

    assert window._dest_combo.currentText() == str(b)
    chosen = {lib.nickname: lib.selected for lib in window._scan_result.symbol_libs}
    assert chosen == {"Listed": True, "Other": False}


_BUSY_IMPORT_TEXT = (
    "The library folder cannot change while an import is open. Finish or close the import window first."
)
_BUSY_MIGRATION_TEXT = (
    "The library folder cannot change while the migration window is open. Close the migration window, then try again."
)
_BUSY_KICAD_TEXT = (
    "The library folder cannot change while KiCad's settings are being checked. Try again in a moment."
)
BUSY_TEXTS = {
    "scan": "The library folder cannot change while a scan is running. Try again when it ends.",
    "import": _BUSY_IMPORT_TEXT,
    "post_install": _BUSY_IMPORT_TEXT,
    "migration": _BUSY_MIGRATION_TEXT,
    "pending_migration": _BUSY_MIGRATION_TEXT,
    "path_var": _BUSY_KICAD_TEXT,
    "chooser": _BUSY_KICAD_TEXT,
    "atomic": "The library folder cannot change while Check Atomic Parts is open. Close that window first.",
}


@pytest.mark.parametrize("state", list(BUSY_TEXTS))
def test_switch_refused_while_busy(qtbot, make_root_window, state):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    recent_before = settings.load_library_recent()
    text = BUSY_TEXTS[state]
    if state == "scan":
        make_root_window.gate = threading.Event()
        window = make_root_window(a, wait=False)
        qtbot.waitUntil(lambda: len(make_root_window.scan_calls) == 1, timeout=30000)
    else:
        window = make_root_window(a)
    flags = {
        "import": ("_import_dialog", object(), None),
        "post_install": ("_pending_post_install", object(), None),
        "migration": ("_migration_dialog", object(), None),
        "pending_migration": ("_pending_migration", True, False),
        "path_var": ("_path_var_busy", True, False),
        "chooser": ("_chooser_busy", True, False),
        "atomic": ("_atomic_dialog", object(), None),
    }
    reset = None
    try:
        if state != "scan":
            name, value, rest = flags[state]
            setattr(window, name, value)
            reset = (name, rest)
        calls_before = len(make_root_window.scan_calls)

        window._request_switch(b, Source.CHOSEN)
        qtbot.wait(50)
        assert [line for line in log_lines(window) if line == text] == [text]
        assert window.statusBar().currentMessage() == text
        assert COLORS["warning"].lower() in window._log._text.toHtml().lower()
        assert window._root == a and window._source is Source.CHOSEN
        assert settings.load_library_root() is None
        assert settings.load_library_recent() == recent_before
        assert len(make_root_window.scan_calls) == calls_before

        # a result that arrives later meets the same guard
        assert window._switch_root(b, Source.CHOSEN) is False
        assert [line for line in log_lines(window) if line == text] == [text, text]
        assert window._root == a
        assert settings.load_library_root() is None
        assert settings.load_library_recent() == recent_before
    finally:
        if make_root_window.gate is not None:
            make_root_window.gate.set()
        if reset is not None:
            setattr(window, reset[0], reset[1])
    settle_scan(qtbot, window)


def test_one_click_failure_changes_nothing(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    gone = make_root_window.tmp_path / "gone"
    text = f"Not using {gone}: This folder does not exist. Choose another folder."

    window._request_switch(gone, Source.CHOSEN)
    qtbot.waitUntil(lambda: text in log_lines(window), timeout=30000)

    assert window.statusBar().currentMessage() == text
    assert COLORS["error"].lower() in window._log._text.toHtml().lower()
    assert window._root == a
    assert settings.load_library_root() is None
    assert settings.load_library_recent() == []
    assert make_root_window.scan_calls == [a]


def test_same_folder_only_says_so(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    (a / "sub").mkdir()
    window = make_root_window(a)

    window._request_switch(Path(str(a) + "/sub/.."), Source.CHOSEN)
    qtbot.wait(50)

    assert window.statusBar().currentMessage() == "You are already using this library folder."
    assert make_root_window.scan_calls == [a]
    assert make_root_window.checks == []
    assert settings.load_library_root() is None


def test_stale_check_result_is_ignored(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    c = other_collection(make_root_window, "c")
    window = make_root_window(a)
    slow = threading.Event()
    make_root_window.check_gates[str(b)] = slow
    try:
        window._request_switch(b, Source.CHOSEN)
        window._request_switch(c, Source.CHOSEN)
        qtbot.waitUntil(lambda: window._root == c and window._worker is None, timeout=30000)
    finally:
        slow.set()
    settle_checks(qtbot, window)
    settle_scan(qtbot, window)

    assert window._root == c
    assert b not in make_root_window.scan_calls
    assert settings.load_library_root() == c
    assert not [line for line in log_lines(window) if line.startswith(f"Library folder: {b}")]


def test_scan_error_keeps_new_folder(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    make_root_window.result_for = lambda root: RuntimeError("disk gone")

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert window._root_path.full_text() == str(b)
    assert window._tree._sym_tree.topLevelItemCount() == 0
    assert "Scan error: disk gone" in log_lines(window)


def test_switch_deletes_nothing(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    settings.add_library_recent(a)
    cache_a = settings.scan_cache_file(a)
    cache_a.parent.mkdir(parents=True, exist_ok=True)
    cache_a.write_text("saved scan of a", encoding="utf-8")

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert cache_a.read_text(encoding="utf-8") == "saved scan of a"
    assert str(a) in settings.load_library_recent()
    assert a.is_dir()


def saved_recent(make, count, gone=()):
    """count tmp folders recent01.., newest first, saved as the recent list; the numbers in gone are deleted."""
    folders = [make_collection(make.tmp_path / f"recent{n:02d}") for n in range(1, count + 1)]
    settings.get_settings().setValue("library/recent", [str(f) for f in folders])
    for n in gone:
        shutil.rmtree(folders[n - 1])
    return folders


@pytest.mark.parametrize("saved, gone, shown", [(12, (3, 5), 10), (13, (3, 5), 10), (4, (), 4)])
def test_recent_menu_entries(qtbot, make_root_window, saved, gone, shown):
    folders = saved_recent(make_root_window, saved, gone)
    window = make_root_window(folders[0])
    existing = [f for n, f in enumerate(folders, 1) if n not in gone][:shown]
    saved_before = settings.load_library_recent()

    window._rebuild_recent_menu()
    # Existence is checked on a worker: the entries that are gone drop out when its answer arrives
    qtbot.waitUntil(lambda: [a.data() for a in window._recent_menu.actions()] == [str(f) for f in existing], timeout=30000)
    actions = window._recent_menu.actions()

    assert [a.data() for a in actions] == [str(f) for f in existing]
    assert [a.toolTip() for a in actions] == [str(f) for f in existing]
    assert [a.statusTip() for a in actions] == [str(f) for f in existing]
    prefixes = [a.text().split(" ", 1)[0] for a in actions]
    assert prefixes == ["&1", "&2", "&3", "&4", "&5", "&6", "&7", "&8", "&9", "10"][:shown]
    assert [a.isChecked() for a in actions] == [True] + [False] * (shown - 1)
    assert settings.load_library_recent() == saved_before


def test_recent_menu_text_is_escaped_and_elided(make_root_window):
    amp = make_collection(make_root_window.tmp_path / "R&D Parts")
    long = make_collection(make_root_window.tmp_path / ("n" * 150))
    settings.get_settings().setValue("library/recent", [str(amp), str(long)])
    window = make_root_window(amp)

    window._rebuild_recent_menu()
    first, second = window._recent_menu.actions()

    assert "R&&D Parts" in first.text()
    assert first.data() == str(amp)
    shown = second.text().split(" ", 1)[1]
    assert len(shown) <= 64
    assert "..." in shown and shown.startswith(str(long)[:5]) and shown.endswith("n" * 5)
    assert second.statusTip() == str(long)


def test_elide_middle():
    assert main_window._elide_middle("short", 64) == "short"
    text = "x" * 30 + "y" * 100 + "z" * 30
    out = main_window._elide_middle(text, 64)
    assert len(out) == 64 and "..." in out
    assert out.startswith("x") and out.endswith("z")


def test_recent_menu_rebuilt_on_show(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    assert window._recent_menu.actions() == []
    added = other_collection(make_root_window, "added")
    settings.add_library_recent(added)

    file_menu(window).aboutToShow.emit()
    assert [x.data() for x in window._recent_menu.actions()] == [str(added)]

    qtbot.waitUntil(lambda: window._recent_check.is_done(), timeout=30000)
    qtbot.wait(30)
    shutil.rmtree(added)
    file_menu(window).aboutToShow.emit()
    qtbot.waitUntil(lambda: window._recent_menu.actions() == [], timeout=30000)


def test_recent_menu_disabled_when_empty_or_busy(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    assert window._recent_menu.menuAction().isEnabled() is False
    assert window._recent_menu.menuAction().statusTip() == "Switch to a collection you used before"

    b = other_collection(make_root_window, "b")
    settings.add_library_recent(b)
    file_menu(window).aboutToShow.emit()
    assert window._recent_menu.menuAction().isEnabled() is True

    make_root_window.gate = threading.Event()
    try:
        window._on_rescan()
        assert window._recent_menu.menuAction().isEnabled() is False
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._recent_menu.menuAction().isEnabled() is True


def test_recent_entry_current_is_noop(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    settings.add_library_recent(a)
    window = make_root_window(a)
    window._rebuild_recent_menu()
    action = window._recent_menu.actions()[0]
    assert action.isChecked()

    action.trigger()
    qtbot.wait(50)

    assert window.statusBar().currentMessage() == "You are already using this library folder."
    assert make_root_window.scan_calls == [a]
    assert make_root_window.checks == []


def test_recent_entry_switches(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    settings.add_library_recent(b)
    window = make_root_window(a)
    window._rebuild_recent_menu()

    window._recent_menu.actions()[0].trigger()
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert window._source is Source.CHOSEN
    assert settings.load_library_root() == b


# -- Plan 15-07 Task 2: Use KiCad's Folder, Open Library Folder in Explorer, the amber tag ---------------


def write_kicad_common(config_base, github=None, models=None, version="10.0"):
    """A KiCad config the window reads: KICAD_LIB_GITHUB (and CUSTOM_3DMODEL_DIR) as given, else vars null."""
    folder = config_base / version
    folder.mkdir(parents=True, exist_ok=True)
    values = {}
    if github is not None:
        values["KICAD_LIB_GITHUB"] = str(github)
    if models is not None:
        values["CUSTOM_3DMODEL_DIR"] = str(models)
    path = folder / "kicad_common.json"
    path.write_text(json.dumps({"environment": {"vars": values or None}}, indent=2) + "\n", encoding="utf-8")
    return path


KICAD_UNSET_TIP = "KiCad has no library folder set (KICAD_LIB_GITHUB). Set it in KiCad Preferences > Configure Paths."


def test_use_kicads_folder_unset(make_root_window):
    window = make_root_window(other_collection(make_root_window, "a"))
    assert window._act_use_kicad.isEnabled() is False
    assert window._act_use_kicad.statusTip() == KICAD_UNSET_TIP


def test_use_kicads_folder_unset_in_config(make_root_window):
    write_kicad_common(make_root_window.config_base, github=None)
    window = make_root_window(other_collection(make_root_window, "a"))
    assert window._act_use_kicad.isEnabled() is False
    assert window._act_use_kicad.statusTip() == KICAD_UNSET_TIP


def test_use_kicads_folder_is_the_current_folder(make_root_window):
    a = other_collection(make_root_window, "a")
    (a / "sub").mkdir()
    write_kicad_common(make_root_window.config_base, github=str(a) + "/sub/..")
    window = make_root_window(a)
    assert window._act_use_kicad.isEnabled() is False
    assert window._act_use_kicad.statusTip() == "You are already using KiCad's folder."


def test_use_kicads_folder_other_collection(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    write_kicad_common(make_root_window.config_base, github=b)
    window = make_root_window(a)
    assert window._act_use_kicad.isEnabled() is True
    assert window._act_use_kicad.statusTip() == f"Switch to the library folder KiCad reads: {b}"

    make_root_window.gate = threading.Event()
    try:
        window._on_rescan()
        assert window._act_use_kicad.isEnabled() is False
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._act_use_kicad.isEnabled() is True


def test_use_kicads_folder_switches_and_forgets_choice(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    settings.save_library_root(a)
    write_kicad_common(make_root_window.config_base, github=b)
    window = make_root_window(a)

    window._act_use_kicad.trigger()
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert window._source is Source.KICAD
    assert window._root_tag.text() == "KiCad's folder"
    assert settings.load_library_root() is None
    assert make_root_window.scan_calls == [a, b]
    # it is the current folder now
    assert window._act_use_kicad.isEnabled() is False
    assert window._act_use_kicad.statusTip() == "You are already using KiCad's folder."


def test_use_kicads_folder_that_is_gone_changes_nothing(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    gone = make_root_window.tmp_path / "gone"
    write_kicad_common(make_root_window.config_base, github=gone)
    window = make_root_window(a)

    window._act_use_kicad.trigger()
    qtbot.waitUntil(
        lambda: any(line.startswith(f"Not using {gone}:") for line in log_lines(window)), timeout=30000
    )

    assert window._root == a
    assert make_root_window.scan_calls == [a]


@pytest.fixture
def opened(monkeypatch):
    """Replace QDesktopServices.openUrl: records the local paths, answers with opened[0]."""
    urls = []
    answer = [True]

    def fake_open(url):
        urls.append(url.toLocalFile())
        return answer[0]

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(fake_open))
    fake_open.urls = urls
    fake_open.answer = answer
    return fake_open


def test_open_folder_calls_desktop_services(qtbot, make_root_window, opened):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    if sys.platform == "win32":
        assert window._act_open_folder.text() == "S&how Library Folder in Explorer"
        assert window._act_open_folder.statusTip() == f"Open {a} in Explorer"
    else:
        assert window._act_open_folder.text() == "S&how Library Folder in File Manager"
        assert window._act_open_folder.statusTip() == f"Open {a} in the file manager"

    window._act_open_folder.trigger()
    assert opened.urls == [QUrl.fromLocalFile(str(a)).toLocalFile()]

    # read-only: it stays enabled while a scan runs
    make_root_window.gate = threading.Event()
    try:
        window._on_rescan()
        assert window._act_open_folder.isEnabled() is True
        window._act_open_folder.trigger()
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert len(opened.urls) == 2


def test_open_folder_deleted_logs_error(make_root_window, opened):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    shutil.rmtree(a)

    window._act_open_folder.trigger()

    assert opened.urls == []
    text = f"Cannot open {a}: the folder no longer exists. Choose another library folder."
    assert text in log_lines(window)
    assert COLORS["error"].lower() in window._log._text.toHtml().lower()


def test_open_folder_failure_logs_warning(make_root_window, opened):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    opened.answer[0] = False

    window._act_open_folder.trigger()

    text = f"Could not open {a} in Explorer. Check that a file manager is installed, then try again."
    assert text in log_lines(window)
    assert COLORS["warning"].lower() in window._log._text.toHtml().lower()


def test_tag_amber_when_kicad_reads_another_folder(make_root_window):
    a = other_collection(make_root_window, "a")
    elsewhere = make_root_window.tmp_path / "elsewhere"
    write_kicad_common(make_root_window.config_base, github=elsewhere)
    window = make_root_window(a)

    assert window._root_tag.text() == "⚠ KiCad reads a different folder"
    assert AMBER in window._root_tag.styleSheet()
    assert window._root_tag.toolTip() == f"KiCad reads {str(elsewhere).replace(chr(92), '/')}."
    assert window._root_tag.textFormat().name == "PlainText"


def test_tag_is_plain_when_nothing_to_compare(make_root_window):
    # no KiCad config at all
    window = make_root_window(other_collection(make_root_window, "a"))
    assert window._root_tag.text() == Source.CHOSEN.value
    assert MUTED in window._root_tag.styleSheet() and AMBER not in window._root_tag.styleSheet()
    assert window._root_tag.toolTip() == ""
    assert not [line for line in log_lines(window) if "KiCad reads its libraries from" in line]

    # a config whose KICAD_LIB_GITHUB is unset
    write_kicad_common(make_root_window.config_base, github=None)
    other = make_root_window(other_collection(make_root_window, "b"))
    assert other._root_tag.text() == Source.CHOSEN.value
    assert not [line for line in log_lines(other) if "KiCad reads its libraries from" in line]


def test_tag_follows_a_switch(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    write_kicad_common(make_root_window.config_base, github=b)
    window = make_root_window(a)
    assert window._root_tag.text() == "⚠ KiCad reads a different folder"

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert window._root_tag.text() == Source.CHOSEN.value
    assert window._root_tag.toolTip() == ""


def test_start_logs_the_wrong_folder_warning_once(make_root_window):
    a = other_collection(make_root_window, "a")
    write_kicad_common(make_root_window.config_base, github=make_root_window.tmp_path / "elsewhere")
    window = make_root_window(a)

    mismatch = kicad_setup.checkout_mismatch(a, config_base=make_root_window.config_base)
    expected = kicad_setup.wrong_checkout_warning(mismatch)
    assert log_lines(window).count(expected) == 1
    assert COLORS["warning"].lower() in window._log._text.toHtml().lower()


def test_menu_order(make_root_window):
    window = make_root_window(other_collection(make_root_window, "a"))
    actions = file_menu(window).actions()

    assert actions[0] is window._act_new_collection
    assert actions[1] is window._act_choose_folder
    assert actions[2] is window._act_use_kicad
    assert actions[3] is window._recent_menu.menuAction()
    assert actions[4] is window._act_open_folder
    assert actions[5].isSeparator()
    assert actions[6] is window._act_import
    for action in actions[:5]:
        assert action.shortcut().isEmpty()
    mnemonics = [a.text().split("&", 1)[1][0] for a in actions[:5]]
    assert mnemonics == ["N", "O", "K", "L", "h"]


# -- Plan 15-07 Task 3: the KiCad path-variable offer after a switch -------------------------------------

DECLINED = "KiCad still points at {}. Generate Tables and Install Part will offer the change again."
DECLINED_UNSET = "KiCad's KICAD_LIB_GITHUB is not set. Generate Tables and Install Part will offer the change again."


def common_path(make):
    return make.config_base / "10.0" / "kicad_common.json"


def config_vars(make):
    return json.loads(common_path(make).read_text(encoding="utf-8"))["environment"]["vars"]


def settle_offer(qtbot, window):
    """The scan has ended and the off-thread KiCad-open check and the question are done."""
    qtbot.waitUntil(lambda: window._worker is None and not window._path_var_busy, timeout=30000)
    qtbot.wait(50)
    qtbot.waitUntil(lambda: not window._path_var_busy, timeout=30000)


def test_offer_after_switch_when_values_differ(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    path = write_kicad_common(make_root_window.config_base, github=None)
    window = make_root_window(a)
    assert make_root_window.questions == []  # a plain start asks nothing
    before = path.read_bytes()

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b, timeout=30000)
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)

    (title, text), = make_root_window.questions
    assert title == "Change KiCad path variables?"
    assert f"KICAD_LIB_GITHUB: (not set) -> {str(b).replace(chr(92), '/')}" in text
    assert "CUSTOM_3DMODEL_DIR: (not set) -> " in text
    assert path.read_bytes() == before
    assert DECLINED_UNSET in log_lines(window)
    assert not [line for line in log_lines(window) if "(not set)" in line and "still points" in line]


def test_declined_offer_names_the_folder_kicad_still_points_at(qtbot, make_root_window):
    """UAT-COS-01: with the variable set, the line keeps its set-variable wording."""
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    elsewhere = make_root_window.tmp_path / "elsewhere"
    write_kicad_common(make_root_window.config_base, github=elsewhere, models=elsewhere / "m")
    window = make_root_window(a)

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b, timeout=30000)
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)

    assert DECLINED.format(elsewhere) in log_lines(window)
    assert DECLINED_UNSET not in log_lines(window)


def test_offer_yes_writes_both_variables_and_clears_the_amber_tag(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    elsewhere = make_root_window.tmp_path / "elsewhere"
    write_kicad_common(make_root_window.config_base, github=elsewhere, models=elsewhere / "m")
    make_root_window.answer = QMessageBox.StandardButton.Yes
    window = make_root_window(a)
    assert window._root_tag.text() == "⚠ KiCad reads a different folder"

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b, timeout=30000)
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)

    desired = library_scanner._desired_path_vars(b)
    assert config_vars(make_root_window) == desired
    assert window._root_tag.text() == Source.CHOSEN.value
    assert not [line for line in log_lines(window) if line.startswith("KiCad still points at")]


def test_no_offer_when_values_match(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    desired = library_scanner._desired_path_vars(b)
    write_kicad_common(
        make_root_window.config_base, github=desired["KICAD_LIB_GITHUB"], models=desired["CUSTOM_3DMODEL_DIR"]
    )
    window = make_root_window(a)

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    settle_offer(qtbot, window)

    assert make_root_window.questions == []
    assert not [line for line in log_lines(window) if "already set correctly" in line]
    assert not [line for line in log_lines(window) if line.startswith("KiCad still points at")]


def test_no_offer_after_use_kicads_folder(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    # KICAD_LIB_GITHUB names b but CUSTOM_3DMODEL_DIR differs: the predicate would say yes
    write_kicad_common(make_root_window.config_base, github=b, models=make_root_window.tmp_path / "m")
    window = make_root_window(a)

    window._act_use_kicad.trigger()
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    settle_offer(qtbot, window)

    assert make_root_window.questions == []
    assert make_root_window.kicad_open == []


def test_no_offer_at_plain_start(qtbot, make_root_window):
    write_kicad_common(make_root_window.config_base, github=None)
    window = make_root_window(other_collection(make_root_window, "a"))
    settle_offer(qtbot, window)
    assert make_root_window.questions == []
    assert make_root_window.kicad_open == []


def test_no_offer_while_scanning(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    write_kicad_common(make_root_window.config_base, github=None)
    window = make_root_window(a)
    make_root_window.gate = threading.Event()
    try:
        assert window._switch_root(b, Source.CHOSEN) is True
        qtbot.waitUntil(lambda: b in make_root_window.scan_calls, timeout=30000)
        qtbot.wait(100)
        assert make_root_window.questions == []
    finally:
        make_root_window.gate.set()
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)


def test_switched_start_offers_after_first_scan(qtbot, make_root_window):
    b = other_collection(make_root_window, "b")
    write_kicad_common(make_root_window.config_base, github=None)

    window = make_root_window(b, Source.CHOSEN, switched=True)
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)

    assert len(make_root_window.questions) == 1
    assert DECLINED_UNSET in log_lines(window)
    assert not [line for line in log_lines(window) if "(not set)" in line and "still points" in line]


def test_offer_with_kicad_open_uses_the_three_button_variant(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    path = write_kicad_common(make_root_window.config_base, github=None)
    make_root_window.running = ["kicad"]
    window = make_root_window(a)
    before = path.read_bytes()

    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b, timeout=30000)
    qtbot.waitUntil(lambda: len(make_root_window.kicad_open) == 1, timeout=30000)
    settle_offer(qtbot, window)

    changes, names = make_root_window.kicad_open[0]
    assert names == ["kicad"]
    assert [c[0] for c in changes] == ["KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR"]
    assert make_root_window.questions == []
    assert path.read_bytes() == before
    assert DECLINED_UNSET in log_lines(window)
    assert not [line for line in log_lines(window) if "(not set)" in line and "still points" in line]


def test_generate_still_offers_after_a_declined_offer(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    make_root_window.result_for = lambda root: ScanResult(
        symbol_libs=[SymbolLibrary("X", "Custom/Symbols/X.kicad_sym", "Custom", selected=True)]
    )
    write_kicad_common(make_root_window.config_base, github=None)
    window = make_root_window(a)
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b, timeout=30000)
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 1, timeout=30000)
    settle_offer(qtbot, window)

    window._on_generate()
    qtbot.waitUntil(lambda: len(make_root_window.questions) == 2, timeout=30000)
    settle_offer(qtbot, window)

    # the decline line belongs to the switch offer only, not to Generate Tables
    assert log_lines(window).count(DECLINED_UNSET) == 1


# -- Plan 15-10 Task 1: Choose Library Folder, Change Folder..., the empty-collection page and focus ------

NEW_TIP = "Create a new, empty library collection and switch to it"
OPEN_TIP = "Open a folder that already holds a library collection"
EMPTY_HEADING = "No libraries in this collection yet"


class FakeChooseDialog(QObject):
    """Stands in for ChooseLibraryFolderDialog: records how it was built and opened, never shows a window."""

    finished = Signal(int)
    instances = []

    def __init__(self, current, *, origin="main", check=None, new_collection=None, parent=None):
        super().__init__(parent)
        self.current = current
        self.origin = origin
        self.parent_window = parent
        self.opened = 0
        self.raised = 0
        self.activated = 0
        self.deleted = False
        self._folder = None
        self._created = False
        FakeChooseDialog.instances.append(self)

    def open(self):
        self.opened += 1

    def raise_(self):
        self.raised += 1

    def activateWindow(self):
        self.activated += 1

    def deleteLater(self):
        self.deleted = True

    def chosen_folder(self):
        return self._folder

    def created(self):
        return self._created

    def accept_with(self, folder, created=False):
        self._folder = folder
        self._created = created
        self.finished.emit(1)

    def reject(self):
        self.finished.emit(0)


@pytest.fixture
def fake_choose(monkeypatch):
    FakeChooseDialog.instances = []
    monkeypatch.setattr(main_window, "ChooseLibraryFolderDialog", FakeChooseDialog)
    return FakeChooseDialog


def one_library(root):
    return ScanResult(symbol_libs=[SymbolLibrary("X", "Custom/Symbols/X.kicad_sym", "Custom")])


def change_button(window):
    return next(b for b in window.findChildren(QPushButton) if b.text() == "Change Folder...")


def test_new_and_open_actions_head_the_file_menu(make_root_window):
    window = make_root_window()
    actions = file_menu(window).actions()[:5]
    new, opened, use_kicad, recent, show = actions
    assert new is window._act_new_collection and opened is window._act_choose_folder
    assert use_kicad is window._act_use_kicad and recent is window._recent_menu.menuAction()
    assert show is window._act_open_folder
    assert new.text() == "&New Library Collection..."
    assert opened.text() == "&Open Library Collection..."
    assert use_kicad.text() == "Use &KiCad's Folder"
    assert recent.text() == "Recent &Library Collections"
    assert show.text() == (
        "S&how Library Folder in Explorer" if sys.platform == "win32" else "S&how Library Folder in File Manager"
    )
    assert new.toolTip() == new.statusTip() == NEW_TIP
    assert opened.toolTip() == opened.statusTip() == OPEN_TIP
    for action in actions:
        assert action.shortcut().isEmpty()
    assert [a.text().split("&", 1)[1][0] for a in actions] == ["N", "O", "K", "L", "h"]
    assert file_menu(window).actions()[5].isSeparator()


def test_change_folder_button_ends_the_row(make_root_window):
    window = make_root_window()
    button = change_button(window)
    row = window.centralWidget().layout().itemAt(0).layout()
    assert row.itemAt(row.count() - 1).widget() is button
    assert button is window._change_folder_btn
    assert button.toolTip() == "Open another library collection"
    assert not button.autoDefault()
    assert button.minimumHeight() >= 28


@pytest.mark.parametrize("how", ["action", "button"])
def test_choose_dialog_opens_window_modal(make_root_window, fake_choose, how):
    window = make_root_window()
    (window._act_choose_folder.trigger if how == "action" else window._change_folder_btn.click)()
    assert len(fake_choose.instances) == 1
    dialog = fake_choose.instances[0]
    assert dialog.current == window._root
    assert dialog.origin == "main"
    assert dialog.parent_window is window
    assert dialog.opened == 1

    # a second trigger raises the open dialog instead of opening another
    window._open_choose_folder()
    assert len(fake_choose.instances) == 1
    assert dialog.raised == 1 and dialog.activated == 1 and dialog.opened == 1


def test_choose_accept_switches(qtbot, make_root_window, fake_choose):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._open_choose_folder()
    dialog = fake_choose.instances[0]
    dialog.accept_with(b)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert make_root_window.scan_calls == [a, b]
    assert window._source is Source.CHOSEN
    assert dialog.deleted and window._choose_dialog is None
    assert not [line for line in log_lines(window) if line.startswith("Created a new collection")]
    assert settings.load_library_root() == b


def test_choose_created_collection_logs_and_switches(qtbot, make_root_window, fake_choose):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._open_choose_folder()
    fake_choose.instances[0].accept_with(b, created=True)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    lines = log_lines(window)
    assert f"Created a new collection in {b}" in lines
    assert lines.index(f"Created a new collection in {b}") < lines.index(f"Library folder: {b} (your choice)")
    assert COLORS["success"].lower() in window._log._text.toHtml().lower()


def test_choose_keep_current_changes_nothing(qtbot, make_root_window, fake_choose):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    before = len(log_lines(window))
    window._open_choose_folder()
    dialog = fake_choose.instances[0]
    dialog.reject()
    qtbot.wait(50)

    assert window._root == a
    assert make_root_window.scan_calls == [a]
    assert len(log_lines(window)) == before
    assert settings.load_library_root() is None
    assert dialog.deleted and window._choose_dialog is None
    # the next trigger builds a fresh dialog
    window._open_choose_folder()
    assert len(fake_choose.instances) == 2


def test_choose_refused_while_busy(qtbot, make_root_window, fake_choose):
    make_root_window.gate = threading.Event()
    window = make_root_window(wait=False)
    qtbot.waitUntil(lambda: len(make_root_window.scan_calls) == 1, timeout=30000)
    try:
        assert not window._act_choose_folder.isEnabled()
        assert not window._change_folder_btn.isEnabled()
        text = BUSY_TEXTS["scan"]
        window._open_choose_folder()
        assert fake_choose.instances == []
        assert [line for line in log_lines(window) if line == text] == [text]
        assert window.statusBar().currentMessage() == text
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._act_choose_folder.isEnabled()
    assert window._change_folder_btn.isEnabled()


class FakeNewCollectionDialog(QObject):
    """Stands in for NewCollectionDialog: records how it was built and opened, never shows a window."""

    finished = Signal(int)
    instances = []

    def __init__(self, *, origin="choose", parent_folder=None, name=None, parent=None, **kwargs):
        super().__init__(parent)
        self.origin = origin
        self.parent_window = parent
        self.opened = 0
        self.raised = 0
        self.activated = 0
        self.deleted = False
        self.creating = False
        self._folder = None
        FakeNewCollectionDialog.instances.append(self)

    def open(self):
        self.opened += 1

    def raise_(self):
        self.raised += 1

    def activateWindow(self):
        self.activated += 1

    def deleteLater(self):
        self.deleted = True

    def is_creating(self):
        return self.creating

    def created_folder(self):
        return self._folder

    def accept_with(self, folder):
        self._folder = folder
        self.finished.emit(1)

    def reject(self):
        self.finished.emit(0)


@pytest.fixture
def fake_new(monkeypatch):
    FakeNewCollectionDialog.instances = []
    monkeypatch.setattr(main_window, "NewCollectionDialog", FakeNewCollectionDialog)
    return FakeNewCollectionDialog


def test_new_collection_opens_window_modal_over_the_main_window(make_root_window, fake_new):
    window = make_root_window()
    window._act_new_collection.trigger()
    (dialog,) = fake_new.instances
    assert dialog.origin == "main" and dialog.parent_window is window and dialog.opened == 1

    # a second trigger raises the open dialog instead of opening another
    window._open_new_collection()
    assert len(fake_new.instances) == 1
    assert dialog.raised == 1 and dialog.activated == 1 and dialog.opened == 1


def test_new_collection_refused_while_busy(qtbot, make_root_window, fake_new):
    make_root_window.gate = threading.Event()
    window = make_root_window(wait=False)
    qtbot.waitUntil(lambda: len(make_root_window.scan_calls) == 1, timeout=30000)
    try:
        assert not window._act_new_collection.isEnabled()
        text = BUSY_TEXTS["scan"]
        window._open_new_collection()
        assert fake_new.instances == []
        assert [line for line in log_lines(window) if line == text] == [text]
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._act_new_collection.isEnabled()


def test_new_collection_back_changes_nothing(qtbot, make_root_window, fake_new):
    a = other_collection(make_root_window, "a")
    window = make_root_window(a)
    before = len(log_lines(window))
    window._open_new_collection()
    dialog = fake_new.instances[0]
    dialog.reject()
    qtbot.wait(50)

    assert window._root == a and make_root_window.scan_calls == [a]
    assert len(log_lines(window)) == before
    assert settings.load_library_root() is None
    assert dialog.deleted and window._new_dialog is None


def test_new_collection_created_logs_and_switches(qtbot, make_root_window, fake_new):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._open_new_collection()
    dialog = fake_new.instances[0]
    dialog.accept_with(b)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    lines = log_lines(window)
    assert f"Created a new collection in {b}" in lines
    assert lines.index(f"Created a new collection in {b}") < lines.index(f"Library folder: {b} (your choice)")
    assert COLORS["success"].lower() in window._log._text.toHtml().lower()
    assert window._source is Source.CHOSEN and settings.load_library_root() == b
    assert dialog.deleted and window._new_dialog is None


def test_window_close_is_refused_while_the_main_new_collection_creates(qtbot, make_root_window, fake_new):
    window = make_root_window()
    window.show()
    window._open_new_collection()
    (dialog,) = fake_new.instances
    dialog.creating = True
    assert window.close() is False
    assert window.isVisible() and window._new_dialog is dialog and not dialog.deleted

    dialog.creating = False
    assert window.close() is True


def test_change_folder_and_open_action_open_the_same_window(make_root_window, fake_choose):
    window = make_root_window()
    window._act_choose_folder.trigger()
    (dialog,) = fake_choose.instances
    assert dialog.origin == "main"
    assert window._choose_dialog is dialog


def test_open_folder_stays_enabled_while_scanning(qtbot, make_root_window):
    make_root_window.gate = threading.Event()
    window = make_root_window(wait=False)
    qtbot.waitUntil(lambda: len(make_root_window.scan_calls) == 1, timeout=30000)
    try:
        assert window._act_open_folder.isEnabled()
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)


def real_skeleton(make, name="new lib"):
    """The real New Collection skeleton in a tmp folder, scanned by the real scan (no git process starts)."""
    ctx, _calls = recording_git({"--version": (0, "git version 2.49.0.windows.1"), "init": (0, "")})
    target = make.tmp_path / name
    assert create_collection(target, ctx, app_dir=make.tmp_path / "app", environ={}) == []
    make.result_for = lambda root: library_scanner.scan_all(root)
    return target


def test_new_collection_skeleton_shows_the_empty_page(make_root_window):
    root = real_skeleton(make_root_window)
    window = make_root_window(root)
    assert window._scan_result.footprint_libs[0].empty is True
    assert window._list_stack.currentWidget() is window._empty_page
    assert str(root) in window._empty_body.text()
    assert window.focusWidget() is window._import_btn


def test_skeleton_with_a_footprint_shows_the_trees(qtbot, make_root_window):
    root = real_skeleton(make_root_window)
    window = make_root_window(root)
    assert window._list_stack.currentWidget() is window._empty_page
    pretty = root / "Custom" / "Footprints" / "Atomic_Footprints.pretty"
    (pretty / "X.kicad_mod").write_text('(footprint "X")\n', encoding="utf-8")
    window._start_scan()
    settle_scan(qtbot, window)
    assert window._list_stack.currentWidget() is window._tree


def test_empty_collection_page(qtbot, make_root_window):
    root = make_collection(make_root_window.tmp_path / "empty lib")
    window = make_root_window(root)
    assert window._list_stack.currentWidget() is window._empty_page
    assert window._empty_heading.text() == EMPTY_HEADING
    assert window._empty_body.text() == (
        f"Press Import Part... (Ctrl+I) to add your first part. It is saved in the Custom folder of {root}."
    )

    # hidden while a scan runs
    make_root_window.gate = threading.Event()
    window._start_scan()
    try:
        assert window._list_stack.currentWidget() is window._tree
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)
    assert window._list_stack.currentWidget() is window._empty_page

    # one library found: the trees come back
    make_root_window.result_for = one_library
    window._start_scan()
    settle_scan(qtbot, window)
    assert window._list_stack.currentWidget() is window._tree


def test_empty_page_names_the_new_folder_after_a_switch(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    assert str(b) in window._empty_body.text()
    assert str(a) not in window._empty_body.text()


def test_empty_page_is_plain_text(make_root_window):
    root = make_collection(make_root_window.tmp_path / "R&D (x)")
    window = make_root_window(root)
    assert window._empty_body.textFormat() == Qt.TextFormat.PlainText
    assert window._empty_body.wordWrap()
    assert "R&D (x)" in window._empty_body.text()
    assert MUTED in window._empty_body.styleSheet()


def test_empty_page_not_before_first_scan(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    make_root_window.result_for = one_library
    window = make_root_window(a)
    assert window._list_stack.currentWidget() is window._tree
    make_root_window.gate = threading.Event()
    try:
        assert window._switch_root(b, Source.CHOSEN) is True
        assert window._list_stack.currentWidget() is window._tree
        assert window._tree._sym_tree.topLevelItemCount() == 0
    finally:
        make_root_window.gate.set()
    settle_scan(qtbot, window)


def test_empty_page_after_a_library_rescan(make_root_window):
    root = make_collection(make_root_window.tmp_path / "lib")
    make_root_window.result_for = one_library
    window = make_root_window(root)
    assert window._list_stack.currentWidget() is window._tree
    # a library rescan that leaves nothing shows the message again
    window._on_library_rescanned(
        library_scanner.LibraryRescan(result=ScanResult(), issues=[], rechecked=[])
    )
    assert window._list_stack.currentWidget() is window._empty_page


def test_focus_goes_to_the_symbols_tree_after_the_first_scan(make_root_window):
    make_root_window.result_for = one_library
    window = make_root_window()
    tree = window._tree._sym_tree
    assert window.focusWidget() is tree
    assert tree.currentItem() is tree.topLevelItem(0)
    assert window._focus_after_scan is False


def test_focus_goes_to_import_when_empty(make_root_window):
    window = make_root_window()
    assert window.focusWidget() is window._import_btn


def test_root_row_never_takes_focus(make_root_window):
    window = make_root_window()
    assert window.focusWidget() is not window._change_folder_btn
    assert window._root_path.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_later_rescan_leaves_focus_alone(qtbot, make_root_window, monkeypatch):
    make_root_window.result_for = one_library
    window = make_root_window()
    calls = []
    real = window._apply_focus
    monkeypatch.setattr(window, "_apply_focus", lambda: (calls.append(1), real())[1])
    window._tree._fp_tree.setFocus()
    window._start_scan()
    settle_scan(qtbot, window)
    assert calls == []
    assert window.focusWidget() is window._tree._fp_tree


def test_focus_follows_a_switch(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    make_root_window.result_for = one_library
    window = make_root_window(a)
    window._tree._fp_tree.setFocus()
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    assert window.focusWidget() is window._tree._sym_tree


def test_focus_waits_for_the_path_variable_question(qtbot, make_root_window, monkeypatch):
    seen = []

    def question(self, title, text, buttons, default):
        seen.append((self._focus_after_scan, self.focusWidget()))
        return QMessageBox.StandardButton.No

    write_kicad_common(make_root_window.config_base, github=None)
    make_root_window.result_for = one_library
    monkeypatch.setattr(main_window.MainWindow, "_question", question)
    window = make_root_window(switched=True)
    settle_offer(qtbot, window)
    qtbot.waitUntil(lambda: window._focus_after_scan is False, timeout=30000)

    assert seen, "the path variable question was not asked"
    pending, focus_then = seen[0]
    assert pending is True
    assert focus_then is not window._tree._sym_tree
    assert window.focusWidget() is window._tree._sym_tree


def test_row_controls_fit_at_900px(qtbot, make_root_window):
    """Backstop: a 200-character path and the amber tag never push Change Folder... out of a 900 px window."""
    root = make_collection(make_root_window.tmp_path / "lib")
    window = make_root_window(root)
    long_path = ("C:/" + "/".join(["very_long_folder_name_x"] * 9))[:200]
    assert len(long_path) == 200
    window._root_path.set_full_text(long_path)
    window._root_tag.setText("⚠ KiCad reads a different folder")
    window.resize(900, 700)
    window.show()
    qtbot.waitExposed(window)
    qtbot.wait(50)
    button = change_button(window)
    assert button.isVisible()
    assert button.mapTo(window, button.rect().topRight()).x() <= window.width()
    assert button.width() >= button.sizeHint().width()


def test_default_dialog_class_is_the_real_one():
    from kicad_lib_manager.widgets import choose_folder_dialog

    assert main_window.ChooseLibraryFolderDialog is choose_folder_dialog.ChooseLibraryFolderDialog


# -- Code review CR-02: a relative folder is made absolute before it is saved or offered to KiCad ----


def test_window_root_is_absolute(make_root_window, monkeypatch):
    root = make_collection(make_root_window.tmp_path / "lib")
    monkeypatch.chdir(make_root_window.tmp_path)
    window = make_root_window(Path("lib"))
    assert window._root == root and window._root.is_absolute()
    assert make_root_window.scan_calls == [root]


def test_switch_to_a_relative_folder_saves_and_offers_the_absolute_one(qtbot, make_root_window, monkeypatch):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    monkeypatch.chdir(make_root_window.tmp_path)
    make_root_window.answer = QMessageBox.StandardButton.No

    window._request_switch(Path("b"), Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)

    assert window._root.is_absolute()
    assert settings.load_library_root() == b
    assert settings.load_library_recent()[0] == str(b)
    assert window._root_path.full_text() == str(b)
    assert make_root_window.scan_calls == [a, b]
    assert library_scanner._desired_path_vars(window._root)["KICAD_LIB_GITHUB"] == b.as_posix()


def test_switch_root_absolutises_before_saving(make_root_window, monkeypatch):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    monkeypatch.chdir(make_root_window.tmp_path)
    assert window._switch_root(Path("b"), Source.CHOSEN) is True
    assert window._root == b and settings.load_library_root() == b


def test_window_close_is_refused_while_a_new_collection_creates(qtbot, make_root_window, fake_choose):
    """WR-05: closing the window must not destroy a Choose dialog whose New Collection is writing files."""
    window = make_root_window()
    window.show()
    window._open_choose_folder()
    (dialog,) = fake_choose.instances
    dialog.is_creating = lambda: True
    assert window.close() is False
    assert window.isVisible() and window._choose_dialog is dialog and not dialog.deleted

    dialog.is_creating = lambda: False
    assert window.close() is True


def test_late_folder_check_after_close_switches_nothing(qtbot, make_root_window):
    """WR-03: a check still blocked when the window closes is cancelled, and its late answer is ignored."""
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window.show()
    gate = make_root_window.check_gates[str(b)] = threading.Event()
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: bool(make_root_window.checks) and make_root_window.checks[-1][0] == b, timeout=30000)
    (task,) = window._root_checks
    try:
        assert window.close() is True
        assert window._closing
        # Cancelled at once while the check is still blocked (never joined, never parked)
        assert task.is_running() and task.is_done()
    finally:
        gate.set()
    qtbot.waitUntil(lambda: not task.is_running(), timeout=30000)
    qtbot.wait(50)  # a late result would be delivered now
    assert window._root == a and make_root_window.scan_calls == [a]
    assert settings.load_library_root() is None and settings.load_library_recent() == []


def test_request_after_close_is_ignored(make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window.close()
    window._request_switch(b, Source.CHOSEN)
    assert window._root_checks == [] and make_root_window.checks == []


def test_finished_checks_are_dropped_at_the_next_request(qtbot, make_root_window):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    settle_checks(qtbot, window)
    window._request_switch(a, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == a and window._worker is None, timeout=30000)
    assert len(window._root_checks) == 1


def test_switch_check_runs_on_a_daemon_thread(qtbot, make_root_window, monkeypatch):
    a = other_collection(make_root_window, "a")
    b = other_collection(make_root_window, "b")
    window = make_root_window(a)
    seen = []  # (daemon, is the main thread)

    def recording_check(path, *, current=None):
        thread = threading.current_thread()
        seen.append((thread.daemon, thread is threading.main_thread()))
        return check_folder(path, current=current)

    monkeypatch.setattr(main_window, "check_folder", recording_check)
    window._request_switch(b, Source.CHOSEN)
    qtbot.waitUntil(lambda: window._root == b and window._worker is None, timeout=30000)
    assert seen == [(True, False)]


# -- Code review WR-01: the GUI thread never touches a recent folder's drive ---------------------------


def test_recent_menu_checks_existence_off_the_gui_thread(qtbot, make_root_window, monkeypatch):
    a = other_collection(make_root_window, "a")
    hung = other_collection(make_root_window, "hung")
    gone = other_collection(make_root_window, "gone")
    settings.get_settings().setValue("library/recent", [str(hung), str(gone), str(a)])
    shutil.rmtree(gone)
    window = make_root_window(a)
    gui = threading.get_ident()
    gate = threading.Event()
    seen = []  # (folder name, on the GUI thread)
    real_is_dir = Path.is_dir

    def is_dir(self):
        if self.name in ("hung", "gone"):
            seen.append((self.name, threading.get_ident() == gui))
            if self.name == "hung" and threading.get_ident() != gui:
                gate.wait(10)  # a disconnected drive: the answer takes a long time
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    qtbot.waitUntil(lambda: window._recent_check.is_done(), timeout=30000)
    qtbot.wait(30)
    seen.clear()
    try:
        started = time.monotonic()
        file_menu(window).aboutToShow.emit()
        assert time.monotonic() - started < 2.0
        # Last known list at once: nothing is known to be gone yet, the check is still blocked
        assert [x.data() for x in window._recent_menu.actions()][:1] == [str(hung)]
        qtbot.waitUntil(lambda: bool(seen), timeout=30000)
    finally:
        gate.set()
    qtbot.waitUntil(lambda: [x.data() for x in window._recent_menu.actions()] == [str(hung), str(a)], timeout=30000)
    assert seen and not any(on_gui for _name, on_gui in seen)


def test_folder_comparisons_on_the_gui_thread_do_not_resolve_paths(qtbot, make_root_window, monkeypatch):
    a = other_collection(make_root_window, "a")
    settings.add_library_recent(a)
    window = make_root_window(a)
    gui = threading.get_ident()
    seen = []
    real_resolve = Path.resolve

    def resolve(self, *args, **kwargs):
        if threading.get_ident() == gui and str(self).startswith(str(make_root_window.tmp_path)):
            seen.append(str(self))
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    window._rebuild_recent_menu()
    window._on_recent_chosen(str(a))
    window._request_switch(a, Source.CHOSEN)
    assert seen == []
    assert window.statusBar().currentMessage() == "You are already using this library folder."
