---
phase: 15-choose-library-folder-and-new-collection
fixed_at: 2026-11-23T00:00:00Z
review_path: .planning/phases/15-choose-library-folder-and-new-collection/15-REVIEW.md
iteration: 2
findings_in_scope: 12
fixed: 12
skipped: 0
status: all_fixed
---

# Phase 15: Code Review Fix Report

**Fixed at:** 2026-11-23
**Source review:** .planning/phases/15-choose-library-folder-and-new-collection/15-REVIEW.md
**Iteration:** 2 (pass 1 first, pass 2 for the gap-closure review at the end)

**Summary (both passes):**
- Findings in scope: 12 (pass 1: CR-01, CR-02, WR-01 to WR-07; pass 2: WR-08 to WR-10)
- Fixed: 12
- Skipped: 0 in scope. Out of scope and left: IN-01, IN-03 (pass 1), IN-05, IN-06, IN-07 (pass 2)
- Also done on request: IN-02 (pass 1), IN-04 and UAT-COS-01 (pass 2)

## Pass 1 (first review)

**Summary:**
- Findings in scope: 9 (CR-01, CR-02, WR-01 to WR-07)
- Fixed: 9
- Skipped: 0
- Also done on request: IN-02 (dead `_norm_path` removed). IN-01 and IN-03 were left out of scope, see below.

**Verification environment:** all runs were in the main checkout `` (branch feature/part-importer, `use_worktrees` not used, as instructed), with the project venv. Each new test was also run against the pre-fix source where that was practical, and failed there.

## Fixed Issues

### CR-01: `create_collection` raises AttributeError when `git init` returns an Issue

**Files modified:** `kicad_lib_manager/collection.py`, `tests/test_collection.py`
**Commit:** 9fcbb80
**Applied fix:** Read `done.text` (not `done.message`) from the `Issue`, and added `except Exception` so any unexpected error still reaches the cleanup. Tests: a runner raising `TimeoutExpired` and one raising `FileNotFoundError` on `init` give `collection.create_failed`, leave no `Custom/` behind, and a retry on the same target succeeds; a `RuntimeError` is also cleaned up. Verified failing before the fix.

### CR-02: A relative library folder is accepted, persisted and offered as `KICAD_LIB_GITHUB`

**Files modified:** `kicad_lib_manager/collection.py`, `kicad_lib_manager/startup.py`, `kicad_lib_manager/main_window.py`, `tests/test_collection.py`, `tests/test_startup.py`, `tests/test_main_window_root.py`, `tests/test_choose_folder_dialog.py`, `tests/test_new_collection_dialog.py`
**Commit:** 8e09959
**Applied fix:** New `collection.absolute_folder` (`os.path.abspath`, no disk access, a blank text stays `Path("")`). Applied in `check_folder`, `no_answer`, `check_new_collection`, `create_collection`, `resolve_library_root`, `startup.build_candidates` (CLI, ENV, CHOSEN, KICAD), `startup._after_choice` (first-run hand-off, found by a failing test), `MainWindow.__init__` and `MainWindow._switch_root`. `abspath` was used instead of `resolve()` so the GUI thread and the startup path never touch a slow drive. Two existing resolve tests that asserted the relative fake names now assert the absolute form (the new contract). Tests cover relative `--library-root`, `KICAD_LIBMGR_ROOT`, a typed folder in Choose, New Collection parent `.`, a relative first-run choice, and a switch to a relative folder (saved root, recent list, and the offered `KICAD_LIB_GITHUB` value are absolute). 15 tests fail without the fix.
**Status note:** logic fix, fixed: requires human verification.

### WR-01: Blocking filesystem calls on the GUI thread

