"""The review pages of the library catalog window (Phase 17 plan 13; CAT-02, CAT-03, CAT-08, D-10, D-20, D-23).

The pages are built standalone: no dialog, no service, no worker. They are filled with synthetic plans and staged
downloads and read back through their public methods. Nothing is shown on the desktop (offscreen platform).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QPushButton

from kicad_lib_manager.catalog import curated, licences, manifest, ops, validate
from kicad_lib_manager.catalog.licences import LicenceClass
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.widgets import catalog_pages as cp
from kicad_lib_manager.widgets import theme
from kicad_lib_manager.widgets.import_result import ElidedLabel

FAKE_COLLECTION = Path("/collection")
SHA = "a" * 40
SETTLED = (LicenceClass.OPEN, LicenceClass.SHARE_ALIKE, LicenceClass.PROPRIETARY)


def source(spdx="MIT", *, proprietary=False, known=True, id="Acme", name="Acme", url="https://github.com/acme/parts.git",
           vars=None, licence_url=""):
    extra = {"licence_url": licence_url} if licence_url else {}
    return ops.AddSource(id, name, url, "main", vars or {}, spdx, proprietary=proprietary, licence_known=known, **extra)


def plan_of(src=None, *, size=68, refusals=(), kicad_open=(), gitignore="", reinstall=False, ack_on="", acknowledged=False):
    src = src or source()
    cls = licences.licence_class(src.licence_spdx, proprietary=src.proprietary, known=src.licence_known)
    return ops.AddPlan(
        src, src.name, FAKE_COLLECTION / "ThirdParty" / src.id, cls, cls in SETTLED, size, None if size is None else 6 * size, 500, 100000,
        refusals=tuple(refusals), kicad_open=tuple(kicad_open), gitignore=gitignore, reinstall=reinstall,
        acknowledged_on=ack_on, acknowledged=acknowledged,
    )


def staged_of(plan, *, collisions=(), vars=None, licence_text=None, symbols=("Acme_A", "Acme_B"), footprints=("Acme_F",)):
    report = validate.StagingReport(tuple(symbols), tuple(footprints), tuple(collisions), {}, 0, licence_text, ())
    return ops.Staged(plan.source, plan.folder, SHA, report, (), plan, vars)


def texts(page):
    return [label.text() for label in page.findChildren(QLabel)]


def build(qtbot, page):
    qtbot.addWidget(page)
    return page


# -- Add by URL ---------------------------------------------------------------------------------


def test_add_by_url_page(qtbot):
    page = build(qtbot, cp.AddByUrlPage())
    assert page.heading_text() == "Add a library from GitHub"
    assert cp.URL_BODY in texts(page)
    field = page.field()
    assert field.placeholderText() == "https://github.com/owner/repository"
    assert field.accessibleName() == "Web address"
    assert page.primary_button().text() == "Check Repository"
    assert not page.primary_button().isEnabled()
    assert page.primary_button().toolTip() == "Paste a web address first."
    field.setText("    ")
    assert page.address() == "" and not page.primary_button().isEnabled()
    with qtbot.assertNotEmitted(page.primary_pressed):
        qtbot.keyClick(field, Qt.Key.Key_Return)
    field.setText("  https://github.com/acme/parts  ")
    assert page.address() == "https://github.com/acme/parts"
    assert page.primary_button().isEnabled() and page.primary_button().toolTip() == ""
    with qtbot.waitSignal(page.primary_pressed, timeout=2000):
        qtbot.keyClick(field, Qt.Key.Key_Return)


def test_add_by_url_refusal_rows_keep_the_field_editable(qtbot):
    page = build(qtbot, cp.AddByUrlPage())
    page.field().setText("https://example.com/x")
    page.show_refusals([Issue(Severity.ERROR, "catalog.bad_url", "Only web addresses that start with https://github.com/ can be added."),
                        "A second row."])
    assert page.refusal_texts() == ["✖ Only web addresses that start with https://github.com/ can be added.", "✖ A second row."]
    assert page.field().isEnabled() and page.field().text() == "https://example.com/x"
    rows = [label for label in page.findChildren(QLabel) if label.text().startswith("✖")]
    assert all(label.wordWrap() and label.accessibleName() == label.text() for label in rows)
    page.show_refusals([])
    assert page.refusal_texts() == []


def test_add_by_url_checking_state(qtbot):
    page = build(qtbot, cp.AddByUrlPage())
    page.field().setText("https://github.com/acme/parts")
    page.set_checking(True)
    assert not page.field().isEnabled()
    assert not page.primary_button().isEnabled() and not page.back_button().isEnabled()
    page.set_checking(False)
    assert page.field().isEnabled() and page.primary_button().isEnabled() and page.back_button().isEnabled()


def test_blocked_reason_is_the_primary_tooltip(qtbot):
    page = build(qtbot, cp.AddByUrlPage())
    page.field().setText("https://github.com/acme/parts")
    page.set_blocked("Wait for the scan in the main window to end.")
    assert not page.primary_button().isEnabled()
    assert page.primary_button().toolTip() == "Wait for the scan in the main window to end."
    assert page.back_button().isEnabled()
    page.set_blocked(None)
    assert page.primary_button().isEnabled()


# -- The licence page ---------------------------------------------------------------------------

NOTE_CASES = [
    ("MIT", False, True, None, False, "MIT"),
    ("CC-BY-SA-4.0", False, True, cp.SHARE_ALIKE_NOTE, True, "CC BY-SA 4.0"),
    (None, True, True, cp.PROPRIETARY_NOTE, True, "Proprietary"),
    (None, False, True, cp.NOT_STATED_NOTE, False, "Not stated by the repository"),
    ("Weird-1.0", False, True, cp.OTHER_NOTE, False, "Other (see the licence file)"),
    (None, False, False, cp.UNREADABLE_NOTE, False, "Could not be read from GitHub"),
]


@pytest.mark.parametrize("spdx, proprietary, known, note, tick, shown", NOTE_CASES)
def test_licence_page_rows_and_notes(qtbot, spdx, proprietary, known, note, tick, shown):
    page = build(qtbot, cp.LicencePage())
    plan = plan_of(source(spdx, proprietary=proprietary, known=known))
    page.show_plan(plan, reinstall=False, acknowledged_on="")
    assert page.heading_text() == "Add Acme"
    assert cp.LICENCE_BODY in texts(page)
    assert shown in texts(page)
    assert (cp.WARNING_GLYPH + note in texts(page)) if note else not any(t.startswith("⚠") for t in texts(page))
    link = page.findChild(cp.LinkLabel)
    assert link.url() == "https://github.com/acme/parts" and link.toolTip() == link.url()
    where = [label for label in page.findChildren(ElidedLabel) if label.full_text().endswith("ThirdParty/Acme")]
    assert len(where) == 1 and where[0].toolTip() == where[0].full_text() and where[0].font().family() == theme.MONO_FAMILY
    assert "about 68 MB" in texts(page)
    assert page.primary_button().text() == "Download and Check (about 68 MB)"
    if tick:
        box = page.tick()
        assert box is not None and box.text() == "I have read the licence terms" and not box.isChecked()
        assert box.accessibleName() == box.text()
        assert not page.primary_button().isEnabled()
        assert page.primary_button().toolTip() == "Tick the box to confirm you have read the licence terms."
        assert not page.acknowledged()
        box.setChecked(True)
        assert page.acknowledged() and page.primary_button().isEnabled() and page.primary_button().toolTip() == ""
        box.setChecked(False)
        assert not page.primary_button().isEnabled()
    else:
        assert page.tick() is None and page.primary_button().isEnabled() and not page.acknowledged()


def test_licence_page_size_unknown(qtbot):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(plan_of(size=None))
    assert "Unknown" in texts(page)


def test_licence_page_for_a_typed_address_shows_name_and_cleaned_address(qtbot):
    page = build(qtbot, cp.LicencePage())
    long = "https://github.com/acme/" + "x" * 300
    page.show_plan(plan_of(), name="acme/parts", address=long)
    assert page.heading_text() == "Add acme/parts"
    link = page.findChild(cp.LinkLabel)
    assert link.url() == long and link.toolTip() == long
    assert link.minimumSizeHint().width() == 0  # the address elides, it never widens the page
    assert link.font().family() == theme.MONO_FAMILY


def test_licence_page_reinstall_variant(qtbot):
    page = build(qtbot, cp.LicencePage())
    plan = plan_of(source(None, proprietary=True), reinstall=True, ack_on="2026-11-20", acknowledged=True)
    page.show_plan(plan, reinstall=True, acknowledged_on="2026-11-20")
    assert page.heading_text() == "Reinstall Acme"
    assert "You confirmed the licence terms on 2026-11-20." in texts(page)
    assert page.tick() is None and page.primary_button().isEnabled()
    assert "main" in texts(page) and "Branch" in texts(page)
    assert page.primary_button().text() == "Download and Check (about 68 MB)"


def test_licence_page_refusals_leave_only_back(qtbot):
    page = build(qtbot, cp.LicencePage())
    refusals = [Issue(Severity.ERROR, "catalog.no_space", "There is not enough free space on D: for Acme."),
                Issue(Severity.ERROR, "catalog.unlisted_in_way", "The folder x already exists in ThirdParty.")]
    page.show_plan(plan_of(refusals=refusals, kicad_open=("kicad.exe", "pcbnew.exe")))
    assert "✖ There is not enough free space on D: for Acme." in texts(page)
    assert "✖ The folder x already exists in ThirdParty." in texts(page)
    assert page.is_refused() and page.primary_button().isHidden() and not page.back_button().isHidden()
    assert ("⚠ KiCad is open (kicad.exe, pcbnew.exe). Restart it after the library is added to see the changes."
            in texts(page))
    page.show_plan(plan_of())
    assert not page.is_refused() and not page.primary_button().isHidden()


# -- The licence page: opening line, licence link, size on the button (owner-approved 2026-11-27, 17-17 check) --

STEP_ADD = (
    "Step 1 of 2. Download and Check copies the library to a temporary folder and checks it. "
    "Nothing is added yet: on the next page you choose Add Library or Discard Download."
)
STEP_REINSTALL = STEP_ADD.replace("Add Library", "Reinstall Library")
WURTH_LICENCE_URL = "https://github.com/WurthElektronik/KiCad-Library/blob/master/License_Terms_WE_KiCad_library.pdf"
SPARKFUN_LICENCE_URL = "https://github.com/sparkfun/SparkFun-KiCad-Libraries#license"
LINK_TEXT = "Read the licence"
LINK_FALLBACK_TEXT = "Read the licence on the repository page"
OLD_OPENING_LINE = "Read the licence before you download. Nothing is added to your collection yet."


def curated_plan(tmp_path, id):
    """The real plan of a curated library, as the window builds it (no network, plenty of free space)."""
    return ops.plan_add(
        tmp_path, curated.curated_by_id(id), manifest.Manifest(()),
        free_space=lambda path: SimpleNamespace(free=10**13), running=lambda: [],
    )


def licence_link(page):
    return page.findChild(cp.LinkLabel, "licenceLink")


def body_kinds(page):
    """The kinds of the page's body widgets in layout order (only the ones the order tests name)."""
    kinds = []
    for index in range(page._body.count()):
        widget = page._body.itemAt(index).widget()
        row_texts = [label.text() for label in widget.findChildren(QLabel)]
        if isinstance(widget, QCheckBox):
            kinds.append("tick")
        elif widget.findChild(cp.LinkLabel, "licenceLink") is not None:
            kinds.append("link")
        elif isinstance(widget, QLabel) and widget.text().startswith("⚠"):
            kinds.append("note")
        elif isinstance(widget, QLabel) and widget.text().startswith("You confirmed"):
            kinds.append("confirmed")
        elif cp.LICENCE_LABEL in row_texts:
            kinds.append("licence")
        elif cp.SIZE_LABEL in row_texts:
            kinds.append("size")
        elif cp.INSTALLED_IN_LABEL in row_texts:
            kinds.append("installed")
    return kinds


