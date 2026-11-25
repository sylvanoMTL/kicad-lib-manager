---
phase: 16-repo-split
plan: 02
subsystem: startup
tags: [library-folder, resolve-order, first-run, help-dialog, tdd]

requires:
  - phase: 15-library-root
    provides: "Source enum, resolve_library_root, start_window, first-run window"
provides:
  - "Library folder resolves only from --library-root, KICAD_LIBMGR_ROOT, the chosen folder, KiCad's KICAD_LIB_GITHUB, then the first-run window"
  - "Source has four members (CLI, ENV, CHOSEN, KICAD); the code-folder fallback is deleted"
affects: [16-07 CLAUDE.md rewrite, 16-06 test corpus]

actuals:
  tokens: 9000
  tasks: 2
  commits: 3

plan_head_before: ed3a784ac0375414f438f462d178cf46254173e1
plan_head_after: 4d0fb63

tech-stack:
  added: []
  patterns:
    - "A code-folder collection is never a candidate: pinned by signature and behavior tests"

key-files:
  created: []
  modified:
    - kicad_lib_manager/collection.py
    - kicad_lib_manager/startup.py
    - kicad_lib_manager/main_window.py
    - kicad_lib_manager/widgets/help_dialog.py
    - tests/test_collection.py
    - tests/test_startup.py

key-decisions:
  - "APP_DIR and the app_dir parameters of check_new_collection and create_collection stay: they refuse a new collection inside the app's own folder (guard gate: 2 occurrences of app_dir: Path = APP_DIR)"
  - "main_window default changed in the GREEN commit, not the Task 2 commit, because deleting Source.LEGACY makes the old default raise AttributeError at import"

requirements-completed: [SPLIT-08]

coverage:
  - id: D1
    description: "No start resolves to the folder the app's code lives in; with nothing else usable the first-run window opens (exit 0 with 'No library folder chosen; exiting.' when no window is chosen)"
    requirement: SPLIT-08
    verification:
      - kind: unit
        ref: "tests/test_startup.py#test_code_folder_collection_is_never_used"
        status: pass
      - kind: unit
        ref: "tests/test_startup.py#test_full_order"
        status: pass
    human_judgment: false
  - id: D2
    description: "Source has CLI, ENV, CHOSEN, KICAD only; resolve order and skipped-folder notes name only KiCad's folder"
    requirement: SPLIT-08
    verification:
      - kind: unit
        ref: "tests/test_collection.py#test_source_has_four_members"
        status: pass
      - kind: unit
        ref: "tests/test_collection.py#test_resolve_order"
        status: pass
      - kind: unit
        ref: "tests/test_collection.py#test_chosen_skipped_notes"
        status: pass
    human_judgment: false
  - id: D3
    description: "MainWindow(library_root) without a source shows 'your choice'; the User Guide's start list has no code-folder item"
    requirement: SPLIT-08
    verification:
      - kind: unit
        ref: "python -m pytest tests/test_main_window.py tests/test_main_window_chooser.py tests/test_main_window_import.py tests/test_main_window_migration.py tests/test_checkout_warning.py tests/test_main_window_root.py tests/test_help_dialog.py tests/test_annotations_resolve.py (354 passed)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 02: Remove the code-folder fallback Summary

**The app no longer treats the folder its own code lives in as a library folder: `Source.LEGACY` and the `app_dir` candidate are deleted, so the start resolves through --library-root, KICAD_LIBMGR_ROOT, the chosen folder and KiCad's KICAD_LIB_GITHUB, then the first-run window.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-11-24T13:32:07Z
- **Completed:** 2026-11-24T13:44:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `Source` keeps CLI, ENV, CHOSEN, KICAD; `_chosen_note` always names "KiCad's folder (...)" as the next candidate.
- `build_candidates(*, cli, env, chosen=None, kicad=None)` and `start_window(argv, environ, *, chosen, kicad, first_run, check, timeout)` have no `app_dir`; the first-run hand-off now also happens from a checkout that is itself a collection.
- `MainWindow.__init__` default source is `Source.CHOSEN`; the User Guide start list has four sources and then the setup window.
- The new-collection refusal inside the app's own folder (`APP_DIR`, `check_new_collection`, `create_collection`) is untouched.

## TDD Gate Compliance

- **RED** (`2ca5f09`, `test(16-02)`): `test_code_folder_collection_is_never_used` failed on the planned assertion (`build_candidates` parameters still ended with `app_dir`); `test_source_has_four_members` failed (`['CLI','ENV','CHOSEN','KICAD','LEGACY']`). Run: `python -m pytest tests/test_startup.py tests/test_collection.py -n 0`, 2 failed, 156 passed. Semantic assessment: both targets executed and failed on the intended assertion, not on an import, syntax or fixture fault. The `gsd_run check tdd-red-evidence` classifier is not available in this worktree (no `.claude/gsd-core`), so no machine-validated record was written.
- **GREEN** (`a4eac58`, `feat(16-02)`): same command, 158 passed.
- **REFACTOR:** none needed.

