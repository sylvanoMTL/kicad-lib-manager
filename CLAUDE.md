# CLAUDE.md

## Project Overview
KiCad library manager: a PySide6 app that imports vendor parts, generates KiCad library tables, checks the atomic rule and pins libraries in KiCad. It works on one library collection the user chooses (the owner's lives in a separate private repository, `sylvanoMTL/kicad_libraries`); this repository ships no libraries.

Library conventions the app enforces: own symbol libraries are named `Atomic_<official KiCad symbol library stem>` with one shared `Atomic_Footprints` footprint library, and every part in them must pass the atomic rule (`MPN`, `Manufacturer`, one `Footprint`, `Value` = `MPN`, `Datasheet`, `Description` and an existing 3D model). The full rule, the KiCad path variables and the manual route are in the collection's own `CLAUDE.md` and README, and the app's User Guide (`F1`) explains the rule too.

## Repository Structure
- `kicad_lib_manager.py` — PySide6 GUI entry point
- `kicad_lib_manager/` — the app package:
  - `main_window.py` — MainWindow, ScanWorker (QThread), KiCad detection
  - `startup.py`, `collection.py` — the library-folder choice at start and the collection checks
  - `library_scanner.py` — scan the library folder, parse symbol/footprint links, cross-reference with KiCad defaults
  - `table_generator.py` — generate tables, backup/restore logic (paired by number)
  - `models.py` — dataclasses: SymbolLibrary, FootprintLibrary, FootprintRef, ScanResult
  - `importer/` — the part importer and the migration to atomic libraries
  - `catalog/` — the library catalog, with no Qt: the hardened git runner for the network work (`gitnet.py`), the address and name rules, the `catalog.json` record, the curated list, the staging check, the status and update check, and the Add / Update / Remove / Reinstall operations
  - `widgets/` — the windows and panels (library table, log panel, backup dialog, first-run, import, migration, library catalog window and its pages, User Guide)
- `tests/` — the test suite (see `tests/README.md`)
- `scripts/` — `prepublish_scan.py`, `check_skip_budget.py`, `split/` (the one-off repo split scripts)
  - `scripts/catalog/` — the one-off conversion of a collection's Würth Elektronik submodule to a catalog library, and the collection README and CLAUDE.md templates for the catalog layout
- `.githooks/` — the repository hooks (enable them with `git config core.hooksPath .githooks`)
- `.github/workflows/ci.yml` — Windows CI (`windows-latest`)
- `.planning/` — GSD planning files

## Importing Parts
File > Import Part... (`Ctrl+I`) is the way in for Ultra Librarian, SnapEDA, SamacSys
and loose files — it extracts the package, places the symbol, footprint and 3D model,
and rewrites names and paths to the atomic scheme before any write. The manual route
for when the importer can't be used is in the collection's `CLAUDE.md`.

## Python Environment
- Use `py -3.14 -m venv env` (Windows CPython from python.org, NOT MSYS2 Python) — PySide6 requires standard Windows Python
- Activate: `.\env\Scripts\activate` (PowerShell)
- Dependencies: `pip install -r requirements.txt` (PySide6)
- Test dependencies: `pip install -r requirements-dev.txt` (pytest, pytest-qt, pytest-xdist, pytest-timeout)

## Running the GUI
```
.\env\Scripts\python.exe kicad_lib_manager.py
```
Override the library folder for development or testing with `--library-root` or the
`KICAD_LIBMGR_ROOT` environment variable (the command line wins):
```
.\env\Scripts\python.exe kicad_lib_manager.py --library-root <folder>
```

### GUI Behavior
- **Library folder**: the app works on one library folder, the folder that holds `Custom/`. At start it takes the first of these that passes the folder check: `--library-root`, `KICAD_LIBMGR_ROOT`, the folder you chose last time, KiCad's `KICAD_LIB_GITHUB`; when none does, the first-run window opens. A remembered folder that was deleted is skipped with a log line; a bad `--library-root` or `KICAD_LIBMGR_ROOT` stops the start (exit code 2) instead of falling back. The **Library folder:** row above the toolbar shows the full path, a tag that says where it came from (`set by --library-root`, `set by KICAD_LIBMGR_ROOT`, `your choice`, `KiCad's folder`), an amber `KiCad reads a different folder` tag when `KICAD_LIB_GITHUB` names another folder, and a **Change Folder...** button (it opens **Open Library Collection**). A start through `--library-root` or `KICAD_LIBMGR_ROOT` adds that folder to Recent Library Collections but never saves it as your choice. The window title is `<folder name> - KiCad External Lib Manager`.
- **New Library Collection...** (File menu, no shortcut): opens the New Collection window directly over the main window (its back button is **Keep Current Folder**); a created collection is logged (`Created a new collection in <path>`) and the app switches to it through the same checked switch as the Open window.
- **Open Library Collection...** (File menu, no shortcut): opens a window with a Folder field, Browse... and check rows (exists, writable, is a collection, a path-length warning above 100 characters that does not block); it is also what **Change Folder...** runs. It opens only a collection (button **Open Collection**): an empty folder shows a line pointing to New Library Collection... and a button that opens it pre-filled with the folder, and any other folder that is not a collection is refused with a line pointing to New Library Collection... The File menu also has **Use KiCad's Folder**, **Recent Library Collections** (up to 10 existing folders, including a folder started through `--library-root` / `KICAD_LIBMGR_ROOT`) and **Show Library Folder in Explorer**. A switch is refused while a scan runs, the import window or the migration window is open, or KiCad's settings are being checked; otherwise it saves the choice, clears the selection and runs a full scan of the new folder. The Destination box follows the new folder (and the new folder becomes its newest history entry) when it showed the previous library folder or was blank; a Destination elsewhere (such as a KiCad project folder) stays. After a switch the app offers to change KiCad's path variables (`Change KiCad path variables?`, No is the default; nothing is written without Yes), except after Use KiCad's Folder. The question is separate from Install Part and Generate Tables (they do not need the change, and the answer does not undo anything they did), and Yes makes all your KiCad projects use the libraries in the library folder after KiCad restarts.
- **First run**: when no folder resolves, the application-modal **Set Up Your Library Folder** window opens before the main window with Use KiCad's Folder, Open Library Collection..., New Library Collection... and Quit; **Quit** (or Esc, or the close box) exits with code 0 and saves nothing.
- **New collection**: **New Library Collection...** asks for a Parent folder and a Name and, on **Create Collection**, creates `<Name>/Custom/` with `Symbols/`, `Footprints/Atomic_Footprints.pretty/`, `3DModels/`, `.gitignore` and `README.md` (empty folders hold a `.gitkeep`). `Custom` is its own git repository on branch `main`, the collection root is a plain folder, and nothing is committed for you: after the first import and commit the skeleton files show as other changes that stay uncommitted. The import's Commit step shows no parent option for a new collection.
- **Import Result view**: after an install the result is laid out in two columns under one banner line.
  - The banner says what was installed and sums up the warnings: `No warnings.`, or the count in amber (or red with errors). When there are warnings, the Warnings list is at the top of the left column. The banner also carries **Help** (`F1`) at its right end, the same top-right place as on the import window's toolbar while you choose and edit a package.
  - The left column lists Files written, the Library list and Library tables rows, and the Backup folder.
  - The right column holds the whole Commit step: the branch beside the Commit heading, Files to commit, the message box and the parent option. The message box opens on its first line and is as tall as the message, up to 12 lines.
  - Commit sits beside Close in the bottom bar, the same height as Close, so it is visible without scrolling. Each column scrolls on its own only when the window is too short.
  - The window keeps its width and shrinks to the height the result needs (never taller than the import step was, never below its minimum, always inside the screen). It fits again when the Commit step finishes checking git or the result changes, until you resize it yourself; a later import step gets back the size it had before the install.
  - A Files written or Files to commit list of more than 3 files starts collapsed behind a **Show** button (the heading keeps the count). Files to commit opens by itself when a file is marked.
- **Library Catalog...** (File menu, right under Import Part..., `Ctrl+Shift+L`): adds, updates and removes third-party KiCad libraries that live in public GitHub repositories. The menu text carries the number of libraries a check confirmed to have an update (`Library Catalog... (n updates)`, with a tooltip; never a popup). The window is parentless and non-modal, stays open beside the main window, shows one collection (the current library folder) and is not remembered between runs.
  - The list (Name, Status, Licence, Size, with a search field) holds the curated libraries (Würth Elektronik and SparkFun), the libraries you added by address and any stray folder. A row has one status: Not installed, Installed (with a tick when a check found it current), Update available, Problem: folder missing (listed in `catalog.json`, folder gone) or Problem: not in the catalog (a `ThirdParty` folder that `catalog.json` does not list). A few missing upstream 3D models are scan warnings and never change a status. The Details pane shows Repository, Licence, Size, Libraries, Path variables, Installed version, Updates and Folder, and the buttons of the status: Add This Library, Update This Library, Remove This Library, Reinstall This Library, and Set Path Variables... (only for an installed library whose variable is not set or is set to another folder). **Help** (`F1`) opens the User Guide on its Library Catalog page without changing the saved place.
  - Libraries are downloaded into `ThirdParty/<id>/` of the collection (`ThirdParty/.staging/` holds a download until it is checked) and recorded in `catalog.json` in the collection root. The app writes `catalog.json` and, in a git repository, the `/ThirdParty/` line of `.gitignore`, and never commits either; the result strip notes that `catalog.json` changed. KiCad's own Plugin and Content Manager is never touched.
  - **Add**: a licence page (repository, branch, licence, size, install folder; the tick **I have read the licence terms** for share-alike and proprietary licences, and on the Add preview for a licence that is not stated or not known; nothing is refused for its licence), **Download and Check** (a progress strip; **Cancel Adding** ends the git process tree and deletes the copy), then the Add preview (what will be added, libraries that share a name with one you already have or with KiCad's own, which start unticked and are never renamed, and the path variables) with **Add Library** and **Discard Download**. Nothing is written to the collection before Add Library, and its final record write cannot be stopped: the strip says `Adding cannot be stopped halfway`, and a close during it is ignored. **Add by URL...** takes only public `https://github.com/` addresses; other hosts, private or missing repositories, repositories already listed, repositories with no KiCad 6+ libraries, KiCad 5 only, Plugin and Content Manager only, or Git LFS models are refused with the reason.
  - **Update**: `Looking for changes in ...`, then a preview (versions, files changed, Libraries added, Libraries removed) with **Update Library** and **Keep Current Version**. Files changed inside a library's folder refuse the update and are listed (a catalog library is a managed copy; own changes belong in `Custom/`). **Remove**: a confirmation page that names the folder, its size, the libraries that leave the scan and the path variables it used; **Keep Library** is the default, the Esc target and the first focus, `Ctrl+Return` never removes, the work cannot be stopped halfway, and a failed Remove keeps the entry. **Reinstall** (folder missing) downloads again from the recorded address and keeps the licence confirmation.
  - After a job the main window rescans only that source on a worker (no Loading Libraries window), ticks its libraries (same-name ones stay unticked), carries the ticked Würth libraries from `WurthElektronik/KiCad-Library` to `ThirdParty/WurthElektronik` (with a log line), and offers the library's path variables through the existing `Change KiCad path variables?` question (No is the default). Nothing runs Generate Tables for you; the result line has the button.
  - Git: the catalog's network work needs Git 2.32 or newer (refused below, with a note; a warning below 2.49.1). Without a usable Git the buttons that download are disabled with the reason as tooltip.
  - Busy rules: the catalog waits while a scan runs or the import or migration window is open; a folder switch is refused while a catalog job runs or a downloaded library waits for an answer; closing the window during a job asks `Stop the current job?`.
  - Update check: at every start and after a folder switch, a background `ls-remote` check runs when something is installed and Git is usable. It never blocks, downloads nothing, writes no file in the collection and is silent when GitHub cannot be reached (it logs one line when updates exist). **Check for Updates** in the window does the same on request and logs when GitHub cannot be reached.
- **Startup**: auto-detects KiCad installation for default footprint cross-referencing. If not found, prompts the user to select the footprints folder. The last scan is shown instantly when no library file changed since it was saved; otherwise the full scan runs and the log says why. Rescan always runs the full scan. The Destination box offers only folders that still exist (a deleted folder in the saved history is skipped, and the repository folder is used when none is left).
- **Loading Libraries**: the window shown while a full scan runs has a **Skip** button from the moment the scan starts reading a library source (its symbols, then its 3D model paths); it names that source (for example **Skip WurthElektronik**) and skips only that source's 3D model path check. The symbols are always read in full, so its libraries are still listed and Generate Tables keeps them; a Skip pressed while the symbols are read takes effect when that source's 3D model path check starts. The skip is logged and saved with the scan, the next start says so, and Rescan does the full check.
- **Two columns**: Symbols (left) and Footprints (right), grouped by source (Custom, WurthElektronik).
- **Footprint selection is driven by symbols**: checking/unchecking a symbol auto-selects/deselects its linked footprints. Sync is scoped per source — changing Custom symbols only affects Custom footprints.
- **Select All / Deselect All**: applies to all symbols, then recalculates footprints via the filter.
- **Warnings**: orange text for symbols with missing footprint references. Cross-references check both the repo and KiCad's default libraries.
- **Right-click**: Expand All / Collapse All context menu on both trees. Right-clicking a library row also offers **Rescan this library**, which re-reads just that library (and, for a footprint library, the Atomic_ symbol libraries that link to it) and keeps the check boxes.
- **Saved scan**: stored in `%APPDATA%/KiCadExtLibManager/scan_cache/` (one file per repository folder, beside `settings.ini`, never inside the repo). Safe to delete; the next start then runs the full scan.
- **User Guide**: `F1` or Help > User Guide opens it in its own window, which stays open beside the other windows. It reopens on the page or section you last chose, scrolled to its heading (saved beside `settings.ini`, also after a restart). The import window's Help and `F1` open it on Importing Parts without changing that saved place; the main window's Help and `F1` then bring it back to that place, also while it is still open. If it is already open on that place, it is only brought to the front.
- **Migrate to Atomic Libraries...** (`Ctrl+Shift+M`): offered while `Custom/` still has a v1-named (non-`Atomic_`) symbol or footprint library, or a `.bak` file; otherwise greyed out with a tooltip explaining there is nothing to migrate. Refuses while `Custom` has uncommitted files. Tags `Custom` `pre-atomic` before writing. Shows a part list grouped by target library with a failure strip for every remaining atomic-rule problem and for every library that is only a guess (until you pick a library for that part; the part list marks guessed and suggested libraries, and a weak match on part numbers yields to the part's description) and a draft that is saved and restored; Run Migration stays disabled until the strip is empty. It runs as one transaction, then opens a Result view with the old -> new map (also saved as `Custom/MIGRATION-ATOMIC.md`), the destination folder for the library tables with a Browse... button (the main window's Destination changes with it; a missing or blank folder is pointed out), a Generate Tables button whose outcome is shown under the buttons, a commit step, and a Pin Atomic Libraries in KiCad button. The migration window is window-modal, so it blocks the main window while open.
- **Pin Atomic Libraries in KiCad...** (`Ctrl+Shift+K`): pins every `Atomic_` symbol library and `Atomic_Footprints` at the top of KiCad's library lists, and adds the `MPN` and `Manufacturer` columns right after Description (removing a stray `MANUFACTURER` column). Shows old -> new before writing and backs up the KiCad config files first. Refuses from a git worktree or from a library folder other than the one KiCad's `KICAD_LIB_GITHUB` names.
- **Wrong checkout** (D-26): when KiCad's `KICAD_LIB_GITHUB` names another folder than the library folder the app works on (fix it with Use KiCad's Folder or the path-variable offer), Generate Tables and Install Part still write but show an amber warning naming both folders (KiCad will not see the new libraries or parts until they exist in the folder KiCad reads), while the migration's Run and Pin Atomic Libraries in KiCad refuse outright, naming both folders and saying to use the folder KiCad reads (Use KiCad's Folder) or fix `KICAD_LIB_GITHUB` in KiCad Preferences > Configure Paths. Nothing is said when the variable is not set or there's no KiCad config to read.

