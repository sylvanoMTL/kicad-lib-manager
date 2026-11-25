---
phase: 15-choose-library-folder-and-new-collection
plan: 11
subsystem: docs-and-end-to-end-proof
tags: [library-folder, new-collection, real-git, user-guide, claude-md, docs-tests]
status: complete
requires: ["15-03", "15-05", "15-06", "15-08", "15-09", "15-10"]
provides:
  - "slow end-to-end tests: a new collection takes the Ultra Librarian sample through import and root commit with real git"
  - "the two collection shapes (none, gitlink) both commit; only gitlink bumps a parent commit"
  - "User Guide page HELP_PAGES['library_folder'] first under On Launch"
  - "CLAUDE.md library-folder behaviour, override and D-26 wording"
affects: []
tech-stack:
  added: []
  patterns:
    - "end-to-end flow reuses the real core (build_plan, apply_plan, build_commit_plan, probe_commit, run_commit) under tmp_path with the tracked vendor zip as read-only input"
key-files:
  created: []
  modified:
    - tests/test_collection_git.py
    - kicad_lib_manager/widgets/help_dialog.py
    - CLAUDE.md
    - tests/test_help_dialog.py
    - tests/test_docs_atomic.py
key-decisions:
  - "The guide page is inserted as the first child of On Launch, so the menu numbers of KiCad Detection and Repository Scan moved from 3.1/3.2 to 3.2/3.3; every help key is unchanged (the saved last section is keyed by name)"
requirements-completed: [ROOT-03, ROOT-05, ROOT-06, ROOT-09]
duration: 35 min
completed: 2026-11-23
commits: 2
plan_head_before: 04059e4913a4f882d447cef4f48f87da4129cf0a
plan_head_after: 1e1b1316e7fcb6eab4a192bd3d4d7e1203b8e00a
actuals:
  tokens: 9000
  tasks: 2
  commits: 2
---

# Phase 15 Plan 11: Docs and end-to-end proof Summary

A brand-new collection takes the Ultra Librarian sample through import and a root commit on main with real git, both collection shapes commit, and the User Guide and CLAUDE.md now describe the library folder.

## What was built

### Task 1: end to end with real git (commit a845683)

`tests/test_collection_git.py` gained three slow, `requires_git` tests (4 pass in total with the 15-06 test):

- `test_new_collection_first_part_commits`: `create_collection` under tmp_path, then the UL sample (read through the `ul_package` fixture) installs into `Atomic_Battery_Management` with `build_plan` and `apply_plan`. The probe reports state `ready`, branch `main`, `parent_mode` `none`, `parent_dir` None, gate not refused, `other_changes == 5`. `run_commit` makes a single root commit (no parent, no parent commit). `git show --name-only` lists exactly the three installed files, `git status` still lists the five skeleton files as untracked, and `scan_all(target)` lists `Atomic_Battery_Management` and `Atomic_Footprints` with source `Custom`.
- `test_every_collection_shape_commits[none|gitlink]`: the none shape uses a created collection, the gitlink shape uses `make_superproject` with `import_files`. `probe.parent_mode` matches the shape; `run_commit` with `bump_parent = (shape == "gitlink")` commits, and a parent commit (HEAD moved) exists only for gitlink.

Git identity is set with four `monkeypatch.setenv` calls. Everything lives under tmp_path and is removed with `remove_tree`.

**Files the first commit contained** (the flow's own commit in the new collection, asserted by the test):
- `3DModels/CSD85301Q2.stp`
- `Footprints/Atomic_Footprints.pretty/DQK0006B.kicad_mod`
- `Symbols/Atomic_Battery_Management.kicad_sym`

The five skeleton files (`.gitignore`, `3DModels/.gitkeep`, `Footprints/Atomic_Footprints.pretty/.gitkeep`, `README.md`, `Symbols/.gitkeep`) stay untracked.

### Task 2: User Guide and CLAUDE.md (commit 1e1b131)

Guide page `library_folder` ("Library Folder", first item of On Launch). Section headings (the h3 headings that appear in the menu):
1. Which folder is used at start
2. Changing the library folder
3. The setup window
4. New Collection
5. KiCad path variables after a switch
6. For development and testing

It covers the resolve order and tags, the deleted-folder skip, the bad override stopping the start, Choose Library Folder... / Change Folder... (check rows, 100-character warning), Use KiCad's Folder, Recent Library Folders, Open Library Folder in Explorer, the busy refusals, fresh scan per switch, the setup window and Quit, New Collection (Custom is its own git repository on branch main, `.gitkeep`, nothing committed, skeleton files stay uncommitted), the amber tag and the path-variable question (No is the default), and `--library-root` / `KICAD_LIBMGR_ROOT`. The Importing Parts Commit list has the new line "In a new collection, where Custom has no parent repository, no parent option is shown."

CLAUDE.md: KICAD_LIB_GITHUB now points to the library folder; the worktree sentence names `--library-root PATH` / `KICAD_LIBMGR_ROOT`; Running the GUI has the override; GUI Behavior has the bullets Library folder, Choose Library Folder..., First run, New collection; the Wrong checkout and Pin bullets use library-folder wording (still "another folder"). Menu Shortcuts is unchanged.

Tests: `test_help_library_folder_page`, `test_help_outline_has_library_folder`, `test_claude_md_describes_the_library_folder`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Existing test shifted by the plan's own change] Outline numbers**
- **Found during:** Task 2
- **Issue:** `test_help_outline_numbers_follow_the_menu_order` pinned `kicad_detection` at 3.1 and `repo_scan` at 3.2 and the total section-anchor count at 25. The new first child of On Launch shifts them (the plan's own requirement: "first item of the On Launch group").
- **Fix:** `MENU_NUMBERS` now has `library_folder` 3.1, `kicad_detection` 3.2, `repo_scan` 3.3; the anchor count is 25 plus the new page's sections. No help key was renamed or removed.
- **Files modified:** tests/test_help_dialog.py
- **Commit:** 1e1b131

No findings about production code: the import-and-commit flow worked in a new collection exactly as RESEARCH Codebase Inventory 8 recorded, so no production file was touched.

## Verification

- `tests/test_collection_git.py --full -n 0`: 4 passed.
- `tests/test_help_dialog.py tests/test_docs_atomic.py -n 0`: 77 passed.
- Acceptance greps: `HELP_PAGES["library_folder"]` 1, `KICAD_LIBMGR_ROOT` in CLAUDE.md 3, `Choose Library Folder` in CLAUDE.md present, `test_claude_md_describes_the_library_folder` 1.
- The quick and full suites were not run here (the orchestrator runs them after the merge).

## Human check (owner, end of phase)

Manual UAT from the main checkout (15-VALIDATION.md "Manual-Only Verifications"); not performed by the executor:

1. Start with an empty settings folder and no `KICAD_LIB_GITHUB`: the setup window shows three rows and Quit closes the app.
2. Change Folder... to a scratch collection, decline then accept the `VAR: old -> new` question, then Use KiCad's Folder.
3. New Collection in Documents, import a part, Commit, and confirm no parent option is shown.
4. A 200-character path in the row at 900 px window width, and the dialogs at 175% display scaling.
5. Remember a folder on a network drive, disconnect it, start the app: the next choice is used with a log line within about 5 s.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface; the tests write only under tmp_path.

## Self-Check: PASSED

- tests/test_collection_git.py, kicad_lib_manager/widgets/help_dialog.py, CLAUDE.md, tests/test_help_dialog.py, tests/test_docs_atomic.py: FOUND
- Commits a845683 and 1e1b131: FOUND in HEAD history
