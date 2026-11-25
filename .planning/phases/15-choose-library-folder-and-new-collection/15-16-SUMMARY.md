---
phase: 15-choose-library-folder-and-new-collection
plan: 16
subsystem: main-window, scanner, scan-cache
tags: [gap-closure, uat-gap-2, uat-gap-4, empty-collection, destination]
requires: ["15-13", "15-10"]
provides:
  - "SymbolLibrary.empty, FootprintLibrary.empty (default False) and ScanResult.holds_nothing"
  - "library_scanner: _symbol_file_facts, _pretty_holds_footprint, _SYMBOL_RE; empty flags set by the full scan and the one-library rescan"
  - "scan_cache FORMAT 3 with the empty flags encoded and decoded (strict bool)"
  - "MainWindow._show_list_page and _apply_focus decide with holds_nothing; _switch_root Destination follow rule"
affects: []
tech-stack:
  added: []
  patterns: ["flags computed by the scan off the GUI thread and carried by the saved scan; no disk access in the window"]
key-files:
  created:
    - tests/test_empty_libraries.py
  modified:
    - kicad_lib_manager/models.py
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/scan_cache.py
    - kicad_lib_manager/main_window.py
    - kicad_lib_manager/widgets/help_dialog.py
    - tests/test_main_window_root.py
    - CLAUDE.md
    - .planning/phases/15-choose-library-folder-and-new-collection/15-UI-SPEC.md
decisions:
  - "A .pretty with no .kicad_mod (suffix compared case-insensitively) and a .kicad_sym with no (symbol \" entry are empty; a file or folder that cannot be read counts as not empty"
  - "The page shows when every library found is empty (ScanResult.holds_nothing); the trees return as soon as one library holds a part"
  - "Destination follows a switch only when it shows the old library folder (spelling comparison) or is blank; the followed folder is also added to the Destination history before the scan starts (Claude's discretion inside the owner decision of 2026-11-23, because the box shows the newest existing history entry at start, so a display-only change would show the old folder again at the next start)"
status: complete
metrics:
  duration: "~30 min"
  completed: 2026-11-23
actuals:
  tokens: 17000
  tasks: 3
  commits: 3
plan_head_before: 37502d507c386a73025e0b058db2889a8eb5e516
plan_head_after: cce6154fb42aab6f1efe74dbd5bada29f4ea5291
---

# Phase 15 Plan 16: Empty collection by content, Destination follows a switch Summary

A new collection (whose skeleton holds an empty `Atomic_Footprints.pretty`) now shows "No libraries in this collection yet" with focus on Import Part..., and the Destination box follows a library folder switch when it showed the old folder or was blank.

## What changed

- **Gap 2 (UAT test 3).** `SymbolLibrary.empty` and `FootprintLibrary.empty` are set by `find_symbol_libs`, `find_footprint_libs` and the one-library rescan (a symbol file is read once for its footprint links and for a symbol entry). `ScanResult.holds_nothing` drives `_show_list_page` and `_apply_focus`. The saved scan is now format 3 and carries the flags; a saved scan of format 2 is not reused (`cache.other_version`).
- **Gap 4 (UAT test 9).** `_switch_root` computes `follow = blank or same_spelling(box text, old root)` before the folder changes, and when true calls `self._set_dest_items(add_dest_to_history(str(path)))` before `_start_scan()`, so the scan pre-selects from the tables at the new Destination. A refused switch returns first, so it changes nothing. A Destination elsewhere keeps its text and the saved history.
- CLAUDE.md, the User Guide's "Changing the library folder" paragraph (a sentence, no new heading) and the UI-SPEC Destination row state the rule.

## RED evidence (at base 37502d5, before any production edit)

- `test_new_collection_skeleton_shows_the_empty_page`: failed with `AttributeError: 'FootprintLibrary' object has no attribute 'empty'` (its first assertion reads the flag).
- `test_skeleton_with_a_footprint_shows_the_trees`: failed on its first assertion, `window._list_stack.currentWidget() is window._empty_page` (the real skeleton showed the trees, `LibraryTableWidget`, which is the UAT shot s3_03 behaviour); this is the page-level RED.
- Scanner, model and cache tests failed on the missing `empty` field / `holds_nothing`; `test_older_cache_format_is_not_reused` failed because format 2 was still accepted.
- Destination tests at the base: five of seven failed (follow from old folder, empty history, blank box, Use KiCad's Folder, pre-selection); the two "stays" tests (elsewhere, refused) passed at the base as expected, they guard the prohibition.

## Deviations from Plan

None - plan executed exactly as written. (`_parse_footprint_refs` stays as the thin wrapper the plan asked for; it has no caller left in the package.)

## Verification

416 tests pass across `tests/test_empty_libraries.py`, `test_main_window_root.py`, `test_main_window.py`, `test_scan_cache.py`, `test_docs_atomic.py`, `test_help_dialog.py`, `test_layering.py`, `test_scanner_skip_dirs.py`, `test_rescan_library.py`, `test_scanner_issues.py`, `test_atomic_scan.py`, `test_annotations_resolve.py` (targeted; the quick and full suites are the orchestrator's). All `<acceptance_criteria>` greps pass (`add_dest_to_history` 4 in main_window.py, `<b>Destination</b>` 2 in help_dialog.py, "Unchanged by a switch" 0 in the UI-SPEC).

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface; the saved scan decoder stays strict (`_flag`), covered by `test_cache_decode_rejects_a_non_boolean_empty_flag`.

## Commits

- ab03a6e feat(15-16): empty collection page follows content, not library count
- 8ca7382 feat(15-16): saved scan carries the empty flags (format 3)
- cce6154 feat(15-16): Destination follows a library folder switch

## Self-Check: PASSED

Files exist (`tests/test_empty_libraries.py`, the modified sources) and commits ab03a6e, 8ca7382, cce6154 are on the branch.
