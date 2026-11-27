---
phase: 17-library-catalog
plan: 08
subsystem: importer
tags: [importer, third-party, catalog, corpus, invariant, tdd]

requires:
  - phase: 17-library-catalog
    provides: curated Wurth entry with legacy_prefix and variable map (17-04), collection constants THIRD_PARTY_DIR and STAGING_DIR (17-05), validate.unresolved_models (17-06)
provides:
  - importer.verify.symbol_search_dirs over ThirdParty/<id> clones plus the legacy Wurth folder; every third-party label searched recursively
  - tests/test_third_party_sources.py (vendor-name invariant, corpus unresolved-models test = D-26 check 3 as a standing test)
  - Wurth corpus tests read ThirdParty/WurthElektronik (legacy folder as fallback); audit rule covers ThirdParty
affects: [17-09, 17-10, 17-11, 17-13, 17-17, 17-18]

plan_head_before: fd23afbf3fb4e119b16891ae6a92d64260df6786
plan_head_after: 977fcfb47d6582051a692a28b54064fbda31dfb9

actuals:
  tokens: 3750
  tasks: 2
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Third-party sources are identified by catalog id (the ThirdParty/<id> folder name); the vendor folder name stays only in the curated entry, the legacy name search and the User Guide text, and a guard test keeps it there"
    - "Corpus-helper functions that take the collection root (_wurth_root_in) so the rule is quick-testable on a scratch tree while the corpus-reading wrapper stays behind the corpus mark"

key-files:
  created:
    - tests/test_third_party_sources.py
  modified:
    - kicad_lib_manager/importer/verify.py
    - tests/test_install_verify.py
    - tests/test_importer_layering.py
    - tests/test_roundtrip_corpus.py
    - tests/test_corpus_audit.py

key-decisions:
  - "Search order is Custom, every ThirdParty/<id> folder (sorted by id without case, .staging and dot folders skipped, label '<id>:'), the legacy WurthElektronik folder ('WurthElektronik:') while it exists, KiCad stock, extra folders; a Wurth clone present in both places is reported once because both carry the same label"
  - "_symbol_files is flat only for the own, stock and extra labels ('' and 'KiCad:') and recursive for every other label"
  - "importer.verify is allowed to import collection (layering allow-list in tests/test_importer_layering.py), as importer.layout, planner and others already are; no catalog import"
  - "The Wurth corpus root is ThirdParty/WurthElektronik when that folder exists, else the legacy folder, else the legacy path so the corpus test fails naming both places instead of skipping"

requirements-completed: [CAT-12, CAT-05]  # REQUIREMENTS.md boxes stay open: later plans of the phase declare the same IDs (shared-ID gate)

coverage:
  - id: D1
    description: "The importer's same-part-name search covers every ThirdParty/<id> clone recursively with label '<id>:' (staging and dot folders never), keeps the legacy WurthElektronik folder, and keeps the order Custom, third-party, KiCad stock, extra folders"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_install_verify.py#test_search_dirs_cover_third_party_clones"
        status: pass
      - kind: unit
        ref: "tests/test_install_verify.py#test_third_party_label_is_searched_recursively"
        status: pass
      - kind: unit
        ref: "tests/test_install_verify.py#test_elsewhere_search_dirs_order (unchanged)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Wurth corpus tests read ThirdParty/WurthElektronik of the corpus collection and fall back to the legacy folder; the data-folder audit also flags a root path to ThirdParty"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_roundtrip_corpus.py#test_wurth_root_follows_third_party"
        status: pass
      - kind: unit
        ref: "tests/test_corpus_audit.py#test_audit_finds_third_party_paths"
        status: pass
    human_judgment: false
  - id: D3
    description: "The vendor-name invariant: only catalog/curated.py, importer/verify.py and widgets/help_dialog.py of the app package contain the vendor folder name"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_third_party_sources.py#test_only_known_modules_name_wurth"
        status: pass
      - kind: unit
        ref: "tests/test_third_party_sources.py#test_the_invariant_sees_a_planted_vendor_name"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-26 check 3 as a standing corpus test: no unresolved Wurth model path in the corpus collection's ThirdParty clone with its entry's variables, or in the legacy folder with the curated variable map. Proven here on five synthetic collections; the run against the owner's real collection is owner-run"
    requirement: "CAT-12"
    verification: []
    human_judgment: true
    rationale: "The test is marked corpus and slow and is deselected without KICAD_TEST_CORPUS; only the owner's real Wurth library can show it passes on real data. Its logic was exercised on scratch collections (new place and legacy place, model present and missing, neither folder) with a one-off script."

