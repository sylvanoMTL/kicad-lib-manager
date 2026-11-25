---
phase: 15-choose-library-folder-and-new-collection
plan: 12
subsystem: importer, layering-guard
tags: [collection, literal-sweep, ast-guard, layering]
requires: ["15-01", "15-02", "15-03"]
provides:
  - "tests/test_custom_literals.py helpers custom_literals(source), package_modules(), IMPORTER_MODULES"
  - "test_no_custom_literal_in_importer[<module>] (one parameter per importer module)"
  - "test_shared_footprint_library_matches (stems and collection constants held equal)"
affects: [15-09]
tech-stack:
  added: []
  patterns: ["AST walk with docstring ids excluded; string Constant == 'Custom' or starts 'Custom/' or '/Custom'"]
key-files:
  created:
    - tests/test_custom_literals.py
  modified:
    - kicad_lib_manager/importer/layout.py
    - kicad_lib_manager/importer/incoming.py
    - kicad_lib_manager/importer/commit_gate.py
    - kicad_lib_manager/importer/commit_step.py
    - kicad_lib_manager/importer/migration/gate.py
    - kicad_lib_manager/importer/migration/inventory.py
    - kicad_lib_manager/importer/planner.py
    - tests/test_importer_layering.py
decisions:
  - "importer/stems.py keeps its own SHARED_FOOTPRINT_LIBRARY; a test holds it equal to collection's instead of importing it"
  - "migration/gate.py keeps importing SHARED_FOOTPRINT_LIBRARY from migration.inventory; only the Custom literals were swept"
status: complete
metrics:
  duration: "~20 min"
  completed: 2026-11-23
actuals:
  tokens: 5000
  tasks: 2
  commits: 2
plan_head_before: e0f4d80e86ae06535cc24a5eec4c53ad4e818f9e
plan_head_after: 66516448f703b450fa4c2987899f5eb32e7ffc65
---

# Phase 15 Plan 12: Importer literal sweep Summary

The importer package no longer holds the `Custom` literal: every path and message prefix reads `collection.OWN_DIR`, `SYMBOLS_DIR`, `FOOTPRINTS_DIR` or `MODELS_DIR`, and an AST guard fails the run if one comes back.

## Importer sites: before / after

Before: 10 sites in 7 modules (the guard failed 7 module parameters at the RED run). After: 0. Values are unchanged (importer, migration, commit and install tests pass unchanged).

| Module | Site |
|--------|------|
| importer/layout.py | `repo_root / OWN_DIR`, `custom / SYMBOLS_DIR`, `FOOTPRINTS_DIR`, `MODELS_DIR` |
| importer/incoming.py | `FootprintLibrary(..., OWN_DIR)` |
| importer/commit_gate.py | `source=OWN_DIR` |
| importer/commit_step.py | both `_not_pushed(upstream, OWN_DIR, branch)` calls |
| importer/migration/gate.py | `_MODELS_PREFIX`, `shared_folder_rel`, `target_rel` f-strings |
| importer/migration/inventory.py | `"{OWN_DIR}/{SYMBOLS_DIR} still holds ..."` |
| importer/planner.py | `"{OWN_DIR}/{FOOTPRINTS_DIR} holds ..."` |

## Reused by plan 15-09

`custom_literals(source) -> list[tuple[int, str]]`, `package_modules() -> list[str]` (every .py under kicad_lib_manager except collection.py, posix paths), `IMPORTER_MODULES`, and `PACKAGE` in `tests/test_custom_literals.py`. Plan 15-09 adds the twin test for the non-importer modules.

Layering: `collection` is now in the ALLOWED entry of importer.layout, importer.incoming, importer.commit_gate, importer.commit_step, importer.planner, importer.migration.gate and importer.migration.inventory.

## Verification

- `tests/test_custom_literals.py tests/test_importer_layering.py`: 62 passed.
- `tests/test_importer_layering.py tests/test_install_plan.py tests/test_incoming_check.py tests/test_commit_gate.py tests/test_import_dialog.py`: 422 passed.
- `tests/test_migration_gate.py tests/test_migration_inventory.py tests/test_install_plan.py tests/test_categories.py tests/test_commit_step.py`: 208 passed, 1 skipped (local-only SamacSys sample absent), slow tests deselected.

## Deviations from Plan

None - plan executed exactly as written. (Task 2's second automated command and the slow-marked tests were run without `--full`; the git-repo tests of commit_step are `@pytest.mark.slow` and are left to the orchestrator's post-merge run.)

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- tests/test_custom_literals.py exists; commits 0802631 and 6651644 are ancestors of HEAD.
