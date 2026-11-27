---
phase: 17-library-catalog
plan: 14
subsystem: main-window
tags: [catalog, main-window, selection, scan-source, remove-source, path-variables, wurth-carry-over, pyside6, tdd]

requires:
  - phase: 17-library-catalog
    provides: _on_catalog_job_finished, _catalog_vars, the busy rules and the catalog window wiring (17-12); CatalogOutcome, set_finishing, set_scan, set_kicad_fp_dir, path_vars_requested, generate_requested (17-13); scan_source, remove_source and model_vars in the scanner (17-05); catalog manifest, path_vars and curated legacy_prefix (17-04)
provides:
  - catalog/selection.py with SelectionChange and preselect_source (Qt-free tick rule with the legacy-twin carry-over)
  - the main window's follow-up of every finished catalog job (source rescan on a worker, selection, carry-over line, path-variable question, finishing state)
  - the catalog window always holds the main window's last scan and KiCad's footprint folder
  - tests/test_catalog_selection.py (8 tests) and tests/test_main_window_catalog_jobs.py (19 tests)
affects: [17-15, 17-16, 17-17, 17-19]

plan_head_before: 20278caa5a0e91a722ba17e9610a16aa98d16964
plan_head_after: d47147bed74cd316edf2f874cac11f91f611a57d

actuals:
  tokens: 13500
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "CatalogRescanWorker(QThread) beside LibraryRescanWorker: fingerprint first, then scan_source or remove_source, then scan_cache.save; one Issue answer means 'run the full scan'"
    - "One _CatalogFollowup record at a time; the full-scan fallback applies the same selection in _on_scan_finished through followup.scan_started"
    - "The finishing state is set when the job ends and lifted by _end_catalog_finishing, either at once or when the path-variable question returns (_catalog_finish_after_vars)"

key-files:
  created:
    - kicad_lib_manager/catalog/selection.py
    - tests/test_catalog_selection.py
    - tests/test_main_window_catalog_jobs.py
  modified:
    - kicad_lib_manager/main_window.py

key-decisions:
  - "The one-source rescan runs on a new CatalogRescanWorker(QThread) next to LibraryRescanWorker, not on TaskWorker: tests/test_exit_with_hung_check.py allows exactly two TaskWorker calls in main_window.py (the KiCad-open checks)"
  - "Update ticks only libraries that were not in the previous scan (the new rel_paths are computed from the previous scan, so the outcome needs no extra field); Add and Reinstall tick the whole source"
  - "_select_linked_footprints is not called after a catalog job: preselect_source already ticks both kinds of a source, and the linked-footprint rule would tick a footprint library the clash rule left unticked and could re-tick one the owner unticked in another source"
  - "The path-variable question is asked only when the finished library needs a variable (outcome.vars not empty) and would_change_path_vars is True; a No logs the existing 'KiCad still points at ... will offer the change again' line through _offer_from_switch"
  - "A failed source read logs 'Library catalog step failed: {text}' and falls back to the full scan, so the scan never stays stale"
  - "The name-clash line of an Add is written once by ops (through the catalog window); the main window writes its own clash line only for an Update, which ops does not report"

patterns-established:
  - "A catalog follow-up never renames: a clashing library starts unticked and the clash rules (_trim_collided_selection) still run after the preselection"
  - "Name lists in main-window log lines go through _capped_names (5 names, then 'and {n} more')"

requirements-completed: [CAT-05, CAT-06, CAT-08, CAT-12, CAT-04]

