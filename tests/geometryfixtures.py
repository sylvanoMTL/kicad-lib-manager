"""Geometry checks for the dialogs (Phase 15-14, UAT gap 3), shared by the in-process tests and the 1.75 child.

Plain helpers over Qt widgets, plus the dialog cases both runs build. The package is imported inside the
builders only, so the geometry checks themselves stay Qt-only.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


def _name(widget: QWidget) -> str:
    text = getattr(widget, "text", None)
    if callable(text):
        try:
            return f"{type(widget).__name__} {ascii(str(text())[:40])}"
        except TypeError:
            pass
    return type(widget).__name__


def _visible_children(widget: QWidget) -> list[QWidget]:
    return [
        child
        for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
        if child.isVisibleTo(widget) and not child.isWindow()
    ]


def overlapping_children(widget: QWidget) -> list[str]:
    """Name every pair of visible sibling widgets whose geometries intersect, under widget and its laid-out children."""
    found: list[str] = []
    children = _visible_children(widget)
    for index, first in enumerate(children):
        for second in children[index + 1:]:
            if first.geometry().intersects(second.geometry()):
                found.append(f"{_name(first)} overlaps {_name(second)}")
    for child in children:
        if child.layout() is not None:
            found.extend(overlapping_children(child))
    return found


def clipped_wrapped_labels(widget: QWidget) -> list[str]:
    """Name every visible word-wrapped label under widget that is shorter than its height for its width."""
    found: list[str] = []
    for label in widget.findChildren(QLabel):
        if label.isVisibleTo(widget) and label.wordWrap() and label.height() < label.heightForWidth(label.width()):
            found.append(f"{_name(label)} is {label.height()} px, needs {label.heightForWidth(label.width())}")
    return found


def largest_vertical_gap(widget: QWidget) -> tuple[int, str]:
    """The largest empty band between the visible direct children of widget, with the two widgets around it.

    The children are walked top to bottom; the gap is a child's top minus the lowest bottom so far
    (bottom = y + height). Returns (0, "") when there is no gap or fewer than two children.
    """
    children = sorted(_visible_children(widget), key=lambda child: child.y())
    largest, between = 0, ""
    lowest, lowest_child = None, None
    for child in children:
        if lowest is not None and child.y() - lowest > largest:
            largest = child.y() - lowest
            between = f"{_name(lowest_child)} / {_name(child)}"
        bottom = child.y() + child.height()
        if lowest is None or bottom > lowest:
            lowest, lowest_child = bottom, child
    return largest, between


def content_bottom(widget: QWidget, ancestor: QWidget) -> int:
    """The lowest bottom (y + height, mapped into ancestor) of widget's visible direct children.

    A widget without visible children gives its own top in ancestor.
    """
    bottoms = [child.mapTo(ancestor, child.rect().topLeft()).y() + child.height() for child in _visible_children(widget)]
    if not bottoms:
        return widget.mapTo(ancestor, widget.rect().topLeft()).y()
    return max(bottoms)


def stretched_labels(widget: QWidget, slack: int) -> list[str]:
    """Name every visible label under widget taller than it needs by more than slack pixels.

    What a label needs is heightForWidth(width) when it word-wraps, else its size hint height.
    """
    found: list[str] = []
    for label in widget.findChildren(QLabel):
        if not label.isVisibleTo(widget):
            continue
        need = label.heightForWidth(label.width()) if label.wordWrap() else label.sizeHint().height()
        if label.height() - need > slack:
            found.append(f"{_name(label)} is {label.height()} px, needs {need}")
    return found


def needed_height(dialog: QWidget) -> int:
    layout = dialog.layout()
    layout.activate()
    needed = layout.totalMinimumSize().height()
    if layout.hasHeightForWidth():
        needed = max(needed, layout.totalHeightForWidth(dialog.width()))
    return needed


def missing_height(dialog: QWidget) -> int:
    """How many pixels the dialog is shorter than its layout needs for its width (0 or less when it fits)."""
    return needed_height(dialog) - dialog.height()


# -- The dialog cases (the same in the test process and in the 1.75 child) -----------------------------

LONG_WARN_ROW = (
    "The path is 122 characters long. KiCad and git can fail on long Windows paths. "
    "A shorter folder such as C:/KiCad_Libraries is safer."
)
LONG_FAIL_ROW = (
    "This is not a library collection: it has no Custom folder with Symbols or Footprints inside. "
    "To start a new collection, use New Library Collection... with an empty or new folder."
)
NC_CASES = ("nc-setup", "nc-choose", "nc-issues")
CHOOSE_CASES = ("choose-main", "choose-setup", "choose-failure")
ALL_CASES = (*NC_CASES, *CHOOSE_CASES)


def new_collection_case(case: str, work: Path):
    """A New Collection dialog (real check, fake git) for case nc-setup, nc-choose or nc-issues; not shown yet."""
    from kicad_lib_manager.widgets.new_collection_dialog import NewCollectionDialog

    work = Path(work)
    find_git = lambda root: Path("git")  # noqa: E731
    if case == "nc-setup":
        parent = work / "parent"
        parent.mkdir(parents=True, exist_ok=True)
        return NewCollectionDialog(origin="setup", parent_folder=parent, name="KiCad_Libraries", find_git=find_git)
    if case == "nc-choose":
        parent = work / "parent"
        (parent / "Existing").mkdir(parents=True, exist_ok=True)
        return NewCollectionDialog(origin="choose", parent_folder=parent, name="Existing", find_git=find_git)
    if case == "nc-issues":
        parent = work / ("p" * 90) / ("q" * 40)
        parent.mkdir(parents=True, exist_ok=True)
        return NewCollectionDialog(origin="setup", parent_folder=parent, name="KiCad_Libraries", find_git=find_git)
    raise ValueError(case)


def settle_new_collection(dialog, pump, deadline_s: float = 20.0) -> bool:
    """Call pump() until the newest check answered; False when it did not within the deadline."""
    import time

    end = time.monotonic() + deadline_s
    while dialog._pending:
        if time.monotonic() > end:
            return False
        pump()
    return True


def fake_choose_check(rows):
    """A check function for the Choose dialog that answers the given rows for any folder."""
    from kicad_lib_manager.collection import FolderCheck

    def check(path, *, current=None):
        return FolderCheck(Path(path), tuple(rows), "collection", 122)

    return check


def choose_rows(with_warning: bool = True):
    from kicad_lib_manager.collection import CheckRow

    rows = [
        CheckRow("pass", "This folder exists"),
        CheckRow("pass", "You can write to this folder"),
        CheckRow("pass", "It is a library collection", " (Custom holds Symbols or Footprints)"),
    ]
    if with_warning:
        rows.append(CheckRow("warn", LONG_WARN_ROW))
    return rows


def choose_case(case: str, work: Path):
    """A Choose dialog with a fake check for choose-main, choose-setup or choose-failure; the field is set, not shown."""
    from kicad_lib_manager.collection import CheckRow, FolderCheck
    from kicad_lib_manager.widgets.choose_folder_dialog import ChooseLibraryFolderDialog

    folder = Path(work) / "collection"
    folder.mkdir(parents=True, exist_ok=True)
    if case == "choose-main":
        return ChooseLibraryFolderDialog(folder, origin="main", check=fake_choose_check(choose_rows()))
    if case == "choose-setup":
        dialog = ChooseLibraryFolderDialog(None, origin="setup", check=fake_choose_check(choose_rows()))
        dialog._field.setText(str(folder))
        return dialog
    if case == "choose-failure":

        def check(path, *, current=None):
            return FolderCheck(Path(path), (CheckRow("fail", LONG_FAIL_ROW),), "not_collection", 30)

        return ChooseLibraryFolderDialog(folder, origin="main", check=check)
    raise ValueError(case)


def settle_choose(dialog, pump, deadline_s: float = 20.0) -> bool:
    import time

    end = time.monotonic() + deadline_s
    while dialog._pending or dialog._result is None:
        if time.monotonic() > end:
            return False
        pump()
    return True
