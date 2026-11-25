# Phase 15: Choose Library Folder and New Collection - Context

**Gathered:** 2026-11-23
**Status:** Ready for planning

<domain>
## Phase Boundary

The app stops assuming the library collection is the folder its own code lives in. It resolves a library folder (override, remembered choice, KiCad's `KICAD_LIB_GITHUB`, first-run window), shows it, lets the user switch (Choose library folder..., Use KiCad's folder, recent folders, open in Explorer), checks a chosen folder before use, and can create a new empty collection in which a first part imports and commits end to end. Covers ROOT-01..ROOT-12. The KiCad path variables for the chosen folder go through the existing `VAR: old -> new` confirmation. Not in this phase: the repo split and removing the legacy in-repo collection (Phase 16), the catalog and third-party clone location (Phase 17), the table model and project-local tables (Phase 18), the menu regroup (Phase 19), packaging and the freeze-tool spike (Phase 21).

</domain>

<decisions>
## Implementation Decisions

### What counts as a collection
- A folder is a library collection when it contains a `Custom/` folder that holds `Symbols/` or `Footprints/`. Choosing an empty folder offers "Create a new collection here"; choosing any other folder without that layout is refused with the reason (owner, 2026-11-23). — **Reversibility:** costly — the collection-layout rule is the contract `collection.py` exposes and that the catalog (Phase 17), the repo split (Phase 16) and the first-run window build on; loosening or tightening it later changes which folders those phases accept.

### Earlier owner decisions this phase implements (2026-11-22)
- D3: a library folder the user chose outranks KiCad's `KICAD_LIB_GITHUB` (ROOT-02).
- D4: a new collection runs `git init -b main` inside `Custom/` (Custom is its own repo; the collection root is a plain folder; `.gitkeep` in every skeleton folder; no automatic commit); the commit step shows no parent option there and still bumps the `Custom` gitlink in the owner's collection (ROOT-09).
- First-run setup can create an empty collection; recent folders and Open in Explorer are in scope.

### Decided autonomously
- [Resolve order] Q: "How the override, the chosen folder and KiCad's folder rank" → Selected: "`--library-root` command-line option over `KICAD_LIBMGR_ROOT` over the remembered folder over `KICAD_LIB_GITHUB` over the first-run window (D3)" — one resolve function in the new Qt-free collection.py
- [Settings] Q: "Where the choice is stored" → Selected: "QSettings keys `library/root` and `library/recent` (at most 10, newest first, like the Destination history), read and written only through settings.py helpers" — settings helpers can read an old key if renamed
- [Deleted folder] Q: "A remembered folder that no longer exists" → Selected: "skipped with a log line naming it; the next choice in the order is used; Recent library folders lists only folders that still exist (same rule as the Destination box)" — local rule in the resolve function and the menu builder
- [Path length] Q: "Long folder paths" → Selected: "a folder path over about 100 characters gets a warning in the folder check and the log, not a refusal (PITFALLS 12)" — one threshold constant
- [Wrong-folder rule] Q: "What the wrong-checkout (v2.0 decision 26) check compares once the folder is chosen" → Selected: "the resolved library folder against KiCad's `KICAD_LIB_GITHUB` (not the folder the app runs from); the migration's Run and Pin Atomic Libraries in KiCad still refuse, Generate and Install still warn; nothing is said when the variable is unset" — the check already takes a path argument
- [Dev worktree] Q: "Running from the Kicad_Libraries-importer worktree" → Selected: "resolves like any start (normally to KiCad's folder, the main checkout); development and UAT use `--library-root` / `KICAD_LIBMGR_ROOT`; the legacy in-repo fallback stays until Phase 16" — follows from D3; the override is the escape hatch
- [New collection files] Q: "Where `.gitignore` and README go" → Selected: "inside `Custom/` (the git repo per D4), with `.gitkeep` in each empty skeleton folder; no automatic commit" — plain text files written once
- [Menus] Q: "Where the new actions live" → Selected: "File > Choose library folder..., Use KiCad's folder, Recent library folders submenu, Open library folder in Explorer (Phase 19 regroups the menus)" — menu wiring only
- [Open in Explorer] Q: "How the folder is opened" → Selected: "QDesktopServices.openUrl(QUrl.fromLocalFile(folder)), which also works on macOS and Linux" — one call
- [Dialog modality] Q: "Blocking or not" → Selected: "the first-run window is application-modal only at startup (no main window yet); Choose library folder and New collection during use are window-modal or non-blocking per the existing dialogs (PITFALLS 29)" — a dialog flag

