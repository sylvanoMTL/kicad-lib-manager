---
phase: 17-library-catalog
plan: 06
subsystem: catalog
tags: [catalog, staging-check, validation, git-lfs, path-variables, collisions, tdd]

requires:
  - phase: 17-library-catalog
    provides: manifest path-variable rules (17-04), unresolved_var_models and stock symbol nicknames (17-05), catalog package and layering guard (17-03)
provides:
  - catalog.validate.validate_staging (files-only check of a download, refusals in the UI-SPEC order)
  - StagingReport, Collision, find_collisions, licence_text, detect_vars, unresolved_models
affects: [17-07, 17-08, 17-09, 17-10, 17-11]

plan_head_before: ffa5f1fd2b3e806ff9af32a18c18b975d22bb361
plan_head_after: cac403b3e0a366d9c80596b2ccf1e973f93a15be

actuals:
  tokens: 10600
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One os.walk pass lists a download (libraries, footprint files, markers, links); .git is skipped and links and junctions are never followed"
    - "Module-private copies of the manifest variable and folder rules, pinned to the manifest by tests because catalog.validate may not import catalog.manifest"
    - "Votes per candidate folder, ties broken by shorter folder then name, so the result never depends on file order"

key-files:
  created:
    - kicad_lib_manager/catalog/validate.py
    - tests/test_catalog_validate.py
    - tests/test_catalog_detect_vars.py
  modified: []

key-decisions:
  - "Refusal codes and texts (UI-SPEC copy without the display marker): catalog.no_libraries, catalog.kicad5_only, catalog.pcm_only, catalog.lfs, catalog.link; order no libraries, KiCad 5, PCM, LFS, link"
  - "The link refusal has no UI-SPEC copy, so its text is plain: 'This download contains a shortcut to another folder (<first path>), which the catalog does not accept. Nothing was added.'"
  - "KiCad 5 only is checked before PCM only: any .lib file with no .kicad_sym and no .pretty folder is KiCad 5 only; a PCM marker (metadata.json whose $schema names kicad at any depth, repository.json, packages.json, or .zip files with nothing else but documents) only decides when no library file of any kind exists"
  - "detect_vars: sample at most 200 distinct model paths per variable (even stride over the sorted list), a folder is taken when at least 80 percent of the sample exists under it with exact letter case, a tie goes to the shorter folder"
  - "KiCad's own variables are counted per model (not per distinct path); the warning says '1 3D model uses ...' in the singular and '{n} 3D models use ...' otherwise"
  - "Own-variable patterns are KICAD<digits>_, KISYS, *_3RD_PARTY, KIPRJMOD, the KiCad template and home names and KICAD_PATH; KICAD_4MS_LIBS and SPARKFUN_KICAD_LIBRARY are mappable"
  - "validate walks the download itself instead of calling find_symbol_libs and find_footprint_libs: the scanner's walker skips top-level folders named like its SKIP_DIRS and parses every symbol file, while the check only needs the nicknames; scan_source walks a clone without that skip, so counts agree"
  - "find_collisions compares stock names within their own kind (symbols with stock symbols, footprints with stock footprints) and own and other-catalog names by nickname alone; a library that clashes twice gets one row, stock first"

requirements-completed: [CAT-02, CAT-03, CAT-08, CAT-10]

