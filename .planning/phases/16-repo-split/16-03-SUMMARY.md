---
phase: 16-repo-split
plan: 03
subsystem: infra
tags: [prepublish-scan, ci, github-actions, junit, skip-budget, stdlib]

requires:
  - phase: 16-repo-split
    provides: "16-CONTEXT decisions D-09, D-10, D-19, D-20 and the 16-RESEARCH scan design"
provides:
  - "scripts/prepublish_scan.py: stdlib pre-publish scan (tree and history walk, rule and place output only)"
  - "scripts/check_skip_budget.py: junit skip ceiling and passed floor"
  - ".github/workflows/ci.yml: windows-latest job running scan, quick pytest, skip budget"
  - "tool code areas that scan clean with every rule"
affects: [16-06, 16-11, 16-12, 16-14, 16-16]

actuals:
  tokens: 60000
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "scripts loaded by path in tests (importlib spec_from_file_location), never as a package"
    - "planted violations assembled from pieces at run time so a test file scans clean"
    - "inline marker `scan: allow <rule>` for a single-line exemption, listed by --list-allowed"

key-files:
  created:
    - scripts/prepublish_scan.py
    - scripts/check_skip_budget.py
    - .github/workflows/ci.yml
    - tests/test_prepublish_scan.py
    - tests/test_skip_budget.py
    - tests/test_ci_workflow.py
  modified:
    - tests/test_isolation.py
    - tests/test_commit_step.py
    - tests/test_migration_dialog_run.py
    - tests/test_docs_atomic.py

key-decisions:
  - "Findings are de-duplicated by (rule, place), so a file seen in the tree and in a history blob prints once"
  - "A commit-message trailer line gives session_trailer only (not also session_url), so one trailer is one finding"
  - "The copy check (--corpus) reports copied_content at the file path (file-level rule), never at a line"
  - "Deny emails collected from another repository drop allow-listed addresses, so a noreply committer never blocks"

patterns-established:
  - "Pure rule functions (scan_blob, scan_message, scan_identity, scan_ref) plus a thin git walk"
  - "Usage errors print `<script>: <reason>` to stderr and exit 2; a verdict line is always the last stdout line"

requirements-completed: [SPLIT-03, SPLIT-04]

