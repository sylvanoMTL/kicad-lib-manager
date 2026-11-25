---
phase: 16-repo-split
plan: 12
subsystem: infra
tags: [rehearsal, repo-split, prepublish-scan, uri-diff, cutover, fresh-clone]

requires:
  - phase: 16-repo-split
    provides: "16-03 scan and skip budget, 16-04 build_tool_repo / verify_export, 16-05 uri_diff / cutover_collection, 16-11 fresh-clone budget numbers"
provides:
  - "rehearsal record the live run (16-13..16-16) repeats: export counts, scan result, marker exemptions, budget lines, hook result, URI counts, corpus summaries"
  - "evidence folder <repos-folder>/kicad-split-backup/rehearsal/ (dry run, snapshots, run summaries, scan outputs)"
  - "finding for plan 16-13: the live KiCad sym-lib-table holds 6 disabled entries whose files do not exist, so uri_diff compare cannot print '0 missing' on the live tables"
affects: [16-13, 16-14, 16-15, 16-16]

actuals:
  tokens: 40
  tasks: 3
  commits: 1
plan_head_before: 2617e56ba6ad11fce68f38fd9a375ae533a45a10
plan_head_after: f7d2129216c87a2f87c7c1ed8cc93e1e5f8f6e9f

tech-stack:
  added: []
  patterns:
    - "rehearsal on git clone --no-local copies with the origin removed (source) or its push URL set to DISABLED (collection); nothing pushed anywhere"
    - "rehearsal variables persisted in kicad-split-backup/rehearsal/split16.env, outside every repository"

key-files:
  created: []
  modified:
    - .planning/phases/16-repo-split/16-RESEARCH.md

key-decisions:
  - "The one scan finding (a planning-text table row that quotes the workstation_path rule's own regexes) got one inline allow marker, not a rule change"
  - "The six pre-existing missing live entries were reported, not fixed: the plan assigns that decision to the owner in plan 16-13"

requirements-completed: [SPLIT-01, SPLIT-02, SPLIT-03, SPLIT-04]

coverage:
  - id: D1
    description: "Tool side: build from a pre-split tag gives one commit with the noreply identity, verify_export ok, scan clean on tree and history with owner emails, deny terms and both corpora"
    requirement: SPLIT-01
    verification:
      - kind: other
        ref: "build_tool_repo.py then verify_export.py ('verify_export: ok (413 files)') then prepublish_scan.py --tree --history ... ('prepublish_scan: clean (413 files, 410 blobs, 1 commits)')"
        status: pass
    human_judgment: false
  - id: D2
    description: "A fresh clone of the built repository (no downloaded_examples, no Custom) passes the quick run within the skip budget with and without KiCad, and the commit-msg hook drops the Claude-Session line"
    requirement: SPLIT-04
    verification:
      - kind: other
        ref: "pytest quick run + check_skip_budget.py: 4013 passed / 3 skipped (KiCad), 3998 passed / 3 skipped (KICAD_TEST_HIDE_KICAD=1)"
        status: pass
      - kind: other
        ref: "git commit --allow-empty -F msgfile in the clone with core.hooksPath .githooks: Co-Authored-By kept, Claude-Session gone"
        status: pass
    human_judgment: false
  - id: D3
    description: "Collection side: cutover_collection --apply on a scratch collection keeps both gitlinks, .gitmodules and the samples on disk; the resolved-URI snapshot of KiCad's tables is byte-identical before and after"
    requirement: SPLIT-02
    verification:
      - kind: other
        ref: "uri_diff.py compare scratch-before scratch-after: 428 entries identical, but exit 1 because 6 pre-existing disabled entries are missing both before and after"
        status: fail
      - kind: other
        ref: "same compare with the 6 disabled stale entries filtered out of both snapshots: 'uri_diff: identical, 422 entries, 0 missing' (supplementary, not the plan's literal check)"
        status: pass
    human_judgment: true
    rationale: "The plan's literal check ('0 missing') cannot pass while the live tables keep 6 stale disabled Wurth entries; whether to delete those entries, or to make uri_diff ignore disabled entries, is the owner's decision in plan 16-13"
  - id: D4
    description: "Corpus run against the cut scratch collection passes (bare pytest and --full -m corpus)"
    requirement: SPLIT-04
    verification:
      - kind: other
        ref: "KICAD_TEST_CORPUS=<scratch collection> bare pytest: 4083 passed, 3 skipped; --full -m corpus: 8091 passed, 1 skipped"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-11-25
