---
phase: 16-repo-split
plan: 04
subsystem: infra
tags: [repo-split, allow-list, git-archive, scrub, git-hooks, stdlib]

requires:
  - phase: 16-repo-split
    provides: "16-03 pre-publish scan (scripts/prepublish_scan.py) that the pre-push hook runs and that every file here scans clean with"
provides:
  - "scripts/split/allowlist.txt: the tool-repo allow-list (include prefixes and ! exclusions)"
  - "scripts/split/scrub.py: workstation-path scrub (parse_map, scrub_text, scrub_bytes, scrub_tree)"
  - "scripts/split/verify_export.py: export checker (AllowList, load_allow_list, matches, hard_denied, HARD_DENY, REQUIRED, verify)"
  - "scripts/split/build_tool_repo.py: allow-listed git-archive export, scrub, verify, one first commit on main"
  - "scripts/split/sync_planning.py: post-split .planning/ delta carried from the private repo to the tool checkout"
  - ".githooks/commit-msg and .githooks/pre-push (mode 100755)"
affects: [16-06, 16-12, 16-14, 16-15]

actuals:
  tokens: 14300
  tasks: 3
  commits: 6
plan_head_before: a4e775fa7560fd36d59ecabea5a1f49b197fe634
plan_head_after: 3bd805823f2f8faf58a8089c31d2308e3ec12e0e

tech-stack:
  added: []
  patterns:
    - "sibling scripts in scripts/split import each other by module name (sys.path[0] is the script folder); tests prepend scripts/split with monkeypatch.syspath_prepend"
    - "export from a git ref through git archive and a streaming tarfile reader, never from the working tree"
    - "planted workstation paths and session URLs assembled from pieces so the test files scan clean"

key-files:
  created:
    - scripts/split/allowlist.txt
    - scripts/split/scrub.py
    - scripts/split/verify_export.py
    - scripts/split/build_tool_repo.py
    - scripts/split/sync_planning.py
    - tests/test_split_export.py
    - tests/test_githooks.py
    - .githooks/commit-msg
    - .githooks/pre-push
  modified:
    - .gitattributes

key-decisions:
  - "The hard-deny list is part of AllowList.allowed(), so an exported path under Custom/, WurthElektronik/, downloaded_examples/, reports/, research_notes/, .planning/milestones|quick|debug/, .gitmodules, MILESTONES.md or RETROSPECTIVE.md is refused even if a future allow-list line named it"
  - "build() also drops session lines from a given message (clean_message) as well as relying on the commit-msg hook, because a hook is not enforced where the exec bit is lost"
  - "build() stops with exit 1 and removes what it wrote when verify_export reports a problem, and with exit 2 for a refusal (non-empty destination, unknown ref, allowed gitlink, unsafe archive member)"
  - "pre-push picks the first interpreter that actually runs (env/Scripts/python.exe, env/bin/python, python3, python) because a Windows Store python alias exists on PATH but does not run"

patterns-established:
  - "Allow-list semantics: a trailing / is a whole-segment folder prefix, any other line is one file, ! excludes, exclusion wins"
  - "Scrub: --map folders in forward-slash, backslash and git-bash spellings, case-insensitive, longest first, empty NEW makes the path repo-relative"

requirements-completed: [SPLIT-01, SPLIT-03]

