# Roadmap: KiCad Part Importer

## Milestones

- ✅ **v1.0 Part Importer** — Phases 1-7 (shipped 2026-10-25) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Atomic Libraries** — Phases 8-13 (shipped 2026-11-13) — [archive](milestones/v2.0-ROADMAP.md)
- 🚧 **v3.0 Public Library Manager** — Phases 14-21 (in progress)

## Phases

<details>
<summary>✅ v1.0 Part Importer (Phases 1-7) — SHIPPED 2026-10-25</summary>

- [x] Phase 1: Foundation (6/6 plans) — completed 2026-10-18
- [x] Phase 2: Hardening Existing Code (9/9 plans) — completed 2026-10-19
- [x] Phase 3: Package Intake and Naming (10/10 plans) — completed 2026-10-19
- [x] Phase 4: Plan and Install Core (13/13 plans) — completed 2026-10-20
- [x] Phase 5: Import UI and Post-Install (11/11 plans) — completed 2026-10-22
- [x] Phase 6: Git Commit Step (8/8 plans) — completed 2026-10-23
- [x] Phase 7: SnapEDA and SamacSys Adapters (13/13 plans) — completed 2026-10-24

</details>

<details>
<summary>✅ v2.0 Atomic Libraries (Phases 8-13) — SHIPPED 2026-11-13</summary>

**Milestone Goal:** Every own part lives in an `Atomic_<KiCad stem>` library and is guaranteed atomic, whether it came through the importer or was made by hand. The existing parts are migrated in one clean commit, and the test suite no longer depends on the workstation.

- [x] Phase 8: Test Isolation and KiCad 10 (6/6 plans) — completed 2026-10-26
- [x] Phase 9: Atomic Rule Check and Scan Detection (9/9 plans) — completed 2026-10-26
- [x] Phase 10: Importer on the Atomic Scheme (30/30 plans) — completed 2026-10-29
- [x] Phase 11: Commit Gate and Commit Panel Fixes (17/17 plans) — completed 2026-11-01
- [x] Phase 12: Import Flow Fixes and Case-Sensitive Re-test (21/21 plans) — completed 2026-11-11
- [x] Phase 13: Atomic Migration and KiCad Setup (28/28 plans) — completed 2026-11-13

Quick task 261027-gg7 (saved scan reused at startup, Rescan this library) is archived in `milestones/v2.0-quick/`.

</details>

### 🚧 v3.0 Public Library Manager (In Progress)

**Milestone Goal:** Make the KiCad Library Manager a public app that anyone can install, working on a library collection kept outside the app's own code.

The phases follow the owner's fixed order, one phase per area. Phase 14 speeds up the test suite first, so every later phase runs a suite that fits the GSD test gate, and it installs the worker isolation that Phase 15 relies on. Phase 15 lets the app run outside its own repo on a library folder it resolves or the user chooses, and create a new empty collection; it carries the milestone's largest refactor. The owner runs Phases 14-15 autonomously (`/gsd-autonomous --to 15`) and stops there. Phase 16 splits the public tool repo from the private library collection in an interactive session, because the app must already run outside the repo and the split touches the checkout KiCad reads. Phase 17 adds the library catalog and converts WurthElektronik, which can leave the collection repo only after the split. Phase 18 makes Generate Tables write project-local tables; it comes after the catalog so Add, Remove and Generate agree on what a project's table lists. Phase 19 regroups the menus once every new action exists. Phase 20 declares Python 3.14 the minimum before Phase 21 freezes the app and builds the installer. Until Phase 20 the code stays importable on Python 3.10+ (`tests/test_annotations_resolve.py`).

- [x] **Phase 14: Test Suite Speed-Up** - A quick parallel run fits the GSD test gate, and the full suite runs in parallel with the same results as the serial run (completed 2026-11-23)
- [x] **Phase 15: Choose Library Folder and New Collection** - The app runs from any folder on a library folder it resolves or the user chooses, and can create a new empty collection (completed 2026-11-23)
- [x] **Phase 16: Repo Split** - Public tool repo and private library collection split apart, with the owner's KiCad unchanged (interactive phase, not autonomous) (completed 2026-11-26)
- [ ] **Phase 17: Library Catalog** - Add, update and remove third-party KiCad libraries from GitHub, from a curated list or by URL; WurthElektronik becomes a catalog entry
- [ ] **Phase 18: Project-Local Table Model** - Generate Tables writes project-local tables into the chosen KiCad project, never KiCad's global tables
- [ ] **Phase 19: Menu Regroup** - Menus regrouped into File / Libraries / KiCad / Help with the new actions placed and every shortcut unchanged
- [ ] **Phase 20: Python 3.14 Minimum** - Python 3.14 declared in pyproject, README and constraints, with a clear message on an older Python
- [ ] **Phase 21: Windows Installer and Release** - Per-user NSIS installer with a Git check, built by one local command and on `v*` tags, attached to GitHub releases

## Phase Details

### Phase 14: Test Suite Speed-Up

