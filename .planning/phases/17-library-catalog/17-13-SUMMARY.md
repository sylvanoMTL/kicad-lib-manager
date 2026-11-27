---
phase: 17-library-catalog
plan: 13
subsystem: widgets
tags: [catalog, add, add-by-url, reinstall, licence-page, preview, job-strip, cancel, close-question, pyside6, tdd]

requires:
  - phase: 17-library-catalog
    provides: CatalogDialog, CatalogServices and the browse slice (17-11); the main window's busy rules that call is_job_running, holds_download and is_finishing (17-12); plan_add, plan_reinstall, check_repository, stage_add, register_add, discard_staging (17-07); licence classes and labels (17-04); StagingReport and Collision (17-06)
provides:
  - widgets/catalog_pages.py with ReviewPage, CollapsibleList, AddByUrlPage, LicencePage, AddPreviewPage, LinkLabel, destructive_button_qss and the shared copy
  - the Add, Add by URL and Reinstall flows inside CatalogDialog (one job at a time on a TaskWorker, job strip, cancel, close question, discard on close)
  - CatalogOutcome and set_kicad_fp_dir for plan 17-14; ReviewPage, CollapsibleList and destructive_button_qss for plan 17-15
  - tests/test_catalog_pages.py (32 tests) and tests/test_catalog_dialog_add.py (36 tests)
affects: [17-14, 17-15, 17-17, 17-19]

plan_head_before: 9ac826f85ae76e1d4816a1cb83ef27b11567a6a0
plan_head_after: d82700c08f6dc6e2642c27b81fd3f0fd1ebd1c06

actuals:
  tokens: 36500
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Pages are pure widgets (no service call); the window owns one job at a time (phase plan, check, stage, register or discard) on a TaskWorker spawned with _spawn/_reap, a threading.Event per job as the cancel, and on_done(job, value) callbacks on the GUI thread"
    - "A job that is stopped after its download finished deletes the copy inside the worker and returns a sentinel, so a stopped download is never shown"
    - "A review page owns its tick and its own primary rule (_own_primary_rule); the window only sets blocked (outside reason) and busy (own job running)"
    - "_refresh_details is a no-op while a review page is open, so a late scan or size result never pulls the page away"

key-files:
  created:
    - kicad_lib_manager/widgets/catalog_pages.py
    - tests/test_catalog_pages.py
    - tests/test_catalog_dialog_add.py
  modified:
    - kicad_lib_manager/widgets/catalog_dialog.py
    - .planning/WINDOWS.md

key-decisions:
  - "The planning step (free space, running KiCad) and the repository check run off the GUI thread as jobs; the plan job shows no strip, the check job shows Checking the repository... with Cancel Check"
  - "The percentage 100 from git switches the strip to Checking {name}... (the download is complete and its files are being checked); an unknown percentage is indeterminate"
  - "The final Add (record write) cannot be stopped: Cancel Adding is disabled with a tooltip and a close is ignored with the strip reading 'Adding cannot be stopped halfway. Close this window after it ends.' (the same rule the UI-SPEC gives Remove), so Stop and Close never promises 'Nothing is added' for a step that finishes"
  - "Closing with a download waiting deletes it on the GUI thread before the window hides: a worker could outlive the window and the main window may close right after"
  - "job_finished carries CatalogOutcome for the end of an add or reinstall flow only: success (ok True), a stop, a refusal, a failure and a discard (ok False); the plan and the repository check emit nothing"
  - "The licence page's Repository link is Mono (an address is machine text) so the cleaned address of an Add by URL is an elided Mono label with the full address as tooltip"

patterns-established:
  - "CatalogOutcome(kind, id, name, ok, symbol_count, footprint_count, collisions, vars, legacy_prefix, root_is_repo); kind is add or reinstall"
  - "A page change always goes through _enter_page (locks the list and search, takes Close's default away, focuses the page) and _leave_pages (unlocks, refreshes the Details, focuses the list)"

requirements-completed: [CAT-02, CAT-03, CAT-08, CAT-09]

