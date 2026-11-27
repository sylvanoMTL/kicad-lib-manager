---
phase: 17-library-catalog
plan: 11
subsystem: widgets
tags: [catalog, window, pyside6, list, details, update-check, strips, geometry, tdd]

requires:
  - phase: 17-library-catalog
    provides: status.row_statuses, check_updates, updates_line, size_text (17-10); ops.net_status, clean_staging, size_on_disk (17-07, 17-10); manifest.load and path_vars, licence labels (17-04); library_scanner.current_path_vars (17-05)
provides:
  - widgets/catalog_dialog.py with CatalogDialog, CatalogServices, the UI copy constants and time_wording
  - the browse slice of the catalog window (header, notice strips, toolbar, sorted searchable list, Details page, result strip, manual Check for Updates, hide and reload)
  - tests/test_catalog_dialog.py (55 quick tests) and tests/test_catalog_dialog_geometry.py (11 offscreen cases)
affects: [17-12, 17-13, 17-14, 17-15, 17-17]

plan_head_before: c2ef0e63fa47af3c7a4104a3e0fa747638117bad
plan_head_after: 145f957ef9b043ac3a78fb392d5836b20dd4d11f

actuals:
  tokens: 27800
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Every slow read (Git check, staging clean-up, KiCad variable read, folder size, update check) runs through run_in_background; each callback carries the generation it started under and a close or root change bumps it, so a late result is dropped"
    - "CatalogServices is a frozen dataclass of the catalog functions (like ImportCore); tests replace single fields"
    - "A wrapped label ignores its text's width (Ignored horizontal policy) and long paths sit in ElidedLabels, so no text widens the window"
    - "The window hides on close and rebuilds from disk when it is shown again (search cleared, Git and record read again)"

key-files:
  created:
    - kicad_lib_manager/widgets/catalog_dialog.py
    - tests/test_catalog_dialog.py
    - tests/test_catalog_dialog_geometry.py
  modified: []

key-decisions:
  - "ElidedLabel was not moved: import_result imports no catalog or dialog module, so catalog_dialog imports it directly without a cycle"
  - "The Repository link and the Details heading elide (middle and right, full text as tooltip) instead of wrapping: Qt breaks a line only at spaces, so an address or a 60-character name cannot wrap and would widen the window"
  - "Every wrapped label has an Ignored horizontal policy; a path that cannot wrap is cut at the right edge and its full text is the tooltip (record strip) or sits in an ElidedLabel (Folder, header)"
  - "The detail pane has no minimum height of its own and the splitter rule keeps it at 200 px only while the window has room, so two long strips at 760 x 520 squeeze the pane (it scrolls) and never the list or the toolbar"
  - "Until the Git check answers, the network actions are disabled with the tooltip 'Looking for Git...'; the check starts at construction, on every root change and when the window is shown again after a close"
  - "Check for Updates summary counts only CURRENT checks ('Checked {n} catalog libraries: all up to date.', singular for 1); all-unknown gives the warning; any update gives the updates_line"
  - "Size on disk is measured off the GUI thread (CatalogServices.size_on_disk, a 12 GB Wurth folder would freeze the window) and reads 'Calculating...' first"

patterns-established:
  - "show_result(lines, generate=, manifest_note=): lines are (text, level) with level success or warning; the window adds the check or warning glyph"
  - "closeEvent drops outstanding results even for a window that is not visible (it is then deleted by the test fixture or the main window)"

requirements-completed: [CAT-01, CAT-07, CAT-06]  # REQUIREMENTS.md boxes stay open where later plans of the phase declare the same IDs (shared-ID gate)

coverage:
  - id: D1
    description: "Window shell: parentless non-modal CatalogDialog titled 'Library Catalog - KiCad External Lib Manager', 900 x 640 with a 760 x 520 minimum, header with Help (F1) and the elided Mono collection path, Close as the default button, focus in Search"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_window_is_parentless_and_non_modal"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_title_size_and_minimum"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_header_path_is_elided_mono_with_tooltip"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_focus_starts_in_search_and_f1_opens_help"
        status: pass
    human_judgment: false
  - id: D2
    description: "The list: four columns with the exact status texts, colours and tooltips, licence and size cells, name order that never changes with a status, no header sorting, search on name, description and repository with the empty state"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_status_texts_and_colours"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_rows_sorted_and_stable"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_search_filters_and_empty_state"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_search_keeps_selection_only_when_the_row_still_matches"
        status: pass
    human_judgment: false
  - id: D3
    description: "Notice strips in the fixed order (record unreadable, Git missing, Git too old, old Git) with their disabled actions and reasons; the Git check, staging clean-up and variable read run off the GUI thread and a stale answer is dropped"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_unreadable_record_strip_disables_actions"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_git_too_old_strip_disables_network_actions"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_git_check_and_cleanup_run_off_the_gui_thread"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_stale_git_result_is_dropped_after_a_root_change"
        status: pass
    human_judgment: false
  - id: D4
    description: "Details page: every row with an explicit value for every state, the folder-missing, not-in-catalog and update strips with the spec text, licence acknowledgement, size on disk, library counts from the scan or the curated list, and the time wording"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_problem_strips_read_as_the_spec"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_no_details_row_is_ever_blank"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_updates_row_texts"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_time_wording"
        status: pass
    human_judgment: false
  - id: D5
    description: "Path variable state per library (set, not set, set to a different folder, KiCad settings not found, needs none)"
    requirement: "CAT-06"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_path_variable_states"
        status: pass
    human_judgment: false
  - id: D6
    description: "Manual Check for Updates on a daemon thread with Checking... state, the three summary log lines, update_states_changed, a failed check logged, and a result after a root change dropped; set_check_running for the startup check"
    requirement: "CAT-07"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_check_for_updates_runs_in_background"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_check_summary_lines"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_check_result_after_root_change_is_dropped"
        status: pass
    human_judgment: false
  - id: D7
    description: "Result strip with Generate Tables and the catalog.json note (git root only), hide on close, reopen rebuilt from disk with an empty search, set_root reload, no timer or late result after close"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_show_result_strip"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_close_hides_and_reopen_clears_search"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_set_root_reloads_everything"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_done_stops_timers_and_ignores_late_results"
        status: pass
    human_judgment: false
  - id: D8
    description: "Layout holds at 760 x 520, 900 x 640 and 1100 x 720: toolbar, headers, Details rows and buttons reachable without horizontal scrolling, long path/name/folder elide, markup names as typed, search shrinks before the buttons, two strips at 520 px keep the list at 120 px"
    requirement: "CAT-01"
    verification:
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_geometry.py#test_minimum_size_keeps_everything_reachable"
        status: pass
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_geometry.py#test_long_names_elide_without_widening"
        status: pass
      - kind: automated_ui
        ref: "tests/test_catalog_dialog_geometry.py#test_all_strips_at_minimum_height"
        status: pass
    human_judgment: true
    rationale: "The offscreen platform has no real fonts and 96 DPI only; whether the window looks right at the owner's display scale is for the verify-work UAT (UI-SPEC planner assumption)"

duration: 18min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 11: Catalog Window Browse Slice Summary

**A parentless, non-modal Library Catalog window that lists every curated, added and stray library with its exact status, licence and size, searches them, shows a Details page with path-variable and update state, the record and Git notice strips and a manual Check for Updates that never leaves the GUI thread, and is proven to lay out at 760 x 520 offscreen.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-11-27T10:35:15Z
- **Completed:** 2026-11-27T10:53:33Z (code), SUMMARY and state follow
- **Tasks:** 3 (tasks 1 and 2 each a RED test commit then a GREEN feat commit; task 3 geometry tests plus the fixes they found)
- **Files:** 3 created (`widgets/catalog_dialog.py` about 1300 lines, two test modules)

## Accomplishments

- `CatalogDialog` and `CatalogServices`: the window, its signals and the API plans 17-12, 17-13 and 17-15 build on.
- The list with the seven status texts, colours and tooltips of the UI-SPEC, stable name order, search with the empty state, keyboard path from Search into the list.
- Notice strips in the fixed order with their reasons as tooltips on the disabled actions (D-02, D-11, D-29); the Git check, the staging clean-up and the KiCad variable read each run on a daemon thread.
- The Details page for every state: Repository link, Licence (with the acknowledgement), Size (about, or on disk measured off the GUI thread), Libraries (scan counts, curated counts or "Known after it is added"), Path variables (CAT-06), Installed version, Updates (D-32 time wording), Folder, plus the folder-missing, not-in-catalog and update-available strips.
- The result strip, hide-on-close with a rebuild from disk on reopen, `set_root` as one reload step, and a generation counter that drops every late result.
- Manual Check for Updates (CAT-07) with the three summary log lines of the UI-SPEC.
- 55 quick tests and 11 offscreen geometry cases (about 6 s together), all passing with 0 skipped.

## Public API (read by plans 17-12, 17-13, 17-14 and 17-15)

```python
# kicad_lib_manager/widgets/catalog_dialog.py
CATALOG_TITLE, CATALOG_TOPIC = "catalog"      # + every UI-SPEC text as a module constant (see below)
class CatalogServices:   # frozen dataclass, defaults are the real functions
    load_manifest, curated (the CURATED tuple), row_statuses, check_updates, net_status, clean_staging,
    current_path_vars, path_vars, size_on_disk, plan_add, stage_add, register_add, discard_staging,
    plan_reinstall, check_repository, plan_update, apply_update, plan_remove, apply_remove,
    kicad_running, repo_info, free_space
class CatalogDialog(QDialog):
    __init__(root, *, services=None, show_guide=None, clock=datetime.now)   # no parent
    signals: log_line(str text, str level), update_states_changed(object), generate_requested(),
             path_vars_requested(str), job_finished(object), busy_changed()
    set_root(root), set_scan(result), set_blocked(reason | None), apply_update_states(states),
    set_check_running(bool), refresh(), show_result(lines, *, generate, manifest_note),
    is_job_running(), holds_download(), is_finishing(), set_finishing(bool),
    selected_id(), current_row()
def time_wording(when, now) -> str
```

Hooks for the next plans: the Details page has an empty `_button_row` (QHBoxLayout, stretch first) for the page buttons, `_pages` (QStackedWidget: empty page, Details page) for review pages, `_action_block()` and `_refresh_actions()` for the shared disable rule (reasons: finishing, blocked, unreadable record, Git, Git still being looked for), `_track(task)` for a new background job, and `_stop_background()` which also bumps the generation. `log_line` levels are `info`, `warning`, `error`; `show_result` levels are `success`, `warning`.

Constants holding the UI copy (all in `catalog_dialog.py`, each text written once): `HEADING_TEXT`, `HELP_TEXT`, `INSTALLED_IN_TEXT`, `SEARCH_TEXT`, `CHECK_TEXT`, `CHECKING_TEXT`, `ADD_URL_TEXT`, `CLOSE_TEXT`, `GENERATE_TEXT`, `EMPTY_PANE_TEXT`, `NO_MATCH_HEADING`, `NO_MATCH_BODY`, the status texts (`NOT_INSTALLED_TEXT`, `INSTALLED_CURRENT_TEXT`, `INSTALLED_TEXT`, `INSTALLED_TIP`, `UPDATE_AVAILABLE_TEXT`, `FOLDER_MISSING_TEXT`, `NOT_IN_CATALOG_TEXT`, `UNKNOWN_TEXT`), `RECORD_STRIP_TEXT`, the tooltips (`RECORD_UNREADABLE_TIP`, `GIT_MISSING_TIP`, `GIT_TOO_OLD_TIP`, `GIT_CHECKING_TIP`, `FINISHING_TIP`), `FIELDS`, the Details texts (`NOT_STATED_TEXT`, `LICENCE_UNREADABLE_TEXT`, `SIZE_PENDING_TEXT`, `LIBRARIES_UNKNOWN_TEXT`, `NO_VARS_TEXT`, `VAR_*_TEXT`, `UPDATES_*_TEXT`), `FOLDER_MISSING_STRIP`, `NOT_IN_CATALOG_STRIP`, `UPDATE_STRIP`, `MANIFEST_NOTE_TEXT`, `CHECK_OFFLINE_LINE`, `STEP_FAILED`.

ElidedLabel did not move: `import_result` imports no dialog or catalog module, so `catalog_dialog` imports it directly.

## Task Commits

1. **Task 1: shell, strips, toolbar, list and search** - RED `5b6cb9d` (test), GREEN `cf83f8d` (feat)
2. **Task 2: Details page, result strip, Check for Updates, hide and reload** - RED `3f5687d` (test), GREEN `c6b5c12` (feat)
3. **Task 3: geometry backstops offscreen** - `145f957` (test, with the layout fixes they found)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `kicad_lib_manager/widgets/catalog_dialog.py` - the window, CatalogServices, the copy constants, time_wording
- `tests/test_catalog_dialog.py` - 55 qtbot tests of the shell, list, statuses, search, strips, Details, check, hide and reload
- `tests/test_catalog_dialog_geometry.py` - 11 offscreen geometry cases at 760 x 520, 900 x 640 and 1100 x 720

## Decisions Made

See `key-decisions` above. In short: ElidedLabel stays where it is; addresses and the heading elide because Qt cannot break inside an unbroken word; wrapped labels never widen the window; the pane gives way before the list; the network actions wait for the Git check; the size on disk is measured on a thread.

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `5b6cb9d` test(17-11) | `cf83f8d` feat(17-11) |
| 2 | `3f5687d` test(17-11) | `c6b5c12` feat(17-11) |
| 3 | `145f957` test(17-11) (tests, with the fix in the same commit; the plan task is not `tdd="true"`) | same commit |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-10); the runs were read by hand. Task 1: collection stopped with `ImportError: cannot import name 'catalog_dialog' from 'kicad_lib_manager.widgets'`, the planned missing module (no test could run, so no assertion was reached). Task 2: 19 of the 55 tests failed on the planned missing behaviour (`AttributeError: 'CatalogDialog' object has no attribute '_result_strip'` / `show_result`, and `Timeout` waiting for a check that no button started), the other 36 (the Task 1 behaviour, `time_wording`, close and reopen) passed as expected. Task 3: before the fix the geometry cases failed on a Details page 1208 px wide in an 834 px viewport and on a strip label 10 px short. No refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A result that arrives for a window that was never shown crashed after deletion**
- **Found during:** Task 2 (teardown of the first GREEN run: `RuntimeError: Internal C++ object (QTreeWidget) already deleted`)
- **Issue:** `done()` only runs for a visible window; `close()` on a hidden window just accepts the event, so outstanding background results were delivered to a deleted window.
- **Fix:** `closeEvent` drops outstanding results (generation bump, cancel event, tasks cancelled) before the normal close.
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py
- **Pinned by:** every test that builds a window and does not show it (the qtbot teardown closes it)
- **Committed in:** c6b5c12

**2. [Rule 1 - Bug] Long unbreakable text widened the detail page and the strips**
- **Found during:** Task 3 (`test_long_names_elide_without_widening`: page 1208 px in an 834 px viewport)
- **Issue:** a word-wrapped QLabel reports the width of its longest word as its minimum, so a 60-character name, a 150-character web address or a long path pushed the page past the window. Qt cannot break inside a word (measured: no break at a zero-width space, a soft hyphen or CSS word-break).
- **Fix:** wrapped labels have an Ignored horizontal policy (a path that cannot wrap is cut at the edge, its full text is the tooltip or sits in an ElidedLabel); the Repository link (`_LinkLabel`, middle elision) and the Details heading (ElidedLabel, right elision) elide with the whole text as tooltip. The detail pane has no height of its own to insist on, so two long strips at 760 x 520 squeeze the pane (it scrolls) and never the list or the toolbar; the 200 px rule holds while the window has room.
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py, tests/test_catalog_dialog.py, tests/test_catalog_dialog_geometry.py
- **Committed in:** 145f957

**3. [Rule 3 - Blocking] Small additions outside the plan's lists**
- `CatalogServices.size_on_disk` (not in the plan's field list): the size of an installed folder must be measured off the GUI thread (the Wurth folder is about 12 GB).
- `CatalogDialog(..., clock=datetime.now)` keyword: the plan's time-wording test needs an injected clock; `selected_id()`, `current_row()` and the public `time_wording()`.
- Details strip for `Update available` (`⚠ A newer version is available ({installed} -> {available}).`): it is in the UI-SPEC status table although no must_have lists it.
- **Committed in:** cf83f8d, c6b5c12

**4. [Plan note] Known limits against the UI-SPEC**
- Line height 1.5 for wrapped strips: a plain-text QLabel has no line-height setting and the plan requires plain text, so the native line metrics are used.
- The Repository link elides instead of wrapping (see deviation 2); the UI-SPEC says "wraps".
- The job strip, the primary buttons of the pages and `Ctrl+Return` are not built here: no job or page exists before plan 17-13 (the Details `_button_row` is the attachment point).

---

**Total deviations:** 2 auto-fixed bugs, 1 blocking-scope addition (three small parts), 1 note. **Impact:** no must_have is weakened; the elision of the address and the heading is the one visible difference from the UI-SPEC wording and is needed to keep the window from widening.

## Issues Encountered

- A first attempt to append the Task 2 tests with a shell heredoc failed on quoting and wrote nothing; the tests were written to a scratch file and appended with a short Python script.
- The offscreen platform draws no glyphs (every character is a box), so the screenshot taken for a sanity check shows layout only, not text.

## Known Stubs

| File | Line | Reason |
|------|------|--------|
| kicad_lib_manager/widgets/catalog_dialog.py | `self._add_url_btn = QPushButton(ADD_URL_TEXT)` | The `Add by URL...` button is in the toolbar (the geometry plan names it) but has no action until plan 17-13 attaches the Add by URL page |
| kicad_lib_manager/widgets/catalog_dialog.py | `def is_job_running` | `is_job_running()` and `holds_download()` answer False until plan 17-13 adds the catalog jobs |

Both are intentional and named in the plan ("no job kinds exist before plan 17-13", "Add by URL... joins the toolbar in plan 17-13"); they are recorded in `.planning/WINDOWS.md`. The User Guide page key `catalog` does not exist yet (the guide is extended in a later plan of the phase), so Help currently opens the guide on its remembered page.

## Threat Flags

None beyond the plan's threat model: T-17-31 (plain text everywhere except the Repository link, whose address is HTML-escaped and only an `https://` address becomes a link) and T-17-32 (Git check, staging clean-up, variable read, folder size and update check on daemon threads; generation counter plus cancel event drop stale results) are mitigated and tested.

## Next Phase Readiness

Plans 17-12 (menu entry, startup check, busy rules, close rules), 17-13 (Add and Add by URL), 17-14 and 17-15 (Update, Remove, Reinstall) build on the API above. 17-12 wires `show_guide`, `set_scan`, `set_root`, `set_blocked`, `apply_update_states` and `set_check_running`. Display scaling above 150 % is not verified (UI-SPEC planner assumption); the owner checks it in the verify-work UAT.

## Self-Check: PASSED

- Files found: kicad_lib_manager/widgets/catalog_dialog.py, tests/test_catalog_dialog.py, tests/test_catalog_dialog_geometry.py.
- Commits `5b6cb9d`, `cf83f8d`, `3f5687d`, `c6b5c12`, `145f957` are on main (5 commits measured from the ledger base `c2ef0e6`).
- Acceptance greps print the expected counts (`class CatalogDialog` 1, `CATALOG_TITLE = "Library Catalog - KiCad External Lib Manager"` 1, `Select a library to see its details.` 1, `def show_result` 1, geometry `def test_` 7 definitions giving 11 cases).
- Plan verification: `test_catalog_dialog.py` (55), `test_catalog_dialog.py` with `test_background.py` (64) and `test_catalog_dialog_geometry.py` (11, 0 skipped) pass with `-n 0`; `test_layering.py`, `test_catalog_layering.py` and `test_annotations_resolve.py` pass; the pre-publish scan of the three files is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