def test_licence_page_opening_line_for_add(qtbot):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(plan_of())
    assert cp.LICENCE_BODY == STEP_ADD
    assert STEP_ADD in texts(page) and OLD_OPENING_LINE not in texts(page)
    opening = [label for label in page.findChildren(QLabel) if label.text() == STEP_ADD]
    assert len(opening) == 1 and opening[0].wordWrap() and opening[0].styleSheet() == f"color: {theme.MUTED};"
    assert texts(page)[1] == STEP_ADD  # the first line under the heading


def test_licence_page_opening_line_for_reinstall_names_the_reinstall_buttons(qtbot):
    page = build(qtbot, cp.LicencePage())
    plan = plan_of(source(None, proprietary=True), reinstall=True, ack_on="2026-11-20", acknowledged=True)
    page.show_plan(plan, reinstall=True, acknowledged_on="2026-11-20")
    assert STEP_REINSTALL in texts(page) and STEP_ADD not in texts(page) and OLD_OPENING_LINE not in texts(page)
    # the two names are the ones the reinstall preview really shows
    preview = build(qtbot, cp.AddPreviewPage())
    preview.show_staged(staged_of(plan), plan, root_is_repo=False)
    assert f"you choose {preview.primary_button().text()} or {preview.back_button().text()}." in STEP_REINSTALL
    # and an Add goes back to the Add names
    page.show_plan(plan_of())
    assert STEP_ADD in texts(page) and STEP_REINSTALL not in texts(page)


