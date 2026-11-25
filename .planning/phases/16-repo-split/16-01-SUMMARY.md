---
phase: 16-repo-split
plan: 01
subsystem: testing
tags: [pytest, fixtures, zipfile, ultra-librarian, synthetic-sample, xdist]

requires:
  - phase: 16-repo-split
    provides: 16-RESEARCH.md UL Builder Specification and the Bucket A module list
provides:
  - tests/ulfixtures.py, a stdlib-only synthetic Ultra Librarian builder and the content-addressed ul_sample_zip()
  - zipfixtures.UL_ZIP, the ul_package fixture and tests/test_adapters.py reading the generated sample
  - proof that all 31 Bucket A modules (plus test_snapeda_adapter and test_suggest_atomic) pass on the generated sample with the real TI zip moved away
affects: [16-17, 16-18, 16-09, 16-11, 16-15]

actuals:
  tokens: 4700
  tasks: 2
  commits: 2

plan_head_before: ed3a784ac0375414f438f462d178cf46254173e1
plan_head_after: 635c192ac1cd3a24adf9143aa62acdb1bf317db3

tech-stack:
  added: []
  patterns:
    - "Generated test sample built once per content hash under tempfile.gettempdir()/kicad_lib_manager_tests/<sha12>/, written to a temp name and os.replace'd, with a PermissionError retry that accepts a target whose SHA-256 matches"
    - "Fixed ZipInfo (date_time, ZIP_DEFLATED, create_system 0) so two builds are byte-identical"

key-files:
  created:
    - tests/ulfixtures.py
    - tests/test_ulfixtures.py
  modified:
    - tests/zipfixtures.py
    - tests/conftest.py
    - tests/test_adapters.py

key-decisions:
  - "The builder lives in its own stdlib-only module (tests/ulfixtures.py), not in vendorfixtures.py, so zipfixtures can import it without a cycle"
  - "Every member body is written from scratch (a plain rectangle per unit, clean pad numbers, a few STEP entities); only layout, names, property names and quirks are reproduced (D-15, D-10)"
  - "ZipInfo.create_system is pinned to 0 so the platform does not leak into the bytes"

patterns-established:
  - "Content-addressed generated fixture: path = <temp>/kicad_lib_manager_tests/<sha12>/<name>, so a changed builder gets a new folder and parallel workers share one file"

requirements-completed: [SPLIT-04]

coverage:
  - id: D1
    description: "Synthetic Ultra Librarian zip with the six members of the real sample in the same order, CRLF ASCII, no BOM, claimed by the UL adapter with confidence 1.0"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_ulfixtures.py (10 tests, with the real zip moved out of the checkout)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two builds are byte-identical and the build is parallel-safe under the system temp folder"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_ulfixtures.py#test_two_builds_are_identical, #test_sample_zip_is_content_addressed, #test_sample_zip_build_survives_a_held_open_target"
        status: pass
    human_judgment: false
  - id: D3
    description: "zipfixtures.UL_ZIP, the ul_package fixture and test_adapters.py no longer build a path to downloaded_examples/ul_CSD85301Q2.zip"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "run (a): 795 passed, 16 skipped with the real zip moved out"
        status: pass
    human_judgment: false
  - id: D4
    description: "The builder carries every fact the other 14 Bucket A modules read through their own path, so plans 16-17 and 16-18 are constant swaps"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "run (b): 632 passed, 7 skipped with the generated zip copied to the real file's path"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 01: Synthetic Ultra Librarian sample Summary

**A stdlib-only builder writes a deterministic six-member Ultra Librarian zip from scratch into a content-addressed temp folder; the fixtures and the 31 Bucket A modules pass on it with the licence-restricted TI download moved out of the checkout.**

## Performance

