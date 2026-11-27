"""The review pages of the library catalog window (Phase 17 plan 13; CAT-02, CAT-03, CAT-08, D-04, D-10, D-13, D-15, D-20, D-23).

Pure widgets with no service call and no worker: the window (catalog_dialog.py) hands each page the plan or the
staged download it shows and reads the answers back through signals. Every text is plain text (a name containing
< or & shows as typed); only the Repository link is rich text. The copy of the UI-SPEC lives here once, and
catalog_dialog imports what it shares. Pages: AddByUrlPage, LicencePage and AddPreviewPage (which also shows the
refusals after a download); ReviewPage is their common base and CollapsibleList the shared list of nicknames.
"""

import html
import math

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..catalog import licences, status
from ..catalog.licences import LicenceClass
from ..models import Issue
from . import theme
from .import_result import ElidedLabel, ListToggle

# ── The copy (UI-SPEC "Copywriting Contract", "Add flow", "Add by URL", "Refusals") ────────────────────────

ERROR_GLYPH = "✖ "
WARNING_GLYPH = "⚠ "
SUCCESS_GLYPH = "✓ "

UNKNOWN_TEXT = "Unknown"
NOT_STATED_TEXT = "Not stated by the repository"
LICENCE_UNREADABLE_TEXT = "Could not be read from GitHub"

BACK_TEXT = "Back to List"
DISCARD_TEXT = "Discard Download"
DISCARD_TIP = "Delete the downloaded copy. Nothing is added."
TRY_AGAIN_TEXT = "Try Again"
DOWNLOAD_TEXT = "Download and Check"
CHECK_REPOSITORY_TEXT = "Check Repository"
ADD_LIBRARY_TEXT = "Add Library"
REINSTALL_LIBRARY_TEXT = "Reinstall Library"

URL_HEADING = "Add a library from GitHub"
URL_BODY = "Paste the web address of a public GitHub repository that holds KiCad symbol and footprint libraries."
URL_LABEL = "Web address"
URL_PLACEHOLDER = "https://github.com/owner/repository"
URL_EMPTY_TIP = "Paste a web address first."

ADD_HEADING = "Add {name}"
REINSTALL_HEADING = "Reinstall {name}"
LICENCE_BODY = "Read the licence before you download. Nothing is added to your collection yet."
REPOSITORY_LABEL = "Repository"
BRANCH_LABEL = "Branch"
LICENCE_LABEL = "Licence"
SIZE_LABEL = "Size"
INSTALLED_IN_LABEL = "Will be installed in"
TICK_TEXT = "I have read the licence terms"
TICK_TIP = "Tick the box to confirm you have read the licence terms."
CONFIRMED_ON_TEXT = "You confirmed the licence terms on {date}."
CONFIRMED_TEXT = "You confirmed the licence terms."
SHARE_ALIKE_NOTE = (
    "Share-alike licence: if you share changed copies of these files, you must share them under the same terms."
)
PROPRIETARY_NOTE = (
    "Proprietary licence: the owner sets the terms of use. Read them on the repository page before you continue."
)
NOT_STATED_NOTE = (
    "The repository does not state a licence. Its licence file, if it has one, is shown after the download, "
    "before the library is added."
)
OTHER_NOTE = (
    "The repository's licence is not one the app can name. Its licence file, if it has one, is shown after the "
    "download, before the library is added."
)
UNREADABLE_NOTE = "Could not read the licence and size from GitHub right now. They are shown after the download."
KICAD_OPEN_TEXT = "KiCad is open ({names}). Restart it after the library is added to see the changes."

DOWNLOADED_TEXT = "Downloaded and checked: {s} symbol libraries and {f} footprint libraries."
WHAT_HEADING = "What will be added"
FOLDER_ROW_TEXT = "{s} symbol libraries, {f} footprint libraries"
RECORD_ROW_TEXT = "records this library"
GITIGNORE_APPEND_TEXT = (
    "gets the line /ThirdParty/ so git does not treat the downloaded libraries as part of your collection"
)
GITIGNORE_CREATE_TEXT = (
    "is created with the line /ThirdParty/ so git does not treat the downloaded libraries as part of your collection"
)
VARS_HEADING = "Path variables"
VAR_TEXT = (
    "This library needs the KiCad path variable {var} to point to {folder}. After you press Add Library, the app "
    "asks before it changes KiCad's settings."
)
CLASH_HEADING = "Libraries with the same name"
NO_CLASH_TEXT = "No library has the same name as one you already have."
CLASH_ONE_TEXT = "1 library has the same name as a library you already have:"
CLASH_MANY_TEXT = "{n} libraries have the same name as a library you already have:"
CLASH_COLUMNS = ("Library", "Kind", "Same name as")
CLASH_NOTE = (
    "They start unticked, so Generate Tables will not list two libraries with one name. Tick one yourself if you "
    "want it. Names are never changed."
)
LICENCE_HEADING = "Licence"
LICENCE_LINE = "Licence: {name}"
LICENCE_LINE_CONFIRMED = "Licence: {name} (you confirmed you read the terms)"
NO_LICENCE_FILE_TEXT = "This repository has no licence file, so nothing says what you may do with it."
NOTHING_ADDED_TEXT = "Nothing was added. The downloaded copy was deleted."

