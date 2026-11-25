---
phase: 15-choose-library-folder-and-new-collection
plan: 06
subsystem: new-collection
tags: [collection, git-init, dialog, pyside6, ROOT-06]
requires: [15-01, 15-02]
provides:
  - "collection.create_collection / check_new_collection / validate_collection_name (Qt-free)"
  - "widgets/new_collection_dialog.NewCollectionDialog with created_folder()"
affects: [15-08, 15-09, 15-10, 15-11]
tech-stack:
  added: []
  patterns:
    - "refuse before writing, then create with O_EXCL and mkdir (never exist_ok), cleanup only this call's recorded paths in reverse"
    - "debounced off-thread check with a request counter; creation on a TaskWorker with the form disabled"
key-files:
  created:
    - kicad_lib_manager/widgets/new_collection_dialog.py
    - tests/test_new_collection_dialog.py
    - tests/test_collection_git.py
  modified:
    - kicad_lib_manager/collection.py
    - tests/test_collection.py
    - tests/collectionfixtures.py
key-decisions:
  - "Files are created with os.open(O_CREAT|O_EXCL) and folders with mkdir without exist_ok, so create_collection can never overwrite or fill something that was already there"
  - "A whitespace-only name counts as empty (row 4); a name with a trailing space is row 5"
  - "The first check of a dialog starts at once (0 ms); every later edit waits 300 ms"
  - "After a failed creation the failure rows stay and Create stays disabled until the next edit (which clears them and checks again), matching 'Choose another name or folder, then try again'"
  - "A worker still running after 5 s at close is parked in a module list so its QThread is never destroyed while running"
requirements-completed: [ROOT-06]
duration: 40 min
completed: 2026-11-23
status: complete
actuals:
  tokens: 45000
  tasks: 2
  commits: 2
plan_head_before: e0f4d80e86ae06535cc24a5eec4c53ad4e818f9e
plan_head_after: bcc7b628fc80516335b7a6026e46e948eed3a623
commits: 2
---

# Phase 15 Plan 06: New Collection creation and dialog Summary

A new user can create an empty library collection: `create_collection` builds the D4 skeleton in an empty or new folder and runs `git init --template= -b main` inside `Custom/` (nothing committed), and the window-modal New Collection dialog drives it off the GUI thread with every UI-SPEC row.

## What was built

- **Task 1** (commit `e368bea`): collection.py gained `GITIGNORE_TEXT`, `README_TEXT`, `_RESERVED_NAMES`, `validate_collection_name`, `program_files_folders`, `_inside` (whole path parts), `NewCollectionCheck` (`target`, `rows`, `existing_empty`, `blocked`), `check_new_collection` (UI-SPEC rows 1-11 in order, plain existing-empty line, length warning last), `create_collection`, and helpers `_remove_tree`, `_write_new`, `_cleanup`. Issue codes: `collection.refused`, `collection.git_missing`, `collection.git_too_old`, `collection.create_failed`, `collection.leftovers`. `collection` now imports `gitops` (plan 15-09 registers `{"models", "fsutil", "gitops"}` in tests/test_layering.py; the module stays Qt-free, verified with `python -I`). tests/collectionfixtures.py has `recording_git(answers)`; tests/test_collection.py has 64 new tests; tests/test_collection_git.py is the slow real-git test (main branch, no HEAD, five untracked skeleton files, `check_folder(target).state == "collection"`).
- **Task 2** (commit `bcc7b62`): `widgets/new_collection_dialog.py` and 19 offscreen tests. Parent folder (Documents, else home, or the empty folder's parent) plus Name (`KiCad_Libraries` or the empty folder's name), `Will create:` ElidedLabel with full-path tooltip, 8-row preview, footnote, issue strip, indeterminate progress bar, back button `Back to Choose` / `Back to Setup`, `Create Collection` (min width 112, not default, `Ctrl+Return`). 300 ms debounce, request counter drops stale results, `find_git` runs on every check (inside the worker), creation on a `TaskWorker`; while it runs the form and back button are disabled and `reject()`, Esc and the close box are ignored.

## Exact text written into a new collection

`Custom/.gitignore` (LF line ends, UTF-8):

```
# KiCad temporary and backup files
*.bak
*.bck
*-backups
*.kicad_prl
*~
_autosave-*
*.tmp
fp-info-cache
~*.lck
\#auto_saved_files#
```

`Custom/README.md` (LF line ends, UTF-8):

```
# KiCad library collection

This folder holds your own KiCad parts.

- `Symbols/` holds one `Atomic_<KiCad symbol library>.kicad_sym` file per category, such as `Atomic_Connector`.
- `Footprints/Atomic_Footprints.pretty/` holds every footprint.
- `3DModels/` holds the 3D models, one `<MPN>.<ext>` file per part, linked as `${CUSTOM_3DMODEL_DIR}/<file>`.

Every part in an `Atomic_` library follows the atomic rule:

- `MPN` and `Manufacturer` are set
- `Footprint` resolves to exactly one `Lib:FP`
- `Value` is the `MPN`
- `Datasheet` and `Description` are set
- its 3D model file exists

This folder is its own git repository on branch main. Nothing was committed when it was created: commit your first part from the import window.
```

The three `.gitkeep` files (Symbols, Footprints/Atomic_Footprints.pretty, 3DModels) are empty.

## Verification

- `tests/test_collection.py` 94 passed; `tests/test_collection_git.py --full` 1 passed; `tests/test_new_collection_dialog.py` 19 passed (twice, no `QThread: Destroyed` output); `tests/test_annotations_resolve.py`, `tests/test_layering.py`, `tests/test_importer_layering.py`, `tests/test_isolation.py` pass.
- Acceptance greps: 3 creation functions, `init_repository` referenced, `recording_git` defined once, `class NewCollectionDialog` 1, `"Cancel"` 0, `QMessageBox` 0, `Creating...` 1; collection.py loads no PySide6.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test design] Tests used `Issue.message`; the model field is `Issue.text`**
- **Found during:** Task 1 run
- **Fix:** tests read `.text`
- **Commit:** e368bea

**2. [Rule 1 - Test design] App-folder boundary test expected a single row for a non-empty app folder**
- **Found during:** Task 1 run
- **Fix:** the test asserts the app-folder row comes first (the folder is also non-empty, so row 10 follows)
- **Commit:** e368bea

**3. [Rule 1 - Test design] `dialog.result()` is 0 (Rejected) before any outcome**
- **Found during:** Task 2 run
- **Fix:** the test asserts the dialog is still visible and still creating
- **Commit:** bcc7b62

### Plan-shape notes

- Tests and implementation were each committed in one commit per task (RED was observed locally as an ImportError before the implementation was written; no separate `test(...)` commit).
- The per-plan commit ledger file was not written (shell restrictions in this worktree); `plan_head_before` is the dispatch base e0f4d80.
- The dialog wires `Ctrl+Return` through a `QShortcut`; the test emits its `activated` signal rather than synthesising a key press (a window-context shortcut needs an active window, which the offscreen platform does not give).

**Total deviations:** 3 auto-fixed (test design only). **Impact:** none on behavior.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat register (T-15-15 to T-15-19 are covered by tests: name rules, Program Files and app-folder refusals on whole path parts, non-empty and cleanup tests, the slow no-commit test, off-thread worker tests).

## Self-Check: PASSED

Files verified present: kicad_lib_manager/collection.py, kicad_lib_manager/widgets/new_collection_dialog.py, tests/test_collection.py, tests/collectionfixtures.py, tests/test_collection_git.py, tests/test_new_collection_dialog.py. Commits e368bea and bcc7b62 are ancestors of HEAD.
