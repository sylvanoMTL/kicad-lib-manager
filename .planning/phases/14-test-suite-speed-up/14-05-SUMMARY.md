---
phase: 14-test-suite-speed-up
plan: 05
subsystem: testing
tags: [pytest, isolation, qsettings, kicad-cli, xdist, user-state-guard]
requires:
  - phase: 14-test-suite-speed-up
    provides: "runfixtures.run_pytest/write_tree, conftest sessionfinish, --full and slow marker (14-01, 14-02)"
provides:
  - "every test runs in its own empty user home: APPDATA, LOCALAPPDATA, USERPROFILE, HOME, XDG_*, the QSettings ini and KICAD_CONFIG_HOME point into a folder under the pytest base temp, removed when the test ends"
  - "KICAD_LIB_GITHUB, CUSTOM_3DMODEL_DIR, WE_3DMODEL_DIR unset inside every test"
  - "the 10 local_kicad table tests are opt-in behind KICAD_TEST_REAL_CONFIG=1; an opted-out collection never reads the KiCad config folder"
  - "run-level guard: a change to the owner's real app state fails the run (also under xdist), a change to KiCad's own config only warns"
  - "proof that the live Custom/ guard fails a run under 2 xdist workers"
affects: [14-04, 14-06, phase-15]
actuals:
  tokens: 11500
  tasks: 2
  commits: 5
plan_head_before: b81afafda5355dd6fa474521de72c9e2b377eb2d
plan_head_after: c3e7b9f46c868e4dc0ad7641e98acb0e6f7328e4
tech-stack:
  added: []
  patterns:
    - "autouse function fixture redirects env + QSettings.setPath and removes its folder with a rmtree captured at import (a test may patch shutil.rmtree)"
    - "controller-only hash guard in pytest_sessionstart / pytest_sessionfinish; paths in messages, never contents"
    - "child-run meta-tests with a fake owner profile passed through the child's environment"
key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/customfixtures.py
    - tests/test_isolation.py
    - tests/test_customfixtures.py
    - tests/test_roundtrip_corpus.py
key-decisions:
  - "Per-test user folders are named user<N> from a process counter (mktemp numbered=False), not mktemp's numbering, because the folder is removed at teardown and mktemp would reuse the freed number for the next test"
  - "The fixture removes its folder with a shutil.rmtree captured at conftest import: test_prune_failure_warns patches shutil.rmtree to refuse and the teardown ran under that patch"
  - "Guard messages go through the terminal reporter before the final summary line; the exit status is forced to TESTS_FAILED only from OK or NO_TESTS_COLLECTED"
requirements-completed: [TEST-07]
coverage:
  - id: D1
    description: "Environment, QSettings, scan cache, backup folder, Path.home and find_kicad_config_dir are isolated per test; KiCad variables cleared; KICAD_CONFIG_HOME redirected even when the shell set it"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_isolation.py#test_user_state_is_redirected, test_kicad_variables_are_cleared_even_when_set"
        status: pass
    human_judgment: false
  - id: D2
    description: "A settings value one test writes is never seen by a later test, serially and under 2 workers; per-test and session folders are removed"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_isolation.py#test_settings_do_not_leak_between_tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "kicad-cli started with no env= writes kicad.json and kicad_common.json into the per-test KICAD_CONFIG_HOME; the kicad_cli tests keep their passed and skipped counts"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_isolation.py#test_kicad_cli_uses_the_test_config_folder; -m kicad_cli before 34 passed, 2 skipped / after 34 passed, 2 skipped"
        status: pass
    human_judgment: false
  - id: D4
    description: "local_kicad real-table tests are opt-in (KICAD_TEST_REAL_CONFIG=1); no real-config read at collection otherwise; with the switch they still pass"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_roundtrip_corpus.py#test_local_kicad_tables_are_opt_in, test_local_kicad_tables_with_opt_in; KICAD_TEST_REAL_CONFIG=1 -k local_kicad 12 passed"
        status: pass
    human_judgment: false
  - id: D5
    description: "Run-level guard: app-state change fails the run naming paths (under xdist), KiCad config change only warns, absent or empty state is quiet, no contents printed"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_isolation.py#test_user_state_guard_* (5 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The live Custom/ guard still fails a run under 2 workers, naming Symbols/a.kicad_sym"
    requirement: TEST-07
    verification:
      - kind: integration
        ref: "tests/test_customfixtures.py#test_guard_failure_fails_the_run_under_xdist"
        status: pass
    human_judgment: false
duration: 55min
completed: 2026-11-22
status: complete
---

# Phase 14 Plan 05: User-state isolation and run-level guard Summary

**Every test now runs in its own empty user home (environment, QSettings ini and KICAD_CONFIG_HOME redirected, KiCad path variables cleared, folder removed afterwards), the real-KiCad-table tests are opt-in, and the controller hashes the owner's real app state so a run that changes it fails (KiCad's own config only warns).**

## Performance

- **Duration:** about 55 min
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 (no new files, no change under kicad_lib_manager/)

## Accomplishments