# Update and Remove (UI-SPEC "Update flow", "Remove flow", "Refusals")
UPDATE_HEADING = "Update {name}"
KEEP_VERSION_TEXT = "Keep Current Version"
KEEP_VERSION_TIP = "Do not update. Nothing changes."
UPDATE_LIBRARY_TEXT = "Update Library"
VERSION_LABEL = "Version"
FILES_LABEL = "Files changed"
FILES_TEXT = "{n} files"
ADDED_TITLE = "Libraries added"
REMOVED_TITLE = "Libraries removed"
NONE_TEXT = "None"
REMOVED_NOTE = "Projects that use a removed library lose those parts."
UP_TO_DATE_TEXT = "{name} is already up to date."
MORE_TEXT = "and {n} more"
DIRTY_MAX_ROWS = 8
SHORT_ID = 7
KICAD_OPEN_UPDATED_TEXT = "KiCad is open ({names}). Restart it after the library is updated to see the changes."
KICAD_OPEN_REMOVED_TEXT = "KiCad is open ({names}). Restart it after the library is removed to see the changes."

REMOVE_HEADING = "Remove {name}?"
KEEP_LIBRARY_TEXT = "Keep Library"
REMOVE_LIBRARY_TEXT = "Remove Library"
REMOVE_LEAD_TEXT = "This deletes the folder"
REMOVE_TAIL_LISTED = "({size} on disk) and removes {name} from the catalog."
REMOVE_TAIL_UNLISTED = "({size} on disk)."
REMOVE_GONE_TEXT = "The folder is already gone, so only the catalog entry is removed."
LEAVE_TITLE = "Libraries that leave your scan"
LEAVE_NOTE = "The next Generate Tables drops them from your KiCad library tables."
VARS_USED_HEADING = "Path variables it used"
VARS_STAY_NOTE = "They stay set in KiCad. Projects that still use this library's 3D models lose them."

# ── Sizes ───────────────────────────────────────────────────────────────────────────────────────────────

CONTROL_HEIGHT = 28
LIST_MAX_ROWS = 6
LICENCE_BOX_LINES = 8
SECTION_SPACING = theme.SP_MD


# ── Small helpers (the window imports them, so each is written once) ────────────────────────────────────

def plain_label(text: str = "", *, wrap: bool = False) -> QLabel:
    """A plain-text label. A wrapped one ignores its text's width, so a long unbreakable path never widens the window.

    Qt breaks a line only at spaces, so such a path is cut off at the right edge; every text that can hold a path
    carries its full text as tooltip or sits in an ElidedLabel.
    """
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    if wrap:
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


def heading_font(label: QLabel) -> None:
    font = label.font()
    font.setBold(True)
    font.setPointSize(theme.HEADING_PT)
    label.setFont(font)


def mono(widget: QWidget) -> None:
    widget.setFont(QFont(theme.MONO_FAMILY, theme.MONO_PT))


def muted(label: QLabel) -> None:
    label.setStyleSheet(f"color: {theme.MUTED};")


def status_line(glyph: str, text: str, token: str) -> QLabel:
    """A wrapped plain row with its glyph in the colour of its meaning; the accessible name is the whole row."""
    label = plain_label(glyph + text, wrap=True)
    label.setStyleSheet(f"color: {token};")
    label.setAccessibleName(label.text())
    return label


def destructive_button_qss() -> str:
    """The Remove Library button: ERROR fill, white bold text, the padding and height of PRIMARY_BUTTON_QSS (plan 17-15)."""
    return "\n".join([
        f"QPushButton {{ background-color: {theme.ERROR}; color: white; padding: 8px 16px; "
        "font-weight: bold; min-height: 12px; }",
        "QPushButton:disabled { background-color: #E1E1E1; color: #595959; }",
    ])


def licence_display(source) -> str:
    """The licence of an AddSource as the pages name it (the UI-SPEC table of licence labels, with its detail forms)."""
    cls = licences.licence_class(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)
    if cls is LicenceClass.NOT_STATED:
        return NOT_STATED_TEXT
    if cls is LicenceClass.UNKNOWN:
        return LICENCE_UNREADABLE_TEXT
    return licences.licence_label(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)


class LinkLabel(QLabel):
    """The Repository link: one rich-text line elided in the middle to its width; the whole address is the tooltip.

    A web address has no place a line may break, so it is elided instead of wrapped and never widens the window.
    Only an https address becomes a link (opens in the browser).
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("repositoryLink")
        self.setTextFormat(Qt.TextFormat.RichText)  # the one rich-text label of the window
        self.setOpenExternalLinks(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Link, QColor(theme.LINK))
        self.setPalette(palette)
        self._url = ""

    def set_url(self, url: str) -> None:
        self._url = url
        self.setToolTip(url)
        self._refresh()

    def url(self) -> str:
        return self._url

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if not self._url:
            shown = ""
        else:
            width = self.contentsRect().width()
            text = self._url if width < 40 else self.fontMetrics().elidedText(self._url, Qt.TextElideMode.ElideMiddle, width)
            if self._url.startswith("https://"):
                shown = f'<a href="{html.escape(self._url, quote=True)}">{html.escape(text)}</a>'
            else:
                shown = html.escape(text)
        if self.text() != shown:
            self.setText(shown)


def clear_layout(layout) -> None:
    """Remove and delete every widget and nested layout of a layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


