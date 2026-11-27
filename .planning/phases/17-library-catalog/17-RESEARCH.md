# Phase 17: Library Catalog - Research

**Researched:** 2026-11-27
**Domain:** desktop app (PySide6 + stdlib) running hardened network `git` against untrusted GitHub repositories, a JSON manifest, KiCad path variables, one previewed submodule-to-clone conversion
**Confidence:** MEDIUM-HIGH (git behaviour and code facts verified by runs and by reading source this session; the three optional curated libraries and some Windows edge cases are not)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Where clones live and the manifest (D2)**
- **D-01:** Catalog libraries are cloned into **`ThirdParty/<id>/`** under the collection root (curated entries use their curated id, for example `ThirdParty/WurthElektronik/`, `ThirdParty/SparkFun/`). `source_of()` already maps `ThirdParty/<id>/...` to source `<id>`. Würth moves once from `WurthElektronik/KiCad-Library` (see D-24..D-28). — **Reversibility:** costly — moving the folder again means rewriting every managed table URI and repointing the path variables of every installed library
- **D-02:** The manifest is **`catalog.json` at the collection root**, beside `ThirdParty/`. It records per library: id, URL, branch, installed commit, path variables (name and clone-relative target), and the licence acknowledgement (D-10). Validated on read; a bad or unreadable manifest is a reported problem, never a crash.
- **D-03:** **The app writes `catalog.json` and never commits it.** In the owner's collection (root is a git repo) it shows up as a changed file the owner commits by hand. In a new collection (root is a plain folder) it is just a file. No new commit path is added in this phase.
- **D-04:** **Add by URL, licence and size before cloning:** one unauthenticated GitHub API call (`api.github.com/repos/<owner>/<repo>`) for size, default branch and SPDX licence. When it reports `NOASSERTION` or none, the `LICENSE*` file found in the staging clone is shown before the library is registered. Offline or rate-limited: size and licence are shown as unknown and the staging check still runs. Curated entries carry licence and size in the app's own list, with no API call needed.
- **D-05:** **A manifest entry whose folder is missing** (another machine, or deleted by hand) shows **"Problem: folder missing"** with a **Reinstall** button that clones the recorded URL and branch again. Remove still works. This is how a collection is recreated on another machine.
- **D-06:** **A `ThirdParty/` folder that `catalog.json` doesn't list** shows **"Problem: not in the catalog"**, is still scanned like any source, and its only action is Remove (with confirmation). The app never deletes it on its own. Leftovers in `ThirdParty/.staging/` are the exception and are cleaned up silently.