**Goal**: The owner gets test results in minutes instead of half an hour: a quick parallel run fits the GSD test gate, and the full suite runs in parallel with exactly the results of the serial run
**Depends on**: Nothing (first v3.0 phase; v2.0 is shipped)
**Requirements**: TEST-04, TEST-05, TEST-06, TEST-07, TEST-08, TEST-09
**Success Criteria** (what must be TRUE):
  1. `pytest -m "not slow"` with parallel workers finishes in under 10 minutes on the workstation, so the GSD test gate (600 s default) can run it instead of timing out.
  2. The full suite runs in parallel (pytest-xdist) in at most half of the serial baseline measured with `--durations` (about 30 minutes for 9689 tests today), and gives the same pass and skip counts as the serial run ten times in a row.
  3. Every slow test (real git, Würth corpus, kicad-cli) carries the `slow` marker, and strict markers stay on, so an unregistered marker still fails the run.
  4. Parallel workers share one git template built once per run, no test reads or writes the real `settings.ini`, `%APPDATA%` or KiCad config, and a run that writes to the live library collection still fails.
  5. A hung test fails with a timeout that names it, instead of stalling the run.
**Research flags**: Standard; measure, do not research. D9 (worker count and distribution, `-n 6..8 --dist worksteal` or `-n 4 --dist loadfile`) is settled by measuring both and taking the faster one that passes ten green runs.
**Notes**: Measure first: a `--durations` baseline from three serial runs, the first discarded. Build the git template once under a FileLock in `tmp_path_factory.getbasetemp().parent` with finaliser cleanup; an autouse fixture redirects QSettings, `APPDATA`, `LOCALAPPDATA` and `HOME` and clears `KICAD_LIB_GITHUB`; per-worker guard message; `xdist_group` for the kicad-cli and Würth tests; a short `--basetemp`. Dev-only dependencies: pytest-xdist 3.8.0, pytest-timeout 2.4.0 pinned (2.5.0 was yanked), filelock. Runs autonomously together with Phase 15. PITFALLS.md 1-7.
**Plans**: 6/6 plans complete

Plans:
**Wave 1**
- [x] 14-01-PLAN.md — Tracer: pinned xdist/timeout plugins, quick-run defaults, `--full`, one shared git template per run, timeout meta-tests

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 14-02-PLAN.md — Real-git tests marked `slow`, with a tripwire that fails any unmarked one
- [x] 14-03-PLAN.md — `measure.py` and `MEASURE.md`: serial reference, -n/--dist matrix, quick timing, ten-run check

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 14-05-PLAN.md — Per-test user-state isolation, run-level user-state guard, live Custom/ guard under xdist

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 14-04-PLAN.md — Marker meta-tests and the slow set closed against BASELINE.md's 50 slowest

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 14-06-PLAN.md — Test docs (quick and full commands) and the measured -n/--dist in addopts
**UI hint**: no

### Phase 15: Choose Library Folder and New Collection

**Goal**: The app runs from any folder on a library collection it resolves or the user chooses, never on its own code folder, and a new user can create an empty collection and import and commit a first part in it
**Depends on**: Phase 14 (fast parallel suite and the isolation fixture that redirects settings, `%APPDATA%` and the KiCad variables)
**Requirements**: ROOT-01, ROOT-02, ROOT-03, ROOT-04, ROOT-05, ROOT-06, ROOT-07, ROOT-08, ROOT-09, ROOT-10, ROOT-11, ROOT-12
**Success Criteria** (what must be TRUE):
  1. Started from a folder outside any collection, the app scans and writes only the library folder it resolved, in the order `--library-root` / `KICAD_LIBMGR_ROOT` override, then the folder the user chose (remembered in settings), then KiCad's `KICAD_LIB_GITHUB`, then the first-run prompt; the main window shows the current library folder.
  2. User can switch with File > Choose library folder... (refused while a scan or import runs), return with "Use KiCad's folder", pick a recent folder under File, and open the current folder in Windows Explorer; every switch rescans. A chosen folder is checked (exists, writable, collection layout, path length) before use, and a remembered folder that was deleted falls back to the next choice with a log line.
  3. With no folder resolved, a first-run window offers KiCad's folder, an existing collection, or a new one. A new collection gets `Custom/Symbols`, `Custom/Footprints/Atomic_Footprints.pretty`, `Custom/3DModels`, git init, `.gitignore` and a README; a non-empty folder, a drive root or Program Files is refused.
  4. In a new collection a first part imports and commits end to end with no parent option shown; in the owner's collection the commit still bumps the `Custom` gitlink in the parent repo.
  5. The KiCad path variables for the chosen folder are offered through the existing `VAR: old -> new` confirmation and are never written without it.
