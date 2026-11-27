import itertools
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from corpusfixtures import CORPUS_ENV, corpus_problem, corpus_raw, corpus_root, kicad_found, kicad_hidden

# Force (not setdefault): a developer shell with another platform must not open real windows
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# The owner's real user folders, captured at import, before any test redirects them (the run-level guard reads them)
_REAL = {
    name: os.environ.get(name)
    for name in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME")
}
# The real rmtree, taken at import: a test may patch shutil.rmtree (test_prune_failure_warns), and the
# per-test cleanup below runs while that patch is still active
_rmtree = shutil.rmtree
# Environment variables that name a user folder, with the folder each gets under a test's own home
_USER_DIRS = (
    ("APPDATA", "AppData/Roaming"),
    ("LOCALAPPDATA", "AppData/Local"),
    ("XDG_CONFIG_HOME", ".config"),
    ("XDG_DATA_HOME", ".local/share"),
)
# KiCad's path variables: unset inside a test, which sets one itself with monkeypatch when it needs one
_CLEARED_VARS = ("KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "WE_3DMODEL_DIR")

REPO_ROOT = Path(__file__).resolve().parent.parent

_GAP_RE = re.compile(r"[ \t\r\n]*")
_ATOM_BAD_RE = re.compile(r'[ \t\r\n()"]')


def pytest_addoption(parser):
    """Add --full: the shell-safe way to run the slow tests too (PowerShell 5.1 drops an empty `-m ""`)."""
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="also run the tests marked slow: real git, the Wurth corpus, kicad-cli",
    )


_RUN_CONFIG = None


def _run_temp(config) -> Path:
    """The run's shared base temp: a worker's base is <run>/popen-gwN, so its parent is the run folder."""
    base = config._tmp_path_factory.getbasetemp()
    return base.parent if hasattr(config, "workerinput") else base


def pytest_configure(config):
    """Clear the default `-m 'not slow'` when --full is given; an explicit other -m stays as typed.

    A KICAD_TEST_CORPUS that is not a library collection stops the run (pytest's usage error, exit code 4).
    """
    global _RUN_CONFIG
    _RUN_CONFIG = config
    reason = corpus_problem()
    if reason is not None:
        raise pytest.UsageError(f"{CORPUS_ENV}={corpus_raw()!r} is not a library collection: {reason}")
    if config.getoption("--full") and config.option.markexpr == "not slow":
        config.option.markexpr = ""
    if kicad_hidden():
        _hide_kicad()


def _hide_kicad() -> None:
    """Make find_kicad_footprint_dir() find no KiCad when asked without a base, so a run on the workstation matches a CI runner.

    A call with an explicit base (the scanner tests build their own) goes to the real function. Installed before any
    test module imports the name, in the controller and in every worker.
    """
    import functools

    from kicad_lib_manager import library_scanner

    original = library_scanner.find_kicad_footprint_dir

    @functools.wraps(original)
    def find_kicad_footprint_dir(base=None, *args, **kwargs):
        if base is None:
            return None
        return original(base, *args, **kwargs)

    library_scanner.find_kicad_footprint_dir = find_kicad_footprint_dir


# What the gates deselected in this run: {"corpus": n, "needs_kicad": m}. A serial run records it here; a worker sends it to the
# controller through config.workeroutput, and pytest_testnodedown merges it here
_DESELECTED = pytest.StashKey[dict[str, int]]()
_WORKER_KEY = "kicad_test_deselected"
_CORPUS_LINE = "deselected: {n} corpus (set KICAD_TEST_CORPUS to a collection folder to run them)"
_KICAD_LINE = "deselected: {n} needs_kicad (no KiCad install found)"


