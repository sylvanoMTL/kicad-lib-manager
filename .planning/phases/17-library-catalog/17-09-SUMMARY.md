---
phase: 17-library-catalog
plan: 09
subsystem: tooling
tags: [scripts, git, submodule, catalog, wurth, conversion, tdd]
status: complete

requires:
  - phase: 17-library-catalog
    provides: catalog.json manifest and path variables (17-03), curated Wurth entry (17-04), validate.unresolved_models (17-06), uri_diff.py and the cutover discipline (Phase 16)
provides:
  - scripts/catalog/wurth_to_catalog.py, the dry-run-first conversion that removes the WurthElektronik submodule behind a bundle, a rollback tag and the three D-26 pass checks
  - scripts/catalog/collection/README.md and CLAUDE.md, the collection docs for the catalog layout, written by --apply
  - tests/test_wurth_to_catalog.py, 10 quick and 8 slow tests on a synthetic parent with two submodules, including the way back
affects: [17-19, 17-20]

plan_head_before: f11a4938795db844bff64d08dc14ef69c96fc23f
plan_head_after: df95723b92cc690d97f255a552093e98e9cc9b0c

actuals:
  tokens: 19966
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One-off collection scripts follow the cutover_collection discipline: dry run by default, every refusal before the first write, exit 0/1/2, a printed way back"
    - "The one function that starts git (_git) enforces an allow-list of local commands, so 'never clean, push or any network command' is a runtime guarantee and a test, not only a promise"
    - "Slow script tests run main() in process on a throwaway superproject (gitfixtures.make_superproject plus a second submodule and a ThirdParty clone) with kicad_running and TEMPLATES monkeypatched"

key-files:
  created:
    - scripts/catalog/wurth_to_catalog.py
    - scripts/catalog/collection/README.md
    - scripts/catalog/collection/CLAUDE.md
    - tests/test_wurth_to_catalog.py
  modified: []

key-decisions:
  - "The old Wurth folder is rewritten in the before snapshot in both spellings the snapshot holds, <LIB>/ and ${KICAD_LIB_GITHUB}/ (a snapshot keeps the variable in uri and the root placeholder in resolved), on a whole path segment only"
  - "The module data folder is .git/modules/<first segment of the submodule name> (WurthElektronik), so the way back moves it back to the same place; refused when Custom's module data would share it"
  - "The conversion commit stages .gitignore, catalog.json, .gitmodules, README.md and CLAUDE.md with the gitlink removal (discretion item decided yes); it is made only with --apply and --message"
  - "--config-dir names the folder that holds KiCad's version folders (10.0, 9.0), so one override serves both the newest-config check and the older-config lines"

requirements-completed: [CAT-12]  # REQUIREMENTS.md boxes stay open: later plans of the phase declare the same IDs (shared-ID gate)

