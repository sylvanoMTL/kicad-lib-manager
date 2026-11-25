# Project Research Summary

**Project:** KiCad Part Importer / KiCad Library Manager (milestone v3.0 Public Library Manager)
**Domain:** Public, installable Windows desktop app (PySide6, stdlib + PySide6 only) that manages an external KiCad library collection
**Researched:** 2026-11-22
**Confidence:** MEDIUM-HIGH (code facts HIGH; catalog and installer behaviour MEDIUM; several items LOW or unverified, listed under Gaps)

Phases follow the owner's fixed order: P1 test speed-up, P2 choose library folder (incl. new empty collection), P3 repo split (interactive), P4 library catalog, P5 table model, P6 menu regroup, P7 Python 3.14 minimum, P8 NSIS installer with freeze tool.

## Executive Summary

v3.0 turns a personal tool that lives inside its own library repo into an app anyone can install, working on a collection kept outside the app's code. The code is closer to ready than assumed: `REPO_ROOT` is one module constant (17 use sites in `main_window.py`), services already take `repo_root: Path`, and the scan cache is keyed per folder. The real coupling is the literal `Custom` (about 25 sites) and `WurthElektronik` (two). Recommended: one Qt-free `collection.py` owning those names, `Custom/` kept as the own-library folder in every collection, and third-party libraries cloned into the collection and recorded in a manifest.

The catalog should use plain shallow `git clone`s plus a committed `catalog.json` manifest (URL, ref, pinned commit, path variables), not submodules, run through a second network-capable git module with its own allow-list; `gitops.py` keeps its no-remote invariant. Tables stay on one global model with `${KICAD_LIB_GITHUB}/...` URIs. Freezing: PyInstaller 6.22.3 onedir (measured to build and start), inside a per-user NSIS installer with an advisory Git check reading HKCU and HKLM. Test speed-up: pytest-xdist, pytest-timeout, a `slow` marker, and a once-per-run git template under a FileLock. No new runtime dependency.

Main risks are procedural. (1) Both GitHub repos are already PUBLIC (verified `gh repo view`, 2026-11-22), though CLAUDE.md and PROJECT.md call `Custom/` private. (2) The repo split is the riskiest step and the research disagrees on its direction (D1). (3) The frozen app would silently lose the saved scan (signature hashes `.py` files) and could scan or write into its install folder if a `REPO_ROOT` site is missed. (4) After the split the public suite can go green by skipping format tests. (5) Moving Wurth can orphan about 89 generated URIs and the `WE_3DMODEL_DIR` 3D models, the 2026-10-21 failure mode.

## Key Findings

### Recommended Stack

New only; existing Python 3.14.4, PySide6 6.12.0, S-expression layer and subprocess git stay.

- pytest-xdist 3.8.0 (`-n 6..8`, not auto; measured git contention); pytest-timeout 2.4.0 pinned (2.5.0 yanked 2026-08-16).
- PyInstaller 6.22.3 onedir from a committed spec: 66 s build, 123 MB, 38 MB compressed, started offscreen. No onefile, no UPX. Nuitka 4.3.5 measured (84 MB, 5 min cold) as fallback.
- NSIS 3.13 (3.12 local): per-user, `RequestExecutionLevel user`, `SetRegView 64`, advisory Git check, no bundled Git.
- hatchling `pyproject.toml`: `requires-python >=3.14`, `[project.gui-scripts]`, PEP 735 groups, PEP 639 licence. Flat layout kept.
- PySide6-Essentials 6.12.0 in the frozen build (not yet tested against the full suite).
- Catalog git: subprocess, `git -c core.longpaths=true -c core.autocrlf=false -c protocol.ext.allow=never clone --depth 1 --single-branch -- <https-url> <dest>`.
- Optional GitHub metadata via stdlib urllib (60 req/h unauthenticated; cached; curated list shipped in app).
- Dev-only: pytest-xdist, pytest-timeout, filelock. git-filter-repo 2.47.0 as one-off tool.

### Expected Features

