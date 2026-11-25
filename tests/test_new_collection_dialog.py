"""Offscreen tests for the New Collection dialog (Phase 15-06, ROOT-06).

Every check and creation is a fake injected through the constructor, so no real git runs and nothing is
created on disk except by the one test that uses the real check on a tmp folder.
"""

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton

from kicad_lib_manager import collection
from kicad_lib_manager.collection import CheckRow, NewCollectionCheck
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.widgets import new_collection_dialog as ncd
from kicad_lib_manager.widgets.new_collection_dialog import NewCollectionDialog
from kicad_lib_manager.widgets.theme import AMBER, ERROR

NO_GIT = "Git was not found. A collection needs Git to commit your parts. Install Git for Windows, then try again."
FAILED = (
    "Could not create the collection: git init failed. Choose another name or folder, then try again."
)
LEFT = "Some folders were left behind in {path}. Delete them and try again."
GUI_THREAD = threading.get_ident()


class Recorder:
    """A fake check and a fake create that remember their calls and the threads they ran on."""

    def __init__(self, rows_for=None):
        self.checks: list[tuple[str, str, bool]] = []
        self.threads: list[int] = []
        self.creates: list[Path] = []
        self.rows_for = rows_for or (lambda parent, name: ())
        self.create_result: list[Issue] | Exception = []
        self.gate: threading.Event | None = None
        self.slow: dict[str, threading.Event] = {}

    def check(self, parent, name, *, git_found, app_dir, environ):
        self.checks.append((str(parent), name, git_found))
        self.threads.append(threading.get_ident())
        wait = self.slow.get(name)
        if wait is not None:
            wait.wait(10)
        rows = tuple(self.rows_for(parent, name))
        return NewCollectionCheck(Path(parent) / name if name else None, rows)

    def create(self, target, ctx, *, app_dir, environ):
        self.creates.append(Path(target))
        self.threads.append(threading.get_ident())
        if self.gate is not None:
            self.gate.wait(10)
        if isinstance(self.create_result, Exception):
            raise self.create_result
        return self.create_result


@pytest.fixture
def docs(tmp_path, monkeypatch):
    """The Documents folder the dialog pre-fills: a tmp folder."""
    folder = tmp_path / "Documents"
    folder.mkdir()

    class FakePaths:
        StandardLocation = QStandardPaths.StandardLocation

        @staticmethod
        def standardLocations(_location):
            return [str(folder)]

    monkeypatch.setattr(ncd, "QStandardPaths", FakePaths)
    return folder


@pytest.fixture
def made(qtbot, tmp_path, docs):
    """Build a dialog with fakes; returns (factory, recorder)."""
    rec = Recorder()

    def make(**kwargs) -> NewCollectionDialog:
        options = {
            "check": rec.check,
            "create": rec.create,
            "find_git": lambda root: Path("git"),
            "app_dir": tmp_path / "app",
            "environ": {},
        }
        options.update(kwargs)
        dialog = NewCollectionDialog(**options)
        qtbot.addWidget(dialog)
        return dialog

    return make, rec


def settle(qtbot, dialog: NewCollectionDialog):
    qtbot.waitUntil(lambda: not dialog._pending, timeout=30000)


def labels(dialog: NewCollectionDialog) -> list[str]:
    return [label.text() for label in dialog._issue_labels()]


def test_defaults(made, docs):
    make, _ = made
    dialog = make()
    assert dialog.windowTitle() == "New Collection"
    assert dialog.minimumWidth() == 560
    assert dialog.windowModality() == Qt.WindowModality.WindowModal
    assert dialog._parent_edit.text() == str(docs)
    assert dialog._name_edit.text() == "KiCad_Libraries"
    assert dialog._heading.text() == "Create a new library collection"
    assert dialog._body.text() == (
        "A collection is the folder that holds your own symbols, footprints and 3D models. "
        "Nothing is created until you click Create Collection."
    )
    assert dialog._parent_edit.accessibleName() == "Parent folder"
    assert dialog._name_edit.accessibleName() == "Collection name"
    assert dialog._preview.toPlainText().splitlines() == [
        "KiCad_Libraries/",
        "  Custom/            its own git repository (branch main)",
        "    Symbols/",
        "    Footprints/",
        "      Atomic_Footprints.pretty/",
        "    3DModels/",
        "    .gitignore",
        "    README.md",
    ]
    assert dialog._footnote.text() == (
        "Empty folders get a .gitkeep file so git keeps them. Nothing is committed for you."
    )
    assert "Cancel" not in [button.text() for button in dialog.findChildren(QPushButton)]
    assert dialog._create_btn.text() == "Create Collection"
    assert dialog._create_btn.minimumWidth() == 112
    assert not dialog._create_btn.autoDefault() and not dialog._create_btn.isDefault()
    assert not dialog._back_btn.autoDefault() and not dialog._back_btn.isDefault()


