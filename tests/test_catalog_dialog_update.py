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


# ══ The window ══════════════════════════════════════════════════════════════════════════════════════
# Fake catalog services record their calls; gates let a test hold a job in the middle.

import threading  # noqa: E402
import time  # noqa: E402
from dataclasses import replace  # noqa: E402
from datetime import datetime  # noqa: E402

from catalogfixtures import make_third_party  # noqa: E402
from collectionfixtures import make_collection  # noqa: E402
from PySide6.QtWidgets import QMenu, QMessageBox  # noqa: E402

from kicad_lib_manager.catalog import curated, manifest  # noqa: E402
from kicad_lib_manager.catalog.manifest import Manifest  # noqa: E402
from kicad_lib_manager.catalog.ops import NetStatus  # noqa: E402
from kicad_lib_manager.catalog.status import Check, UpdateState  # noqa: E402
from kicad_lib_manager.models import FootprintLibrary, ScanResult, SymbolLibrary  # noqa: E402
from kicad_lib_manager.widgets import catalog_dialog as cd  # noqa: E402

SHA = "a" * 40
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")
THIRD = replace(SPARKFUN, id="ThirdOne", name="Third One", url="https://github.com/x/third.git")
NET_OK = NetStatus(object(), (2, 50, 0), None, None)
NOW = datetime(2026, 11, 27, 12, 0, 0)


class Usage:
    def __init__(self, free):
        self.free = free


class Fakes:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.look_calls: list[str] = []
        self.apply_calls: list = []
        self.remove_plan_calls: list = []
        self.remove_calls: list = []
        self.look_started, self.look_release = threading.Event(), threading.Event()
        self.apply_started, self.apply_release = threading.Event(), threading.Event()
        self.remove_started, self.remove_release = threading.Event(), threading.Event()
        for gate in (self.look_release, self.apply_release, self.remove_release):
            gate.set()
        self.plan = None  # what plan_update answers (an UpdatePlan or an Issue)
        self.apply_issues: list[Issue] | None = None
        self.remove_issues: list[Issue] | None = None  # None: the real ops.apply_remove runs

    def release_all(self):
        for gate in (self.look_release, self.apply_release, self.remove_release):
            gate.set()

    def plan_update(self, root, entry, net, *, progress=None, cancel=None, running=None):
        self.look_calls.append(entry.id)
        self.look_started.set()
        while not self.look_release.is_set():
            if cancel is not None and cancel.is_set():
                return Issue(Severity.INFO, "git.cancelled", "Stopped.")
            time.sleep(0.005)
        if cancel is not None and cancel.is_set():
            return Issue(Severity.INFO, "git.cancelled", "Stopped.")
        if self.plan is not None:
            return self.plan
        return update_plan(name=entry.id, added=("New_A", "New_B"), removed=("Old_A",))

    def apply_update(self, root, plan, net, *, cancel=None):
        self.apply_calls.append(plan)
        self.apply_started.set()
        while not self.apply_release.is_set():
            if cancel is not None and cancel.is_set():
                break
            time.sleep(0.005)
        if cancel is not None and cancel.is_set():
            return [Issue(Severity.INFO, "git.cancelled", "Stopped.")]
        if self.apply_issues is not None:
            return list(self.apply_issues)
        text = f"Updated {plan.name} to {plan.new[:7]}: {len(plan.added)} libraries added, {len(plan.removed)} removed."
        issues = [Issue(Severity.SUCCESS, "catalog.updated", text)]
        if plan.removed:
            issues.append(Issue(
                Severity.WARNING, "catalog.update_removed",
                f"Update of {plan.name} removed {len(plan.removed)} libraries: {', '.join(plan.removed)}. "
                "Projects that use them lose those parts.",
            ))
        return issues

    def plan_remove(self, root, target_id, mf, *, scan=None, running=None):
        self.remove_plan_calls.append((target_id, scan))
        return ops.plan_remove(root, target_id, mf, scan=scan, running=running)

    def apply_remove(self, root, plan, *, allow_file=False):
        self.remove_calls.append(plan)
        self.remove_started.set()
        while not self.remove_release.is_set():
            time.sleep(0.005)
        if self.remove_issues is not None:
            return list(self.remove_issues)
        return ops.apply_remove(root, plan)


@pytest.fixture
def fakes(tmp_path):
    fake = Fakes(tmp_path)
    yield fake
    fake.release_all()


