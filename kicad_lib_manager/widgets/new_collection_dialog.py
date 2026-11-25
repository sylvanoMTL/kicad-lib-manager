"""The New Collection dialog (Phase 15, ROOT-06): pick a parent folder and a name, review, create.

One window-modal dialog (the caller uses open()). Every check and the creation itself run on a
background daemon thread (widgets/background.py), so the GUI never blocks on a slow drive: the check starts 300 ms after the last
edit, a result that is not the newest request is dropped, and while a creation runs the form is
disabled and the back button, Esc and the close box are ignored. Nothing is created before
Create Collection, and nothing is committed afterwards (D4).
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QStandardPaths, QTimer
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from .. import gitops
from ..collection import APP_DIR, CheckRow, check_new_collection, create_collection
from ..gitops import GitContext
from ..models import Issue, Severity
from . import theme
from .background import BackgroundTask, run_in_background
from .import_result import ElidedLabel

DEBOUNCE_MS = 300
DEFAULT_NAME = "KiCad_Libraries"
_BACK_TEXT = {"main": "Keep Current Folder", "choose": "Back to Open", "setup": "Back to Setup"}
_GIT_MISSING = (
    "Git was not found. A collection needs Git to commit your parts. Install Git for Windows, then try again."
)
_BODY = (
    "A collection is the folder that holds your own symbols, footprints and 3D models. "
    "Nothing is created until you click Create Collection."
)
_FOOTNOTE = "Empty folders get a .gitkeep file so git keeps them. Nothing is committed for you."
_PREVIEW_TAIL = (
    "  Custom/            its own git repository (branch main)",
    "    Symbols/",
    "    Footprints/",
    "      Atomic_Footprints.pretty/",
    "    3DModels/",
    "    .gitignore",
    "    README.md",
)
_MIN_CONTROL_HEIGHT = 28


def default_parent_folder() -> Path:
    """The Documents folder (the Qt standard location), else the home folder."""
    for text in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DocumentsLocation):
        if text and Path(text).is_dir():
            return Path(text)
    return Path.home()


def _preview_text(name: str) -> str:
    return "\n".join([f"{name or '<name>'}/", *_PREVIEW_TAIL])


def fit_height_to_content(dialog: QDialog) -> None:
    """Make the dialog at least as tall as its layout needs for its current width.

    An explicit minimum width stops the layout from raising the window's minimum height, and a top-level
    window does not apply height-for-width to itself, so a wrapped row keeps a one-line height and fixed-height
    children overlap. The minimum height is therefore set from the layout here: after every redraw, on show and
    when the width changes.
    """
    layout = dialog.layout()
    if layout is None or getattr(dialog, "_fitting", False):
        return  # the resize below must not start another fit
    dialog._fitting = True
    try:
        layout.activate()
        needed = layout.totalMinimumSize().height()
        if layout.hasHeightForWidth():
            needed = max(needed, layout.totalHeightForWidth(dialog.width()))
        dialog.setMinimumHeight(needed)
        if dialog.height() < needed:
            dialog.resize(dialog.width(), needed)
    finally:
        dialog._fitting = False


def child_is_creating(child) -> bool:
    """True when the child dialog is a New Collection dialog in the middle of creating (a stand-in without the method is not)."""
    return child is not None and bool(getattr(child, "is_creating", lambda: False)())


class NewCollectionDialog(QDialog):
    def __init__(
        self,
        *,
        origin: str = "choose",
        parent_folder: Path | None = None,
        name: str | None = None,
        check: Callable = check_new_collection,
        create: Callable = create_collection,
        find_git: Callable = gitops.find_git,
        app_dir: Path = APP_DIR,
        environ=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("New Collection")
        self.setMinimumWidth(560)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        self._check_fn = check
        self._create_fn = create
        self._find_git = find_git
        self._app_dir = app_dir
        self._environ = environ
        self._created: Path | None = None
        self._creating = False
        self._pending = True  # a check is scheduled or running for the newest edit
        self._request = 0  # the newest request; an older result is dropped
        self._failure_rows: list[CheckRow] = []
        self._check_rows: tuple[CheckRow, ...] = ()
        self._blocked = True
        self._target: Path | None = None
        self._tasks: list[BackgroundTask] = []
        self._closing = False
        self._focused = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        outer.setSpacing(theme.SP_SM)

        self._heading = QLabel("Create a new library collection")
        font = self._heading.font()
        font.setPointSize(theme.HEADING_PT)
        font.setBold(True)
        self._heading.setFont(font)
        outer.addWidget(self._heading)

        self._body = QLabel(_BODY)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: {theme.MUTED};")
        outer.addWidget(self._body)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(theme.SP_SM)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._parent_edit = QLineEdit(str(parent_folder if parent_folder is not None else default_parent_folder()))
        self._parent_edit.setAccessibleName("Parent folder")
        self._parent_edit.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._browse_btn.setAutoDefault(False)
        self._browse_btn.clicked.connect(self._on_browse)
        parent_row = QHBoxLayout()
        parent_row.setContentsMargins(0, 0, 0, 0)
        parent_row.setSpacing(theme.SP_SM)
        parent_row.addWidget(self._parent_edit, 1)
        parent_row.addWidget(self._browse_btn)
        form.addRow("Parent folder", parent_row)
        self._name_edit = QLineEdit(name if name is not None else DEFAULT_NAME)
        self._name_edit.setAccessibleName("Collection name")
        self._name_edit.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        form.addRow("Name", self._name_edit)
        outer.addLayout(form)

        mono = QFont(theme.MONO_FAMILY, theme.MONO_PT)
        will_row = QHBoxLayout()
        will_row.setContentsMargins(0, 0, 0, 0)
        will_row.setSpacing(theme.SP_SM)
        will_row.addWidget(QLabel("Will create:"))
        self._will_create = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
        self._will_create.setFont(mono)
        will_row.addWidget(self._will_create, 1)
        outer.addLayout(will_row)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFont(mono)
        self._preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._preview.setStyleSheet(f"QPlainTextEdit {{ background-color: {theme.SURFACE}; }}")
        self._preview.setAccessibleName("Preview of the new collection")
        document_margin = int(self._preview.document().documentMargin())
        self._preview.setFixedHeight(
            8 * self._preview.fontMetrics().lineSpacing() + 2 * self._preview.frameWidth() + 2 * document_margin + 2
        )
        outer.addWidget(self._preview)

        self._footnote = QLabel(_FOOTNOTE)
        self._footnote.setWordWrap(True)
        self._footnote.setStyleSheet(f"color: {theme.MUTED};")
        outer.addWidget(self._footnote)

        self._strip = QFrame()
        self._strip.setObjectName("issueStrip")
        self._strip.setStyleSheet(f"QFrame#issueStrip {{ border: 1px solid {theme.BORDER}; }}")
        self._strip_layout = QVBoxLayout(self._strip)
        self._strip_layout.setContentsMargins(theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM)
        self._strip_layout.setSpacing(theme.SP_XS)
        self._strip.hide()
        outer.addWidget(self._strip)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.hide()
        outer.addWidget(self._progress)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(theme.SP_SM)
        buttons.addStretch(1)
        self._back_btn = QPushButton(_BACK_TEXT.get(origin, _BACK_TEXT["choose"]))
        self._back_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._back_btn.clicked.connect(self.reject)
        self._create_btn = QPushButton("Create Collection")
        self._create_btn.setStyleSheet(theme.PRIMARY_BUTTON_QSS)
        self._create_btn.setMinimumWidth(112)
        self._create_btn.setMinimumHeight(_MIN_CONTROL_HEIGHT)
        self._create_btn.clicked.connect(self._on_create)
        for button in (self._back_btn, self._create_btn):
            button.setAutoDefault(False)
            button.setDefault(False)
            buttons.addWidget(button)
        outer.addLayout(buttons)
        self._create_btn.setEnabled(False)

        self._create_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self._create_shortcut.activated.connect(self._on_create_shortcut)

        self.setTabOrder(self._parent_edit, self._browse_btn)
        self.setTabOrder(self._browse_btn, self._name_edit)
        self.setTabOrder(self._name_edit, self._back_btn)
        self.setTabOrder(self._back_btn, self._create_btn)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._start_check)

        self._refresh_preview()
        self._name_edit.setFocus()
        self._name_edit.selectAll()
        self._parent_edit.textChanged.connect(self._on_edited)
        self._name_edit.textChanged.connect(self._on_edited)
        self._schedule_check(0)  # the first check does not wait for the debounce

    # ── public ──────────────────────────────────────────────────────────────

    def created_folder(self) -> Path | None:
        """The collection folder after a successful creation, else None."""
        return self._created

    def is_creating(self) -> bool:
        """True while the creation runs: files are being written, so no parent may close this dialog."""
        return self._creating

    # ── test and layout helpers ─────────────────────────────────────────────

    def _issue_labels(self) -> list[QLabel]:
        found = []
        for index in range(self._strip_layout.count()):
            widget = self._strip_layout.itemAt(index).widget()
            if isinstance(widget, QLabel):
                found.append(widget)
        return found

    # ── editing and checking ────────────────────────────────────────────────

    def _on_edited(self, _text: str = ""):
        self._failure_rows = []
        self._refresh_preview()
        self._schedule_check(DEBOUNCE_MS)

    def _refresh_preview(self):
        name = self._name_edit.text()
        self._preview.setPlainText(_preview_text(name))
        parent = self._parent_edit.text().strip()
        self._will_create.set_full_text(str(Path(parent) / name) if parent and name else "")

    def _schedule_check(self, delay_ms: int):
        """Mark a check as pending (any result in flight is now stale) and start it after delay_ms."""
        self._request += 1
        self._pending = True
        self._debounce.start(delay_ms)
        self._draw()

    def _start_check(self):
        if self._creating or self._closing:
            return
        request = self._request
        parent_text = self._parent_edit.text()
        name_text = self._name_edit.text()
        find_git, check, app_dir, environ = self._find_git, self._check_fn, self._app_dir, self._environ

        def work():
            # git is looked up again on every check: it may be installed or removed while the dialog is open
            root = Path(parent_text.strip()) / name_text if parent_text.strip() and name_text.strip() else app_dir
            found = isinstance(find_git(root), Path)
            return check(parent_text, name_text, git_found=found, app_dir=app_dir, environ=environ)

        self._run(
            work,
            lambda result, r=request: self._on_checked(r, result),
            lambda text, r=request: self._on_check_failed(r, text),
            name="new-collection-check",
        )

    def _on_checked(self, request: int, result):
        if request != self._request or self._closing:
            return  # a newer edit has been made since this check started
        self._check_rows = tuple(result.rows)
        self._target = result.target
        self._pending = False
        self._draw()

    def _on_check_failed(self, request: int, text: str):
        if request != self._request or self._closing:
            return
        self._check_rows = (CheckRow("fail", f"Library folder step failed: {text}"),)
        self._target = None
        self._pending = False
        self._draw()

    def _draw(self):
        """Show the rows of the newest check (or of a failed creation) and set the Create button."""
        rows = list(self._failure_rows) if self._failure_rows else ([] if self._pending else list(self._check_rows))
        while self._strip_layout.count():
            item = self._strip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for row in rows:
            label = QLabel(row.shown)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setAccessibleName(row.shown)
            if row.kind == "fail":
                label.setStyleSheet(f"color: {theme.ERROR};")
            elif row.kind == "warn":
                label.setStyleSheet(f"color: {theme.AMBER};")
            self._strip_layout.addWidget(label)
            label.show()  # a child made on a shown dialog stays hidden until a queued call, and a hidden one is not laid out
        self._strip.setVisible(bool(rows) and not self._creating)
        blocked = any(row.kind == "fail" for row in rows)
        usable = not self._pending and not blocked and self._target is not None and not self._failure_rows
        self._create_btn.setEnabled(usable and not self._creating)
        fit_height_to_content(self)

    # ── browse ──────────────────────────────────────────────────────────────

    def _on_browse(self):
        start = self._parent_edit.text().strip()
        folder = Path(start) if start else None
        while folder is not None and not folder.is_dir():
            folder = folder.parent if folder.parent != folder else None
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose the parent folder", str(folder) if folder is not None else str(Path.home())
        )
        if not chosen:
            return  # closed without a choice: nothing changes
        self._parent_edit.setText(str(Path(chosen)))
        self._schedule_check(0)

    # ── creating ────────────────────────────────────────────────────────────

    def _on_create_shortcut(self):
        if self._create_btn.isEnabled():
            self._on_create()

    def _on_create(self):
        if self._creating or not self._create_btn.isEnabled() or self._target is None:
            return
        target = self._target
        self._creating = True
        self._failure_rows = []
        for widget in (self._parent_edit, self._name_edit, self._browse_btn, self._back_btn):
            widget.setEnabled(False)
        self._create_btn.setText("Creating...")
        self._create_btn.setEnabled(False)
        self._strip.hide()
        self._progress.show()
        find_git, create, app_dir, environ = self._find_git, self._create_fn, self._app_dir, self._environ

        def work():
            exe = find_git(target.parent)
            if not isinstance(exe, Path):
                return [Issue(Severity.ERROR, "collection.git_missing", _GIT_MISSING)]
            return create(target, GitContext(exe), app_dir=app_dir, environ=environ)

        # The creation (run_in_background) task is never cancelled: while self._creating is True reject, done and closeEvent
        # all refuse, so _cancel_tasks cannot run and a half-written skeleton is never left behind.
        self._run(
            work,
            lambda issues, t=target: self._on_created(t, issues),
            self._on_create_failed,
            name="new-collection-create",
        )

    def _end_creating(self):
        self._creating = False
        self._progress.hide()
        for widget in (self._parent_edit, self._name_edit, self._browse_btn, self._back_btn):
            widget.setEnabled(True)
        self._create_btn.setText("Create Collection")

    def _on_created(self, target: Path, issues):
        if self._closing:
            return
        if not issues:
            self._created = target
            self._end_creating()
            self.accept()
            return
        self._end_creating()
        self._failure_rows = [CheckRow("fail", issue.text) for issue in issues]
        self._draw()

    def _on_create_failed(self, text: str):
        if self._closing:
            return
        self._end_creating()
        self._failure_rows = [CheckRow("fail", f"Library folder step failed: {text}")]
        self._draw()

    # ── background checks and closing ───────────────────────────────────────

    def _run(self, fn: Callable, on_result: Callable, on_failed: Callable, *, name: str) -> BackgroundTask:
        """A task on a daemon thread owned by the dialog; a close cancels the checks and never waits for them."""
        self._tasks = [task for task in self._tasks if not task.is_done()]
        task = run_in_background(fn, on_result, on_failed, name=name)
        self._tasks.append(task)
        return task

    def _cancel_tasks(self):
        # Only reached when nothing is being created (done and closeEvent refuse first)
        for task in self._tasks:
            task.cancel()
        self._tasks = []

    def reject(self):
        if self._creating:
            return  # there is nothing to stop safely: the work takes well under a second
        super().reject()

    def done(self, result: int):
        if self._creating:
            return
        self._closing = True
        self._debounce.stop()
        self._cancel_tasks()
        super().done(result)

    def closeEvent(self, event: QCloseEvent):
        if self._creating:
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
            self._name_edit.setFocus()
            self._name_edit.selectAll()
        fit_height_to_content(self)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            fit_height_to_content(self)
