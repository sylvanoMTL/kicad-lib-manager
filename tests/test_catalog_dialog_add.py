"""The Add, Add by URL and Reinstall flows of the library catalog window (Phase 17 plan 13; CAT-02, CAT-03, CAT-08, CAT-09, D-04, D-05, D-10, D-13..D-16, D-18, D-20, D-23).

Every test builds the window with fake catalog services (plan_add and the others are the real pure functions
where they need no network; stage_add, register_add, discard_staging and check_repository are fakes that record
their calls and wait on gates the test controls): no git process, no network, no window on the desktop.
"""

import threading
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from kicad_lib_manager.catalog import curated, manifest, ops, validate
from kicad_lib_manager.catalog.githubapi import RepoInfo
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.catalog.ops import NetStatus
from kicad_lib_manager.catalog.urls import RepoRef
from kicad_lib_manager.models import FootprintLibrary, Issue, ScanResult, Severity, SymbolLibrary
from kicad_lib_manager.widgets import catalog_dialog as cd
from kicad_lib_manager.widgets import theme

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
    """The catalog functions the window calls, recording every call; the gates let a test hold a job in the middle."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.stage_calls: list[SimpleNamespace] = []
        self.register_calls: list[SimpleNamespace] = []
        self.discard_calls: list = []
        self.check_calls: list[str] = []
        self.plan_calls = 0
        self.progress = [("Receiving objects", 10), ("Receiving objects", 42)]
        self.stage_started = threading.Event()
        self.stage_release = threading.Event()
        self.stage_release.set()
        self.register_started = threading.Event()
        self.register_release = threading.Event()
        self.register_release.set()
        self.check_started = threading.Event()
        self.check_release = threading.Event()
        self.check_release.set()
        self.stage_issue: Issue | None = None
        self.stage_issues: list[Issue] = []  # answered one per call before the normal result
        self.collisions: tuple = ()
        self.licence_text: str | None = None
        self.vars: dict | None = None
        self.symbols = ("Acme_A", "Acme_B")
        self.footprints = ("Acme_F",)
        self.register_issues: list[Issue] | None = None
        self.checks: dict[str, object] = {}
        self.discard_issue: Issue | None = None
        self.stock_fp = frozenset({"Device"})
        self.stock_sym = frozenset({"Device"})
        self.stock_dirs: list = []

    def release_all(self):
        for gate in (self.stage_release, self.register_release, self.check_release):
            gate.set()

    # -- the fake functions --

    def plan_add(self, root, source, mf, *, free_space, running):
        self.plan_calls += 1
        return ops.plan_add(root, source, mf, free_space=free_space, running=running)

    def plan_reinstall(self, root, entry, mf, *, free_space, running):
        self.plan_calls += 1
        return ops.plan_reinstall(root, entry, mf, free_space=free_space, running=running)

    def check_repository(self, root, text, mf, net, *, repo_info=None, cancel=None):
        self.check_calls.append(text)
        self.check_started.set()
        while not self.check_release.is_set():
            if cancel is not None and cancel.is_set():
                return Issue(Severity.INFO, "git.cancelled", "Stopped.")
            time.sleep(0.005)
        return self.checks.get(text, Issue(Severity.ERROR, "catalog.bad_url", "Only web addresses that start with https://github.com/ can be added."))

    def stage_add(self, root, plan, net, *, progress=None, cancel=None, stock_fp=frozenset(), stock_sym=frozenset(),
                  own=None, other_catalog=None, free_space=None):
        self.stage_calls.append(SimpleNamespace(plan=plan, stock_fp=stock_fp, stock_sym=stock_sym, own=own, other=other_catalog))
        for text, percent in self.progress:
            progress(text, percent)
        self.stage_started.set()
        while not self.stage_release.is_set():
            if cancel.is_set():
                break
            time.sleep(0.005)
        if cancel.is_set():
            return self.staged(plan)  # a download that finished just as the user pressed Cancel
        if self.stage_issues:
            return self.stage_issues.pop(0)
        if self.stage_issue is not None:
            return self.stage_issue
        return self.staged(plan)

    def staged(self, plan):
        report = validate.StagingReport(self.symbols, self.footprints, tuple(self.collisions), {}, 0, self.licence_text, ())
        variables = dict(plan.source.vars) if self.vars is None else dict(self.vars)
        return ops.Staged(plan.source, self.tmp / "staging" / plan.source.id, SHA, report, (), plan, variables)

    def discard_staging(self, staged):
        self.discard_calls.append(staged)
        return self.discard_issue

    def register_add(self, root, staged, *, acknowledged=False, today=None, allow_file=False):
        self.register_calls.append(SimpleNamespace(staged=staged, acknowledged=acknowledged, today=today))
        self.register_started.set()
        while not self.register_release.is_set():
            time.sleep(0.005)
        if self.register_issues is not None:
            return list(self.register_issues)
        source, plan = staged.source, staged.plan
        make_third_party(root, source.id, {"a.kicad_sym": "(kicad_symbol_lib)"})
        current = manifest.load(root)
        previous = current.find(source.id)
        entry = CatalogEntry(
            source.id, source.url, source.branch, staged.commit, dict(staged.vars or {}), source.licence_spdx,
            acknowledged=acknowledged or (previous is not None and previous.acknowledged),
            acknowledged_on=today or "", added_on=today or "",
        )
        assert manifest.save(root, current.with_entry(entry)) is None
        counts = f"{len(staged.report.symbol_libs)} symbol libraries, {len(staged.report.footprint_libs)} footprint libraries"
        verb = "Reinstalled" if plan.reinstall else "Added"
        tail = "" if plan.reinstall else " to the catalog"
        return [Issue(Severity.SUCCESS, "catalog.added", f"{verb} {plan.name}{tail}: {counts}.")]

    def stock(self, fp_dir=None):
        self.stock_dirs.append(fp_dir)
        return self.stock_fp


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
        plan_add=fakes.plan_add,
        plan_reinstall=fakes.plan_reinstall,
        check_repository=fakes.check_repository,
        stage_add=fakes.stage_add,
        register_add=fakes.register_add,
        discard_staging=fakes.discard_staging,
        stock_fp=fakes.stock,
        stock_sym=lambda fp_dir=None: fakes.stock_sym,
    )
    base.update(overrides)
    return replace(cd.CatalogServices(), **base)


def entry(id, *, commit=SHA, spdx="CC-BY-4.0", ack=True, ack_on="2026-11-20"):
    return CatalogEntry(
        id=id, url=f"https://github.com/acme/{id.lower()}.git", branch="main", commit=commit, vars={},
        licence_spdx=spdx, acknowledged=ack, acknowledged_on=ack_on, added_on="2026-11-20",
    )


def build(qtbot, tmp_path, fakes, *, entries=(), folders=(), **overrides):
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
    logs, outcomes, busy = [], [], []
    dialog.log_line.connect(lambda text, level: logs.append((level, text)))
    dialog.job_finished.connect(outcomes.append)
    dialog.busy_changed.connect(lambda: busy.append((dialog.is_job_running(), dialog.holds_download())))
    return logs, outcomes, busy


def by_name(dialog):
    tree = dialog._tree
    return {tree.topLevelItem(i).text(0): tree.topLevelItem(i) for i in range(tree.topLevelItemCount())}


def select(dialog, name):
    item = by_name(dialog)[name]
    dialog._tree.setCurrentItem(item)
    item.setSelected(True)
    return item


def texts(widget):
    return [label.text() for label in widget.findChildren(QLabel)]


def open_licence(qtbot, dialog, name="SparkFun"):
    select(dialog, name)
    button = dialog._reinstall_btn if by_name(dialog)[name].text(1).startswith("✖") else dialog._add_btn
    button.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)


def to_preview(qtbot, dialog, fakes, name="SparkFun"):
    open_licence(qtbot, dialog, name)
    page = dialog._licence_page
    if page.tick() is not None:
        page.tick().setChecked(True)
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)


def idle(dialog):
    return not dialog.is_job_running()


# -- Add a curated library -----------------------------------------------------------------------


def test_curated_add_three_presses(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, busy = record(dialog)
    fakes.stage_release.clear()
    select(dialog, "SparkFun")
    assert dialog._add_btn.text() == "Add This Library" and not dialog._add_btn.isHidden()
    assert dialog._reinstall_btn.isHidden()
    dialog._add_btn.click()  # press 1: the licence page, nothing is written
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    assert dialog._licence_page.heading_text() == "Add SparkFun"
    assert fakes.stage_calls == [] and not (Path(dialog._root) / "ThirdParty" / "SparkFun").exists()
    assert dialog._pages.currentWidget() is dialog._licence_page

    dialog._licence_page.primary_button().click()  # press 2: the download
    qtbot.waitUntil(lambda: bool(dialog._job_label.full_text() == "Downloading SparkFun... 42%"), timeout=10000)
    assert dialog._job_strip.isVisibleTo(dialog) and dialog.is_job_running()
    assert (dialog._job_bar.minimum(), dialog._job_bar.maximum(), dialog._job_bar.value()) == (0, 100, 42)
    assert dialog._job_bar.width() == 240 and dialog._job_bar.accessibleName() == "Progress of adding SparkFun"
    assert dialog._job_cancel.text() == "Cancel Adding" and dialog._job_cancel.isEnabled()
    assert dialog._job_cancel.toolTip() == "Stop adding SparkFun and delete what it downloaded. Nothing is changed."
    assert not dialog._licence_page.primary_button().isEnabled() and not dialog._licence_page.back_button().isEnabled()
    assert fakes.stage_calls[0].stock_fp == frozenset({"Device"}) and fakes.stage_calls[0].stock_sym == frozenset({"Device"})
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    assert dialog.holds_download() and idle(dialog) and dialog._job_strip.isHidden()
    preview = dialog._preview_page
    assert preview.heading_text() == "Add SparkFun" and preview.primary_button().text() == "Add Library"
    assert "✓ Downloaded and checked: 2 symbol libraries and 1 footprint libraries." in texts(preview)
    assert not (Path(dialog._root) / "ThirdParty" / "SparkFun").exists()  # nothing yet: the preview is the last stop
    assert fakes.register_calls == []

    fakes.register_release.clear()
    preview.primary_button().click()  # press 3: Add Library
    qtbot.waitUntil(lambda: bool(fakes.register_started.is_set()), timeout=10000)
    assert dialog._job_label.full_text() == "Adding SparkFun..." and dialog._job_bar.maximum() == 0
    assert not preview.primary_button().isEnabled() and not preview.back_button().isEnabled()
    fakes.register_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None and idle(dialog)), timeout=10000)

    assert dialog._pages.currentWidget() is dialog._details_page
    assert by_name(dialog)["SparkFun"].text(1) == "✓ Installed"
    result = [label.text() for label in dialog._result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert result == ["✓ Added SparkFun: 2 symbol libraries and 1 footprint libraries are in your scan."]
    assert not dialog._result_generate_btn.isHidden()
    assert logs == [("success", "Added SparkFun to the catalog: 2 symbol libraries, 1 footprint libraries.")]
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert isinstance(outcome, cd.CatalogOutcome) and outcome.ok
    assert (outcome.kind, outcome.id, outcome.name) == ("add", "SparkFun", "SparkFun")
    assert (outcome.symbol_count, outcome.footprint_count) == (2, 1)
    assert outcome.collisions == () and outcome.legacy_prefix == SPARKFUN.legacy_prefix and outcome.root_is_repo is False
    assert outcome.vars == dict(SPARKFUN.vars)
    assert fakes.register_calls[0].acknowledged is False and fakes.register_calls[0].today == "2026-11-27"
    assert busy[0] == (True, False) and busy[-1] == (False, False) and (False, True) in busy
    assert not dialog.holds_download()


def test_job_strip_steps(qtbot, tmp_path, fakes):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    fakes.progress = [("Counting objects", None)]
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: fakes.stage_started.is_set(), timeout=10000)
    assert dialog._job_label.full_text() == "Downloading SparkFun..." and dialog._job_bar.maximum() == 0
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: dialog._page_kind == "preview", timeout=10000)
    dialog._preview_page.back_button().click()
    qtbot.waitUntil(lambda: dialog._page_kind is None and idle(dialog), timeout=10000)
    fakes.stage_release.clear()
    fakes.stage_started.clear()
    fakes.progress = [("Receiving objects", 100)]  # the download is complete: its files are being checked
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: fakes.stage_started.is_set(), timeout=10000)
    qtbot.waitUntil(lambda: dialog._job_label.full_text() == "Checking SparkFun...", timeout=10000)
    assert dialog._job_bar.maximum() == 0
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: dialog._page_kind == "preview", timeout=10000)


def test_clashes_are_reported_in_the_result_and_the_log(qtbot, tmp_path, fakes):
    fakes.collisions = (validate.Collision("Device", "Symbol", "a KiCad library"), validate.Collision("Acme_F", "Footprint", "your Custom libraries"))
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, _ = record(dialog)
    to_preview(qtbot, dialog, fakes)
    assert dialog._preview_page.clash_list().row_count() == 2
    dialog._preview_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None and idle(dialog) and outcomes), timeout=10000)
    result = [label.text() for label in dialog._result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert result == [
        "✓ Added SparkFun: 2 symbol libraries and 1 footprint libraries are in your scan.",
        "⚠ 2 of them share a name with a library you already have and are unticked.",
    ]
    assert outcomes[0].collisions == fakes.collisions


def test_the_nickname_maps_come_from_the_last_scan(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, folders=("ThirdOne",), entries=(entry("ThirdOne"),))
    dialog.set_scan(ScanResult(
        symbol_libs=[SymbolLibrary("Atomic_R", "Custom/Symbols/Atomic_R.kicad_sym", "Custom"),
                     SymbolLibrary("My_Parts", "Custom/Symbols/My_Parts.kicad_sym", "Custom"),
                     SymbolLibrary("Third_Sym", "ThirdParty/ThirdOne/Third_Sym.kicad_sym", "ThirdOne"),
                     SymbolLibrary("Own_Sym", "ThirdParty/SparkFun/Own_Sym.kicad_sym", "SparkFun")],
        footprint_libs=[FootprintLibrary("Atomic_Footprints", "Custom/Footprints/Atomic_Footprints.pretty", "Custom")],
    ))
    dialog.set_kicad_fp_dir(tmp_path / "kicad" / "footprints")
    to_preview(qtbot, dialog, fakes)
    call = fakes.stage_calls[0]
    assert call.own == {"Atomic_R": "your Atomic_ libraries", "My_Parts": "your Custom libraries", "Atomic_Footprints": "your Atomic_ libraries"}
    assert call.other == {"Third_Sym": "Third One"}  # the library being added is not its own clash
    assert fakes.stock_dirs == [tmp_path / "kicad" / "footprints"]


def test_proprietary_tick_gates_download(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog, WURTH.name)
    page = dialog._licence_page
    assert page.tick() is not None and not page.tick().isChecked()
    assert not page.primary_button().isEnabled()
    assert page.primary_button().toolTip() == "Tick the box to confirm you have read the licence terms."
    page.primary_button().click()
    qtbot.wait(100)
    assert fakes.stage_calls == [] and dialog._page_kind == "licence"
    page.tick().setChecked(True)
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    assert dialog._preview_page.tick() is None  # asked once, on the page where the licence is known
    dialog._preview_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.register_calls and dialog._page_kind is None), timeout=10000)
    assert fakes.register_calls[0].acknowledged is True


def checked_repo(url="https://github.com/acme/parts", *, spdx=None, size_kb=2048):
    ref = RepoRef("acme", "parts", url, "acme-parts")
    info = RepoInfo("acme/parts", size_kb, "main", spdx, False, False)
    return ops.CheckedRepo(ref, info, "main")


# -- The licence page explains the two steps and links to the licence (owner-approved 2026-11-27, 17-17 check) --

STEP_ADD = (
    "Step 1 of 2. Download and Check copies the library to a temporary folder and checks it. "
    "Nothing is added yet: on the next page you choose Add Library or Discard Download."
)
STEP_REINSTALL = STEP_ADD.replace("Add Library", "Reinstall Library")
LINK_TEXT = "Read the licence"
LINK_FALLBACK_TEXT = "Read the licence on the repository page"
WURTH_LICENCE_URL = "https://github.com/WurthElektronik/KiCad-Library/blob/master/License_Terms_WE_KiCad_library.pdf"
SPARKFUN_LICENCE_URL = "https://github.com/sparkfun/SparkFun-KiCad-Libraries#license"


def licence_link(dialog):
    return dialog._licence_page.findChild(cd.catalog_pages.LinkLabel, "licenceLink")


def body_widgets(page):
    return [page._body.itemAt(i).widget() for i in range(page._body.count())]


def test_curated_licence_page_opening_line_link_and_size_on_the_button(qtbot, tmp_path, fakes):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog, "SparkFun")
    page = dialog._licence_page
    assert STEP_ADD in texts(page)
    link = licence_link(dialog)
    assert link.link_text() == LINK_TEXT and link.url() == SPARKFUN_LICENCE_URL
    assert page.primary_button().text() == "Download and Check (about 69 MB)"
    assert "about 69 MB" in texts(page)
    page.primary_button().click()  # the download runs: the buttons are busy, the text stays
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)
    assert not page.primary_button().isEnabled() and page.primary_button().text() == "Download and Check (about 69 MB)"
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    # the two names in the opening line are the buttons of the next page
    preview = dialog._preview_page
    assert f"you choose {preview.primary_button().text()} or {preview.back_button().text()}." in STEP_ADD


def test_proprietary_licence_page_puts_the_tick_under_the_licence_link(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog, WURTH.name)
    page = dialog._licence_page
    link = licence_link(dialog)
    assert link.link_text() == LINK_TEXT and link.url() == WURTH_LICENCE_URL
    assert page.primary_button().text() == "Download and Check (about 2.7 GB)"
    widgets = body_widgets(page)
    link_row = next(i for i, w in enumerate(widgets) if w.findChild(cd.catalog_pages.LinkLabel, "licenceLink") is not None)
    licence_row = next(i for i, w in enumerate(widgets) if cd.catalog_pages.LICENCE_LABEL in [x.text() for x in w.findChildren(QLabel)])
    assert link_row == licence_row + 1
    assert widgets[link_row + 1].text().startswith("⚠ Proprietary licence")
    assert widgets[link_row + 2] is page.tick()
    page.show()
    qtbot.wait(20)
    page.focus_first()
    assert page.focusWidget() is page.tick()


def test_reinstall_licence_page_names_the_reinstall_buttons(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, entries=(entry("SparkFun"),))  # recorded, folder missing
    open_licence(qtbot, dialog, "SparkFun")
    page = dialog._licence_page
    assert page.heading_text() == "Reinstall SparkFun"
    assert STEP_REINSTALL in texts(page) and STEP_ADD not in texts(page)
    link = licence_link(dialog)
    assert link.link_text() == LINK_TEXT and link.url() == SPARKFUN_LICENCE_URL  # a curated library keeps its address
    assert page.primary_button().text() == "Download and Check (about 69 MB)"
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    preview = dialog._preview_page
    assert f"you choose {preview.primary_button().text()} or {preview.back_button().text()}." in STEP_REINSTALL


def open_url_licence(qtbot, dialog, address):
    dialog._add_url_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "url"), timeout=5000)
    dialog._url_page.field().setText(address)
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    return dialog._licence_page


def test_add_by_url_licence_page_links_to_the_repository_page(qtbot, tmp_path, fakes):
    fakes.checks["https://github.com/acme/parts"] = checked_repo(spdx="MIT", size_kb=2048)
    dialog = build(qtbot, tmp_path, fakes)
    page = open_url_licence(qtbot, dialog, "https://github.com/acme/parts")
    assert STEP_ADD in texts(page)
    link = licence_link(dialog)
    assert link.link_text() == LINK_FALLBACK_TEXT and link.url() == "https://github.com/acme/parts"
    assert page.primary_button().text() == "Download and Check (about 2 MB)"


def test_add_by_url_licence_page_without_a_known_size_has_a_plain_button(qtbot, tmp_path, fakes):
    ref = RepoRef("acme", "parts", "https://github.com/acme/parts", "acme-parts")
    fakes.checks["https://github.com/acme/parts"] = ops.CheckedRepo(
        ref, None, "main", Issue(Severity.ERROR, "api.unknown", "GitHub did not answer."),
    )
    dialog = build(qtbot, tmp_path, fakes)
    page = open_url_licence(qtbot, dialog, "https://github.com/acme/parts")
    assert "Unknown" in texts(page)
    assert page.primary_button().text() == "Download and Check"
    assert licence_link(dialog).link_text() == LINK_FALLBACK_TEXT


def test_unknown_licence_tick_on_preview(qtbot, tmp_path, fakes):
    fakes.licence_text = "Some licence text."
    fakes.checks["https://github.com/acme/parts"] = checked_repo(spdx=None)
    dialog = build(qtbot, tmp_path, fakes)
    dialog._add_url_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "url"), timeout=5000)
    dialog._url_page.field().setText("https://github.com/acme/parts")
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    assert dialog._licence_page.tick() is None and dialog._licence_page.primary_button().isEnabled()
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    preview = dialog._preview_page
    assert preview.licence_box() is not None and "Some licence text." in preview.licence_box().toPlainText()
    assert not preview.primary_button().isEnabled()
    preview.tick().setChecked(True)
    preview.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.register_calls and dialog._page_kind is None and idle(dialog)), timeout=10000)
    assert fakes.register_calls[0].acknowledged is True


# -- Add by URL ----------------------------------------------------------------------------------


def test_add_by_url_flow(qtbot, tmp_path, fakes):
    good = checked_repo(spdx="MIT")
    fakes.checks["https://github.com/acme/parts.git"] = good
    fakes.checks["https://github.com/acme/known"] = Issue(Severity.ERROR, "catalog.already_listed", "This library is already in your catalog as SparkFun. Select it in the list.")
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, _ = record(dialog)
    select(dialog, "SparkFun")
    assert dialog._add_url_btn.isEnabled()
    dialog._add_url_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "url"), timeout=5000)
    page = dialog._url_page
    assert dialog._tree.selectedItems() == [] and not dialog._tree.isEnabled()
    assert dialog._pages.currentWidget() is page
    assert not page.primary_button().isEnabled() and page.primary_button().toolTip() == "Paste a web address first."
    page.field().setText("   ")
    page.primary_button().click()
    qtbot.keyClick(page.field(), Qt.Key.Key_Return)
    qtbot.wait(100)
    assert fakes.check_calls == []  # an empty address never runs a check
    page.field().setText("https://example.com/nope")
    qtbot.keyClick(page.field(), Qt.Key.Key_Return)  # Enter presses Check Repository
    qtbot.waitUntil(lambda: bool(page.refusal_texts() and idle(dialog)), timeout=10000)
    assert page.refusal_texts() == ["✖ Only web addresses that start with https://github.com/ can be added."]
    assert page.field().isEnabled() and page.field().text() == "https://example.com/nope"
    page.field().setText("https://github.com/acme/known")
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(page.refusal_texts() == ["✖ This library is already in your catalog as SparkFun. Select it in the list."]), timeout=10000)
    page.field().setText("https://github.com/acme/parts.git")
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    licence = dialog._licence_page
    assert licence.heading_text() == "Add acme/parts"
    assert licence.findChild(cd.catalog_pages.LinkLabel).url() == "https://github.com/acme/parts"
    assert any(label.full_text().endswith("ThirdParty/acme-parts") for label in licence.findChildren(cd.ElidedLabel))
    assert "about 2 MB" in texts(licence)
    licence.back_button().click()
    assert dialog._page_kind is None and dialog._tree.isEnabled()
    assert logs == []  # a refused address writes nothing to the log


def test_a_failed_check_is_a_refusal_row_and_a_step_failure_is_logged(qtbot, tmp_path, fakes):
    def boom(*a, **kw):
        raise RuntimeError("kaput")

    dialog = build(qtbot, tmp_path, fakes, check_repository=boom)
    logs, _, _ = record(dialog)
    dialog._add_url_btn.click()
    dialog._url_page.field().setText("https://github.com/acme/parts")
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._url_page.refusal_texts() and idle(dialog)), timeout=10000)
    assert ("error", "Library catalog step failed: RuntimeError: kaput") in logs
    assert dialog._url_page.field().isEnabled() and dialog._page_kind == "url"


def test_cancel_check_returns_to_the_address_page(qtbot, tmp_path, fakes):
    fakes.check_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    logs, _, _ = record(dialog)
    dialog._add_url_btn.click()
    dialog._url_page.field().setText("https://github.com/acme/parts")
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.check_started.is_set()), timeout=10000)
    assert dialog._job_label.full_text() == "Checking the repository..." and dialog._job_bar.maximum() == 0
    assert dialog._job_cancel.text() == "Cancel Check"
    assert not dialog._url_page.field().isEnabled() and not dialog._url_page.primary_button().isEnabled()
    dialog._job_cancel.click()
    assert dialog._job_label.full_text() == "Stopping..." and not dialog._job_cancel.isEnabled()
    qtbot.waitUntil(lambda: bool(idle(dialog)), timeout=10000)
    assert dialog._page_kind == "url" and dialog._url_page.field().isEnabled() and dialog._url_page.refusal_texts() == []
    assert logs == []


def test_zero_libraries_ends_on_the_refusal_page(qtbot, tmp_path, fakes):
    fakes.checks["https://github.com/acme/parts"] = checked_repo(spdx="MIT")
    fakes.stage_issue = Issue(Severity.ERROR, "catalog.no_libraries", ops.NO_LIBRARIES_TEXT)
    dialog = build(qtbot, tmp_path, fakes)
    dialog._add_url_btn.click()
    dialog._url_page.field().setText("https://github.com/acme/parts")
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview" and dialog._preview_page.is_refusal()), timeout=10000)
    assert "✖ This repository holds no KiCad symbol or footprint libraries, so there is nothing to add." in texts(dialog._preview_page)
    assert dialog._preview_page.primary_button().isHidden()


# -- Cancel, refusals, Try Again --------------------------------------------------------------------


def test_cancel_adding(qtbot, tmp_path, fakes):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, busy = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set() and dialog._job_label.full_text().endswith("42%")), timeout=10000)
    dialog._job_cancel.click()
    assert dialog._job_label.full_text() == "Stopping..." and not dialog._job_cancel.isEnabled()
    qtbot.waitUntil(lambda: bool(idle(dialog) and dialog._page_kind is None), timeout=10000)
    assert len(fakes.discard_calls) == 1  # a download that finished as Cancel was pressed is deleted
    assert ("info", "Stopped adding SparkFun. Nothing was added.") in logs
    assert dialog._pages.currentWidget() is dialog._details_page and dialog._tree.isEnabled()
    assert dialog._job_strip.isHidden() and not dialog.holds_download()
    assert busy[-1] == (False, False)
    assert len(outcomes) == 1 and outcomes[0].ok is False and outcomes[0].id == "SparkFun"
    assert not (Path(dialog._root) / "ThirdParty" / "SparkFun").exists()


def test_refusal_after_download_and_try_again(qtbot, tmp_path, fakes):
    lfs = Issue(Severity.ERROR, "catalog.lfs", "This library keeps its 3D models in Git LFS, which the catalog does not support. Nothing was added.")
    failed = Issue(Severity.ERROR, "git.clone_failed", "The download failed: could not resolve host")
    fakes.stage_issues = [lfs, failed]
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, _ = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview" and idle(dialog)), timeout=10000)
    page = dialog._preview_page
    assert page.is_refusal() and "✖ " + lfs.text in texts(page)
    assert "Nothing was added. The downloaded copy was deleted." in texts(page)
    assert page.primary_button().isHidden() and page.back_button().text() == "Back to List"
    assert not dialog.holds_download()
    assert ("error", "Could not add SparkFun: " + lfs.text) in logs
    page.back_button().click()
    assert dialog._page_kind is None and dialog._pages.currentWidget() is dialog._details_page

    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview" and idle(dialog) and page.primary_button().text() == "Try Again"), timeout=10000)
    assert not page.primary_button().isHidden() and "✖ " + failed.text in texts(page)
    page.primary_button().click()  # Try Again downloads again; the third answer is the real preview
    qtbot.waitUntil(lambda: bool(dialog.holds_download()), timeout=10000)
    assert len(fakes.stage_calls) == 3 and page.primary_button().text() == "Add Library"
    assert all(not outcome.ok for outcome in outcomes) and len(outcomes) == 2


def test_register_failure_keeps_the_preview_and_the_download(qtbot, tmp_path, fakes):
    fakes.register_issues = [Issue(Severity.ERROR, "catalog.write_failed", "The record could not be written.")]
    dialog = build(qtbot, tmp_path, fakes)
    logs, _, _ = record(dialog)
    to_preview(qtbot, dialog, fakes)
    dialog._preview_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(idle(dialog) and logs), timeout=10000)
    assert ("error", "Could not add SparkFun: The record could not be written.") in logs
    assert dialog._page_kind == "preview" and dialog.holds_download()
    assert "✖ The record could not be written." in texts(dialog._preview_page)
    assert dialog._preview_page.primary_button().isEnabled()


def test_discard_download(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, busy = record(dialog)
    to_preview(qtbot, dialog, fakes)
    assert dialog._preview_page.back_button().text() == "Discard Download"
    dialog._preview_page.back_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None and idle(dialog)), timeout=10000)
    assert len(fakes.discard_calls) == 1 and not dialog.holds_download()
    assert ("info", "Discarded the download of SparkFun. Nothing was added.") in logs
    assert outcomes and outcomes[-1].ok is False and fakes.register_calls == []


# -- Reinstall ---------------------------------------------------------------------------------------


def test_reinstall_flow(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, entries=(entry("SparkFun"),))  # recorded, folder missing
    logs, outcomes, _ = record(dialog)
    select(dialog, "SparkFun")
    assert by_name(dialog)["SparkFun"].text(1) == "✖ Problem: folder missing"
    assert dialog._reinstall_btn.text() == "Reinstall This Library" and not dialog._reinstall_btn.isHidden()
    assert dialog._add_btn.isHidden()
    dialog._reinstall_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    page = dialog._licence_page
    assert page.heading_text() == "Reinstall SparkFun"
    assert "You confirmed the licence terms on 2026-11-20." in texts(page) and page.tick() is None
    assert "main" in texts(page)
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    preview = dialog._preview_page
    assert preview.heading_text() == "Reinstall SparkFun" and preview.primary_button().text() == "Reinstall Library"
    assert [path for path, _ in preview.what_rows()] == [(Path(dialog._root) / "ThirdParty" / "SparkFun").as_posix() + "/"]
    preview.primary_button().click()
    qtbot.waitUntil(lambda: bool(outcomes and idle(dialog)), timeout=10000)
    assert ("success", "Reinstalled SparkFun: 2 symbol libraries, 1 footprint libraries.") in logs
    result = [label.text() for label in dialog._result_strip.findChildren(QLabel) if label.objectName() == "resultLine"]
    assert result == ["✓ Reinstalled SparkFun: 2 symbol libraries and 1 footprint libraries are in your scan."]
    assert outcomes[0].kind == "reinstall" and outcomes[0].ok


def test_reinstall_cancel_text(qtbot, tmp_path, fakes):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes, entries=(entry("SparkFun"),))
    logs, _, _ = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._job_label.full_text() == "Downloading SparkFun again... 42%"), timeout=10000)
    assert dialog._job_cancel.text() == "Cancel Reinstalling"
    dialog._job_cancel.click()
    qtbot.waitUntil(lambda: bool(idle(dialog)), timeout=10000)
    assert ("info", "Stopped reinstalling SparkFun. Nothing was added.") in logs


# -- Closing -----------------------------------------------------------------------------------------


def answer(monkeypatch, choice):
    """Replace the question's exec: record the box and press the named button."""
    seen = []

    def fake_exec(self):
        seen.append(self)
        for button in self.buttons():
            if button.text() == choice:
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return seen


