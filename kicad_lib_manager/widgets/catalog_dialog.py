"""The library catalog window (Phase 17; CAT-01, CAT-06, CAT-07, D-02, D-05, D-06, D-11, D-16, D-29, D-32).

A parentless, non-modal window like the User Guide: it shows the collection the main window works on, with one
row per curated, added or stray library (status, licence, size), a search, the notice strips of the record and of
Git, a Details page for the selected row and a manual Check for Updates. This module is the browse slice; Add,
Update, Remove and Reinstall attach to it in the plans that follow (see CatalogServices for the functions they
call). Every library name, path, nickname and reason is shown as plain text; only the Repository link is rich
text. Nothing here touches the disk or the network on the GUI thread beyond reading catalog.json and listing
ThirdParty: the Git check, the staging clean-up, the KiCad variable read, the folder sizes and the update check
run on daemon threads (widgets/background.py), and a generation counter drops every result that arrives after the
window closed or the collection changed.
"""

import math
import os
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QStyle, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import kicad_process, library_scanner
from ..collection import OWN_DIR, THIRD_PARTY_DIR
from ..catalog import curated as curated_list
from ..catalog import githubapi, manifest, ops, status
from ..catalog.licences import LicenceClass
from ..catalog.manifest import CatalogEntry
from ..catalog.status import Check, State
from ..models import Issue, Severity
from . import catalog_pages, theme
from .background import BackgroundTask, run_in_background
from .catalog_pages import AddByUrlPage, AddPreviewPage, LicencePage, RemovePage, ReviewPage, UpdatePreviewPage
from .catalog_pages import LinkLabel as _LinkLabel
from .catalog_pages import heading_font as _heading_font
from .catalog_pages import mono as _mono
from .catalog_pages import muted as _muted
from .catalog_pages import plain_label as _plain_label
from .import_dialog import TaskWorker
from .import_result import ElidedLabel

# ── The copy (UI-SPEC "Copywriting Contract"; each text is written once, here) ──────────────────────

CATALOG_TITLE = "Library Catalog - KiCad External Lib Manager"
CATALOG_TOPIC = "catalog"  # the User Guide page key

HEADING_TEXT = "Library Catalog"
HELP_TEXT = "Help"
INSTALLED_IN_TEXT = "Libraries are installed in "
SEARCH_TEXT = "Search libraries"
CHECK_TEXT = "Check for Updates"
CHECKING_TEXT = "Checking..."
ADD_URL_TEXT = "Add by URL..."
CLOSE_TEXT = "Close"
LIST_NAME = "Libraries"
COLUMNS = ("Name", "Status", "Licence", "Size")
EMPTY_PANE_TEXT = "Select a library to see its details."
NO_MATCH_HEADING = "No library matches your search"
NO_MATCH_BODY = "Clear the search, or press Add by URL... to add a library from GitHub."

NOT_INSTALLED_TEXT = "Not installed"
INSTALLED_CURRENT_TEXT = "✓ Installed"
INSTALLED_TEXT = "Installed"
INSTALLED_TIP = "Updates have not been checked, or GitHub could not be reached."
UPDATE_AVAILABLE_TEXT = "⚠ Update available"
FOLDER_MISSING_TEXT = "✖ Problem: folder missing"
NOT_IN_CATALOG_TEXT = "⚠ Problem: not in the catalog"
UNKNOWN_TEXT = catalog_pages.UNKNOWN_TEXT

RECORD_STRIP_TEXT = (
    "✖ The catalog record of this collection cannot be read ({reason}). Nothing was changed. "
    "Fix or delete catalog.json in {collection}, then reopen the catalog."
)
ERROR_GLYPH = catalog_pages.ERROR_GLYPH
WARNING_GLYPH = catalog_pages.WARNING_GLYPH

RECORD_UNREADABLE_TIP = "The catalog record cannot be read."
GIT_MISSING_TIP = "Git was not found."
GIT_TOO_OLD_TIP = "Your Git is too old for the catalog."
GIT_CHECKING_TIP = "Looking for Git..."
FINISHING_TIP = "Finishing the last change..."

GENERATE_TEXT = "Generate Tables"
MANIFEST_NOTE_TEXT = "catalog.json in {collection} changed. The app does not commit it for you."

# The Details page (UI-SPEC "Details page")
FIELDS = (
    ("repository", "Repository"),
    ("licence", "Licence"),
    ("size", "Size"),
    ("libraries", "Libraries"),
    ("vars", "Path variables"),
    ("version", "Installed version"),
    ("updates", "Updates"),
    ("folder", "Folder"),
)
LABEL_COLUMN_WIDTH = 120
NOT_STATED_TEXT = catalog_pages.NOT_STATED_TEXT
LICENCE_UNREADABLE_TEXT = catalog_pages.LICENCE_UNREADABLE_TEXT
SIZE_PENDING_TEXT = "Calculating..."
SIZE_UNKNOWN_TEXT = "Unknown"
SIZE_ON_DISK_TIP = "{size} on disk"
LIBRARIES_UNKNOWN_TEXT = "Known after it is added"
NO_VARS_TEXT = "This library needs none."
VARS_PENDING_TEXT = "Reading KiCad settings..."
VAR_SET_TEXT = "✓ set"
VAR_NOT_SET_TEXT = "⚠ not set"
VAR_DIFFERENT_TEXT = "⚠ set to a different folder"
VAR_NO_SETTINGS_TEXT = "KiCad settings were not found"
UPDATES_CHECKING_TEXT = "Checking for updates..."
UPDATES_NEVER_TEXT = "Not checked yet"
UPDATES_OFFLINE_TEXT = "Could not check for updates (GitHub could not be reached)"
UPDATES_BRANCH_GONE_TEXT = "Could not check for updates (the repository no longer has this branch)"
FOLDER_MISSING_STRIP = (
    "✖ The folder {folder} is missing. It may have been deleted, or this collection was copied from another "
    "computer without it. Reinstall This Library downloads it again from {repository}."
)
NOT_IN_CATALOG_STRIP = (
    "⚠ This folder is in ThirdParty but is not in the catalog, so the app does not know where it came from. "
    "Its libraries are still scanned like any other. The app never deletes it by itself; Remove This Library "
    "deletes it after you confirm."
)
UPDATE_STRIP = "⚠ A newer version is available ({installed} -> {available})."
CHECK_OFFLINE_LINE = "Could not check for updates: GitHub could not be reached."
STEP_FAILED = "Library catalog step failed: {text}"

# The Add, Add by URL and Reinstall flows (UI-SPEC "Add flow", "Job strip", "Close rules", "Busy rules", "Log lines")
ADD_THIS_TEXT = "Add This Library"
REINSTALL_THIS_TEXT = "Reinstall This Library"
UPDATE_THIS_TEXT = "Update This Library"
REMOVE_THIS_TEXT = "Remove This Library"
SET_VARS_TEXT = "Set Path Variables..."
UPDATE_CURRENT_TIP = "Already up to date."
UPDATE_UNKNOWN_TIP = "No update is known. Press Check for Updates."
PAGE_OPEN_TIP = "Go back to the list first."
WAIT_TIP = "Wait for {job} to finish."
STOPPING_TEXT = "Stopping..."
CANCEL_TIP = "Stop {job} and delete what it downloaded. Nothing is changed."
REGISTER_CANCEL_TIP = "Adding cannot be stopped halfway. It ends in a moment."
REGISTER_CLOSE_TEXT = "Adding cannot be stopped halfway. Close this window after it ends."
CHECKING_REPOSITORY_TEXT = "Checking the repository..."
DOWNLOADING_TEXT = "Downloading {name}..."
DOWNLOADING_PERCENT_TEXT = "Downloading {name}... {percent}%"
DOWNLOADING_AGAIN_TEXT = "Downloading {name} again..."
DOWNLOADING_AGAIN_PERCENT_TEXT = "Downloading {name} again... {percent}%"
CHECKING_NAME_TEXT = "Checking {name}..."
CHECKING_FILES_TEXT = "Checking {name}... {percent}% ({done} of {total} files)"
ADDING_NAME_TEXT = "Adding {name}..."
CANCEL_CHECK_TEXT = "Cancel Check"
CANCEL_ADDING_TEXT = "Cancel Adding"
CANCEL_REINSTALLING_TEXT = "Cancel Reinstalling"
STOP_TITLE = "Stop the current job?"
STOP_TEXT = (
    "{job} is still running. If you close the catalog now, it is stopped and the partly downloaded files are "
    "deleted. {consequence}"
)
STOP_CLOSE_TEXT = "Stop and Close"
KEEP_WORKING_TEXT = "Keep Working"
CONSEQUENCE_ADD = "Nothing is added to your collection."
CONSEQUENCE_CHECK = "Nothing is changed."
RESULT_ADDED = "Added {name}: {s} symbol libraries and {f} footprint libraries are in your scan."
RESULT_REINSTALLED = "Reinstalled {name}: {s} symbol libraries and {f} footprint libraries are in your scan."
RESULT_CLASHES = "{n} of them share a name with a library you already have and are unticked."
LOG_STOPPED_ADDING = "Stopped adding {name}. Nothing was added."
LOG_STOPPED_REINSTALLING = "Stopped reinstalling {name}. Nothing was added."
LOG_DISCARDED = "Discarded the download of {name}. Nothing was added."
LOG_DISCARD_FAILED = "Could not delete the downloaded copy of {name}: {text}"
LOG_COULD_NOT = "Could not {verb} {name}: {text}"
LOOKING_TEXT = "Looking for changes in {name}..."
UPDATING_NAME_TEXT = "Updating {name}..."
REMOVING_NAME_TEXT = "Removing {name}..."
CANCEL_UPDATING_TEXT = "Cancel Updating"
CANCEL_REMOVING_TEXT = "Cancel Removing"
REMOVE_CANCEL_TIP = "Removing cannot be stopped halfway. It ends in a moment."
REMOVE_CLOSE_TEXT = "Removing cannot be stopped halfway. Close this window after it ends."
CONSEQUENCE_UPDATE = "{name} stays on the version it has now."
RESULT_UPDATED = "Updated {name} to {commit}: {a} libraries added, {r} removed."
RESULT_REMOVED = "Removed {name}. Press Generate Tables to drop its libraries from your KiCad library tables."
LOG_STOPPED_UPDATING = "Stopped updating {name}. It stays on its current version."
UPDATE_CRASHED_TEXT = "The update failed because something unexpected went wrong. See the log for details."
REMOVE_CRASHED_TEXT = "Removing failed because something unexpected went wrong. See the log for details."
CHECK_CRASHED_TEXT = "Something went wrong while checking the repository. See the log for details."
STAGE_CRASHED_TEXT = "The download failed because something unexpected went wrong. See the log for details."
REGISTER_CRASHED_TEXT = "Adding failed because something unexpected went wrong. See the log for details."
OWN_ATOMIC_TEXT = "your Atomic_ libraries"
OWN_CUSTOM_TEXT = "your Custom libraries"
JOB_BAR_WIDTH = 240
# a failed download may be tried again; a refusal after the download may not (the repository itself is the problem)
RETRY_CODES = frozenset({
    "git.clone_failed", "git.timeout", "git.unreachable", "git.not_started", "git.no_commit", "git.read_failed",
    "git.branch_missing", "catalog.step_failed",
})


def job_label(flow: str, name: str) -> str:
    """How a job is named in a tooltip or a question: `the repository check`, `adding {name}`, `updating {name}`, ..."""
    if flow == "check":
        return "the repository check"
    verb = {"reinstall": "reinstalling", "update": "updating", "remove": "removing"}.get(flow, "adding")
    return f"{verb} {name}"


@dataclass(frozen=True)
class CatalogOutcome:
    """What a catalog job left behind, handed to the main window with job_finished.

    kind is "add", "reinstall", "update" or "remove"; ok is False for a stop, a refusal and a failure (the window logged it). The counts,
    collisions (validate.Collision rows), vars (path variable -> folder inside the clone), legacy_prefix (the old
    folder of a curated library, for the selection carry-over) and root_is_repo are filled when ok is True.
    """

    kind: str
    id: str
    name: str
    ok: bool
    symbol_count: int = 0
    footprint_count: int = 0
    collisions: tuple = ()
    vars: dict = field(default_factory=dict)
    legacy_prefix: str | None = None
    root_is_repo: bool = False


