---
phase: 16-repo-split
plan: 11
subsystem: testing
tags: [pytest, corpus-gate, skip-budget, prepublish-scan, static-audit]
requires:
  - phase: 16-repo-split
    provides: 16-03 pre-publish scan and skip-budget script, 16-06 corpus and needs_kicad gate, 16-08..16-10 and 16-17/18 test conversions
provides:
  - "tests/test_corpus_audit.py: static audit against repository-data paths, corpus-type skips and unmarked corpus readers"
  - "measured fresh-clone skip budget with and without KiCad, and a green corpus run"
  - "tests/README.md rewritten for the split suite"
  - "kept planning files scan clean (every rule except workstation_path)"
affects: [16-12, 16-14, 16-16]
actuals:
  tokens: 14000
  tasks: 3
  commits: 4
plan_head_before: 1459e61fa1b5594c036bdb87afbea1194e37dae4
plan_head_after: b2e1e14f3dfa30fd1afb287cc6915e8510482036
tech-stack:
  added: []
  patterns:
    - "static test audits read source text with balanced-paren call extraction, detectors proven on planted lines assembled from pieces"
key-files:
  created: [tests/test_corpus_audit.py]
  modified: [tests/README.md, tests/test_ulfixtures.py, tests/test_importer_layering.py, .planning/research/PITFALLS.md, .planning/phases/16-repo-split/16-RESEARCH.md]
key-decisions:
  - "Two real offenders found by the new audits were fixed in place, no exception was added"
  - "The skip-reason detector reads the whole skip call up to its balanced closing parenthesis, so a reason on a later line of a multi-line skipif is still seen"
requirements-completed: [SPLIT-03, SPLIT-04, SPLIT-08]
coverage:
  - id: D1
    description: "A static audit fails on repo-root data paths, corpus-type skip reasons and unmarked corpus readers, with its detectors proven on planted lines"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_corpus_audit.py#test_audit_finds_planted_paths, test_audit_finds_planted_skips, test_no_test_module_reads_repo_data, test_no_corpus_type_skips, test_corpus_readers_are_marked"
        status: pass
    human_judgment: false
  - id: D2
    description: "A fresh --no-local clone without downloaded_examples/ and with empty submodules passes the quick run within the skip budget, with and without KiCad"
    requirement: SPLIT-04
    verification:
      - kind: other
        ref: "pytest quick run in the clone + python scripts/check_skip_budget.py a.xml / b.xml --max-skips 10 --min-passed 3500"
        status: pass
    human_judgment: false
  - id: D3
    description: "The quick run with KICAD_TEST_CORPUS set to the real collection passes"
    requirement: SPLIT-08
    verification:
      - kind: other
        ref: "pytest quick run with KICAD_TEST_CORPUS set to the feature/part-importer checkout"
        status: pass
    human_judgment: false
  - id: D4
    description: "tests/README.md documents the split suite (markers, env vars, deselected lines, usage error, skip budget with measured counts, synthetic UL sample, corpus guard)"
    requirement: SPLIT-08
    verification: []
    human_judgment: true
    rationale: "Documentation wording; the acceptance greps only prove the key terms are present"
  - id: D5
    description: "The kept planning files scan clean with every rule except workstation_path, and every marker exemption is listed"
    requirement: SPLIT-03
    verification:
      - kind: other
        ref: "python scripts/prepublish_scan.py --tree --deny-emails-from-repo . --skip-rule workstation_path --path <keep-set>"
        status: pass
    human_judgment: false
duration: 55min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 11: Corpus Audit, Fresh-Clone Skip Budget and Planning Scan Summary

**Static audit that keeps the public suite off repository data, a fresh-clone proof of 4013 passed / 3 skipped (3998 / 3 without KiCad), a green 4083-test corpus run, a rewritten tests/README.md, and a planning keep-set that scans clean**

## Performance

- **Duration:** about 55 min
- **Completed:** 2026-11-24
- **Tasks:** 3
- **Files modified:** 7 (1 created)

## Accomplishments