def services(fakes, **overrides):
    base = dict(
        curated=(SPARKFUN, WURTH, THIRD),
        net_status=lambda root: NET_OK,
        clean_staging=lambda root: [],
        current_path_vars=lambda **kw: {},
        size_on_disk=lambda folder: 69_000_000,
        kicad_running=lambda: [],
        free_space=lambda root: Usage(10**13),
        plan_update=fakes.plan_update,
        apply_update=fakes.apply_update,
        plan_remove=fakes.plan_remove,
        apply_remove=fakes.apply_remove,
    )
    base.update(overrides)
    return replace(cd.CatalogServices(), **base)


def listed(id, *, vars=None, spdx="CC-BY-4.0"):
    return CatalogEntry(
        id=id, url=f"https://github.com/acme/{id.lower()}.git", branch="main", commit=SHA, vars=dict(vars or {}),
        licence_spdx=spdx, acknowledged=True, acknowledged_on="2026-11-20", added_on="2026-11-20",
    )


def build_window(qtbot, tmp_path, fakes, *, entries=(), folders=(), **overrides):
    root = make_collection(tmp_path / "col")
    for id in folders:
        make_third_party(root, id, {"a.kicad_sym": "(kicad_symbol_lib)"})
    if entries:
        assert manifest.save(root, Manifest(tuple(entries))) is None
    dialog = cd.CatalogDialog(root, services=services(fakes, **overrides), show_guide=lambda topic: None, clock=lambda: NOW)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    qtbot.waitUntil(lambda: bool(dialog._net_status is not None and dialog._vars_read), timeout=10000)
    return dialog


def record(dialog):
    logs, outcomes = [], []
    dialog.log_line.connect(lambda text, level: logs.append((level, text)))
    dialog.job_finished.connect(outcomes.append)
    return logs, outcomes


def by_name(dialog):
    tree = dialog._tree
    return {tree.topLevelItem(i).text(0): tree.topLevelItem(i) for i in range(tree.topLevelItemCount())}


def select(dialog, name):
    item = by_name(dialog)[name]
    dialog._tree.setCurrentItem(item)
    item.setSelected(True)
    return item


def idle(dialog):
    return not dialog.is_job_running()


def available(dialog, id="SparkFun", sha=NEW):
    dialog.apply_update_states({id: UpdateState(id, Check.AVAILABLE, sha, NOW)})


def current(dialog, id="SparkFun"):
    dialog.apply_update_states({id: UpdateState(id, Check.CURRENT, SHA, NOW)})


def shown(dialog, button):
    return button.isVisibleTo(dialog._details_page)


def accent(dialog):
    return [
        b for b in dialog.findChildren(QPushButton) if b.styleSheet() == theme.PRIMARY_BUTTON_QSS and b.isVisibleTo(dialog)
    ]


def answer(monkeypatch, choice):
    seen = []

    def fake_exec(self):
        seen.append(self)
        for button in self.buttons():
            if button.text() == choice:
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return seen


def start_update(qtbot, dialog):
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "update"), timeout=10000)


def start_remove(qtbot, dialog):
    dialog._remove_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "remove"), timeout=10000)


# -- The Details buttons per status --------------------------------------------------------------


def test_details_buttons_per_state(qtbot, tmp_path, fakes):
    dialog = build_window(
        qtbot, tmp_path, fakes, entries=(listed("SparkFun"), listed("ThirdOne")), folders=("SparkFun", "Stray"),
    )

    def buttons():
        every = (dialog._vars_btn, dialog._remove_btn, dialog._update_btn, dialog._add_btn, dialog._reinstall_btn)
        return [b for b in every if shown(dialog, b)]

    select(dialog, next(name for name in by_name(dialog) if name.startswith("W")))  # not installed
    assert buttons() == [dialog._add_btn] and accent(dialog) == [dialog._add_btn]

    select(dialog, "SparkFun")  # installed, updates not checked
    assert buttons() == [dialog._remove_btn, dialog._update_btn]
    assert dialog._update_btn.text() == "Update This Library" and not dialog._update_btn.isEnabled()
    assert dialog._update_btn.toolTip() == "No update is known. Press Check for Updates."
    assert dialog._remove_btn.text() == "Remove This Library" and dialog._remove_btn.isEnabled()
    assert dialog._remove_btn.styleSheet() == "" and accent(dialog) == []

    current(dialog)  # installed, confirmed current
    assert buttons() == [dialog._remove_btn, dialog._update_btn]
    assert not dialog._update_btn.isEnabled() and dialog._update_btn.toolTip() == "Already up to date."
    assert accent(dialog) == []

    available(dialog)  # update available
    assert by_name(dialog)["SparkFun"].text(1) == "⚠ Update available"
    assert buttons() == [dialog._remove_btn, dialog._update_btn]
    assert dialog._update_btn.isEnabled() and dialog._update_btn.toolTip() == ""
    assert accent(dialog) == [dialog._update_btn]
    assert dialog._problem_label.text() == f"⚠ A newer version is available ({SHA[:7]} -> {NEW[:7]})."

    select(dialog, "Third One")  # folder missing
    assert buttons() == [dialog._remove_btn, dialog._reinstall_btn] and accent(dialog) == [dialog._reinstall_btn]

    select(dialog, "Stray")  # not in the catalog
    assert buttons() == [dialog._remove_btn] and dialog._remove_btn.isEnabled() and accent(dialog) == []

    # no Update all anywhere: no button, menu or action carries it
    words = [b.text() for b in dialog.findChildren(QPushButton)] + [m.title() for m in dialog.findChildren(QMenu)]
    assert not any("update all" in text.casefold() for text in words)


