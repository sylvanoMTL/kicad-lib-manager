---
phase: 15-choose-library-folder-and-new-collection
plan: 09
subsystem: collection-contract
tags: [literal-sweep, layering, guard, collection]
requires: ["15-01", "15-02", "15-03", "15-04", "15-05", "15-06", "15-07", "15-12"]
provides:
  - "test_no_custom_literal: AST guard over every non-importer package module"
  - "collection registered in tests/test_layering.py as {models, fsutil, gitops}"
affects: [Phase 16 repo split, Phase 17 ThirdParty catalogs]
tech-stack:
  added: []
  patterns: ["one module names the collection folders; an AST test holds the literal"]
key-files:
  created: []
  modified:
    - tests/test_custom_literals.py
    - tests/test_layering.py
    - kicad_lib_manager/atomic_check.py
    - kicad_lib_manager/atomic_fixes.py
    - kicad_lib_manager/changes.py
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/scan_cache.py
    - kicad_lib_manager/kicad_setup.py
    - kicad_lib_manager/main_window.py
key-decisions:
  - "_determine_source delegates to collection.source_of; kicad_setup.same_folder is now collection.same_folder (imported, so the name keeps working for callers and tests)"
requirements-completed: [ROOT-01, ROOT-06]
status: complete
duration: 20 min
completed: 2026-11-23
actuals:
  tokens: 9000
  tasks: 2
  commits: 3
plan_head_before: e13d7fd984c66b2fc52383bb33f941815330d668
plan_head_after: 5b45d26d33b5ab80b130f5a4bd83d378709669c9
---

# Phase 15 Plan 09: Core half of the Custom literal sweep Summary

The `Custom` literal now lives only in `collection.py`: the atomic check, fixes, change marks, scanner, saved scan, KiCad setup and main window read `OWN_DIR`, `FOOTPRINTS_DIR` and `MODELS_DIR`, and a parametrised AST test fails the run if it comes back anywhere in the package.

## What was done

- **Task 1 (RED then GREEN):** added `test_no_custom_literal[<module>]` (one parameter per non-importer package module). It failed for atomic_check.py, atomic_fixes.py, changes.py, library_scanner.py, main_window.py and scan_cache.py (6 failed, 77 passed). Registered `collection` in tests/test_layering.py as `{models, fsutil, gitops}`, added it to the entries of atomic_check, atomic_fixes, changes, library_scanner, scan_cache and kicad_setup, and added `kicad_lib_manager.collection` to the Qt-free `_CODE` proof. Swept atomic_check (3 sites), atomic_fixes (3), changes (1).
- **Task 2:** swept library_scanner (4 sites: `_desired_path_vars`, `_custom_model_names`, two source comparisons), scan_cache (3), main_window (1). `_determine_source` now returns `collection.source_of(rel_path)`. kicad_setup's own `same_folder` body and the now-unused `import os` were removed; `same_folder` is imported from `.collection`.

AST walk outside the importer package: **15 sites before, 0 after** (collection.py excluded). The guard has 83 passing parameters/tests in tests/test_custom_literals.py.

## Verification

- tests/test_custom_literals.py, tests/test_layering.py, tests/test_importer_layering.py: 115 passed.
- tests/test_layering.py, test_atomic_check, test_atomic_fixes, test_atomic_scan, test_scan_changes: 206 passed.
- test_scanner_skip_dirs, test_scan_cache, test_kicad_config, test_kicad_setup, test_checkout_check, test_rescan_library, test_main_window_migration: 200 passed (slow tests deselected, not run with `--full`).
- Extra: test_scan_skip, test_scanner_issues, test_main_window, test_main_window_root, test_main_window_chooser, test_atomic_scan: 204 passed.
- All existing tests pass unchanged. Values written are byte-identical, so the saved-scan fingerprint is unchanged; the code-signature change gives one full scan after the update, as for any scanner edit.

## Deviations from Plan

None - plan executed exactly as written. Notes: the TDD RED test was committed on its own (a5c359a, fails at that commit by design); the layering edit was committed with the sweep (cfbef9e). One behaviour nuance: `_determine_source("")` now returns "Unknown" (collection.source_of) where it returned ""; the scan never passes an empty path, and `ThirdParty/<id>` now yields the id as the plan intends for Phase 17.

## Known Stubs

None.

## Threat Flags

None. T-15-28 is mitigated by `test_no_custom_literal`.

## Commits

- a5c359a test(15-09): guard the Custom literal in every non-importer package module (RED)
- cfbef9e feat(15-09): register collection in the layering map; atomic modules read the folder constants
- 5b45d26 feat(15-09): scanner, saved scan, KiCad setup and main window read the collection constants

## Self-Check: PASSED
