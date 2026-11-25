---
phase: 16-repo-split
plan: 13
subsystem: infra
tags: [repo-split, live-run, visibility, bundle, merge, pre-split]

requires:
  - phase: 16-repo-split
    provides: "16-12 rehearsal record, uri_diff.py snapshot, split16.env variables"
provides:
  - "verified git bundles of kicad_libraries and kicad_custom_library in <repos-folder>/kicad-split-backup/"
  - "kicad_libraries and kicad_custom_library PRIVATE on GitHub (SPLIT-07 half, D-11)"
  - "main of the main checkout fast-forwarded to feature/part-importer (a156d29), pushed, with tags v2.0 (already on origin) and pre-split pushed"
  - "live URI baseline live/uri-before.json (D-22): 428 entries, 0 missing"
affects: [16-14, 16-15, 16-16]

actuals:
  tokens: 0
  tasks: 3
  commits: 0
plan_head_before: a156d29e6b6581bc5c935d0cb22099847c5951b7
plan_head_after: a156d29e6b6581bc5c935d0cb22099847c5951b7

tech-stack:
  added: []
  patterns:
    - "every live git command names the main checkout with git -C <main-checkout> (D-26); the plan changed no file of the importer worktree"

key-files:
  created:
    - .planning/phases/16-repo-split/16-13-SUMMARY.md
  modified: []

key-decisions:
  - "Owner chose go (not go-record-custom): no gitlink mismatch, so step 3 was skipped"
  - "v2.0 already existed on origin at the same SHA as the local tag: the push was a no-op, not a force"
  - "worktree-agent-a5e8655b32e875242 deleted with the safe git branch -d (it was merged into main); the other 7 are checked out in live worktrees and were left alone"

requirements-completed: [SPLIT-07]

status: complete
---

# Phase 16 Plan 13: Live run part 1 Summary

Both existing GitHub repos are now private, the main checkout KiCad reads has `main` fast-forwarded to the importer branch (`a156d29`) and pushed, and `pre-split` marks that commit on origin, with two verified bundles as the way back. `commits: 0` counts code commits: the plan has no file changes of its own (`files_modified: []`); this SUMMARY is the only commit and is made after the count.

## Preflight report (Task 1, read-only; before the owner decision)

| Check | Value |
|-------|-------|
| KICAD_LIB_GITHUB vs `$MAIN` | same folder (`<main-checkout>`), D-26 satisfied |
| Main checkout branch / tracked changes | `main` at `05f9fffa1ef50c5bf227302d235005fd0d7f183c`, no tracked changes, 0/0 against origin/main |
| Submodule status | Custom `bbd48c5` (pre-atomic-1-gbbd48c5), WurthElektronik/KiCad-Library `ddb5a9e` (heads/master); no `+`/`-` mismatch |
| Fast-forward possible | yes, `main` is an ancestor of `feature/part-importer`; diff under Custom/, WurthElektronik/, .gitmodules empty |
| Branches / tags | 8 local `worktree-agent-*` branches; tags v1.0, v2.0 local; `v2.0` already on origin at `5d320c968f85b1a7019541ff401adf63ba7e461f` |
| gh | logged in as sylvanoMTL with repo scope; kicad_libraries and kicad_custom_library PUBLIC; kicad-lib-manager free (D-03) |
| Running app from the main checkout | none; owner also confirmed the app is closed |
| Live URI baseline | `uri_diff: 428 entries, 0 missing`; six disabled stale Wurth entries listed as notes, accepted by the owner |
| `downloaded_examples` | five entries exist only in the importer worktree, two ignored zips only in main (see notes for 16-16) |

## Task 2: owner decision

Owner answered **go** and confirmed the Library Manager app is closed.

## Task 3: live steps and results

