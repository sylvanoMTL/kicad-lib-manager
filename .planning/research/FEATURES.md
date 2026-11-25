# Feature Research

**Domain:** Public desktop KiCad library manager (library-folder chooser, GitHub library catalog, table model, Windows installer), added on top of the existing PySide6 Library Manager + part importer
**Researched:** 2026-11-22
**Milestone:** v3.0 Public Library Manager (subsequent milestone; only new-feature areas covered)
**Confidence:** MEDIUM-HIGH (KiCad PCM behaviour and the third-party library facts are verified against KiCad docs, the live official PCM repository and the GitHub API on 2026-11-22; onboarding and installer conventions rest on established practice plus a few secondary sources)

Confidence tags used below: **[H]** official docs or data fetched directly today, **[M]** one secondary source or inference from verified facts, **[L]** general practice, not checked in this session.

---

## Key Findings (read this first)

1. **Do not build on KiCad's PCM; coexist with it.** PCM installs zipped, CI-built packages into the `KICAD<n>_3RD_PARTY` folder, prefixes nicknames with `PCM_`, writes only into the *global* tables, and rewrites 3D paths to `${KICAD<n>_3RD_PARTY}/3dmodels/<pkgid>/...` at packaging time [H]. A GitHub clone of the same project cannot be used as a PCM package and vice versa. The official PCM repository has only **17 library packages** today and has neither Würth nor Digi-Key [H, fetched 2026-11-22]. A git-clone catalog into the user's collection folder is a different product that fills the gap, and the two must simply not step on each other (never touch `PCM_` entries or `installed_packages.json`).
2. **The hard part of a clone catalog is not cloning, it is path variables.** Every vendor repo expects its own variable for 3D models: Würth `${WE_3DMODEL_DIR}`, SparkFun `${SPARKFUN_KICAD_LIBRARY}`, CDFER `${KICAD8_3RD_PARTY}/3dmodels/<pkgid>/`, Alternate-KiCad-Library `${KICAD10_3DMODEL_DIR}` [H, sampled from the repos]. A catalog entry therefore has to carry (a) where the `.kicad_sym` / `.pretty` / 3D roots are inside the repo and (b) which path variables to define and what they point to. The app already has the "show `VAR: old -> new`, ask, back up, write `kicad_common.json`" flow; the catalog reuses it.
3. **Many popular "KiCad libraries" are not drop-in clones.** Digi-Key is unmaintained and ships 1,223 legacy `.lib` files, zero `.kicad_sym` [H]; Seeed OPL has 15 `.lib` + 1 `.kicad_sym` and irregular folder names [H]; Espressif's `main` is the PCM packaging source and its README says PCM is the recommended install [H]. "Add by URL" needs validation that explains these cases instead of cloning blindly, and the curated list must be small and tested.
4. **Existing git runner forbids network subcommands on purpose** (PROJECT.md Key Decisions: no remote subcommand, never push). The catalog needs a second, separate allow-list (clone, fetch, ls-remote, fast-forward merge) rather than loosening the first one.
5. **Würth's licence is proprietary** (limited, non-sublicensable licence in `License_Terms_WE_KiCad_library.pdf`; GitHub reports `NOASSERTION`) [H/M]. That alone is why the public tool repo must not carry it and why "clone on demand" is right. Show the licence before cloning anything.

---

## Feature Landscape