def test_close_question_keep_working_and_stop(qtbot, tmp_path, fakes, monkeypatch):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    logs, _, _ = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)

    seen = answer(monkeypatch, "Keep Working")
    dialog.close()
    box = seen[0]
    assert box.windowTitle() == "Stop the current job?"
    assert box.text() == (
        "Adding SparkFun is still running. If you close the catalog now, it is stopped and the partly downloaded "
        "files are deleted. Nothing is added to your collection."
    )
    assert box.windowModality() == Qt.WindowModality.WindowModal and box.parent() is dialog
    assert sorted(button.text() for button in box.buttons()) == ["Keep Working", "Stop and Close"]
    assert box.defaultButton().text() == "Keep Working" and box.escapeButton().text() == "Keep Working"
    assert dialog.isVisible() and dialog.is_job_running() and dialog._job_label.full_text().startswith("Downloading SparkFun")

    answer(monkeypatch, "Stop and Close")
    dialog.close()
    qtbot.waitUntil(lambda: bool(not dialog.isVisible()), timeout=10000)
    assert idle(dialog) and ("info", "Stopped adding SparkFun. Nothing was added.") in logs
    assert len(fakes.discard_calls) == 1 and dialog._page_kind is None


def test_close_question_when_the_job_ended_first(qtbot, tmp_path, fakes, monkeypatch):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)

    def fake_exec(self):
        fakes.stage_release.set()  # the download ends while the question is open
        qtbot.waitUntil(lambda: bool(dialog.holds_download()), timeout=10000)
        for button in self.buttons():
            if button.text() == "Stop and Close":
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    dialog.close()
    qtbot.waitUntil(lambda: bool(not dialog.isVisible()), timeout=10000)
    assert len(fakes.discard_calls) == 1 and not dialog.holds_download()