**Research flags**: D3 was decided by the owner on 2026-11-22 (a chosen folder outranks `KICAD_LIB_GITHUB`, ROOT-02). D4 was decided by the owner on 2026-11-22: a new collection runs `git init -b main` inside `Custom/`, so the commit step's check that `Custom` is its own work tree still holds (`.gitkeep` in every skeleton folder, no automatic commit). The freeze-tool spike that research placed here is done in Phase 21 instead.
**Notes**: This phase carries the milestone's largest refactor: a Qt-free `collection.py` (folder-name constants, `source_of`, resolve / inspect / create), `MainWindow(library_root)` replacing the 17 `REPO_ROOT` sites and the five test-harness seams, `.git` pruning at any depth in the scanner and scan-cache walkers, the commit step's `parent_mode` (`none` | `gitlink`), and one `run_process()` helper (`CREATE_NO_WINDOW`) for `git init` and every later subprocess runner. The literal `Custom` (about 25 sites) moves to constants, held by a layering test. The legacy in-repo fallback stays until Phase 16. Runs autonomously with Phase 14 (`/gsd-autonomous --to 15`) and is not split further. PITFALLS.md 12, 13, 14, 25, 29 (path length over about 100 characters, deleted-folder rule, non-modal dialogs).
**Plans**: 16/16 plans complete (4 gap-closure plans after the automated UAT)

Plans:
**Wave 1**
- [x] 15-01-PLAN.md — Tracer: `--library-root` / `KICAD_LIBMGR_ROOT` start end to end; `collection.py` check and resolve; `MainWindow(library_root)`; the Library folder row and title
- [x] 15-02-PLAN.md — `procs.run_process` for every child process; `git init` allow-listed as `gitops.init_repository`
- [x] 15-03-PLAN.md — Commit step `parent_mode` (gitlink / none); the panel hides the parent option for a new collection
- [x] 15-04-PLAN.md — `.git` pruned at any depth in both walkers; path variables offered for any library folder; `would_change_path_vars`
- [x] 15-05-PLAN.md — `library/root` and `library/recent` settings; `configured_library_folder`; D-26 copy for the library folder

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 15-06-PLAN.md — `create_collection` with refusals and cleanup; the New Collection dialog
- [x] 15-07-PLAN.md — Folder switching: `_switch_root` and the busy guard, Recent Library Folders, Use KiCad's Folder, Open in Explorer, amber tag, post-switch path-variable offer
- [x] 15-12-PLAN.md — The literal `Custom` swept from the importer package; the AST guard's walk and importer half

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 15-08-PLAN.md — Choose Library Folder dialog and the first-run window
- [x] 15-09-PLAN.md — The literal `Custom` swept from the core, scanner and window modules; the guard completed for the whole package; collection in the layering map

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 15-10-PLAN.md — Choose Library Folder wiring, Change Folder..., empty-collection page, focus; full start order and first-run hand-off

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 15-11-PLAN.md — End-to-end new collection import and commit (real git, both shapes); User Guide and CLAUDE.md; UAT list

**Wave 6** *(gap closure after the automated UAT; blocked on Wave 5 completion)*
- [x] 15-13-PLAN.md — Gap 1 (main window): folder checks on daemon threads via `widgets/background.py`; a check blocked at close never a live QThread; child-process exit test
- [x] 15-14-PLAN.md — Gap 3: New Collection never overlaps, Choose strip rows shown in full; geometry tests at default scale and 1.75

**Wave 7** *(blocked on Wave 6 completion)*
- [x] 15-15-PLAN.md — Gap 1 (dialogs): Choose, first-run and New Collection checks on the background runner; parking helper removed; AST guard
- [x] 15-16-PLAN.md — Gaps 2 and 4: empty page by content (empty `.pretty` counts as empty, saved scan format 3); Destination follows a switch from the old folder or a blank box
**UI hint**: yes

### Phase 16: Repo Split

**Execution**: Interactive phase. Run with `/gsd-discuss-phase 16` and step-by-step execution, not `/gsd-autonomous`; the autonomous run stops after Phase 15.
**Goal**: The app code lives in a public tool repo that holds nothing private, and the owner's libraries live in a private collection repo with no code, while the owner's KiCad keeps working exactly as before
**Depends on**: Phase 15 (the app must run outside the repo before the code leaves it)
**Requirements**: SPLIT-01, SPLIT-02, SPLIT-03, SPLIT-04, SPLIT-05, SPLIT-06, SPLIT-07, SPLIT-08
**Success Criteria** (what must be TRUE):
  1. The tool repo holds the app code, tests, pyproject, planning and build scripts and no library content; the collection repo holds `Custom` and the third-party libraries and no code.
  2. The owner's KiCad keeps working after the split: every table URI resolves, with zero missing libraries before and after.
  3. The visibility of both GitHub repos is decided and set, and a pre-publish scan of the tool repo's full history finds no owner paths, vendor downloads, part data or other private or licence-restricted content.
  4. A fresh clone of the tool repo, without the collection, passes the test suite within a stated skip budget, with a synthetic sample in place of the TI vendor zip if that can't be published.
  5. The tool repo has a chosen licence, a README covering install and first run, the developer docs and the documented dev workflow (the tool runs against a chosen collection: the main checkout for KiCad, scratch collections for tests); the collection README covers naming, the atomic rule and the path variables.
