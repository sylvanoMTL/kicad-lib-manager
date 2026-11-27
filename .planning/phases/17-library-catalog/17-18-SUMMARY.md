---
phase: 17-library-catalog
plan: 18
subsystem: catalog
tags: [catalog, curated-list, d-22, d-33, cat-09, tdd]

requires:
  - phase: 17-library-catalog
    provides: the owner-run D-22 results (plan 17-17), KiCad's add-on list reader and its fixture (plan 17-22), the merged rows (plan 17-25)
provides:
  - CURATED is exactly Wurth and SparkFun with their confirmed values and licence addresses
  - CANDIDATES is an empty tuple (the Candidate type stays)
  - REJECTED holds Espressif with its plain reason
  - a module docstring that records the 17-17 results of all four libraries
affects: [17-19, 17-20]

plan_head_before: 635b0b8a0ccd8bbbebd8b0ba71179e4961204fbd
plan_head_after: 817c28208321b4ff047e8dc17fceb1ba249726a9

actuals:
  tokens: 6200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "a test that used to be parametrized over a list that can become empty loops over it instead (an empty parametrization is a skip)"
    - "tests derive the expected rows from the curated tuple they built the window with, never from a literal count"

key-files:
  created: []
  modified:
    - kicad_lib_manager/catalog/curated.py
    - tests/test_catalog_curated.py
    - tests/test_catalog_status.py

key-decisions:
  - "4ms and Alternate-KiCad-Library are in neither CURATED, CANDIDATES nor REJECTED: KiCad's add-on list brings them and its review is their D-22 check (D-33)"
  - "Espressif is REJECTED with the reason that its 3D models point into the add-on folder of KiCad's Plugin and Content Manager (KICAD8_3RD_PARTY and KICAD9_3RD_PARTY) and that it is not in KiCad's add-on list; it stays installable by its web address"
  - "Only one test names the whole curated id set (test_the_curated_list_is_wurth_and_sparkfun); every other test derives from CURATED, CANDIDATES and REJECTED"

requirements-completed: []

coverage:
  - id: D1
    description: "CURATED holds exactly WurthElektronik and SparkFun with their values unchanged (SparkFun 30 / 21 libraries, SPARKFUN_KICAD_LIBRARY, licence addresses kept)"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_catalog_curated.py#test_the_curated_list_is_wurth_and_sparkfun"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_curated.py#test_sparkfun_facts"
        status: pass
    human_judgment: false
  - id: D2
    description: "Espressif is REJECTED with the add-on folder reason, no rejected address is curated, and no fixture listing of KiCad's add-on list has Espressif's repository"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_catalog_curated.py#test_espressif_is_rejected_with_the_add_on_folder_reason"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_curated.py#test_espressif_is_not_in_kicads_list"
        status: pass
    human_judgment: false
  - id: D3
    description: "4ms and Alternate-KiCad-Library are addable listings of KiCad's add-on list (fixture), are not curated, and SparkFun is both curated and listed"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_catalog_curated.py#test_kicads_list_brings_4ms_and_alternate"
        status: pass
    human_judgment: false
  - id: D4
    description: "No test is skipped because CANDIDATES became empty (skip budget 0 on the two edited modules)"
    verification:
      - kind: command
        ref: "env/Scripts/python.exe scripts/check_skip_budget.py <junit of test_catalog_curated + test_catalog_status> --max-skips 0 --min-passed 20"
        status: pass
    human_judgment: false
  - id: D5
    description: "CAT-09's Wurth part is verified only by the owner's rehearsal and live run (plans 17-19, 17-20)"
    requirement: CAT-09
    verification: []
    human_judgment: true
    rationale: "Wurth is a 12 GB real-network clone; only the owner-run rehearsal and live Add can verify it, so CAT-09 stays pending"

duration: 25min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 18: Curated list after the D-22 results and D-33 Summary

**CURATED is Wurth and SparkFun, CANDIDATES is empty, and Espressif is REJECTED with its Plugin and Content Manager reason; 4ms and Alternate-KiCad-Library now come from KiCad's add-on list**

## Performance

