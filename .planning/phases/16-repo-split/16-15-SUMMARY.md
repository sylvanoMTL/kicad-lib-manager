---
phase: 16-repo-split
plan: 15
subsystem: repo-split-live-run
tags: [cutover, git, kicad, uri-diff, smoke-start, venv]

requires:
  - phase: 16-repo-split (16-13)
    provides: uri-before.json baseline, pre-split bundle and tag a156d29
  - phase: 16-repo-split (16-14)
    provides: tool repo published, prepublish.denyEmailsFromRepo = main checkout
provides:
  - the collection's remove-code commit 4f39aa9 on sylvanoMTL/kicad_libraries main (pushed)
  - live/uri-before-cutover.json, live/uri-after.json, live/cutover-dry-run.txt in the backup folder
  - proof that the tool checkout's env starts the app on the collection
affects: [16-16, 16-17, 16-18]

actuals:
  tokens: 6000
  tasks: 3
  commits: 0
plan_head_before: 967688b2f814b5061b117c8a535e53f53671b8fe
plan_head_after: 967688b2f814b5061b117c8a535e53f53671b8fe

tech-stack:
  added: []
  patterns: ["offscreen smoke start with every user folder and QSettings redirected to scratch"]

key-files:
  created: []
  modified: []

key-decisions:
  - "Owner chose cut-and-delete-venvs; both venvs were deleted only after the smoke start passed"

requirements-completed: [SPLIT-02, SPLIT-05]

coverage:
  - id: D1
    description: "The collection's main carries exactly .gitignore, .gitmodules, CLAUDE.md, README.md and the two gitlinks, with both gitlink SHAs, .gitmodules bytes and the remote unchanged"
    requirement: SPLIT-02
    verification:
      - kind: other
        ref: "git -C MAIN ls-tree -r HEAD (6 entries) and the cutover script's own post-check"
        status: pass
    human_judgment: false
  - id: D2
    description: "KiCad's resolved table URIs are identical before and after the remove-code commit, zero missing"
    requirement: SPLIT-02
    verification:
      - kind: other
        ref: "env/Scripts/python.exe scripts/split/uri_diff.py compare uri-before-cutover.json uri-after.json (and uri-before.json uri-after.json)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The collection main is pushed and carries its own README.md and CLAUDE.md (SPLIT-05)"
    requirement: SPLIT-05
    verification:
      - kind: other
        ref: "git -C MAIN ls-remote origin refs/heads/main equals HEAD 4f39aa9"
        status: pass
    human_judgment: false
  - id: D4
    description: "The tool checkout's env starts the app on the main checkout (offscreen, isolated user folders) and the scan lists the Custom libraries"
    verification:
      - kind: other
        ref: "scratchpad 16-15/smoke_start.py: 412 symbol libraries (10 Custom), 44 footprint libraries (1 Custom), exit 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "The owner starts the app the way they will from now on (tool checkout env, real settings) and opens KiCad's Symbol and Footprint library managers"
    verification: []
    human_judgment: true
    rationale: "Uses the owner's real settings and the running KiCad; the URI diff is the required proof, this is the owner's own confirmation (task 3 human-check, pending for the end-of-phase review)"

duration: 25min
completed: 2026-11-26
status: complete
---

# Phase 16 Plan 15: Cut the collection (live run, part 3) Summary

**The collection's main checkout lost its app code in one remove-code commit (4f39aa9, pushed to sylvanoMTL/kicad_libraries), KiCad's 428 resolved table URIs came out identical with 0 missing, the tool checkout's own env started the app on it, and the two old venvs are gone.**

## Performance

- **Tasks:** 3 (Task 1 and Task 2 in the earlier run, Task 3 here)
- **Files modified in the tool repo:** 0 (all changes landed in the collection, outside this repository); only this SUMMARY is committed here
- **Commits in the tool repo for this plan:** 0 production commits (the work is the collection commit below)

