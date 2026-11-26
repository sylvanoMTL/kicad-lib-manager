"""Offscreen tests for the Open Library Collection dialog (Phase 15-08, ROOT-03 and ROOT-07).

The real check_folder runs on tmp folders for the row texts; fakes injected through the constructor record the
threads, the timing and the new-collection hand-off.
"""

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QProgressBar, QPushButton

from kicad_lib_manager import collection
from kicad_lib_manager.collection import FolderCheck, OWN_DIR, SYMBOLS_DIR, check_folder
from kicad_lib_manager.widgets import choose_folder_dialog as cfd
from kicad_lib_manager.widgets.choose_folder_dialog import ChooseLibraryFolderDialog
from kicad_lib_manager.widgets.theme import AMBER, ERROR, MUTED

GUI_THREAD = threading.get_ident()
BODY = (
    "Pick a folder that already holds a library collection. "
    "To start a new one, use New Library Collection... instead."
)


def make_collection(root: Path) -> Path:
    (root / OWN_DIR / SYMBOLS_DIR).mkdir(parents=True)
    return root


class Recorder:
    """A check that wraps the real one, remembering its calls and the threads it ran on."""

    def __init__(self):
        self.calls: list[str] = []
        self.threads: list[int] = []
        self.gate: threading.Event | None = None
        self.slow: dict[str, threading.Event] = {}

    def __call__(self, path, *, current=None):
        self.calls.append(str(path))
        self.threads.append(threading.get_ident())
        if self.gate is not None:
            self.gate.wait(10)
        wait = self.slow.get(str(path))
        if wait is not None:
            wait.wait(10)
        return check_folder(path, current=current)


class FakeNewCollection(QDialog):
    """Records the keyword arguments of the hand-off and lets a test accept or reject it."""

    instances: list["FakeNewCollection"] = []

    def __init__(self, **kwargs):
        super().__init__(kwargs.get("parent"))
        self.kwargs = kwargs
        self.folder: Path | None = None
        self.opened = False
        FakeNewCollection.instances.append(self)

    def created_folder(self):
        return self.folder

    def open(self):
        self.opened = True
        super().open()


@pytest.fixture(autouse=True)
def _reset_fakes():
    FakeNewCollection.instances = []


@pytest.fixture
def made(qtbot):
    rec = Recorder()

    def make(current=None, **kwargs) -> ChooseLibraryFolderDialog:
        options = {"check": rec, "new_collection": FakeNewCollection}
        options.update(kwargs)
        dialog = ChooseLibraryFolderDialog(current, **options)
        qtbot.addWidget(dialog)
        return dialog

    return make, rec


def settle(qtbot, dialog):
    qtbot.waitUntil(lambda: not dialog._pending, timeout=30000)


def shown(dialog) -> list[str]:
    return [label.accessibleName() for label in dialog._row_labels()]


def test_prefill_and_texts(made, tmp_path):
    make, _ = made
    folder = make_collection(tmp_path / "lib")
    dialog = make(folder)
    assert dialog.windowTitle() == "Open Library Collection"
    assert dialog.minimumWidth() == 560
    assert dialog.windowModality() == Qt.WindowModality.WindowModal
    assert dialog._field.text() == str(folder)
    assert dialog._field.accessibleName() == "Library folder"
    assert dialog._heading.text() == "Open a library collection"
    assert dialog._use_btn.text() == "Open Collection"
    assert dialog._create_here_btn.text() == "New Library Collection..."
    assert dialog._body.text() == BODY
    blank = make(None)
    assert blank._field.text() == "" and blank._field.placeholderText() == "Choose a folder"
    assert dialog._back_btn.text() == "Keep Current Folder"
    assert make(None, origin="setup")._back_btn.text() == "Back to Setup"
    for each in (dialog, blank):
        assert "Cancel" not in [button.text() for button in each.findChildren(QPushButton)]
        assert each._use_btn.minimumWidth() == 112
        for button in each.findChildren(QPushButton):
            assert not button.autoDefault() and not button.isDefault()


