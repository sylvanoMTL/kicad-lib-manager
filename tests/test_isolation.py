"""Meta-tests for the parallel test harness (Phase 14): shared git template, timeouts, user-state isolation."""

import ast
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest
from gitfixtures import requires_git
from runfixtures import REPO_ROOT, run_pytest, write_tree

_HANG = "import time\n\n\ndef test_hangs():\n    time.sleep(60)\n"


def _tail(done) -> str:
    return (done.stdout + done.stderr)[-3000:]


@pytest.mark.slow
@requires_git
def test_templates_are_built_once(tmp_path):
    """Four workers ask for the same git template at once: exactly one builds it, none leaks a folder."""
    tests = "".join(
        f"def test_build_{n}(tmp_path):\n"
        "    repos = make_superproject(tmp_path / 'r')\n"
        "    assert (repos.custom / 'Symbols').is_dir()\n\n\n"
        for n in range(4)
    )
    run_dir = write_tree(
        tmp_path / "run",
        {
            "test_git_build.py": "import pytest\n"
            "from gitfixtures import make_superproject\n\n"
            "pytestmark = pytest.mark.slow\n\n\n" + tests
        },
    )

    done = run_pytest(
        run_dir, "-n", "4", basetemp=tmp_path / "bt", env={"GITFIXTURES_BUILD_LOG": str(tmp_path / "builds.txt")}
    )

    assert done.returncode == 0, _tail(done)
    assert "4 passed" in done.stdout, _tail(done)
    assert "4 workers" in done.stdout, _tail(done)
    builds = (tmp_path / "builds.txt").read_text(encoding="utf-8").splitlines()
    assert len(builds) == 1 and builds[0].startswith("template_lf "), builds
    assert not (tmp_path / "bt" / "git_templates").exists()


def test_hung_test_fails_naming_it(tmp_path):
    """Under workers a hung test fails the run within seconds, and the report says TIMEOUT and gives its node id."""
    run_dir = write_tree(tmp_path / "run", {"test_hang.py": _HANG})

    start = time.monotonic()
    done = run_pytest(run_dir, "-n", "2", "--timeout", "2", basetemp=tmp_path / "bt")
    elapsed = time.monotonic() - start

    assert done.returncode != 0, _tail(done)
    assert "TIMEOUT test_hang.py::test_hangs after 2 s" in done.stdout, _tail(done)
    assert "crashed while running" in done.stdout, _tail(done)
    assert elapsed < 30, elapsed


def test_hung_test_fails_naming_it_serially(tmp_path):
    """Serially pytest-timeout's own banner and stack dump name the hung test function."""
    run_dir = write_tree(tmp_path / "run", {"test_hang.py": _HANG})

    start = time.monotonic()
    done = run_pytest(run_dir, "-n", "0", "--timeout", "2", basetemp=tmp_path / "bt")
    elapsed = time.monotonic() - start

    assert done.returncode != 0, _tail(done)
    assert "Timeout" in done.stdout + done.stderr, _tail(done)
    assert "test_hangs" in done.stdout + done.stderr, _tail(done)
    assert elapsed < 30, elapsed


# A registered widget whose timer, or whose worker's queued result, starts a slow worker after its test body ended
_WIDGET_LIFETIME = '''import time

import shiboken6
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QWidget

_EVENTS = []
_WIDGETS = {}


class _Worker(QThread):
    def __init__(self, name, seconds, parent):
        super().__init__(parent)
        self._name, self._seconds = name, seconds

    def run(self):
        _EVENTS.append(f"start {self._name}")
        time.sleep(self._seconds)
        _EVENTS.append(f"end {self._name}")


class _TimerOwner(QWidget):
    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: _Worker("timer", 1.0, self).start())


class _ChainOwner(QWidget):
    def __init__(self):
        super().__init__()
        self.first = _Worker("first", 0.3, self)
        self.first.finished.connect(lambda: _Worker("second", 1.0, self).start())


def test_timer_pending_at_the_end(qtbot):
    owner = _TimerOwner()
    qtbot.addWidget(owner)
    owner.timer.start(300)
    _WIDGETS["timer"] = owner


def test_the_timer_is_due_now(qtbot):
    assert not shiboken6.isValid(_WIDGETS["timer"])
    time.sleep(0.6)
    QApplication.processEvents()
    qtbot.wait(20)
    assert _EVENTS == []


def test_worker_result_starts_another_in_teardown(qtbot):
    owner = _ChainOwner()
    qtbot.addWidget(owner)
    owner.first.start()
    _WIDGETS["chain"] = owner


def test_after_the_chain(qtbot):
    assert not shiboken6.isValid(_WIDGETS["chain"])
    qtbot.wait(20)
    assert _EVENTS == ["start first", "end first", "start second", "end second"]
'''


