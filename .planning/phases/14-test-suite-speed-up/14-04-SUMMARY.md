---
phase: 14-test-suite-speed-up
plan: 04
subsystem: testing
tags: [pytest, markers, subprocess-watch, xdist, git]

requires:
  - phase: 14-test-suite-speed-up
    provides: "slow auto-mapping hook and --full (14-01), builder tripwire and git marks (14-02), measure.py slow-coverage (14-03), per-test user isolation (14-05)"
provides:
  - "tests/test_markers.py: nine quick meta-tests pinning the slow-marker rules"
  - "collect_repo in tests/runfixtures.py: a collection-only child run over the repo suite"
  - "subprocess watch in tests/conftest.py: an unmarked test that starts git init, git clone, git submodule add or git submodule update --init fails at teardown, naming itself and the command"
  - "every test among BASELINE.md's 50 slowest is collected as slow"
affects: [14-06]

actuals:
  tokens: 4000
  tasks: 2
  commits: 3
plan_head_before: e60a439dcd30d0bae00ee567e5985494fcc92461
plan_head_after: 2dc0a97692e35a5913bddf01d5f52dae79fdd2ff

tech-stack:
  added: []
  patterns:
    - "Popen subclass that only records the argv before the process starts, armed per test in pytest_runtest_setup and restored in a finally in the teardown wrapper"
    - "Meta-tests that write a child test module and assert on its pytest output (run_pytest / collect_repo)"

key-files:
  created: [tests/test_markers.py]
  modified: [tests/conftest.py, tests/runfixtures.py, tests/test_scanner_issues.py, tests/test_scanner_skip_dirs.py]

key-decisions:
  - "The git watch only detects: it marks and selects nothing; the slow rules (hooks, gitfixtures tripwire, helper modules) are unchanged by Task 2"
  - "The two baseline tests that were not slow got @pytest.mark.slow on their own functions"

patterns-established:
  - "A slow-marked test pays nothing for the watch: _repo_watch is None for it"

requirements-completed: [TEST-06, TEST-04]

coverage:
  - id: D1
    description: "Nine quick meta-tests pin the slow rules: wurth/kicad_cli/kicad_cli_path are slow, every requires_git test is slow (one exact read-only allow-list entry), the slow marker is registered and used, --full widens the selection, an unregistered marker fails, the builder tripwire fires, and the subprocess watch fires"
    requirement: TEST-06
    verification:
      - kind: unit
        ref: "tests/test_markers.py (9 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unmarked test that creates a real git repository (own git init, string or list argv, clone, submodule) fails naming itself; git status and slow tests are left alone; the modules that start git today and the two Popen-subclassing tests still pass"
    requirement: TEST-04
    verification:
      - kind: unit
        ref: "tests/test_markers.py#test_unmarked_own_git_repo_fails_loudly"
        status: pass
      - kind: unit
        ref: "quick run of test_atomic_uat, test_commit_step, test_migration_precheck, test_gitops, test_real_vendor_samples, test_scan_changes, test_commit_gate: 70 passed, 9 skipped"
        status: pass
      - kind: unit
        ref: "tests/test_import_dialog.py::test_import_flow_never_runs_git and tests/test_main_window_import.py::test_post_install_steps_never_run_git: 2 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every test among BASELINE.md's 50 slowest is collected as slow (measure.py slow-coverage: not slow 0)"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "python .planning/phases/14-test-suite-speed-up/measure.py slow-coverage"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-11-22
status: complete
---

# Phase 14 Plan 04: Marker audit and baseline slow set Summary

**Nine quick meta-tests pin the slow-marker rules, a Popen-recording watch in tests/conftest.py fails any unmarked test that starts git init/clone/submodule, and the last two untagged baseline tests are now slow.**

## Performance

