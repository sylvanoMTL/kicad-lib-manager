---
phase: 17-library-catalog
plan: 10
subsystem: catalog
tags: [catalog, update, remove, status, update-check, git, tdd]

requires:
  - phase: 17-library-catalog
    provides: network git runner (17-03), manifest and curated rules (17-04), staging check (17-06), Add and Reinstall ops and fake_net (17-07)
provides:
  - catalog.ops Update and Remove as plan and apply (UpdatePlan, plan_update, apply_update, RemovePlan, plan_remove, apply_remove, size_on_disk)
  - catalog.status (State, Check, UpdateState, Row, row_statuses, check_updates, updates_line, update_count, size_text)
  - validate.lfs_attributes (the one LFS attribute rule, shared by the staging check and the update check)
  - tests: quick Update/Remove and status modules, slow file:// proofs of the whole lifecycle
affects: [17-11, 17-12, 17-13, 17-15, 17-17]

plan_head_before: 315f7d5a1e9144a2fa7ed2235441c4d02c060eea
plan_head_after: 08fbcb6d92b80c57c75a2c01a14a8c1b6a8df298

actuals:
  tokens: 22900
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Update is plan then apply: the plan fetches into the object store only and records the previewed commit; apply re-checks settings, clean tree and LFS, then resets to exactly that commit"
    - "Remove is rename-first: the folder moves into ThirdParty/.staging/<id>.removing.<hex>, then the entry is removed, then the renamed folder is deleted last"
    - "Library changes are compared as (kind, name) pairs so a footprint library that leaves is not hidden by a symbol library of the same name"

key-files:
  created:
    - kicad_lib_manager/catalog/status.py
    - tests/test_catalog_ops_update.py
    - tests/test_catalog_status.py
    - tests/test_catalog_ops_git.py
  modified:
    - kicad_lib_manager/catalog/ops.py
    - kicad_lib_manager/catalog/validate.py
    - tests/catalogfixtures.py
    - tests/test_catalog_layering.py

key-decisions:
  - "A failed Remove keeps the catalog entry (rename into .staging first, entry second, delete last); a delete that fails leaves a leftover that clean_staging removes later and a catalog.remove_leftover warning"
  - "plan_update returns an Issue when it cannot look (missing folder, unexpected git settings, fetch failure) and an UpdatePlan carrying a refusal for changed files and for Git LFS, so the window can still show the changed files"
  - "apply_update on a clone already at the planned commit makes no reset and returns the success line; the entry's commit and baseline are rewritten only when they differ"
  - "After the reset the known_dirty baseline is recomputed from git status (a new commit may bring new case collisions); when the status cannot be read the old baseline stays"
  - "check_updates marks the rest UNKNOWN after the first timeout and NOT_CHECKED after a cancel; a cancelled check never claims a state it did not look up"
  - "row_statuses takes the Issue catalog.json gave (D-02) and returns every row UNKNOWN; an unlisted ThirdParty folder with a curated id is the curated row (NOT_IN_CATALOG), not a second row"

requirements-completed: [CAT-01, CAT-04, CAT-07, CAT-10, CAT-11]  # REQUIREMENTS.md boxes stay open where later plans of the phase declare the same IDs (shared-ID gate)