coverage:
  - id: D1
    description: "validate_staging reads files only and stops at the first refusal in the order no libraries, KiCad 5 only, Plugin and Content Manager only, Git LFS, link, each as an Issue with the UI-SPEC refusal text"
    requirement: "CAT-03"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_refusal_order"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_no_libraries_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_kicad5_only_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_pcm_only_is_refused"
        status: pass
    human_judgment: false
  - id: D2
    description: "A download that keeps 3D models in Git LFS (a .gitattributes filter=lfs line anywhere, or a pointer file under 1 KB) or holds a symbolic link or junction is refused; .git is never read; nothing from the download is run or changed"
    requirement: "CAT-02"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_lfs_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_lfs_pointer_file_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_symlink_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_the_download_is_never_executed_or_changed"
        status: pass
    human_judgment: false
  - id: D3
    description: "A download with one symbol library and no footprint library is accepted; counts, the submodule warning and the root licence text (cut at 64 KB with a note) come back in the report"
    requirement: "CAT-03"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_one_symbol_library_is_enough"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_gitmodules_warns"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_licence_text_is_cut_at_64_kb"
        status: pass
    human_judgment: false
  - id: D4
    description: "Libraries whose nickname a KiCad stock library, another catalog library, an Atomic_ library or a Custom library already has are listed as (nickname, kind, clashes with); nothing is renamed"
    requirement: "CAT-08"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_collisions_listed_never_renamed"
        status: pass
    human_judgment: false
  - id: D5
    description: "detect_vars maps SparkFun, 4ms and Wurth shaped trees to '', '' and '3dmodels', applies the 80 percent rule on a sample of at most 200 paths, and never maps KiCad's or the Plugin and Content Manager variables, counting their models in a warning"
    requirement: "CAT-10"
    verification:
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_detect_vars_sparkfun_layout"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_detect_vars_wurth_layout"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_detect_vars_four_ms_layout"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_kicad_and_pcm_variables_are_never_mapped"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_below_eighty_percent_is_not_mapped"
        status: pass
    human_judgment: false
  - id: D6
    description: "unresolved_models gives the model paths that do not exist with exact letter case through library_scanner.unresolved_var_models; the private variable and folder rules match the manifest rules case by case"
    requirement: "CAT-10"
    verification:
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_unresolved_models_is_exact_case"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_private_variable_rule_matches_the_manifest_rule"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_detect_vars.py#test_private_folder_rule_matches_the_manifest_rule"
        status: pass
    human_judgment: false
  - id: D7
    description: "Detection against the real SparkFun, 4ms and Wurth clones"
    verification: []
    human_judgment: true
    rationale: "The tests use hand-built trees shaped like those libraries; a run against the real downloads belongs to the owner-run catalog verification (no network in tests)."

duration: 9min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 06: Staging check Summary

**`catalog/validate.py` decides from files alone whether a download may become a catalog library: ordered refusals with the UI-SPEC copy (no libraries, KiCad 5 only, PCM only, Git LFS, link), a submodule warning, the licence file, a name-clash list that never renames, and the path variables the models need, found by an 80 percent rule on a 200-path sample.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-11-27T09:26:00Z
- **Completed:** 2026-11-27T09:35:30Z
- **Tasks:** 2 (each a RED test commit then a GREEN feat commit)
- **Files modified:** 3 (all new)

## Accomplishments