def test_buttons_follow_the_busy_reasons(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    available(dialog)
    select(dialog, "SparkFun")
    dialog.set_blocked("Wait for the scan in the main window to end.")
    for button in (dialog._update_btn, dialog._remove_btn):
        assert not button.isEnabled() and button.toolTip() == "Wait for the scan in the main window to end."
    dialog.set_blocked(None)
    assert dialog._update_btn.isEnabled() and dialog._remove_btn.isEnabled() and dialog._update_btn.toolTip() == ""
    fakes.look_release.clear()
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(fakes.look_started.is_set()), timeout=10000)
    for button in (dialog._update_btn, dialog._remove_btn):
        assert not button.isEnabled() and button.toolTip() == "Wait for updating SparkFun to finish."
    fakes.look_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "update"), timeout=10000)


# -- Update ---------------------------------------------------------------------------------------


def test_update_flow(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    available(dialog)
    select(dialog, "SparkFun")
    fakes.look_release.clear()
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(fakes.look_started.is_set()), timeout=10000)
    assert dialog._job_label.full_text() == "Looking for changes in SparkFun..." and dialog._job_strip.isVisibleTo(dialog)
    assert dialog._job_bar.maximum() == 0 and dialog._job_bar.accessibleName() == "Progress of updating SparkFun"
    assert dialog._job_cancel.text() == "Cancel Updating" and dialog._job_cancel.isEnabled()
    assert fakes.apply_calls == [] and dialog.is_job_running()
    fakes.look_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "update"), timeout=10000)
    page = dialog._update_page
    assert dialog._pages.currentWidget() is page and idle(dialog) and dialog._job_strip.isHidden()
    assert page.heading_text() == "Update SparkFun" and page.primary_button().text() == "Update Library"
    assert page.back_button().text() == "Keep Current Version"

    page.back_button().click()  # Keep Current Version: nothing changes
    assert dialog._page_kind is None and dialog._pages.currentWidget() is dialog._details_page
    assert fakes.apply_calls == [] and outcomes == []
    assert by_name(dialog)["SparkFun"].text(1) == "⚠ Update available"

    start_update(qtbot, dialog)
    fakes.apply_release.clear()
    dialog._update_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.apply_started.is_set()), timeout=10000)
    assert dialog._job_label.full_text() == "Updating SparkFun..." and dialog._job_cancel.text() == "Cancel Updating"
    assert not dialog._update_page.primary_button().isEnabled() and not dialog._update_page.back_button().isEnabled()
    fakes.apply_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None and idle(dialog)), timeout=10000)
    assert len(fakes.apply_calls) == 1 and fakes.apply_calls[0].new == NEW
    assert by_name(dialog)["SparkFun"].text(1) == "✓ Installed"
    result = [label.text() for label in dialog._result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert result == ["✓ Updated SparkFun to 7654321: 2 libraries added, 1 removed."]
    assert not dialog._result_generate_btn.isHidden()
    assert ("success", "Updated SparkFun to 7654321: 2 libraries added, 1 removed.") in logs
    assert any(level == "warning" and text.startswith("Update of SparkFun removed 1 libraries") for level, text in logs)
    assert len(outcomes) == 1 and outcomes[0].ok
    assert (outcomes[0].kind, outcomes[0].id, outcomes[0].name) == ("update", "SparkFun", "SparkFun")


def test_update_current_dirty_and_refused(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    available(dialog)
    select(dialog, "SparkFun")

    fakes.plan = update_plan(name="SparkFun", current=True)
    start_update(qtbot, dialog)
    assert "✓ SparkFun is already up to date." in texts(dialog._update_page)
    assert dialog._update_page.primary_button().isHidden()
    dialog._update_page.back_button().click()

    dirty = tuple(f"symbols/f{n}.kicad_sym" for n in range(10))
    fakes.plan = update_plan(name="SparkFun", dirty=dirty, refusal=dirty_issue("SparkFun"))
    start_update(qtbot, dialog)
    assert dialog._update_page.dirty_list().row_count() == 8 and "and 2 more" in texts(dialog._update_page)
    assert dialog._update_page.primary_button().isHidden() and dialog._update_page.back_button().text() == "Back to List"
    assert outcomes and not outcomes[-1].ok and fakes.apply_calls == []
    dialog._update_page.back_button().click()

    unreachable = "GitHub could not be reached. Check your internet connection, then try again."
    fakes.plan = Issue(Severity.ERROR, "git.unreachable", unreachable)
    start_update(qtbot, dialog)
    assert "✖ " + unreachable in texts(dialog._update_page)
    assert ("error", "Could not update SparkFun: " + unreachable) in logs
    dialog._update_page.back_button().click()
    assert dialog._page_kind is None and fakes.apply_calls == []


def test_update_cancel_and_close_question(qtbot, tmp_path, fakes, monkeypatch):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    available(dialog)
    select(dialog, "SparkFun")
    fakes.look_release.clear()
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(fakes.look_started.is_set()), timeout=10000)

    seen = answer(monkeypatch, "Keep Working")
    dialog.close()
    box = seen[0]
    assert box.windowTitle() == "Stop the current job?"
    assert box.text() == (
        "Updating SparkFun is still running. If you close the catalog now, it is stopped and the partly downloaded "
        "files are deleted. SparkFun stays on the version it has now."
    )
    assert sorted(b.text() for b in box.buttons()) == ["Keep Working", "Stop and Close"]
    assert dialog.isVisible() and dialog.is_job_running()

    answer(monkeypatch, "Stop and Close")
    dialog.close()
    qtbot.waitUntil(lambda: bool(not dialog.isVisible()), timeout=10000)
    assert idle(dialog) and fakes.apply_calls == []
    assert dialog._page_kind is None and not dialog.holds_download()


def test_update_cancel_button_returns_to_the_details(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    available(dialog)
    select(dialog, "SparkFun")
    fakes.look_release.clear()
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(fakes.look_started.is_set()), timeout=10000)
    dialog._job_cancel.click()
    assert dialog._job_label.full_text() == "Stopping..." and not dialog._job_cancel.isEnabled()
    qtbot.waitUntil(lambda: bool(idle(dialog) and dialog._page_kind is None), timeout=10000)
    assert ("info", "Stopped updating SparkFun. It stays on its current version.") in logs
    assert dialog._pages.currentWidget() is dialog._details_page and fakes.apply_calls == []
    assert len(outcomes) == 1 and not outcomes[0].ok and outcomes[0].kind == "update"


def test_failed_update_logs_error_and_raw_text(qtbot, tmp_path, fakes):
    def boom(root, entry, net, *, progress=None, cancel=None, running=None):
        raise RuntimeError("boom")

    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",), plan_update=boom)
    logs, outcomes = record(dialog)
    available(dialog)
    select(dialog, "SparkFun")
    dialog._update_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "update"), timeout=10000)
    assert ("error", "Library catalog step failed: boom") in logs
    assert any(level == "error" and text.startswith("Could not update SparkFun: ") for level, text in logs)
    assert any(text.startswith("✖ ") for text in texts(dialog._update_page))
    assert dialog._update_page.primary_button().isHidden() and idle(dialog)
    assert len(outcomes) == 1 and not outcomes[0].ok
    dialog._update_page.back_button().click()
    assert dialog._page_kind is None


