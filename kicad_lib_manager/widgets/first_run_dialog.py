"""The first-run window (Phase 15, ROOT-05): shown at startup when no library folder resolved.

Three plain choices (KiCad's folder, an existing collection, a new collection) or Quit. Application-modal
because there is no main window yet. The window writes no setting and prints nothing: the caller reads
choice() (None when the user quit) and does both (plan 15-10). Every check runs on a background daemon thread (widgets/background.py); a close cancels it and never waits.
"""

import html
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont, QGuiApplication, QShowEvent
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
)

from ..collection import FolderCheck, Source, check_folder
from . import theme
from .choose_folder_dialog import ChooseLibraryFolderDialog
from .background import BackgroundTask, run_in_background
from .new_collection_dialog import NewCollectionDialog, child_is_creating

_BODY = (
    "This app works on one library folder: the folder that holds your Custom libraries. "
    "Choose how to set it up. Nothing is created or changed until you confirm."
)
_NO_KICAD_FOLDER = "KiCad does not name a library folder yet (KICAD_LIB_GITHUB is not set)."
_ROW2_TEXT = "Pick a folder that already has a Custom folder with Symbols or Footprints inside it."
_ROW3_TEXT = "Start with an empty collection and import your first part into it."
_MIN_CONTROL_HEIGHT = 28
_WIDTH = 560


@dataclass(frozen=True)
class FirstRunChoice:
    path: Path
    source: Source
    created: bool = False


