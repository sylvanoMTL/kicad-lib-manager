# Phase 15: Choose Library Folder and New Collection - Research

**Researched:** 2026-11-23
**Domain:** PySide6 desktop app refactor: resolve and switch the library folder, create a new git-backed collection, generalise the commit step, harden the scanner and subprocess layer
**Confidence:** HIGH for the code inventory and the end-to-end feasibility (read and executed this session); MEDIUM for the dialog and threading design (a recommendation on top of approved UI-SPEC copy); two items need an owner or planner decision (Open Questions 1 and 2).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**What counts as a collection**
- A folder is a library collection when it contains a `Custom/` folder that holds `Symbols/` or `Footprints/`. Choosing an empty folder offers "Create a new collection here"; choosing any other folder without that layout is refused with the reason (owner, 2026-11-23). — **Reversibility:** costly — the collection-layout rule is the contract `collection.py` exposes and that the catalog (Phase 17), the repo split (Phase 16) and the first-run window build on; loosening or tightening it later changes which folders those phases accept.

**Earlier owner decisions this phase implements (2026-11-22)**
- D3: a library folder the user chose outranks KiCad's `KICAD_LIB_GITHUB` (ROOT-02).
- D4: a new collection runs `git init -b main` inside `Custom/` (Custom is its own repo; the collection root is a plain folder; `.gitkeep` in every skeleton folder; no automatic commit); the commit step shows no parent option there and still bumps the `Custom` gitlink in the owner's collection (ROOT-09).
- First-run setup can create an empty collection; recent folders and Open in Explorer are in scope.

**Decided autonomously**
- [Resolve order] Q: "How the override, the chosen folder and KiCad's folder rank" → Selected: "`--library-root` command-line option over `KICAD_LIBMGR_ROOT` over the remembered folder over `KICAD_LIB_GITHUB` over the first-run window (D3)" — one resolve function in the new Qt-free collection.py
- [Settings] Q: "Where the choice is stored" → Selected: "QSettings keys `library/root` and `library/recent` (at most 10, newest first, like the Destination history), read and written only through settings.py helpers" — settings helpers can read an old key if renamed
- [Deleted folder] Q: "A remembered folder that no longer exists" → Selected: "skipped with a log line naming it; the next choice in the order is used; Recent library folders lists only folders that still exist (same rule as the Destination box)" — local rule in the resolve function and the menu builder
- [Path length] Q: "Long folder paths" → Selected: "a folder path over about 100 characters gets a warning in the folder check and the log, not a refusal (PITFALLS 12)" — one threshold constant
- [Wrong-folder rule] Q: "What the D-26 check compares once the folder is chosen" → Selected: "the resolved library folder against KiCad's `KICAD_LIB_GITHUB` (not the folder the app runs from); the migration's Run and Pin Atomic Libraries in KiCad still refuse, Generate and Install still warn; nothing is said when the variable is unset" — the check already takes a path argument
- [Dev worktree] Q: "Running from the Kicad_Libraries-importer worktree" → Selected: "resolves like any start (normally to KiCad's folder, the main checkout); development and UAT use `--library-root` / `KICAD_LIBMGR_ROOT`; the legacy in-repo fallback stays until Phase 16" — follows from D3; the override is the escape hatch
- [New collection files] Q: "Where `.gitignore` and README go" → Selected: "inside `Custom/` (the git repo per D4), with `.gitkeep` in each empty skeleton folder; no automatic commit" — plain text files written once
- [Menus] Q: "Where the new actions live" → Selected: "File > Choose library folder..., Use KiCad's folder, Recent library folders submenu, Open library folder in Explorer (Phase 19 regroups the menus)" — menu wiring only
- [Open in Explorer] Q: "How the folder is opened" → Selected: "QDesktopServices.openUrl(QUrl.fromLocalFile(folder)), which also works on macOS and Linux" — one call
- [Dialog modality] Q: "Blocking or not" → Selected: "the first-run window is application-modal only at startup (no main window yet); Choose library folder and New collection during use are window-modal or non-blocking per the existing dialogs (PITFALLS 29)" — a dialog flag

### Claude's Discretion
- How the current library folder is shown (owner: "You decide"). Proposal: a "Library folder: <path>" line above the Symbols / Footprints lists with the full path as tooltip, plus the folder name in the window title; the planner may choose differently if the layout argues for it.
- What happens when the first-run window is closed without a choice (owner: "You decide"). Proposal: the app closes and the window returns at the next start (no empty main-window state), with a log/console line; reconsider if the planner finds an empty state cheap.
- When the KiCad path variable change is offered after a switch (owner: "You decide"). Proposal: offer it right after switching to a folder KiCad does not point at, through the existing `VAR: old -> new` confirmation and the existing KiCad-open check; Generate and Install keep offering it as today while it differs. Never written without the confirmation (ROOT-10).
- How a new collection's location is given (owner: "You decide"). Proposal: New collection asks for a parent folder plus a name and creates the folder; choosing an empty folder in Choose library folder... offers to create the collection in it. A non-empty folder, a drive root or Program Files is refused (ROOT-06).

(The approved `15-UI-SPEC.md` resolves all four discretion items; its "(default)" judgement calls are approved unless they conflict with CONTEXT.md. One real conflict between "as today" and the UI-SPEC copy is surfaced in Open Question 1.)

### Deferred Ideas (OUT OF SCOPE)
- Removing the legacy in-repo collection fallback — Phase 16 (repo split).
- Third-party clone location and `catalog.json` — Phase 17 (D2).
- Project-local table destination — Phase 18 (TBL-03).
- Menu regroup into File / Libraries / KiCad / Help — Phase 19.
- Migration dialog timers not stopped on close (app follow-up from Phase 14) — `todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md`, not part of this phase unless the planner touches that dialog anyway.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (REQUIREMENTS.md, verbatim) | Research Support |
|----|------------------------------------------|------------------|
| ROOT-01 | The app runs from any folder and works on the library folder it resolves, never on its own code folder | `MainWindow(library_root)` replaces the `REPO_ROOT` module constant (16 code references, 5 test harnesses); `startup.py` resolves before the window exists; legacy in-repo fallback is the last candidate only |
| ROOT-02 | The folder is resolved in this order: `--library-root` / `KICAD_LIBMGR_ROOT` override, then the folder the user chose (remembered in settings), then KiCad's `KICAD_LIB_GITHUB`, then the first-run prompt | `collection.resolve_library_root(candidates, check)` pure function; `kicad_setup.configured_library_folder()` reads `KICAD_LIB_GITHUB` from `kicad_common.json`; argparse `parse_known_args` for `--library-root` |
| ROOT-03 | User can switch folders with File > Choose library folder..., which rescans; refused while a scan or import runs | `_switch_root(path, source)` with one busy guard (scan, import, atomic dialog, migration, path-var check, chooser check, pending post-install / migration); `_start_scan()` full scan, fresh selection (`_startup_pending` re-armed) |
| ROOT-04 | User can return to KiCad's folder with "Use KiCad's folder" | `Use KiCad's Folder` action; `clear_library_root()`; enabled only when `KICAD_LIB_GITHUB` is set and differs |
| ROOT-05 | When no folder resolves, a first-run window offers: use KiCad's folder, choose an existing collection, or create a new one | `startup.py` shows `FirstRunDialog` (application-modal, before `MainWindow`); Quit exits 0 with a stderr line |
| ROOT-06 | User can create a new empty collection (`Custom/Symbols`, `Custom/Footprints/Atomic_Footprints.pretty`, `Custom/3DModels`, git init, `.gitignore`, README); a non-empty folder, a drive root or Program Files is refused; a first part can then be imported and committed in it end to end | `collection.create_collection()`; `gitops.init_repository()` (`init` added to the allow-list); real import + commit into this skeleton was executed this session and succeeded (see Codebase Inventory 8) |
| ROOT-07 | A chosen folder is checked (exists, writable, collection layout, path length); a remembered folder that was deleted falls back to the next choice with a log line | `collection.check_folder()` returning ordered rows; one `PATH_LENGTH_WARNING` constant; resolve loop skips a failing remembered folder and emits the UI-SPEC warning line |
| ROOT-08 | The current library folder is shown in the main window | Library-folder row (`ElidedLabel`, source tag, `Change Folder...`) above the toolbar, window title `{folder name} - KiCad External Lib Manager` |
| ROOT-09 | The commit step works for both collection shapes: the owner's (parent repo + `Custom` submodule, gitlink bump) and a new one with no parent (no parent option shown) | `CommitProbe.parent_mode` (`gitlink` default, `none`); `_parent_state` decides by `rev-parse --show-toplevel` plus `ls-files -s -- Custom` (mode `160000`); `CommitPanel` hides five widgets for `none` |
| ROOT-10 | KiCad path variables for the chosen folder are offered through the existing old -> new confirmation | `_sync_path_vars()` after the switch rescan ends, only when `would_change_path_vars()` is true; **`_path_var_refusal` must stop refusing a different folder (Open Question 1)** |
| ROOT-11 | Recent library folders are listed under File for one-click switching | `library/recent` helpers (max 10, newest first, display filters to existing folders); `Recent Library Folders` submenu |
| ROOT-12 | User can open the current library folder in Windows Explorer from the menu | `QDesktopServices.openUrl(QUrl.fromLocalFile(...))`, enabled even while a scan runs |
</phase_requirements>

