---
phase: 15-choose-library-folder-and-new-collection
plan: 05
subsystem: settings, kicad-setup, user-guide
tags: [qsettings, library-folder, d-26, kicad-config]
requires: []
provides:
  - "settings helpers load_library_root, save_library_root, clear_library_root, load_library_recent, add_library_recent"
  - "kicad_setup.configured_library_folder(config_base=...)"
  - "CheckoutMismatch.library_folder (renamed from app_folder)"
  - "D-26 warning and refusal in library-folder wording"
affects: [15-01, 15-07, 15-10]
tech-stack:
  added: []
  patterns: ["QSettings quirk guard (_text_values) for bare str / [] / non-text values"]
key-files:
  created:
    - tests/test_settings_library.py
  modified:
    - kicad_lib_manager/settings.py
    - kicad_lib_manager/kicad_setup.py
    - kicad_lib_manager/widgets/help_dialog.py
    - tests/test_checkout_check.py
    - tests/test_help_dialog.py
decisions:
  - "load_library_root returns the stored text as a Path without an existence check; check_folder at use decides (T-15-13)"
  - "library/recent is deduplicated with normcase(normpath) and keeps the newest spelling; display filtering of deleted folders is left to the menu"
status: complete
metrics:
  duration: "~15 min"
  completed: 2026-11-23
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 14b857f9b99f67b25795f88084877b20a9b377ec
plan_head_after: a714fd9ee0e07f7e24aeae54cfe5954ba13da4af
---

# Phase 15 Plan 05: Library folder settings and D-26 wording Summary

Remembered library folder and recent list persisted through tested settings helpers, KiCad's KICAD_LIB_GITHUB readable as a resolve candidate, and every D-26 message and guide sentence now speaks of the library folder and File > Use KiCad's Folder.

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | library/root and library/recent settings helpers | 60da5c4 | kicad_lib_manager/settings.py, tests/test_settings_library.py |
| 2 | KiCad's folder read, library-folder D-26 wording, guide sentences | a714fd9 | kicad_lib_manager/kicad_setup.py, kicad_lib_manager/widgets/help_dialog.py, tests/test_checkout_check.py, tests/test_help_dialog.py |

## Verification

- `tests/test_settings_library.py tests/test_settings_import.py`: 16 passed
- `tests/test_checkout_check.py tests/test_help_dialog.py tests/test_kicad_setup.py tests/test_checkout_warning.py tests/test_migration_dialog_run.py`: 132 passed (the last three unchanged, they compare against function output)
- Acceptance greps: library/root 3+, library/recent 2+, 5 helper defs, configured_library_folder 1, "this app is working on" 2, "push them from here" 0, "app_folder" 0, "then pull" 0.

## Deviations from Plan

**1. [Process] TDD RED commit not separated**
- Tests and implementation for each task were written before the first test run, so each task has one `feat` commit instead of a `test` then `feat` pair; no RED run was recorded.
- Impact: none on behaviour; all behaviours in the plan's `<behavior>` lists are covered by tests.

**2. [Rule 2 - scope-adjacent] Added tests**
- Added `test_refusal_text`, `test_configured_library_folder_newest_version_wins`, a parametrised odd-value test and `test_help_wrong_checkout_no_longer_says_push_and_pull` beyond the minimum listed.

Total deviations: 1 process note, 1 small test addition. Impact: none.

## Known Stubs

None.

## Threat Flags

None. T-15-13 and T-15-14 mitigated: helpers return untrusted text only, odd types read as None.

## Notes for later plans

- The guide now states the path-variable change is offered for another folder and refused only for a git worktree; the matching behaviour in `library_scanner.sync_kicad_path_vars` (still refuses another folder) belongs to a later plan in this phase.
- The commit count above (2) is measured from the ledger before this SUMMARY commit.

## Self-Check: PASSED

- FOUND: tests/test_settings_library.py, kicad_lib_manager/settings.py, kicad_lib_manager/kicad_setup.py
- FOUND commits: 60da5c4, a714fd9
