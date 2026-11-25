---
phase: "14"
slug: "test-suite-speed-up"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-22"
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `14-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-qt 4.5.0, plus pytest-xdist 3.8.0 and pytest-timeout 2.4.0 installed by this phase |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.\env\Scripts\python.exe -m pytest` (bare; becomes the parallel `-m "not slow"` run via addopts) |
| **Full suite command** | `.\env\Scripts\python.exe -m pytest --full` (serial reference: `--full -n 0`) |
| **Estimated runtime** | quick run under 600 s (target); full parallel run at most half the serial baseline in `BASELINE.md` |

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/test_markers.py tests/test_isolation.py -q` plus the touched module(s) (about 30-60 s)
- **After every plan wave:** bare `python -m pytest` (the quick run; must finish under 10 minutes; also the GSD gate)
- **Before `/gsd-verify-work`:** the orchestrator runs `--full` once with a long budget, then the ten-run equality script; executors never start a full run
- **Max feedback latency:** 600 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| orchestrator (before wave 1) | — | 0 | TEST-05 | — | N/A | timing baseline | serial `python -m pytest --durations=50 -q -p no:cacheprovider` before any change → `BASELINE.md` (durations block + final summary line, committed) | ✅ | ✅ green |
| 14-03-01 (script), orchestrator run after 14-06 | 14-03 / 14-06 | 2 / after 5 | TEST-04 | — | N/A | timing | `python .planning/phases/14-test-suite-speed-up/measure.py quick --runs 3` (gate command `python -m pytest -x -q --tb=short`; runs 2-3 each exit 0 in < 600 s) | ✅ | ✅ green |
| 14-03-02 (script), orchestrator run after 14-06 | 14-03 / 14-06 | 2 / after 5 | TEST-05 | T-14-08, T-14-16 | a missed bound is reported, never passed | timing | `python .planning/phases/14-test-suite-speed-up/measure.py tenrun` (every `--full` parallel run ≤ 0.5 × BASELINE.md wall; `half_ok`; prints `TEST-05: met` or `TEST-05: not met`); early warning `measure.py choose` (`half-of-baseline: met` or `missed`); a miss runs MEASURE.md step 6 (contingency) once, else `TEST-05: not met` goes to gap closure | ✅ | ✅ green |
| 14-01-02, 14-04-01 | 14-01 / 14-04 | 1 / 4 | TEST-06 | T-14-19 | the subprocess watch only records, never changes a call | meta-test + collection + runtime watch | `python -m pytest tests/test_markers.py -q` (9 tests: wurth/kicad_cli/kicad_cli_path tests are slow; every function-level @requires_git test is slow except the one allow-listed read-only id; `--full`; unregistered marker fails; builder tripwire; `test_unmarked_own_git_repo_fails_loudly`: an unmarked test starting `git init`/`git clone` fails at teardown with `<nodeid> creates a real git repository (<command>): mark it @pytest.mark.slow`, with or without @requires_git); quick run of the modules that start git passes with no watch message | ✅ | ✅ green |
| 14-02-01, 14-02-02, 14-02-03 | 14-02 | 2 | TEST-06 | — | N/A | runtime tripwire + function-level marks | quick run of the twelve git modules and test_atomic_uat passes with no "builds a real git repository" line; `--collect-only -q -m "not slow"` over test_commit_gate, test_commit_gate_panel and test_scan_changes prints `7/58 tests collected (51 deselected)` (only builder tests are slow, `pytestmark = requires_git` unchanged, no module-level slow mark); `python -m pytest tests/test_atomic_uat.py --full -m slow -q` (its 2 own-`git init` tests are slow); `python -m pytest tests/test_markers.py -q -k unmarked_git` | ✅ | ✅ green |
| 14-04-02 | 14-04 | 4 | TEST-06 | — | N/A | baseline coverage | `python .planning/phases/14-test-suite-speed-up/measure.py slow-coverage` (exit 0: every BASELINE.md top-50 test is slow) | ✅ | ✅ green |
| 14-01-02, 14-01-03 | 14-01 | 1 | TEST-07 | T-14-01, T-14-02, T-14-03 | templates built once, no `%TEMP%` leak, only the run's own folder removed | subprocess `-n 4` | `python -m pytest tests/test_isolation.py::test_templates_are_built_once --full -q` (slow: needs `--full`) | ✅ | ✅ green |
| 14-05-01 | 14-05 | 3 | TEST-07 | T-14-10 | no real settings / APPDATA / KiCad config / env var visible to tests; per-test user folders removed at teardown | in-process + child meta-tests | `python -m pytest tests/test_isolation.py -q -k "redirected or cleared or leak"` (the leak test also checks no `user<N>` / `qsettings_session<N>` folder is left in the child's base temp) | ✅ | ✅ green |
| 14-05-01 | 14-05 | 3 | TEST-07 | T-14-17 | no default-run test reads the real KiCad config: local_kicad opt-in behind `KICAD_TEST_REAL_CONFIG=1`, nothing read at collection | unit + collection | `env -u KICAD_TEST_REAL_CONFIG python -m pytest tests/test_roundtrip_corpus.py -q -rs -k local_kicad` ("2 passed, 1 skipped", skip names `KICAD_TEST_REAL_CONFIG=1`) | ✅ | ✅ green |
| 14-05-01 | 14-05 | 3 | TEST-07 | T-14-17 | kicad-cli reads and writes only the per-test `KICAD_CONFIG_HOME` | kicad-cli meta-test + before/after counts | `python -m pytest tests/test_isolation.py::test_kicad_cli_uses_the_test_config_folder --full -q`; `-m kicad_cli` passed/skipped counts equal the run saved before the conftest edit | ✅ | ✅ green |
| 14-05-02 | 14-05 | 3 | TEST-07 | T-14-10, T-14-11, T-14-12 | real app-state files unchanged after a run (fails); KiCad config change only warns | controller guard + unit tests on a fake tree + child runs | `python -m pytest tests/test_isolation.py -k user_state_guard -q` | ✅ | ✅ green |
| 14-05-02 | 14-05 | 3 | TEST-07 | T-14-13 | a live `Custom/` write still fails the run under xdist | subprocess `-n 2` | `python -m pytest tests/test_customfixtures.py -q` (existing serial case + new `-n 2` case) | ✅ | ✅ green |
| 14-03-02 (script), orchestrator run after 14-06 | 14-03 / 14-06 | 2 / after 5 | TEST-08 | — | N/A | ten-run equality | `python .planning/phases/14-test-suite-speed-up/measure.py tenrun` (ten consecutive `--full` runs, the six counts equal to the `measure.py serial` reference every time) | ✅ | ✅ green |
| 14-01-03 | 14-01 | 1 | TEST-09 | T-14-04, T-14-18 | a crash is never reported as a timeout (record matched by node id, per-run folder) | subprocess | `python -m pytest tests/test_isolation.py -q -k hung` (exit ≠ 0, elapsed < 30 s; under `-n 2` stdout holds `TIMEOUT test_hang.py::test_hangs after 2 s` and `crashed while running`; under `-n 0` "Timeout" and `test_hangs`); `python -m pytest tests/test_sexpr.py -q -p no:xdist -p no:timeout -o "addopts=-ra --strict-markers"` (conftest still loads: optional hooks) | ✅ | ✅ green |
| 14-01-03 | 14-01 | 1 | TEST-09 | — | N/A | static config check | `python -m pytest tests/test_isolation.py -q -k timeout_config` (`timeout = 300`, thread method, Würth budget test `timeout(900)`) | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky* — task IDs are `<phase>-<plan>-<task>` (14-01-02 = plan 14-01, Task 2). Slow tests (marked `slow`) need `--full` when selected by node id.

---

## Wave 0 Requirements

- [x] `.planning/phases/14-test-suite-speed-up/BASELINE.md` — serial `--durations=50` run before any change (orchestrator runs it with a long budget)
- [x] `tests/test_markers.py`, `tests/test_isolation.py` — new meta-tests
- [x] `tests/conftest.py` additions — `--full`, slow-marker hook, isolation fixture (with `KICAD_CONFIG_HOME` redirect), template root, run-level user-state guard
- [x] `tests/test_roundtrip_corpus.py` — `local_kicad` opt-in behind `KICAD_TEST_REAL_CONFIG=1` (plan 14-05)
- [x] `tests/gitfixtures.py` — template built once per run under a stdlib lock, tripwire for unmarked git tests
- [x] `pip install -r requirements-dev.txt` (pytest-xdist 3.8.0, pytest-timeout 2.4.0) into this worktree's `env/` (the venv the GSD gate's bare `python` resolves to, plan 14-01); the main checkout's venv only when tests are run there (README, plan 14-06)
- [x] Ten-run and timing scripts in the phase folder: `measure.py` and its runbook `MEASURE.md` (plan 14-03)
- [x] `tests/runfixtures.py` — child-pytest helper (`run_pytest` with `-p conftest -c pyproject.toml --confcutdir`, `collect_repo`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ten consecutive parallel full runs match the serial counts | TEST-08 | about 10 × 10-15 min; too long for an executor | Orchestrator runs the phase-folder script with a long budget and records the ten count lines in the SUMMARY. Done 2026-11-23 at dd5f5fb: 10/10 equal to the serial reference (11681 passed, 6 skipped), slowest 338.57 s (MEASUREMENTS.md, 14-06-SUMMARY.md) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 600s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-11-23 (validate-phase 14; every map command re-run green at c89a726+; TEST-04/05/08 from the recorded measurements)

## Validation Audit 2026-11-23

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
