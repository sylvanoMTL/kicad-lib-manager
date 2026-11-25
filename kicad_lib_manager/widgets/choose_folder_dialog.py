"""The Open Library Collection dialog (Phase 15, ROOT-03 and ROOT-07): type or browse to a folder, see why it can
or cannot be opened, and hand an empty folder to New Library Collection.

One window-modal dialog (the caller uses open()). The folder check runs on a background daemon thread (widgets/background.py), so a slow or
unreachable drive never freezes the window and never delays closing (a close cancels the check and never waits): it starts 300 ms after the last edit, a result that is not the newest
request is dropped, and while it runs the strip says so and Open Collection is disabled. The dialog switches
nothing and writes no setting; the caller reads chosen_folder() and created() (plan 15-10).
"""

import html
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSizePolicy,
    QVBoxLayout,
)

from ..collection import CheckRow, FolderCheck, check_folder
from . import theme
from .background import BackgroundTask, run_in_background
from .new_collection_dialog import NewCollectionDialog, child_is_creating, fit_height_to_content

DEBOUNCE_MS = 300
_BACK_TEXT = {"main": "Keep Current Folder", "setup": "Back to Setup"}
_BODY = (
    "Pick a folder that already holds a library collection. "
    "To start a new one, use New Library Collection... instead."
)
_MIN_CONTROL_HEIGHT = 28


