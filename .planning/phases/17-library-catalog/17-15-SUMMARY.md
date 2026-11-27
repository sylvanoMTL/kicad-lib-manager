---
phase: 17-library-catalog
plan: 15
subsystem: widgets
tags: [catalog, update, remove, details-buttons, set-path-variables, destructive-confirmation, job-strip, pyside6, tdd]

requires:
  - phase: 17-library-catalog
    provides: ReviewPage, CollapsibleList, destructive_button_qss, the job runner, the job strip, the close question and CatalogOutcome (17-13); plan_update, apply_update, plan_remove, apply_remove and status rows (17-10); the Details page and path_vars_requested (17-11); the main window's follow-up of kind update and remove (17-14)
provides:
  - UpdatePreviewPage and RemovePage in widgets/catalog_pages.py
  - the Update and Remove flows, the Details buttons per status and Set Path Variables... in widgets/catalog_dialog.py
  - tests/test_catalog_dialog_update.py (23 tests)
affects: [17-16, 17-17, 17-19]

plan_head_before: a33821c6b2246e5b6a6241c3320ade53240a3362
plan_head_after: ff21228d6176fe95b8dd33c4004511e2e603275c

actuals:
  tokens: 31000
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A page that confirms a deletion owns the guards itself: primary_accepts_ctrl_return() is False, focus_first() lands on Keep Library, and the dialog gives Keep Library the default flag only while the page is open"
    - "A change that removes the shown row (a Remove of a library that leaves the list) renders its result strip on the empty pane through the same _render_result renderer the Details page uses"
    - "Phases look, apply and remove join plan, check, stage, register and discard; _STOPPABLE names the four a Cancel button or the close question may stop"

key-files:
  created:
    - tests/test_catalog_dialog_update.py
  modified:
    - kicad_lib_manager/widgets/catalog_pages.py
    - kicad_lib_manager/widgets/catalog_dialog.py

key-decisions:
  - "Update ends in two jobs: look (plan_update, cancellable, strip 'Looking for changes in X...') and apply (apply_update, cancellable until its reset; a late cancel lets it finish and the update is reported as done)"
  - "A Keep Current Version, a Back to List and a Stop and Close never reach apply_update: it is called from exactly one place, the preview's Update Library"
  - "Remove Library is called from exactly one place, the confirmation page's primary button; Ctrl+Return is skipped for that page, the page focuses Keep Library, and Enter on the destructive button reaches Keep Library, the default"
  - "The Update preview is not a held download: the fetch goes into the clone's object store, so holds_download() stays False and closing asks nothing and logs nothing"
  - "A 'Libraries that leave your scan' list and 'Path variables it used' row are omitted when there are none (the UI-SPEC only names the omission for the variables)"

patterns-established:
  - "Details button matrix: Set Path Variables... and Remove This Library plain, then Update This Library (accent only while an update is available), then the Add or Reinstall accent button; every button waits for a job or an outside reason, Update also needs an update to apply"
  - "CatalogOutcome kinds are now add, reinstall, update and remove; a stop, a refusal and a failure emit ok False"

requirements-completed: [CAT-04, CAT-06, CAT-01]

coverage:
  - id: D1
    description: "Update preview, up to date, changed-files refusal (8 rows then and n more), other refusals; Remove confirmation in both first-line variants plus the unlisted-folder variant; the lists collapse above 3 and stay at most 6 rows tall"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_update_preview_page"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_update_current_and_dirty_variants"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_remove_page"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_update_lists_overflow"
        status: pass
    human_judgment: false
  - id: D2
    description: "Details buttons follow the status table; no Update all anywhere; every button waits for a job or an outside reason"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_details_buttons_per_state"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_buttons_follow_the_busy_reasons"
        status: pass
    human_judgment: false
  - id: D3
    description: "Update: looks for changes first, changes no file before Update Library, Keep Current Version never applies, result strip and log lines, job_finished kind update"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_update_flow"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_update_cancel_and_close_question"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_failed_update_logs_error_and_raw_text"
        status: pass
    human_judgment: false
  - id: D4
    description: "Remove: confirmation page, Keep Library default and Esc, Ctrl+Return and Enter on the destructive button never delete, Cancel Removing disabled, close ignored during the delete, a failed Remove keeps the entry and the row"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_remove_flow"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_remove_keep_library_and_escape_never_delete"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_failed_remove_keeps_the_entry"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_remove_not_in_catalog_folder"
        status: pass
    human_judgment: false
  - id: D5
    description: "Set Path Variables... appears only for an installed library whose variable is not set or set to a different folder and emits path_vars_requested(id)"
    requirement: "CAT-06"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_set_path_variables_button"
        status: pass
    human_judgment: false
  - id: D6
    description: "Look of the destructive button, the two long lists and the Remove page at the owner's display scale and fonts"
    requirement: "CAT-04"
    verification:
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_update.py#test_update_lists_overflow"
        status: pass
    human_judgment: true
    rationale: "The offscreen platform has no real fonts and 96 DPI only; the look of the red Remove Library button and of the lists at the owner's scale is for the verify-work UAT"

