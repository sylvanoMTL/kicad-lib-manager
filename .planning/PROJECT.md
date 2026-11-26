# KiCad Part Importer

## What This Is

A part importer and atomic-library manager built into the existing PySide6 KiCad Library Manager (`kicad_lib_manager`). The user browses to a component package downloaded from Ultra Librarian, SnapEDA, SamacSys / Component Search Engine, or a folder of loose files. The importer suggests the `Atomic_<official KiCad stem>` library the device belongs in, shows an editable preview, and installs the symbol, footprint and 3D model in one transaction with names and paths rewritten to the repo's atomic scheme. Every part in an `Atomic_` library is held to the atomic rule (MPN, Manufacturer, one resolving footprint link, Value = MPN, Datasheet, Description, an existing 3D model) by the importer, every scan, a fix dialog and the commit gate. The app refreshes the library tables, pins the `Atomic_` libraries in KiCad's chooser, and, after confirmation, commits the part in the `Custom` submodule. It is a personal tool for the repo owner, replacing the manual copy, paste and path-fixing routine described in CLAUDE.md.

## Current State

**Shipped:** v2.0 Atomic Libraries (2026-11-13). Before it, v1.0 Part Importer (2026-10-24, closed 2026-10-25). See `.planning/MILESTONES.md`, `.planning/milestones/v2.0-ROADMAP.md` and `.planning/milestones/v1.0-ROADMAP.md`.

- Ultra Librarian, SnapEDA, SamacSys/CSE and loose-file packages import end to end into `Atomic_` libraries: intake, `Atomic_<stem>` suggestion, editable preview, per-item conflicts, transactional install gated on the atomic rule, table refresh and a confirmed path-limited commit that refuses non-atomic parts.
- The owner's 21 parts live in 10 `Atomic_` symbol libraries plus the shared `Atomic_Footprints` since the live migration of 2026-11-12 (`Custom` bbd48c5, parent c6920f5); every scan reports zero atomic violations, and KiCad 10's chooser pins the `Atomic_` libraries with MPN and Manufacturer columns.
- About 30.6k lines of application Python and 59.3k lines of tests: 9689 passing, 4 documented skips, 0 failures, on synthetic `Custom/` fixtures against KiCad 10 (kicad-cli 10.0.7). A full run takes about 30 minutes.
- Since Phase 16 (2026-11-26) the app lives in the public tool repo `sylvanoMTL/kicad-lib-manager` (MIT, fresh history), and the owner's libraries live in the private collection `sylvanoMTL/kicad_libraries` (no code). KiCad reads the collection's main checkout `Kicad_Libraries`; the app runs from its own tool checkout with its own Python 3.14.4 / PySide6 6.12.0 venv, and the old `Kicad_Libraries-importer` worktree is retired.

## Current Milestone: v3.0 Public Library Manager

**Goal:** Make the KiCad Library Manager a public app that anyone can install, working on a library collection kept outside the app's own code.

**Target features (in phase order):**
- Test suite speed-up first (measure with `--durations`, pytest-xdist, a `slow` marker, shared git fixtures), so every later phase runs a faster suite.
- The app chooses its library folder instead of assuming it lives inside the repo: default is the folder KiCad's `KICAD_LIB_GITHUB` names, otherwise a "Choose library folder..." prompt remembered in settings; it can also create a new empty collection (`Custom/` skeleton with `Atomic_Footprints.pretty` and `3DModels`, git init) for a new user.
- Repo split: a public tool repo (app code, tests, planning, releases) and the owner's private library collection (`Custom` + third-party libraries, no code). Done interactively, not in an autonomous run; the licence is chosen in this phase.
- Library catalog (like Fusion 360 / Eagle): add a third-party KiCad library from GitHub with one click, update and remove it from the UI, from a curated list plus "Add by URL"; WurthElektronik becomes a catalog-managed entry. Plain clones + a manifest versus git submodules is decided in research.
- One clear table model: Generate Tables writes project-local tables into the chosen KiCad project folder, never the global tables (decided 2026-11-22).
- Menu regroup into File / Libraries / KiCad / Help (former backlog 999.1, layout already decided 2026-11-13).
- Python 3.14 is the minimum: declared in pyproject and the README, constraints updated, the Python 3.10 compatibility check dropped.
- Windows installer built with NSIS that checks Git is installed (freeze tool, PyInstaller or Nuitka, chosen in research).

**Not in v3.0:** a public community atomic library (later, after a licensing check); the other v2.0 leftovers (review findings, UI advisories, live re-tests 999.3/999.4, future requirements PREV2-01, FMT2-01, META2-01, PAD-01, DBL-01). The owner's own `Atomic_` libraries stay private.

## Core Value

A downloaded vendor package ends up as a correctly named, correctly linked part in the right `Custom/` library, with the symbol's Footprint field pointing at `<Lib>:<FP>` and the 3D model at `${CUSTOM_3DMODEL_DIR}/<file>.step`, without hand-editing any KiCad file.

## Requirements

### Validated

<!-- Inferred from the existing codebase (see .planning/codebase/). -->