def test_licence_page_text_has_no_jargon(qtbot):
    page = build(qtbot, cp.LicencePage())
    for plan, reinstall in ((plan_of(), False), (plan_of(reinstall=True), True)):
        page.show_plan(plan, reinstall=reinstall)
        for text in texts(page) + [page.primary_button().text(), page.back_button().text()]:
            assert not any(word in text.casefold() for word in ("spdx", "manifest", "clone", "staging")), text


def test_licence_link_for_wurth(qtbot, tmp_path):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(curated_plan(tmp_path, "WurthElektronik"))
    link = licence_link(page)
    assert link is not None and link.link_text() == LINK_TEXT
    assert link.url() == WURTH_LICENCE_URL and link.toolTip() == WURTH_LICENCE_URL
    assert f'href="{WURTH_LICENCE_URL}"' in link.text() and LINK_TEXT in link.text()
    assert link.openExternalLinks() and link.accessibleName() == LINK_TEXT
    assert link.url() != page.findChild(cp.LinkLabel, "repositoryLink").url()  # a second link, not the repository's


def test_licence_link_for_sparkfun(qtbot, tmp_path):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(curated_plan(tmp_path, "SparkFun"))
    link = licence_link(page)
    assert link.link_text() == LINK_TEXT and link.url() == SPARKFUN_LICENCE_URL and link.toolTip() == SPARKFUN_LICENCE_URL
    assert f'href="{SPARKFUN_LICENCE_URL}"' in link.text()