status: complete
---

# Phase 16 Plan 12: Full dry run of the split on scratch clones Summary

**The whole split rehearsed on `git clone --no-local` copies: a 413-file one-commit tool repo that scans clean and passes 4013 / 3998 tests from a fresh clone, and a code-free scratch collection whose resolved KiCad URIs are byte-identical before and after (428 entries), with the one caveat that the live KiCad tables already carry 6 missing disabled entries.**

## Performance

- **Duration:** about 50 min (includes one full restart after a scan finding)
- **Completed:** 2026-11-25
- **Tasks:** 3 (Task 1 was done by the orchestrator at the owner's request; Tasks 2 and 3 here)
- **Repository files changed:** 1 (a single marker in `16-RESEARCH.md`)

## Accomplishments

- Task 1 acceptance re-checked first: `deny-terms.txt` exists and is non-empty, and the folder is not inside a repository. Its contents were never printed, copied or logged; it was passed to the scan by path only.
- The tool side passed end to end after one source fix (below).
- The collection side passed except for the literal "0 missing" check, because of 6 stale entries in the live table that exist before the split.
- Nothing was pushed, no `gh` write command ran (only `gh api user --jq .id`), KiCad's configuration files keep their old modification times (tables 2026-11-10, `kicad_common.json` 2026-11-23), and the main checkout was only read (its `git status` shows only the untracked `env-py311/` that was there before).

## Task Commits

1. **Task 1** - no commit (owner/orchestrator wrote the deny-terms file outside every repository)
2. **Task 2 source fix:** `f7d2129` (fix) - one inline `scan: allow workstation_path` marker on `.planning/phases/16-repo-split/16-RESEARCH.md:324`
3. **Task 3** - no repository change

**Plan metadata:** the commit that adds this SUMMARY follows.

## Task 2 record: tool side

Variables (derived, not typed): `MAIN` = first worktree entry, `WT` = the feature/part-importer checkout, `TOOL_PATH` = `<repos folder>/kicad-lib-manager`, `BACKUP` = `<repos folder>/kicad-split-backup`, `EMAIL` = the owner's noreply address built from `gh api user --jq .id`. They are persisted in `kicad-split-backup/rehearsal/split16.env` (the `S=` line was removed with the scratch folder).

**Export** (`build_tool_repo.py --source <src clone> --ref pre-split`, source clone had `origin` removed, tag `pre-split` created only there): 413 files, one commit on `main`.

| Entry | Files |
|-------|-------|
| `.gitattributes` | 1 |
| `.githooks` | 2 |
| `.github` | 1 |
| `.gitignore` | 1 |
| `.planning` | 128 |
| `CLAUDE.md` | 1 |
| `LICENSE` | 1 |
| `README.md` | 1 |
| `kicad_lib_manager` | 85 |
| `kicad_lib_manager.py` | 1 |
| `pyproject.toml` | 1 |
| `requirements-dev.txt` | 1 |
| `requirements.txt` | 1 |
| `scripts` | 12 |
| `tests` | 176 |

- `verify_export.py`: `verify_export: ok (413 files)`.
- `git -C tool rev-list --count HEAD` printed 1; `git log -1 --format=%ae` printed `39799529+sylvanoMTL@users.noreply.github.com`; `git -C src remote` printed nothing.
- **Scan result** (`--repo --tree --history --deny-emails-from-repo <WT> --deny-terms-file <BACKUP>/deny-terms.txt --corpus <WT> --corpus <MAIN>`): first run 1 finding, after the fix `prepublish_scan: clean (413 files, 410 blobs, 1 commits)`, exit 0. Each scan takes about 2 minutes (corpus copy check on two collections).
- **Fresh clone** (`git clone --no-local` of the built repo, no `downloaded_examples`, no `Custom`, this venv's interpreter with the clone as cwd, `KICAD_TEST_CORPUS` blank):

| Run | Passed | Skipped | Deselected | Time | Budget line |
|-----|--------|---------|------------|------|-------------|
| KiCad 9 and 10 installed | 4013 | 3 | 41 corpus | 102.4 s | `skip budget: 4013 passed, 3 skipped (max 10), 0 failed, 0 errors` |
| `KICAD_TEST_HIDE_KICAD=1` | 3998 | 3 | 41 corpus, 15 needs_kicad | 78.8 s | `skip budget: 3998 passed, 3 skipped (max 10), 0 failed, 0 errors` |

  These equal the 16-11 measurements (4013 / 3 and 3998 / 3). The three skips are the two symlink-privilege skips and the real-KiCad-config skip, the same as in 16-11.
- **Hook check** (clone with `core.hooksPath .githooks`, `user.name sylvanoMTL`, noreply `user.email`, empty commit whose message ended with a `Co-Authored-By` line and a `Claude-Session` line): `git log -1 --format=%B` keeps `Co-Authored-By` (count 1) and lost `Claude-Session` (count 0).

### Source fix made (one)

| Place | Finding | Disposition |
|-------|---------|-------------|
| `.planning/phases/16-repo-split/16-RESEARCH.md:324` | `workstation_path` | The row of the "Rule classes" table quotes the rule's own regexes (`/Users/[^/\s]+/`, `/home/(?!runner\b)[^/\s]+/`, the pytest-of pattern); even after the export scrub they match the rule. A planning-text false positive: one `<!-- scan: allow workstation_path -->` marker appended to the row, commit `f7d2129`. No rule was changed. 16-11 had skipped `workstation_path` on the keep-set, which is why only the rehearsal export could show it. |

After the fix the scratch folder was deleted and the whole rehearsal restarted at step 0 (new scratch folder, env file rewritten), as the plan requires.

### Marker exemptions

Run: the same scan with `--list-allowed` added: `prepublish_scan: 5 allowed by marker`, then `clean (413 files, 410 blobs, 1 commits)`. The owner reviews this table before the first push (plan 16-14 Task 2) and before the flip (16-16).

| Place | Rule | Why the line is not a real hit | Origin |
|-------|------|--------------------------------|--------|
| `.planning/phases/16-repo-split/16-RESEARCH.md:324` | workstation_path | Table row that lists the rule's own detection patterns as prose; no real path of a person | this fix loop (`f7d2129`) |
| `.planning/phases/16-repo-split/16-RESEARCH.md:328` | secret | The "Pre-Publish Scan Design" row for the secret rule, which lists its patterns and quotes the planted constant as prose | plan 16-11 |
| `.planning/phases/16-repo-split/16-RESEARCH.md:572` | secret | Quotes the planted test constant `_SECRET` of `tests/test_isolation.py`, a made-up 17-character string, not a credential | plan 16-11 |
| `tests/test_commit_step.py:1149` | workstation_path | A synthetic POSIX folder with an apostrophe (`o'neil`) used to test shell quoting of a git command; not a real person's folder | plan 16-03 |
| `tests/test_isolation.py:310` | secret | `_SECRET` is a planted test string a child test writes to prove the isolation guard; not a credential | plan 16-03 |

The two `tests/test_docs_atomic.py` markers of 16-03 are gone because plan 16-07 deleted that file.

## Task 3 record: collection side

- Scratch collection: `git clone --no-local` of this checkout, `git switch -c main`, `remote set-url --push origin DISABLED` (`git config remote.origin.pushurl` prints `DISABLED`). Both submodules initialised offline from `WT`'s working copies with `url.<local>.insteadOf`; `git submodule status` showed both at the recorded SHAs with no leading `+`: `Custom` `bbd48c5f3648e10e769840e29c72c64926a7f433`, `WurthElektronik/KiCad-Library` `ddb5a9ea669b907f009f764b245e39d32ac15bd1`. The five real downloads (`downloaded_examples/`, 2 zips from vendors plus loose folder, 6 entries) were copied in untracked.
- KiCad's folder (read by `uri_diff.py vars`): `<home>/AppData/Roaming/kicad/10.0`; `KICAD_LIB_GITHUB` = `<main-checkout>`, `CUSTOM_3DMODEL_DIR` = `<main-checkout>/Custom/3DModels`. Only a copy of `sym-lib-table`, `fp-lib-table` and `kicad_common.json` was snapshotted.
- **Live entry count:** `live-before`: 428 entries, 6 missing. **Scratch before:** 428 entries, 6 missing. `compare live-before scratch-before` found the same 428 entries with identical resolved paths and the same 6 missing files; no library exists in one and not the other, so there is no live-vs-scratch URI difference to list for the owner.
- Cutover dry run (saved) listed: remove 16 top-level entries (`.planning` 714 tracked files, `tests` 176, `kicad_lib_manager` 85, `scripts` 12, ...), untrack `downloaded_examples` (1 tracked file), write README.md, CLAUDE.md and .gitignore from the templates, keep both gitlinks and `.gitmodules` bytes. `--apply` exited 0 with `committed on main` (`6a5a061`) and the script's own post-checks passed.
- After the apply: `git ls-tree -r HEAD` lists exactly `100644 .gitignore`, `100644 .gitmodules`, `100644 CLAUDE.md`, `100644 README.md`, `160000 Custom`, `160000 WurthElektronik/KiCad-Library`; both gitlink SHAs equal the ones of `HEAD~1`; `git diff HEAD~1 HEAD -- .gitmodules` prints nothing; `downloaded_examples/ul_CSD85301Q2.zip` is still on disk and `git ls-files downloaded_examples` prints nothing.
- **Snapshots:** `scratch-before.json` and `scratch-after.json` are byte-identical (`cmp`). The plan's literal compare:

```
uri_diff: 12 difference(s) between ...scratch-before.json and ...scratch-after.json   (exit 1)
```

  All 12 "differences" are `missing (before)` / `missing (after)` lines for the same 6 entries; no `added`, `removed` or `changed` line. The entries are identical.

- **Why 6 missing (pre-existing, not caused by the split):** `Inductor_Wurth_WE-SUKW`, `MagIC_Wurth_MagIC-FDSM`, `-FIMM`, `-LDHM`, `-VDRM`, `-VISM` are entries of KiCad's global `sym-lib-table` that carry `(disabled)`. Their files are not in the Wurth library at the pinned commit (nor in the main checkout): upstream renamed the series (`Ferrite_Wurth_WE-SUKW`, `MagIC_Wurth_WPME-*`). `uri_diff` counts a disabled entry as missing.
- **Supplementary proof (not the plan's literal check):** with the 6 disabled stale entries removed from both snapshot files, `compare scratch-before scratch-after` printed `uri_diff: identical, 422 entries, 0 missing` (exit 0), and `compare live-before scratch-before` printed the same line. This is the evidence that the remove-code commit leaves every other resolved URI unchanged.
- **Corpus runs** from the tool clone against the cut scratch collection (`KICAD_TEST_CORPUS=<scratch collection>`; `Custom` in the collection stayed unchanged, no `changed the live Custom/ folder` failure):
  - bare pytest: `4083 passed, 3 skipped, 4 warnings in 96.76s`
  - `--full -m corpus`: `8091 passed, 1 skipped in 152.77s` (the skip is `KICAD_ATOMIC_UAT_DIR` unset)
- Evidence copied to `<repos-folder>/kicad-split-backup/rehearsal/`: `cutover-dry.txt`, `cutover-apply.txt`, `live-before.json`, `scratch-before.json`, `scratch-after.json`, `compare.txt`, `scan2.txt`, `scan3.txt` (list-allowed), `build.txt`, `gitlinks-before.txt`, `gitlinks-after.txt`, the four run summaries and `split16.env`.
- **Scratch folder deleted** (`split16-zo6ncob7`) after the checks passed; the first scratch folder (`split16-hk5j22e4`) was deleted after the scan finding. The `S=` line was removed from `split16.env`.

## Decisions Made

- One inline marker for the scan finding, because the row is documentation of the rule itself and a rewrite would destroy the research table; the rule was not touched.
- The 6 stale entries were not touched and `uri_diff.py` was not changed: the plan reserves the decision to the owner in 16-13 (delete the stale disabled entries from KiCad's `sym-lib-table`, or accept them as known, or make `uri_diff` ignore `(disabled)` entries and say so in the verdict line).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Planning-text false positive blocked the scan**
- **Found during:** Task 2 step 4
- **Issue:** `prepublish_scan` reported `workstation_path` at `.planning/phases/16-repo-split/16-RESEARCH.md:324` in the exported tree.
- **Fix:** one inline `scan: allow workstation_path` marker (the plan's permitted disposition for a false positive), scratch folder deleted, rehearsal restarted from step 0.
- **Files modified:** `.planning/phases/16-repo-split/16-RESEARCH.md`
- **Verification:** rescan clean (413 files, 410 blobs, 1 commits)
- **Committed in:** `f7d2129`

### Plan checks not met literally

**2. [Assumption case] Task 3 compare verify cannot print "0 missing" on the live tables**
- **Issue:** the plan's first Task 3 verify command and step 6 require `uri_diff: identical, <n> entries, 0 missing`. Both snapshots carry the same 6 missing disabled entries (see above), so the command exits 1 although nothing differs between before and after.
- **Disposition:** the plan's own Assumptions section covers this case ("the rehearsal reports it and the owner decides in plan 16-13"). Reported here; the supplementary filtered compare shows the identical result without the stale entries. **Owner decision needed in 16-13 before the live run**, otherwise the live compare in 16-15 fails the same way.

**3. [Rule 3 - Blocking] Environment**
- The scan and the two pytest runs each exceed the Bash tool's 120 s default; the scan ran as a background command and was awaited, the pytest runs used the 600 s foreground limit. `$(...)` substitution worked in this sandbox, so no command had to be split.

**Total deviations:** 1 auto-fixed (Rule 1), 1 plan check not met literally (owner decision), 1 environment note.

## Issues Encountered

- `cutover_collection.py --apply` prints `cutover: leftover kept: README.md is not a plain folder` and the same for `CLAUDE.md` after its successful commit. Both files are the freshly written templates, so nothing is wrong, but the wording suggests a problem. Cosmetic, outside this plan's scope; left for the owner (a one-line change in the leftover loop to skip the `WRITE` targets).
- `git status --no-optional-locks` is not an option of this git version; it must be passed as `git --no-optional-locks status`.

## Known Stubs

None.

## Threat Flags

None. No new surface; the work used only scratch copies and read-only calls on the real checkouts.

## Next Phase Readiness

- 16-13 starts with the owner decision on the 6 stale disabled entries (see Deviation 2), then repeats these steps live. Numbers to compare in the live run: 413 exported files and one commit; 4013 / 3 and 3998 / 3 budgets; 428 table entries; the collection tree of exactly six lines.
- The marker table above is ready for the owner's review before the first push.

## Self-Check: PASSED

- Commit `f7d2129` is an ancestor of HEAD; `.planning/phases/16-repo-split/16-12-SUMMARY.md` exists; `<repos-folder>/kicad-split-backup/deny-terms.txt` still exists and `git -C` on that folder still fails (not in a repository); the evidence files listed above exist in `kicad-split-backup/rehearsal/`.
- Acceptance: tool repo 1 commit with the noreply author; `git -C src remote` printed nothing; `pushurl` printed `DISABLED`; both gitlinks and `.gitmodules` unchanged; `downloaded_examples` untracked on disk; compare literal check not met for the reason in Deviation 2.

## Owner decision after the rehearsal (orchestrator, 2026-11-25)

The literal `uri_diff compare` check failed only on six `(disabled)` sym-lib-table entries whose files Würth renamed upstream (`Inductor_Wurth_WE-SUKW`, `MagIC_Wurth_MagIC-FDSM`, `-FIMM`, `-LDHM`, `-VDRM`, `-VISM`); they were missing before and after alike. Owner chose "ignore disabled entries": `scripts/split/uri_diff.py` now lists a disabled entry with a gone file as `disabled, file not found` (a note) and no longer counts it as missing; a change of the disabled flag is still a difference (commits e55097d RED, then the GREEN commit). A read-only snapshot of the live KiCad 10 tables now prints `428 entries, 0 missing` with the six as notes, so the live compare in 16-15 can pass as written. The owner's KiCad config was not changed.
