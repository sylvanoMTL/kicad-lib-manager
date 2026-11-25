---
phase: 16-repo-split
plan: 14
subsystem: infra
tags: [repo-split, live-run, tool-repo, ci, handoff]

requires:
  - phase: 16-repo-split
    provides: "16-13 pre-split tag, private collection repos, bundles, live/split16.env"
provides:
  - "private GitHub repo sylvanoMTL/kicad-lib-manager (PRIVATE, 4 commits, 414 files, main at f8c06b8)"
  - "the tool checkout at <tool-checkout> with its own env, hooks, local config, .claude/ and CLAUDE.local.md"
  - "auto-memory copied to the Claude project folder of the tool checkout"
  - "the handoff command for the next session (planning sync into the tool checkout)"
affects: [16-15, 16-16]

actuals:
  tokens: 0
  tasks: 3
  commits: 0
plan_head_before: 40c0102fdfb03dfa4e82bd24629ae4f66927eaa2
plan_head_after: 40c0102fdfb03dfa4e82bd24629ae4f66927eaa2

tech-stack:
  added: []
  patterns:
    - "tool repo work is committed in the tool checkout (own hooks); the importer worktree only gets this SUMMARY"

key-files:
  created:
    - .planning/phases/16-repo-split/16-14-SUMMARY.md
  modified: []

key-decisions:
  - "Owner approved push (Task 2) with the six marker exemptions listed below"
  - "Owner decision after three red CI runs: simplify; a green CI run is no longer a gate for the split (section Owner decision)"
  - "The repo stays PRIVATE; the owner flips it later (16-16 or by hand)"

requirements-completed: [SPLIT-01, SPLIT-03, SPLIT-08]

status: complete
---

# Phase 16 Plan 14: Live run part 2 Summary

The tool repo exists on GitHub as a private repository, `https://github.com/sylvanoMTL/kicad-lib-manager`, with 4 commits (the import plus three test-only fixes) and 414 files. A fresh clone of GitHub's copy scans clean with `--tree --history`. The tool checkout `<tool-checkout>` has its own Python 3.14 env, passes the quick suite (4017 passed, 3 skipped) and is set up for the next session. `commits: 0` counts code commits of the importer worktree (this plan changes no file of it); the tool repo commits are listed below.

## Task 1: build, verify, scan (done earlier)