duration: 35min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 15: Update and Remove Summary

**The catalog window can update a library after a preview (Looking for changes, then Update Library) and remove one after a confirmation page whose destructive Remove Library is never the default, never on Ctrl+Return and never focused first; a failed Remove keeps the entry, and Set Path Variables... shows only for a library whose variable is not set.**

## Performance

- **Duration:** about 35 min
- **Tasks:** 2 (each a RED test commit then a GREEN feat commit)
- **Files:** 1 created (`tests/test_catalog_dialog_update.py`, 23 tests), 2 modified (`widgets/catalog_pages.py` +253 lines, `widgets/catalog_dialog.py` about +420 lines)

## Accomplishments

- Two pages on `ReviewPage`, standalone and tested without a window.
- The Update flow (look job, preview, apply job), the Remove flow (plan job, confirmation, remove job), the Details buttons for every installed and problem status, and Set Path Variables....
- The close rules for both: the question names the version an update stays on; a Remove ignores a close and says so on the strip.

## Button matrix as coded (Details page, left to right)

| Status | Visible buttons | Primary (accent) | Notes |
|--------|-----------------|------------------|-------|
| Not installed (curated) | Add This Library | Add This Library | |
| Installed, confirmed current | Remove This Library, Update This Library | none | Update disabled, tooltip `Already up to date.` |
| Installed, not checked or offline | Remove This Library, Update This Library | none | Update disabled, tooltip `No update is known. Press Check for Updates.` |
| Update available | Remove This Library, Update This Library | Update This Library | strip `⚠ A newer version is available (...)` |
| Folder missing (listed) | Remove This Library, Reinstall This Library | Reinstall This Library | |
| Not in the catalog | Remove This Library | none | |

Set Path Variables... (plain, leftmost) is added for an installed row (INSTALLED or UPDATE_AVAILABLE) with a variable that is not set or set to a different folder (`_vars_differ`, read from the same state text the Path variables row shows; hidden while KiCad's settings are unread or missing). Every button is disabled with the reason as tooltip while a job runs or an outside reason applies; Update This Library also needs `UPDATE_AVAILABLE`.

## Page methods

```python
# kicad_lib_manager/widgets/catalog_pages.py
UpdatePreviewPage(ReviewPage)   # show_plan(plan, *, name=None)      the preview, Keep Current Version / Update Library
                                # show_current(name)                 '✓ {name} is already up to date.', Back to List
                                # show_dirty(plan, *, name=None)     the refusal, changed files in Mono (8 rows, 'and {n} more')
                                # show_refusal(issue, *, heading="") any other refusal, Back to List
                                # show_notice(text)                  a ✖ row above an open preview
                                # added_list() / removed_list() / dirty_list()
RemovePage(ReviewPage)          # show_plan(plan, *, name=None)      'Remove {name}?', Keep Library / Remove Library
                                # show_refusal(issue)                a failed delete: ✖ row, Back to List
                                # line_text() / folder_label() / nickname_list() / focus_first()
ReviewPage.primary_accepts_ctrl_return()   # False on RemovePage
```

Dialog: `_update_btn`, `_remove_btn`, `_vars_btn`, `_update_page`, `_remove_page`, `_gone_result_strip`; jobs `look` (flow update, `Looking for changes in {name}...`, `Cancel Updating`), `apply` (`Updating {name}...`, `Cancel Updating`), `remove` (`Removing {name}...`, `Cancel Removing` disabled); `_STOPPABLE = ("check", "stage", "look", "apply")`. `job_finished` carries `CatalogOutcome` with kind `update` or `remove`, `id` and `name`; a stop, a refusal and a failure emit `ok=False`.

## Task Commits

1. **Task 1: the pages** - RED `19efa93` (test), GREEN `f75b277` (feat)
2. **Task 2: the flows in the window** - RED `3b8d4e9` (test), GREEN `ff21228` (feat)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Decisions Made

See `key-decisions` above.

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `19efa93` test(17-15) | `f75b277` feat(17-15) |
| 2 | `3b8d4e9` test(17-15) | `ff21228` feat(17-15) |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-14); the runs were read by hand. Task 1: 9 tests failed on `AttributeError: module ... has no attribute 'RemovePage'` or `'UpdatePreviewPage'`, the planned missing classes (no assertion reached, a weak RED because the whole feature is missing). Task 2: 14 tests failed on `AttributeError` for the missing `_vars_btn`, `_update_btn`, `_remove_btn`, `_update_page` and `_remove_page`, the planned new members. After GREEN the first run had 2 failures, both in the new tests: a test that pressed Update twice after the first press had correctly made the row current, and the raw worker text carries the exception class (`RuntimeError: boom`). No refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Remove Library never takes the first focus**
- **Found during:** Task 1
- **Issue:** `ReviewPage.focus_first` falls back to the primary button, which on the Remove page is the destructive one; Space then deletes
- **Fix:** `RemovePage.focus_first` focuses Keep Library, and the dialog skips Ctrl+Return for a page whose `primary_accepts_ctrl_return()` is False
- **Files modified:** kicad_lib_manager/widgets/catalog_pages.py, kicad_lib_manager/widgets/catalog_dialog.py
- **Committed in:** f75b277, ff21228