## Task Commits

1. **Task 1 RED: failing tests** - `2ca5f09` (test)
2. **Task 1 GREEN: collection.py, startup.py (and the main_window default, see Deviations)** - `a4eac58` (feat)
3. **Task 2: User Guide list item removed** - `4d0fb63` (feat)

**Plan metadata:** committed with this SUMMARY (docs).

## Deleted and Rewritten Tests

- Deleted: `tests/test_startup.py::test_legacy_only_when_app_folder_is_a_collection`; `tests/test_collection.py::test_legacy_failure_is_silent`.
- Added: `test_code_folder_collection_is_never_used` (test_startup.py), `test_source_has_four_members` (test_collection.py).
- Rewritten: `test_full_order` (CLI > ENV > CHOSEN > KICAD, then first-run hand-off when a missing remembered folder and a non-collection KiCad folder both fail); `test_resolve_order`, `test_chosen_skipped_notes` (unusable CHOSEN now falls to KiCad's folder), `test_kicad_skipped_note` (no code-folder winner: root None), `test_notes_keep_their_order` (chosen and kicad both failing, ends "Choose a library folder to continue.") in test_collection.py.
- Edited: the `seams` fixture and `start` helper lost `app_dir`; three `build_candidates(..., app_dir=...)` calls lost the keyword; the module docstring no longer mentions an app folder.
- `tests/test_help_dialog.py` needed no change (it did not assert the removed item).

## Files Created/Modified

- `kicad_lib_manager/collection.py` - `Source.LEGACY` deleted, `_chosen_note` and `resolve_library_root` simplified, `APP_DIR` comment reworded.
- `kicad_lib_manager/startup.py` - candidate and `app_dir` removed, unused `APP_DIR` and `is_collection` imports dropped.
- `kicad_lib_manager/main_window.py` - default `source` is `Source.CHOSEN`.
- `kicad_lib_manager/widgets/help_dialog.py` - code-folder list item removed.
- `tests/test_collection.py`, `tests/test_startup.py` - as listed above.

## Decisions Made

- `APP_DIR` and the `app_dir` parameters of `check_new_collection` / `create_collection` stay (guard gate: `grep -c "app_dir: Path = APP_DIR" kicad_lib_manager/collection.py` prints 2).
- The pre-split CLAUDE.md bullet naming the code-folder source is left for plan 16-07, as the plan states.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MainWindow default moved into the GREEN commit**
- **Found during:** Task 1 (GREEN)
- **Issue:** `MainWindow.__init__` has `source: Source = Source.LEGACY` as a default evaluated at definition time; deleting the member makes `main_window` (and so `startup`, which the Task 1 tests import) fail with `AttributeError`. The plan assigns that line to Task 2.
- **Fix:** the one-line default change was committed with Task 1's GREEN commit; Task 2 then only carried the help_dialog edit plus its verification run.
- **Files modified:** kicad_lib_manager/main_window.py
- **Verification:** Task 1 and Task 2 automated commands both pass.
- **Committed in:** `a4eac58`

**2. [Test shape] `test_code_folder_collection_is_never_used` asserts parameter lists, not a literal name**
- The plan's acceptance criterion requires `grep -cE "LEGACY|app_dir" tests/test_startup.py` to print 0, so the test pins the removal by comparing `inspect.signature(...).parameters` to the exact expected names, plus `build_candidates(cli=None, env=None) == []` and the first-run hand-off.

---

**Total deviations:** 1 auto-fixed (1 blocking), 1 test-shape note
**Impact on plan:** None on scope; only the commit in which one line landed.

## Issues Encountered

None. Targeted runs only (the orchestrator runs the quick suite after the wave): 158 passed (test_startup + test_collection) and 354 passed (Task 2 command). The submodules `Custom/` and `WurthElektronik/KiCad-Library` are empty in this worktree; none of the targeted tests needed them.

## Known Stubs

None.

## Threat Flags

None. T-16-03 is mitigated: the code-folder candidate is deleted, pinned by `test_code_folder_collection_is_never_used` and `test_source_has_four_members`, and the new-collection refusal inside the app folder is kept.

## Next Phase Readiness

Ready for 16-07 to rewrite the CLAUDE.md bullet that still names the code-folder source (and the `the folder this app runs from` tag in its tag list).

---
*Phase: 16-repo-split*
*Completed: 2026-11-24*

## Self-Check: PASSED

- Modified files exist; commits `2ca5f09`, `a4eac58`, `4d0fb63` are ancestors of HEAD.
- Acceptance greps all at their expected values (0, 0, 0, 0, 0, 1, 1, 2 for Task 1; 1, 0, 0, 0 for Task 2).
