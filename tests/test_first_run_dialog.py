"""Offscreen tests for the first-run window (Phase 15-08, ROOT-05).

The folder check, the Choose dialog and the New Collection dialog are fakes injected through the constructor,
so no real folder is checked off the tmp tree and nothing is created.
"""

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton

from kicad_lib_manager.collection import CheckRow, FolderCheck, Source
from kicad_lib_manager.widgets import first_run_dialog as frd
from kicad_lib_manager.widgets.first_run_dialog import FirstRunChoice, FirstRunDialog
from kicad_lib_manager.widgets.theme import AMBER, AMBER_TINT, ERROR, MONO_FAMILY

GUI_THREAD = threading.get_ident()
KICAD = "C:/KiCad_Libraries"
BODY = (
    "This app works on one library folder: the folder that holds your Custom libraries. "
    "Choose how to set it up. Nothing is created or changed until you confirm."
)
NO_KICAD = "KiCad does not name a library folder yet (KICAD_LIB_GITHUB is not set)."


def folder_check(path, state="collection", rows=None):
    path = Path(path)
    return FolderCheck(path, tuple(rows or ()), state, len(str(path)))


class Recorder:
    """A fake folder check that records its calls and threads and can be gated."""

    def __init__(self, state="collection", rows=None):
        self.state = state
        self.rows = rows
        self.calls: list[str] = []
        self.threads: list[int] = []
        self.gate: threading.Event | None = None

    def __call__(self, path, *, current=None):
        self.calls.append(str(path))
        self.threads.append(threading.get_ident())
        if self.gate is not None:
            self.gate.wait(10)
        return folder_check(path, self.state, self.rows)


class FakeChoose(QDialog):
    instances: list["FakeChoose"] = []

    def __init__(self, current, **kwargs):
        super().__init__(kwargs.get("parent"))
        self.current = current
        self.kwargs = kwargs
        self.folder: Path | None = None
        self.was_created = False
        FakeChoose.instances.append(self)

    def chosen_folder(self):
        return self.folder

    def created(self):
        return self.was_created


class FakeNew(QDialog):
    instances: list["FakeNew"] = []

    def __init__(self, **kwargs):
        super().__init__(kwargs.get("parent"))
        self.kwargs = kwargs
        self.folder: Path | None = None
        FakeNew.instances.append(self)

    def created_folder(self):
        return self.folder


@pytest.fixture(autouse=True)
def _reset_fakes():
    FakeChoose.instances = []
    FakeNew.instances = []


@pytest.fixture
def made(qtbot):
    rec = Recorder()

    def make(kicad_folder=KICAD, notice=None, **kwargs) -> FirstRunDialog:
        options = {"check": rec, "choose": FakeChoose, "new_collection": FakeNew}
        options.update(kwargs)
        dialog = FirstRunDialog(kicad_folder, notice, **options)
        qtbot.addWidget(dialog)
        return dialog

    return make, rec


def buttons(dialog) -> list[str]:
    return [button.text() for button in dialog.findChildren(QPushButton)]


def test_window_shape(made):
    make, _ = made
    dialog = make()
    assert dialog.windowTitle() == "Set Up Your Library Folder"
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert dialog.parent() is None
    assert dialog.minimumWidth() == dialog.maximumWidth() == 560
    assert dialog._heading.text() == "Where are your KiCad libraries?"
    assert dialog._body.text() == BODY
    titles = [label.text() for label in dialog.findChildren(QLabel) if label.font().bold()]
    assert "Use KiCad's folder" in titles
    assert "Open an existing collection" in titles
    assert "Create a new collection" in titles
    assert buttons(dialog) == ["Use KiCad's Folder", "Open Library Collection...", "New Library Collection...", "Quit"]
    descriptions = [label.text() for label in dialog.findChildren(QLabel)]
    assert "Pick a folder that already has a Custom folder with Symbols or Footprints inside it." in descriptions
    assert "Start with an empty collection and import your first part into it." in descriptions
    for button in dialog.findChildren(QPushButton):
        assert not button.autoDefault() and not button.isDefault()
        assert "background-color" not in button.styleSheet()  # none uses PRIMARY_BUTTON_QSS
    assert dialog.choice() is None
    assert dialog._notice_strip is None


