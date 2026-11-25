# Phase 16: Repo Split - Pattern Map

**Mapped:** 2026-11-24
**Files analyzed:** 14 new or modified
**Analogs found:** 11 / 14 (3 have no code analog: CI yml, commit-msg hook, scripts/split/*)

All paths are repo-relative. Every analog below is git-tracked source (no gitignored mirror paths).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/vendorfixtures.py` (add `ul_*` builders) | test fixture builder | transform (bytes out) | `samacsys_members` / `snapeda_members` / `*_zip` in same file | exact |
| `tests/zipfixtures.py` (`UL_ZIP` becomes generated) | test fixture constant | file-I/O | `zipfixtures.zip_bytes` / `make_zip`, existing `UL_ZIP` line 25 | role-match |
| `tests/conftest.py` (`pytest_collection_modifyitems`, `pytest_addoption`, summary count, `ul_package`, `_live_custom_untouched`) | test config / hook | event-driven, file-I/O | same file: timeouts-through-run-temp mechanism | exact |
| `pyproject.toml` (register `corpus`, `needs_kicad`) | config | n/a | existing `markers = [...]` | exact |
| `tests/test_markers.py` (extend for new markers) | test (meta) | request-response | same file `test_wurth_and_kicad_cli_tests_are_slow` | exact |
| `tests/test_corpus_gate.py` (new meta-test) | test (meta) | request-response | `tests/test_isolation.py` `run_pytest` tests | exact |
| `tests/test_vendorfixtures.py` (UL originality) | test | transform | `test_fixture_originality` line 124 | exact |
| `scripts/prepublish_scan.py` | utility script | batch (git walk + text scan) | none in repo; conventions from `kicad_lib_manager/procs.py`, `gitops.py` | partial |
| `scripts/check_skip_budget.py` | utility script | batch (parse pytest output) | none; same conventions | partial |
| `scripts/split/*` (+ `uri_diff.py`) | utility scripts | batch / file-I/O | `kicad_lib_manager/library_scanner.py` `parse_lib_table`-style parsing; `table_generator.parse_lib_table` | role-match |
| `tests/test_prepublish_scan.py` | test | transform + one slow git test | `tests/gitfixtures.py` + `@pytest.mark.slow` rule | role-match |
| `.github/workflows/ci.yml` | config | n/a | none | no analog |
| `.githooks/commit-msg` | config / hook | transform | none | no analog |
| `kicad_lib_manager/collection.py` (remove `Source.LEGACY`) | service | request-response | itself | n/a |

## Pattern Assignments

### `tests/vendorfixtures.py` - add Ultra Librarian builder (test builder, transform)

**Analog:** `samacsys_members` / `samacsys_zip` / `snapeda_members` in the same file.

**Module contract** (lines 1-15): stdlib plus `zipfixtures` only; "builders copy each vendor's layout, file names, property names and markers, never its geometry, models or licence text".
```python
from pathlib import Path

from zipfixtures import BS, LEGACY_DCM_BYTES, LEGACY_LIB_BYTES, LEGACY_MOD_BYTES, STEP_BYTES, _quote, make_zip
```

**Constants + member list + zip writer shape** (lines 145-165; samacsys 308-345 is the same):
```python
def snapeda_members(*, how_to: bool = True, with_model: bool = False) -> list[tuple[str, bytes]]:
    """Return the members of a SnapEDA download, all at the zip root. ..."""
    members: list[tuple[str, bytes]] = [
        (f"{SNAPEDA_SYMBOL}.kicad_sym", snapeda_symbol()),
        (f"{SNAPEDA_FOOTPRINT}.kicad_mod", snapeda_footprint()),
    ]
    ...
    return members


def snapeda_zip(path: Path, **kwargs) -> Path:
    """Write a synthetic SnapEDA zip to path (creating its folder) and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return make_zip(path, snapeda_members(**kwargs))
```
Copy for UL: `ul_symbol()`, `ul_footprint()`, `ul_members()` (RESEARCH "UL Builder Specification" gives exact member order, CRLF everywhere, `ul_` zip stem, timestamp symbol name `YYYY-MM-DD_HH-MM-SS.kicad_sym`, `UL_IGNORED`), `ul_zip(path)`. Symbol text is built as `lines` joined with `"\r\n"` then `.encode("utf-8")` like `samacsys_footprint` (lines ~290-306). Use `STEP_BYTES` only if it starts with `ISO-10303-21;`; otherwise write a small CRLF STEP header.

**Determinism gap (no analog, new code):** `zipfixtures.zip_bytes` (lines 30-44 of that file) does `zf.writestr(name, data, ...)` with plain names, which stamps the current time. It already accepts `str | zipfile.ZipInfo` members, so pass `zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))` with `compress_type` set per member.

**`UL_ZIP` generation** (`tests/zipfixtures.py:25` today `UL_ZIP = REPO_ROOT / "downloaded_examples" / "ul_CSD85301Q2.zip"`): replace with a path under `tempfile.gettempdir()/kicad_lib_manager_tests/<sha12>/ul_CSD85301Q2.zip`, built at import, written to a temp name then `os.replace`. Keep the file name (the `ul_` stem scores a point in `UltraLibrarianAdapter.detect`). Keep `UL_SYMBOL_MEMBER`, `UL_FOOTPRINT_MEMBER`, `UL_MODEL_MEMBER` constants (lines 26-28) consistent with the builder.

**Originality test** `tests/test_vendorfixtures.py:115-135`: `_real_member_hashes` + `test_fixture_originality` parametrised over `["snapeda","samacsys","snapeda_model"]`. Add `"ul"` and mark the whole test `corpus` (it currently `pytest.skip`s when the real zip is absent; that skip becomes a deselect):
```python
@pytest.mark.parametrize("vendor", ["snapeda", "samacsys", "snapeda_model"])
def test_fixture_originality(vendor):
    real = REAL_ZIPS[vendor]
    if not real.exists():
        pytest.skip(...)
    real_hashes = _real_member_hashes(real)
    for name, data in _all_members():
        assert hashlib.sha256(data).hexdigest() not in real_hashes, f"{name} is a byte copy of a real {vendor} member"
```

---

### `tests/conftest.py` - corpus / needs_kicad deselect with printed count (hook, event-driven)

**Analog:** the same file's existing hooks. Quoted so the planner can copy.

**Hook that must be extended** (lines 68-79, `tryfirst` so built-in `-m` sees marks):
```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("slow") is not None:
            continue
        if (item.get_closest_marker("wurth") is not None or ...):
            item.add_marker(pytest.mark.slow)
```
Change signature to `(config, items)`; after the slow loop, partition `items` by `corpus` (gate: `KICAD_TEST_CORPUS` names a folder holding `Custom/`) and `needs_kicad` (gate: KiCad stock footprint dir found, via `find_kicad_footprint_dir()` from `kicad_lib_manager.library_scanner`), `items[:] = kept`, and call `config.hook.pytest_deselected(items=removed)`. Make `wurth` imply `corpus` here (`item.add_marker(pytest.mark.corpus)`) as RESEARCH recommends. Raise `pytest.UsageError` when `KICAD_TEST_CORPUS` is set but invalid. Do not put `not corpus` in `addopts` (the `--full` rewrite at line 63 only matches the exact string `not slow`, and `test_isolation.py` asserts `"-m 'not slow'" in ini["addopts"]`).

**Option / config shape** (lines 40-66): `pytest_addoption` adds `--full`; `pytest_configure` stores `_RUN_CONFIG = config`.

**Count-through-run-temp-files mechanism to copy** (workers write, controller reads):
```python
_RUN_CONFIG = None

def _run_temp(config) -> Path:
    """The run's shared base temp: a worker's base is <run>/popen-gwN, so its parent is the run folder."""
    base = config._tmp_path_factory.getbasetemp()
    return base.parent if hasattr(config, "workerinput") else base
```
Worker write (lines 243-252, 260-272): `record = _run_temp(item.config) / "timeouts" / f"{item.config.workerinput['workerid']}.txt"`, append line, wrap in `try/except OSError: pass  # a failed write must never stop the timeout`. Controller read (lines 283-300, `pytest_handlecrashitem`):
```python
folder = _run_temp(_RUN_CONFIG) / "timeouts"
if not folder.is_dir():
    return
for record in sorted(folder.glob("*.txt")):
    for line in record.read_text(encoding="utf-8").splitlines():
```
Apply: in `pytest_collection_modifyitems` on a worker (`hasattr(config, "workerinput")`) write `<run temp>/deselected/<workerid>.txt` with lines `corpus 123` / `needs_kicad 7` (all workers collect the same set, so the controller takes the max or the first, not the sum). On the controller (no `workerinput`) it also collects, so it can print directly. Print the line in `pytest_terminal_summary` (or reuse `_report(session, line)` at lines 180-185, which writes through the terminalreporter): `"deselected: 123 corpus (set KICAD_TEST_CORPUS to run), 7 needs_kicad (KiCad not found)"`. Note `_tmp_path_factory.getbasetemp()` is not yet usable during collection in some setups; the existing code only calls it at test time, so verify or compute the folder lazily and fall back to the controller's own count.

**`ul_package` fixture** (lines 500-512): change only the path line
```python
package = open_package(REPO_ROOT / "downloaded_examples" / "ul_CSD85301Q2.zip", REPO_ROOT)
```
to `open_package(UL_ZIP, REPO_ROOT)` with `from zipfixtures import UL_ZIP`.

**`_live_custom_untouched`** (lines 544-552): 
```python
@pytest.fixture(scope="session", autouse=True)
def _live_custom_untouched():
    from customfixtures import guard_custom
    yield from guard_custom(REPO_ROOT / "Custom")
```
Repoint the argument at `Path(os.environ["KICAD_TEST_CORPUS"]) / "Custom"` when set, else a path that does not exist (the docstring already says the guard does nothing when Custom is absent; confirm `guard_custom` handles a missing folder).

---

### `pyproject.toml` - marker registration (config)

**Analog:** lines 11-16 of the same file.
```toml
addopts = "-ra --strict-markers -n 8 --dist worksteal -m 'not slow'"
markers = [
    "wurth: needs the WurthElektronik submodule checked out (stress/perf corpus)",
    "local_kicad: reads the user's real KiCad config tables under the OS config dir (opt-in, read-only)",
    "kicad_cli: needs the real kicad-cli 10 binary (skipped with a stated reason otherwise)",
    "slow: builds real git repositories, ...",
]
```
Add `"corpus: needs real vendor samples, the Wurth corpus or the live Custom/; runs only when KICAD_TEST_CORPUS names a collection folder, otherwise deselected with a printed count"` and `"needs_kicad: needs an installed KiCad's stock libraries; deselected with a printed count when KiCad is not found"`. Keep `addopts` unchanged. Keep `timeout = 300`.

---

### `tests/test_markers.py` (meta, extend)

**Analog:** lines 27-41.
```python
from runfixtures import TESTS_DIR, collect_repo, run_pytest, write_tree

def test_wurth_and_kicad_cli_tests_are_slow():
    done = collect_repo("-m", "(wurth or kicad_cli) and not slow")
    assert done.returncode == 5, _tail(done)

def test_slow_marker_is_registered_and_used():
    done = collect_repo("-m", "slow")
    assert done.returncode == 0, _tail(done)
```
Add: `corpus` and `needs_kicad` are registered and used (`collect_repo("-m", "corpus")` returncode 0 when `KICAD_TEST_CORPUS` is set; careful: with the gate closed everything corpus is deselected, so assert via a static AST audit like `_test_functions` / `_module_is_slow` at lines 47-70 rather than collection). Remove the `_READ_ONLY_GIT_TESTS` entry for `test_vendor_zips_stay_local` (line 9) when that test is deleted.

---

### `tests/test_corpus_gate.py` (new meta-test; request-response)

**Analog:** `tests/test_isolation.py` plus `tests/runfixtures.run_pytest`.

**Helper signature** (`tests/runfixtures.py:47-77`): `run_pytest(run_dir, *args, basetemp, env=None, timeout=180)` runs a child `python -m pytest -p conftest -c <repo pyproject> --rootdir run_dir --confcutdir run_dir -o addopts=-ra --strict-markers --basetemp ...`. Note it overrides `addopts`, so pass `-m "not slow"` yourself if needed.

**Test shape** (`test_isolation.py:32-55` and 155):
```python
run_dir = write_tree(tmp_path / "run", {"test_hang.py": _HANG})
done = run_pytest(run_dir, "-n", "2", "--timeout", "2", basetemp=tmp_path / "bt")
assert done.returncode != 0, _tail(done)
assert "TIMEOUT test_hang.py::test_hangs after 2 s" in done.stdout, _tail(done)
```
Apply: `write_tree` two files, one `@pytest.mark.corpus` test and one plain, run with `-n 2` (proves the count survives xdist) and `env={}` without `KICAD_TEST_CORPUS`; assert `"1 passed"`, the printed `deselected` line with count, and that the corpus test did not run. Second case with `env={"KICAD_TEST_CORPUS": str(tmp_path / "nope")}` asserts non-zero return and a usage error. Third case with a scratch folder containing `Custom/` asserts the corpus test ran. Same for `needs_kicad`. Import the same names as test_isolation: `from runfixtures import REPO_ROOT, run_pytest, write_tree`; `_tail(done)` = last 3000 chars of stdout+stderr. These tests do not create a git repo, so they need no `slow` mark (check: the child run loads the repo conftest, whose `_live_custom_untouched` must tolerate a missing corpus).

---

### `scripts/prepublish_scan.py`, `scripts/check_skip_budget.py`, `scripts/split/*` (stdlib scripts)

**No `scripts/` directory exists.** Closest conventions:
- Root scripts carry `#!/usr/bin/env python3`, a module docstring with usage, `main()` thin, `if __name__ == "__main__": main()` (from `.claude/CLAUDE.md` "Script Conventions"; `kicad_lib_manager.py`, `generate_lib_tables.py`).
- Stdlib only, `pathlib.Path`, type hints `X | None`, `list[str]`.
- Child processes: argv always a list, never a shell string, capture output; `kicad_lib_manager/procs.py` `run_process` is the model but scripts must not import the app package (the scan runs in CI before anything is installed; keep scripts self-contained):
```python
def run_process(argv, *, runner=None, **kwargs):
    kwargs.setdefault("capture_output", True)
    if "input" not in kwargs and "stdin" not in kwargs:
        kwargs["stdin"] = subprocess.DEVNULL
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    run = runner if runner is not None else subprocess.run
    return run(list(argv), **kwargs)
```
  For scripts use plain `subprocess.run([...], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)`.
- `kicad_lib_manager/gitops.py` imports (lines 9-20) show the git-calling style (`GitRun`, `run_git`, env sanitising via `_env`); `gitops.run_git` at line 120 is the shape to imitate (fixed env, no pager, output decoded with `_text`) but do not import it.
- Exit codes and message-list style: functions return `list[str]` findings, caller prints and sets the exit code (matches the app's "messages as list[str]" rule). RESEARCH "Pre-Publish Scan Design" defines exit 0/1/2 and pure `scan_text(path, data, rules) -> list[Finding]` plus a thin git walk.
- Public-script rule: no owner identifiers in the script; read identity terms at run time (`--deny-emails-from-repo PATH`, `--deny-terms-file`).

**`scripts/split/uri_diff.py` analog for parsing KiCad lib tables:** `kicad_lib_manager/table_generator.py` `parse_lib_table()` (docstring lists returned keys `name, type, uri, options, descr, raw`) and `_LIB_ENTRY_RE`. Re-implement the regex in the script (do not import the app); resolve `${VAR}` against `kicad_common.json` `environment.vars` (see `library_scanner.sync_kicad_path_vars` for the JSON shape).

**Skip budget script:** parse `-ra` summary line (`N passed, M skipped`), as seen in the suite output `3911 passed, 29 skipped, 4 warnings in 100.15s`; fail when skipped > 10. Under xdist the deselected count is not in the summary, so read the line printed by the conftest hook above.

**Tests for the scripts:** pure-function tests in the quick run; one `@pytest.mark.slow` test builds a tiny git repo with planted violations (the suite rule: a test that creates a real git repo must carry `slow`, else the run fails with "builds a real git repository: mark it @pytest.mark.slow"). Use `tests/gitfixtures.py` helpers for the repo build.

---

### `kicad_lib_manager/collection.py` / tests - Source.LEGACY removal

Per RESEARCH section 4 (Collection-Side Cutover) all places are listed; test cases to delete are in `tests/test_collection.py` and `tests/test_startup.py`. Keep `SKIP_DIRS` containing `downloaded_examples` (`test_scanner_skip_dirs`).

## Shared Patterns

### Gate by marker, report by count, never skip
**Source:** `tests/conftest.py` `pytest_collection_modifyitems` + run-temp record files (lines 53-79, 243-300).
**Apply to:** `corpus` and `needs_kicad` handling, the skip-budget script's input, `tests/test_corpus_gate.py`.
Avoid module-level `pytest.mark.skipif(not path.exists())` for corpus data (PITFALLS 11). Existing skip sites such as `test_fixture_originality`'s `pytest.skip(...)` and `test_edits.py:106` convert to the marker.

### Slow rule for real git
**Source:** `tests/test_markers.py` static audit of `requires_git` and `_OFFENDER_HINT`.
**Apply to:** any new test that builds a repo (scan git-walk test, split-script tests): add `pytestmark = pytest.mark.slow`.

### Synthetic-only fixtures, public part numbers allowed
**Source:** `tests/vendorfixtures.py` docstring; `tests/customfixtures.py:40` `UL_PART_TOKENS = ("CSD85301Q2", "DQK0006B", "DLV0006A")` must keep matching the builder.
**Apply to:** the UL builder; D-10 allows the MPNs and generic `Atomic_<stem>` names.

### Stdlib-only scripts, no workstation paths, no owner identity
**Source:** `.claude/CLAUDE.md` conventions; RESEARCH anti-pattern list.
**Apply to:** everything under `scripts/` and the new CLAUDE.md files.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/workflows/ci.yml` | config | n/a | No CI exists. Use RESEARCH "Windows CI (D-20)" section (windows-latest, bare `pytest`, `scripts/check_skip_budget.py`, `scripts/prepublish_scan.py`). |
| `.githooks/commit-msg` | hook | transform | No hooks exist; strips `Claude-Session:` lines (RESEARCH Collection-Side Cutover section 6). Enable via `core.hooksPath` in the tool checkout. |
| `scripts/split/*` orchestration | batch | file-I/O + git | No scripted-git precedent; use `git archive pre-split -- <allow-list>` per RESEARCH Pattern 1 and the explicit path list (never `git rm -r .` or `git clean -fdx` in the checkout KiCad reads). |

## Metadata

**Analog search scope:** `tests/` (conftest, vendorfixtures, zipfixtures, runfixtures, test_isolation, test_markers, test_vendorfixtures, test_zipfixtures), `kicad_lib_manager/procs.py`, `kicad_lib_manager/gitops.py`, `pyproject.toml`, tracked root files.
**Files scanned:** about 12 read; tracked top-level listing checked with `git ls-files`. No `scripts/`, `.github/` or `.githooks/` directories exist.
**Pattern extraction date:** 2026-11-24
