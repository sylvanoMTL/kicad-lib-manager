"""Start-up tests (Phase 15, ROOT-01/02): the library folder is resolved before any window exists.

Every test passes its own library folder and KiCad config base, so nothing reads or
writes the owner's real settings.ini, KiCad config or live Custom/. QSettings is redirected by the
autouse fixtures in conftest.py.
"""

import inspect
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from collectionfixtures import make_collection
from PySide6.QtWidgets import QDialog

from kicad_lib_manager import collection, main_window, settings, startup
from kicad_lib_manager.collection import Source
from kicad_lib_manager.models import ScanResult
from kicad_lib_manager.widgets.first_run_dialog import FirstRunChoice
from kicad_lib_manager.widgets.log_panel import COLORS

MISSING_TEXT = "This folder does not exist. Choose another folder."


@pytest.fixture
def seams(monkeypatch, tmp_path):
    """Replace everything the window reaches outside its library folder; record the folders it uses."""
    config_base = tmp_path / "kicad_cfg"
    config_base.mkdir()
    fp_dir = tmp_path / "kicad_fp"
    fp_dir.mkdir()
    rec = SimpleNamespace(scans=[], caches=[], mismatches=[])

    def fake_scan(root, progress=None, kicad_fp_dir=None, *, skip=None, checking=None, model_vars=None):
        rec.scans.append(Path(root))
        return ScanResult()

    real_cache_file = main_window.scan_cache_file

    def fake_cache_file(root):
        rec.caches.append(Path(root))
        return real_cache_file(root)

    def fake_mismatch(root, *, config_base=None):
        rec.mismatches.append(Path(root))
        return None

    def no_window(*args, **kwargs):
        raise AssertionError("a main window was built")

    rec.no_window = no_window
    monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
    monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
    monkeypatch.setattr(main_window, "scan_all", fake_scan)
    monkeypatch.setattr(main_window, "scan_cache_file", fake_cache_file)
    monkeypatch.setattr(main_window, "checkout_mismatch", fake_mismatch)
    monkeypatch.setattr(main_window, "sync_kicad_path_vars", lambda *a, **k: [])
    monkeypatch.setattr(main_window, "kicad_running", lambda: [])
    monkeypatch.setattr(main_window.MainWindow, "_question", lambda self, *a: None)
    return rec


def start(seams, qtbot, argv=(), environ=None, **kwargs):
    # Never the real first-run window: a test that wants one passes its own hand-off
    kwargs.setdefault("first_run", lambda resolution: None)
    outcome = startup.start_window(["kicad_lib_manager.py", *argv], environ or {}, **kwargs)
    if not isinstance(outcome, int):
        qtbot.addWidget(outcome)
        qtbot.waitUntil(lambda: outcome._worker is None, timeout=30000)
    return outcome


def test_library_root_option_opens_window_on_that_folder(seams, qtbot, tmp_path):
    root = make_collection(tmp_path / "lib")
    window = start(seams, qtbot, ["--library-root", str(root)])
    assert window._root == root
    assert seams.scans == [root]
    assert window.windowTitle().startswith("lib - ")
    assert window._source is Source.CLI


def test_window_uses_only_the_folder_it_was_given(seams, qtbot, tmp_path):
    root = make_collection(tmp_path / "lib")
    window = start(seams, qtbot, ["--library-root", str(root)])
    window._check_checkout("generate")
    window._start_scan()
    qtbot.waitUntil(lambda: window._worker is None, timeout=30000)
    assert seams.scans and seams.caches and seams.mismatches
    assert {*seams.scans, *seams.caches, *seams.mismatches} == {root}
    # The Destination box falls back to the library folder, never the code folder
    assert window._dest_combo.currentText() == str(root)
    assert str(collection.APP_DIR) not in window._dest_combo.currentText()


def test_env_root_used_without_option(seams, qtbot, tmp_path):
    root = make_collection(tmp_path / "lib")
    window = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": str(root)})
    assert window._root == root
    assert window._source is Source.ENV