# ── The list of nicknames ───────────────────────────────────────────────────────────────────────────────

class CollapsibleList(QWidget):
    """A heading with the row count, a Show toggle above 3 rows and a list at most 6 rows tall (it scrolls beyond).

    collapse=False keeps the list always shown (the name clashes of the Add preview). Extra columns come from
    columns; a single column has no header. Names elide at the column width and carry their text as tooltip.
    """

    def __init__(self, title: str, columns: tuple[str, ...] = (), *, collapse: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._collapse = collapse
        self._columns = tuple(columns) or ("",)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP_XS)
        head = QHBoxLayout()
        head.setSpacing(theme.SP_SM)
        self._heading = plain_label(title)
        head.addWidget(self._heading)
        self._tree = QTreeWidget()
        self._tree.setObjectName("nicknameList")
        self._tree.setColumnCount(len(self._columns))
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tree.setAccessibleName(title or "Libraries")
        if len(self._columns) > 1:
            self._tree.setHeaderLabels(list(self._columns))
        else:
            self._tree.setHeaderHidden(True)
        self._toggle = ListToggle(self._tree, title or "list")
        head.addWidget(self._toggle)
        head.addStretch(1)
        layout.addLayout(head)
        layout.addWidget(self._tree)
        self._rows = 0

    def set_title(self, title: str) -> None:
        self._title = title
        self._refresh_heading()

    def set_rows(self, rows, *, token: str | None = None) -> None:
        """Show these rows (tuples of texts, one per column); token colours the first column's text."""
        self._tree.clear()
        rows = [tuple(row) if isinstance(row, (tuple, list)) else (row,) for row in rows]
        for row in rows:
            texts = list(row) + [""] * (len(self._columns) - len(row))
            item = QTreeWidgetItem(texts[: len(self._columns)])
            for column, text in enumerate(texts[: len(self._columns)]):
                item.setToolTip(column, text)
            if token is not None:
                item.setForeground(0, QColor(token))
            self._tree.addTopLevelItem(item)
        self._rows = len(rows)
        self._refresh_heading()
        shown = min(self._rows, LIST_MAX_ROWS)
        row_height = self._tree.sizeHintForRow(0) if self._rows else 0
        header = 0 if self._tree.isHeaderHidden() else self._tree.header().sizeHint().height()
        self._tree.setFixedHeight(2 * self._tree.frameWidth() + header + shown * max(row_height, 0) + 2)
        if self._collapse:
            self._toggle.set_rows(self._rows)
        else:
            self._toggle.hide()
            self._tree.setVisible(self._rows > 0)

    def _refresh_heading(self) -> None:
        self._heading.setText(f"{self._title} ({self._rows})" if self._title else "")
        self._heading.setVisible(bool(self._title))

    def row_count(self) -> int:
        return self._rows

    def is_expanded(self) -> bool:
        """True when the rows are shown (a short list, a list that opted out of collapsing, or a toggle that is open)."""
        return not self._tree.isHidden()

    def toggle(self) -> ListToggle:
        return self._toggle

    def tree(self) -> QTreeWidget:
        return self._tree

    def heading_text(self) -> str:
        return self._heading.text()


# ── The common page ─────────────────────────────────────────────────────────────────────────────────────

