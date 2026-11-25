---
phase: 15-choose-library-folder-and-new-collection
reviewed: 2026-11-23T00:00:00Z
depth: standard
pass: 2 (gap-closure diff 160f85c..HEAD, plans 15-13..15-16)
files_reviewed: 18
files_reviewed_list:
  - kicad_lib_manager/widgets/background.py
  - kicad_lib_manager/main_window.py
  - kicad_lib_manager/widgets/choose_folder_dialog.py
  - kicad_lib_manager/widgets/first_run_dialog.py
  - kicad_lib_manager/widgets/new_collection_dialog.py
  - kicad_lib_manager/widgets/import_dialog.py
  - kicad_lib_manager/library_scanner.py
  - kicad_lib_manager/models.py
  - kicad_lib_manager/scan_cache.py
  - kicad_lib_manager/widgets/help_dialog.py
  - tests/hungcheckchild.py
  - tests/test_exit_with_hung_check.py
  - tests/test_background.py
  - tests/geometryfixtures.py
  - tests/dialoggeometrychild.py
  - tests/test_dialog_geometry.py
  - tests/test_empty_libraries.py
  - tests/test_main_window_root.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
  necessity: 0
status: issues_found
---

# Phase 15: Code Review Report (pass 2, gap-closure diff)

**Reviewed:** 2026-11-23
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Previous review

The first review (CR-01, CR-02, WR-01..WR-07, IN-01..IN-03) was fixed or dispositioned as recorded in
`15-REVIEW-DISPOSITION.md` (10 fixed, 2 deferred: IN-01, IN-03; both still deferred and untouched by this
diff). This pass covers only the gap-closure changes since 160f85c; finding IDs continue at CR-03 / WR-08 /
IN-04 so they never collide with the earlier ones. No new Critical finding exists, so no CR-03 is issued.

## Summary

The daemon-thread runner (`widgets/background.py`) holds up under adversarial reading. I traced these cases and
found no defect:

- The worker thread touches no Qt object. It runs `fn` and does `SimpleQueue.put`. Every callback runs from the
  dispatcher's QTimer on the GUI thread.
- `cancel()` and `_drain()` both run on the GUI thread, so the cancel-versus-delivery race cannot interleave. A
  late outcome of a cancelled task fails the `task not in self._pending` test and is dropped.
- Delivery removes the task from `_pending` before it runs the callback. A callback that starts or cancels
  another task is safe, and `_stop_if_idle` runs after the loop.
- A stale dispatcher is handled: `_existing_dispatcher` catches the `RuntimeError` of a deleted C++ object.
- The request-counter rules in `main_window._on_root_checked`, `ChooseLibraryFolderDialog._on_checked` and
  `NewCollectionDialog._on_checked` are unchanged, so a superseded result is still dropped.
- The creation task is never cancelled, and `done`, `reject` and `closeEvent` all refuse while `_creating` is
  set. Ctrl+Q routes through `close()`, so no in-app exit path abandons a creation thread.
- No QSettings or scan-cache write leaks out of the child-process tests: the scan cache sits beside the
  redirected `settings.ini`.

The empty-flag detection (`_SYMBOL_RE`, `_pretty_holds_footprint`) fails safe. An unreadable file or folder
counts as not empty, and a false "empty" would need a `.kicad_sym` with no quoted `(symbol "`, which KiCad
never writes. The format 3 cache bump is enforced before any decode, and the existing fingerprint covers the
files and folders involved. The Destination rule is correct for a Destination elsewhere, which is neither
changed nor written to history. I ran `test_background`, `test_empty_libraries`, `test_exit_with_hung_check`
and `test_dialog_geometry`: 31 passed in 9 s.

Remaining concerns: one new GUI-thread disk access on the switch path, one test that does not test what it
claims, and robustness gaps in the runner.

## Warnings

### WR-08: `_switch_root` now runs `Path.is_dir()` on every Destination history entry on the GUI thread, against its own "no disk access" comment

