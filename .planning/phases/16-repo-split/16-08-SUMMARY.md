---
phase: 16-repo-split
plan: 08
subsystem: testing
tags: [pytest, corpus-gate, live-custom, wurth]
requires:
  - phase: 16-repo-split
    provides: 16-06 corpus gate and tests/corpusfixtures.py; 16-17 synthetic UL zip repoint
provides:
  - "eight test modules read the live Custom/ and Wurth data only from the KICAD_TEST_CORPUS collection and carry the corpus mark"
affects: [16-12]
actuals:
  tokens: 9000
  tasks: 2
  commits: 2
plan_head_before: 474f2b7a416191a8ea8da1c9c053389a437d3368
plan_head_after: bf976409d8fbf9db43d400f10867034ccde4360e
tech-stack:
  added: []
  patterns:
    - "placeholder param per family (custom/corpus, wurth/corpus, custom-corpus) carries the corpus mark and fails inside an open corpus with no input"
    - "a missing corpus input is an assertion failure, never a skip"
key-files:
  created: []
  modified:
    - tests/test_roundtrip_corpus.py
    - tests/test_scanner_issues.py
    - tests/test_kicad_files.py
    - tests/test_edits.py
    - tests/test_naming_sanitize.py
    - tests/test_locate_text_caps.py
    - tests/test_sexpr.py
    - tests/test_atomic_uat.py
key-decisions:
  - "Placeholder params fail with a message when the corpus is open but holds no input, so a half-empty collection is a failure"
  - "test_live_custom_model_findings_are_zero keeps slow and gains corpus, so it needs --full as well as a corpus"
requirements-completed: [SPLIT-04]
coverage:
  - id: D1
    description: "Without a corpus the eight modules pass and the corpus tests are deselected with a count"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "KICAD_TEST_CORPUS= pytest tests/test_roundtrip_corpus.py tests/test_scanner_issues.py tests/test_kicad_files.py tests/test_edits.py -n 0 (122 passed, 1 skipped, 9 deselected); tests/test_naming_sanitize.py tests/test_locate_text_caps.py tests/test_sexpr.py tests/test_atomic_uat.py (227 passed, 6 deselected)"
        status: pass
    human_judgment: false
  - id: D2
    description: "With the corpus set to the feature/part-importer checkout every live test runs and passes against the real Custom/ and Wurth data, and the session guard stays green"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "KICAD_TEST_CORPUS=<checkout> pytest (task 1 modules: 163 passed, 1 skipped; task 2 modules: 231 passed); --full -k live_custom_model: 1 passed"
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 08: Live-Custom and Wurth Tests Read the Corpus Collection Summary

**Eight test modules now read the live Custom/ and Wurth data from the KICAD_TEST_CORPUS collection under the corpus mark, so a fresh clone deselects them with a count while the public halves (fixtures, synthetic zip, tokenizer, UL caps) keep running everywhere.**

## Performance

- **Duration:** about 25 min
- **Tasks:** 2 (test-conversion tasks, 1 commit each)
- **Files modified:** 8

## Accomplishments

- test_roundtrip_corpus: `custom/<path>` params from `corpus_path("Custom")`, ids unchanged, each marked corpus; `custom/corpus` and `wurth/corpus` placeholders; Wurth helpers read `corpus_path("WurthElektronik")`; `test_wurth_corpus_parse_budget` keeps its name, decorator and 900 s timeout.
- test_scanner_issues: both live tests call `check_3d_model_paths(corpus_root())` and assert their inputs exist.
- test_kicad_files: `_custom_files` reads the corpus; live symbol and footprint tests are corpus-marked and assert a non-empty list.
- test_edits: `_first_corpus_symbol()` (first `.kicad_sym` of corpus Custom/Symbols in sorted order) replaces the migrated `Connector_USB_GCT` path; `custom-<path>` params are corpus-marked with a `custom-corpus` placeholder.
- test_naming_sanitize / test_locate_text_caps / test_sexpr / test_atomic_uat: public and corpus halves split (`test_filename_live_models_unchanged`, `test_live_custom_files_are_below_both_caps` and `test_ul_sample_files_are_below_both_caps` are new); the tokenizer test stays public; the UAT scratch test carries the corpus mark.

## Counts

| Run | Modules | Result |
|---|---|---|
| no corpus | test_roundtrip_corpus, test_scanner_issues, test_kicad_files, test_edits | 122 passed, 1 skipped (opt-in real KiCad config), 9 deselected corpus |
| no corpus | test_naming_sanitize, test_locate_text_caps, test_sexpr, test_atomic_uat | 227 passed, 6 deselected (5 corpus + 1 slow) |
| corpus = feature/part-importer checkout | first four modules | 163 passed, 1 skipped |
| corpus = feature/part-importer checkout | last four modules | 231 passed |
| corpus + `--full -k live_custom_model` | test_scanner_issues | 1 passed (101 s) |
| corpus + `--collect-only --full -m wurth` | test_roundtrip_corpus | 8017 Wurth tests collected from the corpus |

The full Wurth round trip was not run here (plan 16-12 rehearsal, per the plan).

## Task Commits

1. Task 1: `d755578` (test) - round-trip, scanner, KiCad-file and edit tests
2. Task 2: `bf97640` (test) - naming, size-cap, tokenizer and atomic-UAT tests

## TDD Gate Compliance

The tasks convert existing tests to the corpus gate; the "implementation" is the test code itself, so there is no separate RED commit. The conversions were verified in both directions (no corpus: deselected with a count; corpus open: all pass), and the plan's acceptance greps all hold (direct Custom/Wurth reads 0, "not checked out" 0, Connector_USB_GCT 0, corpusfixtures import 1 per module, corpus marks 5 in task 2 modules, new test names present).

## Deviations from Plan

None - plan executed exactly as written. Unused `REPO_ROOT` constants (test_kicad_files, test_edits, test_scanner_issues, test_sexpr) and the unused `Path` import in test_naming_sanitize were removed with their last reader, as the plan allows. `REPO` stays in test_roundtrip_corpus (the fixtures folder uses it).

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. The corpus tests only read the collection; the corpus run printed no session-guard failure.

## Self-Check: PASSED

- All eight modified files present; commits d755578 and bf97640 are ancestors of HEAD.