- **Duration:** about 35 min
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- `tests/test_markers.py`: nine meta-tests (collection audit for wurth/kicad_cli, slow marker registered and used, AST audit of every `@requires_git` test with the exact one-entry read-only allow-list, kicad_cli_path users are slow, `--full`, unregistered marker still fails, builder tripwire message, subprocess watch message). `python -m pytest tests/test_markers.py` gives 9 passed in about 6 s.
- `collect_repo(*args, timeout=120)` in `tests/runfixtures.py`.
- Subprocess watch in `tests/conftest.py`: `_REAL_POPEN`, `_repo_watch`, `_git_repo_command` (handles list argv with `-c`/`-C` options, quoted string argv, `git.exe`, `submodule add`, `submodule update --init`; never raises), `_RepoWatchPopen`. Armed in `pytest_runtest_setup` for items without the slow mark; checked and restored (in a `finally`) in the `pytest_runtest_teardown` wrapper, which fails the item with `<nodeid> creates a real git repository (<command>): mark it @pytest.mark.slow`.
- Baseline closure: `measure.py slow-coverage` reports `baseline tests: 50`, covered 47 plus 2 newly marked = 49 collected and slow, `not slow` 0, 1 missing.
- Quick run once as the sweep (bare pytest, parallel): 3376 passed, 29 skipped, 83.8 s, no watch message and no tripwire message anywhere.

## Task Commits

1. **Task 1 RED: marker audit meta-tests and collect_repo** - `29aff3d` (test); `test_unmarked_own_git_repo_fails_loudly` failed on the planned assertion (the child ran 4 passed, expected a non-zero exit with two teardown errors), the other eight passed
2. **Task 1 GREEN: subprocess watch** - `3d8d606` (feat); 9 passed
3. **Task 2: mark the two remaining baseline tests slow** - `2dc0a97` (test)

No REFACTOR commit (no change needed).

## Files Created/Modified

- `tests/test_markers.py` - the nine meta-tests
- `tests/runfixtures.py` - `collect_repo`
- `tests/conftest.py` - subprocess watch, hook changes
- `tests/test_scanner_skip_dirs.py` - `test_real_repo_has_no_tests_source` marked slow (12.88 s in BASELINE.md); added `import pytest`
- `tests/test_scanner_issues.py` - `test_live_custom_model_findings_are_zero` marked slow (12.42 s in BASELINE.md)

## Slow-coverage record (Task 2)

- Baseline tests: 50. Marked in this task: the two above (modules `tests/test_scanner_skip_dirs.py` and `tests/test_scanner_issues.py`). Neither is above 100 s, so no timeout mark was added.
- Missing (not collected in this worktree because the WurthElektronik submodule is not checked out; a warning only, not an error): `tests/test_roundtrip_corpus.py::test_roundtrip_wurth_file[wurth/KiCad-Library/symbols/Connector_Wurth_WR-TBL.kicad_sym]`.
- No test was named by the subprocess watch in the sweep (expected: none).
- `tests/conftest.py`, `tests/gitfixtures.py`, `tests/customfixtures.py` and `tests/runfixtures.py` were not touched by Task 2 (only Task 1 changed conftest and runfixtures).

## TDD Gate Compliance

RED commit `29aff3d` precedes GREEN commit `3d8d606`. RED evidence: the target test `test_unmarked_own_git_repo_fails_loudly` executed and failed on its first planned assertion (`assert done.returncode != 0`, child output `4 passed`), because no watch existed; the other eight tests passed (8 passed, 1 failed). The gsd-tools classifier (`check tdd-red-evidence`) could not be run: this worktree has no `gsd_run`. Semantic assessment: the failure is the planned one (target ran, failed on the behavior assertion, no import or fixture fault).

## Decisions Made

None beyond the plan. A small inline choice: `_git_repo_command` filters option tokens after the git subcommand so `git submodule --quiet add` and `git submodule update --recursive --init` are also recognised.

## Deviations from Plan

None - plan executed exactly as written. (The plan's `-m ""` for the watch child run was dropped because `run_pytest` already removes the default `-m`; no behavior change.)

## Issues Encountered

None. The Bash tool of this worktree rejects some compound commands that mention git paths, so commands were issued one at a time.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- tests/test_markers.py, tests/runfixtures.py (`collect_repo`), tests/conftest.py (`_git_repo_command`, `_RepoWatchPopen`) present; acceptance greps: collect_repo 1, `^def test_` 9, `_git_repo_command` 1, `_RepoWatchPopen` 1, "creates a real git repository" 1 in conftest, `_READ_ONLY_GIT_TESTS` 6, `^@requires_git` 0, `^@pytest.mark.slow` 0 in test_markers.py.
- Commits `29aff3d`, `3d8d606`, `2dc0a97` are ancestors of HEAD.
- `measure.py slow-coverage`: not slow 0; verify commands 1-3 of Task 1 pass (9 passed; 70 passed 9 skipped; 2 passed).
