---
phase: 14-test-suite-speed-up
fixed_at: 2026-11-23T00:00:00Z
review_path: .planning/phases/14-test-suite-speed-up/14-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-11-23
**Source review:** .planning/phases/14-test-suite-speed-up/14-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

Info findings (IN-01..IN-05) are out of scope for this run and remain in REVIEW.md.
Edits and commits were made in the main checkout (no worktree), as the caller directed. Targeted tests ran there with `-n 0`; the full and quick suites were not run.

## Fixed Issues

### WR-01: A failed template build cannot be retried on Windows

**Files modified:** `tests/gitfixtures.py`, `tests/conftest.py`
**Commit:** 0877972
**Applied fix:** The rebuild step now removes a leftover half-built folder with a read-only-aware `remove_tree` instead of `shutil.rmtree(..., ignore_errors=True)`, so `folder.mkdir()` no longer raises `FileExistsError`. `_force_remove` and a version-aware `remove_tree` wrapper now live in `gitfixtures.py` (public name `remove_tree`, so conftest does not import a private name). `conftest.py` imports `remove_tree` lazily in `pytest_sessionfinish` and its own copy of `_force_remove` and the unused `stat` import are gone. Checked a tree holding a read-only file: `remove_tree` deletes it and `mkdir` then succeeds.

### WR-02: Lock acquisition and release do not tolerate Windows delete-pending files

**Files modified:** `tests/gitfixtures.py`
**Commit:** 7ba3f27
**Applied fix:** Taking the lock now treats `PermissionError` like `FileExistsError` (keep polling until `done` appears or the deadline passes), but only on `win32`. On other platforms a `PermissionError` is a real fault and is re-raised. The deadline message now names the exception type. Releasing the lock swallows `OSError` from `lock.unlink`, so it cannot replace the build's own exception or fail a successful build whose `done` marker is already written.

### WR-03: `choose_setting` excludes a setting forever once any tenrun for it has failed

**Files modified:** `.planning/phases/14-test-suite-speed-up/measure.py`
**Commit:** d2f430f
**Applied fix:** Added `_newest_tenrun` (newest tenrun per `(n, dist)` for the selection, same shape as `_newest_matrix`) and `choose_setting` now drops only settings whose newest tenrun failed. Self-test gained three cases: failed tenrun then passing tenrun keeps the setting, passing then failed drops it again, and a failed tenrun of another setting does not affect this one. `measure.py self-test` passes.

Verification of the caller's `choose` conditions, with one discrepancy that is not caused by this change:
- `choose --check-pyproject` does NOT currently print `-n 8 --dist worksteal` and exits 1, both before and after this commit (checked against the HEAD version of measure.py). Cause: the newest serial record is the "after-crash-fix" run (`serial-20261122T233825`, 11681 passed), while all six matrix records carry the older serial's counts (11680 passed). `same_counts` therefore rejects every matrix setting, and `choose` reports "no matrix setting exited 0 with the serial reference's counts". Nothing was written to the store by these runs.
- With the older serial record as reference (same counts as the matrix), both the old and the new `choose_setting` return `(8, 'worksteal')`, and pyproject addopts are `-n 8 --dist worksteal`. So the fix does not change the chosen setting.
- `build_report` over the real store is byte-identical before and after the change, and identical to the committed `MEASUREMENTS.md`, so no regeneration was needed or done. Verdict lines unchanged: TEST-04 met (68.08 s, 69.22 s), TEST-05 met (slowest 338.57 s <= 781.96 s), TEST-08 met (10 consecutive runs equal to the serial reference).
- Decision for the orchestrator: restoring a passing `choose` needs a fresh matrix measurement after the crash fix (or an explicit decision about which serial record is the reference). I did not edit the store or the reference selection, since that would alter measurement evidence.

### WR-04: A stale assertion in `test_templates_are_built_once` can never fail

**Files modified:** `tests/test_isolation.py`
**Commit:** 28457e6
**Applied fix:** Removed the `before` glob and the final `gitfixture_template_*` comparison against the system temp folder, plus the now-unused `import tempfile`. I removed the check rather than replacing it: templates are created under `<basetemp>/git_templates`, and the run-level assertion directly above (`not (tmp_path / "bt" / "git_templates").exists()`) already checks that real location after the child run's session finish. A replacement glob over the system temp folder would only add flakiness from unrelated runs.

## Verification (where it ran)

All runs were in the main checkout, `env/Scripts/python.exe -m pytest -n 0`, no worktree:
- `tests/test_isolation.py --full` (includes the slow 4-worker template test, run after WR-01/WR-02 and again after WR-04): 14 passed.
- `tests/test_customfixtures.py tests/test_markers.py tests/test_isolation.py` (final state): 48 passed, 3 deselected (slow).
- `--full tests/test_commit_step.py -k commit` (real git through the shared template, after WR-01/WR-02): 123 passed.
- `measure.py self-test`: ok.

---

_Fixed: 2026-11-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