def test_licence_link_falls_back_to_the_repository_page(qtbot):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(plan_of(source("MIT")))  # no licence address: an Add by URL, or Espressif
    link = licence_link(page)
    assert link.link_text() == LINK_FALLBACK_TEXT
    assert link.url() == "https://github.com/acme/parts" and link.toolTip() == link.url()
    assert 'href="https://github.com/acme/parts"' in link.text()
    assert link.accessibleName() == LINK_FALLBACK_TEXT
    # a typed address opens the cleaned address the page shows as the repository
    long = "https://github.com/acme/" + "x" * 300
    page.show_plan(plan_of(), name="acme/parts", address=long)
    assert licence_link(page).url() == long and licence_link(page).link_text() == LINK_FALLBACK_TEXT
    assert licence_link(page).minimumSizeHint().width() == 0  # it elides, it never widens the page


def test_licence_link_text_is_elided_to_its_width_but_keeps_its_address(qtbot, tmp_path):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(curated_plan(tmp_path, "WurthElektronik"))
    page.show()
    qtbot.wait(20)
    link = licence_link(page)
    link.setFixedWidth(50)  # too narrow for the words
    qtbot.wait(20)
    assert "…" in link.text() and f'href="{WURTH_LICENCE_URL}"' in link.text()
    assert link.url() == WURTH_LICENCE_URL and link.link_text() == LINK_TEXT
    assert link.minimumSizeHint().width() == 0