coverage:
  - id: D1
    description: "plan_update refuses unexpected git settings before git runs, refuses changed files with the UI-SPEC text and the file list (known_dirty baseline excluded, letter case ignored), fetches the manifest address and branch without changing any file, and previews old -> new, files changed and libraries added/removed; Git LFS in the new version is refused"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_update_preview"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_dirty_tree_refuses_with_files"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_unexpected_git_settings_refuse_before_git"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_lfs_in_new_commit_refuses"
        status: pass
    human_judgment: false
  - id: D2
    description: "apply_update re-checks the tree and the LFS rule, resets to the previewed commit only (never FETCH_HEAD or a newer remote commit), is a no-op when repeated, leaves every file unchanged when stopped before the reset, and writes the new commit and baseline to catalog.json"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_apply_update_resets_to_the_planned_sha"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_apply_update_twice_is_a_no_op"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_stopped_update_leaves_every_file_unchanged"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_ops_git.py#test_reset_uses_the_previewed_commit"
        status: pass
    human_judgment: false
  - id: D3
    description: "Remove is all-or-nothing from the user's point of view: a rename that fails keeps folder and entry, a failed save moves the folder back, a gone folder loses only its entry, an unlisted folder is deleted with no catalog change, only a direct child of ThirdParty is ever removed, KiCad's files are never touched"
    requirement: "CAT-04"
    verification:
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_remove_rename_failure_keeps_everything"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_remove_save_failure_moves_folder_back"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_remove_never_leaves_third_party"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_remove_never_touches_kicad_files"
        status: pass
    human_judgment: false
  - id: D4
    description: "row_statuses gives one row per curated, listed and unlisted library, never for .staging or dot folders, sorted by name and stable; every row is UNKNOWN when catalog.json cannot be read; a few missing 3D models never change a state"
    requirement: "CAT-01"
    verification:
      - kind: unit
        ref: "tests/test_catalog_status.py#test_rows_for_every_case"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_status.py#test_unreadable_manifest_makes_every_row_unknown"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_status.py#test_model_warnings_do_not_change_state"
        status: pass
    human_judgment: false
  - id: D5
    description: "check_updates runs one ls-remote per installed entry with a folder, never downloads or writes, gives CURRENT, AVAILABLE, BRANCH_GONE or UNKNOWN, stops after the first timeout and honours the cancel event; updates_line gives the D-19 forms"
    requirement: "CAT-07"
    verification:
      - kind: unit
        ref: "tests/test_catalog_status.py#test_check_updates_states"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_status.py#test_check_stops_after_a_timeout"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_status.py#test_check_writes_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_ops_git.py#test_check_updates_against_real_remotes"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real-git proofs (file:// only): add, update after an advance and after a force-push, dirty refusal, the case-collision baseline that keeps Update possible, LFS adopted later refused with the tree unchanged, remove, reinstall after a manual delete"
    requirement: "CAT-11"
    verification:
      - kind: integration
        ref: "tests/test_catalog_ops_git.py (9 tests, --full)"
        status: pass
    human_judgment: false
  - id: D7
    description: "Writes stay in the collection and Remove never unsets a path variable or edits a KiCad file (the edge probe's CAT-10 assumption, held by sentinel hashes; owner review at verify-work)"
    requirement: "CAT-10"
    verification:
      - kind: unit
        ref: "tests/test_catalog_ops_update.py#test_remove_never_touches_kicad_files"
        status: pass
    human_judgment: true
    rationale: "The edge probe left the meaning of 'KiCad's PCM is left alone' unclassified; the sentinel hashes prove the assumption but the owner confirms the assumption itself."

duration: 12min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 10: Update, Remove and Statuses Summary

**Update, Remove and the row statuses with the update check are Qt-free operations: an Update previews exactly what a fetch brought and resets only to that previewed commit on a clean tree, a Remove renames before it deletes so it cannot half-happen, and every row has one state, proven through a fake runner and against real local repositories.**

## Performance

- **Duration:** about 12 min
- **Started:** 2026-11-27T10:18:04Z
- **Completed:** 2026-11-27T10:30:04Z (code), SUMMARY and state follow
- **Tasks:** 3 (tasks 1 and 2 each a RED test commit then a GREEN feat commit; task 3 only adds tests plus one fix)
- **Files:** 4 created, 4 modified

## Accomplishments

- Update half of `catalog/ops.py`: `plan_update` / `apply_update`, with the clone's own git settings, the clean tree and the LFS rule all checked before anything is reset, and again at apply time.
- Remove half: `plan_remove` / `apply_remove` / `size_on_disk`, rename-first, contained to direct children of ThirdParty.
- `catalog/status.py`: states, rows, the update check and the summary line.
- 69 new quick tests (35 Update and Remove, 34 status) and 9 slow ones (about 14 s on real git).

## Fields and enums as coded (read by plans 17-11, 17-12 and 17-15)