@dataclass
class _Job:
    """One job on a worker: phase is plan, check, stage, register, discard, look, apply or remove; flow is check, add, reinstall, update or remove."""

    phase: str
    flow: str
    name: str
    cancel: threading.Event
    gen: int
    on_done: Callable | None = None
    worker: object = None
    stopping: bool = False
    dropped: bool = False
    checking: bool = False  # a file count of the check was shown; a later git line never resets the strip


@dataclass
class _Flow:
    """The Add, Reinstall, Update, Remove or Add by URL in progress: kind is add, reinstall, update, remove or url (the address page)."""

    kind: str
    id: str = ""
    name: str = ""
    plan: object = None
    url: bool = False


_STOPPED = object()  # what a stage job returns when the user pressed Cancel
_FILES_STEP = "check-files"  # the text of a progress emission that carries the check's file count: (marker, files done, files in all)
_STOPPABLE = ("check", "stage", "look", "apply")  # the phases a Cancel button or a close question can stop

# ── Sizes (UI-SPEC "Spacing Scale"; px at 96 DPI) ───────────────────────────────────────────────────

WINDOW_SIZE = (900, 640)
WINDOW_MINIMUM = (760, 520)
LIST_MINIMUM_HEIGHT = 120
PANE_MINIMUM_HEIGHT = 200  # kept while the window has room; strips may squeeze the pane (it scrolls), never the list
STATUS_WIDTH, LICENCE_WIDTH, SIZE_WIDTH = 200, 120, 80
CONTROL_HEIGHT = 28
_LIST_SHARE = 0.45

_ROW_ID = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class CatalogServices:
    """The catalog functions the window calls; tests replace single fields with fakes (like ImportCore).

    Plans 17-13 and 17-15 call the Add, Update, Remove and Reinstall functions through these fields.
    """

    load_manifest: Callable = manifest.load
    curated: tuple = curated_list.CURATED
    row_statuses: Callable = status.row_statuses
    check_updates: Callable = status.check_updates
    net_status: Callable = ops.net_status
    clean_staging: Callable = ops.clean_staging
    current_path_vars: Callable = library_scanner.current_path_vars
    path_vars: Callable = manifest.path_vars
    size_on_disk: Callable = ops.size_on_disk
    plan_add: Callable = ops.plan_add
    stage_add: Callable = ops.stage_add
    register_add: Callable = ops.register_add
    discard_staging: Callable = ops.discard_staging
    plan_reinstall: Callable = ops.plan_reinstall
    check_repository: Callable = ops.check_repository
    plan_update: Callable = ops.plan_update
    apply_update: Callable = ops.apply_update
    plan_remove: Callable = ops.plan_remove
    apply_remove: Callable = ops.apply_remove
    kicad_running: Callable = kicad_process.kicad_running
    repo_info: Callable = githubapi.repo_info
    free_space: Callable = shutil.disk_usage
    stock_fp: Callable = library_scanner.get_kicad_default_fp_nicknames
    stock_sym: Callable = library_scanner.get_kicad_default_sym_nicknames


def _status_cell(row: status.Row) -> tuple[str, str | None, str]:
    """(text, colour token or None for the default text colour, tooltip) of a row's Status cell."""
    state = row.state
    if state is State.NOT_INSTALLED:
        return NOT_INSTALLED_TEXT, theme.MUTED, NOT_INSTALLED_TEXT
    if state is State.INSTALLED:
        if row.update is not None and row.update.check is Check.CURRENT:
            return INSTALLED_CURRENT_TEXT, theme.SUCCESS, INSTALLED_CURRENT_TEXT
        return INSTALLED_TEXT, theme.MUTED, INSTALLED_TIP
    if state is State.UPDATE_AVAILABLE:
        return UPDATE_AVAILABLE_TEXT, theme.AMBER, UPDATE_AVAILABLE_TEXT
    if state is State.FOLDER_MISSING:
        return FOLDER_MISSING_TEXT, theme.ERROR, FOLDER_MISSING_TEXT
    if state is State.NOT_IN_CATALOG:
        return NOT_IN_CATALOG_TEXT, theme.AMBER, NOT_IN_CATALOG_TEXT
    return UNKNOWN_TEXT, theme.MUTED, UNKNOWN_TEXT