## Summary

The work is a mechanical-but-wide refactor plus one new Qt-free domain module. Every service already takes `repo_root: Path`; the coupling is (a) one module constant `REPO_ROOT` in `main_window.py` (16 code references), (b) 24 hard-coded `"Custom"` / `"Custom/..."` string constants in 13 modules, (c) four process-start call sites in three modules that each set `CREATE_NO_WINDOW` by hand, (d) two walkers that only prune `.git` at the top level, and (e) a commit step that models a parent repo even when none exists. All of it was read this session; counts below are exact, not estimated.

The feasibility risk the roadmap worried about is retired: I created the D4 skeleton (`Custom/{Symbols,Footprints/Atomic_Footprints.pretty,3DModels}` with `.gitkeep`, `.gitignore`, `git init -b main` in `Custom/`), ran the real `build_plan` -> `apply_plan` -> `build_commit_plan` -> `probe_commit` -> `run_commit` on the Ultra Librarian sample into it, and got a successful root commit on `main` (3 files, probe state `ready`, atomic gate not refused). The only commit-step change needed is the presentation of "no parent". One hard blocker was found that the CONTEXT does not mention: `library_scanner._path_var_refusal` refuses to offer the path variables whenever `KICAD_LIB_GITHUB` names a different folder, which is exactly the case ROOT-10 and success criterion 5 are about. The planner must relax it (Open Question 1) or ROOT-10 cannot be met.

**Primary recommendation:** Build in this order, one plan owning `main_window.py` at a time: (1) Qt-free foundations (`collection.py`, `procs.py`, `gitops.init_repository`, settings helpers, `.git` pruning, `parent_mode`, literal-to-constant sweep, layering tests); (2) `MainWindow(library_root)` + `startup.py` + entry point + the five test harnesses + D-26 copy + path-variable refusal relaxation; (3) the three dialogs, the menu actions, the row, the empty state and the busy guard; (4) Help text, `CLAUDE.md`, the slow end-to-end test and UAT.

## Project Constraints (from CLAUDE.md)

Extracted from `./CLAUDE.md` and `./.claude/CLAUDE.md`; treated with the authority of locked decisions.

- **Stack:** Python 3.10+ grammar (the `tests/test_annotations_resolve.py` gate parses every module against 3.10: no PEP 695, no `except A, B:`, no f-string that reuses its own quote type), PySide6 6.12, stdlib only otherwise. No new dependency in this phase.
- **Platform:** Windows 11 primary, standard CPython (not MSYS2); keep the macOS/Linux branches working (`QDesktopServices` call is cross-platform; menu text is `...in File Manager` off Windows).
- **Safety:** no write without a preview first; writes to KiCad files and the repo must be atomic or backed up; git commits need explicit confirmation (the new collection is never committed automatically).
- **Error handling convention:** side-effecting helpers return `list[Issue]` / message lists; `MainWindow` routes them to the log panel; `QMessageBox` only for the sanctioned path-variable / chooser confirms and About (no new `QMessageBox` this phase).
- **Threading:** no scanning or filesystem-slow work on the GUI thread; long work in a `QThread` subclass (`TaskWorker` reuse for the folder check and creation).
- **Widgets:** `blockSignals(True/False)` pairs in the same function; `self._updating` guard for reentrant `itemChanged`; Qt enums fully qualified; widgets take `parent=None`.
- **Layering:** services do not import Qt except `settings.py`; `models.py` imports nothing; do not import `main_window` from lower modules; `tests/test_layering.py` pins foundation modules (`ALLOWED` map) and `tests/test_importer_layering.py` pins every importer module.
- **Persistence:** all QSettings access through `settings.py` helpers (`load_*` / `save_*` / `add_*`); keys are slash-grouped.
- **Paths:** `pathlib.Path` everywhere; `.as_posix()` for anything written to KiCad tables or compared to repo-relative strings; Windows separators normalised when writing KiCad config.
- **Message phrases are contracts:** `MainWindow` severity routing keys on literal phrases in some messages; keep `Warning:` / `removed` / `Failed` / `Could not` / `not found` stable where touched.
- **Docs:** CLAUDE.md "GUI Behavior" and the User Guide (`widgets/help_dialog.py`) describe behaviour and are asserted by `tests/test_docs_atomic.py` / `tests/test_help_dialog.py`; update them with the behaviour, then run those two modules.
- **Git workflow:** commit submodule changes separately; the dev worktree must not run imports / Generate / migration / Pin against the owner's live collection (D-26): use `--library-root` or `KICAD_LIBMGR_ROOT`.
- **GSD:** repo edits only through a GSD workflow; executors run targeted test modules only, the orchestrator runs the suites (memory: the ~9500-test full run takes ~29 min; quick `pytest` is ~70 s).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Folder-name constants, `source_of`, resolve order, folder check, create skeleton | Domain service, Qt-free (`collection.py`) | Git layer (`gitops.init_repository`) | Phases 16, 17 and 18 build on this contract; must be testable without Qt and importable by importer modules |
| Remembering the chosen folder and recent list | Settings (`settings.py`, QSettings) | — | Locked: only through `settings.py` helpers |
| Startup orchestration (argv, env, settings, KiCad config, first-run) | Entry/startup module (`startup.py`, may import Qt) | `kicad_lib_manager.py` stays thin | Convention "keep main() thin"; resolve must finish before `MainWindow` exists |
| Reading `KICAD_LIB_GITHUB` | KiCad-config service (`kicad_setup.py`) | — | Reuses `_read_config`; same Qt-free contract as `checkout_mismatch` |
| Switching, busy guard, rescan, row, menus, empty state | GUI orchestrator (`main_window.py`) | Widgets | `MainWindow` owns `self._root`; dialogs get it at construction |
| Choose / New Collection / First-run windows | GUI widgets (new modules under `widgets/`) | `TaskWorker` for off-thread check and create | UI-SPEC surfaces; no filesystem call on the GUI thread |
| Parent-repo detection (`parent_mode`) | Commit service (`importer/commit_step.py`) | `commit_panel.py` presents it | Probe decides, panel only shows |
| Process start (`CREATE_NO_WINDOW`) | New leaf `procs.py` | `gitops`, `kicad_cli`, `kicad_process` call it | One place; layering test forbids other `subprocess` starts |
| `.git` pruning | Scanner + scan cache (`library_scanner.py`, `scan_cache.py`) | — | Both walkers must agree or the saved scan goes stale |
| KiCad path variable offer | KiCad-config service (`library_scanner.sync_kicad_path_vars`) | `MainWindow._sync_path_vars` (confirm, KiCad-open check) | Existing machinery; one new read-only predicate |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`pathlib`, `os`, `argparse`, `tempfile`, `shutil`, `dataclasses`, `enum`, `subprocess`) | 3.14.4 in the venv; 3.10 grammar floor | `collection.py`, `procs.py`, `startup.py` | Project rule: stdlib only unless clearly justified [VERIFIED: `env/Scripts/python.exe` reports `3.14.4`; `.claude/CLAUDE.md` Constraints] |
| PySide6 | 6.12.0 | Dialogs, menu, `QDesktopServices`, `QStandardPaths`, `QSettings`, `QStackedLayout` | Already the only third-party dependency [VERIFIED: `import PySide6; PySide6.__version__` -> `6.12.0`] |
| git | 2.49.0.windows.1 on this machine; app floor `(2, 25)` | `git init -b main` in `Custom/` | `-b` needs git 2.28 or newer, above the app's floor: gate it (see Pitfall 7) [VERIFIED: `git --version`; `gitops.py:28`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest, pytest-qt, pytest-xdist, pytest-timeout | as pinned in `requirements-dev.txt` | Tests | Existing harness; `pyproject.toml` addopts `-ra --strict-markers -n 8 --dist worksteal -m 'not slow'` [VERIFIED: pyproject.toml read] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `argparse.parse_known_args` | Manual `sys.argv` scan | argparse gives `--library-root=PATH` and `--library-root PATH`, exit code 2 on misuse (matches UI-SPEC exit 2); `parse_known_args` leaves Qt's own switches (`-style`, `-platform`) alone |
| New `procs.py` leaf | Put `run_process` in `gitops.py` | `gitops.py` is "the only module that starts git"; `kicad_process` and `kicad_cli` must not import it. A leaf keeps `kicad_process`'s `ALLOWED = set()` shape (becomes `{"procs"}`) |
| `init` in the allow-list + `gitops.init_repository` | A separate `git init` call in `collection.py` | Would break the "gitops is the only module that starts git" invariant (`gitops.py` docstring, GIT-05); an allow-list edit is a deliberate, reviewed act and already has an exact-set test |

**Installation:** none (no new package).

