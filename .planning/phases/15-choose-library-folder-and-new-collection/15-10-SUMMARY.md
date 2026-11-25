---
phase: 15-choose-library-folder-and-new-collection
plan: 10
subsystem: main-window-and-startup
tags: [library-folder, choose-folder, first-run, empty-collection, focus, startup, pyside6]
requires: ["15-01", "15-05", "15-07", "15-08", "15-09"]
provides:
  - "File > Choose Library Folder... (first in File) and the Change Folder... button open ChooseLibraryFolderDialog window-modal"
  - "empty-collection page in a QStackedLayout list area"
  - "focus rule after the first scan of a folder (LibraryTableWidget.focus_symbols)"
  - "startup.start_window reads library/root and KICAD_LIB_GITHUB; run_first_run; first-run choice saving"
affects: [15-11]
tech-stack:
  added: []
  patterns:
    - "_library_actions_busy(running): one rule for every library-folder control, equal to _switch_refusal"
    - "_READ sentinel default: None means no candidate, the sentinel means read settings / KiCad config"
key-files:
  created: []
  modified:
    - kicad_lib_manager/main_window.py
    - kicad_lib_manager/widgets/library_table.py
    - kicad_lib_manager/startup.py
    - tests/test_main_window_root.py
    - tests/test_library_table_widget.py
    - tests/test_startup.py
key-decisions:
  - "A first-run choice is re-checked (check_in_time) before anything is saved; a failure prints 'Not using {path}: {reason}' and exits 2 (T-15-27/T-15-29)"
  - "build_candidates dedupes by a lexical key (normcase/normpath/abspath), not Path.resolve(), so a missing or slow drive never blocks the main thread before the window exists"
  - "The empty-page body label uses an Ignored horizontal size policy: a long path with no break point never widens the window (it clips instead)"
  - "The Recent submenu and Use KiCad's Folder now follow the same busy rule as Choose (all of _switch_refusal), not only a running scan"
requirements-completed: [ROOT-02, ROOT-03, ROOT-05, ROOT-06, ROOT-07, ROOT-08]
status: complete
duration: "~70 min"
completed: 2026-11-23
actuals:
  tokens: 40000
  tasks: 2
  commits: 4
plan_head_before: 858aeeae6d9b2647e10923251f8b3320c6c9439f
plan_head_after: 6bbe38c6bbf033b38eaecf7df1d98feb5b4fdd19
commits: 4
---

# Phase 15 Plan 10: Choose Library Folder, empty page and the full start Summary

