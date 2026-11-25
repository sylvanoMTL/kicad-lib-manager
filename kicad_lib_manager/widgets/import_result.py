"""Widgets for the end of an import (Phase 5): the install step text and the Result view.

Every string that comes from a package or an Issue is shown as plain text, never as markup.
"""

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from ..importer.plan import InstallPlan, InstallResult
from ..models import Severity
from . import theme

_FILES_ROWS = 8  # Files written rows shown before the list scrolls
OPEN_ROWS_MAX = 3  # a list with at most this many rows is always shown; a longer one starts collapsed
_SUMMARY_MIN_LINES = 3  # text lines of each column that stay visible however short the window is
_COLUMN_MIN_WIDTH = theme.SP_XL * 10  # narrowest a column gets (320 px); the window's minimum keeps both
_STATUS_TITLES = {"library_list": "Library list", "tables": "Library tables"}
_HINT_ROWS = ("generate_hint", "checkout_hint")  # standalone lines, hidden until set
_NO_WARNINGS = "No warnings."
_QWIDGETSIZE_MAX = 16777215  # Qt's "no maximum height"
# Appended to the primary style on the moved Commit button: the same side padding, no vertical padding, so the
# bar sets the height (the button is fixed to Close's height) and the two buttons match
_BAR_BUTTON_QSS = "\nQPushButton { padding: 0px 16px; }"


class ElidedLabel(QLabel):
    """One-line plain-text label that elides its text to fit the width; the full text stays available.

    The size policy is Ignored horizontally, so a long text never widens the layout it sits in.
    """

    def __init__(
        self,
        text: str = "",
        parent=None,
        *,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        full_tooltip: bool = False,
    ):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._mode = mode
        self._full_tooltip = full_tooltip
        self._full = ""
        self.set_full_text(text)

    def set_full_text(self, text: str):
        self._full = text
        if self._full_tooltip:
            self.setToolTip(text)
        self._refresh()

    def full_text(self) -> str:
        """The text before eliding."""
        return self._full

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        width = self.contentsRect().width()
        # width < 40: not laid out yet; show everything and elide on the first real resize
        shown = self._full if width < 40 else self.fontMetrics().elidedText(self._full, self._mode, width)
        if self.text() != shown:
            self.setText(shown)


class _FilesList(QListWidget):
    """The Files written list. Enter opens the current file and stops there.

    A stock list view ignores Enter after activating, which hands it to the dialog's default button
    (Close) and would close the Result view as the file opens.
    """

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.currentItem()
            if item is not None:
                self.itemActivated.emit(item)
            event.accept()
            return
        super().keyPressEvent(event)


class ListToggle(QToolButton):
    """A Show / Hide button that folds one list widget away; hidden when the list is short.

    A list of up to OPEN_ROWS_MAX rows is always shown and the button is hidden. A longer list starts
    collapsed. A heading that carries the row count stays outside, so the count is always visible.
    """

    def __init__(self, list_widget: QWidget, name: str, parent=None):
        super().__init__(parent)
        self._list = list_widget
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setAccessibleName(f"Show or hide {name}")
        self.toggled.connect(self._on_toggled)
        self._set_look(False)
        self.hide()

    def set_rows(self, count: int, keep_state: bool = False):
        """Fit the toggle to a list of `count` rows: few rows show the list, many collapse it (unless keep_state)."""
        if count <= OPEN_ROWS_MAX:
            self.hide()
            self._list.setVisible(True)
            return
        self.show()
        if not keep_state:
            self.setChecked(False)
        self._list.setVisible(self.isChecked())

    def open(self):
        """Show the list now (a marked file must never stay hidden)."""
        if not self.isHidden():
            self.setChecked(True)

    def _set_look(self, checked: bool):
        self.setText("Hide" if checked else "Show")
        self.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def _on_toggled(self, checked: bool):
        self._set_look(checked)
        if not self.isHidden():
            self._list.setVisible(checked)


