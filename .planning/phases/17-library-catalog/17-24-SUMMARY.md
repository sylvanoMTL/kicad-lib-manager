---
phase: 17-library-catalog
plan: 24
subsystem: catalog
tags: [catalog, naming, pcm, nickname-prefix, scan, catalog-json, tdd]

requires:
  - phase: 17-library-catalog
    provides: names.display_name and source_names (17-21), scan_source(progress=) and catalog_source_names (17-23), the add-on list (17-22), the decisions D-33 and D-34 (17-17)
provides:
  - catalog.json records name, nickname_prefix and addon_id per library; manifest.PCM_PREFIX and nickname_prefixes
  - the name rule decided once in the check of the download (validate.decide_prefix, StagingReport.nickname_prefix)
  - prefixes= in scan_all, scan_source and rescan_library; library_scanner.footprint_refs_of
  - main_window.catalog_prefixes, passed by the three scan workers
  - StagingReport.addon_folder_models and the add-on folder 3D model warning
affects: [17-25, 17-26, 17-27]

plan_head_before: 7826ec4d1dba7353a874f4bc9bab9368cf3ee42d
plan_head_after: 50d5268b70b313566f871c8e3c819c7c6c8552d0

actuals:
  tokens: 20100
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "the name rule is a catalog.json field fixed at the check of the download and applied by every scan through a prefixes mapping (catalog id -> prefix); library_scanner imports no catalog module"
    - "validate keeps a module-private PCM_PREFIX copy (layering forbids importing manifest) and a test pins it equal to manifest.PCM_PREFIX"
    - "rescan_library re-derives a library's name from the rule only when prefixes is given; without it the name it had is kept"

key-files:
  created: []
  modified:
    - kicad_lib_manager/catalog/manifest.py
    - kicad_lib_manager/catalog/validate.py
    - kicad_lib_manager/catalog/ops.py
    - kicad_lib_manager/catalog/names.py
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager/main_window.py
    - tests/test_catalog_ops_git.py
    - tests/test_catalog_manifest.py
    - tests/test_catalog_names.py
    - tests/test_catalog_validate.py
    - tests/test_catalog_detect_vars.py
    - tests/test_scan_catalog.py
    - tests/test_main_window_catalog_jobs.py

key-decisions:
  - "Name rule as coded (validate.decide_prefix): over every symbol file of the download, every Footprint link (one per distinct library:footprint pair per file) whose library is one of the download's own footprint libraries counts as a plain link when it names the stem exactly, else as a PCM_ link when it is PCM_ + a stem; more PCM_ links give 'PCM_', more plain links give '', and equal counts (no link at all included) give default_prefix. Links to KiCad's or other libraries are not counted"
  - "validate_staging(prefix=...) is '' or 'PCM_' for a fixed rule and None to decide; the default is '' so existing callers keep their names; the report lists and finds clashes under the prefixed names"
  - "Which caller passes which rule: _curated_source and a bare AddSource give '' (fixed, curated libraries keep their names); _checked_source (an Add by web address) gives None with default_prefix ''; plan_reinstall gives the entry's recorded rule (fixed) with its recorded name and add-on id; the caller for KiCad's add-on list (default_prefix 'PCM_' and addon_id) is not built yet, AddSource carries both fields for it"
  - "catalog.json keys: name, nickname_prefix, addon_id written after branch in a fixed order and always written; FORMAT stays 1; read back with refusals 'The name of {name} is not text this app can show.' (printable, up to 100 characters), '{name} has a library-name rule this app does not know.' (only '' or 'PCM_') and 'The KiCad add-on id of {name} is not in a form this app understands.' (id pattern, up to 128 characters)"
  - "display_name returns the recorded name first, then the curated name, owner/repo and the id"
  - "Update lists added and removed libraries, and Remove from the files on disk lists its libraries, with the entry's prefix in front, as the scan and the tables name them"
  - "Models on a *_3RD_PARTY variable are counted apart from KiCad's other own variables (detect_vars now returns the third count) and reported with ADDON_FOLDER_MODELS_TEXT; neither kind is ever mapped"
  - "The catalog never sets, reads or lists KiCad's add-on folder or installed_packages.json; table_generator is unchanged because its external-entry rule already keeps a row KiCad's manager wrote byte for byte (pinned by test_kicad_manager_row_is_kept)"

patterns-established:
  - "A scan keyword that a worker passes forces the fake scan functions of the main-window tests to accept it: every fake_scan signature now ends in model_vars=None, prefixes=None"

requirements-completed: [CAT-05, CAT-08, CAT-10, CAT-06]

