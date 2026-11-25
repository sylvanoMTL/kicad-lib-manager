---
phase: 14-test-suite-speed-up
reviewed: 2026-11-23T00:00:00Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - tests/conftest.py
  - tests/gitfixtures.py
  - tests/runfixtures.py
  - tests/customfixtures.py
  - tests/test_isolation.py
  - tests/test_markers.py
  - tests/test_customfixtures.py
  - tests/test_main_window.py
  - tests/test_roundtrip_corpus.py
  - tests/test_manifests.py
  - tests/test_docs_atomic.py
  - pyproject.toml
  - requirements-dev.txt
  - .planning/phases/14-test-suite-speed-up/measure.py
  - tests/test_atomic_uat.py
  - tests/test_commit_deletions.py
  - tests/test_commit_gate.py
  - tests/test_commit_gate_panel.py
  - tests/test_commit_step.py
  - tests/test_gitops.py
  - tests/test_import_dialog.py
  - tests/test_migration_commit.py
  - tests/test_migration_full.py
  - tests/test_migration_precheck.py
  - tests/test_rescan_library.py
  - tests/test_scan_cache.py
  - tests/test_scan_changes.py
  - tests/test_scanner_issues.py
  - tests/test_scanner_skip_dirs.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
  necessity: 0
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-11-23
**Depth:** standard
**Files Reviewed:** 29
**Status:** issues_found

## Summary

The harness is carefully built and the isolation design holds up under inspection. I found no way for a test to reach the real `%APPDATA%`, `settings.ini`, KiCad config or live `Custom/` through the paths the suite uses today:

- No fixture has module, class or package scope, so nothing runs before the per-test `_isolated_user_state`. The only session fixtures are the three guards, and `_qsettings_sandbox` covers QSettings for them.
- Every app path that reads user state (`settings.get_settings`, `scan_cache_file`, `migration_draft_file`, `default_backup_dir`, `find_kicad_config_dir`) derives from the redirected environment or from QSettings. `test_user_state_is_redirected` pins each one.
- The marker-only edits are all on real test functions. An AST sweep found no `@pytest.mark.slow` on a helper, fixture or non-test.
- I ran `test_docs_atomic.py`, `test_manifests.py` and `test_markers.py` with `-n 0`: 16 passed.

The real defects are in the shared git template's failure path (it is broken on Windows), the lock's Windows delete-pending race, one permanent-exclusion rule in `measure.py` that can mis-judge a re-measure, and one vacuous assertion left over from the old template design. Everything else is latent or low impact.

## Warnings

### WR-01: A failed template build cannot be retried on Windows (rmtree ignores read-only git objects, then mkdir raises)

**File:** `tests/gitfixtures.py:208-211`
**Issue:** The `_template` docstring promises "a failed build leaves no marker, so the next caller rebuilds". The rebuild step is `shutil.rmtree(folder, ignore_errors=True)` followed by `folder.mkdir()`. Git writes loose objects read-only on Windows, and `shutil.rmtree` cannot unlink read-only files there without an error handler. With `ignore_errors=True` the failure is swallowed and the folder survives, so `folder.mkdir()` raises `FileExistsError`. I reproduced this on this machine: after `rmtree(ignore_errors=True)` on a tree holding a read-only file, `exists` is `True` and `mkdir()` raises `[WinError 183]`.

So the first transient failure of a build (a git timeout, AV interference, `_build` dying after the first commit) turns every later caller's error into an unrelated `FileExistsError`. The retry never happens, and the real cause is lost. `conftest.py` already has `_force_remove` for this exact case, but `gitfixtures.py` cannot import it.

**Fix:**
```python
def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)

...
if not done.exists():
    if folder.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(folder, onexc=_force_remove)
        else:
            shutil.rmtree(folder, onerror=_force_remove)
    folder.mkdir()
```
Move `_force_remove` into `gitfixtures.py` and have `conftest.py` import it, so there is one copy.

### WR-02: Lock acquisition and release do not tolerate Windows delete-pending files

**File:** `tests/gitfixtures.py:195-219`
**Issue:** The loop treats only `FileExistsError` as "someone else holds the lock". On Windows, `os.open(lock, O_CREAT | O_EXCL)` on a file that was just unlinked but is still delete-pending (an AV scanner or the search indexer holding a share-delete handle) raises `PermissionError`, not `FileExistsError`. The docstring already names the virus scanner as the reason the template is published by marker rather than by rename, so the author knows this is real. Under 8 workers, the waiters poll every 0.25 s exactly when the builder unlinks its lock, so the window is hit regularly enough to matter. The waiter then errors out instead of seeing `done`.

The same scanner behaviour makes `lock.unlink(missing_ok=True)` in the `finally` able to raise `PermissionError`. That would replace a build exception, or turn a successful build into an error even though `done` is already written.

**Fix:**
```python
try:
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
except (FileExistsError, PermissionError):
    ...  # same deadline and sleep as today
...
finally:
    os.close(handle)
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        pass  # a leftover lock is harmless once `done` exists; waiters leave the loop on `done`
```

### WR-03: `choose_setting` excludes a setting forever once any tenrun for it has failed