def test_close_with_waiting_download_discards(qtbot, tmp_path, fakes, monkeypatch):
    dialog = build(qtbot, tmp_path, fakes)
    logs, _, _ = record(dialog)
    to_preview(qtbot, dialog, fakes)
    seen = answer(monkeypatch, "Keep Working")
    dialog.close()
    assert seen == []  # closing with a waiting download asks nothing
    assert not dialog.isVisible() and len(fakes.discard_calls) == 1 and not dialog.holds_download()
    assert ("info", "Discarded the download of SparkFun. Nothing was added.") in logs
    assert dialog._page_kind is None


def test_close_question_for_a_repository_check(qtbot, tmp_path, fakes, monkeypatch):
    fakes.check_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    dialog._add_url_btn.click()
    dialog._url_page.field().setText("https://github.com/acme/parts")
    dialog._url_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.check_started.is_set()), timeout=10000)
    seen = answer(monkeypatch, "Keep Working")
    dialog.close()
    assert seen[0].text() == (
        "The repository check is still running. If you close the catalog now, it is stopped and the partly downloaded "
        "files are deleted. Nothing is changed."
    )
    answer(monkeypatch, "Stop and Close")
    dialog.close()
    qtbot.waitUntil(lambda: bool(not dialog.isVisible()), timeout=10000)