- Built from the main checkout's `pre-split` tag (`a156d29`) into a scratch folder: one commit `2712099`, 414 files, author sylvanoMTL with the GitHub noreply address, no Claude-Session line.
- `verify_export`: ok. `prepublish_scan --tree --history` with the owner emails, the deny-terms file and the corpus copied-content check: clean.
- Per-entry counts of the 414 files (still the same on GitHub's copy): root 9, `.githooks` 2, `.github` 1, `.planning` 129, `kicad_lib_manager` 85, `scripts` 12, `tests` 176. Full list: `<repos-folder>/kicad-split-backup/live/tool-files.txt`.

## Task 2: owner decision

Owner answered **push**, with this marker exemption list (`<repos-folder>/kicad-split-backup/live/allowed.txt`): every line a scan let through only because of an inline `scan: allow <rule>` marker.

| Rule | Where | Origin |
|------|-------|--------|
| workstation_path | `.planning/phases/16-repo-split/16-12-SUMMARY.md:153` | NEW since the rehearsal (the summary quotes the row text of 16-RESEARCH.md line 324, rule patterns as prose) |
| workstation_path | `.planning/phases/16-repo-split/16-RESEARCH.md:324` | 16-12 (f7d2129) |
| secret | `.planning/phases/16-repo-split/16-RESEARCH.md:328` | 16-11 |
| secret | `.planning/phases/16-repo-split/16-RESEARCH.md:572` | 16-11 |
| workstation_path | `tests/test_commit_step.py:1149` | 16-03 |
| secret | `tests/test_isolation.py:310` | 16-03 |

Six exemptions, one of them new. No CI fix added a marker, so the list did not grow in Task 3.

## Task 3: what was done

| Step | Result |
|------|--------|
| 1 Create + push | `gh repo create sylvanoMTL/kicad-lib-manager --private ... --push`; visibility printed PRIVATE; it still is PRIVATE at the end of this plan |
| 2 CI | four runs, see the table below; the fourth is green |
| 3 Tool checkout | cloned from GitHub's copy to `<tool-checkout>`; local git config: `user.name` sylvanoMTL, `user.email` the noreply address, `core.hooksPath .githooks`, `core.autocrlf false`, `prepublish.denyTermsFile` (backup folder), `prepublish.denyEmailsFromRepo` (main checkout) |
| 4 Env | `py -3.14 -m venv env`, pinned `requirements-dev.txt` only (no new package). Quick suite: 4017 passed, 3 skipped, 4 warnings in 92.5 s. Budget line: `skip budget: 4017 passed, 3 skipped (max 10), 0 failed, 0 errors` (min 3500). Scan: `prepublish_scan: clean (414 files, 436 blobs, 4 commits)` |
| 5 Claude and GSD | `.claude/` copied from the importer worktree (without `worktrees/` and `debug/`); `.claude/settings.local.json` has `"attribution": {"sessionUrl": false}`; the GSD files' embedded importer-worktree paths were rewritten (see deviations) |
| 6 CLAUDE.local.md | written in the tool checkout (git-ignored) with the workstation specifics: main checkout folder, KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR values, the D-26 rule with those folders, the backup folder and the corpus command. `git status --porcelain` prints nothing; `CLAUDE.local.md`, `.claude` and `env` are each ignored (checked one by one) |
| 7 Memory | the 5 auto-memory files (MEMORY.md plus four topic files, md5-identical to the source) were copied to the Claude project folder named `c--Git-Repo-Clones-kicad-lib-manager` under the user's `.claude/projects/`; the old folder is untouched (it moves into the backup folder in 16-16, after the owner approves) |
| 8 Handoff | below |

No commit in the tool repo carries a Claude-Session line (`git log --format=%B | grep -c Claude-Session` prints 0, also on a fresh clone); all four commits are by sylvanoMTL with the noreply address.

### Fresh clone of GitHub's copy (temporary folder, deleted afterwards)

`git clone https://github.com/sylvanoMTL/kicad-lib-manager.git` into a temporary folder: 4 commits, 414 files, head `f8c06b8`. `prepublish_scan.py --repo <clone> --tree --history --deny-emails-from-repo <main checkout> --deny-terms-file <backup>/deny-terms.txt --corpus <main checkout> --corpus <importer worktree>` printed `prepublish_scan: clean (414 files, 436 blobs, 4 commits)`. The clone was removed.

### CI runs (windows-latest, private repo)

| Run id | Head | Result | Cause |
|--------|------|--------|-------|
| 45618281218 | `2712099` | red | five GUI tests raced on the slower runner (a test asserted a state at once that the app reaches a moment later); fixed in `03b2afb` |
| 45620496098 | `03b2afb` | red | two races: `test_close_refused_while_installing`, `test_migration_dialog_run.py::test_commit_panel_offered_and_probed` (waitUntil of 5 s too short); fixed in `3db4498` (342 waits raised to 30 s, about 20 close sites wait for the asserted state) |
| 45628866231 | `3db4498` | red | two races: `test_install_progress_and_lock` (IndexError: the helper `blocking_apply` emitted its progress steps before it put its gate into `gates`, so `gates[0].set()` could run too early) and `test_commit_not_logged_after_a_commit` (an assert on visibility right after a click-driven close) |
| 45632317281 | `f8c06b8` | **success** (job `test`, all steps green, about 4 min) | fixes in `f8c06b8`: `blocking_apply` registers its gate before it emits any step; six click-driven closes now `qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=30000)` before the assert |

All causes are test timing, not app defects; assertions are unchanged, nothing was skipped, marked slow or xfailed, and neither the pytest config nor `ci.yml` was touched.

Fix commits in the tool repo: `03b2afb` fix(tests): wait for the asserted state in five GUI tests that raced on CI; `3db4498` test: wait for the asserted state after close and on async workers (CI races); `f8c06b8` test: register gates before progress and wait after click-driven closes (CI races).

### Local counts

- After `f8c06b8`, quick suite, normal run: **4017 passed, 3 skipped** (95.5 s and again 92.5 s with the junit file for the budget check).
- One throttled run (process pinned to 2 CPU cores with `start /affinity 3`, `-n 8`): 4016 passed, 3 skipped, 1 failed in 347.9 s. The one failure is `tests/test_isolation.py::test_hung_test_fails_naming_it`, a wall-clock bound (`elapsed < 30`, took 41.6 s) of a subprocess test that starts two workers: it measures speed, not a GUI race, and passes in the normal run. No test touched by this plan's fixes failed under the throttle. The owner's decision (below) ended the planned loop of three throttled runs after this one.

## Owner decision

After three red CI runs caused by test timing races on GitHub's slower runner (not app defects), the owner chose **Simplify**: a green CI run is no longer a gate for the split. The orchestrator relayed it in place of the earlier "Fix + throttled check" loop. The fixes already made were kept, one normal local run was enough, the push followed, and the CI result was recorded without a further fix round. As it happened, the fourth run is green. Races that remain in other tests (if any) are a follow-up for the tool repo. GitHub Actions is free for public repos and within the free monthly minutes for private ones. The copy of these tests on `feature/part-importer` keeps the races (the old copy retires in 16-16).

## Deviations from Plan

**1. [Rule 3 - Blocking] GSD files carried importer-worktree paths.** Found during Task 3 step 5: 690 embedded importer-worktree paths in 253 files of the copied `.claude/`, which would send every GSD command back to the old worktree. They were rewritten to the tool checkout path (git-ignored files, no effect on the repo). The GSD install manifest hashes now differ from the files. **Advice: run a clean GSD reinstall in the tool checkout** (the installer, not an update) when convenient; until then the rewritten copy works.

**2. [Rule 1 - Bug, tests only] Three rounds of test timing fixes** for the red CI runs (table above), in the tool repo only; the `feature/part-importer` copy of the tests is unchanged.

**3. [Rule 3 - Sandbox] `git check-ignore -q` with several paths is rejected, so the three ignore checks ran one by one; `rm -rf "$(...)"` on the fresh clone was refused by the sandbox safety check, so it was removed by its literal path.**

**4. [Owner decision] CI green not required** (section above); not a deviation of the code, a change of the success criterion for this plan.

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 3), 1 owner decision. **Impact:** none on the split content.