def test_focus_and_selection_on_the_name(made, qtbot):
    make, _ = made
    dialog = make()
    dialog.show()
    qtbot.waitUntil(lambda: dialog._name_edit.hasFocus() or dialog.focusWidget() is dialog._name_edit)
    assert dialog._name_edit.selectedText() == "KiCad_Libraries"


def test_documents_folder_falls_back_to_home(qtbot, tmp_path, monkeypatch):
    class NoPaths:
        StandardLocation = QStandardPaths.StandardLocation

        @staticmethod
        def standardLocations(_location):
            return []

    monkeypatch.setattr(ncd, "QStandardPaths", NoPaths)
    rec = Recorder()
    dialog = NewCollectionDialog(check=rec.check, create=rec.create, find_git=lambda root: Path("git"))
    qtbot.addWidget(dialog)
    assert dialog._parent_edit.text() == str(Path.home())


@pytest.mark.parametrize(
    "origin,text",
    [("main", "Keep Current Folder"), ("choose", "Back to Open"), ("setup", "Back to Setup")],
)
def test_back_button_text_by_origin(made, qtbot, origin, text):
    make, rec = made
    dialog = make(origin=origin)
    settle(qtbot, dialog)
    assert dialog._back_btn.text() == text
    calls = len(rec.checks)
    dialog._back_btn.click()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert len(rec.checks) == calls and rec.creates == []
    assert dialog.created_folder() is None


def test_prefilled_from_choose(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10_000)
    (tmp_path / "Empty").mkdir()
    dialog = NewCollectionDialog(
        origin="choose",
        parent_folder=tmp_path,
        name="Empty",
        find_git=lambda root: Path("git"),
        app_dir=tmp_path / "app",
        environ={},
    )
    qtbot.addWidget(dialog)
    settle(qtbot, dialog)
    assert dialog._parent_edit.text() == str(tmp_path) and dialog._name_edit.text() == "Empty"
    assert labels(dialog) == ["This folder already exists and is empty. It will be used."]
    assert dialog._create_btn.isEnabled()


def test_rows_render_with_glyphs(made, qtbot):
    make, rec = made
    rec.rows_for = lambda parent, name: (
        (CheckRow("fail", "Nope."), CheckRow("warn", "Careful."), CheckRow("plain", "Fyi."))
        if name == "bad"
        else (CheckRow("warn", "Careful."),)
    )
    dialog = make()
    dialog._name_edit.setText("bad")
    settle(qtbot, dialog)
    shown = dialog._issue_labels()
    assert [label.text() for label in shown] == ["✖ Nope.", "⚠ Careful.", "Fyi."]
    assert ERROR in shown[0].styleSheet() and AMBER in shown[1].styleSheet() and shown[2].styleSheet() == ""
    assert [label.accessibleName() for label in shown] == [label.text() for label in shown]
    assert all(label.textFormat() == Qt.TextFormat.PlainText for label in shown)
    assert not dialog._create_btn.isEnabled()
    dialog._name_edit.setText("fine")
    settle(qtbot, dialog)
    assert labels(dialog) == ["⚠ Careful."]
    assert dialog._create_btn.isEnabled()


def test_no_rows_hides_the_strip(made, qtbot):
    make, _ = made
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    assert labels(dialog) == [] and dialog._strip.isHidden()
    assert dialog._create_btn.isEnabled()


def test_check_is_debounced_and_off_thread(made, qtbot):
    make, rec = made
    dialog = make()
    dialog._name_edit.setText("a")
    dialog._name_edit.setText("ab")
    dialog._name_edit.setText("abc")
    assert not dialog._create_btn.isEnabled()  # a check is pending
    qtbot.wait(100)
    assert rec.checks == []
    qtbot.waitUntil(lambda: len(rec.checks) == 1, timeout=3000)
    settle(qtbot, dialog)
    qtbot.wait(450)
    assert [name for _, name, _ in rec.checks] == ["abc"]
    assert rec.threads[0] != GUI_THREAD
    assert dialog._create_btn.isEnabled()