coverage:
  - id: D1
    description: "Review pages: Add by URL, licence page for every licence class (notes, tick, refusals, reinstall variant, KiCad-open line), Add preview sections (added items, .gitignore row, path variables, name clashes, licence), refusal mode, collapsible list, one accent button per page, plain text"
    requirement: "CAT-08"
    verification:
      - kind: unit
        ref: "tests/test_catalog_pages.py (32 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A curated library is added with three presses (Add This Library, Download and Check, Add Library); nothing reaches the collection before the last; progress, result strip, log lines and the CatalogOutcome payload"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_curated_add_three_presses"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_proprietary_tick_gates_download"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_unknown_licence_tick_on_preview"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_clashes_are_reported_in_the_result_and_the_log"
        status: pass
    human_judgment: false
  - id: D3
    description: "Add by URL: the address page, Check Repository disabled when empty, refusals under the field, the cleaned address on the licence page, zero libraries ends on the refusal page, cancel of the check"
    requirement: "CAT-03"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_add_by_url_flow"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_zero_libraries_ends_on_the_refusal_page"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_cancel_check_returns_to_the_address_page"
        status: pass
    human_judgment: false
  - id: D4
    description: "Cancel Adding (Stopping..., process tree ended through the cancel event, copy deleted, log line, back to the list), refusals after the download with Try Again for a failed download only, a failed record write keeps the preview, Discard Download"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_cancel_adding"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_refusal_after_download_and_try_again"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_register_failure_keeps_the_preview_and_the_download"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_discard_download"
        status: pass
    human_judgment: false
  - id: D5
    description: "Reinstall: the licence page without a second tick, the recorded repository and branch, the folder-only preview, Reinstall Library, the Reinstalled result"
    requirement: "CAT-09"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_reinstall_flow"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_reinstall_cancel_text"
        status: pass
    human_judgment: false
  - id: D6
    description: "Close rules: Stop the current job? with Keep Working as default and Esc button, Stop and Close ends the job and closes, a waiting download is discarded silently, the record write ignores a close, no worker acts after done()"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_close_question_keep_working_and_stop"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_close_with_waiting_download_discards"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_close_during_the_record_write_is_ignored"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_no_worker_after_done"
        status: pass
    human_judgment: false
  - id: D7
    description: "Busy rules, list lock, Esc as the back button, Ctrl+Return as the primary, Close never default on a review page, exactly one accent button visible"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_one_job_at_a_time_and_blocked_reasons"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_list_locked_while_a_page_is_open"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_esc_backs_out_and_ctrl_return_presses_primary"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_one_accent_button_at_a_time"
        status: pass
    human_judgment: false
  - id: D8
    description: "Long text backstops: a 300-character address scrolls in the field and elides on the next page without widening the window; a 60-character name elides in the step label while the 240 px bar and the cancel button keep their size"
    requirement: "CAT-03"
    verification:
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_add.py#test_web_address_long_text"
        status: pass
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_add.py#test_step_label_elides"
        status: pass
    human_judgment: true
    rationale: "The offscreen platform has no real fonts and 96 DPI only; the look at the owner's display scale is for the verify-work UAT (UI-SPEC planner assumption)"

duration: 22min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 13: Add, Add by URL and Reinstall Summary

**A user can add a curated library, add a GitHub address or reinstall a missing library from the catalog window in three presses (licence page, Download and Check, Add Library), with a job strip showing the download percentage, Cancel Adding that ends the git process tree and deletes the copy, a Stop the current job? question on close, and nothing written to the collection before the last press.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-11-27T11:16:30Z
- **Completed:** 2026-11-27T11:38:00Z (code), SUMMARY and state follow
- **Tasks:** 2 (each a RED test commit then a GREEN feat commit)
- **Files:** 3 created (`widgets/catalog_pages.py` about 640 lines, two test modules), `widgets/catalog_dialog.py` about 700 lines added

## Accomplishments

- The review pages and their copy (UI-SPEC "Add flow", "Add by URL", "Refusals"), standalone and tested without a window.
- The three flows inside the window, a single job at a time, the job strip with the exact step and cancel labels, and the close rules (question, ignore during the record write, silent discard of a waiting download).
- `CatalogOutcome` and `set_kicad_fp_dir` for plan 17-14, `ReviewPage`, `CollapsibleList` and `destructive_button_qss` for plan 17-15; `is_job_running()` and `holds_download()` are real now, so the main window's busy rules (plan 17-12) work against the real window.

## Public API (read by plans 17-14 and 17-15)

```python
# kicad_lib_manager/widgets/catalog_dialog.py
@dataclass(frozen=True)
class CatalogOutcome:   # emitted with CatalogDialog.job_finished
    kind: str            # "add" or "reinstall" (a curated Add, an Add by URL and a Reinstall)
    id: str; name: str   # the ThirdParty folder name and the name the window shows (owner/repo for an address)
    ok: bool             # False for a stop, a refusal, a failure and a discarded download (the window logged it)
    symbol_count: int = 0; footprint_count: int = 0
    collisions: tuple = ()          # validate.Collision rows, those libraries start unticked
    vars: dict = {}                 # path variable -> folder inside the clone ('' = the clone itself)
    legacy_prefix: str | None = None
    root_is_repo: bool = False
CatalogDialog.set_kicad_fp_dir(path | None)     # stock library names for the clash check, read inside the job
CatalogServices: + stock_fp, stock_sym         # library_scanner.get_kicad_default_fp_nicknames / _sym_nicknames
job_label(flow, name) -> str                    # "the repository check", "adding X", "reinstalling X"
```