class ReviewPage(QWidget):
    """A page of the detail pane: a wrapped heading, sections, and a bottom row with a plain back button and one primary.

    primary_pressed and back_pressed are the only ways out. set_blocked(reason) disables the primary with the reason
    as tooltip (a scan, the import or migration window, another job); set_busy(True) disables both buttons and the
    page's inputs while the page's own job runs. A subclass adds its own rule through _own_primary_rule().
    """

    primary_pressed = Signal()
    back_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blocked: str | None = None
        self._busy = False
        self._primary_shown = True
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SECTION_SPACING)
        self._heading = plain_label(wrap=True)
        heading_font(self._heading)
        root.addWidget(self._heading)
        root.addSpacing(theme.SP_LG - SECTION_SPACING)  # 24 px between the heading and the first section
        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(SECTION_SPACING)
        root.addLayout(self._body)
        root.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.SP_SM)
        buttons.addStretch(1)
        self._back = QPushButton(BACK_TEXT)
        self._primary = QPushButton()
        self._primary.setStyleSheet(theme.PRIMARY_BUTTON_QSS)
        for button in (self._back, self._primary):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setMinimumHeight(CONTROL_HEIGHT)
        self._back.clicked.connect(self.back_pressed)
        self._primary.clicked.connect(self.primary_pressed)
        buttons.addWidget(self._back)
        buttons.addWidget(self._primary)
        root.addLayout(buttons)

    # -- buttons --

    def back_button(self) -> QPushButton:
        return self._back

    def primary_button(self) -> QPushButton:
        return self._primary

    def set_heading(self, text: str) -> None:
        self._heading.setText(text)
        self._heading.setAccessibleName(text)

    def heading_text(self) -> str:
        return self._heading.text()

    def set_primary(self, text: str) -> None:
        self._primary.setText(text)

    def set_back(self, text: str, tooltip: str = "") -> None:
        self._back.setText(text)
        self._back.setToolTip(tooltip)

    def set_primary_shown(self, shown: bool) -> None:
        """A refusal page keeps only its back button (the primary is hidden, not disabled)."""
        self._primary_shown = bool(shown)
        self._primary.setVisible(self._primary_shown)

    def set_primary_enabled(self, enabled: bool, tooltip: str = "") -> None:
        self._primary.setEnabled(bool(enabled))
        self._primary.setToolTip(tooltip)

    def set_blocked(self, reason: str | None) -> None:
        self._blocked = reason or None
        self.refresh_buttons()

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._set_inputs_enabled(not self._busy)
        self.refresh_buttons()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        """A page with inputs (the web address, the tick) disables them while its job runs."""

    def _own_primary_rule(self) -> str | None:
        """The reason the page's own rules keep the primary disabled (the missing tick), or None."""
        return None

    def primary_accepts_ctrl_return(self) -> bool:
        """False on the Remove page: Ctrl+Return never confirms a deletion (D-21)."""
        return True

    def refresh_buttons(self) -> None:
        reason = self._own_primary_rule()
        if self._busy:
            self.set_primary_enabled(False, "")
        elif self._blocked:
            self.set_primary_enabled(False, self._blocked)
        elif reason:
            self.set_primary_enabled(False, reason)
        else:
            self.set_primary_enabled(True, "")
        self._back.setEnabled(not self._busy)

    # -- sections --

    def _clear_body(self) -> None:
        clear_layout(self._body)

    def _add(self, widget: QWidget) -> QWidget:
        self._body.addWidget(widget)
        return widget

    def focus_first(self) -> None:
        """Focus the page's first input: the field, else the tick, else the primary when enabled, else back."""
        target = self._first_input()
        if target is not None and target.isEnabled() and target.isVisibleTo(self):
            target.setFocus()
        elif self._primary.isEnabled() and self._primary.isVisibleTo(self):
            self._primary.setFocus()
        else:
            self._back.setFocus()

    def _first_input(self) -> QWidget | None:
        return None


def _row(title: str, value: QWidget) -> QWidget:
    """A labelled row of a page: the label in a 120 px column, the value to its right."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(theme.SP_SM)
    label = plain_label(title)
    label.setMinimumWidth(120)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    lay.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
    lay.addWidget(value, 1)
    return box


# ── Add by URL ──────────────────────────────────────────────────────────────────────────────────────────

class AddByUrlPage(ReviewPage):
    """`Add a library from GitHub`: the Web address field, Check Repository and the refusal rows under the field."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_heading(URL_HEADING)
        self.set_primary(CHECK_REPOSITORY_TEXT)
        body = plain_label(URL_BODY, wrap=True)
        muted(body)
        self._add(body)
        self._field = QLineEdit()
        self._field.setPlaceholderText(URL_PLACEHOLDER)
        self._field.setAccessibleName(URL_LABEL)
        self._field.setMinimumHeight(CONTROL_HEIGHT)
        self._field.textChanged.connect(self._on_text)
        self._field.returnPressed.connect(self._on_return)
        self._add(_row(URL_LABEL, self._field))
        self._refusals = QVBoxLayout()
        self._refusals.setContentsMargins(0, 0, 0, 0)
        self._refusals.setSpacing(theme.SP_XS)
        self._body.addLayout(self._refusals)
        self._checking = False
        self.refresh_buttons()

    def address(self) -> str:
        """The typed address without the spaces around it; '' when blank."""
        return self._field.text().strip()

    def field(self) -> QLineEdit:
        return self._field

    def reset(self) -> None:
        """A fresh page: an empty field and no refusal row."""
        self._field.clear()
        self.show_refusals([])
        self.set_checking(False)

    def show_refusals(self, issues) -> None:
        """One ✖ row under the field for each issue (an Issue or a plain text); the field stays editable."""
        clear_layout(self._refusals)
        for issue in issues:
            text = issue.text if isinstance(issue, Issue) else str(issue)
            self._refusals.addWidget(status_line(ERROR_GLYPH, text, theme.ERROR))

    def refusal_texts(self) -> list[str]:
        out = []
        for index in range(self._refusals.count()):
            widget = self._refusals.itemAt(index).widget()
            if widget is not None:
                out.append(widget.text())
        return out

    def set_checking(self, on: bool) -> None:
        """While the check runs the field and Check Repository are disabled (the job strip shows the step)."""
        self._checking = bool(on)
        self.set_busy(self._checking)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self._field.setEnabled(enabled)

    def _own_primary_rule(self) -> str | None:
        return None if self.address() else URL_EMPTY_TIP

    def _on_text(self, _text: str) -> None:
        self.refresh_buttons()

    def _on_return(self) -> None:
        if self._primary.isEnabled():
            self.primary_pressed.emit()

    def _first_input(self) -> QWidget | None:
        return self._field


# ── The licence page ────────────────────────────────────────────────────────────────────────────────────

