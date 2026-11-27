"""Geometry of the library catalog window at its size limits (Phase 17 plan 11; UI-SPEC C2, C3, C4, C5 and C12 backstops).

Offscreen qtbot tests (the conftest forces the offscreen platform): the window is laid out at 760 x 520, 900 x 640
and 1100 x 720 and the pieces are checked against each other and against the window. Nothing is skipped.
"""

import threading
from dataclasses import replace
from pathlib import Path

import geometryfixtures as gf
import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget

from kicad_lib_manager.catalog import addons, curated, gitnet, manifest, status
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.catalog.ops import NetStatus
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.widgets import catalog_dialog as cd

SHA = "a" * 40
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")
NET_OK = NetStatus(object(), (2, 50, 0), None, None)
SIZES = [(760, 520), (900, 640), (1100, 720)]
LIST_READ = lambda: addons.IndexRead((), None, False, "")  # noqa: E731 - a read of KiCad's add-on list that found nothing to add


def entry(id, url):
    return CatalogEntry(id=id, url=url, branch="main", commit=SHA, licence_spdx="MIT", added_on="2026-11-20")


def services(**overrides):
    base = dict(
        curated=(SPARKFUN, WURTH),
        net_status=lambda root: NET_OK,
        clean_staging=lambda root: [],
        current_path_vars=lambda **kw: {},
        size_on_disk=lambda folder: 69_000_000,
    )
    base.update(overrides)
    return replace(cd.CatalogServices(), **base)


def make(qtbot, tmp_path, *, size=(900, 640), real_root=True, **overrides):
    root = make_collection(tmp_path / "col") if real_root else tmp_path / ("p" * 100) / ("q" * 90) / "col"
    if real_root:
        for id in ("SparkFun", "demo", "Stray"):
            make_third_party(root, id, {"a.kicad_sym": "(kicad_symbol_lib)"})
        entries = (
            entry("SparkFun", SPARKFUN.url),
            entry("demo", "https://github.com/acme/demo-lib.git"),
            entry("WurthElektronik", WURTH.url),
        )
        assert manifest.save(root, Manifest(entries)) is None
    dialog = cd.CatalogDialog(root, services=services(**overrides), show_guide=lambda topic: None)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._net_status is not None and dialog._vars_read, timeout=10000)
    dialog.resize(*size)
    dialog.show()
    qtbot.wait(50)
    return dialog


def select(dialog, name):
    for index in range(dialog._tree.topLevelItemCount()):
        item = dialog._tree.topLevelItem(index)
        if item.text(0) == name:
            dialog._tree.setCurrentItem(item)
            item.setSelected(True)
            return item
    raise AssertionError(name)


def inside(widget: QWidget, window: QWidget) -> bool:
    """True when widget's whole rectangle lies inside window's rectangle."""
    top_left = widget.mapTo(window, widget.rect().topLeft())
    bottom_right = widget.mapTo(window, widget.rect().bottomRight())
    return window.rect().contains(top_left) and window.rect().contains(bottom_right)


def no_horizontal_scroll(dialog):
    assert not dialog._tree.horizontalScrollBar().isVisible()
    assert not dialog._scroll.horizontalScrollBar().isVisible()
    page = dialog._pages
    assert page.width() <= dialog._scroll.viewport().width()


# -- the minimum size and the default -----------------------------------------------------------


@pytest.mark.parametrize("size", SIZES)
def test_minimum_size_keeps_everything_reachable(qtbot, tmp_path, size):
    dialog = make(qtbot, tmp_path, size=size)
    select(dialog, "SparkFun")
    dialog.show_result([("Added SparkFun.", "success"), ("A second line.", "warning")], generate=True, manifest_note=True)
    qtbot.wait(50)

    assert dialog.size() == QSize(*size)  # the window did not grow to fit its content
    for widget in (dialog._toolbar, dialog._search, dialog._check_btn, dialog._add_url_btn, dialog._help_btn, dialog._close_btn):
        assert widget.isVisible() and inside(widget, dialog), widget
    # the four column headers fit the list, in full
    header = dialog._tree.header()
    assert [header.sectionSize(i) > 0 for i in range(4)] == [True] * 4
    assert header.sectionViewportPosition(3) + header.sectionSize(3) <= dialog._tree.viewport().width() + 1
    # the Details rows and the page's visible buttons
    assert dialog._pages.currentWidget() is dialog._details_page
    for key, (label, value) in dialog._field_rows.items():
        if not label.isHidden():
            assert value.mapTo(dialog, value.rect().topRight()).x() <= dialog.width(), key
    assert inside(dialog._result_generate_btn, dialog) or dialog._scroll.verticalScrollBar().maximum() > 0
    no_horizontal_scroll(dialog)
    assert gf.overlapping_children(dialog) == []
    assert gf.clipped_wrapped_labels(dialog) == []