**Update, licence and git (D6, D7, D11)**
- **D-07:** **Update = `fetch --depth 1 origin <branch>` + `reset --hard FETCH_HEAD`, only on a clean tree.** `status --porcelain` must be empty first. Otherwise Update refuses, lists the changed files and says local changes belong in `Custom/`. Catalog clones are managed read-only copies.
- **D-08:** **Update preview:** fetch first (the working tree doesn't change yet), then show old -> new commit, the library nicknames added and removed (removed in amber, since projects using them lose those parts) and the number of files changed. The reset runs only when the user presses Update.
- **D-09:** **Per-library Update only**, no Update all.
- **D-10:** **Licence gate: warn and acknowledge.** Every Add shows the licence first. When it is unknown, proprietary or share-alike, Add stays disabled until the user ticks "I have read the licence terms". Nothing is refused for its licence. Würth needs the tick. The acknowledgement is stored in the manifest entry.
- **D-11:** **Minimum git for the catalog: warn below 2.49.1, allow** (CVE-2025-48384; the owner's machine has 2.49.0). The catalog window shows an amber line naming the version. The commit path keeps its 2.25 minimum.
- **D-12:** **The startup update check uses `git ls-remote`**, one per installed library, through the network runner. No GitHub API, so no rate limit or ETag cache. It never blocks and never downloads. Offline: status unknown, no error.
- **D-13:** **Git LFS: refuse in staging.** `.gitattributes` with `filter=lfs`, or model files starting with `version https://git-lfs`, stops the Add with "this library keeps its 3D models in Git LFS, which the catalog doesn't support". The staging folder is deleted.
- **D-14:** **KiCad running: warn, allow** for Add, Update, Remove and Reinstall ("KiCad is open; restart it to see the changes"). Path-variable writes keep their existing KiCad-running check.
- **D-15:** **Disk space:** before a clone, compare free space with the known size (curated list or API) plus a safety margin, and refuse with the numbers when it is short. Unknown size: no check.

**Catalog window and Add flow**
- **D-16:** **A non-modal window** that stays open beside the main window, like the User Guide. While an Add, Update, Remove or Reinstall runs, a library-folder switch is refused (as when the import window is open), and closing the catalog asks to cancel the running job. Layout: a search box and **Add by URL...** above a list (Name, Status, Licence, Size), and below it a detail pane for the selected library (repo, library counts, path variables needed and whether they are set, installed commit, last check time, action buttons) with a progress bar and **Cancel**.
- **D-17:** **File > Library Catalog...**, shortcut **`Ctrl+Shift+L`**, beside Import Part. Phase 19 moves it to the Libraries menu and keeps the shortcut.
- **D-18:** **After a successful Add** (cloned to staging, validated, renamed into place, registered in `catalog.json`): the main window rescans just that source and its libraries appear preselected. If the library needs path variables, the existing old -> new confirmation opens (No is the default, nothing is written without Yes). Then the result offers Generate Tables, which the user starts. The same goes for Reinstall.
- **D-19:** **Update-available notice:** one log line ("2 catalog libraries have updates: SparkFun, Espressif") and the menu entry reads `Library Catalog... (2 updates)`. No popup. Offline: no line.
- **D-20:** **Nickname collisions (CAT-08)** with KiCad stock, other catalog or `Atomic_`/Custom libraries are listed in the Add preview with what each one clashes with. Add still runs. The colliding libraries start **unchecked** in the scan, so Generate Tables adds no duplicate unless the user ticks them. Never renamed.
- **D-21:** **Remove** deletes the clone and its `catalog.json` entry after a confirmation that names the folder, its size, the nicknames that disappear and the path variables it used (with a note that projects using them lose their 3D models). Its libraries leave the scan, and the next Generate Tables drops their managed entries (already reported as "removed"). Path variables are not unset.
- **D-22:** **Curated list:** Würth and SparkFun are required (CAT-09). Espressif, 4ms and Alternate-KiCad-Library are **each verified in this phase** on the owner's machine (real network: clone, scan, 3D paths, path variables) and added to the curated list only if they pass. A failure is recorded with its reason, and that library stays installable through Add by URL.
- **D-23:** Add by URL refuses non-KiCad, KiCad 5-only (`.lib` only), PCM-only and private or not-found repos, each with a message saying why (CAT-03). https GitHub URLs only; `.git` and `/tree/...` suffixes are stripped.

**Würth conversion (CAT-12)**
- **D-24:** **The owner adds Würth through the real catalog** (end-to-end test of CAT-12 with the real app), sets `WE_3DMODEL_DIR` through its confirmation (pointing into `ThirdParty/WurthElektronik/`), and runs Generate Tables, which rewrites the about 89 `WurthElektronik/KiCad-Library/...` URIs. A rescan must show zero missing. **A one-off script in `scripts/`** (like Phase 16's `scripts/split/`) then removes the submodule (`git submodule deinit -f`, `git rm`, the `.git/modules/...` data, the `.gitmodules` entry) behind a rollback tag, with dry-run and apply modes. The app gains no submodule-specific code. — **Reversibility:** costly — rollback restores the gitlink from the tag and the moved module data (D-27), and Generate runs again with the old path variable
- **D-25:** **Rehearsal first** on a `git clone --no-local` copy of the collection with a scratch KiCad config: the full sequence there, then the live run from the main checkout KiCad reads (D-26), after a `git bundle` and the rollback tag.
- **D-26:** **Pass check before the submodule is removed**, all three needed: (1) the resolved-URI lists from `scripts/split/uri_diff.py` have the same nicknames before and after, with only the Würth paths changing; (2) zero missing files; (3) the app's 3D model path check reports zero unresolved Würth models with the new `WE_3DMODEL_DIR`.
- **D-27:** **The old submodule's git data** (`.git/modules/WurthElektronik/...`, about 2.7 GB) is **moved to the owner's backup folder** outside every repository (the one named in CLAUDE.local.md), not deleted, so a rollback needs no download. The owner deletes it by hand later.

**Locked from earlier phases (not re-asked)**
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

### Deferred Ideas (OUT OF SCOPE)
- Update all (one preview for every library with an update): declined for now (D-09).
- Pin a library to a tag or commit; remote-updatable curated list; GitLab hosts; atomic-rule quality report on a third-party clone: from research, not in this phase.
- Unsetting a removed library's path variables: declined (D-21).

### Folded Todos
- **Stop the migration dialog's draft and rebuild timers when it closes** (`.planning/todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md`). `MigrationDialog` never stops `_draft_timer` (800 ms) or `_rebuild_timer` (300 ms) on close, so a timer due after `done()` could start a worker that the deferred delete destroys ("QThread: Destroyed while thread is still running"). Fix as the todo suggests: stop both timers in `done()` before `super().done(r)` and in the delayed close in `_reap`; a pending draft save runs as a worker through the existing close-waits path, so the last edit is kept; add a test that closes with a pending timer and checks no worker starts. It isn't catalog work: the owner folded it in as a small, separate plan. The catalog window (D-16) should follow the same close rule for its own timers and workers.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAT-01 | Catalog window lists curated libraries with status, licence, size | `catalog/status.py` row model (5 states), curated list data verified below, window model copied from `HelpDialog`, `Ctrl+Shift+L` is free (grep of every `setShortcut` this session) |
| CAT-02 | One-click curated Add: shallow clone, progress, Cancel, validated before registered, licence shown first | Exact clone argv, `StreamedProcess` with tree kill (verified), staging layout, two-phase `stage_add` / `commit_add`, progress regex |
| CAT-03 | Add by URL; refuse non-KiCad, KiCad 5-only, PCM-only, private | URL policy, one API call (cost verified), `ls-remote --symref` for default branch (verified), staging validation rules and messages |
| CAT-04 | Update and Remove with confirmations | `fetch --depth 1 <url> <branch>` + `reset --hard <sha>` (verified incl. force-push), `diff-tree` preview (verified), remove = delete clone + manifest entry |
| CAT-05 | Plain clones in a manifest, appear in scan and Generate Tables | `catalog.json` schema, `scan_source`/`remove_source`, `.staging` scan exclusion, `library_description` fix, selection carry-over |
| CAT-06 | Path variables set through the old -> new confirmation | `extra_vars` for `sync_kicad_path_vars` / `would_change_path_vars`, var-name rules, folder auto-detection, new `${VAR}` model check |
| CAT-07 | Startup check without download, offline = unknown | `ls-remote --exit-code` (verified 0.6 s, exit codes), daemon-thread pattern, kill on close |
| CAT-08 | Collision warning, never rename | stock footprint + symbol nickname sets, scan `collision_peers`, unchecked start (existing `_copy_selection`) |
| CAT-09 | Würth, SparkFun verified; others only if verified | Real clones and scans of SparkFun and 4ms done; Espressif fails; Alternate not cloned (size) |
| CAT-10 | PCM untouched | var-name deny rule `KICAD*`, never write outside root/`ThirdParty`/`catalog.json`/`.gitignore`, sentinel test |
| CAT-11 | Network git safe, commit path cannot reach network | Hardened flag set verified by runs, env, allow-list, layering tests; test-suite constraints that force the design |
| CAT-12 | Würth becomes a catalog entry, nothing missing | Conversion script shape, three pass checks, selection carry-over gap, rollback, runtime state inventory |
</phase_requirements>

## Summary

The milestone research is sound on the big choices (plain shallow clones, a manifest, a separate network runner) and is now fully decided by CONTEXT.md. This research checked it against today's code and against real git on this machine (git 2.49.0 for Windows, system config with `credential.helper=manager`, `core.autocrlf=true`, `core.symlinks=false`, git-lfs filters). It found **twelve places where the plan must differ from the milestone text or from what CONTEXT.md implies**; they are listed under "Corrections" and each one has a concrete fix. The three most important: (1) the shared launcher is `procs.py`, not a new `gitops.launch()`, because two existing tests pin who may start a process or import `subprocess`; (2) the scanner has **no** check that a `${VAR}/model.step` path resolves for a non-Custom source, so D-26 check (3) needs a new scanner rule fed by the manifest; (3) CONTEXT.md does not say how the owner's 89 selected Würth libraries move to the new `ThirdParty/WurthElektronik/...` paths, and the existing selection is keyed by `rel_path`, so a carry-over step is needed.

Real verification was done where it was cheap and safe: SparkFun and 4ms were shallow-cloned with the hardened flags (9-10 s each), scanned with the app's own `scan_all`, and their model paths checked against the clone; Espressif was read through the GitHub tree API and fails (its footprints use KiCad's PCM variable `${KICAD8_3RD_PARTY}`); Alternate-KiCad-Library was structure-checked but not cloned (185 MB, above the 150 MB rule). Würth's layout was read from the owner's existing checkout (read-only): 7,612 model paths, all `${WE_3DMODEL_DIR}/<lib>.3dshapes/...`, and a **9.6 GB working tree in 15,426 files**, much more than the 2.6 GB API size suggests, which changes the disk-space rule of D-15.

**Primary recommendation:** Build bottom-up in the order of CONTEXT.md, but put the shared process starter in `procs.py` (`StreamedProcess` with tree-kill), keep `catalog/gitnet.py` importing only `models` and `procs`, keep every decision in pure, Qt-free, fake-net-testable functions so the quick run covers the logic, and prove the git flags with a small set of `slow` `file://` tests plus pinned-argv quick tests.

## Corrections to the milestone research and gaps in CONTEXT.md (verified against current code)

| # | Milestone/CONTEXT says | Verified fact | Consequence for the plan |
|---|------------------------|---------------|--------------------------|
| C1 | "extract `gitops.launch()`; gitnet shares it" | `tests/test_procs.py:102-113` `test_only_procs_starts_processes` forbids any `subprocess.Popen/run/...` and `os.spawn*/popen/system` outside `procs.py`; `tests/test_gitops.py:238` asserts `importers == {"gitops.py", "kicad_process.py", "importer/kicad_cli.py", "procs.py"}` for `import subprocess`. `run_process` is `subprocess.run`-based and cannot stream or cancel | Add `StreamedProcess`/`start_process` **to `procs.py`** (it is the one starter). `gitnet` imports `procs` + `models` only and must **not** `import subprocess`. Do not touch `gitops` for this. Taskkill must also go through `run_process`. |
| C2 | "D-26(3): the app's 3D model path check reports zero unresolved Würth models" | `library_scanner._check_model_files` only flags non-Custom paths that do not start with `${` (`elif not path.startswith("${") and ("/" in path or "\\" in path):`, line 659). A `${WE_3DMODEL_DIR}/x.step` path is never resolved or reported | New rule: pass the manifest's per-source `vars` into the scan (`model_vars`) and check exact-case existence. Without it D-26(3) is vacuous. |
| C3 | "rescan zero missing; selection carries over" | Selection is keyed by `rel_path` (`MainWindow._copy_selection`). New Würth libraries live at `ThirdParty/WurthElektronik/...`, the 89 selected ones at `WurthElektronik/KiCad-Library/...`; both have source `WurthElektronik` and the same nicknames, so they collide (`collision_peers`) and new ones start unchecked | Add a **moved-library selection carry-over**: curated entry field `legacy_prefix` (Würth: `WurthElektronik/KiCad-Library/`), applied once after Add (see "Würth conversion"). Needs an owner/planner decision (Open Question 1). |
| C4 | `table_generator.library_description` is generic | Line 58: `source = rel_path.split("/", 1)[0]` gives `ThirdParty` for every catalog library ("ThirdParty: Antenna SMD Wurth"). Existing managed descriptions are kept by URI tail, so moved paths lose theirs | Use `collection.source_of(rel_path)`. `table_generator` ALLOWED imports in `tests/test_layering.py:19` must add `collection`, or pass the source in. |
| C5 | `ThirdParty/.staging/` is "just a folder" | `source_of("ThirdParty/.staging/x/y.pretty")` returns `.staging`; `_walk_matches` prunes only `.git` at any depth and `SKIP_DIRS` at top level; `scan_cache._walk` the same | A running or leftover staging clone would appear as a library source and in the saved-scan fingerprint. Prune `ThirdParty/.staging` in both walkers (`library_scanner._walk_matches` and `scan_cache._walk`). |
| C6 | Scanner treats non-variable model paths as absolute | `kicad-embed://...` (embedded model) is reported `scan.model_absolute` | Real 4ms scan: 9 false warnings. Exempt `kicad-embed://` in `_check_model_files`. |
| C7 | Clone is "plain git" | The system config on this machine defines `filter.lfs.*` (git-lfs). **Any** git command in a clone that has `filter=lfs` files runs `git-lfs` and installed `post-checkout`, `post-commit`, `post-merge`, `pre-push` hooks into the clone's `.git/hooks` (observed) | Neutralise `filter.lfs.*` on every network-runner call, set `GIT_LFS_SKIP_SMUDGE=1`, and re-check `.gitattributes` of `FETCH_HEAD` before an update reset (a library can adopt LFS later). |
| C8 | D-07 "status --porcelain empty" | A synthetic repo with two paths differing only by case (`Footprints/` and `footprints/`) leaves `M Footprints/Lib.pretty/a.kicad_mod` forever after clone and after every reset (the reported case even flips). SparkFun's real tree has `Footprints/` and `footprints/` too, but its colliding folders hold distinct files, so its real status is clean today | Keep the clean-tree rule, add a small `known_dirty` baseline (casefolded paths recorded right after clone/update when non-empty) so a repo like this cannot lock Update forever. |
| C9 | Free-space check "known size plus margin" | API `size` is packed history in KB. Measured working tree + `.git` on disk: SparkFun API 69 MB gives 302 MB (4.3x), 4ms 58 MB gives 324 MB (5.4x); Würth API 2.6 GB, owner's checked-out tree alone is **9.6 GB / 15,426 files** | Required free space = about 6 x API size + 500 MB for Add by URL; curated entries should carry a measured `install_mb`. Würth needs about 12 GB or more. |
| C10 | `git status`/`rev-parse` in a clone folder is safe | `git -C <folder without .git> rev-parse --show-toplevel` **returned the parent collection repository** (verified). A `reset --hard` there would hit the owner's collection | Network runner sets `GIT_DIR=<clone>/.git` and `GIT_WORK_TREE=<clone>` for every local operation in a clone (verified: a missing `.git` then fails with "not a git repository"). |
| C11 | `git diff --shortstat` for "files changed" | `git diff` (porcelain) allows textconv and external diff drivers named by the repo's `.gitattributes` (system config defines `diff.astextplain.textconv`) | Use plumbing `diff-tree -r --no-renames --name-status -z` (verified in a depth-1 clone), count lines. No textconv. |
| C12 | Espressif "verify 3D paths" | 42 of its 45 model paths (in 68 footprints) use `${KICAD8_3RD_PARTY}` / `${KICAD9_3RD_PARTY}` (PCM-baked, e.g. `${KICAD8_3RD_PARTY}/3dmodels/com_github_espressif_kicad-libraries/espressif.3dshapes/...`); redefining those variables would touch PCM's folder (CAT-10) | Espressif fails D-22: not curated, recorded with this reason, stays installable by URL (with a "N models use KiCad PCM variables" warning). |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Catalog list, detail pane, licence tick, progress, Cancel | GUI thread (`widgets/catalog_dialog.py`) | main window (menu text, busy refusal) | Qt widgets only; no git, no disk walks |
| Clone / fetch / reset / ls-remote | Worker thread -> child `git` process (`catalog/gitnet.py` via `procs`) | none | The only network path; cancellable; never on the GUI thread |
| GitHub API call (size, licence, default branch) | Worker thread (`catalog/githubapi.py`, urllib) | none | Separate from the git runner, https `api.github.com` only |
| Staging validation, collision list, var detection, status rows | Qt-free service (`catalog/validate.py`, `status.py`) | worker thread | Pure filesystem and text; fully testable without git |
| Manifest read/write, curated list | Qt-free service (`catalog/manifest.py`, `curated.py`) | disk (`catalog.json`) | Untrusted JSON, atomic write through `fsutil` |
| Add / Update / Remove / Reinstall orchestration | Qt-free service (`catalog/ops.py`) | worker thread | plan -> preview -> apply, returns `list[Issue]` |
| Source scan merge (`scan_source`, `remove_source`), `${VAR}` model check, `.staging` skip | Scanner (`library_scanner.py`) | `scan_cache.py` | Existing owner of scanning; manifest vars come in as a plain mapping, so no catalog import |
| KiCad path variables | `library_scanner.sync_kicad_path_vars` (+ `extra_vars`) | main window confirm | Existing confirm, backup, KiCad-running logic |
| Table rows for catalog libraries | `table_generator` via Generate Tables | none | Unchanged mechanism; only the description rule changes |
| Update check at startup | Daemon thread (`widgets/background.run_in_background` pattern) | main window | A hung `ls-remote` must never abort the app at exit (QThread rule in `background.py` docstring) |
| Würth submodule removal | One-off script in `scripts/` | owner's collection git | Not app code (D-24) |

## Standard Stack

### Core
No new package. Everything is the standard library plus what the app already uses.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`json`, `re`, `urllib.request`, `shutil`, `os`, `threading`, `queue`) | 3.14 (venv) | manifest, URL policy, API call, free space, process streaming | Already the project's rule: stdlib only unless clearly justified |
| PySide6 | 6.12 (installed) | catalog window, `QThread` job worker | existing |
| git | installed 2.49.0 (below the D-11 line 2.49.1) | clone/fetch/ls-remote/reset | the only git; not bundled |

### Supporting
| Module (existing) | Used for |
|-------------------|----------|
| `fsutil.atomic_write_text`, `read_source`, `backup_file` | manifest and `.gitignore` writes with EOL/BOM kept |
| `procs.run_process` | non-streaming starts (taskkill, `git --version`) |
| `widgets/import_dialog.TaskWorker` (line 343, `class TaskWorker(QThread):`) | the job worker with `progress/result/failed` signals |
| `widgets/background.run_in_background` | daemon-thread startup check |
| `kicad_process.kicad_running` | D-14 warning |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `taskkill /T /F` | Windows Job Object (ctypes) | Job objects are tidier but add ctypes surface; taskkill verified to kill git + git-remote-http in 1.6 s |
| `GIT_CONFIG_GLOBAL=<nul>` | also `GIT_CONFIG_NOSYSTEM=1` | NOSYSTEM verified to work with https here, but it drops the system file's TLS settings (`http.sslBackend`, `http.sslCAInfo`) that corporate setups may depend on; keep system config, override with `-c` |
| `git clone` | GitHub zip download | no history needed, but no `ls-remote` update model and no commit identity; rejected by CONTEXT |

**Installation:** none (no new dependency). `requirements*.txt` unchanged.

**Version verification:** `git --version` prints `git version 2.49.0.windows.1` (this session). No registry package is added, so no `npm view`/`pip index` step applies.

## Package Legitimacy Audit

No external package is installed by this phase (stdlib, existing PySide6, system git). Nothing to audit.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 menu Ctrl+Shift+L ---> CatalogDialog (non-modal, parentless like HelpDialog)
                          |  rows <- status.row_statuses(manifest, curated, update_states, folders on disk)
                          |  Add / Add by URL / Update / Remove / Reinstall / Cancel
                          v
                 TaskWorker (QThread)  --progress--> bar + log      (one job at a time)
                          |   cancel token (threading.Event)
                          v
                    catalog/ops.py  (Qt-free, returns Issues + plan objects)
        +-----------------+------------------+-------------------------------+
        v                 v                  v                               v
 githubapi.py        gitnet.py          validate.py                   manifest.py / curated.py
 (urllib, https      (hardened argv,    (staging tree checks:         (catalog.json untrusted
  api.github.com,     env, allow-list,   KiCad? KiCad5? PCM? LFS?      JSON, atomic write)
  one GET)            ls-remote/clone/   symlinks, libs, collisions,
        |             fetch/reset/       3D vars, licence file)
        |             diff-tree/status)          |
        |                  |                     |
        |             procs.StreamedProcess      +--> filesystem: ThirdParty/.staging/<job>/ --rename--> ThirdParty/<id>/
        |             (Popen, stderr lines,
        |              taskkill /T /F cancel)
        v                  v
   GitHub API         git.exe -> git-remote-https -> github.com  (https only)

 startup:  MainWindow scan ends --> run_in_background(check_updates) --> gitnet.ls_remote per entry
              --> {id: current | available | unknown} --> log line + menu text "(N updates)"

 after Add / Reinstall (main window, existing patterns):
   rescan source only (scan_source) --> preselect non-colliding libs --> extra_vars confirm
   (sync_kicad_path_vars, No default) --> result offers Generate Tables (user starts it)

 Generate Tables (unchanged): scan selection --> table_generator merge (managed marker ${KICAD_LIB_GITHUB}/)
```

### Recommended Project Structure
```
kicad_lib_manager/
  procs.py                    # + StreamedProcess, start_process (the one starter)
  catalog/
    __init__.py               # docstring only
    urls.py                   # parse_github_url, valid_id, valid_branch (pure)
    gitnet.py                 # NetGit: the only module whose argv may hold clone/fetch/ls-remote/reset --hard
    githubapi.py              # repo_info(owner, repo) -> RepoInfo | Issue (urllib, one GET)
    manifest.py               # CatalogEntry, load/save/validate catalog.json, var rules, path_vars()
    curated.py                # CURATED tuple (Python module, frozen-safe)
    validate.py               # validate_staging(folder) -> StagingReport (Qt-free filesystem checks)
    ops.py                    # plan/stage/commit add, plan/apply update, plan/apply remove, reinstall
    status.py                 # State, row_statuses(), check_updates()
  widgets/catalog_dialog.py   # window
  library_scanner.py          # + model_vars rule, kicad-embed exemption, .staging prune, scan_source/remove_source, extra_vars
  scan_cache.py               # + .staging prune, catalog.json in the fingerprint
  table_generator.py          # library_description uses source_of
  main_window.py              # menu action, busy refusal, startup check, post-Add handler
scripts/catalog/wurth_to_catalog.py     # one-off conversion, dry run + apply
tests/ (see Validation Architecture)
```

### Pattern 1: process starter that streams and cancels (`procs.py`)
**What:** one class owns the child, a reader thread puts stderr chunks on a queue, the caller loops with a short poll, so a stalled server (no output) can still be cancelled.
**Verified behaviour:** a git clone against a TCP server that accepts and never answers had two live processes (`git.exe`, `git-remote-http.exe`); `taskkill /T /F /PID <pid>` ended both in 1.6 s, `poll()` returned 1, no survivors; the half-made destination folder **still existed** afterwards, so staging removal is a separate, retried step.
```python
# Source: verified in this session (scratchpad experiment exp_kill.py), shape only
class StreamedProcess:
    def __init__(self, popen): ...                # Popen created in procs.py with creationflags=
                                                   # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW, stdin=DEVNULL,
                                                   # stdout=DEVNULL, stderr=PIPE
    def lines(self, poll=0.2, stop=None):         # yields stderr split on \r and \n; checks stop() each poll
    def wait(self, timeout=None): ...
    def cancel(self):                              # win32: run_process([System32\taskkill.exe, "/T", "/F", "/PID", pid]);
                                                   # else os.killpg(pid, SIGKILL) (start_new_session=True)
```

### Pattern 2: two-phase Add (plan, stage+validate, preview, commit)
1. `plan_add(...)`: URL policy, optional API call, git version line, disk-space check, licence known/unknown, `.gitignore` need, KiCad-running warning. Pure except the API call.
2. `stage_add(...)` (worker): `clone` into `ThirdParty/.staging/<id>.<8 hex>/`; `validate_staging`; returns `Staged` (library lists, collisions, detected vars, licence text, warnings) or an `Issue` (staging deleted).
3. UI shows the preview (D-20 collisions, licence, vars, `.gitignore` edit) and the licence tick (D-10).
4. `commit_add(...)`: re-check the target is free, `os.replace(staging, ThirdParty/<id>)` (same parent, atomic, retry on `PermissionError` like `atomic_write_bytes`), write `catalog.json` atomically, optional `.gitignore` line; if the manifest write fails, move the folder back. Only then does the main window rescan.
Cancel or close at any point before step 4 deletes staging.

### Pattern 3: manifest vars become `extra_vars`
`manifest.path_vars(root, entries) -> dict[str, str]` builds `VAR -> "<root>/ThirdParty/<id>/<folder>"` with forward slashes (the same `str(root).replace("\\", "/")` rule as `_desired_path_vars`). `sync_kicad_path_vars(..., extra_vars=...)` and `would_change_path_vars(..., extra_vars=...)` merge them into `desired`. Because `_plan_changes` and `_only_vars_changed` already take `desired`, no other change is needed. Every caller that passes `self._root` today (`_on_path_var_check`, `_offer_path_vars_after_switch`) reads the manifest and passes the extras, so Generate Tables and a folder switch also offer a missing catalog variable.

### Anti-Patterns to Avoid
- **Widening `gitops.ALLOWED_SUBCOMMANDS`** (pinned by `tests/test_gitops.py::EXPECTED_ALLOWED`) or adding `gitnet.py` to `GIT_MODULES` in `test_gitops.py` (its forbidden-constant test would fail by design).
- **`import subprocess` in `catalog/*`** (breaks the pinned importer set).
- **Running git in a clone with discovery** (C10), with the user's global config, or without the `filter.lfs.*` override (C7).
- **Using `origin` from the clone's own `.git/config` as the URL**: pass the manifest URL explicitly; the clone config is never trusted.
- **Writing `last_check` into `catalog.json`**: it would dirty the owner's tracked file on every start; keep it in memory or `QSettings`.
- **A QThread for the startup check**: a hung `ls-remote` at exit would abort the process (docstring of `widgets/background.py`).

## The git command lines (exact)

All argv are lists, `shell` never used, `--` before every URL/path, option values attached with `=` (`--branch=<b>`). Values come from validated regexes (below). `<NUL>` is `os.devnull`.

**Common prefix (every network-runner call):**
```
git --literal-pathspecs
    -c core.quotepath=false
    -c credential.helper=            -c core.askPass=
    -c protocol.allow=never          -c protocol.https.allow=always        # tests add: -c protocol.file.allow=always
    -c core.hooksPath=               -c core.fsmonitor=false
    -c transfer.bundleURI=false      -c submodule.recurse=false
    -c http.sslVerify=true           -c http.lowSpeedLimit=1000  -c http.lowSpeedTime=60
    -c filter.lfs.process=  -c filter.lfs.smudge=  -c filter.lfs.required=false
    -c diff.external=       -c core.pager=cat
```
**Clone (staging):**
```
git <prefix> clone --depth 1 --single-branch --branch=<branch> --no-tags --template= --progress
    --config core.autocrlf=false --config core.longpaths=true --config core.symlinks=false
    -- <https-url> <staging-folder>
```
**Update fetch (preview phase), then apply:**
```
git <prefix> -C <clone> fetch --depth 1 --no-tags --no-recurse-submodules --progress -- <manifest-url> <branch>
git <prefix> -C <clone> rev-parse --verify FETCH_HEAD^{commit}                 -> <sha>   (kept for the apply)
git <prefix> -C <clone> diff-tree -r --no-renames --name-status -z --no-commit-id HEAD <sha>
git <prefix> -C <clone> ls-tree -r --name-only -z <sha>                        (nicknames added/removed; .gitattributes names)
git <prefix> -C <clone> cat-file blob <sha>:<path>/.gitattributes              (LFS re-check; rc 128 = no such file)
git <prefix> -C <clone> status --porcelain=v1 -z --untracked-files=all          (clean tree rule)
git <prefix> -C <clone> reset --hard -q <sha>                                    (apply; the previewed sha, never FETCH_HEAD)
```
**Update check (startup), one per library:**
```
git <prefix> ls-remote --exit-code -- <manifest-url> refs/heads/<branch>        rc 0: "<sha>\trefs/heads/<branch>"; rc 2: branch gone; rc 128: unreachable/private
git <prefix> ls-remote --symref -- <url> HEAD                                    "ref: refs/heads/<default>\tHEAD" then "<sha>\tHEAD"  (Add by URL default branch)
```
**Environment (built from scratch, not from `gitops._env`):** copy `os.environ` minus every `GIT_*` key; then set `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, `GIT_CONFIG_GLOBAL=<NUL>`, `GIT_OPTIONAL_LOCKS=0`, `GIT_LFS_SKIP_SMUDGE=1`, `LC_ALL=C`; for any operation inside a clone also `GIT_DIR=<clone>/.git` and `GIT_WORK_TREE=<clone>`. Do **not** set `GIT_CONFIG_NOSYSTEM`. Proxy variables pass through untouched.

**Verified this session [VERIFIED: runs on git 2.49.0.windows.1]:**
- `ls-remote` over https with this prefix: exit 0, 0.4-0.6 s, correct sha; a nonexistent repo: exit 128 at once with `fatal: could not read Username for 'https://github.com': terminal prompts disabled` and **no Git Credential Manager window** although the system config here names `credential.helper=manager` (the empty `credential.helper=` clears it); `http://` URL: `fatal: transport 'http' not allowed`.
- Clone with the clone flags: exit 0, config persisted (`core.autocrlf=false`, `core.longpaths=true`, `core.symlinks=false`, `remote.origin.tagopt=--no-tags`), no hook files from the remote, no sample hooks.
- `core.longpaths`: without it a 379-character destination path fails (`Filename too long`, exit 128, "Clone succeeded, but checkout failed") even though the OS `LongPathsEnabled` is 1; with `--config core.longpaths=true` it succeeds.
- A user-level `core.hooksPath` **does** run a `post-checkout` hook during `git clone` (hook ran), `--template=` alone does **not** stop it; `-c core.hooksPath=` (empty) or `=<NUL>` stops it; `GIT_CONFIG_GLOBAL=<NUL>` also stops it.
- LFS: with the three `filter.lfs.*` overrides a `filter=lfs` file stays a pointer (`version https://git-lfs.github.com/spec/v1` visible) and the clone succeeds; without the overrides any later git command in the clone ran git-lfs and wrote four hooks.
- `fetch --depth 1 <url> <branch>` then `reset --hard <sha>` works after a normal advance and after a force-push to an unrelated (orphan) history; `diff-tree` between `HEAD` and the fetched commit works in a depth-1 clone; `status --porcelain=v1 -z --untracked-files=all` lists edits and untracked files.
- `http.lowSpeedLimit=1000` + `http.lowSpeedTime=4` against a stalled server: `fatal: unable to access ...: Operation too slow` after 4.1 s, exit 128 (git itself is the stall timer).

**Not verified (owner-run if wanted):** whether `GIT_TERMINAL_PROMPT=0` alone (without clearing the helper) suppresses Git Credential Manager's window. It must not be run from automation (it could open a window). The design does not depend on it because the helper is cleared. Owner-run, only if curious: `set GIT_TERMINAL_PROMPT=0` then `git ls-remote https://github.com/<owner>/<private-repo>.git` in a console on a machine with GCM, and watch for a window.

## Module boundaries and function signatures (against current code)

```python
# procs.py (extend; only file allowed to hold Popen / taskkill start)
def start_process(argv, *, env=None, cwd=None, starter=None) -> "StreamedProcess"

# catalog/urls.py  (imports: models only)
GITHUB_HOST = "github.com"
def parse_github_url(text: str, *, allow_file: bool = False) -> "RepoRef | Issue"   # RepoRef(owner, repo, https_url, default_id)
def valid_id(text: str) -> bool            # ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$, not .staging, not Windows reserved, not only dots, no trailing dot/space
def valid_branch(text: str) -> bool        # ^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$, no "..", no "//", no trailing "/" or ".lock"

# catalog/gitnet.py  (imports: models, procs)
NET_SUBCOMMANDS = frozenset({"clone", "fetch", "ls-remote", "reset", "status", "rev-parse", "diff-tree", "ls-tree", "cat-file"})
MIN_NET_GIT_WARN = (2, 49, 1)
@dataclass(frozen=True)
class NetGit:
    exe: Path
    allow_file: bool = False        # tests only (file:// through the same code); production never sets it
    starter: Callable | None = None # tests only
def ls_remote(net, url, branch) -> "RemoteHead | Issue"            # RemoteHead(sha) ; Issue code git.unreachable | git.branch_missing
def default_branch(net, url) -> "tuple[str, str] | Issue"          # (branch, sha) from --symref
def clone_shallow(net, url, branch, dest, *, progress, cancel, limit_bytes=None) -> "GitRun | Issue"
def fetch_shallow(net, clone, url, branch, *, progress, cancel) -> "str | Issue"   # returns the fetched sha
def reset_hard(net, clone, sha) -> "GitRun | Issue"
def status_entries(net, clone) -> "list[str] | Issue"
def changed_paths(net, clone, sha) -> "list[tuple[str, str]] | Issue"
def tree_paths(net, clone, rev) -> "list[str] | Issue"
def read_blob(net, clone, rev, path) -> "bytes | None"

# catalog/githubapi.py  (stdlib only)
@dataclass(frozen=True)
class RepoInfo: size_kb: int; default_branch: str; spdx: str | None; private: bool; archived: bool; full_name: str
def repo_info(owner: str, repo: str, *, opener=None, timeout=10.0) -> "RepoInfo | Issue"   # Issue code api.unknown (offline, 403 rate limit) never blocks Add

# catalog/manifest.py  (imports: models, fsutil, collection)
@dataclass(frozen=True)
class CatalogEntry: id; url; branch; commit; vars: dict[str, str]; licence_spdx: str | None; acknowledged: bool; known_dirty: tuple[str, ...] = ()
def load(root: Path) -> "Manifest | Issue"           # missing file = empty manifest; bad file = Issue (reported, never raised)
def save(root: Path, manifest: "Manifest") -> "Issue | None"   # fsutil.atomic_write_text, UTF-8, LF, trailing newline
def path_vars(root: Path, entries) -> dict[str, str]
def valid_var_name(name: str) -> bool                # ^[A-Z][A-Z0-9_]{2,63}$ and NOT KiCad's or the app's own names:
                                                     #   ^KICAD\d+_ , ^KISYS , _3RD_PARTY$ , KIPRJMOD , KICAD_(USER|SYSTEM)_TEMPLATE_DIR ,
                                                     #   KICAD_LIB_GITHUB , CUSTOM_3DMODEL_DIR   (note: 4ms's real KICAD_4MS_LIBS must pass)

# catalog/validate.py  (imports: models, kicad_files, collection)
def validate_staging(folder: Path, *, stock_fp: set[str], stock_sym: set[str], own: set[str], other_catalog: dict[str, str]) -> "StagingReport | Issue"
def detect_vars(folder: Path, footprint_files: list[Path]) -> dict[str, str]    # VAR -> clone-relative folder, stock/PCM vars excluded
def unresolved_models(folder: Path, vars: dict[str, str]) -> list[str]           # exact-case, used by the dialog, scan rule and conversion script

# catalog/ops.py  (imports: models, fsutil, collection, manifest, validate, urls, curated, gitnet, githubapi)
def plan_add(root, source: "CuratedEntry | str", net, ...) -> "AddPlan | Issue"
def stage_add(root, plan, net, *, progress, cancel) -> "Staged | Issue"
def commit_add(root, staged, *, acknowledged: bool, gitignore_edit: bool) -> list[Issue]
def discard_staging(staged) -> None
def plan_update(root, entry, net, *, progress, cancel) -> "UpdatePlan | Issue"
def apply_update(root, plan, net) -> list[Issue]
def plan_remove(root, entry) -> "RemovePlan"
def apply_remove(root, plan) -> list[Issue]
def clean_staging(root, *, older_than_s=3600) -> list[Issue]    # D-06: silent, skips fresh folders (another app instance)

# catalog/status.py
class State(Enum): NOT_INSTALLED; INSTALLED; UPDATE_AVAILABLE; PROBLEM            # "unknown" is a flag on INSTALLED, not a fifth state
def row_statuses(root, manifest, curated, updates: dict[str, "UpdateState"]) -> list["Row"]
def check_updates(root, manifest, net, *, cancel, on_one=None) -> dict[str, "UpdateState"]   # stops after the first timeout (offline)

# library_scanner.py (extend)
def scan_all(..., model_vars: Mapping[str, Mapping[str, str]] | None = None)       # source -> {VAR: clone-relative folder}
def scan_source(repo_root, previous: ScanResult, source_dir: str, kicad_fp_dir=None, *, model_vars=None) -> "ScanResult | Issue"
def remove_source(previous: ScanResult, source: str, kicad_fp_dir=None) -> ScanResult
def sync_kicad_path_vars(repo_root, *, ..., extra_vars: Mapping[str, str] | None = None)
def would_change_path_vars(repo_root, *, config_base=None, extra_vars=None)
```
`scan_source`/`remove_source` follow the `rescan_library` pattern (merge into a copy of the last scan, recompute collisions, cross-references and the atomic summary from the merged lists, return an `Issue` with code `rescan.full_needed` when only a full scan is right). A full scan with Würth takes about 70 s (the 3D check about 63 s, per the `scan_all` comment), so the per-source path is worth having. Test seam: `NetGit.starter`.

**Quoted facts these signatures rest on** [VERIFIED: read this session]:
- `kicad_lib_manager/collection.py:22` `THIRD_PARTY_DIR = "ThirdParty"` and lines 81-88: `def source_of(rel_path: str) -> str:` ... `if parts and parts[0] == THIRD_PARTY_DIR and len(parts) > 1 and parts[1]:` `return parts[1]`.
- `kicad_lib_manager/gitops.py:22-27` the allow-list is `"--version", "rev-parse", "symbolic-ref", "status", "merge-base", "rev-list", "log", "ls-tree", "cat-file", "var", "add", "reset", "switch", "commit", "ls-files", "diff-tree", "check-ignore", "tag", "init"`; line 30 `MIN_GIT_VERSION = (2, 25)`.
- `kicad_lib_manager/library_scanner.py:217-223` `_desired_path_vars` returns `{"KICAD_LIB_GITHUB": repo_str, "CUSTOM_3DMODEL_DIR": f"{repo_str}/{OWN_DIR}/{MODELS_DIR}"}`; line 245 `def sync_kicad_path_vars(`; line 226 `def would_change_path_vars(repo_root: Path, *, config_base: Path | None = None) -> bool:`.
- `kicad_lib_manager/procs.py:11` `def run_process(argv: Sequence[str], *, runner: Callable | None = None, **kwargs):`.
- `kicad_lib_manager/table_generator.py:58` `source = rel_path.split("/", 1)[0]`.

### Manifest schema (Claude's discretion, recommended)
```json
{
  "format": 1,
  "libraries": [
    {
      "id": "SparkFun",
      "url": "https://github.com/sparkfun/SparkFun-KiCad-Libraries.git",
      "branch": "main",
      "commit": "1f1f7b8fdacd76f334bb0c0d83074d8ffedcc95c",
      "vars": {"SPARKFUN_KICAD_LIBRARY": ""},
      "licence": {"spdx": null, "acknowledged": true},
      "known_dirty": []
    }
  ]
}
```
`vars` values are clone-relative folders (`""` = the clone root, `"3dmodels"` for Würth). The folder is **derived** (`ThirdParty/<id>`), never stored, so a hand-edited manifest cannot point outside. Validation on read (same untrusted-JSON helpers as `scan_cache._text/_list/_dict`): `format` an int, unknown higher format = read-only problem; ids unique case-insensitively and `valid_id`; `url` passes `parse_github_url`; `branch` passes `valid_branch`; `commit` is 40 hex or empty; every var name passes `valid_var_name` and every folder has no `..`, no drive, no leading `/`. File size cap (for example 1 MB) before `json.loads`.

### Staging validation (messages for D-13, D-23)
Order, stopping at the first refusal; all on files, never executing anything from the clone:
1. **Layout**: count `*.kicad_sym` and `*.pretty` folders with the scanner's walkers (`.git` pruned). None found: if `*.lib` (and `*.dcm`) exist -> "KiCad 5-only: this repository has only the old `.lib` format"; elif PCM markers (`metadata.json` carrying a `$schema` with `kicad`, `repository.json`, `packages.json`, `PCM*` folders or a `.zip` that is the only content) -> "PCM-only: install it through KiCad's Plugin and Content Manager"; else "no KiCad libraries found". Libraries plus leftover `.lib` files is fine (4ms has 24 `.lib` and 25 `.kicad_sym`).
2. **LFS** (D-13): any `.gitattributes` line with `filter=lfs`; or a file under 1 KB whose first bytes are `version https://git-lfs.github.com/spec/v1`. Refuse with the D-13 text.
3. **Symlinks / reparse points**: any entry where `os.path.islink` or `os.path.isjunction` (3.12+) is true: refuse (clones also carry `core.symlinks=false`, so this only fires on odd platforms).
4. **Submodules**: `.gitmodules` present: allow, warn "submodules are not downloaded".
5. **Licence file**: first of `LICENSE*`, `UNLICENSE*`, `COPYING*` at the root (case-insensitive) for the D-04 fallback display (read at most 64 KB).
6. **Variables**: `detect_vars` (below). Models using KiCad's own variables (`^KICAD\d*_`) are counted and reported ("N models use KiCad's own variables; they resolve only on a matching KiCad version, or never for PCM paths"), never mapped.
7. **Collisions (D-20)** against KiCad stock footprint nicknames (`get_kicad_default_fp_nicknames`), KiCad stock symbol nicknames (stems of `*.kicad_sym` in `find_kicad_footprint_dir().parent / "symbols"`; no helper exists, add one beside it), other catalog sources and `Custom`/`Atomic_` libraries (from the last scan). Output: `list[(nickname, kind, clashes_with)]`.

**`detect_vars`** (verified idea against the real SparkFun, 4ms and the owner's Würth): for each `${VAR}/rest` model path with a non-KiCad variable, find where `rest` lives in the clone using an index keyed on the last two path components (`<x>.3dshapes/<file>`); the folder is the prefix common to at least 80 % of that variable's sampled paths. Results: SparkFun `${SPARKFUN_KICAD_LIBRARY}/3dmodels/<lib>.3dshapes/<f>` -> `""`; 4ms `${KICAD_4MS_LIBS}/3dmodels/...` -> `""`; Würth `${WE_3DMODEL_DIR}/<lib>.3dshapes/<f>` -> `"3dmodels"`. Curated entries carry the verified map; detection is the check for Add by URL.

### The `${VAR}` model rule in the scanner (fixes C2, C6)
In `_check_model_files`, for a non-Custom `source` with `model_vars.get(source)`: if `path` matches `^\$\{([A-Za-z0-9_]+)\}/(.*)` and the variable is in that source's map, resolve to `<source dir>/<folder>/<rest>` and test membership in a per-(source, folder) **set of exact relative names** (build it once with `os.walk`; do not use `exists()` because Windows ignores case, the same reason `_custom_model_names` exists); a miss is `Issue(WARNING, "scan.model_missing", f"[{rel}] 3D model not found in {id}/{folder} (names are case-sensitive): {path}")`. Unknown variables and KiCad's own variables are not checked (as today). Exempt `kicad-embed://`. Thread `model_vars` through `scan_all`, `rescan_library` and `ScanWorker`/`LibraryRescanWorker` (the worker reads the manifest at the thread boundary; a bad manifest means no rule, never an exception). Put `catalog.json`'s `(mtime, size)` into `scan_cache.fingerprint` (a var change must invalidate the saved scan); `_code_signature()` already covers rule changes in code.

## Real verification of the curated candidates (D-22, CAT-09)

Method: SparkFun and 4ms shallow-cloned with the hardened clone line into a scratch collection (`Custom/` skeleton + `ThirdParty/<id>`), scanned with the app's own `scan_all`, model paths resolved with the proposed rule; Espressif and Alternate read through the GitHub tree API and raw files (no clone). Scratch folders deleted afterwards. API numbers are from the unauthenticated REST API on 2026-11-27.

| id | Repo @ branch | API size | Licence | Result |
|----|---------------|----------|---------|--------|
| WurthElektronik | `WurthElektronik/KiCad-Library` @ `master` | 2.6 GB (2,738,361 KB) | API `NOASSERTION`; proprietary Würth terms (PDF in repo) -> tick required (D-10) | Layout read from the owner's checkout (read-only): 402 `.kicad_sym`, 43 `.pretty`, 7,612 model paths **all** `${WE_3DMODEL_DIR}/<lib>.3dshapes/<file>`, 0 non-variable paths. Working tree **9.6 GB, 15,426 files**. Not cloned (multi-GB). Owner KiCad 10 and 9 configs both hold `WE_3DMODEL_DIR` today, written with backslashes, pointing at `...\WurthElektronik\KiCad-Library\3dmodels`. Vars: `{"WE_3DMODEL_DIR": "3dmodels"}` |
| SparkFun | `sparkfun/SparkFun-KiCad-Libraries` @ `main` | 69 MB | API `null`; README says CC BY 4.0 [CITED: milestone FEATURES.md] -> curated list must carry it | **Passes.** Clone 9.4 s, 302 MB on disk (.git 43 MB), status clean. Scan: 30 symbol + 21 footprint libraries on Windows (upstream has `Footprints/` and `footprints/` as separate folders; Windows merges them, three `.pretty` names appear in both; no real file clash), 0 nickname collisions. 429 `${SPARKFUN_KICAD_LIBRARY}` model paths, **6 missing upstream** (for example `Capacitor.3dshapes/CP_Elec_5x4.4.step`, `Connector.3dshapes/FPC_0.5mm-22-RA.step`; confirmed absent from the folder), 2 stock `${KICAD9_3DMODEL_DIR}`. Vars `{"SPARKFUN_KICAD_LIBRARY": ""}`. Two footprint-library warnings (`lcd-tft` not found) are upstream's |
| 4ms | `4ms/4ms-kicad-lib` @ `master` | 58 MB | API and `metadata.json`: Unlicense | **Passes.** Clone 10.1 s, 324 MB. 25 symbol + 29 footprint libraries (includes `footprints-legacy/4ms-legacy-footprints.pretty`), 0 collisions. 126 `${KICAD_4MS_LIBS}` paths, **0 missing**; 266 stock `${KICAD10_3DMODEL_DIR}` (KiCad 10 only); 9 `kicad-embed://` (false warning today, C6); `[4ms_IC]` references footprint library `PCM_Espressif` which is not in the repo (upstream, warning). Vars `{"KICAD_4MS_LIBS": ""}` |
| Espressif | `espressif/kicad-libraries` @ `main` | 72 MB | API `NOASSERTION`; `LICENSE.md` | **Fails D-22.** All 68 footprints read, 45 model paths: 39 use `${KICAD8_3RD_PARTY}`, 3 `${KICAD9_3RD_PARTY}`, 1 `${KICAD8_3DMODEL_DIR}`, 2 `${KICAD10_3DMODEL_DIR}`. PCM-baked paths; mapping them would redefine PCM variables (CAT-10). Record the reason; stays installable by URL |
| Alternate-KiCad-Library | `DawidCislo/Alternate-KiCad-Library` @ `main` | 181 MB (above the 150 MB rule, **not cloned**) | API `null` (PCM metadata says CC-BY-SA per milestone research) | Structure only: 39 `.kicad_sym` in `symbols/`, 63 unique `.pretty` in `Footprints/`, 11,274 footprints, no own 3D models, models use stock `${KICAD10_3DMODEL_DIR}` (sampled 12). Needs the owner-run clone (below). Expect a long first scan (11k footprint files) |

**Owner-run verification (D-22), per library, on the real network** (nothing here runs from automation): in the app Add the library from the catalog, wait for the scan, then check the log for model warnings. For a scripted double check, from a scratch collection folder (not the owner's):
`git clone --depth 1 --single-branch --no-tags --template= -c core.hooksPath= -c credential.helper= --config core.autocrlf=false --config core.longpaths=true -- https://github.com/DawidCislo/Alternate-KiCad-Library.git ThirdParty/Alternate-KiCad-Library`
then Rescan and note: library counts, `scan.nickname_collision` lines against KiCad stock, clone time and disk size. Record pass/fail with the reason in this phase's summary; add to `curated.py` only on pass.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes with EOL/BOM kept | custom temp-file code | `fsutil.atomic_write_text`, `read_source` | retry on locks, EOL preserved |
| Backups of `kicad_common.json`, old -> new confirm, KiCad-running check | a second variable writer | `sync_kicad_path_vars(extra_vars=...)` | the confirm, the `_PATH_VAR_PASSES` re-read and the backup pruning already exist |
| Killing a process tree | `proc.kill()` alone | `taskkill /T /F /PID` through `run_process` (verified) | `proc.kill()` leaves `git-remote-https` |
| Stall/timeout of a network transfer | a Python watchdog on bytes | `http.lowSpeedLimit` / `http.lowSpeedTime` (verified) plus a wall-clock cap | git itself reports `Operation too slow` |
| Rewriting a tree to read-only-safe delete | `shutil.rmtree` bare | a shared `fsutil.remove_tree` (clear read-only bit, retry on `PermissionError`); `collection._remove_tree` is private and `tests/gitfixtures.remove_tree` is test-only | `.git/objects` is read-only on Windows and Defender holds files |
| Resolved-URI proof for the Würth pass check | a new comparison | `scripts/split/uri_diff.py snapshot` and `compare` | reused by D-26 |
| Nickname collision detection inside the scan | a second algorithm | `find_nickname_collisions` / `collision_peers` | the tree, `_trim_collided_selection` and Generate already honour it |
| Checking a repo-local ignore rule | parsing `.gitignore` | `gitops.ignored_paths` (`check-ignore --no-index`) and `gitops.show_toplevel` | already in the allow-list |
| Table entry removal after Remove | a new table editor | the existing merge (`table.stale_managed` / `table.removed`) on the next Generate | D-21 |
| Layering enforcement | ad-hoc greps | the AST pattern of `tests/test_importer_layering.py` | one proven pattern |

**Key insight:** nearly every hard part already has a tested home in this repo. The risk is not missing machinery, it is wiring the new network path without bypassing the three existing guards (only `procs` starts processes, only four modules import `subprocess`, `gitops` has no remote subcommand).

## Runtime State Inventory (Würth conversion = migration)

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | The owner's tables (`sym-lib-table`, `fp-lib-table` in the newest KiCad config folder) hold about 89 managed `${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library/...` URIs. The saved scan (`%APPDATA%/KiCadExtLibManager/scan_cache/`, one file per root) caches Würth libraries at the old paths. No database. | Data migration: Generate Tables rewrites the URIs (needs C3 carry-over); the saved scan invalidates itself through the fingerprint (files appear/vanish). Code edit: none for storage |
| Live service config | KiCad `kicad_common.json` `environment.vars.WE_3DMODEL_DIR` exists in the **10.0 and the 9.0** config folders (old path, backslashes). The app edits only the newest, so 9.0 keeps pointing at the removed folder | Data migration through the app's confirm (10.0). Tell the owner 9.0 is not updated (decision: leave, or edit by hand) |
| OS-registered state | None found: no scheduled task or service names the folder (the app registers nothing). KiCad open holds no persistent handles to `.kicad_mod`, but its 3D viewer may keep STEP files open | None; the script refuses while KiCad runs (use the same tasklist check as `kicad_process`) |
| Secrets/env vars | None. `WE_3DMODEL_DIR` is a KiCad path variable (not a secret); `tests/conftest.py` clears `WE_3DMODEL_DIR` per test (verified in `_CLEARED_VARS`) | None |
| Build artifacts / installed | `.git/modules/WurthElektronik` is about 2.7 GB (verified `du`); `.gitmodules` holds the Würth section; the collection's `README.md` and `CLAUDE.md` (templates in `scripts/split/collection/`) describe Würth as a submodule at the old path; `tests` use `corpus_path("WurthElektronik")` | Code edits: README/CLAUDE templates and the owner's copies; test paths (below). Data move: module data to the backup folder (D-27) |

Würth-specific code and tests to generalise (grep this session): `importer/verify.py:27` `_WURTH_PREFIX = "WurthElektronik:"` and `:238` `wurth = layout.repo_root / "WurthElektronik"` (`symbol_search_dirs`; `_symbol_files` walks Würth recursively and the rest flat) -> search every `ThirdParty/<id>` recursively, label `<id>:`, keep the legacy folder while it exists; `widgets/help_dialog.py` (2 mentions); `tests/test_roundtrip_corpus.py:242,250` `corpus_path("WurthElektronik")` -> `corpus_path("ThirdParty", "WurthElektronik")`; `tests/test_corpus_audit.py:23` the `_DATA` regex names `Custom|WurthElektronik|downloaded_examples|\.planning` (add `ThirdParty`); `tests/customfixtures.py:305`, `test_footprint_index.py:50-54`, `test_install_verify.py:422-429,492-496`, `test_official_footprint.py:375-381` use the old folder (keep passing through the legacy-folder support, add ThirdParty cases); `scripts/prepublish_scan.py` and `scripts/split/*` mention Würth (historical, unchanged).

**The canonical question answered:** after every file is updated, what still holds the old string? The owner's tables (until Generate), `kicad_common.json` 9.0 `WE_3DMODEL_DIR`, `.git/modules/WurthElektronik`, table backups (`*_backup_N`, harmless history), and the collection's docs.

## Würth conversion script (CAT-12, D-24..D-27)

`scripts/catalog/wurth_to_catalog.py`, same discipline as `scripts/split/cutover_collection.py` (read: it prints a plan and writes nothing unless `--apply`, refuses before any write, never runs `git clean`/`push`, prints the way back). Modes: `plan` (default), `--apply`.

**Preconditions (both modes, read-only, exit 1 on any miss):** `--repo` is the collection's top folder and the checkout KiCad reads; on `main`; no uncommitted tracked change except `.gitignore`/`catalog.json`/docs the app or owner edited (listed); `.gitmodules` and `git ls-files -s` show the Würth gitlink (mode 160000) and `Custom`; `catalog.json` has entry `WurthElektronik`, its folder exists, its `.git` is a directory, `git status` clean (baseline allowed), HEAD equals the recorded commit or is shown; KiCad not running; `WE_3DMODEL_DIR` in the newest `kicad_common.json` equals `<root>/ThirdParty/WurthElektronik/3dmodels` (forward slashes); the three D-26 checks pass:
1. `--before` and `--after` snapshots from `uri_diff snapshot` (taken before the Add and after Generate): rewrite the `before` snapshot's `uri` and `resolved` strings with `<LIB>/WurthElektronik/KiCad-Library/` -> `<LIB>/ThirdParty/WurthElektronik/` and call `uri_diff.compare`; it must print no difference (same nicknames, only Würth paths moved, every entry `exists`).
2. `after["missing"] == []` (and report `disabled_missing` as notes, as `uri_diff` does).
3. `catalog.validate.unresolved_models(clone, entry.vars)` is empty for `WE_3DMODEL_DIR`. The script may `sys.path`-insert the tool checkout (it ships in the same repo), unlike `uri_diff` which stays stdlib-only.

**Apply sequence:** (a) `git bundle create <backup folder>/pre-wurth.bundle --all` and verify it (`git bundle verify`); (b) lightweight tag `pre-wurth-catalog` at HEAD (script runs plain `git`; it is not the app); (c) `git submodule deinit -f -- WurthElektronik/KiCad-Library`; (d) `git rm -f -- WurthElektronik/KiCad-Library` (removes the gitlink, the work tree and the `.gitmodules` section; deleting 15,426 files takes minutes on Windows); (e) remove the empty `WurthElektronik/` folder; (f) **move** `.git/modules/WurthElektronik` to `<backup folder>/wurth-modules/` (D-27; same drive, `shutil.move`; refuse when the target exists); (g) stage `.gitignore` (`ThirdParty/` line), `catalog.json`, the README/CLAUDE edits, show the diff, and commit only with an explicit `--message` after the dry-run text (Claude's discretion item: recommended yes, exact files listed); (h) post-checks: `git submodule status` lists only `Custom` at its previous SHA, `.gitmodules` has no Würth section, `git ls-files` equals `.gitignore .gitmodules CLAUDE.md Custom README.md catalog.json`, `git status --porcelain` empty, `ThirdParty` untracked and ignored (`check-ignore`).

**Way back (printed, not run):** close KiCad; move `<backup folder>/wurth-modules` back to `.git/modules/WurthElektronik`; `git checkout pre-wurth-catalog -- .gitmodules .gitignore README.md CLAUDE.md WurthElektronik/KiCad-Library` then `git submodule update --init -- WurthElektronik/KiCad-Library` (objects are local, no download); restore the earlier `kicad_common.json` from the app's backup (`<default backup dir>/kicad_common/<version>/kicad_common.json_backup_N`) or set `WE_3DMODEL_DIR` back in KiCad Preferences > Configure Paths; File > Restore Backup (`Ctrl+R`) restores the previous table pair. Also `git bundle` is the last resort.

**Rehearsal (D-25):** `git clone --no-local <main checkout> <scratch>`; the submodule data must be initialised from the local module data (a download is 2.6 GB): run the app with `--library-root <scratch>` and `APPDATA` pointing at a scratch KiCad config folder (the app reads `%APPDATA%/kicad/<ver>` through `os.environ`, but Qt's `QSettings` ignores `APPDATA`, so one extra entry lands in the real Recent list: harmless). Walk the whole sequence there first.

**Carry-over of the 89 selections (C3, Open Question 1):** recommended minimal design: `CuratedEntry.legacy_prefix` (Würth: `WurthElektronik/KiCad-Library/`). After the scan that follows an Add, for every library under `ThirdParty/<id>/<rest>` whose twin `<legacy_prefix><rest>` exists and is selected: select the new one, unselect the twin, log one line "Moved N selected libraries from <old> to ThirdParty/<id>; Generate Tables rewrites their entries". It is generic ("a catalog entry that replaces a folder"), contains no submodule code, runs through `scan_source` results and needs no git. Without it the owner would have to re-tick about 89 libraries by hand while 402+43 same-name pairs show as collisions.

## Common Pitfalls

### Pitfall 1: a tripwire turns a "quick" catalog test into a failure
**What goes wrong:** `tests/conftest.py` swaps `subprocess.Popen` for non-slow tests and fails the test at teardown when a git `init` or `clone` command started (`_git_repo_command`, lines 196-244 and 421-447). `gitfixtures._require_slow` fails first for repository builders.
**How to avoid:** quick tests never start git: fake `NetGit.starter` and fake-net `ops`. Real clones live only in `@pytest.mark.slow` tests. A quick test may start a **Python** child through `StreamedProcess` (not matched by the tripwire).

### Pitfall 2: `rmtree` on a fresh clone fails on Windows
**What goes wrong:** read-only pack files, Defender or indexer holding files; a killed clone leaves a half-made folder (verified it exists after tree-kill).
**How to avoid:** one `fsutil.remove_tree(folder, retries)` (clear the read-only bit, retry `PermissionError` with short sleeps like `atomic_write_bytes`); refuse to remove a link or junction (`islink`/`isjunction`); containment check `folder.resolve().is_relative_to(root/ThirdParty)` before deleting. Leftover `.staging` folders older than an hour are removed silently when the catalog opens (a younger one may belong to another running instance).

### Pitfall 3: git commands that climb into the collection repository
**What goes wrong:** (C10) a clone without `.git` resolves to the parent repo; `reset --hard` or `status` then act on the owner's collection.
**How to avoid:** explicit `GIT_DIR`/`GIT_WORK_TREE`, plus an `os.path.isdir(clone/".git")` pre-check in ops, plus a `.git/config` allow-list parse (next pitfall).

### Pitfall 4: the clone's own `.git/config` is not trustworthy
**What goes wrong:** a restored backup, a hand edit or another program can add `core.fsmonitor`, `core.sshCommand`, `core.pager`, `diff.external`, `alias.*`, `core.hooksPath`, `credential.helper`, `remote.origin.url` pointing elsewhere. Local config is read by every git command.
**How to avoid:** before any git command in an installed clone, parse `.git/config` as text (no git) and allow only keys git itself writes for this clone: `core.repositoryformatversion|filemode|bare|logallrefupdates|symlinks|ignorecase|autocrlf|longpaths|fscache|precomposeunicode|protectNTFS`, `remote.origin.url|fetch|tagopt`, `branch.<b>.remote|merge`, `gc.*`, `maintenance.*`, `lfs.repositoryformatversion` (git-lfs writes it). Anything else: PROBLEM "unexpected git settings in <id>" and no git command runs. Always pass the **manifest** URL, never `origin`. Command-line `-c` already overrides the known dangerous keys.

### Pitfall 5: shallow-clone and case-collision status noise
**What goes wrong:** C8. Update refused forever on a repo like the synthetic case-colliding one; the case of the reported path flips between runs.
**How to avoid:** `known_dirty` (casefolded) recorded after clone/update when the status is non-empty; Update compares `{p.casefold()} - known`. The dirty-file list shown to the user excludes the baseline.

### Pitfall 6: LFS adopted by a library later
**What goes wrong:** an Update brings `.gitattributes` with `filter=lfs`; `reset --hard` then writes pointer files and git-lfs hooks.
**How to avoid:** `plan_update` reads every `.gitattributes` in `ls-tree` of the fetched sha through `cat-file blob` and refuses (D-13 text) before any reset; the reset also runs with the `filter.lfs.*` overrides.

### Pitfall 7: QThread destroyed while running at close
**What goes wrong:** the repo has hit "QThread: Destroyed while thread is still running" (todo, `background.py` docstring, `tests/conftest.py` teardown notes).
**How to avoid:** the catalog window and the main window follow the import/migration pattern: `is_running()`, close asks to cancel (D-16), `cancel()` kills the process tree, the window waits for the worker without blocking (`done()` override like `MigrationDialog.done`), timers stopped on close, and `MainWindow.closeEvent` closes the catalog window and waits for its worker. The startup check uses a daemon thread, and `closeEvent` calls `cancel()` on its `StreamedProcess` so no `git ls-remote` outlives the app.

### Pitfall 8: help page numbering test
**What goes wrong:** `tests/test_help_dialog.py:565-566` hard-codes the outline numbers (`"migrating": "4.5", "restoring": "4.6", "filter": "5", ...`). Inserting a page before `restoring` shifts them.
**How to avoid:** append `("catalog", "Library Catalog")` as the **last** child of `_how_to_use` (it becomes 4.7; top-level 5, 6, 7 do not move) and extend that test; add `Ctrl+Shift+L` to the shortcuts page (`tests/test_help_dialog.py:91-95` enumerates them) and to the CLAUDE.md shortcut table (`tests/test_docs_split.py:180-181` reads it).

### Pitfall 9: menu accelerator clash
`&Library Catalog...` would share `&L` with `Recent &Library Collections` in the same File menu; pick another letter (for example `Library Catalo&g...`).

### Pitfall 10: the busy refusals miss the new window
`MainWindow._switch_refusal` (lines 847-859) lists scan, import, migration, KiCad checks, atomic. Add a catalog-job state returning a `_BUSY_CATALOG` text, and make **Rescan, Generate Tables, Import and Migrate** refuse while a catalog Add/Update/Remove/Reinstall runs (an update `reset --hard` rewriting files under a running scan produces torn results; `_set_scan_running` is the existing disable list).

## Code Examples

### Hardened argv and env builder (the shape the tests pin)
```python
# Source: flags verified by runs in this session (see "The git command lines"); names are the proposal
_BASE = ("credential.helper=", "core.askPass=", "protocol.allow=never", "protocol.https.allow=always",
         "core.hooksPath=", "core.fsmonitor=false", "transfer.bundleURI=false", "submodule.recurse=false",
         "http.sslVerify=true", "http.lowSpeedLimit=1000", "http.lowSpeedTime=60",
         "filter.lfs.process=", "filter.lfs.smudge=", "filter.lfs.required=false", "diff.external=", "core.pager=cat")

def _argv(net, sub: str, args, *, clone=None):
    if sub not in NET_SUBCOMMANDS:
        raise ValueError(f"git {sub} is not allowed")
    cfg = list(_BASE) + (["protocol.file.allow=always"] if net.allow_file else [])
    flat = [x for item in cfg for x in ("-c", item)]
    return [str(net.exe), "--literal-pathspecs", "-c", "core.quotepath=false", *flat, *(["-C", str(clone)] if clone else []), sub, *args]

def _env(clone=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_LFS_SKIP_SMUDGE="1", LC_ALL="C")
    if clone is not None:
        env.update(GIT_DIR=str(Path(clone) / ".git"), GIT_WORK_TREE=str(clone))
    return env
```

### Progress from `--progress` stderr (split on `\r` and `\n`)
```python
# Source: observed git output in this session ("Receiving objects:  45% (x/y), 10.5 MiB | 5.2 MiB/s", "Updating files: 30% (100/333)")
_STAGE = re.compile(r"(Counting objects|Compressing objects|Receiving objects|Resolving deltas|Updating files):\s+(\d+)%")
_BAND = {"Counting objects": (0, 5), "Compressing objects": (5, 10), "Receiving objects": (10, 70),
         "Resolving deltas": (70, 80), "Updating files": (80, 100)}
def percent(line: str) -> int | None:
    m = _STAGE.search(line)
    if not m:
        return None
    lo, hi = _BAND[m.group(1)]
    return lo + (hi - lo) * int(m.group(2)) // 100
```
A clone of a small repository also prints `Cloning into '<path>'...`; treat unparsed lines as log text, and keep the last 5 lines for the failure message (strip any `https://user:pass@` before logging).

### Name-status parse (verified output: status, NUL, path, NUL)
```python
def parse_name_status(raw: str) -> list[tuple[str, str]]:
    parts = raw.split("\0")
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2) if parts[i]]
```

### Hermetic real-git upstream for slow tests (plumbing, no work tree, case collisions possible)
```python
# Source: verified in this session (exp_difftree.py): commit-tree through a private index builds any tree, even paths
# that differ only by case, and a force-push is just update-ref to an orphan commit
def commit_tree(bare, files: dict[str, str], parent=None) -> str:
    env = {**base_env, "GIT_DIR": str(bare), "GIT_INDEX_FILE": str(bare.parent / "idx")}
    for path, text in files.items():
        sha = git("hash-object", "-w", "--stdin", env=env, input=text.encode()).strip()
        git("update-index", "--add", "--cacheinfo", f"100644,{sha},{path}", env=env)
    tree = git("write-tree", env=env).strip()
    commit = git("commit-tree", tree, "-m", "m", *(["-p", parent] if parent else []), env=env).strip()
    git("update-ref", "refs/heads/main", commit, env=env)
    return commit
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Submodule per vendor library | Plain shallow clone + manifest | decided 2026-11-22 | no parent-repo gitlink churn, works for users without a parent repo |
| `--recurse-submodules` clones | never recurse; warn on `.gitmodules` | CVE-2025-48384 (fixed 2.49.1/2.50.1 and older branches) | the catalog is unaffected by the CVE class even on 2.49.0, but D-11 warns |
| GitHub API polling for updates | `git ls-remote` | CONTEXT D-12 | no rate limit, no token, 0.6 s per library |
| KiCad PCM-only distribution of vendor libraries | Both PCM zip and git source exist | ongoing | PCM-baked 3D paths (Espressif, CDFER) do not resolve in a plain clone |

**Deprecated/outdated:** milestone item "extract `gitops.launch()`" (C1); milestone "Espressif as candidate" (C12); `ARCHITECTURE.md` remark that `_check_model_files` "already treats non-Custom sources leniently" is true but means there is no resolution check (C2).

## Folded todo: stop the migration dialog's timers on close (small separate plan)

Facts [VERIFIED: read `widgets/migration_dialog.py` and its test file this session]: timers created at lines 560-568 (`_rebuild_timer` 300 ms to `_start_rebuild`, `_draft_timer` 800 ms to `_start_save_draft`), restarted at lines 1065-1066, 1224-1225 and 1600-1601; `done(r)` (line 1876) returns early while running/committing or when `_closing`, otherwise sets `_closing`/`_pending_result` when any worker runs, else `super().done(r)`; `_reap` (line 1120) finishes a deferred close with `QDialog.done`. Fix: at the top of `done()` after the refusal checks, remember `pending = self._draft_timer.isActive()`, stop both timers; if `pending`, call `self._start_save_draft()` so the last edit is kept (the worker is then covered by the existing "any running" branch). In `_reap`, stop both timers again before `QDialog.done`. Guard `_start_rebuild` and `_start_save_draft` with `if self._closing: return` except for the one deliberate final save. Test (quick, `qtbot`, like `test_close_while_planning_waits_without_blocking` at `tests/test_migration_dialog.py:699`): edit a field so both timers are active, call `reject()`, assert both timers inactive and that after the dialog closes exactly one save worker ran (draft kept) and no rebuild worker started afterwards. The catalog dialog reuses the same close shape.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ASVS chapter numbering (V5 validation, V9 communications, V10 malicious code, V12 files, V14 configuration) follows ASVS 4.0.3 | Security Domain | label mismatch only |
| A2 | `GIT_CONFIG_GLOBAL` exists from git 2.32; older git ignores it and would read the user's global config | gitnet env, floor | on git below 2.32 the user's hooks/insteadOf could apply; propose a hard floor `(2, 32)` for network operations (an extension of D-11, planner/owner call) |
| A3 | Free-space rule "about 6 x API size + 500 MB" | D-15 | too strict or too loose for unusual repos; measured ratios 4.3 and 5.4 (small repos), Würth worktree alone 3.5x |
| A4 | GitHub's API answers an unauthenticated request for a private repo with 404 (indistinguishable from not found); rate limit 60/h | Add by URL | the 60/h limit is verified from response headers (`X-RateLimit-Limit: 60`); the 404 behaviour for a real private repo was not exercised |
| A5 | `GIT_ALLOW_PROTOCOL=https` env would add belt and braces to `protocol.*.allow` | gitnet | config keys are verified; the env var was not exercised, so the plan uses config only |
| A6 | Windows `taskkill /T` works the same from a frozen/packaged app; `os.killpg` path on Linux/macOS untested | Cancel | CI and the owner run Windows; non-Windows is unproven |
| A7 | `os.path.isjunction` exists from Python 3.12 | symlink/junction check | the venv is 3.14; older Pythons would need `getattr` fallback |
| A8 | Würth shallow clone time and its `.git` size are unknown (worktree 9.6 GB measured on the owner's existing checkout) | disk-space rule, UAT | first real Add may take many minutes and about 12 GB or more |
| A9 | Alternate-KiCad-Library will scan cleanly after a real clone | curated list | not verified (size above the rule); stays out of the curated list until the owner run |
| A10 | `git-lfs` hook installation behaviour in other git-lfs versions | C7 | the neutralising flags are applied regardless |
| A11 | SparkFun licence is CC BY 4.0 (README, per milestone FEATURES.md) and Espressif/Alternate are CC-BY-SA family | curated licence column | wrong licence text shown; curated entries must be re-read from the repos' LICENSE/README during planning |
| A12 | Defender or the indexer can lock files during rename of a fresh clone | commit_add | handled by the retry loop; the number of retries is a guess |

## Open Questions

1. **How do the 89 selected Würth libraries move to the new paths?**
   - What we know: selection is by `rel_path`; old and new libraries share nicknames and collide; D-24 says Generate rewrites the URIs; D-20 starts colliding libraries unchecked.
   - What's unclear: CONTEXT.md does not say who selects the new ones.
   - Recommendation: the `legacy_prefix` carry-over above (generic, no git, tested without git). Needs the owner's yes or an explicit alternative (tick by hand).
2. **Hard git floor for network operations?** D-11 allows 2.49.0 with a warning. Recommend an additional refusal below 2.32 because `GIT_CONFIG_GLOBAL` is needed (A2). Confirm with the owner.
3. **Where is "last check time" kept?** Not in `catalog.json` (dirties a tracked file). Recommend memory plus one `QSettings` key per root; planner's call.
4. **9.0 KiCad config:** leave `WE_3DMODEL_DIR` in the 9.0 folder pointing at the removed path (the app only edits the newest)? Recommend yes, say so in the conversion output.
5. **SparkFun's 6 missing models:** show as warnings (recommended, they are upstream's) rather than a Problem state.
6. **Staging cleanup age:** one hour is a guess (A12-style); acceptable because the app is single-user.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | everything | yes | 2.49.0.windows.1 (below 2.49.1: warn per D-11) | none; the catalog shows the amber line, the commit path keeps 2.25 |
| git-lfs | not required (refused in staging) | yes (filters in the system config) | not queried | the filter overrides keep it from running |
| Git Credential Manager | must not be reached | yes (`credential.helper=manager` in the system config) | n/a | `credential.helper=` clears it (verified) |
| Network (github.com, api.github.com) | real Add/Update, owner-run D-22/D-24 | yes this session | n/a | offline = status unknown (D-12) |
| Python venv, PySide6 6.12, pytest + xdist + qt + timeout | tests | yes | Python 3.14 | n/a |
| KiCad 10 install | `needs_kicad` tests, stock nickname sets | yes on this machine | 10.0 | tests deselect with a printed count when absent |
| `taskkill.exe` | Cancel | yes (System32) | n/a | `Popen.kill()` (leaves children) |
| Free disk | Würth Add | yes (about 580 GB free of 1.8 TB) | n/a | D-15 refusal with numbers |

**Missing dependencies with no fallback:** none. **With fallback:** none needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x with pytest-xdist (`-n 8 --dist worksteal`), pytest-timeout (300 s, thread), pytest-qt (`qt_api = "pyside6"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-ra --strict-markers -n 8 --dist worksteal -m 'not slow'"`; markers `wurth`, `local_kicad`, `kicad_cli`, `corpus`, `needs_kicad`, `slow`) |
| Quick run command | `env/Scripts/python.exe -m pytest tests/<module>.py -n 0` (one module); whole quick run `env/Scripts/python.exe -m pytest` (about 90 s, skips `slow`) |
| Full suite command | `env/Scripts/python.exe -m pytest --full` (about 7 min); one slow module: `env/Scripts/python.exe -m pytest tests/<module>.py --full -n 0` |

### How the quick run still gets real catalog coverage
`tests/conftest.py` fails any non-slow test that starts `git init`/`git clone` (tripwire) and `gitfixtures` refuses builders without `slow`. So the **logic** is made git-free and the **flags** are pinned textually:
1. Pure functions (URL policy, manifest, validation on hand-built trees, collisions, status rows, plan/preview text, name-status parsing, progress regex, var detection, `${VAR}` rule) need no git.
2. `ops` take a `net` object; quick tests pass a `FakeNet` that writes a synthetic library tree into the destination and returns canned shas (a `make_third_party(root, id)` builder next to `tests/collectionfixtures.make_collection`). That runs the full add / update / remove / reinstall / rollback / cancel state machines in the quick run.
3. `gitnet` quick tests use `NetGit.starter` (recording) and assert the exact argv and env (hardened flags present, `--` before the URL, no `file` allowance in production, allow-list exact, no `subprocess` import).
4. `StreamedProcess` is tested with real **Python** child processes (progress split, stall + cancel, grandchild killed), which the tripwire ignores.
5. Real git (`file://` bare repo built with plumbing, see Code Examples) lives in a few `@pytest.mark.slow` tests that prove behaviour: persisted clone config, hooks do not run with a hostile global `core.hooksPath`, update after force-push, LFS refusal, dirty refusal, case-collision baseline, unreachable URL = unknown.
Because CI runs only the quick suite (`tests/README.md`), add the new slow modules to the "run before every publish" list in `tests/README.md`.

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAT-01 | rows with 4 states, licence, size, search | unit + qtbot | `pytest tests/test_catalog_status.py tests/test_catalog_dialog.py -n 0` | Wave 0 |
| CAT-02 | clone argv, progress, cancel kills tree, staging validated before register, licence shown first | unit + qtbot + slow | `pytest tests/test_gitnet.py tests/test_procs_stream.py tests/test_catalog_ops.py -n 0`; slow: `tests/test_catalog_ops_git.py --full -n 0` | Wave 0 |
| CAT-03 | URL policy; refusals non-KiCad / KiCad 5 / PCM / private | unit | `pytest tests/test_catalog_urls.py tests/test_catalog_validate.py -n 0` | Wave 0 |
| CAT-04 | update plan/apply/refusals, remove confirmation text | unit + slow | `pytest tests/test_catalog_ops.py -n 0`; slow `tests/test_catalog_ops_git.py` | Wave 0 |
| CAT-05 | manifest valid/invalid, plain clone (no `.gitmodules` written), scan sees `ThirdParty/<id>`, `.staging` skipped, description uses the id | unit | `pytest tests/test_catalog_manifest.py tests/test_scan_catalog.py tests/test_table_descriptions.py -n 0` | Wave 0 (+ existing `test_table_descriptions.py`) |
| CAT-06 | `extra_vars` offered through the confirm, rules for names, `${VAR}` model check | unit | `pytest tests/test_catalog_vars.py tests/test_kicad_config.py -n 0` | Wave 0 |
| CAT-07 | startup check: available/current/unknown, stops after first timeout, never blocks, no error line offline, menu text `(N updates)` | unit + qtbot | `pytest tests/test_catalog_status.py tests/test_main_window_catalog.py -n 0` | Wave 0 |
| CAT-08 | collisions with stock/catalog/Atomic_/Custom listed, libs start unchecked, no rename | unit | `pytest tests/test_catalog_validate.py tests/test_main_window_catalog.py -n 0` | Wave 0 |
| CAT-09 | curated list has Würth and SparkFun with licence, vars, size; others only if verified | unit | `pytest tests/test_catalog_curated.py -n 0` | Wave 0 |
| CAT-10 | KiCad's own variable names refused (`KICAD<digits>_*`, `*_3RD_PARTY`, `KISYS*`, `KIPRJMOD`) while `KICAD_4MS_LIBS`, `SPARKFUN_KICAD_LIBRARY`, `WE_3DMODEL_DIR` pass; ops never touch tables/`installed_packages.json`/`3rdparty` (sentinel hash) | unit | `pytest tests/test_catalog_vars.py tests/test_catalog_ops.py -n 0` | Wave 0 |
| CAT-11 | allow-list exact, flags pinned, only `procs` starts processes, commit-path modules do not import `catalog.gitnet`/`githubapi`, gitnet imports only `models`+`procs` | unit (AST) | `pytest tests/test_catalog_layering.py tests/test_gitnet.py tests/test_procs.py tests/test_gitops.py tests/test_layering.py -n 0` | Wave 0 (+ existing files edited) |
| CAT-12 | script plan/apply on a synthetic parent with two submodules, three pass checks, rollback tag, post-checks; carry-over of selection | unit + slow | `pytest tests/test_wurth_convert.py tests/test_catalog_carryover.py -n 0`; slow `--full` | Wave 0 |
| (todo) | migration dialog stops timers on close | qtbot | `pytest tests/test_migration_dialog.py -n 0` | exists, add test |
| (docs) | help page 4.7, shortcut `Ctrl+Shift+L`, CLAUDE.md entries | unit | `pytest tests/test_help_dialog.py tests/test_docs_split.py -n 0` | exists, edit |

Corpus-gated (deselected with a printed count unless `KICAD_TEST_CORPUS` names the collection): a `corpus` test that, when `<collection>/ThirdParty/WurthElektronik` exists, loads `catalog.json` and asserts `unresolved_models == []`; the existing `wurth` tests move to the new location.

### Sampling Rate
- **Per task commit:** the single new/edited test module with `-n 0`.
- **Per wave merge:** bare `env/Scripts/python.exe -m pytest` (quick run, about 90 s).
- **Phase gate:** `pytest --full` green (slow catalog modules included), plus `scripts/check_skip_budget.py` budget unchanged, plus the owner-run UAT list.

### Wave 0 Gaps
- [ ] `tests/test_procs_stream.py`: `StreamedProcess` with Python children (progress, stall, cancel tree, no console flag)
- [ ] `tests/test_gitnet.py`: argv/env/allow-list/URL checks with a recording starter
- [ ] `tests/test_catalog_layering.py`: AST rules (see CAT-11), generalising `test_importer_layering.py`'s `layering_errors`; also edit `tests/test_layering.py` (`table_generator` allowed set, new modules) and keep `tests/test_gitops.py::test_only_known_modules_import_subprocess` untouched
- [ ] `tests/test_catalog_urls.py`, `test_catalog_manifest.py`, `test_catalog_curated.py`, `test_catalog_validate.py`, `test_catalog_status.py`, `test_catalog_vars.py`, `test_scan_catalog.py`, `test_catalog_ops.py` (FakeNet), `test_catalog_dialog.py`, `test_main_window_catalog.py`
- [ ] `tests/catalogfixtures.py`: `make_third_party`, `FakeNet`, `commit_tree` (plumbing upstream, slow only), reusing `collectionfixtures.make_collection` and `recording_git`
- [ ] slow: `tests/test_catalog_ops_git.py`, `tests/test_wurth_convert.py` (+ add both to the pre-publish slow list in `tests/README.md`)
- [ ] edits to existing: `tests/test_help_dialog.py` (numbering, shortcuts), `tests/test_docs_split.py`, `tests/test_migration_dialog.py`, the Würth path tests listed above, `tests/test_corpus_audit.py` regex
Framework install: none.

### Owner-run UAT (cannot be automated)
Add Würth for real (clone time, disk use, licence tick, `WE_3DMODEL_DIR` confirm, scan with zero model warnings), SparkFun and 4ms Add and Remove, Alternate-KiCad-Library verification, startup "(N updates)" with a deliberately old commit, offline start, Cancel mid-clone with no `git.exe` left in the Task Manager and no staging folder, then the rehearsal and the live conversion.

## Security Domain

Security enforcement is on (ASVS level 1, block on high). Threat input: untrusted GitHub repositories and API answers, a hand-editable manifest, a subprocess boundary, a destructive conversion script.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no accounts; credentials are refused, not used) | helper cleared, prompts off, userinfo in URLs rejected |
| V3 Session Management | no | n/a |
| V4 Access Control | partly (what the app may write) | writes limited to `<root>/ThirdParty`, `catalog.json`, `.gitignore`, KiCad `kicad_common.json` through the confirm; containment check before delete |
| V5 Input Validation | yes | `urls.parse_github_url`, `valid_id`, `valid_branch`, `valid_var_name`, manifest validation, API JSON type checks and size cap, `--` and `=`-attached options |
| V6 Cryptography | no (TLS by git/urllib) | `http.sslVerify=true`; never disable verification; `GIT_SSL_NO_VERIFY` is stripped with every `GIT_*` |
| V7 Error Handling and Logging | yes | Issues instead of exceptions, no credential or token in any log line (strip userinfo), stderr excerpts limited |
| V8 Data Protection | yes (low) | no secrets stored; manifest holds URLs and hashes only |
| V9 Communication | yes | https only (git `protocol.allow` list, urllib fixed host), redirects only inside `api.github.com` for the API |
| V10 Malicious Code | yes | nothing from a clone is executed: hooks off, filters off, no scripts run, no import of cloned files |
| V12 Files and Resources | yes | staging folder, symlink/junction refusal, path containment, retry-safe deletion, size and free-space guards |
| V14 Configuration | yes | hardened git config set on the command line, global config ignored, clone config allow-list, minimum git |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hook execution at clone (user `core.hooksPath`/`init.templateDir`) | Elevation | verified: `-c core.hooksPath=`, `--template=`, `GIT_CONFIG_GLOBAL=<nul>` (T1) |
| CVE-2025-48384 (CR in submodule path, post-checkout via symlink) | Elevation | no recursion anywhere, no `submodule` subcommand, `submodule.recurse=false`, `--no-recurse-submodules`, `core.symlinks=false`, D-11 warning on git below 2.49.1 [CITED: github.blog git-security-vulnerabilities-announced-6; NVD lists 2.49.1 among the fixed versions] |
| CVE-2025-48385 (bundle-uri file write) | Tampering | `-c transfer.bundleURI=false` (the article's own workaround) [CITED: same article] |
| CVE-2025-48386 (wincred overflow) | Elevation | `credential.helper=` cleared; wincred is never invoked [CITED: same article] |
| Config-driven command execution from the clone's `.git/config` (`core.fsmonitor`, `core.sshCommand`, pager, `diff.external`, aliases) | Elevation | `.git/config` key allow-list parse before any git run; manifest URL, never `origin`; `-c` overrides for the known command keys |
| Discovery climbing into the collection repo | Tampering | explicit `GIT_DIR`/`GIT_WORK_TREE` (verified) + `.git` pre-check |
| Textconv/external diff from `.gitattributes` | Elevation | `diff-tree` plumbing only (no textconv), `-c diff.external=` |
| Credential prompt / GCM window / hang | DoS, Spoofing | helper cleared (verified: no window with GCM installed), `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, stdin devnull, low-speed timeout, Cancel |
| Protocol downgrade / SSRF | Spoofing | `protocol.allow=never` + `protocol.https.allow=always` (verified: `transport 'http' not allowed`), host exactly `github.com`, no port, no userinfo, no query |
| Option injection and path traversal via names | Tampering | regexes for id/branch/var, reserved device names (`CON`, `NUL`, `COM1`...), only dots rejected, `--`, containment `is_relative_to(ThirdParty)` |
| Symlink / junction escape | Tampering | `core.symlinks=false`, staging refusal of links, refuse to delete or rename a link, `rmtree` never follows |
| Git LFS pointers or downloads | DoS | `filter.lfs.*` neutralised, `GIT_LFS_SKIP_SMUDGE=1`, `.gitattributes` and pointer sniff, re-check on update |
| Oversized repo / disk exhaustion / compressible bombs | DoS | API size + 6x rule, runtime free-space-delta cap during clone (kill when exceeded), depth 1, single branch, no tags |
| Untrusted JSON (manifest, API) | Tampering | typed validation, size caps, unknown format = read-only, no `eval`/pickle |
| Network from the commit path | Elevation | layering test: no commit-path module imports `catalog.gitnet`/`githubapi`; `gitops` allow-list untouched and pinned |
| Cancel leaves processes or half clones | DoS | tree kill (verified), staging removal with retry, startup `clean_staging` |
| Update TOCTOU (remote moves between preview and apply) | Tampering | apply resets to the **previewed sha**, re-checks clean tree and LFS at apply |
| PCM tampering | Tampering | `valid_var_name` rejects KiCad's own names (`KICAD<digits>_*`, `*_3RD_PARTY`, `KISYS*`, `KIPRJMOD`); never write PCM files; sentinel-hash test |
| Destructive conversion script | Tampering | dry run default, bundle + tag + module data moved not deleted, refuses while KiCad runs, post-checks, way back printed |

## Sources

### Primary (HIGH confidence)
- This session, read in full or in the cited ranges: `kicad_lib_manager/gitops.py`, `procs.py`, `collection.py` (identity, source_of, create_collection), `library_scanner.py` (path vars, scan, rescan), `table_generator.py`, `scan_cache.py` (walker, fingerprint), `fsutil.py`, `kicad_process.py`, `widgets/background.py`, `widgets/help_dialog.py`, `main_window.py` (menu, switch refusal, scan flow, closeEvent, path-var flow), `widgets/migration_dialog.py` (timers, done, reap), `importer/verify.py`, `scripts/split/uri_diff.py`, `scripts/split/cutover_collection.py`, `tests/conftest.py`, `tests/gitfixtures.py`, `tests/test_gitops.py`, `tests/test_procs.py`, `tests/test_layering.py`, `tests/test_importer_layering.py`, `tests/corpusfixtures.py`, `pyproject.toml`, `tests/README.md`.
- Runs on git 2.49.0.windows.1 (scratch only, deleted afterwards): hardened ls-remote against github.com; local file:// clones; hook, template, LFS, long path, collision, shallow update, force-push, diff-tree, discovery and tree-kill experiments; real shallow clones and `scan_all` of two public libraries.
- GitHub REST API, unauthenticated, 2026-11-27: repo metadata for the five libraries and tree listings (no tokens).
- Owner's collection (read-only): `git status`, `git submodule status`, `.gitmodules`, file counts and size of the Würth tree, `kicad_common.json` variables.

### Secondary (MEDIUM confidence)
- [GitHub blog: Git security vulnerabilities announced](https://github.blog/open-source/git/git-security-vulnerabilities-announced-6/): the seven CVEs, upgrade to 2.50.1, workarounds `transfer.bundleURI=false`, no `--recurse-submodules` on untrusted repos, avoid wincred.
- [NVD CVE-2025-48384](https://nvd.nist.gov/vuln/detail/CVE-2025-48384) and the linked advisories (via search): fixed in 2.43.7, 2.44.4, 2.45.4, 2.46.4, 2.47.3, 2.48.2, 2.49.1 and 2.50.1; CR in config values with a submodule path.
- `.planning/research/` milestone files (SUMMARY, FEATURES, PITFALLS 6 and 15-22, ARCHITECTURE, STACK): used as the starting point; corrected above.

### Tertiary (LOW confidence)
- Training knowledge flagged `[ASSUMED]` in the Assumptions Log (A1, A2, A5, A6, A7).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, no new dependency; git behaviour verified by runs.
- Architecture: HIGH for module boundaries (constrained by existing tests I read), MEDIUM for `scan_source`/`remove_source` effort and the carry-over design.
- Pitfalls: HIGH for items marked verified; MEDIUM for Defender and rename-lock behaviour (not reproduced).
- Curated list: HIGH for SparkFun, 4ms, Espressif (failure), MEDIUM for Würth (layout from the owner's tree, no fresh clone), LOW for Alternate (not cloned).

**Research date:** 2026-11-27
**Valid until:** 2026-12-27 for git/GitHub facts (30 days); curated-library facts change whenever those repos change (re-check at execution time, especially SparkFun's missing models and the API size numbers)