class LicencePage(ReviewPage):
    """The page before anything is downloaded: repository, licence, size, the install folder, notes, refusals and the tick."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_primary(DOWNLOAD_TEXT)
        self._tick: QCheckBox | None = None
        self._refused = False
        self._reinstall = False

    def show_plan(self, plan, *, reinstall: bool = False, acknowledged_on: str = "", name: str | None = None,
                  address: str | None = None) -> None:
        """Fill the page from an ops.AddPlan. name and address override the plan's (an Add by URL shows owner/repo and the cleaned address)."""
        self._clear_body()
        self._tick = None
        self._reinstall = bool(reinstall)
        source = plan.source
        shown_name = name or plan.name
        self.set_heading((REINSTALL_HEADING if reinstall else ADD_HEADING).format(name=shown_name))
        body = plain_label(LICENCE_BODY, wrap=True)
        muted(body)
        self._add(body)

        link = LinkLabel()
        mono(link)
        link.set_url(address or source.url.removesuffix(".git").rstrip("/"))
        self._add(_row(REPOSITORY_LABEL, link))
        if reinstall:
            branch = plain_label(source.branch)
            mono(branch)
            self._add(_row(BRANCH_LABEL, branch))
        licence = plain_label(licence_display(source), wrap=True)
        self._add(_row(LICENCE_LABEL, licence))
        size = UNKNOWN_TEXT if plan.size_mb is None else f"about {status.size_text(plan.size_mb)}"
        self._add(_row(SIZE_LABEL, plain_label(size)))
        where = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
        mono(where)
        where.set_full_text(plan.folder.as_posix())
        self._add(_row(INSTALLED_IN_LABEL, where))

        cls = plan.licence
        note = {
            LicenceClass.SHARE_ALIKE: SHARE_ALIKE_NOTE,
            LicenceClass.PROPRIETARY: PROPRIETARY_NOTE,
            LicenceClass.NOT_STATED: NOT_STATED_NOTE,
            LicenceClass.OTHER: OTHER_NOTE,
            LicenceClass.UNKNOWN: UNREADABLE_NOTE,
        }.get(cls)
        if note:
            self._add(status_line(WARNING_GLYPH, note, theme.AMBER))

        confirmed = reinstall and plan.acknowledged
        if confirmed:
            date = acknowledged_on or plan.acknowledged_on
            self._add(plain_label(CONFIRMED_ON_TEXT.format(date=date) if date else CONFIRMED_TEXT, wrap=True))
        elif cls in (LicenceClass.SHARE_ALIKE, LicenceClass.PROPRIETARY):
            self._tick = QCheckBox(TICK_TEXT)
            self._tick.setAccessibleName(TICK_TEXT)
            self._tick.toggled.connect(lambda _on: self.refresh_buttons())
            self._add(self._tick)

        for issue in plan.refusals:
            self._add(status_line(ERROR_GLYPH, issue.text, theme.ERROR))
        if plan.kicad_open:
            self._add(status_line(WARNING_GLYPH, KICAD_OPEN_TEXT.format(names=", ".join(plan.kicad_open)), theme.AMBER))
        self._refused = bool(plan.refusals)
        self.set_primary_shown(not self._refused)  # a refusal leaves only Back to List
        self.refresh_buttons()

    def acknowledged(self) -> bool:
        """True when the tick on this page is ticked (False when it is not shown)."""
        return self._tick is not None and self._tick.isChecked()

    def tick(self) -> QCheckBox | None:
        return self._tick

    def is_refused(self) -> bool:
        return self._refused

    def _set_inputs_enabled(self, enabled: bool) -> None:
        if self._tick is not None:
            self._tick.setEnabled(enabled)

    def _own_primary_rule(self) -> str | None:
        if self._tick is not None and not self._tick.isChecked():
            return TICK_TIP
        return None

    def _first_input(self) -> QWidget | None:
        return self._tick


# ── The Add preview and the refusals after a download ───────────────────────────────────────────────────

