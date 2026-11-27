---
phase: 17-library-catalog
plan: 02
subsystem: ui
tags: [pyside6, qtimer, qthread, migration-dialog, close-rule]

requires:
  - phase: 13-atomic-migration
    provides: MigrationDialog with the draft and rebuild timers and the close-waits path (D-14)
provides:
  - MigrationDialog stops its draft and rebuild timers on every real close
  - a pending draft save still runs once as a worker on close, so the last edit is kept
  - no worker starts after the window closed (starts guarded by _closing)
  - the close rule the catalog window copies in plans 17-11, 17-13 and 17-15 (D-16)
affects: [17-11, 17-13, 17-15]

actuals:
  tokens: 1100
  tasks: 2
  commits: 3
plan_head_before: 42ddcc94c3fa42b9288af14dd063c2004b2a6b02
plan_head_after: 6f2749d2a5befde25cb5161c4afdefe51dc48181

tech-stack:
  added: []
  patterns:
    - "Close rule: stop every QTimer in done() and again in the delayed close; a pending save runs once before _closing is set; worker starts return at once while _closing"

key-files:
  created: []
  modified:
    - kicad_lib_manager/widgets/migration_dialog.py
    - tests/test_migration_dialog.py
    - .planning/todos/done/2026-11-23-migration-dialog-stop-timers-on-close.md

key-decisions:
  - "The timer stops are written inline in done() and _reap (not in a helper) so each close path shows the rule where it is applied"
  - "The final draft save is started before _closing is set; the _closing guard in _start_save_draft therefore lets it by while every later timer start is refused"

requirements-completed: []

coverage:
  - id: D1
    description: "Closing the migration window stops _draft_timer and _rebuild_timer and starts no rebuild afterwards"
    verification:
      - kind: unit
        ref: "tests/test_migration_dialog.py#test_close_with_pending_timers_starts_no_rebuild"
        status: pass
    human_judgment: false
  - id: D2
    description: "A pending draft save when the window closes runs once as a worker, the last edit is kept, and the window closes when it ends"
    verification:
      - kind: unit
        ref: "tests/test_migration_dialog.py#test_close_with_pending_timers_starts_no_rebuild"
        status: pass
    human_judgment: false
  - id: D3
    description: "With nothing pending the window closes at once and starts no worker"
    verification:
      - kind: unit
        ref: "tests/test_migration_dialog.py#test_close_without_pending_draft_closes_at_once"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 02: Migration window timers stop on close Summary

**MigrationDialog stops its draft and rebuild QTimers in done() and in the delayed _reap close, runs a pending draft save once as a worker so the last edit survives, and refuses every worker start while closing.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-27T08:42:00Z (approximate)
- **Completed:** 2026-11-27T08:49:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `done()` (after the existing refusals for a running migration, a running commit and an already-closing window) remembers whether the draft timer was active, stops `_draft_timer` and `_rebuild_timer`, and starts one `_start_save_draft()` when a save was pending; the existing "any worker running" branch then defers the close.
- `_reap` stops both timers again right before `QDialog.done`, so a timer restarted by a result handler during the wait cannot survive the close.
- `_start_rebuild` and `_start_save_draft` return at once while `_closing` is set; the one final save from `done()` runs before `_closing` is set, so it is not blocked.
- The folded todo of 2026-11-23 is moved to `.planning/todos/done/` with "Fixed by plan 17-02".

## Task Commits

1. **Task 1 RED: failing test for closing with pending timers** - `dddd58c` (test)
2. **Task 1 GREEN: stop timers on close, keep the pending draft save** - `64e0fa5` (feat)
3. **Task 2: todo filed as done** - `6f2749d` (chore)

No REFACTOR commit (nothing to clean up).

**Plan metadata:** committed after this SUMMARY (docs: complete plan).

## TDD Gate Compliance

- RED (`dddd58c`): `test_close_with_pending_timers_starts_no_rebuild` failed on `assert not dialog._draft_timer.isActive()` after `reject()` (the old `done()` closed at once and left both timers running). Semantic assessment: the target test executed, failed on the planned assertion (timers inactive on close) for the intended reason, no import, fixture or syntax fault. The second test, `test_close_without_pending_draft_closes_at_once`, passed at RED by design: it is a regression guard for the no-pending path, which already closed at once. The pytest report format is not one of the `gsd_run check tdd-red-evidence` adapters, so the machine classifier was not run; the failure output was inspected by hand.
- GREEN (`64e0fa5`): both new tests and the 20 earlier tests of the module pass.

## Files Created/Modified

- `kicad_lib_manager/widgets/migration_dialog.py` - timers stopped in `done()` and `_reap`; `_start_rebuild` / `_start_save_draft` guarded by `_closing`.
- `tests/test_migration_dialog.py` - `test_close_with_pending_timers_starts_no_rebuild` (counts rebuilds through a wrapped `build_plan`, saves through a fake `save_draft`, waits past both delays) and `test_close_without_pending_draft_closes_at_once` (counts `_spawn` calls).
- `.planning/todos/done/2026-11-23-migration-dialog-stop-timers-on-close.md` - moved from pending, "Fixed by plan 17-02" added.

## Decisions Made

- Inline timer stops in both close paths instead of a helper, so the rule is visible where each path closes (and the plan's grep acceptance counts hold).
- The final-save-before-`_closing` ordering carries a short comment in `done()` and `_start_save_draft`.

## Deviations from Plan

None - plan executed exactly as written. (A first version used a `_stop_timers` helper; it was inlined before the GREEN commit so the acceptance greps, at least 2 occurrences of each `.stop()`, hold.)

## Issues Encountered

None. No existing test relied on a timer firing after the close, so no existing test was adjusted.

## Verification

- `env/Scripts/python.exe -m pytest tests/test_migration_dialog.py tests/test_migration_dialog_files.py tests/test_migration_dialog_run.py tests/test_migration_draft.py tests/test_main_window_migration.py -n 0 -q -p no:cacheprovider` (also with `--full`): 81 passed.
- Acceptance greps: `_draft_timer.stop()` 2, `_rebuild_timer.stop()` 2 in the dialog; the new test name present once in `tests/test_migration_dialog.py`; the todo is in `done/` and absent from `pending/`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The D-16 close rule is fixed for plans 17-11, 17-13 and 17-15: stop every QTimer of a window in `done()`, run a pending save once before setting `_closing`, and make every timer or worker start return at once while closing.

## Self-Check: PASSED

- FOUND: kicad_lib_manager/widgets/migration_dialog.py (changes), tests/test_migration_dialog.py (new tests), `.planning/todos/done/2026-11-23-migration-dialog-stop-timers-on-close.md`
- FOUND commits: dddd58c, 64e0fa5, 6f2749d (ancestors of HEAD)

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