def _gate(items, removed: list, counts: dict[str, int], name: str, closed: bool) -> list:
    """Move every item marked `name` into removed when the gate is closed; return the items that stay."""
    if not closed:
        return items
    kept = []
    gone = 0
    for item in items:
        if item.get_closest_marker(name) is not None:
            removed.append(item)
            gone += 1
        else:
            kept.append(item)
    if gone:
        counts[name] = gone
    return kept


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Mark the Wurth corpus and kicad-cli tests slow, and the Wurth corpus tests corpus; deselect the closed gates.

    tryfirst so the built-in -m deselection sees the marks. A test whose gate is closed is deselected, never skipped,
    and the count is printed at the end of the run, so the public suite cannot go green by skipping. Neither group
    counts toward the skip budget.
    """
    for item in items:
        if item.get_closest_marker("wurth") is not None and item.get_closest_marker("corpus") is None:
            item.add_marker(pytest.mark.corpus)
        if item.get_closest_marker("slow") is not None:
            continue
        if (
            item.get_closest_marker("wurth") is not None
            or item.get_closest_marker("kicad_cli") is not None
            or "kicad_cli_path" in getattr(item, "fixturenames", ())
        ):
            item.add_marker(pytest.mark.slow)
    removed: list = []
    counts: dict[str, int] = {}
    kept = _gate(list(items), removed, counts, "corpus", corpus_root() is None)
    kept = _gate(kept, removed, counts, "needs_kicad", not kicad_found())
    if removed:
        config.hook.pytest_deselected(items=removed)
        items[:] = kept
    if hasattr(config, "workeroutput"):
        config.workeroutput[_WORKER_KEY] = counts
    else:
        config.stash[_DESELECTED] = counts


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    """On the controller, merge a worker's deselected counts (every worker collects the same set, so take the maximum)."""
    counts = getattr(node, "workeroutput", {}).get(_WORKER_KEY, {})
    merged = _RUN_CONFIG.stash.setdefault(_DESELECTED, {}) if _RUN_CONFIG is not None else {}
    for name, number in counts.items():
        merged[name] = max(merged.get(name, 0), number)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print how many tests each closed gate deselected (the controller only; a worker has no terminal)."""
    counts = config.stash.get(_DESELECTED, {})
    if counts.get("corpus"):
        terminalreporter.write_line(_CORPUS_LINE.format(n=counts["corpus"]))
    if counts.get("needs_kicad"):
        terminalreporter.write_line(_KICAD_LINE.format(n=counts["needs_kicad"]))


@pytest.fixture(scope="session", autouse=True)
def _git_template_root(request, tmp_path_factory):
    """Give tests/gitfixtures.py one template folder shared by every worker of the run.

    A worker's base temp is <run>/popen-gwN, so its parent is shared by all workers; a serial run uses its own base.
    """
    base = tmp_path_factory.getbasetemp()
    root = (base.parent if hasattr(request.config, "workerinput") else base) / "git_templates"
    module = sys.modules.get("gitfixtures")
    if module is not None:
        module.set_template_root(root)
    yield


# ── Subprocess watch: an unmarked test must not create a real git repository ──────

# The real Popen, taken at import: the watch swaps subprocess.Popen per test and restores this
_REAL_POPEN = subprocess.Popen
# The repository-creating git commands started during the running test; None means not watching
_repo_watch: list[str] | None = None
# git options that take the next token as their value
_GIT_VALUE_OPTIONS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")


def _git_repo_command(argv) -> str | None:
    """The repository-creating git command that argv starts (init, clone, submodule add/update --init), else None.

    Never raises. A string or path-like argv is split like a command line; a sequence is taken as is.
    """
    try:
        if isinstance(argv, (str, bytes, os.PathLike)):
            tokens = [token.strip('"') for token in shlex.split(os.fsdecode(argv), posix=False)]
        else:
            tokens = [os.fsdecode(token) for token in argv]
        if not tokens or Path(tokens[0]).name.lower() not in ("git", "git.exe"):
            return None
        rest = tokens[1:]
        index = 0
        while index < len(rest):
            token = rest[index]
            if token in _GIT_VALUE_OPTIONS:
                index += 2
            elif token.startswith("-"):
                index += 1
            else:
                break
        if index >= len(rest):
            return None
        command, after = rest[index], [token for token in rest[index + 1 :] if not token.startswith("-") or token == "--init"]
        if command in ("init", "clone"):
            return f"git {command}"
        if command == "submodule":
            plain = [token for token in after if token != "--init"]
            if plain and plain[0] == "add":
                return "git submodule add"
            if plain and plain[0] == "update" and "--init" in after:
                return "git submodule update --init"
        return None
    except (ValueError, TypeError):
        return None


class _RepoWatchPopen(_REAL_POPEN):
    """Popen that records a repository-creating git command before the process starts; nothing else changes."""

    def __init__(self, *args, **kwargs):
        if _repo_watch is not None:
            argv = kwargs["args"] if "args" in kwargs else (args[0] if args else None)
            command = _git_repo_command(argv)
            if command is not None:
                _repo_watch.append(command)
        super().__init__(*args, **kwargs)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Tell gitfixtures which test is running, for the slow-marker tripwire; arm the git watch for non-slow tests."""
    global _repo_watch
    module = sys.modules.get("gitfixtures")
    if module is not None:
        module.set_current_item(item)
    if item.get_closest_marker("slow") is None:
        _repo_watch = []
        subprocess.Popen = _RepoWatchPopen
    else:
        _repo_watch = None


