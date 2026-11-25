"""The remembered library folder and the recent list (plan 15-05): library/root and library/recent through settings.py."""

import os
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from kicad_lib_manager import settings


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path):
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path / "qsettings"),
    )
    file_name = Path(settings.get_settings().fileName()).resolve()
    assert tmp_path.resolve() in file_name.parents


def test_nothing_stored_gives_none_and_empty():
    assert settings.load_library_root() is None
    assert settings.load_library_recent() == []


def test_root_round_trip_keeps_odd_characters(tmp_path):
    folder = tmp_path / "R&D, Parts" / "Kicad"
    settings.save_library_root(folder)
    assert settings.load_library_root() == folder
    assert str(settings.load_library_root()) == str(folder)


def test_root_is_returned_even_when_missing(tmp_path):
    folder = tmp_path / "gone"
    settings.save_library_root(folder)
    assert not folder.exists()
    assert settings.load_library_root() == folder


def test_root_list_value_is_handled(tmp_path):
    s = settings.get_settings()
    s.setValue("library/root", [str(tmp_path / "a"), str(tmp_path / "b")])
    assert settings.load_library_root() == tmp_path / "a"
    s.setValue("library/root", 42)
    assert settings.load_library_root() is None
    s.setValue("library/root", "   ")
    assert settings.load_library_root() is None
    s.setValue("library/root", [])
    assert settings.load_library_root() is None


def test_clear_removes_the_key(tmp_path):
    settings.save_library_root(tmp_path)
    settings.clear_library_root()
    assert not settings.get_settings().contains("library/root")
    assert settings.load_library_root() is None


def test_recent_newest_first_and_deduplicated(tmp_path):
    a = str(tmp_path / "a")
    b = str(tmp_path / "b")
    settings.add_library_recent(Path(a))
    settings.add_library_recent(Path(b))
    result = settings.add_library_recent(Path(a))
    assert result == [a, b]
    assert settings.load_library_recent() == [a, b]


def test_recent_same_folder_other_spelling_keeps_newest(tmp_path):
    first = str(tmp_path / "x" / "lib")
    second = str(tmp_path / "x" / "." / "lib")
    settings.add_library_recent(Path(first))
    result = settings.add_library_recent(Path(second))
    assert len(result) == 1
    assert result[0] == str(Path(second))
    if sys.platform == "win32":
        upper = str(tmp_path / "X" / "LIB")
        result = settings.add_library_recent(Path(upper))
        assert result == [upper]
        assert os.path.normcase(upper) == os.path.normcase(first)


def test_recent_is_capped_at_ten(tmp_path):
    for i in range(12):
        settings.add_library_recent(tmp_path / f"lib{i}")
    recent = settings.load_library_recent()
    assert len(recent) == 10
    assert recent[0] == str(tmp_path / "lib11")
    assert recent[-1] == str(tmp_path / "lib2")


def test_recent_single_and_empty(tmp_path):
    s = settings.get_settings()
    s.setValue("library/recent", [str(tmp_path / "one")])
    assert settings.load_library_recent() == [str(tmp_path / "one")]
    s.setValue("library/recent", [])
    assert settings.load_library_recent() == []
    s.setValue("library/recent", str(tmp_path / "single"))
    assert settings.load_library_recent() == [str(tmp_path / "single")]
    s.setValue("library/recent", [str(tmp_path / "ok"), 7, "", "  "])
    assert settings.load_library_recent() == [str(tmp_path / "ok")]


def test_recent_keeps_commas_and_ampersands(tmp_path):
    odd = tmp_path / "R&D, Parts"
    settings.add_library_recent(odd)
    settings.add_library_recent(tmp_path / "plain")
    assert settings.load_library_recent() == [str(tmp_path / "plain"), str(odd)]


def test_recent_display_never_rewrites(tmp_path):
    gone = tmp_path / "gone"
    settings.add_library_recent(gone)
    assert not gone.exists()
    assert settings.load_library_recent() == [str(gone)]