class CatalogDialog(QDialog):
    """The catalog window; shows one collection (the main window's library folder) at a time.

    Signals: log_line(text, level) for the log panel; update_states_changed(states) after a manual check;
    generate_requested() from the result strip; path_vars_requested(id) for the path variable question;
    job_finished(outcome) once for every catalog job that ends; busy_changed() whenever is_job_running,
    holds_download or is_finishing changes.
    """

    log_line = Signal(str, str)
    update_states_changed = Signal(object)
    generate_requested = Signal()
    path_vars_requested = Signal(str)
    job_finished = Signal(object)
    busy_changed = Signal()

    def __init__(
        self,
        root: Path,
        *,
        services: CatalogServices | None = None,
        show_guide: Callable[[str], None] | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        super().__init__(None)  # no parent: a parent would let a window-modal question of the main window block it
        self._root = Path(root)
        self._services = services or CatalogServices()
        self._show_guide = show_guide
        self._help_dialog: QDialog | None = None
        self._clock = clock

        self._gen = 0  # bumped on close and on a root change; a result of an older one is dropped
        self._background: list[BackgroundTask] = []
        self._check_cancel = threading.Event()
        self._fresh = False  # True from a load until the window closes
        self._mf = None  # Manifest, or the Issue catalog.json gave (D-02)
        self._rows: list[status.Row] = []
        self._updates: dict[str, status.UpdateState] = {}
        self._net_status = None  # ops.NetStatus once the Git check answered
        self._kicad_vars: dict[str, str] | None = None
        self._vars_read = False
        self._scan = None
        self._blocked: str | None = None
        self._finishing = False
        self._external_check = False
        self._manual_check = False
        self._shown_id: str | None = None
        self._split_user = False
        self._size_cache: dict[Path, int | None] = {}  # folder -> bytes on disk, None when it could not be measured
        self._size_queue: list[Path] = []  # folders waiting to be measured, the next one first; one is measured at a time
        self._size_running: Path | None = None
        self._size_stale: set[Path] = set()  # folders whose running measurement is out of date (the folder changed under it)
        self._size_task: BackgroundTask | None = None
        self._kicad_fp_dir: Path | None = None
        self._job: _Job | None = None  # the one job on a worker; plan, check, stage, register or discard
        self._flow: _Flow | None = None  # the Add, Reinstall or Add by URL in progress
        self._staged: ops.Staged | None = None  # a checked download waiting on the preview
        self._page_kind: str | None = None  # None (the list), url, licence or preview
        self._workers: list[TaskWorker] = []
        self._pending_close: int | None = None  # a close waits for the job to end
        self._asking = False
        self._busy_sent = (False, False)
        self._vars_differ = False  # the shown row has a path variable that is not set or set to another folder

        self.setWindowTitle(CATALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MINIMUM)

        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit_detail)
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.setInterval(0)
        self._focus_timer.timeout.connect(self._focus_page)

        self._build_ui()
        self._reload(reset=True)

    # ── Layout ────────────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        outer.setSpacing(theme.SP_SM)

        header = QHBoxLayout()
        header.setSpacing(theme.SP_SM)
        self._heading = _plain_label(HEADING_TEXT)
        _heading_font(self._heading)
        header.addWidget(self._heading)
        header.addStretch(1)
        self._help_btn = QToolButton()
        self._help_btn.setText(HELP_TEXT)
        self._help_btn.setAccessibleName(HELP_TEXT)
        self._help_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))
        self._help_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._help_btn.setAutoRaise(True)
        self._help_btn.setShortcut(QKeySequence("F1"))
        self._help_btn.clicked.connect(self._on_help)
        header.addWidget(self._help_btn)
        outer.addLayout(header)

        where = QHBoxLayout()
        where.setSpacing(theme.SP_XS)
        self._installed_in = _plain_label(INSTALLED_IN_TEXT)
        self._path_label = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
        _mono(self._path_label)
        where.addWidget(self._installed_in)
        where.addWidget(self._path_label, 1)
        outer.addLayout(where)

        # The notice strips, in the fixed order of UI-SPEC "Notice strips"; each is hidden when it does not apply
        self._record_strip, self._record_label = self._make_strip("recordStrip", amber=False)
        self._git_missing_strip, self._git_missing_label = self._make_strip("gitMissingStrip", amber=False)
        self._git_too_old_strip, self._git_too_old_label = self._make_strip("gitTooOldStrip", amber=False)
        self._git_old_strip, self._git_old_label = self._make_strip("gitOldStrip", amber=True)
        for strip in (self._record_strip, self._git_missing_strip, self._git_too_old_strip, self._git_old_strip):
            outer.addWidget(strip)

        self._toolbar = QWidget()
        toolbar = QHBoxLayout(self._toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(theme.SP_SM)
        self._search = QLineEdit()
        self._search.setPlaceholderText(SEARCH_TEXT)
        self._search.setAccessibleName(SEARCH_TEXT)
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumHeight(CONTROL_HEIGHT)
        self._search.setMinimumWidth(theme.SP_XL * 2)  # the search field shrinks first
        self._search.textChanged.connect(self._apply_filter)
        self._search.installEventFilter(self)
        self._check_btn = QPushButton(CHECK_TEXT)
        self._add_url_btn = QPushButton(ADD_URL_TEXT)
        for button in (self._check_btn, self._add_url_btn):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setMinimumHeight(CONTROL_HEIGHT)
        # one width for both labels of the check button, so it does not jump while it reads Checking...
        metrics = self._check_btn.fontMetrics()
        widest = max(metrics.horizontalAdvance(CHECK_TEXT), metrics.horizontalAdvance(CHECKING_TEXT))
        self._check_btn.setMinimumWidth(max(self._check_btn.sizeHint().width(), widest + 2 * theme.SP_MD))
        self._check_btn.clicked.connect(self._on_check_clicked)
        self._add_url_btn.clicked.connect(self._on_add_url)
        toolbar.addWidget(self._search, 1)
        toolbar.addWidget(self._check_btn)
        toolbar.addWidget(self._add_url_btn)
        outer.addWidget(self._toolbar)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(theme.SP_SM)
        self._splitter.addWidget(self._build_list())
        self._splitter.addWidget(self._build_pane())
        self._splitter.setStretchFactor(0, 45)
        self._splitter.setStretchFactor(1, 55)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)
        outer.addWidget(self._splitter, 1)
        outer.addWidget(self._build_job_strip())

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self._close_btn = QPushButton(CLOSE_TEXT)
        self._close_btn.setMinimumHeight(CONTROL_HEIGHT)
        self._close_btn.setAutoDefault(True)
        self._close_btn.setDefault(True)  # on the idle list view only; a review page takes the default away
        self._close_btn.clicked.connect(self.reject)
        bottom.addWidget(self._close_btn)
        outer.addLayout(bottom)

        self.setTabOrder(self._search, self._check_btn)
        self.setTabOrder(self._check_btn, self._add_url_btn)
        self.setTabOrder(self._add_url_btn, self._tree)
        self.setTabOrder(self._tree, self._help_btn)
        self.setTabOrder(self._help_btn, self._close_btn)

    def _make_strip(self, name: str, *, amber: bool) -> tuple[QFrame, QLabel]:
        """A hidden notice strip: the amber form (tint and a 2px left bar, like checkoutBanner) or the framed error form."""
        frame = QFrame()
        frame.setObjectName(name)
        if amber:
            frame.setStyleSheet(
                f"QFrame#{name} {{ background-color: {theme.AMBER_TINT}; border-left: 2px solid {theme.AMBER}; }}"
            )
        else:
            frame.setStyleSheet(f"QFrame#{name} {{ border: 1px solid {theme.BORDER}; }}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM)
        layout.setSpacing(theme.SP_XS)
        label = _plain_label(wrap=True)
        label.setObjectName(f"{name}Label")
        label.setStyleSheet(f"color: {theme.AMBER if amber else theme.ERROR};")
        layout.addWidget(label, 1)
        frame.hide()
        return frame, label

    def _build_list(self) -> QWidget:
        self._list_stack = QStackedWidget()
        self._list_stack.setMinimumHeight(LIST_MINIMUM_HEIGHT)

        tree = QTreeWidget()
        self._tree = tree
        tree.setColumnCount(len(COLUMNS))
        tree.setHeaderLabels(list(COLUMNS))
        tree.setAccessibleName(LIST_NAME)
        tree.setRootIsDecorated(False)
        tree.setUniformRowHeights(True)
        tree.setSortingEnabled(False)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionsClickable(False)  # header clicks do nothing: rows stay in name order
        header.setSectionsMovable(False)
        header.setHighlightSections(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, STATUS_WIDTH), (2, LICENCE_WIDTH), (3, SIZE_WIDTH)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, width)
        tree.headerItem().setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._list_stack.addWidget(tree)

        self._empty_list = QWidget()
        empty = QVBoxLayout(self._empty_list)
        empty.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        empty.setSpacing(theme.SP_XS)
        self._empty_heading = _plain_label(NO_MATCH_HEADING)
        _heading_font(self._empty_heading)
        self._empty_body = _plain_label(NO_MATCH_BODY, wrap=True)
        _muted(self._empty_body)
        empty.addWidget(self._empty_heading)
        empty.addWidget(self._empty_body)
        empty.addStretch(1)
        self._list_stack.addWidget(self._empty_list)
        return self._list_stack

    def _build_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("detailPane")
        pane.setStyleSheet(
            f"QFrame#detailPane {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; }}"
        )
        # No height of its own to insist on: when the strips take the room the pane shrinks and scrolls, the list does not
        pane.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(theme.SP_MD, theme.SP_MD, theme.SP_MD, theme.SP_MD)
        layout.setSpacing(theme.SP_SM)

        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)
        self._pages = QStackedWidget()
        self._scroll.setWidget(self._pages)
        self._pages.setAutoFillBackground(False)  # QScrollArea.setWidget turns it on

        self._empty_page = QWidget()
        empty = QVBoxLayout(self._empty_page)
        empty.setContentsMargins(0, 0, 0, 0)
        empty.setSpacing(theme.SP_SM)
        # the result of a Remove whose row left the list has no Details page to sit on: it shows here
        self._gone_result_strip, self._gone_lines_box, self._gone_note, self._gone_generate_btn = self._make_result_strip(
            "goneResultStrip"
        )
        empty.addWidget(self._gone_result_strip)
        self._empty_label = _plain_label(EMPTY_PANE_TEXT, wrap=True)
        _muted(self._empty_label)
        empty.addWidget(self._empty_label)
        empty.addStretch(1)
        self._pages.addWidget(self._empty_page)

        self._details_page = self._build_details()
        self._pages.addWidget(self._details_page)
        self._url_page = AddByUrlPage()
        self._licence_page = LicencePage()
        self._preview_page = AddPreviewPage()
        self._update_page = UpdatePreviewPage()
        self._remove_page = RemovePage()
        for page in (self._url_page, self._licence_page, self._preview_page, self._update_page, self._remove_page):
            self._pages.addWidget(page)
        self._url_page.primary_pressed.connect(self._on_url_primary)
        self._url_page.back_pressed.connect(self._on_page_back)
        self._licence_page.primary_pressed.connect(self._start_download)
        self._licence_page.back_pressed.connect(self._on_page_back)
        self._preview_page.primary_pressed.connect(self._on_preview_primary)
        self._preview_page.back_pressed.connect(self._on_preview_back)
        self._update_page.primary_pressed.connect(self._on_update_primary)
        self._update_page.back_pressed.connect(self._on_page_back)
        self._remove_page.primary_pressed.connect(self._on_remove_primary)
        self._remove_page.back_pressed.connect(self._on_page_back)
        self._show_page(self._empty_page)
        layout.addWidget(self._scroll, 1)
        return pane

    def _build_details(self) -> QWidget:
        """The Details page: heading, description, result strip, problem strip, the labelled rows and a button row."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP_SM)
        self._detail_heading = ElidedLabel("", mode=Qt.TextElideMode.ElideRight, full_tooltip=True)
        _heading_font(self._detail_heading)
        layout.addWidget(self._detail_heading)
        self._detail_description = _plain_label(wrap=True)
        _muted(self._detail_description)
        layout.addWidget(self._detail_description)

        # The result strip: shown after a job ends, kept until another row is selected (D-03, D-18)
        self._result_strip, self._result_lines_box, self._result_note, self._result_generate_btn = self._make_result_strip(
            "resultStrip"
        )
        layout.addWidget(self._result_strip)
        self._result: tuple[list[tuple[str, str]], bool, bool] | None = None

        # The problem and update strip (folder missing, not in the catalog, a newer version)
        self._problem_strip = QFrame()
        self._problem_strip.setObjectName("problemStrip")
        problem = QHBoxLayout(self._problem_strip)
        problem.setContentsMargins(theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM)
        self._problem_label = _plain_label(wrap=True)
        problem.addWidget(self._problem_label, 1)
        self._problem_strip.hide()
        layout.addWidget(self._problem_strip)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.SP_SM)
        grid.setVerticalSpacing(theme.SP_XS)
        grid.setColumnMinimumWidth(0, LABEL_COLUMN_WIDTH)
        grid.setColumnStretch(1, 1)
        self._field_rows: dict[str, tuple[QLabel, QWidget]] = {}
        for index, (key, title) in enumerate(FIELDS):
            label = _plain_label(title)
            label.setMinimumWidth(LABEL_COLUMN_WIDTH)
            value = self._make_value(key)
            grid.addWidget(label, index, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, index, 1)
            self._field_rows[key] = (label, value)
        layout.addLayout(grid)

        # The buttons of the page, left to right: the plain ones, then the one primary of the row's status
        self._button_row = QHBoxLayout()
        self._button_row.setSpacing(theme.SP_SM)
        self._button_row.addStretch(1)
        self._vars_btn = self._details_plain_button(SET_VARS_TEXT, self._on_vars_clicked)
        self._remove_btn = self._details_plain_button(REMOVE_THIS_TEXT, self._on_remove_clicked)
        self._update_btn = self._details_plain_button(UPDATE_THIS_TEXT, self._on_update_clicked)
        self._add_btn = self._details_primary_button(ADD_THIS_TEXT, self._on_add_clicked)
        self._reinstall_btn = self._details_primary_button(REINSTALL_THIS_TEXT, self._on_reinstall_clicked)
        layout.addLayout(self._button_row)
        layout.addStretch(1)
        return page

    def _make_result_strip(self, name: str) -> tuple[QFrame, QVBoxLayout, QLabel, QPushButton]:
        """A hidden result strip: the lines, the catalog.json note and the Generate Tables button."""
        frame = QFrame()
        frame.setObjectName(name)
        frame.setStyleSheet(
            f"QFrame#{name} {{ background-color: {theme.SURFACE_HEADER}; border: 1px solid {theme.BORDER}; }}"
        )
        strip = QHBoxLayout(frame)
        strip.setContentsMargins(theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM)
        strip.setSpacing(theme.SP_SM)
        text = QVBoxLayout()
        text.setSpacing(theme.SP_XS)
        lines = QVBoxLayout()
        lines.setSpacing(theme.SP_XS)
        text.addLayout(lines)
        note = _plain_label(wrap=True)
        _muted(note)
        text.addWidget(note)
        strip.addLayout(text, 1)
        button = QPushButton(GENERATE_TEXT)
        button.setAutoDefault(False)
        button.setMinimumHeight(CONTROL_HEIGHT)
        button.clicked.connect(self.generate_requested)
        strip.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        frame.hide()
        return frame, lines, note, button

    def _details_plain_button(self, text: str, slot) -> QPushButton:
        """A plain button of the Details page (Remove This Library, Set Path Variables..., a disabled Update This Library)."""
        button = QPushButton(text)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setMinimumHeight(CONTROL_HEIGHT)
        button.clicked.connect(slot)
        button.hide()
        self._button_row.addWidget(button)
        return button

    def _details_primary_button(self, text: str, slot) -> QPushButton:
        """A primary (accent) button of the Details page; only one is visible for a row, and none without a row."""
        button = QPushButton(text)
        button.setStyleSheet(theme.PRIMARY_BUTTON_QSS)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setMinimumHeight(CONTROL_HEIGHT)
        button.clicked.connect(slot)
        button.hide()
        self._button_row.addWidget(button)
        return button

    def _make_value(self, key: str) -> QWidget:
        if key == "repository":
            return _LinkLabel()
        if key == "folder":
            folder = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
            _mono(folder)
            return folder
        if key in ("vars", "version"):
            box = QWidget()
            lay = QVBoxLayout(box) if key == "vars" else QHBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(theme.SP_XS if key == "version" else 0)
            return box
        return _plain_label(wrap=True)

    def _show_page(self, page: QWidget) -> None:
        """Make page the current page; the other pages stop asking for height, so the pane fits the page shown."""
        for index in range(self._pages.count()):
            other = self._pages.widget(index)
            other.setSizePolicy(
                QSizePolicy.Policy.Preferred if other is page else QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred if other is page else QSizePolicy.Policy.Ignored,
            )
        self._pages.setCurrentWidget(page)
        self._fit_timer.start()

    def _fit_detail(self) -> None:
        self._pages.updateGeometry()
        self._scroll.updateGeometry()

    # ── The splitter ──────────────────────────────────────────────────────────────────────────

    def _on_splitter_moved(self, *_args) -> None:
        self._split_user = True

    def _apply_split(self) -> None:
        """About 45 % list and 55 % pane; the list keeps 120 px and the pane 200 px while the window has room for both."""
        if self._split_user:
            return
        total = self._splitter.height() - self._splitter.handleWidth()
        if total <= 0:
            return
        list_height = round(total * _LIST_SHARE)
        pane_height = total - list_height
        if pane_height < PANE_MINIMUM_HEIGHT and total >= LIST_MINIMUM_HEIGHT + PANE_MINIMUM_HEIGHT:
            pane_height = PANE_MINIMUM_HEIGHT
        list_height = max(LIST_MINIMUM_HEIGHT, total - pane_height)
        self._splitter.setSizes([list_height, max(0, total - list_height)])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_split()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if event.spontaneous():
            return
        if not self._fresh:  # reopened after a close: an empty search, and the record and Git are read again
            self._search.clear()
            self._reload(reset=False)
        self._apply_split()
        self._search.setFocus()

    # ── Loading ───────────────────────────────────────────────────────────────────────────────

    def _reload(self, *, reset: bool) -> None:
        """Read the record, build the rows and strips at once, then start the background checks."""
        self._load()
        self._start_background(reset=reset)
        self._fresh = True

    def _load(self) -> None:
        self._path_label.set_full_text(f"{self._root.as_posix()}/ThirdParty")
        self._mf = self._services.load_manifest(self._root)
        self._rebuild_rows()
        self._update_strips()
        self._refresh_actions()

    def _start_background(self, *, reset: bool) -> None:
        """The Git check, the staging clean-up and the KiCad variable read, each on its own daemon thread."""
        for task in self._background:
            task.cancel()
        self._background = []
        if reset:
            self._net_status = None
            self._kicad_vars = None
            self._vars_read = False
            self._refresh_actions()
        gen, root, services = self._gen, self._root, self._services
        self._background = [
            run_in_background(
                lambda: services.net_status(root),
                lambda result, g=gen: self._on_net(g, result),
                lambda text, g=gen: self._on_net_failed(g, text),
                name="catalog-git-check",
            ),
            run_in_background(
                lambda: services.clean_staging(root),
                lambda result, g=gen: self._on_cleaned(g, result),
                lambda text, g=gen: self._on_step_failed(g, text),
                name="catalog-clean-staging",
            ),
            run_in_background(
                lambda: services.current_path_vars(),
                lambda result, g=gen: self._on_vars(g, result),
                lambda text, g=gen: self._on_vars(g, None),
                name="catalog-kicad-variables",
            ),
        ]

    def _stop_background(self) -> None:
        """Drop every outstanding result: the window closed or the collection changed."""
        self._gen += 1
        self._check_cancel.set()
        self._check_cancel = threading.Event()
        for task in self._background:
            task.cancel()
        self._background = []
        self._fit_timer.stop()
        self._focus_timer.stop()
        self._manual_check = False
        self._size_cache.clear()
        self._size_queue.clear()
        self._size_stale.clear()
        self._size_running = None
        if self._size_task is not None:
            self._size_task.cancel()
            self._size_task = None

    def _track(self, task: BackgroundTask) -> BackgroundTask:
        """Remember a background task so a close or a root change can drop its result."""
        self._background = [t for t in self._background if not t.is_done()]
        self._background.append(task)
        return task

    def _on_net(self, gen: int, result) -> None:
        if gen != self._gen:
            return
        self._net_status = result
        self._update_strips()
        self._refresh_actions()

    def _on_net_failed(self, gen: int, text: str) -> None:
        if gen != self._gen:
            return
        self.log_line.emit(STEP_FAILED.format(text=text), "error")
        refusal = Issue(
            Severity.ERROR,
            "catalog.git_check_failed",
            "Git could not be checked. Reopen the catalog to try again.",
        )
        self._on_net(gen, ops.NetStatus(None, None, refusal, None))

    def _on_cleaned(self, gen: int, issues) -> None:
        if gen != self._gen:
            return
        for issue in issues or ():
            self.log_line.emit(issue.text, "warning")

    def _on_step_failed(self, gen: int, text: str) -> None:
        if gen != self._gen:
            return
        self.log_line.emit(STEP_FAILED.format(text=text), "error")

    def _on_vars(self, gen: int, result) -> None:
        if gen != self._gen:
            return
        self._kicad_vars = dict(result) if isinstance(result, dict) else None
        self._vars_read = True
        self._refresh_details()

    # ── The list ──────────────────────────────────────────────────────────────────────────────

    def _make_item(self, row: status.Row) -> QTreeWidgetItem:
        text, token, tip = _status_cell(row)
        item = QTreeWidgetItem([row.name, text, row.licence_label, ""])
        item.setData(0, _ROW_ID, row.id)
        item.setToolTip(0, row.name)
        item.setToolTip(1, tip)
        item.setToolTip(2, row.licence_label)
        if token is not None:
            item.setForeground(1, QBrush(QColor(token)))
        if row.licence_class is LicenceClass.UNKNOWN:
            item.setForeground(2, QBrush(QColor(theme.MUTED)))
        self._set_size_cell(item, row)
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    @staticmethod
    def _on_disk(row: status.Row) -> bool:
        """True for a row whose folder exists, so its size is the size on disk."""
        return row.state in (State.INSTALLED, State.UPDATE_AVAILABLE, State.NOT_IN_CATALOG)

    def _set_size_cell(self, item: QTreeWidgetItem, row: status.Row) -> None:
        """The Size cell: the size on disk of an installed folder (Calculating... until measured), else the listed size."""
        if not self._on_disk(row):
            text, tip, muted = row.size_text, row.size_text, row.size_mb is None
        elif row.folder not in self._size_cache:
            text, tip, muted = SIZE_PENDING_TEXT, SIZE_PENDING_TEXT, True
        elif self._size_cache[row.folder] is None:
            text, tip, muted = SIZE_UNKNOWN_TEXT, SIZE_UNKNOWN_TEXT, True
        else:
            text = status.size_text(math.ceil(self._size_cache[row.folder] / 1_000_000))
            tip, muted = SIZE_ON_DISK_TIP.format(size=text), False
        item.setText(3, text)
        item.setToolTip(3, tip)
        item.setForeground(3, QBrush(QColor(theme.MUTED)) if muted else QBrush())

    def _rebuild_rows(self) -> None:
        keep = self.selected_id()
        self._rows = list(
            self._services.row_statuses(
                self._root, self._mf, curated=self._services.curated, updates=self._updates
            )
        )
        tree = self._tree
        tree.blockSignals(True)
        try:
            tree.clear()
            for row in self._rows:
                item = self._make_item(row)
                tree.addTopLevelItem(item)
                if row.id == keep:
                    tree.setCurrentItem(item)
                    item.setSelected(True)
        finally:
            tree.blockSignals(False)
        self._apply_filter()
        for row in sorted(self._rows, key=lambda r: r.id != keep):  # the selected row's folder first
            if self._on_disk(row):
                self._request_size(row.folder)
        self._pump_sizes()

    def _row_text(self, row: status.Row) -> list[str]:
        repository = row.entry.url if row.entry is not None else (row.curated.url if row.curated is not None else "")
        description = row.curated.description if row.curated is not None else ""
        return [row.name, description, repository]

    def _apply_filter(self, *_args) -> None:
        needle = self._search.text().strip().casefold()
        by_id = {row.id: row for row in self._rows}
        shown = 0
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            row = by_id[item.data(0, _ROW_ID)]
            match = not needle or any(needle in text.casefold() for text in self._row_text(row))
            item.setHidden(not match)
            shown += 1 if match else 0
        current = self._tree.currentItem()
        if current is not None and current.isHidden():
            self._tree.clearSelection()
            self._tree.setCurrentIndex(QModelIndex())
        self._list_stack.setCurrentWidget(self._tree if shown else self._empty_list)
        self._on_selection_changed()

    def selected_id(self) -> str | None:
        """The id of the selected row, or None."""
        selected = self._tree.selectedItems()
        return selected[0].data(0, _ROW_ID) if selected else None

    def current_row(self) -> status.Row | None:
        """The selected row, or None."""
        wanted = self.selected_id()
        return next((row for row in self._rows if row.id == wanted), None)

    def eventFilter(self, watched, event):
        if watched is self._search and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Down:
            self._focus_list()
            return True
        return super().eventFilter(watched, event)

    def _focus_list(self) -> None:
        if self._list_stack.currentWidget() is not self._tree:
            return
        self._tree.setFocus()
        if self._tree.currentItem() is None:
            for index in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(index)
                if not item.isHidden():
                    self._tree.setCurrentItem(item)
                    item.setSelected(True)
                    break

    # ── The detail pane ───────────────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        selected = self.selected_id()
        if selected != self._shown_id:
            self._result = None  # another row: the result of the last job goes
        self._shown_id = selected
        self._refresh_details()

    def _refresh_details(self) -> None:
        if self._page_kind is not None:  # a review page is open: a late result never pulls it away
            return
        row = self.current_row()
        if row is None:
            self._render_result(self._result, self._gone_result_strip, self._gone_lines_box, self._gone_note, self._gone_generate_btn)
            self._show_page(self._empty_page)
            return
        self._gone_result_strip.hide()
        self._fill_details(row)
        self._show_page(self._details_page)

    def _fill_details(self, row: status.Row) -> None:
        """Set every Details row for this row; a row that does not apply is hidden, none is ever blank."""
        installed = row.state in (State.INSTALLED, State.UPDATE_AVAILABLE)
        on_disk = installed or row.state is State.NOT_IN_CATALOG
        problem = row.state in (State.FOLDER_MISSING, State.NOT_IN_CATALOG)
        self._detail_heading.set_full_text(row.name)
        description = row.curated.description if row.curated is not None else ""
        self._detail_description.setText(description)
        self._detail_description.setVisible(bool(description))
        self._fill_problem_strip(row)
        self._fill_result()

        url = self._repository_url(row)
        self._set_repository(url)
        self._set_value("licence", self._licence_text(row))
        self._set_value("size", self._size_text(row) if on_disk else self._size_estimate(row))
        self._set_value("libraries", self._libraries_text(row, on_disk))
        self._fill_vars(row)
        self._fill_version(row)
        self._set_value("updates", self._updates_text(row))
        folder = self._field_rows["folder"][1]
        folder.set_full_text(row.folder.as_posix())

        self._show_field("repository", bool(url))
        for key in ("licence", "size", "libraries", "vars"):
            self._show_field(key, True)
        self._show_field("version", installed)
        self._show_field("updates", installed)
        self._show_field("folder", installed or problem)
        self._add_btn.setVisible(row.state is State.NOT_INSTALLED and row.curated is not None)
        self._reinstall_btn.setVisible(row.state is State.FOLDER_MISSING and row.entry is not None)
        listed = row.entry is not None
        self._update_btn.setVisible(installed and listed)
        self._update_btn.setStyleSheet(theme.PRIMARY_BUTTON_QSS if row.state is State.UPDATE_AVAILABLE else "")
        self._remove_btn.setVisible(((installed or row.state is State.FOLDER_MISSING) and listed) or row.state is State.NOT_IN_CATALOG)
        self._vars_btn.setVisible(installed and self._vars_differ)
        self._refresh_detail_buttons()

    # -- the rows --

    def _show_field(self, key: str, visible: bool) -> None:
        label, value = self._field_rows[key]
        label.setVisible(visible)
        value.setVisible(visible)

    def _set_value(self, key: str, text: str) -> None:
        self._field_rows[key][1].setText(text)

    @staticmethod
    def _repository_url(row: status.Row) -> str:
        """The repository page of a row without the .git ending; '' for a folder the record does not list."""
        url = row.entry.url if row.entry is not None else (row.curated.url if row.curated is not None else "")
        return url.removesuffix(".git").rstrip("/")

    def _set_repository(self, url: str) -> None:
        self._field_rows["repository"][1].set_url(url)

    @staticmethod
    def _licence_text(row: status.Row) -> str:
        if row.licence_class is LicenceClass.NOT_STATED:
            text = NOT_STATED_TEXT
        elif row.licence_class is LicenceClass.UNKNOWN:
            text = LICENCE_UNREADABLE_TEXT
        else:
            text = row.licence_label
        entry = row.entry
        if entry is not None and entry.acknowledged:
            when = f" on {entry.acknowledged_on}" if entry.acknowledged_on else ""
            text += f" (you confirmed you read the terms{when})"
        return text

    @staticmethod
    def _size_estimate(row: status.Row) -> str:
        return "Unknown" if row.size_mb is None else f"about {row.size_text}"

    def _size_text(self, row: status.Row) -> str:
        """The folder's size on disk for the Details page; measured off the GUI thread, so it reads Calculating... first."""
        folder = row.folder
        if folder in self._size_cache:
            size = self._size_cache[folder]
            return SIZE_UNKNOWN_TEXT if size is None else SIZE_ON_DISK_TIP.format(size=status.size_text(math.ceil(size / 1_000_000)))
        self._request_size(folder, first=True)
        self._pump_sizes()
        return SIZE_PENDING_TEXT

    def _request_size(self, folder: Path, *, first: bool = False) -> None:
        """Queue a folder for measuring (first puts it next); a measured, queued or running folder is not queued twice."""
        if folder in self._size_cache or (folder == self._size_running and folder not in self._size_stale):
            return
        if folder in self._size_queue:
            if first:
                self._size_queue.remove(folder)
                self._size_queue.insert(0, folder)
            return
        if first:
            self._size_queue.insert(0, folder)
        else:
            self._size_queue.append(folder)

    def _pump_sizes(self) -> None:
        """Start the next measurement when none runs: the folders are measured one after another, never in parallel."""
        if self._size_running is not None or not self._size_queue:
            return
        folder = self._size_queue.pop(0)
        self._size_running = folder
        services, gen = self._services, self._gen
        self._size_task = run_in_background(
            lambda: int(services.size_on_disk(folder)),
            lambda result, g=gen: self._on_size(g, folder, result),
            lambda text, g=gen: self._on_size(g, folder, None),
            name="catalog-folder-size",
        )

    def _on_size(self, gen: int, folder: Path, size: int | None) -> None:
        if gen != self._gen:
            return
        self._size_running = None
        self._size_task = None
        if folder in self._size_stale:  # the folder changed while it was measured: the value is dropped
            self._size_stale.discard(folder)
        else:
            self._size_cache[folder] = size
            self._update_size_cells(folder)
        self._pump_sizes()

    def _update_size_cells(self, folder: Path) -> None:
        """Write a measured size into its list cell and the Details page, in place: selection and search stay."""
        by_id = {row.id: row for row in self._rows}
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            row = by_id.get(item.data(0, _ROW_ID))
            if row is not None and row.folder == folder and self._on_disk(row):
                self._set_size_cell(item, row)
        current = self.current_row()
        if current is not None and current.folder == folder:
            self._refresh_details()

    def _forget_size(self, id: str) -> None:
        """A finished Add, Update or Reinstall changed this library's folder: it is measured again."""
        for row in self._rows:
            if row.id == id:
                folder = row.folder
                self._size_cache.pop(folder, None)
                if folder in self._size_queue:
                    self._size_queue.remove(folder)
                if folder == self._size_running:
                    self._size_stale.add(folder)

    def _libraries_text(self, row: status.Row, on_disk: bool) -> str:
        if on_disk and self._scan is not None:
            prefix = f"ThirdParty/{row.folder.name}/".casefold()

            def count(libraries) -> int:
                return sum(1 for lib in libraries if lib.rel_path.replace("\\", "/").casefold().startswith(prefix))

            return f"{count(self._scan.symbol_libs)} symbol libraries, {count(self._scan.footprint_libs)} footprint libraries"
        known = row.curated
        if known is not None and (known.symbol_libs or known.footprint_libs):
            return f"{known.symbol_libs} symbol libraries, {known.footprint_libs} footprint libraries"
        return LIBRARIES_UNKNOWN_TEXT

    def _fill_vars(self, row: status.Row) -> None:
        """One line per path variable: its name in Mono and whether KiCad has it set to this library's folder (CAT-06)."""
        box = self._field_rows["vars"][1]
        self._clear_layout(box.layout())
        self._vars_differ = False
        names = row.entry.vars if row.entry is not None else (row.curated.vars if row.curated is not None else {})
        wanted = self._services.path_vars(self._root, [CatalogEntry(row.id, "", "", vars=dict(names))])
        if not wanted:
            box.layout().addWidget(_plain_label(NO_VARS_TEXT, wrap=True))
            return
        for name in sorted(wanted):
            text, token = self._var_state(name, wanted[name])
            self._vars_differ = self._vars_differ or text in (VAR_NOT_SET_TEXT, VAR_DIFFERENT_TEXT)
            line = QWidget()
            lay = QHBoxLayout(line)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(theme.SP_SM)
            title = _plain_label(name)
            _mono(title)
            state = _plain_label(text, wrap=True)
            state.setStyleSheet(f"color: {token};")
            lay.addWidget(title)
            lay.addWidget(state, 1)
            box.layout().addWidget(line)

    def _var_state(self, name: str, expected: str) -> tuple[str, str]:
        if not self._vars_read:
            return VARS_PENDING_TEXT, theme.MUTED
        current = self._kicad_vars
        if current is None:
            return VAR_NO_SETTINGS_TEXT, theme.MUTED
        if name not in current:
            return VAR_NOT_SET_TEXT, theme.AMBER
        if _same_path(current[name], expected):
            return VAR_SET_TEXT, theme.SUCCESS
        return VAR_DIFFERENT_TEXT, theme.AMBER

    def _fill_version(self, row: status.Row) -> None:
        box = self._field_rows["version"][1]
        self._clear_layout(box.layout())
        entry = row.entry
        if entry is None:
            return
        commit = _plain_label(entry.commit[:7] if entry.commit else UNKNOWN_TEXT)
        if entry.commit:
            _mono(commit)
        box.layout().addWidget(commit)
        if entry.added_on:
            box.layout().addWidget(_plain_label(f"(added {entry.added_on})"))
        box.layout().addStretch(1)

    def _updates_text(self, row: status.Row) -> str:
        if self._checking():
            return UPDATES_CHECKING_TEXT
        update = row.update
        if update is None or update.check is Check.NOT_CHECKED:
            return UPDATES_NEVER_TEXT
        if update.check is Check.UNKNOWN:
            return UPDATES_OFFLINE_TEXT
        if update.check is Check.BRANCH_GONE:
            return UPDATES_BRANCH_GONE_TEXT
        when = f" {time_wording(update.checked_at, self._clock())}" if update.checked_at is not None else ""
        outcome = "an update is available" if update.check is Check.AVAILABLE else "up to date"
        return f"Checked{when}: {outcome}"

    def _fill_problem_strip(self, row: status.Row) -> None:
        text, token, amber = "", theme.ERROR, False
        if row.state is State.FOLDER_MISSING:
            text = FOLDER_MISSING_STRIP.format(folder=row.folder.as_posix(), repository=self._repository_url(row))
        elif row.state is State.NOT_IN_CATALOG:
            text, token, amber = NOT_IN_CATALOG_STRIP, theme.AMBER, True
        elif row.state is State.UPDATE_AVAILABLE and row.entry is not None and row.update is not None:
            text = UPDATE_STRIP.format(installed=row.entry.commit[:7], available=(row.update.remote_sha or "")[:7])
            token, amber = theme.AMBER, True
        if not text:
            self._problem_strip.hide()
            return
        self._problem_strip.setStyleSheet(
            f"QFrame#problemStrip {{ background-color: {theme.AMBER_TINT}; border-left: 2px solid {theme.AMBER}; }}"
            if amber
            else f"QFrame#problemStrip {{ border: 1px solid {theme.BORDER}; }}"
        )
        self._problem_label.setStyleSheet(f"color: {token};")
        self._problem_label.setText(text)
        self._problem_label.setAccessibleName(text)
        self._problem_strip.show()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # -- the result strip --

    def show_result(self, lines: list[tuple[str, str]], *, generate: bool, manifest_note: bool) -> None:
        """Show what a job did on the selected row's page, until another row is selected or another action starts.

        lines are (text, level) with level "success" or "warning"; the window adds the glyph. generate adds the
        Generate Tables button; manifest_note adds the catalog.json line (only when the root is a git repository, D-03).
        """
        self._result = (list(lines), bool(generate), bool(manifest_note))
        self._shown_id = self.selected_id()
        self._fill_result()

    def _fill_result(self) -> None:
        self._render_result(self._result, self._result_strip, self._result_lines_box, self._result_note, self._result_generate_btn)

    def _render_result(self, result, frame: QFrame, box: QVBoxLayout, note_label: QLabel, button: QPushButton) -> None:
        """Fill one result strip (the Details page's, or the empty page's for a row that left the list) from a result."""
        self._clear_layout(box)
        if result is None:
            frame.hide()
            return
        lines, generate, note = result
        for text, level in lines:
            glyph, token = ("✓ ", theme.SUCCESS) if level == "success" else ("⚠ ", theme.AMBER)
            label = _plain_label(glyph + text, wrap=True)
            label.setObjectName("resultLine")
            label.setStyleSheet(f"color: {token};")
            label.setAccessibleName(label.text())
            box.addWidget(label)
        is_git = (self._root / ".git").exists()
        note_label.setText(MANIFEST_NOTE_TEXT.format(collection=self._root.as_posix()) if note and is_git else "")
        note_label.setVisible(bool(note and is_git))
        button.setVisible(generate)
        frame.show()

    # ── Strips and actions ────────────────────────────────────────────────────────────────────

    def _update_strips(self) -> None:
        mf = self._mf
        if isinstance(mf, Issue):
            text = RECORD_STRIP_TEXT.format(reason=mf.text, collection=self._root.as_posix())
            self._record_label.setText(text)
            self._record_label.setToolTip(text)
            self._record_label.setAccessibleName(text)
            self._record_strip.show()
        else:
            self._record_strip.hide()
        missing = too_old = old = False
        net = self._net_status
        if net is not None and net.refusal is not None:
            text = ERROR_GLYPH + net.refusal.text
            if net.refusal.code == "git.too_old":
                too_old = True
                self._git_too_old_label.setText(text)
                self._git_too_old_label.setAccessibleName(text)
            else:
                missing = True
                self._git_missing_label.setText(text)
                self._git_missing_label.setAccessibleName(text)
        elif net is not None and net.warning is not None:
            old = True
            text = WARNING_GLYPH + net.warning.text
            self._git_old_label.setText(text)
            self._git_old_label.setAccessibleName(text)
        self._git_missing_strip.setVisible(missing)
        self._git_too_old_strip.setVisible(too_old)
        self._git_old_strip.setVisible(old)
        self._apply_split()

    def _external_block(self) -> str | None:
        """Why the actions cannot run for a reason outside this window's own job, or None."""
        if self._finishing:
            return FINISHING_TIP
        if self._blocked:
            return self._blocked
        if isinstance(self._mf, Issue):
            return RECORD_UNREADABLE_TIP
        net = self._net_status
        if net is None:
            return GIT_CHECKING_TIP
        if net.refusal is not None:
            if net.refusal.code == "git.too_old":
                return GIT_TOO_OLD_TIP
            return GIT_MISSING_TIP if net.refusal.code == "git.not_found" else net.refusal.text
        return None

    def _action_block(self) -> str | None:
        """Why the network actions cannot run right now, or None when they can."""
        job = self._job
        if job is not None:
            return WAIT_TIP.format(job=job_label(job.flow, job.name))
        return self._external_block()

    def _checking(self) -> bool:
        return self._manual_check or self._external_check

    def _refresh_actions(self) -> None:
        reason = self._action_block()
        checking = self._checking()
        page_open = self._flow is not None
        tip = reason or (PAGE_OPEN_TIP if page_open else "")
        self._check_btn.setText(CHECKING_TEXT if checking else CHECK_TEXT)
        self._check_btn.setEnabled(reason is None and not checking and not page_open)
        self._check_btn.setToolTip(tip)
        self._add_url_btn.setEnabled(reason is None and not page_open)
        self._add_url_btn.setToolTip(tip)
        self._refresh_detail_buttons()
        external, busy = self._external_block(), self._job is not None
        for page in (self._url_page, self._licence_page, self._preview_page, self._update_page, self._remove_page):
            page.set_blocked(external)
            page.set_busy(busy)

    def _refresh_detail_buttons(self) -> None:
        """Enable the Details buttons: every one waits for a job or an outside reason, Update also needs an update to apply."""
        reason = self._action_block()
        row = self.current_row()
        for button in (self._add_btn, self._reinstall_btn, self._remove_btn, self._vars_btn):
            button.setEnabled(reason is None)
            button.setToolTip(reason or "")
        update = row is not None and row.state is State.UPDATE_AVAILABLE
        self._update_btn.setEnabled(reason is None and update)
        if reason:
            tip = reason
        elif update or row is None:
            tip = ""
        elif row.update is not None and row.update.check is Check.CURRENT:
            tip = UPDATE_CURRENT_TIP
        else:
            tip = UPDATE_UNKNOWN_TIP
        self._update_btn.setToolTip(tip)

    def _on_check_clicked(self) -> None:
        """Check for Updates on a daemon thread; the result is dropped when the window closed or the collection changed."""
        if self._checking() or self._action_block() is not None or isinstance(self._mf, Issue):
            return
        services, root, mf, net = self._services, self._root, self._mf, self._net_status.net
        cancel, gen = self._check_cancel, self._gen
        self._manual_check = True
        self._refresh_actions()
        self._refresh_details()
        self._track(
            run_in_background(
                lambda: services.check_updates(root, mf, net, cancel=cancel),
                lambda states: self._on_check_done(gen, states),
                lambda text: self._on_check_failed(gen, text),
                name="catalog-update-check",
            )
        )

    def _on_check_done(self, gen: int, states) -> None:
        if gen != self._gen:
            return
        self._manual_check = False
        self._updates = dict(states)
        self._rebuild_rows()
        self._refresh_actions()
        self._refresh_details()
        self.update_states_changed.emit(self._updates)
        names = [row.name for row in self._rows if row.state is State.UPDATE_AVAILABLE]
        line = status.updates_line(names)
        if line is not None:
            self.log_line.emit(line, "info")
            return
        checks = [state.check for state in self._updates.values()]
        if checks and all(check is Check.UNKNOWN for check in checks):
            self.log_line.emit(CHECK_OFFLINE_LINE, "warning")
            return
        current = sum(1 for check in checks if check is Check.CURRENT)
        noun = "library" if current == 1 else "libraries"
        self.log_line.emit(f"Checked {current} catalog {noun}: all up to date.", "info")

    def _on_check_failed(self, gen: int, text: str) -> None:
        if gen != self._gen:
            return
        self._manual_check = False
        self._refresh_actions()
        self._refresh_details()
        self.log_line.emit(STEP_FAILED.format(text=text), "error")

    # ── The API the main window and the next plans use ────────────────────────────────────────

    def set_root(self, root: Path) -> None:
        """Show another collection: header, list, strips and statuses reload in one step, any open page is dropped."""
        self._stop_background()
        self._release_download()
        self._abandon_flow()
        self._root = Path(root)
        self._updates = {}
        self._scan = None
        self._tree.clearSelection()
        self._tree.setCurrentIndex(QModelIndex())
        self._reload(reset=True)

    def set_scan(self, result) -> None:
        """The main window's last scan; the Details page counts the libraries of an installed library from it."""
        self._scan = result
        self._refresh_details()

    def set_blocked(self, reason: str | None) -> None:
        """Disable the actions with this reason as tooltip (a scan, the import or migration window); None lifts it."""
        self._blocked = reason or None
        self._refresh_actions()

    def apply_update_states(self, states) -> None:
        """The result of the startup check (or any check): show it in the rows."""
        self._updates = dict(states)
        self._rebuild_rows()

    def set_check_running(self, running: bool) -> None:
        """The main window's startup check runs: the button reads Checking... and the Updates row follows."""
        self._external_check = bool(running)
        self._refresh_actions()
        self._refresh_details()

    def refresh(self) -> None:
        """Read the record and the folders again and rebuild the rows; the background checks are not restarted."""
        self._load()

    def is_job_running(self) -> bool:
        """True while a catalog job runs: planning, a repository check, a download, the final Add or a discard."""
        return self._job is not None

    def holds_download(self) -> bool:
        """True while a downloaded copy waits for the user's answer on a review page (or is being deleted)."""
        return self._staged is not None

    def set_kicad_fp_dir(self, path: Path | None) -> None:
        """KiCad's footprint folder, where the stock library names are read from (inside the download job)."""
        self._kicad_fp_dir = Path(path) if path else None

    def is_finishing(self) -> bool:
        return self._finishing

    def set_finishing(self, on: bool) -> None:
        """The main window rescans and asks about path variables after a change; every action waits (D-18)."""
        on = bool(on)
        if on == self._finishing:
            return
        self._finishing = on
        self._refresh_actions()
        self.busy_changed.emit()

    # ── The Add, Add by URL and Reinstall flows ───────────────────────────────────────────────

    # -- the job strip and the runner --

    def _build_job_strip(self) -> QWidget:
        """The job strip: a step label, a progress bar and a cancel button named for the job; shown only while one runs."""
        strip = QWidget()
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP_SM)
        self._job_label = ElidedLabel("", mode=Qt.TextElideMode.ElideRight, full_tooltip=True)
        self._job_bar = QProgressBar()
        self._job_bar.setFixedWidth(JOB_BAR_WIDTH)
        self._job_bar.setTextVisible(False)
        self._job_bar.setRange(0, 0)
        self._job_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {theme.BORDER}; background-color: {theme.SURFACE_BASE}; height: 12px; }}"
            f"QProgressBar::chunk {{ background-color: {theme.ACCENT}; }}"
        )
        self._job_cancel = QPushButton()
        self._job_cancel.setAutoDefault(False)
        self._job_cancel.setMinimumHeight(CONTROL_HEIGHT)
        self._job_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self._job_label, 1)
        layout.addWidget(self._job_bar)
        layout.addWidget(self._job_cancel)
        strip.hide()
        self._job_strip = strip
        return strip

    def _spawn(self, fn: Callable, tag=None) -> TaskWorker:
        """Create a worker owned by the window; it stays referenced until the window goes (a finished one is never deleted early)."""
        worker = TaskWorker(fn, parent=self, tag=tag)
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._reap(w))
        return worker

    def _reap(self, worker: TaskWorker) -> None:
        """Join a finished worker; QThread.finished arrives just before the thread ends, so the bounded wait is short."""
        worker.wait(2000)

    def _start_job(self, phase: str, flow: str, name: str, fn: Callable, on_done: Callable) -> _Job:
        """Run fn(progress, cancel) on a worker as the one job; on_done(job, value) runs on the GUI thread when it ends."""
        job = _Job(phase, flow, name, threading.Event(), self._gen, on_done)

        def run(emit):
            def progress(text, percent, total=0):
                emit(text, -1 if percent is None else int(percent), int(total))

            return fn(progress, job.cancel)

        worker = self._spawn(run, tag=job)
        job.worker = worker
        worker.progress.connect(lambda text, percent, total, j=job: self._on_job_progress(j, percent, total, text))
        worker.result.connect(lambda value, j=job: self._on_job_result(j, value))
        worker.failed.connect(lambda text, j=job: self._on_job_failed(j, text))
        self._job = job
        self._show_job(job)
        self._refresh_actions()
        self._emit_busy()
        worker.start()
        return job

    def _show_job(self, job: _Job) -> None:
        label = job_label(job.flow, job.name)
        self._job_bar.setAccessibleName(f"Progress of {label}")
        self._job_bar.setRange(0, 0)
        if job.phase in ("plan", "discard"):
            self._job_strip.hide()
            return
        again = job.flow == "reinstall"
        stoppable, unstoppable_tip = True, REGISTER_CANCEL_TIP
        if job.phase == "check":
            text, cancel = CHECKING_REPOSITORY_TEXT, CANCEL_CHECK_TEXT
        elif job.phase == "look":
            text, cancel = LOOKING_TEXT.format(name=job.name), CANCEL_UPDATING_TEXT
        elif job.phase == "apply":
            text, cancel = UPDATING_NAME_TEXT.format(name=job.name), CANCEL_UPDATING_TEXT
        elif job.phase == "remove":
            text, cancel = REMOVING_NAME_TEXT.format(name=job.name), CANCEL_REMOVING_TEXT
            stoppable, unstoppable_tip = False, REMOVE_CANCEL_TIP
        else:
            cancel = CANCEL_REINSTALLING_TEXT if again else CANCEL_ADDING_TEXT
            if job.phase == "stage":
                text = (DOWNLOADING_AGAIN_TEXT if again else DOWNLOADING_TEXT).format(name=job.name)
            else:
                text = ADDING_NAME_TEXT.format(name=job.name)
                stoppable = False
        self._set_job_text(text)
        self._job_cancel.setText(cancel)
        self._job_cancel.setEnabled(stoppable)
        self._job_cancel.setToolTip(CANCEL_TIP.format(job=label) if stoppable else unstoppable_tip)
        self._job_strip.show()

    def _set_job_text(self, text: str) -> None:
        self._job_label.set_full_text(text)

    def _on_job_progress(self, job: _Job, percent: int, total: int = 0, text: str = "") -> None:
        if job is not self._job or job.phase != "stage" or job.stopping:
            return
        if text == _FILES_STEP:  # the check of the downloaded files: percent carries the files done
            if total <= 0:
                return
            job.checking = True
            whole = min(100, percent * 100 // total)
            self._job_bar.setRange(0, 100)
            self._job_bar.setValue(whole)
            self._set_job_text(CHECKING_FILES_TEXT.format(name=job.name, percent=whole, done=f"{percent:,}", total=f"{total:,}"))
            return
        if job.checking:
            return
        again = job.flow == "reinstall"
        if percent < 0:
            self._job_bar.setRange(0, 0)
            text = (DOWNLOADING_AGAIN_TEXT if again else DOWNLOADING_TEXT).format(name=job.name)
        elif percent >= 100:  # the download is complete; what follows is the check of its files
            self._job_bar.setRange(0, 0)
            text = CHECKING_NAME_TEXT.format(name=job.name)
        else:
            self._job_bar.setRange(0, 100)
            self._job_bar.setValue(percent)
            template = DOWNLOADING_AGAIN_PERCENT_TEXT if again else DOWNLOADING_PERCENT_TEXT
            text = template.format(name=job.name, percent=percent)
        self._set_job_text(text)

    def _on_cancel_clicked(self) -> None:
        job = self._job
        if job is not None and job.phase in _STOPPABLE and not job.stopping:
            self._cancel_job(job)

    def _cancel_job(self, job: _Job) -> None:
        """Ask the job to stop; the job ends by itself (git's process tree is ended through the cancel event)."""
        job.stopping = True
        job.cancel.set()
        self._job_bar.setRange(0, 0)
        self._set_job_text(STOPPING_TEXT)
        self._job_cancel.setEnabled(False)

    def _end_job(self) -> None:
        self._job = None
        self._job_strip.hide()
        self._refresh_actions()

    def _emit_busy(self) -> None:
        state = (self.is_job_running(), self.holds_download())
        if state != self._busy_sent:
            self._busy_sent = state
            self.busy_changed.emit()

    def _on_job_result(self, job: _Job, value) -> None:
        if job is not self._job:  # an abandoned job: its answer is dropped
            return
        self._end_job()
        closing = self._pending_close is not None
        if job.on_done is not None and not (closing and job.phase in ("plan", "check")):
            job.on_done(job, value)
        self._emit_busy()
        self._complete_pending_close()

    def _on_job_failed(self, job: _Job, text: str) -> None:
        if job is not self._job:
            return
        self._end_job()
        self.log_line.emit(STEP_FAILED.format(text=text), "error")
        if self._pending_close is None:
            phase = job.phase
            if phase == "plan":
                self._leave_pages(clear_selection=bool(self._flow and self._flow.url))
            elif phase == "check":
                self._url_page.show_refusals([Issue(Severity.ERROR, "catalog.step_failed", CHECK_CRASHED_TEXT)])
            elif phase == "stage":
                self._show_refusal(Issue(Severity.ERROR, "catalog.step_failed", STAGE_CRASHED_TEXT))
            elif phase == "register":
                self._preview_page.show_notice(REGISTER_CRASHED_TEXT)
            elif phase == "look":
                self._show_update_refusal(Issue(Severity.ERROR, "catalog.step_failed", UPDATE_CRASHED_TEXT))
            elif phase == "apply":
                self._log_could_not("update", Issue(Severity.ERROR, "catalog.step_failed", UPDATE_CRASHED_TEXT))
                self._update_page.show_notice(UPDATE_CRASHED_TEXT)
            elif phase == "remove":
                issue = Issue(Severity.ERROR, "catalog.step_failed", REMOVE_CRASHED_TEXT)
                self._log_could_not("remove", issue)
                self._remove_page.show_refusal(issue)
                flow = self._flow
                if flow is not None:
                    self._emit_outcome(flow, ok=False)
                self.refresh()  # the disk may have changed before the worker failed
            else:  # discard
                self._staged = None
                self._leave_pages(clear_selection=bool(self._flow and self._flow.url))
        self._emit_busy()
        self._complete_pending_close()

    def _complete_pending_close(self) -> None:
        if self._pending_close is not None and self._job is None:
            r, self._pending_close = self._pending_close, None
            self._complete_close(r)

    # -- the pages --

    def _review_page(self) -> ReviewPage | None:
        pages = {
            "url": self._url_page, "licence": self._licence_page, "preview": self._preview_page,
            "update": self._update_page, "remove": self._remove_page,
        }
        return pages.get(self._page_kind)

    def _enter_page(self, kind: str) -> None:
        """Show a review page: the list locks to the chosen library, Close gives up its default, focus follows."""
        self._page_kind = kind
        self._lock_list(True)
        self._show_page(self._review_page())
        self._update_default_button()
        self._refresh_actions()
        self._focus_timer.start()

    def _leave_pages(self, *, clear_selection: bool = False) -> None:
        """Back to the list: its row's Details (or the empty pane), the list unlocked and focused."""
        self._page_kind = None
        self._flow = None
        self._lock_list(False)
        if clear_selection:
            self._tree.clearSelection()
            self._tree.setCurrentIndex(QModelIndex())
        self._refresh_details()
        self._update_default_button()
        self._refresh_actions()
        self._tree.setFocus()

    def _lock_list(self, locked: bool) -> None:
        """While a page is open the list stays on the chosen library (no other row, no search that could hide it)."""
        self._tree.setEnabled(not locked)
        self._search.setEnabled(not locked)

    def _update_default_button(self) -> None:
        """Close is the default button on the idle list view only; never on a review page, so Enter cannot dismiss a preview."""
        idle = self._page_kind is None
        self._close_btn.setAutoDefault(idle)
        self._close_btn.setDefault(idle)
        # the Remove page's Keep Library is the default button while that page is open (Enter keeps the library)
        self._remove_page.back_button().setDefault(self._page_kind == "remove")

    def _focus_page(self) -> None:
        page = self._review_page()
        if page is not None:
            page.focus_first()

    def _on_page_back(self) -> None:
        flow = self._flow
        self._leave_pages(clear_selection=bool(flow is not None and (flow.url or flow.kind == "url")))

    def _details_primary(self) -> QPushButton | None:
        if self._pages.currentWidget() is not self._details_page or self._flow is not None:
            return None
        for button in (self._add_btn, self._reinstall_btn, self._update_btn):
            if button.isVisibleTo(self._details_page) and button.isEnabled():
                return button
        return None

    def keyPressEvent(self, event) -> None:
        """Esc presses a review page's back button (never a confirm); Ctrl+Return presses the enabled primary."""
        page = self._review_page()
        key = event.key()
        if key == Qt.Key.Key_Escape and page is not None:
            if page.back_button().isEnabled():
                page.back_button().click()
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            button = page.primary_button() if page is not None else self._details_primary()
            if page is not None and not page.primary_accepts_ctrl_return():
                button = None  # Ctrl+Return never confirms a deletion
            if button is not None and button.isEnabled() and button.isVisibleTo(self):
                button.click()
            event.accept()
            return
        super().keyPressEvent(event)

    # -- Add and Reinstall from the Details page --

    def _on_add_clicked(self) -> None:
        row = self.current_row()
        if row is not None and row.curated is not None and row.state is State.NOT_INSTALLED:
            self._begin_flow("add", row)

    def _on_reinstall_clicked(self) -> None:
        row = self.current_row()
        if row is not None and row.entry is not None and row.state is State.FOLDER_MISSING:
            self._begin_flow("reinstall", row)

    def _begin_flow(self, kind: str, row: status.Row) -> None:
        """Plan the Add or Reinstall off the GUI thread (free space and running KiCad are read there), then open the licence page."""
        mf = self._mf
        if self._action_block() is not None or self._flow is not None or isinstance(mf, Issue):
            return
        services, root = self._services, self._root
        self._flow = _Flow(kind, row.id, row.name)
        self._lock_list(True)
        known, entry = row.curated, row.entry

        def plan(progress, cancel):
            if kind == "add":
                return services.plan_add(root, known, mf, free_space=services.free_space, running=services.kicad_running)
            return services.plan_reinstall(root, entry, mf, free_space=services.free_space, running=services.kicad_running)

        self._start_job("plan", kind, row.name, plan, self._on_planned)

    def _on_planned(self, job: _Job, plan) -> None:
        flow = self._flow
        if flow is None:
            return
        flow.plan = plan
        self._licence_page.show_plan(plan, reinstall=plan.reinstall, acknowledged_on=plan.acknowledged_on, name=flow.name)
        self._enter_page("licence")

    # -- Add by URL --

    def _on_add_url(self) -> None:
        if self._flow is not None or self._action_block() is not None:
            return
        self._tree.clearSelection()
        self._tree.setCurrentIndex(QModelIndex())
        self._flow = _Flow("url")
        self._url_page.reset()
        self._enter_page("url")

    def _on_url_primary(self) -> None:
        text = self._url_page.address()
        mf, net = self._mf, self._net_status
        if not text or self._action_block() is not None or isinstance(mf, Issue) or net is None or net.net is None:
            return
        self._url_page.show_refusals([])
        services, root, git = self._services, self._root, net.net

        def check(progress, cancel):
            checked = services.check_repository(root, text, mf, git, repo_info=services.repo_info, cancel=cancel)
            if isinstance(checked, Issue) or cancel.is_set():
                return checked
            plan = services.plan_add(root, checked, mf, free_space=services.free_space, running=services.kicad_running)
            return checked, plan

        self._start_job("check", "check", "", check, self._on_checked)

    def _on_checked(self, job: _Job, value) -> None:
        if job.stopping or self._flow is None:
            return  # stopped: the address page stays as it was, the field editable
        if isinstance(value, Issue):
            self._url_page.show_refusals([value])
            return
        checked, plan = value
        ref = checked.ref
        display = f"{ref.owner}/{ref.repo}" if ref.owner else plan.name
        self._flow = _Flow("add", plan.source.id, display, plan, url=True)
        self._licence_page.show_plan(plan, reinstall=False, acknowledged_on="", name=display, address=ref.https_url)
        self._enter_page("licence")

    # -- the download --

    def _nickname_maps(self, id: str) -> tuple[dict[str, str], dict[str, str]]:
        """The nicknames the download may clash with, from the last scan: your own libraries and the other catalog libraries."""
        own: dict[str, str] = {}
        other: dict[str, str] = {}
        scan = self._scan
        if scan is None:
            return own, other
        names = {row.id.casefold(): row.name for row in self._rows}
        for lib in (*scan.symbol_libs, *scan.footprint_libs):
            rel = lib.rel_path.replace("\\", "/")
            if rel.startswith(f"{THIRD_PARTY_DIR}/"):
                if lib.source.casefold() != id.casefold():
                    other.setdefault(lib.nickname, names.get(lib.source.casefold(), lib.source))
            elif lib.source == OWN_DIR:
                own.setdefault(lib.nickname, OWN_ATOMIC_TEXT if lib.nickname.startswith("Atomic_") else OWN_CUSTOM_TEXT)
        return own, other

    def _start_download(self) -> None:
        flow, net = self._flow, self._net_status
        if flow is None or flow.plan is None or self._action_block() is not None or net is None or net.net is None:
            return
        own, other = self._nickname_maps(flow.id)
        services, root, fp_dir, plan, git = self._services, self._root, self._kicad_fp_dir, flow.plan, net.net

        def stage(progress, cancel):
            stock_fp = frozenset(services.stock_fp(fp_dir))
            stock_sym = frozenset(services.stock_sym(fp_dir))
            sent = [-1]

            def check_progress(done: int, total: int) -> None:
                """Forward one count per whole percent, and the last: a large library has over ten thousand files."""
                whole = done * 100 // total if total > 0 else 0
                if whole != sent[0] or done >= total:
                    sent[0] = whole
                    progress(_FILES_STEP, done, total)

            result = services.stage_add(
                root, plan, git, progress=progress, cancel=cancel, stock_fp=stock_fp, stock_sym=stock_sym,
                own=own, other_catalog=other, free_space=services.free_space, check_progress=check_progress,
            )
            if cancel.is_set():  # a download that finished as the user pressed Cancel is deleted, never shown
                if isinstance(result, ops.Staged):
                    services.discard_staging(result)
                return _STOPPED
            return result

        self._start_job("stage", flow.kind, flow.name, stage, self._on_staged)

    def _on_staged(self, job: _Job, value) -> None:
        flow = self._flow
        if flow is None:
            return
        if value is _STOPPED or job.stopping:
            line = LOG_STOPPED_REINSTALLING if flow.kind == "reinstall" else LOG_STOPPED_ADDING
            self.log_line.emit(line.format(name=flow.name), "info")
            self._emit_outcome(flow, ok=False)
            self._leave_pages(clear_selection=flow.url)
            return
        if isinstance(value, Issue):
            self._show_refusal(value)
            return
        self._staged = value
        self._preview_page.show_staged(
            value, flow.plan, root_is_repo=(self._root / ".git").exists(),
            name=flow.name if flow.url else None, licence_confirmed=self._licence_page.acknowledged(),
        )
        self._enter_page("preview")

    def _show_refusal(self, issue: Issue) -> None:
        """A refused or failed download: the ✖ row with Back to List (and Try Again for a failed download); nothing was added."""
        flow = self._flow
        if flow is None:
            return
        verb = "reinstall" if flow.kind == "reinstall" else "add"
        self.log_line.emit(LOG_COULD_NOT.format(verb=verb, name=flow.name, text=issue.text), "error")
        heading = (catalog_pages.REINSTALL_HEADING if flow.kind == "reinstall" else catalog_pages.ADD_HEADING).format(name=flow.name)
        self._preview_page.show_refusal(issue, can_retry=issue.code in RETRY_CODES, heading=heading)
        self._enter_page("preview")
        self._emit_outcome(flow, ok=False)

    def _emit_outcome(self, flow: _Flow, *, ok: bool, **fields) -> None:
        kind = flow.kind if flow.kind in ("reinstall", "update", "remove") else "add"
        self.job_finished.emit(CatalogOutcome(kind, flow.id, flow.name, ok, **fields))

    # -- the preview: Add Library, Discard Download, Try Again --

    def _on_preview_primary(self) -> None:
        if self._preview_page.is_refusal():  # Try Again
            self._start_download()
            return
        flow, staged, net = self._flow, self._staged, self._net_status
        if flow is None or staged is None or self._action_block() is not None:
            return
        acknowledged = self._licence_page.acknowledged() or self._preview_page.acknowledged()
        today = self._clock().date().isoformat()
        services, root = self._services, self._root

        def register(progress, cancel):
            return services.register_add(root, staged, acknowledged=acknowledged, today=today)

        self._start_job("register", flow.kind, flow.name, register, self._on_registered)

    def _on_registered(self, job: _Job, issues) -> None:
        flow, staged = self._flow, self._staged
        if flow is None or staged is None:
            return
        errors = [issue for issue in issues if issue.severity is Severity.ERROR]
        verb = "reinstall" if flow.kind == "reinstall" else "add"
        if errors:  # the download is still waiting: the preview shows why, and Add Library or Discard Download remain
            text = errors[0].text
            self.log_line.emit(LOG_COULD_NOT.format(verb=verb, name=flow.name, text=text), "error")
            self._preview_page.show_notice(text)
            return
        for issue in issues:
            self.log_line.emit(issue.text, issue.severity.value)
        report = staged.report
        symbols = len(report.symbol_libs) if report is not None else 0
        footprints = len(report.footprint_libs) if report is not None else 0
        collisions = tuple(report.collisions) if report is not None else ()
        variables = dict(staged.vars) if staged.vars is not None else dict(staged.source.vars)
        plan = flow.plan
        outcome = CatalogOutcome(
            "reinstall" if flow.kind == "reinstall" else "add", flow.id, flow.name, True, symbols, footprints,
            collisions, variables, plan.legacy_prefix if plan is not None else None, (self._root / ".git").exists(),
        )
        self._staged = None
        self._flow = None
        self._page_kind = None
        self._lock_list(False)
        self._forget_size(flow.id)
        # the library was just downloaded at its recorded commit, so its row reads installed and current
        self._updates[flow.id] = status.UpdateState(flow.id, Check.CURRENT, staged.commit, self._clock())
        self.refresh()
        self._select_row(flow.id)
        template = RESULT_REINSTALLED if outcome.kind == "reinstall" else RESULT_ADDED
        lines = [(template.format(name=flow.name, s=symbols, f=footprints), "success")]
        if collisions:
            lines.append((RESULT_CLASHES.format(n=len(collisions)), "warning"))
        self.show_result(lines, generate=True, manifest_note=True)
        self._refresh_details()
        self._update_default_button()
        self._refresh_actions()
        self._tree.setFocus()
        self._emit_busy()
        self.job_finished.emit(outcome)

    def _select_row(self, id: str) -> None:
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item.data(0, _ROW_ID) == id and not item.isHidden():
                self._tree.setCurrentItem(item)
                item.setSelected(True)
                return

    def _on_preview_back(self) -> None:
        flow = self._flow
        if self._preview_page.is_refusal() or self._staged is None or flow is None:  # Back to List
            self._leave_pages(clear_selection=bool(flow is not None and flow.url))
            return
        staged, services = self._staged, self._services

        def discard(progress, cancel):
            return services.discard_staging(staged)

        self._start_job("discard", flow.kind, flow.name, discard, self._on_discarded)

    def _on_discarded(self, job: _Job, issue) -> None:
        flow = self._flow
        name = flow.name if flow is not None else ""
        if isinstance(issue, Issue):  # the leftover is cleaned up at the next start
            self.log_line.emit(LOG_DISCARD_FAILED.format(name=name, text=issue.text), "error")
        else:
            self.log_line.emit(LOG_DISCARDED.format(name=name), "info")
        self._staged = None
        if flow is not None:
            self._emit_outcome(flow, ok=False)
        self._leave_pages(clear_selection=bool(flow is not None and flow.url))

    def _release_download(self) -> None:
        """Delete a waiting download now, on the GUI thread (the window is closing or the collection changed)."""
        staged = self._staged
        if staged is None:
            return
        name = self._flow.name if self._flow is not None else (staged.plan.name if staged.plan is not None else staged.source.name)
        issue = self._services.discard_staging(staged)
        self._staged = None
        if isinstance(issue, Issue):
            self.log_line.emit(LOG_DISCARD_FAILED.format(name=name, text=issue.text), "error")
        else:
            self.log_line.emit(LOG_DISCARDED.format(name=name), "info")

    def _abandon_flow(self) -> None:
        """Drop the job, the page and the flow without asking: the window closed or the collection changed."""
        job = self._job
        if job is not None:
            job.cancel.set()
            job.dropped = True
            self._job = None
            self._job_strip.hide()
        self._flow = None
        self._page_kind = None
        self._lock_list(False)
        self._update_default_button()
        self._refresh_actions()
        self._emit_busy()

    # ── Update, Remove and Set Path Variables... ──────────────────────────────────────────────

    def _log_could_not(self, verb: str, issue: Issue) -> None:
        """The error line of a refused or failed job: `Could not {verb} {name}: {text}` (a text that says so already is kept as it is)."""
        flow = self._flow
        name = flow.name if flow is not None else ""
        text = issue.text if issue.text.startswith(f"Could not {verb} ") else LOG_COULD_NOT.format(verb=verb, name=name, text=issue.text)
        self.log_line.emit(text, "error")

    def _on_vars_clicked(self) -> None:
        row = self.current_row()
        if row is not None and self._action_block() is None:
            self.path_vars_requested.emit(row.id)

    # -- Update --

    def _on_update_clicked(self) -> None:
        """Update This Library: look for changes first (the folder is not touched); the preview is the next stop."""
        row, net = self.current_row(), self._net_status
        if (
            row is None or row.entry is None or row.state is not State.UPDATE_AVAILABLE or self._flow is not None
            or self._action_block() is not None or net is None or net.net is None or isinstance(self._mf, Issue)
        ):
            return
        self._flow = _Flow("update", row.id, row.name)
        self._lock_list(True)
        services, root, entry, git = self._services, self._root, row.entry, net.net

        def look(progress, cancel):
            return services.plan_update(root, entry, git, progress=progress, cancel=cancel, running=services.kicad_running)

        self._start_job("look", "update", row.name, look, self._on_looked)

    def _on_looked(self, job: _Job, value) -> None:
        flow = self._flow
        if flow is None or flow.kind != "update":
            return
        if job.stopping:
            self._stopped_update(flow)
            return
        if isinstance(value, Issue):
            self._show_update_refusal(value)
            return
        flow.plan = value
        page, name = self._update_page, flow.name
        if value.refusal is not None:
            self._log_could_not("update", value.refusal)
            if value.dirty:
                page.show_dirty(value, name=name)
            else:
                page.show_refusal(value.refusal, heading=catalog_pages.UPDATE_HEADING.format(name=name))
            self._emit_outcome(flow, ok=False)
        elif value.current:
            page.show_current(name)
            # the check said a newer version exists, but this folder already is at the fetched commit
            self._updates[flow.id] = status.UpdateState(flow.id, Check.CURRENT, value.new, self._clock())
            self._rebuild_rows()
            self.update_states_changed.emit(self._updates)
        else:
            page.show_plan(value, name=name)
        self._enter_page("update")

    def _stopped_update(self, flow: _Flow) -> None:
        self.log_line.emit(LOG_STOPPED_UPDATING.format(name=flow.name), "info")
        self._emit_outcome(flow, ok=False)
        self._leave_pages()

    def _show_update_refusal(self, issue: Issue) -> None:
        """A failed or refused look for changes: the ✖ row with Back to List; nothing was changed."""
        flow = self._flow
        if flow is None:
            return
        self._log_could_not("update", issue)
        self._update_page.show_refusal(issue, heading=catalog_pages.UPDATE_HEADING.format(name=flow.name))
        self._enter_page("update")
        self._emit_outcome(flow, ok=False)

    def _on_update_primary(self) -> None:
        """Update Library on the preview: the one place apply_update is called from, and only for the previewed commit."""
        flow, net = self._flow, self._net_status
        plan = flow.plan if flow is not None else None
        if (
            flow is None or flow.kind != "update" or not isinstance(plan, ops.UpdatePlan) or plan.refusal is not None
            or plan.current or self._action_block() is not None or net is None or net.net is None
        ):
            return
        services, root, git = self._services, self._root, net.net

        def apply(progress, cancel):
            return services.apply_update(root, plan, git, cancel=cancel)

        self._start_job("apply", "update", flow.name, apply, self._on_applied)

    def _on_applied(self, job: _Job, issues) -> None:
        flow = self._flow
        plan = flow.plan if flow is not None else None
        if flow is None or not isinstance(plan, ops.UpdatePlan):
            return
        if any(issue.code == "git.cancelled" for issue in issues):
            self._stopped_update(flow)
            return
        errors = [issue for issue in issues if issue.severity is Severity.ERROR]
        if errors:  # the preview stays: it says why, and Update Library or Keep Current Version remain
            self._log_could_not("update", errors[0])
            self._update_page.show_notice(errors[0].text)
            return
        for issue in issues:
            self.log_line.emit(issue.text, issue.severity.value)
        self._updates[flow.id] = status.UpdateState(flow.id, Check.CURRENT, plan.new, self._clock())
        text = RESULT_UPDATED.format(name=flow.name, commit=plan.new[:7], a=len(plan.added), r=len(plan.removed))
        outcome = CatalogOutcome("update", flow.id, flow.name, True, root_is_repo=(self._root / ".git").exists())
        self._finish_change(flow, [(text, "success")], manifest_note=True, outcome=outcome)
        self.update_states_changed.emit(self._updates)

    def _finish_change(self, flow: _Flow, lines, *, manifest_note: bool, outcome: CatalogOutcome) -> None:
        """An Update or Remove ended: the page closes, the rows are read again, the result strip shows, the main window follows up."""
        self._flow = None
        self._page_kind = None
        self._lock_list(False)
        self._forget_size(flow.id)
        self.refresh()
        self._select_row(flow.id)
        self.show_result(lines, generate=True, manifest_note=manifest_note)
        self._refresh_details()
        self._update_default_button()
        self._refresh_actions()
        self._tree.setFocus()
        self._emit_busy()
        self.job_finished.emit(outcome)

    # -- Remove --

    def _on_remove_clicked(self) -> None:
        """Remove This Library: plan on a worker (size and the libraries that leave the scan), then the confirmation page."""
        row, mf = self.current_row(), self._mf
        if row is None or self._flow is not None or self._action_block() is not None or isinstance(mf, Issue):
            return
        listed = row.entry is not None and row.state in (State.INSTALLED, State.UPDATE_AVAILABLE, State.FOLDER_MISSING)
        if not (listed or row.state is State.NOT_IN_CATALOG):
            return
        self._flow = _Flow("remove", row.id, row.name)
        self._lock_list(True)
        services, root, scan, target = self._services, self._root, self._scan, row.id

        def plan(progress, cancel):
            return services.plan_remove(root, target, mf, scan=scan, running=services.kicad_running)

        self._start_job("plan", "remove", row.name, plan, self._on_remove_planned)

    def _on_remove_planned(self, job: _Job, plan) -> None:
        flow = self._flow
        if flow is None or flow.kind != "remove":
            return
        flow.plan = plan
        self._remove_page.show_plan(plan, name=flow.name)
        self._enter_page("remove")

    def _on_remove_primary(self) -> None:
        """Remove Library, pressed by hand on the confirmation page: the one place apply_remove is called from (D-21)."""
        flow = self._flow
        plan = flow.plan if flow is not None else None
        if flow is None or flow.kind != "remove" or not isinstance(plan, ops.RemovePlan) or self._action_block() is not None:
            return
        services, root = self._services, self._root

        def remove(progress, cancel):
            return services.apply_remove(root, plan)

        self._start_job("remove", "remove", flow.name, remove, self._on_removed)

    def _on_removed(self, job: _Job, issues) -> None:
        flow = self._flow
        plan = flow.plan if flow is not None else None
        if flow is None or not isinstance(plan, ops.RemovePlan):
            return
        errors = [issue for issue in issues if issue.severity is Severity.ERROR]
        if errors:  # a failed Remove changes nothing the window shows: the entry and the row stay as they were
            for issue in issues:
                self.log_line.emit(issue.text, issue.severity.value)
            self._remove_page.show_refusal(errors[0])
            self._emit_outcome(flow, ok=False)
            return
        for issue in issues:
            self.log_line.emit(issue.text, issue.severity.value)
        self._updates.pop(flow.id, None)
        outcome = CatalogOutcome("remove", flow.id, flow.name, True, root_is_repo=(self._root / ".git").exists())
        self._finish_change(
            flow, [(RESULT_REMOVED.format(name=flow.name), "success")], manifest_note=plan.listed, outcome=outcome
        )

    # ── Closing ───────────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """A visible window closes through done() and its rules; a hidden one drops everything at once (it may be deleted)."""
        if self.isVisible():
            super().closeEvent(event)  # QDialog calls reject(), which ends in done(); the event is ignored if the window stays
            return
        self._release_download()
        self._abandon_flow()
        self._stop_background()
        self._fresh = False
        super().closeEvent(event)

    def _stop_question(self, job: _Job) -> tuple[QMessageBox, object]:
        """The window-modal question `Stop the current job?`; Keep Working is the default and the Esc button."""
        label = job_label(job.flow, job.name)
        if job.flow == "check":
            consequence = CONSEQUENCE_CHECK
        elif job.flow == "update":
            consequence = CONSEQUENCE_UPDATE.format(name=job.name)
        else:
            consequence = CONSEQUENCE_ADD
        text = STOP_TEXT.format(job=label[:1].upper() + label[1:], consequence=consequence)
        box = QMessageBox(QMessageBox.Icon.Question, STOP_TITLE, text, QMessageBox.StandardButton.NoButton, self)
        box.setTextFormat(Qt.TextFormat.PlainText)
        stop = box.addButton(STOP_CLOSE_TEXT, QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(KEEP_WORKING_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep)
        box.setEscapeButton(keep)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        return box, stop

    def _ask_stop(self, job: _Job) -> bool:
        """True when the user chose Stop and Close."""
        box, _stop = self._stop_question(job)
        box.exec()
        clicked = box.clickedButton()
        return clicked is not None and box.buttonRole(clicked) == QMessageBox.ButtonRole.DestructiveRole

    def done(self, r: int) -> None:
        """Hide the window (it is reused), after the job rules: a job is stopped first, a Remove-like step is waited for.

        A repository check, a download or an update asks `Stop the current job?` (Stop and Close ends the job and
        closes the window when it has ended); the final Add and a Remove cannot be stopped halfway, so the close is
        ignored and the strip says so; a download waiting on a preview is deleted without asking.
        """
        if self._asking:
            return
        job = self._job
        if job is not None:
            if job.phase in ("register", "remove"):
                self._set_job_text(REGISTER_CLOSE_TEXT if job.phase == "register" else REMOVE_CLOSE_TEXT)
                return
            if job.phase in _STOPPABLE and not job.stopping and self.isVisible():
                self._asking = True
                try:
                    stop = self._ask_stop(job)
                finally:
                    self._asking = False
                if not stop:
                    return
                job = self._job  # it may have ended while the question was open
            if job is not None:
                self._pending_close = r
                if job.phase in _STOPPABLE and not job.stopping:
                    self._cancel_job(job)
                else:
                    job.cancel.set()
                return
        self._complete_close(r)

    def _complete_close(self, r: int) -> None:
        """No job is left: delete a waiting download, drop the page, join the workers and hide the window."""
        self._pending_close = None
        self._release_download()
        self._abandon_flow()
        for worker in self._workers:
            if worker.isRunning():
                worker.wait(2000)  # bounded: a worker that has answered is about to end
        self._emit_busy()
        self._refresh_details()  # before the background tasks are dropped: it may start a folder size read
        self._stop_background()
        self._fresh = False
        super().done(r)

    def _on_help(self) -> None:
        """Open the User Guide on Library Catalog without changing its saved place (the shared guide does that)."""
        if self._show_guide is not None:
            self._show_guide(CATALOG_TOPIC)
            return
        from .help_dialog import HelpDialog  # a module-level import would be circular

        if self._help_dialog is None:
            self._help_dialog = HelpDialog(topic=CATALOG_TOPIC)
        else:
            self._help_dialog.show_topic(CATALOG_TOPIC)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()


def _same_path(first: str, second: str) -> bool:
    """True when two folder texts name the same place (slashes, trailing slash and, on Windows, letter case ignored)."""
    def norm(text: str) -> str:
        return os.path.normcase(os.path.normpath(text.strip()))

    return norm(first) == norm(second)


def time_wording(when: datetime, now: datetime) -> str:
    """`today at HH:MM`, `yesterday at HH:MM`, otherwise `YYYY-MM-DD HH:MM` (D-32)."""
    clock = when.strftime("%H:%M")
    if when.date() == now.date():
        return f"today at {clock}"
    if when.date() == (now - timedelta(days=1)).date():
        return f"yesterday at {clock}"
    return f"{when.strftime('%Y-%m-%d')} {clock}"