def test_registered_widget_ends_in_its_own_test(tmp_path):
    """A widget the test registered is destroyed in its own teardown, after every thread it started has ended.

    Neither a pending timer nor a worker started during teardown may act in the next test or be destroyed while
    it runs (Qt then ends the whole process: "QThread: Destroyed while thread is still running").
    """
    run_dir = write_tree(tmp_path / "run", {"test_widget_lifetime.py": _WIDGET_LIFETIME})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt")

    assert done.returncode == 0, _tail(done)
    assert "4 passed" in done.stdout, _tail(done)


def test_timeout_config():
    """pyproject pins the quick-run defaults, and the Wurth budget test carries a timeout above its budget."""
    ini = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert int(ini["timeout"]) == 300
    assert ini["timeout_method"] == "thread"
    assert "--strict-markers" in ini["addopts"]
    assert "-m 'not slow'" in ini["addopts"]
    assert any(marker.startswith("slow:") for marker in ini["markers"])

    tree = ast.parse((REPO_ROOT / "tests" / "test_roundtrip_corpus.py").read_text(encoding="utf-8"))
    func = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "test_wurth_corpus_parse_budget"
    )
    seconds = [
        deco.args[0].value
        for deco in func.decorator_list
        if isinstance(deco, ast.Call) and ast.unparse(deco.func) == "pytest.mark.timeout" and deco.args
    ]
    assert seconds, "test_wurth_corpus_parse_budget has no pytest.mark.timeout(...)"
    assert isinstance(seconds[0], int) and seconds[0] >= 600


# ── Per-test user-state isolation ─────────────────────────────────────────────────


def _under(path, base) -> bool:
    return Path(path).resolve().is_relative_to(base)


def test_user_state_is_redirected(tmp_path_factory):
    """Every place the app or a child process looks for user state lies under this run's base temp."""
    from kicad_lib_manager import settings
    from kicad_lib_manager.fsutil import default_backup_dir
    from kicad_lib_manager.library_scanner import find_kicad_config_dir

    base = tmp_path_factory.getbasetemp().resolve()
    for name in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "KICAD_CONFIG_HOME"):
        assert _under(os.environ[name], base), name
    assert _under(Path.home(), base)
    assert _under(settings.get_settings().fileName(), base)
    assert _under(settings.scan_cache_file(REPO_ROOT), base)
    assert _under(default_backup_dir(), base)
    assert find_kicad_config_dir() is None
    for name in ("KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "WE_3DMODEL_DIR"):
        assert name not in os.environ, name

    # A child process (kicad-cli is started like this, with no env=) inherits the per-test config folder
    done = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ.get('KICAD_CONFIG_HOME', ''))"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() and _under(done.stdout.strip(), base), done.stdout


_FAKE_KICAD_VARS = {
    "KICAD_LIB_GITHUB": "C:/fake/kicad_lib_github",
    "CUSTOM_3DMODEL_DIR": "C:/fake/custom_3d",
    "KICAD_CONFIG_HOME": "C:/fake/kicad_config",
    "WE_3DMODEL_DIR": "C:/fake/we_3d",
}

_CLEARED_TEST = (
    "import os\n"
    "from pathlib import Path\n\n\n"
    "def test_variables(tmp_path_factory):\n"
    "    assert 'KICAD_LIB_GITHUB' not in os.environ\n"
    "    assert 'CUSTOM_3DMODEL_DIR' not in os.environ\n"
    "    assert 'WE_3DMODEL_DIR' not in os.environ\n"
    "    config = os.environ['KICAD_CONFIG_HOME']\n"
    "    assert config != 'C:/fake/kicad_config'\n"
    "    assert Path(config).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve())\n"
)


def test_kicad_variables_are_cleared_even_when_set(tmp_path):
    """A shell that set the KiCad variables does not reach a test: three are removed, KICAD_CONFIG_HOME is re-pointed."""
    run_dir = write_tree(tmp_path / "run", {"test_cleared.py": _CLEARED_TEST})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt", env=_FAKE_KICAD_VARS)

    assert done.returncode == 0, _tail(done)
    assert "1 passed" in done.stdout, _tail(done)