coverage:
  - id: D1
    description: "wurth_to_catalog.py prints a plan and writes nothing without --apply; every refusal (not on main, tracked or untracked changes, no catalog entry, KiCad running, wrong WE_3DMODEL_DIR, odd clone config, snapshot differences, missing model, backup inside a work tree or the repository, existing backup target, tag exists, ThirdParty not ignored) exits 1 with 'nothing was written' and leaves the repository untouched"
    requirement: "CAT-12"
    verification:
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_dry_run_writes_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_refusals"
        status: pass
      - kind: unit
        ref: "tests/test_wurth_to_catalog.py#test_argument_errors_exit_2"
        status: pass
    human_judgment: false
  - id: D2
    description: "The three D-26 pass checks hold before the submodule is removed (rewritten before snapshot compares identical to the after snapshot, no missing entry, no unresolved 3D model in the clone)"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_wurth_to_catalog.py#test_rewrite_snapshot"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_refusals"
        status: pass
    human_judgment: false
  - id: D3
    description: "--apply converts in the fixed order (verified bundle, lightweight tag, deinit, rm, module data moved to the backup folder, docs, one commit), runs the post-checks, stops at the first failure with the way back, and the printed way back restores the submodule offline"
    requirement: "CAT-12"
    verification:
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_apply_converts"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_apply_stops_at_the_first_failure_and_prints_the_way_back"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_apply_then_way_back_restores_the_submodule"
        status: pass
    human_judgment: false
  - id: D4
    description: "Older KiCad config folders that still set WE_3DMODEL_DIR are named with the old and the new value and never written; only local git commands can run"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_wurth_to_catalog.py#test_stale_var_lines"
        status: pass
      - kind: unit
        ref: "tests/test_wurth_to_catalog.py#test_only_local_git_commands_can_run"
        status: pass
    human_judgment: false
  - id: D5
    description: "The collection README and CLAUDE.md templates describe Custom as the only submodule, ThirdParty and catalog.json, WE_3DMODEL_DIR through the catalog, with no submodule-add or recursive-clone instruction; the dry run shows a diff per differing doc"
    requirement: "CAT-12"
    verification:
      - kind: unit
        ref: "tests/test_wurth_to_catalog.py#test_templates_describe_the_catalog_layout"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_dry_run_shows_a_diff_for_each_doc_that_differs"
        status: pass
      - kind: integration
        ref: "tests/test_wurth_to_catalog.py#test_apply_writes_the_real_templates"
        status: pass
    human_judgment: false
  - id: D6
    description: "The conversion works on the owner's real collection and real KiCad config (the rehearsal and the live run are the owner checkpoints 17-19 and 17-20)"
    requirement: "CAT-12"
    verification: []
    human_judgment: true
    rationale: "The script was proven on synthetic repositories only; it was never run, not even as a dry run, against the owner's collection or the folder KiCad reads"

duration: 20min
completed: 2026-11-27
---

# Phase 17 Plan 09: Wurth to catalog conversion script Summary

**A one-off, dry-run-first script that removes the WurthElektronik submodule behind a verified bundle, a rollback tag and the three D-26 pass checks, moves (never deletes) the module data to a backup folder, commits once, and prints a way back that a slow test proves works offline; plus the collection README and CLAUDE.md templates for the catalog layout.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-11-27T09:59:00Z
- **Completed:** 2026-11-27T10:20:00Z
- **Tasks:** 2 (Task 1 TDD: RED then GREEN; Task 2 one commit)
- **Files modified:** 4 (all created)

## Accomplishments

