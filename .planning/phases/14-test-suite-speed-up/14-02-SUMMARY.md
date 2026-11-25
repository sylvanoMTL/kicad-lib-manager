---
phase: 14-test-suite-speed-up
plan: 02
subsystem: testing
tags: [pytest, markers, slow, gitfixtures, tripwire]
requires:
  - phase: 14-test-suite-speed-up
    provides: "--full, -m 'not slow' in addopts, wurth/kicad_cli auto-slow hook, shared git template (14-01)"
provides:
  - "runtime tripwire: a test that builds a real git repository without @pytest.mark.slow fails before any git work, naming its node id"
  - "176 @pytest.mark.slow marks on test functions in the twelve git modules and test_atomic_uat"
affects: [14-03 measure, 14-04 marker audit, 14-06 docs]
actuals:
  tokens: 1400
  tasks: 3
  commits: 3
plan_head_before: fd42324cb3d3f5d5936ca49d6a7c5a9beb33870d
plan_head_after: c0d258617b9887ea89eec58f4227a76e0f646751
tech-stack:
  added: []
  patterns:
    - "gitfixtures._require_slow reads the running item's closest slow marker; conftest pytest_runtest_setup (tryfirst) feeds the item"
    - "slow goes on test functions only, never on a module pytestmark"
key-files:
  created: []
  modified:
    - tests/gitfixtures.py
    - tests/conftest.py
    - tests/test_commit_step.py
    - tests/test_commit_deletions.py
    - tests/test_atomic_uat.py
    - tests/test_commit_gate.py
    - tests/test_commit_gate_panel.py
    - tests/test_scan_changes.py
    - tests/test_migration_precheck.py
    - tests/test_migration_commit.py
    - tests/test_migration_full.py
    - tests/test_import_dialog.py
    - tests/test_gitops.py
    - tests/test_scan_cache.py
    - tests/test_rescan_library.py
key-decisions:
  - "Tripwire fails closed: inside a test with no item set it raises 'gitfixtures cannot see the running test'; outside a test it does nothing"
  - "Mixed git-gated modules marked by AST reachability of the builders, so the 7 non-builder tests stay in the quick run"
requirements-completed: [TEST-06, TEST-04]
coverage:
  - id: D1
    description: "A real-git test without the slow marker fails at once naming its node id"
    requirement: TEST-06
    verification:
      - kind: integration
        ref: "pytest tests/test_scan_changes.py -x on the then-unmarked module printed 'builds a real git repository: mark it @pytest.mark.slow'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every builder-reaching test in the twelve git modules and the two own-git-init tests of test_atomic_uat are slow; quick sweep of all 13 modules passes (389 passed, no tripwire message)"
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "pytest <12 git modules> tests/test_atomic_uat.py -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 7 non-builder tests of the three git-gated modules stay in the quick run"
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "pytest --collect-only -m 'not slow' tests/test_commit_gate.py tests/test_commit_gate_panel.py tests/test_scan_changes.py -> 7/58 tests collected (51 deselected)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Marked tests still pass under --full -m slow"
    requirement: TEST-06
    verification:
      - kind: integration
        ref: "--full -m slow over test_atomic_uat (1 passed, 1 skipped), test_migration_commit+test_commit_gate_panel (4 passed), gitops/scan_cache/rescan_library/migration_full (10 passed), test_import_dialog (3 passed)"
        status: pass
    human_judgment: false
duration: 20min
completed: 2026-11-22
status: complete
---

# Phase 14 Plan 02: Slow marks and git tripwire Summary

**Every real-git test is now `@pytest.mark.slow` (176 function-level marks across 13 modules), and `gitfixtures.make_superproject`/`make_worktree` fail at once, naming the test, when called from an unmarked one.**

## Performance

- **Duration:** about 20 min
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments
- `tests/gitfixtures.py`: `_current_item`, `set_current_item`, `_require_slow`; `_require_slow()` is the first statement of `make_superproject` and `make_worktree`, so the failure costs no git work. The message is `<nodeid> builds a real git repository: mark it @pytest.mark.slow`; inside a test with no item set it raises `gitfixtures cannot see the running test: import gitfixtures at the top of the test module`.
- `tests/conftest.py`: `pytest_runtest_setup` (tryfirst) feeds the item to `gitfixtures` when that module is loaded.
- Marks added per module (decorators counted in the committed content): test_commit_step 97, test_commit_gate 26, test_scan_changes 23, test_migration_precheck 8, test_gitops 4, test_commit_deletions 3, test_import_dialog 3, test_rescan_library 3, test_commit_gate_panel 2, test_migration_commit 2, test_scan_cache 2, test_atomic_uat 2, test_migration_full 1 (total 176; test_isolation's 1 is from 14-01).
- The 7 non-builder tests of the three `pytestmark = requires_git` modules stay in the quick run (`pytestmark` lines unchanged): test_commit_gate `test_gate_texts`, `test_move_introduced_lists_a_part_once`, `test_check_linked_symbols_has_nine_parameters`, `test_gate_texts_for_clean_and_problem_only_results`; test_scan_changes `test_a_custom_that_is_not_a_git_checkout_skips_the_highlight_with_one_line`, `test_a_tree_whose_only_library_is_outside_custom_gives_no_skip_line`, `test_changes_calls_only_the_read_only_git_functions`.
- `test_real_vendor_samples.py` untouched (its `@requires_git` test creates no repository); 14-04 allow-lists it by id. `--strict-markers` still in addopts.

## Task Commits

1. **Task 1: tripwire; commit_step, commit_deletions, atomic_uat** - `2090f02` (feat)
2. **Task 2: git-gated modules, precheck, migration_commit** - `e60cde4` (feat)
3. **Task 3: mixed modules and sweep** - `c0d2586` (feat)

## Decisions Made
- Marks were applied by a one-off script (outside the repo): `@requires_git` lines get a slow line above them; for the three git-gated modules an AST walk marked each test that reaches a builder directly or through `_repos` / `_footprint_repos`. Counts matched the plan exactly (26, 2, 23). Working-tree CRLF line endings of the files were preserved.

## Deviations from Plan

None - plan executed exactly as written. The sweep over the twelve git modules plus test_atomic_uat in the quick run found no test that still reached a builder unmarked (389 passed, no tripwire message), so no extra marks were needed.

## Issues Encountered
- Files in the working tree are CRLF (index is LF via autocrlf), so a literal `grep -c "^@pytest.mark.slow$"` on the working file prints 0; the counts above were verified against `\r?$` and the committed (LF) content. No file content issue.

## Self-Check: PASSED
- Quick sweep: 389 passed. `--full -m slow` runs pass in every touched module. Collect-only `-m not slow` over the three git-gated modules: `7/58 tests collected (51 deselected)`. Tripwire fires on an unmarked module (test_scan_changes before Task 2). `--collect-only -m slow` over the suite exits 0 (227 slow tests of 3621). No STATE.md/ROADMAP.md changes.