def test_licence_link_replaces_the_old_address_on_a_second_plan(qtbot, tmp_path):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(curated_plan(tmp_path, "WurthElektronik"))
    page.show_plan(plan_of(source("MIT")))
    links = [label for label in page.findChildren(cp.LinkLabel) if label.objectName() == "licenceLink"]
    assert len(links) == 1 and links[0].link_text() == LINK_FALLBACK_TEXT


ORDER_CASES = [
    # the licence row, the link, the amber note, then the tick (or the line that replaces it), then Size and the folder
    (dict(spdx="CC-BY-SA-4.0", licence_url=SPARKFUN_LICENCE_URL), False, ["licence", "link", "note", "tick", "size", "installed"]),
    (dict(spdx=None, proprietary=True, licence_url=WURTH_LICENCE_URL), False, ["licence", "link", "note", "tick", "size", "installed"]),
    (dict(spdx=None, proprietary=True, licence_url=WURTH_LICENCE_URL), True, ["licence", "link", "note", "confirmed", "size", "installed"]),
    (dict(spdx=None, known=True), False, ["licence", "link", "note", "size", "installed"]),
    (dict(spdx="MIT"), False, ["licence", "link", "size", "installed"]),
]


@pytest.mark.parametrize("kwargs, reinstall, expected", ORDER_CASES)
def test_licence_page_order_licence_link_note_tick(qtbot, kwargs, reinstall, expected):
    page = build(qtbot, cp.LicencePage())
    plan = plan_of(source(**kwargs), reinstall=reinstall, ack_on="2026-11-20", acknowledged=reinstall)
    page.show_plan(plan, reinstall=reinstall, acknowledged_on="2026-11-20")
    kinds = body_kinds(page)
    assert kinds == expected
    if "tick" in kinds:
        # the tick sits directly under the link and the note
        assert kinds.index("tick") == kinds.index("link") + 2 == kinds.index("licence") + 3


def test_licence_page_first_focus_stays_on_the_tick(qtbot, tmp_path):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(curated_plan(tmp_path, "WurthElektronik"))
    page.show()
    qtbot.wait(20)  # a widget added to a shown page is shown by a queued event
    page.focus_first()
    assert page.focusWidget() is page.tick() and page.tick() is not None
    assert licence_link(page).focusPolicy() == Qt.FocusPolicy.NoFocus


BUTTON_CASES = [
    (68, "Download and Check (about 68 MB)", "about 68 MB"),
    (999, "Download and Check (about 999 MB)", "about 999 MB"),
    (2674, "Download and Check (about 2.7 GB)", "about 2.7 GB"),
    (None, "Download and Check", "Unknown"),
]


@pytest.mark.parametrize("size, button, size_row", BUTTON_CASES)
def test_download_button_shows_the_size_when_it_is_known(qtbot, size, button, size_row):
    page = build(qtbot, cp.LicencePage())
    page.show_plan(plan_of(size=size))
    assert cp.DOWNLOAD_TEXT == "Download and Check"
    assert page.primary_button().text() == button
    assert size_row in texts(page)  # the Size row and the button say the same size
    if size is not None:
        assert button == f"{cp.DOWNLOAD_TEXT} ({size_row})"


def test_download_button_text_follows_the_plan_and_survives_busy_and_blocked(qtbot):
    page = build(qtbot, cp.LicencePage())
    assert page.primary_button().text() == "Download and Check"  # nothing shown yet
    page.show_plan(plan_of(size=68))
    page.set_blocked("Close the import window first.")
    assert page.primary_button().text() == "Download and Check (about 68 MB)" and not page.primary_button().isEnabled()
    assert page.primary_button().toolTip() == "Close the import window first."
    page.set_blocked(None)
    page.set_busy(True)
    assert page.primary_button().text() == "Download and Check (about 68 MB)" and not page.primary_button().isEnabled()
    page.set_busy(False)
    page.show_plan(plan_of(size=None))  # the next plan has no known size
    assert page.primary_button().text() == "Download and Check"
    page.show_plan(plan_of(size=2674, reinstall=True), reinstall=True)
    assert page.primary_button().text() == "Download and Check (about 2.7 GB)"


