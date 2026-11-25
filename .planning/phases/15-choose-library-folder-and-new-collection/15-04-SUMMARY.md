---
phase: 15-choose-library-folder-and-new-collection
plan: 04
subsystem: scanner
tags: [scanner, scan-cache, kicad-config, path-variables, git]
requires: []
provides:
  - "_walk_matches: .git pruned at any depth (library_scanner)"
  - "scan_cache._walk skips .git at any depth"
  - "_desired_path_vars, would_change_path_vars (read-only predicate)"
  - "sync_kicad_path_vars offers the change for any library folder (worktree refusal kept)"
affects: [15-07, 15-09]
tech-stack:
  added: []
  patterns: ["os.walk with in-place dirnames pruning replaces rglob + post-filter"]
key-files:
  created: []
  modified:
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/scan_cache.py
    - tests/test_scanner_skip_dirs.py
    - tests/test_scan_cache.py
    - tests/test_kicad_config.py
key-decisions:
  - "Other-folder refusal removed from _path_var_refusal: KICAD_LIB_GITHUB naming another folder is now offered through the existing confirm (owner decision 2026-11-23); Pin Atomic Libraries and migration Run refusals untouched"
  - "No scan-cache FORMAT bump: no .git file ever matched the suffix filter; the code-signature change alone forces one full scan"
requirements-completed: [ROOT-10, ROOT-06]
status: complete
duration: 25 min
completed: 2026-11-23
commits: 4
plan_head_before: 14b857f9b99f67b25795f88084877b20a9b377ec
plan_head_after: c30ae026b48b3d86af23c24c57bb52155a4487ff
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
---

# Phase 15 Plan 04: Scanner .git pruning and path-variable offer Summary

Both walkers now ignore `.git` at any depth, and the KiCad path-variable change is offered (never written without Yes) for a library folder KiCad does not point at yet, with a read-only `would_change_path_vars` predicate for plan 15-07.

## What was done

**Task 1 (RED c8ee4f0, GREEN fd305e8).** `_walk_matches(root, pattern, *, dirs=False)` in `library_scanner.py` replaces `_in_skip_dir` + `rglob`: it uses `os.walk` (no symlink following), drops top-level `SKIP_DIRS` and a `.git` folder at every depth in place, and matches names with `fnmatch` (same platform case rule as rglob), returning a sorted list. `_collect_files` and `find_footprint_libs` use it; `_in_skip_dir` was deleted (nothing imported it). `scan_cache._walk` skips `.git` at every depth for both `skip_top` values so the fingerprint and the scan agree.

**Task 2 (RED 0f9a662, GREEN c30ae02).** `_path_var_refusal` keeps only the worktree branch, reworded to "Not changing KiCad path variables: the library folder {path} is a git worktree. KICAD_LIB_GITHUB stays {value}. Choose the library checkout itself as the library folder to update them." (code `config.worktree_refused`). `_desired_path_vars(repo_root)` extracted; `would_change_path_vars(repo_root, *, config_base=None)` reads the newest `kicad_common.json` through `_read_config` + `_plan_changes` and never writes, logs, asks or calls `running`. `kicad_setup.py` untouched.

## Verification

- `tests/test_scanner_skip_dirs.py tests/test_scan_cache.py tests/test_rescan_library.py tests/test_atomic_scan.py`: 101 passed.
- `tests/test_kicad_config.py tests/test_kicad_setup.py`: 87 passed.
- `tests/test_checkout_warning.py tests/test_main_window.py`: 89 passed.
- Acceptance greps: `config.other_checkout_refused` 0 in library_scanner.py, `def would_change_path_vars` 1, `is a git worktree` 1, `config.worktree_refused` 1, `os.walk` and `name == ".git"` present.

No window test changed because the refusal was relaxed (their path-variable trees have no KICAD_LIB_GITHUB). The old `test_other_checkout_refuses_without_asking_or_writing` in `tests/test_kicad_config.py` was replaced by `test_other_folder_is_offered_and_written_only_on_yes` (No leaves file and backups byte-identical; Yes writes exactly the two variables, other keys kept, backup made).

## Deviations from Plan

None - plan executed exactly as written.

## Deferred / follow-up notes

- The User Guide text in `kicad_lib_manager/widgets/help_dialog.py` (around line 246) still says the app refuses path-variable changes from "a checkout other than the one KiCad names"; it is now out of date for Generate Tables' path-variable step. Docs were not in this plan's file list; a later phase 15 docs plan should update it.
- `_walk_matches` matches files only for file patterns (rglob also yielded folders named like `*.kicad_sym`; none exist in practice).

## Known Stubs

None.

## Threat Flags

None. T-15-10 (confirm default No, backup, atomic replace, worktree refusal) is covered by `test_other_folder_is_offered_and_written_only_on_yes`; T-15-11/12 (.git crawl or planted libraries) by `test_nested_git_folders_are_never_scanned` and `test_fingerprint_ignores_nested_git`.

## Self-Check: PASSED

Files modified exist; commits c8ee4f0, fd305e8, 0f9a662, c30ae02 are ancestors of HEAD; no STATE.md or ROADMAP.md changes.