class AddPreviewPage(ReviewPage):
    """The Add (and Reinstall) preview after the download, or, in refusal mode, the ✖ row of a refused download."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick: QCheckBox | None = None
        self._what_rows: list[tuple[str, str]] = []
        self._clashes: CollapsibleList | None = None
        self._licence_box: QPlainTextEdit | None = None
        self._refusal = False

    def show_staged(self, staged, plan, *, root_is_repo: bool, name: str | None = None, licence_confirmed: bool = False) -> None:
        """Fill the preview from an ops.Staged and its AddPlan.

        name overrides the plan's (an Add by URL shows owner/repo); licence_confirmed is True when the tick was
        already given on the licence page (the licence section is then one line).
        """
        self._clear_body()
        self._tick = None
        self._clashes = None
        self._licence_box = None
        self._what_rows = []
        self._refusal = False
        reinstall = bool(plan.reinstall)
        shown_name = name or plan.name
        self.set_heading((REINSTALL_HEADING if reinstall else ADD_HEADING).format(name=shown_name))
        self.set_primary(REINSTALL_LIBRARY_TEXT if reinstall else ADD_LIBRARY_TEXT)
        self.set_back(DISCARD_TEXT, DISCARD_TIP)
        self.set_primary_shown(True)
        report = staged.report
        symbols = len(report.symbol_libs) if report is not None else 0
        footprints = len(report.footprint_libs) if report is not None else 0
        self._add(status_line(SUCCESS_GLYPH, DOWNLOADED_TEXT.format(s=symbols, f=footprints), theme.SUCCESS))

        # What will be added
        collection = plan.folder.parent.parent.as_posix()
        rows = [(plan.folder.as_posix() + "/", FOLDER_ROW_TEXT.format(s=symbols, f=footprints))]
        if not reinstall:
            rows.append((f"{collection}/catalog.json", RECORD_ROW_TEXT))
            if root_is_repo and plan.gitignore in ("append", "create"):
                rows.append((
                    f"{collection}/.gitignore",
                    GITIGNORE_CREATE_TEXT if plan.gitignore == "create" else GITIGNORE_APPEND_TEXT,
                ))
        self._what_rows = rows
        section = QWidget()
        lay = QVBoxLayout(section)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SP_XS)
        lay.addWidget(plain_label(WHAT_HEADING))
        for path, text in rows:
            line = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
            mono(line)
            line.set_full_text(path)
            lay.addWidget(line)
            detail = plain_label(text, wrap=True)
            muted(detail)
            lay.addWidget(detail)
        self._add(section)

        # Path variables
        variables = staged.vars if staged.vars is not None else dict(plan.source.vars)
        if variables:
            section = QWidget()
            lay = QVBoxLayout(section)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(theme.SP_XS)
            lay.addWidget(plain_label(VARS_HEADING))
            for var in sorted(variables):
                sub = str(variables[var]).strip("/")
                folder = plan.folder.as_posix() + (f"/{sub}" if sub else "")
                row = plain_label(VAR_TEXT.format(var=var, folder=folder), wrap=True)
                row.setAccessibleName(row.text())
                lay.addWidget(row)
            self._add(section)

        # Libraries with the same name
        collisions = list(report.collisions) if report is not None else []
        section = QWidget()
        lay = QVBoxLayout(section)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SP_XS)
        lay.addWidget(plain_label(CLASH_HEADING))
        if not collisions:
            lay.addWidget(status_line(SUCCESS_GLYPH, NO_CLASH_TEXT, theme.SUCCESS))
        else:
            sentence = CLASH_ONE_TEXT if len(collisions) == 1 else CLASH_MANY_TEXT.format(n=len(collisions))
            lay.addWidget(status_line(WARNING_GLYPH, sentence, theme.AMBER))
            self._clashes = CollapsibleList("", CLASH_COLUMNS, collapse=False)
            self._clashes.set_rows([(c.nickname, c.kind, c.clashes_with) for c in collisions])
            lay.addWidget(self._clashes)
            note = plain_label(CLASH_NOTE, wrap=True)
            muted(note)
            lay.addWidget(note)
        self._add(section)

        # Licence
        source = plan.source
        label = licences.licence_label(source.licence_spdx, proprietary=source.proprietary, known=source.licence_known)
        section = QWidget()
        lay = QVBoxLayout(section)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SP_XS)
        confirmed_before = reinstall and plan.acknowledged
        if plan.licence_text_known or confirmed_before:
            text = LICENCE_LINE_CONFIRMED if (licence_confirmed or confirmed_before) and plan.licence is not LicenceClass.OPEN else LICENCE_LINE
            lay.addWidget(plain_label(text.format(name=label), wrap=True))
        else:
            lay.addWidget(plain_label(LICENCE_HEADING))
            licence_text = report.licence_text if report is not None else None
            if licence_text:
                self._licence_box = QPlainTextEdit()
                self._licence_box.setReadOnly(True)
                self._licence_box.setPlainText(licence_text)
                self._licence_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
                self._licence_box.setAccessibleName("Licence file")
                mono(self._licence_box)
                metrics = self._licence_box.fontMetrics()
                self._licence_box.setFixedHeight(
                    LICENCE_BOX_LINES * metrics.lineSpacing() + 2 * self._licence_box.frameWidth() + 2 * theme.SP_SM
                )
                lay.addWidget(self._licence_box)
            else:
                lay.addWidget(status_line(WARNING_GLYPH, NO_LICENCE_FILE_TEXT, theme.AMBER))
            self._tick = QCheckBox(TICK_TEXT)
            self._tick.setAccessibleName(TICK_TEXT)
            self._tick.toggled.connect(lambda _on: self.refresh_buttons())
            lay.addWidget(self._tick)
        self._add(section)

        if plan.kicad_open:
            self._add(status_line(WARNING_GLYPH, KICAD_OPEN_TEXT.format(names=", ".join(plan.kicad_open)), theme.AMBER))
        self.refresh_buttons()

    def show_refusal(self, issue, *, can_retry: bool, heading: str = "") -> None:
        """A download that was refused or failed: the ✖ row, the line saying nothing was added, Back to List (and Try Again)."""
        self._clear_body()
        self._tick = None
        self._clashes = None
        self._licence_box = None
        self._what_rows = []
        self._refusal = True
        if heading:
            self.set_heading(heading)
        text = issue.text if isinstance(issue, Issue) else str(issue)
        self._add(status_line(ERROR_GLYPH, text, theme.ERROR))
        self._add(plain_label(NOTHING_ADDED_TEXT, wrap=True))
        self.set_back(BACK_TEXT)
        self.set_primary(TRY_AGAIN_TEXT)
        self.set_primary_shown(can_retry)
        self.refresh_buttons()

    def show_notice(self, text: str) -> None:
        """A ✖ row at the top of the preview (an Add that failed after the download, which is still waiting)."""
        row = status_line(ERROR_GLYPH, text, theme.ERROR)
        self._body.insertWidget(0, row)

    def acknowledged(self) -> bool:
        """True when the tick on the preview is ticked (False when it is not shown)."""
        return self._tick is not None and self._tick.isChecked()

    def tick(self) -> QCheckBox | None:
        return self._tick

    def clash_list(self) -> CollapsibleList | None:
        return self._clashes

    def what_rows(self) -> list[tuple[str, str]]:
        """The (path, description) rows of What will be added."""
        return list(self._what_rows)

    def licence_box(self) -> QPlainTextEdit | None:
        return self._licence_box

    def is_refusal(self) -> bool:
        return self._refusal

    def _set_inputs_enabled(self, enabled: bool) -> None:
        if self._tick is not None:
            self._tick.setEnabled(enabled)

    def _own_primary_rule(self) -> str | None:
        if self._tick is not None and not self._tick.isChecked():
            return TICK_TIP
        return None

    def _first_input(self) -> QWidget | None:
        return self._tick


# ── The Update preview ──────────────────────────────────────────────────────────────────────────────────

def _section() -> tuple[QWidget, QVBoxLayout]:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(theme.SP_XS)
    return box, lay


def _kicad_open_line(template: str, names) -> QLabel:
    return status_line(WARNING_GLYPH, template.format(names=", ".join(names)), theme.AMBER)


class UpdatePreviewPage(ReviewPage):
    """`Update {name}`: the version change, the files changed and the libraries added and removed; also its refusals.

    Variants: show_plan (the preview), show_current (already up to date), show_dirty (changed files block the
    update, D-07) and show_refusal (any other refusal or failure). Only the preview keeps a primary button.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._added: CollapsibleList | None = None
        self._removed: CollapsibleList | None = None
        self._dirty: CollapsibleList | None = None

    def _begin(self, heading: str) -> None:
        self._clear_body()
        self._added = self._removed = self._dirty = None
        self.set_heading(heading)
        self.set_back(BACK_TEXT)
        self.set_primary(UPDATE_LIBRARY_TEXT)
        self.set_primary_shown(False)

    def show_plan(self, plan) -> None:
        """Fill the preview from an ops.UpdatePlan that has no refusal and is not current."""
        self._begin(UPDATE_HEADING.format(name=plan.name))
        self.set_back(KEEP_VERSION_TEXT, KEEP_VERSION_TIP)
        self.set_primary_shown(True)
        version = plain_label(f"{plan.old[:SHORT_ID]}  ->  {plan.new[:SHORT_ID]}")
        mono(version)
        self._add(_row(VERSION_LABEL, version))
        self._add(_row(FILES_LABEL, plain_label(FILES_TEXT.format(n=plan.files_changed))))
        self._added = self._name_section(ADDED_TITLE, plan.added, removed=False)
        self._removed = self._name_section(REMOVED_TITLE, plan.removed, removed=True)
        if plan.kicad_open:
            self._add(_kicad_open_line(KICAD_OPEN_UPDATED_TEXT, plan.kicad_open))
        self.refresh_buttons()

    def _name_section(self, title: str, names, *, removed: bool) -> CollapsibleList | None:
        """A list of library names (collapsed above 3, at most 6 rows tall); `None` under a `(0)` heading when there are none."""
        box, lay = _section()
        listing = None
        if names:
            listing = CollapsibleList(title)
            listing.set_rows([(f"{WARNING_GLYPH}{n}" if removed else n,) for n in names], token=theme.AMBER if removed else None)
            lay.addWidget(listing)
            if removed:
                note = plain_label(REMOVED_NOTE, wrap=True)
                muted(note)
                lay.addWidget(note)
        else:
            lay.addWidget(plain_label(f"{title} (0)"))
            none = plain_label(NONE_TEXT)
            muted(none)
            lay.addWidget(none)
        self._add(box)
        return listing

    def show_current(self, name: str) -> None:
        """The fetched version is the one installed: `✓ {name} is already up to date.` and Back to List."""
        self._begin(UPDATE_HEADING.format(name=name))
        self._add(status_line(SUCCESS_GLYPH, UP_TO_DATE_TEXT.format(name=name), theme.SUCCESS))
        self.refresh_buttons()

    def show_dirty(self, plan) -> None:
        """Changed files block the update: the refusal, then the changed files in Mono (8 rows, then `and {n} more`)."""
        self._begin(UPDATE_HEADING.format(name=plan.name))
        if plan.refusal is not None:
            self._add(status_line(ERROR_GLYPH, plan.refusal.text, theme.ERROR))
        files = list(plan.dirty)
        if files:
            self._dirty = CollapsibleList("", collapse=False)
            mono(self._dirty.tree())
            self._dirty.set_rows([(path,) for path in files[:DIRTY_MAX_ROWS]])
            self._add(self._dirty)
            if len(files) > DIRTY_MAX_ROWS:
                more = plain_label(MORE_TEXT.format(n=len(files) - DIRTY_MAX_ROWS))
                muted(more)
                self._add(more)
        self.refresh_buttons()

    def show_refusal(self, issue, *, heading: str = "") -> None:
        """Any other refusal or failure (GitHub unreachable, Git LFS in the new version, a missing folder): ✖ row, Back to List."""
        self._begin(heading or self.heading_text())
        text = issue.text if isinstance(issue, Issue) else str(issue)
        self._add(status_line(ERROR_GLYPH, text, theme.ERROR))
        self.refresh_buttons()

    def show_notice(self, text: str) -> None:
        """A ✖ row at the top of the preview (an update that failed after the preview, which stays open)."""
        self._body.insertWidget(0, status_line(ERROR_GLYPH, text, theme.ERROR))

    def added_list(self) -> CollapsibleList | None:
        return self._added

    def removed_list(self) -> CollapsibleList | None:
        return self._removed

    def dirty_list(self) -> CollapsibleList | None:
        return self._dirty


