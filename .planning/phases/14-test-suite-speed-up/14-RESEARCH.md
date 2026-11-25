# Phase 14: Test Suite Speed-Up - Research

**Researched:** 2026-11-22
**Domain:** pytest harness (pytest 9.1.1 + pytest-qt 4.5.0 + pytest-xdist 3.8.0 + pytest-timeout 2.4.0) on Windows 11, CPython 3.14.4, PySide6 6.12.0, real `git` 2.49.0 subprocess fixtures
**Confidence:** HIGH for mechanics (each one was run here in a scratch project or on the real suite); MEDIUM for final timings (the serial baseline and the parallel full runs are still to be measured by the phase itself)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### New test dependencies
- Add exactly `pytest-xdist==3.8.0` and `pytest-timeout==2.4.0` to `requirements-dev.txt` (dev-only); do not add `filelock` — the once-per-run git-template lock uses the standard library (an exclusive-create lock file in the shared base temp folder), in line with "stdlib unless clearly justified". pytest-timeout 2.5.0 was yanked (2026-08-16) and must not be used. — **Reversibility:** costly — pinned dev dependencies are installed into both checkouts' venvs and referenced by pytest config, CI and docs later in the milestone.

### Decided autonomously
- [Parallelism] Q: "Worker count and distribution mode" → Selected: "Measure -n 4/6/8 with --dist loadfile and --dist worksteal on the full suite, keep the fastest setting that gives ten identical full runs, and record it in pyproject addopts" — one addopts value.
- [Parallelism] Q: "Per-test timeout" → Selected: "pytest-timeout with timeout_method thread (Windows has no signal method) and a 300 s default; the few known-long tests get an explicit longer timeout marker; a timeout names the test" — config value plus markers.
- [Markers] Q: "What counts as slow" → Selected: "Tests that build real git repos or submodules, the Würth corpus/perf tests and kicad-cli tests, chosen from a --durations measurement rather than by guessing; registered under strict markers" — a marker on test functions or modules.
- [Isolation] Q: "Real user state under parallel workers" → Selected: "An autouse fixture redirects APPDATA, LOCALAPPDATA, HOME/USERPROFILE and the QSettings ini path to a per-test temp folder and clears KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR; tests that need a value set it themselves" — test-only fixture.
- [Isolation] Q: "Git template fixtures under xdist" → Selected: "Build each gitfixtures template once per run in tmp_path_factory.getbasetemp().parent under the stdlib lock, reuse it from every worker, and remove it at the end of the session; the leaking tempfile.mkdtemp templates are fixed" — local change in tests/gitfixtures.py.
- [Isolation] Q: "Live Custom/ guard under xdist" → Selected: "Keep _live_custom_untouched session-scoped so it runs in every worker; any worker that writes the live Custom/ fails the run, naming the paths" — mechanism unchanged.
- [Measurement] Q: "Baseline" → Selected: "One serial full run with --durations=50 before any change, results recorded in the phase folder; the SUMMARY reports before/after wall times for the quick and full runs" — documentation only.

### Claude's Discretion
- What bare `pytest` runs (owner said "You decide"): bare `pytest` becomes the quick parallel run (xdist workers, `-m "not slow"` via addopts), so it fits the GSD test gate's 600 s as is; the full run is one explicit, documented command (for example `pytest -m ""` or a small script) used at phase end, by the verifier and for the ten-run equality check. The README/CLAUDE.md test instructions name both commands. If the planner finds a cleaner way to make the full run explicit (e.g. a `--full` option in conftest), that is fine as long as bare `pytest` stays the quick run.

### Deferred Ideas (OUT OF SCOPE)
- Running the suite in GitHub Actions CI on Windows — belongs to Phase 16 (public tool repo) / Phase 21 (release workflow).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-04 | Quick parallel run (`-m "not slow"`) under 10 minutes so it fits the GSD gate | Quick set is about 3400 of 11668 tests; measured module timings put its serial cost far below the git/Würth/kicad-cli set; gate command and its `-x`/exit-code-5 behaviour documented (sections "Standard Stack", "Common Pitfalls" 8-9) |
| TEST-05 | Full suite parallel in at most half the serial baseline | Measured speed-ups on this machine: git modules 266 s -> 67 s at `-n 6` (3.97x), kicad-cli 70 s -> 25 s; Würth corpus (379 s serial) is the critical path under `loadfile` so `worksteal`/`loadgroup` must be measured |
| TEST-06 | Slow tests carry `slow`; strict markers stay on | Inventory of git / Würth / kicad-cli tests; marker auto-mapping verified; runtime tripwire design makes the git marking exhaustive |
| TEST-07 | Workers isolated: git templates once per run, no real settings/APPDATA/KiCad config, live-collection guard still fails | Template-under-lock design, isolation fixture design verified for fixture ordering, guard verified under xdist (fails the run, names the path) |
| TEST-08 | Same pass/skip counts as serial, ten times in a row | Count-compare protocol, count drift risks (corpus size, local_kicad, skips), ten-run script |
| TEST-09 | Hung test fails with a timeout naming it | Verified on the real repo conftest + pytest-qt: under xdist the failure reads `worker 'gwN' crashed while running '<nodeid>'` |
</phase_requirements>

## Summary

The suite is far larger than the numbers in CONTEXT/ROADMAP: **11668 tests are collected today, not 9689** [VERIFIED: `pytest --collect-only -q` this session: "11668 tests collected"]. 8018 of them are `wurth`-marked (the per-file Würth round trip, 8017 in `tests/test_roundtrip_corpus.py` plus 1 in `tests/test_scanner_issues.py`), 36 are `kicad_cli`, 10 are `local_kicad`, and about 190 test functions reach the real-git builders (`make_superproject` / `make_worktree`). The Würth corpus is 8016 files in both checkouts [VERIFIED: `find` count in the worktree and in `<main-checkout>`], against 6034 files in the 2026-10-25 comment in `tests/test_roundtrip_corpus.py`. So the baseline must be re-measured, and pass/skip counts only compare within one checkout.

Everything the phase needs works on this machine, measured with the two plugins installed into a scratch folder (nothing was installed into `env/`): xdist 3.8.0 and pytest-timeout 2.4.0 load under pytest 9.1.1 + pytest-qt 4.5.0 on Python 3.14.4; `-n`/`-m`/`--dist` in `addopts` and `-m ""`/`-n 0` overrides behave as expected; `--dist` modes were compared; the live-Custom guard fires in every worker and fails the run; a hung test under the thread timeout method fails with a message naming the test. Four things the CONTEXT does not mention and the planner must handle: (1) `xdist_group` has **no effect** unless `--dist loadgroup` is used, so with `worksteal` it is silently ignored; (2) `-m ""` is dropped by Windows PowerShell 5.1, so a `--full` option (or `-m "slow or not slow"`) is the safe explicit full-run spelling; (3) `test_wurth_corpus_parse_budget` has a computed budget of 400 s now (`max(60.0, 0.05 x 8016)`), which is longer than the 300 s default timeout, so it needs an explicit longer `timeout` marker; (4) the GSD gate default command is `python -m pytest -x -q --tb=short 2>&1 || uv run python -m pytest -x -q --tb=short`, and a scoped regression run whose files are all `slow` exits with code 5 (nothing collected).

**Primary recommendation:** Do the serial `--durations` baseline first (bare `pytest`, before any file changes). Then add the two pinned plugins, put `-n 6 --dist worksteal -m "not slow"` (final values from measurement), `timeout = 300`, `timeout_method = "thread"` and the `slow` marker in `pyproject.toml`; add a `--full` option in `tests/conftest.py`; build git templates once per run under a stdlib exclusive-create lock with a ".done" marker file (no directory rename); add one autouse isolation fixture that coexists with the 19 per-file ones; and enforce the `slow` marker with a runtime tripwire in `tests/gitfixtures.py` plus a collection-based audit test.

## Project Constraints (from CLAUDE.md)

Extracted from `./CLAUDE.md` and `./.claude/CLAUDE.md` (same authority as locked decisions):

