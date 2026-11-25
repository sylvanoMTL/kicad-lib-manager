"""Child process of test_exit_with_hung_check.py (a helper script, not a test module).

Usage: python tests/hungcheckchild.py MODE WORK

WORK holds the collections `a` and `b` made by the parent. The script starts the real MainWindow
offscreen, blocks one folder check forever on an Event that is never set (a dead network drive),
prints BLOCKED_AT_CLOSE=1 once that check is blocked, closes the window, ends the event loop and
exits with the loop's code. A QThread still blocked at that point would abort the interpreter at
exit; a daemon thread is simply abandoned.

Modes: switch (the switch check of a Recent or Choose result), recent (the Recent existence check),
choose (the Choose Library Folder dialog opened from the main window, checking folder b),
first-run (the first-run window, row 1 checking folder b), new-collection (the New Collection dialog, its
first check). The dialog modes build the dialog directly, without a MainWindow, and close it with reject().
Markers on stdout (ASCII only): BLOCKED_AT_CLOSE=<0|1>, EVENT_LOOP=<code>, TIMEOUT=<what>.
"""
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEADLINE = 20.0


def main(mode: str, work: Path) -> int:
    from PySide6.QtCore import QSettings, QTimer, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    # A child does not inherit the test's QSettings redirect, and on Windows QSettings ignores APPDATA
    settings_dir = work / "qsettings"
    settings_dir.mkdir(exist_ok=True)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))

    def handler(_mode, _context, message):
        sys.stderr.write(f"{message}\n")
        sys.stderr.flush()

    qInstallMessageHandler(handler)

    from kicad_lib_manager import main_window, settings
    from kicad_lib_manager.collection import Source
    from kicad_lib_manager.models import ScanResult

    a, b = work / "a", work / "b"
    config_base = work / "kicad_cfg"
    config_base.mkdir(exist_ok=True)
    fp_dir = work / "kicad_fp"
    fp_dir.mkdir(exist_ok=True)
    main_window.CHECKOUT_CONFIG_BASE = config_base
    main_window.load_kicad_fp_dir = lambda: fp_dir
    main_window.scan_all = lambda root, progress=None, kicad_fp_dir=None, **kwargs: ScanResult()
    main_window.kicad_running = lambda: []

    gate = threading.Event()  # never set: the dead drive does not answer
    entered = threading.Event()
    if mode == "switch":
        real_check = main_window.check_folder

        def check(path, *, current=None):
            if Path(path) == b:
                entered.set()
                gate.wait()
            return real_check(path, current=current)

        main_window.check_folder = check
    elif mode == "recent":
        settings.add_library_recent(b)

        def exists(entry):
            if Path(entry) == b:
                entered.set()
                gate.wait()
            return Path(entry).is_dir()

        main_window._recent_folder_exists = exists
    elif mode == "choose":
        import functools

        from kicad_lib_manager.widgets import choose_folder_dialog
        real_check = choose_folder_dialog.check_folder

        def blocking(path, *, current=None):
            if Path(path) == b:
                entered.set()
                gate.wait()
            return real_check(path, current=current)

        main_window.ChooseLibraryFolderDialog = functools.partial(
            choose_folder_dialog.ChooseLibraryFolderDialog, check=blocking
        )
    elif mode == "first-run":
        from kicad_lib_manager.widgets import first_run_dialog

        def blocking(path, *, current=None):
            entered.set()
            gate.wait()

        def make_dialog():
            dialog = first_run_dialog.FirstRunDialog(str(b), check=blocking)
            dialog.show()
            dialog._on_use_kicad()
            return dialog
    elif mode == "new-collection":
        from kicad_lib_manager.widgets import new_collection_dialog

        def blocking(parent, name, *, git_found, app_dir, environ):
            entered.set()
            gate.wait()

        def make_dialog():
            return new_collection_dialog.NewCollectionDialog(
                origin="setup", parent_folder=work, name="blocked", check=blocking,
                find_git=lambda root: Path("git"), app_dir=work / "app", environ={},
            )
    else:
        print(f"TIMEOUT=unknown mode {mode}", flush=True)
        return 3

    app = QApplication([])

    def pump_until(what: str, done) -> bool:
        end = time.monotonic() + DEADLINE
        while not done():
            if time.monotonic() > end:
                print(f"TIMEOUT={what}", flush=True)
                return False
            app.processEvents()
            time.sleep(0.01)
        return True

    if mode in ("first-run", "new-collection"):
        dialog = make_dialog()
        if not pump_until("blocked check", entered.is_set):
            print("BLOCKED_AT_CLOSE=0", flush=True)
            return 3
        print("BLOCKED_AT_CLOSE=1", flush=True)
        dialog.reject()
        QTimer.singleShot(0, app.quit)
        code = app.exec()
        print(f"EVENT_LOOP={code}", flush=True)
        return code
    window = main_window.MainWindow(a, Source.CHOSEN)
    window.show()
    if not pump_until("first scan", lambda: window._worker is None):
        return 3
    if mode == "switch":
        window._request_switch(b, Source.CHOSEN)
    elif mode == "choose":
        window._open_choose_folder()
        dialog = window._choose_dialog
        if not pump_until("first dialog check", lambda: not dialog._pending):
            return 3
        dialog._field.setText(str(b))
    if not pump_until("blocked check", entered.is_set):
        print("BLOCKED_AT_CLOSE=0", flush=True)
        return 3
    print("BLOCKED_AT_CLOSE=1", flush=True)
    window.close()
    QTimer.singleShot(0, app.quit)
    code = app.exec()
    print(f"EVENT_LOOP={code}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], Path(sys.argv[2])))