def test_rows_for_each_state(made, qtbot, tmp_path, monkeypatch):
    make, _ = made
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10_000)

    good = make_collection(tmp_path / "good")
    dialog = make(None)
    dialog._field.setText(str(good))
    settle(qtbot, dialog)
    assert shown(dialog) == [
        "✓ This folder exists",
        "✓ You can write to this folder",
        "✓ It is a library collection (Custom holds Symbols or Footprints)",
    ]
    hinted = dialog._row_labels()[2]
    assert MUTED in hinted.text() and "(Custom holds Symbols or Footprints)" in hinted.text()
    assert dialog._use_btn.isEnabled() and not dialog._create_here_btn.isVisibleTo(dialog)

    # the folder already in use: the plain line, Open Collection disabled
    in_use = make(good)
    settle(qtbot, in_use)
    assert shown(in_use)[-1] == "You are already using this library folder."
    assert not in_use._use_btn.isEnabled()

    # an empty folder: the plain offer, Create Here shown, Use disabled
    empty = tmp_path / "empty"
    empty.mkdir()
    dialog._field.setText(str(empty))
    settle(qtbot, dialog)
    assert shown(dialog)[-1] == (
        "This folder is empty, so it is not a library collection yet. Press New Library Collection... to start one in it."
    )
    assert dialog._create_here_btn.isVisibleTo(dialog) and not dialog._use_btn.isEnabled()

    # missing, not a collection and a Custom folder each stop at their own failure row
    dialog._field.setText(str(tmp_path / "nope"))
    settle(qtbot, dialog)
    assert shown(dialog) == ["✖ This folder does not exist. Choose another folder."]
    assert not dialog._use_btn.isEnabled() and not dialog._create_here_btn.isVisibleTo(dialog)
    assert ERROR in dialog._row_labels()[0].styleSheet()

    other = tmp_path / "other"
    other.mkdir()
    (other / "x.txt").write_text("x")
    dialog._field.setText(str(other))
    settle(qtbot, dialog)
    assert shown(dialog)[-1].startswith("✖ This is not a library collection")
    assert not dialog._use_btn.isEnabled()

    own = make_collection(tmp_path / "coll") / OWN_DIR
    dialog._field.setText(str(own))
    settle(qtbot, dialog)
    assert shown(dialog)[-1].startswith("✖ This looks like the Custom folder of a collection.")
    assert not dialog._use_btn.isEnabled()


def test_long_collection_path_adds_the_warning_row(made, qtbot, tmp_path, monkeypatch):
    make, _ = made
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10)
    good = make_collection(tmp_path / "good")
    dialog = make(None)
    dialog._field.setText(str(good))
    settle(qtbot, dialog)
    labels = dialog._row_labels()
    assert len(labels) == 4 and labels[3].accessibleName().startswith("⚠ The path is ")
    assert AMBER in labels[3].styleSheet()
    assert dialog._use_btn.isEnabled()  # the warning never blocks


def test_use_this_folder_only_for_a_collection(made, qtbot, tmp_path):
    make, _ = made
    good = make_collection(tmp_path / "good")
    dialog = make(None)
    dialog._field.setText(str(good))
    settle(qtbot, dialog)
    dialog._use_btn.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.chosen_folder() == good and dialog.created() is False

    other = make(None)
    other._field.setText(str(tmp_path / "nope"))
    settle(qtbot, other)
    assert not other._use_btn.isEnabled()
    other._use_shortcut.activated.emit()  # Ctrl+Return does nothing while it is disabled
    assert other.result() == QDialog.DialogCode.Rejected and other.chosen_folder() is None

    again = make(None)
    again._field.setText(str(good))
    settle(qtbot, again)
    again._use_shortcut.activated.emit()
    assert again.chosen_folder() == good


def test_checking_state(made, qtbot, tmp_path):
    make, rec = made
    good = make_collection(tmp_path / "good")
    rec.gate = threading.Event()
    dialog = make(None)
    dialog._field.setText(str(good))
    dialog.show()
    qtbot.waitUntil(lambda: bool(rec.calls), timeout=30000)
    assert shown(dialog) == ["Checking the folder..."]
    assert dialog._strip.isVisibleTo(dialog)
    assert dialog._progress.isVisibleTo(dialog) and dialog._progress.maximum() == 0
    assert isinstance(dialog._progress, QProgressBar)
    assert not dialog._use_btn.isEnabled()
    assert rec.threads and all(t != GUI_THREAD for t in rec.threads)
    rec.gate.set()
    settle(qtbot, dialog)
    assert shown(dialog)[0] == "✓ This folder exists"
    assert not dialog._progress.isVisibleTo(dialog)
    assert dialog._use_btn.isEnabled()


def test_debounce_and_stale_results(made, qtbot, tmp_path):
    make, rec = made
    first = make_collection(tmp_path / "a")
    second = make_collection(tmp_path / "b")
    dialog = make(None)
    for text in (str(tmp_path / "x"), str(tmp_path / "xy"), str(first)):
        dialog._field.setText(text)
    # No wall-clock wait: the event loop has not run since the last edit, so the quiet period is still counting
    assert dialog._debounce.isActive()
    assert rec.calls == []  # nothing before the quiet period is over
    settle(qtbot, dialog)
    assert rec.calls == [str(first)]  # three quick edits, one check

    # a slow older check finishing last does not replace the newest rows
    release = threading.Event()
    rec.slow[str(first)] = release
    dialog._field.setText(str(first) + " ")  # the same folder; the slow gate keys on the stripped text
    qtbot.waitUntil(lambda: len(rec.calls) == 2, timeout=30000)
    dialog._field.setText(str(second))
    settle(qtbot, dialog)
    assert dialog._result.path == second
    release.set()
    qtbot.wait(200)
    assert dialog._result.path == second
    assert dialog._use_btn.isEnabled()