### Menu Shortcuts
- `Ctrl+G` — Generate Tables
- `Ctrl+R` — Restore Backup (paired sym + fp)
- `Ctrl+K` — Set KiCad Path (rescans after change)
- `Ctrl+Shift+M` — Migrate to Atomic Libraries...
- `Ctrl+Shift+K` — Pin Atomic Libraries in KiCad...
- `Ctrl+Shift+L` — Library Catalog...
- `Ctrl+Q` — Exit

## Running the Tests
- Quick parallel run: `.\env\Scripts\python.exe -m pytest` (skips the tests marked `slow`; the same run the GSD test gate and CI use)
- Full run: `.\env\Scripts\python.exe -m pytest --full`; serial reference: `--full -n 0`
- Debugging (`--pdb`, `-s`, `breakpoint()`): add `-n 0`
- The suite needs no collection: the tests build their own scratch collections
- Marker `corpus`: tests that need real vendor samples or a real collection run only when `KICAD_TEST_CORPUS` names a collection folder; otherwise they are deselected and the run prints the count (never quietly skipped)
- Marker `needs_kicad`: tests that need an installed KiCad's stock libraries are deselected with a printed count when KiCad is not found; `KICAD_TEST_HIDE_KICAD=1` hides KiCad to reproduce CI
- The catalog tests never use the network: they use local `file://` repositories and fake runners, and the modules that start real git are marked slow (`tests/README.md` lists them for the run before a publish)
- Skip budget: a quick run on a fresh clone has at most 10 skips; `scripts/check_skip_budget.py` checks it and CI fails above it
- A test that creates a real git repository must carry `@pytest.mark.slow`, otherwise it fails with `<nodeid> builds a real git repository: mark it @pytest.mark.slow` or `<nodeid> creates a real git repository (<command>): mark it @pytest.mark.slow`
- Every test has a 300 s timeout (thread method); under workers it reads `TIMEOUT <nodeid> after <N> s` above xdist's worker-crash line
- Every test gets its own empty user folders, QSettings ini and KiCad config folder; no test reads your real KiCad config unless `KICAD_TEST_REAL_CONFIG=1`
- Run-level guards fail the run when it changed the real app state; a change to KiCad's own config only warns. Rerun after using the app or KiCad during a run
- Markers, timeouts, isolation and guards are explained in `tests/README.md`

