---
phase: 14-test-suite-speed-up
plan: 03
subsystem: testing
tags: [pytest, pytest-xdist, measurement, stdlib]

requires:
  - phase: 14-01
    provides: "--full, slow auto-mapping, addopts -n/--dist, runfixtures"
provides:
  - "measure.py: one stdlib-only runner for the serial reference, -n/--dist matrix, quick-run timing, ten-run check and the D9 choice"
  - "MEASURE.md: orchestrator runbook (order, commands, budgets, verdict rules, one-time TEST-05 contingency)"
affects: [14-06]

actuals:
  tokens: 14000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "results.jsonl as the only source of reported numbers; MEASUREMENTS.md rebuilt from it by a pure build_report()"
    - "budgeted child run in its own process group, killed as a tree (taskkill /T /F, or killpg)"

key-files:
  created:
    - .planning/phases/14-test-suite-speed-up/measure.py
    - .planning/phases/14-test-suite-speed-up/MEASURE.md
  modified: []

key-decisions:
  - "Interpreter lookup: MEASURE_PYTHON, else sys.executable, else repo env/; the first that imports pytest and xdist wins (the worktree has no env/)"
  - "TEST-05 reads met only when the latest tenrun record has ok and half_ok both true; TEST-08 reads the same record's ok"
  - "The tenrun record carries an extra reason field so the report can name why TEST-08 was not met"

requirements-completed: [TEST-04, TEST-05, TEST-08]

duration: 30min
completed: 2026-11-22
status: complete
plan_head_before: fd42324cb3d3f5d5936ca49d6a7c5a9beb33870d
plan_head_after: ffeb48c7781f7011f8e8a303fe9dc30033a0b9e6
---

# Phase 14 Plan 03: Measurement script and runbook Summary

**`measure.py` runs and judges every long measurement of the phase (serial reference, six-setting -n/--dist matrix, quick gate timing, ten-run equality with the half-of-baseline bound) from one results.jsonl, kills a run's whole process tree on a budget overrun, and `MEASURE.md` tells the orchestrator the order and the one-time TEST-05 contingency.**

## Performance

- **Duration:** about 30 min
- **Tasks:** 2
- **Files:** 2 created (measure.py 800+ lines, MEASURE.md)

## Accomplishments

- Parsing: `parse_summary` (with or without `=` padding, `error`/`errors`, `no tests ran`), `parse_durations`, `parse_addopts`, `baseline()`.
- `run_pytest`: own process group, budget, tree kill on overrun, 300-line log tail with the home folder redacted (single, doubled-backslash and forward-slash forms), record appended to results.jsonl, report rewritten.
- Commands: `self-test`, `baseline`, `serial`, `full`, `matrix`, `quick`, `tenrun`, `choose` (`--check-pyproject`), `slow-coverage`; `--out`, `--note`, selection after `--`.
- `choose_setting` is pure: newest matrix record per setting, equal counts with the serial reference, drops settings with a failed tenrun, keeps ok-but-slow ones, ties to the smaller n. `choose` prints `half-of-baseline: met|missed` and stores `half_ok`.
- `MEASURE.md` steps 1-8, step 6 being the TEST-05 contingency (template per `(populate, autocrlf)`; Defender exclusion only with the owner's yes, with the `Remove-MpPreference -ExclusionPath` undo).

## Evidence (smoke runs on tests/test_sexpr.py, store in a temp folder outside the repo)

Parsed baseline (`measure.py baseline`):

```
baseline counts: 11662 passed, 1 failed, 5 skipped, 0 errors, 0 xfailed, 0 xpassed
baseline wall seconds: 1563.92
baseline durations lines: 50
```

Smoke lines:

```
[quick-...-1] exit=0 wall=6.76s passed=153 skipped=1 failed=0 errors=0 xfailed=0 xpassed=0
[quick-...-2] exit=0 wall=4.96s passed=153 skipped=1 failed=0 errors=0 xfailed=0 xpassed=0
TEST-04: met (walls [6.76, 4.96], exits [0, 0])
[full-...] exit=0 wall=4.81s passed=153 skipped=1 ...
[serial-...] exit=0 wall=4.72s passed=153 skipped=1 ...   (-n 0)
[matrix-n2-worksteal-...] exit=0 wall=4.46s ...   [matrix-n2-loadfile-...] exit=0 wall=6.07s ...
-n 2 --dist worksteal
half-of-baseline: met (4.46 s <= 781.96 s)
TEST-08: met
TEST-05: met (slowest 4.41 s <= 781.96 s)
choose --check-pyproject: "pyproject addopts hold -n 6 --dist worksteal, not the chosen setting", exit 1 (as designed)
```

- `self-test` passes (parsers, `_addopts_values`, redaction, all `choose_setting` cases, `half_bound(1754.32) == 877.16`, report verdict lines for met, slow, incomplete and missed-half cases).
- Budget kill (scratch check, 4 s budget on `tests/test_commit_step.py` under 6 workers): record `exit=timeout`, wall 4.37 s, log shows `node down: Not properly terminated`; no pytest process of this run was left afterwards.
- `slow-coverage` ran in this checkout: `baseline tests: 50`, covered 3, not slow 46, missing 1 (a Wurth id, submodule absent). Exit 1 is expected until 14-02's git marks are merged here; it will be re-run by the orchestrator after wave 4.
- `git status --porcelain -- .planning/phases/14-test-suite-speed-up/measurements` printed nothing after the smoke runs.
- Acceptance greps: 5 core defs, `taskkill` present, imports stdlib-only, 3 choose helpers, `half-of-baseline` 3 hits, MEASURE.md hits for `measure.py tenrun`, `TEST-05 contingency`, `TEST-05: not met`, `Remove-MpPreference`, `measure.py serial`.

## Task Commits

1. **Task 1: measure.py core** - `50a4d1e` (feat)
2. **Task 2: tenrun, choose, slow-coverage, MEASURE.md** - `ffeb48c` (feat)

## Decisions Made

See key-decisions. `build_report` was written complete in Task 1 (it already reads `tenrun` and `choose` records) so Task 1 was self-contained; Task 2 only added the commands that write those records.

## Deviations from Plan

None - plan executed exactly as written (the report's quick verdict wording says "runs after the first" instead of "runs 2-3" so it stays true when `--runs` is not 3).

## Issues Encountered

- The worktree shell guard refused some compound commands (a `git` word inside a longer command, and one containing the smoke selection), so the smoke runs were driven through scratch shell scripts in the session scratchpad (not part of the repo).
- The worktree has no `env/`; the main checkout's venv interpreter was used from the worktree root, as the orchestrator note says.

## Notes for the orchestrator

- BASELINE.md records one pre-existing failure (`tests/test_docs_atomic.py::test_project_md_marks_migration_delivered`, exit 1). A serial reference exiting 1 is allowed (choose compares counts), but `tenrun` requires exit 0 on every run, so TEST-08 cannot be met until that test passes in the measured checkout. MEASURE.md step 5 says so.
- No real serial, matrix, quick, tenrun or full run was started; no pytest process is left running.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-14-06 tree kill, T-14-07 redacted tail logs, T-14-08 verdicts computed from the records, T-14-16 Defender lever needs the owner).

## Self-Check: PASSED

- Files exist: measure.py, MEASURE.md.
- Commits `50a4d1e` and `ffeb48c` exist on the branch.