class _CommitScroll(QScrollArea):
    """The pinned commit region. Its size hint is the panel's full height.

    A stock QScrollArea caps its hint at 24 text lines, which would let the layout squeeze a taller
    commit panel; here the panel gets its full height first and scrolls only when the window is shorter.
    """

    def sizeHint(self) -> QSize:
        widget = self.widget()
        if widget is None:
            return super().sizeHint()
        hint = widget.sizeHint()
        height = hint.height()
        # wrapped labels make the panel taller at the real width than its default hint says
        width = self.viewport().width()
        if width > 0 and widget.hasHeightForWidth():
            height = max(height, widget.heightForWidth(width))
        height = max(height, widget.minimumSizeHint().height())
        frame = 2 * self.frameWidth()
        return QSize(hint.width() + frame, height + frame)


def _content_height(scroll: QScrollArea) -> int:
    """The height a scroll area's widget needs at the scroll area's full inner width (no scroll bar), 0 without one."""
    widget = scroll.widget()
    if widget is None:
        return 0
    width = scroll.width() - 2 * scroll.frameWidth()
    height = widget.heightForWidth(width) if widget.hasHeightForWidth() else widget.sizeHint().height()
    return max(height, widget.minimumSizeHint().height())


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    font = label.font()
    font.setBold(True)
    font.setPointSize(theme.HEADING_PT)
    label.setFont(font)
    return label


def _plain_label(*, wrap: bool = True) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    return label