@pytest.mark.parametrize("size", SIZES)
def test_list_and_pane_keep_their_minimums(qtbot, tmp_path, size):
    dialog = make(qtbot, tmp_path, size=size)
    assert dialog._list_stack.height() >= cd.LIST_MINIMUM_HEIGHT
    assert dialog._scroll.parentWidget().height() >= cd.PANE_MINIMUM_HEIGHT


def test_tall_details_scroll_inside_the_pane(qtbot, tmp_path):
    dialog = make(qtbot, tmp_path, size=(760, 520))
    select(dialog, "SparkFun")
    lines = [(f"Line {n}: a long enough result line to wrap in the narrow strip of the detail pane window.", "warning") for n in range(14)]
    dialog.show_result(lines, generate=True, manifest_note=True)
    qtbot.wait(100)
    assert dialog.size() == QSize(760, 520)
    assert dialog._scroll.verticalScrollBar().maximum() > 0  # the pane scrolls instead of growing the window
    assert inside(dialog._close_btn, dialog) and inside(dialog._toolbar, dialog)
    assert dialog._list_stack.height() >= cd.LIST_MINIMUM_HEIGHT


# -- long text -----------------------------------------------------------------------------------


def _long_row(root: Path, name: str) -> status.Row:
    folder = root / "ThirdParty" / ("f" * 120)
    known = curated.curated_by_id("SparkFun")
    return status.Row(
        id="f" * 120,
        name=name,
        state=status.State.INSTALLED,
        licence_label="MIT",
        licence_class=status.LicenceClass.OPEN,
        size_mb=69,
        size_text="69 MB",
        entry=CatalogEntry(id="f" * 120, url="https://github.com/" + "o" * 39 + "/" + "r" * 90, branch="main", commit=SHA, added_on="2026-11-20"),
        curated=known,
        folder=folder,
        update=None,
    )


def test_long_names_elide_without_widening(qtbot, tmp_path):
    name = "N" * 60

    def rows(root, mf, *, curated=(), updates=None, listings=()):
        return [_long_row(root, name)]

    dialog = make(qtbot, tmp_path, real_root=False, row_statuses=rows)
    select(dialog, name)
    qtbot.wait(100)
    assert dialog.width() <= 900
    # the 200-character collection path is elided in the header and complete in the tooltip
    path = dialog._path_label
    assert len(path.full_text()) >= 200 and "…" in path.text() and path.toolTip() == path.full_text()
    # the 60-character name wraps or fits, and the folder path elides
    assert dialog._detail_heading.full_text() == name
    folder = dialog._field_rows["folder"][1]
    assert len(folder.full_text()) > 150 and "…" in folder.text() and folder.toolTip() == folder.full_text()
    no_horizontal_scroll(dialog)
    for widget in (dialog._toolbar, dialog._check_btn, dialog._add_url_btn, dialog._close_btn):
        assert inside(widget, dialog)
    assert dialog._check_btn.width() >= dialog._check_btn.sizeHint().width()
    assert gf.clipped_wrapped_labels(dialog) == []
    assert dialog.width() <= 900


def test_markup_names_show_as_typed(qtbot, tmp_path):
    name = "R&D <Parts>"
    dialog = make(qtbot, tmp_path, curated=(replace(SPARKFUN, name=name), WURTH))
    select(dialog, name)
    item = dialog._tree.currentItem()
    assert item.text(0) == name and item.toolTip(0) == name
    # a mnemonic would drop the ampersand and markup would swallow the angle brackets in the shown text
    assert dialog._detail_heading.text() == name
    assert dialog._detail_heading.textFormat() == Qt.TextFormat.PlainText