**Open owner decisions** (from research SUMMARY.md):
  - D1 Split direction and history: keep this repo and its history as the public tool repo (collection a fresh `git init`), keep it as the private collection and build the tool repo from a filtered copy, or give the tool repo a fresh squashed history. The history holds 1,584 commits with `Co-Authored-By` / `Claude-Session` trailers and workstation paths.
  - D10 Licence for the tool repo (research placeholder: MIT), and how third-party share-alike content is treated.
  - D12 Whether the tracked `downloaded_examples/ul_CSD85301Q2.zip` (TI, Ultra Librarian) may be redistributed; if not, a synthetic builder replaces it first.
  - D13 Whether `.planning/` is published as is or scrubbed (workstation paths, part data).
  - D14 Repo visibility: `sylvanoMTL/kicad_libraries` and `sylvanoMTL/kicad_custom_library` are both public as of 2026-11-22. Make them private, or accept public and treat the split as stopping future exposure only.
**Research flags**: Interactive session first (D1, D10, D12, D13, D14). `git filter-repo` with gitlinks is unverified: rehearse on a throwaway clone and diff `git ls-tree -r HEAD`.
**Notes**: Rehearse on `git clone --no-local` copies first, with a `git bundle` and a `pre-split` tag; keep the library layouts and compare the resolved table URI list before and after (the 2026-10-21 incident). The live split runs from the main checkout KiCad reads (D-26). WurthElektronik stays a submodule in the collection until Phase 17. The tool repo gets Windows CI (`pytest -m "not slow"`); the legacy in-repo fallback is removed, the conftest live-collection guard is repointed and the library corpus becomes opt-in (`KICAD_TEST_CORPUS`). About 25 test modules read `Custom`, `WurthElektronik`, `downloaded_examples` or `.planning`; each is classified so the public suite can't go green by skipping. CLAUDE.md is split between the two repos. PITFALLS.md 8, 9, 10, 11, 12, 22.
**Plans**: 18/18 plans complete (13 code plans in waves 1-4, the rehearsal, 4 live-run plans; waves 6-9 are interactive)

Plans:
**Wave 1**
- [x] 16-01-PLAN.md — Tracer: synthetic Ultra Librarian zip (`tests/ulfixtures.py`) behind `zipfixtures.UL_ZIP` and `ul_package`; builder proven against all 31 Bucket A modules
- [x] 16-02-PLAN.md — `Source.LEGACY` removed: the code folder is never a library folder; User Guide and window default
- [x] 16-03-PLAN.md — `scripts/prepublish_scan.py`, `scripts/check_skip_budget.py`, Windows CI workflow; code-area findings cleared at the source
- [x] 16-05-PLAN.md — Collection side: `uri_diff.py` (D-22) and `cutover_collection.py` with the collection README, CLAUDE.md and .gitignore

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 16-04-PLAN.md — Tool-repo export: allow-list, scrub, `verify_export`, `build_tool_repo`, `sync_planning`; commit-msg and pre-push hooks (after 16-03: the hook runs its scan)
- [x] 16-06-PLAN.md — `corpus` and `needs_kicad` markers deselected with printed counts; `KICAD_TEST_CORPUS`, `KICAD_TEST_HIDE_KICAD`; guard on the corpus Custom/
- [x] 16-07-PLAN.md — Tool docs: MIT LICENSE, tool README (install, first run), tool CLAUDE.md with the dev workflow; `test_docs_split.py`
- [x] 16-17-PLAN.md — Seven Bucket A modules repointed at `UL_ZIP` (adapter, gate, generated-text, round-trip, KiCad-file, edits); pinned-hash test deleted
- [x] 16-18-PLAN.md — Seven Bucket A modules repointed at `UL_ZIP` (import window, install, suggestion, SnapEDA); vendor-sample skip deleted

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 16-08-PLAN.md — D-18 classification; live Custom / Wurth readers on the corpus
- [x] 16-09-PLAN.md — Real vendor downloads on the corpus; UL builder checked against the real sample; stay-local test and zip exception gone
- [x] 16-10-PLAN.md — `needs_kicad` on the twelve stock-library tests

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 16-11-PLAN.md — Static corpus audit; fresh-clone proof of the skip budget with and without KiCad; corpus run; tests/README.md; kept planning files scan clean

**Wave 5** *(blocked on Wave 4 completion; interactive)*
- [x] 16-12-PLAN.md — Rehearsal on `--no-local` copies: build, scan, fresh-clone tests, scratch remove-code commit, URI diff, corpus run

**Wave 6** *(interactive; this session, every git command on the main checkout)*
- [x] 16-13-PLAN.md — Live 1: preflight, owner go, bundles, both repos private, merge into main, push main / v2.0 / pre-split, stray branches deleted

**Wave 7** *(interactive)*
- [x] 16-14-PLAN.md — Live 2: build from pre-split, scan, owner approval, private `kicad-lib-manager`, CI, tool checkout with its own env and local setup, handoff

**Wave 8** *(interactive; new session in the tool checkout after the handoff sync)*
- [x] 16-15-PLAN.md — Live 3: remove-code commit in the main checkout, URI diff identical with zero missing, push, smoke start, old venvs