- ✓ Scan the repo for symbol libraries (`.kicad_sym`) and footprint libraries (`.pretty/`), grouped by source (Custom, WurthElektronik) — existing
- ✓ Parse each symbol's footprint references and cross-check them against the repo and KiCad's default footprint libraries, with warnings for missing ones — existing
- ✓ Check 3D model paths referenced in `.kicad_mod` files — existing
- ✓ Auto-detect the KiCad install and user config directory, and prompt for the footprints folder if they aren't found — existing
- ✓ Two-column Symbols | Footprints tree, where symbol selection drives footprint selection per source — existing
- ✓ Generate `sym-lib-table` / `fp-lib-table`, merging in existing external entries, with numbered paired backups and restore — existing
- ✓ Write `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` into KiCad's `kicad_common.json` — existing
- ✓ Background scan on a QThread, a colour-coded log panel, Rescan (Ctrl+Shift+R), and persisted settings (QSettings) — existing
- ✓ Dependency manifest with pinned PySide6 (`requirements.txt` / `requirements-dev.txt`) — Phase 1
- ✓ Headless pytest harness (offscreen Qt, strict markers), run bare from the repo root — Phase 1
- ✓ Lossless S-expression layer: every repo `.kicad_sym`, `.kicad_mod` and lib table round-trips byte-identically; edits change only the targeted span and keep CRLF/LF — Phase 1
- ✓ Atomic write helper (temp file + `os.replace`, read-only pre-check, locked-file retry) and `<name>_backup_<N>` backup helper in `fsutil.py` — Phase 1
- ✓ Table merge keeps every external entry whatever its layout; entries it can't classify are kept verbatim with a warning (HARD-01) — Phase 2
- ✓ Locked or read-only tables during Generate log one error per file and leave the UI consistent (HARD-02) — Phase 2
- ✓ `kicad_common.json` is backed up, written atomically, and only `environment.vars` changes (HARD-03) — Phase 2
- ✓ KiCad version directories sorted numerically, so `10.0` wins over `9.0` (HARD-04) — Phase 2
- ✓ No overlapping scans: one guarded `_start_scan`, with controls disabled while a scan runs (HARD-05) — Phase 2
- ✓ Generated S-expression values are escaped (HARD-06) — Phase 2
- ✓ Rescan keeps the current selection; pre-selection from the tables happens only at startup (HARD-07) — Phase 2
- ✓ Same-nickname libraries in different sources are reported as a collision and kept distinct in the UI (HARD-08) — Phase 2
- ✓ Legacy `${KIPRJMOD}/Custom/3DModels` paths rewritten to `${CUSTOM_3DMODEL_DIR}` in one Custom commit; the scanner warns about any other model path (HARD-09) — Phase 2
- ✓ Legacy `generate_lib_tables.py` CLI removed; issues routed by severity instead of message substrings — Phase 2
- ✓ A vendor package opens as a `.zip` or a folder of loose KiCad files, read in place or staged outside the repo, never written into it (INTK-01) — Phase 3
- ✓ Ultra Librarian zips are recognised and their symbol, footprint and 3D model found at any depth, including a root-level STEP with an unrelated name (INTK-02) — Phase 3
- ✓ KiCad 5-only packages are rejected with a "re-download as KiCad v6+" message (INTK-05) — Phase 3
- ✓ Hostile packages are refused or skipped safely: zip slip, absolute names, symlinks, zip bombs, corrupt members, and oversized or string-heavy KiCad text bounded in memory (INTK-06) — Phase 3
- ✓ A `<Type>_<SubCategory>_<Manufacturer>` library name is suggested from existing `Custom/` libraries and part info (LIB-01; editing arrives with the Phase 5 preview) — Phase 3
- ✓ Symbol, footprint and file names are sanitised, with original and sanitised names both reported (LIB-03) — Phase 3
- ✓ Symbol merged into the target `.kicad_sym` S-expression-aware: other symbols and the header stay byte-identical, renames follow sub-symbols and `extends` (INST-01, INST-02) — Phase 4
- ✓ Footprint copied into the target `.pretty/`; filename, internal name, value, symbol Footprint field `<Lib>:<FP>` and `ki_fp_filters` agree (INST-03) — Phase 4
- ✓ 3D model copied to `Custom/3DModels/<MPN>.<ext>` (same SHA-256 reused) and linked as `${CUSTOM_3DMODEL_DIR}/<file>`, rewriting or inserting the `(model ...)` block (INST-04, INST-05) — Phase 4
- ✓ Packages with no 3D model install without one and warn (INTK-08) — Phase 4
- ✓ A new library creates the matching `.kicad_sym` + `.pretty/` pair; an existing library header is never changed (LIB-02 install side; choosing in the UI arrives with Phase 5) — Phase 4
- ✓ Install is one transaction: app-data backups, ordered atomic writes, verify, and rollback on any failure or exception; a target changed after planning is refused as stale; a second identical install is a no-op (INST-06..INST-09) — Phase 4
- ✓ Post-install warnings for a name found in another library and for pin/pad mismatches (POST-03, POST-04) — Phase 4
- ✓ Import Part dialog (File > Import Part..., Ctrl+I, or drop one zip/folder on the main window) opens one Ultra Librarian zip or loose-files folder per session; the newest Downloads zip and the last folder are offered but never opened without a click (UX-01, UX-02) — Phase 5
- ✓ Several symbols, footprints or models in a package are picked in the dialog (INTK-07); "nothing found" shows the package and detection reasons (Phase 4 WR-06, IN-04) — Phase 5
- ✓ Target library suggested and editable, or an existing `Custom/` library picked; a "new" badge shows a `.kicad_sym` + `.pretty` pair will be created, and placeholder names block Install (LIB-01, LIB-02 UI) — Phase 5
- ✓ Preview before any write: every file, rename, path rewrite and format/kicad-cli action, with diffs and a file content view; footprint name and Value/Datasheet/Description/Manufacturer/MPN editable, explicit clear supported, Footprint field `<Lib>:<FP>` kept in sync; preview and install share one plan (PREV-01..PREV-07) — Phase 5
- ✓ Per-conflict Overwrite / Rename / Skip with no bulk control and nothing pre-selected; Install blocked until every conflict is decided (PREV-05) — Phase 5
- ✓ After install: Result view, rescan with the library checked and current, add-only `sym-lib-table` / `fp-lib-table` entries for a new library, a Generate hint for an existing unlisted one, and a "reopen KiCad's editors" notice when KiCad is running (POST-01, POST-02, POST-05) — Phase 5
- ✓ Commit step in the Result view: shows the Custom branch, the parent repo and branch, the exact installed files and an editable message with Import-Vendor / Import-Package / Import-Date trailers; on click commits only those files in `Custom` (`commit --only`, bystander changes untouched), then only the `Custom` gitlink in the parent; detached HEAD on `main`'s history offers a plain `switch main`, otherwise refuses; never pushes, reports "Not pushed — N commits ahead" (GIT-01..GIT-05) — Phase 6
- ✓ SnapEDA and SamacSys/CSE zips open and auto-detect through the same flow as Ultra Librarian, with the vendor label, a readable Field changes section, and an `Import-Vendor:` commit trailer; a SnapEDA zip with no model installs with the "no 3D model found" warning, SamacSys other-CAD folders are skipped with one log line; real samples install and load in kicad-cli (Phase 7)
- ✓ A separately downloaded 3D model (bare STEP/STP/WRL, or a zip holding one) is added with "Add 3D model..." in the import dialog under the same intake safety checks, and installs as `Custom/3DModels/<MPN>.<ext>` linked as `${CUSTOM_3DMODEL_DIR}/<file>` (FMT2-02, G-07-2) — Phase 7
- ✓ An unusable model source (no model, failed content check, partly bad zip, read failure) is a red blocking error on the model row with Remove / Add 3D model... recovery; preview columns are user-resizable and elide; status-strip reasons carry a click hint (G-07-5, G-07-7, G-07-8) — Phase 7
- ✓ Headless pytest suite for importer logic (format detection, symbol merge, path rewriting, naming), using real downloads as fixtures, plus tests for the hardened table and parser code; real-sample tests skip when the local downloads are absent — v1.0 (1966 passing at close)
- ✓ All 54 v1 requirements (FOUND, HARD, INTK, FMT2-02, LIB, PREV, INST, POST, GIT, UX) — v1.0
- ✓ Tests build their own synthetic `Custom/` and never read or write the live one, guarded by a write-protect check; the suite passes whatever parts the owner has installed (TEST-01) — Phase 8
- ✓ Real kicad-cli tests expect KiCad 10 output (format 20251024) and skip with a stated reason when kicad-cli 10 is absent (TEST-02) — Phase 8
- ✓ Bare `pytest` on the workstation: 8063 passed, 3 documented skips, 0 failed (TEST-03) — Phase 8
- ✓ D-01 re-tested on KiCad 10: installing into a 20241209 `Custom/` library keeps the header, merges the symbol as-is with one warning, and the result opens in KiCad 10's Symbol Editor with both units placeable (VER-01, UAT 2026-10-26) — Phase 8
- ✓ One atomic rule check (MPN, Manufacturer, footprint link resolving to exactly one `<Lib>:<FP>`, Value = MPN, Datasheet, Description, 3D model) with one canonical manufacturer table; every rule blocking for `Atomic_` libraries only, derived symbols checked on their own fields (ATOM-01..03) — Phase 9
- ✓ Every scan runs the check: failing symbols marked in the tree per part with Status count and one row per broken rule and note, one log line per failure; parts new or changed since the last `Custom` commit highlighted; Check Atomic Parts (Ctrl+Shift+A, or double-click) previews and applies only safe fixes (SCAN-01..03, UAT 2026-10-26) — Phase 9
- ✓ Importer on the atomic scheme: suggests `Atomic_<stem>` from KiCad sibling votes, then the vendor category map, else asks; refuses official KiCad names and manufacturer tokens; installs footprints into the shared `Atomic_Footprints` or links an official KiCad footprint (1:1 pairing dropped); Install blocked with clickable reasons until the part passes the atomic rule; generated `ki_keywords`, footprint description and tags, editable in the preview (LIB-04..07, FLD-01, FLD-03; UAT 2026-10-29) — Phase 10
- ✓ Commit gate and commit panel: Commit refuses (and fails closed on unreadable linked libraries) while any committed part breaks the atomic rule, naming part and rule; the panel keeps git's output, the refusal detail and the manual command across re-probes, checks HEAD after a timeout, uses one parent-message builder and PowerShell quoting on Windows, keeps the parent checkbox choice and `GIT_AUTHOR_*`/`GIT_COMMITTER_*` identity; primary Commit button, tinted outcomes, "Committed in Custom only" (GIT-06, REV-06..11, UI-02; UAT 2026-11-01, pasted command checked in real Windows PowerShell 5.1 and PowerShell 7 consoles) — Phase 11
- ✓ Import-flow fixes: Phase 5 review warnings closed (table step text, empty Destination, build/Install overlap, GUI thread never waits on kicad-cli, fresh settings write gated by a KiCad-open question); Help and conflict rows on theme tokens; case-twin rollback/overwrite re-tested on a case-sensitive folder; plus UAT-raised fixes: Cancel on every import page, compact start page, per-source Skip while libraries load, a shared User Guide window with a numbered menu that reopens on the last chosen section (REV-01..05, UI-01, VER-02; UAT 2026-11-11, live re-tests of REV-05's KiCad-open dialog and REV-04's Finishing strip deferred to backlog 999.3/999.4) — Phase 12
- ✓ All 40 v2.0 requirements (TEST-01..03, ATOM-01..03, LIB-04..07, SCAN-01..03, FLD-01..03, TBL-01..02, MIG-01..05, GIT-06, VER-01..02, REV-01..11, UI-01..02, DOC-01) — v2.0