def test_enter_rechecks_without_accepting(made, qtbot, tmp_path):
    make, rec = made
    good = make_collection(tmp_path / "good")
    dialog = make(None)
    dialog.show()
    dialog._field.setText(str(good))
    settle(qtbot, dialog)
    calls = len(rec.calls)
    qtbot.keyClick(dialog._field, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: len(rec.calls) == calls + 1, timeout=30000)
    settle(qtbot, dialog)
    assert dialog.isVisible() and dialog.result() == QDialog.DialogCode.Rejected


def test_browse(made, qtbot, tmp_path, monkeypatch):
    make, rec = made
    good = make_collection(tmp_path / "good")
    seen: list[str] = []

    def pick(parent, title, start):
        seen.append(start)
        return pick.answer

    pick.answer = ""
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(pick))

    dialog = make(None)
    dialog._field.setText(str(tmp_path / "missing" / "deeper"))
    settle(qtbot, dialog)
    before = len(rec.calls)
    dialog._browse_btn.click()
    assert seen[-1] == str(tmp_path)  # the nearest existing parent
    assert dialog._field.text() == str(tmp_path / "missing" / "deeper") and len(rec.calls) == before

    dialog._field.setText(str(good))
    dialog._browse_btn.click()
    assert seen[-1] == str(good)  # the field's own folder

    dialog._field.setText("")
    dialog._browse_btn.click()
    assert seen[-1] == str(Path.home())

    other = make_collection(tmp_path / "other")
    pick.answer = str(other)
    dialog._browse_btn.click()
    assert dialog._field.text() == str(other)
    settle(qtbot, dialog)  # checked at once, without the debounce
    assert dialog._use_btn.isEnabled() and rec.calls[-1] == str(other)


def test_blank_field_hides_strip(made, qtbot, tmp_path):
    make, rec = made
    good = make_collection(tmp_path / "good")
    dialog = make(None)
    dialog.show()
    assert not dialog._strip.isVisibleTo(dialog) and not dialog._use_btn.isEnabled()
    dialog._field.setText(str(good))
    settle(qtbot, dialog)
    assert dialog._strip.isVisibleTo(dialog)
    dialog._field.setText("   ")
    assert not dialog._strip.isVisibleTo(dialog) and not dialog._use_btn.isEnabled()
    assert not dialog._create_here_btn.isVisibleTo(dialog)
    qtbot.wait(450)
    assert rec.calls == [str(good)]  # a blank field is never checked


def test_create_here_hand_off(made, qtbot, tmp_path):
    make, _ = made
    empty = tmp_path / "Fresh"
    empty.mkdir()
    dialog = make(None)
    dialog.show()
    dialog._field.setText(str(empty))
    settle(qtbot, dialog)
    assert dialog._create_here_btn.isVisibleTo(dialog)
    dialog._create_here_btn.click()
    (fake,) = FakeNewCollection.instances
    assert fake.opened
    assert fake.kwargs == {
        "origin": "choose", "parent_folder": empty.parent, "name": "Fresh", "parent": dialog,
    }

    # Back to Open: the dialog stays open and unchanged
    fake.reject()
    assert dialog.isVisible() and dialog._field.text() == str(empty)
    assert dialog.chosen_folder() is None and dialog.created() is False

    # a created collection becomes the chosen folder and the Choose dialog accepts
    dialog._create_here_btn.click()
    fake = FakeNewCollection.instances[-1]
    assert fake is not FakeNewCollection.instances[0]
    fake.folder = empty
    fake.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.chosen_folder() == empty and dialog.created() is True


def test_tab_order_and_focus(made, qtbot, tmp_path):
    make, _ = made
    empty = tmp_path / "empty"
    empty.mkdir()
    dialog = make(None)
    dialog._field.setText(str(empty))
    dialog.show()
    settle(qtbot, dialog)
    qtbot.waitUntil(lambda: dialog.focusWidget() is dialog._field, timeout=30000)
    order = [dialog._field]
    widget = dialog._field
    for _ in range(20):
        widget = widget.nextInFocusChain()
        if widget in (dialog._browse_btn, dialog._create_here_btn, dialog._back_btn, dialog._use_btn):
            if widget not in order:
                order.append(widget)
    assert order[:5] == [dialog._field, dialog._browse_btn, dialog._create_here_btn, dialog._back_btn, dialog._use_btn]


