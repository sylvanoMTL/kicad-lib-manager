"""Resolve the library folder before any window exists (Phase 15, ROOT-01/02/05/07)."""

import argparse
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Mapping

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from . import kicad_setup, settings, userdirs
from .collection import (
    Candidate, FolderCheck, Resolution, Source, absolute_folder, check_folder,
    no_answer, resolve_library_root, spelling_key,
)
from .main_window import APP_TITLE, MainWindow
from .models import Issue, Severity
from .widgets.first_run_dialog import FirstRunChoice, FirstRunDialog

ENV_VAR = "KICAD_LIBMGR_ROOT"
# The scratch switch for owner checks (D-35): the app's settings, backups and KiCad's settings move under one folder
SCRATCH_OPTION = "--scratch-root"
SCRATCH_ENV_VAR = "KICAD_LIBMGR_SCRATCH_ROOT"
SCRATCH_NOTE = (
    "Working in the scratch folder {folder}: the app's settings, saved scans and backups and KiCad's "
    "settings are read and written there, and your real ones are not touched."
)
STARTUP_CHECK_TIMEOUT = 5.0
# The default of start_window's chosen and kicad: read the saved choice and KiCad's configuration.
# An explicit None means "no such candidate".
_READ = object()


def parse_args(argv: list[str]) -> tuple[str | None, list[str]]:
    """Split argv into the --library-root value and the arguments left for Qt."""
    known, rest = _parse(argv)
    return known.library_root, rest


def scratch_root_arg(argv: list[str]) -> str | None:
    """The --scratch-root value, or None when the option is not given."""
    return _parse(argv)[0].scratch_root


def _parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--library-root", default=None)
    parser.add_argument(SCRATCH_OPTION, default=None)  # it never reaches Qt
    return parser.parse_known_args(argv[1:])


def apply_scratch_root(folder: Path) -> None:
    """Move the app's settings, backups and KiCad's settings folder under folder, for the rest of the process.

    KICAD_CONFIG_HOME is set so a program the app starts (kicad-cli) reads the scratch KiCad settings too.
    """
    userdirs.set_scratch_root(folder)
    settings.use_scratch_settings(folder)
    kicad_folder = userdirs.kicad_config_base()
    kicad_folder.mkdir(parents=True, exist_ok=True)
    os.environ["KICAD_CONFIG_HOME"] = str(kicad_folder)


def check_in_time(
    path: "Path | str",
    check: Callable[["Path | str"], FolderCheck] = check_folder,
    timeout: float = STARTUP_CHECK_TIMEOUT,
) -> FolderCheck:
    """Run the folder check on a daemon thread; a drive that does not answer in time counts as unavailable.

    A stuck thread is abandoned (never a ThreadPoolExecutor, whose exit would wait for it).
    """
    box: list[FolderCheck] = []
    failure: list[BaseException] = []

    def work():
        try:
            box.append(check(path))
        except BaseException as exc:  # reported on the calling thread
            failure.append(exc)

    thread = threading.Thread(target=work, daemon=True, name="library-folder-check")
    thread.start()
    thread.join(timeout)
    if box:
        return box[0]
    if failure:
        raise failure[0]
    return no_answer(path)


def build_candidates(
    *,
    cli: str | None,
    env: str | None,
    chosen: "Path | str | None" = None,
    kicad: "Path | str | None" = None,
) -> list[Candidate]:
    """The candidates in the locked order: CLI, ENV, CHOSEN, KICAD.

    A candidate that names the folder of an earlier one (the same folder in another spelling) is
    dropped, so a folder is checked once and reported once.
    """
    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add(candidate: Candidate) -> None:
        text = str(candidate.path).strip()
        if text:
            key = spelling_key(text)
            if key in seen:
                return
            seen.add(key)
        candidates.append(candidate)

    if cli is not None:
        # A blank value stays blank: it must never become the working directory
        # A relative folder becomes absolute here: it is saved and offered to KiCad later
        add(Candidate(absolute_folder(cli) if cli.strip() else "", Source.CLI))
    if env is not None and env.strip():
        add(Candidate(absolute_folder(env), Source.ENV))
    if chosen is not None and str(chosen).strip():
        add(Candidate(absolute_folder(chosen), Source.CHOSEN))
    if kicad is not None and str(kicad).strip():
        add(Candidate(absolute_folder(kicad), Source.KICAD))
    return candidates


def _say(text: str) -> None:
    """Write one line to stderr; a frozen build has no stderr."""
    if sys.stderr is not None:
        sys.stderr.write(text + "\n")


def _show_error(text: str) -> None:
    """Show a fatal start-up reason in a message box (the only place to say it without a console)."""
    QMessageBox.critical(None, APP_TITLE, text)


def _fatal(text: str) -> None:
    """Say why the app is stopping: always on stderr, and in a message box when there is no stderr.

    A windowed launch (pythonw, a frozen build, a shortcut without a console) has no stderr, so
    without the box the app would simply not start and say nothing.
    """
    _say(text)
    if sys.stderr is None and QApplication.instance() is not None:
        _show_error(text)