## Accomplishments

- Task 1 (earlier run): preflight and dry run. MAIN = `<repos-folder>/Kicad_Libraries` = `prepublish.denyEmailsFromRepo` = KiCad's `KICAD_LIB_GITHUB` (KiCad 10.0 config); main at `a156d29e6b6581bc5c935d0cb22099847c5951b7` (the pre-split tag), level with origin/main, no tracked changes. Drift compare of the 16-13 baseline against `uri-before-cutover.json`: `uri_diff: identical, 428 entries, 0 missing`. The dry run (`live/cutover-dry-run.txt`) listed 16 paths to remove (85 files in kicad_lib_manager, 176 in tests, 12 in scripts, 715 in .planning, plus app entry point, hooks, CI, requirements, reports, research notes, LICENSE, old README.md and CLAUDE.md), downloaded_examples (1 tracked file) to untrack, the three files to write (README.md, CLAUDE.md, .gitignore) and the two gitlinks `Custom bbd48c5f3648e10e769840e29c72c64926a7f433` and `WurthElektronik/KiCad-Library ddb5a9ea669b907f009f764b245e39d32ac15bd1`; `.gitmodules` kept; no "unexpected tracked path".
- Task 2: the owner chose **cut-and-delete-venvs** (through the orchestrator) and reported no shortcut, alias or scheduled task that starts the app from MAIN (assumption A10: none reported by the owner; not inspected). Re-checked right before the apply: no python process ran `kicad_lib_manager.py` from MAIN.
- Task 3 step 1: `cutover_collection.py --repo MAIN --apply` removed the code, untracked downloaded_examples, wrote README.md, CLAUDE.md and .gitignore from `scripts/split/collection/`, and committed on main: **`4f39aa9631b36d56e63b5232a64c7f6e886a3d45`** ("Remove the app code: the library manager now lives in sylvanoMTL/kicad-lib-manager"). Its own post-check passed: "tree, both gitlink SHAs, .gitmodules bytes and remote URL are unchanged". Its leftover cache-only folder `kicad_lib_manager` was removed by the script (the two other "leftover kept" lines name README.md and CLAUDE.md, which are files, not folders).
- Gitlink / .gitmodules / remote checks after the commit: `git ls-tree -r HEAD` is exactly `100644 .gitignore`, `100644 .gitmodules`, `100644 CLAUDE.md`, `100644 README.md`, `160000 Custom` (bbd48c5f...), `160000 WurthElektronik/KiCad-Library` (ddb5a9ea...); `.gitmodules` bytes unchanged; remote still `https://github.com/sylvanoMTL/kicad_libraries.git`. `downloaded_examples/` is still on disk and `git ls-files downloaded_examples` prints nothing; `git status --porcelain --untracked-files=no` is empty.
- Step 2, the three compare lines (snapshot `live/uri-after.json`, KiCad config `<home>/AppData/Roaming/kicad/10.0`):
  - snapshot: `uri_diff: 428 entries, 0 missing`
  - `compare uri-before-cutover.json uri-after.json`: `uri_diff: identical, 428 entries, 0 missing`
  - `compare uri-before.json uri-after.json` (16-13 baseline): `uri_diff: identical, 428 entries, 0 missing`
  - The six disabled-and-missing Wurth symbol libraries (Inductor_Wurth_WE-SUKW, MagIC_Wurth_MagIC-FDSM, -FIMM, -LDHM, -VDRM, -VISM) appear as notes on both sides; the owner accepted them in 16-13.