def test_close_during_the_record_write_is_ignored(qtbot, tmp_path, fakes, monkeypatch):
    fakes.register_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    to_preview(qtbot, dialog, fakes)
    dialog._preview_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.register_started.is_set()), timeout=10000)
    seen = answer(monkeypatch, "Stop and Close")
    dialog.close()
    assert seen == [] and dialog.isVisible()
    assert dialog._job_label.full_text() == "Adding cannot be stopped halfway. Close this window after it ends."
    assert not dialog._job_cancel.isEnabled()
    fakes.register_release.set()
    qtbot.waitUntil(lambda: bool(idle(dialog)), timeout=10000)


def test_no_worker_after_done(qtbot, tmp_path, fakes, monkeypatch):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    logs, outcomes, _ = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)
    answer(monkeypatch, "Stop and Close")
    dialog.close()
    qtbot.waitUntil(lambda: bool(not dialog.isVisible()), timeout=10000)
    seen = (list(logs), list(outcomes))
    qtbot.wait(200)
    assert (logs, outcomes) == seen
    assert all(not worker.isRunning() for worker in dialog._workers) and dialog._job is None
    assert dialog._page_kind is None and dialog._staged is None


def test_reopening_after_a_close_starts_on_the_list(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    dialog.close()
    assert dialog._page_kind is None
    dialog.show()
    qtbot.waitUntil(lambda: bool(dialog._net_status is not None), timeout=10000)
    assert dialog._pages.currentWidget() is not dialog._licence_page and dialog._tree.isEnabled()


# -- Busy rules and keyboard -------------------------------------------------------------------------


def test_one_job_at_a_time_and_blocked_reasons(qtbot, tmp_path, fakes):
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    page = dialog._licence_page
    dialog.set_blocked("Close the import window first.")
    assert not page.primary_button().isEnabled() and page.primary_button().toolTip() == "Close the import window first."
    dialog.set_blocked(None)
    assert page.primary_button().isEnabled()
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)
    for button in (dialog._add_url_btn, dialog._check_btn):
        assert not button.isEnabled() and button.toolTip() == "Wait for adding SparkFun to finish."
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    dialog.set_blocked("Wait for the scan in the main window to end.")
    assert not dialog._preview_page.primary_button().isEnabled()
    assert dialog._preview_page.primary_button().toolTip() == "Wait for the scan in the main window to end."
    assert dialog._preview_page.back_button().isEnabled()  # Discard Download still works
    dialog.set_blocked(None)


