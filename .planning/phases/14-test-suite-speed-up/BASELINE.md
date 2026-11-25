# Phase 14 — Serial Baseline

Recorded by the orchestrator before any Phase 14 change.

- **Commit:** 20a557a53360fd4d219008abce9b8e46616e64ea (base of Phase 14 execution; no test or config change yet)
- **Command:** `env/Scripts/python.exe -m pytest --durations=50 -q -p no:cacheprovider` (serial, bare pytest, no xdist/timeout plugins installed)
- **Started:** 2026-11-22 16:35 (epoch 1795365302), **ended:** epoch 1795366868
- **Wall time (pytest):** 1563.92 s (26 min 03 s)
- **Exit code:** 1
- **Counts:** 11662 passed, 1 failed, 5 skipped, 4 warnings
- **Machine:** 16 logical cores, Windows 11, Python 3.14.4, pytest 9.1.1, pytest-qt 4.5.0

## Known failure (pre-existing, not caused by Phase 14)

`tests/test_docs_atomic.py::test_project_md_marks_migration_delivered` fails because the PROJECT.md line it looks for ("Own symbol libraries named `Atomic_...`" as an Active checkbox) was rewritten into the Validated list at the v2.0 close (commit 6b38a74). It reads `.planning/PROJECT.md`, not test-speed code; it fails identically in serial and parallel runs, so count comparisons are unaffected. Fixed right after this baseline in 5471a0a (the test now looks for the Validated `- ✓` line), so post-change runs expect 0 failed; compare post-change parallel runs with the post-change serial run, not with these counts.

## Final summary line (verbatim)

```
1 failed, 11662 passed, 5 skipped, 4 warnings in 1563.92s (0:26:03)
```

## Slowest 50 durations (verbatim)