## Dev Workflow
The tool runs against a collection you choose; the code of this repository holds no library.
- Real use and the corpus run use the main checkout of the collection, the folder KiCad reads (its `KICAD_LIB_GITHUB`). Imports, Generate Tables, the migration, Pin Atomic Libraries in KiCad and their commits run from that checkout, not from a development checkout of this repository.
- Development and tests use a scratch collection: the tests build their own, so the suite needs no collection. To start the app on one, use `--library-root PATH` or `KICAD_LIBMGR_ROOT`; when both are set, the command line wins. With no usable folder the app opens the first-run window.
- Corpus tests: `KICAD_TEST_CORPUS=<collection folder>` runs the tests marked `corpus` against that collection.
- `KICAD_TEST_HIDE_KICAD=1` hides the installed KiCad, to reproduce CI.
- The owner's machine specifics (the main checkout folder, the values of the KiCad path variables, the concrete folders of the wrong-checkout rule) are not in this file; they live in the untracked `CLAUDE.local.md` of the tool checkout.
- Before a push, run `scripts/prepublish_scan.py --tree --history` (the pre-push hook and CI run it too).

## Git Workflow
- Commit with the GitHub noreply email set locally in this clone (`git config user.email`, not global)
- Never add a `Claude-Session:` line or a session URL to a commit message in this repo; `Co-Authored-By` lines stay, and the commit-msg hook strips a session line
- Enable the hooks once per clone: `git config core.hooksPath .githooks`; the pre-push hook runs `scripts/prepublish_scan.py --tree --history`
- CI runs on `windows-latest`: the quick `pytest` run, the skip-budget check and the pre-publish scan
- Use descriptive commit messages with the area of the app they touch
- `.gitignore` excludes generated `sym-lib-table`/`fp-lib-table`, `env/`, `venv/`, `.venv/`, `__pycache__/` and `.claude/`; `CLAUDE.local.md` stays untracked and is never committed
