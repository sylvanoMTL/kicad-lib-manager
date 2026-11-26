---
phase: "15"
slug: "choose-library-folder-and-new-collection"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-23"
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `15-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-qt 4.5.0 + pytest-xdist 3.8.0 + pytest-timeout 2.4.0 (`qt_api = "pyside6"`, offscreen Qt) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-ra --strict-markers -n 8 --dist worksteal -m 'not slow'"`, `timeout = 300`) |
| **Quick run command** | `.\env\Scripts\python.exe -m pytest <module> -n 0 -q` (one or two targeted modules, under 30 s) — executors |
| **Full suite command** | `.\env\Scripts\python.exe -m pytest` (quick parallel, ~70 s, the GSD gate) / `.\env\Scripts\python.exe -m pytest --full` (~330 s) — orchestrator only |
| **Estimated runtime** | ~30 s per targeted run; ~70 s quick; ~330 s full |

---

## Sampling Rate

- **After every task commit:** the one or two targeted modules for that task (`-n 0`, under 30 s); a test that creates a real git repository is `@pytest.mark.slow` and is run by node id with `--full`
- **After every plan wave:** the orchestrator runs bare `pytest` (quick, ~70 s; post-merge gate)
- **Before `/gsd-verify-work`:** `pytest --full` green, plus `tests/test_docs_split.py` (was `test_docs_atomic.py` until plan 16-07) and `tests/test_help_dialog.py` after the docs plan
- **Max feedback latency:** 70 seconds (quick run)

---

## Per-Task Verification Map