# Metrics
duration: 7min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 08: Third-party sources follow ThirdParty Summary

**The importer's "same part name in another library" search now covers every ThirdParty/<id> clone recursively (plus the legacy Wurth folder), the Wurth corpus tests read ThirdParty/WurthElektronik, and a guard test keeps the vendor folder name out of every other module.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-11-27T09:50:00Z
- **Completed:** 2026-11-27T09:58:00Z
- **Tasks:** 2 (TDD: 3 RED/GREEN commits per task pair plus one refactor and one line-ending restore)
- **Files modified:** 6 (1 created)

## Accomplishments

- `symbol_search_dirs` returns, after Custom, one `("<id>:", ThirdParty/<id>)` pair per clone (sorted by id without case; `.staging`, dot folders and loose files skipped), then the legacy `WurthElektronik:` folder while it exists, then KiCad stock and extra folders. It still returns `(label, folder)` pairs, so `test_elsewhere_search_dirs_order` passes unchanged.
- `_symbol_files` walks recursively for every label except `""` and `"KiCad:"`, so a symbol at `ThirdParty/SparkFun/symbols/deep/A.kicad_sym` is found as `SparkFun:A`.
- `tests/test_roundtrip_corpus.py`: `_wurth_root_in(collection)` picks `ThirdParty/WurthElektronik` when it exists, else the legacy folder; `_wurth_files` and `_wurth_params` use it; ids stay `wurth/<path relative to the root used>`.
- `tests/test_corpus_audit.py`: the `_DATA` rule also matches `ThirdParty`; a new self-test proves root paths to it are flagged while `corpus_path("ThirdParty", ...)` in a corpus-marked test is not (and is flagged when unmarked).
- `tests/test_third_party_sources.py`: `test_only_known_modules_name_wurth` (scans the text of every module of the app package, any letter case), a planted-violation self-test, and `test_corpus_wurth_models_resolve` (corpus + slow).

## Task Commits

1. **Task 1: name search over ThirdParty clones**
   - RED `70ffd59` (test) - two failing tests, RED_EVIDENCE_OK (junit), both fail on the planned assertions (no ThirdParty pairs listed; recursive third-party symbol not found)
   - GREEN `23cacaa` (feat)
2. **Task 2: corpus paths, audit rule, invariant**
   - RED `9da3c7e` (test) - `test_audit_finds_third_party_paths` and `test_wurth_root_follows_third_party` fail on the planned assertions, RED_EVIDENCE_OK (junit)
   - GREEN `5c9f029` (feat)
   - `ec8ec13` (refactor) - the corpus test failure names the ThirdParty clone path even without a catalog entry
3. `977fcfb` (style) - restore CRLF line endings of tests/test_install_verify.py (see Deviations)

**Plan metadata:** the docs commit that carries this SUMMARY.

## TDD Gate Compliance

Task 1: RED (`70ffd59`) precedes GREEN (`23cacaa`). Task 2: RED (`9da3c7e`) precedes GREEN (`5c9f029`).
RED evidence for both (semanticAssessment): the target tests were collected and executed and failed on the planned assertion for the planned reason (missing ThirdParty entries in the search list; legacy-only Wurth root; audit regex without ThirdParty). `_wurth_root_in` was extracted behaviour-preservingly in the RED commit so the test fails on an assertion, not on a missing name.
Guard tests (`test_only_known_modules_name_wurth`, `test_the_invariant_sees_a_planted_vendor_name`) were green from the start by design: the invariant already held at plan time; the planted-violation self-test proves the guard can go red. `test_corpus_wurth_models_resolve` cannot run without a corpus.

## Files Created/Modified