# -- The Add preview ----------------------------------------------------------------------------

CLASHES = (
    validate.Collision("Device", "Symbol", "a KiCad library"),
    validate.Collision("Atomic_R", "Footprint", "your Atomic_ libraries"),
    validate.Collision("Other", "Symbol", "SparkFun"),
)


def test_add_preview_sections(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source("MIT", vars={"ACME_3D": "models"}), gitignore="append")
    staged = staged_of(plan, vars={"ACME_3D": "models"})
    page.show_staged(staged, plan, root_is_repo=True)
    assert page.heading_text() == "Add Acme"
    assert page.primary_button().text() == "Add Library"
    assert page.back_button().text() == "Discard Download"
    assert page.back_button().toolTip() == "Delete the downloaded copy. Nothing is added."
    assert "✓ Downloaded and checked: 2 symbol libraries and 1 footprint libraries." in texts(page)
    rows = page.what_rows()
    assert [path for path, _ in rows] == ["/collection/ThirdParty/Acme/", "/collection/catalog.json", "/collection/.gitignore"]
    assert rows[0][1] == "2 symbol libraries, 1 footprint libraries" and rows[1][1] == "records this library"
    assert rows[2][1].startswith("gets the line /ThirdParty/ so git")
    sentence = ("This library needs the KiCad path variable ACME_3D to point to /collection/ThirdParty/Acme/models. "
                "After you press Add Library, the app asks before it changes KiCad's settings.")
    assert sentence in texts(page)
    assert "✓ No library has the same name as one you already have." in texts(page)
    assert "Licence: MIT" in texts(page)
    assert page.tick() is None and page.primary_button().isEnabled()


