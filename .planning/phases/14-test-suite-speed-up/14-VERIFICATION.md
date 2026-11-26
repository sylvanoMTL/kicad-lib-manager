---
phase: 14-test-suite-speed-up
verified: 2026-11-26T12:30:00Z
status: passed
score: 6/6 must-haves verified
covered_files: [".planning/phases/14-test-suite-speed-up/14-01-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-01-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-02-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-02-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-03-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-03-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-04-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-04-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-05-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-05-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-06-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-06-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/BASELINE.md", ".planning/phases/14-test-suite-speed-up/MEASURE.md", ".planning/phases/14-test-suite-speed-up/MEASUREMENTS.md", ".planning/phases/14-test-suite-speed-up/measure.py", "CLAUDE.md", "README.md", "pyproject.toml", "requirements-dev.txt", "tests/README.md", "tests/conftest.py", "tests/customfixtures.py", "tests/gitfixtures.py", "tests/runfixtures.py", "tests/test_isolation.py", "tests/test_markers.py"]
covered_digest: "v4:sha256:63042ad377c6824b627a9c9feeb7baeb91172fef1b69a168646a82e4201560f3"
behavior_unverified: 0
overrides_applied: 0
coincidental_reliance_items: []
re_verification:
  previous_status: passed
  previous_score: 6/6
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 14: Test Suite Speed-Up Verification Report

**Phase Goal:** The owner gets test results in minutes instead of half an hour: a quick parallel run fits the GSD test gate, and the full suite runs in parallel with exactly the results of the serial run
**Verified:** 2026-11-26T12:30:00Z
**Status:** passed
**Re-verification:** Yes, regenerated at HEAD 2920420 because the previous report (2026-11-23, status passed) went stale. No gaps were open before, so this is a staleness refresh, not a gap-closure round.

## Why the previous report went stale

Two covered inputs changed after 2026-11-23. Both changes come from Phase 16 (the repo split), not from new Phase 14 work.

1. `.planning/phases/14-test-suite-speed-up/measurements/` (`results.jsonl` and the 40 raw timing logs) no longer exists in this repository. Phase 16 dropped it on purpose: plan 16-04's export allow-list has `!.planning/phases/14-test-suite-speed-up/measurements/`, so the published tool repository (history starting at the import commit 2712099) does not carry the logs. This is not a gap. I dropped the folder from the covered file set. The folder is confirmed absent (`ls` fails).
2. `tests/README.md` was rewritten in plan 16-11 with the measured counts of the new repository. I re-checked it (see TEST-06/07/09 docs below).

Where the TEST-04/05/08 evidence now lives (all in this repository, all in the covered set):
- `.planning/phases/14-test-suite-speed-up/MEASUREMENTS.md`: the full run table (serial, six-setting matrix, three quick runs, two ten-runs of ten with exit code, wall time, pass/skip counts) and the verdicts.
- `BASELINE.md`: the serial baseline, 1563.92 s, 11662 passed / 1 failed (pre-existing, explained) / 5 skipped, with the 50 slowest tests.
- `MEASURE.md` and the six SUMMARY.md files.
- The raw logs survive only in the owner's pre-split backup bundle, outside every repository. I could not and did not re-read them this time; the previous report did read them and found them equal to the recorded counts. Consequence: for the full-suite claims (TEST-05, TEST-08) this report rests on the recorded table plus the code that governs equality (unchanged logic, exercised by the meta-tests I re-ran), not on fresh raw-log reads. I judge that sufficient: the table is a generated file (`measure.py` writes it from results.jsonl), is internally consistent (ten rows of 11681 / 6 / exit 0 matching the serial reference of 11681 / 6), and the earlier verifier confirmed the raw logs against it.