- `tests/test_corpus_audit.py`: `repo_data_lines`, `corpus_skip_lines` and five tests (two planted-line proofs, three repository-wide audits).
- Fresh-clone and corpus runs measured and recorded (below); tests/README.md carries the numbers.
- PITFALLS.md and 16-RESEARCH.md fixed at the source; the planning keep-set scan prints `prepublish_scan: clean (127 files, 0 blobs, 0 commits)`.

## Task Commits

1. **Task 1 RED:** `99ed234` (test) - planted-line tests fail against stub detectors that return no lines
2. **Task 1 GREEN:** `e28fb4d` (feat) - real detectors, plus the two in-place fixes below
3. **Task 2:** `a5f6e33` (docs) - tests/README.md rewrite with the measured counts (the three runs are measurements, they commit nothing)
4. **Task 3:** `b2e1e14` (docs) - PITFALLS.md email reworded, marker on the 16-RESEARCH.md line

## Measured runs

All three runs are quick runs with workers (bare `python -m pytest`, `-rs`). Fresh-clone runs were made from `git clone --no-local` of the worktree at `e28fb4d` (the README and planning commits that follow change no test code), with `downloaded_examples/` deleted and `Custom/` and `WurthElektronik/KiCad-Library` verified empty. The clone was deleted afterwards.

| Run | Passed | Skipped | Deselected | Time | Budget check |
| --- | --- | --- | --- | --- | --- |
| (a) fresh clone, KiCad 9 and 10 installed, `KICAD_TEST_CORPUS` and `KICAD_TEST_HIDE_KICAD` blank | 4013 | 3 | `deselected: 41 corpus (set KICAD_TEST_CORPUS to a collection folder to run them)`; no needs_kicad line (KiCad found, nothing deselected) | 2 min 3 s (122.81 s) | `skip budget: 4013 passed, 3 skipped (max 10), 0 failed, 0 errors` |
| (b) fresh clone, `KICAD_TEST_HIDE_KICAD=1` | 3998 | 3 | `deselected: 41 corpus (...)` and `deselected: 15 needs_kicad (no KiCad install found)` | 1 min 41 s (101.45 s) | `skip budget: 3998 passed, 3 skipped (max 10), 0 failed, 0 errors` |
| (c) worktree, `KICAD_TEST_CORPUS` set to the feature/part-importer checkout (read-only) | 4083 | 3 | none | 2 min 14 s (133.71 s) | not applicable; no `changed the live Custom/ folder` failure |

Skip reasons, identical in all three runs:

1. `tests/test_model_source.py:201`: `symlinks not permitted here: [WinError 1314] A required privilege is not held by the client`
2. `tests/test_package_folder.py:105`: `symlinks not permitted here: [WinError 1314] ...`
3. `tests/test_roundtrip_corpus.py:193`: `reads your real KiCad config tables: set KICAD_TEST_REAL_CONFIG=1 to run`

## Planning scan

