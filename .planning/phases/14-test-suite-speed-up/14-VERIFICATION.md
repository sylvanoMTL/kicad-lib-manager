---
phase: 14-test-suite-speed-up
verified: 2026-11-23T02:40:00Z
status: passed
score: 6/6 must-haves verified
covered_files: [".planning/phases/14-test-suite-speed-up/14-01-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-01-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-02-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-02-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-03-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-03-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-04-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-04-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-05-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-05-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/14-06-PLAN.md", ".planning/phases/14-test-suite-speed-up/14-06-SUMMARY.md", ".planning/phases/14-test-suite-speed-up/measure.py", ".planning/phases/14-test-suite-speed-up/measurements/results.jsonl", "CLAUDE.md", "README.md", "pyproject.toml", "requirements-dev.txt", "tests/README.md", "tests/conftest.py", "tests/customfixtures.py", "tests/gitfixtures.py", "tests/runfixtures.py", "tests/test_isolation.py", "tests/test_markers.py"]
covered_digest: "v4:sha256:aaf4afbb484774a2aae400a60021267e0dc95b7e24baf01bcc2d1309ae2f0bfe"
behavior_unverified: 0
overrides_applied: 0
coincidental_reliance_items: []
---

# Phase 14: Test Suite Speed-Up Verification Report

**Phase Goal:** The owner gets test results in minutes instead of half an hour: a quick parallel run fits the GSD test gate, and the full suite runs in parallel with exactly the results of the serial run
**Verified:** 2026-11-23T02:40:00Z
**Status:** passed
**Re-verification:** No, initial verification (verified at HEAD c89a726)

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP success criterion) | Status | Evidence |
|---|---|---|---|
| 1 | `pytest -m "not slow"` with parallel workers finishes in under 10 minutes (TEST-04) | VERIFIED | `pyproject.toml` addopts: `-ra --strict-markers -n 8 --dist worksteal -m 'not slow'`, so bare `pytest` is the quick run. I ran it once at HEAD: `3438 passed, 4 skipped, 4 warnings in 66.86s`, exit 0. Recorded quick runs after the crash fix: 69.21 / 68.08 / 69.22 s, all exit 0, against the 600 s gate. |
| 2a | Full suite runs in parallel in at most half the serial baseline (TEST-05) | VERIFIED | Baseline BASELINE.md: 1563.92 s serial (half = 781.96 s). Chosen `-n 8 --dist worksteal`: ten-run walls 320.43..338.57 s (0.20-0.22 of baseline); post-review matrix run 333.75 s. Even against the later serial reference (1507.81 s, half = 753.9 s) it is met. I confirmed the final lines in the raw logs (e.g. `tenrun-20261123T000701-05.log`: `11681 passed, 6 skipped in 320.33s`). `measure.py choose --check-pyproject` prints `-n 8 --dist worksteal`, "half-of-baseline: met (333.75 s <= 781.96 s)", "pyproject addopts hold the chosen setting", exit 0 (verified by me). |
| 2b | Same pass and skip counts as the serial run, ten times in a row (TEST-08) | VERIFIED | Serial reference at dd5f5fb: 11681 passed / 6 skipped, 0 failed (`serial-20261122T233825.log`). Ten consecutive logs `tenrun-20261123T000701-01..10` each end `11681 passed, 6 skipped`, exit 0 (read from the raw logs, not only results.jsonl). Earlier ten-run at the pre-crash-fix commit also 10/10 at 11680/6 vs a serial 11680/6. See "Ten-run timing question" below. |
| 3 | Every slow test (real git, Wurth corpus, kicad-cli) carries `slow`, strict markers stay on (TEST-06) | VERIFIED | `--strict-markers` still in addopts; `slow` registered in pyproject. `conftest.py` auto-marks `wurth`, `kicad_cli` and `kicad_cli_path` users slow (tryfirst hook); the 97+ real-git tests in test_commit_step.py etc. are marked in source; a runtime tripwire (`gitfixtures._require_slow`) and a Popen watch (`_RepoWatchPopen`) fail any unmarked test that builds or creates a git repo. `tests/test_markers.py` (9 tests incl. `test_unregistered_marker_still_fails`, `test_unmarked_git_test_fails_loudly`, `test_unmarked_own_git_repo_fails_loudly`) passed in my `-n 0 --full` run. Quick run excluded the slow set and stayed green, so the tripwire never fired on an unmarked test. |
| 4 | One git template per run, no test touches real settings.ini / %APPDATA% / KiCad config, a write to live Custom/ still fails (TEST-07) | VERIFIED | Template: `gitfixtures._template` builds under a stdlib exclusive-create lock in `<run base temp>/git_templates`, removed in `pytest_sessionfinish`; `test_templates_are_built_once` (4-worker child run) passed. Isolation: autouse `_isolated_user_state` redirects APPDATA, LOCALAPPDATA, USERPROFILE, HOME, XDG_*, KICAD_CONFIG_HOME and QSettings.setPath per test and clears `KICAD_LIB_GITHUB` / `CUSTOM_3DMODEL_DIR` / `WE_3DMODEL_DIR`; session `_qsettings_sandbox` covers session fixtures; `local_kicad` tests are opt-in (my quick run shows the skip "set KICAD_TEST_REAL_CONFIG=1 to run"). Run-level guard hashes the real app state at session start and fails the run on change (KiCad config only warns); `_live_custom_untouched` stays session-scoped and `test_guard_failure_fails_the_run_under_xdist` passed. All of `test_isolation.py` (14 tests) and `test_customfixtures.py` passed in my run: 51 passed in 55.46 s with `-n 0 --full`. All 20 recorded full runs exited 0, so the real-state guard never fired. |
| 5 | A hung test fails with a timeout that names it (TEST-09) | VERIFIED | `pyproject.toml`: `timeout = 300`, `timeout_method = "thread"`, pytest-timeout 2.4.0 pinned. `conftest.py` hooks (`pytest_timeout_set_timer`, `pytest_handlecrashitem`) write and surface `TIMEOUT <nodeid> after N s` under xdist. `test_hung_test_fails_naming_it` (workers) and `test_hung_test_fails_naming_it_serially` actually spawn a child run with a sleeping test and assert the node id in output; both passed in my run. |