Job kinds (phase, flow): `plan` (add or reinstall; no strip), `check` (flow `check`, `Checking the repository...`, `Cancel Check`), `stage` (`Downloading {name}... {n}%` or `Downloading {name} again... {n}%`, then `Checking {name}...`, `Cancel Adding` or `Cancel Reinstalling`), `register` (`Adding {name}...`, cancel disabled) and `discard` (no strip). `job_finished` is emitted once at the end of an add or reinstall flow: after the record write (ok True), and for a stop, a refusal, a failure or a discard (ok False). The plan and the repository check emit nothing.

Hooks for plan 17-15: the Details `_button_row` holds `_add_btn` and `_reinstall_btn`; `_details_primaries` logic is in `_details_primary()` (Ctrl+Return); `_start_job(phase, flow, name, fn, on_done)` is the runner (`fn(progress, cancel)`, `on_done(job, value)`); `_enter_page(kind)` / `_leave_pages()` own the page change; `_show_job` and `_job_label` map a job to its strip text (extend the phase and flow cases for update and remove); `_refresh_actions` also sets `set_blocked` and `set_busy` on every review page (add the new pages to its tuple).

```python
# kicad_lib_manager/widgets/catalog_pages.py (no service call, no worker)
ReviewPage(QWidget)        # signals primary_pressed, back_pressed; set_heading, set_primary, set_back(text, tooltip),
                           # set_primary_shown, set_primary_enabled, set_blocked(reason), set_busy(bool),
                           # refresh_buttons, focus_first, back_button(), primary_button(); hook _own_primary_rule()
CollapsibleList(title, columns=(), *, collapse=True)   # set_rows(rows, token=None), row_count, is_expanded, toggle, tree
AddByUrlPage       # address(), field(), reset(), show_refusals(issues), refusal_texts(), set_checking(on)
LicencePage        # show_plan(plan, *, reinstall, acknowledged_on, name=None, address=None), acknowledged(), tick(), is_refused()
AddPreviewPage     # show_staged(staged, plan, *, root_is_repo, name=None, licence_confirmed=False),
                   # show_refusal(issue, *, can_retry, heading=""), show_notice(text), acknowledged(), what_rows(),
                   # clash_list(), licence_box(), is_refusal()
LinkLabel, destructive_button_qss(), plain_label, mono, muted, heading_font, status_line, clear_layout, licence_display
```

## Task Commits

1. **Task 1: the review pages** - RED `f38b6cc` (test), GREEN `5f96a40` (feat)
2. **Task 2: the flows in the window** - RED `2c7c3e1` (test), GREEN `d82700c` (feat)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md, ROADMAP.md, REQUIREMENTS.md and WINDOWS.md.

## Files Created/Modified

- `kicad_lib_manager/widgets/catalog_pages.py` - the pages, the list, the shared helpers and copy
- `kicad_lib_manager/widgets/catalog_dialog.py` - Details buttons, Add by URL button, page stack, job strip and runner, close rules, CatalogOutcome, `set_kicad_fp_dir`
- `tests/test_catalog_pages.py` - 32 standalone tests
- `tests/test_catalog_dialog_add.py` - 36 qtbot tests with fake services and gates
- `.planning/WINDOWS.md` - the two 17-11 stubs (Add by URL button, job state) marked fixed

## Decisions Made

See `key-decisions` above.

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `f38b6cc` test(17-13) | `5f96a40` feat(17-13) |
| 2 | `2c7c3e1` test(17-13) | `d82700c` feat(17-13) |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-12); the runs were read by hand. Task 1: collection stopped with `ImportError: cannot import name 'catalog_pages'`, the planned missing module (no test could run, so no assertion was reached). Task 2: all 35 tests failed at the fixture on `TypeError: CatalogServices.__init__() got an unexpected keyword argument 'stock_fp'`, the planned new service field, so none reached an assertion (a weak RED for the same reason as Task 1: the whole feature is missing). After GREEN the first full run had 4 failures, all in the new tests (a name that is `Würth Elektronik` in the list, a pixel width compared with a character count, a helper for the first focus), and one leak found by the run order (see deviation 2); no refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CatalogServices gained two fields**
- **Found during:** Task 2
- **Issue:** the stage job reads KiCad's stock library names (`library_scanner.get_kicad_default_fp_nicknames` and `..._sym_nicknames`) and a test must replace them
- **Fix:** `stock_fp` and `stock_sym` fields with the real functions as defaults
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py
- **Committed in:** d82700c