`measure.py choose --check-pyproject` can no longer run in this repository: it reports `no serial reference with this selection; run measure.py serial first`, because results.jsonl is gone. This is the expected consequence of the split and not a defect. `measure.py self-test` still prints `self-test: ok`.

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP success criterion) | Status | Evidence |
|---|---|---|---|
| 1 | A quick parallel run (`pytest -m "not slow"`) finishes in under 10 minutes and fits the GSD test gate (TEST-04) | VERIFIED | `pyproject.toml` addopts today: `-ra --strict-markers -n 8 --dist worksteal -m 'not slow'`, so bare `pytest` is the quick run. I ran it myself at HEAD 2920420: `4017 passed, 3 skipped, 4 warnings in 88.25s (0:01:28)`, exit 0, `deselected: 41 corpus (set KICAD_TEST_CORPUS ...)` printed. The orchestrator's run was 99.55 s with the same counts. Both are far under the 600 s gate. Recorded quick runs in MEASUREMENTS.md: 68.08 / 69.22 s. |
| 2a | The full suite runs in parallel in at most half the serial baseline (TEST-05) | VERIFIED | MEASUREMENTS.md: baseline 1563.92 s, half = 781.96 s. Chosen `-n 8 --dist worksteal`: ten-run walls 320.43..338.57 s (0.20 to 0.22 of baseline), matrix run after the crash fix 333.75 s. Even against the later serial reference (1507.81 s, half = 753.9 s) it holds. `pyproject.toml` still holds the chosen setting. Not re-run (about 7 minutes, excluded by instruction); evidence is the recorded table, see above. |
| 2b | The parallel full run gives the same pass and skip counts as the serial run, ten times in a row (TEST-08) | VERIFIED | MEASUREMENTS.md: serial reference `serial-20261122T233825` 11681 passed / 6 skipped / 0 failed; ten consecutive `tenrun-20261123T000701-01..10` rows all 11681 / 6 / 0 / exit 0. The earlier ten-run (11680 / 6 vs serial 11680 / 6) also 10/10. The verdict line "TEST-08: met (10 consecutive runs equal to the serial reference)" is generated by measure.py. The previous report's caveat stands: four review fixes landed after the ten-run, touching only error paths of `gitfixtures`/`conftest` cleanup, and were re-exercised by the full matrix re-run and the meta-tests (which I re-ran again now). Not literally recorded "ten in a row at HEAD"; documented, not hidden. |
| 3 | Every slow test (real git, Wurth corpus, kicad-cli) carries `slow`; strict markers stay on (TEST-06) | VERIFIED | `--strict-markers` in addopts; `slow` registered in `pyproject.toml` markers. `tests/test_markers.py` passed in my `--full` run (included in 52 passed, 26.30 s). The quick run excludes slow tests and stayed green, so the unmarked-git-test tripwire never fired. Orchestrator's `measure.py slow-coverage`: 46 of the 50 baseline tests covered and slow, 0 not slow, 4 not collected (corpus-marked, needs KICAD_TEST_CORPUS; warning only). |
| 4 | Git templates built once per run; no test touches the real `settings.ini` / `%APPDATA%` / KiCad config; a write to the live collection still fails (TEST-07) | VERIFIED | `tests/test_isolation.py` and `tests/test_customfixtures.py` passed in my `--full` run (14 + the Custom-guard tests, with the 4-worker template-once test and the guard-under-xdist test). `conftest.py` holds the autouse `_isolated_user_state` (line 485) and the run-level guard that fails with `the test run changed the real app state: ...` (line 308); KiCad config change only warns. The quick run printed the `local_kicad` opt-in skip (`set KICAD_TEST_REAL_CONFIG=1 to run`), so no test read the real KiCad config. The run exited 0, so the real-state guard did not fire. |
| 5 | A hung test fails with a timeout instead of stalling the run (TEST-09) | VERIFIED | `pyproject.toml`: `timeout = 300`, `timeout_method = "thread"`; `requirements-dev.txt` pins `pytest-timeout==2.4.0` and `pytest-xdist==3.8.0`. `conftest.py` hooks `pytest_timeout_set_timer` and `pytest_handlecrashitem` write and surface `TIMEOUT <nodeid> after N s`. The meta-tests that spawn a child run with a sleeping test and assert the node id in the output (`test_hung_test_fails_naming_it` with workers and serially) are in `tests/test_markers.py` / `test_isolation.py` and passed in my run. |