**File:** `kicad_lib_manager/main_window.py:915-918` (calls `_set_dest_items`, `main_window.py:979-993`)
**Issue:** The new follow branch calls `self._set_dest_items(add_dest_to_history(str(path)))`, and the comment
above it says "Spelling only: no disk access on the GUI thread". `_set_dest_items` filters the whole history
(up to 10 entries) with `Path(entry).is_dir()`, a synchronous check on the GUI thread. One history entry on a
disconnected network drive therefore freezes the window for tens of seconds at the moment of the switch. That
is the dead-drive scenario this phase hardens everywhere else: UAT 5 and the whole 15-13 daemon-thread move.
The follow rule only runs when Destination was the old folder or blank, so it is the common case, not a
corner. `_populate_dest_combo` has the same cost at start, which predates this diff. The new call site puts it
in a path that the gap closure claims is free of disk access, and the `Source.KICAD` switch is also affected.
The switch is already running off the checked, usable `path`; only the history filter blocks.
**Fix:** Do not stat the history on the GUI thread in the follow branch. The new folder just passed
`check_folder`, so show it first and keep the old existence filter off this path. Either:
```python
# in _switch_root, follow branch
history = add_dest_to_history(str(path))
self._dest_combo.blockSignals(True)
self._dest_combo.clear()
self._dest_combo.addItems([str(path)] + [h for h in history[1:] if h.strip()])  # no stat here
self._dest_combo.setCurrentIndex(0)
self._dest_combo.blockSignals(False)
```
or give `_set_dest_items` an `check_exists=False` parameter, or run the existence filter through
`run_in_background` like the Recent menu does. Add a test that monkeypatches `Path.is_dir` to record the
calling thread (as `test_recent_menu_checks_existence_off_the_gui_thread` does) and switches with a Destination
that follows.

### WR-09: `test_a_raising_callback_does_not_stop_the_next_delivery` passes without the guard it names

**File:** `tests/test_background.py:67-81`
**Issue:** The test is meant to pin the `try/except` around `task._deliver` in `_Dispatcher._drain`
(`background.py:105-109`). Both tasks wait on one gate and finish together, but nothing forces them into the
same drain tick. If the guard is removed, the exception from the first callback is reported by PySide through
`sys.excepthook` and the loop is left. The second outcome stays in `_outcomes` and the next 15 ms tick
delivers it, so every assertion still holds. I verified this by running the test body against a copy of
`_drain` with the guard removed (scratch run, source untouched): it passed. The test gives false assurance for
the one behaviour the docstring "One failing callback must not stop the next delivery" promises.
**Fix:** Make both outcomes land in a single drain, then call the drain directly:
```python
dispatcher = background._dispatcher()
dispatcher._timer.stop()                       # no tick between the two puts
first = run_in_background(lambda: 1, bad)
second = run_in_background(lambda: 2, got.append)
qtbot.waitUntil(lambda: not first.is_running() and not second.is_running(), timeout=5000)
dispatcher._drain()                            # one drain must deliver both
assert [str(e) for e in reported] == ["callback failed"] and got == [2]
```
(`run_in_background` re-starts the timer on `add`; stop it again after both are added, or call `_drain` while
holding the order by waiting until both threads have returned and then draining once.)

### WR-10: A task can be left pending forever (no outcome), which also blocks the Recent check and keeps the poll timer running

**File:** `kicad_lib_manager/widgets/background.py:159-180`
**Issue:** Two paths register a task with the dispatcher and never produce an outcome:
1. `work()` catches only `Exception`. If `fn` raises a `BaseException` that is not an `Exception`
   (`SystemExit`, `KeyboardInterrupt` raised in the worker, `GeneratorExit` from a library), the `finally`
   decrements the counter and sets `_returned`, but nothing is put on `_outcomes`. The task stays in
   `_pending`: `is_done()` is never true, the 15 ms timer polls forever, and `_refresh_recent_existence`
   (`running.is_done()`) never starts another Recent check. `startup.check_in_time` already catches
   `BaseException` for the same reason.
2. `dispatcher.add(task)` and the counter increment happen before `thread.start()`. If `start()` raises
   (`RuntimeError: can't start new thread` under resource pressure), the exception reaches the caller but the
   task stays in `_pending` and `_started_not_returned` is never decremented.
