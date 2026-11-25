---
phase: 15-choose-library-folder-and-new-collection
verified: 2026-11-23T15:00:00Z
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
  - ".planning/phases/15-choose-library-folder-and-new-collection/15-UAT.md"
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
  - "tests/test_empty_libraries.py"
  - "tests/test_exit_with_hung_check.py"
  - "tests/test_main_window_root.py"
  - "tests/test_startup.py"
covered_digest: "v4:sha256:33c93627c477e25bf44a5058d62a3f27787516540af904857be5a138f059d37a"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "UAT test 8 (blocker): closing with a folder check blocked on a dead drive aborted the process (0xC0000409, QThread destroyed while running)"
    - "UAT test 3 (major): the empty-collection page never showed for a new collection (empty Atomic_Footprints.pretty counted as a library)"
    - "UAT test 4 (major): New Collection footnote overlapped the preview; Choose clipped a wrapped strip row"
    - "UAT test 9 (major): Destination did not follow a library folder switch"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "ROOT-01 'never on its own code folder': the legacy in-repo fallback (Source.LEGACY, the folder the app runs from) is still the last candidate when it holds a collection"
    addressed_in: "Phase 16"
    evidence: "Phase 16 Notes: 'the legacy in-repo fallback is removed'; Phase 15 ROADMAP Notes and 15-CONTEXT Deferred Ideas: 'The legacy in-repo fallback stays until Phase 16'; 15-UAT.md Notes repeat it"
  - truth: "UI-SPEC 900 px minimum main-window width: the real minimum is 965 px (973-974 native), set by the pre-existing toolbar row"
    addressed_in: "Phase 19"
    evidence: "15-UAT.md: owner accepted the real toolbar minimum on 2026-11-23, UI-SPEC amended, 'toolbar is reworked with the Phase 19 menu regroup'. Not a ROADMAP success criterion."
human_verification:
  - test: "Sign off the new UAT-COS-01 copy: decline the KiCad path-variable question after a switch while KICAD_LIB_GITHUB is unset"
    expected: "The log reads \"KiCad's KICAD_LIB_GITHUB is not set. Generate Tables and Install Part will offer the change again.\" (was \"KiCad still points at (not set).\"); with the variable set it still reads \"KiCad still points at <folder>. ...\""
    why_human: "15-REVIEW-DISPOSITION.md records this as new copy with 'owner to confirm at sign-off'; help and log copy is owner-governed (UI-SPEC)"
  - test: "Re-run the owner's automated UAT harness once at HEAD (scratchpad uat15, scenarios s7, s8 and the Destination case of s3/s9; offscreen is enough)"
    expected: "s8 exits 0 with no 'QThread: Destroyed'; a switch with a dead Destination-history entry returns at once and the dead entry drops later; real-file integrity unchanged"
    why_human: "Three code changes landed after the last UAT run (UAT re-run was at HEAD 860e05e, native pass after it): WR-08 (Destination history stat moved to a background task, marked 'fixed: requires human verification' by the fixer), WR-10 (background runner catches BaseException and a failing thread start) and the UAT-COS-01 wording. All three have new passing automated tests, including the child-process exit test, so this is a confirmation run, not a known failure."
---

# Phase 15: Choose Library Folder and New Collection Verification Report

**Phase Goal:** The app runs from any folder on a library collection it resolves or the user chooses, never on its own code folder, and a new user can create an empty collection and import and commit a first part in it
**Verified:** 2026-11-23T15:00:00Z
**Status:** human_needed
**Re-verification:** Yes, after the automated UAT, gap-closure plans 15-13..15-16 and the second code review (HEAD 6bdff0a)

## Goal Achievement

All five ROADMAP success criteria are achieved at HEAD 6bdff0a, over all 16 plans (15-01..15-12 plus the four `gap_closure: true` plans 15-13..15-16). The four gaps the automated UAT found (one blocker, three major) are closed in code, covered by new tests, and confirmed by the UAT re-runs recorded in `15-UAT.md`. No blocker and no gap remains. The status stays `human_needed` for two small items only: the new UAT-COS-01 wording needs the owner's sign-off, and three fixes made after the last UAT run (WR-08, WR-10, UAT-COS-01) were not re-run in the real-app harness.