_USER_STATE = pytest.StashKey[tuple[dict[str, str], dict[str, str], list[Path], Path | None]]()


def pytest_sessionstart(session):
    """Hash the owner's real app state and KiCad config once, on the controller, before any test runs.

    Under xdist the workers never compare; the controller compares once at the end (pytest_sessionfinish).
    """
    if hasattr(session.config, "workerinput"):
        return
    from customfixtures import app_state_digest, kicad_config_digest, user_state_roots

    roots, kicad = user_state_roots(_REAL, sys.platform)
    session.config.stash[_USER_STATE] = (app_state_digest(roots), kicad_config_digest(kicad), roots, kicad)


def _report(session, line: str) -> None:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(line)
    else:
        print(line, file=sys.stderr)


def _list_changes(changed: list[str]) -> str:
    from customfixtures import _SHOWN_CHANGES

    text = ", ".join(changed[:_SHOWN_CHANGES])
    if len(changed) > _SHOWN_CHANGES:
        text += f" and {len(changed) - _SHOWN_CHANGES} more"
    return text


def _check_user_state(session) -> None:
    """Compare the real app state and KiCad config with their hashes from the start of the run.

    A change to the app's own state fails the run. A change to KiCad's own config only warns, because the owner
    may have used the app or KiCad during the run: rerun if the named files are not from the tests. Paths only,
    never contents.
    """
    from customfixtures import app_state_digest, custom_changes, kicad_config_digest

    if _USER_STATE not in session.config.stash:
        return
    app_before, kicad_before, roots, kicad = session.config.stash[_USER_STATE]
    app_changed = custom_changes(app_before, app_state_digest(roots))
    kicad_changed = custom_changes(kicad_before, kicad_config_digest(kicad))
    if app_changed:
        _report(session, "the test run changed the real app state: " + _list_changes(app_changed))
        if session.exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    if kicad_changed:
        _report(session, "warning: KiCad's own config changed during the run (was KiCad open?): " + _list_changes(kicad_changed))


def pytest_sessionfinish(session, exitstatus):
    """On the controller: compare the real user state, then remove this run's own <base temp>/git_templates.

    Nothing else is ever touched.
    """
    if hasattr(session.config, "workerinput"):
        return
    _check_user_state(session)
    factory = getattr(session.config, "_tmp_path_factory", None)
    if factory is None:
        return
    templates = factory.getbasetemp() / "git_templates"
    if not templates.exists():
        return
    from gitfixtures import remove_tree

    remove_tree(templates)


