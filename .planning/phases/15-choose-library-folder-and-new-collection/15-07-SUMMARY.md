---
phase: 15-choose-library-folder-and-new-collection
plan: 07
subsystem: main-window
tags: [library-folder, switch, recent-folders, d-26, path-variables, pyside6]
requires: ["15-01", "15-04", "15-05"]
provides:
  - "MainWindow._switch_root / _request_switch / _switch_refusal: one guarded way to change the library folder"
  - "File > Use KiCad's Folder, Recent Library Folders, Open Library Folder in Explorer"
  - "amber '⚠ KiCad reads a different folder' tag and the start-up D-26 log line"
  - "post-switch KiCad path-variable offer; MainWindow(..., switched=True)"
affects: [15-10]
tech-stack:
  added: []
  patterns:
    - "request counter so only the newest off-thread folder check can switch"
    - "_refresh_library_actions(running=None): _set_scan_running runs before the worker is set or cleared, so it passes the state"
key-files:
  created: []
  modified:
    - kicad_lib_manager/main_window.py
    - tests/test_main_window_root.py
    - tests/test_checkout_warning.py
    - tests/test_main_window_import.py
key-decisions:
  - "Use KiCad's Folder clears library/root and does not add to library/recent (literal reading of the plan action); every other source saves both"
  - "Every switch request bumps the check counter, including refused and same-folder ones, so a slow earlier check can never override a later request"
  - "A switch hides the Generate/Install checkout banner (it described the previous folder)"
requirements-completed: [ROOT-03, ROOT-04, ROOT-08, ROOT-10, ROOT-11, ROOT-12]
status: complete
duration: "~75 min"
completed: 2026-11-23
actuals:
  tokens: 45000
  tasks: 3
  commits: 7
plan_head_before: e0f4d80e86ae06535cc24a5eec4c53ad4e818f9e
plan_head_after: 6c37bad15afa323caa7cc16cedae846fd22b9bf0
commits: 7
---

# Phase 15 Plan 07: Library folder switching in the main window Summary

The main window can now change its library folder while it runs: one guarded `_switch_root`, a Recent Library Folders submenu, Use KiCad's Folder, Open Library Folder in Explorer, the amber "KiCad reads a different folder" tag, and the existing path-variable question offered once after a switch. (`plan_head_after` is the last production commit; the SUMMARY commit follows it, which is why `commits: 7` is one more than `plan_head_before..plan_head_after`.)

## Final signatures (plan 15-10 calls these)

- `MainWindow._request_switch(self, path: Path, source: Source) -> None` - refuses when busy, shows "already using" for the current folder, else checks the folder on a `TaskWorker` and switches only if that is still the newest request and the check is usable; a failed check logs `Not using {path}: {reason}` (error) and a 5000 ms status message.
- `MainWindow._switch_root(self, path: Path, source: Source) -> bool` - refuses again (returns False, changes nothing) when busy; else saves the choice (`Source.KICAD` clears `library/root`, others save `library/root` and `library/recent`), updates title/row/tag/menu, blanks the trees, re-arms `_startup_pending`, arms the path-variable offer (not for `Source.KICAD`), logs the root and starts a full scan. Call it only with a folder that passed `check_folder`.
- `MainWindow._refresh_library_actions(self, running: bool | None = None) -> None` - enables the Recent submenu (needs an entry and no scan) and Use KiCad's Folder, sets their tips and the Open status tip. Pass `running` only from `_set_scan_running`.
- `MainWindow._switch_refusal() -> str | None`, `_refuse_switch(text)`, `_log_root()`, `_rebuild_recent_menu()`, `_open_library_folder()`, `_refresh_root_tag()`, `_offer_path_vars_after_switch()`.
- Constructor: `MainWindow(library_root, source=Source.LEGACY, startup_notes=(), switched=False)`; `switched=True` makes the first scan's end offer the path-variable change.
- Attributes: `_recent_menu`, `_act_use_kicad`, `_act_open_folder`, `_root_check_seq`, `_root_check_workers`, `_offer_vars_after_scan`, `_offer_from_switch`. Module constants and `_elide_middle(text, limit)` as listed in the plan.

## Tasks

| Task | Name | Commits |
| ---- | ---- | ------- |
| 1 | _switch_root, busy guard, off-thread check, Recent submenu | bf97466 (RED), a316b8b |
| 2 | Use KiCad's Folder, Open Library Folder, amber tag, start D-26 line | c3f0f89 (RED), cf1f35d |
| 3 | Path-variable offer after a switch | 4ea043d (RED), 6c37bad |

## Verification

- `tests/test_main_window_root.py`: 59 passed (switch, 8 busy states, stale check, scan error, Recent entries/escaping/elision/rebuild, Use KiCad's states, Explorer, tag, offer cases).
- `tests/test_main_window_root.py test_main_window.py test_main_window_import.py test_main_window_migration.py test_main_window_chooser.py test_checkout_warning.py test_startup.py`: 241 passed.
- `tests/test_docs_atomic.py test_import_dialog.py test_importer_layering.py test_scan_cache.py`: 326 passed.
- Acceptance greps: the four switch/recent defs 4, `add_library_recent` 2, "Check Atomic Parts is open" 1, `QDesktopServices.openUrl` 1, "KiCad reads a different folder" 1, `configured_library_folder` 3, `would_change_path_vars` 2, "KiCad still points at" 1, `_offer_vars_after_scan` 4. Whole suites not run (orchestrator owns that).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing File menu test assumed Import Part is the first action**
- **Found during:** Task 1 verification
- **Issue:** `test_import_action_first_in_file_menu` (tests/test_main_window_import.py) read actions 0 and 1; the library folder items now come first.
- **Fix:** it finds the first separator and checks Import Part and its following separator after it.
- **Commit:** a316b8b

**2. [Rule 1 - Bug] The Generate/Install banner would describe the previous folder after a switch**
- **Found during:** Task 1
- **Fix:** `_switch_root` hides `_checkout_banner` (it is shown again by the next Generate Tables on a mismatch).
- **Commit:** a316b8b

### Plan-shape notes

- `tests/test_checkout_warning.py` counts changed to 2 in the RED commit of Task 2, but the start-up D-26 line was written in the Task 1 constructor edit (`_log_root()` extraction), so those two assertions were already green when committed.
- `_refresh_library_actions` takes an optional `running` argument (plan signature had none) because `_set_scan_running` runs before the worker is set or cleared.
- Use KiCad's Folder does not add the folder to `library/recent` (plan action text); flagged in key-decisions in case 15-10 wants otherwise.
- The tag is recomputed after every path-variable sync (`_on_path_var_check`), which also refreshes the Use KiCad's Folder tip.
- A transient API error interrupted the run during Task 3; work resumed from the committed RED state.

**Total deviations:** 2 auto-fixed, 5 shape notes. **Impact:** none on behavior.

## Known Stubs

None.

## Threat Flags

None. T-15-20 (busy guard checked twice, `test_switch_refused_while_busy` over all eight states), T-15-21 (offer only through the existing confirm, only when `would_change_path_vars`, never after Use KiCad's or at a plain start), T-15-22 (`&` doubled in text only, full path in tooltip/status tip/data), T-15-23 (`QUrl.fromLocalFile` of the existing folder only), T-15-24 (request counter) are covered by tests.

## Self-Check: PASSED

Modified files present; commits bf97466, a316b8b, c3f0f89, cf1f35d, 4ea043d, 6c37bad are ancestors of HEAD; STATE.md and ROADMAP.md untouched.