class ChooseLibraryFolderDialog(QDialog):
    def __init__(
        self,
        current: Path | None,
        *,
        origin: str = "main",
        check: Callable = check_folder,
        new_collection: Callable = NewCollectionDialog,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Open Library Collection")
        self.setMinimumWidth(560)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        self._current = Path(current) if current is not None else None
        self._check_fn = check
        self._new_collection = new_collection
        self._chosen: Path | None = None
        self._created = False
        self._result: FolderCheck | None = None
        self._failure_rows: list[CheckRow] = []
        self._pending = False  # a check is scheduled or running for the newest text
        self._request = 0  # the newest request; an older result is dropped
        self._tasks: list[BackgroundTask] = []
        self._new_dialog = None
        self._closing = False
        self._focused = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        outer.setSpacing(theme.SP_SM)

        self._heading = QLabel("Open a library collection")
        font = self._heading.font()
        font.setPointSize(theme.HEADING_PT)
        font.setBold(True)
        self._heading.setFont(font)
        outer.addWidget(self._heading)

        self._body = QLabel(_BODY)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: {theme.MUTED};")
        outer.addWidget(self._body)

        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(theme.SP_SM)
        folder_row.addWidget(QLabel("Folder"))
        self._field = QLineEdit(str(self._current) if self._current is not None else "")
        self._field.setAccessibleName("Library folder")
        self._field.setPlaceholderText("Choose a folder")
        self._field.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        folder_row.addWidget(self._field, 1)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        folder_row.addWidget(self._browse_btn)
        outer.addLayout(folder_row)

        self._strip = QFrame()
        self._strip.setObjectName("checkStrip")
        self._strip.setStyleSheet(
            f"QFrame#checkStrip {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; }}"
        )
        self._strip_layout = QVBoxLayout(self._strip)
        self._strip_layout.setContentsMargins(theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM)
        self._strip_layout.setSpacing(theme.SP_XS)
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(theme.SP_XS)
        self._strip_layout.addLayout(self._rows_layout)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.hide()
        self._strip_layout.addWidget(self._progress)
        self._strip.hide()
        outer.addWidget(self._strip)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(theme.SP_SM)
        self._create_here_btn = QPushButton("New Library Collection...")
        self._create_here_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._create_here_btn.hide()
        buttons.addWidget(self._create_here_btn)
        buttons.addStretch(1)
        self._back_btn = QPushButton(_BACK_TEXT.get(origin, _BACK_TEXT["main"]))
        self._back_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._use_btn = QPushButton("Open Collection")
        self._use_btn.setStyleSheet(theme.PRIMARY_BUTTON_QSS)
        self._use_btn.setMinimumWidth(112)
        self._use_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._use_btn.setEnabled(False)
        buttons.addWidget(self._back_btn)
        buttons.addWidget(self._use_btn)
        outer.addLayout(buttons)
        for button in (self._browse_btn, self._create_here_btn, self._back_btn, self._use_btn):
            button.setAutoDefault(False)
            button.setDefault(False)

        self._browse_btn.clicked.connect(self._on_browse)
        self._create_here_btn.clicked.connect(self._on_create_here)
        self._back_btn.clicked.connect(self.reject)
        self._use_btn.clicked.connect(self._on_use)

        self._use_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self._use_shortcut.activated.connect(self._on_use_shortcut)

        self.setTabOrder(self._field, self._browse_btn)
        self.setTabOrder(self._browse_btn, self._create_here_btn)
        self.setTabOrder(self._create_here_btn, self._back_btn)
        self.setTabOrder(self._back_btn, self._use_btn)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._start_check)

        self._field.setFocus()
        self._field.textChanged.connect(self._on_edited)
        self._field.returnPressed.connect(lambda: self._schedule_check(0))
        self._schedule_check(0)  # the first check does not wait for the debounce

    # ── public ──────────────────────────────────────────────────────────────

    def chosen_folder(self) -> Path | None:
        """The folder after Open Collection or a created collection, else None."""
        return self._chosen

    def created(self) -> bool:
        """True when the chosen folder is a collection created from this dialog."""
        return self._created

    # ── test and layout helpers ─────────────────────────────────────────────

    def _row_labels(self) -> list[QLabel]:
        found = []
        for index in range(self._rows_layout.count()):
            widget = self._rows_layout.itemAt(index).widget()
            if isinstance(widget, QLabel):
                found.append(widget)
        return found

    # ── editing and checking ────────────────────────────────────────────────

    def _on_edited(self, _text: str = ""):
        self._failure_rows = []
        self._schedule_check(DEBOUNCE_MS)

    def _schedule_check(self, delay_ms: int):
        """Mark a check as pending (any result in flight is now stale) and start it after delay_ms."""
        self._request += 1
        self._failure_rows = []
        self._result = None
        if not self._field.text().strip():
            self._debounce.stop()
            self._pending = False  # a blank field is not checked
        else:
            self._pending = True
            self._debounce.start(delay_ms)
        self._draw()

    def _start_check(self):
        if self._closing:
            return
        request = self._request
        text = self._field.text().strip()
        check, current = self._check_fn, self._current

        self._run(
            lambda: check(Path(text), current=current),
            lambda result, r=request: self._on_checked(r, result),
            lambda failure, r=request: self._on_check_failed(r, failure),
        )

    def _on_checked(self, request: int, result: FolderCheck):
        if request != self._request or self._closing:
            return  # a newer edit has been made since this check started
        self._result = result
        self._pending = False
        self._draw()

    def _on_check_failed(self, request: int, text: str):
        if request != self._request or self._closing:
            return
        self._result = None
        self._failure_rows = [CheckRow("fail", f"Library folder step failed: {text}")]
        self._pending = False
        self._draw()

    def _make_label(self, row: CheckRow) -> QLabel:
        label = QLabel()
        if row.hint:
            # Both parts are escaped: a path in a row shows as typed, only the hint is muted
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setText(
                f"{html.escape(row.shown)}<span style=\"color: {theme.MUTED};\">{html.escape(row.hint)}</span>"
            )
        else:
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setText(row.shown)
        label.setWordWrap(True)
        label.setAccessibleName(row.shown + row.hint)
        if row.kind == "fail":
            label.setStyleSheet(f"color: {theme.ERROR};")
        elif row.kind == "warn":
            label.setStyleSheet(f"color: {theme.AMBER};")
        # A long unbroken path never widens the dialog: the strip grows in height only
        policy = label.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        label.setSizePolicy(policy)
        return label

    def _draw(self):
        """Show the rows of the newest check (or Checking...) and set the buttons."""
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        blank = not self._field.text().strip()
        if blank:
            rows: list[CheckRow] = []
        elif self._pending:
            rows = []
        elif self._failure_rows:
            rows = list(self._failure_rows)
        else:
            rows = list(self._result.rows) if self._result is not None else []
        if self._pending and not blank:
            checking = QLabel("Checking the folder...")
            checking.setTextFormat(Qt.TextFormat.PlainText)
            checking.setStyleSheet(f"color: {theme.MUTED};")
            checking.setAccessibleName("Checking the folder...")
            self._rows_layout.addWidget(checking)
            checking.show()  # a child made on a shown dialog stays hidden until a queued call, and a hidden one is not laid out
        for row in rows:
            label = self._make_label(row)
            self._rows_layout.addWidget(label)
            label.show()
        self._progress.setVisible(self._pending and not blank)
        self._strip.setVisible(not blank and (self._pending or bool(rows)))
        settled = not self._pending and self._result is not None
        self._use_btn.setEnabled(settled and self._result.state == "collection")
        self._create_here_btn.setVisible(settled and self._result.can_create_here)
        fit_height_to_content(self)

    # ── browse ──────────────────────────────────────────────────────────────

    def _on_browse(self):
        start = self._field.text().strip()
        folder = Path(start) if start else None
        while folder is not None and not folder.is_dir():
            folder = folder.parent if folder.parent != folder else None
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose the library folder", str(folder) if folder is not None else str(Path.home())
        )
        if not chosen:
            return  # closed without a choice: nothing changes
        self._field.setText(str(Path(chosen)))
        self._schedule_check(0)

    # ── using the folder ────────────────────────────────────────────────────

    def _on_use_shortcut(self):
        if self._use_btn.isEnabled():
            self._on_use()

    def _on_use(self):
        if not self._use_btn.isEnabled() or self._result is None:
            return
        self._chosen = self._result.path
        self._created = False
        self.accept()

    # ── a new collection in an empty folder ─────────────────────────────────

    def _on_create_here(self):
        if self._new_dialog is not None or self._result is None or not self._result.can_create_here:
            return
        folder = self._result.path
        dialog = self._new_collection(origin="choose", parent_folder=folder.parent, name=folder.name, parent=self)
        self._new_dialog = dialog
        dialog.finished.connect(self._on_new_collection_finished)
        dialog.open()

    def _on_new_collection_finished(self, code: int):
        dialog, self._new_dialog = self._new_dialog, None
        if dialog is None or code != int(QDialog.DialogCode.Accepted):
            return  # Back to Open: this dialog stays as it was
        folder = dialog.created_folder()
        if folder is None:
            return
        self._chosen = Path(folder)
        self._created = True
        self.accept()

    # ── background checks and closing ───────────────────────────────────────

    def _run(self, fn: Callable, on_result: Callable, on_failed: Callable) -> BackgroundTask:
        """A check on a daemon thread owned by the dialog; a close cancels it and never waits for it."""
        self._tasks = [task for task in self._tasks if not task.is_done()]
        task = run_in_background(fn, on_result, on_failed, name="choose-folder-check")
        self._tasks.append(task)
        return task

    def _cancel_tasks(self):
        for task in self._tasks:
            task.cancel()
        self._tasks = []

    def is_creating(self) -> bool:
        """True while the New Collection window over this one is writing a collection (nothing may close us)."""
        return child_is_creating(self._new_dialog)

    def done(self, result: int):
        if self.is_creating():
            return  # the child's worker is writing files: it must not be destroyed with this dialog
        self._closing = True
        self._debounce.stop()
        self._cancel_tasks()
        super().done(result)

    def closeEvent(self, event: QCloseEvent):
        if self.is_creating():
            event.ignore()
            return
        self._closing = True
        self._debounce.stop()
        self._cancel_tasks()
        super().closeEvent(event)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if not self._focused:
            self._focused = True
            self._field.setFocus()
        fit_height_to_content(self)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            fit_height_to_content(self)