- P2 table stakes: resolve folder in fixed order; visible current folder; File > Choose library folder...; first-run with three paths (KiCad's folder, existing, create new empty collection); validate folder (writable, not Program Files, not drive root); new collection skeleton (`Custom/` with `Atomic_Footprints.pretty`, `3DModels`, `.gitkeep`, git init, .gitignore, README); offer KiCad variables through existing confirm.
- P4 table stakes: list with status (Not installed / Installed / Update available / Problem), search; one-click shallow Add with progress, Cancel; Update by fetch and fast-forward with indicator; Remove (clone plus managed entries, confirm naming both); Add flows into existing preview and confirm; per-entry path variables; small verified curated list; Add by URL with messages (no .kicad_sym or .pretty; KiCad 5 .lib only; PCM-first source; private repo not supported); licence shown before cloning; PCM coexistence (never touch PCM_*, 3rdparty, installed_packages.json); WurthElektronik becomes a catalog entry.
- P5: explicit target, global default; mode shown at Generate and in User Guide.
- P6: File / Libraries / KiCad / Help; all shortcuts unchanged (Ctrl+I, G, R, K, Shift+M, Shift+K, Shift+A, Shift+R, Q; F1).
- P8: Start menu shortcut; uninstaller; upgrade in place; user data never removed; per-user; Git check; silent /S; SHA-256; LGPL notices.
- Differentiators (later): recent collections, Explorer open, no-KiCad mode, PCM hint, atomic score on Add, size check, pin to tag, update check.
- Defer: remote curated list, project-from-usage generation, PCM repository reader, code signing (unsigned first; SmartScreen warning documented), GitLab hosts, public community atomic library.
- Anti-features: PCM client; installing into KICAD<n>_3RD_PARTY; submodules for catalog; arbitrary git URLs; auto-update; bundling Git; writing under Program Files; editing third-party clones; silent folder creation; several active collections; per-library URI variables; auto-rename of nicknames.
- Seed set (verified 2026-11-22): Würth (proprietary licence, shallow clone, about 2.7 GB on GitHub, `${WE_3DMODEL_DIR}`); SparkFun (CC BY 4.0, `${SPARKFUN_KICAD_LIBRARY}`); Espressif and 4ms (candidates, 3D paths unconfirmed); Alternate KiCad Library (stock model variable, test case). Excluded: Digi-Key (legacy .lib only, unmaintained), Seeed OPL (irregular), CDFER (PCM-baked paths).

### Architecture Approach

Collection layout: root holds `Custom/` (own repo), `ThirdParty/<id>/` (git-ignored clones, location open in D2), `catalog.json`, `.gitignore`. Owner's collection keeps parent with `Custom` submodule; new user's has none.

Components:

1. `collection.py` (NEW, Qt-free): constants `OWN_DIR`, `THIRD_PARTY_DIR`, `MANIFEST_NAME`; `resolve_library_root()`, `inspect_collection()`, `create_collection()`; `source_of(rel_path)` gives the same source `WurthElektronik` for legacy and new Wurth paths.
2. `catalog/manifest.py`, `catalog/curated.py`, `catalog/ops.py` (NEW): validate-on-read manifest; curated list as Python module; plan/preview/apply for add, update, remove; staging in `ThirdParty/.staging/`, validated before rename.
3. `catalog/gitnet.py` (NEW): only network git; allow-list `{clone, fetch, ls-remote, reset, rev-parse, status}`; https GitHub only; shares launcher via extracted `gitops.launch()`.
4. `widgets/catalog_dialog.py`, `widgets/library_root_dialog.py` (NEW), non-modal from constructor.
5. `main_window.py` (MODIFIED): `REPO_ROOT` becomes `self._root`; `_set_root()` refused while busy; menu regroup.
6. `library_scanner.py`, `scan_cache.py` (MODIFIED): prune `.git` at any depth (rglob currently descends every `.git/objects`); `scan_source()`; frozen-aware signature; `sync_kicad_path_vars(extra_vars=...)`.
7. Commit step (MODIFIED): `parent_mode` `none | gitlink`; with `none` the parent option is hidden.

Patterns: plan, preview, apply; single source for folder names (layering test forbids literal "Custom" outside collection.py); validate before register; marker-based table ownership.

Path variables: manifest `vars` maps KiCad variables that footprints hard-code (e.g. `WE_3DMODEL_DIR`) to clone-relative folders, detected at Add by scanning `(model ...)` paths; written via existing `VAR: old -> new` confirm. Absolute or `${KIPRJMOD}` models reported, never rewritten.

### Critical Pitfalls (top 13 of 32)

1. Both repos public; decide private or accept (D14). Read first.
2. xdist session fixtures run per worker: build git template once under FileLock in `tmp_path_factory.getbasetemp().parent`; finaliser cleanup. (P1)
3. Shared real state under workers: autouse fixture redirecting QSettings, APPDATA, LOCALAPPDATA, HOME; clear KICAD_LIB_GITHUB; guard the resolved folder. (P1, P2)
4. Saved scan dies in frozen build: `_code_signature()` returns "" without `.py`; use VERSION + build stamp when frozen; test it. (P8)
5. `REPO_ROOT` in frozen app points into install folder: replace all 17 sites by `self._root`; move five test harness seams to the constructor. (P2)
6. Splitting the checkout KiCad reads (2026-10-21 incident): rehearse on `git clone --no-local` copies; `git bundle` and `pre-split` tag; keep layouts; compare resolved URI list before and after. (P3)
7. Private content in public history: `.planning/` paths, `CLAUDE.md` paths, tracked `ul_CSD85301Q2.zip`, owner email and Co-Authored-By/Claude-Session trailers in commits (replace-text does not reach messages or tags). Allow-list filter or fresh squashed history, then pre-publish scan. (P3)
8. Public suite greens by skipping: about 25 test modules read Custom, WurthElektronik, downloaded_examples or .planning. Classify each; KICAD_TEST_CORPUS opt-in; skip budget. (P3, P8)
9. Wurth move breaks 3D models: 7,612 `${WE_3DMODEL_DIR}` paths set by hand. Previewed transaction: clone, verify set, define variable, Generate, rescan zero missing, then remove submodule (`deinit -f`, `git rm`, delete `.git/modules/...`). (P4)
10. Catalog clones: `-c core.hooksPath=<empty>`, `init.templateDir=`, `core.fsmonitor=false`, `credential.helper=`, `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, no recursion, https only, `--` before URL, git 2.49.1+ (D6); Cancel kills tree and deletes staging. (P4)
11. Per-project tables shadow global by nickname: global only automatic; project export explicit, merging, reports shadowing. (P5)
12. Nickname collisions: check stock nicknames, installed catalog, Atomic_/Custom at Add; never auto-rename. (P4)
13. Freeze and installer traps: clean venv with PySide6-Essentials; exclude QtQml, QtQuick, QtPdf, QtVirtualKeyboard (re-test); CREATE_NO_WINDOW in one `run_process()`; Git via which, HKCU and HKLM InstallPath, Program Files; Git check advisory; upgrade needs app stopped; uninstaller never touches collections or settings without default-No question. (P2, P8)

Also in PITFALLS: pitfalls 14-32 cover folder precedence, path length and CRLF (`core.autocrlf` true rewrites `.kicad_sym`), shallow update semantics, LFS, licences, KiCad running checks, menu shortcut enumeration test, Python 3.14 annotation guard (ruff F821), Defender and SmartScreen.

## Implications for Roadmap

### Phase 1: Test suite speed-up

**Rationale:** Every later phase runs the suite; GSD gate default 600 s cannot cover about 29 min. Nothing depends on it except iteration speed.
**Delivers:** pytest-xdist (worker count per D9), pytest-timeout 2.4.0, `slow` marker in pyproject (strict markers stay on), `--durations` baseline (three runs, discard first), FileLock git template, autouse isolation fixture, per-worker guard message, `xdist_group` for kicad_cli and Wurth, short `--basetemp`; GSD-gate command under about 8-10 min.
**Avoids:** Pitfalls 1-7.
**Research flag:** standard; measure, do not research.

### Phase 2: Choose library folder (and new empty collection)

**Rationale:** The tool must run outside its repo before the code leaves it (P3); root of catalog and table work.
**Delivers:** `collection.py`; QSettings key; `library_root_dialog` (first run, choose, new collection, path-length warning over about 100 chars); `MainWindow(library_root)` replacing REPO_ROOT and five harnesses; `--library-root` / `KICAD_LIBMGR_ROOT` override for dev and UAT; `.git` pruning in scanner and scan-cache walkers; literal "Custom" to constants; `RepoLayout` fields; parent-mode `none`; `run_process()` helper; freeze spike (D8).
**Avoids:** Pitfalls 12, 13 (`.gitkeep`, `git init -b main`, refuse non-empty and drive root), 14 (precedence, deleted-folder rule, non-modal), 25, 29.
**Research flag:** decide D3 and D4 before planning; freeze spike here.

### Phase 3: Repo split (interactive, not autonomous)

**Rationale:** App must already run outside the repo (P2); Wurth leaves the collection only after the tool repo no longer carries it (P4e).
**Delivers:** public tool repo (code, tests, pyproject, LICENSE, README with install and first run, Windows CI `pytest -n auto -m "not slow"`); private collection (Custom plus third-party, no code); legacy fallback removed; conftest guard repointed; `KICAD_TEST_CORPUS` opt-in; CLAUDE.md split; synthetic replacement for `ul_CSD85301Q2.zip` if not redistributable; pre-publish scan exit criterion; scratch-clone rehearsal; fresh-clone suite run within skip budget.
**Avoids:** Pitfalls 8, 9, 10, 11, 12 (design), 22.
**Research flag:** interactive session first (D1, D10, D12, D13, D14).

### Phase 4: Library catalog (WurthElektronik catalog-managed)

**Rationale:** Needs chooser (P2), table decision (P5 decided before this table step), and the split (P3).
**Delivers in order:** (a) `gitnet.py` plus `gitops.launch()` extraction, layering test that commit-path modules cannot import gitnet, threat-model note; (b) manifest, curated, `scan_source`, `sync_kicad_path_vars(extra_vars)`; (c) ops add, update, remove, tested against local bare repos through `file://` (no network in tests); (d) catalog dialog with progress, Cancel, licence display; (e) Wurth conversion from main checkout with rollback tag.
**Avoids:** Pitfalls 6, 15, 16, 17, 18, 19, 20, 21, 22.
**Research flag:** decide D2, D6, D7, D11 at plan time; research LFS detection and 304 cost.

### Phase 5: Table model

**Rationale:** Add, Remove and Generate must write the same table.
**Delivers:** Destination default = newest KiCad config folder (`find_kicad_config_dir()`), repo or collection root only without KiCad config; "KiCad tables folder" label; `table_generator.remove_library_entries(dest, rel_prefix)`; mode shown at Generate; Help text; optional explicit project export if D5 keeps it.
**Avoids:** Pitfalls 23, 24.
**Research flag:** decide D5 first.

### Phase 6: Menu regroup

**Delivers:** File / Libraries / KiCad / Help by moving existing QAction objects; every shortcut unchanged; Help section keys stable (saved last section keyed by name); test enumerating actions against the CLAUDE.md shortcut table; docs updated in same plan.
**Avoids:** Pitfall 32. Standard.

### Phase 7: Python 3.14 minimum

**Delivers:** `requires-python >=3.14`; README and CLAUDE.md agree (one test); `env-py311` deleted and noted; guard in `app.main()`; undefined-name check kept (ruff F821, or rewrite `test_annotations_resolve.py` with annotationlib) after dropping the 3.10 grammar check.
**Avoids:** Pitfall 31. Standard.

### Phase 8: NSIS installer and frozen build

**Delivers:** `_version.py` single source; `main()` in `kicad_lib_manager/app.py`, root script a three-line shim; frozen-aware `_code_signature()`; `kicad_lib_manager.spec` (PyInstaller onedir, PySide6-Essentials, no UPX, datas for licences); `--selftest` and frozen smoke test (offscreen start, scan tiny collection, exit 0); NSIS script (per-user, `$LOCALAPPDATA\Programs`, advisory Git check, uninstaller removes program folder only, asks default No before settings); `release.yml` on `v*` tags (choco NSIS 3.13.0, makensis, SHA-256, gh release); THIRD-PARTY-NOTICES and LGPL text in About; clean Windows VM verification.
**Avoids:** Pitfalls 25-30.
**Research flag:** spike before planning: PyInstaller vs Nuitka on 3.14.4 and PySide6 6.12 (size, start time, Defender, clean VM); code-signing route (SignPath needs a prior release and OSI licence).

### Phase Ordering Rationale

- P1 first: verification speed for everything after; installs the isolation fixture P2 relies on.
- P2 before P3: split removes the assumption that libraries sit beside code.
- P3 before P4: Wurth cannot leave while the tool repo carries it; catalog tests need the new layout.
- Table decision before catalog Add/Remove: avoids rework.
- P6 after P4 and P5: each action placed once.
- P7 before P8: tool and declared minimum must agree.
- Freeze spike in P2, not P8: outcome constrains P7 and P8.

### Research Flags

- Needs decision or research before planning: P2 (D3, D4, freeze spike), P3 (D1, D10, D12, D13, D14, interactive), P4 (D2, D6, D7, D11, LFS, 304 cost), P5 (D5), P8 (3.14 spike, signing).
- Standard: P1 (measure), P6, P7.

## Decisions for the owner

**Verified fact (2026-11-22):** `sylvanoMTL/kicad_libraries` and `sylvanoMTL/kicad_custom_library` are both **PUBLIC** (0 forks, 0 stars). CLAUDE.md and PROJECT.md describe `Custom/` as private. Decide: make both private, or accept public and treat the split as stopping future exposure only.

- **D1 Repo split direction (disagreement).** STACK: keep this repo and history as public tool repo; collection is fresh `git init`. ARCHITECTURE: keep the private repo as collection (final "remove app code" commit); public tool repo from a filtered copy. PITFALLS: fresh squashed history for the public repo. Trade-off: history keeps 1,584 commits with trailers and paths to scrub.
- **D2 Clone location and Wurth path (disagreement).** ARCHITECTURE: `ThirdParty/<id>/`, Wurth moved, one-time rewrite of about 89 `WurthElektronik/...` URIs. FEATURES: `<Vendor>/<Repo>`, Wurth kept in place (no URI change). STACK: no fixed path. `source_of` handles both.
- **D3 Chosen folder vs KICAD_LIB_GITHUB (disagreement).** Milestone: KICAD_LIB_GITHUB first, else remembered. ARCHITECTURE: CLI/env override > remembered > KICAD_LIB_GITHUB > prompt, with a "Use KiCad's folder" reset; otherwise the menu action is a no-op whenever KiCad sets the variable.
- **D4 New-collection git shape (disagreement).** FEATURES: root is the repo, `Custom/` plain (needs a single-repo commit mode). ARCHITECTURE: `git init` inside `Custom/` (no commit-mode change). PITFALLS: owner keeps submodule; new collections single-repo via one `RepoLayout` method.
- **D5 Table model (disagreement).** FEATURES: explicit global or project target. ARCHITECTURE and PITFALLS: global only automatic; project export later. Recommendation: global default.
- **D6 Minimum git (disagreement).** Code: 2.25. PITFALLS: 2.49.1+ for CVE-2025-48384 (this machine has 2.49.0). Recommendation: 2.49.1 with a warning below.
- **D7 Catalog update (disagreement).** STACK: `fetch --depth 1` + `merge --ff-only`. ARCHITECTURE and PITFALLS: `fetch --depth 1 origin <ref>` + `reset --hard FETCH_HEAD` on a clean tree (shallow ff can fail). Recommendation: reset form.
- **D8 Freeze tool timing (disagreement).** STACK: PyInstaller now (measured). ARCHITECTURE and PITFALLS: spike first. Recommendation: PyInstaller, confirmed in P2 spike; Nuitka only if clean-VM Defender flags it.
- **D9 Test workers (disagreement).** STACK: `-n 6..8`, `--dist worksteal`. PITFALLS: `-n 4`, `--dist loadfile` first. Recommendation: measure both in P1; take the faster that passes ten green runs.
- **D10 Licences.** Tool repo licence chosen in P3 (STACK placeholder MIT). Treatment of third-party share-alike content.
- **D11 Curated list and licence gate.** Refuse no-licence libraries, or allow with warning and acknowledgement? Lean: warning plus acknowledgement.
- **D12 Tracked vendor sample.** Is `downloaded_examples/ul_CSD85301Q2.zip` redistributable? If not, synthetic builder first.
- **D13 `.planning/` publication.** As is, or scrubbed?
- **D14 Public or private repos.** See verified fact.
- **D15 Signing.** Ship unsigned first; SignPath after one release (STACK, FEATURES).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Versions checked 2026-11-22; PyInstaller, Nuitka and xdist measured locally. Not measured: frozen GUI flows, Essentials-only suite, filter-repo with gitlinks. |
| Features | MEDIUM-HIGH | PCM and seed facts checked (sampled). Onboarding and installer conventions LOW (general practice). |
| Architecture | MEDIUM (design), HIGH (code facts) | Grepped and read from code; design choices reasoned, not prototyped. |
| Pitfalls | MEDIUM-HIGH | Code, git, gh facts HIGH; antivirus, GCM, some filter-repo behaviour MEDIUM or LOW. |

**Overall:** MEDIUM-HIGH. Roadmap order is firm; open decisions change content of P2, P3, P4, P5, not order.

### Gaps to Address

- Public repo status (D14): decide before P3 scope is fixed.
- Repo split direction and history (D1): biggest risk; resolve in interactive P3; rehearse on fresh clone.
- GCM vs `GIT_TERMINAL_PROMPT=0` (UNVERIFIED): test with a private URL before P4 ships; also set `GCM_INTERACTIVE=Never`.
- Essentials-only PySide6 (UNVERIFIED): run full suite on Essentials-only venv (P1 or P8).
- `git filter-repo` with gitlinks (UNVERIFIED): rehearse on throwaway clone; diff `git ls-tree -r HEAD`.
- Espressif, 4ms, Alternate 3D paths (NOT CONFIRMED): verify in a clone test before one-click listing.
- Git LFS pointers (LOW-MEDIUM): detect `version https://git-lfs` during staging.
- GitHub 304 cost (UNVERIFIED): cache by ETag; degrade to "unknown" offline.
- Nuitka with PySide6 on 3.14 (LOW): needed only if PyInstaller fails the spike.
- Antivirus and SmartScreen (LOW, anecdotal): clean-VM Defender and VirusTotal in release checklist.
- KiCad project-table precedence and `.lck` files (MEDIUM): verify on KiCad 10 only if D5 keeps a project mode.
- Frozen saved-scan behaviour (UNVERIFIED): P8 test must assert non-empty signature.
- Installer running-app check (UNVERIFIED): mutex or FindWindow; test with app open.

## Sources

- Codebase on `feature/part-importer`: `main_window.py`, `library_scanner.py`, `scan_cache.py`, `table_generator.py`, `gitops.py`, `importer/commit_step.py`, `importer/layout.py`, `importer/verify.py`, `tests/conftest.py`, `tests/gitfixtures.py`, `tests/test_layering.py`, `.gitignore`, `.gitmodules` (HIGH).
- `gh repo view` for both repos, 2026-11-22 (HIGH).
- PyPI JSON: pytest-xdist 3.8.0, pytest-timeout 2.4.0 (2.5.0 yanked), pytest-qt 4.5.0, PyInstaller 6.22.3, git-filter-repo 2.47.0 (HIGH).
- PyInstaller changelog and licence page; GitHub REST rate limits; GitHub runner image readme; GitHub blog on CVE-2025-48384 (HIGH).
- KiCad 10 reference manual (PCM, global vs project tables); official PCM `repository.json`, fetched 2026-11-22 (HIGH).
- pytest-xdist how-to; Python Packaging User Guide (HIGH).
- Local measurements (scratch, not committed): xdist smoke 266 passed at `-n 8`; serial `test_commit_step.py` 123 passed in 295 s; PyInstaller 66 s, 123 MB; Nuitka 5 min 11 s, 84 MB; Defender scan clean on one machine.
- Secondary (MEDIUM): KiCad third-party and licence pages; SPDX KiCad-libraries-exception; Nuitka 4.2 release post; Qt deployment guides; git-for-Windows registry reference; GitHub API repository files for seed list; KiCad PCM dev docs; Autodesk library manager help; KiLM (MIT, v0.6.1).
- Tertiary (LOW): antivirus anecdotes; Jira BAM-18205 credential hang; Obsidian, Calibre, Zotero onboarding (general practice); Adom PCM wiki note.

---
*Research completed: 2026-11-22*
*Ready for roadmap: yes, after the owner resolves D1, D3, D4 and D14*
