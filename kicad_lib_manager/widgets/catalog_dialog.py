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

import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QStackedWidget, QStyle, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import kicad_process, library_scanner
from ..catalog import curated as curated_list
from ..catalog import githubapi, manifest, ops, status
from ..catalog.licences import LicenceClass
from ..catalog.status import Check, State
from ..models import Issue, Severity
from . import theme
from .background import BackgroundTask, run_in_background
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
UNKNOWN_TEXT = "Unknown"

RECORD_STRIP_TEXT = (
    "✖ The catalog record of this collection cannot be read ({reason}). Nothing was changed. "
    "Fix or delete catalog.json in {collection}, then reopen the catalog."
)
ERROR_GLYPH = "✖ "
WARNING_GLYPH = "⚠ "

RECORD_UNREADABLE_TIP = "The catalog record cannot be read."
GIT_MISSING_TIP = "Git was not found."
GIT_TOO_OLD_TIP = "Your Git is too old for the catalog."
GIT_CHECKING_TIP = "Looking for Git..."
FINISHING_TIP = "Finishing the last change..."

# ── Sizes (UI-SPEC "Spacing Scale"; px at 96 DPI) ───────────────────────────────────────────────────

WINDOW_SIZE = (900, 640)
WINDOW_MINIMUM = (760, 520)
LIST_MINIMUM_HEIGHT = 120
PANE_MINIMUM_HEIGHT = 200  # the pane's own minimum is lower, so the strips never push the list under its 120 px
_PANE_FLOOR = 80
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


def _plain_label(text: str = "", *, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    return label


def _heading_font(label: QLabel) -> None:
    font = label.font()
    font.setBold(True)
    font.setPointSize(theme.HEADING_PT)
    label.setFont(font)


def _mono(widget: QWidget) -> None:
    widget.setFont(QFont(theme.MONO_FAMILY, theme.MONO_PT))


def _muted(label: QLabel) -> None:
    label.setStyleSheet(f"color: {theme.MUTED};")


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

        self.setWindowTitle(CATALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MINIMUM)

        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit_detail)

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
        pane.setMinimumHeight(_PANE_FLOOR)
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
        self._empty_label = _plain_label(EMPTY_PANE_TEXT, wrap=True)
        _muted(self._empty_label)
        empty.addWidget(self._empty_label)
        empty.addStretch(1)
        self._pages.addWidget(self._empty_page)

        self._details_page = self._build_details()
        self._pages.addWidget(self._details_page)
        self._show_page(self._empty_page)
        layout.addWidget(self._scroll, 1)
        return pane

    def _build_details(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP_SM)
        self._detail_heading = _plain_label(wrap=True)
        _heading_font(self._detail_heading)
        layout.addWidget(self._detail_heading)
        layout.addStretch(1)
        self._details_layout = layout
        return page

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
        self._manual_check = False

    def _on_net(self, gen: int, result) -> None:
        if gen != self._gen:
            return
        self._net_status = result
        self._update_strips()
        self._refresh_actions()

    def _on_net_failed(self, gen: int, text: str) -> None:
        if gen != self._gen:
            return
        self.log_line.emit(f"Library catalog step failed: {text}", "error")
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
        self.log_line.emit(f"Library catalog step failed: {text}", "error")

    def _on_vars(self, gen: int, result) -> None:
        if gen != self._gen:
            return
        self._kicad_vars = dict(result) if isinstance(result, dict) else None
        self._vars_read = True
        self._refresh_details()

    # ── The list ──────────────────────────────────────────────────────────────────────────────

    def _make_item(self, row: status.Row) -> QTreeWidgetItem:
        text, token, tip = _status_cell(row)
        item = QTreeWidgetItem([row.name, text, row.licence_label, row.size_text])
        item.setData(0, _ROW_ID, row.id)
        item.setToolTip(0, row.name)
        item.setToolTip(1, tip)
        item.setToolTip(2, row.licence_label)
        item.setToolTip(3, row.size_text)
        if token is not None:
            item.setForeground(1, QBrush(QColor(token)))
        if row.licence_class is LicenceClass.UNKNOWN:
            item.setForeground(2, QBrush(QColor(theme.MUTED)))
        if row.size_mb is None:
            item.setForeground(3, QBrush(QColor(theme.MUTED)))
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

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
        self._shown_id = self.selected_id()
        self._refresh_details()

    def _refresh_details(self) -> None:
        row = self.current_row()
        if row is None:
            self._show_page(self._empty_page)
            return
        self._fill_details(row)
        self._show_page(self._details_page)

    def _fill_details(self, row: status.Row) -> None:
        self._detail_heading.setText(row.name)

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

    def _action_block(self) -> str | None:
        """Why the network actions cannot run right now, or None when they can."""
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

    def _checking(self) -> bool:
        return self._manual_check or self._external_check

    def _refresh_actions(self) -> None:
        reason = self._action_block()
        checking = self._checking()
        self._check_btn.setText(CHECKING_TEXT if checking else CHECK_TEXT)
        self._check_btn.setEnabled(reason is None and not checking)
        self._check_btn.setToolTip(reason or "")
        self._add_url_btn.setEnabled(reason is None)
        self._add_url_btn.setToolTip(reason or "")

    def _on_check_clicked(self) -> None:
        """Check for Updates; attached in the next task."""

    # ── The API the main window and the next plans use ────────────────────────────────────────

    def set_root(self, root: Path) -> None:
        """Show another collection: header, list, strips and statuses reload in one step, any open page is dropped."""
        self._stop_background()
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
        """True while an Add, Update, Remove or Reinstall runs (the jobs attach in plan 17-13)."""
        return False

    def holds_download(self) -> bool:
        """True while a downloaded copy waits for the user's answer on a review page."""
        return False

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

    # ── Closing ───────────────────────────────────────────────────────────────────────────────

    def done(self, r: int) -> None:
        """Hide the window (it is reused); stop every timer and drop every outstanding result."""
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


def time_wording(when: datetime, now: datetime) -> str:
    """`today at HH:MM`, `yesterday at HH:MM`, otherwise `YYYY-MM-DD HH:MM` (D-32)."""
    clock = when.strftime("%H:%M")
    if when.date() == now.date():
        return f"today at {clock}"
    if when.date() == (now - timedelta(days=1)).date():
        return f"yesterday at {clock}"
    return f"{when.strftime('%Y-%m-%d')} {clock}"