```python
# kicad_lib_manager/catalog/ops.py
UpdatePlan(entry, name, folder, old, new, files_changed, added, removed, dirty, current, kicad_open, refusal)  # frozen
RemovePlan(id, name, folder, exists, size_bytes, nicknames, vars, listed, kicad_open)                       # frozen
def plan_update(root, entry, net, *, progress=None, cancel=None, running=kicad_process.kicad_running) -> UpdatePlan | Issue
def apply_update(root, plan, net, *, cancel=None) -> list[Issue]
def plan_remove(root, target_id, mf, *, scan=None, running=...) -> RemovePlan
def apply_remove(root, plan, *, allow_file=False) -> list[Issue]       # allow_file: tests whose catalog lists a file:// upstream
def size_on_disk(folder) -> int

# kicad_lib_manager/catalog/status.py
class State(Enum): NOT_INSTALLED, INSTALLED, UPDATE_AVAILABLE, FOLDER_MISSING, NOT_IN_CATALOG, UNKNOWN
class Check(Enum): NOT_CHECKED, CURRENT, AVAILABLE, BRANCH_GONE, UNKNOWN
UpdateState(id, check, remote_sha, checked_at)
Row(id, name, state, licence_label, licence_class, size_mb, size_text, entry, curated, folder, update)
def row_statuses(root, mf: Manifest | Issue, *, curated=CURATED, updates=None) -> list[Row]
def check_updates(root, mf, net, *, cancel=None, on_one=None, now=datetime.now) -> dict[str, UpdateState]
def update_count(states, mf) -> int
def updates_line(names) -> str | None
def size_text(mb) -> str      # 999 -> "999 MB", 1000 -> "1.0 GB", None -> "Unknown"
```

`plan_update` returns an `Issue` when it cannot look (`catalog.folder_missing`, `catalog.unexpected_settings`, git errors) and an `UpdatePlan` for everything the page can show: `current=True` (old equals new, nothing else filled), `dirty` plus `refusal` (`catalog.dirty`, nothing fetched, `new == ""`), or the preview with `refusal` set only for `catalog.lfs`. A row's name is the curated name, `owner/repo` for a library added by address, or the folder name; an unlisted folder's id is its folder name.

## Log texts as coded

| Code | Level | Text |
|------|-------|------|
| `catalog.updated` | success | `Updated {name} to {7-char commit}: {a} libraries added, {r} removed.` |
| `catalog.update_removed` | warning | `Update of {name} removed {r} libraries: {names, at most 5, then "and {m} more"}. Projects that use them lose those parts.` |
| `catalog.dirty` | error | `{name} cannot be updated: files in {folder} were changed after it was added. Catalog libraries are managed copies, and an update would overwrite your changes. Keep your own changes in Custom/ instead.` |
| `catalog.lfs` | error | `{name} cannot be updated: the new version keeps its 3D models in Git LFS, which the catalog does not support. Nothing was changed.` |
| `catalog.unexpected_settings` | error | `{name} cannot be updated: its download folder has git settings the app did not write ({up to 3 setting names}). Remove {name} and add it again.` |
| `catalog.removed` | success | `Removed {name} from the catalog. Generate Tables drops its libraries from your KiCad library tables.` (an unlisted folder: `Removed the folder {name}. Generate Tables ...`) |
| `catalog.remove_failed` | error | `Could not remove {name}: {plain reason}. Close anything that uses files in {folder}, then try again. The catalog entry was kept.` (the last sentence is left out for an unlisted folder) |
| `catalog.remove_leftover` | warning | `Part of {name} could not be deleted yet ({reason}). It is in ThirdParty/.staging and is deleted the next time the catalog starts.` |
| `catalog.record_changed` | info | the 17-07 text, added to both applies in a git repository |

`{folder}` is the folder as a forward-slash path. Not used by this plan: `catalog.current` (listed in the plan's artifact table; "already up to date" is `UpdatePlan.current`, and the window owns the `✓ {name} is already up to date.` strip).

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `e7da10e` test(17-10) | `f2b7b17` feat(17-10) |
| 2 | `49dad16` test(17-10) | `d9428be` feat(17-10) |
| 3 | `08fbcb6` test(17-10) (tests only, plus the fix below) | the fix is in the same commit |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-09); the RED runs were read by hand. Task 1: all 34 new tests (the 35th was added with the fix of task 3) failed with `AttributeError: module 'kicad_lib_manager.catalog.ops' has no attribute ...` for the planned functions (`plan_update`, `apply_update`, `plan_remove`, `apply_remove`, `size_on_disk`, `_library_names`, `UpdatePlan`); the existing ops and tracer suites (52 tests) still passed on the extended `fake_net`. Task 2: collection failed with `ImportError: cannot import name 'status'`, the planned missing module. Task 3 is slow proofs of already-built behaviour: the first run was 2 failed, 7 passed (below). No refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A leaving footprint library was hidden by a symbol library of the same name**
- **Found during:** Task 3 (`test_add_update_remove_cycle` on real git)
- **Issue:** `plan_update` compared bare library names, so removing the footprint library `Demo` while the symbol library `Demo` stayed reported nothing removed (and the "Projects that use them lose those parts" warning never showed).
- **Fix:** `_typed_names` compares (kind, name) pairs and the plan lists the distinct names; `_library_names` (a name counts once) is kept for the Remove page.
- **Files modified:** kicad_lib_manager/catalog/ops.py
- **Pinned by:** `tests/test_catalog_ops_update.py#test_library_leaving_with_a_surviving_name_is_still_reported` (quick)
- **Committed in:** 08fbcb6