class FirstRunDialog(QDialog):
    def __init__(
        self,
        kicad_folder: str | None,
        notice: str | None = None,
        *,
        check: Callable = check_folder,
        choose: Callable = ChooseLibraryFolderDialog,
        new_collection: Callable = NewCollectionDialog,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Set Up Your Library Folder")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedWidth(_WIDTH)

        self._kicad_folder = kicad_folder.strip() if kicad_folder and kicad_folder.strip() else None
        self._check_fn = check
        self._choose = choose
        self._new_collection = new_collection
        self._choice: FirstRunChoice | None = None
        self._checking = False  # the row 1 check is running
        self._tasks: list[BackgroundTask] = []
        self._sub_dialog = None
        self._closing = False
        self._placed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        outer.setSpacing(theme.SP_SM)

        self._heading = QLabel("Where are your KiCad libraries?")
        font = self._heading.font()
        font.setPointSize(theme.HEADING_PT)
        font.setBold(True)
        self._heading.setFont(font)
        outer.addWidget(self._heading)

        self._body = QLabel(_BODY)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: {theme.MUTED};")
        outer.addWidget(self._body)
        outer.addSpacing(theme.SP_LG - theme.SP_SM)  # 24 px between the heading block and what follows

        self._notice_strip: QFrame | None = None
        if notice:
            self._notice_strip = QFrame()
            self._notice_strip.setObjectName("noticeStrip")
            self._notice_strip.setStyleSheet(
                f"QFrame#noticeStrip {{ background-color: {theme.AMBER_TINT}; border-left: 2px solid {theme.AMBER}; }}"
            )
            strip_layout = QHBoxLayout(self._notice_strip)
            strip_layout.setContentsMargins(theme.SP_MD, theme.SP_SM, theme.SP_SM, theme.SP_SM)
            self._notice_label = QLabel(f"⚠ {notice}")
            self._notice_label.setTextFormat(Qt.TextFormat.PlainText)
            self._notice_label.setWordWrap(True)
            self._notice_label.setAccessibleName(f"⚠ {notice}")
            self._notice_label.setStyleSheet(f"color: {theme.AMBER};")
            _ignore_width(self._notice_label)
            strip_layout.addWidget(self._notice_label, 1)
            outer.addWidget(self._notice_strip)

        # row 1: KiCad's folder
        if self._kicad_folder is not None:
            mono = QFont(theme.MONO_FAMILY, theme.MONO_PT)
            description = (
                "KiCad's settings name "
                f"<span style=\"font-family: '{mono.family()}';\">{html.escape(self._kicad_folder)}</span>"
                " as its library folder."
            )
            row1_plain = f"KiCad's settings name {self._kicad_folder} as its library folder."
        else:
            description = ""
            row1_plain = _NO_KICAD_FOLDER
        self._row1, self._row1_desc, self._row1_btn, self._row1_error = self._option(
            outer, "Use KiCad's folder", description or row1_plain, "Use KiCad's Folder",
            rich=self._kicad_folder is not None,
        )
        self._row1_desc.setAccessibleName(row1_plain)
        if self._kicad_folder is None:
            self._row1_btn.setEnabled(False)
        self._row1_btn.clicked.connect(self._on_use_kicad)

        # row 2: an existing collection
        self._row2, _desc2, self._row2_btn, _err2 = self._option(
            outer, "Open an existing collection", _ROW2_TEXT, "Open Library Collection..."
        )
        self._row2_btn.clicked.connect(self._on_choose)

        # row 3: a new collection
        self._row3, _desc3, self._row3_btn, _err3 = self._option(
            outer, "Create a new collection", _ROW3_TEXT, "New Library Collection..."
        )
        self._row3_btn.clicked.connect(self._on_new)

        box = QDialogButtonBox()
        self._quit_btn = box.addButton("Quit", QDialogButtonBox.ButtonRole.RejectRole)
        self._quit_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._quit_btn.setAutoDefault(False)
        self._quit_btn.setDefault(False)
        box.rejected.connect(self.reject)
        outer.addWidget(box)

        self.setTabOrder(self._row1_btn, self._row2_btn)
        self.setTabOrder(self._row2_btn, self._row3_btn)
        self.setTabOrder(self._row3_btn, self._quit_btn)
        self._focus_first_option()

    # ── building ────────────────────────────────────────────────────────────

    def _option(self, outer: QVBoxLayout, title: str, description: str, button_text: str, *, rich: bool = False):
        """One framed option row; returns (frame, description label, button, error label)."""
        frame = QFrame()
        frame.setObjectName("optionRow")
        frame.setStyleSheet(
            f"QFrame#optionRow {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; }}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(theme.SP_MD, theme.SP_SM, theme.SP_MD, theme.SP_SM)
        layout.setSpacing(theme.SP_SM)

        text_block = QVBoxLayout()
        text_block.setContentsMargins(0, 0, 0, 0)
        text_block.setSpacing(theme.SP_XS)
        title_label = QLabel(title)
        title_label.setTextFormat(Qt.TextFormat.PlainText)
        title_font = title_label.font()
        title_font.setPointSize(theme.HEADING_PT)
        title_font.setBold(True)
        title_label.setFont(title_font)
        text_block.addWidget(title_label)
        desc = QLabel()
        desc.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        desc.setText(description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.MUTED};")
        _ignore_width(desc)
        text_block.addWidget(desc)
        error = QLabel()
        error.setTextFormat(Qt.TextFormat.PlainText)
        error.setWordWrap(True)
        error.setStyleSheet(f"color: {theme.ERROR};")
        _ignore_width(error)
        error.hide()
        text_block.addWidget(error)
        layout.addLayout(text_block, 1)

        button = QPushButton(button_text)
        button.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        button.setAutoDefault(False)
        button.setDefault(False)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addWidget(frame)
        return frame, desc, button, error

    def _focus_first_option(self):
        for button in (self._row1_btn, self._row2_btn, self._row3_btn):
            if button.isEnabled():
                button.setFocus()
                return

    # ── public ──────────────────────────────────────────────────────────────

    def choice(self) -> FirstRunChoice | None:
        """What the user chose, or None when the window was closed with Quit, Esc or the close box."""
        return self._choice

    # ── row 1: KiCad's folder ───────────────────────────────────────────────

    def _on_use_kicad(self):
        if self._checking or self._kicad_folder is None or self._closing:
            return  # a second click while the check runs starts nothing new
        self._checking = True
        self._row1_btn.setEnabled(False)
        self._row1_error.hide()
        folder = Path(self._kicad_folder)
        check = self._check_fn

        self._run(lambda: check(folder), self._on_kicad_checked, self._on_kicad_failed)

    def _on_kicad_checked(self, result: FolderCheck):
        if self._closing:
            return
        self._checking = False
        self._row1_btn.setEnabled(True)
        if result.usable:
            self._finish(FirstRunChoice(Path(result.path), Source.KICAD, False))
        elif result.can_create_here:
            self._open_new(result.path.parent, result.path.name)
        else:
            self._show_row1_error(result.reason or "This folder cannot be used.")

    def _on_kicad_failed(self, text: str):
        if self._closing:
            return
        self._checking = False
        self._row1_btn.setEnabled(True)
        self._show_row1_error(f"Library folder step failed: {text}")

    def _show_row1_error(self, reason: str):
        text = f"✖ {reason}"
        self._row1_error.setText(text)
        self._row1_error.setAccessibleName(text)
        self._row1_error.show()

    # ── rows 2 and 3 ────────────────────────────────────────────────────────

    def _on_choose(self):
        if self._sub_dialog is not None or self._closing:
            return
        dialog = self._choose(None, origin="setup", parent=self)
        self._sub_dialog = dialog
        dialog.finished.connect(self._on_choose_finished)
        dialog.open()

    def _on_choose_finished(self, code: int):
        dialog, self._sub_dialog = self._sub_dialog, None
        if dialog is None or code != int(QDialog.DialogCode.Accepted):
            return  # Back to Setup: this window stays open
        folder = dialog.chosen_folder()
        if folder is not None:
            self._finish(FirstRunChoice(Path(folder), Source.CHOSEN, bool(dialog.created())))

    def _on_new(self):
        self._open_new(None, None)

    def _open_new(self, parent_folder: Path | None, name: str | None):
        if self._sub_dialog is not None or self._closing:
            return
        kwargs = {"origin": "setup", "parent": self}
        if parent_folder is not None:
            kwargs["parent_folder"] = parent_folder
            kwargs["name"] = name
        dialog = self._new_collection(**kwargs)
        self._sub_dialog = dialog
        dialog.finished.connect(self._on_new_finished)
        dialog.open()

    def _on_new_finished(self, code: int):
        dialog, self._sub_dialog = self._sub_dialog, None
        if dialog is None or code != int(QDialog.DialogCode.Accepted):
            return
        folder = dialog.created_folder()
        if folder is not None:
            self._finish(FirstRunChoice(Path(folder), Source.CHOSEN, True))

    def _finish(self, choice: FirstRunChoice):
        self._choice = choice
        self.accept()

    # ── background checks and closing ───────────────────────────────────────

    def _run(self, fn: Callable, on_result: Callable, on_failed: Callable) -> BackgroundTask:
        """A check on a daemon thread owned by the window; a close cancels it and never waits for it."""
        self._tasks = [task for task in self._tasks if not task.is_done()]
        task = run_in_background(fn, on_result, on_failed, name="first-run-check")
        self._tasks.append(task)
        return task

    def _cancel_tasks(self):
        for task in self._tasks:
            task.cancel()
        self._tasks = []

    def is_creating(self) -> bool:
        """True while a collection is being created in a window over this one (nothing may close us)."""
        return child_is_creating(self._sub_dialog)

    def done(self, result: int):
        if self.is_creating():
            return  # the child's worker is writing files: it must not be destroyed with this window
        self._closing = True
        self._cancel_tasks()
        super().done(result)

    def closeEvent(self, event: QCloseEvent):
        if self.is_creating():
            event.ignore()
            return
        self._closing = True
        self._cancel_tasks()
        super().closeEvent(event)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if not self._placed:
            self._placed = True
            self._focus_first_option()
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                frame = self.frameGeometry()
                frame.moveCenter(screen.availableGeometry().center())
                self.move(frame.topLeft())


def _ignore_width(label: QLabel) -> None:
    """A long unbroken path never widens the window: the label's width comes from the layout."""
    policy = label.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
    label.setSizePolicy(policy)