def test_update_apply_failure_keeps_the_preview(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    available(dialog)
    select(dialog, "SparkFun")
    fakes.apply_issues = [dirty_issue("SparkFun")]
    start_update(qtbot, dialog)
    dialog._update_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(len(fakes.apply_calls) == 1 and idle(dialog)), timeout=10000)
    assert dialog._page_kind == "update" and dialog._update_page.primary_button().text() == "Update Library"
    assert ("✖ " + dirty_issue("SparkFun").text) in texts(dialog._update_page)
    assert any(level == "error" for level, _ in logs) and by_name(dialog)["SparkFun"].text(1) == "⚠ Update available"
    assert outcomes == []  # the preview is still open; nothing ended


# -- Remove ---------------------------------------------------------------------------------------


def test_remove_flow(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    select(dialog, "SparkFun")
    folder = Path(dialog._root) / "ThirdParty" / "SparkFun"
    start_remove(qtbot, dialog)
    page = dialog._remove_page
    assert dialog._pages.currentWidget() is page and page.heading_text() == "Remove SparkFun?"
    assert page.back_button().isDefault() and not dialog._close_btn.isDefault()
    assert not page.primary_button().isDefault() and folder.is_dir()
    assert fakes.remove_calls == []

    fakes.remove_release.clear()
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.remove_started.is_set()), timeout=10000)
    assert dialog._job_label.full_text() == "Removing SparkFun..." and dialog._job_bar.maximum() == 0
    assert dialog._job_cancel.text() == "Cancel Removing" and not dialog._job_cancel.isEnabled()
    assert dialog._job_cancel.toolTip() == "Removing cannot be stopped halfway. It ends in a moment."
    dialog.close()  # ignored for as long as the Remove runs
    assert dialog.isVisible()
    assert dialog._job_label.full_text() == "Removing cannot be stopped halfway. Close this window after it ends."
    fakes.remove_release.set()
    qtbot.waitUntil(lambda: bool(idle(dialog) and dialog._page_kind is None), timeout=10000)

    assert not folder.exists() and manifest.load(dialog._root).find("SparkFun") is None
    assert by_name(dialog)["SparkFun"].text(1) == "Not installed"  # a curated row returns
    assert dialog.selected_id() == "SparkFun" and dialog._pages.currentWidget() is dialog._details_page
    result = [label.text() for label in dialog._result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert result == ["✓ Removed SparkFun. Press Generate Tables to drop its libraries from your KiCad library tables."]
    assert not dialog._result_generate_btn.isHidden()
    done = "Removed SparkFun from the catalog. Generate Tables drops its libraries from your KiCad library tables."
    assert ("success", done) in logs
    assert len(outcomes) == 1 and outcomes[0].ok
    assert (outcomes[0].kind, outcomes[0].id, outcomes[0].name) == ("remove", "SparkFun", "SparkFun")


def test_remove_keep_library_and_escape_never_delete(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    select(dialog, "SparkFun")
    folder = Path(dialog._root) / "ThirdParty" / "SparkFun"
    start_remove(qtbot, dialog)
    qtbot.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)  # Ctrl+Return never confirms
    qtbot.keyClick(dialog._remove_page.primary_button(), Qt.Key.Key_Return)  # nor does Enter on the destructive button
    assert fakes.remove_calls == [] and folder.is_dir()
    if dialog._page_kind is None:  # Enter reached Keep Library, the default button: back to the list
        start_remove(qtbot, dialog)
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)  # Esc is Keep Library
    assert dialog._page_kind is None and fakes.remove_calls == [] and folder.is_dir()
    start_remove(qtbot, dialog)
    dialog._remove_page.back_button().click()
    assert dialog._page_kind is None and fakes.remove_calls == [] and folder.is_dir()
    assert dialog._close_btn.isDefault()  # Close is the default again on the list view