_LEAK_TEST = (
    "from kicad_lib_manager import settings\n\n\n"
    "def _write():\n"
    "    store = settings.get_settings()\n"
    "    store.setValue('phase14_probe', 'written')\n"
    "    store.sync()\n\n\n"
    "def _read():\n"
    "    assert settings.get_settings().value('phase14_probe') is None\n\n\n"
    "def test_write_1():\n    _write()\n\n\n"
    "def test_read_2():\n    _read()\n\n\n"
    "def test_write_3():\n    _write()\n\n\n"
    "def test_read_4():\n    _read()\n"
)


def test_settings_do_not_leak_between_tests(tmp_path):
    """A value one test writes to the settings is never seen by a later test, serially or under workers, and no folder is left."""
    for workers in ("0", "2"):
        run_dir = write_tree(tmp_path / f"run{workers}", {"test_leak.py": _LEAK_TEST})
        base = tmp_path / f"bt{workers}"

        done = run_pytest(run_dir, "-n", workers, basetemp=base)

        assert done.returncode == 0, _tail(done)
        assert "4 passed" in done.stdout, _tail(done)
        left = sorted(base.glob("**/user[0-9]*")) + sorted(base.glob("**/qsettings_session[0-9]*"))
        assert left == [], left


@pytest.mark.kicad_cli
def test_kicad_cli_uses_the_test_config_folder(kicad_cli_path):
    """kicad-cli, started with no env=, writes its config into the per-test KICAD_CONFIG_HOME folder only."""
    done = subprocess.run([str(kicad_cli_path), "version"], capture_output=True, timeout=120)

    assert done.returncode == 0, done.stderr
    assert any(Path(os.environ["KICAD_CONFIG_HOME"]).glob("*/kicad_common.json"))


# ── Run-level user-state guard ────────────────────────────────────────────────────