### What I re-ran this pass

- Quick suite once: **3925 passed, 4 skipped, 82.4 s** (the same four skips: two symlink-privilege, Custom submodule not checked out, real-KiCad-config corpus).
- `pytest --full -n 0` on `tests/test_collection_git.py tests/test_exit_with_hung_check.py tests/test_dialog_geometry.py tests/test_empty_libraries.py tests/test_background.py`: **37 passed** (real git end to end, child processes that block a check past close, geometry at scale 1.0 and 1.75, empty-collection flags, background runner).
- Read the code for each gap fix (below). No GUI was started, the owner's settings and KiCad config were not touched, no background process was left, nothing was committed. The orchestrator's full run (12177 passed, 6 skipped) was taken on trust; I did not run it.

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Started outside a collection the app scans and writes only the folder it resolved, in the order `--library-root` over `KICAD_LIBMGR_ROOT`, chosen folder, `KICAD_LIB_GITHUB`, first-run prompt; the main window shows the folder | VERIFIED | Unchanged from the first pass: `build_candidates` (CLI, ENV, CHOSEN, KICAD, LEGACY) and `resolve_library_root` (startup.py:64-101, collection.py:273-307); my earlier direct probe of every ordering and the fatal bad override still stands and `tests/test_startup.py` + `tests/test_collection.py` pass in the quick run. UAT tests 1, 5, 6 (first run, dead drive, relative paths absolute) pass offscreen and native. |
| 2 | Choose library folder (refused while busy), Use KiCad's Folder, Recent, Open in Explorer; every switch rescans; the folder is checked first; a deleted remembered folder falls back with a log line | VERIFIED | `_switch_root` / `_request_switch` / `_switch_refusal` unchanged in behaviour; the folder checks now run on `widgets/background.run_in_background` (daemon thread plus GUI-thread poll), so a dead drive can neither freeze the window nor abort the exit. The Destination now follows a switch (gap 4, see below). UAT tests 2, 5, 7, 8, 9 pass. |
| 3 | First-run window with three options; a new collection gets the skeleton, `git init`, `.gitignore`, README; non-empty folder, drive root, Program Files refused | VERIFIED | Unchanged code, re-confirmed by the quick run and by the slow real-git module. UAT test 3 (new collection) now passes in full, including the empty-collection page that failed before. |
| 4 | In a new collection a first part imports and commits end to end with no parent option; in the owner's collection the commit still bumps the `Custom` gitlink | VERIFIED | `tests/test_collection_git.py --full`: 4 passed (new collection first part, root commit holds exactly the three installed files, both shapes `none` and `gitlink`). UAT test 3 also drove it through the real app: skeleton, `git init -b main`, import of the UL sample, commit panel without a parent option, three-file commit, skeleton files left untracked. |
| 5 | KiCad path variables for the chosen folder are offered through `VAR: old -> new` and never written without it | VERIFIED | `sync_kicad_path_vars` still returns without writing when `confirm` is missing or answers No. UAT test 2: No leaves `kicad_common.json` byte-identical, Yes writes both variables absolute with one backup, Use KiCad's Folder asks nothing. |

**Score:** 5/5 truths verified (0 present, behavior-unverified).

### Gap-closure verification (plans 15-13..15-16)