**Files modified:** `kicad_lib_manager/main_window.py`, `kicad_lib_manager/collection.py`, `kicad_lib_manager/startup.py`, `tests/test_main_window_root.py`, `tests/test_collection.py`
**Commit:** 05cea7d
**Applied fix:** Recent-folder existence is now checked on one background `TaskWorker` at a time. `_recent_folders` does no disk access: it uses a cache (`_recent_exists`, unknown counts as existing), so the menu shows the last known list at once and drops gone entries when the answer arrives. GUI-thread folder comparisons (`_rebuild_recent_menu`, `_on_recent_chosen`, `_request_switch`, `_refresh_library_actions`) use new disk-free `collection.same_spelling`; the worker's `check_folder` still decides the real same-folder case. `startup._spelling_key` moved to `collection.spelling_key`. `_switch_root` marks the new folder as existing. Existing recent-menu tests now wait for the worker's answer. New tests: existence check runs off the GUI thread and a hung entry does not block the menu; no `Path.resolve` on the GUI thread for these comparisons; `same_spelling` never resolves.
**Not changed:** `configured_library_folder` (glob and read of KiCad's local `kicad_common.json`) is still read on each `_refresh_library_actions`. It is a local config read with no dead-drive risk, and caching it would hide config changes that the existing tests and the path-variable steps rely on. The `same_folder` `OSError`/`ValueError` concern is gone for the GUI paths because they no longer resolve.
**Status note:** logic fix, fixed: requires human verification.

### WR-02: Fatal start errors invisible under pythonw or a frozen build

**Files modified:** `kicad_lib_manager/startup.py`, `tests/test_startup.py`
**Commit:** b075e8d
**Applied fix:** New `startup._fatal(text)`: always `_say` (stderr), and when `sys.stderr is None` (and a `QApplication` exists) also `QMessageBox.critical(None, APP_TITLE, text)` through `startup._show_error`. Used for the failing CLI/ENV override and for a first-run choice that fails its re-check. Exit codes are unchanged (2 for both failures, 0 for Quit, and Quit shows no box). **Text used:** the box shows exactly the stderr line (for example `--library-root: <folder> cannot be used: This folder does not exist. Choose another folder.` or `Not using <folder>: <reason>`), titled `KiCad External Lib Manager`. Tests: box requested when stderr is None for both cases, no box for Quit, no box when stderr exists.

### WR-03: MainWindow root-check workers destroyed while running, late result switches a closed window

**Files modified:** `kicad_lib_manager/main_window.py`, `tests/test_main_window_root.py`
**Commit:** 3d65576
**Applied fix:** `self._closing`, set in `closeEvent` only after every early return that ignores the event, makes `_request_switch` and `_on_root_checked` return early. `closeEvent` uses the shared `join_workers` (one short wait, then park). Finished workers are dropped at the next request. Tests: a gated check at close is parked and its late answer saves nothing and starts no scan; a request after close does nothing; finished workers are pruned. Verified failing before the fix.
**Status note:** logic fix, fixed: requires human verification.

### WR-04: Dialog `_join_workers` freezes the GUI per hung worker; code triplicated

**Files modified:** `kicad_lib_manager/widgets/import_dialog.py`, `kicad_lib_manager/widgets/choose_folder_dialog.py`, `kicad_lib_manager/widgets/new_collection_dialog.py`, `kicad_lib_manager/widgets/first_run_dialog.py`, `tests/test_choose_folder_dialog.py`, `tests/test_first_run_dialog.py`
**Commit:** 98bd872
**Applied fix:** One helper `import_dialog.join_workers(workers, budget_ms=1000)` and one `PARKED_WORKERS` list replace the three `_PARKED` / `_join_workers` copies: a single bounded total wait, then every worker still running is parked (parent removed, dropped from the list when it ends). Dialog behaviour and copy are unchanged. Two existing assertions moved from `cfd._PARKED` / `frd._PARKED` to `PARKED_WORKERS`. Tests: three hung workers cost one budget and are parked; closing a Choose dialog with three hung checks is bounded.

### WR-05: A parent dialog can close and delete a child New Collection dialog mid-creation

**Files modified:** `kicad_lib_manager/widgets/new_collection_dialog.py`, `kicad_lib_manager/widgets/choose_folder_dialog.py`, `kicad_lib_manager/widgets/first_run_dialog.py`, `kicad_lib_manager/main_window.py`, `tests/test_new_collection_dialog.py`, `tests/test_choose_folder_dialog.py`, `tests/test_first_run_dialog.py`, `tests/test_main_window_root.py`
**Commit:** bf8a826
**Applied fix:** `NewCollectionDialog.is_creating()` plus `child_is_creating(child)` (tolerates stand-ins without the method). Choose and First Run dialogs expose `is_creating()` for their child and refuse `done`, `reject` and `closeEvent` while it is true; `MainWindow.closeEvent` ignores the close while its Choose dialog's child is creating (the window stays until the creation ends, like an install). Tests at all four levels.

### WR-06: Cleanup `rmtree` on the whole created target

**Files modified:** `kicad_lib_manager/collection.py`, `tests/test_collection.py`
**Commit:** 03449f0
**Applied fix:** `_cleanup(created, empty_only=target)`: the target folder this call made is removed with `rmdir` (only when empty); everything else this call created is still removed, and the existing `collection.leftovers` issue reports what remains. The check-then-create gap itself is not widened: `Custom` and each folder are created without `exist_ok`, so a folder that appears in between makes the call fail and clean up only its own paths. Test: a file written into the target during `git init` survives a failed creation and `collection.leftovers` is reported. Verified failing before the fix.

### WR-07: New Collection accepts the folder name `.git`

**Files modified:** `kicad_lib_manager/collection.py`, `tests/test_collection.py`
**Commit:** 2bd1b88
**Applied fix:** `validate_collection_name` refuses `.git` in any case and any name that starts with a space. New copy (not in UI-SPEC): `A collection cannot be named .git: git keeps its own data in a folder with that name. Choose another name.` and `A folder name cannot start with a space. Choose another name.` Names such as `.gitignore`, `.github`, `a.git` stay valid. Tests added to the name rules and the new-collection check.

### IN-02: `_norm_path` is dead code (done on request)

**Files modified:** `kicad_lib_manager/library_scanner.py`, `kicad_lib_manager/kicad_setup.py`
**Commit:** 04a85b2
**Applied fix:** Deleted the function and its import. Nothing else referenced it (grep of the repo, tests included).

## Skipped Issues

### IN-01: Help text omits the Check Atomic Parts busy state

**File:** `kicad_lib_manager/widgets/help_dialog.py`
**Reason:** Out of scope (Info finding; `fix_scope` is critical_warning and the request named it as left to the report). Help copy is also governed by the UI-SPEC, so the sentence change belongs to the owner.
**Original issue:** The help page lists four refusal states, but `_switch_refusal` also refuses while Check Atomic Parts is open.

### IN-03: The one-process-starter guard is easy to bypass

**File:** `tests/test_procs.py:77-93`
**Reason:** Out of scope (Info finding, left to the report as requested).
**Original issue:** `test_only_procs_starts_processes` misses import aliases, `QProcess` and root scripts.

## Targeted test results

Run with `env/Scripts/python.exe -m pytest <modules> -n 0 -q` in the main checkout:

- `test_collection`, `test_collection_git`, `test_startup`, `test_main_window_root`, `test_new_collection_dialog`, `test_choose_folder_dialog`, `test_first_run_dialog`, `test_procs`, `test_settings_library`, `test_custom_literals`, `test_kicad_config`, `test_kicad_setup`, `test_main_window`, `test_main_window_chooser` with `--full`: 583 passed.
- `test_import_dialog`, `test_commit_step`, `test_commit_panel`, `test_help_dialog` (quick tier): 413 passed, 114 deselected.
- The whole quick or full suite was not run (the orchestrator does that).

## Pass 2 (gap-closure review)

**Source review:** the same `15-REVIEW.md`, now holding the pass 2 report (gap-closure diff 160f85c..HEAD, plans 15-13..15-16).
**Iteration:** 2

**Summary:**
- Findings in scope: 3 (WR-08, WR-09, WR-10)
- Fixed: 3
- Skipped: 0
- Also done on request: IN-04 (dead `_parse_footprint_refs` removed) and UAT-COS-01 (cosmetic log line from the native UAT screenshots). IN-05, IN-06 and IN-07 were left, see below.

**Verification environment:** all runs in the main checkout `` (branch feature/part-importer, no worktree, as instructed), project venv, `QT_QPA_PLATFORM=offscreen`, QSettings and KiCad config isolated by the test fixtures. Each new test was also run against the pre-fix source and failed there.

### Fixed Issues

#### WR-08: `_switch_root` stats every Destination history entry on the GUI thread

**Files modified:** `kicad_lib_manager/main_window.py`, `tests/test_main_window_root.py`
**Commits:** 358c5e4 (fix and test), 1d1bac6 (follow-up: own task slot)
**Applied fix:** `_set_dest_items(history, check_exists=True)` gained a `check_exists` switch. The follow branch of `_switch_root` now calls it with `check_exists=False`, so the history (new folder first) is shown at once with no `Path.is_dir()` on the GUI thread. `_prune_dest_items` then checks the entries on a `run_in_background` task and `_on_dest_existence` drops the ones that are gone (current entry kept, repository-folder fallback unchanged, ignored after close). This keeps the Destination rule from 15-CONTEXT (the box offers only folders that still exist) without the blocking stat. The first commit put the task in `_root_checks`, which `test_finished_checks_are_dropped_at_the_next_request` counts; the follow-up gives it its own slot `_dest_check` (a newer check replaces it, `closeEvent` cancels it). Start-up `_populate_dest_combo`, Generate Tables and Browse still use the checked form (they predate this diff and are user actions, left as they are).
**Test:** `test_a_switch_does_not_stat_a_dead_history_entry_on_the_gui_thread` puts a blocked entry (`dead`) and a deleted entry (`gone`) in the history, patches `Path.is_dir` to hang on them, and asserts `_switch_root` returns in under 2 s, that no `is_dir` on those entries ran on the GUI thread, and that the gone entry is dropped later while the new folder stays current. Without the fix the switch waits for the 10 s gate and the test fails.
**Status note:** logic fix, fixed: requires human verification.

#### WR-09: the raising-callback test did not exercise the drain guard

**Files modified:** `tests/test_background.py`
**Commit:** d169f71
**Applied fix:** Test only (the guard in `_Dispatcher._drain` was already right). The test now lets the first task finish, adds the second, stops the poll timer so no tick runs between them, waits until both threads returned, and calls `dispatcher._drain()` once: the first callback raises, the second must still be delivered, and the timer must be idle after. Verified: with the `try/except` removed from `_drain` the test fails (the first error escapes the drain); with it present it passes.

#### WR-10: a task could stay pending forever

**Files modified:** `kicad_lib_manager/widgets/background.py`, `tests/test_background.py`
**Commit:** 92260e8
**Applied fix:** `work()` catches `BaseException`, so a `SystemExit` or `KeyboardInterrupt` in `fn` still puts a failure outcome on the queue (text `SystemExit: 3`). `thread.start()` is wrapped: on any exception the counter is decremented, `_returned` is set and the task is cancelled (which forgets it and stops the idle timer), then the error is re-raised to the caller.
**Tests:** `test_a_base_exception_from_fn_leaves_no_stuck_task` (failure text delivered, task done, poll timer stops, counter back to its start) and `test_a_failing_thread_start_leaves_no_stuck_task` (a `RuntimeError` from `Thread.start` reaches the caller; nothing pending, counter unchanged, timer stopped). Both fail on the pre-fix source.

#### IN-04 (done on request): dead `_parse_footprint_refs`

**Files modified:** `kicad_lib_manager/library_scanner.py`
**Commit:** 91a189d
**Applied fix:** Deleted the wrapper. A search of the package and the tests found no use (only two prose mentions in `.claude/CLAUDE.md`, which is not touched). A deletion has no behaviour test of its own; the scanner tests (46 passed) cover both callers.

#### UAT-COS-01 (cosmetic, from the native UAT screenshots)

**Files modified:** `kicad_lib_manager/main_window.py`, `tests/test_main_window_root.py`
**Commit:** 13c5503
**Applied fix:** With `KICAD_LIB_GITHUB` unset the declined-offer log line now reads "KiCad's KICAD_LIB_GITHUB is not set. Generate Tables and Install Part will offer the change again." (it was "KiCad still points at (not set). ..."). With the variable set the line is unchanged ("KiCad still points at {folder}. ..."). The UI-SPEC row for this line lists only the set-variable wording, so the unset variant is new copy for the owner to confirm.
**Tests:** the three existing unset-case assertions now expect the new line; the new `test_declined_offer_names_the_folder_kicad_still_points_at` pins the set-variable wording.

### Skipped Issues

#### IN-05: `fit_height_to_content` only grows the dialog and never clamps to the screen

**File:** `kicad_lib_manager/widgets/new_collection_dialog.py:63-84`
**Reason:** Out of scope (Info finding, cosmetic; `fix_scope` is critical_warning and the request left it). A clamp changes the dialog geometry rules from the UI-SPEC, which is the owner's call.
**Original issue:** The height only grows, is never clamped to the available screen and never shrinks back.

#### IN-06: the runner's GUI-thread-only contract is unenforced; orphaned outcomes wait in the queue

**File:** `kicad_lib_manager/widgets/background.py`
**Reason:** Out of scope (Info finding, left as requested).
**Original issue:** No thread assertion in `_dispatcher()`, and a cancelled task's late outcome sits in `_outcomes` until the next `run_in_background`.

#### IN-07: `test_folder_checks_never_use_a_qthread` pins an exact `TaskWorker(` count

**File:** `tests/test_exit_with_hung_check.py:62-66`
**Reason:** Out of scope (Info finding, left as requested; same class as the deferred IN-03).
**Original issue:** `assert len(calls) == 2` breaks on a legitimate third `TaskWorker` and is bypassed by an alias.

### Targeted test results (pass 2)

Run with `env/Scripts/python.exe -m pytest <modules> -n 0 -q` in the main checkout, `QT_QPA_PLATFORM=offscreen`:

- `test_background`, `test_main_window_root`, `test_empty_libraries`, `test_exit_with_hung_check`, `test_main_window`, `test_main_window_chooser`, `test_main_window_import`: 278 passed.
- `test_main_window_migration`, `test_dialog_geometry`, `test_startup`: 58 passed.
- `test_empty_libraries`, `test_scanner_issues`, `test_scanner_skip_dirs` (after IN-04): 46 passed.
- The whole quick or full suite was not run (the orchestrator does that). No process was left running.

---

_Fixed: 2026-11-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