def test_stale_result_is_ignored(made, qtbot):
    make, rec = made
    release = threading.Event()
    rec.slow["slow"] = release
    rec.rows_for = lambda parent, name: (CheckRow("fail", f"row for {name}"),)
    dialog = make()
    try:
        dialog._name_edit.setText("slow")
        qtbot.waitUntil(lambda: ("slow" in [name for _, name, _ in rec.checks]), timeout=3000)
        dialog._name_edit.setText("fast")
        qtbot.waitUntil(lambda: labels(dialog) == ["✖ row for fast"], timeout=3000)
    finally:
        release.set()
    qtbot.waitUntil(lambda: all(task.is_done() for task in dialog._tasks), timeout=30000)
    qtbot.wait(50)
    assert labels(dialog) == ["✖ row for fast"]


def test_git_found_is_detected_each_check(made, qtbot):
    make, rec = made
    seen = []

    def find_git(root):
        seen.append(root)
        return Path("git") if len(seen) < 3 else Issue(Severity.WARNING, "git.not_found", "git was not found on PATH")

    dialog = make(find_git=find_git)
    settle(qtbot, dialog)
    dialog._name_edit.setText("two")
    settle(qtbot, dialog)
    dialog._name_edit.setText("three")
    settle(qtbot, dialog)
    assert len(seen) == len(rec.checks) >= 3
    assert [found for _, _, found in rec.checks][-1] is False and rec.checks[0][2] is True


def test_create_success_accepts(made, qtbot):
    make, rec = made
    rec.gate = threading.Event()
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    dialog._create_btn.click()
    try:
        assert dialog._create_btn.text() == "Creating..." and not dialog._create_btn.isEnabled()
        assert not dialog._parent_edit.isEnabled() and not dialog._name_edit.isEnabled()
        assert not dialog._browse_btn.isEnabled()
        assert dialog._progress.isVisible()
        assert dialog._progress.minimum() == 0 and dialog._progress.maximum() == 0
        assert dialog._strip.isHidden()
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
        dialog._back_btn.click()
        dialog.reject()
        dialog.close()
        assert dialog.isVisible() and dialog._creating
        # No close path cancelled the creation task
        assert dialog._tasks and all(task.is_running() and not task.is_done() for task in dialog._tasks[-1:])
    finally:
        with qtbot.waitSignal(dialog.accepted, timeout=30000):
            rec.gate.set()
    assert dialog.created_folder() == Path(dialog._parent_edit.text()) / "KiCad_Libraries"
    assert rec.creates == [dialog.created_folder()]
    assert rec.threads[-1] != GUI_THREAD


def test_ctrl_return_creates_only_when_enabled(made, qtbot):
    make, rec = made
    dialog = make()
    assert dialog._create_shortcut.key().toString() == "Ctrl+Return"
    dialog._name_edit.setText("later")  # a check is pending: Create is disabled
    dialog._create_shortcut.activated.emit()
    assert rec.creates == []
    settle(qtbot, dialog)
    with qtbot.waitSignal(dialog.accepted, timeout=30000):
        dialog._create_shortcut.activated.emit()
    assert rec.creates == [Path(dialog._parent_edit.text()) / "later"]


def test_create_failure_keeps_dialog_open(made, qtbot):
    make, rec = made
    target_text = []
    rec.create_result = [
        Issue(Severity.ERROR, "collection.create_failed", FAILED),
        Issue(Severity.ERROR, "collection.leftovers", LEFT.format(path="X")),
    ]
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    target_text.append(dialog._will_create.full_text())
    dialog._create_btn.click()
    qtbot.waitUntil(lambda: len(labels(dialog)) == 2, timeout=30000)
    assert labels(dialog) == ["✖ " + FAILED, "✖ " + LEFT.format(path="X")]
    assert dialog._parent_edit.isEnabled() and dialog._name_edit.isEnabled() and dialog._browse_btn.isEnabled()
    assert dialog._create_btn.text() == "Create Collection" and not dialog._create_btn.isEnabled()
    assert dialog._progress.isHidden() and not dialog._strip.isHidden()
    assert dialog.isVisible() and dialog.created_folder() is None
    # an edit clears the failure and checks again
    dialog._name_edit.setText("other")
    settle(qtbot, dialog)
    assert labels(dialog) == [] and dialog._create_btn.isEnabled()