def test_failed_remove_keeps_the_entry(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    logs, outcomes = record(dialog)
    select(dialog, "SparkFun")
    folder = Path(dialog._root) / "ThirdParty" / "SparkFun"
    reason = (
        f"Could not remove SparkFun: a file is in use. Close anything that uses files in {folder.as_posix()}, "
        "then try again. The catalog entry was kept."
    )
    fakes.remove_issues = [Issue(Severity.ERROR, "catalog.remove_failed", reason)]
    start_remove(qtbot, dialog)
    dialog._remove_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(len(fakes.remove_calls) == 1 and idle(dialog)), timeout=10000)
    page = dialog._remove_page
    assert dialog._page_kind == "remove" and ("✖ " + reason) in texts(page)
    assert page.back_button().text() == "Back to List" and page.primary_button().isHidden()
    assert ("error", reason) in logs
    assert folder.is_dir() and manifest.load(dialog._root).find("SparkFun") is not None
    assert by_name(dialog)["SparkFun"].text(1) == "Installed"  # the row is as it was
    assert len(outcomes) == 1 and not outcomes[0].ok and outcomes[0].kind == "remove"
    page.back_button().click()
    assert dialog._page_kind is None and dialog._pages.currentWidget() is dialog._details_page
    assert dialog._result_strip.isHidden()


