---
phase: 15-choose-library-folder-and-new-collection
verified: 2026-11-26T12:00:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-01-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-01-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-02-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-02-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-03-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-03-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-04-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-04-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-05-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-05-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-06-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-06-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-07-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-07-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-08-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-08-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-09-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-09-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-10-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-10-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-11-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-11-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-12-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-12-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-13-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-13-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-14-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-14-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-15-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-15-SUMMARY.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-16-PLAN.md"
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-16-SUMMARY.md"
  - "kicad_lib_manager.py"
  - "kicad_lib_manager/collection.py"
  - "kicad_lib_manager/gitops.py"
  - "kicad_lib_manager/importer/commit_step.py"
  - "kicad_lib_manager/kicad_setup.py"
  - "kicad_lib_manager/library_scanner.py"
  - "kicad_lib_manager/main_window.py"
  - "kicad_lib_manager/models.py"
  - "kicad_lib_manager/procs.py"
  - "kicad_lib_manager/scan_cache.py"
  - "kicad_lib_manager/settings.py"
  - "kicad_lib_manager/startup.py"
  - "kicad_lib_manager/widgets/background.py"
  - "kicad_lib_manager/widgets/choose_folder_dialog.py"
  - "kicad_lib_manager/widgets/commit_panel.py"
  - "kicad_lib_manager/widgets/first_run_dialog.py"
  - "kicad_lib_manager/widgets/import_dialog.py"
  - "kicad_lib_manager/widgets/new_collection_dialog.py"
  - "tests/hungcheckchild.py"
  - "tests/test_background.py"
  - "tests/test_collection.py"
  - "tests/test_collection_git.py"
  - "tests/test_dialog_geometry.py"
  - "tests/test_docs_split.py"
  - "tests/test_empty_libraries.py"
  - "tests/test_exit_with_hung_check.py"
  - "tests/test_main_window_root.py"
  - "tests/test_startup.py"
covered_digest: "v4:sha256:54f4a86c0c74514428fd24909c7701058101c51b4144f64d56a80e863808a191"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 15: Choose Library Folder and New Collection Verification Report

**Phase Goal:** The app runs from any folder on a library collection it resolves or the user chooses, never on its own code folder, and a new user can create an empty collection and import and commit a first part in it
**Verified:** 2026-11-26T12:00:00Z
**Status:** passed
**Re-verification:** Yes. The 2026-11-23 report (passed) went stale because four covered test files changed afterwards. This pass checks that change, re-checks the behaviour Phase 16 changed, and re-runs the Phase 15 test modules at HEAD 1c34cd5 (code unchanged since 2920420; later commits touch only `.planning`).

## What changed since the last report, and why it does not regress anything

### The four test files (commit 3db4498)

`tests/test_background.py`, `tests/test_dialog_geometry.py`, `tests/test_main_window_root.py` and `tests/test_startup.py` were edited by one Phase 16 commit, "wait for the asserted state after close and on async workers (CI races)".

I diffed those four files line by line (`git show 3db4498 -U0`): 75 lines removed, 75 added, and after normalising the number in `timeout=N` the removed and added line sets are identical. Every change is a `qtbot.waitUntil` / `waitSignal` timeout raised (71 from `5000`, 3 from `10000`, 1 from `15000`, all to `30000`). No assertion, fixture, test name, marker or expected value changed in these four files, and no timeout was lowered. The "wait for the asserted state after close" edits the commit message mentions are in other test files, not in these four. So no assertion backing a ROOT requirement was weakened. No app code, pytest config or CI file was touched by the commit.

### Phase 16 behaviour changes judged against Phase 15