def test_add_preview_gitignore_row_variants(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    for state, root_is_repo, expected in (
        ("create", True, "is created with the line /ThirdParty/"),
        ("append", True, "gets the line /ThirdParty/"),
        ("append", False, None),
        ("", True, None),
    ):
        plan = plan_of(gitignore=state)
        page.show_staged(staged_of(plan), plan, root_is_repo=root_is_repo)
        rows = page.what_rows()
        ignore = [text for path, text in rows if path.endswith(".gitignore")]
        if expected is None:
            assert not ignore and len(rows) == 2
        else:
            assert len(ignore) == 1 and ignore[0].startswith(expected)


def test_add_preview_without_variables_has_no_path_variable_section(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of()
    page.show_staged(staged_of(plan, vars={}), plan, root_is_repo=False)
    assert "Path variables" not in texts(page)


def test_add_preview_clash_list(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of()
    page.show_staged(staged_of(plan, collisions=CLASHES), plan, root_is_repo=False)
    assert "⚠ 3 libraries have the same name as a library you already have:" in texts(page)
    assert cp.CLASH_NOTE in texts(page)
    clashes = page.clash_list()
    tree = clashes.tree()
    assert [tree.headerItem().text(c) for c in range(3)] == ["Library", "Kind", "Same name as"]
    assert [[tree.topLevelItem(r).text(c) for c in range(3)] for r in range(3)] == [
        ["Device", "Symbol", "a KiCad library"],
        ["Atomic_R", "Footprint", "your Atomic_ libraries"],
        ["Other", "Symbol", "SparkFun"],
    ]
    assert clashes.is_expanded() and clashes.toggle().isHidden()
    page.show_staged(staged_of(plan, collisions=CLASHES[:1]), plan, root_is_repo=False)
    assert "⚠ 1 library has the same name as a library you already have:" in texts(page)
    page.show_staged(staged_of(plan), plan, root_is_repo=False)
    assert page.clash_list() is None


def test_add_preview_licence_file_with_tick(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source(None, known=True))  # not stated: the file text and the tick belong here
    page.show_staged(staged_of(plan, licence_text="Permission is granted.\n" * 30), plan, root_is_repo=False)
    box = page.licence_box()
    assert isinstance(box, QPlainTextEdit) and box.isReadOnly() and "Permission is granted." in box.toPlainText()
    assert box.font().family() == theme.MONO_FAMILY
    assert box.height() <= 8 * box.fontMetrics().lineSpacing() + 40
    tick = page.tick()
    assert tick is not None and not tick.isChecked() and not page.acknowledged()
    assert not page.primary_button().isEnabled()
    assert page.primary_button().toolTip() == "Tick the box to confirm you have read the licence terms."
    tick.setChecked(True)
    assert page.acknowledged() and page.primary_button().isEnabled()


def test_add_preview_without_a_licence_file(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source(None, known=False))
    page.show_staged(staged_of(plan, licence_text=None), plan, root_is_repo=False)
    assert "⚠ This repository has no licence file, so nothing says what you may do with it." in texts(page)
    assert page.licence_box() is None and page.tick() is not None and not page.primary_button().isEnabled()


def test_add_preview_licence_known_on_the_page_is_one_line(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source("CC-BY-SA-4.0"))
    page.show_staged(staged_of(plan), plan, root_is_repo=False, licence_confirmed=True)
    assert "Licence: CC BY-SA 4.0 (you confirmed you read the terms)" in texts(page)
    assert page.tick() is None and page.primary_button().isEnabled()


def test_reinstall_preview_lists_only_the_folder(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source(None, proprietary=True), reinstall=True, ack_on="2026-11-20", acknowledged=True, gitignore="append")
    page.show_staged(staged_of(plan), plan, root_is_repo=True)
    assert page.heading_text() == "Reinstall Acme"
    assert page.primary_button().text() == "Reinstall Library"
    assert [path for path, _ in page.what_rows()] == ["/collection/ThirdParty/Acme/"]
    assert page.tick() is None and page.primary_button().isEnabled()


def test_add_preview_name_override_and_notice(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of()
    page.show_staged(staged_of(plan), plan, root_is_repo=False, name="acme/parts")
    assert page.heading_text() == "Add acme/parts"
    page.show_notice("Could not add acme/parts: the record could not be written.")
    assert "✖ Could not add acme/parts: the record could not be written." in texts(page)


def test_preview_kicad_open_line(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(kicad_open=("kicad.exe",))
    page.show_staged(staged_of(plan), plan, root_is_repo=False)
    assert "⚠ KiCad is open (kicad.exe). Restart it after the library is added to see the changes." in texts(page)


# -- Refusals after a download ------------------------------------------------------------------


def test_refusal_mode(qtbot):
    page = build(qtbot, cp.AddPreviewPage())
    issue = Issue(Severity.ERROR, "catalog.lfs", "This library keeps its 3D models in Git LFS, which the catalog does not support. Nothing was added.")
    page.show_refusal(issue, can_retry=False, heading="Add Acme")
    assert page.is_refusal() and page.heading_text() == "Add Acme"
    assert "✖ " + issue.text in texts(page)
    assert "Nothing was added. The downloaded copy was deleted." in texts(page)
    assert page.back_button().text() == "Back to List" and page.back_button().toolTip() == ""
    assert page.primary_button().isHidden()
    page.show_refusal(Issue(Severity.ERROR, "git.clone_failed", "The download failed: offline"), can_retry=True)
    assert not page.primary_button().isHidden() and page.primary_button().text() == "Try Again"
    assert page.primary_button().isEnabled()


# -- The collapsible list -----------------------------------------------------------------------


def test_collapsible_list(qtbot):
    lst = cp.CollapsibleList("Libraries that leave your scan")
    qtbot.addWidget(lst)
    lst.set_rows([("A",), ("B",)])
    assert lst.heading_text() == "Libraries that leave your scan (2)"
    assert lst.toggle().isHidden() and lst.is_expanded()
    lst.set_rows([(f"Library_{n}",) for n in range(5)])
    assert lst.heading_text() == "Libraries that leave your scan (5)"
    assert not lst.toggle().isHidden() and lst.toggle().text() == "Show"
    assert not lst.is_expanded()
    lst.toggle().setChecked(True)
    assert lst.is_expanded() and lst.toggle().text() == "Hide"
    lst.set_rows([(f"Library_{n}_" + "x" * 80,) for n in range(40)])
    tree = lst.tree()
    row = tree.sizeHintForRow(0)
    assert tree.maximumHeight() <= 6 * row + 2 * tree.frameWidth() + 4
    assert tree.textElideMode() == Qt.TextElideMode.ElideRight
    assert tree.topLevelItem(0).toolTip(0) == tree.topLevelItem(0).text(0)
    assert lst.row_count() == 40
    lst.set_rows([])
    assert lst.row_count() == 0 and lst.heading_text() == "Libraries that leave your scan (0)"


def test_collapsible_list_that_never_collapses(qtbot):
    lst = cp.CollapsibleList("", ("Library", "Kind"), collapse=False)
    qtbot.addWidget(lst)
    lst.set_rows([(f"L{n}", "Symbol") for n in range(9)])
    assert lst.toggle().isHidden() and lst.is_expanded() and lst.heading_text() == ""
    assert lst.tree().maximumHeight() < 9 * lst.tree().sizeHintForRow(0)


def test_amber_list_text(qtbot):
    lst = cp.CollapsibleList("Libraries removed")
    qtbot.addWidget(lst)
    lst.set_rows([("Gone",)], token=theme.AMBER)
    assert lst.tree().topLevelItem(0).foreground(0).color().name().upper() == "#8A5200"


# -- Whole-page rules ---------------------------------------------------------------------------


def all_pages(qtbot):
    url = build(qtbot, cp.AddByUrlPage())
    url.field().setText("https://github.com/acme/parts")
    licence = build(qtbot, cp.LicencePage())
    licence.show_plan(plan_of(source("MIT")))
    preview = build(qtbot, cp.AddPreviewPage())
    plan = plan_of(source("MIT"))
    preview.show_staged(staged_of(plan), plan, root_is_repo=False)
    return url, licence, preview


def test_one_primary_button_per_page(qtbot):
    for page in all_pages(qtbot):
        accent = [b for b in page.findChildren(QPushButton) if b.styleSheet() == theme.PRIMARY_BUTTON_QSS and not b.isHidden()]
        assert len(accent) == 1, page
        plain = [b for b in page.findChildren(QPushButton) if b.styleSheet() == "" and not b.isHidden()]
        assert len(plain) == 1  # Back to List or Discard Download
        assert all(not b.autoDefault() and not b.isDefault() for b in page.findChildren(QPushButton))


def test_plain_text_labels(qtbot):
    name = "R&D <Parts>"
    page = build(qtbot, cp.LicencePage())
    page.show_plan(plan_of(), name=name)
    assert page.heading_text() == f"Add {name}"
    for label in page.findChildren(QLabel):
        if isinstance(label, cp.LinkLabel):
            continue
        assert label.textFormat() == Qt.TextFormat.PlainText, label.text()
    preview = build(qtbot, cp.AddPreviewPage())
    plan = plan_of()
    preview.show_staged(staged_of(plan, collisions=CLASHES), plan, root_is_repo=True, name=name)
    assert preview.heading_text() == f"Add {name}"
    for label in preview.findChildren(QLabel):
        assert label.textFormat() == Qt.TextFormat.PlainText, label.text()


def test_destructive_button_qss_matches_the_primary_metrics():
    qss = cp.destructive_button_qss()
    assert theme.ERROR in qss and "color: white" in qss and "font-weight: bold" in qss
    for part in ("padding: 8px 16px", "min-height: 12px"):
        assert part in qss and part in theme.PRIMARY_BUTTON_QSS
    assert theme.ACCENT not in qss


def test_focus_goes_to_the_first_input(qtbot):
    url, licence, preview = all_pages(qtbot)
    for page in (url, licence, preview):
        page.show()
        page.focus_first()
    assert url.focusWidget() is url.field()
    plan = plan_of(source("CC-BY-SA-4.0"))
    licence.show_plan(plan)
    qtbot.wait(20)  # a widget added to a shown page is shown by a queued event
    licence.focus_first()
    assert licence.focusWidget() is licence.tick()
    licence.tick().setChecked(True)
    assert licence.primary_button().isEnabled()
