---
phase: 17-library-catalog
plan: 21
subsystem: catalog
tags: [catalog, progress, sizes, naming, pyside6, tdd]

requires:
  - phase: 17-library-catalog
    provides: the catalog window, its flows and the 17-17 owner findings (plans 17-11 to 17-17)
provides:
  - the check's file count (validate_staging / stage_add check_progress) and the job strip line 'Checking {name}... {percent}% ({done} of {total} files)'
  - the Size cell of installed rows on disk, measured one folder at a time off the GUI thread and shared with Details
  - RemovePlan.symbol_nicknames and footprint_nicknames and the Remove page heading '{s} symbol and {f} footprint libraries'
  - catalog/names.py: display_name and source_names, the one name rule of a catalog library
affects: [17-22, 17-23, 17-24, 17-25]

plan_head_before: be31174e844ea1a48488a4ff21ff72529bbec583
plan_head_after: 0d8f37bcd66bc8e2bde8b50aca1cbfeab655fe43

actuals:
  tokens: 60000
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "check progress as progress(done, total) callbacks through validate_staging -> stage_add -> the stage closure, throttled to one count per whole percent in the window"
    - "a marker text ('check-files') on the worker's progress signal carries the file count: (marker, files done, files in all)"
    - "one measurement at a time: a queue, a running folder and a stale set; the window drops a result whose folder changed under it"

key-files:
  created:
    - kicad_lib_manager/catalog/names.py
    - tests/test_catalog_names.py
  modified:
    - kicad_lib_manager/catalog/validate.py
    - kicad_lib_manager/catalog/ops.py
    - kicad_lib_manager/catalog/status.py
    - kicad_lib_manager/widgets/catalog_dialog.py
    - kicad_lib_manager/widgets/catalog_pages.py
    - tests/test_catalog_layering.py
    - tests/test_catalog_ops.py
    - tests/test_catalog_ops_update.py
    - tests/test_catalog_dialog.py
    - tests/test_catalog_dialog_add.py
    - tests/test_catalog_dialog_update.py
    - .planning/phases/17-library-catalog/17-UI-SPEC.md

key-decisions:
  - "The file count rides the worker's existing progress signal (text, percent, total): the text slot holds the marker 'check-files', the percent slot the files done and the total slot the files in all; ordinary git lines keep (text, percent, 0)"
  - "The window throttles the count (one per whole percent, plus the last) in the stage closure, so a library of 11,000 footprints sends at most 102 updates"
  - "Folder sizes: the cache survives a reload (a finished Add, Update, Reinstall or Remove drops that folder's value through _forget_size and the folder is measured again); the old behaviour of clearing every value on each reload is gone"
  - "names.display_name takes an optional url= so a checked address that has no entry yet is named owner/repo; ops imports the function by name (display_name) because several ops functions use a local called names"
  - "An entry whose id is not curated and whose address is on GitHub is named owner/repo everywhere, including the Update, Remove and Reinstall pages and log lines"

requirements-completed: [CAT-02, CAT-01, CAT-04]

coverage:
  - id: D1
    description: "The job strip shows the check's file count with thousands separators and a determinate bar, throttled, and Cancel still stops the job and deletes the download"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_check_shows_file_count"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_check_count_is_throttled"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_check_reports_footprint_progress"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_stage_add_forwards_the_check_count"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Size cell of installed, update-available and not-in-the-catalog rows shows the size on disk (Calculating..., Unknown), measured one folder at a time and shared with the Details page"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_installed_size_cell_shows_size_on_disk"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_folders_are_measured_one_at_a_time"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_a_finished_change_measures_the_folder_again"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Remove page counts symbol and footprint libraries apart and lists each library with its kind"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_remove_page_counts_each_kind"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_update.py#test_plan_remove_splits_the_kinds"
        status: pass
    human_judgment: false
  - id: D4
    description: "A library added by web address has one name, owner/repo, in the list, Details, every page and every catalog log line"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_names.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "How the new job strip text, the Size cells and the Remove list read in the real window on a large library (11,000 footprints)"
    verification: []
    human_judgment: true
    rationale: "Owner-visible wording and layout on a real download; the offscreen tests assert the texts, not how the strip feels while a real check runs"

duration: 62min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 21: Check progress, sizes on disk, Remove counts and one library name Summary

**The catalog counts the files of a download check in the job strip, shows installed sizes on disk one folder at a time, counts symbol and footprint libraries apart on the Remove page, and names a library added by web address `owner/repo` everywhere through the new `catalog/names.py`.**

## Performance

- **Duration:** about 62 min
- **Started:** 2026-11-27T15:24:00Z
- **Completed:** 2026-11-27T16:30:00Z
- **Tasks:** 3 (1 tracer, 2 auto, all TDD)
- **Files modified:** 14 (2 created)

## Accomplishments

- Owner finding 1 (17-17): while a download is checked the strip reads `Checking SparkFun... 38% (4,210 of 11,050 files)` with a determinate bar; before the files are counted it stays `Checking {name}...` with the moving bar; Cancel still ends with `Stopped adding ... Nothing was added.` and deletes the download.
- Owner finding 4: installed, update-available and not-in-the-catalog rows show their size on disk (`325 MB`, `9.6 GB`, tooltip `{size} on disk`), `Calculating...` and `Unknown` in MUTED; the list and Details share one measurement per folder per load.
- Owner finding 5: the Remove page heads its list `Libraries that leave your scan: 25 symbol and 29 footprint libraries` and lists each library with a Kind column, so a symbol and a footprint library of one name are two rows.
- Owner finding 6 (catalog side): `catalog/names.py` is the one name rule; the list, plans, refusals and log lines of the catalog use it. The main window's trees and log lines follow in plan 17-23.

## Interfaces added

- `validate.detect_vars(folder, footprint_files, *, progress=None)` and `validate.validate_staging(..., progress=None)`: `progress(done, total)` is called once per footprint file read; no call for a refusal or a download with no footprint file.
- `ops.stage_add(..., check_progress=None)`: handed to `validate_staging`; runs on the thread that called `stage_add`.
- Worker progress signal: ordinary git lines are `(text, percent_or_-1, 0)`; the check's count is `("check-files", files_done, files_total)` (`catalog_dialog._FILES_STEP`). `_on_job_progress(job, percent, total=0, text="")`; once a count was shown (`_Job.checking`) a git line no longer touches the strip.
- Size measurement order: rows that are on disk are queued in list order with the selected row's folder first (`_request_size`, `first=True` from the Details page), one `run_in_background` task at a time (`_pump_sizes`); the result updates the row cell in place (`_update_size_cells`) and the Details page. `_forget_size(id)` runs on a finished Add, Reinstall, Update and Remove.
- `ops.RemovePlan(..., symbol_nicknames=(), footprint_nicknames=())`; `nicknames` stays the union of the names. `catalog_pages.leave_counts(s, f)`, `CollapsibleList(..., counted=False)`.
- `names.display_name(id, entry=None, *, url=None, curated=CURATED)` and `names.source_names(mf, *, curated=CURATED)`; registered in `tests/test_catalog_layering.py` (imports models, catalog.curated, catalog.manifest, catalog.urls; catalog.status and catalog.ops may import it).

## Task Commits

1. **Task 1 (tracer): the check's file count** - RED `dda6db6` (test), GREEN `abb1ed2` (feat). Tracer verified end-to-end (ops, validate and add-dialog modules pass) before expanding.
2. **Task 2: sizes on disk and Remove counts** - RED `93cf385` (test), GREEN `6e96971` (feat)
3. **Task 3: one name** - RED `3313a7b` (test), GREEN `528e773` (feat)

**Other:** `0d8f37b` (docs: UI-SPEC copy for the three changes). The plan metadata commit follows this file.

## Files Created/Modified