```
============================ slowest 50 durations =============================
46.52s call     tests/test_roundtrip_corpus.py::test_wurth_corpus_parse_budget
15.72s call     tests/test_migration_full.py::test_whole_v1_custom_migrates_to_zero_violations
12.88s call     tests/test_scanner_skip_dirs.py::test_real_repo_has_no_tests_source
12.42s call     tests/test_scanner_issues.py::test_live_custom_model_findings_are_zero
12.00s call     tests/test_scanner_issues.py::test_wurth_model_paths_stay_quiet
10.89s call     tests/test_commit_deletions.py::test_migration_shaped_commit_records_deletions_and_moves
10.40s call     tests/test_import_dialog.py::test_gate_refusal_and_recovery_end_to_end
9.80s call     tests/test_migration_commit.py::test_migration_commit_end_to_end
9.41s call     tests/test_commit_step.py::test_recheck_rebaselines_then_commits
8.72s call     tests/test_commit_step.py::test_recheck_adds_untracked_linked_model
8.33s call     tests/test_commit_step.py::test_recheck_leaves_unrelated_untracked_files_out
8.07s call     tests/test_commit_step.py::test_probe_gated_and_click_refused_for_failing_part
7.97s call     tests/test_commit_step.py::test_probe_old_failure_stays_ready_and_commits
7.75s call     tests/test_roundtrip_corpus.py::test_roundtrip_wurth_file[wurth/KiCad-Library/symbols/Connector_Wurth_WR-TBL.kicad_sym]
7.75s call     tests/test_commit_gate_panel.py::test_unreadable_linked_library_refuses_probe_panel_and_click
7.53s call     tests/test_commit_step.py::test_commit_slow_post_commit_hook_reports_commit
7.38s call     tests/test_commit_step.py::test_recheck_leaves_tracked_unchanged_footprint_out
7.31s call     tests/test_commit_step.py::test_recheck_writes_nothing
7.27s call     tests/test_commit_step.py::test_recheck_adds_modified_tracked_footprint
7.22s call     tests/test_commit_step.py::test_recheck_with_a_failing_file_list_adds_a_warning
7.13s call     tests/test_commit_step.py::test_probe_parent_states
7.10s call     tests/test_commit_step.py::test_probe_and_commit_in_linked_worktree
7.10s call     tests/test_commit_step.py::test_dirty_before_flags_preexisting_edit[True]
7.07s call     tests/test_commit_step.py::test_recheck_adds_nothing_when_no_part_links_a_model
6.96s call     tests/test_commit_step.py::test_change_after_recheck_refused_again
6.92s call     tests/test_commit_step.py::test_recheck_gate_runs_on_new_content
6.88s call     tests/test_commit_step.py::test_changed_diff_text_file
6.68s call     tests/test_commit_gate_panel.py::test_unchecked_linked_part_shown_in_panel_without_refusing
5.93s call     tests/test_commit_gate.py::test_symbol_changes_matches_scan_marks
5.90s call     tests/test_import_dialog.py::test_tracer_commit_end_to_end
5.81s call     tests/test_commit_gate.py::test_gate_old_failure_does_not_block
5.78s call     tests/test_commit_gate.py::test_gate_blocks_a_failing_new_part
5.77s call     tests/test_commit_step.py::test_recheck_without_git_returns_the_plan_and_an_unavailable_probe
5.72s call     tests/test_migration_commit.py::test_refused_tag_writes_nothing
5.70s call     tests/test_customfixtures.py::test_every_synthetic_library_loads_in_kicad_cli
5.66s call     tests/test_commit_gate.py::test_gate_blocks_a_failing_pre_import_edit
5.65s call     tests/test_commit_gate.py::test_gate_unreadable_outside_library_ignored_without_linked_files
5.64s call     tests/test_commit_gate.py::test_gate_findings_never_block
5.63s call     tests/test_commit_step.py::test_probe_no_main_refused
5.62s call     tests/test_commit_step.py::test_ahead_counts_and_not_pushed_lines
5.57s call     tests/test_scan_cache.py::test_custom_git_part_follows_commits_not_pack_refs
5.49s call     tests/test_scan_changes.py::test_the_scan_leaves_the_git_state_of_custom_alone
5.49s call     tests/test_commit_gate.py::test_gate_new_footprint_with_model_does_not_block
5.48s call     tests/test_import_dialog.py::test_git_state_changes_only_after_click
5.47s call     tests/test_commit_gate.py::test_gate_committed_model_never_blocks_alone
5.46s call     tests/test_commit_gate.py::test_gate_judges_derived_child_of_changed_parent
5.44s call     tests/test_commit_gate.py::test_scan_result_for_feeds_check_dialog
5.41s call     tests/test_commit_step.py::test_changed_diff_added_file_shows_head_against_now
5.40s call     tests/test_commit_gate.py::test_gate_unresolved_link_elsewhere_adds_nothing
5.40s call     tests/test_commit_step.py::test_changed_diff_unknown_file_is_an_error
```

## Short test summary (verbatim)

```
=========================== short test summary info ===========================
SKIPPED [1] tests\test_atomic_uat.py:283: set KICAD_ATOMIC_UAT_DIR to build the atomic-check UAT scratch repo
SKIPPED [1] tests\test_edits.py:106: Custom submodule not checked out (git submodule update --init Custom)
SKIPPED [1] tests\test_install_e2e.py:617: set KICAD_IMPORT_UAT_DIR to build the manual UAT scratch install
SKIPPED [1] tests\test_model_source.py:201: symlinks not permitted here: [WinError 1314] A required privilege is not held by the client: '<home>\\AppData\\Local\\Temp\\pytest-of-<user>\\pytest-27572\\test_bare_model_symlink_refuse0\\real.stp' -> '<home>\\AppData\\Local\\Temp\\pytest-of-<user>\\pytest-27572\\test_bare_model_symlink_refuse0\\linked.stp'
SKIPPED [1] tests\test_package_folder.py:105: symlinks not permitted here: [WinError 1314] A required privilege is not held by the client: '<home>\\AppData\\Local\\Temp\\pytest-of-<user>\\pytest-27572\\test_folder_symlink_skipped0\\outside.step' -> '<home>\\AppData\\Local\\Temp\\pytest-of-<user>\\pytest-27572\\test_folder_symlink_skipped0\\pick\\linked.step'
FAILED tests/test_docs_atomic.py::test_project_md_marks_migration_delivered
1 failed, 11662 passed, 5 skipped, 4 warnings in 1563.92s (0:26:03)
```