class _BannerLabel(QLabel):
    """The success line: one plain-text line that asks for its whole width and never widens the window.

    A word-wrap label would hint at a squarish block and wrap a short line in a wide row, and its wrapped
    height is not part of a window's minimum size. This one keeps one line and is cut off at the right
    edge when the row is too narrow; the full text is the tooltip.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())


class ImportResultView(QWidget):
    """What the dialog shows after a successful install (D-15, D-16, D-18).

    One banner row on top, two columns below it and one bottom bar. The banner row is the success line. The
    left column (a scroll area) is the install summary: the KiCad-running notice (hidden until the dialog
    finds KiCad running), Warnings, Files written, the post-install status rows the main window updates and
    the backup folder. The right column is the commit slot (hidden until the dialog puts the Phase 6 commit
    panel in it). Each column scrolls vertically on its own, only when the window is too short, and keeps at
    least three text lines. The bottom bar holds Commit (moved there from the commit panel, so it is in view
    without scrolling) and Close. With no commit step the left column takes the full width and the bar
    holds Close only.
    """

    file_activated = Signal(object)  # the absolute Path of a written file, on double click or Enter
    content_changed = Signal()  # the height the view needs may have changed (a column's layout was redone)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backup_dir: Path | None = None
        self._warning_labels: list[QLabel] = []
        self._commit_button: QPushButton | None = None  # the panel's Commit button while it sits in the bottom bar

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(theme.SP_MD)

        # the banner row: what was installed, the warnings summary, then Help at the right edge
        banner_row = QHBoxLayout()
        self._banner_row = banner_row
        banner_row.setSpacing(theme.SP_MD)
        self._banner = _BannerLabel()
        font = self._banner.font()
        font.setBold(True)
        font.setPointSize(theme.DISPLAY_PT)
        self._banner.setFont(font)
        self._banner.setStyleSheet(f"color: {theme.SUCCESS};")
        valign = Qt.AlignmentFlag.AlignVCenter  # a label takes its own height, never the row's
        banner_row.addWidget(self._banner, 0, valign)
        self._warnings_summary = _plain_label(wrap=False)
        banner_row.addWidget(self._warnings_summary, 0, valign)
        banner_row.addStretch(1)
        self.help_button = QToolButton()
        self.help_button.setAutoRaise(True)
        self.help_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.help_button.hide()  # until set_help_action gives it the dialog's Help action
        banner_row.addWidget(self.help_button, 0, valign)
        outer.addLayout(banner_row)

        columns = QHBoxLayout()
        columns.setSpacing(theme.SP_LG)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SP_MD)

        # the Warnings list is the first section of the left column and shows only when there are warnings
        self._warnings_box = QWidget()
        warnings = QVBoxLayout(self._warnings_box)
        warnings.setContentsMargins(0, 0, 0, 0)
        warnings.setSpacing(theme.SP_XS)
        self._warnings_heading = _heading("Warnings")
        warnings.addWidget(self._warnings_heading)
        self._warnings_layout = QVBoxLayout()
        self._warnings_layout.setSpacing(theme.SP_XS)
        warnings.addLayout(self._warnings_layout)
        lay.addWidget(self._warnings_box)

        self._kicad_notice = _plain_label()
        self._kicad_notice.setStyleSheet(
            f"background-color: {theme.AMBER_TINT}; padding: {theme.SP_SM}px;"
        )
        self._kicad_notice.setAccessibleName("KiCad is running")
        self._kicad_notice.hide()
        lay.addWidget(self._kicad_notice)

        files = QVBoxLayout()
        files.setSpacing(theme.SP_XS)
        self._files_heading = _heading("Files written (0)")
        self._files_list = _FilesList()
        self._files_toggle = ListToggle(self._files_list, "Files written")
        heading_row = QHBoxLayout()
        heading_row.setSpacing(theme.SP_SM)
        heading_row.addWidget(self._files_heading)
        heading_row.addWidget(self._files_toggle)
        heading_row.addStretch(1)
        files.addLayout(heading_row)
        self._files_list.setAccessibleName("Files written")
        self._files_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._files_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._files_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._files_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._files_list.itemActivated.connect(self._on_item_activated)
        files.addWidget(self._files_list)
        lay.addLayout(files)

        status = QVBoxLayout()
        status.setSpacing(theme.SP_XS)
        self._status_labels: dict[str, QLabel] = {}
        for row in ("library_list", "tables", *_HINT_ROWS):
            label = _plain_label()
            self._status_labels[row] = label
            status.addWidget(label)
        for row in _HINT_ROWS:
            self._status_labels[row].hide()
        lay.addLayout(status)

        # Backup folder: shown only when the install replaced an existing file (it made a backup)
        self._backup_row = QWidget()
        backup_lay = QHBoxLayout(self._backup_row)
        backup_lay.setContentsMargins(0, 0, 0, 0)
        backup_lay.setSpacing(theme.SP_SM)
        self._backup_label = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
        self._backup_label.setFont(QFont(theme.MONO_FAMILY, theme.MONO_PT))
        self._backup_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._backup_label.setAccessibleName("Backup folder")
        backup_lay.addWidget(self._backup_label, stretch=1)
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.clicked.connect(self._on_open_folder)
        backup_lay.addWidget(self.open_folder_button)
        self._backup_row.hide()
        lay.addWidget(self._backup_row)

        lay.addStretch(1)
        self._scroll.setWidget(body)
        body.installEventFilter(self)  # a layout request in the left column asks the dialog to fit again
        # each column scrolls on its own and keeps three text lines however short the window is
        self._scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self._scroll.setMinimumHeight(self._column_min_height())
        self._scroll.setMinimumWidth(_COLUMN_MIN_WIDTH)
        columns.addWidget(self._scroll, 1)

        # The Phase 6 commit step is the right column, beside the summary: hidden at zero height until
        # set_commit_panel puts a panel in. Its Commit button is moved into the bottom bar.
        self.commit_slot = QWidget()
        self.commit_slot.setObjectName("commitSlot")
        slot_lay = QVBoxLayout(self.commit_slot)
        slot_lay.setContentsMargins(0, 0, 0, 0)
        self._commit_scroll = _CommitScroll()
        self._commit_scroll.setWidgetResizable(True)
        self._commit_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._commit_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._commit_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        slot_lay.addWidget(self._commit_scroll)
        self._commit_panel: QWidget | None = None
        self.commit_slot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.commit_slot.setFixedHeight(0)
        self.commit_slot.hide()
        columns.addWidget(self.commit_slot, 1)
        outer.addLayout(columns, 1)

        self._button_row = QHBoxLayout()
        self._button_row.setSpacing(theme.SP_SM)
        self._button_row.addStretch(1)
        self.close_button = QPushButton("Close")
        self._button_row.addWidget(self.close_button)
        outer.addLayout(self._button_row)

        self._set_warnings(())
        self._reset_status()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Tell the dialog when a column's layout was redone; the event itself is never consumed."""
        if event.type() == QEvent.Type.LayoutRequest and (
            watched is self._scroll.widget() or (self._commit_panel is not None and watched is self._commit_panel)
        ):
            self.content_changed.emit()
        return False

    def fitting_height(self) -> int:
        """The view height that shows the banner row, the taller column in full and the bottom bar at the current width.

        Neither column scrolls at this height.
        """
        outer = self.layout()
        outer.activate()
        columns = max(
            _content_height(self._scroll),
            _content_height(self._commit_scroll) if self._commit_panel is not None else 0,
            self._column_min_height(),
        )
        margins = outer.contentsMargins()
        return (
            self._banner_row.sizeHint().height()
            + columns
            + self._button_row.sizeHint().height()
            + 2 * outer.spacing()
            + margins.top()
            + margins.bottom()
        )

    # -- filling the view ------------------------------------------------------------------------

    def show_result(self, result: InstallResult, plan: InstallPlan, repo_root: Path):
        """Fill every block from a successful install. The status rows start without a state."""
        self.clear_commit_panel()
        self._banner.setText(f"✓ Installed {plan.symbol_name} into {result.library}")
        self._banner.setToolTip(self._banner.text())
        self._kicad_notice.hide()
        self._set_warnings(result.issues)
        self._reset_status()
        self._fill_files(result.touched, Path(repo_root))
        self._backup_dir = result.backup_dir
        if result.backup_dir is None:
            self._backup_row.hide()
        else:
            self._backup_label.set_full_text(f"Backup folder: {result.backup_dir}")
            self._backup_row.show()

    def set_help_action(self, action: QAction):
        """Show the dialog's Help action on the banner row; its F1 shortcut keeps working through the button."""
        self.help_button.setDefaultAction(action)
        self.help_button.show()

    def _column_min_height(self) -> int:
        return self._scroll.fontMetrics().lineSpacing() * _SUMMARY_MIN_LINES

    def set_commit_panel(self, panel: QWidget):
        """Put the Phase 6 commit panel into the right column and its Commit button into the bottom bar."""
        self.clear_commit_panel()
        self._commit_panel = panel
        self._commit_scroll.setWidget(panel)
        panel.installEventFilter(self)
        self.commit_slot.setMinimumWidth(_COLUMN_MIN_WIDTH)
        self.commit_slot.setMinimumHeight(self._column_min_height())
        self.commit_slot.setMaximumHeight(_QWIDGETSIZE_MAX)
        self.commit_slot.show()
        self._commit_scroll.verticalScrollBar().setValue(0)
        button = panel.take_commit_button()
        button.setParent(self)
        self._button_row.insertWidget(self._button_row.count() - 1, button)  # just left of Close
        button.setStyleSheet(theme.PRIMARY_BUTTON_QSS + _BAR_BUTTON_QSS)
        button.setFixedHeight(self.close_button.sizeHint().height())
        button.show()
        self._commit_button = button
        QWidget.setTabOrder(button, self.close_button)

    def clear_commit_panel(self):
        """Remove any panel and collapse the slot again: hidden, zero height (a failed or empty install has none)."""
        button, self._commit_button = self._commit_button, None
        if button is not None:  # reparented away from the panel, so deleting the panel would not delete it
            self._button_row.removeWidget(button)
            button.hide()
            button.setParent(None)
            button.deleteLater()
        panel, self._commit_panel = self._commit_panel, None
        if panel is not None:
            self._commit_scroll.takeWidget()
            panel.removeEventFilter(self)
            panel.hide()
            panel.setParent(None)
            panel.deleteLater()
        self.commit_slot.setFixedHeight(0)
        self.commit_slot.hide()

    def _set_warnings(self, issues):
        for label in self._warning_labels:
            self._warnings_layout.removeWidget(label)
            label.hide()
            label.setParent(None)
            label.deleteLater()
        self._warning_labels = []
        shown = [issue for issue in issues if issue.severity in (Severity.WARNING, Severity.ERROR)]
        self._warnings_box.setVisible(bool(shown))
        errors = sum(issue.severity is Severity.ERROR for issue in shown)
        warns = len(shown) - errors
        if not shown:
            self._warnings_summary.setText(_NO_WARNINGS)
            self._warnings_summary.setStyleSheet(f"color: {theme.MUTED};")
        else:
            parts = []
            if errors:
                parts.append(f"{errors} {'error' if errors == 1 else 'errors'}")
            if warns:
                parts.append(f"{warns} {'warning' if warns == 1 else 'warnings'}")
            self._warnings_summary.setText(f"{'✖' if errors else '⚠'} {', '.join(parts)}")
            self._warnings_summary.setStyleSheet(f"color: {theme.ERROR if errors else theme.AMBER};")
        for issue in shown:
            warning = issue.severity is Severity.WARNING
            label = _plain_label()
            label.setText(f"{'⚠' if warning else '✖'} {issue.text}")
            label.setStyleSheet(f"color: {theme.AMBER if warning else theme.ERROR};")
            self._add_warning(label)

    def _add_warning(self, label: QLabel):
        self._warning_labels.append(label)
        self._warnings_layout.addWidget(label)

    def _reset_status(self):
        for row, title in _STATUS_TITLES.items():
            label = self._status_labels[row]
            label.setText(title)
            label.setStyleSheet("")
        for row in _HINT_ROWS:
            hint = self._status_labels[row]
            hint.setText("")
            hint.hide()

    def _fill_files(self, touched, repo_root: Path):
        files = self._files_list
        files.clear()
        for path in touched:
            try:
                shown = Path(path).relative_to(repo_root).as_posix()
            except ValueError:
                shown = Path(path).as_posix()
            item = QListWidgetItem(shown)
            item.setToolTip(shown)
            item.setData(Qt.ItemDataRole.UserRole, Path(path))
            files.addItem(item)
        self._files_heading.setText(f"Files written ({files.count()})")
        # Up to eight rows tall, then the list scrolls
        row = files.sizeHintForRow(0) if files.count() else files.fontMetrics().height() + 8
        files.setFixedHeight(row * min(max(files.count(), 1), _FILES_ROWS) + 2 * files.frameWidth())
        self._files_toggle.set_rows(files.count())

    # -- updates from the dialog and the main window ---------------------------------------------

    def set_kicad_running(self, text: str):
        """Show the notice that KiCad is open and must reopen its editors (POST-05, D-18); the dialog words it."""
        self._kicad_notice.setText(f"⚠ {text}")
        self._kicad_notice.show()

    def set_status(self, row: str, text: str, severity: Severity):
        """Set one post-install status row: library_list, tables, generate_hint, or
        checkout_hint (D-16, D-17, D-26).

        The first two read "{Row title}: {text}"; a hint is a line of its own and appears when set.
        """
        label = self._status_labels[row]
        title = _STATUS_TITLES.get(row)
        label.setText(f"{title}: {text}" if title else text)
        color = {Severity.SUCCESS: theme.SUCCESS, Severity.ERROR: theme.ERROR, Severity.WARNING: theme.AMBER}.get(severity)
        label.setStyleSheet(f"color: {color};" if color else "")
        label.show()

    def status_text(self, row: str) -> str:
        return self._status_labels[row].text()

    # -- actions ---------------------------------------------------------------------------------

    def _on_item_activated(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path is not None:
            self.file_activated.emit(path)

    def _on_open_folder(self):
        # Only the folder the app made for this install; nothing taken from a package is ever opened (T-05-34)
        if self._backup_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._backup_dir)))
