---
gsd_state_version: "1.0"
milestone: v3.0
milestone_name: Public Library Manager
current_phase: 16
current_phase_name: Repo Split
status: executing
stopped_at: Phase 16 context gathered
last_updated: "2026-11-26T14:02:45.069Z"
last_activity: 2026-11-25
last_activity_desc: Phase 16 execution resumed (wave continue)
state_head: b0058d8c87676d9c6b85d8e70db4dfd90484fe6f
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 40
  completed_plans: 40
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-23)

**Core value:** A downloaded vendor package ends up as a correctly named, correctly linked part in the right `Custom/` library (Footprint field `<Lib>:<FP>`, 3D model at `${CUSTOM_3DMODEL_DIR}/<file>.step`) without hand-editing any KiCad file.
**Current focus:** Phase 16 — Repo Split

## Current Position

Phase: 16 (Repo Split) — EXECUTING
Plan: 1 of 18
Status: Executing Phase 16
Last activity: 2026-11-25 — Phase 16 execution resumed (wave continue)

Progress: [███░░░░░░░] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 203
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

### Pending Todos

- Stop the migration dialog's draft and rebuild timers when it closes — `todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md` (app follow-up from the Phase 14 worker-crash debug session; not observed in the app).

### Blockers/Concerns

- [Phase 16]: Both GitHub repos, `sylvanoMTL/kicad_libraries` and `sylvanoMTL/kicad_custom_library`, are currently PUBLIC (verified with `gh repo view`, 2026-11-22), although CLAUDE.md and PROJECT.md describe `Custom/` as private. The visibility is decided in Phase 16 (D14, SPLIT-07). It does not block Phases 14-15.
- [Phase 15]: D4 decided by the owner 2026-11-22: a new collection runs `git init -b main` inside `Custom/` (Custom is its own repo, the collection root is a plain folder, no parent option in the commit step).

None block Phase 16 otherwise. Open, non-blocking:

- [Phase 15]: Review IN-01, IN-03, IN-05, IN-06, IN-07 deferred with reasons (15-REVIEW-DISPOSITION.md); legacy own-folder fallback (Source.LEGACY) to be removed in Phase 16; first-run window cannot appear when the app runs from a checkout that is itself a collection (by design until Phase 16)

- [Phase 14]: Review IN-01..IN-05 deferred with reasons (14-REVIEW-DISPOSITION.md); WR-01..WR-04 fixed

- [Phase 10]: Review findings (10-REVIEW-DISPOSITION.md): WR-01 unlocked shared caches in footprint_index/siblings, WR-03 unvalidated manufacturer owner chain, WR-04 unescaped vendor tooltips, IN-01..IN-06
- [Phase 11]: Review findings (11-REVIEW-DISPOSITION.md): WR-01 a kept atomic refusal line survives the Check again after Open Check Atomic Parts fixes (one-line fix: `CommitPanel.forget_refusal()` from `_on_atomic_fixes_applied`); IN-01..IN-03
- [Phase 12]: Review findings (12-REVIEW-DISPOSITION.md); Phase 10 follow-up kept in 10-UAT.md: a log panel inside the import dialog
- [Phase 13]: UI review advisory items (13-UI-REVIEW.md, 16/24): accessible names on icon-only controls, User Guide wording, spacing of the new windows not rendered
- [Backlog]: 999.1 regroup the main-window menus (now MENU-01..MENU-03, Phase 19); 999.3 re-test the KiCad-open question from the main checkout; 999.4 Finishing strip with a real kicad-cli rebuild
- [From v1.0]: Phase 4 WR-04 deferred as REF-01 (split `build_plan`); Phase 4 IN-01/02/03/05 and Phase 5 IN-01..IN-06 not addressed. REVIEW-DISPOSITION files under `milestones/v1.0-phases/` and `milestones/v2.0-phases/`.
- [Repo]: in the `Kicad_Libraries-importer` worktree the `Custom` submodule is checked out at 8f7d454 ("Added and modified some components") while the parent records d78f3f7; the gitlink bump is pending and outside the milestone close.

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

Last session: 2026-11-24T09:57:21.929Z
Stopped at: Phase 16 context gathered
Resume file: .planning/phases/16-repo-split/16-CONTEXT.md

## Operator Next Steps

- Phase 16 (repo split) is interactive: start with `/gsd-discuss-phase 16`
- Phase 16 (repo split) is interactive: `/gsd-discuss-phase 16` and step-by-step execution, not `/gsd-autonomous`
- Merge `feature/part-importer` into `main` and push the `v2.0` tag when ready (tag created locally, not pushed)