def _fake_user_state(tmp_path):
    """A fake owner profile for a child run: its environment, the app's settings.ini and a KiCad config file."""
    if sys.platform == "win32":
        roaming, local = tmp_path / "Roaming", tmp_path / "Local"
        env = {"APPDATA": str(roaming), "LOCALAPPDATA": str(local)}
        app_dir, kicad_dir = roaming / "KiCadExtLibManager", roaming / "kicad"
    elif sys.platform == "darwin":
        env = {"HOME": str(tmp_path / "Home")}
        app_dir = tmp_path / "Home" / ".config" / "KiCadExtLibManager"
        kicad_dir = tmp_path / "Home" / "Library" / "Preferences" / "kicad"
    else:
        env = {"XDG_CONFIG_HOME": str(tmp_path / "Config"), "XDG_DATA_HOME": str(tmp_path / "Data")}
        app_dir, kicad_dir = tmp_path / "Config" / "KiCadExtLibManager", tmp_path / "Config" / "kicad"
    app_file, kicad_file = app_dir / "settings.ini", kicad_dir / "10.0" / "kicad_common.json"
    for path, text in ((app_file, "[General]\n"), (kicad_file, "{}\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    env.update({"GUARD_APP_FILE": str(app_file), "GUARD_KICAD_FILE": str(kicad_file)})
    return env


_SECRET = "secret-token-1405"  # scan: allow secret
_WRITE_APP = (
    "import os\nfrom pathlib import Path\n\n\ndef test_writes():\n"
    f"    Path(os.environ['GUARD_APP_FILE']).write_text('{_SECRET}\\n', encoding='utf-8')\n"
)
_WRITE_KICAD = (
    "import os\nfrom pathlib import Path\n\n\ndef test_writes():\n"
    f"    Path(os.environ['GUARD_KICAD_FILE']).write_text('{_SECRET}\\n', encoding='utf-8')\n"
)
_TOUCH_NOTHING = "def test_quiet():\n    assert True\n"


def test_user_state_guard_lists_app_and_kicad_files(tmp_path):
    """The guard watches the app's settings, scan cache and backups plus KiCad's common file and tables, by hash."""
    from customfixtures import app_state_digest, custom_changes, kicad_config_digest, user_state_roots

    roaming, local = tmp_path / "Roaming", tmp_path / "Local"
    write_tree(
        roaming,
        {
            "KiCadExtLibManager/settings.ini": "a",
            "KiCadExtLibManager/scan_cache/a.json": "1",
            "kicad/10.0/kicad_common.json": "{}",
            "kicad/10.0/sym-lib-table": "t",
            "kicad/10.0/other.txt": "o",
            "kicad/templates/x": "x",
        },
    )
    write_tree(local, {"KiCadExtLibManager/backups/b.bak": "b"})

    roots, kicad = user_state_roots({"APPDATA": str(roaming), "LOCALAPPDATA": str(local)}, "win32")

    assert roots == [roaming / "KiCadExtLibManager", local / "KiCadExtLibManager" / "backups"]
    assert kicad == roaming / "kicad"
    app_before = app_state_digest(roots)
    kicad_before = kicad_config_digest(kicad)

    def relative(digest):
        return sorted(Path(key).relative_to(tmp_path).as_posix() for key in digest)

    assert relative(app_before) == [
        "Local/KiCadExtLibManager/backups/b.bak",
        "Roaming/KiCadExtLibManager/scan_cache/a.json",
        "Roaming/KiCadExtLibManager/settings.ini",
    ]
    assert relative(kicad_before) == ["Roaming/kicad/10.0/kicad_common.json", "Roaming/kicad/10.0/sym-lib-table"]

    (roaming / "KiCadExtLibManager" / "settings.ini").write_text("changed", encoding="utf-8")
    (roaming / "KiCadExtLibManager" / "scan_cache" / "c.json").write_text("2", encoding="utf-8")
    (local / "KiCadExtLibManager" / "backups" / "b.bak").unlink()
    (roaming / "kicad" / "10.0" / "other.txt").write_text("changed", encoding="utf-8")

    assert custom_changes(app_before, app_state_digest(roots)) == sorted(
        str(path)
        for path in (
            roaming / "KiCadExtLibManager" / "settings.ini",
            roaming / "KiCadExtLibManager" / "scan_cache" / "c.json",
            local / "KiCadExtLibManager" / "backups" / "b.bak",
        )
    )
    # other.txt is not a watched KiCad file
    assert custom_changes(kicad_before, kicad_config_digest(kicad)) == []


def test_user_state_guard_is_quiet_without_real_folders(tmp_path):
    """No variables, absent folders or empty folders give nothing to compare, so the guard never reports."""
    from customfixtures import app_state_digest, custom_changes, kicad_config_digest, user_state_roots

    assert user_state_roots({}, "win32") == ([], None)
    assert user_state_roots({"APPDATA": None, "LOCALAPPDATA": ""}, "win32") == ([], None)
    assert user_state_roots({"HOME": None}, "linux") == ([], None)
    assert user_state_roots({"HOME": None}, "darwin") == ([], None)
    (tmp_path / "empty").mkdir()
    assert app_state_digest([tmp_path / "absent", tmp_path / "empty"]) == {}
    assert kicad_config_digest(None) == {}
    assert kicad_config_digest(tmp_path / "absent") == {}
    assert kicad_config_digest(tmp_path / "empty") == {}
    assert custom_changes({}, {}) == []


def test_user_state_guard_fails_the_run(tmp_path):
    """A run whose test writes the app's own settings fails under 2 workers, naming the file but not its contents."""
    env = _fake_user_state(tmp_path / "profile")
    run_dir = write_tree(tmp_path / "run", {"test_writes.py": _WRITE_APP})

    done = run_pytest(run_dir, "-n", "2", basetemp=tmp_path / "bt", env=env)

    assert done.returncode != 0, _tail(done)
    assert "changed the real app state" in done.stdout, _tail(done)
    assert "settings.ini" in done.stdout, _tail(done)
    assert _SECRET not in done.stdout + done.stderr


def test_user_state_guard_only_warns_about_kicad_config(tmp_path):
    """A change to KiCad's own config is reported as a warning and does not fail the run."""
    env = _fake_user_state(tmp_path / "profile")
    run_dir = write_tree(tmp_path / "run", {"test_writes.py": _WRITE_KICAD})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt", env=env)

    assert done.returncode == 0, _tail(done)
    assert "KiCad's own config changed" in done.stdout, _tail(done)
    assert "kicad_common.json" in done.stdout, _tail(done)
    assert "changed the real app state" not in done.stdout, _tail(done)
    assert _SECRET not in done.stdout + done.stderr


def test_user_state_guard_quiet_run_passes(tmp_path):
    """A run that touches nothing passes and prints neither message."""
    env = _fake_user_state(tmp_path / "profile")
    run_dir = write_tree(tmp_path / "run", {"test_quiet.py": _TOUCH_NOTHING})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt", env=env)

    assert done.returncode == 0, _tail(done)
    assert "changed the real app state" not in done.stdout, _tail(done)
    assert "KiCad's own config changed" not in done.stdout, _tail(done)