**Score:** 6/6 requirement truths verified (0 present-but-behavior-unverified)

### Documentation check (tests/README.md after plan 16-11, CLAUDE.md, README.md)

| Item | Where | Status |
|---|---|---|
| Quick run = bare `pytest`, parallel, skips slow, "the same run the GSD test gate uses" | `tests/README.md` "How to run"; `CLAUDE.md` "Running the Tests" | matches, both name the same command |
| Full run `--full`; serial reference `--full -n 0` | both files | matches |
| `-n 0` for debugging (`--pdb`, `-s`, `breakpoint()`) | both files; `README.md` line 60 | matches |
| Install `requirements-dev.txt` (xdist, timeout); `unrecognized arguments: -n` hint | `tests/README.md` | present |
| Markers (`slow`, `wurth`, `kicad_cli`, `corpus`, `needs_kicad`, `local_kicad`), strict markers, the two exact slow-mark failure messages | `tests/README.md` "Slow tests", "Corpus and KiCad-install tests"; marker list in `pyproject.toml` | present, README marker set equals the registered set |
| Timeouts (300 s thread, 900 s for the Wurth parse budget, the two-line TIMEOUT report under workers) | `tests/README.md` "Timeouts" | present, matches `pyproject.toml` |
| Isolation (own APPDATA/HOME/QSettings, KICAD_* vars removed, `KICAD_TEST_REAL_CONFIG=1` opt-in) and the two run-level guard messages | `tests/README.md` "Your own settings stay out"; `CLAUDE.md` | present |
| Shared git template built once per run | `tests/README.md` "Shared git templates" | present |
| Measured times | `tests/README.md` points to `.planning/phases/14-test-suite-speed-up/MEASUREMENTS.md`, which exists | link resolves |
| Skip budget (at most 10) and expected skips | `tests/README.md` table: quick run 4013 passed / 3 skipped; today 4017 / 3 | consistent: the three skips are the ones I observed |

Minor drift, informational only: the README's 2026-11-24 measurement table says 4013 passed in the clean-clone run; the workstation now shows 4017 passed because four tests were added by later Phase 16 plans. The README states the figures as dated measurements, so this is not a defect.

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `requirements-dev.txt` | pytest-xdist==3.8.0, pytest-timeout==2.4.0 pinned | VERIFIED | Both present, plus `-r requirements.txt`, pytest 9.1.1, pytest-qt 4.5.0. |
| `pyproject.toml` | quick defaults, timeout, slow marker, strict markers | VERIFIED | Read in full above. |
| `tests/conftest.py` | `--full`, slow auto-map, template root, isolation, guards, timeout hooks | VERIFIED | `--full` option (line 44) and `-m` clearing (line 70), guards (264-315), timeout hooks (334-391), isolation fixture (485). Exercised by meta-tests. |
| `tests/gitfixtures.py`, `tests/runfixtures.py`, `tests/customfixtures.py` | once-per-run template, child-run helpers, state digests | VERIFIED | Present and used by the meta-tests that pass. |
| `tests/test_isolation.py`, `tests/test_markers.py` | meta-tests | VERIFIED | Passed (52 passed together with test_customfixtures). |
| `measure.py`, `MEASURE.md`, `MEASUREMENTS.md`, `BASELINE.md` | measurement evidence | VERIFIED | `measure.py self-test` ok. `results.jsonl` and raw logs intentionally absent after the split (see above). |
| `tests/README.md`, `README.md`, `CLAUDE.md` | quick/full commands documented | VERIFIED | See documentation check. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| pyproject addopts | xdist + `not slow` | `-n 8 --dist worksteal -m 'not slow'` | WIRED | My quick run used popen-gw workers (skip paths show `popen-gw6`). |
| `--full` | clears `not slow` | `pytest_configure` | WIRED | My `--full` run collected and ran the slow meta-tests. |
| `_git_template_root` | `gitfixtures.set_template_root` | session autouse | WIRED | Template-once test passed. |
| `pytest_runtest_setup` | `gitfixtures.set_current_item` | tripwire | WIRED | Unmarked-git-test meta-tests passed. |
| timeout hook | controller crash report | `pytest_handlecrashitem` + records file | WIRED | Hung-test meta-tests passed. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Quick gate run | `env/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider` | 4017 passed, 3 skipped, 88.25 s, exit 0 | PASS |
| Marker, isolation, Custom-guard, timeout and template-once meta-tests | `pytest -q -p no:cacheprovider tests/test_markers.py tests/test_isolation.py tests/test_customfixtures.py --full` | 52 passed in 26.30 s | PASS |
| Measurement script self-test | `measure.py self-test` | `self-test: ok`, exit 0 | PASS |
| `measure.py choose --check-pyproject` | as above | cannot run: results.jsonl removed by the split (see above) | N/A (expected) |