coverage:
  - id: D1
    description: "Allow-list decides every path the split cares about, with whole-segment prefixes and hard-deny paths absent by construction"
    requirement: SPLIT-01
    verification:
      - kind: unit
        ref: "tests/test_split_export.py::test_allow_list_decisions, test_include_prefix_is_a_whole_path_segment, test_allow_list_has_no_collection_content_line"
        status: pass
    human_judgment: false
  - id: D2
    description: "verify_export flags an outside path, .gitmodules, Custom/WurthElektronik/downloaded_examples content, a missing required entry and an empty export; exit codes 0/1/2"
    requirement: SPLIT-01
    verification:
      - kind: unit
        ref: "tests/test_split_export.py::test_verify_export_* (11 cases)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Scrub maps folders in three spellings case-insensitively, applies the home, repos-folder and pytest-of rules, is idempotent and leaves CRLF text, binaries and non-UTF-8 files byte-identical"
    requirement: SPLIT-03
    verification:
      - kind: unit
        ref: "tests/test_split_export.py::test_scrub_maps_and_generic_rules, test_scrub_is_idempotent_and_byte_safe, test_scrub_without_a_map_still_applies_the_generic_rules"
        status: pass
    human_judgment: false
  - id: D4
    description: "build_tool_repo exports only allow-listed tracked files of a ref (an untracked file in the working tree and gitlinks are never swept in), scrubs planning text, makes one commit on main with the given identity, core.hooksPath .githooks and the Co-Authored-By trailer without a session line"
    requirement: SPLIT-01
    verification:
      - kind: integration
        ref: "tests/test_split_export.py::test_build_exports_only_the_allow_list (slow, real git)"
        status: pass
      - kind: unit
        ref: "tests/test_split_export.py::test_build_refuses_a_non_empty_dest, test_build_drops_a_session_line_from_a_given_message, test_a_failed_build_is_cleaned_up_even_with_read_only_git_objects"
        status: pass
    human_judgment: false
  - id: D5
    description: "sync_planning carries the scrubbed A/M planning files and removes the D files between a tag and a ref, skipping unlisted paths and touching nothing outside .planning/"
    requirement: SPLIT-03
    verification:
      - kind: integration
        ref: "tests/test_split_export.py::test_sync_planning_copies_the_delta (slow, real git)"
        status: pass
      - kind: unit
        ref: "tests/test_split_export.py::test_sync_planning_refuses_an_unknown_ref"
        status: pass
    human_judgment: false
  - id: D6
    description: "The commit-msg hook strips Claude-Session and session URL lines and keeps Co-Authored-By; the pre-push hook runs the scan with --tree --history and blocks on a non-zero status"
    requirement: SPLIT-03
    verification:
      - kind: integration
        ref: "tests/test_githooks.py (3 slow tests, real git and sh)"
        status: pass
    human_judgment: false

duration: 75min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 04: Tool-repo export scripts and git hooks Summary

**Allow-listed `git archive` export of a ref into a one-commit tool repository (scrubbed `.planning/`, verified against a hard-deny list and required entries), a planning-delta sync, and tracked commit-msg and pre-push hooks that drop the session line and run the pre-publish scan before every push.**

## Performance

- **Duration:** about 75 min
- **Tasks:** 3 (all TDD: RED commit, then GREEN commit each)
- **Files created:** 9, modified: 1 (`.gitattributes`)

## Accomplishments

- `scripts/split/allowlist.txt` names the application, tests, scripts, hooks, CI, project files and the D-05 planning set; Custom, WurthElektronik, downloaded_examples, reports, research_notes, `.gitmodules`, `milestones/`, `quick/`, `debug/`, `MILESTONES.md` and `RETROSPECTIVE.md` are absent by construction, and `!.planning/phases/14-test-suite-speed-up/measurements/` drops the timing logs.
- `build_tool_repo.py` exports only from a git ref (an untracked `kicad_lib_manager/untracked.py` in the working tree never appears), refuses an allowed gitlink, an unsafe or linked archive member and a non-empty destination, scrubs, verifies, then makes the single first commit. It never pushes and never calls GitHub.
- `sync_planning.py` and the hooks complete the loop: later `.planning/` changes reach the tool checkout scrubbed, and a commit there cannot keep a session line or leave without the scan.
- Trial run (informational, scratch folder only): building this worktree's HEAD with the real allow-list gave 397 files (`.planning` 119, `tests` 172, `kicad_lib_manager` 85, `scripts` 12, one commit) and failed only on the missing `LICENSE`, which a later plan adds.

## CLI of each script

| Script | Usage |
|--------|-------|
| `scrub.py` | `python scripts/split/scrub.py --root DIR [--prefix PREFIX ...] [--map OLD=NEW ...]` (default prefix `.planning`; prints changed files; exit 0, 2) |
| `verify_export.py` | `python scripts/split/verify_export.py DIR --allow-list FILE` (prints problems then `verify_export: ok (<n> files)` or `<k> problem(s)`; exit 0, 1, 2) |
| `build_tool_repo.py` | `python scripts/split/build_tool_repo.py --source DIR --ref REF --dest DIR --allow-list FILE [--map OLD=NEW ...] --name NAME --email EMAIL [--message TEXT]` (exit 0, 1 verification failed, 2 refusal) |
| `sync_planning.py` | `python scripts/split/sync_planning.py --source DIR --ref REF --since TAG --dest DIR --allow-list FILE [--map OLD=NEW ...]` (prints `A/M/D/skip <path>` in path order; exit 0, 2) |