**2. [Rule 3 - Blocking] Small additions outside the plan's file list**
- `kicad_lib_manager/catalog/validate.py`: `lfs_attributes(data: bytes)` extracted from the private `_holds_lfs_attr` so the update check and the staging check share one LFS rule (the plan named `ops.py` only). `_holds_lfs_attr` now calls it; behaviour unchanged (`test_catalog_validate.py` passes).
- `tests/test_catalog_layering.py`: `catalog.status` may import `catalog.urls` (a library added by address is named `owner/repo`), as that file's own header asks.
- `apply_remove` has a keyword `allow_file=False` (default keeps the plan's signature): the manifest it re-reads refuses a `file://` upstream otherwise, which the slow proofs use. `apply_update` takes it from `net.allow_file`.
- **Committed in:** f2b7b17 (validate), d9428be (layering), f2b7b17 (allow_file)

**3. [Plan note] fake_net extensions** (the plan allowed these "only if a needed answer is missing"; all keyword-only and defaulted, the 17-07 callers are unchanged): `status` may be a list (one answer per call, last repeats), `tree` may be a dict revision -> paths, `blobs` keys may be `"<rev>:<path>"` (the plan's own example form), `ls_remote` may be a dict branch -> commit with exit code 2 for a missing branch, `diff_tree` (name-status pairs) and `fetch_error`. New helper `write_git_config(folder)` writes the `.git/config` a catalog clone has, because `config_problems` refuses a clone without one.

---

**Total deviations:** 1 auto-fixed bug, 1 blocking-scope addition (three small parts), 1 note. **Impact:** no signature a later plan reads changed beyond the additions above; all must-haves hold.

## Issues Encountered

- My first fixture edit script produced a quoting error in the shell (a heredoc with nested quotes); nothing was written and I redid the edit with the editor tool. No effect on the result.
- `test_case_collision_baseline_keeps_update_possible` proves the baseline on this Windows file system (the casefolded path is recorded after the add and Update stays possible after the reset); on a case-sensitive file system the status is clean and the test checks only that Update is not refused.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model: T-17-27 (reset to the previewed commit, clean tree and LFS re-checked at apply), T-17-28 (every `.gitattributes` of the fetched tree is read through `cat-file`, nothing is checked out), T-17-29 (rename into .staging first, entry second, delete last) and T-17-30 (20 s `ls-remote` timeout from 17-03, stop after the first timeout, cancel, no download) are mitigated and tested.

## Next Phase Readiness

Plans 17-11 (window), 17-12 and 17-15 can build on the signatures above. The window decides the texts of the states; `status.py` returns states only. For a library added by address `check_updates` compares the remote with the entry's recorded commit, which every Add, Update and Reinstall writes as the clone's HEAD.

## Self-Check: PASSED

- Files found: kicad_lib_manager/catalog/ops.py, status.py, validate.py; tests/catalogfixtures.py, test_catalog_ops_update.py, test_catalog_status.py, test_catalog_ops_git.py, test_catalog_layering.py.
- Commits `e7da10e`, `f2b7b17`, `49dad16`, `d9428be`, `08fbcb6` are on main (5 commits measured from the ledger base `315f7d5`).
- Plan verification: `test_catalog_ops_update.py`, `test_catalog_ops.py`, `test_catalog_status.py`, `test_catalog_layering.py`, `test_catalog_validate.py`, `test_catalog_manifest.py`, `test_gitnet.py`, `test_annotations_resolve.py` and `test_layering.py` pass together (338); `test_catalog_ops_git.py`, `test_catalog_tracer.py` and `test_catalog_gitnet_git.py` pass with `--full` (28); acceptance greps print the expected counts (`def plan_update` 1, `def apply_remove` 1, `The catalog entry was kept.` 1, `def check_updates` 1, `def row_statuses` 1, `def test_reset_uses_the_previewed_commit` 1, `def case_collision_upstream` 1); the pre-publish scan of every changed file and the phase folder is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