def test_row1_without_kicad_folder(made, qtbot):
    make, _ = made
    for none in (None, "   "):
        dialog = make(none)
        assert not dialog._row1_btn.isEnabled()
        assert dialog._row1_desc.text() == NO_KICAD
        dialog.show()
        qtbot.waitUntil(lambda d=dialog: d.focusWidget() is d._row2_btn, timeout=2000)
        dialog.close()


def test_row1_names_the_folder_as_plain_text(made):
    make, _ = made
    dialog = make("C:/x/<a> & b")
    text = dialog._row1_desc.text()
    assert "C:/x/&lt;a&gt; &amp; b" in text and MONO_FAMILY in text
    assert dialog._row1_desc.accessibleName() == "KiCad's settings name C:/x/<a> & b as its library folder."
    assert dialog._row1_btn.isEnabled()


def test_row1_collection_is_chosen(made, qtbot):
    make, rec = made
    dialog = make()
    dialog._row1_btn.click()
    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted, timeout=30000)
    assert dialog.choice() == FirstRunChoice(Path(KICAD), Source.KICAD, False)
    assert [Path(c) for c in rec.calls] == [Path(KICAD)] and all(t != GUI_THREAD for t in rec.threads)


def test_row1_empty_folder_opens_new_collection(made, qtbot, tmp_path):
    make, rec = made
    rec.state = "empty"
    target = tmp_path / "Fresh"
    dialog = make(str(target))
    dialog.show()
    dialog._row1_btn.click()
    qtbot.waitUntil(lambda: bool(FakeNew.instances), timeout=30000)
    (fake,) = FakeNew.instances
    assert fake.kwargs == {"origin": "setup", "parent_folder": target.parent, "name": "Fresh", "parent": dialog}
    assert dialog.choice() is None and dialog.isVisible()
    fake.folder = target
    fake.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.choice() == FirstRunChoice(target, Source.CHOSEN, True)


def test_row1_failure_stays_open(made, qtbot):
    make, rec = made
    rec.state = "not_collection"
    rec.rows = (CheckRow("pass", "This folder exists"), CheckRow("fail", "This is not a library collection."))
    dialog = make()
    dialog.show()
    assert not dialog._row1_error.isVisibleTo(dialog)
    dialog._row1_btn.click()
    qtbot.waitUntil(lambda: dialog._row1_error.isVisibleTo(dialog), timeout=30000)
    assert dialog._row1_error.text() == "✖ This is not a library collection."
    assert dialog._row1_error.textFormat() == Qt.TextFormat.PlainText
    assert ERROR in dialog._row1_error.styleSheet()
    assert dialog.isVisible() and dialog.choice() is None
    assert dialog._row1_btn.isEnabled() and dialog._row2_btn.isEnabled() and dialog._row3_btn.isEnabled()
    # the other buttons still work
    dialog._row2_btn.click()
    assert len(FakeChoose.instances) == 1


def test_row1_worker_failure_shows_a_line(made, qtbot):
    make, _ = made

    def broken(path, *, current=None):
        raise OSError("drive gone")

    dialog = make(check=broken)
    dialog.show()
    dialog._row1_btn.click()
    qtbot.waitUntil(lambda: dialog._row1_error.isVisibleTo(dialog), timeout=30000)
    assert dialog._row1_error.text() == "✖ Library folder step failed: OSError: drive gone"
    assert dialog.isVisible()


def test_row2_choose_and_row3_new(made, qtbot, tmp_path):
    make, _ = made
    dialog = make()
    dialog.show()

    dialog._row2_btn.click()
    (choose,) = FakeChoose.instances
    assert choose.current is None and choose.kwargs == {"origin": "setup", "parent": dialog}
    choose.reject()  # Back to Setup
    assert dialog.isVisible() and dialog.choice() is None

    dialog._row2_btn.click()
    choose = FakeChoose.instances[-1]
    choose.folder = tmp_path / "lib"
    choose.was_created = True
    choose.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.choice() == FirstRunChoice(tmp_path / "lib", Source.CHOSEN, True)

    other = make()
    other.show()
    other._row3_btn.click()
    (new,) = FakeNew.instances
    assert new.kwargs == {"origin": "setup", "parent": other}
    new.reject()
    assert other.isVisible() and other.choice() is None
    other._row3_btn.click()
    new = FakeNew.instances[-1]
    new.folder = tmp_path / "made"
    new.accept()
    assert other.choice() == FirstRunChoice(tmp_path / "made", Source.CHOSEN, True)

    plain = make()
    plain.show()
    plain._row2_btn.click()
    choose = FakeChoose.instances[-1]
    choose.folder = tmp_path / "existing"
    choose.accept()
    assert plain.choice() == FirstRunChoice(tmp_path / "existing", Source.CHOSEN, False)


