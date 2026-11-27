---
phase: 17-library-catalog
plan: 05
subsystem: scanner
tags: [scanner, saved-scan, path-variables, 3d-models, catalog, tdd]

requires:
  - phase: 17-library-catalog
    provides: catalog manifest rules and path_vars (17-04), ThirdParty sources and staging (17-01)
provides:
  - scan checks catalog 3D models by exact name through a model_vars mapping (scan.model_missing)
  - ThirdParty/.staging pruned by the scanner walk and the saved-scan fingerprint; catalog.json in the fingerprint
  - scan_source and remove_source (per-source rescan and drop)
  - extra_vars on the path-variable confirmation, current_path_vars, get_kicad_default_sym_nicknames
  - catalog-aware table descriptions
affects: [17-06, 17-07, 17-08, 17-10, 17-11, 17-13, 17-17]

plan_head_before: d197c0d9055baa0d1b02322284f63dd9917b8522
plan_head_after: 5a40dff380a7b1265340ec2bc90e42aaeca8f128

actuals:
  tokens: 16000
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "The scanner stays catalog-free: variables come in as a plain mapping {catalog id: {VAR: clone folder}}"
    - "One shared helper (_replace_source) swaps one source's libraries and lines and recomputes what spans sources"
    - "Exact, case-sensitive name sets (os.walk) instead of exists() for model files, as _custom_model_names does"

key-files:
  created:
    - tests/test_scan_catalog.py
    - tests/test_scan_source.py
    - tests/test_catalog_path_vars.py
  modified:
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/scan_cache.py
    - kicad_lib_manager/collection.py
    - kicad_lib_manager/table_generator.py
    - tests/test_table_descriptions.py
    - tests/test_layering.py

key-decisions:
  - "Model line text: '[<rel>] 3D model not found in ThirdParty/<id>[/<folder>] (names are case-sensitive): <path>'; the folder part is left out when the variable names the clone itself"
  - "_walk_matches gained skip_top (default True); scan_source walks a clone with skip_top=False so a folder named tests or env inside a clone is part of the source, as in a full scan"
  - "scan_source also runs the atomic check on fresh Atomic_-named libraries of the source and remove_source drops the lines such a library owned (unless another library shares its nickname), so both match a full scan"
  - "remove_source with a source_dir that is not exactly ThirdParty/<id> drops nothing and returns a copy (its return type stays ScanResult)"
  - "scan_source returns rescan.full_needed for a missing folder, a missing previous scan or a folder that is not exactly ThirdParty/<id>"
  - "Extras for the confirmation are filtered to non-empty text names and values; an extra named like KICAD_LIB_GITHUB or CUSTOM_3DMODEL_DIR is ignored"
  - "A saved scan from before this plan stays valid: FORMAT is still 3; the new catalog.json key only changes the fingerprint"

requirements-completed: [CAT-05, CAT-06, CAT-08, CAT-12]