- `scripts/catalog/wurth_to_catalog.py` (stdlib plus the app's catalog modules through a sys.path insert; `uri_diff` loaded with importlib): `ConversionPlan`, `plan()`, `apply()`, `rewrite_snapshot()`, `stale_var_lines()`, `doc_diff()`, `way_back()`, `_post_checks()`, `_print_way_back()`, `main()`. Exit codes 0 (done or dry run), 1 (refused, "nothing was written"), 2 (unusable input: missing `--backup-dir` or `--message` with `--apply`, unreadable snapshot, not a folder or not the repository top folder).
- Refusals before any write (both modes): not on main; tracked changes other than `.gitignore`, `catalog.json`, `README.md`, `CLAUDE.md`; untracked unignored files other than those four; no gitlink for Custom or WurthElektronik/KiCad-Library; no `.gitmodules` section; module data folder missing or shared with Custom; `catalog.json` unreadable or without the WurthElektronik entry; the clone without its own `.git` folder or with an unexpected `.git/config`; KiCad running; no KiCad config folder; `WE_3DMODEL_DIR` of the newest config not equal to the catalog path (forward slashes); the three D-26 checks; `ThirdParty` not ignored; the rollback tag already existing; backup folder inside the repository or any git work tree or already holding `pre-wurth.bundle` or `wurth-modules`; templates inside the repository.
- Apply order: `git bundle create ... --all` and `git bundle verify`; lightweight tag; `git submodule deinit -f`; `git rm -f`; remove the empty `WurthElektronik/` folder; move `.git/modules/WurthElektronik` to `<backup>/wurth-modules` (rename, copy-and-remove across drives); write the two docs; `git add` the five files; one commit. Post-checks: only Custom in `git submodule status` at its previous commit, no Wurth section in `.gitmodules`, nothing tracked under `WurthElektronik/`, `catalog.json` tracked, empty `git status`, `ThirdParty` ignored.
- Only local git commands can run: `_git` raises on anything outside `ALLOWED_GIT` (no clean, push, fetch, pull, clone, ls-remote, reset, update-ref) and on `--remote` or any `submodule` command but `deinit` and `status`; `test_only_local_git_commands_can_run` pins it.
- `scripts/catalog/collection/README.md` and `CLAUDE.md`: Custom is the only submodule, `ThirdParty/<name>/` plain downloads managed by File > Library Catalog... (`Ctrl+Shift+L`) and recorded in `catalog.json`, `WE_3DMODEL_DIR` set through the catalog, "Problem: folder missing" and Reinstall on another computer, "Adding a Third-Party Library" instead of the submodule section, the atomic rule and path-variable sections kept.

## Command lines for plans 17-19 and 17-20

Placeholders: `<main checkout>` (the collection folder KiCad reads, or the `git clone --no-local` copy for the rehearsal), `<backup folder>` (outside every repository), `<before.json>` and `<after.json>` (the `uri_diff.py snapshot` files taken before the Add and after Generate Tables), `<config base>` (only for the rehearsal: the scratch folder that holds the KiCad version folders such as 10.0).

Dry run (writes nothing; add `--config-dir <config base>` for the rehearsal):

```
env/Scripts/python.exe scripts/catalog/wurth_to_catalog.py --repo <main checkout> --before <before.json> --after <after.json> --backup-dir <backup folder>
```

Apply (after a clean dry run; the commit is made only here):

```
env/Scripts/python.exe scripts/catalog/wurth_to_catalog.py --repo <main checkout> --before <before.json> --after <after.json> --backup-dir <backup folder> --message "Replace the WurthElektronik submodule by the Library Catalog entry" --apply
```

`--rollback-tag NAME` changes the tag (default `pre-wurth-catalog`). The folders the script reads: `<main checkout>` (git state, `catalog.json`, `ThirdParty/WurthElektronik`) and the KiCad config folders (read only).

## The printed way back (dry run and after apply)

```
wurth_to_catalog: the way back (nothing here runs by itself; close KiCad first):
wurth_to_catalog:   1. move <backup folder>/wurth-modules <main checkout>/.git/modules/WurthElektronik
wurth_to_catalog:   2. git -C <main checkout> checkout pre-wurth-catalog -- .gitmodules .gitignore README.md CLAUDE.md WurthElektronik/KiCad-Library
wurth_to_catalog:   3. git -C <main checkout> submodule update --init -- WurthElektronik/KiCad-Library   (no download: the objects are local)
wurth_to_catalog:   4. commit the restored files in <main checkout>
wurth_to_catalog:   5. restore kicad_common.json from the app's backup folder (kicad_common/<version>/kicad_common.json_backup_N)
wurth_to_catalog:      or set WE_3DMODEL_DIR back in KiCad under Preferences > Configure Paths
wurth_to_catalog:   6. File > Restore Backup (Ctrl+R) in the app restores the previous library tables
wurth_to_catalog:   last resort: <backup folder>/pre-wurth.bundle holds every ref of the repository (git clone it)
```

`test_apply_then_way_back_restores_the_submodule` runs steps 1 to 3 as printed with `protocol.file.allow=never`: the submodule is back at its old commit with its files, from local objects only.

## Task Commits

1. **Task 1: the conversion script**
   - RED `4f00f81` (test) - 13 tests (7 quick, 6 slow) against an inert skeleton: all 13 fail on their planned assertions
   - GREEN `541df32` (feat)
2. **Task 2: collection doc templates** - `df95723` (feat)

**Plan metadata:** the docs commit that carries this SUMMARY.

## TDD Gate Compliance

Task 1: RED (`4f00f81`) precedes GREEN (`541df32`). The plan is `type: execute` and pytest is not a report format of the `tdd-red-evidence` classifier (same as plans 17-01 to 17-08 except where junit was used), so the classifier was not run; the RED run was read by hand (semanticAssessment): with an inert skeleton (`plan` returns an empty plan, `main` returns 0, `rewrite_snapshot` returns a copy, `way_back` returns `[]`) all 13 tests were collected, executed and failed on assertions for the planned reason (an unrewritten snapshot, no stale-version line, exit 0 where 2 was due, no module folder in the plan, the submodule still present after `apply`). The slow fixtures built the synthetic collection correctly in the RED run, so those failures are behaviour failures and not setup faults. Task 2 is not a TDD task; its tests were written with the templates and pass.

## Files Created/Modified

- `scripts/catalog/wurth_to_catalog.py` - the conversion script
- `scripts/catalog/collection/README.md` - collection README for the catalog layout
- `scripts/catalog/collection/CLAUDE.md` - collection CLAUDE.md for the catalog layout
- `tests/test_wurth_to_catalog.py` - 10 quick tests and 8 slow tests (run in process on a throwaway parent with Custom and WurthElektronik/KiCad-Library submodules, a ThirdParty clone, catalog.json, a scratch KiCad config folder and two uri_diff snapshots)

## Decisions Made

See `key-decisions` above. The module data folder choice (first segment of the submodule name) follows from git storing the module of `WurthElektronik/KiCad-Library` in `.git/modules/WurthElektronik/KiCad-Library`: moving `.git/modules/WurthElektronik` and moving it back restores the exact layout.

## Deviations from Plan

### Auto-added Issues

**1. [Rule 2 - Missing Critical] Three refusals the plan did not list**
- **Found during:** Task 1 (designing the post-checks)
- **Issue:** the post-checks require an empty `git status` and an ignored `ThirdParty`, and the tag is created before any change; if any of these were false only after the commit, the conversion would be half done with a failing check. The plan's refusal list did not cover them.
- **Fix:** `plan()` also refuses when `ThirdParty` is not ignored, when an untracked, unignored file other than `.gitignore`, `catalog.json`, `README.md`, `CLAUDE.md` exists, and when the rollback tag already exists. It also refuses when the before or after snapshot holds no Wurth entry at all, so the D-26 checks cannot pass on empty or wrong snapshots.
- **Files modified:** scripts/catalog/wurth_to_catalog.py
- **Verification:** `test_refusals` cases `untracked`, `not_ignored`, `tag_exists`, `empty_snapshots`
- **Committed in:** 541df32

---

**Total deviations:** 1 auto-added (Rule 2). **Impact on plan:** stricter refusals only; every plan truth holds as written.

## Issues Encountered

- A shell heredoc used to patch the test file halved backslashes, which turned two string literals into broken multi-line strings; the tests were rewritten without backslash escapes (`chr(10)`, `chr(92)`) and the file was re-checked before the commit.

## Known Stubs

None.

## Threat Flags

None. The script is local tooling; its trust boundaries (script to the owner's repository, snapshots to the pass checks) are the ones in the plan's threat model, mitigated by the dry-run default, the refusals, the verified bundle plus tag before any change, the allow-listed git commands, the moved module data and the KiCad-running refusal.

## User Setup Required

None - no external service configuration required. The owner runs the script in plans 17-19 (rehearsal) and 17-20 (live).

## Next Phase Readiness

- The conversion is ready for the rehearsal (17-19) and the live run (17-20). Nothing in this plan touched the owner's collection, the folder KiCad reads or the backup folder.
- Test counts: `tests/test_wurth_to_catalog.py` 10 quick (`-n 0`) and 8 slow (`--full -m slow -n 0`, about 2 min), all passing; `test_docs_split`, `test_cutover_collection` and `test_catalog_layering` still pass; `prepublish_scan` is clean for the new files.

## Self-Check: PASSED

- Created files present: scripts/catalog/wurth_to_catalog.py, scripts/catalog/collection/README.md, scripts/catalog/collection/CLAUDE.md, tests/test_wurth_to_catalog.py
- Commits on main: 4f00f81, 541df32, df95723 (3 commits measured from the ledger base f11a493)

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