| UAT gap | Plan | Code evidence (read) | Test evidence (run) | Status |
|---------|------|----------------------|---------------------|--------|
| Test 8, blocker: exit abort with a check blocked on a dead drive | 15-13, 15-15 | New `widgets/background.py`: one daemon `threading.Thread` per check, outcome on a `queue.SimpleQueue`, drained by one GUI-thread `QTimer`; `cancel()` releases callbacks and abandons the thread, never joins. `grep TaskWorker\|QThread` over `choose_folder_dialog.py`, `first_run_dialog.py`, `new_collection_dialog.py`, `startup.py` finds none. The join-then-park helper and `PARKED_WORKERS` are gone. `main_window.py` keeps `TaskWorker` only for the two KiCad-open (`tasklist`, 5 s timeout) checks, which cannot block on a drive. | `tests/test_exit_with_hung_check.py` starts the app in a child process for modes `switch`, `recent`, `choose`, `first-run`, `new-collection`, blocks one check past close and asserts exit code 0 and no `QThread: Destroyed` on stderr (RED at the base was returncode 3221226505); plus an AST guard against `QThread` folder checks. All pass. UAT re-run: s8, s8b, s8c exit 0 in about 0.03 s, native pass exit 0 with no crash dialog. | VERIFIED |
| Test 3, major: empty-collection page not shown | 15-16 | `SymbolLibrary.empty` / `FootprintLibrary.empty` set by the scan (`_pretty_holds_footprint`, `_symbol_file_facts`; an unreadable folder counts as not empty); `ScanResult.holds_nothing` (models.py:135) drives `_show_list_page` and `_apply_focus` (main_window.py:969, 977); saved scan is format 3 and carries the flags, a format-2 cache is not reused. | `tests/test_empty_libraries.py` (real `create_collection` skeleton shows the page and focuses Import Part...; a skeleton with a footprint shows the trees; cache round trip; strict-bool decode). Pass. UAT s3 21/21 checks after the fix. | VERIFIED |
| Test 4, major: dialog overlap and clipped wrapped row | 15-14 | `fit_height_to_content(dialog)` sets the minimum height from `layout.totalHeightForWidth` on show, resize and every strip redraw, used by both dialogs; strip labels are `show()`n at once so the layout counts them. | `tests/test_dialog_geometry.py` (no overlapping children, no clipped wrapped label, nothing missing height, at scale 1.0 and a child process at `QT_SCALE_FACTOR` 1.75). Pass. UAT native pass at 175%: footnote below the preview, dialog fits the screen. | VERIFIED (width: see Deferred) |
| Test 9, major: Destination did not follow a switch | 15-16 (+ WR-08) | `_switch_root` computes `follow = blank or same_spelling(dest text, old root)` before the folder changes; when true it adds the new folder to the history and shows it before the scan starts, so the scan pre-selects from the tables there; a Destination elsewhere is untouched. After WR-08 the existence check of the other history entries runs on a background task (`check_exists=False` then `_prune_dest_items`), so no `Path.is_dir()` runs on the GUI thread. | `tests/test_main_window_root.py` (follow from old folder, from empty history, from blank box, Use KiCad's Folder, pre-selection, stays when elsewhere, stays when refused, no GUI-thread stat of a dead history entry). Pass. UAT test 9 pass offscreen and native. | VERIFIED |

### Code review pass 2 (15-REVIEW.md, 15-REVIEW-DISPOSITION.md)

20 findings in total: 15 fixed, 5 deferred (IN-01, IN-03, IN-05, IN-06, IN-07; all Info, none open). WR-08 (GUI-thread stat of the Destination history), WR-09 (test did not exercise the drain guard) and WR-10 (a task could stay pending after a `BaseException` or a failed thread start) are fixed with tests that fail on the pre-fix source. I read `background.py` at HEAD: `work()` catches `BaseException` and always posts an outcome, and a failing `thread.start()` decrements the counter, sets the returned event and cancels the task before re-raising. IN-04 (dead wrapper) and UAT-COS-01 (log wording) are done.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | ROOT-01 wording "never on its own code folder": the legacy fallback to the app's own folder remains the last candidate until Phase 16 removes it | Phase 16 | ROADMAP Phase 15 and Phase 16 Notes; 15-CONTEXT Deferred Ideas; 15-UAT.md Notes (the first-run window cannot show from a checkout that is itself a collection, by design; the automated run used a `git archive HEAD` copy outside any collection). New collections cannot be created inside the app folder. |
| 2 | UI-SPEC "900 px minimum width" (real minimum 965 px, set by the pre-existing toolbar row) | Phase 19 | Owner accepted it on 2026-11-23, UI-SPEC amended, toolbar rework with the Phase 19 menu regroup. It is not one of the five ROADMAP success criteria, so no override is needed. |

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `collection.py`, `startup.py`, `procs.py`, `settings.py` library helpers | VERIFIED | Unchanged from the first pass; tests green. |
| `widgets/background.py` (new, gap) | VERIFIED | Substantive (daemon thread, queue, dispatcher, cancel); used by `main_window.py` (switch check, Recent existence, Destination prune) and all three dialogs. |
| `choose_folder_dialog.py`, `first_run_dialog.py`, `new_collection_dialog.py` | VERIFIED | Checks and creation on the runner; `fit_height_to_content`; refuse close while creating. |
| `models.py`, `library_scanner.py`, `scan_cache.py` (empty flags, format 3) | VERIFIED | `holds_nothing` used by the window. |
| `tests/test_exit_with_hung_check.py`, `tests/hungcheckchild.py`, `tests/test_dialog_geometry.py`, `tests/test_empty_libraries.py`, `tests/test_background.py` | VERIFIED | Run, 37 passed with `test_collection_git.py`. |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| Dialogs and `MainWindow` folder checks | `background.run_in_background` | `_run(...)` / `_request_switch`, cancelled in `done` / `closeEvent` | WIRED |
| `closeEvent` | exit with a hung check | `cancel()` of every task, thread abandoned | WIRED (child-process test) |
| Scan flags | `_show_list_page`, `_apply_focus` | `ScanResult.holds_nothing` | WIRED |
| `_switch_root` | Destination box and history | `follow` rule, `_set_dest_items(..., check_exists=False)`, `_prune_dest_items` | WIRED |
| Switch scan end | path-variable offer | `_offer_path_vars_after_switch` -> confirm (No default) | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Status |
|----------|------|--------|--------|
| Empty-collection page | `holds_nothing` | per-library `empty` flags set by the scan from real file content, carried through the saved scan | FLOWING |
| Destination box after a switch | history list | `add_dest_to_history(new root)` plus background existence check | FLOWING |
| Library folder row, Recent menu, parent option, offered variables | as in the first pass | resolved folder, QSettings, `_parent_mode`, `kicad_common.json` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Quick suite | `env/Scripts/python.exe -m pytest -q` | 3925 passed, 4 skipped, 82.4 s | PASS |
| Gap and end-to-end modules | `pytest -q --full -n 0 tests/test_collection_git.py tests/test_exit_with_hung_check.py tests/test_dialog_geometry.py tests/test_empty_libraries.py tests/test_background.py` | 37 passed | PASS |
| Creation, refusals and resolve order (first pass, own probe, scratch folder) | direct calls into `collection` / `startup` | skeleton, `main` branch, no root `.git`, no commit; refusals and order as expected; code unchanged since | PASS (carried) |

### Probe Execution

Step 7c: SKIPPED. No `probe-*.sh` is declared by any plan.

### Requirements Coverage

All 12 IDs are claimed by at least one plan's `requirements:` (the gap plans claim ROOT-03, 05, 06, 07, 08, 11 again) and all 12 are in REQUIREMENTS.md mapped to Phase 15; none is orphaned.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| ROOT-01 | 15-01, 15-09, 15-12 | SATISFIED (legacy fallback deferred to Phase 16) | Truth 1; Deferred item 1. |
| ROOT-02 | 15-01, 15-05, 15-10 | SATISFIED | Truth 1. |
| ROOT-03 | 15-07, 15-08, 15-10, 15-11, 15-13, 15-14, 15-15, 15-16 | SATISFIED | Truth 2; UAT 2, 4, 8, 9. |
| ROOT-04 | 15-05, 15-07 | SATISFIED | Use KiCad's Folder; UAT 2. |
| ROOT-05 | 15-08, 15-10, 15-11, 15-15 | SATISFIED | First-run window; UAT 1. |
| ROOT-06 | 15-02, 15-04, 15-06, 15-09, 15-11, 15-12, 15-14, 15-15, 15-16 | SATISFIED | Truth 3 and 4; UAT 3. |
| ROOT-07 | 15-01, 15-08, 15-10, 15-13, 15-14, 15-15 | SATISFIED | Folder check, deleted-folder fallback; UAT 5, 8. |
| ROOT-08 | 15-01, 15-07, 15-10, 15-16 | SATISFIED | Title, row, tag. |
| ROOT-09 | 15-03, 15-11 | SATISFIED | Truth 4. |
| ROOT-10 | 15-04, 15-07 | SATISFIED | Truth 5; UAT 2, 6. |
| ROOT-11 | 15-05, 15-07, 15-13 | SATISFIED | Recent menu; UAT 7. |
| ROOT-12 | 15-07 | SATISFIED | `QDesktopServices.openUrl`; tests. |

### Anti-Patterns Found

None blocking. No `TBD/FIXME/XXX/TODO/HACK` in the files changed by the phase (first-pass scan, re-checked on the gap files by the review pass 2).

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `.planning/REQUIREMENTS.md`, ROADMAP Phase 15 line | ROOT-01..12 still `[ ]` / Pending, phase line not ticked | Info | Bookkeeping at phase close. |
| 15-REVIEW-DISPOSITION.md | IN-01, IN-03, IN-05, IN-06, IN-07 deferred | Info | No bypass or defect in the code today; native 175% UAT shows all dialogs fit on 1920x1080. |
| `main_window._detect_kicad` | blocking `QFileDialog` from the constructor | Info | Pre-existing since v1. |

### Human verification: what 15-UAT.md covers

The earlier eight items map onto the automated UAT as follows. I checked that `15-UAT.md` records each as `pass` after the gap closure and that the scratchpad `uat15/UAT-REPORT.md` and `onscreen.txt` agree (all scenario runs exit 0, `integrity_changed: []`, `killed_strays: []`, 425 real-file entries identical before and after). I did not re-execute the harness.

| Earlier item | Covered by | Judgement |
|--------------|------------|-----------|
| 1 First run, empty settings, no `KICAD_LIB_GITHUB` | UAT test 1 | Covered (run from a `git archive` copy, since the checkout is itself a collection and the legacy fallback hides the window until Phase 16). |
| 2 Change Folder, VAR question No then Yes, Use KiCad's Folder | UAT test 2 (33/33, byte-identical file on No, backup on Yes) | Covered, against a scratch copy of `kicad_common.json`. |
| 3 New Collection, import, commit, no parent option | UAT test 3 (21/21 after the fix) | Covered. |
| 4 200-character path, 900 px, 175% | UAT test 4 | Covered except the 900 px width, accepted by the owner (Deferred item 2). |
| 5 Dead network drive at start | UAT test 5 (window up in 5.4 s, log line names the folder) | Covered. |
| 6 CR-02 relative paths | UAT test 6 (13/13) | Covered. |
| 7 WR-01 File menu with a dead Recent entry | UAT test 7 (popup 5-6 ms, entry dropped later) | Covered. |
| 8 WR-03 close during a slow check | UAT test 8, after 15-13/15-15 | Covered; this was the blocker the UAT found, now exit 0 in the offscreen and native runs and in five child-process tests. |

### Human Verification Required

1. **Owner sign-off of the UAT-COS-01 copy.** After declining the path-variable question with `KICAD_LIB_GITHUB` unset, the log now reads "KiCad's KICAD_LIB_GITHUB is not set. Generate Tables and Install Part will offer the change again." The disposition file itself says "new copy, owner to confirm at sign-off". Cosmetic.
2. **One confirmation run of the UAT harness at HEAD** (scenarios s7, s8 and the Destination case; offscreen suffices). WR-08, WR-10 and UAT-COS-01 landed after the last recorded UAT run. Each has new automated tests that pass here, so I expect it to pass; the fixer marked WR-08 "requires human verification", which is why it stays listed.

### Gaps Summary

No gaps. The goal is achieved: the app resolves or is told its library folder, never silently treats its code folder as the collection except through the documented legacy fallback that Phase 16 removes, can create an empty collection, and takes a first part through import and commit there. The one blocker and three major issues found by the automated UAT are fixed and re-confirmed. The remaining items are a copy sign-off and a confirmation run, not defects.

---

_Verified: 2026-11-23T15:00:00Z_
_Verifier: Claude (gsd-verifier)_

## Human Verification Sign-off

Owner approved Phase 15 on 2026-11-23 after the automated UAT (15-UAT.md: 9/9 pass offscreen and natively at 175%; confirmation run at HEAD 6bdff0a all exit 0, real-file integrity identical) and approved the UAT-COS-01 copy ("KiCad's KICAD_LIB_GITHUB is not set. Generate Tables and Install Part will offer the change again.").