def _record_timeout_then_exit(item, settings, record) -> None:
    """Write the TIMEOUT line, then let pytest-timeout dump the stacks and end the worker exactly as before."""
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        with open(record, "a", encoding="utf-8") as stream:
            stream.write(f"TIMEOUT {item.nodeid} after {settings.timeout:g} s\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        pass  # a failed write must never stop the timeout
    finally:
        import pytest_timeout

        pytest_timeout.timeout_timer(item, settings)


@pytest.hookimpl(tryfirst=True, optionalhook=True)
def pytest_timeout_set_timer(item, settings):
    """In a worker, run pytest-timeout's thread timer ourselves so the hung test's node id is recorded first.

    Under xdist the worker's stdout goes to the null device, so pytest-timeout's banner is lost and the
    controller only says the worker crashed. Returning None elsewhere leaves pytest-timeout's own timer alone.
    """
    if not hasattr(item.config, "workerinput") or settings.method != "thread":
        return None
    record = _run_temp(item.config) / "timeouts" / f"{item.config.workerinput['workerid']}.txt"
    timer = threading.Timer(settings.timeout, _record_timeout_then_exit, (item, settings, record))
    timer.name = f"pytest_timeout {item.nodeid}"

    def cancel():
        timer.cancel()
        timer.join()

    # pytest-timeout's own pytest_timeout_cancel_timer calls item.cancel_timeout, so cancelling is unchanged
    item.cancel_timeout = cancel
    timer.start()
    return True


@pytest.hookimpl(optionalhook=True)
def pytest_handlecrashitem(crashitem, report, sched):
    """On the controller, put the worker's TIMEOUT record for the crashed test into xdist's crash report.

    A crash with no record (a real crash, not a timeout) keeps xdist's report unchanged.
    """
    if _RUN_CONFIG is None:
        return
    folder = _run_temp(_RUN_CONFIG) / "timeouts"
    if not folder.is_dir():
        return
    prefix = f"TIMEOUT {crashitem} after "
    found = None
    for record in sorted(folder.glob("*.txt")):
        for line in record.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix):
                found = line
    if found is not None:
        report.longrepr = f"{found}: pytest-timeout ended the worker (rerun with -n 0 to see its stack dump)\n{report.longrepr}"


def _join_widget_threads(widgets) -> None:
    """Wait for every QThread child of the widgets; a widget whose C++ object is gone is skipped."""
    # Imported only here, so test modules that never create a widget stay Qt-free
    from PySide6.QtCore import QThread

    for widget in widgets:
        try:
            threads = widget.findChildren(QThread)
        except RuntimeError:  # the C++ widget is already gone
            continue
        for thread in threads:
            thread.wait(60000)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    """Join every QThread child of the registered widgets before pytest-qt closes them, and end them in this test.

    pytest-qt closes the registered widgets before fixture teardown, and a close that waits
    for its workers instead of blocking must never let a running thread be destroyed with
    its widget. A test that gates a worker must release it before it ends.

    pytest-qt's deleteLater() runs outside any event loop, so on its own the widget would live on until the next
    test's first qtbot.wait: its timers could still start a worker there, and the deletion would then destroy that
    running thread (Qt ends the whole worker process). So after pytest-qt's teardown the widgets' threads are
    joined again (teardown's processEvents can start one) and their pending deletion is run here.

    After every fixture finaliser it also ends the git watch: an unmarked test during which a repository-creating
    git command started fails here, naming itself and the command.
    """
    global _repo_watch
    widgets = [ref() for ref, _ in getattr(item, "qt_widgets", [])]
    widgets = [widget for widget in widgets if widget is not None]
    if widgets:
        _join_widget_threads(widgets)
    try:
        result = yield
    finally:
        found = _repo_watch
        _repo_watch = None
        subprocess.Popen = _REAL_POPEN
        if widgets:
            from PySide6.QtCore import QCoreApplication, QEvent
            from shiboken6 import isValid

            _join_widget_threads(widgets)
            for widget in widgets:
                if isValid(widget):
                    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)
            widgets.clear()
    if found:
        pytest.fail(
            f"{item.nodeid} creates a real git repository ({', '.join(sorted(set(found)))}): mark it @pytest.mark.slow",
            pytrace=False,
        )
    return result


@pytest.fixture(autouse=True)
def _desktop_screen_area(monkeypatch):
    """Size the import window for a Full HD 100% desktop (1920x1032), not the 800x800 offscreen screen.

    The edit page then keeps its 1100x720 size in every test. A test may patch screen_area again to model
    another screen. Nothing is imported here: a test module that never loads the import window stays Qt-free.
    """
    module = sys.modules.get("kicad_lib_manager.widgets.import_dialog")
    if module is None:
        return
    from PySide6.QtCore import QRect

    monkeypatch.setattr(module, "screen_area", lambda widget: QRect(0, 0, 1920, 1032))