def run_first_run(resolution: Resolution) -> "FirstRunChoice | None":
    """Show the first-run window (application-modal, no parent) and return the choice, None after Quit."""
    # configured_library_folder is looked up at call time so tests can replace it
    dialog = FirstRunDialog(kicad_setup.configured_library_folder(), resolution.notice)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.choice()


def _after_choice(
    choice: FirstRunChoice,
    notes: tuple[Issue, ...],
    check: Callable[["Path | str"], FolderCheck],
    timeout: float,
) -> "MainWindow | int":
    """Check, save and open what the first-run window chose; nothing is saved for a folder that fails the check."""
    folder = absolute_folder(choice.path)  # never save or open a relative folder
    result = check_in_time(folder, check, timeout)
    if not result.usable:
        _fatal(f"Not using {folder}: {result.reason}")
        return 2
    if choice.source is Source.KICAD:
        # The next start resolves to KiCad's folder again
        settings.clear_library_root()
    else:
        settings.save_library_root(folder)
        settings.add_library_recent(folder)
    held = list(notes)
    if choice.created:
        held.append(Issue(Severity.SUCCESS, "library.created", f"Created a new collection in {folder}"))
    return MainWindow(
        folder, choice.source, startup_notes=held, switched=choice.source is Source.CHOSEN,
    )


def check_scratch_folder(folder: Path) -> str | None:
    """None when the scratch folder can be used, else the reason; a folder that fails the check is left as it was."""
    if not folder.exists():
        return "it does not exist"
    if not folder.is_dir():
        return "it is not a folder"
    try:
        settings_folder = folder / userdirs.SETTINGS_FOLDER
        settings_folder.mkdir(exist_ok=True)
        with tempfile.TemporaryFile(dir=settings_folder):
            pass
    except OSError:
        return "the app cannot write there"
    return None


def _start_scratch(argv: list[str], environ: Mapping[str, str]) -> "tuple[Issue, ...] | int":
    """Check and apply the scratch switch before anything is read; the start note, or exit code 2 for a bad value.

    The command line wins over the environment variable. A bad value never falls back to the real folders.
    """
    value = scratch_root_arg(argv)
    source = SCRATCH_OPTION
    if value is None:
        value = environ.get(SCRATCH_ENV_VAR)
        source = SCRATCH_ENV_VAR
    if value is None:
        return ()
    if not value.strip():
        shown, reason = "", "the value is empty"
    else:
        scratch = absolute_folder(value)
        shown, reason = str(scratch), check_scratch_folder(scratch)
    if reason is not None:
        _fatal(f"Not using the scratch folder {shown} (set by {source}): {reason}")
        return 2
    apply_scratch_root(scratch)
    return (Issue(Severity.WARNING, "scratch.in_use", SCRATCH_NOTE.format(folder=scratch)),)


def start_window(
    argv: list[str],
    environ: Mapping[str, str],
    *,
    chosen: "Path | str | None" = _READ,
    kicad: "Path | str | None" = _READ,
    first_run: Callable[[Resolution], "FirstRunChoice | None"] = run_first_run,
    check: Callable[["Path | str"], FolderCheck] = check_folder,
    timeout: float = STARTUP_CHECK_TIMEOUT,
) -> "MainWindow | int":
    """Resolve the library folder and build the window, or return the exit code.

    Everything here runs before any window exists: the remembered folder and KiCad's folder are
    read and checked first (each check bounded by `timeout`), and the first-run window is the only
    dialog, shown only when nothing resolved. The scratch switch, when set, is applied before all of it.
    """
    scratch_note = _start_scratch(argv, environ)
    if isinstance(scratch_note, int):
        return scratch_note
    cli, _rest = parse_args(argv)
    if chosen is _READ:
        chosen = settings.load_library_root()
    if kicad is _READ:
        kicad = kicad_setup.configured_library_folder()
    candidates = build_candidates(
        cli=cli, env=environ.get(ENV_VAR), chosen=chosen, kicad=kicad,
    )
    resolution = resolve_library_root(candidates, check=lambda p: check_in_time(p, check, timeout))
    if resolution.fatal:
        _fatal(resolution.fatal)
        return 2
    if resolution.root is None:
        choice = first_run(resolution)
        if choice is None:
            _say("No library folder chosen; exiting.")
            return 0
        return _after_choice(choice, (*scratch_note, *resolution.notes), check, timeout)
    if resolution.source in (Source.CLI, Source.ENV):
        # A start through --library-root or KICAD_LIBMGR_ROOT is not the user's choice, so library/root stays
        # as it is; the folder joins Recent Library Collections so the user can switch back to it
        settings.add_library_recent(resolution.root)
    return MainWindow(resolution.root, resolution.source, startup_notes=(*scratch_note, *resolution.notes))


def run(argv: list[str] | None = None) -> int:
    """Start the app: resolve the folder, show the window, run the event loop."""
    argv = list(sys.argv if argv is None else argv)
    _cli, rest = parse_args(argv)
    app = QApplication.instance() or QApplication([argv[0], *rest])
    outcome = start_window(argv, os.environ)
    if isinstance(outcome, int):
        return outcome
    outcome.show()
    return app.exec()