**Version verification:** no package is added; `env/Scripts/python.exe -c "import PySide6, pytestqt, xdist; print(PySide6.__version__)"` printed `6.12.0`.

## Package Legitimacy Audit

No external package is installed or recommended by this phase (stdlib + the already pinned PySide6). The legitimacy gate is not applicable.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 start: kicad_lib_manager.py main()
   |
   |-- argparse.parse_known_args(argv)  --> --library-root PATH ; rest -> QApplication
   |-- env KICAD_LIBMGR_ROOT
   |-- settings.load_library_root()                      (QSettings library/root)
   |-- kicad_setup.configured_library_folder()           (kicad_common.json, KICAD_LIB_GITHUB)
   |-- legacy: APP_DIR if it is a collection             (until Phase 16)
   v
 startup.resolve(...)  --builds ordered Candidate list-->  collection.resolve_library_root(candidates, check_folder)
   |                                                           |
   |  CLI/ENV candidate fails check -----------------------> stderr line, exit 2   (no fallback)
   |  chosen candidate fails check ------------------------> warning note held for the log, try next
   |  first passing candidate -----------------------------> Resolution(root, source, notes)
   |  nothing passes --------------------------------------> FirstRunDialog (application-modal)
   |                                                              |-- Use KiCad's folder  -> check -> switch | open New Collection pre-filled
   |                                                              |-- Choose Folder...    -> ChooseLibraryFolderDialog
   |                                                              |-- New Collection...   -> NewCollectionDialog -> TaskWorker(create_collection)
   |                                                              '-- Quit / Esc / close   -> stderr line, exit 0
   v
 MainWindow(library_root, source, startup_notes)
   |-- title, row, tag, menu; notes flushed into LogPanel first
   |-- _detect_kicad ; _start_scan(reuse_cache=True)  (cache file keyed by resolved root)
   |
   |-- File > Choose... / Recent / Use KiCad's / Change Folder...
   |       -> busy guard -> TaskWorker(check_folder) -> _switch_root(path, source)
   |             save settings, title/row/menu, blank trees, scan_result=None, _startup_pending=True
   |             -> _start_scan() full  -> _on_scan_finished -> empty-state page | trees
   |             -> (if switch) would_change_path_vars? -> _sync_path_vars() -> VAR: old -> new confirm
   |
   |-- Import Part -> ImportDialog(self._root, RepoLayout.for_repo(self._root))
   |        -> apply_plan -> build_commit_plan -> probe_commit
   |              parent_mode = gitlink -> parent option as today
   |              parent_mode = none    -> parent widgets hidden
   '-- Generate / Install: write tables, D-26 check(self._root vs KICAD_LIB_GITHUB), path-var offer
```

### Recommended Project Structure
```
kicad_lib_manager/
├── collection.py            # NEW Qt-free: constants, source_of, check_folder, resolve_library_root, create_collection
├── procs.py                 # NEW Qt-free leaf: run_process()
├── startup.py               # NEW: parse_args, build candidates, resolve, first-run hand-off (may import Qt)
├── gitops.py                # + "init" in ALLOWED_SUBCOMMANDS, init_repository()
├── kicad_setup.py           # + configured_library_folder(); D-26 copy (library folder wording)
├── library_scanner.py       # .git prune, constants, would_change_path_vars(), _path_var_refusal relaxed
├── scan_cache.py            # .git prune, constants
├── settings.py              # + library/root and library/recent helpers
├── importer/commit_step.py  # + parent_mode
└── widgets/
    ├── choose_folder_dialog.py   # NEW (planner may merge the three dialogs; keep files small, import_dialog.py is 3615 lines)
    ├── new_collection_dialog.py  # NEW
    ├── first_run_dialog.py       # NEW
    └── commit_panel.py           # hide parent widgets for parent_mode == "none"
tests/
├── test_collection.py  test_collection_git.py (slow)  test_startup.py  test_settings_library.py
├── test_procs.py  test_main_window_root.py  test_library_root_dialogs.py
└── collectionfixtures.py     # NEW helpers: make_collection(), recording git runner
```

### Pattern 1: A pure resolve over an ordered candidate list
**What:** `startup.py` builds `[Candidate(path, Source.CLI), ... ]` in the locked order and hands it to `collection.resolve_library_root`, which runs the folder check on each in order and returns `Resolution(root, source, notes, fatal)`.
**When to use:** ROOT-01, ROOT-02, ROOT-07. Keeps the order, the deleted-folder rule and the override-stops-the-start rule in one tested function with no Qt, no environment and no settings access (the caller reads those).
**Rules:** a failing `CLI` or `ENV` candidate is fatal (UI-SPEC: exit 2, no fallback); a failing `CHOSEN` candidate becomes one `warning` note whose `{next}` text is only known after the loop (`KiCad's folder ({path})`, the legacy folder, or `... Choose a library folder to continue.`); a failing `KICAD` candidate is skipped with one `warning` note (not specified by CONTEXT; recommended, cheap, and the same text feeds the first-run notice); `LEGACY` is last and only added when the app's own folder passes the layout rule.

### Pattern 2: One folder check, rows as data
**What:** `check_folder(path) -> FolderCheck(rows, state, usable, can_create_here, length_chars)`; each row is `(ok: bool | None, text)` using the UI-SPEC copy verbatim; stops at the first failure; the length row never blocks. The Choose dialog, the one-click switches, the first-run row 1 and the startup resolve all consume the same object.
**When to use:** every place a folder is validated. The dialog renders `rows`; the log uses the failing row's text without its glyph (`Not using {path}: {reason}`).