@pytest.fixture(autouse=True)
def _no_addon_list_network(monkeypatch):
    """A read of KiCad's add-on list without an opener answers as offline: the suite never reaches the network.

    The tests of the reader hand read_index an opener stand-in. Any other read (for example a catalog window
    opened by a main-window test) gets the offline answer; each test's settings folder is empty, so no kept
    copy exists and the window shows the curated list.
    """
    import urllib.error

    from kicad_lib_manager.catalog import addons

    def offline(request, timeout, limit):
        raise urllib.error.URLError("the tests use no network")

    monkeypatch.setattr(addons, "_default_opener", offline)


@pytest.fixture(scope="session", autouse=True)
def _qsettings_sandbox(tmp_path_factory):
    """Point QSettings at a throwaway folder for code that builds one outside a test (session fixtures).

    Removed when the session ends; the per-test fixture below re-points it for every test.
    """
    from PySide6.QtCore import QSettings

    folder = tmp_path_factory.mktemp("qsettings_session")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder))
    yield
    _rmtree(folder, ignore_errors=True)


_USER_FOLDERS = itertools.count()


@pytest.fixture(autouse=True)
def _isolated_user_state(tmp_path_factory, monkeypatch):
    """Give every test its own empty user home, QSettings ini and KiCad config folder, removed when it ends.

    Both the environment and QSettings are redirected: the app reads APPDATA and LOCALAPPDATA itself, while
    QSettings on Windows ignores the environment and needs setPath. KICAD_CONFIG_HOME is set, not removed:
    kicad-cli (started by the app with no env=) honours it, and without it would read the owner's real
    KiCad config through the Windows shell API. The folder sits outside tmp_path, so a test that lists its
    tmp_path sees nothing new, and it is removed after the test (the monkeypatch fixture is torn down after
    this one, so the environment still names it meanwhile). A test's own monkeypatch or a module's
    `_isolated_settings` runs later and wins. QtCore is imported in every worker on purpose: it is the only
    way to be sure no later QSettings reaches the real ini.
    """
    from PySide6.QtCore import QSettings

    # A counter, not mktemp's numbering: a removed folder's number would be reused by the next test
    home = tmp_path_factory.mktemp(f"user{next(_USER_FOLDERS)}", numbered=False)
    for name, sub in _USER_DIRS:
        (home / sub).mkdir(parents=True)
        monkeypatch.setenv(name, str(home / sub))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    for name in _CLEARED_VARS:
        monkeypatch.delenv(name, raising=False)
    (home / "kicad_config").mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(home / "kicad_config"))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(home / "qsettings"))
    yield
    _rmtree(home, ignore_errors=True)


@pytest.fixture(autouse=True)
def _scratch_switch_reset(_isolated_user_state):
    """Clear the scratch switch (D-35) before and after every test and put back what a start with it changed.

    The switch sets three process-wide things: the scratch state of kicad_lib_manager.userdirs, the QSettings
    folder and KICAD_CONFIG_HOME. The first is cleared; the other two are set back to the values this test's
    own isolated folders gave them. It depends on _isolated_user_state, so it is set up after it and torn
    down before it; it only adds to the isolation, nothing there is changed.
    """
    from PySide6.QtCore import QSettings

    from kicad_lib_manager import userdirs

    userdirs.set_scratch_root(None)
    # Qt's ini path is <folder>/<org>/<app>.ini: two levels up is the folder that setPath took
    ini = Path(QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "KiCadExtLibManager", "settings").fileName())
    settings_folder = ini.parent.parent
    config_home = os.environ.get("KICAD_CONFIG_HOME")
    yield
    userdirs.set_scratch_root(None)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_folder))
    if config_home is None:
        os.environ.pop("KICAD_CONFIG_HOME", None)
    else:
        os.environ["KICAD_CONFIG_HOME"] = config_home


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


def _collect_tokens(root) -> list[tuple[int, int, str, object]]:
    """Walk nodes iteratively and return (start, end, kind, node) token spans in document order."""
    tokens = []
    stack = [iter(root.children)]
    closers = [None]
    while stack:
        node = next(stack[-1], None)
        if node is None:
            stack.pop()
            closer = closers.pop()
            if closer is not None:
                tokens.append((closer.end - 1, closer.end, "close", closer))
            continue
        if node.kind == "list":
            tokens.append((node.start, node.start + 1, "open", node))
            stack.append(iter(node.children))
            closers.append(node)
        else:
            tokens.append((node.start, node.end, node.kind, node))
    return tokens


