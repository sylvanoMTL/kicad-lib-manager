---
phase: 16-repo-split
plan: 09
subsystem: testing
tags: [pytest, corpus-gate, vendor-samples, originality, ultra-librarian]
requires:
  - phase: 16-repo-split
    provides: "16-01 synthetic UL builder, 16-03 pre-publish scan windows(), 16-06 corpus gate and corpus_path"
provides:
  - "real vendor download tests read from <KICAD_TEST_CORPUS>/downloaded_examples and carry corpus (KiCad 10 ones also needs_kicad)"
  - "test_fixture_originality over snapeda, samacsys, snapeda_model and ul"
  - "test_builders_share_no_three_line_window and test_ul_builder_matches_the_real_sample_structure"
  - "empty _READ_ONLY_GIT_TESTS, no zip exception in .gitignore, only tests/fixtures/** -text (plus .githooks) in .gitattributes"
affects: [16-12, 16-14, 16-15]
actuals:
  tokens: 12000
  tasks: 2
  commits: 3
plan_head_before: 474f2b7a416191a8ea8da1c9c053389a437d3368
plan_head_after: 39d072e2448145368911eef34db0e1b97be1e751
tech-stack:
  added: []
  patterns:
    - "corpus-only reads of licence-restricted downloads, compared in memory, failure messages never carry real content"
key-files:
  created: []
  modified:
    - tests/test_real_vendor_samples.py
    - tests/test_markers.py
    - tests/test_vendorfixtures.py
    - tests/test_categories.py
    - tests/test_atomic_targets.py
    - tests/test_gate_reasons.py
    - tests/ulfixtures.py
    - .gitignore
    - .gitattributes
key-decisions:
  - "The two new vendorfixtures checks are parametrized per vendor (originality windows) or single (UL structure); a missing download inside an open corpus fails with FileNotFoundError, never skips"
  - "Structure-comparison failures name only what differs ('pad count of the synthetic UL sample differs from the real one'), so no real value reaches a log"
  - "requires_kicad_10 became a decorator function applying corpus, needs_kicad and the existing KiCad-10 skipif"
requirements-completed: [SPLIT-04]
coverage:
  - id: D1
    description: "Every real-download test reads its zip from the corpus collection and carries corpus; none skips on a missing file; KiCad 10 suggestion tests also carry needs_kicad"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "KICAD_TEST_CORPUS= pytest tests/test_real_vendor_samples.py tests/test_markers.py tests/test_fixtures.py (94 passed, 12 corpus deselected)"
        status: pass
      - kind: integration
        ref: "KICAD_TEST_CORPUS=<feature/part-importer checkout> pytest tests/test_real_vendor_samples.py --full (12 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "test_vendor_zips_stay_local deleted, _READ_ONLY_GIT_TESTS empty, zip exception and downloaded_examples -text line removed, local tool files ignored"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_markers.py#test_read_only_git_allow_list_is_exact; git check-ignore -q downloaded_examples/new.zip CLAUDE.local.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "With the corpus open the synthetic UL sample matches the real one (members and order, adapter result, property and pin names, pad count, CRLF) and no builder member is a byte copy of or shares three lines with a real member"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "tests/test_vendorfixtures.py#test_ul_builder_matches_the_real_sample_structure, test_builders_share_no_three_line_window, test_fixture_originality (13 passed with the corpus)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The synthetic UL sample keeps matching the real format over time"
    verification: []
    human_judgment: true
    rationale: "Backstop truth: only each owner corpus run (and the 16-12 rehearsal) confirms it going forward; this plan records the first passing run below"
duration: 35min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 09: Real-download tests on the corpus and UL builder checks Summary

**Real SnapEDA, SamacSys and Ultra Librarian download tests moved to the corpus collection (corpus / needs_kicad marks), the stay-local test and zip exception removed, and two new corpus checks that prove the synthetic UL sample matches the real format without copying it**

## Performance

- **Duration:** about 35 min
- **Tasks:** 2 (both `tdd="true"`)
- **Files modified:** 9 (no files created)

## Accomplishments