coverage:
  - id: D1
    description: "After Add or Reinstall only that source is rescanned on a worker (no Loading Libraries window, saved scan rewritten); its libraries appear ticked except name clashes, nothing renamed"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_add_rescans_the_source_and_ticks"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_selection.py#test_add_ticks_the_source_except_clashes"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_selection.py#test_never_renames"
        status: pass
    human_judgment: false
  - id: D2
    description: "When scan_source answers rescan.full_needed, or the worker fails, the full scan runs and applies the same selection rules"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_full_scan_when_source_rescan_is_not_possible"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_finishing_ends_after_a_failed_source_read"
        status: pass
    human_judgment: false
  - id: D3
    description: "Wurth carry-over: ticked legacy twins hand their tick to ThirdParty/<id>, one 'Moved {n} selected libraries ...' line, nothing extra when no twin was ticked, the legacy prefix falls back to the curated entry"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_wurth_selection_carries_over"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_wurth_carry_over_with_nothing_ticked_writes_no_line"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_selection.py#test_legacy_twins_move_their_tick"
        status: pass
    human_judgment: false
  - id: D4
    description: "Update keeps ticks, ticks only new libraries (clashes unticked, one capped clash line) and drops vanished selections; Remove takes the source out of the scan and the next Generate Tables drops its managed entries"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_update_keeps_ticks_and_ticks_new"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_remove_drops_the_source"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_name_lists_are_capped"
        status: pass
    human_judgment: false
  - id: D5
    description: "Path variables: the existing question opens after Add or Reinstall only when the library needs variables KiCad does not hold, with the catalog variables as extra_vars; No writes nothing and logs the existing line; the Set Path Variables button runs the same question"
    requirement: "CAT-06"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_path_variable_question_after_add"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_no_question_when_nothing_would_change_or_no_variable_is_needed"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_set_path_variables_button_runs_the_question"
        status: pass
    human_judgment: false
  - id: D6
    description: "The catalog window shows 'Finishing the last change...' on every action while the rescan and the question run, a folder switch is refused meanwhile; Generate Tables stays the owner's press; the window always has the last scan and KiCad's footprint folder"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_finishing_state_spans_rescan_and_question"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_generate_button_runs_generate"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_catalog_window_has_scan_and_footprint_folder"
        status: pass
    human_judgment: false
  - id: D7
    description: "C14 log rules: nothing is logged while the rescan runs, a failed job only recounts (the catalog window wrote its error and raw lines), name lists are capped"
    requirement: "CAT-08"
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_no_log_line_while_job_runs"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_failed_job_logs_one_error_and_raw_text"
        status: pass
    human_judgment: false
  - id: D8
    description: "The real Wurth conversion (89 selections, about 12 GB source, real KiCad settings file) behaves as the synthetic tests do"
    verification: []
    human_judgment: true
    rationale: "Needs the owner's collection, a real download and KiCad's own settings; the rehearsal is the phase's owner-run step (D-25), not an automated test"

duration: 12min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 14: Main Window Follow-up of Catalog Jobs Summary

**After every finished catalog job the main window rescans only that source on a worker, ticks its libraries (clashes unticked, never renamed, the Wurth ticks carried over to the new folder), offers the library's path variables through the existing No-by-default question, and keeps the catalog window in its "finishing" state until all of that has ended.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-11-27T11:47:33Z
- **Completed:** 2026-11-27T11:59:14Z (code), SUMMARY and state follow
- **Tasks:** 2 (each a RED test commit then a GREEN feat commit)
- **Files:** 3 created, 1 modified (`main_window.py`, CRLF kept)

## Accomplishments

- `catalog/selection.py`: `preselect_source(result, folder, legacy_prefix=, only=)` is the one tested tick rule; the layering guard already listed it as `{models, collection}`.
- The after-job sequence in `main_window.py`, below.
- 27 new quick tests, none starting git or touching KiCad's real settings.

## The after-job sequence as coded

`_on_catalog_job_finished(outcome)` always recounts the menu text and refreshes the busy controls. A failed outcome (`ok` False) stops there. For `kind` in add, reinstall, update, remove with `ok` True:

1. `set_finishing(True)` on the catalog window (every action waits, a folder switch is refused).
2. A `CatalogRescanWorker` takes `scan_cache.fingerprint` first, then runs `scan_source(root, previous, "ThirdParty/<id>", kicad_fp_dir, model_vars=...)` (add, reinstall, update) or `remove_source(previous, folder, kicad_fp_dir)` (remove), and writes the merged result with `scan_cache.save`. No Loading Libraries window opens.
3. On an Issue answer (`rescan.full_needed`) the issue is logged and `_start_scan(show_progress=True, reuse_cache=False)` runs; `_on_scan_finished` applies the same selection through `_CatalogFollowup.scan_started`. A worker exception logs `Library catalog step failed: {text}` and takes the same fallback.
4. On success: `_copy_selection(previous, merged)` keeps the owner's ticks, then
   - add and reinstall: `preselect_source(merged, folder, legacy_prefix=)` for the whole source, the prefix taken from the outcome and else from `curated_by_id`;
   - update: `preselect_source(..., only=<rel_paths not in the previous scan>)`, one clash line when some are left unticked, and the existing `Dropped {n} selections for libraries no longer found: ...` line for vanished ones;
   - remove: nothing is ticked, the source simply leaves the scan.
   Then `_trim_collided_selection`, the scan replaces `_scan_result`, the catalog window gets `set_scan`, the tree is repopulated, and one line `Rescanned {name}: no warnings` (or `{n} warning(s)`) follows the new issue lines. Remove writes no line (the catalog window already did).
5. Add and reinstall only: when `outcome.vars` is not empty and `would_change_path_vars(..., extra_vars=_catalog_vars())` is True, `_sync_path_vars()` runs the existing question (No default, KiCad-open variant, `extra_vars` filtered by the existing code). A No logs the existing `KiCad still points at ... Generate Tables and Install Part will offer the change again.` line.
6. `set_finishing(False)` when no question is needed, or when `_on_path_var_check` returns.

The Würth carry-over line, with `n` the number of moved libraries (`library` when 1):

`Moved {n} selected libraries from WurthElektronik/KiCad-Library to ThirdParty/WurthElektronik. Generate Tables rewrites their entries.`

It is written once, and only when `n > 0`. The update clash line is `{n} libraries of {name} have the same name as libraries you already have and start unticked: {names}.` (5 names, then `and {m} more`), the same text ops writes for an Add.

Other connections: `path_vars_requested` runs `_sync_path_vars` and `generate_requested` runs `_on_generate` (both wired in 17-12, kept as one connection each); `set_kicad_fp_dir` is called when the window is built and after Set KiCad Path.

## Task Commits

1. **Task 1: preselection and the Würth carry-over** - RED `56c7d0a` (test), GREEN `c2334ed` (feat)
2. **Task 2: the main window's follow-up** - RED `1406885` (test), GREEN `d47147b` (feat)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `kicad_lib_manager/catalog/selection.py` - `SelectionChange`, `preselect_source`
- `kicad_lib_manager/main_window.py` - `CatalogRescanWorker`, `_CatalogFollowup`, the follow-up methods, `_capped_names`, KiCad folder hand-over, finishing end in `_on_path_var_check`, worker wait in `closeEvent`
- `tests/test_catalog_selection.py` - 8 tests
- `tests/test_main_window_catalog_jobs.py` - 19 tests

## Decisions Made