Task IDs are `15-<plan>-<task>` from the plans (filled at planning, 2026-11-23); the waves are the plans' execution waves.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01, 15-12-01, 15-12-02, 15-09-02 | 15-01, 15-12, 15-09 | 1, 2, 3 | ROOT-01 | T-15-01, T-15-02 | the window never scans or writes outside the folder it was given; no `REPO_ROOT` left in `main_window.py`; legacy in-repo fallback is last | unit + AST | `pytest tests/test_startup.py tests/test_main_window_root.py tests/test_custom_literals.py tests/test_layering.py -n 0` | ✅ | ✅ green |
| 15-01-01, 15-01-02, 15-05-02, 15-10-02 | 15-01, 15-05, 15-10 | 1, 4 | ROOT-02 | T-15-01, T-15-29 | resolve order CLI > ENV > chosen > KiCad > legacy > first-run; a failing override stops the start (exit 2) instead of falling back | unit | `pytest tests/test_collection.py -k resolve tests/test_startup.py -n 0` | ✅ | ✅ green |
| 15-07-01, 15-08-01, 15-10-01 | 15-07, 15-08, 15-10 | 2, 3, 4 | ROOT-03 | T-15-20, T-15-24 | a switch rescans the new root and resets selection; refused while scan / import / atomic check / migration / path-var check / pending steps run | offscreen GUI | `pytest tests/test_main_window_root.py tests/test_choose_folder_dialog.py -n 0` | ✅ | ✅ green |
| 15-05-01, 15-07-02 | 15-05, 15-07 | 1, 2 | ROOT-04 | T-15-13 | Use KiCad's Folder enabled only when set and different; removes `library/root` | offscreen GUI + settings | `pytest tests/test_main_window_root.py tests/test_settings_library.py -n 0` | ✅ | ✅ green |
| 15-08-02, 15-10-02 | 15-08, 15-10 | 3, 4 | ROOT-05 | T-15-30, T-15-31 | first-run rows, disabled KiCad row when unset, Quit exits 0 with a stderr line | offscreen GUI | `pytest tests/test_first_run_dialog.py tests/test_startup.py -n 0` | ✅ | ✅ green |
| 15-02-02, 15-06-01, 15-06-02 | 15-02, 15-06 | 1, 2 | ROOT-06 | T-15-05, T-15-15, T-15-16, T-15-17 | skeleton contents; non-empty folder, drive root, Program Files, the app's own folder and bad names refused; cleanup after a failed create | unit (recording git runner) | `pytest tests/test_collection.py tests/test_new_collection_dialog.py -n 0` | ✅ | ✅ green |
| 15-06-01, 15-11-01 | 15-06, 15-11 | 2, 5 | ROOT-06 | T-15-18, T-15-32 | real `git init -b main` in `Custom/`, `.gitkeep` present, a first part imported and committed end to end | slow (real git) | `pytest tests/test_collection_git.py --full -n 0` | ✅ | ✅ green |
| 15-01-02, 15-08-01, 15-10-02 | 15-01, 15-08, 15-10 | 1, 3, 4 | ROOT-07 | T-15-03, T-15-25 | check rows (exists, writable, layout variants, path-length warning over 100); a deleted remembered folder falls back with the log line | unit | `pytest tests/test_collection.py tests/test_startup.py -n 0` | ✅ | ✅ green |
| 15-01-02, 15-07-02, 15-10-01 | 15-01, 15-07, 15-10 | 1, 2, 4 | ROOT-08 | T-15-04 | library-folder row text, tooltip, source tag, window title, amber mismatch tag | offscreen GUI | `pytest tests/test_main_window_root.py -n 0` | ✅ | ✅ green |
| 15-03-01, 15-03-02, 15-11-01 | 15-03, 15-11 | 1, 5 | ROOT-09 | T-15-08 | `parent_mode` probe for both shapes; the panel hides the parent widgets for `none`; the gitlink bump is unchanged for the owner's shape | slow (git) + fast panel | `pytest tests/test_commit_step.py --full -n 0`; `pytest tests/test_commit_panel.py -n 0` | ✅ | ✅ green |
| 15-04-02, 15-07-03 | 15-04, 15-07 | 1, 2 | ROOT-10 | T-15-10, T-15-21 | the path-variable change is offered after a switch only when it differs, never written without Yes, not after Use KiCad's Folder; the other-folder refusal is relaxed, the worktree refusal kept | unit + GUI | `pytest tests/test_kicad_config.py tests/test_main_window_root.py -n 0` | ✅ | ✅ green |
| 15-05-01, 15-07-01 | 15-05, 15-07 | 1, 2 | ROOT-11 | T-15-13, T-15-22 | Recent list max 10, newest first, existing folders only, `&` doubled, current checked | unit + GUI | `pytest tests/test_settings_library.py tests/test_main_window_root.py -n 0` | ✅ | ✅ green |
| 15-07-02 | 15-07 | 2 | ROOT-12 | T-15-23 | Explorer opened with the folder URL; a deleted folder logs the error line with its next step | offscreen GUI | `pytest tests/test_main_window_root.py -n 0` | ✅ | ✅ green |
| 15-02-01, 15-02-02, 15-04-01, 15-12-01, 15-12-02, 15-09-01, 15-09-02 | 15-02, 15-04, 15-12, 15-09 | 1, 2, 3 | cross | T-15-05, T-15-06, T-15-07, T-15-11, T-15-28, T-15-34 | `.git` pruned at any depth in both walkers; `subprocess` only in `procs.py` with `CREATE_NO_WINDOW`; `init` allow-listed exactly; the literal `Custom` only in `collection.py`; layering maps updated | unit / AST | `pytest tests/test_scanner_skip_dirs.py tests/test_procs.py tests/test_gitops.py tests/test_kicad_process.py tests/test_kicad_cli.py tests/test_layering.py tests/test_importer_layering.py tests/test_custom_literals.py -n 0` | ✅ | ✅ green |
| 15-13-01, 15-13-02 | 15-13 (gap 1) | 6 | ROOT-03, ROOT-07, ROOT-11 | T-15-35, T-15-36, T-15-37 | a main-window folder check (switch, Recent existence) blocked on a dead drive at close is never a live QThread: the real window in a child process exits 0 with no `QThread: Destroyed`; a late answer switches and saves nothing; results are delivered on the GUI thread | child process + offscreen GUI + unit | `pytest tests/test_exit_with_hung_check.py tests/test_background.py tests/test_main_window_root.py -n 0` | ✅ (new: test_exit_with_hung_check, test_background, hungcheckchild) | ✅ green |
| 15-14-01, 15-14-02 | 15-14 (gap 3) | 6 | ROOT-03, ROOT-06, ROOT-07 | T-15-38, T-15-39 | New Collection content never overlaps (footnote below the preview) from setup or Choose; Choose strip rows show wrapped text in full; neither dialog can be shorter than its content; default scale in process and QT_SCALE_FACTOR 1.75 in a child | offscreen geometry + child process | `pytest tests/test_dialog_geometry.py tests/test_new_collection_dialog.py tests/test_choose_folder_dialog.py -n 0` | ✅ (new: test_dialog_geometry, geometryfixtures, dialoggeometrychild) | ✅ green |
| 15-15-01, 15-15-02, 15-15-03 | 15-15 (gap 1) | 7 | ROOT-03, ROOT-05, ROOT-06, ROOT-07 | T-15-40, T-15-41, T-15-42 | Choose, first-run and New Collection checks run on daemon threads and exit 0 when blocked at close (child modes choose, first-run, new-collection); a creation is never cancelled; no folder-check module uses a QThread (AST guard); the parking helper is gone | child process + offscreen GUI + AST | `pytest tests/test_exit_with_hung_check.py tests/test_choose_folder_dialog.py tests/test_first_run_dialog.py tests/test_new_collection_dialog.py -n 0` | ✅ | ✅ green |
| 15-16-01, 15-16-02, 15-16-03 | 15-16 (gaps 2, 4) | 7 | ROOT-03, ROOT-06, ROOT-08 | T-15-43, T-15-44, T-15-45 | the real New Collection skeleton (empty `.pretty`) shows the empty page with focus on Import Part...; the saved scan carries the empty flags (format 3); after a switch the Destination follows from the old folder or a blank box and a Destination elsewhere stays | unit + offscreen GUI + docs | `pytest tests/test_empty_libraries.py tests/test_main_window_root.py tests/test_scan_cache.py tests/test_docs_split.py tests/test_help_dialog.py -n 0` (`test_docs_atomic.py` was replaced by `test_docs_split.py` in plan 16-07) | ✅ (new: test_empty_libraries) + ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_collection.py` — resolve order, `check_folder` rows, name validation, skeleton with a recording `GitContext.runner` (no real git, so not slow), cleanup, `source_of`
- [x] `tests/test_collection_git.py` (`@pytest.mark.slow`, `requires_git`) — real `create_collection`, branch `main`, `.gitkeep`, real first-part import + commit
- [x] `tests/test_startup.py` — `parse_known_args`, env, settings, KiCad config via an injected `config_base`, override failure exit code 2, stderr `None` guard
- [x] `tests/test_settings_library.py` — helpers incl. a path with a comma, a one-item list, an empty list, the 10 cap, duplicates differing in case or slashes
- [x] `tests/test_procs.py` — flags, defaults, runner injection, patched `subprocess.run` honoured, AST rule
- [x] `tests/test_main_window_root.py` — row, title, tag, switch, busy guard, recent menu, Use KiCad's Folder, Explorer, empty-state page, path-variable offer, focus target
- [x] `tests/test_new_collection_dialog.py` (15-06), `tests/test_choose_folder_dialog.py` and `tests/test_first_run_dialog.py` (15-08) — the three dialogs, one module each (planned split of the researched `test_library_root_dialogs.py`, so the dialog plans can run in their own waves)
- [x] `tests/test_custom_literals.py` (15-12 creates the walk and the importer half, 15-09 adds the rest of the package) — the AST guard that holds the literal `Custom` in `collection.py`
- [x] `tests/collectionfixtures.py` — `make_collection(tmp_path)` (skeleton without git), recording runner, `fake_check` for dialogs
- [x] Existing edits: the five harness files (`MainWindow(repo)`), `tests/test_layering.py`, `tests/test_importer_layering.py`, `tests/test_gitops.py` (`EXPECTED_ALLOWED`), `tests/test_kicad_config.py`, `tests/test_commit_step.py`, the D-26 wording tests, `tests/test_scanner_skip_dirs.py`
- [x] No framework install needed (existing infrastructure).
- [x] Gap closure (after the automated UAT, 2026-11-23): `tests/test_exit_with_hung_check.py` + `tests/hungcheckchild.py` and `tests/test_background.py` (15-13), `tests/test_dialog_geometry.py` + `tests/geometryfixtures.py` + `tests/dialoggeometrychild.py` (15-14), `tests/test_empty_libraries.py` (15-16); each plan's first task creates its own test files, so no separate Wave 0 is needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First run on a clean machine state | ROOT-05 | needs no `library/root` and no KiCad variable on a real desktop | Start the app with an empty settings folder and no `KICAD_LIB_GITHUB`; check the three rows and that Quit closes the app |
| Switch to a scratch collection and back | ROOT-03, ROOT-04, ROOT-10 | real KiCad config and real dialogs | From the main checkout: Change Folder... to a scratch collection, decline then accept the `VAR: old -> new` offer, then Use KiCad's Folder |
| New collection with a first part | ROOT-06, ROOT-09 | real Documents folder, real import and commit | New Collection in Documents, import a part, Commit, confirm no parent option is shown |
| Long path and scaling | ROOT-08 | visual | A 200-character path in the row at 900 px width; 175% display scaling |
| Disconnected network drive as remembered folder | ROOT-07 | needs a real network drive | Remember a folder on a network drive, disconnect it, start the app: the next choice is used with a log line within about 5 s |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 70s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-11-23 (validate-phase 15: all 26 modules named in the map run green together - 1003 passed with --full; full suite 12177 passed / 6 skipped at 6bdff0a; manual-only rows covered by the automated UAT in 15-UAT.md, owner sign-off 2026-11-23)

## Validation Audit 2026-11-23

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Validation Audit 2026-11-26

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |
