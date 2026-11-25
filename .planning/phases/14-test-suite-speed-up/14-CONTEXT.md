# Phase 14: Test Suite Speed-Up - Context

**Gathered:** 2026-11-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing pytest suite (9689 tests, about 30 minutes serial) give results in minutes: a quick parallel run that fits the GSD test gate (600 s), and a full parallel run in at most half the measured serial baseline with exactly the serial run's pass and skip counts, ten times in a row. Covers TEST-04..TEST-09. No application behaviour changes; only the test harness, pytest configuration, dev dependencies and the docs that describe how to run tests. Library-folder work (ROOT), the repo split and CI belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### New test dependencies
- Add exactly `pytest-xdist==3.8.0` and `pytest-timeout==2.4.0` to `requirements-dev.txt` (dev-only); do not add `filelock` — the once-per-run git-template lock uses the standard library (an exclusive-create lock file in the shared base temp folder), in line with "stdlib unless clearly justified". pytest-timeout 2.5.0 was yanked (2026-08-16) and must not be used. Owner approved the three packages (pytest-xdist 3.8.0, pytest-timeout 2.4.0, transitive execnet 2.1.2, all pytest-dev projects) on 2026-11-22 during plan-phase, answering plan 14-01 Task 1's package checkpoint. — **Reversibility:** costly — pinned dev dependencies are installed into both checkouts' venvs and referenced by pytest config, CI and docs later in the milestone.

### Decided autonomously
- [Parallelism] Q: "Worker count and distribution mode" → Selected: "Measure -n 4/6/8 with --dist loadfile and --dist worksteal on the full suite, keep the fastest setting that gives ten identical full runs, and record it in pyproject addopts" — one addopts value.
- [Parallelism] Q: "Per-test timeout" → Selected: "pytest-timeout with timeout_method thread (Windows has no signal method) and a 300 s default; the few known-long tests get an explicit longer timeout marker; a timeout names the test" — config value plus markers.
- [Markers] Q: "What counts as slow" → Selected: "Tests that build real git repos or submodules, the Würth corpus/perf tests and kicad-cli tests, chosen from a --durations measurement rather than by guessing; registered under strict markers" — a marker on test functions or modules.
- [Isolation] Q: "Real user state under parallel workers" → Selected: "An autouse fixture redirects APPDATA, LOCALAPPDATA, HOME/USERPROFILE and the QSettings ini path to a per-test temp folder and clears KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR; tests that need a value set it themselves" — test-only fixture.
- [Isolation] Q: "Git template fixtures under xdist" → Selected: "Build each gitfixtures template once per run in the per-run base temp root (tmp_path_factory.getbasetemp().parent inside an xdist worker, getbasetemp() on the controller and with -n 0, which is the same per-run folder), under the stdlib lock, reuse it from every worker, and remove it at the end of the session; the leaking tempfile.mkdtemp templates are fixed" — local change in tests/gitfixtures.py; wording amended 2026-11-22 after plan check 3 so a shared folder never lands directly under pytest-of-<user>
- [Isolation] Q: "Live Custom/ guard under xdist" → Selected: "Keep _live_custom_untouched session-scoped so it runs in every worker; any worker that writes the live Custom/ fails the run, naming the paths" — mechanism unchanged.
- [Measurement] Q: "Baseline" → Selected: "One serial full run with --durations=50 before any change, results recorded in the phase folder; the SUMMARY reports before/after wall times for the quick and full runs" — documentation only.

