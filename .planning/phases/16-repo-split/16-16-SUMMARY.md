---
phase: 16-repo-split
plan: 16
subsystem: repo-split-live-run
tags: [publish, retire-worktree, memory, final-scan, visibility]

requires:
  - phase: 16-repo-split (16-14)
    provides: tool repo published privately, approved marker-exemption list, prepublish.denyEmailsFromRepo = main checkout
  - phase: 16-repo-split (16-15)
    provides: the collection's remove-code commit 4f39aa9, identical URI compare
provides:
  - the real downloads kept in the collection's downloaded_examples/ (equal SHA-256)
  - live/retire-inventory.txt, retire-decision.txt, retire-recheck.txt, final-refs.txt, final-allowed.txt in the backup folder
  - the importer worktree retired as the owner approved, the old memory folder moved to the backup folder
  - sylvanoMTL/kicad-lib-manager PUBLIC (flipped by the owner), kicad_libraries and kicad_custom_library PRIVATE
affects: [16-17, 16-18]

actuals:
  tokens: 5000
  tasks: 4
  commits: 0
plan_head_before: c5b3a8e80093e1d1d680a85dfc8d2570f32bf063
plan_head_after: c5b3a8e80093e1d1d680a85dfc8d2570f32bf063

tech-stack:
  added: []
  patterns: ["read-only inventory, owner decision, recheck against the approved inventory, then act"]

key-files:
  created: []
  modified: []

key-decisions:
  - "Owner answered retire with no keep lines: the importer worktree, its ignored items and its submodule repositories are let go, the old memory folder is moved (not deleted)"
  - "Owner keeps the 7 leftover agent worktrees in the main checkout for a later quick task, so no worktree-agent-* branch is deleted"
  - "Owner flipped kicad-lib-manager to public as the last step (D-12)"

requirements-completed: [SPLIT-03, SPLIT-07]

coverage:
  - id: D1
    description: "Every real download of the importer worktree (and the extracted sample folder) exists in the main checkout's downloaded_examples/ with the same SHA-256"
    requirement: SPLIT-03
    verification:
      - kind: other
        ref: "retire-inventory.txt [downloads]: every line main:same-sha"
        status: pass
    human_judgment: false
  - id: D2
    description: "The importer worktree is retired only as far as the owner approved, on an inventory equal to the one the owner saw"
    verification:
      - kind: other
        ref: "retire-recheck.txt compared with retire-inventory.txt (no difference); worktree no longer registered in the main checkout; feature/part-importer intact at d1faa59"
        status: pass
    human_judgment: false
  - id: D3
    description: "A fresh clone of what GitHub holds scans clean (tree and history, emails, deny terms, corpus copied-content), marker exemptions unchanged since 16-14, CI green on the same commit, corpus quick run green"
    requirement: SPLIT-03
    verification:
      - kind: other
        ref: "prepublish_scan: clean (416 files, 440 blobs, 5 commits); final-allowed.txt equal to the 16-14 list; CI run 45672175120 success on 967688b; pytest 4087 passed, 3 skipped"
        status: pass
    human_judgment: false
  - id: D4
    description: "GitHub's refs did not change between the final scan and the flip"
    requirement: SPLIT-07
    verification:
      - kind: other
        ref: "git ls-remote equal to live/final-refs.txt (HEAD and refs/heads/main at 967688b)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The tool repo is PUBLIC and the collection and Custom repos are PRIVATE"
    requirement: SPLIT-07
    verification:
      - kind: other
        ref: "gh repo view --json visibility: kicad-lib-manager PUBLIC, kicad_libraries PRIVATE, kicad_custom_library PRIVATE (re-checked when this SUMMARY was written)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The owner starts the app from the tool checkout with real settings and opens KiCad's Symbol and Footprint library managers (carried over from 16-15)"
    verification: []
    human_judgment: true
    rationale: "Uses the owner's real settings and the running KiCad; the URI diff in 16-15 is the required proof, this is the owner's own confirmation (pending for the end-of-phase review)"

duration: 60min
completed: 2026-11-26
status: complete
---

# Phase 16 Plan 16: Retire the importer worktree and publish (live run, part 4) Summary

**The importer worktree was retired as the owner approved on a read-only inventory, the old memory folder was moved into the backup folder, GitHub's copy scanned clean and CI-green with unchanged refs, and the owner flipped sylvanoMTL/kicad-lib-manager to PUBLIC; kicad_libraries and kicad_custom_library stay PRIVATE.**

## Performance

- **Tasks:** 4 (Task 1 and Task 3 by the executor, Task 2 and Task 4 by the owner)
- **Files modified in the tool repo:** 0 (the work landed outside this repository); only this SUMMARY is committed here
- **Commits in the tool repo for this plan:** 0 production commits