- `kicad_lib_manager/importer/verify.py` - `_third_party_dirs`, `symbol_search_dirs` over ThirdParty, recursive search for every third-party label
- `tests/test_install_verify.py` - `test_search_dirs_cover_third_party_clones`, `test_third_party_label_is_searched_recursively`
- `tests/test_importer_layering.py` - `importer.verify` may import `collection`
- `tests/test_roundtrip_corpus.py` - `_wurth_root_in`, `_wurth_root`, `test_wurth_root_follows_third_party`
- `tests/test_corpus_audit.py` - `ThirdParty` in `_DATA`, `test_audit_finds_third_party_paths`
- `tests/test_third_party_sources.py` - vendor-name invariant and the corpus unresolved-models test

## Decisions Made

See key-decisions. Assumption-delta outcome: **promote** held. The catalog id is the identity of a third-party source; the Wurth folder is a legacy variant. No new Wurth-only code was added; `grep -rli wurthelektronik kicad_lib_manager` lists exactly catalog/curated.py, importer/verify.py and widgets/help_dialog.py.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] importer.verify needs `collection` in the layering allow-list**
- **Found during:** Task 1 (GREEN)
- **Issue:** The plan imports THIRD_PARTY_DIR and STAGING_DIR from `..collection`, but `tests/test_importer_layering.py` listed `importer.verify` without `collection`; the layering test would fail. The plan's file list did not name that test.
- **Fix:** Added `"collection"` to the `importer.verify` set (`collection` is a leaf with no network path, the same allowance `importer.layout` and `importer.planner` have).
- **Files modified:** tests/test_importer_layering.py
- **Verification:** tests/test_importer_layering.py passes (155 passed with test_install_verify.py and test_custom_literals.py)
- **Committed in:** 23cacaa

**2. [Rule 1 - Bug] An in-place `sed -i` turned tests/test_install_verify.py from CRLF to LF**
- **Found during:** SUMMARY preparation (`git diff --stat` showed 1075 changed lines)
- **Issue:** MSYS sed rewrote the line endings of the whole file in the RED commit.
- **Fix:** Converted the file back to CRLF in a separate commit; the net diff against the plan start is the 31 added lines only.
- **Files modified:** tests/test_install_verify.py
- **Verification:** `git diff --stat fd23afb HEAD` shows 31 insertions for that file; 46 tests pass
- **Committed in:** 977fcfb

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** No scope change; the history of that file shows one noisy intermediate commit (`70ffd59`) followed by the restore.

## Issues Encountered

- A catalog id equal to `KiCad` would give the label `KiCad:` and be searched flat (labels decide flat versus recursive). Not reachable with the curated ids; noted for the Add dialog rules if a free id is ever allowed to be `KiCad`.
- The quick-run skip count is unchanged (1 skip, the existing real-config test, in the plan's command); the corpus deselection count rose from 3 to 4 with the new corpus test.

## Owner-run items

- `KICAD_TEST_CORPUS=<collection folder>` with `-m corpus` (or `--full`): `tests/test_third_party_sources.py::test_corpus_wurth_models_resolve` (D-26 check 3 on the real Wurth library, before and after the conversion) and the Wurth roundtrip and parse-budget tests, which read ThirdParty/WurthElektronik once the conversion ran. Not run here (no corpus, real library untouched).

## Known Stubs

None.

## Threat Flags

None. The new code only lists folders and reads symbol files read-only; the corpus tests are read-only and opt-in (T-17-22, T-17-23 mitigated as planned).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for the next plan of wave 5/6. The conversion (CAT-12) no longer loses the importer's name check or the Wurth corpus tests; plan 17-18's owner-run verification can run the corpus test as its D-26 check 3.

## Self-Check: PASSED

- FOUND: tests/test_third_party_sources.py, kicad_lib_manager/importer/verify.py
- FOUND commits: 70ffd59, 23cacaa, 9da3c7e, 5c9f029, ec8ec13, 977fcfb
- Automated commands of both tasks pass (155 passed; 42 passed, 1 skipped, 4 deselected); acceptance greps: THIRD_PARTY_DIR 4, test_search_dirs_cover_third_party_clones 1, ThirdParty in test_corpus_audit.py 9, `"ThirdParty", "WurthElektronik"` in test_roundtrip_corpus.py 2, test_only_known_modules_name_wurth 1.
- prepublish_scan on the changed files and the phase folder: clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