coverage:
  - id: D1
    description: "Pre-publish scan detects every D-09 class in planted samples, allows D-10 part numbers and Atomic_ names, prints rule and place only"
    requirement: SPLIT-03
    verification:
      - kind: unit
        ref: "tests/test_prepublish_scan.py (15 tests)"
        status: pass
      - kind: integration
        ref: "tests/test_prepublish_scan.py::test_exit_codes_and_output (slow, real git repositories)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Edge adjacency and empty cases: tests/fixtures/ is a whole path segment; --history on a repository with no commits exits 2"
    requirement: SPLIT-03
    verification:
      - kind: unit
        ref: "tests/test_prepublish_scan.py::test_fixtures_exemption_is_a_whole_segment"
        status: pass
      - kind: integration
        ref: "tests/test_prepublish_scan.py::test_exit_codes_and_output (empty git init repository)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Skip budget passes at exactly 10 skips and 3500 passed, fails one past either; zero tests fail; bad junit exits 2"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_skip_budget.py (7 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Windows CI workflow: push and pull_request, windows-latest, Python 3.14, read-only permissions, full history, scan before pytest then skip budget, no secrets"
    requirement: SPLIT-04
    verification:
      - kind: unit
        ref: "tests/test_ci_workflow.py (4 tests)"
        status: pass
    human_judgment: true
    rationale: "The workflow text is checked, but only a first run on GitHub proves the action tags (checkout v7, setup-python v7) exist; that is plan 16-14"
  - id: D5
    description: "Tool code areas scan clean with every rule; every marker exemption is listed for the owner"
    requirement: SPLIT-03
    verification:
      - kind: other
        ref: "python scripts/prepublish_scan.py --tree --deny-emails-from-repo . --path kicad_lib_manager ... (clean, 259 files)"
        status: pass
    human_judgment: true
    rationale: "The owner reviews the Marker exemptions table at the approval checkpoint (plan 16-14 Task 2)"

duration: 55min
completed: 2026-11-24
status: complete
plan_head_before: ed3a784ac0375414f438f462d178cf46254173e1
plan_head_after: c09b2ce
---

# Phase 16 Plan 03: Pre-publish scan, skip budget and Windows CI Summary

**Stdlib pre-publish scan covering the D-09 rule classes (rule and place output only, inline allow markers, owner identity read at run time), a junit skip-budget check (max 10 skips, at least 3500 passed) and a windows-latest CI workflow that runs scan, quick pytest and the budget, with the tool code areas scanning clean.**

## Performance

- **Duration:** about 55 min
- **Completed:** 2026-11-24
- **Tasks:** 3
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- `scripts/prepublish_scan.py` with pure rules (`scan_blob`, `scan_message`, `scan_identity`, `scan_ref`, `windows`, `build_rules`) and a git walk (`tree_files`, `history_blobs` through one `git cat-file --batch`, `history_commits`, `history_refs`); exit 0 clean, 1 on a finding, 2 on a usage error.
- `scripts/check_skip_budget.py` and `.github/workflows/ci.yml` (scan, then install, then bare pytest with `--junitxml`, then the budget).
- The code areas (`kicad_lib_manager/`, `kicad_lib_manager.py`, `tests/`, `scripts/`, `.github/`, `pyproject.toml`, both requirements files) scan clean: 259 files, no finding, with the owner's commit addresses read from this repository's history at run time.

## Rule list

| Rule | Detects |
|------|---------|
| workstation_path | drive-letter paths into Users or Git_Repo_Clones (both slash styles), git-bash `/c/` style, macOS and Linux homes other than the runner's, pytest-of-<user> folders |
| owner_email | any address from `--deny-emails-from-repo` or local git config `prepublish.denyEmailsFromRepo` (any case) |
| owner_term | any term from an untracked `--deny-terms-file` or `prepublish.denyTermsFile` |
| email | any other address outside the allow-list (example.invalid, example.com, example.org, users.noreply.github.com, noreply@anthropic.com, noreply@github.com, git@github.com) |
| vendor_file | vendor and part-data suffixes, or zip / STEP magic at offset 0, outside `tests/fixtures/` (whole segment) |
| copied_content | `--corpus`: three consecutive lines of at least 25 characters shared with a corpus file, or a blob byte-identical to one |
| secret | gitleaks-style token shapes plus a quoted 16+ character api_key, secret, token or password assignment |
| session_url | a claude.ai session URL in a file or message |
| session_trailer | a `Claude-Session:` line in a commit message |
| commit_identity | author or committer address outside the allow-list or in the deny list; a name holding a deny term |
| ref_name | refs named `worktree-agent-*` |
| large_blob | a blob over 20 MB (reported, not read) |

## Task Commits

1. **Task 1 RED: pre-publish scan tests** - `6a57509` (test)
2. **Task 1 GREEN: pre-publish scan** - `00506af` (feat)
3. **Task 2 RED: skip budget and CI workflow tests** - `b6c0d84` (test)
4. **Task 2 GREEN: skip budget script and CI workflow** - `5a9891c` (feat)
5. **Task 3: clear findings from the code areas** - `c09b2ce` (fix)

RED evidence: for each RED commit the target tests ran against a skeleton script (functions returning nothing, or a one-line workflow) and failed on their own assertions (13 of 15 fast tests and the slow git test for the scan; 10 of 11 for the budget and workflow, the 11th passing trivially). `gsd_run check tdd-red-evidence` is not available in the worktree; the assessment was made by reading the failures (assertion errors on the planned behavior, no import, collection or fixture faults).

## Source fixes in the code areas (Task 3)

| Place | Finding | Fix |
|-------|---------|-----|
| tests/test_migration_dialog_run.py:172 | workstation_path (two real folders passed to `CheckoutMismatch`) | rewritten to `D:/Work/Libs-importer` and `D:/Work/Libs`; no assertion names the strings |
| tests/test_isolation.py:310 | secret (`_SECRET` constant) | inline marker `# scan: allow secret` |
| tests/test_commit_step.py:1149 | workstation_path (synthetic Linux home for a quoting test) | inline marker `# scan: allow workstation_path` |
| tests/test_docs_atomic.py:62-63 | workstation_path (asserts the main-checkout path appears in CLAUDE.md) | inline markers; see Deviations |

Code-area scan result: `prepublish_scan: clean (259 files, 0 blobs, 0 commits)`. The submodule folders `Custom/` and `WurthElektronik/KiCad-Library` were empty in this worktree, so they were not part of the scan and the `--corpus` rule was exercised only by unit tests with planted corpus text.

## Marker exemptions

Run: `python scripts/prepublish_scan.py --tree --list-allowed --deny-emails-from-repo . --path kicad_lib_manager --path kicad_lib_manager.py --path tests --path scripts --path .github --path pyproject.toml --path requirements.txt --path requirements-dev.txt`

| Place | Rule | Why the line is not a real hit |
|-------|------|--------------------------------|
| tests/test_commit_step.py:1149 | workstation_path | A synthetic POSIX folder with an apostrophe (`o'neil`) that tests shell quoting of a git command; not a real person's folder |
| tests/test_docs_atomic.py:62 | workstation_path | Asserts that the current CLAUDE.md names the main-checkout path; the whole file is deleted by plan 16-07 (wave 2) together with that CLAUDE.md section |
| tests/test_docs_atomic.py:63 | workstation_path | Same as line 62 |
| tests/test_isolation.py:310 | secret | `_SECRET` is a planted test string written by a child test to prove the isolation guard; not a credential |

## Decisions Made

See `key-decisions` in the frontmatter. In addition: the email rule takes a bounded local part and bounded domain labels, a top-level label of letters only, and refuses a match whose local part follows a backslash, word character, dot, percent, plus or hyphen (so `\n@pytest.mark.x` and `pyside6@6.12.0` are not addresses).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tests/test_docs_atomic.py carries two workstation_path hits not named in the plan**
- **Found during:** Task 3 (code-area scan)
- **Issue:** lines 62-63 assert the owner's main-checkout path appears in CLAUDE.md; the code-area scan failed on them. The plan names three known findings and says to fix further ones by rewrite or one marker.
- **Fix:** an inline `# scan: allow workstation_path` on each line (a rewrite would break the assertion about CLAUDE.md). Plan 16-07 (wave 2, depends on 16-02) deletes the file, so the markers disappear with it; no wave-1 plan touches the file, so there is no merge conflict.
- **Files modified:** tests/test_docs_atomic.py
- **Verification:** the code-area scan is clean and `pytest tests/test_docs_atomic.py` passes
- **Committed in:** c09b2ce

**2. [Rule 2 - Missing critical] Dedupe, UTF-16 and oversized blob handling added to the scan**
- **Found during:** Task 1
- **Issue:** the plan's "exactly three lines" output needs a file seen in both the tree and a history blob to print once; a UTF-16 file (NUL bytes) would otherwise skip every text rule; reading an enormous blob into memory defeats the 20 MB cap.
- **Fix:** findings are de-duplicated by (rule, place); a blob with a UTF-16 byte order mark is decoded as UTF-16; an oversized blob is read only up to one byte past the cap.
- **Files modified:** scripts/prepublish_scan.py
- **Committed in:** 00506af

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical). **Impact:** no scope creep; the first is a marker the planner did not list, the second hardens the scan.

