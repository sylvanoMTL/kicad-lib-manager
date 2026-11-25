---
phase: 15-choose-library-folder-and-new-collection
plan: 14
subsystem: ui
tags: [pyside6, dialog, geometry, height-for-width, gap-closure]
requires:
  - phase: 15-06
    provides: NewCollectionDialog
  - phase: 15-08
    provides: ChooseLibraryFolderDialog
provides:
  - fit_height_to_content(dialog) in new_collection_dialog.py, used by both dialogs
  - shared geometry checks (overlapping_children, clipped_wrapped_labels, missing_height)
  - in-process geometry tests and a QT_SCALE_FACTOR 1.75 child-process run
affects: [phase-15 UAT gap 3]
tech-stack:
  added: []
  patterns:
    - "A dialog with an explicit minimum width sets its minimum height from layout.totalHeightForWidth on show, resize and redraw"
key-files:
  created:
    - tests/geometryfixtures.py
    - tests/test_dialog_geometry.py
    - tests/dialoggeometrychild.py
  modified:
    - kicad_lib_manager/widgets/new_collection_dialog.py
    - kicad_lib_manager/widgets/choose_folder_dialog.py
key-decisions:
  - "The minimum height is recomputed after every strip redraw, on show and on a width change, with a re-entry guard stored on the dialog"
  - "New strip labels are shown at once with label.show(): a child created on a shown dialog stays hidden until a queued call and a hidden widget is not laid out, so the first refit saw no rows"
requirements-completed: [ROOT-03, ROOT-06, ROOT-07]
status: complete
commits: 4
plan_head_before: 07f30d7f502005e2c40aa28ce4a1b2ea499734be
plan_head_after: 7a583b9
duration: 40 min
completed: 2026-11-23
actuals:
  tokens: 22000
  tasks: 2
  commits: 4
---

# Phase 15 Plan 14: Dialog geometry fit Summary

Both dialogs now take their minimum height from the layout's height for the current width, so the New Collection footnote clears the preview and every wrapped Choose strip row shows all its lines, at the default scale and at QT_SCALE_FACTOR 1.75.

## Tasks

| Task | Commits | What |
|------|---------|------|
| 1 (tracer) | 8279ddc (RED), c738c0c (GREEN) | geometry helpers, in-process tests, 1.75 child, `fit_height_to_content`, New Collection wiring |
| 2 | 971b43f (RED), 7a583b9 (GREEN) | Choose cases and tests, Choose wiring, immediate `show()` of strip labels |

## RED numbers at HEAD (07f30d7)

New Collection (same at dpr 1.0 and 1.75, only the heights differ):

| Case | preview bottom | footnote top | dialog height | missing height | wrapped row (height / needed) |
|------|----------------|--------------|---------------|----------------|-------------------------------|
| nc-setup | 310 (304 at 1.75) | 255 (243 at 1.75) | 403 (385) | 80 (98) | 42 / 54 (36 / 54) |
| nc-choose | 310 (309) | 255 (253) | 403 (401) | 110 (112) | 19 / 26 and 19 / 54 |
| nc-issues | 310 (304) | 255 (243) | 403 (385) | 80 (98) | 42 / 54 (36 / 54) |

The footnote top is above the preview bottom: the overlap of UAT gap 3 reproduces offscreen. Choose (both scales): every strip row 6 px tall against 12, 12, 28 and 54 for its width (missing height 82); the failure row 36 against 54 (missing 18).

## Green numbers after the fix

| Case | dpr 1.0 and 1.75 | preview bottom | footnote top | rows (height / needed) | missing height |
|------|------------------|----------------|--------------|------------------------|----------------|
| nc-setup | no overlap, nothing clipped | 314 | 323 | 54 / 54 | 0 |
| nc-choose | same | 314 | 323 | 26 / 26, 54 / 54 | 0 |
| nc-issues | same | 314 | 323 | 54 / 54 | 0 |
| choose-main, choose-setup | same | n/a | n/a | 12, 12, 28, 54 equal their needs | -24 |
| choose-failure | same | n/a | n/a | 54 / 54 | -24 |

A negative missing height means the dialog is taller than needed. `resize(560, 10)` cannot shrink New Collection below its content (tested).

## Deviations from Plan

**1. [Rule 3 - Blocking] Strip labels must be shown at once**
- **Found during:** Task 2
- **Issue:** after wiring `fit_height_to_content` into the Choose `_draw()` the rows still had 6 px: a label created on a shown dialog carries the hidden flag until a queued `_q_showIfNotHidden`, so the layout skipped the new rows when the refit ran inside `_draw()` and the minimum height was computed without them.
- **Fix:** `label.show()` right after `addWidget` for the strip rows and the "Checking the folder..." label in Choose, and for the issue rows in New Collection.
- **Files modified:** kicad_lib_manager/widgets/choose_folder_dialog.py, kicad_lib_manager/widgets/new_collection_dialog.py
- **Commit:** 7a583b9

**2. Test layout:** the dialog case builders (`new_collection_case`, `choose_case`, fake checks) live in tests/geometryfixtures.py so the in-process tests and the child build exactly the same dialogs; the geometry checks themselves stay Qt-only, and the package is imported inside the builders. Each task was committed RED then GREEN (four commits for two tasks).

**Total deviations:** 1 auto-fixed (Rule 3), 1 structural note. **Impact:** none on scope; heights only, the 560 px minimum width and the Ignored horizontal policy are untouched (`test_long_path_does_not_widen` passes).

## Verification

- tests/test_dialog_geometry.py: 9 passed (three New Collection cases, the resize test, two Choose cases, the failure row, the grow test, the 1.75 child).
- tests/test_choose_folder_dialog.py, test_first_run_dialog.py, test_new_collection_dialog.py, test_annotations_resolve.py, test_layering.py, test_main_window_root.py: all pass (76 and 90 tests).
- Acceptance greps: `def fit_height_to_content` 1, `fit_height_to_content(self)` 3 in new_collection_dialog.py, `fit_height_to_content` 4 in choose_folder_dialog.py, `setMinimumWidth(560)` 1, `Policy.Ignored` 1, `QT_SCALE_FACTOR` in the test, child case names 2 lines.
- Child process isolates APPDATA, LOCALAPPDATA, USERPROFILE and HOME to the test's tmp folder; offscreen platform.

## Known Stubs

None.

## Threat Flags

None. T-15-38 and T-15-39 mitigated as planned.

## Self-Check: PASSED

- tests/geometryfixtures.py, tests/test_dialog_geometry.py, tests/dialoggeometrychild.py exist.
- Commits 8279ddc, c738c0c, 971b43f, 7a583b9 are ancestors of HEAD.