- **Duration:** about 25 min
- **Completed:** 2026-11-24
- **Tasks:** 2 (Task 1 tracer, TDD: RED then GREEN; Task 2 proof runs, no file change)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `tests/ulfixtures.py` builds `ul_CSD85301Q2.zip` with the six members in the real order (`DLV0006A.stp`, `ImportGuides.html`, `readme.txt`, `KiCADv6/2026-10-18_09-12-49.kicad_sym`, `KiCADv6/ImportGuide.html`, `KiCADv6/footprints.pretty/DQK0006B.kicad_mod`), all ASCII with CRLF and no BOM. Sizes: 592, 121, 148, 2813, 217, 2306 bytes; zip 2433 bytes.
- Generated zip SHA-256: `b46a665ece90e290732b2e2b817149820b27c17b645f4601905aa9069971c0fe` (cache folder `b46a665ece90`).
- The UL adapter claims the sample with confidence 1.0 (symbol `CSD85301Q2` with sub-units `_1_1` and `_2_1`, eight pins `S1 G1 D1 D1 D2 S2 G2 D2` numbered 1,2,6,7 / 3,4,5,8; footprint `DQK0006B` with eight SMD pads, pitch 0.65, body 2.1 x 2.1, no `(model ...)`; model `DLV0006A.stp` starting `ISO-10303-21;`).
- `zipfixtures.UL_ZIP = ul_sample_zip()`, the `ul_package` fixture (`open_package(UL_ZIP, REPO_ROOT)`) and `tests/test_adapters.py` read the generated sample; the three files hold no `downloaded_examples/ul_CSD85301Q2.zip` path any more.
- Task 2 proof, real zip moved out each time and put back unchanged (`git status --porcelain downloaded_examples` empty after every run).

## Measured runs (real TI zip moved out of the checkout)

| Run | Modules | Result |
|-----|---------|--------|
| Task 1 verify | test_ulfixtures, test_adapters, test_zipfixtures (`-n 0`) | 74 passed, 0 skipped |
| (a) generated zip as it is | the 18 `UL_ZIP` / `unpack_sample` / `ul_package` modules plus test_ulfixtures and test_adapters | 795 passed, 16 skipped |
| (b) generated zip copied to `downloaded_examples/ul_CSD85301Q2.zip` | the 12 own-path modules plus test_snapeda_adapter and test_suggest_atomic, `test_ul_zip_is_pinned_and_tracked` deselected | 632 passed, 7 skipped |
| extra: slow tests of the Bucket A modules, stand-in in place, `--full -m "slow and not wurth"` | test_install_plan, test_vendor_install, test_customfixtures, test_import_dialog, test_install_e2e, test_generated_text, test_official_footprint | 21 passed, 1 skipped |

Skips are all corpus-type or environment skips, none caused by the builder: the other vendor zips in `downloaded_examples/` (SnapEDA, SamacSys, ATXK, SnapEDA 3D) that are not in this worktree, `test_real_vendor_samples.py:188` (needs the real `ul_CSD85301Q2.zip`, a corpus test), the `Custom/` submodule not checked out (test_sexpr:680, test_roundtrip_corpus:106, test_edits:106 and :179, test_kicad_files:365 and :380), symlink privilege (test_package_folder:105), `test_roundtrip_corpus.py:205` (needs `KICAD_TEST_REAL_CONFIG=1`) and the manual UAT scratch install (test_install_e2e:617). The 24 slow tests of those modules were collected; 23 are non-wurth and ran in the extra run.

## Builder changes made during Task 2

None. Both proof runs passed on the first run against the Task 1 builder, so no builder fact had to be added after Task 1 and no test in test_ulfixtures.py was added for Task 2 beyond Task 1's set.

## Structural facts reproduced beyond the research table