**Wave 9** *(interactive; tool checkout session)*
- [x] 16-16-PLAN.md — Live 4: read-only retirement inventory and final scan of GitHub's copy, owner approves what the retirement removes, worktree retired and memory moved as approved, owner flips the tool repo public
**UI hint**: no

### Phase 17: Library Catalog

**Goal**: The user can add, update and remove third-party KiCad libraries from GitHub inside the app, from a curated list or by URL, and WurthElektronik is managed this way in the owner's collection
**Depends on**: Phase 15 (collection root and manifest location), Phase 16 (WurthElektronik leaves the collection repo only after the tool repo no longer carries it)
**Requirements**: CAT-01, CAT-02, CAT-03, CAT-04, CAT-05, CAT-06, CAT-07, CAT-08, CAT-09, CAT-10, CAT-11, CAT-12
**Success Criteria** (what must be TRUE):
  1. The Library Catalog lists curated libraries with their status (not installed / installed / update available / problem), licence and size. A curated library is added in one click, with the licence shown before cloning and a shallow clone with progress and Cancel, validated before it is registered; it is recorded as a plain clone in the collection's manifest (URL, branch, commit, path variables), never a submodule, and appears in the scan and in Generate Tables.
  2. Add by GitHub URL installs a KiCad library and refuses non-KiCad, KiCad 5-only, PCM-only and private repos with a message saying why; every Add warns about nickname collisions with KiCad stock, other catalog or `Atomic_` libraries and never renames automatically.
  3. User can update an installed library, and remove one (clone and manifest entry) after a confirmation naming what goes. At startup a background check compares each installed library's remote and local commit without downloading, flags "Update available", never blocks, and shows the status as unknown with no error when offline.
  4. The path variables a library needs (for example `WE_3DMODEL_DIR`) are set through the old -> new confirmation, so its 3D models resolve; KiCad's PCM `PCM_` entries, `3rdparty` folder and `installed_packages.json` are never touched; network git runs only in a separate runner (https only, no hooks or credential prompts, no submodule recursion, long paths on, autocrlf off), and the commit path cannot reach the network.
  5. Würth and SparkFun work end to end and form the curated list; KiCad's reviewed libraries (such as 4ms and Alternate-KiCad-Library) are listed from KiCad's official add-on list, whose review counts as their verification, and Espressif is rejected from the curated list with its reason (D-33, D-37); in the owner's collection WurthElektronik is a catalog entry with no missing library or 3D model afterwards.
**Research flags**: Decide at plan time: D2 (clone location and Würth path: `ThirdParty/<id>/` with a one-time rewrite of about 89 `WurthElektronik/...` URIs, or `<Vendor>/<Repo>` with Würth kept in place; `source_of` handles both), D6 (minimum git: 2.49.1+ for CVE-2025-48384 with a warning below; this machine has 2.49.0), D7 (update by `fetch --depth 1 origin <ref>` + `reset --hard FETCH_HEAD` on a clean tree, recommended, or `merge --ff-only`), D11 (curated list and licence gate: refuse libraries with no licence, or warn and ask for acknowledgement; research leans to the latter). Research: Git LFS pointer detection during staging (`version https://git-lfs`) and the GitHub 304 / ETag cost of the startup check (60 requests per hour unauthenticated). Unverified: Git Credential Manager versus `GIT_TERMINAL_PROMPT=0` (test with a private URL, also set `GCM_INTERACTIVE=Never`); the 3D model paths of Espressif, 4ms and Alternate-KiCad-Library.
**Notes**: Build order from research: (a) `catalog/gitnet.py` plus a `gitops.launch()` extraction, a layering test that commit-path modules cannot import gitnet, and a threat-model note; (b) manifest, curated list, `scan_source`, `sync_kicad_path_vars(extra_vars=...)`; (c) add / update / remove as plan, preview, apply, tested against local bare repos through `file://` (no network in tests); (d) catalog dialog with progress, Cancel and licence display; (e) the Würth conversion. Catalog Add and Remove change only the collection and its manifest; tables are written by Generate Tables (project-local from Phase 18). The update check runs automatically at startup (owner, 2026-11-22). The Würth conversion is a previewed transaction from the main checkout with a rollback tag: clone, verify the library set, define `WE_3DMODEL_DIR` (7,612 footprint model paths use it), Generate, rescan with zero missing, then remove the submodule (`deinit -f`, `git rm`, delete `.git/modules/...`). PITFALLS.md 6, 15-22.
**Plans**: 19/27 plans executed in 19 waves (23 code plans, 3 owner checkpoints, 1 curated-list update); executors run sequentially on main this run. Plans 17-21 to 17-27 were inserted after the 17-17 owner check (its findings 1-6 and 8, decisions D-33 to D-37) and run before 17-18