**Score:** 6/6 truths verified (0 present-but-behavior-unverified)

### Ten-run timing question (TEST-08)

The recorded ten-run (10/10) was taken at dd5f5fb. After it, four review fixes landed (0877972, 7ba3f27, d2f430f, 28457e6). I diffed `dd5f5fb..HEAD` over `tests/`, `pyproject.toml`, `requirements-dev.txt` and `kicad_lib_manager/`: only `tests/conftest.py` (cleanup now calls `gitfixtures.remove_tree`, same read-only-aware rmtree as before), `tests/gitfixtures.py` (lock taker also tolerates Windows `PermissionError`; stale half-built folder removed only `if folder.exists()`; lock unlink swallows `OSError`) and `tests/test_isolation.py` (a dead glob assertion removed) changed. All are error paths or equivalent refactors; on the happy path (no stale folder, no delete-pending lock) behavior is identical. Independent post-fix evidence: the full six-setting matrix re-run after 28457e6 (all 11681 / 6, exit 0; the n8 worksteal run is 333.75 s), my own quick run at HEAD, and my full `-n 0 --full` run of the isolation, marker and customfixtures modules (including the 4-worker template-once test that exercises the changed lock code). I judge that repeating the ten-run was not needed for the criterion: the code that governs equality of results did not change, and the changed lines were exercised again and passed. Strictly, "ten in a row at HEAD" is not literally recorded; this is documented here rather than hidden. No human item raised.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `requirements-dev.txt` | pytest-xdist==3.8.0, pytest-timeout==2.4.0 pinned, no filelock | VERIFIED | Both pins present; `pip list` in env shows pytest-xdist 3.8.0, pytest-timeout 2.4.0, execnet 2.1.2; no filelock dependency (stdlib lock). |
| `pyproject.toml` | quick defaults, timeout, slow marker, strict markers | VERIFIED | As quoted in truth 1/3/5. |
| `tests/conftest.py` | `--full`, slow auto-map, template root, isolation, guards, timeout hooks | VERIFIED | 552 lines, substantive; all hooks wired and exercised by meta-tests. |
| `tests/gitfixtures.py` | once-per-run template under stdlib lock, tripwire | VERIFIED | Lock/rebuild/`remove_tree` present; old leaking `tempfile.mkdtemp` template removed (diff). |
| `tests/runfixtures.py`, `tests/customfixtures.py` | child-run helpers, Qt-free state digests | VERIFIED | Used by test_isolation/test_markers/test_customfixtures which pass. |
| `tests/test_isolation.py`, `tests/test_markers.py` | meta-tests | VERIFIED | 14 and 9 tests, all pass. |
| `measure.py`, `MEASURE.md`, `MEASUREMENTS.md`, `BASELINE.md`, `measurements/results.jsonl` | measurement evidence | VERIFIED | `measure.py self-test` ok; raw logs match recorded counts for ten-run, serial, quick, matrix. |
| `tests/README.md`, `README.md`, `CLAUDE.md` | document quick and full commands | VERIFIED | Diff shows both `pytest` and `pytest --full`, `-n 0` for debugging, dependency install note. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| pyproject addopts | xdist plugin + `not slow` | `-n 8 --dist worksteal -m 'not slow'` | WIRED | Quick run observed using popen-gw workers. |
| `--full` | clears `not slow` | `pytest_configure` | WIRED | `test_full_option_runs_slow_tests` passed; full runs counted 11681. |
| `conftest._git_template_root` | `gitfixtures.set_template_root` | session autouse | WIRED | `test_templates_are_built_once` passed. |
| `pytest_runtest_setup` | `gitfixtures.set_current_item` | tripwire | WIRED | `test_unmarked_git_test_fails_loudly` passed. |
| timeout hook | controller crash report | `pytest_handlecrashitem` + records file | WIRED | `test_hung_test_fails_naming_it` passed. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Quick gate run | `env/Scripts/python.exe -m pytest -q` | 3438 passed, 4 skipped, 66.86 s | PASS |
| Isolation, markers, Custom guard, timeout, template-once meta-tests | `pytest -q -n 0 --full tests/test_isolation.py tests/test_markers.py tests/test_customfixtures.py` | 51 passed in 55.46 s | PASS |
| Setting choice and pyproject agreement | `measure.py choose --check-pyproject` | `-n 8 --dist worksteal`, met, exit 0 | PASS |
| Measurement script self-test | `measure.py self-test` | ok, exit 0 | PASS |
| Raw logs vs recorded counts | tail of ten serial/quick/tenrun/matrix logs | all equal recorded counts | PASS |