- tests/test_real_vendor_samples.py, test_categories.py, test_atomic_targets.py, test_gate_reasons.py resolve every real zip with `corpus_path("downloaded_examples", ...)`; the file skips and their "not present" texts are gone. `requires_snapeda`, `requires_samacsys`, `requires_snapeda_model`, `requires_atxk` are now `pytest.mark.corpus`; `requires_kicad_10` applies corpus, needs_kicad and the KiCad-10 version skipif.
- `test_vendor_zips_stay_local` deleted; `_READ_ONLY_GIT_TESTS = {}` and its test asserts the empty dict (and still checks any future entry).
- .gitignore: `downloaded_examples/*` without the `!ul_CSD85301Q2.zip` exception, plus `CLAUDE.local.md`, `.gsd/`, `.pytest_cache/`, `.ruff_cache/`, `junit.xml`; .gitattributes: the `downloaded_examples/** -text` line is gone (`tests/fixtures/** -text` and 16-04's `.githooks/* text eol=lf` kept). The tracked UL zip stays tracked (`git ls-files downloaded_examples` lists it); untracking happens at the collection cutover.
- tests/test_vendorfixtures.py: `test_fixture_originality` now covers snapeda, samacsys, snapeda_model and ul (corpus-marked, UL builder members included in `_all_members()`, REAL_PART_NAMES check kept for the three non-UL vendors); new `test_builders_share_no_three_line_window` (per vendor, loads scripts/prepublish_scan.py by path for `windows`) and `test_ul_builder_matches_the_real_sample_structure`.

## Corpus run output (evidence for the backstop truth)

Corpus = the feature/part-importer checkout (``), read-only:

```
KICAD_TEST_CORPUS=<corpus> pytest tests/test_vendorfixtures.py -n 0 -rA
PASSED tests/test_vendorfixtures.py::test_fixture_originality[snapeda]
PASSED tests/test_vendorfixtures.py::test_fixture_originality[samacsys]
PASSED tests/test_vendorfixtures.py::test_fixture_originality[snapeda_model]
PASSED tests/test_vendorfixtures.py::test_fixture_originality[ul]
PASSED tests/test_vendorfixtures.py::test_builders_share_no_three_line_window[snapeda]
PASSED tests/test_vendorfixtures.py::test_builders_share_no_three_line_window[samacsys]
PASSED tests/test_vendorfixtures.py::test_builders_share_no_three_line_window[snapeda_model]
PASSED tests/test_vendorfixtures.py::test_builders_share_no_three_line_window[ul]
PASSED tests/test_vendorfixtures.py::test_ul_builder_matches_the_real_sample_structure
(13 passed in the module)
```

Whole task-2 verify set with the corpus: `test_vendorfixtures test_categories test_atomic_targets test_gate_reasons test_ulfixtures` 115 passed. `test_real_vendor_samples.py --full` with the corpus: 12 passed (including the two KiCad 10 suggestion tests and the kicad-cli load tests, KiCad 10 being installed). Without a corpus: the three-module run is `94 passed, 12 deselected` (printed `deselected: 12 corpus ...`) and the task-2 modules `103 passed, 12 deselected`; no skip text mentions "not present".

A mutation check showed the structure comparison has teeth: removing one footprint pad from the builder made `test_ul_builder_matches_the_real_sample_structure` fail with `pad count of the synthetic UL sample differs from the real one`; reverted before the commit.

## Task Commits

1. **Task 1 RED:** `e37e1c0` (test) - allow-list test asserts `{}` and failed against the stay-local entry
2. **Task 1 GREEN:** `c79708f` (feat) - real-download tests on the corpus, stay-local test deleted, ignore rules
3. **Task 2:** `39d072e` (feat) - UL originality and structure checks, ATXK and SamacSys readers on the corpus, ulfixtures fix (see deviation)

## Deviations from Plan

**1. [Rule 1 - Bug] UL builder footprint shared three consecutive lines with the real footprint**
- **Found during:** Task 2 (first corpus run of `test_builders_share_no_three_line_window[ul]`)
- **Issue:** the four body-outline `fp_line` lines of `ul_footprint()` were in the real footprint's order, so three consecutive 25+ character lines coincided; the plan's must-have requires none.
- **Fix:** draw the same square outline in another order (top, left, bottom, right); geometry, pad count and every other check unchanged.
- **Files modified:** tests/ulfixtures.py (a 16-01 file, not listed in this plan's files_modified)
- **Verification:** the window check passes for all four vendors; `test_ulfixtures.py` and the structure comparison still pass.
- **Committed in:** 39d072e

**Total deviations:** 1 auto-fixed (1 bug). **Impact:** the guard found a real overlap on its first run; the fix is a pure reorder.

## TDD Gate Compliance

- Task 1: RED `e37e1c0` (`test_read_only_git_allow_list_is_exact` failed: the dict still held the stay-local entry, planned assertion `_READ_ONLY_GIT_TESTS == {}`), GREEN `c79708f`. `gsd_run check tdd-red-evidence` is unavailable in this worktree; semantic assessment: the target test ran and failed on the planned assertion.
- Task 2: no separate RED commit. The new tests verify a builder that already exists (16-01); they are corpus-marked, so without a corpus there is nothing that can fail first, and with the corpus the first run was the RED-equivalent: it failed once on a real defect (the shared window above) and passed after the GREEN fix in the same commit. The mutation check above is the evidence that the structure test can fail.

## Issues Encountered

None beyond the deviation. The worktree has no `ruff` in the shared venv, so no lint run was made; imports follow the isort grouping of the surrounding files.

## Known Stubs

None.

## Threat Flags

None. No real vendor content is written, copied or printed: members are read in memory and failure messages name only builder members or the differing property.

## Next Phase Readiness

- 16-12 rehearsal and 16-14 scan can rely on the corpus tests above; `downloaded_examples/ul_CSD85301Q2.zip` is still tracked and is removed at the collection cutover (16-15).
- The backstop truth (the builder keeps matching the real format) is confirmed by the run above; later owner corpus runs keep it confirmed.

## Self-Check: PASSED

- Commits `e37e1c0`, `c79708f`, `39d072e` are ancestors of HEAD.
- All acceptance greps: stay-local 0, `!downloaded_examples` 0, `.gitattributes downloaded_examples` 0, ignore entries 2, "not present" 0 in the five converted modules, `REPO_ROOT / "downloaded_examples"` pattern 0, new test defs 2.
- Both automated verify commands (without and with the corpus) pass.