| Step | Result |
|------|--------|
| 1 Bundles | `kicad_libraries-pre-split.bundle` 9,755,951 bytes, `kicad_custom_library-pre-split.bundle` 3,173,077 bytes (both in `<repos-folder>/kicad-split-backup/`, created with `--all`). `git bundle verify`: "The bundle records a complete history." and "... is okay" for both |
| 2 Visibility | before: kicad_libraries PUBLIC, kicad_custom_library PUBLIC. `gh repo edit ... --visibility private --accept-visibility-change-consequences` returned 0 for both. after: both PRIVATE (`gh repo view --json visibility`). `git fetch origin` in the main checkout and in `Custom/` both succeeded without a prompt |
| 3 Record Custom | skipped (option go, not go-record-custom; no gitlink mismatch) |
| 4 Merge | `git -C "$MAIN" merge --ff-only feature/part-importer`: fast-forward, `main` moved `05f9fff` -> `a156d29e6b6581bc5c935d0cb22099847c5951b7`. Tracked status empty. `git submodule status` before and after identical (Custom `bbd48c5`, WurthElektronik/KiCad-Library `ddb5a9e`); both lines saved as `live/submodule-before.txt` and `live/submodule-after.txt` |
| 5 Push | `git push origin main`: `05f9fff..a156d29  main -> main`. `git push origin v2.0`: "Everything up-to-date" |
| 6 Branches | `git worktree prune` removed nothing. Deleted `worktree-agent-a5e8655b32e875242` (was `cb12cf3`) with `git branch -d` (merged into main, not checked out anywhere). 7 remain, each checked out in a live worktree (below) |
| 7 Tag | `git tag pre-split main` -> `a156d29e6b6581bc5c935d0cb22099847c5951b7` (lightweight tag, commit SHA); `git push origin pre-split`: `[new tag] pre-split -> pre-split` |

### Verification (the three automated commands and the acceptance criteria)

- Both bundles verify "is okay": PASS
- `gh repo view` reports PRIVATE for both repos: PASS
- `pre-split` == `main` == `a156d29`; `feature/part-importer` is an ancestor of `main`; origin has `refs/heads/main` (`a156d29`), `refs/tags/pre-split` (`a156d29`), `refs/tags/v2.0` (`5d320c9`): PASS
- Remaining `worktree-agent-*` branches are only those checked out in live worktrees (7): PASS
- Main checkout `submodule status` equals the preflight lines; tracked status empty: PASS

## Deviations from Plan

### Handled preflight facts the plan did not foresee

**1. v2.0 already on origin.** The orchestrator instructed a comparison before pushing. The local annotated tag object is `5d320c968f85b1a7019541ff401adf63ba7e461f` (peels to commit `95ad75a20f1471076b7870c5f3f02b2a72877d34`), equal to origin's `refs/tags/v2.0`. The push was a no-op; nothing was force-pushed.

**2. Branch cleanup narrower than the plan's wording.** Only one of the 8 `worktree-agent-*` branches was free to delete; deleting it used `-d` (safe), not `-D`. The 7 others are checked out under `<main-checkout>/.claude/worktrees/`, left for plan 16-16 (no worktree was removed here).

**Total deviations:** 0 auto-fixed. **Impact:** none; both items were anticipated in the dispatch and handled as instructed.

No authentication gate occurred (Git Credential Manager supplied credentials for the now-private repos on fetch and push).

## Notes for plan 16-14 and 16-16

- 16-14: kicad-lib-manager still does not exist on GitHub (name free). Both existing repos are private already, so nothing more is needed before pushing to them.
- 16-16, worktrees and branches still alive in `<main-checkout>/.claude/worktrees/`: `worktree-agent-a0072898c66b956ae` (`fe53537`), `a012859fd0a57169e` (`9ee1d2d`), `a779443efc8fdc197` (`74378bb`), `a9df7190cd595954e` (`9ee1d2d`), `a9e267aa4f1fb9047` (`fe53537`), `ae7f8e785d3f43ff3` (`4a7d7bc`), `aef09a733de6aba33` (`9ee1d2d`). Two of them, `a779443efc8fdc197` and `ae7f8e785d3f43ff3`, each hold one doc-only commit that is not in the feature branch; those commits are in the `--all` bundle `kicad_libraries-pre-split.bundle`.
- 16-16, `downloaded_examples`: five entries exist only in the importer worktree (as listed in the preflight) and two ignored zips only in the main checkout; the merge did not touch either set, so copy them before the importer worktree is retired.
- origin's `feature/part-importer` is still at `a3e480b5350d82fec07c23c254d418adecf8347f`, behind local `a156d29`; this plan did not push it.
- The main checkout KiCad reads now holds all v3.0 code in its working tree on `main`; `Custom/` and `WurthElektronik/KiCad-Library` working copies are unchanged.
- Recovery if ever needed: `git clone <repos-folder>/kicad-split-backup/kicad_libraries-pre-split.bundle` (and the custom one); visibility can be reversed with `gh repo edit <repo> --visibility public --accept-visibility-change-consequences` (D-11).

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- `<repos-folder>/kicad-split-backup/kicad_libraries-pre-split.bundle`, `kicad_custom_library-pre-split.bundle`, `live/uri-before.json`, `live/submodule-before.txt`, `live/submodule-after.txt`: present
- `a156d29` is on origin as `main` and `pre-split`
