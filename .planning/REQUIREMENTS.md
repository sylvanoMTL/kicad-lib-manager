# Requirements: KiCad Part Importer — v3.0 Public Library Manager

**Defined:** 2026-11-22
**Core Value:** A downloaded vendor package ends up as a correctly named, correctly linked part in the right `Custom/` library, with the symbol's Footprint field pointing at `<Lib>:<FP>` and the 3D model at `${CUSTOM_3DMODEL_DIR}/<file>.step`, without hand-editing any KiCad file.
**Milestone goal:** Make the KiCad Library Manager a public app that anyone can install, working on a library collection kept outside the app's own code.

Research: `.planning/research/SUMMARY.md` (and STACK, FEATURES, ARCHITECTURE, PITFALLS). Owner decisions taken while scoping (2026-11-22): a folder the user chose outranks KiCad's `KICAD_LIB_GITHUB`; Generate Tables writes project-local tables only; the catalog update check runs automatically at startup; no code signing or paid services.

## v3.0 Requirements

### Test speed (TEST)

- [x] **TEST-04**: Owner can run a quick parallel test run (`-m "not slow"`) that finishes in under 10 minutes on the workstation, so it fits the GSD test gate
- [x] **TEST-05**: Full suite runs in parallel (pytest-xdist) in at most half of the serial baseline measured with `--durations`
- [x] **TEST-06**: Slow tests (real git, Würth corpus, kicad-cli) carry a `slow` marker; strict markers stay on
- [x] **TEST-07**: Parallel workers are isolated: git templates are built once per run, no test touches the real `settings.ini`, `%APPDATA%` or KiCad config, and the live-collection guard still fails a run that writes to it
- [x] **TEST-08**: The parallel full run gives the same pass and skip counts as the serial run, ten times in a row
- [x] **TEST-09**: A hung test fails with a timeout instead of stalling the run

### Library folder (ROOT)

- [x] **ROOT-01**: The app runs from any folder and works on the library folder it resolves, never on its own code folder
- [x] **ROOT-02**: The folder is resolved in this order: `--library-root` / `KICAD_LIBMGR_ROOT` override, then the folder the user chose (remembered in settings), then KiCad's `KICAD_LIB_GITHUB`, then the first-run prompt
- [x] **ROOT-03**: User can switch folders with File > Choose library folder..., which rescans; refused while a scan or import runs
- [x] **ROOT-04**: User can return to KiCad's folder with "Use KiCad's folder"
- [x] **ROOT-05**: When no folder resolves, a first-run window offers: use KiCad's folder, choose an existing collection, or create a new one
- [x] **ROOT-06**: User can create a new empty collection (`Custom/Symbols`, `Custom/Footprints/Atomic_Footprints.pretty`, `Custom/3DModels`, git init, `.gitignore`, README); a non-empty folder, a drive root or Program Files is refused; a first part can then be imported and committed in it end to end
- [x] **ROOT-07**: A chosen folder is checked (exists, writable, collection layout, path length); a remembered folder that was deleted falls back to the next choice with a log line
- [x] **ROOT-08**: The current library folder is shown in the main window
- [x] **ROOT-09**: The commit step works for both collection shapes: the owner's (parent repo + `Custom` submodule, gitlink bump) and a new one with no parent (no parent option shown)
- [x] **ROOT-10**: KiCad path variables for the chosen folder are offered through the existing old -> new confirmation
- [x] **ROOT-11**: Recent library folders are listed under File for one-click switching
- [x] **ROOT-12**: User can open the current library folder in Windows Explorer from the menu

### Repo split (SPLIT) — interactive phase, not an autonomous run