Enable the hooks in the tool checkout with `git config core.hooksPath .githooks`; this worktree does not enable them.

## Final allow-list (include lines; `!` excludes)

`kicad_lib_manager/`, `kicad_lib_manager.py`, `tests/`, `scripts/`, `.githooks/`, `.github/`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `.gitattributes`, `LICENSE`, `README.md`, `CLAUDE.md`, `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json`, `.planning/state.json`, `.planning/research/`, `.planning/codebase/`, `.planning/todos/`, `.planning/phases/14-test-suite-speed-up/`, `.planning/phases/15-choose-library-folder-and-new-collection/`, `.planning/phases/16-repo-split/`, and `!.planning/phases/14-test-suite-speed-up/measurements/`.

## Task Commits

1. **Task 1: allow-list, scrub, export checker** - `32c4cd8` (test, RED), `fdf419b` (feat, GREEN)
2. **Task 2: tool-repo builder and planning sync** - `24895f3` (test, RED), `fc68d2a` (feat, GREEN)
3. **Task 3: tracked git hooks** - `74c6ed5` (test, RED), `3bd8058` (feat, GREEN)

**Plan metadata:** the SUMMARY commit that follows this file.

## TDD Gate Compliance

RED, GREEN order is present for all three tasks (`test(16-04)` before `feat(16-04)`, no refactor commits). RED evidence: `gsd_run check tdd-red-evidence` is not available in the worktree, so no machine record exists. To keep RED meaningful, each RED commit carried neutral skeleton modules or hooks (functions returning an empty or unchanged value, hooks that exit 0), so every failing test failed on its planned assertion, not on an import or load error: Task 1 18 failed of 19, Task 2 4 failed on the slow tests plus the non-empty destination test, Task 3 2 failed of 3 (the third, "ordinary messages stay unchanged", passes against a no-op hook by design). Semantic assessment: each failure was the assertion about the planned behavior (empty `allowed`, unchanged scrub text, no files exported, session line kept, push not blocked).

## Files Created/Modified

- `scripts/split/allowlist.txt` - the allow-list
- `scripts/split/scrub.py` - workstation-path scrub
- `scripts/split/verify_export.py` - export checker, hard-deny and required lists
- `scripts/split/build_tool_repo.py` - builder and first commit
- `scripts/split/sync_planning.py` - planning delta sync
- `tests/test_split_export.py` - 25 tests (23 quick, 2 slow git tests)
- `tests/test_githooks.py` - 3 slow tests
- `.githooks/commit-msg`, `.githooks/pre-push` - hooks, mode 100755
- `.gitattributes` - added `.githooks/* text eol=lf`

## Decisions Made

