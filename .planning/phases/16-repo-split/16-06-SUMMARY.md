---
phase: 16-repo-split
plan: 06
subsystem: testing
tags: [pytest, xdist, markers, corpus-gate, needs_kicad]
requires:
  - phase: 16-repo-split
    provides: 16-01 synthetic zip and the conftest change this builds on
provides:
  - "corpus and needs_kicad markers, deselected with printed counts when their condition is missing"
  - "KICAD_TEST_CORPUS validation (usage error, exit code 4) and KICAD_TEST_HIDE_KICAD switch"
  - "live-Custom guard repointed at <KICAD_TEST_CORPUS>/Custom"
  - "tests/corpusfixtures.py helper module"
affects: [16-08, 16-09, 16-10]
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
plan_head_before: a4e775fa7560fd36d59ecabea5a1f49b197fe634
plan_head_after: 15bfd30
tech-stack:
  added: []
  patterns:
    - "closed test gates deselect with a printed count, never skip"
    - "xdist worker data to the controller through config.workeroutput and pytest_testnodedown"
key-files:
  created: [tests/corpusfixtures.py, tests/test_corpus_gate.py]
  modified: [pyproject.toml, tests/conftest.py, tests/test_markers.py]
key-decisions:
  - "Worker counts travel through config.workeroutput (key kicad_test_deselected) read in pytest_testnodedown; the run-temp record-file fallback was not needed"
  - "Counts are merged per key with max(), since every worker collects the same set"
  - "KICAD_TEST_HIDE_KICAD wraps library_scanner.find_kicad_footprint_dir in pytest_configure: no base gives None, an explicit base goes to the real function"
requirements-completed: [SPLIT-04]
coverage:
  - id: D1
    description: "A test marked corpus is deselected with a printed count when KICAD_TEST_CORPUS is unset or blank, identically with -n 2 and -n 0; a wrong value is a usage error (exit 4)"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "tests/test_corpus_gate.py#test_corpus_closed_deselects_with_a_count, test_counts_are_the_same_with_and_without_workers, test_blank_corpus_is_unset, test_wrong_corpus_is_a_usage_error, test_open_corpus_runs_corpus_tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "The live-Custom guard watches <corpus>/Custom and nothing without a corpus"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "tests/test_corpus_gate.py#test_guard_watches_the_corpus_custom"
        status: pass
    human_judgment: false
  - id: D3
    description: "needs_kicad tests are deselected with a printed count when KiCad is hidden or absent; KICAD_TEST_HIDE_KICAD makes the scanner find no KiCad; wurth implies corpus"
    requirement: SPLIT-04
    verification:
      - kind: integration
        ref: "tests/test_corpus_gate.py#test_hidden_kicad_deselects_needs_kicad, test_both_counts_print, test_wurth_implies_corpus"
        status: pass
      - kind: unit
        ref: "tests/test_markers.py#test_corpus_and_needs_kicad_are_registered"
        status: pass
    human_judgment: false
  - id: D4
    description: "The needs_kicad-runs-when-KiCad-is-installed direction (host dependent, proven by plan 16-10 on the workstation)"
    verification: []
    human_judgment: true
    rationale: "Depends on the host having KiCad; deliberately not a child-run test (a host skip would cost the CI skip budget)"
duration: 40min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 06: Corpus and needs_kicad Test Gate Summary

**pytest gate that deselects corpus and needs_kicad tests with a printed count (same under xdist and serially), fails on a wrong KICAD_TEST_CORPUS with exit 4, and guards the corpus collection's Custom/**

## Performance

- **Duration:** about 40 min
- **Completed:** 2026-11-24
- **Tasks:** 2 (TDD, 4 commits)
- **Files modified:** 5 (2 created)

## Accomplishments

- `tests/corpusfixtures.py`: `CORPUS_ENV`, `HIDE_KICAD_ENV`, `NO_CORPUS`, `corpus_root()`, `corpus_problem()`, `corpus_path(*parts)`, `kicad_hidden()`, `kicad_found()` (plus a small `corpus_raw()` used for the message).
- `tests/conftest.py`: `pytest_configure` raises `pytest.UsageError` for a bad corpus and installs the HIDE wrapper; `pytest_collection_modifyitems(config, items)` adds corpus to wurth tests, then deselects closed gates through `config.hook.pytest_deselected`; `pytest_testnodedown` and `pytest_terminal_summary` print the counts; `_live_custom_untouched` guards `<corpus>/Custom` or nothing.
- pyproject: `corpus` and `needs_kicad` registered, `wurth` reworded ("implies corpus and slow"); addopts unchanged.