coverage:
  - id: D1
    description: "A footprint under ThirdParty/<id> whose ${VAR}/rest model is not in the folder its variable names gets a scan.model_missing warning by exact (case-sensitive) name; unmapped and KiCad's own variables are not checked; the rule applies only inside ThirdParty/<id>/"
    requirement: "CAT-06"
    verification:
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_var_model_found_and_missing"
        status: pass
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_rule_applies_only_inside_the_clone"
        status: pass
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_kicad_own_and_unmapped_variables_are_not_checked"
        status: pass
    human_judgment: false
  - id: D2
    description: "kicad-embed:// model paths are never reported as absolute; a real absolute path still is"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_kicad_embed_is_not_absolute"
        status: pass
    human_judgment: false
  - id: D3
    description: "ThirdParty/.staging is never entered by the scanner walker or the saved-scan fingerprint; catalog.json at the collection root changes the fingerprint"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_staging_is_never_scanned"
        status: pass
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_catalog_json_changes_the_fingerprint"
        status: pass
    human_judgment: false
  - id: D4
    description: "scan_source and remove_source give the libraries and lines a full scan of the same tree gives, including nickname collisions with Custom (collision_peers on both sides, never renamed), skipped sources and Atomic_-named libraries; previous is never mutated"
    requirement: "CAT-08"
    verification:
      - kind: unit
        ref: "tests/test_scan_source.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Catalog variables go through the existing old -> new confirmation: own variables first, then catalog ones by name, one backup, no write on decline, own variables never replaced, slash and case differences offered as changes, worktree and KiCad-running rules unchanged"
    requirement: "CAT-06"
    verification:
      - kind: unit
        ref: "tests/test_catalog_path_vars.py"
        status: pass
      - kind: unit
        ref: "tests/test_kicad_config.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "A catalog library is described '<id>: <spaced nickname>'; the Wurth description is the same before and after its move"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_table_descriptions.py#test_catalog_library_uses_its_catalog_id"
        status: pass
      - kind: unit
        ref: "tests/test_table_descriptions.py#test_moved_wurth_library_keeps_its_description"
        status: pass
    human_judgment: false
  - id: D7
    description: "Writing catalog variables into KiCad's real settings only after the owner's Yes (no write without a preview)"
    requirement: "CAT-06"
    verification: []
    human_judgment: true
    rationale: "This plan ships the library-level behaviour and its tests on synthetic configs; the dialog the owner answers is built in a later plan and its wording and flow are judged in the owner-run verification."

duration: 12min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 05: Scanner, saved scan and tables learn catalog sources Summary

**The scan checks catalog libraries' `${VAR}` 3D models by exact name, ignores ThirdParty/.staging, rescans or drops one source (`scan_source`, `remove_source`), and offers catalog path variables through the existing old -> new confirmation, all without a catalog import in the scanner.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-11-27T09:17:49Z
- **Completed:** 2026-11-27T09:29:00Z
- **Tasks:** 3 (each a RED test commit then a GREEN feat commit)
- **Files modified:** 9

## Accomplishments

- `model_vars` (catalog id -> {variable: clone folder}) feeds `_check_model_files`, `scan_all`, `check_3d_model_paths` and `rescan_library`; a miss is `Issue(WARNING, "scan.model_missing", "[<rel>] 3D model not found in ThirdParty/<id>[/<folder>] (names are case-sensitive): <path>")`; `unresolved_var_models(clone_dir, footprint_files, var_folders)` is the same rule as a helper.
- `kicad-embed://` models are exempt from the absolute path warning; `ThirdParty/.staging` is pruned in `_walk_matches` and in `scan_cache._walk`; `catalog.json` (mtime, size) is in the fingerprint (FORMAT stays 3). Constants `CATALOG_FILE`, `STAGING_DIR` live in `collection.py`.
- `scan_source(repo_root, previous, "ThirdParty/<id>", kicad_fp_dir=None, *, model_vars=None) -> ScanResult | Issue` and `remove_source(previous, "ThirdParty/<id>", kicad_fp_dir=None) -> ScanResult` share the private helper `_replace_source`, which swaps one source's libraries and lines and recomputes collisions, footprint links and the atomic summary over every library.
- `extra_vars` on `sync_kicad_path_vars`, `would_change_path_vars` and `_desired_path_vars` (own two first, extras sorted by name, own names never replaced); `current_path_vars(*, config_base=None) -> dict | None` reads the newest config read-only; `get_kicad_default_sym_nicknames` gives the stock symbol stems.
- `table_generator.library_description` uses `collection.source_of`; `ALLOWED["table_generator"]` gains `collection`.

## TDD Gate Compliance

All three tasks followed RED -> GREEN; no refactor commits were needed.

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `35f3653` test(17-05) | `75546bf` feat(17-05) |
| 2 | `2f518d6` test(17-05) | `4c983c3` feat(17-05) |
| 3 | `eab6850` test(17-05) | `5a40dff` feat(17-05) |