## HANDOFF for the next session (plans 16-15 and 16-16)

Work now continues in the tool checkout, not in the importer worktree. The tool repo has the planning files only up to the `pre-split` tag; the records of plans 16-12 to 16-14 (and later orchestrator updates) live on `feature/part-importer` in the old worktree and must be carried over once.

1. Open a terminal and start Claude Code inside the tool checkout:
   ```
   cd <tool-checkout>
   claude
   ```
2. Wait until the orchestrator of this session has finished its own STATE.md and ROADMAP.md update commit on `feature/part-importer`, so that the sync picks that up too. Then run the one GSD command:
   ```
   /gsd-fast carry the live-run records into the tool repo
   ```
   and let it execute these steps in order, from `<tool-checkout>`:
   ```
   env/Scripts/python.exe scripts/split/sync_planning.py --source "<main-checkout>" --ref feature/part-importer --since pre-split --dest . --allow-list scripts/split/allowlist.txt --map "=" --map "<main-checkout>=<main-checkout>" --map "<tool-checkout>=<tool-checkout>"
   env/Scripts/python.exe scripts/prepublish_scan.py --tree --history
   git add -A .planning
   git commit -m "docs(16): carry the live-run records into the tool repo"
   git push origin main
   ```
   (the sync copies only the scrubbed `.planning/` delta between `pre-split` and the branch; the scan must print `prepublish_scan: clean`; the commit goes through the hooks; the push is a normal push, never forced.)
3. Then `/gsd-execute-phase 16` continues with plan 16-15 (the collection side cutover), then 16-16 (retire the old worktree and its copies, move the old Claude memory folder into the backup folder after the owner approves, and the owner's flip of the tool repo to public, with a second scan of what GitHub holds first).

Facts the next session needs:
- Repo `https://github.com/sylvanoMTL/kicad-lib-manager` is **PRIVATE** and stays so until the owner flips it.
- The tool checkout is at main `f8c06b8`, clean, in sync with GitHub; its env is `env/Scripts/python.exe` (Python 3.14); hooks are active (`core.hooksPath .githooks`: commit-msg drops Claude-Session, pre-push scans).
- Variables for scripts are in `<repos-folder>/kicad-split-backup/live/split16.env` (MAIN, WT, BACKUP, S, TOOL_PATH, EMAIL).
- KiCad keeps reading the main checkout `<main-checkout>` (D-26); imports, Generate Tables, the migration and Pin Atomic Libraries run there, never from the tool checkout.
- The six marker exemptions above are what the owner sees again before the flip (16-16).
- Recommended: a clean GSD reinstall in the tool checkout (deviation 1).
- Follow-up: remaining timing races in tests (the throttled run showed one speed-bound test, `test_hung_test_fails_naming_it`).

## Known Stubs

None.

## Threat Flags

None. The repo is private, the push was guarded by the scans and the owner's decision, and `CLAUDE.local.md`, `.claude/` and `env/` are ignored in the tool checkout.

## Self-Check: PASSED

- GitHub: visibility PRIVATE; head `f8c06b8` equals the tool checkout's HEAD; run 45632317281 `success`
- Tool checkout: clean status, `core.hooksPath` = `.githooks`, scan clean, budget line within limits, ignore rules hold for `CLAUDE.local.md`, `.claude`, `env`
- Memory folder holds the 5 files; fresh clone removed