- `tests/conftest.py`: `_REAL`, `_USER_DIRS`, `_CLEARED_VARS`, session `_qsettings_sandbox`, function autouse `_isolated_user_state`, `pytest_sessionstart` (controller digest) and the guard in `pytest_sessionfinish`. The 19 modules with their own `_isolated_settings` are untouched and keep working.
- `tests/customfixtures.py`: Qt-free `user_state_roots`, `app_state_digest`, `kicad_config_digest`, reusing `custom_changes`.
- `tests/test_roundtrip_corpus.py`: `_REAL_CONFIG_SWITCH`, `local/opt-in` skip, two meta-tests.
- `tests/test_isolation.py`: 3 isolation tests, 1 kicad_cli test, 5 guard tests. `tests/test_customfixtures.py`: `_run_guarded(workers=)` and the xdist case (it also now drops the parent's PYTEST_* variables from the child environment).

## Evidence

- kicad-cli summary lines: before the conftest edit `34 passed, 2 skipped in 28.04s`; after `34 passed, 2 skipped in 15.02s` (new `test_kicad_cli_uses_the_test_config_folder` deselected, run on its own with `--full`: 1 passed).
- Files kicad-cli 10.0.7 created in an empty KICAD_CONFIG_HOME: `10.0/kicad.json` and `10.0/kicad_common.json` (nothing else).
- Tests that needed their own monkeypatch value under the isolation: none. The only finding was the fixture teardown under `test_prune_failure_warns` (see deviations).
- Sweeps: 28 user-state modules in the quick run 995 passed, 3 skipped; git modules (commit_step, gitops, scan_cache, rescan_library, commit_deletions) with `--full` 240 passed; test_isolation + settings_import + main_window with `--full` 101 passed; bare quick run `3368 passed, 30 skipped, 4 warnings` (exit 0, 79.6 s), no leftover `user*` folder in the base temp, no pytest process left running.
- `KICAD_TEST_REAL_CONFIG=1 -k local_kicad`: 12 passed (10 real tables plus the 2 meta-tests), guard silent.

## Task Commits

1. **Task 1 RED** - `26b1767` (test): isolation, kicad_cli and opt-in tests; 4 failed on the planned assertions
2. **Task 1 GREEN** - `086c2a1` (feat): fixtures and the opt-in switch
3. **Task 2 RED** - `a37bb37` (test): guard tests (4 failed; the xdist Custom case and the quiet case already passed, as the mechanism is unchanged)
4. **Task 2 GREEN** - `0e20c8b` (feat): digest helpers and controller guard
5. **Fix** - `c3e7b9f` (fix): real rmtree captured at import

## Decisions Made

- User folders named from a process counter instead of mktemp's numbering (a removed number would be reused by the next test, and Qt keeps a per-file settings cache).
- A test may patch `shutil.rmtree`; the fixture therefore uses the function captured at import.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Teardown error under a test that patches shutil.rmtree**
- **Found during:** Task 2 sweep (first bare quick run: `ERROR at teardown of test_prune_failure_warns`, PermissionError "in use")
- **Issue:** the test monkeypatches `applier.shutil.rmtree` (the shared module) to refuse; the monkeypatch is torn down after `_isolated_user_state`, so the fixture's `shutil.rmtree(home, ignore_errors=True)` hit the patch.
- **Fix:** `_rmtree = shutil.rmtree` taken at conftest import and used by both fixtures; the test itself is unchanged.
- **Files modified:** tests/conftest.py
- **Verification:** tests/test_install_apply.py 66 passed; second bare quick run green.
- **Committed in:** `c3e7b9f`

**2. [Rule 1 - Bug] mktemp numbering would reuse a removed folder name**
- **Found during:** Task 1 (design check before GREEN)
- **Fix:** `mktemp(f"user{next(counter)}", numbered=False)`; the name still matches the plan's `user[0-9]*` glob.
- **Committed in:** `086c2a1`

**3. [Process incident] The Task 1 RED run wrote one probe key into the owner's real settings.ini**
- **Found during:** Task 1 RED. Before the fixture existed, the leak meta-test's child (which inherits the parent's unredirected environment) wrote `phase14_probe=written` to `%APPDATA%/KiCadExtLibManager/settings.ini`.
- **Fix:** removed exactly that line, restored the file's CRLF line endings (size 1123 bytes, the original minus the probe line); nothing else in the file or the folder was touched. From the GREEN commit on, the child inherits the redirected environment and the key is never written to the real file; the real file was checked after every later run (probe count 0) and the run-level guard stayed silent.

**Total deviations:** 2 auto-fixed (2 bugs) plus 1 process incident, no scope change.

## Issues Encountered

- The shell guard refuses commands that name the worktree path next to git-like words, so long runs went through small scripts in the session scratchpad (not part of the repo).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model.

## Next Phase Readiness

Ready for 14-04 and 14-06. `tests/runfixtures.py` is untouched. Phase 15 can rely on the per-test isolation; note the opt-in `KICAD_TEST_REAL_CONFIG=1` for the real-table tests.

## Self-Check: PASSED

- Files exist: tests/conftest.py, tests/customfixtures.py, tests/test_isolation.py, tests/test_customfixtures.py, tests/test_roundtrip_corpus.py.
- Commits `26b1767`, `086c2a1`, `a37bb37`, `0e20c8b`, `c3e7b9f` are on the branch; `commits: 5` measured from the ledger.
- Acceptance greps and the `_CLEARED_VARS` AST check pass; the three plan-level verification runs pass; no change under kicad_lib_manager/; no pytest process left running.
