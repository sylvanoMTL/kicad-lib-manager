---
gsd_state_version: "1.0"
milestone: v3.0
milestone_name: Public Library Manager
current_phase: 17
current_phase_name: Library Catalog
status: executing
stopped_at: Completed 17-27-PLAN.md
last_updated: "2026-11-27T18:02:50.986Z"
last_activity: 2026-11-27
last_activity_desc: Phase 17 execution started
state_head: 3f16b2f52c8e7138854f67657b4668ce16652daa
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 67
  completed_plans: 63
  percent: 38
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-26)

**Core value:** A downloaded vendor package ends up as a correctly named, correctly linked part in the right `Custom/` library (Footprint field `<Lib>:<FP>`, 3D model at `${CUSTOM_3DMODEL_DIR}/<file>.step`) without hand-editing any KiCad file.
**Current focus:** Phase 17 — Library Catalog

## Current Position

Phase: 17 (Library Catalog) — EXECUTING
Plan: 20 of 20
Status: Ready to execute
Last activity: 2026-11-27 — Phase 17 execution started

Progress: [████░░░░░░] 38%

## Performance Metrics

**Velocity:**
- Total plans completed: 221
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 6 | - | - |
| 02 | 9 | - | - |
| 03 | 10 | - | - |
| 04 | 13 | - | - |
| 05 | 11 | - | - |
| 06 | 8 | - | - |
| 07 | 13 | - | - |
| 08 | 6 | - | - |
| 09 | 9 | - | - |
| 10 | 30 | - | - |
| 11 | 17 | - | - |
| 12 | 21 | - | - |
| 13 | 28 | - | - |
| 14 | 6 | - | - |
| 15 | 16 | - | - |
| 16 | 18 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 02 P07 | 20 min | 3 tasks | 7 files |
| Phase 04 P01 | 20 min | 2 tasks | 9 files |
| Phase 04 P06 | 10 min | 2 tasks | 2 files |
| Phase 04 P07 | 14 min | 3 tasks | 2 files |
| Phase 04 P08 | 14 min | 2 tasks | 2 files |
| Phase 04 P09 | 19 min | 2 tasks | 2 files |
| Phase 04 P10 | 7min | 2 tasks | 5 files |
| Phase 08 P06 | 70 min | 3 tasks | 6 files |
| Phase 17 P01 | 45 min | 2 tasks | 8 files |
| Phase 17 P02 | 6 min | 2 tasks | 3 files |
| Phase 17 P03 | 11 min | 2 tasks | 4 files |
| Phase 17 P04 | 9 min | 2 tasks | 9 files |
| Phase 17 P05 | 12 min | 3 tasks | 9 files |
| Phase 17 P06 | 9 min | 2 tasks | 3 files |
| Phase 17 P07 | 14 min | 2 tasks | 8 files |
| Phase 17 P08 | 7 min | 2 tasks | 6 files |
| Phase 17 P09 | 20 min | 2 tasks | 4 files |
| Phase 17 P10 | 12 min | 3 tasks | 8 files |
| Phase 17 P11 | 18 min | 3 tasks | 3 files |
| Phase 17 P12 | 17 min | 2 tasks | 9 files |
| Phase 17 P13 | 22 min | 2 tasks | 5 files |
| Phase 17 P14 | 12 min | 2 tasks | 4 files |
| Phase 17 P15 | 35 min | 2 tasks | 3 files |
| Phase 17 P16 | 6 min | 2 tasks | 6 files |
| Phase 17 P21 | 62 min | 3 tasks | 14 files |
| Phase 17 P22 | 16 min | 3 tasks | 8 files |
| Phase 17 P23 | 25 min | 3 tasks | 9 files |
| Phase 17 P24 | 17 min | 3 tasks | 21 files |
| Phase 17 P25 | 19 min | 3 tasks | 10 files |
| Phase 17 P27 | 17 min | 3 tasks | 10 files |

## Accumulated Context

### Decisions

The full decision log is in the PROJECT.md Key Decisions table. The v1.0 per-phase decisions are archived with `milestones/v1.0-phases/` (summary in `milestones/v1.0-ROADMAP.md`) and the v2.0 ones with `milestones/v2.0-phases/` (summary in `milestones/v2.0-ROADMAP.md`).