Each was written into the builder from the start (read from the real sample's structure, not its bytes); none was needed to fix a failing test:

- Symbol top line quirks `(pin_names (offset 0.254)) (in_bom yes) (on_board yes)`; pin numbers split over the units as 1,2,6,7 and 3,4,5,8 (`test_symbol_shape`).
- Footprint text layers: `fp_text reference "REF**"` on unquoted `F.SilkS`, `fp_text value DQK0006B` on `F.Fab`, `fp_text user "${REFERENCE}"` on `F.Fab`, `fp_text user "u"` on quoted `"F.SilkS"`, `(at 0 0 unlocked)` placement form (`test_footprint_shape`).
- `ZipInfo.create_system = 0` pinned, so the platform does not change the bytes (`test_two_builds_are_identical`).
- `KiCADv6/ImportGuide.html` carries `<!DOCTYPE html>` and a meta refresh element (to a placeholder `example.invalid` URL); `ImportGuides.html` has neither (adapter score and `UL_IGNORED`, `test_adapter_claims_the_sample`).

## Task Commits

1. **Task 1 (tracer, TDD): synthetic UL zip end to end**
   - RED: `3a4f969` (test) - `tests/test_ulfixtures.py` with a skeleton `tests/ulfixtures.py` (empty bodies)
   - GREEN: `635c192` (feat) - builder, `zipfixtures.UL_ZIP`, `ul_package`, `test_adapters.py`
2. **Task 2: proof runs (a) and (b)** - no file change, no commit (results above)

**Plan metadata:** the commit that adds this SUMMARY (docs).

## Files Created/Modified

- `tests/ulfixtures.py` - stdlib-only builder: `UL_ZIP_NAME`, member constants, `UL_MEMBER_NAMES`, `UL_DATE_TIME`, `ul_symbol/ul_footprint/ul_model/ul_members/ul_zip_bytes/ul_zip/ul_sample_zip`
- `tests/test_ulfixtures.py` - 10 self-tests (the nine planned plus `test_zipfixtures_points_at_the_sample`)
- `tests/zipfixtures.py` - UL constants now imported from `ulfixtures`; `UL_ZIP = ul_sample_zip()`; docstrings reworded
- `tests/conftest.py` - `ul_package` opens `UL_ZIP`
- `tests/test_adapters.py` - local `UL_ZIP` constant replaced by `from zipfixtures import UL_ZIP`

## Decisions Made

- The builder is its own module to avoid the zipfixtures/vendorfixtures import cycle.
- Wave 2 (plans 16-17 and 16-18) can swap the 14 own-path constants for `from zipfixtures import UL_ZIP` with no builder change: run (b) proved it on the generated zip copied into the real file's place.

## Deviations from Plan

### TDD RED evidence

**1. [Rule 3 - tooling] RED evidence not run through `gsd_run check tdd-red-evidence`**
- **Found during:** Task 1 (RED step)
- **Issue:** the worktree has no `.claude/gsd-core`, so `gsd_run` is unavailable (the orchestrator brief says to skip those steps).
- **Fix:** RED was inspected by hand. A skeleton `tests/ulfixtures.py` with empty bodies went into the RED commit so the tests fail on assertions, not on an import error: 9 of 10 failed (member order, CRLF, determinism, content address, held-open target, `UL_ZIP` wiring, symbol shape, footprint shape, STEP magic) for the planned reasons; `test_adapter_claims_the_sample` passed in RED because `zipfixtures.UL_ZIP` still named the real zip at that point (it checks the wiring that GREEN changes, and the real-zip-free run in Task 1's verify is its proof). Some of the failures raised `FileNotFoundError` from the skeleton's non-existent path, still the planned "no sample exists yet" cause.
- **Files modified:** tests/ulfixtures.py, tests/test_ulfixtures.py
- **Commit:** 3a4f969

**Total deviations:** 1 (tooling only). **Impact:** none on the delivered behaviour.

## Authentication Gates

None.

## Known Stubs

None. The RED-only skeleton in `3a4f969` was replaced in `635c192`.

## Threat Flags

None. The new code reads and writes only under `tempfile.gettempdir()/kicad_lib_manager_tests`; no network, auth or trust-boundary surface was added. T-16-01 (originality): every member body is written from scratch; the real zip was read only to learn structure, with `python -I`, from a script outside the repo, printing to the terminal (nothing extracted into the repo). T-16-02 (parallel build): content-addressed target, temp name plus `os.replace`, `PermissionError` retry with a hash re-check, covered by `test_sample_zip_build_survives_a_held_open_target` (runs on win32).

## Issues Encountered

None. Submodules `Custom/` and `WurthElektronik/KiCad-Library` are not checked out in this worktree, which accounts for the `Custom submodule not checked out` skips listed above; none of them is a regression of this change.

## Next Phase Readiness

Plans 16-17 and 16-18 can repoint the 14 own-path modules at `zipfixtures.UL_ZIP` as a plain constant swap. Plan 16-17 deletes `test_ul_zip_is_pinned_and_tracked` (it pins the real file's hash). Plan 16-09 adds the corpus originality test for this builder.

## Self-Check: PASSED

- FOUND: tests/ulfixtures.py, tests/test_ulfixtures.py (created); tests/zipfixtures.py, tests/conftest.py, tests/test_adapters.py (modified)
- FOUND commits: 3a4f969 (RED), 635c192 (GREEN)
- `git status --porcelain downloaded_examples` empty after every proof run; acceptance greps: `def ul_sample_zip` 1, `from ulfixtures import` in zipfixtures 1, `open_package(UL_ZIP, REPO_ROOT)` in conftest 1, the real-zip path in conftest/zipfixtures/test_adapters 0; `ulfixtures.py` imports the standard library only; `def test_` count in test_ulfixtures.py is 10.
