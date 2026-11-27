# Phase 17: Library Catalog - Context

**Gathered:** 2026-11-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The user can add, update and remove third-party KiCad libraries from GitHub inside the app, from a curated list or by URL (CAT-01..CAT-12). Libraries are plain shallow clones recorded in a manifest in the collection, never submodules. A background check at startup flags updates. Path variables a library needs are set through the existing old -> new confirmation. Network git runs only in a separate, hardened runner. In the owner's collection, the WurthElektronik submodule becomes a catalog entry with no missing library or 3D model afterwards.

Out of this phase: project-local tables (Phase 18; catalog Add and Remove change only the collection and its manifest, tables are written by Generate Tables), the menu regroup (Phase 19), a remote-updatable curated list, GitLab or other hosts, a PCM client.

</domain>

<decisions>
## Implementation Decisions

### Where clones live and the manifest (D2)
- **D-01:** Catalog libraries are cloned into **`ThirdParty/<id>/`** under the collection root (curated entries use their curated id, for example `ThirdParty/WurthElektronik/`, `ThirdParty/SparkFun/`). `source_of()` already maps `ThirdParty/<id>/...` to source `<id>`. Würth moves once from `WurthElektronik/KiCad-Library` (see D-24..D-28). — **Reversibility:** costly — moving the folder again means rewriting every managed table URI and repointing the path variables of every installed library
- **D-02:** The manifest is **`catalog.json` at the collection root**, beside `ThirdParty/`. It records per library: id, URL, branch, installed commit, path variables (name and clone-relative target), and the licence acknowledgement (D-10). Validated on read; a bad or unreadable manifest is a reported problem, never a crash.
- **D-03:** **The app writes `catalog.json` and never commits it.** In the owner's collection (root is a git repo) it shows up as a changed file the owner commits by hand. In a new collection (root is a plain folder) it is just a file. No new commit path is added in this phase.
- **D-04:** **Add by URL, licence and size before cloning:** one unauthenticated GitHub API call (`api.github.com/repos/<owner>/<repo>`) for size, default branch and SPDX licence. When it reports `NOASSERTION` or none, the `LICENSE*` file found in the staging clone is shown before the library is registered. Offline or rate-limited: size and licence are shown as unknown and the staging check still runs. Curated entries carry licence and size in the app's own list, with no API call needed.
- **D-05:** **A manifest entry whose folder is missing** (another machine, or deleted by hand) shows **"Problem: folder missing"** with a **Reinstall** button that clones the recorded URL and branch again. Remove still works. This is how a collection is recreated on another machine.
- **D-06:** **A `ThirdParty/` folder that `catalog.json` doesn't list** shows **"Problem: not in the catalog"**, is still scanned like any source, and its only action is Remove (with confirmation). The app never deletes it on its own. Leftovers in `ThirdParty/.staging/` are the exception and are cleaned up silently.