- **Stdlib only unless clearly justified**; PySide6 is the only runtime dependency. Dev-only plugins are limited to the two locked ones (no `filelock`). [CITED: .claude/CLAUDE.md "Constraints - Tech stack"]
- **Platform:** Windows 11 primary, standard CPython (not MSYS2), venv `env/` built with `py -m venv env`; keep existing cross-platform branches working (the isolation fixture must set the POSIX variables too: `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`). [CITED: CLAUDE.md "Python Environment"]
- **No application behaviour changes** in this phase (CONTEXT domain); only tests, pytest config, dev dependencies and docs.
- **Tests must never write the live `Custom/`**; a session guard fails the run naming the paths. [CITED: tests/README.md "The rule: never touch the live Custom/"]
- **Do not copy real libraries into fixtures** (Custom/ and WurthElektronik/ are read only in tests). [CITED: .planning/codebase/TESTING.md]
- **Git commits need explicit confirmation; commit `Custom` submodule changes separately** (no submodule change is expected here).
- **Code style:** 4-space indent, double quotes, f-strings, trailing commas, type hints `X | None`, section comments one line above the code, `_on_` handler naming, Qt enums fully qualified. Test helper modules are plain modules (`tests/*fixtures.py`) imported by name (`from gitfixtures import ...`) because `tests/` is on `sys.path` via rootdir conftest.
- **GSD workflow:** edits go through a GSD command; executors must not start an extra full-suite run (orchestrator runs it with a long budget). [CITED: CONTEXT.md `<specifics>`; memory note "Full test suite duration" and "Executor context bundle"]
- **Docs that must name both commands:** `CLAUDE.md`, `README.md`, `tests/README.md` (and `.planning/codebase/TESTING.md` is stale: it still says "No automated tests exist"; leave it or fix in one line).

## Architectural Responsibility Map

