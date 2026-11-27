"""The Update and Remove flows of the library catalog window (Phase 17 plan 15; CAT-01, CAT-04, CAT-06, D-05..D-09, D-16, D-21).

The first part builds UpdatePreviewPage and RemovePage standalone with synthetic plans (no dialog, no service, no
worker); the second part builds the whole window with fake catalog services that record their calls and wait on
gates the test controls: no git process, no network, nothing shown on the desktop (offscreen platform).
"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from kicad_lib_manager.catalog import ops
from kicad_lib_manager.catalog.manifest import CatalogEntry
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.widgets import catalog_pages as cp
from kicad_lib_manager.widgets import theme
from kicad_lib_manager.widgets.import_result import ElidedLabel

FAKE_COLLECTION = Path("/collection")
OLD = "1234567" + "a" * 33
NEW = "7654321" + "b" * 33


def entry_of(id="Acme", *, vars=None):
    return CatalogEntry(
        id=id, url=f"https://github.com/acme/{id.lower()}.git", branch="main", commit=OLD, vars=dict(vars or {}),
        licence_spdx="MIT", acknowledged=True, acknowledged_on="2026-11-20", added_on="2026-11-20",
    )


def update_plan(*, name="Acme", files=12, added=(), removed=(), dirty=(), current=False, kicad_open=(), refusal=None):
    entry = entry_of(name)
    return ops.UpdatePlan(
        entry, name, FAKE_COLLECTION / "ThirdParty" / name, OLD, OLD if current else NEW, files, tuple(added),
        tuple(removed), tuple(dirty), current, tuple(kicad_open), refusal,
    )


def dirty_issue(name="Acme"):
    folder = (FAKE_COLLECTION / "ThirdParty" / name).as_posix()
    return Issue(
        Severity.ERROR, "catalog.dirty",
        f"{name} cannot be updated: files in {folder} were changed after it was added. Catalog libraries are managed "
        "copies, and an update would overwrite your changes. Keep your own changes in Custom/ instead.",
    )


def remove_plan(*, name="Acme", exists=True, size=69_000_000, nicknames=(), vars=(), listed=True, kicad_open=()):
    return ops.RemovePlan(
        name, name, FAKE_COLLECTION / "ThirdParty" / name, exists, size, tuple(nicknames), tuple(vars), listed,
        tuple(kicad_open),
    )


def texts(page):
    return [label.text() for label in page.findChildren(QLabel)]


def build(qtbot, page):
    qtbot.addWidget(page)
    return page


# -- The Update preview --------------------------------------------------------------------------


def test_update_preview_page(qtbot):
    page = build(qtbot, cp.UpdatePreviewPage())
    page.show_plan(update_plan(files=12, added=("New_A", "New_B"), removed=("Old_A",), kicad_open=("kicad.exe",)))
    assert page.heading_text() == "Update Acme"
    shown = texts(page)
    assert "1234567  ->  7654321" in shown  # 7-character ids, two spaces around the arrow
    assert "12 files" in shown
    version = next(label for label in page.findChildren(QLabel) if label.text() == "1234567  ->  7654321")
    assert version.font().family() == theme.MONO_FAMILY
    added, removed = page.added_list(), page.removed_list()
    assert added.heading_text() == "Libraries added (2)" and added.row_count() == 2 and added.is_expanded()
    assert removed.heading_text() == "Libraries removed (1)" and removed.row_count() == 1
    item = removed.tree().topLevelItem(0)
    assert item.text(0) == "⚠ Old_A" and item.foreground(0).color().name().upper() == theme.AMBER.upper()
    assert "Projects that use a removed library lose those parts." in shown
    assert "⚠ KiCad is open (kicad.exe). Restart it after the library is updated to see the changes." in shown
    assert page.back_button().text() == "Keep Current Version"
    assert page.back_button().toolTip() == "Do not update. Nothing changes."
    assert page.primary_button().text() == "Update Library" and page.primary_button().isEnabled()
    page.show()
    assert page.primary_button().isVisibleTo(page)
    assert page.primary_button().styleSheet() == theme.PRIMARY_BUTTON_QSS


def test_update_preview_none_when_zero_and_collapse_above_three(qtbot):
    page = build(qtbot, cp.UpdatePreviewPage())
    page.show_plan(update_plan(added=(), removed=()))
    assert page.added_list() is None and page.removed_list() is None
    shown = texts(page)
    assert shown.count("None") == 2
    assert "Libraries added (0)" in shown and "Libraries removed (0)" in shown
    assert "Projects that use a removed library lose those parts." not in shown
    page.show_plan(update_plan(added=("A", "B", "C"), removed=("D", "E", "F", "G")))
    assert page.added_list().is_expanded()  # three rows are always shown
    removed = page.removed_list()
    assert removed.heading_text() == "Libraries removed (4)" and not removed.is_expanded()
    assert not removed.toggle().isHidden() and removed.toggle().text() == "Show"
    removed.toggle().setChecked(True)
    assert removed.is_expanded()
    assert "None" not in texts(page)


def test_update_current_and_dirty_variants(qtbot):
    page = build(qtbot, cp.UpdatePreviewPage())
    page.show_current("Acme")
    assert "✓ Acme is already up to date." in texts(page)
    assert page.back_button().text() == "Back to List" and page.primary_button().isHidden()
    assert page.dirty_list() is None

    dirty = tuple(f"symbols/file_{n}.kicad_sym" for n in range(11))
    page.show_dirty(update_plan(name="Acme", dirty=dirty, refusal=dirty_issue()))
    shown = texts(page)
    assert "✖ " + dirty_issue().text in shown
    rows = page.dirty_list()
    assert rows.row_count() == 8 and rows.tree().topLevelItem(0).text(0) == "symbols/file_0.kicad_sym"
    assert rows.tree().font().family() == theme.MONO_FAMILY
    assert "and 3 more" in shown
    assert page.back_button().text() == "Back to List" and page.primary_button().isHidden()
    page.show_dirty(update_plan(name="Acme", dirty=dirty[:8], refusal=dirty_issue()))
    assert page.dirty_list().row_count() == 8 and not any(text.startswith("and ") for text in texts(page))
    page.show_current("Other")
    assert page.dirty_list() is None  # nothing of the earlier variant stays


def test_update_refusal_and_notice(qtbot):
    page = build(qtbot, cp.UpdatePreviewPage())
    page.show_refusal(Issue(Severity.ERROR, "git.unreachable", "GitHub could not be reached."), heading="Update Acme")
    assert "✖ GitHub could not be reached." in texts(page) and page.heading_text() == "Update Acme"
    assert page.back_button().text() == "Back to List" and page.primary_button().isHidden()
    page.show_plan(update_plan(added=("A",)))
    page.show_notice("Could not write the record.")
    assert "✖ Could not write the record." in texts(page)
    assert page.primary_button().text() == "Update Library" and page.back_button().text() == "Keep Current Version"


def test_update_lists_overflow(qtbot):
    page = build(qtbot, cp.UpdatePreviewPage())
    page.resize(560, 700)
    page.show()
    qtbot.waitExposed(page)
    page.show_plan(
        update_plan(files=900, added=tuple(f"Added_{n:02d}" for n in range(40)), removed=tuple(f"Removed_{n:02d}" for n in range(25)))
    )
    added, removed = page.added_list(), page.removed_list()
    assert added.row_count() == 40 and removed.row_count() == 25
    assert not added.is_expanded() and not removed.is_expanded()  # collapsed behind Show above 3
    for lst in (added, removed):
        lst.toggle().setChecked(True)
        assert lst.is_expanded()
        row_height = lst.tree().sizeHintForRow(0)
        assert lst.tree().height() <= 6 * row_height + 2 * lst.tree().frameWidth() + 4  # at most 6 rows tall, then it scrolls
        qtbot.waitUntil(lambda: lst.tree().verticalScrollBar().maximum() > 0, timeout=2000)
    assert page.primary_button().isVisibleTo(page) and page.back_button().isVisibleTo(page)


# -- The Remove confirmation ---------------------------------------------------------------------


def test_remove_page(qtbot):
    page = build(qtbot, cp.RemovePage())
    page.show_plan(remove_plan(name="Acme", nicknames=("A", "B", "C", "D"), vars=("ACME_3D", "ACME_DIR"), kicad_open=("kicad.exe",)))
    assert page.heading_text() == "Remove Acme?"
    folder = (FAKE_COLLECTION / "ThirdParty" / "Acme").as_posix()
    shown = texts(page)
    assert page.line_text() == f"This deletes the folder {folder} (69 MB on disk) and removes Acme from the catalog."
    assert "This deletes the folder" in shown and "(69 MB on disk) and removes Acme from the catalog." in shown
    lst = page.nickname_list()
    assert lst.heading_text() == "Libraries that leave your scan (4)" and lst.row_count() == 4 and not lst.is_expanded()
    assert "The next Generate Tables drops them from your KiCad library tables." in shown
    assert "Path variables it used" in shown and "ACME_3D" in shown and "ACME_DIR" in shown
    mono = next(label for label in page.findChildren(QLabel) if label.text() == "ACME_3D")
    assert mono.font().family() == theme.MONO_FAMILY
    assert "They stay set in KiCad. Projects that still use this library's 3D models lose them." in shown
    assert "⚠ KiCad is open (kicad.exe). Restart it after the library is removed to see the changes." in shown
    folder_label = page.folder_label()
    assert isinstance(folder_label, ElidedLabel) and folder_label.toolTip() == folder

    keep, remove = page.back_button(), page.primary_button()
    assert keep.text() == "Keep Library" and keep.isDefault() and keep.autoDefault()
    assert remove.text() == "Remove Library" and not remove.isDefault() and not remove.autoDefault()
    assert remove.styleSheet() == cp.destructive_button_qss() and remove.styleSheet() != theme.PRIMARY_BUTTON_QSS
    assert not page.primary_accepts_ctrl_return()
    assert not [b for b in page.findChildren(QPushButton) if b.styleSheet() == theme.PRIMARY_BUTTON_QSS]


def test_remove_page_variants(qtbot):
    page = build(qtbot, cp.RemovePage())
    page.show_plan(remove_plan(name="Acme", exists=False, size=0))
    shown = texts(page)
    assert page.line_text() == "The folder is already gone, so only the catalog entry is removed."
    assert "The folder is already gone, so only the catalog entry is removed." in shown
    assert "This deletes the folder" not in shown and page.folder_label() is None
    assert page.nickname_list() is None and "Path variables it used" not in shown
    assert not any("KiCad is open" in text for text in shown)
    page.show_plan(remove_plan(name="Stray", listed=False, nicknames=("S",)))
    folder = (FAKE_COLLECTION / "ThirdParty" / "Stray").as_posix()
    assert page.line_text() == f"This deletes the folder {folder} (69 MB on disk)."  # not in the catalog: nothing to remove from it
    assert page.nickname_list().is_expanded() and page.nickname_list().row_count() == 1
    page.show_plan(remove_plan(name="Big", size=2_400_000_000))
    assert "(2.4 GB on disk) and removes Big from the catalog." in texts(page)


def test_remove_page_long_names(qtbot):
    page = build(qtbot, cp.RemovePage())
    page.resize(520, 600)
    page.show()
    qtbot.waitExposed(page)
    long_name = "A" * 90 + "/" + "B" * 90
    page.show_plan(remove_plan(name=long_name, nicknames=(("N" * 120),)))
    assert page.heading_text() == f"Remove {long_name}?"
    assert page.findChildren(QLabel)[0].wordWrap()  # the heading wraps
    assert page.folder_label().toolTip().endswith(long_name)
    assert page.nickname_list().tree().topLevelItem(0).toolTip(0) == "N" * 120
    assert page.width() == 520  # nothing widened the page


def test_remove_page_failure_and_focus(qtbot):
    page = build(qtbot, cp.RemovePage())
    page.show_plan(remove_plan())
    page.show_refusal(
        Issue(Severity.ERROR, "catalog.remove_failed", "Could not remove Acme: a file is in use. Close anything that uses files in x, then try again. The catalog entry was kept.")
    )
    assert any(text.startswith("✖ Could not remove Acme") for text in texts(page))
    assert page.back_button().text() == "Back to List" and page.primary_button().isHidden()
    page.show_plan(remove_plan())  # a fresh plan restores the confirmation
    page.show()
    qtbot.waitExposed(page)
    assert page.back_button().text() == "Keep Library" and page.primary_button().isVisibleTo(page)
    page.focus_first()
    assert page.focusWidget() is page.back_button()  # focus never lands on the destructive button