### Decisions after research (2026-11-23)
- KiCad path variables after a switch: offer the change even when KiCad's `KICAD_LIB_GITHUB` names another folder — the v2.0 `config.other_checkout_refused` refusal in `sync_kicad_path_vars` goes; the worktree refusal stays (reworded); Pin Atomic Libraries in KiCad and the migration's Run keep refusing; the change is always shown as `VAR: old -> new` with No as the default and is never written without Yes (owner, 2026-11-23). — **Reversibility:** costly — it changes when the app may write the owner's real KiCad config (`kicad_common.json`), a safety rule users and tests (`tests/test_kicad_config.py`) rely on.
- [auto] Busy guard for a folder switch also covers the atomic-check dialog, the chooser setup, a pending post-install step and a pending migration (orchestrator, reversible: one predicate).
- [auto] The startup folder check runs with a daemon-thread timeout of about 5 s; a folder that does not answer counts as unavailable and the next choice is used with a log line (orchestrator, reversible: one helper).
- [auto] After the first commit in a new collection the untracked `.gitkeep` / `.gitignore` / `README.md` are left to the panel's truthful "other changes stay uncommitted" hint (D4: no automatic commit); the User Guide mentions it (orchestrator, reversible: docs).

### Decisions after the automated UAT (2026-11-23)
- Destination after a library folder switch: when Destination is the old library folder or empty, it follows the new library folder; a Destination the user picked elsewhere (e.g. a KiCad project) stays (owner, 2026-11-23). — **Reversibility:** costly — it decides where Generate Tables writes after a switch; a wrong default writes one collection's tables into another.
- Main window minimum width: the real minimum of 965 px (set by the pre-existing toolbar) is accepted for Phase 15; the UI-SPEC 900 px note is amended; the toolbar is reworked with the Phase 19 menu regroup (owner, 2026-11-23).

### Claude's Discretion
- How the current library folder is shown (owner: "You decide"). Proposal: a "Library folder: <path>" line above the Symbols / Footprints lists with the full path as tooltip, plus the folder name in the window title; the planner may choose differently if the layout argues for it.
- What happens when the first-run window is closed without a choice (owner: "You decide"). Proposal: the app closes and the window returns at the next start (no empty main-window state), with a log/console line; reconsider if the planner finds an empty state cheap.
- When the KiCad path variable change is offered after a switch (owner: "You decide"). Proposal: offer it right after switching to a folder KiCad does not point at, through the existing `VAR: old -> new` confirmation and the existing KiCad-open check; Generate and Install keep offering it as today while it differs. Never written without the confirmation (ROOT-10).
- How a new collection's location is given (owner: "You decide"). Proposal: New collection asks for a parent folder plus a name and creates the folder; choosing an empty folder in Choose library folder... offers to create the collection in it. A non-empty folder, a drive root or Program Files is refused (ROOT-06).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `kicad_lib_manager/library_scanner.py::sync_kicad_path_vars(repo_root, *, config_base, backup_root, running, confirm)` sets `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` (`<root>/Custom/3DModels`) with backup, re-read and atomic replace; `MainWindow._sync_path_vars()` runs the KiCad-open check off the GUI thread and the `VAR: old -> new` confirm. Today it is called from Generate (main_window.py ~1710) and after an install (~1031, ~1067).
- `kicad_lib_manager/kicad_setup.py`: `wrong_checkout(repo_root, configured)`, `wrong_checkout_refusal`, `wrong_checkout_warning`, the wrong-checkout (v2.0 decision 26) same-folder comparison (resolved, normalised paths).
- `kicad_lib_manager/settings.py`: QSettings helpers (`load_dest_history` / `add_dest_to_history` max 10, `load_import_dir`, window geometry); new `library/*` helpers go here (all persistence through settings.py).
- Destination box rule: offers only folders that still exist; the repository folder is used when none is left — the same rule fits Recent library folders.
- Scan cache is already one file per repository folder under `%APPDATA%/KiCadExtLibManager/scan_cache/` — a switch keeps each folder's saved scan.
- Phase 14 test harness: autouse `_isolated_user_state` redirects `%APPDATA%`, `%LOCALAPPDATA%`, HOME, QSettings and `KICAD_CONFIG_HOME` and clears `KICAD_LIB_GITHUB` / `CUSTOM_3DMODEL_DIR`; `synthetic_custom` / `atomic_custom` fixtures build collections; `make_superproject` / `make_worktree` (slow) build real git shapes; the run-level app-state guard fails a run that touches real settings.

