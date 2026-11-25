---
phase: 16-repo-split
plan: 07
subsystem: docs
tags: [license, readme, claude-md, doc-tests, dev-workflow]

requires:
  - phase: 16-repo-split
    provides: "16-02 removed the code-folder library source, so the folder order is four sources then the first-run window"
provides:
  - "LICENSE: MIT, copyright 2026 sylvanoMTL, code only"
  - "README.md: tool README (Install, First run, Choosing or creating a collection, Development, Libraries and licences, Licence)"
  - "CLAUDE.md: tool developer guide with Dev Workflow and a rewritten Git Workflow, no workstation path"
  - "tests/test_docs_split.py: 14 doc checks replacing tests/test_docs_atomic.py"
affects: [16-05, 16-11, 16-12, 16-14]

actuals:
  tokens: 14000
  tasks: 2
  commits: 4
plan_head_before: a4e775fa7560fd36d59ecabea5a1f49b197fe634
plan_head_after: 5a17870

tech-stack:
  added: []
  patterns:
    - "doc tests find headings as whole lines and fail with an assertion naming the heading"
    - "workstation-path patterns in tests are assembled from pieces so the file passes the pre-publish scan without markers"

key-files:
  created:
    - LICENSE
    - tests/test_docs_split.py
  modified:
    - README.md
    - CLAUDE.md
  deleted:
    - tests/test_docs_atomic.py

key-decisions:
  - "Doc headings are matched as whole lines (regex), not substrings, so '## Install' cannot match '## Installing'"
  - "CLAUDE.md keeps a short '## Importing Parts' paragraph (the app's Import Part action); the manual route lives in the collection CLAUDE.md"
  - "CLAUDE.local.md is described as untracked and never committed; .gitignore was not changed (not in this plan's file list)"

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-08]

coverage:
  - id: D1
    description: "MIT LICENSE for the handle, code only"
    requirement: SPLIT-06
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_license_is_mit_for_the_handle"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tool README with install, first run, collection choice, development, libraries and licences"
    requirement: SPLIT-06
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_readme_covers_install_and_first_run"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_readme_libraries_note"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_readme_folder_order"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_readme_dev_workflow"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tool CLAUDE.md with Dev Workflow, Git Workflow and no moved sections or workstation paths"
    requirement: SPLIT-05
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_claude_md_sections"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_claude_md_dev_workflow"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_claude_md_git_workflow"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_docs_hold_no_workstation_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "Doc tests no longer depend on planning prose or moved headings; test_docs_atomic.py deleted"
    requirement: SPLIT-05
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_missing_heading_fails_with_its_name"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 07: Tool docs and licence Summary

**MIT LICENSE, an install-to-first-run README, a tool CLAUDE.md with the dev workflow and the no-session-line commit rules, and a 14-test doc check module that replaces test_docs_atomic.py**

## Performance

- **Duration:** about 20 min
- **Completed:** 2026-11-24
- **Tasks:** 2 (both TDD: RED test commit, then GREEN content commit)
- **Files modified:** 5 (LICENSE, README.md, CLAUDE.md, tests/test_docs_split.py created or rewritten; tests/test_docs_atomic.py deleted)

## Accomplishments

- LICENSE is the standard MIT text with `Copyright (c) 2026 sylvanoMTL`.
- README.md is the tool README: install on CPython 3.14, the Set Up Your Library Folder window and its four buttons, the two KiCad path variables and the `Change KiCad path variables?` offer, the four-source folder order, development commands, the D-16b libraries note and the MIT licence section.
- CLAUDE.md is the tool developer guide (D-21) with a new Dev Workflow and a rewritten Git Workflow; the folder-order bullet drops the folder the app runs from.
- tests/test_docs_split.py replaces tests/test_docs_atomic.py; a missing heading fails with its name.

## Sections moved out of CLAUDE.md