- [ ] **SPLIT-01**: A public tool repo holds the app code, tests, pyproject, planning and build scripts, and no library content
- [ ] **SPLIT-02**: A private library collection holds `Custom` and the third-party libraries, no code; the owner's KiCad keeps working (every table URI resolves, zero missing libraries before vs after)
- [ ] **SPLIT-03**: The public repo's history contains nothing private or licence-restricted (pre-publish scan for owner paths, vendor downloads, part data); how the history is handled is decided in the session
- [ ] **SPLIT-04**: The test suite passes from a fresh clone of the tool repo without the collection, within a stated skip budget (a synthetic sample replaces the TI vendor zip if it can't be published)
- [ ] **SPLIT-05**: The docs are split: developer docs in the tool repo; naming, the atomic rule and path variables in the collection README
- [ ] **SPLIT-06**: A licence is chosen and added; the README covers install and first run
- [ ] **SPLIT-07**: The visibility of both GitHub repos is decided and set (both `sylvanoMTL/kicad_libraries` and `sylvanoMTL/kicad_custom_library` are public as of 2026-11-22)
- [ ] **SPLIT-08**: The dev workflow after the split is documented: the tool runs against a chosen collection (the main checkout for KiCad, scratch collections for tests)

### Library catalog (CAT)

- [ ] **CAT-01**: User can open the Library Catalog and see curated libraries with status (not installed / installed / update available / problem), licence and size
- [ ] **CAT-02**: User can add a curated library in one click: shallow clone with progress and Cancel, validated before it is registered, licence shown before cloning
- [ ] **CAT-03**: User can add a library by GitHub URL; non-KiCad, KiCad 5-only, PCM-only and private repos are refused with a message saying why
- [ ] **CAT-04**: User can update an installed library, and remove one (clone and manifest entry) after a confirmation naming what goes
- [ ] **CAT-05**: Installed libraries are plain clones recorded in a manifest in the collection (URL, branch, commit, path variables), not git submodules; they appear in the scan and in Generate Tables
- [ ] **CAT-06**: Path variables a library needs (e.g. `WE_3DMODEL_DIR`) are set through the old -> new confirmation, so its 3D models resolve
- [ ] **CAT-07**: At startup the app checks installed libraries against GitHub in the background (remote commit vs local commit, no download) and flags "Update available"; it never blocks, and offline the status is unknown with no error
- [ ] **CAT-08**: Adding a library warns about nickname collisions with KiCad stock, other catalog or `Atomic_` libraries, and never renames automatically
- [ ] **CAT-09**: Würth and SparkFun are verified end to end; Espressif, 4ms and Alternate-KiCad-Library are verified and added to the curated list if they work
- [ ] **CAT-10**: KiCad's PCM is left alone: `PCM_` entries, the `3rdparty` folder and `installed_packages.json` are never touched
- [ ] **CAT-11**: Network git is safe: a separate runner (https only, no hooks or credential prompts, no submodule recursion, long paths on, autocrlf off), and the commit path cannot reach the network
- [ ] **CAT-12**: WurthElektronik becomes a catalog entry in the owner's collection, with no missing library or 3D model afterwards

### Library tables (TBL)

- [ ] **TBL-03**: Generate Tables writes project-local `sym-lib-table` / `fp-lib-table` into the KiCad project folder chosen as Destination, and never writes KiCad's global tables
- [ ] **TBL-04**: The Destination shows which KiCad project it is and warns when the folder has no `.kicad_pro`; recent project folders are kept
- [ ] **TBL-05**: A library removed from the collection drops out of a project's table on the next Generate, reported in the log
- [ ] **TBL-06**: The table model is stated at Generate and in the User Guide
- [ ] **TBL-07**: The app warns when KiCad's global tables also list a managed library (the project table shadows it)

### Menus (MENU)

- [ ] **MENU-01**: Menus are regrouped into File / Libraries / KiCad / Help with the layout decided on 2026-11-13 (former backlog 999.1)
- [ ] **MENU-02**: The new actions (Choose library folder, Recent folders, Open in Explorer, Library Catalog) sit in the agreed menus
- [ ] **MENU-03**: Every shortcut is unchanged; the User Guide and CLAUDE.md menu paths are updated

### Python 3.14 (PY)

- [ ] **PY-01**: `pyproject.toml` declares `requires-python >=3.14`, the dependencies and dev groups; the README states the minimum
- [ ] **PY-02**: PROJECT.md and CLAUDE.md constraints say 3.14; the 3.10 compatibility check is replaced by an undefined-name check that still catches the G-13-1-a kind of bug
- [ ] **PY-03**: Running on an older Python shows a clear message instead of a traceback

### Build and installer (PKG)

- [ ] **PKG-01**: One local command builds the frozen app (PyInstaller onedir) and the NSIS installer
- [ ] **PKG-02**: The installer is per-user, with a Start menu shortcut, an uninstaller and upgrade in place; it never deletes settings or the library collection
- [ ] **PKG-03**: The installer checks for Git for Windows; if missing it explains and links the download, then lets the user continue; the app checks again at startup
- [ ] **PKG-04**: The frozen app behaves like the source app: the saved scan is reused, no console windows flash for git or kicad-cli, the User Guide opens, imports run
- [ ] **PKG-05**: A `v*` tag builds the installer in GitHub Actions and attaches it to the release with a SHA-256
- [ ] **PKG-06**: The app checks GitHub releases and says when a newer version exists (no automatic install)
- [ ] **PKG-07**: The Qt/PySide6 LGPL notices ship with the app and are shown in About

## Future Requirements

Deferred; tracked but not in this roadmap.

- **FUT-01**: Public community atomic library (after a licensing check)
- **FUT-02**: Code signing, if a free route opens (e.g. SignPath Foundation after a first release)
- **FUT-03**: Catalog hosts other than GitHub (GitLab, plain git URLs)
- **FUT-04**: Remote (downloadable) curated list instead of the one shipped in the app
- Carried from v2.0: review findings (Phases 10-13, REF-01), Phase 13 UI advisories, live re-tests 999.3 / 999.4, PREV2-01, FMT2-01, META2-01, PAD-01, DBL-01

## Out of Scope

| Feature | Reason |
|---------|--------|
| Code signing | Owner won't pay for it (2026-11-22); the SmartScreen warning is documented instead |
| Generate writing KiCad's global tables | Project-local tables are the purpose of the UI (owner, 2026-11-22) |
| Git submodules for catalog libraries | Plain clones + manifest: no parent commit per update, simpler remove, works without a parent repo (research) |
| A KiCad PCM client or installing into `KICAD<n>_3RD_PARTY` | PCM ships prebuilt zips with rewritten paths; the catalog coexists with it instead |
| Bundling Git in the installer | The installer checks for Git and links the download |
| Installing app or library updates automatically | The app only reports that an update exists |
| A public community atomic library | Later, after a licensing check; the owner's `Atomic_` libraries stay the owner's |
| Other v2.0 leftovers | Kept for a later milestone (see Future Requirements) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-04 | Phase 14 | Complete |
| TEST-05 | Phase 14 | Complete |
| TEST-06 | Phase 14 | Complete |
| TEST-07 | Phase 14 | Complete |
| TEST-08 | Phase 14 | Complete |
| TEST-09 | Phase 14 | Complete |
| ROOT-01 | Phase 15 | Complete |
| ROOT-02 | Phase 15 | Complete |
| ROOT-03 | Phase 15 | Complete |
| ROOT-04 | Phase 15 | Complete |
| ROOT-05 | Phase 15 | Complete |
| ROOT-06 | Phase 15 | Complete |
| ROOT-07 | Phase 15 | Complete |
| ROOT-08 | Phase 15 | Complete |
| ROOT-09 | Phase 15 | Complete |
| ROOT-10 | Phase 15 | Complete |
| ROOT-11 | Phase 15 | Complete |
| ROOT-12 | Phase 15 | Complete |
| SPLIT-01 | Phase 16 | Pending |
| SPLIT-02 | Phase 16 | Pending |
| SPLIT-03 | Phase 16 | Pending |
| SPLIT-04 | Phase 16 | Pending |
| SPLIT-05 | Phase 16 | Pending |
| SPLIT-06 | Phase 16 | Pending |
| SPLIT-07 | Phase 16 | Pending |
| SPLIT-08 | Phase 16 | Pending |
| CAT-01 | Phase 17 | Pending |
| CAT-02 | Phase 17 | Pending |
| CAT-03 | Phase 17 | Pending |
| CAT-04 | Phase 17 | Pending |
| CAT-05 | Phase 17 | Pending |
| CAT-06 | Phase 17 | Pending |
| CAT-07 | Phase 17 | Pending |
| CAT-08 | Phase 17 | Pending |
| CAT-09 | Phase 17 | Pending |
| CAT-10 | Phase 17 | Pending |
| CAT-11 | Phase 17 | Pending |
| CAT-12 | Phase 17 | Pending |
| TBL-03 | Phase 18 | Pending |
| TBL-04 | Phase 18 | Pending |
| TBL-05 | Phase 18 | Pending |
| TBL-06 | Phase 18 | Pending |
| TBL-07 | Phase 18 | Pending |
| MENU-01 | Phase 19 | Pending |
| MENU-02 | Phase 19 | Pending |
| MENU-03 | Phase 19 | Pending |
| PY-01 | Phase 20 | Pending |
| PY-02 | Phase 20 | Pending |
| PY-03 | Phase 20 | Pending |
| PKG-01 | Phase 21 | Pending |
| PKG-02 | Phase 21 | Pending |
| PKG-03 | Phase 21 | Pending |
| PKG-04 | Phase 21 | Pending |
| PKG-05 | Phase 21 | Pending |
| PKG-06 | Phase 21 | Pending |
| PKG-07 | Phase 21 | Pending |

**Coverage:**
- v3.0 requirements: 56 total (TEST 6, ROOT 12, SPLIT 8, CAT 12, TBL 5, MENU 3, PY 3, PKG 7)
- Mapped to phases: 56 (Phase 14: 6, Phase 15: 12, Phase 16: 8, Phase 17: 12, Phase 18: 5, Phase 19: 3, Phase 20: 3, Phase 21: 7)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-22*
*Last updated: 2026-11-22 after v3.0 roadmap creation (Phases 14-21)*