Plans:
**Wave 1**
- [x] 17-01-PLAN.md — Tracer: a `file://` library through `procs.StreamedProcess`, hardened `catalog/gitnet`, staging, `ThirdParty/<id>`, `catalog.json`, the scan and the table URIs
- [x] 17-02-PLAN.md — Folded todo: the migration window stops its draft and rebuild timers on close

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 17-03-PLAN.md — Full gitnet surface, git version policy (refuse below 2.32, warn below 2.49.1), clone config allow-list, layering rules cutting the commit path off the network
- [x] 17-04-PLAN.md — URL and id rules, validated `catalog.json`, curated list (Würth, SparkFun) with 4ms / Alternate-KiCad-Library / Espressif as candidates, licence labels

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 17-05-PLAN.md — Scanner: `${VAR}` 3D model rule, `.staging` prune, `scan_source` / `remove_source`, `extra_vars`, catalog-aware table descriptions

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 17-06-PLAN.md — Staging check: refusals (not KiCad, KiCad 5 only, PCM only, LFS, links), collisions, path-variable detection, unresolved models

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 17-07-PLAN.md — The GitHub lookup, `fsutil.remove_tree`, Add and Reinstall as plan, stage and register (disk space, licence tick, `.gitignore` line)
- [x] 17-08-PLAN.md — Würth-specific code and tests follow `ThirdParty/<id>`; vendor-name invariant test
- [x] 17-09-PLAN.md — `scripts/catalog/wurth_to_catalog.py`: dry run and apply, the three D-26 pass checks, bundle and tag, module data moved, way back

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 17-10-PLAN.md — Update and Remove, statuses, `check_updates`, slow real-git lifecycle proofs

**Wave 7** *(blocked on Wave 6 completion)*
- [x] 17-11-PLAN.md — Catalog window, browse slice: shell, notice strips, list, search, Details page, Check for Updates

**Wave 8** *(blocked on Wave 7 completion)*
- [x] 17-12-PLAN.md — Main window: File > Library Catalog... (Ctrl+Shift+L) with update count, startup check, busy rules, path-variable wiring
- [x] 17-13-PLAN.md — Add, Add by URL and Reinstall pages and jobs; job strip with Cancel; close question

**Wave 9** *(blocked on Wave 8 completion)*
- [x] 17-14-PLAN.md — After a job: source rescan, preselection, Würth selection carry-over (D-28), path-variable question
- [x] 17-15-PLAN.md — Update preview, dirty refusal, Remove confirmation, Set Path Variables...

**Wave 10** *(blocked on Wave 9 completion)*
- [x] 17-16-PLAN.md — User Guide page, shortcut row, CLAUDE.md, README, tests/README slow-module list

**Wave 11** *(owner checkpoint, real network)*
- [x] 17-17-PLAN.md — D-22 real-network checks (SparkFun, 4ms, Alternate-KiCad-Library, Espressif), Cancel, offline start, a real update

**Wave 12** *(blocked on Wave 11)*
- [x] 17-21-PLAN.md — Catalog window fixes from 17-17: file count while a download is checked, size on disk in the list, Remove page counts by kind, one name for a library added by address (`catalog/names.py`)

**Wave 13** *(blocked on Wave 12 completion)*
- [x] 17-22-PLAN.md — D-33 reader: KiCad's add-on list (`catalog/addons.py`), cache-aware and hardened, listings with not-addable reasons, KiCad's licence names, fixture and no-network guard
- [ ] 17-23-PLAN.md — Main window fixes from 17-17: refreshing state with a spinning wheel and file count over the trees, one log line per catalog library, catalog names in the trees

**Wave 14** *(blocked on Wave 13 completion)*
- [ ] 17-24-PLAN.md — D-33/D-34 names: KiCad's add-on names (`PCM_`) decided from a library's own links, recorded in `catalog.json`, applied by every scan; KiCad's own add-on manager left alone

**Wave 15** *(blocked on Wave 14 completion)*
- [ ] 17-25-PLAN.md — D-33/D-36 window: KiCad's add-on list in the catalog (rows, Cannot be added yet, Listed in, Add from the list, licence from the list, Names in KiCad; offline the last kept copy with its date)
- [ ] 17-27-PLAN.md — D-35 scratch switch for owner checks: `--scratch-root` / `KICAD_LIBMGR_SCRATCH_ROOT` move the app's settings, saved scans, backups and KiCad's settings folder under one folder

**Wave 16** *(blocked on Wave 15 completion)*
- [ ] 17-26-PLAN.md — UI-SPEC, User Guide, CLAUDE.md and README for plans 17-21 to 17-25 and the scratch switch

**Wave 17** *(blocked on Wave 16 completion)*
- [ ] 17-18-PLAN.md — Curated list after 17-17 and D-33: Würth and SparkFun stay, 4ms and Alternate-KiCad-Library come from KiCad's list, Espressif recorded in REJECTED

**Wave 18** *(owner checkpoint)*
- [ ] 17-19-PLAN.md — Owner check of KiCad's add-on list with 4ms (D-37), then the Würth conversion rehearsal on a `--no-local` copy, all with `--scratch-root`

**Wave 19** *(owner checkpoint, live run)*
- [ ] 17-20-PLAN.md — Live Würth conversion from the main checkout (real settings; the scratch switch stays off)
**UI hint**: yes

### Phase 18: Project-Local Table Model