See `key-decisions` above.

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `56c7d0a` test(17-14) | `c2334ed` feat(17-14) |
| 2 | `1406885` test(17-14) | `d47147b` feat(17-14) |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-13); the runs were read by hand. Task 1: collection stopped with `ModuleNotFoundError: kicad_lib_manager.catalog.selection`, the planned missing module. Task 2: the fixture was written with `raising=False` and imports the real scanner functions, so it builds; 14 of 19 tests failed on assertions for the planned behaviour (a source call list that stayed empty, ticks left on the legacy twins, no question, no finishing state, `_kicad_fp_dir` still `None` on the window), the other 5 (failed job, clash line once, no-question cases, button wiring that 17-12 already made) passed. After GREEN the first run had 2 failures, both test mistakes (a `_progress` that still holds the startup scan's finished dialog, and a path-variable test that wrote no `catalog.json`); a separate guard test then found the TaskWorker rule (deviation 1). No refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The source rescan runs on its own QThread subclass, not TaskWorker**
- **Found during:** Task 2 verification (`tests/test_exit_with_hung_check.py::test_folder_checks_never_use_a_qthread` counted 3 `TaskWorker` calls in main_window.py, the guard allows exactly the 2 KiCad-open checks)
- **Issue:** the plan says TaskWorker; the guard keeps TaskWorker out of everything else in this file
- **Fix:** `CatalogRescanWorker(QThread)` beside `LibraryRescanWorker`, with `result` and `failed` signals, kept in `_catalog_workers`, reaped on its `finished` signal and waited for in `closeEvent`
- **Files modified:** kicad_lib_manager/main_window.py
- **Verification:** the guard test and the 19 job tests pass
- **Committed in:** d47147b

**2. [Plan note] `_select_linked_footprints` is not called**
- The plan's action lists it after the selection; `preselect_source` already ticks the footprint libraries of a source, and the linked-footprint rule is unscoped and additive (it would tick a clashing footprint library the preselection deliberately left unticked, and a footprint library of another source the owner had unticked). Not calling it keeps D-20 and leaves the owner's other ticks alone.

**3. [Plan note] Update takes its "new libraries" from the previous scan**
- `only` for an update is the set of rel_paths that were not in the previous scan, so `CatalogOutcome` needs no extra field and plan 17-15 only has to emit `kind="update"` (and `"remove"`) with `id` and `name`.

**4. [Plan note] "The clash info is logged once"**
- The Add's clash line is written by `ops.register_add` and forwarded by the catalog window; the main window adds none for add or reinstall (a test emits the line through the window's `log_line` and asserts it appears once after the outcome). The main window writes the same-format line only for an Update.

---

**Total deviations:** 1 blocking (worker class), 3 notes. **Impact:** no must_have weakened; the visible differences from the plan text are the worker class and the missing `_select_linked_footprints` call.

## Issues Encountered

- The first RED fixture failed on a missing `main_window.scan_source`; the fixture now imports the real scanner functions and patches the main window names with `raising=False`, so the RED failures are assertions.
- The saved scan after a one-source rescan carries a fingerprint of the whole folder taken before that read, as the plan says. If other library files changed outside the app since the last scan, the saved scan would look fresh at the next start; a Rescan always runs the full scan.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-17-38 (path variables written after an Add) is mitigated by reusing the existing confirmation unchanged (No default, KiCad-open variant, `extra_vars` filtered where they are applied) and asked only when `would_change_path_vars` is True; T-17-39 (duplicate nicknames ticked) by `preselect_source` leaving clashes unticked, `_trim_collided_selection` after it, and the selection tests.

## Next Phase Readiness

Plan 17-15 emits `CatalogOutcome(kind="update" or "remove", id, name, ok=True, ...)` and this window already follows both up. The CLAUDE.md menu shortcut list still lacks `Ctrl+Shift+L` (noted in 17-12; the documentation plan of the phase adds it).

## Self-Check: PASSED

- Files found: kicad_lib_manager/catalog/selection.py, kicad_lib_manager/main_window.py, tests/test_catalog_selection.py, tests/test_main_window_catalog_jobs.py.
- Commits `56c7d0a`, `c2334ed`, `1406885`, `d47147b` are on main (4 commits measured from the ledger base `20278ca`).
- Acceptance greps: `def preselect_source` 1, `scan_source(` / `preselect_source(` in main_window.py 2 (at least 1 each), `def test_wurth_selection_carries_over` 1.
- Plan verification: test_catalog_selection, test_catalog_layering, test_main_window_catalog_jobs, test_main_window_catalog, test_main_window, test_main_window_import, test_main_window_migration pass with `-n 0`; with test_main_window_chooser, test_main_window_root, test_checkout_warning, test_startup, test_catalog_dialog_add, test_exit_with_hung_check, test_corpus_audit, test_custom_literals, test_layering and test_annotations_resolve 629 tests pass; the pre-publish scan of the changed files and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
