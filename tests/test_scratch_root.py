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


# -- Task 2: backups and KiCad's settings folder follow the switch -------------------------------


def _snapshot(*folders: Path) -> dict[str, tuple[int, int]]:
    """Every file under the folders as {path: (size, modification time)}; an absent folder counts as empty."""
    found = {}
    for folder in folders:
        for path in sorted(folder.rglob("*")) if folder.exists() else []:
            if path.is_file():
                stat = path.stat()
                found[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return found


def _user_folders() -> dict[str, Path]:
    """The per-test stand-ins for the owner's real folders (conftest.py gives every test its own)."""
    qsettings = Path(settings.get_settings().fileName()).parent.parent
    return {
        "APPDATA": Path(os.environ["APPDATA"]),
        "LOCALAPPDATA": Path(os.environ["LOCALAPPDATA"]),
        "KICAD_CONFIG_HOME": Path(os.environ["KICAD_CONFIG_HOME"]),
        "qsettings": qsettings,
    }


def _kicad_json(folder: Path, text: str = '{"environment": {"vars": {}}}\n') -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "kicad_common.json"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_backups_go_to_the_scratch_folder(tmp_path):
    from kicad_lib_manager import fsutil, userdirs

    local = tmp_path / "local"
    before = fsutil.default_backup_dir(platform="win32", environ={"LOCALAPPDATA": str(local)})
    assert before == local / "KiCadExtLibManager" / "backups"

    scratch = tmp_path / "scratch"
    userdirs.set_scratch_root(scratch)
    for platform in ("win32", "darwin", "linux"):
        assert fsutil.default_backup_dir(platform=platform, environ={"LOCALAPPDATA": str(local)}) == scratch / "backups"
    assert fsutil.default_backup_dir() == scratch / "backups"

    userdirs.set_scratch_root(None)
    assert fsutil.default_backup_dir(platform="win32", environ={"LOCALAPPDATA": str(local)}) == before


def test_kicad_settings_come_from_the_scratch_folder(tmp_path):
    from kicad_lib_manager import library_scanner, userdirs

    # The per-test APPDATA holds a KiCad folder too: it must not be the one found
    real = _kicad_json(Path(os.environ["APPDATA"]) / "kicad" / "10.0").parent
    assert library_scanner.find_kicad_config_dir() == real

    scratch = tmp_path / "scratch"
    (scratch / "kicad").mkdir(parents=True)
    userdirs.set_scratch_root(scratch)
    # An empty scratch KiCad folder: KiCad's settings are not found, never the real ones
    assert library_scanner.find_kicad_config_dir() is None

    mine = _kicad_json(scratch / "kicad" / "10.0").parent
    assert library_scanner.find_kicad_config_dir() == mine
    # An explicit base still wins
    other = tmp_path / "other"
    wanted = _kicad_json(other / "9.0").parent
    assert library_scanner.find_kicad_config_dir(other) == wanted


def test_real_folders_are_never_touched(seams, qtbot, tmp_path):
    from kicad_lib_manager import library_scanner

    folders = _user_folders()
    # Seed every stand-in for a real folder with a KiCad settings file and a settings ini
    _kicad_json(folders["APPDATA"] / "kicad" / "10.0")
    _kicad_json(folders["LOCALAPPDATA"] / "KiCadExtLibManager" / "backups" / "kicad_common" / "10.0")
    _kicad_json(folders["KICAD_CONFIG_HOME"] / "10.0")
    store = settings.get_settings()
    store.setValue("seed", "real")
    store.sync()
    before = _snapshot(*folders.values())
    assert len(before) >= 4

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    root = make_collection(tmp_path / "lib")
    window = start(qtbot, ["--scratch-root", str(scratch), "--library-root", str(root)])
    assert not isinstance(window, int)

    settings.save_library_root(root)
    cache = settings.scan_cache_file(root)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{}", encoding="utf-8")
    index = settings.addon_index_file()
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("{}", encoding="utf-8")
    settings.get_settings().sync()

    # KiCad's settings: found in the scratch folder, written there, backed up under the scratch backups
    config = _kicad_json(scratch / "kicad" / "10.0")
    issues = library_scanner.sync_kicad_path_vars(root, running=lambda: [], confirm=lambda changes: True)
    assert not [i for i in issues if i.severity.value in ("warning", "error")], issues
    assert "KICAD_LIB_GITHUB" in config.read_text(encoding="utf-8")
    assert any((scratch / "backups" / "kicad_common" / "10.0").iterdir())
    assert Path(os.environ["KICAD_CONFIG_HOME"]) == scratch / "kicad"

    # Nothing in the real folders changed, and nothing new appeared there
    assert _snapshot(*folders.values()) == before
    # Everything the run created outside the collection is under the scratch folder
    created = _snapshot(scratch)
    for needed in (config, cache, index, scratch / "settings"):
        assert any(_under(path, needed) for path in created), needed
