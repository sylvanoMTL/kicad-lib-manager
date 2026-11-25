---
phase: 14-test-suite-speed-up
plan: 06
subsystem: testing
tags: [pytest, docs, xdist, measurement, worker-count]
requires:
  - phase: 14-test-suite-speed-up
    provides: "--full and slow marker, tripwire and subprocess watch, timeout hooks, user-state isolation and run-level guards, measure.py and the matrix runs (14-01 to 14-05)"
provides:
  - "tests/README.md, README.md and CLAUDE.md name the quick run (bare pytest, also the GSD gate) and the full run (--full), with --full -n 0 as the serial reference and -n 0 for debugging"
  - "tests/README.md explains the slow marker and its two tripwire messages, the 300 s timeout and how a timeout reads under workers, per-test isolation, the run-level guards, the local_kicad opt-in, shared git templates and the shell-safe -m fallback"
  - "pyproject addopts holds the measured -n 8 --dist worksteal"
  - "the speed-up todo moved from todos/pending to todos/done"
affects: [phase-15]
actuals:
  tokens: 3500
  tasks: 2
  commits: 2
plan_head_before: 499f246737a6da6c66974636ac142523aa9d77de
plan_head_after: 3e5e113a12c63479eda66645be8ab384fe462892
tech-stack:
  added: []
  patterns:
    - "worker setting taken from `measure.py choose` over recorded matrix runs and confirmed by `choose --check-pyproject`"
key-files:
  created: []
  modified:
    - tests/README.md
    - README.md
    - CLAUDE.md
    - .planning/codebase/TESTING.md
    - pyproject.toml
    - .planning/phases/14-test-suite-speed-up/measurements/results.jsonl
    - .planning/todos/done/2026-11-13-speed-up-full-test-suite.md
key-decisions:
  - "addopts uses -n 8 --dist worksteal: the fastest matrix setting that exited 0 with the serial reference's counts (332.51 s)"
  - "The expected-skips count in tests/README.md is now six (it said four; BASELINE.md already listed five, and the local_kicad opt-in adds the sixth)"
requirements-completed: [TEST-04, TEST-05, TEST-08]
status: complete
---

# Phase 14 Plan 06: Test run docs and measured worker setting Summary

**tests/README.md, README.md and CLAUDE.md now document the quick and full runs, markers, timeouts, isolation and guards in the words the code prints, and pyproject addopts carries the measured `-n 8 --dist worksteal`.**

Requirements TEST-04, TEST-05 and TEST-08 are judged by the orchestrator's phase-end runs (MEASURE.md step 4); the Verdicts section below is for it to fill in.

## Performance

- **Duration:** about 10 min
- **Started:** 2026-11-22T21:21Z
- **Completed:** 2026-11-22T21:32Z
- **Tasks:** 2
- **Files modified:** 7 (the todo is a rename)

## Accomplishments

- tests/README.md: "How to run" rewritten as a command list (install `requirements-dev.txt` in the venv you run from, quick, `--full`, `--full -n 0`, one slow module, `-m kicad_cli`, `-m wurth`, `-n 0` for debugging, `-m "slow or not slow"`); new sections Slow tests, Timeouts, Your own settings stay out, Shared git templates and Regression gate; the `local_kicad` skip row now quotes the `local/opt-in` reason; the Wurth timing section adds the 8016-file corpus, the budget of about 401 s, the 900 s timeout and the 46.52 s baseline parse.
- README.md `## Running the tests` and CLAUDE.md `## Running the Tests` plus a test-dependencies bullet under Python Environment; `.planning/codebase/TESTING.md` carries the out-of-date pointer line.
- Every message quoted in the docs was checked against `tests/conftest.py` and `tests/test_roundtrip_corpus.py`.
- Task 2: `measure.py choose` printed `-n 8 --dist worksteal`; pyproject changed from `-n 6` to `-n 8`; `choose --check-pyproject` exits 0; `test_isolation.py -k timeout_config` passes (1 passed), so `--strict-markers` and `-m 'not slow'` survived the edit.

## Matrix rows (from MEASUREMENTS.md, orchestrator's runs)