**Channel used for the worker counts:** `config.workeroutput["kicad_test_deselected"]` in each worker, read as `node.workeroutput` in the controller's `pytest_testnodedown` (works in xdist 3.8.0, so the run-temp record-file fallback was not built).

**Exact printed lines:**

- `deselected: <n> corpus (set KICAD_TEST_CORPUS to a collection folder to run them)`
- `deselected: <m> needs_kicad (no KiCad install found)`
- usage error: `KICAD_TEST_CORPUS=<repr of value> is not a library collection: <no such folder | not a folder | it has no Custom folder>` (exit code 4)

## Task Commits

1. **Task 1 RED:** `196bad4` (test) - six child-run tests, failing because the corpus marker and gate did not exist
2. **Task 1 GREEN:** `f2a0f52` (feat) - corpus gate, usage error, repointed guard
3. **Task 2 RED:** `47cd8b2` (test) - hidden-KiCad, both-counts and marker registration tests
4. **Task 2 GREEN:** `15bfd30` (feat) - needs_kicad gate, HIDE switch, wurth wording

## TDD Gate Compliance

- RED evidence (`gsd_run check tdd-red-evidence` is unavailable in this worktree): Task 1 RED, 6 failed, each child run ended in `'corpus' not found in markers configuration` (collection error) so the planned assertions (returncode, printed line) failed. Semantic assessment: the failures are the planned behavior missing (marker, gate), not a harness fault. Task 2 RED: 3 failed (`test_hidden_kicad_deselects_needs_kicad`, `test_both_counts_print`, `test_corpus_and_needs_kicad_are_registered`).
- `test_wurth_implies_corpus` was green at Task 2 RED: the wurth-implies-corpus mark was built together with the corpus gate in Task 1 (it is part of that hook), so it is not a RED test.

## Cases exercised and not exercised

- Exercised: closed corpus (unset, blank), wrong corpus (missing folder, folder without Custom/), open corpus built in a temp folder, guard failure on a write into `<corpus>/Custom/Symbols`, hidden KiCad, both counts, wurth with `--full`, counts identical with `-n 2` and `-n 0`.
- Not exercised: the real collection (the worktree has no `Custom/` checkout; an open corpus is a temp folder with `Custom/Symbols`), and "needs_kicad runs when KiCad is installed" (host dependent; this workstation has KiCad 9 and 10, so `kicad_found()` is true here; plan 16-10 proves the run direction).

## Verification

- `tests/test_corpus_gate.py tests/test_isolation.py tests/test_markers.py tests/test_manifests.py -n 0`: 30 passed, 2 deselected (Task 1 state); after Task 2: `test_corpus_gate + test_markers + test_manifests` 22 passed, `test_isolation + test_manifests` 15 passed.
- `KICAD_TEST_HIDE_KICAD=1 pytest tests/test_corpus_gate.py tests/test_kicad_config.py`: 71 passed.
- All acceptance greps of both tasks hold (corpus: 1, addopts: 1, old guard call: 0, pytest_deselected: 1, workeroutput: 4, corpusfixtures defs: 3 and 2, needs_kicad line: 1, registration test: 1, "implies corpus": 1).
- The whole suite was not run (the orchestrator runs the quick suite after the wave merge).

## Decisions Made

- Counts are collected by marker name via a small `_gate` helper, so the corpus partition runs first and needs_kicad only sees what remains (a test with both marks is counted as corpus once).
- A quick (non-`--full`) run counts wurth tests in the corpus line even though `-m 'not slow'` would also drop them, because the gate runs `tryfirst` before the built-in `-m` deselection.

## Deviations from Plan

None - plan executed exactly as written. (The `--full`-free quick-run counting of wurth tests under "corpus" is a consequence of the specified ordering, noted above.)

## Issues Encountered

None.

## Known Stubs

None.

## Next Phase Readiness

Plans 16-08, 16-09 and 16-10 can mark modules `corpus` / `needs_kicad` and build constants with `corpus_path(...)`. `_READ_ONLY_GIT_TESTS` in tests/test_markers.py is untouched, as the plan says.

## Self-Check: PASSED

- tests/corpusfixtures.py, tests/test_corpus_gate.py present; commits 196bad4, f2a0f52, 47cd8b2, 15bfd30 are ancestors of HEAD.