def test_remove_not_in_catalog_folder(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(), folders=("Stray",))
    logs, outcomes = record(dialog)
    select(dialog, "Stray")
    assert by_name(dialog)["Stray"].text(1) == "⚠ Problem: not in the catalog"
    folder = Path(dialog._root) / "ThirdParty" / "Stray"
    start_remove(qtbot, dialog)
    line = dialog._remove_page.line_text()
    assert line.startswith(f"This deletes the folder {folder.as_posix()} (") and line.endswith(" on disk).")
    dialog._remove_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(idle(dialog) and dialog._page_kind is None), timeout=10000)
    assert not folder.exists() and "Stray" not in by_name(dialog)  # the row disappears
    assert dialog._pages.currentWidget() is dialog._empty_page
    assert dialog._gone_result_strip.isVisibleTo(dialog._empty_page)
    gone = [label.text() for label in dialog._gone_result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert gone == ["✓ Removed Stray. Press Generate Tables to drop its libraries from your KiCad library tables."]
    assert len(outcomes) == 1 and outcomes[0].ok and outcomes[0].kind == "remove" and outcomes[0].id == "Stray"
    select(dialog, "SparkFun")  # another row: the line goes
    assert dialog._gone_result_strip.isHidden()


def test_remove_lists_the_scan_libraries(qtbot, tmp_path, fakes):
    dialog = build_window(qtbot, tmp_path, fakes, entries=(listed("SparkFun"),), folders=("SparkFun",))
    scan = ScanResult(
        symbol_libs=[SymbolLibrary("Spark_A", "ThirdParty/SparkFun/a.kicad_sym", "SparkFun")],
        footprint_libs=[FootprintLibrary("Spark_F", "ThirdParty/SparkFun/f.pretty", "SparkFun")],
    )
    dialog.set_scan(scan)
    select(dialog, "SparkFun")
    start_remove(qtbot, dialog)
    assert fakes.remove_plan_calls[0][0] == "SparkFun" and fakes.remove_plan_calls[0][1] is scan
    assert dialog._remove_page.nickname_list().row_count() == 2
    dialog._remove_page.back_button().click()


# -- Set Path Variables... ------------------------------------------------------------------------


def test_set_path_variables_button(qtbot, tmp_path, fakes):
    wanted = {"SPARKFUN_KICAD_LIBRARY": ""}
    kicad = {}
    dialog = build_window(
        qtbot, tmp_path, fakes, entries=(listed("SparkFun", vars=wanted), listed("ThirdOne")), folders=("SparkFun",),
        current_path_vars=lambda **kw: dict(kicad),
    )
    asked = []
    dialog.path_vars_requested.connect(asked.append)
    select(dialog, "SparkFun")
    assert shown(dialog, dialog._vars_btn) and dialog._vars_btn.text() == "Set Path Variables..."  # not set
    assert dialog._vars_btn.styleSheet() == "" and dialog._vars_btn.isEnabled()
    assert dialog._button_row.indexOf(dialog._vars_btn) < dialog._button_row.indexOf(dialog._remove_btn)
    dialog._vars_btn.click()
    assert asked == ["SparkFun"]
    dialog.set_blocked("Close the import window first.")
    assert not dialog._vars_btn.isEnabled() and dialog._vars_btn.toolTip() == "Close the import window first."
    dialog.set_blocked(None)

    expected = manifest.path_vars(dialog._root, [listed("SparkFun", vars=wanted)])
    kicad.update(expected)  # set to this library's folder
    dialog._start_background(reset=False)
    qtbot.waitUntil(lambda: bool(dialog._kicad_vars == expected), timeout=10000)
    assert not shown(dialog, dialog._vars_btn)

    kicad["SPARKFUN_KICAD_LIBRARY"] = "C:/elsewhere"  # set to a different folder
    dialog._start_background(reset=False)
    qtbot.waitUntil(lambda: bool(dialog._kicad_vars == kicad), timeout=10000)
    assert shown(dialog, dialog._vars_btn)
    select(dialog, "Third One")  # not installed on disk: never offered
    assert not shown(dialog, dialog._vars_btn)