The full suite and the ten-run were not re-run, as instructed; they were checked from the recorded raw logs.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| TEST-04 | 14-01, 14-02, 14-03, 14-04, 14-06 | Quick parallel run under 10 min | SATISFIED | Truth 1 |
| TEST-05 | 14-01, 14-03, 14-06 | Full parallel run at most half of serial baseline | SATISFIED | Truth 2a |
| TEST-06 | 14-02, 14-04 | Slow marker, strict markers stay on | SATISFIED | Truth 3 |
| TEST-07 | 14-01, 14-05 | Isolation, once-per-run template, live guard | SATISFIED | Truth 4 |
| TEST-08 | 14-03, 14-06 | Same pass/skip counts as serial, ten times | SATISFIED | Truth 2b |
| TEST-09 | 14-01 | Hung test fails with a named timeout | SATISFIED | Truth 5 |

All six IDs appear in at least one PLAN's `requirements:` and in REQUIREMENTS.md; no orphaned Phase 14 requirement. Bookkeeping note: REQUIREMENTS.md still shows these six as unchecked / "Pending" (lines 13-18, 120-125); the orchestrator should flip them on phase close.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (phase-touched harness files) | - | TODO / FIXME / XXX / TBD scan | none found | - |
| `kicad_lib_manager/` | - | application code diff vs base 20a557a | empty | Harness-only scope honored. |

Deferred review notes (14-REVIEW-DISPOSITION.md, IN-01..IN-05, info-level, 0 open) are harness hardening candidates, not blockers. The MigrationDialog timers-on-close follow-up is captured in `.planning/todos/pending/` as intended. The todo `2026-11-13-speed-up-full-test-suite.md` is moved to `todos/done/` as planned.

Informational: the ROADMAP note asks for a baseline from "three serial runs, first discarded"; CONTEXT narrowed this to one serial `--durations` run, and the later serial reference (1507.81 s) agrees with it within 4 percent, so the half-baseline bound holds under either number.

### Human Verification Required

None.

### Gaps Summary

No gaps. Every roadmap success criterion is backed by code in the repo, by meta-tests that I ran and that passed, and by recorded raw logs whose counts I checked. The only judgment call, that the ten-run was not repeated after the four review fixes, is explained above and does not change the verdict.

---

_Verified: 2026-11-23T02:40:00Z_
_Verifier: Claude (gsd-verifier)_