**Goal**: Generate Tables writes the library tables into the KiCad project the user picked, never into KiCad's global tables, and the user can see which project and which table model apply
**Depends on**: Phase 17 (catalog Add and Remove and Generate must agree on what a project's table lists)
**Requirements**: TBL-03, TBL-04, TBL-05, TBL-06, TBL-07
**Success Criteria** (what must be TRUE):
  1. Generate Tables writes `sym-lib-table` and `fp-lib-table` into the KiCad project folder chosen as Destination, and KiCad's global tables are unchanged afterwards.
  2. The Destination shows which KiCad project it is, warns when the folder has no `.kicad_pro`, and keeps recent project folders.
  3. After a library is removed from the collection, the next Generate drops it from the project's tables and the log names it.
  4. Generate states the table model (project-local, never global) and the User Guide explains it; when KiCad's global tables also list a managed library, the app warns that the project table shadows it.
**Research flags**: D5 was decided by the owner on 2026-11-22: project-local tables only. Research had recommended a global default, so its deliverables built on global tables (such as a Destination defaulting to KiCad's config folder) no longer apply. Verify on KiCad 10 that a project table takes precedence over the global one and how `.lck` files behave (MEDIUM confidence).
**Notes**: A `table_generator.remove_library_entries(dest, rel_prefix)` style removal covers TBL-05. Open for discuss-phase: what happens to the managed entries already in the owner's global tables (Generate never writes there; TBL-07 warns about them). PITFALLS.md 23, 24 (project tables shadow global ones by nickname).
**Plans**: TBD
**UI hint**: yes

### Phase 19: Menu Regroup

**Goal**: The menus are grouped by what they act on, File / Libraries / KiCad / Help, with every v3.0 action in its agreed place and every shortcut unchanged
**Depends on**: Phase 15, Phase 17, Phase 18 (every new action exists, so each is placed once)
**Requirements**: MENU-01, MENU-02, MENU-03
**Success Criteria** (what must be TRUE):
  1. The menu bar reads File / Libraries / KiCad / Help with the layout decided on 2026-11-13: File = Import Part, Exit; Libraries = Rescan Libraries, Select All / Deselect All, Check Atomic Parts, Migrate to Atomic Libraries; KiCad = Generate Tables, Restore Backup, Pin Atomic Libraries in KiCad, Set KiCad Footprint Path; Help unchanged.
  2. Choose library folder..., the recent library folders, Open in Explorer and Library Catalog sit in the menus agreed for them.
  3. Every shortcut works as before (Ctrl+I, Ctrl+G, Ctrl+R, Ctrl+K, Ctrl+Shift+M, Ctrl+Shift+K, Ctrl+Shift+A, Ctrl+Shift+R, Ctrl+Q, F1), checked by a test that enumerates the menu actions against the CLAUDE.md shortcut table.
  4. The User Guide and CLAUDE.md name the new menu paths, and the User Guide still reopens on the section last chosen.
**Research flags**: Standard. Keep the User Guide section keys stable (the saved last section is keyed by name); PITFALLS.md 32.
**Notes**: Former backlog 999.1 (Phase 13 UAT Test 4). Layout with separators as decided: Libraries = Rescan Libraries (Ctrl+Shift+R), Select All / Deselect All, separator, Check Atomic Parts (Ctrl+Shift+A), Migrate to Atomic Libraries (Ctrl+Shift+M); KiCad = Generate Tables (Ctrl+G), Restore Backup (Ctrl+R), separator, Pin Atomic Libraries in KiCad (Ctrl+Shift+K), Set KiCad Footprint Path (Ctrl+K). The menu is named Libraries because Rescan and Select All also cover Würth; Pin lives under KiCad because it edits KiCad config. Phases 15 and 17 add their actions to the existing menus; this phase moves the existing QAction objects. ROOT-03 and ROOT-11 already put Choose library folder... and the recent folders under File; the place of Open in Explorer and Library Catalog is confirmed at discuss time.
**Plans**: TBD
**UI hint**: yes

### Phase 20: Python 3.14 Minimum

**Goal**: Python 3.14 is the one declared minimum everywhere, and a user on an older Python gets a clear message instead of a traceback
**Depends on**: Phase 16 (the tool repo's `pyproject.toml` and README)
**Requirements**: PY-01, PY-02, PY-03
**Success Criteria** (what must be TRUE):
  1. `pyproject.toml` declares `requires-python >=3.14` with the dependencies and dev groups, and the README states the minimum.
  2. PROJECT.md and CLAUDE.md constraints say Python 3.14, and a test fails if they disagree with `pyproject.toml`.
  3. The Python 3.10 compatibility check is gone, and the undefined-name check that replaces it still fails on a G-13-1-a kind of bug (a NameError hidden by 3.14's deferred annotations).
  4. Starting the app on an older Python shows a clear message naming the required version, not a traceback.
**Research flags**: Standard. The undefined-name check can be ruff F821 or `tests/test_annotations_resolve.py` rewritten with `annotationlib`.
**Notes**: Research suggests deleting the main checkout's old `env-py311` venv and noting it. The version guard sits in the app's entry point. PITFALLS.md 31.
**Plans**: TBD
**UI hint**: no

### Phase 21: Windows Installer and Release

**Goal**: Anyone on Windows can install the app from a GitHub release with a per-user installer, and the installed app behaves like the source app
**Depends on**: Phase 20 (the declared minimum and the frozen interpreter agree)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06, PKG-07
**Success Criteria** (what must be TRUE):
  1. One local command builds the frozen app (PyInstaller onedir) and the NSIS installer, and pushing a `v*` tag builds the installer in GitHub Actions and attaches it to the release with its SHA-256.
  2. The installer installs per user with a Start menu shortcut and an uninstaller, upgrades in place, and never deletes settings or the library collection.
  3. On a machine without Git for Windows, the installer explains, links the download and lets the user continue, and the app checks for Git again at startup.
  4. The installed app behaves like the source app: the saved scan is reused, no console window flashes for git or kicad-cli, the User Guide opens and an import runs.
  5. The app says when a newer GitHub release exists (it never installs it), and About shows the Qt/PySide6 LGPL notices that ship with the app.
**Research flags**: Freeze-tool spike before planning: PyInstaller 6.22.3 onedir (measured in research: 66 s build, 123 MB, 38 MB compressed, started offscreen) against Nuitka 4.3.5 (84 MB, about 5 minutes cold) on Python 3.14.4 and PySide6 6.12, comparing size, start time and Defender on a clean VM; Nuitka only if PyInstaller fails (D8). A PySide6-Essentials-only build is not yet tested against the full suite. Signing was decided by the owner on 2026-11-22: none, ship unsigned and document the SmartScreen warning (D15; SignPath stays FUT-02). Unverified: the frozen saved scan (`_code_signature()` returns "" without `.py` files; use the version plus a build stamp and assert a non-empty signature), the installer's running-app check (mutex or FindWindow), antivirus and SmartScreen behaviour (clean-VM Defender and VirusTotal in the release checklist).
**Notes**: From research: a `_version.py` single source; `main()` moved into `kicad_lib_manager/app.py` with the root script a shim; a committed `kicad_lib_manager.spec` (onedir, PySide6-Essentials, no UPX, licence files as data); a `--selftest` frozen smoke test (offscreen start, scan a tiny collection, exit 0); an NSIS 3.13 script (per-user under `$LOCALAPPDATA\Programs`, `RequestExecutionLevel user`, advisory Git check via PATH, HKCU and HKLM InstallPath and Program Files, no bundled Git; the uninstaller removes the program folder only and asks, default No, before settings); `release.yml` on `v*` tags. Child processes go through Phase 15's `run_process()` helper. PITFALLS.md 25-30.
**Plans**: TBD
**UI hint**: no

## Progress

| Milestone | Phases | Plans | Tasks | Shipped |
|-----------|--------|-------|-------|---------|
| v1.0 Part Importer | 1-7 | 70 | 148 | 2026-10-25 |
| v2.0 Atomic Libraries | 8-13 | 111 | 228 | 2026-11-13 |

**Execution Order:**
Phases execute in numeric order: 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21. Phases 14-15 run autonomously; Phase 16 is interactive.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 14. Test Suite Speed-Up | v3.0 | 6/6 | Complete    | 2026-11-23 |
| 15. Choose Library Folder and New Collection | v3.0 | 16/16 | Complete    | 2026-11-23 |
| 16. Repo Split | v3.0 | 18/18 | Complete    | 2026-11-26 |
| 17. Library Catalog | v3.0 | 19/27 | In Progress | - |
| 18. Project-Local Table Model | v3.0 | 0/TBD | Not started | - |
| 19. Menu Regroup | v3.0 | 0/TBD | Not started | - |
| 20. Python 3.14 Minimum | v3.0 | 0/TBD | Not started | - |
| 21. Windows Installer and Release | v3.0 | 0/TBD | Not started | - |

## Backlog

Former backlog 999.1 is now VER-01 (Phase 8) and 999.2 is now VER-02 (Phase 12).
The later backlog 999.1 (Phase 13 UAT Test 4, menu regroup) is now MENU-01..MENU-03 (Phase 19).

### Phase 999.3: Follow-up — Phase 12 deferred UAT follow-up: Test 3 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 12 verification
**Source phase:** 12
**Deferred at:** 2026-11-11 during /gsd-verify-work 12 session completion
**Follow-ups:**
- [ ] Test 3: KiCad-open question before the path-variable change (REV-05): re-test after the merge from the main checkout (not a worktree), changing CUSTOM_3DMODEL_DIR, with KiCad open; check Retry / Change anyway / Not now and that KiCad's other settings are kept. (deferred 2026-11-11)

### Phase 999.4: Follow-up — Phase 12 deferred UAT follow-up: Test 4 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 12 verification
**Source phase:** 12
**Deferred at:** 2026-11-11 during /gsd-verify-work 12 session completion
**Follow-ups:**
- [ ] Test 4: Window stays live during a real kicad-cli rebuild (REV-04): Finishing strip, slow note and Cancel with a real rebuild; too fast to catch by hand, covered by automated tests. (deferred 2026-11-11)