Command (the plan's verify block, with the phase 14 file list written out because the sandbox forbids `$(git ...)`): `prepublish_scan.py --tree --deny-emails-from-repo . --skip-rule workstation_path` over PROJECT, ROADMAP, REQUIREMENTS, STATE, config.json, state.json, research/, codebase/, todos/, phase 15, phase 16 (every PLAN and SUMMARY of waves 1-3 included) and the 25 tracked phase 14 files outside `measurements/`.

Result: `prepublish_scan: clean (127 files, 0 blobs, 0 commits)`. Before the fixes it reported one finding (`secret .planning/phases/16-repo-split/16-RESEARCH.md:572`); the owner-email line of PITFALLS.md was fixed first.

Source fixes:

- `.planning/research/PITFALLS.md` line 127: `authored as sylvanoMTL <address>` became `authored as sylvanoMTL under the owner's commit email`.
- `.planning/phases/16-repo-split/16-RESEARCH.md` line 572 (the "What to do with today's hits" line that quotes the planted test_isolation constant): appended `<!-- scan: allow secret -->`.

### Marker exemptions

Output of the same scan with `--list-allowed` (`prepublish_scan: 2 allowed by marker`). The owner reviews this with plan 16-03's table and the rehearsal markers (16-12) before the first push (16-14 Task 2) and before the flip (16-16).

| Place | Rule | Why it is not a real hit |
| --- | --- | --- |
| `.planning/phases/16-repo-split/16-RESEARCH.md:328` | secret | The "Pre-Publish Scan Design" table row for the secret rule: it lists the rule's patterns and quotes the planted constant as prose; the marker phrase is part of that prose. |
| `.planning/phases/16-repo-split/16-RESEARCH.md:572` | secret | Quotes the planted test constant `_SECRET` of tests/test_isolation.py, a made-up 17-character string used to test environment isolation, not a credential. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_ulfixtures.py built a repo-root path to downloaded_examples**
- **Found during:** Task 1 (GREEN, first audit run)
- **Issue:** `test_zipfixtures_points_at_the_sample` asserted the sample was not under `REPO_ROOT / "downloaded_examples"`, which the audit rightly flags as a repository-data path.
- **Fix:** `assert "downloaded_examples" not in UL_ZIP.parts` (same intent, no repo-root path).
- **Files modified:** tests/test_ulfixtures.py
- **Committed in:** e28fb4d

**2. [Rule 1 - Bug] test_importer_layering.py skip reason said "not present yet"**
- **Found during:** Task 1 (GREEN, first audit run)
- **Issue:** the `requires_importer` skip carried a stale reason (`kicad_lib_manager/importer not present yet: plan 03-01 builds it ...`) that matches the corpus-type skip detector. The package folder always exists in the tool repo, so it is not a missing-corpus skip.
- **Fix:** reason reworded to say what is missing (`the kicad_lib_manager/importer package folder is missing from this checkout`); tests/README.md updated to the new text. No exception added to the audit.
- **Files modified:** tests/test_importer_layering.py, tests/README.md
- **Committed in:** e28fb4d, a5f6e33

**3. [Rule 3 - Blocking] Verify commands adapted to the worktree sandbox**
- **Issue:** the sandbox refuses `$(git ...)`, `export PATH=...` combined with git, and compound commands naming git. The plan's three verify commands were run as equivalent separate commands (same clone, same `--junitxml`, same budget check, `KICAD_TEST_CORPUS=` instead of the `git worktree list` lookup; the plan's phase 14 file list written out by hand).
- **Impact:** none on the measured results.

---

**Total deviations:** 3 (2 Rule 1 in-place conversions the audit exists to find, 1 Rule 3 command adaptation)
**Impact on plan:** no scope creep; both offenders were missed conversions or stale text, fixed without widening the audit.

## TDD Gate Compliance

- RED (`99ed234`): `test_audit_finds_planted_paths` and `test_audit_finds_planted_skips` failed on `assert [] == [2, 3, 4, 5]` style assertions against stub detectors that return `[]`; the three repository-wide audits passed against the stubs (nothing to find), as expected. `gsd_run check tdd-red-evidence` is unavailable in this worktree. Semantic assessment: the target tests executed and failed on the planned assertion because the detectors did not exist yet.
- GREEN (`e28fb4d`): all five tests pass (`5 passed`); the repository-wide audits then found the two offenders above, fixed in the same commit.
- REFACTOR: none.

## Known Stubs

None. (The RED-commit stub detectors were replaced in the GREEN commit.)

## Threat Flags

None. No new network, auth or file-access surface; the audit only reads tests/*.py.

## Issues Encountered

None beyond deviation 3. No other whole-suite runs were made besides the plan's three.

## Next Phase Readiness

- The skip budget and corpus run are proven; 16-12 (rehearsal) can scan an export that includes these files.
- The marker exemptions table above is ready for the owner's pre-push review.

## Self-Check: PASSED

- tests/test_corpus_audit.py, tests/README.md and this SUMMARY exist; commits `99ed234`, `e28fb4d`, `a5f6e33`, `b2e1e14` are ancestors of HEAD.
- Acceptance greps: planted-path/audit/marked defs 3, repo-root data paths in tests 0, `ul_CSD85301Q2.zip` real-download path 0, README KICAD_TEST_CORPUS 12, needs_kicad/HIDE_KICAD 8, "exactly six" 0, "is committed" 0, check_skip_budget.py 1, email in PITFALLS.md 0, `scan: allow secret` in 16-RESEARCH.md 2, allowed-by-marker lines 2.

---
*Phase: 16-repo-split*
*Completed: 2026-11-24*