| Section (old CLAUDE.md) | Now lives in |
|-------------------------|--------------|
| `## KiCad Path Variables` (including the owner's workstation bullet) | `scripts/split/collection/CLAUDE.md` (generic form); the owner's concrete folders go to the untracked `CLAUDE.local.md` of the tool checkout (plan 16-14) |
| `## Library Naming Convention` (atomic rule) | `scripts/split/collection/CLAUDE.md`; a one-paragraph "Library conventions the app enforces" stays in Project Overview |
| `## Importing Parts` manual route | `scripts/split/collection/CLAUDE.md`; CLAUDE.md keeps only the Import Part paragraph |
| `## Adding a New Library Submodule` | `scripts/split/collection/CLAUDE.md` |
| Git Workflow (submodule commit order, generated tables) | `scripts/split/collection/CLAUDE.md`; CLAUDE.md has the tool-repo git rules instead |
| README: structure, clone with submodules, Generate Tables, Configure KiCad, adding and updating submodules | `scripts/split/collection/README.md` |
| `test_claude_md_describes_atomic_scheme` | the collection template test of plan 16-05 |
| `test_library_naming_has_update_note`, `test_project_md_marks_migration_delivered` | deleted (planning prose, Bucket C) |

## Task Commits

1. **Task 1: MIT LICENSE and the tool README** - `d41331a` (test, RED), `d339d37` (feat, GREEN)
2. **Task 2: tool CLAUDE.md and doc tests** - `f2c2b69` (test, RED), `5a17870` (feat, GREEN)

## Files Created/Modified

- `LICENSE` - MIT licence for the code
- `README.md` - tool README
- `CLAUDE.md` - tool developer guide
- `tests/test_docs_split.py` - doc checks for LICENSE, README.md and CLAUDE.md
- `tests/test_docs_atomic.py` - deleted

## Decisions Made

- Headings are matched as whole lines so a prefix heading cannot satisfy a check.
- `## Importing Parts` stays in CLAUDE.md as a short paragraph and is checked by the sections test.
- The CLAUDE.md Git Workflow says `CLAUDE.local.md` stays untracked; `.gitignore` was not touched because it is outside this plan's file list. Plan 16-14 can add the ignore line when it writes that file.

## Deviations from Plan

None - plan executed exactly as written. Two small additions inside the plan's intent: `test_readme_folder_order` (checks the README states the four-source order and not the folder the app runs from, the SPLIT-08 ordering edge) and the Importing Parts heading in the sections test.

## Issues Encountered

- The `.githooks/` folder does not exist in this worktree yet, so the docs name hooks (`core.hooksPath .githooks`, the commit-msg hook that strips the session line, the pre-push scan) that a later plan of this phase creates. Not a regression of this plan.
- The submodules `Custom/` and `WurthElektronik/KiCad-Library` are not checked out in this worktree; none of the plan's tests needed them.

## Verification

- `python -m pytest tests/test_docs_split.py -n 0 -q -p no:cacheprovider`: 14 passed
- `python -m pytest tests/test_help_dialog.py tests/test_main_window.py -n 0 -q -p no:cacheprovider`: 157 passed
- `tests/test_docs_atomic.py` absent; no reference to it remains outside `.planning/`
- `python scripts/prepublish_scan.py --tree --path CLAUDE.md --path README.md --path LICENSE --path tests/test_docs_split.py`: clean, without any allow marker
- Acceptance greps: copyright line 1, README headings 4, "ships no libraries" 2, moved headings in CLAUDE.md 0, Dev Workflow 1, folder-the-app-runs-from 0, workstation paths 0

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

The tool docs are ready for the allow-listed copy (16-12) and for the owner's `CLAUDE.local.md` (16-14). Plan 16-11 rewrites tests/README.md, which CLAUDE.md and README.md point to.

## Self-Check: PASSED

- LICENSE, README.md, CLAUDE.md, tests/test_docs_split.py present; tests/test_docs_atomic.py absent
- Commits d41331a, d339d37, f2c2b69, 5a17870 are ancestors of HEAD

---
*Phase: 16-repo-split*
*Completed: 2026-11-24*