- Step 3, push: `git -C MAIN push origin main` printed `a156d29..4f39aa9  main -> main`; `git ls-remote origin refs/heads/main` returns `4f39aa9631b36d56e63b5232a64c7f6e886a3d45`, equal to HEAD.
- Step 4, smoke start from the tool env (`<repos-folder>/kicad-lib-manager/env/Scripts/python.exe -I`, driver and its user folders under the session scratchpad `16-15/`, offscreen, APPDATA, LOCALAPPDATA, USERPROFILE, HOME, KICAD_CONFIG_HOME and QSettings redirected, file and message dialogs stubbed so nothing can block; the worktree root, same code as the tool checkout HEAD 967688b, on sys.path): `start_window(["kicad_lib_manager.py", "--library-root", MAIN], ...)` returned a window; scan result: **412 symbol libraries (10 Custom), 44 footprint libraries (1 Custom)**, sources Custom and WurthElektronik; exit 0.
- Step 5, venvs: `MAIN/env` and `MAIN/env-py311` both held a `pyvenv.cfg`; both deleted after the smoke start passed; `test -e` fails for both.
- Step 6: the only leftover cache-only folder (`kicad_lib_manager`) was already removed by the cutover script; nothing remained.
- Claude-Session check of the tool repo log (`git log --format=%B -30`): 0 matches. The collection's commit message holds no session line.

## Task Commits

1. **Task 1: Preflight, drift check, dry run** - none (read-only; records in the backup folder)
2. **Task 2: Owner decision** - none (answered "cut-and-delete-venvs")
3. **Task 3: Remove-code commit, URI proof, push, smoke start, venvs** - `4f39aa9` in the collection repository (sylvanoMTL/kicad_libraries), not in this repository

**Plan metadata:** the commit of this SUMMARY in the tool repo worktree.

## Files Created/Modified

- Tool repo: only `.planning/phases/16-repo-split/16-15-SUMMARY.md`.
- Outside the repository: `<repos-folder>/kicad-split-backup/live/uri-before-cutover.json`, `uri-after.json`, `cutover-dry-run.txt`.
- Collection (main checkout): the remove-code commit 4f39aa9; `env/` and `env-py311/` deleted from disk.

## Decisions Made

- Followed the owner's choice `cut-and-delete-venvs`: the venvs were deleted only after the smoke start passed (D-08).
- The smoke start stubs `QFileDialog.getExistingDirectory` and `QMessageBox.exec` in the driver so an undetected KiCad cannot block an unattended run; the app code is not changed.

## Deviations from Plan

None - plan executed exactly as written. (Execution detail only: the sandbox refused piped or compound commands naming git, so each command was run plainly and separately, and the apply output was not tee'd to a file; it is quoted above instead.)

## Issues Encountered

- None blocking. Extra finding, not for this plan and left untouched: MAIN still registers 7 leftover agent worktrees under `<repos-folder>/Kicad_Libraries/.claude/worktrees/agent-*` (branches `worktree-agent-a0072898c66b956ae`, `-a012859fd0a57169e`, `-a779443efc8fdc197`, `-a9df7190cd595954e`, `-a9e267aa4f1fb9047`, `-ae7f8e785d3f43ff3`, `-aef09a733de6aba33`) plus the importer worktree `<repos-folder>/Kicad_Libraries-importer` (feature/part-importer, d1faa59). These are for plan 16-16.

## Pending human check (end-of-phase review)

Task 3 human-check, not yet done by the owner: start the Library Manager the way it will be started from now on (from the tool checkout, `.\env\Scripts\python.exe kicad_lib_manager.py`), then open KiCad's Symbol and Footprint library managers. Expected: the Library folder row shows the main checkout with the tag "KiCad's folder" or "your choice", the scan lists the Custom and WurthElektronik libraries, and KiCad lists the same libraries as before the split with none marked missing. The URI diff above is the required proof (D-22); this is the owner's own confirmation.

## Self-Check: PASSED

- uri_diff: identical (both compares), 428 entries, 0 missing
- Collection tree is exactly the six expected entries; ls-remote equals HEAD 4f39aa9
- Smoke start printed 10 Custom symbol libraries, exit 0
- `env` and `env-py311` absent from the main checkout; `downloaded_examples` present and untracked
- Claude-Session matches in the tool repo log: 0