def test_create_that_raises_shows_the_step_failure(made, qtbot):
    make, rec = made
    rec.create_result = RuntimeError("boom")
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    dialog._create_btn.click()
    qtbot.waitUntil(lambda: labels(dialog) == ["✖ Library folder step failed: RuntimeError: boom"], timeout=30000)
    assert dialog.isVisible() and dialog._name_edit.isEnabled()


def test_missing_git_at_create_time_stops(made, qtbot):
    make, rec = made
    state = {"found": True}

    def find_git(root):
        return Path("git") if state["found"] else Issue(Severity.WARNING, "git.not_found", "git was not found on PATH")

    dialog = make(find_git=find_git)
    settle(qtbot, dialog)
    state["found"] = False
    dialog._create_btn.click()
    qtbot.waitUntil(lambda: labels(dialog) == ["✖ " + NO_GIT], timeout=30000)
    assert rec.creates == [] and dialog.created_folder() is None


def test_browse_cancel_keeps_field(made, qtbot, monkeypatch, tmp_path):
    make, rec = made
    dialog = make()
    settle(qtbot, dialog)
    before = dialog._parent_edit.text()
    answers = {"value": ""}

    class FakeFiles:
        started: list[str] = []

        @staticmethod
        def getExistingDirectory(parent, caption, start="", *args, **kwargs):
            FakeFiles.started.append(start)
            return answers["value"]

    monkeypatch.setattr(ncd, "QFileDialog", FakeFiles)
    dialog._browse_btn.click()
    assert dialog._parent_edit.text() == before and FakeFiles.started == [before]
    other = tmp_path / "Other"
    other.mkdir()
    answers["value"] = str(other)
    calls = len(rec.checks)
    dialog._browse_btn.click()
    assert Path(dialog._parent_edit.text()) == other
    qtbot.waitUntil(lambda: len(rec.checks) > calls, timeout=250)  # at once, not after the 300 ms debounce
    assert rec.checks[-1][0] == dialog._parent_edit.text()


def test_long_target_is_elided(made, qtbot):
    make, rec = made
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    width = dialog.width()
    long_name = "x" * 200
    dialog._name_edit.setText(long_name)
    settle(qtbot, dialog)
    qtbot.wait(50)
    full = str(Path(dialog._parent_edit.text()) / long_name)
    assert dialog._will_create.full_text() == full and dialog._will_create.toolTip() == full
    assert len(dialog._will_create.text()) < len(full)
    assert dialog.width() == width
    assert dialog._preview.toPlainText().splitlines()[0] == long_name + "/"


def test_checks_are_cancelled_on_close(made, qtbot):
    make, rec = made
    release = threading.Event()
    rec.slow["closing"] = release
    dialog = make()
    dialog._name_edit.setText("closing")
    qtbot.waitUntil(lambda: any(name == "closing" for _, name, _ in rec.checks), timeout=3000)
    tasks = list(dialog._tasks)
    assert any(task.is_running() for task in tasks)
    started = time.monotonic()
    try:
        dialog.close()  # a check is still blocked: close cancels it and does not wait
        assert time.monotonic() - started < 1.0
        assert all(task.is_done() for task in tasks)
    finally:
        release.set()
    qtbot.waitUntil(lambda: all(not task.is_running() for task in tasks), timeout=30000)
    qtbot.wait(50)
    assert dialog._pending  # the late answer redrew nothing


def test_a_dot_parent_gives_an_absolute_target(made, qtbot, tmp_path, monkeypatch):
    """CR-02: the real check run for parent "." names the working directory, not a relative path."""
    make, _ = made
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    dialog = make(check=collection.check_new_collection)
    dialog._parent_edit.setText(".")
    dialog._name_edit.setText("Libs2")
    settle(qtbot, dialog)
    assert dialog._target == work / "Libs2" and dialog._target.is_absolute()


def test_is_creating_follows_the_worker(made, qtbot):
    """WR-05: parents ask the dialog whether they may close."""
    make, rec = made
    rec.gate = threading.Event()
    dialog = make()
    dialog.show()
    settle(qtbot, dialog)
    assert dialog.is_creating() is False
    dialog._create_btn.click()
    try:
        assert dialog.is_creating() is True
    finally:
        with qtbot.waitSignal(dialog.accepted, timeout=30000):
            rec.gate.set()
    assert dialog.is_creating() is False