Both are rare, but the failure mode is a silent, permanent dead feature plus a timer that never stops.
**Fix:**
```python
def work():
    global _started_not_returned
    try:
        try:
            outcome = (True, fn())
        except BaseException as exc:          # report it; the dispatcher decides
            outcome = (False, f"{type(exc).__name__}: {exc}")
        _outcomes.put((task, outcome[0], outcome[1]))
    finally:
        ...
thread = threading.Thread(target=work, daemon=True, name=name)
with _count_lock:
    _started_not_returned += 1
dispatcher.add(task)
try:
    thread.start()
except BaseException:
    with _count_lock:
        _started_not_returned -= 1
    dispatcher.forget(task)
    raise
```

## Info

### IN-04: `_parse_footprint_refs` is dead code after the refactor

**File:** `kicad_lib_manager/library_scanner.py:523-524`
**Issue:** Both callers (`find_symbol_libs`, `_refresh_symbol_library`) now call `_symbol_file_facts`. A search
of the repository finds no remaining use of `_parse_footprint_refs`, in the package or in the tests. It is a
leftover wrapper that will drift from `_symbol_file_facts`.
**Fix:** Delete `_parse_footprint_refs`.

### IN-05: `fit_height_to_content` only grows the dialog and never clamps to the screen

**File:** `kicad_lib_manager/widgets/new_collection_dialog.py:63-84`
**Issue:** The function raises the minimum height to what the layout needs and resizes up when short, but never
clamps to `screen().availableGeometry()` and never shrinks back. Two consequences:
1. A tall strip (a wrapped failure row at 175% on a small screen) can set a minimum height above the available
   area. The user then cannot shorten the window to reach buttons by moving it. The UAT already recorded a
   5 px overflow offscreen at 175%.
2. After a long row disappears the dialog stays tall with an empty band, although the minimum shrinks.
Neither recurses (`_fitting` guards the resize) and neither breaks a requirement, so this is cosmetic.
**Fix:** Clamp: `needed = min(needed, dialog.screen().availableGeometry().height() - frame_margin)`, and let the
layout scroll or elide beyond that. Optionally `resize` down when the content shrank and the user did not
resize the dialog by hand.

### IN-06: The runner's GUI-thread-only contract is unenforced, and orphaned outcomes of cancelled tasks wait in the queue

**File:** `kicad_lib_manager/widgets/background.py:30, 128-138, 147-160`
**Issue:**
1. `run_in_background` is documented "GUI thread only" but never checks it. Called from another thread, the
   lazy `_dispatcher()` would create the QObject and QTimer with that thread's affinity, and the timer would
   never fire on the GUI thread. A one-line assertion removes the whole class of mistake.
2. `_outcomes` is a process-wide queue drained only while some task is pending. After `cancel()` stops the
   timer, the cancelled task's late outcome (and its payload, such as a `FolderCheck`) sits in the queue until
   the next `run_in_background`. It is dropped then, but it is retained until that moment.
**Fix:** Add `if QThread.currentThread() is not QCoreApplication.instance().thread(): raise RuntimeError(...)`
in `_dispatcher()`. For the queue, let the worker skip the `put` when `task._finished` is already set (a plain
bool read), so a cancelled task never leaves an entry behind.

### IN-07: `test_folder_checks_never_use_a_qthread` pins an exact count of `TaskWorker(` calls

**File:** `tests/test_exit_with_hung_check.py:62-66`
**Issue:** `assert len(calls) == 2` ties a guard against dead-drive checks to the number of KiCad-open checks in
`main_window.py`. A legitimate third `TaskWorker` for a non-folder job fails the guard, and an aliased
constructor (`from ... import TaskWorker as W`) bypasses it. That is the same class as the deferred IN-03.
**Fix:** Assert on the intent instead: collect each `TaskWorker(...)` call's enclosing function and require it
to be one of the two `kicad_running` users (`main_window.py:2016` and `:2117`), or allow a
named allowlist. Leave the module-level `TaskWorker`/`QThread` name ban for the three dialogs as is.

---

_Reviewed: 2026-11-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
