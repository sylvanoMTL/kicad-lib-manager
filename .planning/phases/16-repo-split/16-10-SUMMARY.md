---
phase: 16-repo-split
plan: 10
subsystem: testing
tags: [pytest, needs_kicad, corpus, skip-budget]
requires:
  - phase: 16-repo-split
    provides: 16-06 needs_kicad and corpus gate, corpusfixtures.corpus_path
provides:
  - "twelve stock-library tests gated by needs_kicad instead of no-KiCad skips"
  - "test_footprint_text real-sample tests gated by corpus and read from the corpus collection"
affects: [16-11]
actuals:
  tokens: 6000
  tasks: 2
  commits: 2
plan_head_before: 474f2b7a416191a8ea8da1c9c053389a437d3368
plan_head_after: 5b1e523
key-files:
  created: []
  modified:
    - tests/test_footprint_text.py
    - tests/test_generated_text.py
    - tests/test_official_footprint.py
    - tests/test_install_verify.py
    - tests/test_siblings.py
    - tests/test_stems.py
    - tests/test_footprint_index.py
key-decisions:
  - "Inside the gate a missing stock file or sample is an assertion failure, not a skip"
  - "The KiCad-10 version skips in test_siblings (2) and test_stems (1) stay; only install presence moved to needs_kicad"
requirements-completed: [SPLIT-04]
coverage:
  - id: D1
    description: "Stock-library tests carry needs_kicad; on a runner without KiCad they are deselected with a printed count and no skip mentions a KiCad install"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "KICAD_TEST_HIDE_KICAD=1 pytest of the seven modules: 131 + 95 passed, 0 skips"
        status: pass
    human_judgment: false
  - id: D2
    description: "On the workstation (KiCad 10 installed) the needs_kicad tests run and pass; the real-sample tests pass against the corpus checkout"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "no HIDE switch, KICAD_TEST_CORPUS=<orchestrator checkout>: 145 passed (four modules), 99 passed (three modules)"
        status: pass
    human_judgment: false
duration: 20min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 10: needs_kicad and corpus marks for the stock-library tests Summary

**Twelve tests that read an installed KiCad's stock libraries now carry needs_kicad (deselected with a count on a KiCad-less runner, run on the workstation), and test_footprint_text's three vendor-sample tests read the corpus collection under the corpus mark.**

## Accomplishments

- test_footprint_text: `_SAMPLES = corpus_path("downloaded_examples")`, the missing-download skip became an assertion, three real-sample tests are `@pytest.mark.corpus`; `_stock` asserts instead of skipping and its two users are `needs_kicad`.
- test_generated_text: `needs_kicad_footprints = pytest.mark.needs_kicad` (alias kept for the five decorators).
- test_official_footprint, test_install_verify: one `needs_kicad` test each, with assertions on the stock folders and `Package_SON.pretty/Texas_DQK.kicad_mod`.
- test_siblings (2 tests), test_stems (1), test_footprint_index (1): install-presence skips replaced by `needs_kicad`; the "installed KiCad is not version 10" skips are untouched.

## needs_kicad deselected count under KICAD_TEST_HIDE_KICAD=1

| Module | needs_kicad | corpus |
|--------|-------------|--------|
| test_footprint_text | 2 | 3 |
| test_generated_text | 7 (5 decorated tests, 3 of them parametrised twice or once) | 0 |
| test_official_footprint | 1 | 0 |
| test_install_verify | 1 | 0 |
| test_siblings | 2 | 0 |
| test_stems | 1 | 0 |
| test_footprint_index | 1 | 0 |

Printed lines: four-module run "deselected: 3 corpus" and "deselected: 11 needs_kicad"; three-module run "deselected: 4 needs_kicad".

## Task Commits

1. Task 1: `d6c8b7b` (test) - footprint-text, generated-text, official-footprint, install-verify
2. Task 2: `5b1e523` (test) - siblings, stems, footprint-index

## Verification

- Task 1 hidden run (`KICAD_TEST_HIDE_KICAD=1 KICAD_TEST_CORPUS=`, `-n 0`): 131 passed, 16 deselected, no skip.
- Task 1 workstation run (KiCad 10, corpus = the orchestrator checkout, read only): 145 passed.
- Task 2 hidden run: 95 passed, 4 deselected; workstation run: 99 passed, no skip reason.
- Acceptance greps: "no KiCad install" 0 in all seven modules; needs_kicad marks 5 (task 1 modules) and 4 (task 2 modules); `"not version 10"` 2 in test_siblings; the `REPO_ROOT / "downloaded_examples"` pattern 0.
- The whole suite was not run (16-11 measures the skip budget).

## TDD Gate Compliance

These tasks change test gating only (marks and assertions on existing tests); no production behavior was added, so no failing RED test exists to write. The gate behavior itself is proven by the 16-06 tests; here the proof is the hidden and workstation runs above.

## Deviations from Plan

None - plan executed exactly as written. (A comment in test_generated_text was reworded so the "no KiCad install" grep count is 0.)

## Known Stubs

None.

## Self-Check: PASSED

- All seven modules modified; commits d6c8b7b and 5b1e523 are ancestors of HEAD.