### Claude's Discretion
- What bare `pytest` runs (owner said "You decide"): bare `pytest` becomes the quick parallel run (xdist workers, `-m "not slow"` via addopts), so it fits the GSD test gate's 600 s as is; the full run is one explicit, documented command (for example `pytest -m ""` or a small script) used at phase end, by the verifier and for the ten-run equality check. The README/CLAUDE.md test instructions name both commands. If the planner finds a cleaner way to make the full run explicit (e.g. a `--full` option in conftest), that is fine as long as bare `pytest` stays the quick run.
- Orchestrator decisions after research (2026-11-22, reversible, made under the owner's "You decide" for this phase and the approved success criterion 4 "no test reads or writes the real settings.ini, %APPDATA% or KiCad config"):
  - Strict reading of success criterion 4: in a default run (quick or `--full`) no test reads the real KiCad config. The 10 `local_kicad` tests become opt-in: they are skipped with a stated reason unless the environment variable `KICAD_TEST_REAL_CONFIG=1` is set, and the real-table paths are not read at collection time without it. kicad-cli subprocesses get `KICAD_CONFIG_HOME` pointed at a per-test temp folder by the isolation fixture (verify with the `kicad_cli` tests before and after).
  - Run-level user-state guard: a change to the app's own state (`%APPDATA%/KiCadExtLibManager` settings and scan cache, `%LOCALAPPDATA%/KiCadExtLibManager` backups) fails the run; a change to KiCad's own config files is reported as a warning only, because the owner may use KiCad during a long run.
  - The dev plugins are installed into this worktree's `env/` (the venv the GSD gate's bare `python` resolves to in this session). The main checkout's venv is the app's runtime venv and gets `pip install -r requirements-dev.txt` only when tests are run there; the README says so. "Both checkouts' venvs" in the dependency decision's rationale describes where the pins may end up, not an install step of this phase.
  - TEST-05 contingency: if the best matrix setting misses "at most half the serial baseline", the orchestrator tries the levers named in research (a template per `(populate, autocrlf)`, a Defender exclusion of the pytest base temp) once and re-measures; if the bound is still missed, TEST-05 is reported not met and goes to gap closure, never silently passed.
  - GSD's own config (`workflow.test_command`, `test_gate_timeout`) is not changed in this phase.
  - Moving `.planning/todos/pending/2026-11-13-speed-up-full-test-suite.md` to `todos/done/` is part of the last plan.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` already holds `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`, `addopts = "-ra --strict-markers"`, `qt_api = "pyside6"`, markers `wurth`, `local_kicad`, `kicad_cli`. New markers (`slow`, timeouts) go here.
- `requirements-dev.txt`: `-r requirements.txt`, `pytest==9.1.1`, `pytest-qt==4.5.0`; `requirements.txt`: `PySide6==6.12.0`.
- `tests/gitfixtures.py`: `_templates: dict[bool, Path]` cache built with `tempfile.mkdtemp(prefix="gitfixture_template_")` (line ~149-158), `make_superproject`, `make_worktree` — the expensive real-git builders (7-15 s per commit-step test).
- `tests/conftest.py`: forces `QT_QPA_PLATFORM=offscreen`; `pytest_runtest_teardown` wrapper joins widget QThreads; autouse `_desktop_screen_area`; fixtures `repo_root`, `synthetic_custom`, `atomic_custom`, `ul_package`, `kicad_cli_path`, `real_tools`, `snapshot`; session autouse `_live_custom_untouched` (`customfixtures.guard_custom`).

### Established Patterns
- About 19 places set APPDATA or call QSettings.setPath per test file (e.g. test_main_window*.py, test_kicad_setup.py, test_settings_import.py) — isolation is per file today, not global; the new autouse fixture must not break those that set their own values.
- Known slow spots: tests/test_commit_plan.py + tests/test_commit_step.py about 6.5 min for 167 tests (real git repos and submodules); the Würth corpus parse budget test about 1 min; Qt window tests that build the full main or migration window per test.
- Research measured xdist 3.8.0 green on 266 tests at -n 8 here, with git contention (an 8 s test took up to 14 s); `-n auto` is not recommended.

### Integration Points
- GSD post-merge test gate runs bare pytest with a 600 s budget (workflow.test_gate_timeout default) — making bare pytest the quick run makes the gate fit.
- Docs that describe running tests: CLAUDE.md, README.md (and `.planning/codebase/TESTING.md` if present).
- The memory note on running the full suite (scratchpad bash script + Monitor, exit-code file) applies to the baseline and to the ten-run check.

</code_context>

<specifics>
## Specific Ideas

- Follow the agreed approach from `.planning/todos/pending/2026-11-13-speed-up-full-test-suite.md` (resolves_phase 14): measure with --durations, parallelise with pytest-xdist, add a slow marker, share the expensive git fixtures; move the todo to done when the phase closes.
- Research: `.planning/research/STACK.md` (xdist/timeout versions, -n 6..8), `.planning/research/PITFALLS.md` (xdist pitfalls 2-7: per-worker session fixtures, shared real state, xdist_group for kicad-cli and Würth perf tests, short --basetemp for Windows path length, duration noise — three runs, discard the first).
- Executors must not start an extra full-suite run as "diligence"; the orchestrator runs the full suite with an explicit long budget.

</specifics>

<deferred>
## Deferred Ideas

- Running the suite in GitHub Actions CI on Windows — belongs to Phase 16 (public tool repo) / Phase 21 (release workflow).

</deferred>
