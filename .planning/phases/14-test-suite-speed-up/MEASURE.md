# Phase 14 measurement runbook

For the orchestrator. Every long run of the phase goes through
`.planning/phases/14-test-suite-speed-up/measure.py`; executors only smoke-test it on one
small module (`-- tests/test_sexpr.py`, with `--out <temp folder>`). Every number reported
for the phase comes from `measurements/results.jsonl` through `MEASUREMENTS.md`.

Run it from the main checkout (``) with that
repo's venv. The script uses `MEASURE_PYTHON` if set, else the interpreter it was started
with, else `env/Scripts/python.exe`; the first one that imports pytest and xdist is used.
Each run is stopped together with its worker processes when it passes its budget (quick
600 s, full 3600 s, serial 5400 s).

Shorthand: `measure.py` below means `python .planning/phases/14-test-suite-speed-up/measure.py`, and `python` is the
venv interpreter.

## 1. BASELINE.md (before wave 1, orchestrator)

`python -m pytest --durations=50 -q -p no:cacheprovider` on the unchanged base commit.
Keep the durations block and the final summary line verbatim; commit it. Check it with
`measure.py baseline` (prints counts, wall seconds and the number of durations lines).

## 2. After wave 4 (plans 14-04 and 14-05) is merged, before plan 14-06

`measure.py serial` (about 30-35 min; the serial reference of this checkout), then
`measure.py matrix` (six full parallel runs: -n 4, 6, 8 with --dist worksteal and loadfile).
Run each in the background with an exit-code file and a monitor, never inside an executor,
never two at once. `measure.py slow-coverage` lists which of the baseline's 50 slowest tests
are marked slow (exit 1 while some are not).

## 3. Apply the chosen setting (plan 14-06 Task 2)

`measure.py choose` prints `-n <N> --dist <mode>` and then `half-of-baseline: met` or
`half-of-baseline: missed`. 14-06 puts that pair into pyproject addopts, and
`measure.py choose --check-pyproject` exits 0 only when addopts hold it. If choose prints
`half-of-baseline: missed`, do step 6 before the ten-run (it saves one ten-run).

## 4. After plan 14-06

`measure.py quick --runs 3` (TEST-04) and `measure.py tenrun` (TEST-05 and TEST-08). Then
copy the "Verdicts" and "Before / after" sections of MEASUREMENTS.md into
`14-06-SUMMARY.md` (CONTEXT "Baseline": the SUMMARY reports before/after wall times).

## 5. A ten-run fails on counts or exit (ok false)

`measure.py choose` now drops that setting. Re-apply the new choice (gap closure of 14-06
Task 2), then run `measure.py tenrun` again. Note: the serial reference of a checkout that
still has the baseline's known failure (`test_project_md_marks_migration_delivered`) exits
1, so a ten-run can never be `ok` until that test passes; fix or settle it first.

## 6. TEST-05 contingency (tried once)

CONTEXT "Orchestrator decisions after research (2026-11-22)", TEST-05 contingency;
RESEARCH Open Question 4, resolved as this contingency.

Trigger: choose printed `half-of-baseline: missed`, or a tenrun record has ok true and
half_ok false.

- Lever 1: one git template per `(populate, autocrlf)` in `tests/gitfixtures.py`, so the
  tests that pass their own `populate` (about 12, RESEARCH Open Question 4) copy a cached
  template instead of building one. Done as a gap-closure plan of this phase, with the
  template-once and tripwire meta-tests still green.
- Lever 2: a Microsoft Defender exclusion of the pytest base temp root
  (`%TEMP%\pytest-of-<user> RESEARCH Assumption A5). It needs an elevated PowerShell and
  the owner's explicit yes, so in an unattended run it is not added and the SUMMARY records
  "Defender exclusion: not tried, needs the owner". When it is added, the SUMMARY names the
  path and the removal command `Remove-MpPreference -ExclusionPath <path>`.

Then re-measure once:

1. `measure.py matrix --note contingency`
2. `measure.py choose` (re-apply to pyproject when the pair changed, gap closure of 14-06 Task 2)
3. `measure.py tenrun --note contingency`

If that tenrun still has half_ok false, MEASUREMENTS.md reads `TEST-05: not met`, the
14-06 SUMMARY says "TEST-05 not met" with both ten-run slowest walls and the bound, and
TEST-05 goes to gap closure. Never change BASELINE.md, the bound, a timeout or the test
selection to make it pass.

## 7. After every run

Check that no python or pytest process from the run is left
(`tasklist | findstr /I python` on Windows; other sessions' processes may show there, look
for `pytest` command lines), then commit `measurements/` and `MEASUREMENTS.md`. Logs hold
only the last 300 lines of pytest output with the home folder replaced by `~`.

## 8. Verdict rules

- TEST-04: runs after the first of three runs of the gate command
  (`python -m pytest -x -q --tb=short`) each exit 0 in under 600 s.
- TEST-05: every ten-run run at most half the BASELINE.md wall time (`half_ok` of the latest
  tenrun record, and the ten-run itself ok). A missed bound is reported as
  `TEST-05: not met`, never as met.
- TEST-08: ten consecutive `--full` runs, each exit 0 with the same passed, skipped, failed,
  errors, xfailed and xpassed counts as the latest serial reference.
- Counts compare only within one checkout on one day (RESEARCH Pitfall 6).