| label | kind | -n | --dist | exit | wall s | wall / baseline | passed | skipped | failed |
|---|---|---|---|---|---|---|---|---|---|
| serial-20261122T201734 | serial | 0 | - | 0 | 1439.26 | 0.92 | 11680 | 6 | 0 |
| matrix-n4-worksteal-20261122T204134 | matrix | 4 | worksteal | 0 | 476.24 | 0.30 | 11680 | 6 | 0 |
| matrix-n6-worksteal-20261122T204931 | matrix | 6 | worksteal | 0 | 374.72 | 0.24 | 11680 | 6 | 0 |
| matrix-n8-worksteal-20261122T205545 | matrix | 8 | worksteal | 0 | 332.51 | 0.21 | 11680 | 6 | 0 |
| matrix-n4-loadfile-20261122T210118 | matrix | 4 | loadfile | 0 | 505.33 | 0.32 | 11680 | 6 | 0 |
| matrix-n6-loadfile-20261122T210943 | matrix | 6 | loadfile | 0 | 545.18 | 0.35 | 11680 | 6 | 0 |
| matrix-n8-loadfile-20261122T211848 | matrix | 8 | loadfile | 0 | 530.25 | 0.34 | 11680 | 6 | 0 |

Chosen pair: `-n 8 --dist worksteal`.
`measure.py choose` second line, verbatim: `half-of-baseline: met (332.51 s <= 781.96 s)`.
`choose --check-pyproject` output: `pyproject addopts hold the chosen setting`, exit 0.

## Task Commits

1. Task 1: docs and todo move - `5e7acf8` (docs)
2. Task 2: measured `-n 8 --dist worksteal` in addopts - `3e5e113` (chore)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale expected-skips count in tests/README.md**
- **Found during:** Task 1
- **Issue:** "Expected skips" said the workstation has exactly four skips; BASELINE.md already listed five (the `test_edits.py` skip after the live Phase 13 migration), and the local_kicad opt-in from 14-05 makes six, the count the serial reference recorded.
- **Fix:** the sentence now lists all six.
- **Files modified:** tests/README.md
- **Commit:** 5e7acf8

**Total deviations:** 1 auto-fixed (1 documentation bug). **Impact:** none on scope.

## Issues Encountered

None. `measure.py choose` also appended its record to `measurements/results.jsonl` each time it ran (three `choose` records, identical values); MEASUREMENTS.md was already current, so it did not change.

## Known Stubs

None.

## Threat Flags

None.

## Verdicts

TEST-04: met (runs after the first, gate command: 68.08 s, 69.22 s; each under 600 s with exit 0)
TEST-05: met (slowest 338.57 s <= 781.96 s)
TEST-08: met (10 consecutive runs equal to the serial reference)
Chosen setting: -n 8 --dist worksteal (matrix estimate against half the baseline: met; 332.51 s vs 781.96 s)

Contingency (MEASURE.md step 6): not needed; half-of-baseline was met by the matrix and by both ten-runs.

Phase-end history (orchestrator):
- First phase-end pass at 82f0d2b: ten-run 10/10 equal (slowest 344.95 s), but quick run 3 of 3 hit a native xdist worker crash in `tests/test_migration_dialog_files.py::test_pad_mismatch_is_amber_not_blocking` (TEST-04 not met). Recorded in 24d1352.
- Root cause (debug session `.planning/debug/resolved/xdist-worker-native-crash.md`): a pytest-qt-closed dialog survived into the next test (deleteLater ran there), its draft/rebuild timer started a TaskWorker, and the deferred delete destroyed the running QThread (Qt fatal "QThread: Destroyed while thread is still running"). Fixed in the test harness only, dd5f5fb (`pytest_runtest_teardown` joins threads started during pytest-qt teardown and runs each registered widget's DeferredDelete in its own test; regression test `test_isolation.py::test_registered_widget_ends_in_its_own_test`). 30/30 clean quick runs after the fix.
- Second phase-end pass at dd5f5fb (the verdicts above): new serial reference 11681 passed / 6 skipped (+1 regression test), quick 3/3 exit 0, ten-run 10/10 equal.
- App follow-up (not changed, harness-only phase): `MigrationDialog` does not stop `_draft_timer`/`_rebuild_timer` on close; captured as a pending todo.

## Before / after

- BASELINE.md serial wall time: 1563.92 s
- Latest serial reference (this checkout): 1507.81 s [note: after-crash-fix]
- Quick gate command, runs after the first: 68.08 s, 69.22 s
- Latest ten-run walls (10 runs): min 320.43 s (0.20 of baseline), median 330.35 s (0.21 of baseline), max 338.57 s (0.22 of baseline)

## Self-Check: PASSED

- tests/README.md, README.md, CLAUDE.md, .planning/codebase/TESTING.md, pyproject.toml and `.planning/todos/done/2026-11-13-speed-up-full-test-suite.md` exist; the pending copy is gone.
- Commits `5e7acf8` and `3e5e113` are on the branch.
- `git diff` of `kicad_lib_manager/` against the base is empty; `.planning/config.json` has no `test_command`.