RED evidence (semantic assessment): the plan is not `type: tdd`, so the format-based `tdd-red-evidence` classifier was not run (pytest is not one of its report formats). Each RED run was read by hand. Task 1: 15 of 16 tests failed on the planned behaviour (an `AssertionError` for the staging, embed and fingerprint cases, a `TypeError` for the unknown `model_vars` keyword, an `AttributeError` for `unresolved_var_models` and `get_kicad_default_sym_nicknames`); the one passing test pins that a folder named `.staging` deeper inside a clone stays scanned. Task 2: all 19 failed with `AttributeError: no attribute 'scan_source'/'remove_source'`. Task 3: 18 failed (`TypeError` for the unknown `extra_vars` keyword and `current_path_vars` missing, an `AssertionError` for the `ThirdParty: ...` description); 10 existing-behaviour tests passed. The test modules were imported as modules (`library_scanner.<name>`) so each test was discovered and failed on its own rather than the whole file failing at import.

## Task Commits

1. **Task 1: catalog 3D models, staging, embed, fingerprint** - `35f3653` (test), `75546bf` (feat)
2. **Task 2: rescan or drop one source** - `2f518d6` (test), `4c983c3` (feat)
3. **Task 3: path variables and table descriptions** - `eab6850` (test), `5a40dff` (feat)

## Files Created/Modified

- `kicad_lib_manager/library_scanner.py` - model_vars rule, unresolved_var_models, embed exemption, staging prune, scan_source, remove_source, extra_vars, current_path_vars, get_kicad_default_sym_nicknames
- `kicad_lib_manager/scan_cache.py` - staging prune and catalog.json in the fingerprint
- `kicad_lib_manager/collection.py` - CATALOG_FILE and STAGING_DIR
- `kicad_lib_manager/table_generator.py` - library_description via source_of
- `tests/test_scan_catalog.py`, `tests/test_scan_source.py`, `tests/test_catalog_path_vars.py` - new quick modules (no git, no network)
- `tests/test_table_descriptions.py`, `tests/test_layering.py` - two description tests; `collection` allowed for table_generator

## Decisions Made

See `key-decisions` above. The one with later consequences: `scan_source` and `remove_source` do not re-judge Custom Atomic_ libraries whose footprint links name a footprint library of the changed source (a full scan does). The atomic rule has one shared footprint library, `Atomic_Footprints`, in `Custom`, so a catalog footprint library is not a link target of atomic parts; a Rescan or the next start's full scan settles any such case.

## Deviations from Plan

None - plan executed exactly as written. Two small additions inside the plan's intent: `scan_source` runs the atomic check on `Atomic_`-named libraries of the source and `_walk_matches` gained a `skip_top` keyword, both so the result equals a full scan (decisions above), each covered by a test.

## Issues Encountered

- A first draft of the staging test expected only `ThirdParty/X/fp.pretty`; `make_collection` also creates `Custom/Footprints/Atomic_Footprints.pretty`. The expectation was corrected in the GREEN commit (test bug, not behaviour).

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None: no new network endpoint, auth path or file access beyond the planned reads of a clone under ThirdParty/<id> and the existing KiCad config write behind the confirmation (T-17-12, T-17-13 mitigated by the tests above).

## Next Phase Readiness

- The main window and workers (later plans) can read the manifest, call `manifest.path_vars` for `model_vars` and `extra_vars`, rescan one source with `scan_source`, drop one with `remove_source`, and show `current_path_vars` states.
- `get_kicad_default_sym_nicknames` is ready for the D-20 collision list.

## Self-Check: PASSED

- Files found: `tests/test_scan_catalog.py`, `tests/test_scan_source.py`, `tests/test_catalog_path_vars.py`, all modified modules.
- Commits found in history: `35f3653`, `75546bf`, `2f518d6`, `4c983c3`, `eab6850`, `5a40dff`.
- Plan verification: the three automated commands pass (623 passed across the scanner, saved scan, table, catalog and layering modules).

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