**2. [Rule 1 - Bug] A folder size read started after the window had dropped its background tasks**
- **Found during:** Task 2 (a Qt-loop exception `QTreeWidget already deleted` in the test after the add test)
- **Issue:** `_complete_close` refreshed the Details after `_stop_background`, which started a new size task that nothing cancelled
- **Fix:** the Details refresh runs before the background tasks are dropped
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py
- **Committed in:** d82700c

**3. [Plan note] Choices where the UI-SPEC is silent (each reversible)**
- The record write (`register`) cannot be stopped, so a close during it is ignored with the strip line `Adding cannot be stopped halfway. Close this window after it ends.`, the rule the UI-SPEC gives Remove, instead of the question the plan lists for Add; the question stays for the repository check and the download.
- A waiting download is deleted on the GUI thread when the window closes (a worker could outlive the window and the main window may close right after); the Discard Download button deletes it on a worker.
- Tooltip `Go back to the list first.` on Check for Updates and Add by URL... while a page is open (the UI-SPEC does not say what a disabled button says then); licence note for an unrecognised licence id (`OTHER`): `The repository's licence is not one the app can name. Its licence file, if it has one, is shown after the download, before the library is added.`; plain texts for a crashed check, download or record write (`... See the log for details.`).
- The Repository link on the licence page is Mono, so the backstop for a 300-character address (elided Mono label, full address as tooltip) holds for the cleaned address.
- `LinkLabel` and the four label helpers moved from `catalog_dialog.py` to `catalog_pages.py` (the dialog imports them under the old private names); `UNKNOWN_TEXT`, `NOT_STATED_TEXT`, `LICENCE_UNREADABLE_TEXT` and the glyphs are now defined once in the pages module.
- `job_finished` is emitted for the add and reinstall flows only (see the API section).

---

**Total deviations:** 1 blocking (service fields), 1 bug (found by the tests), 1 note. **Impact:** no must_have is weakened; the one visible difference from the plan text is the ignored close during the record write.

## Issues Encountered

- A shell heredoc with triple quotes failed on quoting and wrote nothing; the patch scripts were written with the file tool and run from the scratchpad.
- The offscreen platform draws no real fonts, so the long-text backstops check widths and elision, not looks.

## Known Stubs

None. The two stubs recorded by plan 17-11 (the Add by URL button without an action, `is_job_running` and `holds_download` answering False) are resolved and marked fixed in `.planning/WINDOWS.md`. The after-job follow-up (rescan of the source, selection, path-variable question) is the main window's work in plan 17-14 and is not a stub of this plan: `job_finished` already carries everything it needs.

## Threat Flags

None beyond the plan's threat model. T-17-35 (the tick is never pre-ticked, asked once, passed to `register_add`, which refuses an unticked restricted licence), T-17-36 (Esc only presses the back button, Ctrl+Return only an enabled primary, Close never default on a review page) and T-17-37 (a stopped job's result is dropped, the window waits for its worker in `_complete_close`, no callback acts after `done()`) are mitigated and tested.

## Next Phase Readiness

Plan 17-14 reads `CatalogOutcome` from `job_finished` and wires the rescan, the selection carry-over and the path-variable question, calling `set_scan`, `set_finishing` and `set_kicad_fp_dir`. Plan 17-15 adds `UpdatePreviewPage` and `RemovePage` on `ReviewPage`, extends `_show_job` with the update and remove cases and the Details buttons per status. Display scaling above 150 % and the look of the job strip at the owner's DPI are for the verify-work UAT.

## Self-Check: PASSED

- Files found: kicad_lib_manager/widgets/catalog_pages.py, kicad_lib_manager/widgets/catalog_dialog.py, tests/test_catalog_pages.py, tests/test_catalog_dialog_add.py.
- Commits `f38b6cc`, `5f96a40`, `2c7c3e1`, `d82700c` are on main (4 commits measured from the ledger base `9ac826f`).
- Acceptance greps: `class LicencePage` 1, `I have read the licence terms` 1, `Stop the current job?` 3, `class CatalogOutcome` 1, `def test_curated_add_three_presses` 1.
- Plan verification: test_catalog_dialog_add (36), test_catalog_pages (32) and test_catalog_dialog (55) pass with `-n 0`; test_catalog_dialog_geometry, test_main_window_catalog, test_main_window, test_main_window_root, test_catalog_layering, test_layering and test_annotations_resolve pass (233 and 190 tests); the pre-publish scan of the four files is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