# -- the toolbar and the strips --------------------------------------------------------------------


def test_search_shrinks_first(qtbot, tmp_path):
    dialog = make(qtbot, tmp_path, size=(760, 520))
    for button in (dialog._check_btn, dialog._add_url_btn):
        assert button.width() >= button.sizeHint().width()
    # squeeze the toolbar row: the search field gives way, the two buttons keep their full text
    full_search = dialog._search.width()
    buttons = dialog._check_btn.sizeHint().width() + dialog._add_url_btn.sizeHint().width()
    dialog._toolbar.setFixedWidth(buttons + 2 * 8 + dialog._search.minimumWidth() + 40)
    dialog._toolbar.layout().activate()
    qtbot.wait(30)
    assert dialog._search.width() < full_search
    for button in (dialog._check_btn, dialog._add_url_btn):
        metrics = button.fontMetrics()
        assert button.width() >= button.sizeHint().width()
        assert button.width() >= metrics.horizontalAdvance(button.text())
    assert dialog._search.width() >= dialog._search.minimumWidth()


def test_all_strips_at_minimum_height(qtbot, tmp_path):
    reason = "The library list is damaged. " * 10
    issue = Issue(Severity.ERROR, "catalog.unreadable", reason.strip())
    refusal, _ = gitnet.version_issues((2, 30, 0))
    dialog = make(
        qtbot,
        tmp_path,
        size=(760, 520),
        load_manifest=lambda root: issue,
        net_status=lambda root: NetStatus(None, (2, 30, 0), refusal, None),
        read_index=LIST_READ,  # the list of KiCad's add-ons is read: its line is hidden (the next test shows it)
    )
    qtbot.waitUntil(lambda: dialog._index_state == "ok", timeout=10000)
    assert dialog._index_line.isHidden()
    assert not dialog._record_strip.isHidden() and not dialog._git_too_old_strip.isHidden()
    assert dialog.size() == QSize(760, 520)
    assert dialog._list_stack.height() >= cd.LIST_MINIMUM_HEIGHT
    assert dialog._toolbar.isVisible() and inside(dialog._toolbar, dialog)
    assert inside(dialog._close_btn, dialog)
    assert gf.overlapping_children(dialog) == []
    assert gf.clipped_wrapped_labels(dialog) == []
    # with the amber strip instead of the refusal the same holds
    _, warning = gitnet.version_issues((2, 40, 0))
    other = make(
        qtbot,
        tmp_path / "amber",
        size=(760, 520),
        load_manifest=lambda root: issue,
        net_status=lambda root: NetStatus(object(), (2, 40, 0), None, warning),
        read_index=LIST_READ,
    )
    assert not other._git_old_strip.isHidden()
    assert other._list_stack.height() >= cd.LIST_MINIMUM_HEIGHT and inside(other._toolbar, other)


def test_all_strips_and_the_reading_line_at_minimum_height(qtbot, tmp_path):
    """The line under the strips ('Reading KiCad's add-on list...') takes room too: the list keeps 120 px, the toolbar stays."""
    gate = threading.Event()
    reason = "The library list is damaged. " * 10
    issue = Issue(Severity.ERROR, "catalog.unreadable", reason.strip())
    refusal, _ = gitnet.version_issues((2, 30, 0))
    try:
        dialog = make(
            qtbot,
            tmp_path,
            size=(760, 520),
            load_manifest=lambda root: issue,
            net_status=lambda root: NetStatus(None, (2, 30, 0), refusal, None),
            read_index=lambda: (gate.wait(10), None)[1],
        )
        assert dialog._index_state == "reading" and not dialog._index_line.isHidden()
        assert dialog._index_line.text() == "Reading KiCad's add-on list..."
        assert not dialog._record_strip.isHidden() and not dialog._git_too_old_strip.isHidden()
        assert dialog.size() == QSize(760, 520)
        assert dialog._list_stack.height() >= cd.LIST_MINIMUM_HEIGHT
        assert dialog._toolbar.isVisible() and inside(dialog._toolbar, dialog)
        assert inside(dialog._close_btn, dialog)
        assert gf.overlapping_children(dialog) == []
        # with the line added the two long strips may be cut at 760 x 520: the list and the toolbar are what must stay
    finally:
        gate.set()