**2. [Rule 1 - Bug] A Remove whose row leaves the list had no place for its result strip**
- **Found during:** Task 2 (`test_remove_not_in_catalog_folder`)
- **Issue:** the result strip lives on the Details page; a deleted not-in-catalog folder or a listed non-curated library leaves no row, so the UI-SPEC's `✓ Removed {name}...` had nowhere to show
- **Fix:** the empty pane carries a second result strip (`_gone_result_strip`), filled by the same renderer; it hides as soon as a row is selected
- **Committed in:** ff21228

**3. [Plan note] Choices where the UI-SPEC is silent (each reversible)**
- The sentence `This deletes the folder {folder} ({size} on disk) and removes {name} from the catalog.` is built from three widgets (lead, an ElidedLabel with the folder in Mono and its tooltip, tail) so the folder elides instead of being cut, and `line_text()` returns the whole sentence; the accessible name of the block is the whole sentence.
- A ThirdParty folder the catalog does not list gets `This deletes the folder {folder} ({size} on disk).` (no claim about the catalog).
- A checked update that finds the folder already at the fetched commit records the row as current, and emits `update_states_changed`, so the row and the menu count stop offering it.
- A closed Update preview logs nothing: the fetch is in the clone's object store, nothing was downloaded to a copy that could be discarded (the UI-SPEC's `Discarded the download` line applies to the Add copy).
- The log line of a failed Remove is the ops text itself (it already begins `Could not remove {name}:`), not wrapped a second time.
- After a worker crash during a Remove the window reads the record and folders again, because the disk may have changed before the failure.

---

**Total deviations:** 1 missing-critical, 1 bug (both found while writing the tests), 1 note. **Impact:** no must_have is weakened.

## Issues Encountered

- A bash heredoc holding the test module failed on quoting and wrote nothing; the module and the patches were written with the file tool and applied from the scratchpad.
- QPushButton default flags are managed by `QDialog` (focus changes reset them to the main default). The Remove page's Keep Library gets `setDefault(True)` in `_update_default_button` each time the page is entered and false when it is left, so Close is the default again on the list.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-17-40 (a Remove needs the deliberate press of Remove Library: Keep Library is the default, the Esc target and the first focus; Ctrl+Return and Enter on the destructive button never delete; tested in `test_remove_keep_library_and_escape_never_delete`) and T-17-41 (`apply_update` is called only from the preview's Update Library; Keep Current Version, Back to List and Stop and Close never reach it; tested in `test_update_flow` and `test_update_cancel_and_close_question`) are mitigated.

## Next Phase Readiness

The Details pane now covers every action of the catalog window. The look of the red Remove Library button and of the 6-row lists at the owner's display scale is for the verify-work UAT. After a Set Path Variables... answer the window keeps its KiCad variable read until it is reopened (the main window owns the question; a re-read after it is not wired).

## Self-Check: PASSED

- Files found: kicad_lib_manager/widgets/catalog_pages.py, kicad_lib_manager/widgets/catalog_dialog.py, tests/test_catalog_dialog_update.py.
- Commits `19efa93`, `f75b277`, `3b8d4e9`, `ff21228` are on main (4 commits measured from the ledger base `a33821c`).
- Acceptance greps: `class UpdatePreviewPage` 1, `class RemovePage` 1, `Removing cannot be stopped halfway` 2, `def test_failed_remove_keeps_the_entry` 1.
- Plan verification: test_catalog_dialog_update (23), test_catalog_dialog_add, test_catalog_dialog, test_catalog_pages and test_catalog_dialog_geometry (157 tests together) pass with `-n 0`; test_corpus_audit, test_custom_literals, test_exit_with_hung_check, test_catalog_layering, test_layering, test_annotations_resolve, test_main_window_catalog and test_main_window_catalog_jobs pass (273 tests); the pre-publish scan of the three files and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