This is a test-harness phase; the "tiers" are the layers of the pytest run, not the app.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Which tests a bare `pytest` runs (quick vs full) | pytest config (`pyproject.toml` addopts) | `tests/conftest.py` (`--full` option) | Config selects the default; conftest gives the shell-safe override |
| Worker count / distribution | pytest config (`-n`, `--dist`) | — | One addopts value, measured |
| Hang protection | pytest-timeout (`timeout`, `timeout_method` in config) | `@pytest.mark.timeout(N)` on known-long tests | Thread method is the only method on Windows |
| Slow classification | Test modules / functions (`pytestmark`, `@pytest.mark.slow`) | `tests/conftest.py` hook (wurth/kicad_cli -> slow) and runtime tripwire in `tests/gitfixtures.py` | Marker is data on the test; hook and tripwire keep it complete |
| Git template built once | `tests/gitfixtures.py` (lock + marker file) | `tests/conftest.py` (session fixture gives root path; controller cleanup hook) | Fixture-module owns the builder, conftest owns lifecycle |
| Isolation of user state | `tests/conftest.py` autouse fixture (env + QSettings) | per-file `_isolated_settings` fixtures (kept) | Global default, local override stays valid |
| Live-state guards | `tests/customfixtures.guard_custom` (existing) + new user-state guard in conftest | — | Run-level, not test-level |
| Proof of the above | Meta-tests under `tests/` (subprocess pytest runs) | Orchestrator-run ten-run script | Meta-tests are quick; the ten-run check is long |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.1.1 (already pinned) | runner | Existing pin in `requirements-dev.txt` [VERIFIED: requirements-dev.txt:2 "pytest==9.1.1"] |
| pytest-qt | 4.5.0 (already pinned) | `qtbot`, widget teardown | Existing pin [VERIFIED: requirements-dev.txt:3 "pytest-qt==4.5.0"] |
| pytest-xdist | 3.8.0 | parallel workers (`-n`, `--dist`) | Locked by CONTEXT; latest on PyPI [VERIFIED: `pip index versions pytest-xdist` -> "pytest-xdist (3.8.0)"]; ran here under pytest 9.1.1 on Python 3.14.4 [VERIFIED: scratch runs, header "plugins: timeout-2.4.0, xdist-3.8.0, qt-4.5.0"] |
| pytest-timeout | 2.4.0 | per-test timeout | Locked by CONTEXT; latest visible on PyPI (2.5.0 yanked) [VERIFIED: `pip index versions pytest-timeout` -> "pytest-timeout (2.4.0)", 2.5.0 absent; yank date per CONTEXT/STACK.md] |
| execnet | 2.1.2 (transitive of xdist, not pinned by us) | xdist transport | [VERIFIED: `pip index versions execnet` -> "execnet (2.1.2)"] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `os`, `time`, `shutil`, `pathlib` | 3.14 | exclusive-create lock, polling, rmtree | git template lock (replaces `filelock`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib lock | `filelock` | Locked out by CONTEXT (stdlib unless justified) |
| `--full` conftest option | `-m ""` / `-m "slow or not slow"` | `-m ""` works in bash and PowerShell 7.7.0 but is **dropped by Windows PowerShell 5.1** [VERIFIED: argv probe: pwsh 7.7.0 -> `['-m', '']`; powershell 5.1.26100.9818 -> `['-m']`]; `-m "slow or not slow"` is safe everywhere but reads oddly |
| `--dist worksteal` | `loadgroup`, `loadfile` | See "Distribution mode" below: only `loadgroup` honours `xdist_group`; `loadfile` makes the 8074-test Würth module a single-worker critical path |

**Installation (requirements-dev.txt after the change):**
```bash
# requirements-dev.txt
-r requirements.txt
pytest==9.1.1
pytest-qt==4.5.0
pytest-xdist==3.8.0
pytest-timeout==2.4.0
```
Install into every venv that runs the suite: `env/` of this worktree and the main checkout's venv (`.venv/` also exists at the repo root). **Neither plugin is installed in `env/` today** [VERIFIED: `ls env/Lib/site-packages | grep -i -E "pytest|xdist|execnet|timeout"` -> only `_pytest`, `pytest`, `pytest_qt-4.5.0.dist-info`, `pytest-9.1.1.dist-info`]. With `-n 6` in `addopts`, a venv without xdist fails at start with "unrecognized arguments: -n"; document that in the README.

**Version verification:** run `pip index versions` as above on 2026-11-22; the package-legitimacy seam dates: pytest-xdist 2025-07-01, pytest-timeout 2025-05-05, execnet 2025-11-12 (latest-release publish dates reported by the seam).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pytest-xdist 3.8.0 | PyPI | years (latest 2025-07-01) | not exposed by PyPI API (seam: unknown) | github.com/pytest-dev/pytest-xdist | SUS (only reason: `unknown-downloads`) | Locked by owner in CONTEXT; planner: keep the exact pin; the install task cites the CONTEXT lock as the approval (add `checkpoint:human-verify` only if the planner wants an extra gate) |
| pytest-timeout 2.4.0 | PyPI | years (latest 2025-05-05) | not exposed (seam: unknown) | github.com/pytest-dev/pytest-timeout | SUS (only reason: `unknown-downloads`) | Same as above; never use 2.5.0 (yanked) |
| execnet 2.1.2 | PyPI | years (latest 2025-11-12) | not exposed (seam: unknown) | execnet.readthedocs.io | SUS (only reason: `unknown-downloads`) | Transitive of xdist, pulled by pip; not pinned by this phase |

`gsd-tools query package-legitimacy check --ecosystem pypi pytest-xdist pytest-timeout execnet` returned `SUS` for all three with the single reason `unknown-downloads`: the seam gets no weekly-download figure from PyPI, `exists: true`, `deprecated: false`, no postinstall (Python packages have none), source repos under `pytest-dev`. **Packages removed due to SLOP:** none. **Flagged SUS:** all three, for a data-gap reason only. The names came from CONTEXT.md (owner decision) and project research, and `pip index versions` resolved the exact pins.

## Architecture Patterns

### System Architecture Diagram

```
pytest (bare)  --addopts-->  -n 6 --dist worksteal -m "not slow" --timeout=300 (thread)
   |
   |  controller process (xdist)
   |   - pytest_configure: --full => markexpr = ""
   |   - pytest_sessionstart: record real user-state digests (settings dir, backups, KiCad config files)
   |   - spawns N workers, schedules tests (worksteal)
   |   - pytest_sessionfinish: compare digests -> fail run; rmtree git template root (onexc)
   v
worker gw0..gw5 (each: own interpreter, own QApplication, own module state)
   |- session autouse _live_custom_untouched   (digest Custom/ at start, compare at end, per worker)
   |- session autouse sandbox: QSettings.setPath -> session temp (safety net)
   |- function autouse isolation: APPDATA/LOCALAPPDATA/USERPROFILE/HOME/XDG_* -> per-test dir,
   |                              KICAD_LIB_GITHUB/CUSTOM_3DMODEL_DIR removed, QSettings path -> per-test
   |- function autouse _current_item  (tells gitfixtures which test is running; tripwire)
   |- per-file autouse _isolated_settings (19 files; runs AFTER conftest's, re-points to tmp_path/qsettings)
   |
   |- test needing git:  make_superproject(root)
   |       -> _template(autocrlf): shared root = getbasetemp().parent (worker) / getbasetemp() (master)
   |            exists "<name>.done"?  yes -> copytree  (the common path, ~2 s)
   |            no -> os.open(lock, O_CREAT|O_EXCL): winner builds ("<name>/"), writes ".done", removes lock
   |                  losers poll for ".done" until a deadline (< test timeout), then fail with a clear message
   |
   |- hung test -> pytest-timeout thread timer -> dump stacks, os._exit(1)
                    -> xdist: "worker 'gwN' crashed while running '<nodeid>'" -> test FAILED, worker replaced
```

### Recommended Project Structure
```
pyproject.toml                  # addopts, timeout, timeout_method, tmp_path_retention_*, markers += slow
requirements-dev.txt            # + pytest-xdist==3.8.0, pytest-timeout==2.4.0
tests/
├── conftest.py                 # + --full option, slow auto-mapping hook, isolation fixtures, sandbox, controller guards/cleanup
├── gitfixtures.py              # template under lock; tripwire; no tempfile.mkdtemp
├── customfixtures.py           # guard_custom unchanged; (optional) guard_user_state next to it
├── test_markers.py             # NEW: marker audit (collection subprocess, strict-markers proof)
├── test_isolation.py           # NEW: user-state isolation meta-tests + xdist guard + template-once + timeout subprocess runs
└── README.md                   # rewrite "How to run" (stale 18 min / 8 min numbers)
.planning/phases/14-test-suite-speed-up/
├── BASELINE.md                 # serial --durations=50 output, counts, wall time (before any change)
└── ...                         # measurements, ten-run counts
```

### Pattern 1: Config block (values to be fixed by measurement)
**What:** All defaults in `pyproject.toml`; `-n` and `--dist` are the two values the measurement decides.
**When to use:** Always; bare `pytest` is the quick run.
**Example:**
```toml
# Source: scratch run on this machine (pytest 9.1.1, xdist 3.8.0, timeout 2.4.0): single-quoted -m 'not slow' inside addopts is shlex-split correctly
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra --strict-markers -n 6 --dist worksteal -m 'not slow'"
qt_api = "pyside6"
timeout = 300
timeout_method = "thread"
tmp_path_retention_policy = "failed"
tmp_path_retention_count = 1
markers = [
    "wurth: ...", "local_kicad: ...", "kicad_cli: ...",          # existing three stay verbatim
    "slow: real git repositories, the Wurth corpus or kicad-cli; excluded from the quick run, included by --full",
]
```
Current values to keep verbatim: `testpaths = ["tests"]`, `pythonpath = ["."]`, `addopts = "-ra --strict-markers"`, `qt_api = "pyside6"` and the three markers `wurth`, `local_kicad`, `kicad_cli` [VERIFIED: pyproject.toml:1-10]. `xdist_group` and `timeout` markers are registered by the plugins themselves, so `--strict-markers` stays satisfied (`xdist_group` registration: `xdist/plugin.py:263` in the installed 3.8.0 source).

### Pattern 2: `--full` option (shell-safe explicit full run)
**What:** conftest option that clears the default marker expression; works under xdist and serial.
**Example:**
```python
# Source: verified in a scratch project (xdist -n 2 and -n 0, both collect the slow test with --full)
def pytest_addoption(parser):
    parser.addoption("--full", action="store_true", help="run the slow tests too (real git, Wurth corpus, kicad-cli)")


def pytest_configure(config):
    if config.getoption("--full") and config.option.markexpr == "not slow":
        config.option.markexpr = ""
```
Full run: `python -m pytest --full`. Serial reference for the ten-run comparison: `python -m pytest --full -n 0`. Fallback without code: `-m "slow or not slow"`. Verified facts: `-m ""` on the CLI overrides an addopts `-m 'not slow'` (bash) [VERIFIED: scratch run, 2 collected]; `-n 0` runs in-process and `worker_id` is `"master"` [VERIFIED]; an all-deselected selection exits 5 with xdist too [VERIFIED: `-m "slow and not slow"` -> "no tests ran", exit=5].

### Pattern 3: Slow marker mechanics
- **wurth and kicad_cli -> slow automatically**, one hook (verified that an `add_marker` in a `tryfirst` `pytest_collection_modifyitems` is honoured by `-m 'not slow'` and `-m slow`):
```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        if (item.get_closest_marker("wurth") or item.get_closest_marker("kicad_cli")) and not item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.slow)
```
- **git tests explicit:** `pytestmark = pytest.mark.slow` in fully-git modules, `@pytest.mark.slow` on the individual tests in mixed modules (inventory below).
- **Runtime tripwire (makes the git marking exhaustive without guessing):** a function-scoped autouse fixture records `request.node` in `gitfixtures` (module global, reset at teardown); `make_superproject` / `make_worktree` raise `AssertionError("this test builds a real git repository: mark it @pytest.mark.slow")` when the current item has no `slow` marker. Any new unmarked git test then fails the quick run loudly and names itself.

### Pattern 4: Git template once per run (stdlib lock, no directory rename)
**What:** shared root = `tmp_path_factory.getbasetemp().parent` for a worker, `getbasetemp()` itself for `-n 0` (verified layout below). Lock by exclusive create; publish by a `.done` marker file written last, so readers never need a rename (Windows: renaming a freshly written directory tree can fail with WinError 5/32 while Defender scans it).
**Example:**
```python
# tests/gitfixtures.py (sketch; _build, populate_custom, _repos stay as they are)
_root: Path | None = None  # set by the conftest session fixture before any test runs


def set_template_root(root: Path) -> None:
    global _root
    _root = root


def _template(autocrlf: bool) -> Path:
    """A built superproject shared by every worker of this run; the first caller builds it under a lock file."""
    name = "template_crlf" if autocrlf else "template_lf"
    folder, done, lock = _root / name, _root / f"{name}.done", _root / f"{name}.lock"
    _root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _TEMPLATE_WAIT  # keep well below the 300 s test timeout, e.g. 240
    while not done.exists():
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() > deadline:
                raise AssertionError(f"waited {_TEMPLATE_WAIT}s for {lock}; the worker that holds it died, delete it and rerun")
            time.sleep(0.25)
            continue
        try:
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir()
            _build(folder, autocrlf, populate_custom)
            done.write_text("done\n")
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)
    return folder
```
`make_superproject` already re-points every absolute path after `copytree` (`remote.origin.url`, `submodule.Custom.url`, `_local_config`) [VERIFIED: tests/gitfixtures.py:178-185], so a template at a different absolute path is fine. Each build takes several seconds; two variants (`autocrlf` true/false) exist.

**Root and cleanup (conftest):**
```python
@pytest.fixture(scope="session", autouse=True)
def _git_template_root(tmp_path_factory, worker_id):
    base = tmp_path_factory.getbasetemp()
    gitfixtures.set_template_root((base if worker_id == "master" else base.parent) / "git_templates")
```
Cleanup on the controller only (no `workerinput` attribute), after all workers finished:
```python
def pytest_sessionfinish(session):
    if hasattr(session.config, "workerinput"):
        return
    factory = getattr(session.config, "_tmp_path_factory", None)  # exists in 9.1.1; verified at sessionfinish
    if factory is not None:
        shutil.rmtree(factory.getbasetemp() / "git_templates", onexc=_clear_readonly_and_retry)
```
`_clear_readonly_and_retry` must `os.chmod(path, stat.S_IWRITE)` and retry: `.git/objects` files are read-only on Windows (PITFALLS 5). `shutil.rmtree(onexc=...)` needs Python 3.12+; the test venv is 3.14. [VERIFIED layout: scratch run, worker basetemp `...\pytest-of-<user>\pytest-27542\popen-gw1`, controller basetemp `...\pytest-27542`, `-n 0` worker id `master` with basetemp `...\pytest-27543`; with `--basetemp=X`, workers get `X\popen-gw0`.]

### Pattern 5: One isolation fixture that coexists with the 19 per-file ones
**What:** a session fixture makes the whole run safe even if a per-test fixture is bypassed; a function fixture gives every test its own empty user home.
**Coexistence is proven:** a conftest autouse fixture runs before a module-level autouse fixture regardless of name order [VERIFIED: scratch run with adversarial names; order `["conftest", "module"]`]. The 19 per-file `_isolated_settings` fixtures (`QSettings.setPath(... str(tmp_path / "qsettings"))` then `assert tmp_path.resolve() in file_name.parents`) simply re-point the path afterwards; leave them untouched in this phase. Files: `test_checkout_warning.py, test_field_rules.py, test_gate_reasons.py, test_generated_text.py, test_help_dialog.py, test_import_dialog.py, test_install_gate.py, test_main_window.py, test_main_window_chooser.py, test_main_window_import.py, test_main_window_migration.py, test_migration_dialog.py, test_migration_dialog_files.py, test_migration_dialog_run.py, test_migration_draft.py, test_official_footprint.py, test_settings_import.py, test_single_footprint.py, test_suggest_atomic.py` [VERIFIED: `grep -l setPath tests/*.py`, 19 files].
**Example:**
```python
_REAL = {k: os.environ.get(k) for k in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME")}  # captured at conftest import, before any redirect


@pytest.fixture(scope="session", autouse=True)
def _qsettings_sandbox(tmp_path_factory):
    from PySide6.QtCore import QSettings  # one Qt import per worker; the only way to be sure no later QSettings reaches the real ini

    base = tmp_path_factory.mktemp("qsettings_session")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(base))
    yield


@pytest.fixture(autouse=True)
def _isolated_user_state(tmp_path_factory, monkeypatch):
    from PySide6.QtCore import QSettings

    home = tmp_path_factory.mktemp("user")  # outside tmp_path, so tests that list tmp_path see nothing new
    for name, sub in (("APPDATA", "AppData/Roaming"), ("LOCALAPPDATA", "AppData/Local"),
                      ("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share")):
        (home / sub).mkdir(parents=True)
        monkeypatch.setenv(name, str(home / sub))
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(home))
    for name in ("KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "KICAD_CONFIG_HOME", "WE_3DMODEL_DIR"):
        monkeypatch.delenv(name, raising=False)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(home / "qsettings"))
```
Why env **and** `QSettings.setPath`: the app reads `os.environ["APPDATA"]` itself in `find_kicad_config_dir` (`appdata = os.environ.get("APPDATA")`, then `base = Path(appdata) / "kicad"`) [VERIFIED: library_scanner.py:63-67] and `default_backup_dir` uses `LOCALAPPDATA`, but `QSettings` on Windows does not follow the environment, so it needs `setPath` (the per-file fixtures already rely on this). `KICAD_LIB_GITHUB` is not read from the process environment by the app (it comes from KiCad's `kicad_common.json` via `APPDATA`), so clearing the variable is cheap and harmless; redirecting `APPDATA` is what protects the KiCad config [VERIFIED: grep of `kicad_lib_manager` found no `environ`/`getenv` use for `KICAD_LIB_GITHUB`/`CUSTOM_3DMODEL_DIR`]. Tests that need their own value set it after this fixture (their own `monkeypatch.setenv` wins; existing examples: `tests/test_commit_step.py:450-455`, `tests/test_gitops.py:263-265` set `HOME`/`USERPROFILE`/`XDG_CONFIG_HOME` themselves).

### Anti-Patterns to Avoid
- **`tempfile.mkdtemp` for shared fixtures** (today's `_template`): every worker and every run leaks folders. **583 `gitfixture_template_*` folders sit in `%TEMP%` right now** [VERIFIED: `ls -d %TEMP%/gitfixture_template_* | wc -l` -> 583, about 170-700 KB each]. A one-time manual cleanup of those is outside the repo (mention it in the SUMMARY, do not automate deletion of folders the tests did not create this run).
- **Directory rename to publish the template** (Windows WinError 5/32 under Defender); use the `.done` marker.
- **`--basetemp=<fixed path>` in addopts:** pytest wipes it at start, so two runs at once (worktree + main checkout) destroy each other. Offer it only as a documented one-off for path-length trouble.
- **Reading `config._tmp_path_factory` in workers:** use the `tmp_path_factory` fixture there; the private attribute is only for the controller cleanup hook, guarded with `getattr`.
- **`xdist_group` with `worksteal`:** silently ignored (see below).
- **Raising timeouts globally to hide contention.** Mark the few long tests instead.

## Inventory (what is slow, what touches real state)

### Counts [VERIFIED: `pytest --collect-only -q` with `-m` this session]
| Set | Tests |
|-----|------:|
| All collected | 11668 |
| `wurth` | 8018 (8017 in `tests/test_roundtrip_corpus.py`, 1 in `tests/test_scanner_issues.py:282`) |
| `kicad_cli` | 36 |
| `local_kicad` | 10 (disjoint from the two above: `-m "wurth or kicad_cli or local_kicad"` = 8064) |
| everything else | about 3600, of which about 190 reach the git builders |

### Git-builder tests (candidates for `slow`; coarse AST closure over `make_superproject` / `make_worktree` and the helpers that call them; test functions, parametrisation adds a few)
| Module | Test functions reaching the builders | Module total | Measured serial |
|--------|-----:|-----:|-----------------|
| `tests/test_commit_step.py` | 97 | 107 defs / 123 tests | about 295 s (project research STACK.md; 123 passed) |
| `tests/test_commit_gate.py` + `test_commit_gate_panel.py` | 26 + 2 | 32 tests | 147 s (4.6 s per test; slowest 10.2 s) |
| `tests/test_scan_changes.py` | 23 | 26 | 119 s (slowest 14.3 s) |
| `tests/test_migration_precheck.py` + `test_commit_deletions.py` | 7 + 3 | 15 | 24 s |
| `tests/test_migration_commit.py` / `test_migration_full.py` | 2 / 1 | — | 7.6 s, 5.3 s / 12.1 s (slowest tests) |
| `tests/test_import_dialog.py` | 3 of 255 | 255 | 143 s total, the 3 git tests 8.8 s, 7.3 s, 4.0 s |
| `tests/test_gitops.py` | 4 of 40 | 40 | 26 s total (git tests 5.6 s, 3.6 s, ~1 s) |
| `tests/test_scan_cache.py` / `test_rescan_library.py` | 2 / 3 | 57 / 16 | each git test 4.5-5 s |

Measured with targeted serial runs, one module group at a time, on this machine; `tests/test_commit_plan.py` does **not** use the git fixtures (it passed with `test_install_plan`, `test_install_e2e`, `test_scan_cache` as 267 passed, 1 skipped in 67 s together). The todo's "6.5 min for 167 tests (commit_plan + commit_step)" is therefore mostly `test_commit_step.py`.

Other helper callers (not test modules): `tests/migrationfixtures.py:447` calls `make_superproject(root, populate=_populate, **kwargs)`. Tests whose `populate` is not the default (`write_atomic_files`, `_populate`) bypass the template and run the whole `_build` (7-15 s) every time; **an optional further lever** is a template keyed by `(populate, autocrlf)` for deterministic populates (about 12 tests: `test_scan_cache` x2, `test_rescan_library`, `test_migration_commit` x2, `test_commit_gate_panel`, `migrationfixtures`); not required by any TEST id, skip unless the measurement shows these dominate.

### Würth corpus (all `wurth`)
- `test_roundtrip_wurth_file[...]` x 8017 plus `test_wurth_corpus_parse_budget`; module `tests/test_roundtrip_corpus.py` ran 8074 passed in **378.65 s serial** (`--durations`: `test_wurth_corpus_parse_budget` 45.89 s; the slowest single file 7.97 s `Connector_Wurth_WR-TBL.kicad_sym`).
- `test_wurth_corpus_parse_budget` asserts `elapsed < budget` with `budget = max(60.0, _WURTH_PARSE_BUDGET_PER_FILE * len(files))`, `_WURTH_PARSE_BUDGET_PER_FILE = 0.05`; with 8016 files that is **400.8 s**, longer than the 300 s default timeout. It needs `@pytest.mark.timeout(600)` (or higher) [VERIFIED: tests/test_roundtrip_corpus.py:244-258 read this session; file count 8016 from `find`].
- Collection is deterministic across workers (parameter ids come from sorted file lists): a 4-worker run over the module's collection passed (57 passed in 7.3 s, `-k "repo_owned or ul_zip or corpus_sources or zip_member or local_kicad"`), so xdist's identical-collection requirement holds for the 11668-item set [VERIFIED].

### kicad-cli tests (`kicad_cli`, 36 tests; 11 files use the markers)
`tests/test_atomic_scan.py:253`, `test_customfixtures.py:200`, `test_generated_text.py:612`, `test_install_e2e.py:484,585,598`, `test_install_plan.py:652,844,1284,1362`, `test_installfixtures.py:212`, `test_kicad_cli.py:575,588,599`, `test_kicad_files_write.py:724,829`, `test_migration_families.py:327`, `test_official_footprint.py:477`, `test_real_vendor_samples.py:355`, `test_vendor_install.py:541`. Serial **69.7 s**, `-n 6 --dist worksteal` **25.5 s with all 36 passing**: parallel real `kicad-cli.exe` runs (KiCad 10.0 at `C:/Program Files/KiCad/10.0/bin/kicad-cli.exe`) did not collide on this machine in one run [VERIFIED: scratch+repo runs]. The app creates a fresh `tempfile.mkdtemp(prefix=_TEMP_PREFIX)` per call (`kicad_cli.py:155`, `:241`), so there is no shared output folder. Note `test_uat_scratch_install` (`tests/test_install_e2e.py:617`) uses `real_tools` (so kicad-cli) but is skipped without `KICAD_IMPORT_UAT_DIR`; the conftest auto-mapping keys on the `kicad_cli` marker only, so add the marker or accept it (it skips anyway).

### Qt window tests (not slow)
`test_main_window*.py` 161 tests ran in **14.3 s** serial; `test_import_dialog.py` (255) 143 s of which about 20 s are 3 git tests; migration dialog modules (53 tests incl. migration commit/full) 36 s. The todo's "Qt window tests that build the full main or migration window per test" are cheap here; the cost is git, not windows. 26 modules use `qtbot`.

### Real user state touched by tests (APPDATA / HOME / QSettings / KiCad config)
| Channel | App code | Test behaviour today | After the autouse fixture |
|---------|----------|----------------------|---------------------------|
| `QSettings` ini (`settings.get_settings()` = `QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, APP_ORG, APP_NAME)`; `scan_cache_file` / `migration_draft_file` derive from `Path(get_settings().fileName()).parent`) | 13 call sites of `get_settings()` [VERIFIED: grep count; settings.py:18-26 read] | 19 test files isolate per file with `setPath`; **all other modules that reach settings code are unprotected** | covered globally |
| `%APPDATA%/kicad` via `find_kicad_config_dir()` (reads `os.environ["APPDATA"]`) | `library_scanner.py:60-73` | tests pass `base=` or patch `main_window.CHECKOUT_CONFIG_BASE` (default `None` means the real `%APPDATA%` config, `main_window.py:52-54`) | `APPDATA` redirected: unpatched calls see an empty tree |
| `%LOCALAPPDATA%/KiCadExtLibManager/backups` via `fsutil.default_backup_dir` | `fsutil.py:225-243` | tests pass `environ=`/`platform=` or `ATOMIC_BACKUP_ROOT` / `IMPORT_BACKUP_ROOT` seams | redirected |
| `Path.home()` (`import_dialog.py:218` Downloads, `:1434`, `migration_dialog.py:170`) | Windows: `USERPROFILE` | some tests set `HOME`/`USERPROFILE` themselves | redirected |
| `tests/test_roundtrip_corpus.py:_local_table_params` | reads `%APPDATA%/kicad/<ver>/{sym-lib-table,fp-lib-table,design-block-lib-table}` **at collection time** and in `test_roundtrip_local_kicad_table` with `path.read_bytes()` (read only) | the only tests that deliberately read real KiCad config; marked `local_kicad` | **not covered by the fixture (path is computed at import); see Open Question 1** |
| `kicad-cli` process | inherits env; Windows apps normally resolve `%APPDATA%` through the shell API, not the variable [ASSUMED] | passes today | confirm by running `-m kicad_cli` before and after the fixture (36 tests, 70 s serial) |
| Git global/system config | `gitops._env` strips `GIT_CONFIG_GLOBAL` / `GIT_CONFIG_NOSYSTEM` from the app's child env | fixtures write repo-local identity, signing, autocrlf; some tests set `HOME` | redirecting `HOME`/`USERPROFILE` removes the owner's `~/.gitconfig` from every app-run git call too (more hermetic); system gitconfig still applies |

KiCad variables: the app does not read `KICAD_LIB_GITHUB` / `CUSTOM_3DMODEL_DIR` from the environment (see above), they live in `kicad_common.json`. Qt standard paths (`QStandardPaths`) are only used for the Downloads location (`import_dialog.py:215`), which is already seamed.

### Module-level state / shared files under parallel workers [VERIFIED by grep + reading]
- Per-process caches: `kicad_cli._cache` (cleared by 4 fixtures), `scan_cache._code_signature` (`functools.lru_cache`, `scan_cache.py:257`), `clifixtures.located_kicad_cli` (`functools.cache`, probes `kicad-cli version` once per worker, about 3 s x N workers), `main_window.REPO_ROOT`/seams patched by `monkeypatch`. All per-worker, hence unaffected by distribution but each worker repeats them.
- `os.chdir`: only via `monkeypatch.chdir` (4 files); `tempfile.tempdir` only via `monkeypatch.setattr` to a folder under tmp (`test_package_zip`, `test_model_source`, `test_model_attach`, `test_real_vendor_samples`). No sockets, no fixed ports, no fixed temp paths, no shared output files; `snapshot` is a pure digest function; no test writes under `REPO_ROOT` except via `tmp_path`.
- **Subprocess pytest** in `tests/test_customfixtures.py:331` runs `[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(run_dir)]` with `run_dir` under `tmp_path` and no `pyproject.toml` above it, so repo `addopts` (`-n 6`) do not leak in. Keep any new meta-test subprocess outside the repo tree or pass `-n 0 -o addopts=""` explicitly; **do not put `--basetemp` inside the repo** (the repo `pyproject.toml` would then apply to the subprocess).
- Timing-sensitive assertions (can flake under contention; watch in the ten-run check): `tests/test_sexpr.py:228` (`elapsed < 3.0`), `tests/test_install_verify.py:512-520` (`elapsed < 5`, reads the real KiCad stock symbols), `tests/test_import_dialog.py:3752-3754` (`< 5`), `tests/test_locate_text_caps.py:364` (`_END_TO_END_SECONDS = 30`), Würth budget (above). A targeted run of the sexpr, locate_text_caps and install_verify cases took 25.5 s with no failures; headroom is at least 5x on the ones measured.

### Live-Custom guard under xdist [VERIFIED: scratch run with the repo's `guard_custom`]
`_live_custom_untouched` (session, autouse: `yield from guard_custom(REPO_ROOT / "Custom")`, `tests/conftest.py:176-184`) runs once per worker. With a test that appended to a watched file, `-n 2` produced `4 passed, 2 errors`, `exit=1`, and both workers reported `the test run changed the live Custom/ folder: Symbols/a.kicad_sym` as an error at teardown of whichever test ended last on that worker. No false positive is possible from honest concurrent workers because nobody writes `Custom/`; the cost is one 20 MB digest per worker at start and end. The failure names the path but not the offending test (same as serial). `tests/test_customfixtures.py::test_guard_failure_fails_the_run` covers serial only; add an `-n 2` variant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel test execution | a custom process pool / sharding script | `pytest-xdist` `-n`, `--dist worksteal` | Handles worker crash replacement, collection equality checks, reporting |
| Per-test timeout | a watchdog thread in conftest | `pytest-timeout` (thread method, `timeout`, `@pytest.mark.timeout`) | Stack dump + `os._exit`, per-test marker override |
| One-time shared setup across workers | module globals, `mkdtemp` per worker | `tmp_path_factory` + `worker_id` + exclusive-create lock + `.done` marker | Module state is per process; this is the documented xdist pattern, with stdlib only |
| Quick vs full selection | a custom runner script | markers + `addopts -m 'not slow'` + `--full` | `--strict-markers` already enforces registration |
| Removing read-only git trees on Windows | `shutil.rmtree` bare | `shutil.rmtree(onexc=...)` clearing `S_IWRITE` and retrying | `.git/objects` is read-only; Defender holds new files briefly |
| Counting passes/skips for the ten-run check | parsing console dots | the final `-q` summary line (`N passed, M skipped in T s`) or `--junitxml` | Stable, one line per run |

**Key insight:** the cost is git subprocesses and file churn on Windows, not Python; the wins are (1) skipping the git/Würth/kicad-cli set in the default run, (2) running the rest in parallel, (3) not rebuilding templates per worker. Do not try to optimise the application.

## Common Pitfalls

### Pitfall 1: `xdist_group` is ignored under `worksteal`
**What goes wrong:** marking kicad-cli or Würth tests `xdist_group` has no effect with `--dist worksteal`/`load`/`loadfile`.
**Why:** only `LoadGroupScheduling` (`--dist loadgroup`) reads it (`xdist/remote.py:241-245` appends `@group` to node ids only when `loadgroup` is set) [VERIFIED: source of the installed 3.8.0]. `loadgroup` derives from `LoadScopeScheduling` and treats every ungrouped test as its own scope.
**How to avoid:** the kicad-cli tests ran fine in parallel (36 passed, 25.5 s at `-n 6`), so groups are not required by evidence; if the measurement matrix includes `loadgroup`, add groups only for tests that fail under contention. Otherwise register nothing and skip `xdist_group`. Add `--dist loadgroup` to the measurement matrix next to `worksteal` and `loadfile`.

### Pitfall 2: `-m ""` disappears in Windows PowerShell 5.1
**What goes wrong:** `pytest -m ""` becomes `pytest -m` and swallows the next argument or errors. [VERIFIED: argv probe with `powershell` 5.1.26100.9818 -> `['-m']`; `pwsh` 7.7.0 -> `['-m', '']`]
**How to avoid:** document `python -m pytest --full` (conftest option, verified) and `-m "slow or not slow"` as the portable fallback.

### Pitfall 3: Timeout under xdist loses the stack dump and the word "timeout"
**What goes wrong:** the thread method kills the worker with `os._exit(1)`; the controller reports `FAILED tests/test_gitops.py::test_commit_with_identity_from_environment_only` with `worker 'gw0' crashed while running '<nodeid>'`. pytest-timeout's own "Timeout" banner and stacks appear only serially (`-n 0`). [VERIFIED on the real repo (conftest + pytest-qt): `--timeout=2` on a 5.6 s git test and `--timeout=0.1` on two Qt window tests -> both "crashed while running '<nodeid>'", each run about 3-5 s.]
**Why it matters:** the requirement "fails with a timeout that names it" is met by the nodeid in the failure, but the message says "crashed". State that in the docs; for diagnosis rerun the test with `-n 0 --timeout=N`.
**Also:** the crashed worker's child processes (git, kicad-cli) may be orphaned, its tmp folders stay, and xdist caps restarts (`--max-worker-restart`, default 4 x workers). A builder that dies holding the git-template lock leaves the lock behind; the polling deadline (below the 300 s timeout) turns that into a clear failure rather than a second timeout.

### Pitfall 4: First-test absorbs the template build and times out
**What goes wrong:** the fixture time of a test counts toward its timeout (`timeout_func_only` defaults to false), so the test that builds the template plus the ones waiting on the lock spend 10-30 s under contention in setup.
**How to avoid:** lock-wait deadline of about 240 s (< 300 s), builds are about 7-15 s each, two variants; do not add a global `timeout` below 120 s.

### Pitfall 5: Contention makes git tests 2-3x slower per test, speed-up is about 4x at `-n 6`, not 6x
**Measured:** `test_scan_changes.py` + `test_commit_gate.py` + `test_commit_gate_panel.py` (58 tests) 266 s serial -> **67 s at `-n 6 --dist worksteal`** (3.97x); slowest test 5 s -> 8-9 s. STACK.md measured up to 14 s at `-n 8` on `test_commit_step.py`. Do not set `-n auto` (16 logical cores here). Measure 4, 6, 8.

### Pitfall 6: Counts change between machines and checkouts
`11668` today vs `9689` in CONTEXT: the Würth corpus has 8016 files now. Pass/skip counts only compare with the serial run **in the same checkout on the same day**. Expected skips today: the README says exactly four on the workstation (two symlink skips, `KICAD_IMPORT_UAT_DIR`, `KICAD_ATOMIC_UAT_DIR`); this session saw the `KICAD_IMPORT_UAT_DIR` skip in a 268-test subset. The isolation fixture must not turn a passing test into a skip (that is how the equality check will catch it).

### Pitfall 7: Fixture-ordering assumption
The autouse isolation fixture must run before any per-file `_isolated_settings`; verified (conftest first). If a per-file fixture later uses `tmp_path` while the new fixture uses `tmp_path_factory.mktemp`, there is no clash: `mktemp("user")` creates `user0`, `user1`... beside `test_x0`.

### Pitfall 8: The GSD gate command and exit code 5
`post-merge-gate.md` default for a Python project (no `workflow.test_command` set; `.planning/config.json` has none) is `python -m pytest -x -q --tb=short 2>&1 || uv run python -m pytest -x -q --tb=short`, run under `workflow.test_gate_timeout` (default 600). [VERIFIED: .claude/gsd-core/workflows/execute-phase/steps/post-merge-gate.md:136, :146-148; templates/config.json:22 `"test_gate_timeout": 600`] Consequences: (a) bare `pytest` as the quick run fits as is, with `-x` stopping early on a failure (works under xdist); (b) a failing run is run a **second time** through `uv run` (`uv` is installed at `<home>/.local/bin/uv`), doubling failure latency; setting `workflow.test_command` in `.planning/config.json` to `python -m pytest -q --tb=short` avoids that (optional, one-line config change, planner's call); (c) the regression gate runs `python -m pytest -q --tb=short -- <prior-phase test files>`: if those files hold only `slow` tests, `-m 'not slow'` deselects everything and pytest exits **5** ("no tests ran", verified), which the gate reports as a failure. Mitigation options: keep it (rare), or in `pytest_sessionfinish` map exit code 5 to 0 only when every deselected item was `slow`; recommend documenting, not hacking.

### Pitfall 9: `python` on PATH must be the venv interpreter
In this agent shell `which python` resolves to `env/Scripts/python`, so the gate's `python -m pytest` uses the project venv (pytest 9.1.1 confirmed by `python -m pytest --version`). The owner's own shells may differ; the docs should always say `.\env\Scripts\python.exe -m pytest`.

### Pitfall 10: Windows path length and retention
`pytest-of-<user>/pytest-N/popen-gw0/<test_name>0/...` adds 10 characters over serial; nested git worktree/submodule paths already run long. Use `tmp_path_retention_policy = "failed"` and `tmp_path_retention_count = 1` (both are real pytest options [VERIFIED: `pytest --help`: "tmp_path_retention_count", "tmp_path_retention_policy (all/failed/none)"]) so passing tests' git trees are removed and at most one old run is kept; measure whether the per-test removal costs time and keep whichever is faster. Defender exclusion for the base temp is a likely win, not measured (STACK.md).

### Pitfall 11: Interactive debugging
`--pdb`, `-s` output and `breakpoint()` do not work under xdist workers. Document `-n 0` for debugging (verified to run in-process).

## Code Examples

### Controller-side guard for the owner's real app state (proves "no test touches the real settings.ini, %APPDATA% or KiCad config")
```python
# tests/conftest.py (sketch). Digest hashes only; nothing is read into messages.
def _real_state_files() -> list[Path]:
    appdata, local = _REAL["APPDATA"], _REAL["LOCALAPPDATA"]
    roots = []
    if appdata:
        roots += [Path(appdata) / "KiCadExtLibManager"]                  # settings.ini, scan_cache/, migration_draft/
    if local:
        roots += [Path(local) / "KiCadExtLibManager" / "backups"]
    files = [p for r in roots if r.is_dir() for p in r.rglob("*") if p.is_file()]
    if appdata:                                                          # newest KiCad config: the three files the app reads
        kicad = Path(appdata) / "kicad"
        if kicad.is_dir():
            files += [p for v in kicad.iterdir() if v.is_dir() for n in ("kicad_common.json", "sym-lib-table", "fp-lib-table") if (p := v / n).is_file()]
    return files


def pytest_sessionstart(session):
    if not hasattr(session.config, "workerinput"):
        session.config._user_state_before = digest(_real_state_files())


def pytest_sessionfinish(session, exitstatus):
    ...  # controller only: compare, then session.exitstatus = pytest.ExitCode.TESTS_FAILED and print the changed paths
```
Caveat to document (same as the Custom rule): if the owner runs the app or KiCad during a run, those files change; rerun. Whether the three KiCad files belong in the digest is Open Question 1/2 territory.

### Ten-run equality script (orchestrator runs it; scratchpad bash + exit-code file, per the memory note)
```bash
# counts: "N passed, M skipped" from the -q summary line
ref=$(python -m pytest --full -n 0 -q -p no:cacheprovider -rs | tail -1 | grep -oE '[0-9]+ (passed|skipped|failed|error)[a-z]*' | sort | tr '\n' ' ')   # or take it from the baseline run
for i in 1 2 3 4 5 6 7 8 9 10; do
  s=$(date +%s); python -m pytest --full -q -p no:cacheprovider -rs > run_$i.txt 2>&1; code=$?; e=$(date +%s)
  line=$(tail -1 run_$i.txt | grep -oE '[0-9]+ (passed|skipped|failed|error)[a-z]*' | sort | tr '\n' ' ')
  echo "$i exit=$code secs=$((e-s)) counts=[$line] ref=[$ref]" >> tenrun.txt
done
```
(Planner: the serial reference is the *baseline run's* counts from before any change; a second serial run after the change is optional and costs about 30 minutes.)

### Marker audit test (collection based; runs in the quick set)
```python
# tests/test_markers.py (sketch)
def _collect(*args):
    return subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                           "-n", "0", "-o", "addopts=", "--strict-markers", "-c", str(REPO / "pyproject.toml"), *args],
                          cwd=REPO, capture_output=True, text=True, timeout=120)

def test_every_wurth_and_kicad_cli_test_is_slow():
    done = _collect("-m", "(wurth or kicad_cli) and not slow")
    assert done.returncode == 5, done.stdout[-2000:]          # exit 5 = nothing collected

def test_slow_set_is_not_empty_and_registered():
    done = _collect("-m", "slow")
    assert done.returncode == 0 and "tests collected" in done.stdout

def test_unregistered_marker_still_fails(tmp_path):
    (tmp_path / "test_x.py").write_text("import pytest\n@pytest.mark.not_registered\ndef test_x(): pass\n")
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--strict-markers", "-n", "0",
                           "-c", str(REPO / "pyproject.toml"), "--rootdir", str(tmp_path), str(tmp_path)], capture_output=True, text=True)
    assert done.returncode != 0 and "not_registered" in (done.stdout + done.stderr)
```
`-o addopts=` clears the `-n 6 -m 'not slow'` default so the subprocess collects the whole suite (about 4 s serial collection) [VERIFIED: `--collect-only` of 11668 tests took 3.2 s].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tempfile.mkdtemp` template per process | one template per run under `tmp_path_factory.getbasetemp().parent` with a lock | this phase | no leak (583 folders now), one build per variant |
| Per-file `QSettings.setPath` | global autouse + per-file kept | this phase | unprotected modules covered |
| Serial 30-minute full run | quick parallel default, `--full` parallel | this phase | gate fits 600 s |
| `filelock` (xdist docs) | stdlib exclusive-create lock | CONTEXT decision | no new dependency |

**Deprecated/outdated:** `tests/README.md` "How to run" (full 18 min, quick `-m "not wurth"` 8 min) and `.planning/codebase/TESTING.md` ("No automated tests exist") are stale.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Windows `kicad-cli.exe` resolves `%APPDATA%` through the shell API, so redirecting the `APPDATA` variable does not change its behaviour | Inventory (user state) | The 36 kicad-cli tests could fail or behave differently under the fixture; the plan's "run `-m kicad_cli` before/after the fixture" step catches it |
| A2 | The 10 `local_kicad` tests (read-only read of the owner's real KiCad tables) may stay as an explicit, documented exception to "no test reads the real KiCad config" | Open Question 1 | If the owner wants a strict reading, they must be removed or re-pointed to synthetic tables |
| A3 | `-n 6 --dist worksteal` is the likely fastest setting (matrix still to be measured); the quick run lands at a few minutes | Summary / Pattern 1 | Final values come from measurement; only the addopts value changes |
| A4 | Directory rename can fail on Windows under Defender, hence the `.done` marker design | Pattern 4 | None if wrong (marker design is correct either way) |
| A5 | Excluding the pytest base temp from Defender is a likely extra win | Pitfall 10 | Not part of any requirement |

## Open Questions (RESOLVED)

1. **The 10 `local_kicad` tests vs TEST-07 ("no test touches ... KiCad config").**
   - What we know: `tests/test_roundtrip_corpus.py:_local_table_params` reads the owner's real `%APPDATA%/kicad/<ver>/*-lib-table` at collection time and `read_bytes()` in the test; nothing is written; they are opt-in (marker `local_kicad`) and counted in the serial/parallel equality. The autouse fixture cannot redirect them (paths are fixed at import).
   - What's unclear: whether the owner reads TEST-07 as "never read" or "never write/modify".
   - Recommendation: keep them as the single documented read-only exception, list it in README and in the isolation meta-test as an allow-list of exactly these 10 ids, and have the run-level guard prove the three KiCad files are unchanged. If the owner wants no exception, replace the real-table parametrisation with the synthetic `tests/fixtures/tables` ones already in the same module.
   - **RESOLVED (14-CONTEXT.md, orchestrator decisions after research):** strict reading; the 10 tests are opt-in behind `KICAD_TEST_REAL_CONFIG=1` and do not read the real tables at collection time otherwise; kicad-cli gets `KICAD_CONFIG_HOME` redirected per test.
2. **Does the run-level user-state guard include the KiCad config files?** They change when the owner uses KiCad during a run (false positive). Recommendation: include only app-owned folders (`%APPDATA%/KiCadExtLibManager`, `%LOCALAPPDATA%/KiCadExtLibManager/backups`) as a hard failure, and the three KiCad files as a hard failure too but with the documented "rerun if you used KiCad" rule, mirroring the Custom rule. Owner's call.
   - **RESOLVED (14-CONTEXT.md):** app-owned state fails the run; KiCad's own config files are a warning only.
3. **Final `-n` and `--dist`.** Measure `worksteal` at 4/6/8 plus `loadgroup` and `loadfile` at the best count; each full run is about 8-15 minutes, so the matrix is 5-9 runs. Stage it: `worksteal -n 6`, `worksteal -n 8`, `loadgroup -n 6`, `loadfile -n 6`, stop when one is clearly fastest and also green. `loadfile` makes `test_roundtrip_corpus.py` (379 s serial) and `test_commit_step.py` (295 s) single-worker critical paths and is expected to lose.
   - **RESOLVED:** measured by the orchestrator with `measure.py matrix` (plans 14-03, 14-06); the final values are applied in 14-06.
4. **Template per `(populate, autocrlf)`** (about 12 tests bypass today's template): optional lever, only if the durations show them dominant.
   - **RESOLVED (deferred as contingency, 14-CONTEXT.md):** tried once only if TEST-05's half-of-baseline bound is missed; otherwise not built.
5. **Baseline number.** The owner remembers "about 30 minutes for 9689 tests"; today's count is 11668. The BASELINE task must record the actual serial wall time and the three counts (passed, skipped, failed) before any change; TEST-05's "half" is relative to that.
   - **RESOLVED:** the orchestrator records BASELINE.md (serial `--durations=50` on base commit 20a557a) before wave 1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| CPython (project venv `env/`) | everything | ✓ | 3.14.4 (`env/Scripts/python.exe -V`) | — |
| pytest, pytest-qt | runner | ✓ | 9.1.1, 4.5.0 | — |
| pytest-xdist, pytest-timeout | TEST-04/05/08/09 | ✗ in `env/` (installed only in a scratch folder for this research) | 3.8.0 / 2.4.0 available on PyPI | `pip install -r requirements-dev.txt` in each venv (`env/` here, the main checkout's venv, `.venv/`) |
| git | git fixtures | ✓ | 2.49.0.windows.1 | — |
| KiCad 10 / kicad-cli | `kicad_cli` tests | ✓ | `C:/Program Files/KiCad/10.0/bin/kicad-cli.exe` (KiCad 10.0 and 9.0 installed) | tests skip with a stated reason |
| WurthElektronik submodule | `wurth` tests | ✓ | 8016 corpus files, submodule at `ddb5a9ea` | tests skip |
| Custom submodule | live guard, `custom/` params | ✓ | `bbd48c5f` (`pre-atomic-1-gbbd48c5`) | guard no-op |
| CPU | parallelism | ✓ | 16 logical cores (`nproc`) | — |
| PowerShell | owner's shell | pwsh 7.7.0 ✓ and Windows PowerShell 5.1 ✓ | see Pitfall 2 | `--full` |
| `uv` | GSD gate fallback | ✓ | `<home>/.local/bin/uv` | — |

**Missing dependencies with no fallback:** none. **Missing with fallback:** the two plugins in `env/` (install step is task zero of the change set).

## Validation Architecture

> Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-qt 4.5.0 (+ pytest-xdist 3.8.0, pytest-timeout 2.4.0 after this phase) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.\env\Scripts\python.exe -m pytest` (becomes `-n 6 --dist worksteal -m 'not slow'` via addopts) |
| Full suite command | `.\env\Scripts\python.exe -m pytest --full` (serial reference: `--full -n 0`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-04 | bare `pytest` quick run finishes under 600 s | timing, run 3x, discard first | `python -m pytest -q -p no:cacheprovider` wall-clock (e.g. `gsd-tools run-with-timeout 600 -- ...` returns 0, not 124) | ❌ script in phase folder (Wave 0) |
| TEST-05 | `--full` wall time <= 0.5 x serial baseline | timing | `python -m pytest --full -q -p no:cacheprovider --durations=0 --durations-min=2`; baseline from BASELINE.md | ❌ BASELINE.md (task 1) |
| TEST-06 | every wurth / kicad_cli test is slow; git tests slow; unregistered marker fails | meta-test + collection | `python -m pytest tests/test_markers.py -q` (about 10 s) | ❌ Wave 0 |
| TEST-06 | git tests carry slow | runtime tripwire | any unmarked `make_superproject`/`make_worktree` test fails; covered by running the quick set once | ❌ Wave 0 (tripwire in `tests/gitfixtures.py`) |
| TEST-07 | git templates built once per run | subprocess `-n 4` run of 4 git tests with a build-log env var; assert exactly 2 builds (lf and crlf) at most and no `gitfixture_template_*` created in `%TEMP%` | `python -m pytest tests/test_isolation.py::test_templates_are_built_once -q` | ❌ Wave 0 |
| TEST-07 | no real settings / APPDATA / KiCad config / env var visible | in-process meta-test: `get_settings().fileName()` under the per-test dir, `Path.home()`, `APPDATA`, `LOCALAPPDATA` under it, `KICAD_LIB_GITHUB`/`CUSTOM_3DMODEL_DIR` absent | `python -m pytest tests/test_isolation.py -q` | ❌ Wave 0 |
| TEST-07 | run-level guard: real app-state files unchanged after the run | controller hook; unit-test the compare with a fake tree | `python -m pytest tests/test_isolation.py::test_user_state_guard_* -q` | ❌ Wave 0 |
| TEST-07 | live Custom/ write still fails the run, also under xdist | subprocess run like `_run_guarded` with `-n 2` | `python -m pytest tests/test_customfixtures.py -q` (existing serial test) + new `-n 2` case | ✅ serial / ❌ xdist case |
| TEST-08 | parallel full run == serial counts, 10 times | ten-run script (orchestrator, long budget) | script above; compare `passed`/`skipped`/`failed` per run with BASELINE.md | ❌ script in phase folder |
| TEST-09 | hung test fails naming the test | subprocess `-n 2 --timeout=2` on a sleeping test in a tmp dir; assert exit != 0, "crashed while running" and the nodeid in stdout, elapsed < 30 s | `python -m pytest tests/test_isolation.py::test_hung_test_fails_naming_it -q` | ❌ Wave 0 |
| TEST-09 | config carries `timeout = 300`, thread method, long test marked | static check of `pyproject.toml` and `test_wurth_corpus_parse_budget`'s marker | `python -m pytest tests/test_markers.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the meta-test files above plus the module(s) touched (`python -m pytest tests/test_markers.py tests/test_isolation.py -q`, about 30-60 s).
- **Per wave merge:** bare `python -m pytest` (the quick run, must be under 10 minutes; this is also the GSD gate).
- **Phase gate:** orchestrator runs `--full` once with a long budget, then the ten-run script; executors never start a full run.

### Wave 0 Gaps
- [ ] `.planning/phases/14-test-suite-speed-up/BASELINE.md`: serial `python -m pytest --durations=50 -q -p no:cacheprovider` run **before any change** (bare pytest, no plugins needed): wall time, `N passed, M skipped`, top 50 durations. Orchestrator runs it with a long budget (scratchpad bash script + exit-code file, per memory note).
- [ ] `tests/test_markers.py`, `tests/test_isolation.py` (new)
- [ ] conftest additions (`--full`, slow hook, isolation fixtures, template root, controller guards)
- [ ] `tests/gitfixtures.py` template rewrite + tripwire
- [ ] Install `pytest-xdist==3.8.0 pytest-timeout==2.4.0` into every venv (`pip install -r requirements-dev.txt`)
- [ ] Ten-run and timing scripts in the phase folder

## Security Domain

`security_enforcement` is enabled (`.planning/config.json`: `"security_enforcement": true`, ASVS level 1, block on high). This phase changes test tooling only; no application input path changes.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication / V3 Session / V4 Access Control | no | — |
| V5 Input Validation | no (no app input handling changes) | — |
| V6 Cryptography | no (SHA-256 digests in the guard use `hashlib`, existing) | — |
| V10/V14 Dependencies and configuration | yes | exact pins (`==`), `pip index versions` checked, no yanked version (2.5.0), package-legitimacy seam run (SUS for data-gap only) |
| V12 Files and resources | yes (temp folders) | lock file and templates live under the user-private pytest base temp; `onexc` cleanup; no fixed world-writable paths |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Typosquatted or yanked dev dependency | Tampering | exact pins from the owner's decision; verify with `pip index versions`; do not float to `>=` |
| Test run modifying the owner's real settings, KiCad config or library collection | Tampering | autouse isolation + run-level guards (Custom guard existing, user-state guard new) |
| Stale lock file letting a later run read a half-built template | Tampering / DoS | `.done` marker written last; lock file created per run inside that run's base temp (not a fixed path), deadline with a clear failure |
| Leaked temp folders accumulating (583 today) | Information disclosure (low) | build under base temp, controller cleanup, `tmp_path_retention_*` |

## Sources

### Primary (HIGH confidence)
- This repository, read this session: `pyproject.toml`, `requirements-dev.txt`, `tests/gitfixtures.py` (lines 146-185 read; rest via `cat`), `tests/conftest.py`, `tests/customfixtures.py`, `tests/test_roundtrip_corpus.py`, `kicad_lib_manager/{main_window,library_scanner,settings,fsutil}.py` excerpts, `tests/README.md`, `.claude/gsd-core/workflows/execute-phase/steps/post-merge-gate.md` and `regression-gate-run.md`.
- Runs on this machine (2026-11-22): `pytest --collect-only` counts per marker; serial module timings listed in the Inventory; scratch experiments with the two plugins installed under the session scratchpad (`pip install --target ... --no-deps pytest-xdist==3.8.0 pytest-timeout==2.4.0 execnet==2.1.2`): addopts quoting, `-m ""` override, `-n 0`, `--full` option, `add_marker` in a `tryfirst` collection hook, fixture ordering, exit code 5, basetemp layout, guard under xdist, timeout under xdist on the real repo.
- `pip index versions pytest-xdist | pytest-timeout | execnet`; `gsd-tools query package-legitimacy check`.
- Installed xdist 3.8.0 source (`xdist/plugin.py`, `remote.py`, `scheduler/loadgroup.py`).
- `.planning/research/STACK.md` (xdist/timeout section), `.planning/research/PITFALLS.md` (pitfalls 1-7), `.planning/todos/pending/2026-11-13-speed-up-full-test-suite.md`.

### Secondary (MEDIUM confidence)
- Project research claim that pytest-timeout 2.5.0 was yanked on 2026-08-16 (cited from STACK.md; consistent with `pip index versions` hiding it).
- Memory note: full suite about 29 min, GSD gate 600 s always times out.

### Tertiary (LOW confidence)
- None used as a basis for a recommendation; A1, A4, A5 are `[ASSUMED]` above.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, pins from CONTEXT, verified loadable together on this Python/pytest.
- Architecture (lock, isolation, marker mechanics, `--full`): HIGH, each mechanism exercised in a scratch project or on the real conftest.
- Timings: MEDIUM, module-level serial numbers and two parallel samples measured; full baseline and full parallel runs are the phase's job.
- Pitfalls: HIGH for 1-3 and 8 (verified), MEDIUM for 4-6, 10-11.

**Research date:** 2026-11-22
**Valid until:** 2026-12-22 (stable tooling; counts move with the Würth submodule and the suite)