def test_option_beats_env(seams, qtbot, tmp_path):
    cli_root = make_collection(tmp_path / "cli")
    env_root = make_collection(tmp_path / "env")
    window = start(
        seams, qtbot, ["--library-root", str(cli_root)], {"KICAD_LIBMGR_ROOT": str(env_root)},
    )
    assert window._root == cli_root
    assert window._source is Source.CLI


def test_blank_env_is_unset(seams, qtbot, tmp_path, capsys):
    outcome = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": "   "})
    assert outcome == 0
    assert capsys.readouterr().err == "No library folder chosen; exiting.\n"


def test_failing_override_exits_2_without_window(seams, qtbot, tmp_path, monkeypatch, capsys):
    other = make_collection(tmp_path / "other")
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    missing = tmp_path / "missing"
    outcome = start(
        seams, qtbot, ["--library-root", str(missing)], chosen=other, kicad=other,
    )
    assert outcome == 2
    assert capsys.readouterr().err == f"--library-root: {missing} cannot be used: {MISSING_TEXT}\n"


def test_failing_env_override_names_the_variable(seams, qtbot, tmp_path, monkeypatch, capsys):
    other = make_collection(tmp_path / "other")
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    missing = tmp_path / "missing"
    outcome = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": str(missing)}, kicad=other)
    assert outcome == 2
    assert capsys.readouterr().err == f"KICAD_LIBMGR_ROOT: {missing} cannot be used: {MISSING_TEXT}\n"


def test_empty_option_value_is_not_the_working_directory(seams, qtbot, tmp_path, monkeypatch, capsys):
    # The working directory is a collection here, so reading "" as "." would start the window
    cwd = make_collection(tmp_path / "cwd")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    outcome = start(seams, qtbot, ["--library-root", ""])
    assert outcome == 2
    assert capsys.readouterr().err == f"--library-root:  cannot be used: {MISSING_TEXT}\n"


def test_code_folder_collection_is_never_used(seams, qtbot, tmp_path, capsys):
    # The folder the code lives in is a collection too (a pre-split checkout): it is no candidate at all
    code_folder = make_collection(tmp_path / "code")
    assert collection.is_collection(code_folder)
    assert list(inspect.signature(startup.build_candidates).parameters) == ["cli", "env", "chosen", "kicad"]
    assert list(inspect.signature(startup.start_window).parameters) == [
        "argv", "environ", "chosen", "kicad", "first_run", "check", "timeout",
    ]
    assert startup.build_candidates(cli=None, env=None) == []
    asked = []

    def first_run(resolution):
        asked.append(resolution)
        return None

    assert start(seams, qtbot, first_run=first_run) == 0
    assert capsys.readouterr().err == "No library folder chosen; exiting.\n"
    assert len(asked) == 1 and asked[0].root is None
    assert seams.scans == []


def test_parse_args_keeps_qt_switches():
    value, rest = startup.parse_args(
        ["app.py", "-style", "fusion", "--library-root", "C:/Lib", "-platform", "offscreen"]
    )
    assert value == "C:/Lib"
    assert rest == ["-style", "fusion", "-platform", "offscreen"]
    assert startup.parse_args(["app.py"]) == (None, [])
    assert startup.parse_args(["app.py", "--library-root", ""]) == ("", [])


def test_check_in_time_reports_no_answer(tmp_path):
    release = threading.Event()

    def stuck(path):
        release.wait(10)
        return collection.check_folder(path)

    began = time.monotonic()
    result = startup.check_in_time(tmp_path, stuck, 0.1)
    release.set()
    assert time.monotonic() - began < 2
    assert result.state == "no_answer"
    assert result.reason == "The drive did not answer within 5 seconds."
    assert not result.usable


def test_check_in_time_returns_the_answer(tmp_path):
    assert startup.check_in_time(tmp_path, collection.check_folder, 5).state == "empty"


def test_say_without_stderr(monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    startup._say("nothing to write to")


# -- Plan 15-10 Task 2: the full order, the remembered and KiCad folders, the first-run window ------------


def log_lines(window) -> list[str]:
    """The text of every log line, oldest first, without its time stamp."""
    return [line.split("] ", 1)[-1] for line in window._log._text.toPlainText().splitlines()]


def write_kicad_config(github: str) -> None:
    """KiCad's kicad_common.json in the test's own (isolated) APPDATA, naming `github` as KICAD_LIB_GITHUB."""
    folder = Path(os.environ["APPDATA"]) / "kicad" / "10.0"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "kicad_common.json").write_text(
        json.dumps({"environment": {"vars": {"KICAD_LIB_GITHUB": github}}}), encoding="utf-8",
    )