### Pattern 3: Off-thread check with a request counter
**What:** the Choose dialog debounces 300 ms (`QTimer`), starts a `TaskWorker` per check, and ignores a result whose request number is not the latest (same stale-result idea as the import dialog's `session`). Never reuse a worker object; keep finished workers in a list and `wait()` them (same rule as `_path_var_workers`).
**Source:** existing pattern in `main_window.py` (`_path_var_workers`, `_on_path_var_check_finished`).

### Pattern 4: Switch as a single guarded method
`_switch_root(path, source)`: refuse when busy (one `warning` log line + 5000 ms status message), else save settings, set `self._root`, title, row, tag, menu, blank the trees, `self._scan_result = None`, re-arm `self._startup_pending = True` (so the first scan pre-selects from the Destination tables exactly as at start), set `self._offer_vars_after_scan = True` unless the source was `Use KiCad's Folder`, then `_start_scan()` (full scan, not the saved-scan shortcut). Consume the flag at the end of `_finish_scan` after the rescan, the same two-flag shape as `_generate_after_scan` / `_pending_migration`.

### Anti-Patterns to Avoid
- **Reading the folder from a module constant:** after this phase `REPO_ROOT` must not exist in `main_window.py`; tests pass the folder to the constructor.
- **A `QMessageBox` for refusals or checks:** the spec forbids new ones; use the inline strip, the log and the status bar.
- **Resolving inside `MainWindow.__init__`:** the first-run window must not run inside a constructor (the existing `_detect_kicad` blocking-modal-in-constructor anti-pattern is documented in `.claude/CLAUDE.md`).
- **`os.access(path, os.W_OK)` as the writable test on Windows:** it does not reflect ACLs reliably; probe by creating and removing a file (Pitfall 5).
- **Deleting a remembered folder from the saved list when it is missing:** display filters only; the saved list is never rewritten by a display (UI-SPEC, same as the Destination box).

## Codebase Inventory (counted this session)

### 1. `REPO_ROOT` in the app package
`kicad_lib_manager/main_window.py` is the only module. The definition is `REPO_ROOT = Path(__file__).parent.parent.resolve()` (line 46). Grep gives 19 hits: 1 definition, 1 comment (line 48), 1 docstring (line 1372) and **16 code references**:

| Class | Lines | Replace with |
|-------|-------|--------------|
| Destination fallback | 487 `items = [str(REPO_ROOT)]` | `str(self._root)` (Destination box then offers the library folder) |
| Migrate action state | 583, 1262 `migration_reason(RepoLayout.for_repo(REPO_ROOT))` | `self._root` |
| Scan and cache | 630, 631, 673, 674 (`ScanWorker`, `scan_cache_file`, `LibraryRescanWorker`) | `self._root` |
| Post-install table writes | 1023, 1047 `repo_root=REPO_ROOT` | `self._root` |
| Dialog construction | 1181-1182 `ImportDialog(REPO_ROOT, RepoLayout.for_repo(REPO_ROOT), ...)`, 1225 `AtomicCheckDialog`, 1266 `MigrationDialog(REPO_ROOT, ...)` | `self._root` |
| D-26 | 1380 `checkout_mismatch(REPO_ROOT, config_base=CHECKOUT_CONFIG_BASE)` | `self._root` |
| KiCad config writers | 1501 `sync_kicad_path_vars(REPO_ROOT, ...)`, 1586 `sync_kicad_chooser(REPO_ROOT, ...)` | `self._root` |

`ScanWorker.__init__` and `LibraryRescanWorker.__init__` already take `repo_root` as an argument, so they need no change.

### 2. The five test-harness seams
Five harness files patch the constant: `tests/test_main_window.py:78`, `tests/test_main_window_chooser.py:102`, `tests/test_main_window_import.py:97`, `tests/test_main_window_migration.py:152`, `tests/test_checkout_warning.py:84`, each `monkeypatch.setattr(main_window, "REPO_ROOT", repo)` followed by one `main_window.MainWindow()` call. [VERIFIED: grep]. Change each to `main_window.MainWindow(repo)`. The other 385 `REPO_ROOT` matches under `tests/` are unrelated per-file constants (checkout root) and must not be touched. The five module-level injection constants in `main_window.py` (`IMPORT_CORE`, `IMPORT_BACKUP_ROOT`, `ATOMIC_BACKUP_ROOT`, `CHECKOUT_CONFIG_BASE`, `MIGRATION_CORE`, lines 49-57) stay as they are; `CHECKOUT_CONFIG_BASE` keeps the D-26 check away from the real KiCad config.

### 3. Literal `"Custom"` path constants (24 hits, AST count excluding docstrings)
Exact string constants equal to `"Custom"` or starting with `"Custom/"`:
`atomic_check.py` 433, 528 (`'Custom/'`), 665; `atomic_fixes.py` 27, 28 (`'Custom/Footprints'`), 29 (`'Custom/3DModels'`); `changes.py` 25; `importer/commit_gate.py` 541; `importer/commit_step.py` 697, 872 (both are the label argument of `_not_pushed(upstream, "Custom", branch)`); `importer/incoming.py` 38; `importer/layout.py` 24; `importer/migration/gate.py` 25, 80, 215; `importer/migration/inventory.py` 307 and `importer/planner.py` 911 (message prefixes `'Custom/Symbols still holds '`, `'Custom/Footprints holds '`); `library_scanner.py` 557, 600, 914; `main_window.py` 1324; `scan_cache.py` 43, 44, 174. One site the exact-constant rule misses: `library_scanner.py:274` `"CUSTOM_3DMODEL_DIR": f"{repo_str}/Custom/3DModels",` (f-string piece `"/Custom/3DModels"`); the layering test must also inspect `JoinedStr` pieces that start with `/Custom` or `Custom/`. `importer/commit_plan.py` already derives `custom_rel` from the layout, not a literal.

Recommended `collection.py` constants: `OWN_DIR = "Custom"`, `SYMBOLS_DIR`, `FOOTPRINTS_DIR`, `MODELS_DIR`, `SHARED_FOOTPRINT_LIBRARY = "Atomic_Footprints"` (a duplicate of `importer/stems.py:79`; `stems.py` may import it from `collection`, importer modules may import `collection`), `THIRD_PARTY_DIR = "ThirdParty"` (unused until Phase 17, but `source_of` should already honour it so Phase 17 does not change the contract). Do not sweep the other folder-name literals (`"Symbols"`, `"Footprints"`, `"3DModels"`) outside `layout.py` and `collection.py` in this phase; the layering test targets `Custom` only (CONTEXT).

Layering ALLOWED edits this forces: `tests/test_layering.py` `ALLOWED` gets `"collection": {"models", "fsutil", "gitops"}` and `"procs": set()`, plus `"collection"` added to the entries of `atomic_check`, `atomic_fixes`, `changes`, `library_scanner`, `scan_cache`; `gitops` gains `"procs"`; `kicad_process` becomes `{"procs"}`; the `_CODE` import list gains `kicad_lib_manager.collection, kicad_lib_manager.procs` (the Qt-free proof). `tests/test_importer_layering.py` `ALLOWED` entries for `importer.layout`, `importer.incoming`, `importer.commit_gate`, `importer.commit_step`, `importer.migration.gate` (and `importer.kicad_cli` for `procs`) gain `"collection"` / `"procs"`.

### 4. D-26 and where the app folder is compared
`kicad_setup.py`: `wrong_checkout(repo_root, configured)` already takes the folder as an argument, so the rule needs no signature change. `checkout_mismatch(repo_root, *, config_base=None)` reads the newest `kicad_common.json` and returns `None` when the variable is unset, blank, non-string, the config is missing or unreadable (this is the locked "nothing is said when unset" rule). Copy that must change to the UI-SPEC wording: `wrong_checkout_warning` ("... this app runs from ... push them from here, then pull there."), `wrong_checkout_refusal` ("... this app runs from ..."), and the field name `CheckoutMismatch.app_folder` (rename to `library_folder` or keep; tests assert it at `tests/test_checkout_check.py:42`). Callers: `main_window._check_checkout` (1380), `widgets/migration_dialog.py:64,1628`, `kicad_setup._chooser_refusal` (Pin). Tests that assert the old wording and need updating together: `tests/test_checkout_check.py:127-131` (`push them from here, then pull there`), `tests/test_checkout_warning.py:181,249`, `tests/test_kicad_setup.py:326`, `tests/test_migration_dialog_run.py:202`, `tests/test_help_dialog.py:115-126` (`test_help_mentions_wrong_checkout` requires the word `push`), and the User Guide text at `widgets/help_dialog.py:246-255,270-272`.

### 5. Commit step and the parent repo
Quoted from `importer/commit_step.py:182-194`:
```
def _parent_state(ctx: GitContext, cplan: CommitPlan) -> tuple[bool, str, str | None, str | None]:
    root = cplan.repo_root
    top = gitops.show_toplevel(ctx, root)
    if top is None or not _same_dir(top, root):
        return False, f"no parent git repository at {root.as_posix()}", None, None
```
Today that is shown as the amber `Parent commit unavailable: ...` line (`widgets/commit_panel.py:399-401`). `CommitProbe` already carries `parent_dir`, `parent_ok`, `parent_reason`, `parent_branch`, `gitlink_old`, `earlier`. The probe sets `parent_dir=cplan.repo_root` unconditionally (`commit_step.py:295`), which is why the panel always shows `Parent repo: ...`. Widgets to hide for `none` (`widgets/commit_panel.py`): `_parent_check` (227), `_parent_label` (159), `_parent_reason` (232), `_preview_heading` and `_parent_preview` (242, 712-713), `_earlier_label` (711). `bump_parent()` (306) already returns False when the check is disabled, so a hidden, disabled, unchecked box needs no other change.

Recommended `parent_mode` rule, verified against real git: `parent_mode = "gitlink"` when `show_toplevel(root)` equals `root` **and** `git ls-files -s -- Custom` (allowed: `ls-files`) prints a `160000` entry (or `committed_gitlink` is not None); otherwise `"none"`. In the dev worktree `git --literal-pathspecs ls-files -s -- Custom` printed `160000 bbd48c5f3648e10e769840e29c72c64926a7f433 0	Custom` [VERIFIED: ran it]. Default the dataclass field to `"gitlink"` so the existing panel tests that construct `CommitProbe(...)` keep their behaviour. `_precheck` still calls `_parent_state` when `bump_parent` is True; with `none` the panel never sends `bump_parent=True`, but also refuse defensively in `_precheck`.

Existing tests that encode the old behaviour: `tests/test_commit_step.py:542` (`assert probe.parent_reason == f"no parent git repository at {loose.as_posix()}"`, slow) becomes `parent_mode == "none"`; `tests/test_commit_panel.py:564,578` build probes with `parent_ok=False, parent_dir=tmp_path`.

### 6. Every subprocess start (for `run_process()`)
`grep subprocess` in the package gives exactly four starting sites plus the import-only uses:
- `gitops.py:133` `run = ctx.runner or subprocess.run` with `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` (line 141), `stdin=subprocess.DEVNULL` or `input=`, `env=_env()`, `timeout`.
- `importer/kicad_cli.py:70` `run = runner or subprocess.run`, same `creationflags` (line 78), `text=True, errors="replace"`.
- `kicad_process.py:25` Windows `tasklist` (with `creationflags`) and `kicad_process.py:35` the POSIX `ps` call (no `creationflags`).
- `scan_cache.py:116` only mentions "no subprocess" in a docstring.

Test seams to preserve: `GitContext.runner` and `kicad_cli.run_cli(..., runner=)` take fakes called as `runner(argv, **kwargs)`; `tests/test_gitops.py:103` and `tests/test_kicad_cli.py:147` assert `kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)`; **`tests/test_kicad_process.py:30` patches the global function through the module attribute: `monkeypatch.setattr(kicad_process.subprocess, "run", _fake_run(_CSV))`**. So `procs.run_process` must look up `subprocess.run` at call time (never bind it at import), and `kicad_process` must keep `import subprocess` (it still needs `subprocess.SubprocessError`). `tests/test_atomic_scan.py:250` forbids atomic modules importing `subprocess`.

Design: `run_process(argv, *, runner=None, **kwargs)`: set `creationflags=CREATE_NO_WINDOW` (0 off Windows), default `capture_output=True`, default `stdin=DEVNULL` unless `input` is given, `runner or subprocess.run`, exceptions pass through (each caller already maps `TimeoutExpired` / `OSError` to its own `Issue`). Add an AST test: no module under `kicad_lib_manager/` other than `procs.py` calls `subprocess.run`, `.Popen`, `.call`, `.check_call`, `.check_output`; `subprocess.TimeoutExpired` / `SubprocessError` / `DEVNULL` references stay allowed. **Test-harness tripwire:** `tests/conftest.py` swaps `subprocess.Popen` per non-slow test and fails a test whose argv has command `init` or `clone` (`if command in ("init", "clone"):`), so any test that really runs `create_collection` must be `@pytest.mark.slow`; quick tests inject a recording `GitContext.runner` (the fake never reaches `Popen`).

### 7. Walkers that must prune `.git` at any depth
- `library_scanner._collect_files` uses `root.rglob(pattern)` and `find_footprint_libs` uses `root.rglob("*.pretty")`; both filter with `_in_skip_dir`, which only inspects `rel[0]` against `SKIP_DIRS = {"env", "venv", ".venv", ".git", ".claude", "__pycache__", "tests", "downloaded_examples"}`. `Custom/.git/...` (a directory in a new collection; a file in the owner's submodule) and later `ThirdParty/<id>/.git/...` are not pruned.
- `scan_cache._walk` prunes by `if skip_top and not prefix and name in SKIP_DIRS:` (line 89), also top-level only; `library_entries` calls it with `skip_top=False`.
- Other `rglob` calls (`_custom_model_names`, `atomic_check:435`, `atomic_fixes:371`, `commit_gate:423`, `layout.list_model_files`) are rooted at `Custom/3DModels` and cannot meet a `.git`.
Replace the two scanner functions with one `os.walk` helper that prunes `dirnames` named `.git` at every depth and returns the same sorted `Path` list (sort the `Path` objects, as today, so order is unchanged); add `or name == ".git"` (any depth) to `_walk`. The saved-scan fingerprint content does not change (no `.git` file matches the suffix filter), so no cache `FORMAT` bump is needed; the code-signature change causes one full scan after the update, as for any scanner edit.

### 8. The new-collection first-commit flow, executed
Run in the scratchpad with the app's own code and real git 2.49.0: skeleton as D4 (`Custom/Symbols/.gitkeep`, `Custom/Footprints/Atomic_Footprints.pretty/.gitkeep`, `Custom/3DModels/.gitkeep`, `Custom/.gitignore`), `git init -b main` in `Custom/`, repo-local identity, then `build_plan` (library `Atomic_Battery_Management`) on `downloaded_examples/ul_CSD85301Q2.zip`:
- `plan.blocked` False, `apply_plan` `ok` True (a new `Atomic_Battery_Management.kicad_sym`, `DQK0006B.kicad_mod` into the existing `Atomic_Footprints.pretty`, `CSD85301Q2.stp`).
- `probe_commit` printed state `ready`, branch `main`, `parent_ok False`, reason `no parent git repository at ...`, gate not refused.
- `run_commit(cp, "Add CSD85301Q2", False, expected_branch="main")` committed `d813478` ("3 files changed, 5262 insertions(+)") on an unborn branch; `git log --stat` listed exactly the three planned files.
- Real git on an unborn `main`: `symbolic-ref -q --short HEAD` printed `main`; `rev-parse -q --verify HEAD` exited 1 (so `head_commit` is None and `head=""`, which `_earlier` and `_identical_to_head` already treat as "no earlier commit"); `add -N` plus `commit --only -F <msg> --pathspec-from-file=- --pathspec-file-nul` produced `[main (root-commit)]`.
- After the commit `git status` still lists `?? 3DModels/.gitkeep` and `?? Symbols/.gitkeep` (and `.gitignore`, `README.md`, the pretty `.gitkeep` would too): the panel's "N other changes in Custom stay uncommitted" hint will show for a brand-new collection (Open Question 5).

### 9. How the app starts and where the cache is keyed
`kicad_lib_manager.py` is 17 lines: `app = QApplication(sys.argv)`, `window = MainWindow()`, `window.show()`, `sys.exit(app.exec())`. `--library-root` parsing goes in a new `startup.py` called from `main()` before `QApplication`'s arguments are fixed: `known, rest = parser.parse_known_args(sys.argv[1:])`, `QApplication([sys.argv[0], *rest])`. The saved scan is keyed per resolved folder: `settings.scan_cache_file(repo_root)` hashes `os.path.normcase(str(Path(repo_root).resolve()))` with sha256 to a 16-character name under `scan_cache/` beside `settings.ini`, and `scan_cache.load_fresh` additionally compares `payload["repo_root"] != _repo_key(repo_root)`. A switch therefore never mixes two folders' scans and never deletes one. `migration_draft_file` is keyed the same way.

### 10. KiCad variable plumbing the offer reuses
`sync_kicad_path_vars(repo_root, *, config_base, backup_root, running, confirm)` writes `{"KICAD_LIB_GITHUB": repo_str, "CUSTOM_3DMODEL_DIR": f"{repo_str}/Custom/3DModels"}` after the confirm (`library_scanner.py:272-275`). It logs `config.var_ok` info lines when both already match (`_plan_changes`), which the UI-SPEC says must not appear after a switch ("nothing is shown and nothing is logged"); add a side-effect-free `would_change_path_vars(repo_root, *, config_base=None) -> bool` (read config with `_read_config`, `_plan_changes`, return `bool(changes)`; False on a missing dir, missing file or unreadable file) and gate the post-switch offer on it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Command-line option | Manual `sys.argv` loop | `argparse.ArgumentParser(add_help=False).parse_known_args` | `--x=y` and `--x y` forms, exit code 2 on misuse, Qt's own flags pass through |
| Atomic write of config or files | New write helper | `fsutil.atomic_write_text` / `atomic_write_bytes` / `backup_file` | Existing, backed-up, atomic (project Safety rule); the new collection's few files are all new files, so a plain write inside the freshly created folder is acceptable but cleanup must remove them |
| Process start | Per-module `subprocess.run` | `procs.run_process` | One place for `CREATE_NO_WINDOW`; AST test enforces |
| Off-thread work | New `QThread` subclass | `TaskWorker` (`widgets/import_dialog.py:343`, signals `result` / `failed`) | Already used for the KiCad-open check; keeps the `finished` signal unshadowed |
| Middle-elided path label | A second elision widget | `ElidedLabel` (`widgets/import_result.py:26`, `set_full_text`, `mode=`, `full_tooltip=True`) | UI-SPEC requirement |
| Dialog centring | Custom geometry code | `centre_window` (`import_dialog.py:195`) | Existing, screen-aware |
| Same-folder comparison | `==` on strings | `kicad_setup.same_folder` (resolved, `normpath`, `normcase`) | Windows case and separator rules; already used by D-26 |
| Opening the folder | `os.startfile` / `subprocess explorer` | `QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))` | Locked decision; cross-platform; no new process site |
| Windows file-name validation | Ad-hoc checks | One `validate_collection_name()` implementing the Microsoft rules (below) | Reserved names, trailing space or period, superscript digits |
| Read-only `.git` cleanup on failure | Plain `shutil.rmtree` | `rmtree` with an `onexc` / `onerror` that clears the read-only bit (pattern: `tests/gitfixtures.remove_tree`) | git object files are read-only on Windows (PITFALLS 5) |
| List persistence | New file format | `QSettings` list with the `load_dest_history` guard (`isinstance(val, str)`) | A single-element list comes back as a `str` |

**Key insight:** every hard part of this phase already has a tested building block in the repo (git runner, atomic writer, config reader, confirm dialog, off-thread worker, elided label); the risk is wiring and wording, not algorithms.

## Common Pitfalls

### Pitfall 1: ROOT-10 is unreachable while `_path_var_refusal` refuses a different folder
**What goes wrong:** `library_scanner._path_var_refusal` (lines 137-145) returns a `config.other_checkout_refused` warning and the sync stops before any confirm whenever `if is_configured and _norm_path(configured) != _norm_path(repo_str):`. After the switch, the case that matters is exactly "KiCad's `KICAD_LIB_GITHUB` names another folder than the one just chosen", so the `VAR: old -> new` question would never be asked, on the switch nor on Generate / Install ("keep offering it as today" is therefore false for a chosen folder that differs). The UI-SPEC wrong-folder copy even says "let the app point KiCad at this folder when Generate Tables offers to".
**How to avoid:** relax the `other_checkout` refusal in `sync_kicad_path_vars` (keep the `.git`-is-a-file worktree refusal, reword it to "the library folder is a git worktree"). The explicit confirm (default **No**, window-modal, KiCad-open three-button variant) is the safety. Update `tests/test_kicad_config.py:515-528` (`test_other_checkout_refuses_without_asking_or_writing`, must now ask) and keep `test_same_checkout_in_another_spelling_is_not_refused` (line 543). The Pin refusal (`_chooser_refusal`, `kicad_setup.py:308-324`) and the migration Run refusal stay as they are (locked). See Open Question 1.
**Warning signs:** after switching to a folder KiCad does not point at, no dialog appears and the log shows `config.other_checkout_refused`.

### Pitfall 2: A switch must reset the "first scan" state, not just re-run the scan
**What goes wrong:** `_on_scan_finished` only reads the Destination tables and links footprints when `self._startup_pending` is true; `_finish_scan` clears it after every scan. A second scan otherwise goes through `_reapply_selection(previous, result)` and carries the old folder's selection over by `rel_path` (and logs "Kept N selections").
**How to avoid:** in `_switch_root` set `self._scan_result = None` and `self._startup_pending = True` before `_start_scan()` (UI-SPEC step 3: selection starts fresh as at app start). Also confirm `_pending_post_install is None` and `not self._pending_migration` through the busy guard.

### Pitfall 3: Startup order and the first-run window
**What goes wrong:** `MainWindow.__init__` calls `_detect_kicad()` (which can open a blocking `QFileDialog`) and `_start_scan` itself; putting the first-run window or the resolve inside the constructor nests modal dialogs and leaves a half-built window. The log panel also does not exist until `_build_ui` runs, so resolve notes need holding.
**How to avoid:** resolve and first-run in `startup.py` before the window; pass `startup_notes: list[Issue]` and flush them first thing after `_build_ui`; a failing override exits 2 with one stderr line (`--library-root: {path} cannot be used: {reason}`); guard `sys.stderr is None` (a windowed frozen build has none: Phase 21) with a tiny `_say()` helper.

### Pitfall 4: Slow or absent drives during the startup check
**What goes wrong:** `Path.is_dir()` / `iterdir()` on a disconnected network drive can block for tens of seconds with no window on screen. The dialogs are fine (off-thread `TaskWorker`), but the startup resolve has no event loop yet.
**How to avoid (recommended):** run the startup check through a small helper that runs it in a `daemon=True` thread joined with a timeout (about 5 s) and treats a timeout as "cannot be used (no answer from the drive)". Do not use `ThreadPoolExecutor` (non-daemon threads would block interpreter exit). Document that a stuck daemon thread is abandoned. [ASSUMED: no measurement of the real block time]. See Open Question 3.

### Pitfall 5: Writable probe and cleanup on Windows
**What goes wrong:** `os.access(path, os.W_OK)` returns True for ACL-read-only folders; a probe file left behind shows up in `git status` and the scan fingerprint walk.
**How to avoid:** probe with `tempfile.TemporaryFile(dir=folder)`; it created and removed a file in a temp folder here (`probe ok []`) [VERIFIED locally; network shares and ACL-restricted folders: ASSUMED]. For creation failure, remove only what this call created, in reverse order, tolerate read-only entries, and report leftovers in a second issue row (UI-SPEC "Some folders were left behind in {path}").

### Pitfall 6: Windows name rules for a new collection
**What goes wrong:** names that Windows cannot create or that behave as devices.
**How to avoid:** implement exactly the Microsoft rules [CITED: learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file]: reject `< > : " / \ | ? *`, NUL, control characters 1-31, a trailing space or period, and the reserved names `CON, PRN, AUX, NUL, COM1-COM9, COM¹ COM² COM³, LPT1-LPT9, LPT¹ LPT² LPT³`, **also when followed by an extension** (`NUL.txt`); compare case-insensitively. Also reject names that are `.` or `..` and any name containing a path separator (traversal), applied on every platform. Drive roots and UNC share roots are detected with `path.parent == path` (`Path("E:\\")`, `Path("\\\\srv\\share")` both True, `Path("C:\\Users")` False) [VERIFIED: ran it]. Program Files: compare against `%ProgramFiles%`, `%ProgramFiles(x86)%`, `%ProgramW6432%` (all three are set on this machine) using `same_folder`-style normalisation and a prefix check.

### Pitfall 7: `git init -b main` needs git 2.28; the app only requires 2.25
**What goes wrong:** on 2.25-2.27 `-b` is an unknown option and creation fails with a confusing message.
**How to avoid:** in `create_collection` check `gitops.git_version(ctx) >= (2, 28)` and otherwise return the "Git was not found / too old" issue before creating anything; keep `MIN_GIT_VERSION = (2, 25)` for the commit path. Optionally pass `--template=` (verified to run: `git init --template= -b main` printed "Initialized empty Git repository") so a user's `init.templateDir` hooks are not copied into the new repo.

### Pitfall 8: The first commit in a new collection is not blocked by git, but identity can be
**What goes wrong:** with no `user.name` / `user.email` the probe returns `unavailable` with the reason at `commit_step.py:175-178` ("git does not know who you are: set user.name and user.email, or GIT_AUTHOR_NAME, ..."). The UI-SPEC wants a `git config` sentence "when that flow does not already word it"; the flow already words it, so the extra sentence is optional.
**How to avoid:** tests set `GIT_AUTHOR_*` / `GIT_COMMITTER_*` with `monkeypatch.setenv` (the app's `_env()` keeps exactly those four GIT_ variables) or `git config --local` in the fixture; the conftest isolation gives every test an empty HOME with no identity.

### Pitfall 9: Stale wording and stale tests
**What goes wrong:** the D-26 copy, the Help page and `CLAUDE.md` still say "this app runs from" / "push them from here, then pull there"; five test modules assert the old strings (Codebase Inventory 4).
**How to avoid:** change copy, tests and Help in the same plan; run `tests/test_checkout_check.py`, `test_checkout_warning.py`, `test_kicad_setup.py`, `test_migration_dialog_run.py`, `test_help_dialog.py`, `test_docs_atomic.py`.

### Pitfall 10: Parallel plans editing `main_window.py` (1869 lines)
**What goes wrong:** the refactor, the row, the menu, the dialogs and the offer all touch `MainWindow`; parallel waves produce unmergeable edits.
**How to avoid:** one plan owns `main_window.py` per wave; put the dialogs in separate widget modules and test them standalone.

### Pitfall 11: QSettings list quirks
**What goes wrong:** a single-element list is read back as a `str`; values are untrusted.
**How to avoid:** copy the `load_dest_history` guard; treat a `list` returned for `library/root` defensively; always re-check `is_dir()` at use. Verified round trip with this machine's QSettings: a root `<home>\R&D, Parts\Kicad` comes back as the same `str`; a one-item recent list `['C:\a,b\c']` comes back as a list; an empty list is stored as `@Invalid()` and read back as `[]`. Dedupe the recent list on a normalised key (`normcase(normpath)`), keep the spelling the user used, cap at 10.

### Pitfall 12: Menu and status text with `&`
**What goes wrong:** a folder `R&D Parts` becomes a mnemonic in a `QAction` text.
**How to avoid:** double every `&` in the displayed text only (UI-SPEC), keep the real path in the action's `data()`, tooltip and status tip. Labels, the window title and `QLabel`s with `Qt.TextFormat.PlainText` are not affected.

### Pitfall 13: The 3.10 grammar gate
**What goes wrong:** new code written for 3.14 (nested same-quote f-strings, `except A, B:`) fails `tests/test_annotations_resolve.py`, which also parses `kicad_lib_manager.py`.
**How to avoid:** write 3.10-compatible syntax; annotations may use `X | None`; do not rely on deferred annotations.

## Code Examples

### The allow-list edit (a deliberate, reviewed act)
```python
# Source: kicad_lib_manager/gitops.py:21-25 (read this session), plus the one new member
ALLOWED_SUBCOMMANDS = frozenset({
    "--version", "rev-parse", "symbolic-ref", "status", "merge-base", "rev-list", "log", "ls-tree",
    "cat-file", "var", "add", "reset", "switch", "commit", "ls-files", "diff-tree", "check-ignore",
    "tag",  # Phase 13 MIG-01: ...
    "init",  # Phase 15 ROOT-06: new collection only, never a clone, never a remote
})
# tests/test_gitops.py: EXPECTED_ALLOWED (line 26) gains "init"; test_allow_list_is_exact_and_safe (line 66) stays exact.

def init_repository(ctx: GitContext, repo: Path, branch: str = "main") -> GitRun | Issue:
    """`git init -b <branch>` in an existing folder; the branch is a constant the caller picks, never typed text."""
    return run_git(ctx, repo, "init", "--template=", "-b", branch)
```
`run_git` builds `[exe, --literal-pathspecs, -c, core.quotepath=false, -C, repo, init, --template=, -b, main]`; `argv[6]` is the subcommand, which `tests/test_gitops.py:366` asserts is allow-listed. `repo` must exist before the call.

### The resolve contract (Qt-free)
```python
# Recommended shape; names are the planner's to confirm
class Source(Enum):  # tag text comes from the UI-SPEC table
    CLI = "set by --library-root"
    ENV = "set by KICAD_LIBMGR_ROOT"
    CHOSEN = "your choice"
    KICAD = "KiCad's folder"
    LEGACY = "the folder this app runs from"

@dataclass(frozen=True)
class Candidate:
    path: Path
    source: Source

def resolve_library_root(candidates: Sequence[Candidate], check=check_folder) -> Resolution:
    """First candidate that passes; CLI/ENV failures are fatal; CHOSEN/KICAD failures become notes."""
```

### Settings helpers (names fixed by the UI-SPEC "Settings and Persistence" table)
```python
def load_library_root() -> Path | None: ...      # key "library/root"
def save_library_root(path: Path) -> None: ...
def clear_library_root() -> None: ...            # s.remove("library/root")
def load_library_recent() -> list[str]: ...      # key "library/recent", newest first, all saved entries
def add_library_recent(path: Path) -> list[str]: ...  # max 10, no duplicates
```

### Panel presentation for `parent_mode == "none"`
```python
# widgets/commit_panel.py apply_probe(): decide once, hide (not disable) the five widgets
no_parent = probe.parent_mode == "none"
for widget in (self._parent_check, self._parent_label, self._parent_reason):
    widget.setVisible(not no_parent)   # _parent_reason is additionally gated by `probe.state == "ready" and not probe.parent_ok`
# _refresh_parent_and_commit(): show_parent already requires the box to be checked and enabled, so
# _preview_heading, _parent_preview and _earlier_label stay hidden for "none" without extra code.
```

### Layering test for the literal (AST, 3.10-safe)
```python
def _custom_literals(tree):
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
                  and isinstance(n.body[0].value.value, str)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            v = node.value
            if v == "Custom" or v.startswith("Custom/") or v.startswith("/Custom"):
                yield node.lineno, v
# every hit outside collection.py must be zero (a short documented allow-list is acceptable for message prefixes)
```
This exact walk (without the `/Custom` branch) reported the 24 hits listed above.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| App assumes its code folder is the collection | Resolved or chosen library folder | This phase | `MainWindow(library_root)`; legacy fallback only until Phase 16 |
| Parent repo + `Custom` submodule is the only shape | `parent_mode` `gitlink` / `none` | This phase | New collections commit in `Custom/` alone |
| `.git` pruned only at the top | `.git` pruned at any depth | This phase | Needed for `Custom/.git` directories now and for catalog clones in Phase 17 |

**Deprecated/outdated:** `REPO_ROOT` module constant; the "this app runs from" wording of D-26.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tempfile.TemporaryFile(dir=folder)` is a reliable writable probe on network shares and ACL-restricted folders (verified only in a local temp folder) | Pitfall 5 | A read-only share passes the check and the failure appears at the first write; mitigation: also catch `OSError` at create time |
| A2 | An unreachable network path blocks the GUI thread for a noticeable time at startup, so a 5 s daemon-thread timeout is warranted | Pitfall 4 | If the block is short the timeout is unneeded complexity; if the owner never uses network folders it can be dropped |
| A3 | A windowed frozen build has `sys.stderr is None` | Pitfall 3 | Only matters in Phase 21; a guard is cheap either way |
| A4 | Skipping git templates (`--template=`) has no downside for users | Pitfall 7 | A user relying on a global template for a new repo would not get it; trivial to drop the flag |
| A5 | The owner wants the other-folder refusal in `sync_kicad_path_vars` removed (so the offer can be made for a differing folder) | Pitfall 1 / Open Question 1 | If the owner wants the refusal kept, ROOT-10 and success criterion 5 cannot be met for a differing folder |
| A6 | Logging a warning when `KICAD_LIB_GITHUB` names an unusable folder at startup is wanted (CONTEXT only specifies it for the remembered folder) | Pattern 1 | Cosmetic; drop the note |

## Open Questions (RESOLVED)

1. **Relax the other-folder refusal in `sync_kicad_path_vars` (decision needed)**
   - What we know: `_path_var_refusal` stops the offer when `KICAD_LIB_GITHUB` names another folder; CONTEXT says Generate and Install "keep offering it as today", the UI-SPEC says the app can "point KiCad at this folder when Generate Tables offers to", and ROOT-10 requires the offer for the chosen folder.
   - What's unclear: whether the owner intends the refusal to go away (these statements contradict each other as written).
   - Recommendation: remove the `config.other_checkout_refused` branch (keep the worktree refusal, reworded), keep the Pin and migration-Run refusals, rely on the default-No confirm. Update `tests/test_kicad_config.py:515-528`. Flag this to the owner at plan review.
   - **RESOLVED (owner, 2026-11-23):** offer it, keep the worktree block — remove the `config.other_checkout_refused` branch, keep (and reword) the worktree refusal, Pin and the migration's Run keep refusing; the change is always shown as `VAR: old -> new` with No as the default and never written without Yes. Update `tests/test_kicad_config.py:515-528`.

2. **Does the atomic-check dialog belong in the busy guard?**
   - What we know: UI-SPEC lists scan, import, install/post-install, migration and KiCad check; `AtomicCheckDialog` holds the previous `ScanResult` and writes through `repo_root` (`main_window.py:1223-1229`) and is opened with `dialog.open()` (window-modal).
   - Recommendation: include `self._atomic_dialog is not None`, `self._chooser_busy` and `self._pending_post_install / _pending_migration` in the guard so a programmatic switch can never run under it.
   - **RESOLVED (orchestrator, reversible):** yes — the guard includes `_atomic_dialog`, `_chooser_busy`, `_pending_post_install` and `_pending_migration`.

3. **Startup check timeout** — keep it simple (main thread) or use the daemon-thread timeout (Pitfall 4)? Recommend the timeout; the first-run window already exists as the fallback.
   - **RESOLVED (orchestrator, reversible):** use the daemon-thread timeout (about 5 s); on timeout the folder counts as unavailable and the next choice is used with a log line.

4. **First-run closed without a choice** — UI-SPEC resolved it (exit 0, stderr line). No question left; noted so nobody reopens it.
   - **RESOLVED:** UI-SPEC (exit 0, stderr line).

5. **"N other changes stay uncommitted" in a new collection**
   - What we know: after the first commit `.gitkeep`, `.gitignore` and `README.md` remain untracked and the panel hint counts them (`commit_step._other_changes`).
   - Recommendation: accept (D4: no automatic commit; the hint is truthful), but mention it in the User Guide so the first-time user is not surprised.
   - **RESOLVED (orchestrator, reversible):** accept the truthful hint; the User Guide mentions it for a new collection.

6. **`git` missing at New Collection** — UI-SPEC row 1 blocks creation ("A collection needs Git"). The check must use `gitops.find_git` and re-detect each time (PITFALLS 29: Git installed while the app is open).
   - **RESOLVED:** UI-SPEC row 1; check with `gitops.find_git`, re-detected each time.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (venv `env/`) | Everything | yes | 3.14.4 | — |
| PySide6 | GUI and tests | yes | 6.12.0 | — |
| pytest, pytest-qt, pytest-xdist | Validation | yes | `tests/test_layering.py tests/test_checkout_check.py` ran: 27 passed in 0.97 s | — |
| git | `create_collection`, slow tests, commit step | yes | 2.49.0.windows.1 (`/mingw64/bin/git`) | New Collection shows the "Git was not found" row; slow tests skip via `requires_git` |
| KiCad install | Not needed by this phase (footprint folder detection is existing behaviour; tests inject `config_base`) | not checked | — | tests use synthetic `kicad_common.json` |
| Windows Explorer / `QDesktopServices` | ROOT-12 | yes (Windows 11) | — | tests patch `QDesktopServices.openUrl` |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none on this machine.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt + pytest-xdist + pytest-timeout (qt_api = "pyside6") |
| Config file | `pyproject.toml` (`addopts = "-ra --strict-markers -n 8 --dist worksteal -m 'not slow'"`, `timeout = 300`) |
| Quick run command | `.\env\Scripts\python.exe -m pytest <module> -n 0 -q` (one module, under 30 s) |
| Full suite command | `.\env\Scripts\python.exe -m pytest` (quick, ~70 s) / `--full` (~330 s); executors run targeted modules only, the orchestrator runs suites |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROOT-01 | Window uses the constructor folder; no `REPO_ROOT` in `main_window.py`; legacy fallback is last | unit + AST | `pytest tests/test_main_window_root.py tests/test_layering.py -n 0` | Wave 0 (new) |
| ROOT-02 | Order CLI > ENV > chosen > KiCad > legacy > first-run; override failure fatal; argparse keeps Qt flags | unit | `pytest tests/test_collection.py::test_resolve_order tests/test_startup.py -n 0` | Wave 0 |
| ROOT-03 | Switch rescans (fake `scan_all` sees the new root), selection reset, refused while scan / import / atomic / migration / path-var check / pending runs | offscreen GUI | `pytest tests/test_main_window_root.py -n 0` | Wave 0 |
| ROOT-04 | `Use KiCad's Folder` enabled only when set and different; removes `library/root` | offscreen GUI + settings | `pytest tests/test_main_window_root.py tests/test_settings_library.py -n 0` | Wave 0 |
| ROOT-05 | First-run window rows, disabled KiCad row, Quit exits 0 with stderr line, notice strip | offscreen GUI | `pytest tests/test_library_root_dialogs.py -n 0` | Wave 0 |
| ROOT-06 | Skeleton contents and refusals (non-empty, drive root, Program Files, app folder, names); creation cleanup; real git + first-part commit | unit (fake runner) + slow | `pytest tests/test_collection.py -n 0`; `pytest tests/test_collection_git.py --full -n 0` | Wave 0 |
| ROOT-07 | Check rows (exists, writable, layout variants, length warning > 100); deleted remembered folder note text | unit | `pytest tests/test_collection.py -n 0` | Wave 0 |
| ROOT-08 | Row text, tooltip, tag, title (`R&D` plain), amber mismatch tag | offscreen GUI | `pytest tests/test_main_window_root.py -n 0` | Wave 0 |
| ROOT-09 | `parent_mode` probe for both shapes; panel hides five widgets for `none`; gitlink bump unchanged | slow (git) + fast panel | `pytest tests/test_commit_step.py --full -n 0`; `pytest tests/test_commit_panel.py -n 0` | exists (edit) |
| ROOT-10 | Offer after switch only when vars differ; never written without confirm; not after Use KiCad's; refusal relaxed | unit + GUI | `pytest tests/test_kicad_config.py tests/test_main_window_root.py -n 0` | exists (edit) + Wave 0 |
| ROOT-11 | Recent list max 10, newest first, existing only, `&` doubled, current checked | unit + GUI | `pytest tests/test_settings_library.py tests/test_main_window_root.py -n 0` | Wave 0 |
| ROOT-12 | `QDesktopServices.openUrl` called with the folder URL; deleted folder logs the error line; enabled while scanning | offscreen GUI | `pytest tests/test_main_window_root.py -n 0` | Wave 0 |
| cross | `.git` pruned at any depth in both walkers; `subprocess` only in `procs.py`; `CREATE_NO_WINDOW`; `init` allow-listed exactly | unit / AST | `pytest tests/test_scanner_skip_dirs.py tests/test_procs.py tests/test_gitops.py tests/test_kicad_process.py tests/test_kicad_cli.py tests/test_layering.py tests/test_importer_layering.py -n 0` | exists (edit) + Wave 0 |

### Sampling Rate
- **Per task commit:** the one or two targeted modules from the table (`-n 0`, under 30 s).
- **Per wave merge:** the orchestrator runs bare `pytest` (quick, ~70 s).
- **Phase gate:** `pytest --full` green, plus `tests/test_docs_atomic.py` and `tests/test_help_dialog.py` after the docs plan, before `/gsd-verify-work`; manual UAT list below.

### Wave 0 Gaps
- [ ] `tests/test_collection.py` — resolve order, `check_folder` rows, name validation, skeleton with a recording `GitContext.runner` (no real git, so not slow), cleanup, `source_of`
- [ ] `tests/test_collection_git.py` (`@pytest.mark.slow`, `requires_git`) — real `create_collection`, branch `main`, `.gitkeep` present, real first-part import + commit (the scratch script in Codebase Inventory 8 is the template), optionally clone the committed collection and scan it (PITFALLS 13)
- [ ] `tests/test_startup.py` — `parse_known_args`, env, settings, KiCad config via an injected `config_base`, override failure exit code 2, stderr `None` guard
- [ ] `tests/test_settings_library.py` — helpers incl. a path with a comma, a one-item list, an empty list, the 10 cap, duplicates differing in case or slashes
- [ ] `tests/test_procs.py` — flags, defaults, runner injection, patched `subprocess.run` honoured, AST rule
- [ ] `tests/test_main_window_root.py` — row, title, tag, switch, busy guard, recent menu, Use KiCad's, Explorer, empty-state page, path-variable offer, focus target
- [ ] `tests/test_library_root_dialogs.py` — Choose (rows, stop at first failure, debounce, stale result ignored, Browse cancelled), New Collection (11 issue rows, `Creating...`, failure strip), First-run
- [ ] `tests/collectionfixtures.py` — `make_collection(tmp_path)` (skeleton without git), recording runner, `fake_check` for dialogs
- [ ] Existing edits: five harness files (`MainWindow(repo)`), `tests/test_layering.py`, `tests/test_importer_layering.py`, `tests/test_gitops.py` (`EXPECTED_ALLOWED`), `tests/test_kicad_config.py`, `tests/test_commit_step.py:542`, the wording tests in Codebase Inventory 4, `tests/test_scanner_skip_dirs.py`
- [ ] No framework install needed.

**Manual UAT (owner, from the main checkout, `/gsd-verify-work`):** first-run on a machine state with no `library/root` and no KiCad variable; Change Folder to a scratch collection and back with `Use KiCad's Folder`; New Collection in `Documents`, import a part, Commit, confirm no parent option; a 200-character path in the row at 900 px width; 175% display scaling; a disconnected network drive as a remembered folder.

## Security Domain

`security_enforcement` is enabled (absent = enabled); ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | single-user desktop app |
| V3 Session Management | no | — |
| V4 Access Control | no (filesystem permissions only) | the folder check refuses non-writable, Program Files and the app's own folder |
| V5 Input Validation | yes | `validate_collection_name`, `check_folder`, argparse for `--library-root`, re-checking `QSettings` values at use, `KICAD_LIBMGR_ROOT` treated as untrusted text |
| V6 Cryptography | no | none used |
| V12 Files and Resources | yes | no path traversal through the collection name; creation only inside an empty or new folder; cleanup removes only what was created; `Path.resolve()` before comparisons |
| V14 Configuration | yes | `git init` argv is a fixed list through the allow-listed runner, no shell; branch name is a constant; KiCad settings only change after the existing confirm |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Collection name with `..`, separators, device names | Tampering | reject in `validate_collection_name` on every platform; build the target as `parent / name` and assert `target.parent == parent` after resolving |
| Creating or writing inside Program Files or the app folder | Tampering / Elevation | refuse (UI-SPEC rows 6 and 7); re-check inside `create_collection` as defence |
| Tampered `QSettings` / env value pointing at an unexpected folder | Tampering | re-run `check_folder` on every use; never trust the stored value; an override that fails stops the start |
| Command injection through the path into git | Tampering | `run_git` uses an argv list and `-C <path>`, `--literal-pathspecs`; no shell |
| A user-global git template copying hooks into the new repo | Elevation | `--template=` on `init` (optional hardening); hooks that exist still run at commit per D-06 |
| Writing KiCad's global settings without consent | Tampering | existing `VAR: old -> new` confirm, default No, backup, atomic replace; the post-switch offer reuses it |
| Hang on an unreachable path | Denial of service | off-thread check in dialogs, timeout at startup |

## Sources

### Primary (HIGH confidence)
- Repository code read this session: `kicad_lib_manager/main_window.py` (1-1869), `kicad_lib_manager.py`, `library_scanner.py` (20-420, 429-620, 895-993), `kicad_setup.py` (225-330), `scan_cache.py` (30-320, 535-570), `settings.py`, `gitops.py` (1-422), `kicad_process.py`, `importer/kicad_cli.py` (55-105), `importer/commit_step.py` (1-380, 494-560, 810-950), `importer/layout.py`, `widgets/commit_panel.py` (296-460, 636-771), `widgets/theme.py`, `widgets/help_dialog.py` (225-275)
- Tests read: `tests/conftest.py`, `tests/gitfixtures.py`, `tests/test_layering.py`, `tests/test_importer_layering.py` (head), `tests/test_gitops.py` (1-80), `tests/test_main_window.py` (1-170), `tests/test_kicad_config.py` (480-590), `tests/test_commit_step.py` (515-560), `tests/test_help_dialog.py` (105-145), `tests/README.md`, `pyproject.toml`
- Planning inputs: `15-CONTEXT.md`, `15-UI-SPEC.md`, `REQUIREMENTS.md`, `STATE.md`, `research/ARCHITECTURE.md`, `research/PITFALLS.md` (12, 13, 14, 29)
- Executed this session: real git 2.49.0 initial-commit experiment; the end-to-end first-part install and commit into a D4 skeleton using the app's own functions; QSettings round-trip; `TemporaryFile` probe; `Path.parent == Path` drive-root check; AST count of `"Custom"` literals; `pytest tests/test_layering.py tests/test_checkout_check.py` (27 passed)

### Secondary (MEDIUM confidence)
- [Microsoft Learn: Naming Files, Paths, and Namespaces](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file) (fetched 2026-11-23; page dated 2024-08-28, updated 2025-04-11): reserved characters, reserved device names including superscript digits and the extension rule, trailing space or period, MAX_PATH 260

### Tertiary (LOW confidence)
- None used for recommendations; items resting on reasoning only are in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; versions read from the live environment.
- Architecture: HIGH for the inventory and the commit-step feasibility (executed); MEDIUM for the dialog and startup design (recommendations over approved copy).
- Pitfalls: HIGH for 1, 2, 6, 7, 9, 11 (code or tool verified); MEDIUM for 4 and 5 (network behaviour assumed).

**Research date:** 2026-11-23
**Valid until:** 2026-12-23 (stable code base; re-check line numbers if `main_window.py` changes before planning)