### Established Patterns
- `REPO_ROOT` is a module constant: 19 uses in the app package (main_window.py and others) and about 286 references in tests; the roadmap note puts `MainWindow(library_root)` in place of the module constant and the five test-harness seams, with the literal `Custom` (about 25 sites) moved to constants held by a layering test.
- Services return `list[Issue]` / message lists; MainWindow routes them to the log panel; long work runs in QThread workers; widgets use `blockSignals` pairs; Qt enums fully qualified.
- Commit step (`importer/commit_step.py`, `commit_plan.py`, `commit_gate.py`) assumes a parent repo with a `Custom` submodule; Phase 15 adds `parent_mode` (`none` | `gitlink`).

### Integration Points
- `kicad_lib_manager.py` entry point (argument parsing for `--library-root`), `MainWindow.__init__` (startup resolve, first-run window), File menu, scan start / rescan, Generate / Install / migration / Pin (wrong-checkout (v2.0 decision 26) checks), the import dialog's target `Custom/` paths, the commit panel's parent option.
- Scanner and scan-cache walkers must prune `.git` at any depth (a collection's `Custom/.git` and later catalog clones).
- One `run_process()` helper (`CREATE_NO_WINDOW` on Windows) for `git init` and the later subprocess runners.

</code_context>

<specifics>
## Specific Ideas

- Follow the roadmap note for Phase 15: Qt-free `collection.py` (folder-name constants, `source_of`, resolve / inspect / create), `MainWindow(library_root)`, `.git` pruning, `parent_mode`, `run_process()`, the literal `Custom` to constants with a layering test.
- PITFALLS.md 12 (path length over about 100 characters), 13 (deleted-folder rule), 14, 25, 29 (non-modal dialogs) apply.
- Research ARCHITECTURE.md collection layout: root holds `Custom/` (own repo) and later `ThirdParty/<id>/` and `catalog.json` (Phase 17 decides the clone location, D2).
- Test with the Phase 14 isolation (never the owner's real settings or KiCad config); a real-git end-to-end test of create collection → import → commit is `slow`.

</specifics>

<deferred>
## Deferred Ideas

- Removing the legacy in-repo collection fallback — Phase 16 (repo split).
- Third-party clone location and `catalog.json` — Phase 17 (D2).
- Project-local table destination — Phase 18 (TBL-03).
- Menu regroup into File / Libraries / KiCad / Help — Phase 19.
- Migration dialog timers not stopped on close (app follow-up from Phase 14) — `todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md`, not part of this phase unless the planner touches that dialog anyway.

</deferred>
