---
phase: 17-library-catalog
plan: 23
subsystem: main-window
tags: [catalog, refresh-overlay, spinner, scan-progress, log-summary, catalog-names, tdd]

requires:
  - phase: 17-library-catalog
    provides: CatalogRescanWorker and the after-job sequence (17-14), the owner's findings 2, 3 and 6 (17-17), catalog/names.source_names (17-21)
provides:
  - widgets/refresh_overlay.py - RefreshOverlay and SpinnerWheel: a spinning wheel, text, bar and file count over both library trees
  - scan_source(progress=) and CatalogRescanWorker.progress: file counts from the one-source read to the window
  - library_scanner.summarize_catalog_lines: one warning per catalog library and kind for the log
  - LibraryTableWidget.populate(source_names=): a catalog source shown by its catalog name
affects: [17-24, 17-26]

plan_head_before: a1d629d
plan_head_after: 9a3a67ee50f645e85a02c4874e70121ba57a631c

actuals:
  tokens: 14300
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "A child overlay of the list area follows its parent through an event filter on Resize; its wheel timer starts in showEvent and stops in hideEvent (a hidden or closed parent sends hideEvent to it), so no timer outlives the window"
    - "The worker throttles its own signal (one count per whole percent plus the last), scan_source reports every count"
    - "Only what is written to the log is shortened: the ScanResult keeps every issue and warning counts read the raw lines"
    - "A group header in the trees keeps its source key in a data role (_SOURCE_ROLE) while its text is the name shown"

key-files:
  created:
    - kicad_lib_manager/widgets/refresh_overlay.py
    - tests/test_refresh_overlay.py
  modified:
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/main_window.py
    - kicad_lib_manager/widgets/library_table.py
    - tests/test_scan_source.py
    - tests/test_scanner_issues.py
    - tests/test_main_window_catalog_jobs.py
    - tests/test_main_window.py

key-decisions:
  - "scan_source reads the symbol files first and the footprint files second (it used to check the footprints first), so the count only goes up; the result is the same"
  - "The summary lists the first 5 distinct examples and counts the distinct ones left out in 'and {m} more' (equal to the plan's wording when the examples differ, and not repeating one model path when many footprints share it)"
  - "A missing footprint link is grouped only when every symbol library of that nickname lives in the one ThirdParty/<id> source; the library name is read from the issue text itself"
  - "Names come from catalog_source_names(root): catalog.json read through catalog_manifest.load and names.source_names, curated names alone when the record cannot be read; a source with no entry (Custom) keeps its folder name"
  - "The refreshing state ends in _on_catalog_rescanned (in a finally, after the trees are filled) and at the top of _catalog_full_scan, so the fallback and a failed read end it before the Loading Libraries window; Generate Tables stays off until the finishing state ends, as 17-14 made it"

patterns-established:
  - "RefreshOverlay API: show_for(kind, name), set_progress(done, total), finish(); text(), count_text(), bar_value(), bar_maximum(), is_indeterminate() for tests"

requirements-completed: [CAT-02, CAT-05, CAT-01]

coverage:
  - id: D1
    description: "scan_source reports (files read, total) over symbol and footprint files, never going down, ending with (total, total); no keyword means no call"
    requirement: CAT-02
    verification:
      - kind: unit
        ref: "tests/test_scan_source.py#test_scan_source_reports_file_progress"
        status: pass
    human_judgment: false
  - id: D2
    description: "During the source read after a catalog change a large wheel, the text, a bar and '{done} of {total} files' cover both trees; both trees, Select All, Deselect All and Generate Tables are disabled and come back after; the read sends at most one count per whole percent"
    requirement: CAT-02
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_refresh_overlay_during_the_source_read"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_refresh_disables_the_list_controls"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_progress_is_throttled_to_whole_percents"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_overlay.py#test_bar_and_count"
        status: pass
    human_judgment: false
  - id: D3
    description: "The wheel turns only while shown; its timer stops on hide, on a hidden parent and on window close; the overlay hides at once on the full-scan fallback and on a failed read"
    requirement: CAT-02
    verification:
      - kind: unit
        ref: "tests/test_refresh_overlay.py#test_wheel_turns_only_while_shown"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_close_stops_the_wheel"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_refresh_ends_on_fallback_and_failure"
        status: pass
    human_judgment: false
  - id: D4
    description: "The look of the refreshing state (wheel size, spacing, wording on screen) reads as obviously working"
    requirement: CAT-02
    verification: []
    human_judgment: true
    rationale: "Whether the wheel is large and clear enough is the owner's judgment; offscreen tests check the size, the colours and the text, not the impression"
  - id: D5
    description: "For a catalog library the per-file 3D model and footprint-link lines become one warning line per library and kind with count and first 5 examples; the scan result keeps every issue; Custom and other lines stay as they are"
    requirement: CAT-05
    verification:
      - kind: unit
        ref: "tests/test_scanner_issues.py#test_catalog_model_lines_are_summarized"
        status: pass
      - kind: unit
        ref: "tests/test_scanner_issues.py#test_missing_models_and_unreadable_files"
        status: pass
      - kind: unit
        ref: "tests/test_scanner_issues.py#test_missing_footprint_links_are_summarized"
        status: pass
      - kind: unit
        ref: "tests/test_scanner_issues.py#test_other_lines_are_untouched"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_log_shows_one_line_per_catalog_library"
        status: pass
    human_judgment: false
  - id: D6
    description: "Both trees name a catalog source by its catalog name in the group header and Source column; ticking a header ticks exactly that source's libraries; other sources keep their folder name"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_trees_show_catalog_names"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 23: Refreshing state, one log line per catalog library, catalog names in the trees Summary

**A large spinning wheel with text, bar and file count covers the library trees while a catalog change is read again, the log gets one warning per catalog library and kind instead of thousands of per-file lines, and the trees show a catalog library by its catalog name.**

## Performance

- **Duration:** about 25 min
- **Started:** 2026-11-27T16:45:00Z (approximate)
- **Completed:** 2026-11-27T17:01:00Z
- **Tasks:** 3 (each a RED test commit and a GREEN feat commit)
- **Files modified:** 9 (2 created)

## Accomplishments

- Owner finding 2 (17-17): after an Add, Reinstall, Update or Remove the main window shows the refreshing state while the source is read again.
- Owner finding 3: a catalog library's 3D model and footprint-link lines become one summary line per library and kind.
- Owner finding 6 (main window side): the trees show `4ms/4ms-kicad-lib` where they showed the folder name `4ms-4ms-kicad-lib`.

## The overlay API and the throttle rule

- `RefreshOverlay(parent)` covers `parent` (the list area, which holds both trees and the empty page) and follows its size through an event filter. `show_for(kind, name)` sets the text, makes the bar move without a value, clears the count and shows the overlay; `set_progress(done, total)` gives the bar `done * 100 // total` of 100 and the count; `total <= 0` keeps the bar moving; `finish()` hides it.
- Texts as coded: `Refreshing the library list after {adding|reinstalling|updating|removing} {name}. Large libraries can take a minute.` (plain text, word-wrapped, at most 520 px) and `{done} of {total} files` with thousands separators in the MUTED colour. Accessible names: `Refreshing the library list` and `Progress of refreshing the library list`.
- `SpinnerWheel` is 112 x 112 px: a 12 px ACCENT arc of 300 degrees on a BORDER ring, 12 degrees every 40 ms (a full turn in 1.2 s). Its QTimer starts in `showEvent` and stops in `hideEvent`; a hidden or closed parent sends `hideEvent` to it, and `closeEvent` of the main window also calls `finish()`.
- Throttle: `scan_source(progress=)` reports every count (the symbol files first, then the footprint files, then `(total, total)`); `CatalogRescanWorker._report` sends the `progress(int, int)` signal only when the whole percent changed or `done >= total`, so 11,000 files send at most 101 counts.
- The main window sets `_refreshing` in `_begin_refreshing` (after the worker starts) and ends it in `_end_refreshing`: in a `finally` around the one-source result handling, and at the top of `_catalog_full_scan` (the fallback and a failed read). While it is set `_refresh_busy_controls` disables both trees (one widget), Select All and Deselect All; Generate Tables is already off through the catalog finishing state, which ends after the path-variable question as before.

## The summary texts as coded

`{name}` is the catalog name (the id when the map has none). Counts and the "more" number use thousands separators. Examples are the first 5 distinct items.

| Kind | Several | One |
|------|---------|-----|
| 3D model at a fixed folder | `{name}: {n} footprints point their 3D model at a fixed folder instead of a path variable, for example {a}, {b}, ... and {m} more.` | `{name}: 1 footprint points its 3D model at a fixed folder instead of a path variable: {a}.` |
| 3D model not found | `{name}: {n} 3D models were not found (names are case-sensitive), for example ...` | `{name}: 1 3D model was not found (names are case-sensitive): {a}.` |
| Footprint file unreadable | `{name}: {n} footprint files could not be read, for example ...` (paths inside the library folder) | `{name}: 1 footprint file could not be read: {a}.` |
| Footprint link to a library not there | `{name}: {n} footprint links point to footprint libraries that are not in your collection or in KiCad's own libraries: {libs}.` | `{name}: 1 footprint link points to a footprint library that is not in your collection or in KiCad's own libraries: {lib}.` |

Each is one `Severity.WARNING` issue with code `scan.catalog_summary`, placed where the first line of its group was. `main_window._log_scan_issues` writes them instead of the raw list in `_on_scan_finished` and `_log_catalog_rescanned`; the warning counts and the "No warnings." rule still read the raw issues, and `ScanResult.issues` is never changed.

## Where the names come from

`main_window.catalog_source_names(root)` reads `catalog.json` through `catalog_manifest.load` and `catalog/names.source_names` (curated names alone when the record is missing or unreadable). `_populate_tree` passes the map to every `populate` call, and `_log_scan_issues` passes it to the summaries. `LibraryTableWidget.populate(scan_result, source_names=None)` shows the name in the group header and the Source column; the group item keeps the source key in `_SOURCE_ROLE` and `_on_sym_item_changed` reads that key, so ticking a header still ticks exactly that source. Sources stay sorted by their key.

## Task Commits

1. **Task 1 (tracer): file counts to an overlay** - RED `6e0921f`, GREEN `549ff2d`. Tracer verified end-to-end (scan_source and catalog-jobs modules pass) before expanding.
2. **Task 2: the wheel, the controls and every way the refresh ends** - RED `09dda5c`, GREEN `f74e832`
3. **Task 3: one log line per catalog library and the catalog names** - RED `2d5fa69`, GREEN `9a3a67e`

**Plan metadata:** the docs commit follows this file.

## Files Created/Modified

- `kicad_lib_manager/widgets/refresh_overlay.py` - RefreshOverlay, SpinnerWheel (new)
- `kicad_lib_manager/library_scanner.py` - `scan_source(progress=)`, `summarize_catalog_lines` (CRLF kept)
- `kicad_lib_manager/main_window.py` - `CatalogRescanWorker.progress`, the overlay wiring, `_log_scan_issues`, `_populate_tree`, `catalog_source_names` (CRLF kept)
- `kicad_lib_manager/widgets/library_table.py` - `populate(source_names=)`, `_SOURCE_ROLE` (CRLF kept)
- tests: `test_refresh_overlay.py` (new), additions to `test_scan_source.py`, `test_scanner_issues.py`, `test_main_window_catalog_jobs.py`

## Decisions Made

See `key-decisions`. The plans of this phase are `type: execute`, so the `tdd-red-evidence` classifier of `type: tdd` plans was not run and no RED evidence record was written. Each RED commit failed for the planned reason (a missing keyword, attribute or function, and tree headers still showing the folder name); the tests that already passed after the tracer (the controls, the fallback, the verbs, the throttle) were written in the Task 2 RED commit and were green from the tracer on.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two existing tests replaced `LibraryTableWidget.populate` with a one-argument function**
- **Found during:** Task 3 (tests/test_main_window.py, `test_rescan_with_populate_raising_still_clears_busy_state` and the start-scan twin at line 1084)
- **Issue:** `populate` now receives `source_names=`, so their `boom(_result)` stand-in raised a TypeError instead of the intended RuntimeError
- **Fix:** the stand-ins take `**_kwargs`
- **Files modified:** tests/test_main_window.py
- **Commit:** `9a3a67e`

**2. [Rule 1 - Bug, test] The first draft of the log test used identical lines before and after the rescan**
- **Issue:** `_log_catalog_rescanned` only counts lines that were not in the previous scan, so identical fake lines read as "no warnings"; the test now gives the first scan different file names
- **Files modified:** tests/test_main_window_catalog_jobs.py
- **Commit:** `9a3a67e` (the test was still RED-committed in `2d5fa69`)

**3. [Wording] "first 5 examples" is "first 5 distinct examples"**
- The count after "and" is of the distinct examples left out. For the plan's own cases (all examples different) the text is identical; where many footprints share one model path the line does not repeat it.

### Auth gates

None.

**Total deviations:** 3 (1 blocking test fix, 1 test fix, 1 wording refinement). **Impact:** none on the behaviour the plan describes.

## Issues Encountered

None that remained. The Qt offscreen run prints the usual font-directory warnings.

## Threat Flags

None. No network endpoint, auth path or file access was added; the overlay text is plain text and the log panel already shows text as typed (T-17-59), the wheel's timer stops with the overlay (T-17-57).

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 17-24 (which depends on 17-23) can rely on the catalog names in the trees and the log.
- The User Guide, UI-SPEC and CLAUDE.md do not yet describe the refreshing state or the one-line summaries; the docs plans of this phase should add them (not part of this plan's file list).
- The look of the wheel (size, spacing) is for the owner to judge in the next real-network check.

## Self-Check: PASSED

- `kicad_lib_manager/widgets/refresh_overlay.py` and `tests/test_refresh_overlay.py` exist; all six task commits (`6e0921f`, `549ff2d`, `09dda5c`, `f74e832`, `2d5fa69`, `9a3a67e`) are ancestors of HEAD.
- Acceptance greps: `class RefreshOverlay` 1, `progress = Signal` 2, `class SpinnerWheel` 1, `Large libraries can take a minute.` 1, `def summarize_catalog_lines` 1, `_SOURCE_ROLE` 4.
- `-n 0` run of the plan modules and test_main_window, test_main_window_catalog, test_exit_with_hung_check, test_corpus_audit, test_custom_literals, test_layering, test_annotations_resolve, test_library_table_widget, test_library_table_atomic, test_catalog_layering: 522 passed, 2 corpus tests deselected.
