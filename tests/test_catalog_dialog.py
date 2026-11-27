"""The library catalog window, the browse slice (Phase 17 plan 11; CAT-01, CAT-06, CAT-07, D-02, D-05, D-06, D-11, D-16, D-29, D-32).

Every test builds the window with a CatalogServices whose Git check, update check, staging clean-up and KiCad
variable read are fakes, on a synthetic collection under tmp_path: no git process and no network. The window is
never shown on the desktop (the offscreen platform of the conftest).
"""

import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from kicad_lib_manager.catalog import curated, gitnet, manifest, status
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.catalog.ops import NetStatus
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.widgets import catalog_dialog as cd
from kicad_lib_manager.widgets import theme
from kicad_lib_manager.widgets.import_result import ElidedLabel

SHA = "a" * 40
OTHER = "d" * 40
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")
THIRD = replace(SPARKFUN, id="ThirdOne", name="Third One", url="https://github.com/x/third.git")
NET_OK = NetStatus(object(), (2, 50, 0), None, None)
NOW = datetime(2026, 11, 27, 12, 0, 0)


def entry(id, *, url=None, commit=SHA, spdx="MIT", vars=None, ack=False, ack_on="", added="2026-11-20"):
    return CatalogEntry(
        id=id,
        url=url or f"https://github.com/acme/{id.lower()}.git",
        branch="main",
        commit=commit,
        vars=vars or {},
        licence_spdx=spdx,
        acknowledged=ack,
        acknowledged_on=ack_on,
        added_on=added,
    )


def services(**overrides):
    base = dict(
        curated=(SPARKFUN, WURTH, THIRD),
        net_status=lambda root: NET_OK,
        clean_staging=lambda root: [],
        current_path_vars=lambda **kw: {},
        size_on_disk=lambda folder: 69_000_000,
    )
    base.update(overrides)
    return replace(cd.CatalogServices(), **base)


def settle(qtbot, dialog):
    """Wait until the Git check and the KiCad variable read of the newest load have answered."""
    qtbot.waitUntil(lambda: dialog._net_status is not None and dialog._vars_read, timeout=10000)


def build(qtbot, tmp_path, *, entries=(), folders=(), guides=None, settled=True, clock=None, **overrides):
    root = make_collection(tmp_path / "col")
    for id in folders:
        make_third_party(root, id, {"a.kicad_sym": "(kicad_symbol_lib)"})
    if entries:
        assert manifest.save(root, Manifest(tuple(entries))) is None
    kwargs = {"services": services(**overrides), "show_guide": guides.append if guides is not None else (lambda topic: None)}
    if clock is not None:
        kwargs["clock"] = clock
    dialog = cd.CatalogDialog(root, **kwargs)
    qtbot.addWidget(dialog)
    if settled:
        settle(qtbot, dialog)
    return dialog


def items(dialog):
    tree = dialog._tree
    return [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]


def by_name(dialog):
    return {item.text(0): item for item in items(dialog)}


def shown_names(dialog):
    return [item.text(0) for item in items(dialog) if not item.isHidden()]


def colour(item, column):
    return item.foreground(column).color().name().upper()


def hex_of(token):
    return QColor(token).name().upper()


# -- the shell ---------------------------------------------------------------------------------