The full suite and the ten-run were not re-run, as instructed.

### Probe Execution

SKIPPED: this phase declares no `probe-*.sh` scripts.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| TEST-04 | 14-01, 14-02, 14-03, 14-04, 14-06 | Quick parallel run under 10 minutes | SATISFIED | Truth 1 |
| TEST-05 | 14-01, 14-03, 14-06 | Full parallel run at most half of the serial baseline | SATISFIED | Truth 2a |
| TEST-06 | 14-02, 14-04 | Slow marker, strict markers stay on | SATISFIED | Truth 3 |
| TEST-07 | 14-01, 14-05 | Isolation, once-per-run template, live-collection guard | SATISFIED | Truth 4 |
| TEST-08 | 14-03, 14-06 | Same pass/skip counts as serial, ten times | SATISFIED | Truth 2b |
| TEST-09 | 14-01 | Hung test fails with a named timeout | SATISFIED | Truth 5 |

All six IDs appear in a PLAN `requirements:` line (14-01: TEST-04/05/07/09; 14-02: TEST-06/04; 14-03: TEST-04/05/08; 14-04: TEST-06/04; 14-05: TEST-07; 14-06: TEST-04/05/08) and in `.planning/REQUIREMENTS.md`, where lines 13-18 are checked `[x]` and lines 120-125 read "Complete". No orphaned Phase 14 requirement. (The previous report's bookkeeping note about unchecked boxes is resolved.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (covered harness files) | - | TBD / FIXME / XXX debt-marker scan | none | - |

Review dispositions (14-REVIEW-DISPOSITION.md, IN-01..IN-05, info level) remain non-blocking hardening candidates. The security re-audit (14-SECURITY.md, 2026-11-26) reports 20/20 threats closed; the validation re-audit reports 0 gaps (orchestrator evidence, not re-run by me).

### Human Verification Required

None.

### Gaps Summary

No gaps. The goal holds at HEAD 2920420: the quick parallel run takes 88 to 100 s with exit 0 and the pinned xdist/timeout configuration, the marker, isolation, live-collection guard, template-once and named-timeout behaviors are enforced by meta-tests that pass now, the documentation in `tests/README.md`, `CLAUDE.md` and `README.md` is consistent with `pyproject.toml`, and the full-suite claims (half of baseline, 10/10 equal to serial) are recorded in the tracked `MEASUREMENTS.md`. The one thing not freshly re-observable is the full parallel suite itself (excluded by instruction) and its raw logs (moved out of the repository by the split on purpose); both are covered by the recorded table and the earlier raw-log verification.

---

_Verified: 2026-11-26T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