- **Legacy own-folder fallback removed (ROOT-01, ROOT-02).** `kicad_lib_manager/collection.py` `Source` now has only `CLI`, `ENV`, `CHOSEN`, `KICAD`; `grep LEGACY` finds nothing in the app code (only the unrelated `LEGACY_EXTENSIONS` of the vendor importer). `build_candidates` (startup.py:64) and `resolve_library_root` (collection.py:273) implement the order `--library-root`, `KICAD_LIBMGR_ROOT`, the remembered choice, KiCad's `KICAD_LIB_GITHUB`, else the first-run window; a failing CLI or ENV candidate is fatal with no fallback, a failing CHOSEN or KICAD one is skipped with a note. The goal "never on its own code folder" is now met without the exception that the earlier report had deferred, so the deferred item is closed. This is the planned Phase 16 change, not a regression.
- **Menu renames (ROOT-03, ROOT-04, ROOT-11, ROOT-12).** There is no "Choose library folder..." item any more. The behaviour lives under: File > Open Library Collection... (main_window.py:109, 958), the **Change Folder...** button that runs the same window (704), File > New Library Collection... (107, 975), File > Use KiCad's Folder (664), Recent Library Collections, File > Show Library Folder in Explorer (672, `QDesktopServices.openUrl`, 679). Rename with the behaviour kept: requirements satisfied.
- **Docs test.** `tests/test_docs_atomic.py` is replaced by `tests/test_docs_split.py` (plan 16-07); it exists, is in the fingerprint, and passes.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Started from any folder, the app scans and writes only the folder it resolved, in the order CLI over ENV, chosen folder, `KICAD_LIB_GITHUB`, first-run prompt; the main window shows the folder | VERIFIED | `Source` enum without a legacy step; `build_candidates` / `resolve_library_root` read above; Library folder row, tag and `Change Folder...` in main_window.py; `tests/test_startup.py` and `tests/test_collection.py` pass (this run). |
| 2 | Open/Change Folder (refused while busy), Use KiCad's Folder, Recent, Show in Explorer; every switch rescans; the folder is checked first; a deleted remembered folder falls back with a log line | VERIFIED | `_switch_root` / `_request_switch` / `_switch_refusal` with the background folder check; `tests/test_main_window_root.py`, `tests/test_background.py`, `tests/test_exit_with_hung_check.py` pass; 15-UAT tests 2, 5, 7, 8, 9 pass. |
| 3 | First-run window with the three options; a new collection gets the skeleton, `git init` on `main`, `.gitignore`, README; non-empty folder, drive root and Program Files refused | VERIFIED | `create_collection` (collection.py:534) with `validate_collection_name` (365) and the `O_EXCL` file creation (504); `tests/test_collection.py`, `tests/test_collection_git.py` (real git, `--full`) pass; UAT 1 and 3 pass. |
| 4 | A first part imports and commits in a new collection with no parent option; in the owner's collection the commit still bumps the `Custom` gitlink | VERIFIED | `_parent_mode` (commit_step.py:188) used by the commit step (303) and `_precheck` (553); `tests/test_collection_git.py` covers both shapes `none` and `gitlink`; UAT 3 drove it through the real app. |
| 5 | KiCad path variables for the chosen folder are offered through `VAR: old -> new` and never written without confirmation | VERIFIED | `sync_kicad_path_vars` (library_scanner.py:245) writes nothing unless `confirm` answers Yes, a missing `confirm` writes nothing; UAT 2 (No leaves `kicad_common.json` byte-identical, Yes writes with one backup). |

**Score:** 5/5 truths verified (0 behavior-unverified).

### Required Artifacts and Key Links

All artifacts of the previous report still exist and are substantive: `collection.py`, `startup.py`, `procs.py`, `settings.py`, `gitops.py`, `commit_step.py`, `widgets/background.py`, the three dialogs, `models.py` / `library_scanner.py` / `scan_cache.py` (empty-collection flags). Key links unchanged and covered by tests: dialogs and `MainWindow` to `background.run_in_background`, `closeEvent` to task cancel (child-process exit test), scan flags to `_show_list_page`, `_switch_root` to the Destination box, switch-scan end to the path-variable offer. No `TBD/FIXME/XXX` marker in the phase's app files (grep over `collection.py`, `startup.py`, `gitops.py` and the new widgets: none).

