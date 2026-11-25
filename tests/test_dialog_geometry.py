"""Geometry of the New Collection and Choose Library Folder dialogs (Phase 15-14, UAT gap 3).

An explicit minimum width stops the layout from raising a window's minimum height, and a top-level window
ignores height-for-width, so before the fix the footnote was drawn over the preview and a wrapped strip row
kept a one-line height. These tests assert the geometry in process (default scale) and in a child process at
QT_SCALE_FACTOR 1.75.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import geometryfixtures as gf

REPO_ROOT = Path(__file__).resolve().parent.parent
CHILD = Path(__file__).with_name("dialoggeometrychild.py")
EXPECTED_CASES = gf.ALL_CASES


def _settle_nc(qtbot, dialog):
    dialog.show()
    qtbot.waitUntil(lambda: not dialog._pending, timeout=30000)
    qtbot.wait(50)


def _settle_choose(qtbot, dialog):
    dialog.show()
    qtbot.waitUntil(lambda: not dialog._pending and dialog._result is not None, timeout=30000)
    qtbot.wait(50)


def _assert_fits(dialog):
    assert gf.overlapping_children(dialog) == []
    assert gf.clipped_wrapped_labels(dialog) == []
    assert gf.missing_height(dialog) <= 0


@pytest.mark.parametrize("case", gf.NC_CASES)
def test_new_collection_fits(qtbot, tmp_path, case):
    dialog = gf.new_collection_case(case, tmp_path)
    qtbot.addWidget(dialog)
    _settle_nc(qtbot, dialog)
    if case == "nc-issues":
        assert dialog._strip.isVisible()
        assert any("characters long" in label.text() for label in dialog._issue_labels())
    _assert_fits(dialog)
    assert dialog._footnote.geometry().top() > dialog._preview.geometry().bottom()


def test_new_collection_cannot_be_shorter_than_its_content(qtbot, tmp_path):
    dialog = gf.new_collection_case("nc-issues", tmp_path)
    qtbot.addWidget(dialog)
    _settle_nc(qtbot, dialog)
    needed = gf.needed_height(dialog)
    dialog.resize(560, 10)
    qtbot.wait(50)
    assert dialog.height() >= needed
    _assert_fits(dialog)
    assert dialog._footnote.geometry().top() > dialog._preview.geometry().bottom()


@pytest.mark.parametrize("case", ["choose-main", "choose-setup"])
def test_choose_rows_shown_in_full(qtbot, tmp_path, case):
    dialog = gf.choose_case(case, tmp_path)
    qtbot.addWidget(dialog)
    _settle_choose(qtbot, dialog)
    labels = dialog._row_labels()
    assert len(labels) == 4
    _assert_fits(dialog)
    assert gf.overlapping_children(dialog._strip) == []
    assert labels[-1].height() > labels[0].height()  # the warning wraps, so it is taller than a pass row
    assert dialog.width() <= 560


def test_choose_failure_row_shown_in_full(qtbot, tmp_path):
    dialog = gf.choose_case("choose-failure", tmp_path)
    qtbot.addWidget(dialog)
    _settle_choose(qtbot, dialog)
    labels = dialog._row_labels()
    assert [label.accessibleName() for label in labels] == ["✖ " + gf.LONG_FAIL_ROW]
    _assert_fits(dialog)
    assert labels[0].height() >= labels[0].heightForWidth(labels[0].width())


def test_choose_grows_when_rows_arrive(qtbot, tmp_path):
    from kicad_lib_manager.widgets.choose_folder_dialog import ChooseLibraryFolderDialog

    folder = tmp_path / "collection"
    folder.mkdir()
    dialog = ChooseLibraryFolderDialog(None, origin="setup", check=gf.fake_choose_check(gf.choose_rows()))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(50)
    before = dialog.height()
    dialog._field.setText(str(folder))
    qtbot.waitUntil(lambda: not dialog._pending and dialog._result is not None, timeout=30000)
    qtbot.wait(50)
    assert dialog.height() > before
    _assert_fits(dialog)


def test_dialogs_fit_at_175_percent(tmp_path):
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "QT_SCALE_FACTOR": "1.75",
        "APPDATA": str(tmp_path / "appdata"),
        "LOCALAPPDATA": str(tmp_path / "localappdata"),
        "USERPROFILE": str(tmp_path / "home"),
        "HOME": str(tmp_path / "home"),
    }
    result = subprocess.run(
        [sys.executable, str(CHILD), str(tmp_path / "work")],
        capture_output=True,
        text=True,
        timeout=90,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    records = {}
    for line in result.stdout.splitlines():
        if line.startswith("{"):
            record = json.loads(line)
            records[record["case"]] = record
    assert sorted(records) == sorted(EXPECTED_CASES), result.stdout + result.stderr
    for case, record in records.items():
        assert abs(record["dpr"] - 1.75) < 0.01, f"{case}: dpr {record['dpr']}"
        assert record["overlaps"] == [], f"{case}: {record}"
        assert record["clipped"] == [], f"{case}: {record}"
        assert record["missing_height"] <= 0, f"{case}: {record}"
