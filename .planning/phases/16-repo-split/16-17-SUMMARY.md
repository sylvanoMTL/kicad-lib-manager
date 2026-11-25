---
phase: 16-repo-split
plan: 17
subsystem: testing
tags: [pytest, fixtures, ultra-librarian, synthetic-sample]

requires:
  - phase: 16-repo-split
    provides: "16-01 zipfixtures.UL_ZIP, the generated Ultra Librarian zip"
provides:
  - "seven Bucket A test modules that read the Ultra Librarian sample through zipfixtures.UL_ZIP"
  - "test_roundtrip_corpus without the pinned SHA-256 of the real zip"
affects: [16-08, 16-09, 16-10, 16-11, 16-18]

actuals:
  tokens: 1500
  tasks: 2
  commits: 2

plan_head_before: a4e775fa7560fd36d59ecabea5a1f49b197fe634
plan_head_after: ae1c32911b8b64aeefe7bbeb18b457ec410fe060

tech-stack:
  added: []
  patterns:
    - "Test modules import the shared generated sample (from zipfixtures import UL_ZIP) instead of building a path to downloaded_examples/"

key-files:
  created: []
  modified:
    - tests/test_samacsys_adapter.py
    - tests/test_gate_reasons.py
    - tests/test_generated_text.py
    - tests/test_official_footprint.py
    - tests/test_roundtrip_corpus.py
    - tests/test_kicad_files.py
    - tests/test_edits.py

key-decisions:
  - "No builder change was needed: every module passed on the generated sample after the constant swap (the plan's 16-01 run (b) held)"

requirements-completed: [SPLIT-04]

coverage:
  - id: D1
    description: "The seven modules read the Ultra Librarian sample through zipfixtures.UL_ZIP and pass with downloaded_examples/ul_CSD85301Q2.zip moved out of the checkout"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "pytest tests/test_samacsys_adapter.py tests/test_gate_reasons.py tests/test_generated_text.py tests/test_official_footprint.py tests/test_roundtrip_corpus.py tests/test_kicad_files.py tests/test_edits.py -n 8 (real zip moved out): 199 passed, 7 skipped"
        status: pass
    human_judgment: false
  - id: D2
    description: "ZIP_SHA256 and test_ul_zip_is_pinned_and_tracked are gone from test_roundtrip_corpus"
    requirement: SPLIT-04
    verification:
      - kind: other
        ref: "grep -c 'test_ul_zip_is_pinned_and_tracked\\|ZIP_SHA256' tests/test_roundtrip_corpus.py prints 0; grep -c '^ZIP = UL_ZIP' prints 1"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 17: Seven modules read the synthetic Ultra Librarian sample Summary

**Seven Bucket A test modules now take the Ultra Librarian sample from the generated `zipfixtures.UL_ZIP`; the round-trip module no longer pins the real TI zip's SHA-256 or asserts that it is git-tracked.**

## Performance

- **Duration:** about 12 min
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- The module constant `UL_ZIP = REPO_ROOT / "downloaded_examples" / "ul_CSD85301Q2.zip"` is deleted from six modules, and each now imports `UL_ZIP` from `zipfixtures`.
- `tests/test_roundtrip_corpus.py` has `ZIP = UL_ZIP`, so the `zip/*` round-trip params run on the synthetic members. `ZIP_SHA256`, `test_ul_zip_is_pinned_and_tracked` and the then-unused `hashlib` and `subprocess` imports are removed (`REPO` stays: the `custom/*`, fixtures and Wurth parts still use it).
- No change to `tests/ulfixtures.py` or `tests/zipfixtures.py`.

## Swaps (line numbers at the base commit a4e775f)

| Module | Constant removed | Import now |
|--------|------------------|------------|
| tests/test_samacsys_adapter.py | line 46 | `UL_ZIP` added to the parenthesised `from zipfixtures import (...)` |
| tests/test_gate_reasons.py | line 23 | `UL_ZIP` added to `from zipfixtures import STEP_BYTES, UL_ZIP, ...` |
| tests/test_generated_text.py | line 27 | new module-level `from zipfixtures import UL_ZIP` (the in-function import at line 250 stays) |
| tests/test_official_footprint.py | line 112 | `UL_ZIP` added to `from zipfixtures import STEP_BYTES, UL_ZIP, make_zip` |
| tests/test_kicad_files.py | line 27 | new `from zipfixtures import UL_ZIP` after `import pytest` |
| tests/test_edits.py | line 29 | new `from zipfixtures import UL_ZIP` after `import pytest` |
| tests/test_roundtrip_corpus.py | lines 22-23 (`ZIP`, `ZIP_SHA256`) and the test at 117-124 | `ZIP = UL_ZIP`, new `from zipfixtures import UL_ZIP`; test and hash deleted |

Left for later plans, as the plan says: `CUSTOM_SYMBOL` in test_edits (16-08), `ATXK_ZIP` / `requires_atxk` in test_gate_reasons (16-09), `_custom_files` in test_kicad_files and the `custom/*` and Wurth params in test_roundtrip_corpus (16-08), the KiCad stock reads of test_generated_text and test_official_footprint (16-10).

## Measured run (real zip moved out of the checkout)

`downloaded_examples/ul_CSD85301Q2.zip` was moved to the scratchpad, all seven modules run in one pytest call (`-n 8`, quick run, slow tests not selected), then the zip was put back (`downloaded_examples` listing identical, `git status --porcelain` clean for it).

**199 passed, 7 skipped.** All seven skips are environment skips, none caused by this change:
- `Custom/` submodule not checked out: test_kicad_files:365 and :380, test_edits:106 and :179, test_roundtrip_corpus:104
- `ul_ATXK-H14-D-32-768KHZ-E50-T3.zip` not present: test_gate_reasons:240
- needs `KICAD_TEST_REAL_CONFIG=1`: test_roundtrip_corpus:193

The plan's two verify commands were run as one combined run (Task 2's command is a superset of Task 1's), because the harness here rejects the compound shell form; the move-out and move-back were done as separate plain commands.

## Task Commits

1. **Task 1: adapter, gate-reason and generated-text tests** - `493bb9e` (test)
2. **Task 2: round-trip and KiCad-file tests, pinned-hash test removed** - `ae1c329` (test)

## Decisions Made

None beyond following the plan: no builder gap showed up, so there was nothing to hand back to plan 16-01.

## Deviations from Plan

None - plan executed exactly as written (apart from the combined verify run noted above, which covers both tasks' modules).

## Issues Encountered

None. Ruff is not installed in the venv, so import order was kept by hand in the style of the neighbouring files (`from zipfixtures import ...` in the third-party block, a blank line, then `kicad_lib_manager`).

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface; T-16-37 mitigated by running with the real zip out of the checkout and by the real-path grep being 0 over all seven modules.

## Next Phase Readiness

Plan 16-18 repoints the other seven modules in the same wave; 16-08, 16-09 and 16-10 convert the remaining repository reads of these seven modules.

## Self-Check: PASSED

- FOUND commits: 493bb9e, ae1c329 (ancestors of HEAD); `git rev-list --count a4e775f..HEAD` was 2 before this SUMMARY commit
- Acceptance greps: real-path grep 0 in all seven modules; `test_ul_zip_is_pinned_and_tracked|ZIP_SHA256` 0; `^ZIP = UL_ZIP` 1; each of the three Task 2 modules imports from zipfixtures
- `downloaded_examples/ul_CSD85301Q2.zip` back in place; tests/ulfixtures.py and tests/zipfixtures.py unchanged