# ── The Remove confirmation ─────────────────────────────────────────────────────────────────────────────

class RemovePage(ReviewPage):
    """`Remove {name}?`: what the delete takes with it, Keep Library (the default and the Esc button) and Remove Library.

    Remove Library is the destructive button: ERROR fill, never the default button, never on Ctrl+Return, and it
    never takes the first focus (D-21). There is no accent button on this page.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._primary.setStyleSheet(destructive_button_qss())
        self.set_primary(REMOVE_LIBRARY_TEXT)
        self._line = ""
        self._folder: ElidedLabel | None = None
        self._leave: CollapsibleList | None = None
        self._make_back_default(True)

    def _make_back_default(self, on: bool) -> None:
        self._back.setAutoDefault(on)
        self._back.setDefault(on)

    def primary_accepts_ctrl_return(self) -> bool:
        return False

    def show_plan(self, plan) -> None:
        """Fill the confirmation from an ops.RemovePlan."""
        self._clear_body()
        self._folder = self._leave = None
        self.set_heading(REMOVE_HEADING.format(name=plan.name))
        self.set_back(KEEP_LIBRARY_TEXT)
        self.set_primary(REMOVE_LIBRARY_TEXT)
        self.set_primary_shown(True)
        self._make_back_default(True)
        folder = plan.folder.as_posix()
        if plan.exists:
            size = status.size_text(math.ceil(plan.size_bytes / 1_000_000))
            tail = (REMOVE_TAIL_LISTED if plan.listed else REMOVE_TAIL_UNLISTED).format(size=size, name=plan.name)
            self._line = f"{REMOVE_LEAD_TEXT} {folder} {tail}"
            box, lay = _section()
            box.setObjectName("removeLine")
            box.setAccessibleName(self._line)
            lay.addWidget(plain_label(REMOVE_LEAD_TEXT, wrap=True))
            self._folder = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle, full_tooltip=True)
            mono(self._folder)
            self._folder.set_full_text(folder)
            lay.addWidget(self._folder)
            lay.addWidget(plain_label(tail, wrap=True))
            self._add(box)
        else:
            self._line = REMOVE_GONE_TEXT
            self._add(plain_label(REMOVE_GONE_TEXT, wrap=True))
        if plan.nicknames:
            box, lay = _section()
            self._leave = CollapsibleList(LEAVE_TITLE)
            self._leave.set_rows([(name,) for name in plan.nicknames])
            lay.addWidget(self._leave)
            note = plain_label(LEAVE_NOTE, wrap=True)
            muted(note)
            lay.addWidget(note)
            self._add(box)
        if plan.vars:
            box, lay = _section()
            lay.addWidget(plain_label(VARS_USED_HEADING))
            for var in plan.vars:
                label = plain_label(var)
                mono(label)
                lay.addWidget(label)
            note = plain_label(VARS_STAY_NOTE, wrap=True)
            muted(note)
            lay.addWidget(note)
            self._add(box)
        if plan.kicad_open:
            self._add(_kicad_open_line(KICAD_OPEN_REMOVED_TEXT, plan.kicad_open))
        self.refresh_buttons()

    def show_refusal(self, issue) -> None:
        """A delete that failed: the ✖ row (the catalog entry was kept) and Back to List."""
        self._clear_body()
        self._folder = self._leave = None
        self._line = ""
        text = issue.text if isinstance(issue, Issue) else str(issue)
        self._add(status_line(ERROR_GLYPH, text, theme.ERROR))
        self.set_back(BACK_TEXT)
        self.set_primary_shown(False)
        self.refresh_buttons()

    def line_text(self) -> str:
        """The first sentence of the page as one text (`This deletes the folder ...` or the entry-only line)."""
        return self._line

    def folder_label(self) -> ElidedLabel | None:
        return self._folder

    def nickname_list(self) -> CollapsibleList | None:
        return self._leave

    def focus_first(self) -> None:
        """Focus never lands on Remove Library: Keep Library takes it."""
        self._back.setFocus()