def test_blocked_reasons_disable_the_details_buttons(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    select(dialog, "SparkFun")
    assert dialog._add_btn.isEnabled()
    for reason in ("Close the migration window first.", "Finishing the last change..."):
        dialog.set_blocked(reason)
        assert not dialog._add_btn.isEnabled() and dialog._add_btn.toolTip() == reason
    dialog.set_blocked(None)
    dialog.set_finishing(True)
    assert not dialog._add_btn.isEnabled() and dialog._add_btn.toolTip() == "Finishing the last change..."
    dialog.set_finishing(False)
    assert dialog._add_btn.isEnabled() and dialog._add_btn.toolTip() == ""


def test_the_actions_stay_off_while_the_record_or_git_is_bad(qtbot, tmp_path, fakes):
    refused = NetStatus(None, None, Issue(Severity.ERROR, "git.not_found", "Git was not found."), None)
    dialog = build(qtbot, tmp_path, fakes, net_status=lambda root: refused)
    select(dialog, "SparkFun")
    assert not dialog._add_btn.isEnabled() and dialog._add_btn.toolTip() == "Git was not found."


def test_list_locked_while_a_page_is_open(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    assert dialog.selected_id() == "SparkFun"
    assert not dialog._tree.isEnabled() and not dialog._search.isEnabled()
    assert not dialog._add_url_btn.isEnabled() and not dialog._check_btn.isEnabled()
    dialog.set_scan(ScanResult())  # a late result must not pull the page away
    dialog._refresh_details()
    assert dialog._pages.currentWidget() is dialog._licence_page
    dialog._licence_page.back_button().click()
    assert dialog._tree.isEnabled() and dialog._search.isEnabled() and dialog.selected_id() == "SparkFun"
    assert dialog._pages.currentWidget() is dialog._details_page
    qtbot.waitUntil(lambda: bool(dialog._tree.hasFocus()), timeout=2000)


def test_esc_backs_out_and_ctrl_return_presses_primary(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    select(dialog, "SparkFun")
    assert dialog._close_btn.isDefault()
    open_licence(qtbot, dialog)
    assert not dialog._close_btn.isDefault() and not dialog._close_btn.autoDefault()  # Close is never the default on a review page
    qtbot.keyClick(dialog, Qt.Key.Key_Return)
    assert dialog.isVisible() and dialog._page_kind == "licence" and fakes.stage_calls == []
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible() and dialog._page_kind is None
    assert dialog._close_btn.isDefault()

    open_licence(qtbot, dialog, WURTH.name)
    qtbot.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    qtbot.wait(100)
    assert fakes.stage_calls == [] and dialog._page_kind == "licence"  # the primary is disabled until the tick
    dialog._licence_page.tick().setChecked(True)
    qtbot.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    assert len(fakes.stage_calls) == 1 and fakes.register_calls == []
    qtbot.keyClick(dialog, Qt.Key.Key_Return)  # Enter alone never confirms the preview
    qtbot.wait(100)
    assert fakes.register_calls == [] and dialog._page_kind == "preview"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)  # Esc is Discard Download, never Add Library
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None and idle(dialog)), timeout=10000)
    assert fakes.register_calls == [] and len(fakes.discard_calls) == 1