- **Duration:** about 25 min
- **Completed:** 2026-11-27T18:24:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Final CURATED ids: `WurthElektronik` and `SparkFun`, values unchanged (17-17 measured nothing new for SparkFun: 30 symbol and 21 footprint libraries, `SPARKFUN_KICAD_LIBRARY`). The `licence_url` values added in `81177e5` are kept.
- REJECTED reason (Espressif, `https://github.com/espressif/kicad-libraries.git`): its 3D models point into the add-on folder of KiCad's Plugin and Content Manager (`KICAD8_3RD_PARTY` and `KICAD9_3RD_PARTY`), which the catalog never sets, so its models show only when KiCad's manager has installed it too, and it is not in KiCad's add-on list. You can still add it by its web address.
- Where 4ms and Alternate-KiCad-Library come from now: KiCad's add-on list (read by `catalog/addons.py`, merged into the window by plan 17-25). The module docstring records their 17-17 results (4ms 25 / 29 libraries, 325 MB on disk; Alternate 39 / 63 libraries, about 6,900 footprints with 3D models on a fixed KiCad 5.99 folder, CC-BY-SA from KiCad's list).
- The tests that were parametrized over CANDIDATES now loop (an empty parametrization is a skip) or read CURATED and REJECTED; the quick run of both edited modules has 0 skips.

## Task Commits

1. **Task 1: Curated list follows the D-22 results and D-33** - `f16866d` (test, RED), `0a84663` (feat, GREEN)
2. **Task 2: Catalog tests read the curated list instead of pinning its size** - `817c282` (test)

**Plan metadata:** the docs commit that holds this file.

## RED / GREEN

- **RED:** `f16866d` added the new curated tests. Four target tests failed on their planned assertions (`test_the_curated_list_is_wurth_and_sparkfun`, `test_the_three_conditional_libraries_left_the_candidates_by_their_own_outcome`, `test_espressif_is_rejected_with_the_add_on_folder_reason`, `test_the_module_documents_the_d22_rule_and_the_17_17_results`): the old list still held three candidates, REJECTED was empty and the docstring had no D-33 text. The plan is `type: execute` with task-level `tdd="true"`, so the machine RED classifier was not run; the semantic assessment is that each failure was an assertion on the planned behaviour, with no import, collection or fixture error (25 other tests passed).
- **GREEN:** `0a84663` rewrote `curated.py`; all 26 tests of the module pass. One first attempt wrote "Plans 17-17 and 18" in the docstring and the docstring test caught it; fixed before the commit.
- **REFACTOR:** none.

## Files Created/Modified

- `kicad_lib_manager/catalog/curated.py` - CANDIDATES empty, REJECTED holds Espressif, new docstring with the D-22 / D-33 outcome
- `tests/test_catalog_curated.py` - curated-list assertions, the fixture test for 4ms and Alternate (plus the plan-checker advisory: no fixture listing has Espressif's repository), empty-list-safe candidate tests
- `tests/test_catalog_status.py` - one assertion changed

## Task 2: assertions changed

- `tests/test_catalog_status.py::test_listing_rows`: the literal `2 +` in the row count became `len(shown_curated) +`, where `shown_curated` is the curated tuple the test builds the rows with.
- No change in `tests/test_catalog_dialog.py`, `tests/test_catalog_dialog_add.py` or `tests/test_catalog_dialog_update.py`: they build the window with explicit curated tuples, so no assertion pinned the number or the ids of the real CURATED rows.

## Decisions Made

- 4ms and Alternate are in none of the three lists; KiCad's review is their D-22 check (D-33).
- Only one test names the whole curated id set; the rest derive from the tuples.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Windows text-mode writes turn `\n` into CRLF: my first edit of `tests/test_catalog_status.py` rewrote the whole file with CRLF. Caught on the first `git diff --stat` (865 lines), reverted that file and redid the edit byte-exact; the committed diff is 3 insertions and 2 deletions.

## Verification

- `tests/test_catalog_curated.py`, `tests/test_catalog_status.py`, `tests/test_catalog_dialog.py`, `tests/test_catalog_dialog_add.py`, `tests/test_catalog_dialog_update.py`: 203 passed, 0 skipped (`-n 0`).
- Before the final commit, with `--full -n 0`: `test_catalog_curated`, `test_catalog_addons`, `test_catalog_status`, `test_catalog_dialog` (+ `_add`, `_update`), `test_catalog_pages`, `test_wurth_to_catalog`, `test_corpus_audit`, `test_custom_literals`, `test_layering`, `test_catalog_layering`, `test_help_dialog`, `test_docs_split`: 670 passed; `test_catalog_dialog_geometry`: 12 passed.
- `scripts/check_skip_budget.py` on the junit of the two edited modules with `--max-skips 0`: 64 passed, 0 skipped.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CAT-09 stays pending: Wurth is verified only by the owner's rehearsal and live Add (plans 17-19, 17-20). This plan did not mark it complete.
- Plans 17-19 and 17-20 can start from the final list: Wurth and SparkFun curated, 4ms and Alternate from KiCad's list.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