- ✓ Own symbol libraries are `Atomic_<official KiCad stem>` with one shared `Atomic_Footprints`; the migration refuses on uncommitted `Custom`, tags `pre-atomic`, previews every part with a failure strip and a saved draft, runs as one transaction with rollback, writes the old -> new map (`Custom/MIGRATION-ATOMIC.md`) and offers the Custom + parent commits; a guessed library blocks Run until confirmed (MIG-01..05; live run 2026-11-12: 21 parts into 10 `Atomic_` libraries, zero violations) — Phase 13
- ✓ Generated table entries carry library descriptions; Pin Atomic Libraries in KiCad (Ctrl+Shift+K) pins the `Atomic_` libraries and the MPN/Manufacturer columns after an old -> new preview and a backup, refusing from a worktree or another checkout; Generate/Install warn and Run/Pin refuse when `KICAD_LIB_GITHUB` names another folder (TBL-01, TBL-02, D-26; chooser pinned in KiCad 10 on 2026-11-12) — Phase 13
- ✓ CLAUDE.md, PROJECT.md and `research/LIBRARY-NAMING.md` describe the `Atomic_` scheme and the atomic rule; the User Guide has Migrating and Pin sections (DOC-01); the app imports on Python 3.10+ (annotation-resolution test) and the Loading Libraries Skip is offered while symbols are read (re-test UAT 5/5, 2026-11-13) — Phase 13
- ✓ Test suite speed-up: bare `pytest` is the quick parallel run (`-n 8 --dist worksteal -m 'not slow'`, about 70 s, fits the GSD gate) and `pytest --full` the full parallel run (about 330 s against a 1564 s serial baseline), equal to the serial counts ten times in a row; `slow` marker with tripwires, per-test user-state isolation and a run-level app-state guard, git templates built once per run, 300 s named timeouts (TEST-04..09; a native worker crash from a pytest-qt-closed dialog's timer was fixed in the harness) — Phase 14

- ✓ The app works on a library folder it resolves (`--library-root` / `KICAD_LIBMGR_ROOT` > remembered choice > KiCad's `KICAD_LIB_GITHUB` > first-run window; the app's own folder only as a legacy fallback until Phase 16), shown in a Library folder row; Choose Library Folder..., Change Folder..., Recent Library Folders, Use KiCad's Folder and Open Library Folder in Explorer switch it (refused while busy); New Collection creates `Custom/` with its own git repo and no commit, and a first part imports and commits with no parent option; the KiCad path variables are offered after a switch through the VAR: old -> new confirmation (ROOT-01..12; automated GUI UAT offscreen and native at 175%, owner sign-off 2026-11-23) — Phase 15
- ✓ Repo split: the public tool repo `kicad-lib-manager` (MIT, a fresh allow-listed history, scrubbed `.planning/`) holds code, tests, docs and planning; the private collection `kicad_libraries` keeps its history, `Custom` and WurthElektronik and no code; both library repos private, the tool repo public. The owner's KiCad tables resolve identically before and after (428 entries, 0 missing). A pre-publish scan (also the pre-push hook and CI) finds nothing private in the full history. A fresh clone passes on Windows CI with 4004 passed, 1 skipped (budget 10), using a synthetic Ultra Librarian zip, with `corpus` and `needs_kicad` tests deselected and counted. The app's own folder is never a library folder (SPLIT-01..08; owner UAT 2/2, 2026-11-26) — Phase 16

### Active

**v3.0 Public Library Manager** (requirements with REQ-IDs in REQUIREMENTS.md)
- [ ] Library catalog: add, update and remove third-party KiCad libraries from GitHub, curated list plus Add by URL; WurthElektronik managed by it
- [ ] One decided table model (global or per-project) that Generate Tables follows
- [ ] Menus regrouped into File / Libraries / KiCad / Help (former backlog 999.1)
- [ ] Python 3.14 minimum declared in pyproject and the README
- [ ] Windows NSIS installer that checks Git is installed

**Carried, not in v3.0 (open, non-blocking)**
- [ ] Phase 10 review findings (10-REVIEW-DISPOSITION.md): WR-01 unlocked shared caches in footprint_index/siblings, WR-03 unvalidated manufacturer owner chain, WR-04 unescaped vendor tooltips, IN-01..IN-06
- [ ] Phase 11 review findings (11-REVIEW-DISPOSITION.md): WR-01 a kept atomic refusal line survives the Check again that follows Open Check Atomic Parts fixes (Commit enablement unaffected); IN-01..IN-03
- [ ] Phase 12 review findings (12-REVIEW-DISPOSITION.md)
- [ ] Phase 13 UI review advisory items (13-UI-REVIEW.md, 16/24)
- [ ] Phase 10 follow-up kept in 10-UAT.md: a log panel inside the import dialog
- [ ] From v1.0: Phase 4 WR-04 (REF-01, split `build_plan`), Phase 4 IN-01/02/03/05, Phase 5 IN-01..IN-06

**Backlog (ROADMAP.md)**
- [ ] 999.3 KiCad-open question re-test from the main checkout; 999.4 Finishing strip with a real kicad-cli rebuild

### Out of Scope

- Downloading parts from vendor websites or APIs. The user downloads manually; the importer starts from a file on disk.
- Pushing to remotes. The importer commits only; pushing stays manual.
- Importing into the WurthElektronik submodule or other third-party libraries. They're upstream-owned, so imports go only into `Custom/`.
- Batch or queued imports. Decided: one package at a time.
- Non-KiCad formats inside packages (Altium, Eagle, OrCAD). Only the KiCad v6+ files are used.
- Editing symbol graphics or footprint geometry. Only names, fields and paths are changed.
- A brand or manufacturer token in library names, or bare KiCad stems with no token. The owner chose the `Atomic_` prefix (2026-10-25): manufacturer tokens split same-function parts, and KiCad 10 ships libraries under every bare stem.
- Generic symbols in `Atomic_` libraries. Every `Atomic_` part is a real, orderable part (the atomic rule).
- KiCad 10 nested library tables, HTTP or database libraries. Flattened or silently shadowed in the chooser, or they need a server or ODBC driver; not worth it for a single-user repo now (DBL-01 stays a future candidate for passives at scale).
- Renaming or editing the WurthElektronik submodule. Upstream-owned, pull-only.
- A public community atomic library. Later, after a licensing check; the owner's own `Atomic_` libraries stay private (v3.0 scoping, 2026-11-22).
- Editing the owner's KiCad projects to relink them after the migration. KiCad's Edit Symbol Library Links / Update Symbols / Update PCB do this; the app only provides the map and the steps.
- Fixes applied without a preview. Preview before every write stays a project constraint.

## Context

- **Brownfield.** The importer extends `kicad_lib_manager/`, a layered PySide6 app with Qt-free services (`library_scanner.py`, `table_generator.py`), dataclass models, and a widgets package. See `.planning/codebase/ARCHITECTURE.md`.
- **Parsing:** the original regex parsing was replaced in v1.0 by a lossless span-splicing S-expression layer (`kicad_lib_manager/sexpr`, `kicad_files`). Edits change only their span, and every repo file round-trips byte-identically.
- **Sample data:** `downloaded_examples/` holds the committed Ultra Librarian zip plus local-only, licence-restricted SnapEDA (CAD zip and a separate 3D model zip) and SamacSys downloads. Real-sample tests skip when the local files are absent. The original UL notes follow. Sample `downloaded_examples/ul_CSD85301Q2.zip` (Ultra Librarian): It contains `KiCADv6/<timestamp>.kicad_sym`, `KiCADv6/footprints.pretty/DQK0006B.kicad_mod`, import guides, and a STEP model `DLV0006A.stp` at the zip root, outside `KiCADv6/`. Its name matches neither the footprint nor the part. The symbol file is named by timestamp, not part number. The vendor footprint has no `(model ...)` block, so the importer must be able to insert one, not only rewrite an existing path. The symbol's `Footprint` field is the bare `DQK0006B` with no `Lib:` prefix, and `ki_fp_filters` repeats the vendor footprint name.
- **Manual process being replaced** (from CLAUDE.md): download → move the `.kicad_mod` into `<Lib>.pretty/` → copy and paste the symbol into `<Lib>.kicad_sym` in the KiCad Symbol Editor → fix 3D paths to `${CUSTOM_3DMODEL_DIR}` → commit in the submodule, then update the parent repo.
- **Repo layout (since Phase 16):** two repos. The public tool repo `kicad-lib-manager` holds the app, tests, scripts, docs and `.planning/`, with Windows CI and commit-msg / pre-push hooks. The private collection `kicad_libraries` holds `Custom/` (a submodule, `sylvanoMTL/kicad_custom_library`, also private) and the WurthElektronik submodule, plus its own README and CLAUDE.md. KiCad reads the collection's main checkout `Kicad_Libraries` (`KICAD_LIB_GITHUB`), so imports, Generate Tables, the migration and Pin Atomic Libraries in KiCad run against it (D-26). Development and tests use scratch collections; `KICAD_TEST_CORPUS` runs the corpus tests against the main checkout.
- **Sample data after the split:** the tool repo ships no vendor download. `tests/ulfixtures.py` builds a synthetic Ultra Librarian zip with the same layout and quirks; the real samples stay local to the collection side and feed only the `corpus` tests.
- **Libraries:** since the 2026-11-12 migration, `Custom/Symbols/` holds 10 `Atomic_<stem>` libraries (21 parts) and `Custom/Footprints/Atomic_Footprints.pretty`; the v1 names are gone and `Custom/MIGRATION-ATOMIC.md` keeps the old -> new map. `Custom` is tagged `pre-atomic` at the commit before the migration.
- **Tests and dependencies:** pinned `requirements.txt` / `requirements-dev.txt` and a headless pytest suite (offscreen Qt) since v1.0; since v2.0 the suite builds synthetic `Custom/` trees (`synthetic_custom`, `atomic_custom`), a session guard fails any run that changes the live `Custom/`, and the real kicad-cli tests skip unless kicad-cli 10 is found. Since Phase 14 bare `pytest` is the quick parallel run (about 70 s) and `pytest --full` the full parallel run (about 5.5 min for 11681 tests; serial about 25 min). There's still no lint config; `tests/test_annotations_resolve.py` stands in for an undefined-name check after the Python 3.11 NameError (G-13-1-a).
- **Workstation KiCad:** KiCad 10.0 and 9.0 are both installed. kicad-cli discovery picks the newest (10.0.7), which writes symbol format 20251024. Both checkouts run Python 3.14.4 / PySide6 6.12.0 (python.org CPython); the main checkout keeps its old 3.11 venv as `env-py311`.

## Constraints

- **Tech stack:** Python 3.10+ (venv on 3.14), PySide6 6.12, stdlib only otherwise unless a dependency is clearly justified. This extends the existing app rather than starting a new one.
- **Platform:** Windows 11 is primary, with standard CPython (not MSYS2) because PySide6 requires it. Keep the existing cross-platform branches working.
- **KiCad file formats:** output must load in KiCad 6+ libraries. The reference install is KiCad 10, and KiCad 9 is no longer a test target (owner, 2026-10-25). Own symbol libraries are `Atomic_<official KiCad stem>` and every footprint lives in the shared `Atomic_Footprints.pretty` (or links an official KiCad footprint); the v1.0 1:1 `.kicad_sym` / `.pretty` pairing was dropped in Phase 10.
- **Safety:** no write without a preview first. Writes to KiCad files and the repo must be atomic or backed up. Git commits need explicit confirmation.
- **Dependencies:** a new vendor format needs a real sample download in `downloaded_examples/` before it can be built and tested (met for UL, SnapEDA, SamacSys/CSE and loose files in v1.0).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Importer lives inside the existing Library Manager app | Reuses scanner, log panel, settings and table generation; one tool for the repo | ✓ Good — Phase 5 UAT passed |
| Support UL, SnapEDA, SamacSys/CSE and loose files in v1 | Owner uses all of them; zip layouts differ | ✓ Good — Phase 7 UAT passed on the real SnapEDA and SamacSys zips |
| Preview before every write; per-conflict overwrite/rename/skip | Avoid silent damage to curated libraries | ✓ Good — Phase 5 UAT passed |
| Library name suggested from `<Type>_<SubCategory>_<Manufacturer>`, editable | Keeps the convention without blocking edge cases | ⚠️ Revisit — replaced in v2.0 by `Atomic_<KiCad stem>` (worked in v1.0, Phase 5 UAT passed) |
| Own libraries are `Atomic_<official KiCad stem>` with one shared `Atomic_Footprints`; every part must pass a blocking atomic rule (MPN, Manufacturer, footprint link, Value = MPN, Datasheet, Description, 3D model) | KiCad 10 ships libraries under every bare target stem, so a token is mandatory; "atomic" names the guarantee instead of a brand and appears nowhere in KiCad's stock libraries; the owner wants hand-made parts held to the same rule (2026-10-25) | ✓ Good — the check and scan detection shipped in Phase 9, the importer side in Phase 10 and the commit gate in Phase 11, all passed UAT; the migration (Phase 13) moved the 21 existing parts into 10 `Atomic_` libraries on 2026-11-12 and the re-test UAT passed 5/5 on 2026-11-13 |
| Importer details kept as built (owner, 2026-10-29): strict majority for sibling votes, a part with no clear match asks for a library, measured package size (2.1x2.1 mm) and IPC-style tag in footprint text, a package family from tied KiCad footprints only when they agree and are within one pad of the vendor footprint, conflict choices asked again after a refused library name is fixed (WR-07 kept) | The suggestion must never guess a wrong library or family; the owner prefers asking over a wrong default | ✓ Good — Phase 10 UAT passed |
| Footprint keeps vendor name by default, editable | Package codes are often the right name; user can override | ✓ Good — Phase 5 UAT passed |
| Footprint link set automatically; other fields editable in preview | Footprint link is the most error-prone manual step | ✓ Good — Phase 5 UAT passed |
| No 3D model → install without it and warn | Keep the flow simple; models can be added later | ✓ Good — SnapEDA no-model warning verified (Phase 7 UAT) |
| A separately downloaded 3D model is added in the import dialog as a second intake source with the same safety checks; the plan contract is unchanged | SnapEDA ships the model as a separate download (bare file or zip); the Phase 7 UAT (G-07-2) reversed the earlier Out of Scope choice | ✓ Good — Phase 7 UAT tests 3, 4, 6 passed |
| An unusable 3D model source blocks Install as an ERROR; a partly bad zip is rejected as a whole; Remove clears only rejected sources | A silently ignored bad model looked like success (G-07-5, owner decisions 2026-10-24) | ✓ Good — Phase 7 UAT re-test passed |
| One package per import | Simpler review; batch not needed | ✓ Good — Phase 5 UAT passed |
| Commit in `Custom` + bump parent ref after confirmation; never push | Matches the CLAUDE.md git workflow; pushing stays a deliberate act | ✓ Good — Phase 6 UAT passed on the real repo; remote unchanged |
| Fix all High/Medium-High concerns from the codebase map | Importer builds on table/scan/write code that has known data-loss risks | ✓ Good — HARD-01..09 verified and UAT passed (Phase 2) |
| Managed table entries identified by URI tail after `${KICAD_LIB_GITHUB}/`, not by nickname | Nicknames can collide across sources; the path cannot | ✓ Good (Phase 2) |
| Scan busy guard is both disabled controls and a refusing `_start_scan` | A disabled control doesn't stop a programmatic caller (e.g. post-import rescan) | ✓ Good (Phase 2) |
| On a nickname collision, the peer whose rel_path sorts first (Custom before WurthElektronik) stays selected | Deterministic, and personal parts win | ✓ Good (Phase 2) |
| A running KiCad is checked on a worker thread before the path-variable write; the dialog offers Retry / Change anyway / Not now, and the write uses `kicad_common.json` as it is after the dialog | Blocking outright would make Generate unusable while KiCad is open, but writing stale content lost settings KiCad saved meanwhile (Phase 5 WR-06) | ✓ Good — REV-05 (Phase 12); the live re-test from the main checkout is backlog 999.3 |
| Headless pytest for importer and hardened logic | No tests today; parsers and merges are regression-prone | ✓ Good — harness in place, 290+ tests at Phase 1 close |
| Replace regex parsing with an S-expression tokenizer | Needed for safe symbol merge and fixes the table-merge bug | ✓ Good — span-splicing layer round-trips the whole corpus byte-identically (Phase 1) |
| Untrusted KiCad text is bounded before and during parsing: 8 MiB raw-byte cap, 1,000,000-node ceiling, and a linear windowed string scan; an over-cap file is skipped with a WARNING, never a whole-package refusal | Vendor packages are untrusted input; a single hostile file must not exhaust memory or hide the rest of the package | ✓ Good — CR-01/CR-03 closed, 8 MiB hostile strings read within 10× decoded size (Phase 3) |
| Intake never extracts into the repo: zips are staged member-by-member into a temp folder outside the repo, folders are read in place | Keeps the "no write without preview" guarantee for the whole intake step | ✓ Good (Phase 3) |
| Install is a transaction under `except BaseException`: any exception rolls back (`install.unexpected`), interrupts roll back then re-raise | A partial install in a curated library is the worst outcome; an Issue-only rollback missed exceptions (CR-01) | ✓ Good — gap closed and re-verified (Phase 4) |
| Stale-plan check held from preflight to the last write: post-gate re-check, backup copy hashed and used as the rollback pre-image, re-check before every write | kicad-cli runs between preflight and the first write; an edit there was silently overwritten (CR-02) | ✓ Good — gap closed and re-verified (Phase 4) |
| Blank preview text means "not set, keep the vendor value"; an explicit clear is a Phase 5 preview decision | A Qt line edit returns "" for untouched fields (WR-05) | ✓ Good — Phase 5: an emptied field is an explicit clear (Datasheet written empty, cleared Manufacturer skips inference, cleared MPN refused); KiCad loads an empty Datasheet (UAT) |
| kicad-cli normalises only the incoming symbol, and only when its output version equals the target header; footprints are copied as-is | Never change a library's version header; mixed versions load in KiCad 9 (D-01, D-02) | ✓ Good — loads in kicad-cli 9.0.9; verified on KiCad 10 by the automated Phase 8 test (kicad-cli 10.0.7): a 20241209 target takes the as-is-with-warning row and keeps its header (VER-01); the owner's Symbol Editor check is tracked in 08-UAT.md test 2 |
| Post-install table update is add-only: one entry per table for a new library, a no-op when listed, never the tree selection; an existing unlisted library gets a Generate hint | Import must not rewrite the owner's tables or apply an ungenerated selection | ✓ Good (Phase 5) |
| The import flow never runs git; the Result view holds a hidden commit slot for Phase 6 | Commit needs its own confirmation step (GIT-01..05) | ✓ Good (Phase 5) |
| Git runs as `git --literal-pathspecs -c core.quotepath=false -C <repo>` from an allow-list with no remote subcommand, `GIT_*` env stripped, paths on stdin (`--pathspec-file-nul`), message via `-F`; owner hooks always run (no `--no-verify`, D-06) | Package-derived names are untrusted; the user's other changes and the remote must never be touched | ✓ Good — 06-SECURITY.md 26/26 threats closed (Phase 6) |
| KiCad path variables are never written silently: Generate and the post-install table update show `VAR: old -> new` and ask (default No); a git worktree or a checkout other than the configured `KICAD_LIB_GITHUB` is refused with a WARNING; no confirm callback means no write | 2026-10-21: Generate from the dev worktree repointed KiCad 10 at it; 89 WurthElektronik libraries went missing and an ERC error followed | ✓ Good (Quick 261022-gnn) |
| KiCad 10 is the reference version; KiCad 9 expectations are dropped | KiCad 10 is installed on the workstation and the owner no longer targets KiCad 9 (2026-10-25, v1.0 close) | ✓ Good — every real kicad-cli test pins KiCad 10 (format 20251024, generator 10.0) and skips with a stated reason on any other major version (Phase 8, TEST-02) |
| The app runs from the checkout KiCad reads (D-26): Generate Tables and Install Part warn in amber when `KICAD_LIB_GITHUB` names another folder, while the migration's Run and Pin Atomic Libraries in KiCad refuse outright | The 2026-11-12 live UAT first ran from the dev worktree; KiCad would not have seen the migrated libraries | ✓ Good — refusal and warning verified in the Phase 13 re-test |
| A weak sibling vote yields to the part's description, and a guessed library is a blocking strip line until the owner picks one | The live migration filed the ICM-42688-P IMU into `Atomic_Timer` on a weak name match | ✓ Good — 13-25/13-26, UAT 2026-11-13 |
| Both checkouts run on Python 3.14.4 / PySide6 6.12.0 (python.org CPython; main venv rebuilt 2026-11-13, old 3.11 venv kept as `env-py311`); `tests/test_annotations_resolve.py` keeps the code importable on 3.10+ | The main checkout's 3.11 venv exposed a NameError that 3.14's deferred annotations hid (G-13-1-a) | ✓ Good — app starts on both venvs |
| The commit gate fails closed: an unreadable `Atomic_` library or an unlistable Symbols folder refuses the commit | A commit that cannot be proven atomic must not go through on a guess (owner, plan 11-15) | ✓ Good — Phase 11 UAT 3/3, end-to-end run against real git |
| The skip unit while libraries load is the source, and Skip skips only that source's 3D model path check; the symbols are always read in full, and Skip is offered from the start of the source | The 3D check is the long stage (about 100 s for Würth) and skipping symbols would drop libraries from the tables (owner, 2026-11-04; early Skip in 13-24 after G-13-1-b) | ✓ Good — Phase 12 UAT and Phase 13 re-test |
| The last scan is saved beside `settings.ini` (never in the repo) and reused at startup when no library file changed; Rescan always runs the full scan, and any doubt (deleted file, shared nickname) falls back to a full scan | Startup repeated the full Würth scan every time; the fingerprint keeps the shortcut honest | ✓ Good — quick 261027-gg7 |
| A library folder the user chose outranks KiCad's `KICAD_LIB_GITHUB` (override > chosen > KiCad's > first-run prompt) | Otherwise Choose library folder... would do nothing wherever KiCad sets the variable (owner, v3.0 scoping 2026-11-22) | — Pending |
| Generate Tables writes project-local tables into the chosen KiCad project folder, never the global tables; the catalog only manages libraries in the collection | Project-local tables are the purpose of the selection UI (owner, v3.0 scoping 2026-11-22) | — Pending |
| Catalog libraries are plain shallow clones plus a manifest in the collection, not submodules; no code signing or paid services | All four research dimensions agreed on clones; the owner won't pay for signing (2026-11-22) | — Pending |
| Bare `pytest` is the quick parallel run and `--full` the full run; `-n 8 --dist worksteal` chosen from a six-setting matrix | Fastest setting whose runs equalled the serial counts; the quick run fits the GSD 600 s gate unchanged (Phase 14, 2026-11-23) | ✓ Good — quick 68-69 s, ten full runs 320-339 s, all equal to serial |
| Tests never read the real KiCad config by default: `local_kicad` tests opt-in via `KICAD_TEST_REAL_CONFIG=1`, kicad-cli gets a per-test `KICAD_CONFIG_HOME` | Strict reading of "no test touches the real settings, %APPDATA% or KiCad config" (Phase 14, 2026-11-22) | ✓ Good — one documented extra skip |
| A folder is a library collection only when it holds `Custom/` with `Symbols/` or `Footprints/`; an empty folder is offered as a new collection | One layout contract for the chooser, the catalog (Phase 17) and the repo split (Phase 16) (owner, 2026-11-23) | ✓ Good — `collection.check_folder` / `is_collection` |
| The KiCad path variables are offered for any chosen library folder (the v2.0 other-folder refusal is gone; the worktree refusal stays); never written without Yes | Otherwise switching collections leaves KiCad on the old folder (owner, 2026-11-23) | ✓ Good — default No, backup + atomic write |
| After a library folder switch, Destination follows the new folder when it showed the old folder or was blank | Prevents Generate Tables writing one collection's tables into another (owner, 2026-11-23, found by the automated UAT) | ✓ Good |
| Blocking folder checks run on daemon Python threads with results delivered on the GUI thread, never on QThreads | A QThread blocked on a dead network drive aborted the process at exit (automated UAT, Phase 15 gap) | ✓ Good — child-process exit tests |
| Split direction: the existing `kicad_libraries` becomes the private collection with its full history; the tool repo `kicad-lib-manager` is new, its first commit an allow-listed copy of the tree (no `git filter-repo`) | The old history holds workstation paths, session trailers and vendor files; a fresh allow-listed history cannot leak what is not named (owner, Phase 16 D-01/D-02) | ✓ Good — full-history scan clean on GitHub's copy and in CI |
| Tool repo MIT, covering the code only; the tracked TI / Ultra Librarian zip is replaced by a synthetic builder; libraries keep their own licences | Vendor downloads can't be redistributed; tests must still exercise the UL quirks (owner, Phase 16 D-14/D-15/D-16b) | ✓ Good — the builder replaced the zip in every test module |
| Both library repos private; the tool repo is created private, scanned and tested against what GitHub holds, then flipped public by the owner | Stops further exposure of part data; publishing stays the owner's own step (Phase 16 D-11/D-12) | ✓ Good — set 2026-11-26 |
| Tests needing real samples or the live collection carry `corpus` (run only with `KICAD_TEST_CORPUS`), tests needing KiCad's stock libraries carry `needs_kicad`; both are deselected with a printed count, never skipped; a fresh-clone quick run allows at most 10 skips | The public suite must not go green by skipping (owner, Phase 16 D-18/D-19/D-19b) | ✓ Good — CI 4004 passed, 1 skipped |
| v2.0 closed without a milestone audit, with the Phase 8-12 verification reports left stale after their gap plans | Each phase's UAT passed after its gap plans and Phase 13 was verified on the final code; re-running five verifiers would cost more than it would show (owner, 2026-11-13) | — Pending: the next milestone re-verifies whatever it touches |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-26 after Phase 16*
