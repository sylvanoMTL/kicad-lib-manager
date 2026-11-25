---
phase: 15-choose-library-folder-and-new-collection
plan: 13
subsystem: main-window, background-checks
tags: [gap-closure, wr-03, daemon-thread, folder-check, exit-crash]
requires: ["15-07", "15-10"]
provides:
  - "kicad_lib_manager/widgets/background.py: run_in_background, BackgroundTask, running_tasks, POLL_MS"
  - "MainWindow._root_checks / _recent_check on daemon threads; closeEvent cancels, never waits"
  - "tests/hungcheckchild.py child script (modes switch, recent) and tests/test_exit_with_hung_check.py"
affects: [15-15]
tech-stack:
  added: []
  patterns: ["daemon thread + queue.SimpleQueue drained by a GUI-thread QTimer; never a QThread for a check that can block on a dead drive"]
key-files:
  created:
    - kicad_lib_manager/widgets/background.py
    - tests/hungcheckchild.py
    - tests/test_exit_with_hung_check.py
    - tests/test_background.py
  modified:
    - kicad_lib_manager/main_window.py
    - tests/test_main_window_root.py
decisions:
  - "A check thread only runs the function and puts its outcome on a queue.SimpleQueue; one lazily created GUI-thread dispatcher with a 15 ms QTimer (running only while an outcome is outstanding) delivers it"
  - "closeEvent cancels every pending check at once (callbacks released, outcome dropped) and abandons the thread; no join, no parking"
  - "The Recent existence check calls the module function _recent_folder_exists so tests and the child can replace it"
status: complete
metrics:
  duration: "~35 min"
  completed: 2026-11-23
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 07f30d7f502005e2c40aa28ce4a1b2ea499734be
plan_head_after: bfd04d7
---

# Phase 15 Plan 13: Folder checks on daemon threads Summary

The main window's two folder checks that can block on a dead drive (the switch check and the Recent existence check) now run on daemon Python threads through `widgets/background.run_in_background`, so closing the app with one still blocked exits with code 0 instead of aborting with 0xC0000409.

## RED evidence

At the base (before the main_window.py edit) the child test ran against a copy of the base tree: the child printed `BLOCKED_AT_CLOSE=1` and `EVENT_LOOP=0`, then the process ended with **returncode 3221226505** and stderr `QThread: Destroyed while thread '' is still running`. After the edit the same test passes (returncode 0, no "QThread: Destroyed").

## Runner API (plan 15-15 moves the three dialogs onto it)

- `POLL_MS = 15`
- `run_in_background(fn: Callable[[], object], on_result: Callable[[object], None], on_failed: Callable[[str], None] | None = None, *, name: str = "library-folder-check") -> BackgroundTask` (GUI thread only; `RuntimeError` when no QCoreApplication exists). Failure text is `f"{type(exc).__name__}: {exc}"`.
- `BackgroundTask`: `name`, `is_running()` (function has not returned), `is_done()` (outcome delivered or cancelled), `cancel()` (outcome never delivered, callbacks released, thread abandoned).
- `running_tasks() -> int` (started tasks whose function has not returned).
- `_dispatcher()` is private and test-facing (the poll-timer test reads `_dispatcher()._timer`).
- A callback that raises goes to `sys.excepthook` and the next delivery still runs.

## Child script (plan 15-15 adds the dialog modes)

`python tests/hungcheckchild.py MODE WORK` with `WORK` holding collections `a` and `b`. Modes: `switch`, `recent`. It redirects QSettings with `QSettings.setPath` into `WORK/qsettings`, patches `main_window` (`CHECKOUT_CONFIG_BASE`, `load_kicad_fp_dir`, `scan_all`, `kicad_running`), blocks one check on a never-set Event, and closes the window. ASCII markers on stdout: `BLOCKED_AT_CLOSE=<0|1>`, `EVENT_LOOP=<code>`, `TIMEOUT=<what>`. The parent test asserts the marker first, then returncode 0, then no `QThread: Destroyed` in stderr.

## Verification

- `tests/test_exit_with_hung_check.py` (switch, recent) and `tests/test_background.py` (7 tests): 9 passed.
- `tests/test_main_window_root.py`, `test_main_window.py`, `test_main_window_import.py`, `test_main_window_chooser.py`, `test_main_window_migration.py`, `test_checkout_warning.py`: 260 passed. `tests/test_annotations_resolve.py` with `test_main_window_root.py`: 94 passed.
- main_window.py: no `join_workers`, no `_root_check_workers`, `TaskWorker(` only for the two KiCad-open checks.

## Deviations from Plan

None - plan executed exactly as written. Minor ordering note: `tests/hungcheckchild.py` carried both modes from the first commit (the `recent` parametrization was added in the second commit with the runner tests, as planned).

## Known Stubs

None.

## Threat Flags

None. The thread never calls into Qt (T-15-37); cancel drops late outcomes (T-15-36); the child test pins a clean exit (T-15-35).

## Self-Check: PASSED