def test_ctrl_return_presses_the_details_primary(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    select(dialog, "SparkFun")
    qtbot.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)


def test_one_accent_button_at_a_time(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, entries=(entry("ThirdOne"),), folders=())
    fakes.stage_release.clear()

    def accent():
        return [
            b for b in dialog.findChildren(QPushButton)
            if b.styleSheet() == theme.PRIMARY_BUTTON_QSS and b.isVisibleTo(dialog)
        ]

    assert accent() == []  # nothing selected: no accent button
    select(dialog, "SparkFun")
    assert accent() == [dialog._add_btn]
    dialog._add_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    assert accent() == [dialog._licence_page.primary_button()]
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(fakes.stage_started.is_set()), timeout=10000)
    assert len(accent()) == 1
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    assert accent() == [dialog._preview_page.primary_button()]
    dialog._preview_page.back_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind is None), timeout=10000)
    select(dialog, "Third One")  # recorded, folder missing: Reinstall is the one accent button
    assert accent() == [dialog._reinstall_btn]
    dialog._add_url_btn.click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "url"), timeout=5000)
    assert accent() == [dialog._url_page.primary_button()]  # disabled while the field is empty, but still the one accent button


# -- Backstops ---------------------------------------------------------------------------------------


def test_web_address_long_text(qtbot, tmp_path, fakes):
    long = "https://github.com/acme/" + "x" * 300
    ref = RepoRef("acme", "x" * 300, long, "acme-" + "x" * 60)
    fakes.checks[long] = ops.CheckedRepo(ref, RepoInfo("acme/x", 1024, "main", "MIT", False, False), "main")
    dialog = build(qtbot, tmp_path, fakes)
    dialog.resize(*cd.WINDOW_MINIMUM)
    qtbot.wait(50)
    width = dialog.width()
    dialog._add_url_btn.click()
    page = dialog._url_page
    page.field().setText(long)
    assert page.field().text() == long and page.field().fontMetrics().horizontalAdvance(long) > page.field().width()  # it scrolls inside the field
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "licence"), timeout=10000)
    qtbot.wait(100)
    link = dialog._licence_page.findChild(cd.catalog_pages.LinkLabel)
    assert link.url() == long and link.toolTip() == long and link.font().family() == theme.MONO_FAMILY
    assert dialog.width() == width
    assert dialog._pages.width() <= dialog._scroll.viewport().width()
    assert dialog._scroll.horizontalScrollBar().maximum() == 0