coverage:
  - id: D1
    description: "A library whose own symbols link PCM_ names reaches the staging report, catalog.json, the scan and the written fp-lib-table under PCM_ names, and a plain-linked library keeps its names"
    requirement: "CAT-05"
    verification:
      - kind: integration
        ref: "tests/test_catalog_ops_git.py#test_addon_names_reach_the_tables"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_ops_git.py#test_plain_links_keep_the_plain_names"
        status: pass
    human_judgment: false
  - id: D2
    description: "The name rule is decided from the counts of PCM_ and plain links with the default for a tie, fixed by a curated source or a Reinstall, and clashes are found on the prefixed names"
    requirement: "CAT-08"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_name_rule_cases"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_a_fixed_rule_ignores_the_links"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_collisions_are_found_on_the_prefixed_names"
        status: pass
    human_judgment: false
  - id: D3
    description: "catalog.json records the name, name rule and add-on id with plain refusals on read; Reinstall keeps them; Update and Remove name libraries with the prefix; display_name uses the recorded name first"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_catalog_manifest.py#test_a_bad_name_rule_name_or_addon_id_makes_the_record_unreadable"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_names.py#test_reinstall_keeps_the_name_rule"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_names.py#test_update_names_added_and_removed_libraries_with_the_prefix"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_names.py#test_the_recorded_name_comes_first"
        status: pass
    human_judgment: false
  - id: D4
    description: "scan_all, scan_source and rescan_library apply the prefix to ThirdParty/<id>/ only, and the three scan workers pass the rule read from catalog.json (no prefix and no exception when it is unreadable)"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_prefixes_apply_to_their_source_only"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_workers_pass_the_name_rule"
        status: pass
      - kind: unit
        ref: "tests/test_main_window_catalog_jobs.py#test_an_unreadable_record_means_no_prefix_in_any_worker"
        status: pass
    human_judgment: false
  - id: D5
    description: "3D models that point into KiCad's add-on folder are counted and reported in plain words, never mapped, and nothing of KiCad's add-on manager is set, read or overwritten (its own table row is kept byte for byte)"
    requirement: "CAT-10"
    verification:
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_addon_folder_models_are_reported"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_validate.py#test_no_catalog_code_reads_or_writes_kicads_add_on_manager_state"
        status: pass
      - kind: unit
        ref: "tests/test_scan_catalog.py#test_kicad_manager_row_is_kept"
        status: pass
    human_judgment: false
  - id: D6
    description: "How the PCM_ names read in the real Add preview and the trees when a library from KiCad's add-on list (Espressif) is added, and that its 51 'Missing FP' links resolve on the owner's machine"
    verification: []
    human_judgment: true
    rationale: "The add-on list caller and its preview wording come with plan 17-25 and the owner rehearsal of 17-19; here only the files-and-links behaviour is asserted on scratch repositories"

duration: 17min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 24: Add-on Names Summary

**Catalog libraries are named `PCM_<name>` or by their own plain names according to the links in their own symbol files, the rule is recorded in catalog.json and applied by every scan, and nothing KiCad's add-on manager owns is touched**

## Performance

- **Duration:** 17 min
- **Started:** 2026-11-27T17:06:11Z
- **Completed:** 2026-11-27T17:23:00Z
- **Tasks:** 3 (one tracer, two auto; all `tdd="true"`)
- **Files modified:** 21 (6 source files, 15 test files)

## Accomplishments

- The tracer: a library added by web address whose symbols link `PCM_Demo:R_0603` is listed as `PCM_Demo` (symbol and footprint) by the Add check, recorded with `nickname_prefix: "PCM_"`, scanned as `PCM_Demo` with its link resolved (no `scan.footprint_lib_missing`) and written to `fp-lib-table` as `(name "PCM_Demo")` with URI `${KICAD_LIB_GITHUB}/ThirdParty/Demo/footprints/Demo.pretty`; the plain-linked control keeps `Demo` everywhere.
- The record: `CatalogEntry.name`, `nickname_prefix` and `addon_id` are written after `branch` in a fixed order, read back with plain refusals, kept by Reinstall (fixed rule, links not asked again), used by Update, Remove and `display_name` (recorded name first, so the window, trees and log keep one name offline).
- The scan: `prefixes=` in `scan_all`, `scan_source` and `rescan_library` (applied under `ThirdParty/<id>/` only), `footprint_refs_of`, and `main_window.catalog_prefixes(root)` passed by `ScanWorker`, `LibraryRescanWorker` and `CatalogRescanWorker`.
- 3D models on a `*_3RD_PARTY` variable are counted apart and reported as "N 3D models point into the add-on folder of KiCad's Plugin and Content Manager; they show only when that manager has installed this library too."

