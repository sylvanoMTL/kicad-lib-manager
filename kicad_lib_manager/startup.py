"""Resolve the library folder before any window exists (Phase 15, ROOT-01/02/05/07)."""

import argparse
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Mapping

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from . import kicad_setup, settings
from .collection import (
    Candidate, FolderCheck, Resolution, Source, absolute_folder, check_folder,
    no_answer, resolve_library_root, spelling_key,
)
from .main_window import APP_TITLE, MainWindow
from .models import Issue, Severity
from .widgets.first_run_dialog import FirstRunChoice, FirstRunDialog

ENV_VAR = "KICAD_LIBMGR_ROOT"
STARTUP_CHECK_TIMEOUT = 5.0
# The default of start_window's chosen and kicad: read the saved choice and KiCad's configuration.
# An explicit None means "no such candidate".
_READ = object()


def parse_args(argv: list[str]) -> tuple[str | None, list[str]]:
    """Split argv into the --library-root value and the arguments left for Qt."""
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--library-root", default=None)
    known, rest = parser.parse_known_args(argv[1:])
    return known.library_root, rest


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
    dialog, shown only when nothing resolved.
    """
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
        return _after_choice(choice, resolution.notes, check, timeout)
    if resolution.source in (Source.CLI, Source.ENV):
        # A start through --library-root or KICAD_LIBMGR_ROOT is not the user's choice, so library/root stays
        # as it is; the folder joins Recent Library Collections so the user can switch back to it
        settings.add_library_recent(resolution.root)
    return MainWindow(resolution.root, resolution.source, startup_notes=resolution.notes)


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