**File:** `.planning/phases/14-test-suite-speed-up/measure.py:608-618`
**Issue:** `failed` is the set of `(n, dist)` for every tenrun record with `not r.get("ok")`, ignoring order. The store is append-only, and this phase already did a re-measure ("after-crash-fix"). If a setting's first tenrun fails and a later tenrun of the same setting passes, `choose` still drops it, because the old failed record never ages out. `matrix` records are handled correctly by `_newest_matrix` (newest wins), so this is inconsistent. The self-test only covers "failed tenrun drops the setting" and never "newer ok tenrun reinstates it". The effect would be a wrong or missing `Chosen setting` verdict after exactly the fix-and-remeasure loop `MEASURE.md` prescribes.

**Fix:** Judge only the newest tenrun per `(n, dist)` and selection:
```python
newest_ten: dict[tuple, dict] = {}
for r in records:
    if r.get("kind") == "tenrun" and r.get("selection", []) == list(selection):
        newest_ten[(r.get("n"), r.get("dist"))] = r
failed = {key for key, r in newest_ten.items() if not r.get("ok")}
```
Add a self-test case for `[failed tenrun, later ok tenrun]` choosing that setting.

### WR-04: A stale assertion in `test_templates_are_built_once` can never fail

**File:** `tests/test_isolation.py:41,53`
**Issue:** `before`/`after` glob `tempfile.gettempdir()` for `gitfixture_template_*`. Templates now live under the run's base temp (`<base>/git_templates`), so nothing is ever created under that name. The comparison is permanently true and gives false assurance that no template leaks into the system temp folder. The real leak check is the line above it (`not (tmp_path / "bt" / "git_templates").exists()`). An unrelated run in the machine's temp folder could also make the comparison flaky.

**Fix:** Delete lines 41 and 53. If a leak into the system temp folder is the concern, assert the template path directly:
```python
assert not any(Path(tempfile.gettempdir()).glob("**/git_templates"))  # only if the system temp must stay clean
```

## Info

### IN-01: The template's `.gitmodules` URL names the shared template remote

**File:** `tests/gitfixtures.py:138,242-248`
**Issue:** `_build` runs `git submodule add <template>/custom_remote.git Custom`, which commits an absolute template path into `.gitmodules`. After the copy, `make_superproject` rewrites `remote.origin.url`, `submodule.Custom.url` and the submodule's `remote.origin.url`, but not the committed `.gitmodules`. Nothing today runs `git submodule sync` or `update --init` on a copy (only `make_worktree`, where the registered config URL wins), so there is no live bug. A future test that does either would read from or push to the one remote shared by all workers and tests, which is cross-test contamination.

**Fix:** In `_build`, add the submodule with a relative URL, `git submodule add ../custom_remote.git Custom`. It resolves against the superproject's remote, so every copy gets its own sibling remote. Alternatively, set `submodule.Custom.url` and `.gitmodules` in `make_superproject`.

### IN-02: `_rc` reports success when pytest exits 1 (tests failed)

**File:** `.planning/phases/14-test-suite-speed-up/measure.py:485-491`
**Issue:** `_rc` returns 1 only for a timeout or an exit code of 2 or more. `serial`, `full` and `matrix` therefore return 0 for a run with failing tests. Verdict logic is unaffected, because `choose_setting`, `tenrun` and `quick` all check `exit == 0` themselves. A scripted orchestrator that trusts the process exit code would treat a failing serial reference as fine. A failing serial run also becomes the reference that the ten-run equality check compares against.

**Fix:** Return 1 for any non-zero exit. Keep the BASELINE allowance for a known failure as an explicit flag if it is still needed.

### IN-03: `_join_widget_threads` ignores the result of `QThread.wait`

**File:** `tests/conftest.py:322`
**Issue:** `thread.wait(60000)` returns `False` on timeout, and teardown carries on to close and delete the widget anyway. Qt then aborts the whole worker process ("Destroyed while thread is still running"). Under xdist that shows up as an unattributed worker crash, and the failing test's own error is lost. Current gated tests cap their waits at 5 s, so this is latent.

**Fix:** If `wait` returns `False`, call `pytest.fail` naming the item and thread class, or `thread.terminate()` first, so the failure is attributed.

### IN-04: Wall-clock assertions in the child-run meta-tests

**File:** `tests/test_isolation.py:67,81`
**Issue:** `assert elapsed < 30` includes interpreter start-up, a PySide6 import in each child worker and the child's session setup. These tests run inside the 8-way parallel suite and are timing-sensitive on a loaded or cold machine. The 2 s `--timeout` also covers the first test's session-fixture setup (the PySide6 import), so a slow import can trigger it before the test body starts. The ten-run measurements passed, so this is a flake risk, not a defect.

**Fix:** Widen the bound (60 s) or assert on the TIMEOUT line only. Use `--timeout 5` to leave margin for session setup.

### IN-05: The app-state guard fails the run if the owner uses the app during it

**File:** `tests/conftest.py:223-226`
**Issue:** A change to the owner's `settings.ini`, `scan_cache`, `migration_draft` or backups fails the run. The GUI itself writes those files, and a full parallel run is about 5.5 minutes, so the owner running the app meanwhile produces a false failure. The KiCad-config branch already warns with "was KiCad open?". The app branch carries no such hint, and the owner has to work out that a rerun is the answer.

**Fix:** Keep the failing exit, but append "if the app was open during the run, close it and rerun" to the message.

---

_Reviewed: 2026-11-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