## The name rule as coded

`validate.decide_prefix(sym_files, footprint_stems, default_prefix)` reads the Footprint fields of every symbol file of the download (`library_scanner.footprint_refs_of`, one `library:footprint` pair counted once per file). A link whose library is one of the download's own footprint libraries by its exact stem is a plain link; otherwise a link whose library is `PCM_` + one of those stems is a PCM_ link; links to KiCad's or other libraries are not counted. More PCM_ links give `PCM_`, more plain links give `''`, and a tie (including no link at all, footprints only, or no symbol file) gives `default_prefix` (`''` for a web address, `'PCM_'` when the caller says the library comes from KiCad's add-on list). A fixed rule (`prefix` of `''` or `'PCM_'`) skips the links.

| Caller | Rule |
|--------|------|
| `_curated_source`, a bare `AddSource` | `''` fixed (Wurth, SparkFun keep their names whatever their links say) |
| `_checked_source` (Add by web address) | `None` (decided from the links), `default_prefix=''` |
| `plan_reinstall` | the entry's recorded `nickname_prefix` (fixed), recorded name and add-on id |
| KiCad's add-on list | not built yet; `AddSource.default_prefix` and `addon_id` are the fields it will fill |

## KiCad research facts (recorded in the plan, not re-checked here; no network)

- KiCad's Plugin and Content Manager unpacks a package into `${KICAD<n>_3RD_PARTY}/<symbols|footprints|3dmodels>/<identifier with dots as underscores>/` and at every load of the global tables adds a row per library: nickname = the `pcm.lib_prefix` setting (default `PCM_`) + the file or folder stem, description "Added by Plugin and Content Manager" (KiCad source, 9.0 branch: `eeschema/symbol_lib_table.cpp`, `kicad/pcm/pcm_task_manager.cpp`).
- Package authors write the literal `PCM_` into their files: 4ms's `PCM/make_archive.sh` rewrites `4ms_X:` to `PCM_4ms_X:` and the 3D model variable to `${KICAD<n>_3RD_PARTY}/3dmodels/<pkg>/` when it builds the zip, so 4ms's git repository keeps plain names (its README says the git and add-on copies use different names). Espressif's git repository already links `PCM_Espressif:`.
- Decision D-34: the catalog uses the literal `PCM_` (never KiCad's setting), decides per library from its own links, sets no `KICAD<n>_3RD_PARTY` (the manifest rules refuse `*_3RD_PARTY`), and lets the table merge keep any row KiCad's manager wrote.

## Task Commits

1. **Task 1: Tracer - a library that links PCM_ names reaches the tables under PCM_ names**
   - RED `b06ec8d` (test), GREEN `7ccccb9` (feat)
2. **Task 2: The record's name, add-on id and name rule through Reinstall, Update and Remove**
   - RED `bcff3c7` (test), GREEN `47d923b` (feat)
3. **Task 3: Every case of the name rule, KiCad's add-on folder left alone, and the scan workers**
   - RED `6474335` (test), GREEN `961b8a0` (feat), pin test `50d5268` (test)

**Plan metadata:** the docs commit that holds this file, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `kicad_lib_manager/catalog/manifest.py` - `PCM_PREFIX`, the three entry fields, their checks on read, `nickname_prefixes`
- `kicad_lib_manager/catalog/validate.py` - `decide_prefix`, `prefix`/`default_prefix` keywords, `StagingReport.nickname_prefix` and `addon_folder_models`, `ADDON_FOLDER_MODELS_TEXT`, `detect_vars` third count
- `kicad_lib_manager/catalog/ops.py` - `AddSource.nickname_prefix/default_prefix/addon_id`, the rule through stage, register, Reinstall, Update and Remove
- `kicad_lib_manager/catalog/names.py` - the recorded name first
- `kicad_lib_manager/library_scanner.py` - `prefixes=` in the three scans, `footprint_refs_of`
- `kicad_lib_manager/main_window.py` - `catalog_prefixes` and the three workers
- tests: new cases in the catalog, scanner and main-window modules; the fake scan functions of eight main-window test modules accept `prefixes`

## Decisions Made

See `key-decisions` above. The rule's counts and tie rule, the record keys and the callers are listed there and in the table.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The fake scan functions of the main-window tests rejected the new keyword**
- **Found during:** Task 3 (workers pass `prefixes=`)
- **Issue:** eight main-window test modules (and the catalog harness) replace `scan_all` / `rescan_library` with fakes ending in `model_vars=None`; once `ScanWorker` passes `prefixes=` every window start would raise a TypeError in the fake
- **Fix:** the fakes now end in `model_vars=None, prefixes=None` (a byte-safe edit that keeps the CRLF files CRLF); the catalog jobs harness also records the rule each full scan was asked for
- **Files modified:** tests/test_checkout_warning.py, test_main_window.py, test_main_window_catalog.py, test_main_window_catalog_jobs.py, test_main_window_chooser.py, test_main_window_import.py, test_main_window_migration.py, test_main_window_root.py, test_startup.py
- **Verification:** the module list below passes
- **Committed in:** `961b8a0`

**2. [Rule 1 - Bug] Existing detect_vars and warning tests pinned the old "all KiCad variables together" count**
- **Found during:** Task 3 (the plan separates the add-on folder count)
- **Issue:** `detect_vars` returned (map, count of every KiCad-owned variable) and one warning wording covered `KICAD<n>_3RD_PARTY`; the plan reports the add-on folder models apart
- **Fix:** `detect_vars` returns a third count and the staging warning splits; the pins in tests/test_catalog_detect_vars.py were updated in the RED commit (12 two-tuple assertions became three-tuples, two warning assertions follow the new wording)
- **Files modified:** kicad_lib_manager/catalog/validate.py, tests/test_catalog_detect_vars.py
- **Committed in:** `6474335` (tests), `961b8a0` (code)

**3. [Rule 2 - Missing critical] The prohibition "never read or write KiCad's add-on manager state" had no automated check**
- **Found during:** Task 3 (T-17-61)
- **Fix:** `test_no_catalog_code_reads_or_writes_kicads_add_on_manager_state` scans the catalog package for `installed_packages`, `3rdparty`, `lib_prefix`, `pcm.json` and for `_3RD_PARTY` outside the manifest, validate and curated modules
- **Files modified:** tests/test_catalog_validate.py
- **Committed in:** `50d5268`

**4. [Plan wording] validate keeps its own PCM_PREFIX**
- `catalog.validate` may not import `catalog.manifest` (test_catalog_layering), so it holds a module-private `PCM_PREFIX` and `test_the_name_rule_constant_is_the_one_of_the_manifest` pins it to `manifest.PCM_PREFIX`, the way the variable rules are already copied.

**5. [Run instruction] The quick parallel run was not started**
- The plan's last acceptance line names the whole quick run; the run facts for this execution say to run only the named modules with `-n 0` and leave the whole suite to the post-wave gate. The modules run: the plan's three verify commands, `tests/test_corpus_audit.py`, `test_custom_literals.py`, `test_layering.py`, `test_catalog_layering.py`, `test_annotations_resolve.py`, `test_exit_with_hung_check.py`, `test_main_window_catalog_jobs.py`, `test_table_add_entries.py`, `test_table_descriptions.py`, `test_table_merge.py`, `test_write_tables.py`, `test_rescan_library.py`, `test_scan_cache.py`, `test_catalog_status.py`, `test_catalog_ops_update.py`, `test_catalog_manifest.py`, `test_catalog_names.py` (570 passed, 5 deselected) and `tests/test_catalog_ops_git.py --full` (11 passed).

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3), 2 notes
**Impact on plan:** all necessary for the plan's own changes to load and for its prohibition to be checked; no scope creep.

## TDD Gate Compliance

The plan is `type: execute` with `tdd="true"` tasks, so the `tdd-red-evidence` classifier was not run (the same format-based reading as plans 17-21 and 17-22). Each task has a RED `test(17-24)` commit before its GREEN `feat(17-24)` commit. Task 1's RED fails with a TypeError on the not-yet-existing `AddSource(nickname_prefix=...)` keyword (a missing API, the planned reason); Task 2's RED fails on 11 assertions (validation texts, recorded name, prefixed lists); Task 3's RED fails on 23 tests (the add-on folder wording, the three-tuple of `detect_vars`, the workers' `prefixes`). The name-rule case table and the scan and table pins of Task 3 already passed at RED because the tracer implemented the whole rule; they are kept as the plan's behaviour pins. Refactor: none.

## Issues Encountered

None beyond the deviations.

## Known Stubs

None. The caller that adds a library from KiCad's add-on list (`default_prefix='PCM_'`, `addon_id`) is a later plan's work, not a stub of this one.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 17-25: `AddSource.default_prefix` and `addon_id` are in place for the add-on list caller; a library from that list is named by its links with `PCM_` as the tie default.
- The name rule is fixed at the check of the download and shown before Add Library (D-20); nothing renames a library afterwards.

## Self-Check: PASSED

All 12 source and test files named in the plan exist, all 7 task commits are ancestors of HEAD, the RED/GREEN sequence is present for each task, and the pre-publish scan of the changed files and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