def test_step_label_elides(qtbot, tmp_path, fakes):
    name = "A very long library name " + "x" * 35
    long = replace(SPARKFUN, id="LongOne", name=name, url="https://github.com/x/long.git")
    fakes.stage_release.clear()
    dialog = build(qtbot, tmp_path, fakes, curated=(long,))
    dialog.resize(*cd.WINDOW_MINIMUM)
    open_licence(qtbot, dialog, name)
    cancel_before = dialog._job_cancel.sizeHint()
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._job_label.full_text() == f"Downloading {name}... 42%"), timeout=10000)
    qtbot.wait(100)
    label = dialog._job_label
    assert label.toolTip() == label.full_text()
    assert len(label.text()) < len(label.full_text()) and label.text().endswith("…")
    assert dialog._job_bar.width() == 240
    assert dialog._job_cancel.sizeHint().width() >= cancel_before.width()
    assert dialog._job_cancel.isVisibleTo(dialog)
    fakes.stage_release.set()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)


def test_set_root_drops_an_open_page(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes)
    open_licence(qtbot, dialog)
    other = make_collection(tmp_path / "other")
    dialog.set_root(other)
    assert dialog._page_kind is None and dialog._tree.isEnabled()
    assert not dialog.is_job_running() and not dialog.holds_download()