See `key-decisions` in the frontmatter. In short: hard-deny inside `allowed()`, session lines dropped in `build()` as well as by the hook, exit 1 versus 2 for verification versus refusal, and a "first interpreter that actually runs" lookup in pre-push.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Keep the hooks on LF endings**
- **Found during:** Task 3
- **Issue:** a Windows clone with `core.autocrlf true` would check the hooks out with CRLF, and `sh` then fails on the carriage returns, so the session-line strip and the scan gate would silently not run.
- **Fix:** added `.githooks/* text eol=lf` to `.gitattributes` (a file outside the plan's `files_modified`; one line, and `.gitattributes` is on the allow-list so the tool repo carries it).
- **Files modified:** `.gitattributes`
- **Committed in:** `3bd8058`

**2. [Rule 1 - Bug] Scrub placeholder text matched its own rule in the scrub and test files**
- **Found during:** Task 1 scan check
- **Issue:** the literal placeholder `pytest-of-<user> in `scrub.py` and `tests/test_split_export.py` is a `workstation_path` finding of the 16-03 scan.
- **Fix:** the docstring was reworded and the test assembles the placeholder from pieces; the scrub still writes `pytest-of-<user> as the plan specifies.
- **Files modified:** `scripts/split/scrub.py`, `tests/test_split_export.py`
- **Committed in:** `fdf419b`

**3. [Rule 2 - Missing critical] Read-only git objects broke cleanup of a failed build on Windows**
- **Found during:** Task 2 trial run
- **Issue:** after `git init` the object files are read-only on Windows, so `shutil.rmtree(..., ignore_errors=True)` would leave a half-built destination behind after a late failure.
- **Fix:** `_clear` removes with an error handler that makes the file writable and retries; covered by `test_a_failed_build_is_cleaned_up_even_with_read_only_git_objects`.
- **Files modified:** `scripts/split/build_tool_repo.py`, `tests/test_split_export.py`
- **Committed in:** `fc68d2a`

**4. [Rule 2 - Missing critical] Scrub also neutralises a document's placeholder home name**
- **Found during:** Task 2 trial run against the real planning set
- **Issue:** planning text that describes the pattern (a drive-letter users path followed by an owner placeholder in angle brackets) is still a scan finding after the scrub, because the user-name part excluded angle brackets.
- **Fix:** the user-name part now also accepts one bracketed placeholder; a prompt that ends in `>` still keeps its `>` (tested).
- **Files modified:** `scripts/split/scrub.py`, `tests/test_split_export.py`
- **Committed in:** `fc68d2a`

---

**Total deviations:** 4 auto-fixed (1 bug, 3 missing-critical). **Impact on plan:** no scope creep; items 1, 3 and 4 close gaps that would have broken the live run on a Windows clone.

## Issues Encountered

- **The scan flags the scrub's own placeholder (needs a decision in 16-12).** `scripts/prepublish_scan.py` treats `pytest-of-<user> as a `workstation_path` hit (the rule is `pytest-of-<user>\b)[^\s\\/]+` and `<user>` matches). The plan fixes `pytest-of-<user> as the scrub's output, and the existing planning text already holds such placeholders (phase 14 files, `16-03-PLAN.md`, `16-03-SUMMARY.md`, `16-04-PLAN.md`, `16-RESEARCH.md`), so a rehearsal export is never clean until either the scan accepts a bracketed name (for example `pytest-of-<user>\b|<)`) or those lines get an inline `scan: allow` marker. I did not change 16-03's scan (outside this plan's files, and the plan says a finding is never fixed by changing the scan). Trial export of this worktree's HEAD, scanned with `--tree`: 20 findings: 18 `workstation_path` (mostly these placeholders plus the two lines of `CLAUDE.md`, which a later plan rewrites), 1 `secret` (`16-RESEARCH.md:572`, the `_SECRET` string the research says to mark) and 1 `email` (`.planning/research/PITFALLS.md:127`, hand rewrite per the research).
- The full Git for Windows `sh` is found by the hook test through `shutil.which("sh")` or the git exec path; the test skips with a stated reason when no POSIX shell exists.
- The Custom and WurthElektronik submodules are not checked out in this worktree; none of the plan's tests need them.

## Known Stubs

None.

## Threat Flags

None. The scripts only read a git ref and write a new local repository; nothing here opens a network connection, pushes, or calls GitHub (`grep` for a quoted `push` or `gh` argv element in `scripts/split/build_tool_repo.py` and `scripts/split/sync_planning.py` returns nothing).

## Next Phase Readiness

- 16-12 (rehearsal) and 16-14 (live run) can call `build_tool_repo.py` and `sync_planning.py` as documented above. Before the rehearsal can exit 0 the scan question under Issues Encountered must be settled, and `LICENSE` must exist in the source ref (the export checker requires it).
- Plan-level verification: `python scripts/prepublish_scan.py --tree --path scripts/split --path .githooks --path tests/test_split_export.py --path tests/test_githooks.py` prints `prepublish_scan: clean (14 files, 0 blobs, 0 commits)`; `tests/test_split_export.py` quick run 23 passed, slow run 2 passed; `tests/test_githooks.py` 3 passed; the neighbouring `test_prepublish_scan`, `test_ci_workflow`, `test_skip_budget`, `test_cutover_collection`, `test_uri_diff` modules still pass (49 passed).

## Self-Check: PASSED

All nine created files and the modified `.gitattributes` exist on disk; the six task commits `32c4cd8`, `fdf419b`, `24895f3`, `fc68d2a`, `74c6ed5` and `3bd8058` are ancestors of HEAD; `.githooks/commit-msg` and `.githooks/pre-push` are stored with mode 100755; every acceptance grep of the plan returns its expected value (allow-list 5 and 0, three scrub defs, one `def build`, one `def sync`, no quoted push or gh, `archive` present, hook greps 1, `sed -i` 0).

---
*Phase: 16-repo-split*
*Completed: 2026-11-24*