- [v1.0 close]: KiCad 10 is the reference version and KiCad 9 is no longer a target (owner, 2026-10-25).
- [v2.0]: Own symbol libraries are `Atomic_<official KiCad stem>` with one shared `Atomic_Footprints`; every `Atomic_` part passes the blocking atomic rule (owner, 2026-10-25). Live migration 2026-11-12: 21 parts into 10 libraries (`Custom` bbd48c5, parent c6920f5; `Custom` tagged `pre-atomic` before it).
- [v2.0]: The app runs from the checkout KiCad reads (D-26): Generate and Install warn, the migration's Run and Pin Atomic Libraries in KiCad refuse, when `KICAD_LIB_GITHUB` names another folder.
- [v2.0]: Both checkouts on Python 3.14.4 / PySide6 6.12.0; the main checkout's 3.11 venv is kept as `env-py311`. `feature/part-importer` merged into `main` (05f9fff) on 2026-11-13; the Phase 13 close-out docs commits and this milestone close are on `feature/part-importer`.
- [v2.0 close]: Closed as override_closeout without a milestone audit; Phase 8-12 verification reports left stale after their gap plans (owner, 2026-11-13). Eight fixed debug sessions resolved against plans 10-29, 10-30, 12-21, 13-23..13-28.
- [v2.0 close]: Owner decision 2026-11-13: regroup the menus into File / Libraries / KiCad / Help (Pin under KiCad) — backlog 999.1, now MENU-01..MENU-03 in Phase 19.
- [v3.0 scoping]: A library folder the user chose outranks KiCad's `KICAD_LIB_GITHUB`; the order is `--library-root` / `KICAD_LIBMGR_ROOT` override > chosen folder > `KICAD_LIB_GITHUB` > first-run prompt (owner, 2026-11-22; ROOT-02, Phase 15).
- [v3.0 scoping]: Generate Tables writes project-local tables into the chosen KiCad project folder, never KiCad's global tables; the catalog only manages libraries in the collection (owner, 2026-11-22; TBL-03, Phase 18).
- [v3.0 scoping]: Catalog libraries are plain shallow clones plus a manifest in the collection, not git submodules; the catalog update check runs automatically at startup (owner, 2026-11-22; CAT-05, CAT-07, Phase 17).
- [v3.0 scoping]: No code signing or paid services; the installer ships unsigned and the SmartScreen warning is documented (owner, 2026-11-22; Phase 21).
- [Phase 14]: Bare `pytest` is the quick parallel run (`-n 8 --dist worksteal -m 'not slow'`, about 70 s) and `pytest --full` the full parallel run (about 330 s); measured choice from a six-setting matrix, ten full runs equal to serial (11681 passed, 6 skipped).
- [Phase 14]: No default test reads the real KiCad config (`local_kicad` opt-in via `KICAD_TEST_REAL_CONFIG=1`, per-test `KICAD_CONFIG_HOME`); a change to the app's own `%APPDATA%`/`%LOCALAPPDATA%` state fails the run, a KiCad config change only warns.
- [Phase 15]: The app resolves its library folder (override > remembered > KiCad's > legacy own folder until Phase 16 > first-run window); New Collection runs `git init -b main` in `Custom/` with no commit; the commit step's `parent_mode` (gitlink/none); the KiCad path-variable offer now covers any chosen folder (worktree refusal kept, never without Yes); Destination follows a switch when it showed the old folder.
- [Phase 15]: The manual UAT was automated (real app driven with QTest, screenshots, isolated scratch state, offscreen + native on-screen at 175%); scripts in the session scratchpad `uat15/`. Main window minimum width 965-974 px accepted until the Phase 19 toolbar rework.
- [v3.0 roadmap]: Eight phases in the owner's fixed order, one per area (14 TEST, 15 ROOT, 16 SPLIT, 17 CAT, 18 TBL, 19 MENU, 20 PY, 21 PKG). Phases 14-15 run autonomously (`/gsd-autonomous --to 15`) and are not split further; Phase 16 (repo split) is interactive. The freeze-tool spike is in Phase 21, not Phase 15.
- [Phase 16]: After three red CI runs from test timing races on GitHub's runner (not app defects) the owner chose to simplify: a green CI run no longer gates the split; the tool repo stays private until the owner flips it. The 4th run (f8c06b8) went green.
- [Phase 16]: Split done 2026-11-26: `kicad_libraries` kept as the private collection with its history (code removed in one commit); the public tool repo `kicad-lib-manager` (MIT) started from an allow-listed copy with a fresh history; both library repos private, the tool repo flipped public by the owner. KiCad tables resolve identically (428 entries, 0 missing). Fresh-clone CI 4004 passed, 1 skipped (budget 10); `corpus` / `needs_kicad` deselected with counts. `Source.LEGACY` is gone; the `Kicad_Libraries-importer` worktree is retired.
- [Phase 17]: 17-01: catalog progress callbacks receive (text, percent) with percent None until 17-03; StreamedProcess.run checks stop() after every stderr line so cancel is deterministic
- [Phase 17]: 17-02: MigrationDialog stops both timers in done() and _reap; a pending draft save runs once before _closing is set; worker starts refuse while closing (D-16 close rule for the catalog window)
- [Phase 17]: 17-03: catalog network actions refused below Git 2.32 (GIT_CONFIG_GLOBAL arrived in 2.32.0); warning below 2.49.1; addresses with user info refused before git starts
- [Phase 17]: manifest.load takes a keyword allow_file (default False): a file:// catalog entry is refused unless a test asks, so later tests that register two file:// libraries through ops must pass allow_file=True
- [Phase 17]: valid_var_name also refuses system and loader names (PATH, APPDATA, LD_*, DYLD_*, PYTHON*) and KiCad's *_HOME and KICAD_PATH names, beyond the plan list (CAT-10)
- [Phase 17]: default_id is cut to 63 characters and valid_id refuses Custom and ThirdParty, so every address GitHub allows gives a valid, unambiguous id
- [Phase 17]: Only WurthElektronik and SparkFun are CURATED; 4ms, Alternate-KiCad-Library and Espressif stay CANDIDATES until plan 17-17 passes, REJECTED is empty until 17-18
- [Phase 17]: 17-05: scanner stays catalog-free; catalog 3D variables arrive as model_vars {id: {VAR: folder}} and the confirmation takes extra_vars; scan_source/remove_source share _replace_source and match a full scan
- [Phase 17]: 17-06: validate_staging refuses in the order no libraries, KiCad 5, PCM, Git LFS, link; detect_vars takes the folder holding at least 80 percent of up to 200 sampled models, KiCad and PCM variables are counted and never mapped
- [Phase 17]: 17-07: register_add reads catalog.json before anything moves; stage_add also accepts a plain AddSource so the tracer is unchanged; sizes shown in decimal units (12 GB); needed space = curated install_mb or 6 x GitHub size + 500 MB, margin = max(500 MB, 25 %)
- [Phase 17]: 17-08: importer name search covers ThirdParty/<id> clones (label '<id>:', recursive, sorted without case, staging and dot folders skipped) plus the legacy WurthElektronik folder while it exists
- [Phase 17]: 17-08: the Wurth corpus root is ThirdParty/WurthElektronik when it exists, else the legacy folder; vendor folder name allowed only in catalog/curated.py, importer/verify.py, widgets/help_dialog.py (guard test)
- [Phase 17]: 17-09: the Wurth conversion script rewrites the before snapshot in both root spellings, moves .git/modules/WurthElektronik (first segment of the submodule name) to the backup folder, and stages catalog.json and .gitignore in the one conversion commit made only with --apply and --message
- [Phase 17]: 17-10: a failed Remove keeps the catalog entry (rename into .staging first, entry second, delete last)
- [Phase 17]: 17-10: apply_update resets only to the previewed commit and recomputes the known_dirty baseline after the reset
- [Phase 17]: 17-10: library changes of an update are compared as (kind, name) so a leaving footprint library is never hidden by a same-named symbol library
- [Phase 17]: 17-11: the catalog window's Repository link and Details heading elide (full text as tooltip) because Qt cannot break inside an unbroken word; every wrapped label ignores its text width so nothing widens the window
- [Phase 17]: 17-11: network actions in the catalog window stay disabled until the off-thread Git check answers; every slow read runs through run_in_background with a generation counter that drops late results after a close or root change
- [Phase 17]: 17-11: folder size on disk is measured off the GUI thread (CatalogServices.size_on_disk) and reads Calculating... first
- [Phase 17]: 17-12: the startup update check reads catalog.json on the GUI thread (small file) and runs net_status and check_updates on a daemon thread; each check has its own cancel event and _catalog_check_seq drops an older answer after a switch or close
- [Phase 17]: 17-12: main window gates Rescan, Generate Tables, Import Part and Migrate through one _refresh_busy_controls (scan and catalog job); _switch_refusal reads the catalog window via is_job_running, is_finishing and holds_download; catalog_model_vars is read on the scan workers and an unreadable record gives {}
- [Phase 17]: The planning step and the repository check run off the GUI thread as jobs; the final Add (record write) cannot be stopped, so a close during it is ignored with a strip line instead of the Stop the current job? question
- [Phase 17]: A waiting download is deleted on the GUI thread when the window closes; job_finished carries CatalogOutcome for the add and reinstall flows only (success, stop, refusal, failure, discard)
- [Phase 17]: Git percentage 100 switches the job strip to Checking {name}...; the Repository link on the licence page is Mono so an Add by URL address elides with its full text as tooltip
- [Phase 17]: 17-14: the catalog source rescan runs on CatalogRescanWorker(QThread), not TaskWorker (the exit guard allows two TaskWorker calls in main_window.py); an Update ticks only libraries not in the previous scan; _select_linked_footprints is not called after a catalog job
- [Phase 17]: 17-15: Update ends in a look job and an apply job; apply_update is called only from the preview's Update Library, apply_remove only from the Remove page's Remove Library (Keep Library is default, Esc and first focus; Ctrl+Return skipped)
- [Phase 17]: 17-15: a Remove that makes the row leave the list shows its result strip on the empty pane; a failed Remove keeps the entry and the row and offers Back to List
- [Phase 17]: 17-16: the catalog guide page describes the built window (Würth carry-over, Keep Library default with Esc, silent start check, manual check logs offline) and uses no deny-list word
- [Phase 17]: D-33: catalog lists KiCad's official add-on index libraries by their git links, PCM_ nicknames; fix plan before 17-18 (17-17 findings)
- [Phase 17]: 17-21: the check's file count rides the worker progress signal as (check-files, done, total), throttled to one count per whole percent; folder sizes are measured one at a time and survive a reload
- [Phase 17]: 17-21: catalog/names.py is the one name rule; an address-added library is owner/repo in every catalog line, its id stays the folder name
- [Phase 17]: 17-22: the add-on list opener is opener(request, timeout, limit); read_index never raises and offline gives the last kept copy with its date (copy file mtime, set on every successful read)
- [Phase 17]: 17-22: only urls.parse_github_url links become a download address; program repositories, other hosts, packed files and no-link packages are listed as not addable with a plain reason
- [Phase 17]: 17-23: a catalog source is shown by catalog.json's name (names.source_names) in the trees and log; per-file scan lines of a ThirdParty library are summarized one per library and kind in the log only (the scan result keeps every issue)
- [Phase 17]: 17-23: the refreshing overlay's wheel timer runs only while shown (showEvent/hideEvent), the worker sends at most one file count per whole percent
- [Phase 17]: Name rule (17-24): over every symbol file, links to the download's own footprint libraries count as plain by exact stem or PCM_ by PCM_+stem; more PCM_ gives PCM_, more plain gives none, a tie gives the caller's default (none for a web address, PCM_ for KiCad's add-on list); curated sources and Reinstall fix it
- [Phase 17]: catalog.json records name, nickname_prefix and addon_id per library; display_name uses the recorded name first; Update, Remove and the scan name libraries with the prefix
- [Phase 17]: 3D models on a *_3RD_PARTY variable are counted apart from KiCad's other own variables and reported; the catalog never sets, reads or lists KiCad's add-on folder, installed_packages.json or settings
- [Phase 17]: 17-25: a library of KiCad's add-on list is one row (curated wins on repository key; a recorded library takes its listing by add-on id, else repository); Add from the list runs the same GitHub check, licence page, download check and preview; the line about KiCad's list is hidden on review pages
- [Phase 17]: 17-27: scratch switch --scratch-root / KICAD_LIBMGR_SCRATCH_ROOT (command line wins) puts settings, backups and KiCad's settings under PATH/settings, PATH/backups, PATH/kicad; bad value exits 2 with a reason, no fallback

### Pending Todos

- Stop the migration dialog's draft and rebuild timers when it closes — `todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md` (app follow-up from the Phase 14 worker-crash debug session; not observed in the app).

### Blockers/Concerns

- [Phase 16]: Code review closed 2026-11-26 (16-REVIEW-DISPOSITION.md: 39 of 39 fixed). Round 1: CR-01, CR-02, WR-01..WR-20 (fix report in a705743). Round 2, a re-review of the fix changes: WR-21..WR-23 and IN-01..IN-14 (16-REVIEW-FIX.md). The pre-publish scan treats placeholder user folders (bob, alice, user, username, <user>, <username>, <name>) as samples, matched on the whole folder name. `cutover_collection.py --apply` needs `--pre-split-tag` (a tag, not a branch); `build_tool_repo.py` needs `--allow-any-email` for a non-noreply address; `sync_planning.py --since` must be the previous sync's `--ref`; the pre-push hook refuses without `prepublish.denyTermsFile` unless `PREPUBLISH_ALLOW_NO_DENY_LIST=1`.
- [Phase 20]: `tests/test_isolation.py` imports `tomllib` at module level, so it cannot be collected on Python 3.10 (noted by the Phase 16 fixer); moot once 3.14 is the minimum.
- [Phase 15]: D4 decided by the owner 2026-11-22: a new collection runs `git init -b main` inside `Custom/` (Custom is its own repo, the collection root is a plain folder, no parent option in the commit step).

None block Phase 17. Open, non-blocking:

- [Phase 16]: UI review (16-UI-REVIEW.md, 6/8 on the two touched pillars): the `set by --library-root` / `set by KICAD_LIBMGR_ROOT` tags are documented by design; `MainWindow(source=...)` defaults silently to `Source.CHOSEN`; no log line says why a checkout that is itself a collection now gets the first-run window.
- [Phase 15]: Review IN-01, IN-03, IN-05, IN-06, IN-07 deferred with reasons (15-REVIEW-DISPOSITION.md)

- [Phase 14]: Review IN-01..IN-05 deferred with reasons (14-REVIEW-DISPOSITION.md); WR-01..WR-04 fixed

- [Phase 10]: Review findings (10-REVIEW-DISPOSITION.md): WR-01 unlocked shared caches in footprint_index/siblings, WR-03 unvalidated manufacturer owner chain, WR-04 unescaped vendor tooltips, IN-01..IN-06
- [Phase 11]: Review findings (11-REVIEW-DISPOSITION.md): WR-01 a kept atomic refusal line survives the Check again after Open Check Atomic Parts fixes (one-line fix: `CommitPanel.forget_refusal()` from `_on_atomic_fixes_applied`); IN-01..IN-03
- [Phase 12]: Review findings (12-REVIEW-DISPOSITION.md); Phase 10 follow-up kept in 10-UAT.md: a log panel inside the import dialog
- [Phase 13]: UI review advisory items (13-UI-REVIEW.md, 16/24): accessible names on icon-only controls, User Guide wording, spacing of the new windows not rendered
- [Backlog]: 999.1 regroup the main-window menus (now MENU-01..MENU-03, Phase 19); 999.3 re-test the KiCad-open question from the main checkout; 999.4 Finishing strip with a real kicad-cli rebuild
- [From v1.0]: Phase 4 WR-04 deferred as REF-01 (split `build_plan`); Phase 4 IN-01/02/03/05 and Phase 5 IN-01..IN-06 not addressed. REVIEW-DISPOSITION files under `milestones/v1.0-phases/` and `milestones/v2.0-phases/`.

### Quick Tasks Completed

v1.0 quick tasks are archived in `milestones/v1.0-quick/` and v2.0 quick tasks (261027-gg7, saved scan reused at startup) in `milestones/v2.0-quick/` (see each README.md).

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 261123-lmx | Phase 15 owner-test fixes: Commit step visible without scrolling, New/Open Library Collection menu, clearer KiCad path question, override start in Recent | 2026-11-23 | 88056c4 | [261123-lmx-phase-15-owner-test-fixes-commit-step-vi](./quick/261123-lmx-phase-15-owner-test-fixes-commit-step-vi/) |
| 261123-nws | Import result page two-column layout (owner screenshot review) | 2026-11-23 | 88e1a25 | [261123-nws-import-result-page-two-column-layout](./quick/261123-nws-import-result-page-two-column-layout/) |
| 261124-c5m | Import result window shrinks to fit, Help in one place, Commit same height as Close | 2026-11-24 | daea4b2 | [261124-c5m-import-result-window-shrinks-to-fit-help](./quick/261124-c5m-import-result-window-shrinks-to-fit-help/) |

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| todos | 2026-11-13-speed-up-full-test-suite.md | (presence-only) | 2026-11-13 | v2.0 |

## Session Continuity

Last session: 2026-11-27T18:02:49.683Z
Stopped at: Completed 17-27-PLAN.md
Resume file: None

## Operator Next Steps

- Phase 17 (Library Catalog): `/gsd-discuss-phase 17` (no CONTEXT.md yet; D2, D6, D7, D11 to decide at plan time)