def test_window_is_parentless_and_non_modal(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert dialog.parent() is None
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert not dialog.isModal()


def test_title_size_and_minimum(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert cd.CATALOG_TITLE == "Library Catalog - KiCad External Lib Manager"
    assert dialog.windowTitle() == cd.CATALOG_TITLE
    assert dialog.size() == QSize(900, 640)
    assert dialog.minimumSize() == QSize(760, 520)


def test_header_path_is_elided_mono_with_tooltip(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    root = dialog._root
    assert dialog._heading.text() == "Library Catalog"
    assert dialog._installed_in.text() == "Libraries are installed in "
    label = dialog._path_label
    assert isinstance(label, ElidedLabel)
    assert label.font().family() == theme.MONO_FAMILY
    expected = f"{root.as_posix()}/ThirdParty"
    assert label.full_text() == expected
    assert label.toolTip() == expected


def test_long_collection_path_elides_in_the_middle(qtbot, tmp_path):
    long_parent = tmp_path / ("p" * 100) / ("q" * 100)
    long_parent.mkdir(parents=True)
    root = make_collection(long_parent / "col")
    dialog = cd.CatalogDialog(root, services=services(), show_guide=lambda topic: None)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: "…" in dialog._path_label.text())
    assert dialog._path_label.text() != dialog._path_label.full_text()
    assert dialog._path_label.full_text().endswith("/col/ThirdParty")
    assert dialog._path_label.text().endswith("ThirdParty")  # middle elision keeps both ends
    assert dialog.width() <= 900


# -- the list ----------------------------------------------------------------------------------


STATUS_FIXTURE = dict(
    entries=[
        entry("SparkFun", url=SPARKFUN.url, spdx="CC-BY-4.0", commit=SHA),
        entry("demo", url="https://github.com/acme/demo-lib.git"),
        entry("alpha", url="https://github.com/acme/alpha.git"),
        entry("WurthElektronik", url=WURTH.url, spdx=None),
    ],
    folders=["SparkFun", "demo", "alpha", "Stray"],  # WurthElektronik has an entry but no folder
)


def with_updates(dialog):
    dialog.apply_update_states(
        {
            "SparkFun": status.UpdateState("SparkFun", status.Check.CURRENT, SHA, NOW),
            "alpha": status.UpdateState("alpha", status.Check.AVAILABLE, OTHER, NOW),
        }
    )
    return dialog


def test_status_texts_and_colours(qtbot, tmp_path):
    dialog = with_updates(build(qtbot, tmp_path, **STATUS_FIXTURE))
    rows = by_name(dialog)
    expected = {
        "Third One": ("Not installed", theme.MUTED, "Not installed"),
        "SparkFun": ("✓ Installed", theme.SUCCESS, "✓ Installed"),
        "acme/demo-lib": (
            "Installed",
            theme.MUTED,
            "Updates have not been checked, or GitHub could not be reached.",
        ),
        "acme/alpha": ("⚠ Update available", theme.AMBER, "⚠ Update available"),
        "Würth Elektronik": ("✖ Problem: folder missing", theme.ERROR, "✖ Problem: folder missing"),
        "Stray": ("⚠ Problem: not in the catalog", theme.AMBER, "⚠ Problem: not in the catalog"),
    }
    assert set(rows) == set(expected)
    for name, (text, token, tip) in expected.items():
        cell = rows[name]
        assert cell.text(1) == text, name
        assert colour(cell, 1) == hex_of(token), name
        assert cell.toolTip(1) == tip, name


def test_installed_stays_muted_when_a_check_could_not_run(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    dialog.apply_update_states(
        {"SparkFun": status.UpdateState("SparkFun", status.Check.UNKNOWN, None, NOW)}
    )
    cell = by_name(dialog)["SparkFun"]
    assert cell.text(1) == "Installed"
    assert colour(cell, 1) == hex_of(theme.MUTED)


def test_unreadable_record_makes_every_row_unknown(qtbot, tmp_path):
    issue = Issue(Severity.ERROR, "catalog.unreadable", "The library list is damaged.")
    dialog = build(qtbot, tmp_path, load_manifest=lambda root: issue)
    for item in items(dialog):
        assert item.text(1) == "Unknown"
        assert colour(item, 1) == hex_of(theme.MUTED)


def test_rows_sorted_and_stable(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    before = [item.text(0) for item in items(dialog)]
    assert before == sorted(before, key=str.casefold)
    with_updates(dialog)
    assert [item.text(0) for item in items(dialog)] == before
    dialog.refresh()
    assert [item.text(0) for item in items(dialog)] == before


def test_list_columns_and_behaviour(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    tree = dialog._tree
    header = tree.headerItem()
    assert [header.text(i) for i in range(4)] == ["Name", "Status", "Licence", "Size"]
    assert [tree.columnWidth(i) for i in (1, 2, 3)] == [200, 120, 80]
    assert tree.accessibleName() == "Libraries"
    assert not tree.rootIsDecorated()
    assert tree.selectionMode() == tree.SelectionMode.SingleSelection
    assert tree.selectionBehavior() == tree.SelectionBehavior.SelectRows


def test_header_click_does_not_sort(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    dialog.show()
    tree = dialog._tree
    assert not tree.isSortingEnabled()
    assert not tree.header().sectionsClickable()
    before = [item.text(0) for item in items(dialog)]
    section = tree.header().sectionViewportPosition(3) + 10
    qtbot.mouseClick(tree.header().viewport(), Qt.MouseButton.LeftButton, pos=QPoint(section, 5))
    assert [item.text(0) for item in items(dialog)] == before


def test_cells_elide_with_tooltips(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    for item in items(dialog):
        for column in (0, 2, 3):
            assert item.toolTip(column) == item.text(column)
    assert dialog._tree.textElideMode() == Qt.TextElideMode.ElideRight


def test_size_and_licence_cells(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    rows = by_name(dialog)
    assert (rows["SparkFun"].text(2), rows["SparkFun"].text(3)) == ("CC BY 4.0", "69 MB")
    assert (rows["Würth Elektronik"].text(2), rows["Würth Elektronik"].text(3)) == ("Proprietary", "2.7 GB")
    stray = rows["Stray"]
    assert (stray.text(2), stray.text(3)) == ("Unknown", "Unknown")
    assert colour(stray, 2) == hex_of(theme.MUTED) and colour(stray, 3) == hex_of(theme.MUTED)
    assert rows["SparkFun"].textAlignment(3) & Qt.AlignmentFlag.AlignRight


# -- search ------------------------------------------------------------------------------------


def test_search_filters_and_empty_state(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    search = dialog._search
    assert search.placeholderText() == "Search libraries"
    assert search.accessibleName() == "Search libraries"
    assert search.isClearButtonEnabled()
    everything = shown_names(dialog)
    assert len(everything) == 6

    search.setText("SPARKFUN")  # case-insensitive, on the name
    assert shown_names(dialog) == ["SparkFun", "Third One"]  # Third One is a copy with the same description
    search.setText("for sparkfun parts and boards")  # on the description
    assert set(shown_names(dialog)) == {"SparkFun", "Third One"}
    search.setText("github.com/ACME")  # on the repository
    assert set(shown_names(dialog)) == {"acme/demo-lib", "acme/alpha"}
    search.setText("")
    assert shown_names(dialog) == everything

    search.setText("no such library")
    assert shown_names(dialog) == []
    assert dialog._list_stack.currentWidget() is dialog._empty_list
    assert dialog._empty_heading.text() == "No library matches your search"
    assert dialog._empty_body.text() == "Clear the search, or press Add by URL... to add a library from GitHub."
    search.setText("")
    assert dialog._list_stack.currentWidget() is dialog._tree


def test_search_keeps_selection_only_when_the_row_still_matches(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    by_name(dialog)["SparkFun"].setSelected(True)
    assert dialog.selected_id() == "SparkFun"
    dialog._search.setText("spark")
    assert dialog.selected_id() == "SparkFun"
    dialog._search.setText("demo")
    assert dialog.selected_id() is None
    assert dialog._pages.currentWidget() is dialog._empty_page
    assert dialog._empty_label.text() == "Select a library to see its details."


def test_down_in_search_leads_into_the_list(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path, **STATUS_FIXTURE)
    dialog.show()
    dialog._search.setFocus()
    qtbot.keyClick(dialog._search, Qt.Key.Key_Down)
    assert dialog._tree.hasFocus() or dialog.focusWidget() is dialog._tree


# -- the strips and the actions ----------------------------------------------------------------


def strip_state(dialog):
    return {
        "record": not dialog._record_strip.isHidden(),
        "missing": not dialog._git_missing_strip.isHidden(),
        "old": not dialog._git_old_strip.isHidden(),
    }


def test_no_strip_and_no_reserved_space_when_nothing_applies(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert strip_state(dialog) == {"record": False, "missing": False, "old": False}
    assert not dialog._git_too_old_strip.isVisibleTo(dialog)


def test_unreadable_record_strip_disables_actions(qtbot, tmp_path):
    issue = Issue(Severity.ERROR, "catalog.unreadable", "The library list is damaged.")
    dialog = build(qtbot, tmp_path, load_manifest=lambda root: issue)
    text = (
        "✖ The catalog record of this collection cannot be read (The library list is damaged.). "
        f"Nothing was changed. Fix or delete catalog.json in {dialog._root.as_posix()}, then reopen the catalog."
    )
    assert not dialog._record_strip.isHidden()
    assert dialog._record_label.text() == text
    assert dialog._record_label.toolTip() == text
    for button in (dialog._check_btn, dialog._add_url_btn):
        assert not button.isEnabled()
        assert button.toolTip() == "The catalog record cannot be read."
    # browsing keeps working
    assert dialog._search.isEnabled() and dialog._help_btn.isEnabled() and dialog._close_btn.isEnabled()
    assert dialog._tree.isEnabled()


def test_git_missing_strip(qtbot, tmp_path):
    refusal, _ = gitnet.version_issues(None)
    dialog = build(qtbot, tmp_path, net_status=lambda root: NetStatus(None, None, refusal, None))
    assert strip_state(dialog) == {"record": False, "missing": True, "old": False}
    assert dialog._git_missing_label.text() == (
        "✖ Git was not found. The catalog needs Git to download libraries. "
        "Install Git for Windows, then reopen the catalog."
    )
    for button in (dialog._check_btn, dialog._add_url_btn):
        assert not button.isEnabled()
        assert button.toolTip() == "Git was not found."


def test_git_too_old_strip_disables_network_actions(qtbot, tmp_path):
    refusal, _ = gitnet.version_issues((2, 30, 0))
    dialog = build(qtbot, tmp_path, net_status=lambda root: NetStatus(None, (2, 30, 0), refusal, None))
    assert not dialog._git_too_old_strip.isHidden()
    assert dialog._git_missing_strip.isHidden() and dialog._git_old_strip.isHidden()
    assert dialog._git_too_old_label.text() == f"✖ {refusal.text}"
    assert "2.32" in dialog._git_too_old_label.text()
    for button in (dialog._check_btn, dialog._add_url_btn):
        assert not button.isEnabled()
        assert button.toolTip() == "Your Git is too old for the catalog."


def test_old_git_strip_only_without_missing(qtbot, tmp_path):
    _, warning = gitnet.version_issues((2, 40, 0))
    dialog = build(qtbot, tmp_path, net_status=lambda root: NetStatus(object(), (2, 40, 0), None, warning))
    assert strip_state(dialog) == {"record": False, "missing": False, "old": True}
    assert dialog._git_old_label.text() == f"⚠ {warning.text}"
    assert dialog._check_btn.isEnabled() and dialog._add_url_btn.isEnabled()  # the catalog allows an old Git
    # a refusal and a warning never show two Git strips
    refusal, _ = gitnet.version_issues(None)
    both = NetStatus(None, None, refusal, warning)
    dialog2 = build(qtbot, tmp_path / "two", net_status=lambda root: both)
    shown = [s for s in (dialog2._git_missing_strip, dialog2._git_too_old_strip, dialog2._git_old_strip) if not s.isHidden()]
    assert len(shown) == 1


def test_strips_stack_in_the_fixed_order(qtbot, tmp_path):
    issue = Issue(Severity.ERROR, "catalog.unreadable", "The library list is damaged.")
    refusal, _ = gitnet.version_issues(None)
    dialog = build(
        qtbot,
        tmp_path,
        load_manifest=lambda root: issue,
        net_status=lambda root: NetStatus(None, None, refusal, None),
    )
    layout = dialog.layout()
    order = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget() is not None]
    assert order.index(dialog._record_strip) < order.index(dialog._git_missing_strip) < order.index(dialog._git_too_old_strip)
    assert order.index(dialog._git_too_old_strip) < order.index(dialog._git_old_strip)
    assert order.index(dialog._git_old_strip) < order.index(dialog._toolbar)


def test_set_blocked_disables_with_reason(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert dialog._check_btn.isEnabled() and dialog._add_url_btn.isEnabled()
    reason = "Wait for the scan in the main window to end."
    dialog.set_blocked(reason)
    for button in (dialog._check_btn, dialog._add_url_btn):
        assert not button.isEnabled()
        assert button.toolTip() == reason
    assert dialog._search.isEnabled() and dialog._help_btn.isEnabled() and dialog._close_btn.isEnabled()
    dialog.set_blocked(None)
    assert dialog._check_btn.isEnabled() and dialog._add_url_btn.isEnabled()
    assert dialog._check_btn.toolTip() == ""


def test_set_finishing_disables_with_reason_and_signals(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert not dialog.is_finishing() and not dialog.is_job_running() and not dialog.holds_download()
    with qtbot.waitSignal(dialog.busy_changed, timeout=1000):
        dialog.set_finishing(True)
    assert dialog.is_finishing()
    assert not dialog._check_btn.isEnabled()
    assert dialog._check_btn.toolTip() == "Finishing the last change..."
    with qtbot.waitSignal(dialog.busy_changed, timeout=1000):
        dialog.set_finishing(False)
    assert dialog._check_btn.isEnabled()


def test_git_check_and_cleanup_run_off_the_gui_thread(qtbot, tmp_path):
    threads = {}

    def net(root):
        threads["net"] = threading.current_thread()
        return NET_OK

    def clean(root):
        threads["clean"] = threading.current_thread()
        return []

    dialog = build(qtbot, tmp_path, net_status=net, clean_staging=clean)
    qtbot.waitUntil(lambda: set(threads) == {"net", "clean"}, timeout=5000)
    main = threading.current_thread()
    assert threads["net"] is not main and threads["clean"] is not main
    assert dialog.isEnabled()


def test_stale_git_result_is_dropped_after_a_root_change(qtbot, tmp_path):
    gate = threading.Event()
    refusal, _ = gitnet.version_issues(None)
    first_root = []

    def net(root):
        if not first_root:
            first_root.append(root)
            gate.wait(10)
            return NetStatus(None, None, refusal, None)  # the old answer: Git missing
        return NET_OK

    dialog = build(qtbot, tmp_path, net_status=net, settled=False)
    qtbot.waitUntil(lambda: bool(first_root), timeout=5000)
    other = make_collection(tmp_path / "other")
    dialog.set_root(other)
    qtbot.waitUntil(lambda: dialog._net_status is not None, timeout=5000)
    gate.set()
    qtbot.wait(100)
    assert dialog._net_status is NET_OK
    assert dialog._git_missing_strip.isHidden()
    assert dialog._root == other


# -- plain text, focus, help --------------------------------------------------------------------


def test_plain_text_names(qtbot, tmp_path):
    name = "R&D <Parts>"
    dialog = build(qtbot, tmp_path, curated=(replace(SPARKFUN, name=name),))
    item = by_name(dialog)[name]
    assert item.text(0) == name and item.toolTip(0) == name
    for label in dialog.findChildren(QLabel):
        if label.objectName() != "repositoryLink":
            assert label.textFormat() == Qt.TextFormat.PlainText, label.objectName() or label.text()


def test_focus_starts_in_search_and_f1_opens_help(qtbot, tmp_path):
    guides = []
    dialog = build(qtbot, tmp_path, guides=guides)
    dialog.show()
    assert dialog.focusWidget() is dialog._search
    assert dialog._help_btn.shortcut().toString() == "F1"
    dialog._help_btn.click()
    assert guides == [cd.CATALOG_TOPIC] == ["catalog"]


def test_close_is_the_default_button_on_the_idle_list(qtbot, tmp_path):
    dialog = build(qtbot, tmp_path)
    assert dialog._close_btn.text() == "Close"
    assert dialog._close_btn.isDefault()
    assert not dialog._check_btn.autoDefault() and not dialog._add_url_btn.autoDefault()