### Area 1: Library folder choice and first run (v3.0 feature 2)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Resolve the library folder in a fixed, visible order: remembered explicit choice, else folder named by KiCad's `KICAD_LIB_GITHUB`, else first-run prompt | Desktop tools that manage a data folder (Obsidian vaults, Calibre libraries, Zotero data dir) all ask once, remember, and show where the data lives | MEDIUM | `library_scanner` already reads `kicad_common.json`; `settings.py` already persists (QSettings). Replaces module-level `REPO_ROOT` in `main_window.py`; every use of it must go through one accessor. |
| Current folder always visible (window title or status bar) and changeable via `File > Choose library folder...` | Users must be able to tell which collection they are editing, and fix a wrong choice without editing an INI file | LOW | Per-folder scan cache already exists (one file per repository folder), so switching folders is cheap. |
| First-run dialog with three clear paths: use KiCad's folder, choose an existing folder, create a new empty collection | A new user has no collection; a blank window with empty trees reads as broken | MEDIUM | Reuse the existing KiCad-detect code. Offer "KiCad's folder" only when `KICAD_LIB_GITHUB` resolves to an existing folder. |
| Validate a chosen folder (exists, writable, not inside the app's install dir or `Program Files`, not a drive root) and say why when refused | After the installer exists, the app lives under a read-only path; writing libraries there fails confusingly | LOW | New code; cheap and prevents the worst first-run failure. |
| New empty collection: `Custom/Symbols/`, `Custom/Footprints/Atomic_Footprints.pretty/`, `Custom/3DModels/`, `git init`, `.gitignore`, a short README, so the first import works | The milestone target: "a new user can import a first part" | MEDIUM | Must match what the importer and atomic scan expect (`Atomic_Footprints.pretty` is the shared footprint library). Design question for requirements: is the collection root the git repo with `Custom/` a plain folder (recommended), or a nested repo? The commit step today assumes `Custom` is a separate repo with the parent holding a gitlink. |
| Helpful empty state when the folder has no libraries ("Import a part" / "Add a library from the catalog") | Empty trees give no next step | LOW | Pure UI. |
| After creating a collection, offer to point KiCad at it using the existing confirm flow (`KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR`, old -> new, backup, default No) | Without the variables KiCad cannot resolve the new libraries; the app must not write them silently (project constraint) | LOW | Existing `_sync_path_vars` + HARD-03. |
| Existing D-26 wrong-checkout warning keeps working with a chosen folder (warn when chosen folder is not what `KICAD_LIB_GITHUB` names) | Same failure mode, new cause | LOW | Reuse; message wording needs to stop assuming "the checkout KiCad reads" is a git worktree concept. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Recent collections list (switch between a private and a test collection) | The owner has a private collection and a throwaway one for testing the public flow | LOW | Mirror the existing destination-history pattern. |
| "Open folder in Explorer" and "Copy path" on the folder indicator | Users hunt for where files went | LOW | `QDesktopServices`. |
| Graceful no-KiCad state (app opens, browse and catalog work, KiCad-dependent actions greyed with tooltip) | Public users may run the tool before installing KiCad | MEDIUM | Several existing actions assume a KiCad config dir exists. |

#### Anti-Features

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Silently create a folder in Documents on first launch | "Zero-click onboarding" | Surprising writes, OneDrive-redirected Documents on Windows (KiCad's own `3rdparty` has this trap [M]), violates "no write without preview" | Prompt with a proposed default path the user can accept or change |
| Auto-write KiCad path variables at first run | "It should just work" | The 2026-10-21 incident that created the confirm-before-write rule | Keep the confirm dialog |
| Several collections active at once | Power-user wish | Scan, tables, `KICAD_LIB_GITHUB` are single-valued; collisions across collections | One active collection, quick switching |
| Ship starter libraries inside the installer/tool repo | Nicer first run | Licensing (Würth), repo bloat | Offer "Add starter libraries from the catalog" after creation |

---

### Area 2: Library catalog (v3.0 feature 4) and PCM coexistence

#### How the comparable tools work

| Tool | Install unit | Where files go | Table handling | Updates | Notes |
|------|--------------|----------------|----------------|---------|-------|
| **KiCad PCM** [H] | Zip with root `metadata.json`; library zip holds `symbols/*.kicad_sym`, `footprints/*.pretty`, `3dmodels/*.3dshapes`, optional `resources/icon.png` | `KICAD<n>_3RD_PARTY` (default under the user's Documents folder, "Open Package Directory" button), tracked in `installed_packages.json` | Auto-adds entries to **global** tables only, nickname prefix `PCM_` (changeable in Preferences > Packages and Updates; option "Automatically add installed libraries to global library table") | Version list per package with `status` (stable/testing/development/deprecated), `kicad_version` and `kicad_version_max`, `download_sha256`, `download_size`, `install_size`; `keep_on_update` regexes | Custom repos: Manage > "+" > repository URL. Repository = static JSON (`repository.json` pointing at `packages.json` and `resources.zip`, v2 schema via `Accept: application/vnd.kicad.pcm.v2+json`). KiCad 10 needs a restart before new libraries show (SparkFun README) [H] |
| **Fusion 360 / Eagle library manager** [H/M] | Library (cloud object) | Cloud / hub | n/a (libraries are "activated" in the Place Panel) | Update from the Library Manager when remote changes exist; Eagle offers per-library Update and Update All | Public libraries are read-only; to edit you save a copy ("fork"); search by library/component name, preview components before activating, remove unused libraries |
| **KiLM (barisgit/KiLM)** [H] | Local library repo | User-chosen | Adds libraries to KiCad config, sets env vars, pins favourites, timestamped backups, dry-run | `kilm update` for GitHub-based libs; MIT, v0.6.1 (2026-10-23), actively maintained; CLI only, also imports SamacSys/UltraLibrarian/SnapMagic ZIPs | The closest community tool. Same backup/dry-run instincts as this app. CLI-only: no catalog UI, no atomic rule. |
| **SparkFun / Espressif / 4ms / CDFER repos** [H] | Both: PCM zips *and* a git repo | PCM: `3rdparty`; git: anywhere | PCM or manual | PCM notifies of new versions | SparkFun's README says only a true clone lets you edit existing SparkFun designs, because PCM rewrites its `SPARKFUN_KICAD_LIBRARY` paths to `KICAD9_3RD_PARTY`. This is direct evidence that a clone-based path has real users. |

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Catalog window: list with name, vendor, short description, licence, size, supported KiCad version, status (Not installed / Installed / Update available / Problem) and search/filter | Fusion/Eagle/PCM all give a browsable list with status. This is what "like Fusion 360 / Eagle" means | MEDIUM | New widget in `widgets/`, Qt-free `catalog` service beside `library_scanner`. |
| One-click **Add**: shallow clone into the collection, with progress, Cancel, readable errors, no blocking GUI thread | "One click" is the milestone promise; Würth is about 2.7 GB on GitHub (history included), so progress and shallow clone are not optional | HIGH | `git clone --depth 1`, `-c core.longpaths=true` (Windows MAX_PATH with long 3D model names) [L], `GIT_TERMINAL_PROMPT=0` so a private or mistyped URL fails instead of hanging on a credential prompt [L], no submodule recursion, never run anything from the cloned repo. Worker follows the `ScanWorker` QThread pattern. Needs its own git allow-list (see Dependencies). |
| **Update**: fetch + fast-forward, with an "update available" indicator | Every manager has it; PCM notifies of new versions | MEDIUM | Indicator via `git ls-remote` HEAD compare (no clone cost, no GitHub API rate limit). Refuse or warn when the working tree is dirty. Record the commit SHA installed. |
| **Remove**: delete the clone and the managed table entries it produced, after a confirm that names both | Add without Remove is a trap | MEDIUM | Existing `table_generator` merge already drops managed entries for vanished libraries and reports "removed nicknames"; reuse. Deleting a 2.7 GB tree on Windows can be slow (read-only `.git` pack files need chmod before `rmtree`) [L]. |
| After Add: show the libraries found, pre-selected, and go through the existing preview -> table update -> path-variable confirm path | Cloning without wiring it into KiCad leaves the user stuck | MEDIUM | Reuse post-install add-only table logic (POST-01) for the "new library" case; Generate for the rest. Use the existing "Rescan this library" for a fast refresh instead of a full rescan. |
| Per-entry **path variables**: entry declares which variables to define and the clone-relative target (Würth `WE_3DMODEL_DIR`, `WE_SYMBOL_DIR`, `WE_FOOTPRINT_DIR`; SparkFun `SPARKFUN_KICAD_LIBRARY`) | Without it every 3D model in the library is missing; the most common failure for GitHub libraries | MEDIUM | `kicad_common.json` write already exists with confirm, backup, running-KiCad check. Extend its variable set from two fixed names to a per-source list; the existing 3D-path scan will surface unresolved variables. |
| Curated list that is small and verified end to end (clone, scan, generate, KiCad loads it) | An unvetted long list is worse than a short one: every broken entry is a support request | MEDIUM | Suggested seed set below. Ship as bundled JSON in the app. |
| **Add by URL** with validation: accept `https://github.com/<owner>/<repo>` (strip `.git`, `/tree/...`), clone, scan, and reject clearly when there is nothing usable | The milestone requires it; the validation messages are the feature | MEDIUM | Messages needed: "no `.kicad_sym` or `.pretty` found", "legacy `.lib` (KiCad 5) format only, not supported" (Digi-Key case), "this repository looks like a PCM package source; install it through KiCad's PCM instead" (Espressif case), "needs authentication; private repositories are not supported". |
| Show the licence before and after cloning (SPDX from the manifest entry, or the repo's `LICENSE*` file once cloned) and require an acknowledgement for unknown or non-permissive terms | Public users will add proprietary or share-alike libraries unknowingly (Würth is a proprietary licence; Digi-Key/Espressif are CC-BY-SA-4.0 with a designs exception; SparkFun is CC BY 4.0) | LOW-MEDIUM | GitHub reports `NOASSERTION` for Würth, Digi-Key, Espressif even though licence files exist, so do not rely on the API's SPDX field alone. |
| Coexistence with PCM: never edit `PCM_*` entries, never touch `3rdparty` or `installed_packages.json`; warn on a nickname collision with a PCM-installed library | Users will have both; duplicated symbols in the chooser are confusing | LOW | Existing merge already preserves entries without the managed marker as external; HARD-08 collision detection already works across sources. Add a note, not new machinery. |
| WurthElektronik becomes a catalog entry that keeps its current location (`WurthElektronik/KiCad-Library`) | The managed table entries already reference `${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library/...`; changing the folder orphans every entry in the owner's tables | LOW (feature) / MEDIUM (migration) | Submodule -> plain clone needs `git submodule deinit`, removing `.gitmodules` and the gitlink. That belongs in the repo-split phase. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Manifest committed in the collection (`catalog.json`: url, ref, installed SHA, variables, source name) so a collection can be re-created on another machine with "Restore catalog libraries" | Plain clones are git-ignored; the manifest is the reproducible record (what submodules gave, without their friction) | MEDIUM | This is the "plain clones + manifest" answer; submodules force a parent-repo commit and detached-HEAD handling on every update, which is hostile to non-git users. |
| Catalog entry schema borrows PCM vocabulary (`identifier`, `name`, `description`, `license`, `kicad_version` / `kicad_version_max`, `resources.homepage`, `status`) | Familiar to library authors, and leaves the door open to read a PCM `repository.json` as a listing source later | LOW | Vocabulary only; the install mechanism stays git. |
| "Also available through KiCad PCM" hint on entries that publish PCM packages (SparkFun, Espressif, 4ms) | Honest guidance: PCM is the better choice when the user does not need editable paths or other KiCad-version coverage | LOW | A boolean and a sentence in the entry. |
| Atomic-rule check on a clone before adding it (report only: "62 of 403 parts fail the atomic rule") | Unique to this app: a quality score for third-party libraries | LOW (reuses scan) | Do not offer to fix: third-party libraries are upstream-owned (already out of scope). |
| Pin to a tag or commit per entry; "Update" moves to the newest tag instead of branch HEAD | Reproducible designs | MEDIUM | Defer; branch HEAD is enough for v3.0. |
| Size estimate and disk-space check before cloning | Würth/SparkFun/Espressif installs run from tens of MB to several hundred MB (Espressif PCM install_size about 350 MB) | LOW | Entry carries `install_size`; check free space. |
| Remote-updatable curated list (fetched JSON with bundled fallback) | Keeps the list fresh without an app release | MEDIUM | Defer; needs hosting, signature or trust story, offline fallback. |

#### Anti-Features

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Implement a PCM client (download zips, sha256, install into `3rdparty`, write `installed_packages.json`, `PCM_` prefix) | "Reuse the official mechanism" | Duplicates KiCad's own UI; PCM state is owned by KiCad and per-KiCad-version; packages are built artifacts, and most vendors do not publish them; paths are rewritten per KiCad major | Coexist; point users to PCM where an entry is PCM-first |
| Install into KiCad's `KICAD<n>_3RD_PARTY` folder | Looks "standard" | Per-KiCad-major location, may sit under a OneDrive-redirected Documents folder [M]; collection folder is the project's whole premise | Clone into the collection |
| Git submodules for catalog libraries | Existing Würth setup | Each add/update dirties the parent repo, needs commits and gitlink bumps, confuses users without git skills; public-tool users have no parent repo at all | Plain clones + manifest |
| Arbitrary git URLs (ssh, `file:`, any host, credentials in URL) | Flexibility | Credential prompts, hangs, local-path abuse, SSH key surface | `https://` on a short list of hosts (github.com first, gitlab.com next); clear "unsupported" message otherwise |
| Editing or "fixing" files inside a third-party clone | Atomic-rule fixes could apply | Upstream-owned; breaks fast-forward updates | Report only; import into `Custom/` instead |
| Auto-update on launch | Convenience | Silent 2.7 GB network use, surprise table changes | "Update available" indicator and explicit Update |
| Long unvetted curated list or scraping GitHub for KiCad libraries | "Like an app store" | Quality and licence liability | 3-6 verified entries plus Add by URL |
| Using the GitHub REST API for discovery | Search and licence metadata | Unauthenticated rate limit (60 requests/hour) [L]; some repos return `NOASSERTION` | `git ls-remote` and the cloned tree |

#### Suggested curated seed list (facts verified 2026-11-22 via GitHub API and repository files)

| Library | Repo | Licence | Layout | Path variable it expects | Fit for clone catalog |
|---------|------|---------|--------|--------------------------|-----------------------|
| **Würth Elektronik** | `WurthElektronik/KiCad-Library` | Proprietary WE eiSos licence terms (PDF); limited, non-exclusive, non-transferable, non-sublicensable; GitHub `NOASSERTION` | 403 `.kicad_sym`, 43 `.pretty`, 7,478 3D files (STEP); ships its own `sym-lib-table`/`fp-lib-table`; about 2.7 GB on GitHub | `${WE_SYMBOL_DIR}`, `${WE_FOOTPRINT_DIR}`, `${WE_3DMODEL_DIR}` | HIGH. Already used; must be shallow-cloned; licence shown. |
| **SparkFun KiCad Libraries** | `sparkfun/SparkFun-KiCad-Libraries` | CC BY 4.0 (README; commercial use fine; attribution request) | 30 `.kicad_sym`, 24 `.pretty`, 339 3D; folders `symbols/`, `footprints/`, `3dmodels/`; about 68 MB; KiCad 7+ (PCM metadata) | `${SPARKFUN_KICAD_LIBRARY}` (PCM build rewrites to `KICAD9_3RD_PARTY`) | HIGH. Best second entry; also on PCM. Their README confirms that a real clone is needed to edit existing SparkFun projects. |
| **Espressif KiCad Library** | `espressif/kicad-libraries` | CC-BY-SA-4.0 with the standard "designs are not Adapted Material" exception | 1 `.kicad_sym`, 1 `.pretty` (`Espressif.pretty`), 48 3D in `3dmodels/espressif.3dshapes`; targets KiCad 10 on `main`; about 72 MB repo, about 350 MB installed | PCM-first: README recommends PCM; the 3D link behaviour of the source tree was not confirmed | MEDIUM. List as "PCM recommended"; verify 3D paths in a clone test before shipping as one-click. |
| **4ms KiCad Libraries** | `4ms/4ms-kicad-lib` | Unlicense | 25 `.kicad_sym`, 29 `.pretty`, 191 3D, plus 24 legacy `.lib`; about 56 MB; PCM option A in README | Not confirmed | MEDIUM. Candidate; verify. |
| **Alternate KiCad Library** | `dawidcislo/Alternate-KiCad-Library` | CC-BY-SA (PCM metadata); no GitHub SPDX | 39 `.kicad_sym`, 63 `.pretty`, no own 3D models; about 181 MB | Footprints reference KiCad's stock `${KICAD10_3DMODEL_DIR}` | MEDIUM. Works only where stock models resolve; good test for the "uses stock variable" case. |
| CDFER JLCPCB library | `CDFER/JLCPCB-Kicad-Library` | MIT | 296 `.kicad_sym`, 277 3D | Footprint 3D path is `${KICAD8_3RD_PARTY}/3dmodels/com_github_CDFER_JLCPCB-Kicad-Library/...` (sampled in the archived folder) | LOW. Shows PCM-baked paths in a source repo; will not resolve in a clone without remapping. Keep out of the curated list; use as a validation test case. |
| Seeed OPL | `Seeed-Studio/OPL_Kicad_Library` | CC-BY-SA-4.0 | 1 `.kicad_sym`, 15 `.pretty`, 15 legacy `.lib`; irregular folder names with spaces | n/a | LOW. Layout discovery has to cope with it; do not seed. |
| Digi-Key | `digikey/digikey-kicad-library` | CC-BY-SA 4.0 with designs exception | 1,223 `.lib`, **0** `.kicad_sym`; README: "should be considered unmaintained" | n/a | NOT SUITABLE (KiCad 5 format). Use as the "legacy format" validation case. |
| KiCad official libraries | gitlab.com/kicad/libraries | CC-BY-SA 4.0 with exception | Ship with KiCad | `${KICAD10_SYMBOL_DIR}` etc. | NOT a catalog entry; the scanner already cross-references them. |

---

### Area 3: One table model, global vs per-project (v3.0 feature 5)

#### What KiCad users expect [H unless marked]

- Two tables per type: a **global** table in the user config directory (libraries available to all projects) and an **optional project** table (`sym-lib-table` / `fp-lib-table`) in the project folder (KiCad 10 manual).
- Project entries take precedence over a global entry with the same nickname (6.0 docs, via search result) [M]; the 10.0 manual page does not restate it.
- PCM adds libraries to the **global** table by default (preference "Automatically add installed libraries to global library table") [H].
- Community practice is a hybrid: only what is needed everywhere goes global, project-specific libraries go in the project table, and the project table is committed with the project [M, KiCad 5-era forum and mailing-list threads].
- `${KIPRJMOD}` in the *global* table is a known mistake (KiCad bug report) [M]; paths in a project table that use `${KIPRJMOD}` move with the project.
- KiCad 10 has "chained/nested" library tables (a table-typed entry pointing at another table file), but 10.0.1 and 10.0.4 still fixed environment-variable resolution, reloading and read-only handling for nested tables, and the 10.0 manual page does not document them [M]. The Würth repo's own `sym-lib-table` is exactly such a ready-made child table. PROJECT.md already lists nested tables as out of scope; this research supports keeping them out for now.

What the app does today: Generate Tables writes managed `${KICAD_LIB_GITHUB}/...` entries into whatever folder the **Destination** box holds (`main_window._on_generate` -> `write_tables(dest, ...)`), merging external entries and keeping numbered backups. So per-project output already exists in practice but only implicitly, and nothing tells the user which of the two they are editing.

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Make the target explicit: "KiCad global tables (KiCad X.Y)" as the default, or "A project folder..." | Users must know whether they are changing all projects or one; the old free-text Destination does not say | LOW-MEDIUM | Resolve the global table folder from the KiCad config dir already found by `find_kicad_config_dir` (numeric version sort exists, HARD-04); keep history of project folders as now. |
| Same managed-entry format for both targets (`${KICAD_LIB_GITHUB}/...` URIs, the managed marker, descriptions), same merge, same backups | One mental model; entries stay portable between machines because each machine defines its own variable | LOW | Already how it works. |
| The chosen mode is shown at Generate time and in the User Guide | Prevents "I generated but KiCad does not show it" | LOW | |
| Catalog Add/Remove follows the same target | A library added from the catalog must land in the same table Generate would use, and Remove must clean the same one | MEDIUM | Decide the model before the catalog's table step is built. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| "Generate for this project": pick a `.kicad_pro` folder, write a project table with only the libraries the project's schematics/PCB actually use (parse `lib_id` nicknames) | Keeps project tables small and reproducible; solves "global table with 500 libraries" | HIGH | Needs schematic/PCB parsing the app does not have. Defer to a later milestone; the explicit target gets 80% of the value. |
| Compare view: what global has vs what the project overrides | Explains precedence surprises | MEDIUM | Defer. |

#### Anti-Features

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Copy libraries into each project (vendoring) | Self-contained projects | Duplicates 2.7 GB libraries, drifts from upstream, breaks the atomic single-source rule | Reference `${KICAD_LIB_GITHUB}` |
| `${KIPRJMOD}`-relative paths into the collection | Looks portable | Breaks when the project moves; known pitfall | Variable-based absolute URIs |
| Nested/chained tables as the mechanism | One entry instead of N | Still maturing in 10.0.x, not in the 10.0 manual page, older KiCad ignores or mis-handles it (KiCad 6+ is a stated constraint) | Flat managed entries |
| Writing the user's project tables without a preview | Convenience | Violates the preview-before-write constraint, touches version-controlled project files | Same preview and backup as global |

**Recommendation:** global tables as the default and primary model (matches PCM, the owner's workflow, Pin Atomic Libraries, which works on the global config), plus an explicit "project folder" target that uses the same writer. Decide this in the requirements, then let Generate, catalog Add/Remove and the User Guide all follow it.

---

### Area 4: Menu regroup (v3.0 feature 6)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| File / Libraries / KiCad / Help grouping (layout decided 2026-11-13) with every existing action reachable and every existing shortcut unchanged (`Ctrl+I`, `Ctrl+G`, `Ctrl+R`, `Ctrl+K`, `Ctrl+Shift+M`, `Ctrl+Shift+K`, `Ctrl+Shift+A`, `Ctrl+Shift+R`, `Ctrl+Q`, `F1`) | Muscle memory; the User Guide documents these shortcuts | LOW | Mechanical in `main_window._build_ui`. |
| New entries land in the right group: Choose library folder (File), Library catalog (Libraries) | Keeps the regroup stable when Phase 2 and 4 add actions | LOW | Do the regroup after catalog and folder choice exist, as the milestone order already has it. |
| Update the User Guide and CLAUDE.md menu references | Docs go stale first | LOW | |

#### Anti-Features

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Toolbar or ribbon redesign | "While we are here" | Scope creep, test churn | Menus only |

---

### Area 5: Windows installer (v3.0 feature 7) and release basics

#### Table Stakes (what Windows users expect from any installed desktop app)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Start menu shortcut (desktop shortcut optional, off by default) | Users launch from Start | LOW | Per-user installs use the current-user shell context [H, NSIS MultiUser docs]. |
| Registered uninstaller in "Apps & features" (DisplayName, DisplayVersion, Publisher, UninstallString, InstallLocation) | Standard removal path | LOW | NSIS template pattern. |
| Upgrade in place: a newer installer detects the previous install (same app id, install dir from the registry), closes or asks to close a running instance, replaces files, no manual uninstall | Users re-run the latest download | MEDIUM | Version stored in registry; installer compares and may refuse downgrade with a message. Running-app detection via mutex or window class. |
| **User data survives upgrade and uninstall**: settings (`%APPDATA%/KiCadExtLibManager/settings.ini`), scan cache, backups and above all the library collection folder are never touched | Core promise of a data-folder tool; the app already keeps its state outside the install dir by design | LOW | Uninstaller removes only the install dir and its own registry keys; offer (default off) "also remove settings". Never offer to delete the collection. |
| Per-user install without admin rights, default location `%LOCALAPPDATA%\Programs\...`; optional all-users choice | The app writes only to the user's profile and KiCad's user config; a per-user install avoids UAC prompts and keeps the install dir user-writable | MEDIUM | NSIS MultiUser.nsh supports both; a per-user installer must write only to HKCU and the user's profile [H]. |
| **Git check**: look in `HKLM\SOFTWARE\GitForWindows` (`InstallPath`) and `HKCU`, falling back to `git --version` / the default `Program Files\Git\cmd\git.exe`; if missing, explain why Git is needed and offer Open download page / Continue anyway / Cancel | The milestone requirement; the catalog and commit flow need git | LOW-MEDIUM | The NSIS compiler is a 32-bit process, so call `SetRegView 64` before reading HKLM [M, community notes]. No ready-made NSIS Git-for-Windows snippet turned up; write one and test on a machine without Git. |
| **Also check Git at runtime** with a human message when a git feature is used and `git` is not on PATH | The installer check can be bypassed (Git removed later, portable copies) | LOW | A friendly error at the catalog/commit entry point; the existing git runner already finds git. |
| Silent switch `/S` and a version-stamped installer filename | Free in NSIS; helps testers and CI | LOW | |
| Published through GitHub Releases from the public tool repo, with SHA-256 next to the file | "Public app anyone can install" | LOW-MEDIUM | CI build belongs to the repo-split phase or just after. |
| Third-party licence notices (Qt/PySide6 are LGPL; the frozen app redistributes them) shown in the installer or an About box | Legal basics for a public binary | LOW | Choose the freeze layout (onedir) with this in mind; decided in stack research. Also relevant when the tool repo licence is chosen. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| "Check for new version" menu item (opt in; reads the GitHub releases feed) | Users find fixes without watching the repo | LOW-MEDIUM | Network call from the app; keep manual. |
| Code-signed installer | Avoids the SmartScreen "unknown publisher" warning that scares public users | HIGH (cost, certificate process) | Expect the warning in v3.0 and say so in the README; revisit when there are real users. |
| Offer to open the download page for Git and re-check on return | Smoother first install | LOW | |

#### Anti-Features

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Bundle or silently install Git for Windows | "Everything just works" | Large, GPL-licensed, admin prompts, version conflicts with the user's own Git | Detect, explain, link |
| Install into `Program Files` and keep data there | Habit | Read-only for standard users; the app must not write libraries there | Per-user location; data in AppData and the chosen collection |
| Auto-update in the background | Convenience | Silent code replacement from the network, trust and signing burden | Manual notice |
| Installer writes KiCad config or path variables | "Configure KiCad for me" | Breaks the confirm-before-write rule and runs without a preview | The app asks at first run |
| Installer creates the library collection | Fewer steps | Same silent-write problem; location choice belongs in the app's first run | App first-run dialog |

---

### Area 6: Internal items

| Feature | Notes | Complexity |
|---------|-------|------------|
| Test suite speed-up (v3.0 feature 1) | Not user-facing. Catalog tests must never touch the network: clone from local bare repositories (`file://` or a plain path) created by a shared fixture, and mark long clone scenarios with the new `slow` marker. | MEDIUM |
| Python 3.14 minimum (feature 8) | `requires-python = ">=3.14"` in `pyproject.toml`, README, drop the 3.10 import-compat test (`tests/test_annotations_resolve.py` purpose). Installer users never see this because the frozen app embeds its own interpreter. | LOW |
| Repo split (feature 3) | Expected public-repo hygiene: README with install and screenshots, LICENSE chosen in this phase, third-party notices, CONTRIBUTING and issue templates, no library content, audit committed fixtures (`downloaded_examples/` holds a committed Ultra Librarian zip; the SnapEDA and SamacSys samples are already local-only for licence reasons) and what `.planning/` publishes. History rewrite versus fresh start is an open decision for the interactive phase. | MEDIUM (HIGH risk, interactive) |

---

## Feature Dependencies

```
Test speed-up
    └──enables fast iteration for everything below (also needs local bare-repo fixtures for catalog tests)

Library folder chooser (accessor replacing REPO_ROOT)
    ├──requires──> settings.py (QSettings), kicad_common.json reader (library_scanner)
    ├──enables──> New empty collection (skeleton must match importer + atomic scan expectations)
    ├──enables──> Repo split (tool no longer assumes it lives beside the libraries)
    └──enables──> Catalog (clones go into <collection>/<Vendor>/<Repo>)

Repo split
    └──requires──> Chooser done; Würth submodule -> plain clone migration (keeps URI WurthElektronik/KiCad-Library)

Catalog
    ├──requires──> Chooser (target folder), network-capable git runner (separate allow-list from the no-remote runner)
    ├──requires──> Per-source path variables written via existing kicad_common.json confirm flow (HARD-03, running-KiCad check)
    ├──requires──> Table model decision (where Add/Remove write)
    ├──reuses──> scanner source detection (first path segment), managed-marker table merge, HARD-08 collisions, per-library Rescan, per-source Skip, scan cache fingerprint
    └──coexists with──> KiCad PCM (never touch PCM_ entries, 3rdparty, installed_packages.json)

Table model (global default + explicit project target)
    └──requires──> Destination box reworked into explicit target; Generate, Install Part table step, catalog Add/Remove all follow it
    └──constrains──> Pin Atomic Libraries (global config only), D-26 warnings

Menu regroup ──requires──> Chooser and Catalog actions exist (so they get placed once)

Python 3.14 declaration ──precedes──> Installer (freeze tool picks the interpreter)

Installer ──requires──> Python 3.14 declared, app running from any folder (Chooser), Git check at runtime as well as install time
          └──conflicts──> assumptions that the app dir is writable (anything writing next to the code)
```

### Dependency Notes

- **Catalog requires a second git runner.** PROJECT.md Key Decisions record that the commit flow's git runner has an allow-list with no remote subcommand and never pushes (06-SECURITY, 26/26 threats closed). Cloning and fetching need remote subcommands, so build a separate runner (clone/fetch/ls-remote/merge --ff-only, `GIT_TERMINAL_PROMPT=0`, `GIT_*` env stripped, https-only URL check) instead of widening the old one. "Never push" stays true for both.
- **Table model should be decided before the catalog's table step.** Add/Remove must write to and clean the same table that Generate uses; deciding later means reworking the catalog.
- **Chooser before split.** The split removes the assumption that libraries sit next to the code; the chooser is what makes the tool work after that.
- **New-collection layout interacts with the commit step.** The commit flow today commits in `Custom` and then bumps the parent gitlink. A fresh collection has no parent submodule setup, so the requirements must say whether `Custom/` is a plain folder inside a collection repo (commit step needs a "single repo" mode) or its own repo.
- **Catalog libraries and the owner's private collection.** Plain clones must be git-ignored in the collection so third-party and proprietary content is never republished; the manifest records them.

---

## MVP Definition

### Launch With (v3.0)

- [ ] Library folder resolution (saved choice, `KICAD_LIB_GITHUB`, prompt) with visible current folder and `File > Choose library folder...` — makes the app usable anywhere
- [ ] First-run dialog and new empty collection (skeleton, `git init`, offer to set KiCad variables with the existing confirm) — a new user can import a first part
- [ ] Catalog window: curated list (Würth, SparkFun, plus any entry that passes the clone-scan-load test), Add, Update with indicator, Remove, progress and cancel
- [ ] Add by URL for `https://github.com/...` with validation messages (no libraries, legacy `.lib`, PCM-first source, authentication needed) and licence display
- [ ] Per-entry path variables through the existing confirm flow; manifest of installed catalog libraries; Würth as an entry at its current path
- [ ] Explicit table target (KiCad global default, or project folder) with Generate and catalog following it
- [ ] Menu regroup File / Libraries / KiCad / Help
- [ ] Per-user NSIS installer: Start menu, uninstaller, upgrade in place, user data untouched, Git check at install and at runtime
- [ ] Python 3.14 declared; test suite fast enough to iterate

### Add After Validation (v3.x)

- [ ] Remote-updatable curated list — once the bundled list goes stale between releases
- [ ] Pin per tag or commit — when users ask for reproducibility
- [ ] "Check for new version" — once there are public releases
- [ ] Recent-collections switcher — when several collections are in use
- [ ] Atomic-rule score shown for a library before adding it

### Future Consideration (v4+)

- [ ] "Generate for this project" from schematic/PCB `lib_id` usage — needs KiCad project parsing
- [ ] Read a PCM `repository.json` as a listing source ("browse PCM libraries")
- [ ] Code signing
- [ ] GitLab/Codeberg hosts beyond GitHub
- [ ] Public community atomic library (explicitly later, after a licence check)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Library folder resolution + chooser | HIGH | MEDIUM | P1 |
| First-run + new empty collection | HIGH | MEDIUM | P1 |
| Catalog Add (shallow clone, progress, errors) | HIGH | HIGH | P1 |
| Catalog Update + indicator, Remove | HIGH | MEDIUM | P1 |
| Per-entry path variables | HIGH | MEDIUM | P1 |
| Add by URL with validation | HIGH | MEDIUM | P1 |
| Licence display and acknowledgement | MEDIUM | LOW | P1 |
| Explicit table target (global default / project) | HIGH | LOW-MEDIUM | P1 |
| Menu regroup | MEDIUM | LOW | P1 |
| Installer with Git check, per-user, upgrade in place | HIGH | MEDIUM | P1 |
| Manifest for catalog libraries | MEDIUM | MEDIUM | P1 (shapes the plain-clone decision) |
| PCM coexistence guards | MEDIUM | LOW | P1 |
| "Also on PCM" hint | LOW | LOW | P2 |
| Recent collections | LOW | LOW | P2 |
| No-KiCad graceful mode | MEDIUM | MEDIUM | P2 |
| Update-check menu | LOW | MEDIUM | P3 |
| Pin to tag | MEDIUM | MEDIUM | P3 |
| Per-project generate from usage | MEDIUM | HIGH | P3 |
| Code signing | MEDIUM | HIGH | P3 |
| PCM client/installer | LOW | HIGH | Do not build |

**Priority key:** P1 must have for v3.0; P2 add when possible; P3 later.

---

## Competitor / Peer Feature Analysis

| Feature | KiCad PCM | KiLM (CLI) | Fusion/Eagle Library Manager | Our Approach |
|---------|-----------|------------|------------------------------|--------------|
| Browse and search | Yes, official repo (17 library packages) plus custom repos | No | Yes, public + hub libraries | Curated list + Add by URL |
| Install mechanism | Zip, sha256-verified, into `3rdparty` | Clone/config via CLI | Cloud activation | Shallow git clone into the collection |
| Table entries | Auto, global only, `PCM_` prefix | Adds to KiCad config | n/a | Managed entries, global default or project target |
| Path variables | Rewrites to `${KICAD<n>_3RD_PARTY}/...` at packaging | Sets env vars in config | n/a | Per-entry variables via confirm flow |
| Update | Version list, notifies | `kilm update` | Update / Update All | Fetch + fast-forward, indicator via `ls-remote` |
| Remove | Uninstall | Manual | Remove from view | Delete clone + managed entries, with confirm |
| Edit upstream library | No (packages are managed) | n/a | Fork a copy | Read-only clone; import into `Custom/` |
| Safety | Packages can run code (Python plugins) [H, KiCad manual] | Backups, dry-run | Cloud | Preview + backup, never run repo code, https-only, no pushes |
| Part import with quality rule | No | Yes (UL/SamacSys/SnapMagic ZIPs) | n/a | Existing importer + atomic rule |

---

## Sources

- KiCad 10.0 Reference Manual, Plugin and Content Manager and Libraries sections: https://docs.kicad.org/10.0/en/kicad/kicad.html — `KICAD10_3RD_PARTY`, `PCM_` prefix, "Automatically add installed libraries to global library table", global vs project tables, first-run library setup, custom repository Manage > "+" [HIGH, fetched 2026-11-22]
- KiCad 9.0 Reference Manual: https://docs.kicad.org/9.0/en/kicad/kicad.html [HIGH]
- KiCad developer docs, Addons / PCM package and repository format: https://dev-docs.kicad.org/en/addons/ — metadata.json fields, library package layout, v1/v2 repository files, `kicad_version`/`kicad_version_max`, `keep_on_update` [HIGH]
- Official PCM repository, fetched directly: https://repository.kicad.org/repository.json and its `packages.json` (150 packages: 115 plugin, 18 colortheme, 17 library; no Würth, Digi-Key or Espressif) [HIGH, 2026-11-22]
- KiCad blog, Third-party content improvements (PCM in 6.0): https://kicad.org/blog/2021/12/Development-Highlight-Third-Party-Content-Improvements [MEDIUM, dated]
- KiCad third-party libraries page (not maintained or endorsed by KiCad): https://kicad.org/libraries/third_party [HIGH]
- KiCad library licence: https://kicad.org/libraries/license/ [MEDIUM]
- KiCad forum, personal library via PCM: https://forum.kicad.info/t/how-to-make-a-personal-user-library-install-under-pcm/55589 [MEDIUM]
- Adom PCM repository example: https://wiki.adom.inc/adom/kicad-pcm ; Windows Documents-folder/OneDrive trap reported there [LOW-MEDIUM, single source]
- Nested library tables in KiCad 10 (release notes 10.0.1, 10.0.4, nested-table forum thread): https://www.kicad.org/blog/2026/04/KiCad-10.0.1-Release/ , https://kicad.org/blog/2026/06/KiCad-10.0.4-Release/ , https://forum.kicad.info/t/assistance-request-creating-a-library-table-for-nested-libraries/71892 [MEDIUM]
- KiCad 6 library-table precedence and portability: https://docs.kicad.org/6.0/es/pcbnew/pcbnew_footprints_and_libraries.html ; KIPRJMOD in global table bug: https://bugs.launchpad.net/bugs/1830694 ; community practice: https://forum.kicad.info/t/project-and-libary-setup-for-sharing-and-collaboration-kicad-version-5/20842 , https://hackaday.com/2017/05/18/kicad-best-practises-library-management [MEDIUM, KiCad 5/6 era]
- GitHub API and repository files, queried 2026-11-22: `WurthElektronik/KiCad-Library` (README, `sym-lib-table`, `License_Terms_WE_KiCad_library.pdf`), `sparkfun/SparkFun-KiCad-Libraries` (README: licence, `SPARKFUN_KICAD_LIBRARY`, PCM, clone guidance), `espressif/kicad-libraries` (README, `metadata.json`, `repository.json`, LICENSE.md, `package.py`), `digikey/digikey-kicad-library` (README, LICENSE.md), `Seeed-Studio/OPL_Kicad_Library`, `4ms/4ms-kicad-lib`, `dawidcislo/Alternate-KiCad-Library`, `CDFER/JLCPCB-Kicad-Library`; also SparkFun PCM announcement https://news.sparkfun.com/15123 (403 to fetch; content known from the README) [HIGH for counts, licences and variables, sampled files only]
- KiLM: https://github.com/barisgit/KiLM (README, release v0.6.1 2026-10-23, MIT) [HIGH]
- Autodesk Fusion Electronics Library Manager and managed libraries: https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-LIB-MGR-CPT.htm , https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-USE-MG-LIB.htm , https://www.autodesk.com/products/fusion-360/blog/new-managed-online-libraries-use/ [MEDIUM-HIGH]
- NSIS MultiUser (per-user vs per-machine, shell context): https://nsis.sourceforge.io/Docs/MultiUser/Readme.html ; Git for Windows registry location (community page, verify on a real machine): https://samibs.github.io/Registry-Keys-for-Open-Source-Applications-on-Windows/git/ ; 32-bit NSIS registry view caveat from a community result [MEDIUM]
- Onboarding patterns for data-folder desktop tools (Obsidian, Calibre, Zotero) and Windows installer conventions (ARP entries, per-user install, upgrade in place): general practice, not fetched in this session [LOW]
- Project context: `.planning/PROJECT.md`, `kicad_lib_manager/main_window.py` (`_on_generate` writes into the Destination folder)
- Not used: the GSD research-plan/research-store cache seam (no provider-ordering needed for this run); facts were gathered with web fetches and the GitHub CLI directly.

---
*Feature research for: Public KiCad library manager (v3.0)*
*Researched: 2026-11-22*
