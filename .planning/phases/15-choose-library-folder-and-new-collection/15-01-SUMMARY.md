---
phase: 15-choose-library-folder-and-new-collection
plan: 01
subsystem: startup
tags: [library-root, startup, collection, folder-check, pyside6]
requires: []
provides:
  - "kicad_lib_manager/collection.py: Qt-free collection contract (constants, Source, folder check, resolve order)"
  - "kicad_lib_manager/startup.py: --library-root / KICAD_LIBMGR_ROOT start-up and thin entry point"
  - "MainWindow(library_root, source, startup_notes) with title and Library folder row"
affects: [15-02, 15-05, 15-06, 15-07, 15-08, 15-09, 15-10, 15-11, 15-12]
tech-stack:
  added: []
  patterns:
    - "folder resolved before any window exists, passed down as the window's one identity"
    - "daemon-thread timed check (never ThreadPoolExecutor)"
key-files:
  created:
    - kicad_lib_manager/collection.py
    - kicad_lib_manager/startup.py
    - tests/test_startup.py
    - tests/test_collection.py
    - tests/collectionfixtures.py
    - tests/test_main_window_root.py
  modified:
    - kicad_lib_manager.py
    - kicad_lib_manager/main_window.py
    - tests/test_main_window.py
    - tests/test_main_window_chooser.py
    - tests/test_main_window_import.py
    - tests/test_main_window_migration.py
    - tests/test_checkout_warning.py
key-decisions:
  - "Candidate.path and the check functions accept Path | str so a blank --library-root stays blank and is never read as the working directory (Path('') is '.')"
  - "Held CHOSEN note is appended when the loop ends, after any KiCad-skipped note (literal reading of 'once the loop ends')"
  - "start_window's first_run hand-off returns an object with .root and .source (a Resolution) or None; plan 15-10 replaces _no_first_run"
requirements-completed: [ROOT-01, ROOT-02, ROOT-07, ROOT-08]
duration: 45 min
completed: 2026-11-23
status: complete
actuals:
  tokens: 40000
  tasks: 2
  commits: 2
plan_head_before: 14b857f9b99f67b25795f88084877b20a9b377ec
plan_head_after: 5001e1e
commits: 2
---

# Phase 15 Plan 01: Library folder tracer Summary

The app now resolves its library folder (`--library-root`, `KICAD_LIBMGR_ROOT`, later the remembered, KiCad and legacy folders) before any window exists, and `MainWindow(library_root)` scans, caches, checks and writes only in that folder.

## Public names

collection.py (Qt-free, imports only `.models`): `OWN_DIR`, `SYMBOLS_DIR`, `FOOTPRINTS_DIR`, `MODELS_DIR`, `SHARED_FOOTPRINT_LIBRARY`, `THIRD_PARTY_DIR`, `PATH_LENGTH_WARNING`, `APP_DIR`, `folder_key`, `same_folder`, `is_collection`, `source_of`, `Source`, `CheckRow`, `FolderCheck`, `check_folder(path, *, current=None)`, `no_answer`, `Candidate`, `Resolution`, `resolve_library_root(candidates, check=check_folder)`; private `_holds_parts`, `_is_empty`, `_chosen_note`.

startup.py: `ENV_VAR`, `STARTUP_CHECK_TIMEOUT`, `parse_args`, `check_in_time`, `build_candidates`, `_say`, `_no_first_run`, `start_window`, `run`.

main_window.py: `MainWindow(library_root, source=Source.LEGACY, startup_notes=())`, attributes `_root`, `_source`, `_startup_notes`, `_root_path`, `_root_tag`, method `_show_root`, helper `_folder_name`. The module constant for the code folder is gone (0 hits of `REPO_ROOT`).

## Tasks

1. Task 1 (tracer): collection.py, startup.py, thin kicad_lib_manager.py, MainWindow(library_root), five harness edits, tests/test_startup.py (13 tests incl. the `test_window_uses_only_the_folder_it_was_given` invariant). Commit 4e2c290.
2. Task 2: tests/test_collection.py, tests/collectionfixtures.py, tests/test_main_window_root.py (row, title, tag, ampersand, elision, held notes, info line, length warning). Commit 5001e1e.

The tracer verify was re-run end to end (auto-style gate, no checkpoint): start tests, the five harness modules and the 3.10 grammar gate all pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_toolbar_import_button_first read the toolbar as layout item 0**
- **Found during:** Task 1 verification
- **Issue:** the new Library folder row is now item 0 of the central layout, so the toolbar is item 1 (harness test needed more than the two-line edit).
- **Fix:** `itemAt(0)` became `itemAt(1)` with a one-line comment in tests/test_main_window_import.py.
- **Commit:** 4e2c290

**2. [Rule 1 - Test design] Length-sensitive tests depended on a short tmp_path**
- **Found during:** Task 2
- **Issue:** a pytest tmp_path on this machine is already about 100 characters, so a 3-row expectation got the length warning.
- **Fix:** `no_length_row` fixture and a patched `PATH_LENGTH_WARNING`; the boundary test patches the limit to `len(path)` and `len(path) - 1`, and a separate test pins the constant at 100.
- **Commit:** 5001e1e

### Plan-shape notes

- The Library folder row, title helper and held-note flush (Task 2 action for main_window.py) were written in the same change as the Task 1 constructor, so they sit in the Task 1 commit; Task 2 therefore had no RED phase for them (its tests passed on first run after the test fixes above).
- `Candidate.path` and `check_folder`/`no_answer` accept `Path | str` instead of `Path` only (see key-decisions).
- The execution_context ledger file `gsd-plan-head-before-15-01` was not written (shell restrictions); `plan_head_before` is the dispatch base 14b857f.

**Total deviations:** 2 auto-fixed, 3 shape notes. **Impact:** none on behavior; all must-have truths covered by tests.

## Self-Check: PASSED

Files verified present: collection.py, startup.py, the four new test modules; commits 4e2c290 and 5001e1e are ancestors of HEAD. Targeted runs: 252 passed (start, collection, window root, the five harnesses, grammar gate, layering, isolation).

## Known Stubs

None. `_no_first_run` is an intentional default hand-off that plan 15-10 replaces with the first-run window (ROOT-05).