## Accomplishments

- **Task 1, downloads (D-17, additive).** The five real downloads and the extracted sample folder of the importer worktree were copied into the main checkout's `downloaded_examples/` (an existing file is never overwritten; no same-name conflict). SHA-256 (inventory `[downloads]`, every line `main:same-sha`):
  - `194150990-659-usb4145-03-0170-c.zip`: `cace513fa8ea49d39451729b8d66553695310d35561b576b535a424e10ce3d71`
  - `194150990-659-usb4145-03-0170-c/` (3 files): `dummy_CAD_FILE.step` `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, `usb4145-03-0170-c.stp` `7c74c34b81a3cdccef12054c10320198e03ad5c538c047cfd35fa52877dcfba6`, `usb4145-03-0170-c.txt` `cd97ceab342fa6f09f21c6b0dd4c00ce93f0c2cf75ad6c1657bfd7ea60733922`
  - `LIB_RS3-1212S_H3.zip`: `ac9ffc121fef61cf57c9ff84a4987893388f60a54376fce1f61dbbbf0e03f826`
  - `USB4145-03-0170-C_REVA2.zip`: `8c778ec3536b7567744ba5f3d0a6790121f8f5f0354a219a65c9c746e4474eda`
  - `ul_ATXK-H14-D-32-768KHZ-E50-T3.zip`: `07b243191ac1c34b90532eddde986d0665625719d65ef677f2eca15ccbbe179f`
  - `ul_CSD85301Q2.zip` (already in the main checkout, same SHA-256): `9890115a990c03797a3d011eb62f0d7cd067fa10f982771fa8b38595d9399f3e`
- **`.gsd/`:** not copied. The tool checkout has its own; the worktree's holds only the importer's dispatch-isolation records (16 files only there, 2 differing), classed unknown and let go.
- **Task 1, inventory** (`<repos-folder>/kicad-split-backup/live/retire-inventory.txt`): `needs-force=yes` (the worktree's `modules/` folder exists); `[untracked]` empty; no UNSAFE or DIRTY submodule (Custom `bbd48c5`, local branch main `8f7d454`; WurthElektronik/KiCad-Library `ddb5a9e`, local branch master `df5afb5`; all commits ok in the main submodules and on their remotes, no stash entries); 22 reflog-only commits (superseded planning commits plus `5b4470e` feat(04-08)), let go; 9 worktrees listed, none prunable; 7 `worktree-agent-*` branches, each held by its own worktree in the main checkout (so none is proposed for deletion); disposable ignored items (env, .venv, caches, `__pycache__`) and copied ones (`.claude/` copied in 16-14, the downloads above); memory folders equal (5 files each, `memory-equal=yes`).
- **Task 1, final checks of GitHub's copy.** A fresh clone of what GitHub holds scanned with `--tree --history`, the owner's emails, the deny-terms file and the corpus copied-content check: **`prepublish_scan: clean (416 files, 440 blobs, 5 commits)`**. `final-allowed.txt` (`--list-allowed`) has 6 lines, none new since the 16-14 approval: `workstation_path` at 16-12-SUMMARY.md:153, 16-RESEARCH.md:324 and tests/test_commit_step.py:1149; `secret` at 16-RESEARCH.md:328, 16-RESEARCH.md:572 and tests/test_isolation.py:310. Newest CI run on main: **run 45672175120, success, commit 967688b**, the commit on GitHub's `refs/heads/main` line. Corpus quick run against the main checkout (the collection after the split): **4087 passed, 3 skipped**. All three repos were PRIVATE before the flip.
- **Task 2, owner decision.** The owner answered **`retire`** with no `keep` lines (`live/retire-decision.txt`: `retire`). The owner also decided: leave the 7 leftover agent worktrees in the main checkout for a later quick task (5 hold an untracked `.planning/debug` note; 2 hold one unmerged commit each: `a779443efc8fdc197` tip `74378bb`, `ae7f8e785d3f43ff3` tip `4a7d7bc`), and copy the importer project's own memory folder (9 files not in the tool memory) into the tool memory.
- **Task 3, retirement.**
  - The recheck (`live/retire-recheck.txt`) matched the approved inventory (no difference in names, classes, submodule SHAs, reflog-only commits or branch tips), and the worktree and both submodules were clean.
  - `git worktree remove --force` on the importer worktree ran with `--force` because the approved `[commands]` list said so (`needs-force=yes`). It deregistered and emptied the worktree but exited 255 (see Deviations).
  - No `worktree prune` (no prunable entry), no branch deletion (every `worktree-agent-*` branch is held by a registered worktree). `feature/part-importer` is intact at `d1faa59`; branch tips are as in the inventory.
  - The old memory folder was moved to `<repos-folder>/kicad-split-backup/memory-old/Kicad-Libraries-memory` (5 files, `memory-equal=yes` first; a move, nothing deleted). The 9 memory files of the importer project's own folder (git-bash-no-jq, kicad-checkout-layout, library-naming-decision, parked-atxk-h14, plain-language-ui, product-vision-public-tool, uat-instructions-detail, we-library-read-only, worktree-executor-setup) were copied additively into the tool memory by the orchestrator after Task 3; the source folder stays in place.
  - Refs check: GitHub's `ls-remote` equals `live/final-refs.txt` (HEAD and `refs/heads/main` at `967688b`), so nothing was pushed since the final scan.
- **Task 4, the flip.** The owner ran `gh repo edit sylvanoMTL/kicad-lib-manager --visibility public --accept-visibility-change-consequences`. Re-checked when this SUMMARY was written (`gh repo view <repo> --json visibility --jq .visibility`):
  - sylvanoMTL/kicad-lib-manager: **PUBLIC**
  - sylvanoMTL/kicad_libraries: **PRIVATE**
  - sylvanoMTL/kicad_custom_library: **PRIVATE**

## Task Commits

1. **Task 1: Read-only pass, downloads, inventory, final checks** - none (copies into the collection's ignored folder; records in the backup folder)
2. **Task 2: Owner decision `retire`, no keep lines** - none (recorded in `live/retire-decision.txt`)
3. **Task 3: Retire as approved, memory move, refs check** - none (changes the main checkout's worktree list and local folders)
4. **Task 4: Owner flips the tool repo to public** - none (GitHub setting)

**Plan metadata:** the commit of this SUMMARY in the tool repo worktree.

## Files Created/Modified

- Tool repo: only `.planning/phases/16-repo-split/16-16-SUMMARY.md`.
- Outside the repository: `<repos-folder>/kicad-split-backup/live/retire-inventory.txt`, `retire-decision.txt`, `retire-recheck.txt`, `final-refs.txt`, `final-allowed.txt`, and `<repos-folder>/kicad-split-backup/memory-old/`.
- Collection (main checkout): the five downloads and the sample folder added to `downloaded_examples/` (ignored); the importer worktree deregistered.
- Tool memory (`<home>/.claude/projects/` folder of the tool checkout): 9 files added.

## Decisions Made

- Followed the owner's answer `retire` exactly: no keep lines, no extra worktree removals, no branch deletions.
- The 7 leftover agent worktrees and their branches stay for a later quick task (owner's choice), so `[commands]` held no branch deletion.
- The flip was the owner's own action after the final scan, the refs check and the visibility check (D-12).

## Deviations from Plan

**1. [Acceptance criterion not met literally] The retired worktree's empty folder still exists.**
- **Found during:** Task 3
- **Issue:** `git worktree remove --force` deregistered the worktree and emptied it but exited 255 with "failed to delete ...: Permission denied", because Windows holds the now-empty folder `<repos-folder>/Kicad_Libraries-importer` open (some process uses it as its current folder). The criterion "`test -e "$WT"` fails" is therefore not met literally.
- **Fix:** none by the executor; no `--force` beyond the approved one and no retry. The worktree is no longer registered and holds no files; the owner removes the empty folder later, once nothing holds it.
- **Verification:** the three Task 3 automated checks passed (the importer worktree is not in `worktree list --porcelain`, `feature/part-importer` resolves, no unheld `worktree-agent-*` branch is left).

**Total deviations:** 1 (a leftover empty folder). **Impact:** none for the plan's purpose; cosmetic until the owner deletes the folder.

## Issues Encountered

- The 7 leftover agent worktrees under the main checkout's `.claude/worktrees/` remain registered (owner's decision, for a later quick task). Two folders there are not registered as worktrees (`agent-a1b9eaf5f60044bb2`, `agent-a5e8655b32e875242`) and were not touched; they may belong to a running session.

## Pending human check (end-of-phase review)

Carried over from 16-15, not yet done by the owner: start the Library Manager from the tool checkout (`.\env\Scripts\python.exe kicad_lib_manager.py`), then open KiCad's Symbol and Footprint library managers. Expected: the Library folder row shows the main checkout with the tag "KiCad's folder" or "your choice", the scan lists the Custom and WurthElektronik libraries, and KiCad lists the same libraries as before the split with none marked missing.

## Self-Check: PASSED

- Visibilities: kicad-lib-manager PUBLIC, kicad_libraries PRIVATE, kicad_custom_library PRIVATE
- Final scan line, CI run, corpus run and refs check as recorded above
- This SUMMARY scrubbed and scanned clean before its commit
