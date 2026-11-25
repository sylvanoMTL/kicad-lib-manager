---
phase: 15-choose-library-folder-and-new-collection
plan: 03
subsystem: importer commit step
tags: [git, commit-probe, commit-panel, new-collection]
requires: []
provides:
  - "CommitProbe.parent_mode ('gitlink' default, 'none')"
  - "_parent_mode(ctx, cplan) in commit_step"
  - "commit.parent_unavailable refusal for bump_parent without a parent repo"
  - "commit panel hides the parent option for parent_mode 'none'"
affects: [15-11 new collection first-part commit]
tech-stack:
  added: []
  patterns: ["probe decides the collection shape from read-only git calls; panel only presents it"]
key-files:
  created: []
  modified:
    - kicad_lib_manager/importer/commit_step.py
    - kicad_lib_manager/widgets/commit_panel.py
    - tests/test_commit_step.py
    - tests/test_commit_panel.py
key-decisions:
  - "parent_mode is 'gitlink' only when the library folder is the top of a work tree AND records Custom (committed gitlink or index entry); every other case is 'none'"
  - "No git-identity sentence added: the existing unavailable reason already words it"
requirements-completed: [ROOT-09]
duration: 40 min
completed: 2026-11-23
status: complete
commits: 2
plan_head_before: 14b857f9b99f67b25795f88084877b20a9b377ec
plan_head_after: 04568e7a3e6ab3154cfdb285acf20fba3333ed6c
actuals:
  tokens: 3500
  tasks: 2
  commits: 2
---

# Phase 15 Plan 03: Commit step for both collection shapes Summary

The commit probe now tells a parent-repo-plus-Custom-submodule collection ("gitlink") from a plain library folder whose `Custom/` is its own repo ("none"), and the commit panel hides the whole parent option for the second shape with no explanatory text.

## What changed

- `commit_step.py`: `CommitProbe.parent_mode` (default `gitlink`, so every existing construction stays valid). `_parent_mode` uses only `show_toplevel`, `committed_gitlink` and `tracked_paths`. `_preexisting` skips `_parent_state` for `none` and returns no parent folder, reason, branch or gitlink. `_precheck` refuses `bump_parent=True` for `none` with "Not committed: this library folder has no parent git repository. Untick the parent option to commit in Custom only." before any write.
- `commit_panel.py`: `apply_probe` hides `_parent_check`, `_parent_label` and the amber "Parent commit unavailable" line for `none`; the earlier line, preview heading and preview stay hidden through the existing unchecked-box rule. Gitlink behaviour is untouched and the panel does not latch between probes.
- Tests: 4 new slow git tests (`test_probe_gitlink_shape`, `test_untracked_nested_custom_is_none`, `test_first_commit_on_unborn_main`, `test_bump_refused_without_parent`), `test_probe_parent_states` updated (case a now expects `none`, cases b and c assert `gitlink`), and 4 new panel tests.

## Verification

- `pytest tests/test_commit_step.py --full` (whole module): 127 passed.
- `pytest tests/test_commit_panel.py tests/test_commit_gate_panel.py`: 73 passed.
- `pytest tests/test_commit_gate_panel.py tests/test_import_dialog.py`: 252 passed.
- Acceptance greps: `parent_mode` x6 in commit_step.py (>=4), `def _parent_mode` x1, refusal sentence x1, `parent_mode` x1 in commit_panel.py.

## Deviations from Plan

None - plan executed exactly as written. One process note: the panel change was implemented right after the commit_step change and before the panel tests were run, so the panel tests were not observed failing first (the commit_step tests were: 5 failed before the implementation).

## Known Stubs

None.

## Threat Flags

None. T-15-08 is mitigated as planned (`_parent_mode` requires top == library folder and a Custom entry; `_precheck` refuses a bump otherwise).

## Self-Check: PASSED

- kicad_lib_manager/importer/commit_step.py, kicad_lib_manager/widgets/commit_panel.py, tests/test_commit_step.py, tests/test_commit_panel.py: present and committed.
- Commits e8309bd (Task 1) and 04568e7 (Task 2) are on the branch.