@pytest.fixture
def assert_tiles():
    """Return a checker proving node spans plus gaps cover the text exactly."""

    def check(text: str, root) -> None:
        pos = 0
        for start, end, kind, node in _collect_tokens(root):
            assert start >= pos, f"token {kind} at {start} overlaps previous token ending {pos}"
            assert _GAP_RE.fullmatch(text, pos, start), (
                f"gap {pos}:{start} before {kind} token is not pure space/tab/CR/LF"
            )
            if kind == "open":
                assert text[start] == "(", f"list at {start} does not start with '('"
            elif kind == "close":
                assert text[start] == ")", f"list ending at {end} does not end with ')'"
            elif kind == "str":
                assert text[start:end] == node.text, f"str node at {start}:{end} text mismatch"
                assert end - start >= 2 and text[start] == '"' and text[end - 1] == '"', (
                    f"str node at {start}:{end} is not double-quoted"
                )
            elif kind == "atom":
                assert text[start:end] == node.text, f"atom node at {start}:{end} text mismatch"
                assert end > start and not _ATOM_BAD_RE.search(node.text), (
                    f"atom node at {start}:{end} contains a separator or quote"
                )
            pos = end
        assert _GAP_RE.fullmatch(text, pos, len(text)), (
            f"trailing gap {pos}:{len(text)} is not pure space/tab/CR/LF"
        )

    return check


@pytest.fixture
def synthetic_custom(tmp_path):
    """A RepoLayout over an isolated Custom/ built in code (a format mirror of the real one, without the UL sample part); nothing is copied from the checkout."""
    from customfixtures import write_synthetic_custom

    return write_synthetic_custom(tmp_path / "repo")


@pytest.fixture
def atomic_custom(tmp_path):
    """A RepoLayout over an isolated Custom/ built in code that holds the Atomic_ install targets (naming="atomic"); nothing is copied from the checkout."""
    from customfixtures import write_synthetic_custom

    return write_synthetic_custom(tmp_path / "repo", naming="atomic")


@pytest.fixture
def ul_package():
    """Yield (package, candidate) for the synthetic Ultra Librarian sample; the package is closed afterwards."""
    from zipfixtures import UL_ZIP

    from kicad_lib_manager.importer.detect import detect_candidate
    from kicad_lib_manager.importer.package import open_package

    package = open_package(UL_ZIP, REPO_ROOT)
    try:
        candidate, _ = detect_candidate(package)
        yield package, candidate
    finally:
        package.close()


@pytest.fixture
def kicad_cli_path() -> Path:
    """The kicad-cli 10 of the installed KiCad (located as the app does); skips with the gate's reason otherwise."""
    from clifixtures import located_kicad_cli

    exe, reason = located_kicad_cli()
    if exe is None:
        pytest.skip(reason)
    return exe


@pytest.fixture
def real_tools(kicad_cli_path):
    """The tools the app would detect on this machine; kicad-cli is present because kicad_cli_path did not skip."""
    from kicad_lib_manager.importer.planner import detect_tools
    from kicad_lib_manager.library_scanner import find_kicad_footprint_dir

    tools = detect_tools(find_kicad_footprint_dir())
    assert tools.kicad_cli == kicad_cli_path
    return tools


@pytest.fixture
def snapshot():
    """Return a function mapping a folder to {relative path: sha256} for files and {relative path/: "dir"} for folders."""
    from customfixtures import digest_tree

    return digest_tree


@pytest.fixture(scope="session", autouse=True)
def _live_custom_untouched():
    """The suite must never write the live Custom/: a change to it fails the run, naming the paths.

    Watches the Custom/ folder of the KICAD_TEST_CORPUS collection; with no corpus it watches nothing. When that
    Custom/ is not checked out, the guard does nothing.
    """
    from customfixtures import guard_custom

    root = corpus_root()
    if root is None:
        yield
        return
    yield from guard_custom(root / "Custom")