The user-facing loop is closed: the main window can choose or create a library folder (File menu and the Change Folder... button), an empty collection says what to do next, focus lands on the next step, and the app starts in the locked order (override, env, remembered folder, KiCad's folder, app folder, first-run window) with a note when a remembered folder was skipped.

## What was built

- **Task 1** (RED `5cba83d`, GREEN `2d8fa28`): `CHOOSE_FOLDER_TEXT`/`_CHOOSE_TIP`, `_act_choose_folder` first in File (no shortcut, mnemonic C), `_change_folder_btn` last in the library-folder row, `_open_choose_folder` (busy refusal, raises an open dialog, else `ChooseLibraryFolderDialog(self._root, origin="main", parent=self)` + `open()`), `_on_choose_folder_finished` (logs success `Created a new collection in {path}` for a created collection, then `_request_switch(path, Source.CHOSEN)` so the folder is re-checked off the GUI thread). List area is a `QStackedLayout` (page 0 trees, page 1 empty-collection heading and body); `_show_list_page` is called with None from `_start_scan` and `_switch_root` and with the result from `_on_scan_finished` and `_on_library_rescanned`. `_focus_after_scan` is armed in the constructor and `_switch_root`, consumed at the end of `_finish_scan` (no worker, no switch offer pending) or in `_on_path_var_check` after the offer question; `_apply_focus` focuses the Symbols tree via `LibraryTableWidget.focus_symbols()` or the Import Part... button.
- **Task 2** (RED `5a03636`, GREEN `6bbe38c`): `start_window` defaults `chosen`/`kicad` to `_READ` (reads `settings.load_library_root()` and `kicad_setup.configured_library_folder()`, an explicit None means no candidate) and `first_run` to `run_first_run` (application-modal `FirstRunDialog(configured_library_folder(), resolution.notice)`; Quit or Esc gives None). A choice is re-checked, then `save_library_root` + `add_library_recent` (CHOSEN) or `clear_library_root` (KICAD), the held `library.created` success note is added for a created collection, and `MainWindow(..., switched=source is CHOSEN)` opens. None still writes `No library folder chosen; exiting.` and exits 0 without saving. `build_candidates` drops a later candidate naming an earlier one's folder.

## Verification

- `tests/test_main_window_root.py`, `test_library_table_widget.py`, `test_main_window.py`, `test_main_window_import.py`, `test_main_window_chooser.py`, `test_main_window_migration.py`, `test_checkout_warning.py`: 291 passed (after Task 1).
- `tests/test_startup.py test_collection.py test_first_run_dialog.py test_layering.py test_custom_literals.py test_annotations_resolve.py test_main_window_root.py`: 325 passed (after Task 2); `test_docs_atomic.py test_importer_layering.py` pass with the layering set.
- Acceptance greps: `def run_first_run` 1, `load_library_root|configured_library_folder` in startup.py 4, `Choose Library Folder` in main_window.py 3, `QStackedLayout` 2, empty heading 1, `def focus_symbols` 1, the three named startup tests 3.
- Whole suites not run (the orchestrator owns that).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The empty-page body widened the window for a long unbroken path**
- **Found during:** Task 1 (the existing `test_long_path_is_elided_not_widening` jumped to a 3084 px minimum width)
- **Fix:** Ignored horizontal size policy on the body label.
- **Commit:** 2d8fa28

**2. [Rule 2 - Missing critical] A first-run choice was saved without a re-check**
- **Found during:** Task 2 (T-15-29: a dialog result must pass the folder check before use)
- **Fix:** `_after_choice` re-checks through `check_in_time`; a failing folder is not saved (test added).
- **Commit:** 6bbe38c

**3. [Rule 3 - Blocking] `_refresh_library_actions` runs from `_build_menu`, before the button exists**
- **Fix:** it reads the button with `getattr(..., None)`.
- **Commit:** 2d8fa28

### Plan-shape notes

- `test_menu_order` (plan 15-07) was updated: Choose is now action 0 and the mnemonics read C, K, L, O.
- `_refresh_library_actions()` is now also called when the import, migration and Check Atomic Parts windows open or close, when a post-install finishes and when the KiCad checks start or end, so the Choose action and Change Folder... follow every busy state the plan lists (previously only the scan state fed them). The Recent submenu and Use KiCad's Folder share the rule.
- `tests/test_library_table_widget.py` gained two `focus_symbols` tests (not in the plan's files list).
- The `start()` helper in tests/test_startup.py now passes a None-returning `first_run` by default so no test opens the real first-run window.
- The 900 px backstop (200-character path plus the amber tag) is an offscreen geometry check; a look at 150-175% display scaling is left to plan 15-11's UAT.
- Known limit: the empty-page body clips (rather than wraps) a path with no space or slash break point, such as one long Windows backslash path above the window width; the full path is in the Library folder row and the log.

## Known Stubs

None.

## Threat Flags

None. T-15-29 (every candidate through `check_in_time`; dialog results re-checked by `_request_switch` or `_after_choice`), T-15-30 (settings change only after a first-run choice or a successful switch; `test_deleted_remembered_folder_falls_back_with_note` and the not-saved test assert it), T-15-31 (resolve and first run precede `MainWindow`; `test_resolve_runs_before_any_window`) are covered by tests.

## Self-Check: PASSED

Modified files present; commits 5cba83d, 2d8fa28, 5a03636, 6bbe38c are ancestors of HEAD; STATE.md and ROADMAP.md untouched.