def settings_bytes() -> bytes | None:
    store = settings.get_settings()
    store.sync()
    path = Path(store.fileName())
    return path.read_bytes() if path.exists() else None


@pytest.fixture
def spy_window(monkeypatch):
    """Record every MainWindow construction (its arguments) and the order of calls around it."""
    events = []
    real = main_window.MainWindow

    def spy(*args, **kwargs):
        events.append(("window", args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(startup, "MainWindow", spy)
    return events


def test_full_order(seams, qtbot, tmp_path):
    cli = make_collection(tmp_path / "cli")
    env = make_collection(tmp_path / "env")
    chosen = make_collection(tmp_path / "chosen")
    kicad = make_collection(tmp_path / "kicad")

    window = start(seams, qtbot, ["--library-root", str(cli)], {"KICAD_LIBMGR_ROOT": str(env)}, chosen=chosen, kicad=kicad)
    assert (window._root, window._source) == (cli, Source.CLI)
    window = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": str(env)}, chosen=chosen, kicad=kicad)
    assert (window._root, window._source) == (env, Source.ENV)
    window = start(seams, qtbot, chosen=chosen, kicad=kicad)
    assert (window._root, window._source) == (chosen, Source.CHOSEN)
    window = start(seams, qtbot, chosen=None, kicad=kicad)
    assert (window._root, window._source) == (kicad, Source.KICAD)
    # All four fail (the remembered folder is gone, KiCad's is not a collection): the start hands over to first_run
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "notes.txt").write_text("not a collection", encoding="utf-8")
    asked = []

    def first_run(resolution):
        asked.append(resolution)
        return None

    assert start(seams, qtbot, chosen=tmp_path / "gone", kicad=plain, first_run=first_run) == 0
    assert len(asked) == 1 and asked[0].root is None


def test_reads_settings_and_kicad_config_by_default(seams, qtbot, tmp_path):
    remembered = make_collection(tmp_path / "remembered")
    kicad = make_collection(tmp_path / "kicad")
    write_kicad_config(str(kicad))
    settings.save_library_root(remembered)

    window = start(seams, qtbot)
    assert (window._root, window._source) == (remembered, Source.CHOSEN)
    # Finding the folder is not a choice: nothing was saved or added to the recent list
    assert settings.load_library_root() == remembered
    assert settings.load_library_recent() == []

    settings.clear_library_root()
    window = start(seams, qtbot)
    assert (window._root, window._source) == (kicad, Source.KICAD)
    assert settings.load_library_root() is None


def test_deleted_remembered_folder_falls_back_with_note(seams, qtbot, tmp_path):
    gone = tmp_path / "gone"
    kicad = make_collection(tmp_path / "kicad")
    settings.save_library_root(gone)
    before = settings_bytes()

    window = start(seams, qtbot, kicad=kicad)
    assert (window._root, window._source) == (kicad, Source.KICAD)
    assert log_lines(window)[0] == (
        f"The library folder you chose earlier no longer exists: {gone}. Using KiCad's folder ({kicad}) instead."
    )
    # Nothing was saved because a folder was skipped
    assert settings.load_library_root() == gone
    assert settings_bytes() == before


def test_unusable_remembered_folder_note(seams, qtbot, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "notes.txt").write_text("not a collection", encoding="utf-8")
    kicad = make_collection(tmp_path / "kicad")
    settings.save_library_root(plain)
    reason = collection.check_folder(plain).reason
    assert reason

    window = start(seams, qtbot, kicad=kicad)
    assert window._root == kicad
    assert log_lines(window)[0] == (
        f"The library folder you chose earlier cannot be used ({reason}): {plain}. "
        f"Using KiCad's folder ({kicad}) instead."
    )


def test_same_folder_checked_once(seams, qtbot, tmp_path):
    gone = tmp_path / "gone"
    (tmp_path / "sub").mkdir()
    other_spelling = tmp_path / "sub" / ".." / "gone"
    checked = []

    def counting(path):
        checked.append(path)
        return collection.check_folder(path)

    received = []

    def first_run(resolution):
        received.append(resolution)
        return None

    settings.save_library_root(gone)
    start(seams, qtbot, kicad=other_spelling, check=counting, first_run=first_run)
    assert len(checked) == 1
    assert len(received) == 1 and len(received[0].notes) == 1
    assert received[0].notes[0].code == "library.chosen_skipped"


def test_build_candidates_drops_a_folder_named_twice(tmp_path):
    folder = make_collection(tmp_path / "lib")
    (tmp_path / "sub").mkdir()
    again = tmp_path / "sub" / ".." / "lib"
    found = startup.build_candidates(
        cli=None, env=str(folder), chosen=again, kicad=folder,
    )
    assert [(c.source, Path(c.path)) for c in found] == [(Source.ENV, folder)]


def test_blank_override_is_not_dropped_as_a_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(make_collection(tmp_path / "cwd"))
    found = startup.build_candidates(cli="", env=None, chosen=Path("."), kicad=None)
    assert [c.source for c in found] == [Source.CLI, Source.CHOSEN]


def test_nothing_resolves_opens_first_run_with_notice(seams, qtbot, tmp_path, monkeypatch, capsys, spy_window):
    gone = tmp_path / "gone"
    settings.save_library_root(gone)
    before = settings_bytes()
    received = []

    def first_run(resolution):
        received.append(resolution)
        return None

    outcome = start(seams, qtbot, kicad=None, first_run=first_run)
    assert outcome == 0
    assert capsys.readouterr().err == "No library folder chosen; exiting.\n"
    assert len(received) == 1
    assert received[0].root is None
    assert received[0].notice == f"The library folder you used before is gone: {gone}."
    assert spy_window == []
    assert settings_bytes() == before


def test_quit_twice_shows_first_run_twice(seams, qtbot, tmp_path, capsys, spy_window):
    shown = []
    settings.save_library_root(tmp_path / "gone")
    before = settings_bytes()
    for _ in range(2):
        outcome = start(seams, qtbot, kicad=None, first_run=lambda resolution: shown.append(resolution))
        assert outcome == 0
    assert len(shown) == 2
    assert capsys.readouterr().err == "No library folder chosen; exiting.\n" * 2
    assert spy_window == []
    assert settings_bytes() == before


def test_first_run_collection_choice(seams, qtbot, tmp_path, spy_window):
    coll = make_collection(tmp_path / "new")
    choice = FirstRunChoice(coll, Source.CHOSEN, created=True)

    window = start(seams, qtbot, chosen=None, kicad=None, first_run=lambda resolution: choice)
    assert (window._root, window._source) == (coll, Source.CHOSEN)
    assert settings.load_library_root() == coll
    assert settings.load_library_recent()[0] == str(coll)
    lines = log_lines(window)
    assert lines[0] == f"Created a new collection in {coll}"
    assert COLORS["success"].lower() in window._log._text.toHtml().lower()
    assert spy_window[0][2]["switched"] is True


def test_first_run_existing_collection_choice_is_saved_without_a_note(seams, qtbot, tmp_path, spy_window):
    coll = make_collection(tmp_path / "existing")
    window = start(seams, qtbot, chosen=None, kicad=None, first_run=lambda r: FirstRunChoice(coll, Source.CHOSEN))
    assert settings.load_library_root() == coll
    assert settings.load_library_recent()[0] == str(coll)
    assert not [line for line in log_lines(window) if line.startswith("Created a new collection")]
    assert spy_window[0][2]["switched"] is True


def test_first_run_kicad_choice(seams, qtbot, tmp_path, spy_window):
    kicad = make_collection(tmp_path / "kicad")
    settings.save_library_root(tmp_path / "old")

    window = start(seams, qtbot, chosen=None, kicad=None, first_run=lambda r: FirstRunChoice(kicad, Source.KICAD))
    assert (window._root, window._source) == (kicad, Source.KICAD)
    assert settings.load_library_root() is None
    assert settings.load_library_recent() == []
    assert spy_window[0][2]["switched"] is False


def test_first_run_choice_that_fails_the_check_is_not_saved(seams, qtbot, tmp_path, capsys, spy_window):
    gone = tmp_path / "vanished"
    before = settings_bytes()

    outcome = start(seams, qtbot, chosen=None, kicad=None, first_run=lambda r: FirstRunChoice(gone, Source.CHOSEN))
    assert outcome == 2
    assert capsys.readouterr().err == f"Not using {gone}: {MISSING_TEXT}\n"
    assert spy_window == []
    assert settings_bytes() == before


def test_default_first_run_uses_the_dialog(monkeypatch, tmp_path):
    write_kicad_config("X:/kicad")
    asked = []
    chosen = FirstRunChoice(tmp_path, Source.CHOSEN)

    class Accepting:
        def __init__(self, kicad_folder, notice=None, **kwargs):
            asked.append((kicad_folder, notice, kwargs))

        def exec(self):
            return QDialog.DialogCode.Accepted

        def choice(self):
            return chosen

    class Rejecting(Accepting):
        def exec(self):
            return QDialog.DialogCode.Rejected

        def choice(self):
            return chosen  # a Quit never reports a choice, whatever the dialog still holds

    resolution = collection.Resolution(None, None, notice="Because.")
    monkeypatch.setattr(startup, "FirstRunDialog", Accepting)
    assert startup.run_first_run(resolution) is chosen
    assert asked == [("X:/kicad", "Because.", {})]
    monkeypatch.setattr(startup, "FirstRunDialog", Rejecting)
    assert startup.run_first_run(resolution) is None


def test_default_hand_off_is_run_first_run():
    params = inspect.signature(startup.start_window).parameters
    assert params["first_run"].default is startup.run_first_run
    assert params["chosen"].default is startup._READ
    assert params["kicad"].default is startup._READ


def test_resolve_runs_before_any_window(seams, qtbot, tmp_path, spy_window):
    coll = make_collection(tmp_path / "new")

    def first_run(resolution):
        spy_window.append(("first_run",))
        return FirstRunChoice(coll, Source.CHOSEN)

    window = start(seams, qtbot, chosen=None, kicad=None, first_run=first_run)
    assert window is not None
    assert [event[0] for event in spy_window] == ["first_run", "window"]


def test_every_candidate_is_checked_before_use(seams, qtbot, tmp_path):
    folder = make_collection(tmp_path / "lib")
    checked = []

    def counting(path):
        checked.append(Path(path))
        return collection.check_folder(path)

    settings.save_library_root(folder)
    window = start(seams, qtbot, check=counting)
    assert window._root == folder
    assert checked == [folder]


# -- Code review CR-02: every folder that becomes the library folder is absolute ---------------------


def test_relative_library_root_option_becomes_absolute(seams, qtbot, tmp_path, monkeypatch):
    root = make_collection(tmp_path / "libs" / "lib")
    monkeypatch.chdir(tmp_path)
    window = start(seams, qtbot, ["--library-root", os.path.join("libs", "lib")])
    assert window._root == root and window._root.is_absolute()
    assert seams.scans == [root]


def test_relative_env_root_becomes_absolute(seams, qtbot, tmp_path, monkeypatch):
    root = make_collection(tmp_path / "lib")
    monkeypatch.chdir(tmp_path)
    window = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": "lib"})
    assert window._root == root and window._root.is_absolute()


def test_build_candidates_makes_every_candidate_absolute(tmp_path, monkeypatch):
    for name in ("a", "b", "c", "d"):
        make_collection(tmp_path / name)
    monkeypatch.chdir(tmp_path)
    found = startup.build_candidates(cli="a", env="b", chosen=Path("c"), kicad="d")
    assert [Path(c.path) for c in found] == [tmp_path / name for name in "abcd"]
    assert all(Path(c.path).is_absolute() for c in found)


def test_relative_choice_from_first_run_is_saved_absolute(seams, qtbot, tmp_path, spy_window, monkeypatch):
    root = make_collection(tmp_path / "picked")
    monkeypatch.chdir(tmp_path)
    window = start(
        seams, qtbot, first_run=lambda resolution: FirstRunChoice(Path("picked"), Source.CHOSEN, False),
        chosen=None, kicad=None,
    )
    assert window._root == root and window._root.is_absolute()
    assert settings.load_library_root() == root
    assert settings.load_library_recent()[0] == str(root)


# -- Code review WR-02: a fatal start error is visible without a console ------------------------------


@pytest.fixture
def error_boxes(monkeypatch):
    shown = []
    monkeypatch.setattr(startup, "_show_error", shown.append)
    return shown


def test_failing_override_shows_a_box_without_stderr(seams, qtbot, tmp_path, monkeypatch, error_boxes):
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    monkeypatch.setattr(sys, "stderr", None)
    missing = tmp_path / "missing"
    outcome = start(seams, qtbot, ["--library-root", str(missing)], chosen=None, kicad=None)
    assert outcome == 2
    assert error_boxes == [f"--library-root: {missing} cannot be used: {MISSING_TEXT}"]


def test_failed_first_run_recheck_shows_a_box_without_stderr(seams, qtbot, tmp_path, monkeypatch, error_boxes):
    gone = tmp_path / "vanished"
    monkeypatch.setattr(sys, "stderr", None)
    outcome = start(seams, qtbot, chosen=None, kicad=None, first_run=lambda r: FirstRunChoice(gone, Source.CHOSEN))
    assert outcome == 2
    assert error_boxes == [f"Not using {gone}: {MISSING_TEXT}"]


def test_quit_without_stderr_shows_no_box(seams, qtbot, monkeypatch, error_boxes):
    monkeypatch.setattr(sys, "stderr", None)
    assert start(seams, qtbot, chosen=None, kicad=None) == 0
    assert error_boxes == []


def test_fatal_start_error_with_stderr_writes_stderr_and_no_box(seams, qtbot, tmp_path, monkeypatch, capsys, error_boxes):
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    missing = tmp_path / "missing"
    assert start(seams, qtbot, ["--library-root", str(missing)], chosen=None, kicad=None) == 2
    assert capsys.readouterr().err == f"--library-root: {missing} cannot be used: {MISSING_TEXT}\n"
    assert error_boxes == []


# -- quick 261123-lmx: an override start goes into Recent, never into library/root ----------------------------


@pytest.mark.parametrize("how", ["cli", "env"])
def test_override_start_adds_the_folder_to_recent_only(seams, qtbot, tmp_path, how):
    root = make_collection(tmp_path / "lib")
    remembered = make_collection(tmp_path / "remembered")
    settings.save_library_root(remembered)
    assert settings.load_library_recent() == []

    if how == "cli":
        window = start(seams, qtbot, ["--library-root", str(root)])
    else:
        window = start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": str(root)})
    assert window._root == root
    assert settings.load_library_recent()[0] == str(root)
    # an override is not the user's choice: the remembered folder is untouched
    assert settings.load_library_root() == remembered
    window._rebuild_recent_menu()
    checked = [a for a in window._recent_menu.actions() if a.isChecked()]
    assert len(checked) == 1 and checked[0].data() == str(root)


def test_override_start_without_a_remembered_folder_saves_no_root(seams, qtbot, tmp_path):
    root = make_collection(tmp_path / "lib")
    start(seams, qtbot, ["--library-root", str(root)])
    assert settings.load_library_recent()[0] == str(root)
    assert settings.load_library_root() is None


def test_failing_override_adds_nothing_to_recent(seams, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "MainWindow", seams.no_window)
    missing = tmp_path / "missing"
    assert start(seams, qtbot, ["--library-root", str(missing)]) == 2
    assert settings.load_library_recent() == []
    assert start(seams, qtbot, environ={"KICAD_LIBMGR_ROOT": str(missing)}) == 2
    assert settings.load_library_recent() == []


def test_kicad_folder_start_adds_nothing_to_recent(seams, qtbot, tmp_path):
    kicad = make_collection(tmp_path / "kicad")
    window = start(seams, qtbot, kicad=kicad)
    assert window._source is Source.KICAD
    assert settings.load_library_recent() == []