def test_notice_strip_only_when_given(made):
    make, _ = made
    text = "The library folder you used before is gone: X."
    dialog = make(notice=text)
    assert dialog._notice_strip is not None
    assert dialog._notice_label.text() == f"⚠ {text}"
    assert AMBER_TINT in dialog._notice_strip.styleSheet() and AMBER in dialog._notice_strip.styleSheet()
    assert "border-left: 2px" in dialog._notice_strip.styleSheet()
    assert make(notice=None)._notice_strip is None


def test_quit_esc_and_close_choose_nothing(made, qtbot):
    make, _ = made
    quit_dialog = make()
    quit_dialog.show()
    quit_dialog._quit_btn.click()
    assert quit_dialog.result() == QDialog.DialogCode.Rejected and quit_dialog.choice() is None

    esc = make()
    esc.show()
    qtbot.keyClick(esc, Qt.Key.Key_Escape)
    assert esc.result() == QDialog.DialogCode.Rejected and esc.choice() is None

    closed = make()
    closed.show()
    closed.close()
    assert closed.result() == QDialog.DialogCode.Rejected and closed.choice() is None


def test_tab_order_and_initial_focus(made, qtbot):
    make, _ = made
    dialog = make()
    dialog.show()
    qtbot.waitUntil(lambda: dialog.focusWidget() is dialog._row1_btn, timeout=2000)
    wanted = [dialog._row1_btn, dialog._row2_btn, dialog._row3_btn, dialog._quit_btn]
    order = [dialog._row1_btn]
    widget = dialog._row1_btn
    for _ in range(12):
        widget = widget.nextInFocusChain()
        if widget in wanted and widget not in order:
            order.append(widget)
    assert order == wanted


def test_double_click_row1_starts_one_check(made, qtbot):
    make, rec = made
    rec.gate = threading.Event()
    dialog = make()
    dialog.show()
    dialog._row1_btn.click()
    dialog._row1_btn.click()
    dialog._on_use_kicad()  # even a direct call while the check runs starts nothing
    qtbot.waitUntil(lambda: bool(rec.calls), timeout=30000)
    rec.gate.set()
    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted, timeout=30000)
    assert [Path(c) for c in rec.calls] == [Path(KICAD)]


def test_close_during_check_cancels_and_chooses_nothing(made, qtbot):
    make, rec = made
    rec.gate = threading.Event()
    dialog = make()
    dialog.show()
    dialog._row1_btn.click()
    qtbot.waitUntil(lambda: bool(rec.calls), timeout=30000)
    tasks = list(dialog._tasks)
    assert tasks and all(task.is_running() for task in tasks)
    started = time.monotonic()
    dialog.close()  # the check is still blocked: close cancels it and does not wait
    assert time.monotonic() - started < 1.0
    assert all(task.is_done() for task in tasks)
    rec.gate.set()
    qtbot.waitUntil(lambda: all(not task.is_running() for task in tasks), timeout=30000)
    qtbot.wait(100)
    assert not FakeNew.instances and not FakeChoose.instances
    assert dialog.choice() is None and dialog.result() == QDialog.DialogCode.Rejected


def test_long_kicad_path_fits(made, qtbot):
    make, _ = made
    path = "C:/" + "k" * 146  # 150 characters
    dialog = make(path)
    dialog.show()
    qtbot.wait(50)
    assert dialog.width() == 560
    button = dialog._row1_btn
    assert button.isVisible()
    right = button.mapTo(dialog, button.rect().bottomRight()).x()
    assert 0 < right <= dialog.width()


# -- Code review WR-05: a window over this one that is creating cannot be closed from here --------------


def test_close_is_refused_while_a_new_collection_creates(made, qtbot, tmp_path):
    make, rec = made
    dialog = make()
    dialog.show()
    dialog._row3_btn.click()
    qtbot.waitUntil(lambda: bool(FakeNew.instances), timeout=30000)
    (fake,) = FakeNew.instances
    assert not dialog.is_creating()
    fake.is_creating = lambda: True
    assert dialog.is_creating()
    dialog.reject()
    dialog.done(0)
    assert dialog.close() is False
    assert dialog.isVisible() and dialog.result() == 0 and not dialog._closing
    fake.is_creating = lambda: False
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