- `kicad_lib_manager/catalog/names.py` - the name rule (new)
- `kicad_lib_manager/catalog/validate.py` - footprint-file progress callback
- `kicad_lib_manager/catalog/ops.py` - `check_progress`, `RemovePlan` kinds, names through `display_name`, `_checked_source` named owner/repo
- `kicad_lib_manager/catalog/status.py` - row names through `names.display_name` (`_repo_name` removed)
- `kicad_lib_manager/widgets/catalog_dialog.py` - job strip count, size queue and cells, `_forget_size`
- `kicad_lib_manager/widgets/catalog_pages.py` - Remove page counts and Kind column
- tests: `test_catalog_names.py` (new), additions to `test_catalog_ops.py`, `test_catalog_dialog.py`, `test_catalog_dialog_add.py`, `test_catalog_dialog_update.py`, `test_catalog_layering.py`; expectation updates in `test_catalog_ops.py`, `test_catalog_ops_update.py`

## Decisions Made

See `key-decisions` above. The RED commits of this plan are format-based (a pytest TypeError, a missing-field TypeError, an import error, and assertion failures for the size tests); the plan frontmatter is `type: execute`, so the `tdd-red-evidence` classifier gate of `type: tdd` plans was not run and no RED evidence record was written. The RED failures were all for the planned reason (the new keyword, fields or module did not exist yet; the size cells still showed the listed size).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing tests encoded the old names and the old size cell**
- **Found during:** Task 2 and Task 3
- **Issue:** `test_cells_elide_with_tooltips` and `test_size_and_licence_cells` expected the listed size for an installed row and the tooltip equal to the text; `test_catalog_ops.py` and `test_catalog_ops_update.py` expected `a-b`, `Demo`, `Mine`, `Other` as the names of entries whose address is on GitHub.
- **Fix:** the expectations now follow the plan's rules (size on disk with its own tooltip; `owner/repo` for address-added entries, `Demo` stays their id and folder).
- **Files modified:** tests/test_catalog_dialog.py, tests/test_catalog_ops.py, tests/test_catalog_ops_update.py
- **Committed in:** `6e96971`, `528e773`

**2. [Rule 1 - Bug] The old size cache could lose a measurement for good**
- **Found during:** Task 2
- **Issue:** a reload cancelled the tracked size task but kept the folder in `_size_pending`, so that folder was never measured again; the plan also asks for one folder at a time.
- **Fix:** the new size queue is owned by its own task field (cancelled only when the window closes or the collection changes), results of a changed folder are dropped through a stale set, and the cache survives a reload.
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py
- **Committed in:** `6e96971`

**3. [Rule 2 - Missing critical] UI-SPEC copy**
- **Found during:** final review
- **Issue:** the binding UI-SPEC still showed the old Remove heading, the plain strip text and the listed size; the plan's `files_modified` did not list it.
- **Fix:** the three entries were updated.
- **Files modified:** .planning/phases/17-library-catalog/17-UI-SPEC.md
- **Committed in:** `0d8f37b`

---

**Total deviations:** 3 auto-fixed (2 bug, 1 missing critical)
**Impact on plan:** no scope change; the test and spec edits only follow the plan's own behaviour.

## Issues Encountered

- A shell heredoc with a `\x00` escape wrote a real NUL into `catalog_dialog.py`; it was replaced by the plain marker `check-files` before the first commit.
- `names` is a common local variable in `ops.py`, so the module is imported as `from .names import display_name`.

## Known Stubs

None.

## Threat Flags

None. The check count only carries two integers across the thread boundary (T-17-49: throttled, tested), and names come from the validated id and `urls.parse_github_url` parts shown in the existing plain-text labels (T-17-50).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 17-22 to 17-25 can build on `names.display_name` / `source_names`; 17-23 should use `source_names(mf)` for the main window's trees and log lines.
- The owner should look at the job strip on a real large download (D5 is a judgment item).

## Self-Check: PASSED

- Files exist: names.py, tests/test_catalog_names.py, this SUMMARY.
- Commits `dda6db6`, `abb1ed2`, `93cf385`, `6e96971`, `3313a7b`, `528e773`, `0d8f37b` are ancestors of HEAD.
- Plan modules, the four guard tests and the main-window catalog tests pass with `-n 0` (647 + 189 tests); the pre-publish scan of the changed files and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
