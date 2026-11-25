# Phase 14: Test Suite Speed-Up - Pattern Map

**Mapped:** 2026-11-22
**Files analyzed:** 12 new/modified
**Analogs found:** 11 / 12 (all analogs are git-tracked: tests/*.py, pyproject.toml, requirements-dev.txt)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `requirements-dev.txt` | config | n/a | itself (2 pins) | exact |
| `pyproject.toml` | config | n/a | itself (`[tool.pytest.ini_options]`) | exact |
| `tests/conftest.py` (add `--full`, slow hook, isolation, template root, controller guards) | test config / fixtures | event-driven (hooks) | itself: `pytest_runtest_teardown`, `_desktop_screen_area`, `_live_custom_untouched` | exact |
| `tests/gitfixtures.py` (`_template` under lock + tripwire) | test helper | file-I/O | itself: `_template`, `make_superproject` | exact |
| `tests/test_markers.py` (new) | test (meta) | request-response (subprocess) | `tests/test_customfixtures.py::_run_guarded` | role-match |
| `tests/test_isolation.py` (new) | test (meta) | request-response (subprocess + in-process) | `tests/test_customfixtures.py` + `tests/test_settings_import.py::_isolated_settings` | role-match |
| `tests/test_customfixtures.py` (add `-n 2` guard case) | test | subprocess | `_run_guarded` / `test_guard_failure_fails_the_run` | exact |
| `tests/test_roundtrip_corpus.py` (timeout marker on budget test) | test | batch | itself, line 244 | exact |
| git-using test modules (`slow` marks): `test_commit_step.py`, `test_commit_gate*.py`, `test_scan_changes.py`, `test_migration_precheck.py`, `test_commit_deletions.py`, `test_migration_commit.py`, `test_migration_full.py`, `test_import_dialog.py` (3), `test_gitops.py` (4), `test_scan_cache.py` (2), `test_rescan_library.py` (3) | test | file-I/O | existing `@pytest.mark.wurth` / `kicad_cli` usage | role-match |
| `tests/README.md`, `README.md`, `CLAUDE.md` (run commands) | docs | n/a | `tests/README.md` lines 5-15 | exact |
| `.planning/phases/14-test-suite-speed-up/BASELINE.md`, ten-run/timing scripts | docs/script | batch | RESEARCH.md "Ten-run equality script" | partial |
| user-state run guard (in conftest or `customfixtures.py`) | guard | event-driven | `guard_custom` in `tests/customfixtures.py` (not re-read; RESEARCH sketch) | role-match |

## Pattern Assignments

### `pyproject.toml` (config)

**Analog:** itself, lines 1-10 (keep the three existing markers verbatim):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra --strict-markers"
qt_api = "pyside6"
markers = [
    "wurth: needs the WurthElektronik submodule checked out (stress/perf corpus)",
    "local_kicad: reads the user's real KiCad config tables under the OS config dir (opt-in, read-only)",
    "kicad_cli: needs the real kicad-cli 10 binary (skipped with a stated reason otherwise)",
]
```
Target (values for -n/--dist fixed by measurement): addopts `"-ra --strict-markers -n 6 --dist worksteal -m 'not slow'"`, `timeout = 300`, `timeout_method = "thread"`, `tmp_path_retention_policy = "failed"`, `tmp_path_retention_count = 1`, plus a `"slow: ..."` marker line in the same one-line style. Do not register `timeout`/`xdist_group` (plugins do).

### `requirements-dev.txt` (config)

Current content (3 lines): `-r requirements.txt`, `pytest==9.1.1`, `pytest-qt==4.5.0`. Append `pytest-xdist==3.8.0` and `pytest-timeout==2.4.0` (exact `==` pins, same style; no filelock, never 2.5.0).

### `tests/conftest.py` (fixtures/hooks)

**Analog:** itself.

**Hook style** (lines 17-38): module-level `@pytest.hookimpl(wrapper=True, tryfirst=True)` with a docstring explaining why; heavy Qt imports done lazily inside the function ("test modules that never create a widget stay Qt-free"). Follow this: import `QSettings` inside the fixtures, never at module top.

**Autouse function fixture style** (lines 41-53):
```python
@pytest.fixture(autouse=True)
def _desktop_screen_area(monkeypatch):
    """Size the import window ... Nothing is imported here: a test module that never loads the import window stays Qt-free."""
    module = sys.modules.get("kicad_lib_manager.widgets.import_dialog")
    if module is None:
        return
```

**Session autouse guard style** (lines 176-184), to keep unchanged and to sit beside the new session fixtures (`_qsettings_sandbox`, `_git_template_root`):
```python
@pytest.fixture(scope="session", autouse=True)
def _live_custom_untouched():
    from customfixtures import guard_custom
    yield from guard_custom(REPO_ROOT / "Custom")
```
Imports at top (lines 1-11): `os, re, sys, Path, pytest`; `os.environ["QT_QPA_PLATFORM"] = "offscreen"` forced at import; `REPO_ROOT` constant. Add `shutil`, `stat` as needed and capture `_REAL` env right after the QT line, before any redirect.

New code to add (copy from RESEARCH Patterns 2, 3, 4, 5 and "Controller-side guard"): `pytest_addoption --full`, `pytest_configure` (clears `markexpr` when `not slow`), `pytest_collection_modifyitems` (tryfirst; wurth/kicad_cli -> slow), `_qsettings_sandbox` (session), `_isolated_user_state` (function, autouse, `tmp_path_factory.mktemp("user")`, monkeypatch env, `QSettings.setPath`), `_git_template_root` (session, uses `worker_id`), `pytest_sessionfinish` controller-only cleanup guarded by `hasattr(session.config, "workerinput")` and `getattr(config, "_tmp_path_factory", None)`, rmtree with `onexc` that chmods `S_IWRITE` and retries.

### `tests/gitfixtures.py` (helper, file-I/O)

**Analog:** itself.

**Imports** (lines 10-26): stdlib block `hashlib, os, shutil, subprocess, tempfile, ...`, then `pytest`, then `from zipfixtures import ...` (flat module imports, `tests/` on sys.path). Add `time`; drop `tempfile` once `mkdtemp` is gone.

**Code to replace** (lines 149-158):
```python
_templates: dict[bool, Path] = {}


def _template(autocrlf: bool) -> Path:
    """A built superproject kept for the whole test session; building one takes several seconds."""
    if autocrlf not in _templates:
        folder = Path(tempfile.mkdtemp(prefix="gitfixture_template_"))
        _build(folder, autocrlf, populate_custom)
        _templates[autocrlf] = folder
    return _templates[autocrlf]
```
Replacement: RESEARCH Pattern 4 (`_root`, `set_template_root`, exclusive-create `os.open(lock, O_CREAT|O_EXCL|O_WRONLY)`, `.done` marker written last, `_TEMPLATE_WAIT` about 240 s, clear AssertionError on deadline).

**Core copy path stays** (lines 178-190): `make_superproject` copies the template with `shutil.copytree(..., ignore=shutil.ignore_patterns("seed_*"))`, then re-points `remote.origin.url`, `submodule.Custom.url` and calls `_local_config`. Because `_local_config` (82-95) already unsets/re-sets `core.hooksPath`, a template at another absolute path is safe. The `.done`/`.lock` files live beside (not inside) the template folder so `copytree` does not pick them up.

**Tripwire:** add a module global `_current_item` plus `set_current_item(item)`; at the top of `make_superproject` (and `make_worktree`, not read here; locate it in the same file) raise `AssertionError("this test builds a real git repository: mark it @pytest.mark.slow")` when the item lacks `get_closest_marker("slow")`. A conftest function-scoped autouse fixture feeds it from `request.node` and resets at teardown. Note `migrationfixtures.py:447` also calls `make_superproject`, so the tripwire covers it.

### `tests/test_markers.py` and `tests/test_isolation.py` (meta-tests, new)

**Analog:** `tests/test_customfixtures.py` lines 320-345 (`_run_guarded`): subprocess pytest with `[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(run_dir)]`, `cwd=run_dir` under `tmp_path`, env built from `dict(os.environ)` plus `PYTHONPATH = tests_dir + repo root`, `capture_output=True, text=True, timeout=120`; assertions on `returncode` and substrings of `done.stdout`:
```python
def test_guard_failure_fails_the_run(tmp_path):
    done = _run_guarded(tmp_path, touch=True)

    assert done.returncode != 0, done.stdout
    assert "changed the live Custom/ folder" in done.stdout
```
Copy this shape. Subprocess must run outside the repo tree (so repo addopts do not leak) or pass `-n 0 -o addopts=`; never `--basetemp` inside the repo. Test bodies for markers audit and the unregistered-marker case: RESEARCH "Marker audit test". For the `-n 2` guard case, add `"-n", "2"` to a copy of `_run_guarded`'s argv (the run_dir has no pyproject, so xdist must be importable from the same interpreter); for the timeout test use `-n 2 --timeout=2` on a sleeping test and assert `"crashed while running"` and the nodeid.

**In-process isolation meta-test analog:** `tests/test_settings_import.py` lines 11-19 (the per-file fixture pattern the new autouse one must coexist with and which stays untouched in 19 files):
```python
@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path):
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "qsettings"))
    file_name = Path(settings.get_settings().fileName()).resolve()
    assert tmp_path.resolve() in file_name.parents
```
The meta-test asserts the same shape without defining its own fixture: `get_settings().fileName()` under the per-test dir, `os.environ["APPDATA"]`/`LOCALAPPDATA`/`Path.home()` under it, `KICAD_LIB_GITHUB`/`CUSTOM_3DMODEL_DIR` absent.

### `tests/test_roundtrip_corpus.py` (timeout marker)

**Analog:** itself, lines 244-258. Add one decorator line above the existing mark:
```python
@pytest.mark.wurth
@pytest.mark.timeout(900)   # budget is max(60, 0.05 x 8016 files) = 400.8 s, above the 300 s default
def test_wurth_corpus_parse_budget():
```
Module already carries per-test `@pytest.mark.wurth` (slow comes from the conftest hook, no module edit needed).

### Git-using test modules (slow marking)

**Analog:** existing marker usage, e.g. `@pytest.mark.wurth` on functions. Fully-git modules (`test_commit_step.py`, `test_commit_gate.py`, `test_commit_gate_panel.py`, `test_scan_changes.py`, `test_migration_precheck.py`, `test_commit_deletions.py`, `test_migration_commit.py`, `test_migration_full.py`): add module-level `pytestmark = pytest.mark.slow` (verify the module has no non-git tests first). Mixed modules (`test_import_dialog.py`, `test_gitops.py`, `test_scan_cache.py`, `test_rescan_library.py`): `@pytest.mark.slow` per test; the runtime tripwire lists any missed test by name. Existing `requires_git = pytest.mark.skipif(GIT is None, ...)` in gitfixtures.py line 36 is the module-level-mark idiom to mirror.

### Docs (`tests/README.md`, `README.md`, `CLAUDE.md`)

**Analog:** `tests/README.md` lines 5-15 (current "How to run" list: full `pytest`, quick `-m "not wurth"`, `-m kicad_cli`, `-m wurth`, note that `-ra` prints skip reasons). Rewrite to: bare `.\env\Scripts\python.exe -m pytest` = quick parallel; `... -m pytest --full` = everything; `--full -n 0` = serial reference; `-n 0` for pdb/debugging; note venv must have xdist installed (`pip install -r requirements-dev.txt`) or `-n` is an unrecognized argument; timeout shows as "worker crashed while running <nodeid>" (rerun `-n 0` for the stack). Document the `local_kicad` read-only exception. `README.md` and `CLAUDE.md` currently have no pytest lines (grep matched only tests/README.md); add a short test section naming both commands.

## Shared Patterns

### Lazy Qt imports in conftest
**Source:** `tests/conftest.py` lines 28-30, 48-51. **Apply to:** all new conftest fixtures; import `QSettings` inside the function.

### Subprocess-pytest meta-test
**Source:** `tests/test_customfixtures.py` lines 320-345. **Apply to:** `test_markers.py`, `test_isolation.py`, the xdist guard case.

### Per-file settings isolation stays
**Source:** 19 files with `QSettings.setPath` (list in RESEARCH Pattern 5). **Apply to:** do not edit; the conftest autouse runs first, per-file fixtures re-point afterwards.

### Session guard via generator fixture
**Source:** `tests/conftest.py` 176-184 + `customfixtures.guard_custom`. **Apply to:** any new run-level guard (user-state digest); keep the "fails the run naming paths" semantics.

### Style
4-space indent, double quotes, trailing commas, one-line "why" comments above code, one-line docstrings on helpers, `Path | None` typing.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| ten-run / timing scripts (phase folder) | script | batch | No shell scripts exist in the repo; use the bash sketch in RESEARCH.md, run via scratchpad + exit-code file per the memory note |

## Metadata

**Analog search scope:** `tests/conftest.py`, `tests/gitfixtures.py`, `tests/test_customfixtures.py`, `tests/test_settings_import.py`, `tests/test_roundtrip_corpus.py`, `pyproject.toml`, `requirements-dev.txt`, `tests/README.md`
**Files scanned:** 8 read or excerpted (customfixtures.py and make_worktree body not read; planner should open them when editing)
**Pattern extraction date:** 2026-11-22
