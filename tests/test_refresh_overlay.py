"""The refreshing overlay and its spinning wheel (Phase 17 plan 23; owner finding 2 of 17-17, T-17-57).

Offscreen only. The wheel's timer must run only while the overlay is shown and must never outlive its window.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from kicad_lib_manager.widgets import refresh_overlay
from kicad_lib_manager.widgets.refresh_overlay import RefreshOverlay


@pytest.fixture
def parts(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(640, 400)
    parent.show()
    return parent, RefreshOverlay(parent)


def test_wheel_turns_only_while_shown(qtbot, parts):
    parent, overlay = parts
    wheel = overlay.wheel
    assert not wheel.is_spinning()

    overlay.show_for("add", "Acme")
    assert wheel.is_spinning()
    start = wheel.angle()
    qtbot.waitUntil(lambda: wheel.angle() != start, timeout=3000)

    overlay.finish()
    assert not wheel.is_spinning()
    stopped = wheel.angle()
    qtbot.wait(150)
    assert wheel.angle() == stopped

    overlay.show_for("update", "Acme")
    assert wheel.is_spinning()
    parent.close()
    assert not wheel.is_spinning()


def test_wheel_stops_when_the_parent_is_hidden(parts):
    parent, overlay = parts
    overlay.show_for("remove", "Acme")
    assert overlay.wheel.is_spinning()

    parent.hide()

    assert not overlay.wheel.is_spinning()


@pytest.mark.parametrize(
    ("kind", "verb"),
    [("add", "adding"), ("reinstall", "reinstalling"), ("update", "updating"), ("remove", "removing")],
)
def test_texts_per_kind(parts, kind, verb):
    _parent, overlay = parts

    overlay.show_for(kind, "Acme")

    assert overlay.text() == f"Refreshing the library list after {verb} Acme. Large libraries can take a minute."
    assert overlay.isVisibleTo(overlay.parent())


def test_a_name_is_shown_as_typed(parts):
    _parent, overlay = parts

    overlay.show_for("add", "Fish & <b>Chips</b>")

    assert overlay.text() == "Refreshing the library list after adding Fish & <b>Chips</b>. Large libraries can take a minute."
    assert overlay._label.textFormat() == Qt.TextFormat.PlainText


def test_bar_and_count(parts):
    _parent, overlay = parts
    overlay.show_for("add", "Acme")
    # before the first count the bar only moves and the count is empty
    assert overlay.is_indeterminate()
    assert overlay.count_text() == ""

    overlay.set_progress(0, 0)
    assert overlay.is_indeterminate()
    assert overlay.count_text() == ""

    overlay.set_progress(4210, 11050)
    assert not overlay.is_indeterminate()
    assert (overlay.bar_value(), overlay.bar_maximum()) == (38, 100)
    assert overlay.count_text() == "4,210 of 11,050 files"

    overlay.set_progress(11050, 11050)
    assert overlay.bar_value() == 100

    # a new refresh starts from the moving bar again
    overlay.show_for("update", "Acme")
    assert overlay.is_indeterminate()
    assert overlay.count_text() == ""


def test_overlay_covers_its_parent(parts):
    parent, overlay = parts
    overlay.show_for("add", "Acme")
    assert overlay.size() == parent.size()

    parent.resize(900, 520)

    assert overlay.size() == parent.size()
    assert overlay.pos() == parent.rect().topLeft()


def test_accessible_names(parts):
    _parent, overlay = parts

    assert overlay.accessibleName() == "Refreshing the library list"
    assert overlay._bar.accessibleName() == "Progress of refreshing the library list"


def test_the_wheel_is_large(parts):
    _parent, overlay = parts
    overlay.show_for("add", "Acme")

    assert overlay.wheel.width() >= 96
    assert overlay.wheel.height() >= 96
    assert refresh_overlay.WHEEL_SIZE >= 96