### Behavioral Spot-Checks and Tests

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 15 modules incl. real git and child-process exit tests | `env/Scripts/python.exe -m pytest -q --full -p no:cacheprovider tests/test_startup.py tests/test_collection.py tests/test_main_window_root.py tests/test_background.py tests/test_dialog_geometry.py tests/test_collection_git.py tests/test_exit_with_hung_check.py tests/test_empty_libraries.py` | 302 passed in 19.6 s | PASS |
| Quick suite (orchestrator, HEAD 2920420) | `pytest -q` | 4017 passed, 3 skipped (two symlink-privilege, the real-KiCad-config opt-in), 41 corpus tests deselected with the printed count, 99.55 s | PASS (taken from the orchestrator) |
| All 25 modules of 15-VALIDATION.md's map plus docs tests (orchestrator) | `pytest --full` on those modules | 1021 passed in 155.77 s; `test_docs_split.py` + `test_help_dialog.py`: 88 passed | PASS (taken from the orchestrator) |
| Security re-audit (orchestrator) | 15-SECURITY.md | 46/46 threats closed; mitigations grep-confirmed | PASS (taken from the orchestrator) |

Probe execution (Step 7c): SKIPPED, no plan declares a `probe-*.sh`.

### Requirements Coverage

All 12 IDs are claimed by plan `requirements:` frontmatter, are `[x]` and `Complete` for Phase 15 in `.planning/REQUIREMENTS.md` (lines 22-33, 126-137), and none is orphaned.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ROOT-01 | SATISFIED | Truth 1; the legacy fallback is gone (Phase 16), so the app never runs on its own code folder. |
| ROOT-02 | SATISFIED | Truth 1 (order and fatal CLI/ENV). |
| ROOT-03 | SATISFIED (renamed) | Truth 2; Open Library Collection... / Change Folder..., refused while a scan or import runs. |
| ROOT-04 | SATISFIED | File > Use KiCad's Folder. |
| ROOT-05 | SATISFIED | First-run window; UAT 1. |
| ROOT-06 | SATISFIED | Truth 3 and 4; UAT 3. |
| ROOT-07 | SATISFIED | Folder check, deleted-folder fallback with log line; UAT 5, 8. |
| ROOT-08 | SATISFIED | Library folder row, tag and window title. |
| ROOT-09 | SATISFIED | Truth 4 (`none` and `gitlink` shapes). |
| ROOT-10 | SATISFIED | Truth 5. |
| ROOT-11 | SATISFIED | Recent Library Collections menu; UAT 7. |
| ROOT-12 | SATISFIED | Show Library Folder in Explorer. |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | UI-SPEC "900 px minimum width" (real minimum 965 px, set by the pre-existing toolbar row) | Phase 19 | Owner accepted it on 2026-11-23, UI-SPEC amended; toolbar rework with the Phase 19 menu regroup. Not a ROADMAP success criterion. |

(The earlier deferred item "legacy in-repo fallback until Phase 16" is closed: Phase 16 removed it.)

### Human Verification

None open. The two items the previous report listed (owner sign-off of the UAT-COS-01 copy, a confirmation run of the UAT harness at HEAD) are recorded as done: `15-UAT.md` has `status: complete`, all nine tests pass offscreen and natively at 175%, the confirmation run at HEAD 6bdff0a exited 0 with real-file integrity identical, and the owner approved Phase 15 and the UAT-COS-01 copy on 2026-11-23 (sign-off preserved in the history of this file). Not re-raised.

### Anti-Patterns

No blocker. Info only: IN-01, IN-03, IN-05, IN-06, IN-07 stay deferred in `15-REVIEW-DISPOSITION.md` (none a defect); `main_window._detect_kicad` still opens a blocking `QFileDialog` from the constructor (pre-existing since v1).

### Gaps Summary

No gaps. The only change to Phase 15 covered files since the last report is a set of raised wait timeouts in four test files with every assertion intact. Phase 16's removal of the legacy fallback and the menu renames keep or improve the Phase 15 requirements. The goal is achieved.

---

_Verified: 2026-11-26T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
