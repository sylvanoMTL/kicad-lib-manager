"""The scratch switch for owner checks (Phase 17, D-35): --scratch-root / KICAD_LIBMGR_SCRATCH_ROOT.

Every folder in these tests is a temp folder of the test. The per-test user folders of conftest.py stand in
for the owner's real ones: a test seeds them, runs the switch and shows they were not read or written.
"""

import os
from pathlib import Path

import pytest
from collectionfixtures import make_collection

from kicad_lib_manager import main_window, settings, startup
from kicad_lib_manager.models import ScanResult
from kicad_lib_manager.widgets.log_panel import COLORS

SCRATCH_LINE = (
    "Working in the scratch folder {folder}: the app's settings, saved scans and backups and KiCad's "
    "settings are read and written there, and your real ones are not touched."
)


@pytest.fixture
def seams(monkeypatch, tmp_path):
    """Replace everything the window reaches outside its library folder (as tests/test_startup.py does)."""
    config_base = tmp_path / "kicad_cfg"
    config_base.mkdir()
    fp_dir = tmp_path / "kicad_fp"
    fp_dir.mkdir()

    def fake_scan(root, progress=None, kicad_fp_dir=None, *, skip=None, checking=None, model_vars=None, prefixes=None):
        return ScanResult()

    monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
    monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
    monkeypatch.setattr(main_window, "scan_all", fake_scan)
    monkeypatch.setattr(main_window, "checkout_mismatch", lambda root, *, config_base=None: None)
    monkeypatch.setattr(main_window, "sync_kicad_path_vars", lambda *a, **k: [])
    monkeypatch.setattr(main_window, "kicad_running", lambda: [])
    monkeypatch.setattr(main_window.MainWindow, "_question", lambda self, *a: None)


def start(qtbot, argv=(), environ=None, **kwargs):
    kwargs.setdefault("first_run", lambda resolution: None)
    outcome = startup.start_window(["kicad_lib_manager.py", *argv], environ or {}, **kwargs)
    if not isinstance(outcome, int):
        qtbot.addWidget(outcome)
        qtbot.waitUntil(lambda: outcome._worker is None, timeout=30000)
    return outcome


def log_lines(window) -> list[str]:
    return [line.split("] ", 1)[-1] for line in window._log._text.toPlainText().splitlines()]


def scratch_state():
    """The scratch folder the switch holds right now (looked up late: the module is new in this plan)."""
    from kicad_lib_manager import userdirs

    return userdirs.scratch_root()


def _under(path, folder) -> bool:
    return Path(os.path.abspath(path)).is_relative_to(Path(os.path.abspath(folder)))


def test_scratch_root_moves_the_settings(seams, qtbot, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    root = make_collection(tmp_path / "lib")
    per_test_ini = Path(settings.get_settings().fileName())

    window = start(qtbot, ["--scratch-root", str(scratch), "--library-root", str(root)])

    assert not isinstance(window, int)
    store = settings.get_settings()
    store.sync()
    ini = Path(store.fileName())
    assert _under(ini, scratch / "settings")
    assert ini.exists()  # the library folder joined Recent Library Collections in the scratch ini
    assert settings.load_library_recent()[0] == str(root)
    assert _under(settings.scan_cache_file(root), scratch / "settings")
    assert _under(settings.addon_index_file(), scratch / "settings")
    assert _under(settings.migration_draft_file(root), scratch / "settings")
    # The per-test qsettings folder of conftest.py got no file
    assert not per_test_ini.exists()
    assert not per_test_ini.parent.exists()


def test_scratch_line_is_logged_first(seams, qtbot, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    root = make_collection(tmp_path / "lib")

    window = start(qtbot, ["--scratch-root", str(scratch), "--library-root", str(root)])

    assert log_lines(window)[0] == SCRATCH_LINE.format(folder=scratch)
    assert COLORS["warning"].lower() in window._log._text.toHtml().lower()


def test_without_the_switch_nothing_moves(seams, qtbot, tmp_path):
    root = make_collection(tmp_path / "lib")
    per_test_ini = Path(settings.get_settings().fileName())

    window = start(qtbot, ["--library-root", str(root)])

    assert not isinstance(window, int)
    assert Path(settings.get_settings().fileName()) == per_test_ini
    assert scratch_state() is None
    assert not log_lines(window)[0].startswith("Working in the scratch folder")


def test_the_scratch_state_is_cleared_between_tests():
    # A test that set the switch must not leak it to the next one (the autouse reset of conftest.py)
    assert scratch_state() is None