### Update, licence and git (D6, D7, D11)
- **D-07:** **Update = `fetch --depth 1 origin <branch>` + `reset --hard FETCH_HEAD`, only on a clean tree.** `status --porcelain` must be empty first. Otherwise Update refuses, lists the changed files and says local changes belong in `Custom/`. Catalog clones are managed read-only copies.
- **D-08:** **Update preview:** fetch first (the working tree doesn't change yet), then show old -> new commit, the library nicknames added and removed (removed in amber, since projects using them lose those parts) and the number of files changed. The reset runs only when the user presses Update.
- **D-09:** **Per-library Update only**, no Update all.
- **D-10:** **Licence gate: warn and acknowledge.** Every Add shows the licence first. When it is unknown, proprietary or share-alike, Add stays disabled until the user ticks "I have read the licence terms". Nothing is refused for its licence. Würth needs the tick. The acknowledgement is stored in the manifest entry.
- **D-11:** **Minimum git for the catalog: warn below 2.49.1, allow** (CVE-2025-48384; the owner's machine has 2.49.0). The catalog window shows an amber line naming the version. The commit path keeps its 2.25 minimum.
- **D-12:** **The startup update check uses `git ls-remote`**, one per installed library, through the network runner. No GitHub API, so no rate limit or ETag cache. It never blocks and never downloads. Offline: status unknown, no error.
- **D-13:** **Git LFS: refuse in staging.** `.gitattributes` with `filter=lfs`, or model files starting with `version https://git-lfs`, stops the Add with "this library keeps its 3D models in Git LFS, which the catalog doesn't support". The staging folder is deleted.
- **D-14:** **KiCad running: warn, allow** for Add, Update, Remove and Reinstall ("KiCad is open; restart it to see the changes"). Path-variable writes keep their existing KiCad-running check.
- **D-15:** **Disk space:** before a clone, compare free space with the known size (curated list or API) plus a safety margin, and refuse with the numbers when it is short. Unknown size: no check.

### Catalog window and Add flow
- **D-16:** **A non-modal window** that stays open beside the main window, like the User Guide. While an Add, Update, Remove or Reinstall runs, a library-folder switch is refused (as when the import window is open), and closing the catalog asks to cancel the running job. Layout: a search box and **Add by URL...** above a list (Name, Status, Licence, Size), and below it a detail pane for the selected library (repo, library counts, path variables needed and whether they are set, installed commit, last check time, action buttons) with a progress bar and **Cancel**.
- **D-17:** **File > Library Catalog...**, shortcut **`Ctrl+Shift+L`**, beside Import Part. Phase 19 moves it to the Libraries menu and keeps the shortcut.
- **D-18:** **After a successful Add** (cloned to staging, validated, renamed into place, registered in `catalog.json`): the main window rescans just that source and its libraries appear preselected. If the library needs path variables, the existing old -> new confirmation opens (No is the default, nothing is written without Yes). Then the result offers Generate Tables, which the user starts. The same goes for Reinstall.
- **D-19:** **Update-available notice:** one log line ("2 catalog libraries have updates: SparkFun, Espressif") and the menu entry reads `Library Catalog... (2 updates)`. No popup. Offline: no line.
- **D-20:** **Nickname collisions (CAT-08)** with KiCad stock, other catalog or `Atomic_`/Custom libraries are listed in the Add preview with what each one clashes with. Add still runs. The colliding libraries start **unchecked** in the scan, so Generate Tables adds no duplicate unless the user ticks them. Never renamed.
- **D-21:** **Remove** deletes the clone and its `catalog.json` entry after a confirmation that names the folder, its size, the nicknames that disappear and the path variables it used (with a note that projects using them lose their 3D models). Its libraries leave the scan, and the next Generate Tables drops their managed entries (already reported as "removed"). Path variables are not unset.
- **D-22:** **Curated list:** Würth and SparkFun are required (CAT-09). Espressif, 4ms and Alternate-KiCad-Library are **each verified in this phase** on the owner's machine (real network: clone, scan, 3D paths, path variables) and added to the curated list only if they pass. A failure is recorded with its reason, and that library stays installable through Add by URL.
- **D-23:** Add by URL refuses non-KiCad, KiCad 5-only (`.lib` only), PCM-only and private or not-found repos, each with a message saying why (CAT-03). https GitHub URLs only; `.git` and `/tree/...` suffixes are stripped.

### Würth conversion (CAT-12)
- **D-24:** **The owner adds Würth through the real catalog** (end-to-end test of CAT-12 with the real app), sets `WE_3DMODEL_DIR` through its confirmation (pointing into `ThirdParty/WurthElektronik/`), and runs Generate Tables, which rewrites the about 89 `WurthElektronik/KiCad-Library/...` URIs. A rescan must show zero missing. **A one-off script in `scripts/`** (like Phase 16's `scripts/split/`) then removes the submodule (`git submodule deinit -f`, `git rm`, the `.git/modules/...` data, the `.gitmodules` entry) behind a rollback tag, with dry-run and apply modes. The app gains no submodule-specific code. — **Reversibility:** costly — rollback restores the gitlink from the tag and the moved module data (D-27), and Generate runs again with the old path variable
- **D-25:** **Rehearsal first** on a `git clone --no-local` copy of the collection with a scratch KiCad config: the full sequence there, then the live run from the main checkout KiCad reads (D-26), after a `git bundle` and the rollback tag.
- **D-26:** **Pass check before the submodule is removed**, all three needed: (1) the resolved-URI lists from `scripts/split/uri_diff.py` have the same nicknames before and after, with only the Würth paths changing; (2) zero missing files; (3) the app's 3D model path check reports zero unresolved Würth models with the new `WE_3DMODEL_DIR`.
- **D-27:** **The old submodule's git data** (`.git/modules/WurthElektronik/...`, about 2.7 GB) is **moved to the owner's backup folder** outside every repository (the one named in CLAUDE.local.md), not deleted, so a rollback needs no download. The owner deletes it by hand later.

### Decided at plan time (2026-11-27, from 17-RESEARCH.md open questions)
- **D-28:** **Würth selections carry over.** The curated Würth entry records its old folder (`WurthElektronik/KiCad-Library`); after the Add, every library that was selected at the old path starts ticked at its new `ThirdParty/WurthElektronik/...` path, so one Generate Tables rewrites the about 89 entries. Generic (driven by the curated entry), no submodule code.
- **D-29:** **Catalog network actions need git 2.32 or newer** (the runner needs `GIT_CONFIG_GLOBAL`; verify the exact version at implementation). Below it, Add, Update, Reinstall and the update check are refused with a message naming the version and asking to update Git. D-11's amber warning below 2.49.1 stays; the commit path keeps its 2.25 minimum.
- **D-30:** **KiCad 9.0 settings are not touched by the Würth conversion.** The app keeps editing only the current KiCad config; the conversion script prints a line naming the stale `WE_3DMODEL_DIR` in an older KiCad config and its new value, for the owner to fix by hand.
- **D-31:** **A few missing 3D models are warnings, not a Problem state.** A library whose model paths partly miss upstream (SparkFun: 6 of 429) stays Installed; the missing models are reported as warnings in the scan and the log, like the existing 3D model path check.
- **D-32:** **The last update-check time is kept in memory only** (no new `catalog.json` field, no new QSettings key): the startup check runs on every start, so the detail pane shows the time of this session's last check, or "Not checked yet". `[informational]` — reversible, decided by Claude.

### Locked from earlier phases (not re-asked)
- Plain shallow clones plus a manifest, never submodules; the update check runs automatically at startup (owner, 2026-11-22).
- Catalog Add and Remove change only the collection and its manifest; tables are written by Generate Tables.
- No write without a preview; git commits need explicit confirmation; nicknames are never renamed automatically.
- D-26 (v2.0): live runs from the main checkout KiCad reads; Generate and Install warn on a wrong checkout.
- `gitops.py` keeps its no-remote allow-list; network git lives only in a separate runner (CAT-11: https only, no hooks or credential prompts, no submodule recursion, `core.longpaths=true`, `core.autocrlf=false`), and a layering test keeps commit-path modules from importing it.
- KiCad's PCM is never touched: `PCM_` entries, the `3rdparty` folder, `installed_packages.json` (CAT-10).
- Tests use local bare repos through `file://`, with no network in tests; the real network checks (D-22, D-24) are owner-run.

### Claude's Discretion
- The folder name for an Add by URL (`<owner>-<repo>` suggested) and the exact `catalog.json` schema (PCM vocabulary where it fits).
- Adding a `ThirdParty/` line to the collection root's `.gitignore` when one is missing, shown in the Add preview (the owner's root is a git repo; a clone there must not become an embedded repo).
- The disk-space margin, clone/fetch/ls-remote timeouts, and how Cancel kills the git process tree and removes staging (retry-on-lock rmtree).
- Whether the conversion script's commit in the owner's parent repo also stages `catalog.json` and the `.gitignore` line (shown in its dry-run, explicit confirm).
- Generalising the Würth-specific code (`importer/verify.py` `_WURTH_PREFIX` and the `layout.repo_root / "WurthElektronik"` search; the `wurth` test marker and corpus paths, which must follow the new `ThirdParty/WurthElektronik/` location).
- The User Guide page for the catalog, and the CLAUDE.md GUI Behaviour and Menu Shortcuts entries.
- Plan order and wave split, within the build order of ROADMAP.md (gitnet + layering test, manifest/curated/scan/path vars, ops tested on `file://`, dialog, Würth conversion last).

### Folded Todos
- **Stop the migration dialog's draft and rebuild timers when it closes** (`.planning/todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md`). `MigrationDialog` never stops `_draft_timer` (800 ms) or `_rebuild_timer` (300 ms) on close, so a timer due after `done()` could start a worker that the deferred delete destroys ("QThread: Destroyed while thread is still running"). Fix as the todo suggests: stop both timers in `done()` before `super().done(r)` and in the delayed close in `_reap`; a pending draft save runs as a worker through the existing close-waits path, so the last edit is kept; add a test that closes with a pending timer and checks no worker starts. It isn't catalog work: the owner folded it in as a small, separate plan. The catalog window (D-16) should follow the same close rule for its own timers and workers.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 17: Library Catalog": goal, success criteria, research flags (D2, D6, D7, D11, LFS, 304 cost, GCM vs `GIT_TERMINAL_PROMPT`), build order notes, Würth conversion notes
- `.planning/REQUIREMENTS.md` §CAT: CAT-01..CAT-12
- `.planning/PROJECT.md`: Key Decisions table (D-26, atomic naming, v3.0 scoping)
- `.planning/STATE.md`: v3.0 scoping decisions (plain clones + manifest, startup check)

### Research
- `.planning/research/SUMMARY.md`: catalog git flags, module plan (`catalog/manifest.py`, `curated.py`, `ops.py`, `gitnet.py`, `widgets/catalog_dialog.py`), open decisions D2/D6/D7/D11 (now decided above)
- `.planning/research/FEATURES.md` §"Area 2: Library catalog": table stakes, anti-features, verified curated seed list (licences, layouts, path variables of Würth, SparkFun, Espressif, 4ms, Alternate-KiCad-Library; excluded Digi-Key, Seeed OPL, CDFER as validation cases)
- `.planning/research/PITFALLS.md`: Pitfall 6 (git config leakage), 15 (untrusted clones, CVE-2025-48384, LFS), 16 (credential prompts, GCM, Cancel kills the tree), 17 (long paths, autocrlf), 18 (shallow update semantics), 19 (nickname collisions, Würth string assumptions in `verify.py`), 20 (path variables, `WE_3DMODEL_DIR`), 21 (replacing the Würth submodule), 22 (licences)
- `.planning/research/ARCHITECTURE.md` and `.planning/research/STACK.md`: catalog sections (clone layout, `gitops.launch()` extraction, git flags)

### Prior phase artifacts
- `.planning/phases/16-repo-split/16-CONTEXT.md`: D-22 (resolved-URI diff), D-23 (rehearsal on `--no-local` copies), D-18 (corpus marker)
- `scripts/split/uri_diff.py`: the resolved-URI diff reused by the Würth pass check (D-26)

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/CONCERNS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `kicad_lib_manager/collection.py`: `THIRD_PARTY_DIR = "ThirdParty"` and `source_of()` already map `ThirdParty/<id>/...` to source `<id>`; `is_collection()`.
- `kicad_lib_manager/gitops.py`: `run_git` with its `ALLOWED_SUBCOMMANDS` (no remote subcommands by design), version checks (`MIN_GIT_VERSION`). Extract the launcher (`gitops.launch()`) so `catalog/gitnet.py` shares it without widening the allow-list.
- `kicad_lib_manager/procs.py`: the one process starter.
- `kicad_lib_manager/library_scanner.py`: `sync_kicad_path_vars()` / `_desired_path_vars()` / `would_change_path_vars()` write `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` with confirm and backup; extend with `extra_vars=...` for per-library variables. The 3D-model path check and the per-source Skip already exist; "Rescan this library" re-reads one library.
- `kicad_lib_manager/table_generator.py`: the merge already drops managed entries of vanished libraries and reports removed nicknames (Remove relies on it); HARD-08 duplicate-nickname handling.
- `kicad_lib_manager/kicad_process.py`: the KiCad-running check (D-14).
- `kicad_lib_manager/widgets/background.py`, `scan_progress.py`: worker and progress patterns; `ScanWorker` QThread in `main_window.py`.
- `kicad_lib_manager/widgets/help_dialog.py`: the non-modal User Guide window, the model for D-16; already mentions WurthElektronik as a source example.

### Established Patterns
- Services are Qt-free and return `list[str]`/`Issue` messages; long work runs on a QThread; plan -> preview -> apply for every write.
- Layering tests (`tests/test_importer_layering.py`) are the pattern for "commit-path modules cannot import gitnet".
- Tests isolate git config and KiCad config per test; a test that creates a real git repo must be marked `slow`.
- A folder switch is refused while the import or migration window is open; the catalog joins that rule.

### Integration Points
- `main_window.py` File menu (next to `_act_import`), the startup sequence (background update check after the scan), the folder-switch guard.
- `importer/verify.py` (`_WURTH_PREFIX`, `layout.repo_root / "WurthElektronik"`) and the `wurth` test marker in `pyproject.toml` / `tests/conftest.py` must follow Würth's new location.

</code_context>

<specifics>
## Specific Ideas

- Catalog window layout as previewed in the discussion: search and Add by URL on top, list with Name / Status / Licence / Size, detail pane with repo, library counts, "Needs: WE_3DMODEL_DIR (set)", installed commit, last check time, Update / Remove, progress bar with Cancel.
- Menu entry text carries the update count: `Library Catalog... (2 updates)`.
- Dirty-clone refusal wording points to `Custom/` for local changes.

</specifics>

<deferred>
## Deferred Ideas

- Update all (one preview for every library with an update): declined for now (D-09).
- Pin a library to a tag or commit; remote-updatable curated list; GitLab hosts; atomic-rule quality report on a third-party clone: from research, not in this phase.
- Unsetting a removed library's path variables: declined (D-21).

</deferred>

---

*Phase: 17-library-catalog*
*Context gathered: 2026-11-26*