## Issues Encountered

- `gsd_run` and `gsd-tools` are not present in the worktree, so STATE.md, ROADMAP.md and requirements tracking were left to the orchestrator as instructed.
- The tool sandbox refused compound `cd ... && git ...` commands; commits were made from the worktree's own working directory.

## Known Stubs

None.

## Threat Flags

None. The new surface is a read-only scan script and a workflow that matches the plan's threat model (`permissions: contents: read`, official actions only by major tag, no `pull_request_target`, no secrets).

## Next Phase Readiness

- Plan 16-06 can wire the deselected-count output the skip budget relies on; plan 16-11 clears the kept `.planning` files; plan 16-12 re-runs the scan on the export, including `scripts/split/`, and with `--corpus` against the live collection.
- The `actions/checkout@v7` and `actions/setup-python@v7` tags come from the research and are confirmed by the first CI run (plan 16-14).

## Self-Check: PASSED

- Created files present: scripts/prepublish_scan.py, scripts/check_skip_budget.py, .github/workflows/ci.yml, tests/test_prepublish_scan.py, tests/test_skip_budget.py, tests/test_ci_workflow.py
- Commits present: 6a57509, 00506af, b6c0d84, 5a9891c, c09b2ce
- Targeted tests pass: test_prepublish_scan (15 fast and 1 slow), test_skip_budget, test_ci_workflow, test_markers, and the three edited test modules plus test_docs_atomic