def test_esc_rejects_and_cancels_checks(made, qtbot, tmp_path):
    make, rec = made
    good = make_collection(tmp_path / "good")
    rec.gate = threading.Event()
    dialog = make(None)
    dialog._field.setText(str(good))
    dialog.show()
    qtbot.waitUntil(lambda: bool(rec.calls), timeout=30000)
    tasks = list(dialog._tasks)
    assert tasks and all(task.is_running() for task in tasks)
    started = time.monotonic()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)  # the check is still gated: close cancels it and does not wait
    assert time.monotonic() - started < 1.0
    assert dialog.result() == QDialog.DialogCode.Rejected and dialog.chosen_folder() is None
    assert all(task.is_done() for task in tasks)
    rec.gate.set()
    qtbot.waitUntil(lambda: all(not task.is_running() for task in tasks), timeout=30000)
    qtbot.wait(50)
    assert dialog.chosen_folder() is None and dialog.result() == QDialog.DialogCode.Rejected


def test_worker_failure_shows_a_row(made, qtbot):
    make, _ = made

    def broken(path, *, current=None):
        raise OSError("drive gone")

    dialog = make(None, check=broken)
    dialog._field.setText("somewhere")
    settle(qtbot, dialog)
    assert shown(dialog) == ["✖ Library folder step failed: OSError: drive gone"]
    assert not dialog._use_btn.isEnabled()


def test_long_path_does_not_widen(made, qtbot, tmp_path):
    make, _ = made
    long_name = "a" * 250
    dialog = make(None)
    dialog._field.setText(str(tmp_path / long_name))
    dialog.show()
    settle(qtbot, dialog)
    qtbot.wait(50)
    assert dialog.width() <= 560

    # a failure row that names a long path wraps inside the strip
    deep = make_collection(tmp_path / ("b" * 120)) / OWN_DIR
    dialog._field.setText(str(deep))
    settle(qtbot, dialog)
    qtbot.wait(50)
    assert shown(dialog)[-1].startswith("✖ This looks like the Custom folder")
    assert dialog.width() <= 560


def test_no_markup_in_paths(made, qtbot, tmp_path):
    make, _ = made
    odd = tmp_path / "a &amp; b &lt;i&gt; y"
    odd.mkdir()
    own = make_collection(odd) / OWN_DIR
    dialog = make(None)
    dialog._field.setText(str(own))
    settle(qtbot, dialog)
    label = dialog._row_labels()[-1]
    assert label.textFormat() == Qt.TextFormat.PlainText
    assert "a &amp; b &lt;i&gt; y" in label.text()


def test_a_typed_relative_folder_is_chosen_as_an_absolute_path(made, qtbot, tmp_path, monkeypatch):
    """CR-02: the folder the dialog hands back is never relative."""
    make, _ = made
    good = make_collection(tmp_path / "good")
    monkeypatch.chdir(tmp_path)
    dialog = make(None)
    dialog._field.setText("good")
    settle(qtbot, dialog)
    dialog._use_btn.click()
    assert dialog.chosen_folder() == good and dialog.chosen_folder().is_absolute()


# -- Code review WR-04: closing with several hung checks does not wait -------------------------------


def test_closing_with_several_hung_checks_is_bounded(made, qtbot, tmp_path):
    make, rec = made
    rec.gate = threading.Event()
    dialog = make(None)
    dialog.show()
    for name in ("a", "ab", "abc"):
        dialog._field.setText(str(tmp_path / name))
        dialog._start_check()  # what the debounce timer does after each edit
    qtbot.waitUntil(lambda: len(rec.calls) == 3, timeout=30000)
    tasks = list(dialog._tasks)
    assert len(tasks) == 3
    started = time.monotonic()
    try:
        dialog.close()
        assert time.monotonic() - started < 1.0  # no wait at all, not 3 x 5 s
        assert all(task.is_done() and task.is_running() for task in tasks)  # cancelled, still blocked
    finally:
        rec.gate.set()
    qtbot.waitUntil(lambda: all(not task.is_running() for task in tasks), timeout=30000)


# -- Code review WR-05: a child New Collection dialog that is creating cannot be closed from above ------


def test_close_and_reject_are_refused_while_the_new_collection_creates(made, qtbot, tmp_path):
    make, _ = made
    empty = tmp_path / "Fresh"
    empty.mkdir()
    dialog = make(None)
    dialog.show()
    dialog._field.setText(str(empty))
    settle(qtbot, dialog)
    dialog._create_here_btn.click()
    (fake,) = FakeNewCollection.instances
    assert not dialog.is_creating()
    fake.is_creating = lambda: True  # its worker is writing files
    assert dialog.is_creating()

    dialog.reject()
    dialog.done(0)
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.close() is False
    assert dialog.isVisible() and dialog.result() == 0 and not dialog._closing
    assert dialog._new_dialog is fake

    fake.is_creating = lambda: False  # creation over: closing works again
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