- `StagingReport(symbol_libs, footprint_libs, collisions, vars, kicad_var_models, licence_text, warnings)` and `Collision(nickname, kind, clashes_with)`; `validate_staging(folder, *, stock_fp, stock_sym, own, other_catalog)` returns the report or the first refusal `Issue` (severity ERROR).
- Refusal codes and texts: `catalog.no_libraries` ("This repository holds no KiCad symbol or footprint libraries, so there is nothing to add."), `catalog.kicad5_only`, `catalog.pcm_only`, `catalog.lfs` ("This library keeps its 3D models in Git LFS, which the catalog does not support. Nothing was added."), `catalog.link`. Warnings: `catalog.submodules` ("submodules are not downloaded") and `catalog.kicad_vars` (the count of models using KiCad's own variables).
- `detect_vars(folder, footprint_files) -> (mapping, kicad_models)`: sample at most `SAMPLE_LIMIT` = 200 paths per variable, a folder needs `MIN_SHARE_PERCENT` = 80 percent of the sample, exact letter case, the index is keyed on the last two path components; `unresolved_models(folder, vars)` calls `library_scanner.unresolved_var_models`, the same check the scan rule uses.
- `find_collisions` is public for the Update preview; `licence_text(folder)` reads LICENSE*, LICENCE*, UNLICENSE*, COPYING* at the root, cut at 64 KB with a note.

## TDD Gate Compliance

Both tasks followed RED then GREEN; no refactor commits were needed.

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `c384854` test(17-06) | `25217fe` feat(17-06) |
| 2 | `f449d15` test(17-06) | `cac403b` feat(17-06) |

RED evidence (semantic assessment): the plan is not `type: tdd`, so the format-based `tdd-red-evidence` classifier was not run (pytest is not one of its report formats). Each RED run was read by hand. Task 1: the RED commit holds a docstring-only `validate.py`, so all 33 tests were collected and each failed with `AttributeError: module ... has no attribute 'validate_staging'` (or `licence_text`, `find_collisions`). Task 2: of 67 tests, 66 failed on the planned behaviour (`AttributeError` for `detect_vars`, `unresolved_models`, `_mappable`, `_is_kicad_own`, `_safe_folder`, `SAMPLE_LIMIT`, plus an `AssertionError` for the missing variable warning and the missing `vars` mapping in `validate_staging`); the one passing test pins that a download without variables has no variable warning.

## Task Commits

1. **Task 1: refusals, LFS and links, submodule warning, licence file, collisions** - `c384854` (test), `25217fe` (feat)
2. **Task 2: path variables and the shared exact-case model check** - `f449d15` (test), `cac403b` (feat)

## Files Created/Modified

- `kicad_lib_manager/catalog/validate.py` - the staging check (Qt-free, no subprocess, imports models, kicad_files and library_scanner only)
- `tests/test_catalog_validate.py` - 33 quick tests: refusal order and texts, LFS, links, submodules, licence, collisions, counts
- `tests/test_catalog_detect_vars.py` - 67 quick tests: variable detection on SparkFun, 4ms and Wurth shaped trees, the 80 percent and sampling rules, KiCad and PCM variables, the exact-case check, and the pins to the manifest rules

## Decisions Made

See `key-decisions` above. The one with later consequences: `validate_staging` walks the download itself (nicknames from file and folder names) rather than through `find_symbol_libs` and `find_footprint_libs`, so a symbol file is never parsed during the check and a top-level folder named like a scanner skip folder still counts, as it does for `scan_source`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Junctions are pruned by hand during the walk**
- **Found during:** Task 1
- **Issue:** `os.walk` does not report a Windows directory junction as a symbolic link, so a junction in a download would have been walked into (T-17-15).
- **Fix:** every directory and file entry goes through `os.path.islink` and `os.path.isjunction` before it is entered or counted; links are listed for the refusal and never followed. The same helper keeps `detect_vars` and `unresolved_models` out of links.
- **Files modified:** kicad_lib_manager/catalog/validate.py
- **Verification:** `test_symlink_is_refused` (a real symlink or, where the platform refuses one, a junction)
- **Committed in:** 25217fe

**2. [Rule 1 - Wording] Singular warning for one model**
- **Found during:** Task 2
- **Issue:** the plan's wording would read "1 3D models use ..." for a single model.
- **Fix:** one model reads "1 3D model uses KiCad's own path variables; it shows only in a matching KiCad version."; two or more use the plan's text.
- **Files modified:** kicad_lib_manager/catalog/validate.py, tests/test_catalog_detect_vars.py
- **Committed in:** cac403b

**3. [Plan note] Walk instead of find_symbol_libs / find_footprint_libs**
- The plan's key link names those two functions for the counts. The check walks the download itself (see Decisions Made); the key link `unresolved_var_models` is honoured.

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 wording), 1 noted implementation choice
**Impact on plan:** no scope change; all must-haves hold.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None: the module adds no network endpoint, auth path or write. T-17-15 (links), T-17-16 (LFS) and T-17-17 (read caps: 100 bytes for the LFS sniff, 64 KB for the licence file, `.gitattributes` and `metadata.json`, 200 sampled paths per variable) are mitigated and tested.

## Next Phase Readiness

- Plan 17-07 onward can call `validate_staging(...)` with `stock_sym` from `library_scanner.get_kicad_default_sym_nicknames`, `stock_fp` from `get_kicad_default_fp_nicknames`, and `own` / `other_catalog` built from the last scan and the manifest; `report.vars` feeds `CatalogEntry.vars`, `unresolved_models` is the D-26 check 3 shared with the conversion script.

## Self-Check: PASSED

- Files found: `kicad_lib_manager/catalog/validate.py`, `tests/test_catalog_validate.py`, `tests/test_catalog_detect_vars.py`.
- Commits found in history: `c384854`, `25217fe`, `f449d15`, `cac403b`.
- Plan verification: both automated commands pass (100 tests, 0 skipped); `test_catalog_layering.py` and `test_layering.py` pass (75 tests); acceptance greps print 1 for `def validate_staging`, `which the catalog does not support`, `def detect_vars`, `def unresolved_models`; the pre-publish scan of the new files and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
