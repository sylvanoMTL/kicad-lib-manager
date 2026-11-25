---
phase: 15-choose-library-folder-and-new-collection
plan: 15
subsystem: dialogs, background-checks
tags: [gap-closure, daemon-thread, folder-check, exit-crash, choose-folder, first-run, new-collection]
requires: ["15-13", "15-14"]
provides:
  - "Choose Library Folder, first-run row 1 and New Collection checks and creation on widgets/background.run_in_background"
  - "_run(fn, on_result, on_failed) and _cancel_tasks() and _tasks: list[BackgroundTask] on the three dialogs"
  - "tests/hungcheckchild.py modes choose, first-run, new-collection; test_folder_checks_never_use_a_qthread"
affects: []
tech-stack:
  added: []
  patterns: ["a dialog owns a list of BackgroundTask and cancels it in done/closeEvent; no wait, no QThread to park"]
key-files:
  created: []
  modified:
    - kicad_lib_manager/widgets/choose_folder_dialog.py
    - kicad_lib_manager/widgets/first_run_dialog.py
    - kicad_lib_manager/widgets/new_collection_dialog.py
    - kicad_lib_manager/widgets/import_dialog.py
    - tests/test_choose_folder_dialog.py
    - tests/test_first_run_dialog.py
    - tests/test_new_collection_dialog.py
    - tests/hungcheckchild.py
    - tests/test_exit_with_hung_check.py
decisions:
  - "The creation task of New Collection is started through the same _run as the checks but is never cancelled: reject, done and closeEvent still refuse while _creating, so _cancel_tasks cannot run during a creation"
  - "_run prunes finished tasks from _tasks before adding one, so a long-lived dialog does not accumulate them"
  - "The dialog child modes build the dialog directly after the QApplication (no MainWindow) and close it with reject()"
status: complete
metrics:
  duration: "~40 min"
  completed: 2026-11-23
actuals:
  tokens: 16000
  tasks: 3
  commits: 5
plan_head_before: 37502d507c386a73025e0b058db2889a8eb5e516
plan_head_after: c751bf1
---

# Phase 15 Plan 15: Dialog folder checks on the background runner Summary

The Choose Library Folder, first-run and New Collection windows now run their folder checks (and the New Collection creation) on daemon threads through `widgets/background.run_in_background`, close by cancelling instead of joining and parking a QThread, and the join-then-park helper, its parked list and its budget constant are deleted, so a dead drive can no longer abort the process at exit from any window.

## RED evidence (returncode of each new child mode before its dialog edit)

| Mode | Dialog tree used | returncode | stderr |
|------|------------------|-----------:|--------|
| choose | base 37502d5 (main window opens the Choose dialog) | 3221226505 (0xC0000409) | `QThread: Destroyed while thread '' is still running` |
| first-run | 76305f0 (first-run still on TaskWorker) | 3221226505 | `QThread: Destroyed while thread '' is still running` |
| new-collection | 76305f0 (New Collection still on TaskWorker) | 3221226505 | `QThread: Destroyed while thread '' is still running` |

All three print `BLOCKED_AT_CLOSE=1` and `EVENT_LOOP=0` before the abort. After the edits all three exit with code 0 and no "QThread: Destroyed".

## What changed

- `choose_folder_dialog.py`, `first_run_dialog.py`, `new_collection_dialog.py`: `_workers` became `_tasks: list[BackgroundTask]`; `_spawn` and the join wrapper became `_run(...)` and `_cancel_tasks()`; the work functions take no `progress` argument; `done` and `closeEvent` call `_cancel_tasks()` after their existing refusals (`is_creating()` / `_creating`), `_closing` and the debounce stop. The request counter and `_closing` rules are kept, so a late answer changes nothing. The 15-14 `fit_height_to_content` calls are untouched.
- `import_dialog.py`: the parked-worker list, the budget constant and the join-then-park helper (27 lines) are deleted. `TaskWorker` and `import time` stay (import dialog and the two KiCad-open checks in the main window).
- Tests: `test_esc_rejects_and_cancels_checks` (renamed), `test_closing_with_several_hung_checks_is_bounded` (asserts the three tasks are cancelled and still blocked, close takes under 1 s), `test_close_during_check_cancels_and_chooses_nothing` (first-run, also asserts no sub-dialog opened by the late answer), `test_checks_are_cancelled_on_close` (renamed from `test_workers_are_joined_on_close`; the late answer redraws nothing), `test_create_success_accepts` now also asserts the creation task is still running and not done after every refused close. The direct test of the deleted helper is gone.
- `tests/hungcheckchild.py`: modes `choose`, `first-run`, `new-collection`. `tests/test_exit_with_hung_check.py`: parametrized over five modes plus `test_folder_checks_never_use_a_qthread` (AST: no `TaskWorker` or `QThread` name in the three dialog modules; `TaskWorker(` called exactly twice in `main_window.py`; no module under `kicad_lib_manager/` names the helper, list or budget constant).

## Verification

- `tests/test_exit_with_hung_check.py`, `test_choose_folder_dialog.py`, `test_first_run_dialog.py`, `test_new_collection_dialog.py`, `test_import_dialog.py`: 312 passed (3 deselected by the project's default markers).
- `tests/test_main_window_root.py`, `test_background.py`, `test_annotations_resolve.py`: 101 passed.
- Earlier in the run: `test_dialog_geometry.py` and `test_startup.py` with the three dialog modules: 83 passed.
- Acceptance greps: `TaskWorker` count 0 in the three dialog modules; `join_workers|PARKED_WORKERS|JOIN_BUDGET_MS` count 0 under `kicad_lib_manager` and `tests`; `class TaskWorker` still in `import_dialog.py` (1).

## UI-SPEC note

The UI-SPEC line "TaskWorker for the folder check and for creating a collection" is now served by `widgets/background.py` (same contract: off the GUI thread; the outcome arrives on the GUI thread; failure text `ExceptionName: message`). It is not edited here.

## Deviations from Plan

None - plan executed exactly as written. Two small notes:
- The `run_in_background` acceptance count (>= 3) for `new_collection_dialog.py` counts lines; the import, the single call in `_run` and a comment above the creation call (which names the runner) give 3.
- Each plan commit pair for the tracer and the child modes is a `test(15-15)` commit followed by the `feat`/`refactor` commit, as the TDD gate asks.

## Known Stubs

None.

## Threat Flags

None. T-15-40 (parked QThread abort): proven by three child processes exiting 0 and the AST guard. T-15-41 (abandoned creation): the creation task is never cancelled and every close path still refuses while creating (existing WR-05 tests pass, plus the new running-and-not-done assertion). T-15-42 (late answer): `_cancel_tasks()` plus the kept `_closing` and request-counter checks; the renamed close tests release the gate afterwards and assert nothing changed.

## Self-Check: PASSED

- FOUND: the nine files in key-files.modified (all changed in commits bc5013a, 76305f0, 5e8e276, 87a85c2, c751bf1).
- FOUND commits on this branch: bc5013a, 76305f0, 5e8e276, 87a85c2, c751bf1.