def test_a_crash_in_the_download_is_logged_and_offers_try_again(qtbot, tmp_path, fakes):
    def boom(*a, **kw):
        raise RuntimeError("kaput")

    dialog = build(qtbot, tmp_path, fakes, stage_add=boom)
    logs, _, _ = record(dialog)
    open_licence(qtbot, dialog)
    dialog._licence_page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview" and idle(dialog)), timeout=10000)
    assert ("error", "Library catalog step failed: RuntimeError: kaput") in logs
    assert dialog._preview_page.is_refusal() and dialog._preview_page.primary_button().text() == "Try Again"
    assert not dialog.holds_download()


def test_licence_page_refusals_from_plan_add(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, free_space=lambda root: Usage(1024 * 1024))
    open_licence(qtbot, dialog)
    page = dialog._licence_page
    assert page.is_refused() and page.primary_button().isHidden()
    assert any(text.startswith("✖ There is not enough free space on") for text in texts(page))


def test_kicad_open_line_on_the_licence_page(qtbot, tmp_path, fakes):
    dialog = build(qtbot, tmp_path, fakes, kicad_running=lambda: ["kicad.exe"])
    open_licence(qtbot, dialog)
    assert "⚠ KiCad is open (kicad.exe). Restart it after the library is added to see the changes." in texts(dialog._licence_page)


def _fully_visible_in_pane(dialog, button):
    """True when the whole button lies inside the detail pane's visible area (not scrolled out of it)."""
    viewport = dialog._scroll.viewport()
    top_left = button.mapTo(viewport, button.rect().topLeft())
    bottom_right = button.mapTo(viewport, button.rect().bottomRight())
    return viewport.rect().contains(top_left) and viewport.rect().contains(bottom_right)


@pytest.mark.parametrize("size", [(1030, 660), (760, 520)])
def test_review_page_buttons_stay_in_view_in_a_short_pane(qtbot, tmp_path, fakes, size):
    """The owner could not see Download and Check under the licence page's rows (amber Git line, short pane): the
    page's text scrolls on its own and its button row stays in view."""
    from kicad_lib_manager.catalog import gitnet

    _, warning = gitnet.version_issues((2, 49, 0))
    dialog = build(qtbot, tmp_path, fakes, net_status=lambda root: NetStatus(object(), (2, 49, 0), None, warning))
    dialog.resize(*size)
    qtbot.wait(50)
    assert not dialog._git_old_strip.isHidden()
    open_licence(qtbot, dialog)
    qtbot.wait(100)
    page = dialog._licence_page
    for button in (page.primary_button(), page.back_button()):
        assert button.isVisible() and _fully_visible_in_pane(dialog, button), button.text()
    assert dialog._scroll.verticalScrollBar().maximum() == 0  # the pane itself does not scroll on a review page
    # the preview page, with more rows, keeps its buttons in view too
    page.primary_button().click()
    qtbot.waitUntil(lambda: bool(dialog._page_kind == "preview"), timeout=10000)
    qtbot.wait(100)
    preview = dialog._preview_page
    assert _fully_visible_in_pane(dialog, preview.primary_button()) and _fully_visible_in_pane(dialog, preview.back_button())
