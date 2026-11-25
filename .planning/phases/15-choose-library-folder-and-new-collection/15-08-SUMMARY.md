---
phase: 15-choose-library-folder-and-new-collection
plan: 08
subsystem: library-folder-dialogs
tags: [dialog, pyside6, first-run, choose-folder, ROOT-03, ROOT-05, ROOT-07]
requires: [15-01, 15-06]
provides:
  - "widgets/choose_folder_dialog.ChooseLibraryFolderDialog with chosen_folder() and created()"
  - "widgets/first_run_dialog.FirstRunDialog with choice(), and FirstRunChoice(path, source, created)"
affects: [15-09, 15-10, 15-11]
tech-stack:
  added: []
  patterns:
    - "debounced off-thread folder check with a request counter; workers joined in done()/closeEvent, a stuck one parked in a module list"
    - "injected check and dialog classes so offscreen tests need no real drive or dialog"
key-files:
  created:
    - kicad_lib_manager/widgets/choose_folder_dialog.py
    - kicad_lib_manager/widgets/first_run_dialog.py
    - tests/test_choose_folder_dialog.py
    - tests/test_first_run_dialog.py
  modified: []
key-decisions:
  - "A row with a muted hint (the collection row) is rich text with both parts html.escaped; every other row label is plain text"
  - "Row and description labels use an Ignored horizontal size policy so a long unbroken path wraps or clips and never widens the window"
  - "A blank Folder field is never checked (no worker, strip hidden, Use This Folder disabled)"
  - "First-run row 1 button is disabled while its check runs, plus a flag, so a second click starts nothing"
  - "Each module keeps its own _PARKED list instead of importing the private one from new_collection_dialog"
requirements-completed: [ROOT-03, ROOT-05, ROOT-07]
duration: 35 min
completed: 2026-11-23
status: complete
actuals:
  tokens: 28000
  tasks: 2
  commits: 2
plan_head_before: e13d7fd984c66b2fc52383bb33f941815330d668
commits: 2
plan_head_after: 46294c3cea4a4ed16b50ae4e556fbb1cab8a6be3
---

# Phase 15 Plan 08: Choose Library Folder and first-run window Summary

The two remaining windows of the phase exist as standalone widgets: Choose Library Folder with the live off-thread folder check and the new-collection hand-off, and the first-run window with three plain choices or Quit. Both return their result through accessors and write nothing.

## What was built

- **Task 1** (commit `ea839e5`): `widgets/choose_folder_dialog.py` and 15 offscreen tests. Window-modal, minimum width 560, heading and body verbatim, Folder field (accessible name `Library folder`, placeholder `Choose a folder`), Browse... (nearest existing parent, else home; a cancelled pick changes nothing; a pick checks at once), check strip of per-row labels (ERROR, AMBER, hinted collection row muted), `Checking the folder...` with an indeterminate bar, `Create a New Collection Here...` only for `state == "empty"`, back button `Keep Current Folder` / `Back to Setup`, `Use This Folder` (min width 112, enabled only for a `collection` state with no check pending), Ctrl+Return only when enabled, Return in the field re-checks.
- **Task 2** (commit `46294c3`): `widgets/first_run_dialog.py` and 14 offscreen tests. Application-modal, no parent, fixed width 560, three framed rows with plain buttons, optional amber notice strip, Quit in a `QDialogButtonBox` (RejectRole); Quit, Esc and the close box reject with `choice()` None. Row 1 shows the KiCad folder (escaped, Consolas) or the disabled-state sentence, checks off the GUI thread, and on pass/empty/fail chooses, opens New Collection, or shows `✖ {reason}` in the row.

## Constructor signatures for plan 15-10

```python
ChooseLibraryFolderDialog(current: Path | None, *, origin: str = "main",   # "main" | "setup"
                          check=check_folder, new_collection=NewCollectionDialog, parent=None)
    .chosen_folder() -> Path | None      # set on Use This Folder or a created collection
    .created() -> bool                   # True when the folder was created from this dialog
    # open with dialog.open() (window-modal); accepted => read chosen_folder()/created()

FirstRunDialog(kicad_folder: str | None, notice: str | None = None, *,
               check=check_folder, choose=ChooseLibraryFolderDialog,
               new_collection=NewCollectionDialog, parent=None)
    .choice() -> FirstRunChoice | None   # None after Quit, Esc or the close box
    # application-modal: run with exec(); then act on choice()

@dataclass(frozen=True) FirstRunChoice(path: Path, source: Source, created: bool = False)
    # Source.KICAD for row 1; Source.CHOSEN for rows 2 and 3 (a new collection has created=True)
```

The caller must re-check a returned folder off the GUI thread before switching (T-15-27), save the setting only after the switch, and print `No library folder chosen; exiting.` to stderr when `choice()` is None. The first-run window opened with `choose(None, origin="setup", parent=self)` and `new_collection(origin="setup", parent=self)` (row 1 empty folder adds `parent_folder` and `name`).

## Verification

- `tests/test_choose_folder_dialog.py` 15 passed; `tests/test_first_run_dialog.py` 14 passed; with `tests/test_annotations_resolve.py`, `tests/test_custom_literals.py` and `tests/test_layering.py` 97 passed together, no `QThread: Destroyed` output.
- Acceptance greps: `class ChooseLibraryFolderDialog` 1, `Keep Current Folder` present, `QMessageBox` 0 in both modules, FirstRunDialog/FirstRunChoice 2, `ApplicationModal` 1, `PRIMARY_BUTTON_QSS` 0 in first_run_dialog.py.
- Neither module holds a string constant equal to `Custom` or starting with `Custom/` (the existing custom-literal test passes).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test design] Tests compared a Windows path as typed with the normalised `Path` string**
- **Found during:** Task 2 run
- **Fix:** compare `Path(call)` with `Path(KICAD)`
- **Commit:** 46294c3

**2. [Rule 1 - Test design] `qtbot.waitUntil` rejects a list return value; the tab-order walk needed the whole focus chain**
- **Found during:** Task 1 run
- **Fix:** wrap in `bool(...)`, walk up to 20 chain steps
- **Commit:** ea839e5

### Plan-shape notes

- Tests and implementation were each committed together per task (RED observed locally as a missing module/failures before fixes; no separate `test(...)` commit), as in plan 15-06.
- The plan commit ledger file lives at `<git-dir>/gsd-plan-head-before-15-08` (base `e13d7fd`).
- The 150- and 250-character backstop truths are covered by offscreen geometry checks (`test_long_kicad_path_fits`, `test_long_path_does_not_widen`); a real-screen look is left to the verifier.
- Windows dark mode and high contrast remain unhandled, as listed in the plan's Assumptions.

**Total deviations:** 2 auto-fixed (test design only). **Impact:** none on behavior.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register (T-15-25 off-thread checks with `Checking the folder...`; T-15-26 plain-text labels, the rich-text paths html.escaped and tested; T-15-27 the dialogs only return a checked choice and write nothing).

## Self-Check: PASSED

Files verified present: kicad_lib_manager/widgets/choose_folder_dialog.py, kicad_lib_manager/widgets/first_run_dialog.py, tests/test_choose_folder_dialog.py, tests/test_first_run_dialog.py. Commits ea839e5 and 46294c3 are ancestors of HEAD.
