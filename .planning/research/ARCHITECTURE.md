# Architecture Patterns: v3.0 Public Library Manager

**Domain:** Desktop KiCad library manager (PySide6) turned from a personal in-repo tool into a public app working on an external library collection
**Researched:** 2026-11-22
**Scope:** only what the eight v3.0 phases need. Code facts were grepped from `kicad_lib_manager/` and `tests/` on branch `feature/part-importer` (HIGH). Design recommendations are MEDIUM unless marked. `.planning/codebase/ARCHITECTURE.md` is dated 2026-10-18 and predates the importer, the atomic check, the commit step, the scan cache and the migration; this file supersedes it for v3.0.

## Executive Summary

The code is closer to ready than the "app lives inside the repo" assumption suggests. The literal `REPO_ROOT` exists in exactly one module (`main_window.py:46`, 17 use sites). Every service already takes `repo_root: Path` as a parameter, and the importer already carries it in `RepoLayout.for_repo(repo_root)`. The scan cache is already keyed per resolved repository folder. So the "library root" is not a new type threaded through 100 files; it is one resolved `Path` that `MainWindow` owns instead of importing a constant.

The real coupling is not `REPO_ROOT` but **hard-coded folder names**: `"Custom"` appears as a literal in about 25 places (scanner, scan cache, atomic check/fixes, changes, importer layout, verify, migration, commit gate), `"WurthElektronik"` in two (`importer/verify.py`, `table_generator.library_description` via `rel_path.split("/")[0]`), and the scan `source` is "first path segment of `rel_path`". Recommendation: **keep `Custom/` as the fixed name of the own-library folder in every collection** (the owner's tables, KiCad projects and `CUSTOM_3DMODEL_DIR` depend on it) and centralise the names in one new Qt-free module, `collection.py`. Third-party libraries go under a new `ThirdParty/<id>/` folder; `source_of(rel_path)` returns `<id>` for those, so `WurthElektronik` stays a source name after it becomes catalog-managed.

The catalog should use **plain shallow clones plus a manifest (`catalog.json`) stored in the collection root**, not submodules. Submodule management (`submodule add/deinit/rm`, `.git/modules`, `.gitmodules` trust) is the hardest git surface to do safely on Windows, forces the collection to be a git repo, and turns every library update into a parent commit that collides with the commit step. Plain clones make add/update/remove a folder operation; the manifest records the URL, ref and the commit actually checked out, which restores reproducibility. This needs one new, separate network-capable git module because `gitops.py` deliberately has no remote subcommand (a security invariant, GIT-05).

Tables: **keep global tables as the one managed model**, with `${KICAD_LIB_GITHUB}`-relative URIs. Per-project tables break the Pin Atomic Libraries chooser setup and the "available in every project" goal; PCM-style packaging needs per-package metadata that arbitrary GitHub libraries do not have. Generate Tables then changes only in default Destination (newest KiCad config folder instead of the repo root), in removal handling for catalog libs, and in a generalised path-variable sync that also writes the variables third-party footprints hard-code (`WE_3DMODEL_DIR`, today set by hand in the owner's KiCad; no app code references it).

Two non-obvious blockers surfaced: (1) the saved-scan freshness check hashes the app's `.py` sources, which do not exist in a frozen app, so a frozen build would silently never reuse the saved scan (about 70 s startup with Wurth); (2) the scanner and scan-cache walkers descend into `.git` below the top level, which is free for a submodule (`.git` is a file) but expensive for plain clones (`.git` is a directory of objects).

## Recommended Architecture

### Collection layout (new)

```
<library root>/                  KICAD_LIB_GITHUB points here; a folder, git repo optional
  catalog.json                   manifest of catalog-managed libraries (versioned in the collection repo if there is one)
  Custom/                        own libraries; its own git repo (init'd by "New collection")
    Symbols/Atomic_*.kicad_sym
    Footprints/Atomic_Footprints.pretty
    3DModels/<MPN>.<ext>
    README.md
  ThirdParty/                    catalog clones, one folder per catalog id, gitignored by the collection repo
    WurthElektronik/             plain shallow clone (own .git directory)
    <id>/...
    .staging/                    in-progress clones, never scanned, deleted on failure
  .gitignore                     ThirdParty/
```

The owner's private collection keeps today's shape (parent repo with `Custom` as a submodule) so the parent-gitlink bump stays possible. A new user's collection is a plain folder whose `Custom/` is its own repo, so there is no parent repo and no bump (see Commit step below).

### Components (new vs modified)

| Component | Status | Responsibility | Qt? |
|-----------|--------|----------------|-----|
| `kicad_lib_manager/collection.py` | **NEW** | Folder-name constants (`OWN_DIR="Custom"`, `THIRD_PARTY_DIR="ThirdParty"`, `MANIFEST_NAME`), `resolve_library_root()`, `inspect_collection(path)`, `create_collection(path)`, `source_of(rel_path)`, `CollectionInfo` (kind: complete / missing Custom / not a collection; has_parent_repo) | no |
| `kicad_lib_manager/catalog/manifest.py` | **NEW** | `CatalogEntry`, load/validate/save `catalog.json` (untrusted-JSON rules like `scan_cache`, atomic write via `fsutil`) | no |
| `kicad_lib_manager/catalog/curated.py` | **NEW** | Bundled curated list as a Python module (frozen-safe, no data file) | no |
| `kicad_lib_manager/catalog/gitnet.py` | **NEW** | The only module allowed network git (`clone`, `fetch`, `reset`, `ls-remote`, `rev-parse`, `status`); URL validation; reuses gitops' process launcher | no |
| `kicad_lib_manager/catalog/ops.py` | **NEW** | `plan_add/apply_add`, `plan_update/apply_update`, `plan_remove/apply_remove` returning `Issue` lists and a preview plan; staging clone, validation, 3D variable detection | no |
| `kicad_lib_manager/widgets/catalog_dialog.py` | **NEW** | Curated + installed list, Add by URL, Update, Remove, preview, progress; runs ops on `TaskWorker` | yes |
| `kicad_lib_manager/widgets/library_root_dialog.py` | **NEW** | First-run / "Choose library folder..." / "New collection..." | yes |
| `kicad_lib_manager/_build_info.py` | **NEW** | `VERSION` + build stamp written by the build script; used when frozen | no |
| `main_window.py` | **MODIFIED** | `REPO_ROOT` constant becomes `self._root` (constructor argument), `_set_root()` switch, new actions, menu regroup | yes |
| `settings.py` | **MODIFIED** | `load/save_library_root()`; `scan_cache_file`/`migration_draft_file` unchanged (already keyed by root) | yes |
| `importer/layout.py` | **MODIFIED** | `RepoLayout` gains `third_party_dir`, `manifest_path` (built only by `for_repo`, so safe) | no |
| `library_scanner.py` | **MODIFIED** | `_determine_source` -> `collection.source_of`; prune `.git` at any depth; `scan_source(root, source)`; `sync_kicad_path_vars(extra_vars=...)`; `"Custom"` literals -> constants | no |
| `scan_cache.py` | **MODIFIED** | `_walk` prunes `.git` anywhere; frozen-aware `_code_signature`; literals -> constants | no |
| `table_generator.py` | **MODIFIED** | `library_description` uses `source_of`; `remove_library_entries(dest, rel_prefix)`; default dest helper | no |
| `kicad_setup.py` | **MODIFIED** | `configured_library_folder(config_base)` (reuses the `checkout_mismatch` read); no semantic change to D-26/Pin | no |
| `gitops.py` | **MODIFIED (small)** | extract a public `launch()` so `gitnet` shares the one process-start point; allow-list stays offline-only | no |
| `importer/commit_step.py` | **MODIFIED** | parent mode `none / gitlink`; parent option hidden (not warned) when no parent applies | no |
| `importer/verify.py`, `atomic_check.py`, `atomic_fixes.py`, `changes.py`, `importer/migration/*`, `importer/commit_gate.py` | **MODIFIED (mechanical)** | `"Custom"` / `"WurthElektronik"` literals -> `collection` constants; `symbol_search_dirs` searches every `ThirdParty/*` instead of Wurth only | no |
| `widgets/help_dialog.py` | **MODIFIED** | text only: collection, catalog, global-table model (it is embedded HTML, so freezing needs no data files) | yes |

### Component boundaries and layering

`test_layering.py` pins foundation modules to Qt-free and to an `ALLOWED` import map. New modules join the map: `collection` imports nothing from the package except `models`; `catalog.*` imports `fsutil`, `gitops` (launcher only), `kicad_files`, `library_scanner` (for validation scan), `collection`, `models`. `library_scanner` imports `collection` (one small leaf, add to its allowed set). The importer package may import `collection`. Nothing below `main_window` imports `main_window`.

### Data flow

```
start
 -> collection.resolve_library_root(cli/env override, saved choice, KiCad KICAD_LIB_GITHUB)
 -> inspect_collection(root)            (not a collection -> library_root_dialog)
 -> MainWindow(root): scan cache keyed by resolved root -> ScanWorker(root)
 -> scan: Custom/** + ThirdParty/<id>/** (.git pruned) -> source = source_of(rel_path)
 -> tree grouped by source -> Generate -> write_tables(dest = KiCad config folder)
 -> sync_kicad_path_vars(root, extra_vars = union of catalog entry vars)   [confirm]
catalog Add
 -> plan_add(url): validate URL -> staging clone -> scan staging for v6+ libs -> detect ${VAR} model paths
    -> preview (libraries found, licence file, variables, disk size)
 -> apply_add: rename staging -> ThirdParty/<id>, manifest entry (url, ref, commit), scan_source(id)
 -> add-only table entries (existing add_library_entries) + path-var confirm
```

## Where `REPO_ROOT` and repo-relative assumptions live (grep results)

**Literal `REPO_ROOT` (all in `main_window.py`):**

| Line | Use | v3.0 change |
|------|-----|-------------|
| 46 | `REPO_ROOT = Path(__file__).parent.parent.resolve()` | delete; `MainWindow.__init__(library_root)`; legacy fallback (code inside a collection) only until the split |
| 487 | Destination box falls back to `str(REPO_ROOT)` | fall back to newest KiCad config folder (phase 5), the root only if none |
| 583, 1262 | `migration_reason(RepoLayout.for_repo(REPO_ROOT))` | `self._root` |
| 630-631, 673-674 | `ScanWorker` / `LibraryRescanWorker` + `scan_cache_file(REPO_ROOT)` | `self._root` |
| 1023, 1047 | `repo_root=REPO_ROOT` post-install table update | `self._root` |
| 1181-1182, 1225 | atomic check dialog / import core layout | `self._root` |
| 1266 | `MigrationDialog(REPO_ROOT, ...)` | `self._root` |
| 1372, 1380 | D-26 `checkout_mismatch(REPO_ROOT, ...)` | `self._root` |
| 1501, 1586 | commit / pin paths | `self._root` |

Tests monkeypatch `main_window.REPO_ROOT` in 5 harness files (`test_main_window.py:78`, `test_main_window_chooser.py:102`, `test_main_window_import.py:97`, `test_main_window_migration.py:152`, `test_checkout_warning.py:84`). Replace with the constructor argument; this is the main test churn of phase 2.

**Hard-coded folder names (the real coupling):**

| File | Sites | Note |
|------|-------|------|
| `library_scanner.py` | 27 `CUSTOM_MODEL_PREFIX`, 274 `{repo}/Custom/3DModels`, 557 `_custom_model_names`, 600 `source == "Custom"`, 914 | 274 also defines the `CUSTOM_3DMODEL_DIR` value written to KiCad |
| `library_scanner.py:410` | `_determine_source` = first path segment | replace by `source_of` |
| `scan_cache.py` | 43-44 prefixes, 174 `_custom_git_state(root/"Custom")` | fingerprint covers `Custom` HEAD only |
| `atomic_check.py` | 433, 528, 665 | `rel_path.startswith("Custom/")`, `lib.source == "Custom"` |
| `atomic_fixes.py` | 27-29 | `_CUSTOM`, `Custom/Footprints`, `Custom/3DModels` |
| `changes.py:25`, `importer/layout.py:24`, `importer/incoming.py:38`, `importer/commit_gate.py:541`, `importer/commit_plan.py:43`, `importer/migration/gate.py:25,80,215`, `importer/migration/inventory.py` | `"Custom"` / `"Custom/..."` | `RepoLayout.custom_dir` already centralises some |
| `importer/verify.py` | 27 `_WURTH_PREFIX`, 238 `repo_root/"WurthElektronik"`, 248 recursive walk only for Wurth | generalise to all `ThirdParty/*` |
| `table_generator.py:51-60` | `library_description`: `source = rel_path.split("/",1)[0]` | would print "ThirdParty: ..."; use `source_of` |
| `main_window.py:1324` | `lib.source != "Custom"` | constant |
| `settings.py:48-59` | `scan_cache_file` / `migration_draft_file` keyed by `sha256(normcase(resolve(root)))[:16]` | already root-aware; no change |
| `gitops.find_git(repo_root)` | refuses a git found inside the repo | fine for a collection root |
| `SKIP_DIRS` in `library_scanner.py:30` | `env`, `tests`, `downloaded_examples`, ... | exists for code-in-repo; harmless after split, prune later |

**Not coupled (good):** the scan result model, `fsutil`, `kicad_files`, `sexpr`, table merge (managed marker is the variable, not a folder), `kicad_process`, widgets. The User Guide is embedded HTML in `help_dialog.py`; no resource files are read relative to `__file__` anywhere except `scan_cache._code_signature` and the `REPO_ROOT` line.

## The library-root abstraction

**Decision:** do not introduce a `LibraryRoot` object that every function takes. Services keep `repo_root: Path`; `RepoLayout` stays the importer's carrier and gains two fields. What is new is (a) one resolver, (b) one constants module, (c) `MainWindow` owning the root.

```python
# kicad_lib_manager/collection.py  (Qt-free, imports models only)
OWN_DIR = "Custom"
THIRD_PARTY_DIR = "ThirdParty"
MANIFEST_NAME = "catalog.json"

def source_of(rel_path: str) -> str:
    parts = rel_path.split("/")
    if len(parts) >= 3 and parts[0] == THIRD_PARTY_DIR:
        return parts[1]            # ThirdParty/WurthElektronik/... -> "WurthElektronik"
    return parts[0] if parts else "Unknown"   # Custom/..., legacy WurthElektronik/KiCad-Library/...

def resolve_library_root(*, override, saved, kicad_configured) -> Path | None: ...
def inspect_collection(path: Path) -> CollectionInfo: ...
def create_collection(path: Path) -> list[Issue]: ...   # Custom skeleton + git init inside Custom/, catalog.json, .gitignore
```

`source_of` handling both layouts is what makes the Wurth conversion (phase 4) and the split (phase 3) independent: a legacy top-level `WurthElektronik/KiCad-Library` submodule and a new `ThirdParty/WurthElektronik` clone both yield source `WurthElektronik`, so tree grouping, per-source Skip, selection and the D-23-style source names do not change.

**Resolution order (recommended):** explicit override (`--library-root` CLI flag or `KICAD_LIBMGR_ROOT` env; dev and UAT only) > remembered choice from "Choose library folder..." > folder named by KiCad's `KICAD_LIB_GITHUB` > prompt. This differs slightly from the milestone text ("default is KICAD_LIB_GITHUB, else remembered choice"): if the variable always wins, the menu action has no effect whenever KiCad has the variable set. Treat the saved value as an explicit act and keep a "Use KiCad's folder" reset. The owner should confirm (Open Question 1). Until the split, a fourth candidate (the folder above the package, if it has `Custom/`) keeps the in-repo run working; delete it in phase 3.

**Switching at runtime:** `MainWindow._set_root(path)` refuses while a scan, import, migration or catalog dialog is open, then clears the tree, repopulates the Destination box, and calls `_start_scan(reuse_cache=True)`. Nothing else caches the root: the import and migration dialogs get it at construction, the scan cache and migration draft are keyed by it.

### Flow through each subsystem

| Subsystem | Change |
|-----------|--------|
| **Scanner** | Scans `Custom/**` and `ThirdParty/**` under the root. `source_of` replaces `_determine_source`. `_collect_files` and `find_footprint_libs` use `rglob`, so they descend `ThirdParty/<id>/.git/` (thousands of object directories for a plain clone; a submodule's `.git` was a file). Replace with an `os.walk` that prunes any directory named `.git` at any depth. `scan_cache._walk` has the same flaw (`skip_top` only skips `SKIP_DIRS` at the top level). Add `scan_source(root, source)` so Add/Update scans one source, not the whole tree (the full scan's 3D check is about 63 of 70 s for Wurth). |
| **Importer** | Unchanged logic: it writes only into `Custom/`. `RepoLayout.for_repo(root)` gains `third_party_dir`. `verify.symbol_search_dirs` searches every `ThirdParty/*` for "same part name elsewhere". Imports into third-party libs stay out of scope. |
| **Tables** | Managed marker stays `${KICAD_LIB_GITHUB}/` (see Catalog and Table model). URIs for catalog libs become `${KICAD_LIB_GITHUB}/ThirdParty/<id>/<rel>`. The owner's existing `WurthElektronik/KiCad-Library/...` entries are rewritten by one Generate after the conversion; the merge drops managed entries not in the selection and adds the new ones. |
| **Commit step** | See next subsection. |
| **Scan cache key** | Already per resolved root (`settings.scan_cache_file`), so switching roots gives a separate saved scan, never a stale mix. Fingerprint additions: stat `catalog.json`; `_custom_git_state` stays Custom-only (clone updates change file mtimes, which `_walk` already catches). Frozen builds: `_code_signature()` must not read `.py` files (see Installer). |
| **D-26 guard** | Meaning is unchanged but its trigger shifts: with the default resolution order the app root equals `KICAD_LIB_GITHUB` automatically; a mismatch now arises only after an explicit "Choose library folder..." or an override. That is exactly the dev/UAT case, so keep it as is (amber warn on Generate/Install, refuse on Migration Run and Pin). `kicad_setup.configured_library_folder()` is the one new helper. The worktree refusal `(root / ".git").is_file()` stays valid for a collection that is itself a worktree; the original reason (app code living in a dev worktree of the library repo) disappears with the split. |
| **Pin Atomic Libraries** | No code change. It reads the Destination tables and writes KiCad's global chooser files. It depends on global tables (see Table model). |

### Commit step when the collection is the parent

`commit_step._custom_unavailable` requires `Custom` to be its own git work tree (`show_toplevel(custom) == custom`, to avoid ever committing into a parent by accident, T-06-07). Therefore the recommended new-collection shape is **`git init` inside `Custom/`**, not at the root. Consequences:

| Collection shape | Custom commit | Parent step |
|------------------|---------------|-------------|
| Owner's private repo (parent repo, `Custom` submodule) | unchanged | unchanged, optional checkbox (`bump_parent` already exists) |
| New collection (plain root folder, `Custom/` is its own repo) | works | not applicable: hide the checkbox |
| Root is a git repo and `Custom` is an ordinary tracked folder | refused today ("Custom is not a git work tree") | out of scope for v3.0; document |

Change: `_parent_state` today returns `parent_ok=False` with reason "no parent git repository", which the panel shows as a refusal reason. Replace by a `parent_mode` probe: `"gitlink"` when the root is a git work tree and HEAD (or the index) holds mode 160000 for `Custom`; else `"none"`. With `none`, the panel shows no parent option and no warning. The existing `bump_parent: bool` plumbing in `commit_step.py:498-896` needs no other change.

## Catalog design

### Storage decision: plain shallow clones + manifest

| Criterion | Plain clones + `catalog.json` (recommended) | Submodules of the collection repo |
|-----------|---------------------------------------------|------------------------------------|
| Add | `git clone --depth 1` into `.staging`, validate, rename | `git submodule add` (touches `.gitmodules`, index, `.git/modules`); needs the collection to be a repo |
| Update | `fetch --depth 1` then `reset --hard FETCH_HEAD` on a clean tree | `submodule update --remote` plus a parent commit per update |
| Remove | delete folder (clear read-only bits on `.git` objects, Windows) and drop manifest entry | `submodule deinit`, `git rm`, delete `.git/modules/<x>`: multi-step, easy to leave residue |
| Reproducibility | manifest records `url`, `ref`, `commit`; "Restore catalog" re-clones the recorded commit | gitlink in parent history (best), but only for users with a parent repo |
| Interaction with commit step | none (clones are gitignored; commit step stays Custom-only) | parent index dirties on every add/update; collides with the optional parent bump and `busy_operation` checks |
| Non-git collections (new user) | works | does not work |
| Offline use | fully offline after first clone; network only on explicit Add/Update | same once checked out; `submodule update` needs network if anything is missing |
| Disk | shallow clone, no history | full history unless configured shallow |
| Security surface | one URL, no `.gitmodules` recursion, `--no-recurse-submodules` | nested `.gitmodules` URLs and `file`/`ext` transports need hardening |
| Commit history noise | none | one parent commit per library change |

The only thing submodules do better is bit-exact reproducibility, which the manifest `commit` field mostly recovers. The owner's existing Wurth submodule is converted once (phase 4, interactive, from the main checkout): `git submodule deinit -f` and `git rm WurthElektronik/KiCad-Library` in the collection repo, then Catalog Add.

### Data model: manifest in the collection, not in settings

`catalog.json` lives in the collection root, so it travels with the collection (second machine: clone the collection, open the app, "N catalog libraries are missing: install"). QSettings holds only machine-local state (root path, UI state).

```json
{
  "version": 1,
  "libraries": [
    {
      "id": "WurthElektronik",
      "name": "Wurth Elektronik KiCad Library",
      "url": "https://github.com/WurthElektronik/KiCad-Library.git",
      "ref": "main",
      "commit": "ddb5a9ea...",
      "origin": "curated",
      "added": "2026-11-30",
      "vars": { "WE_3DMODEL_DIR": "3dmodels" },
      "license": "License_Terms_WE_KiCad_library.pdf"
    }
  ]
}
```

- `id` is a validated slug (`[A-Za-z0-9][A-Za-z0-9._-]*`, no case-twin of another id); it is the folder name and the scan `source`.
- `vars` maps a KiCad path variable to a folder **relative to the clone**. It is the only place the app learns about variables third-party footprints hard-code.
- Validate on read like `scan_cache`: wrong type, unknown key, duplicate id, `..` or absolute path in `vars` gives a plain note and ignores the file (never executes anything from it). The manifest is trusted no more than a downloaded package.
- The curated list ships as `catalog/curated.py` (same shape plus a one-line description), versioned with the app; no remote fetch of a curated list in v3.0.

### Table entries and path variables

- **Library URIs:** keep one variable, `${KICAD_LIB_GITHUB}/ThirdParty/<id>/<rel>`. The existing ownership rule (managed = URI contains `${KICAD_LIB_GITHUB}/`), `add_library_entries`, `_merge_table` and D-26 all key on it. A per-library variable would add a variable to `kicad_common.json` per Add, break marker-based ownership, and gain nothing.
- **3D models third-party libs expect:** Wurth footprints contain 7612 `(model "${WE_3DMODEL_DIR}/<lib>.3dshapes/<file>.step")` and nothing else (verified); the owner's `kicad_common.json` holds `WE_3DMODEL_DIR` set by hand. Generalise `library_scanner.sync_kicad_path_vars` from the fixed pair to `desired = {KICAD_LIB_GITHUB, CUSTOM_3DMODEL_DIR, **catalog vars resolved to absolute paths}`. The confirm, backup, KiCad-running, re-read and refusal logic is reused unchanged (it already shows `VAR: old -> new`).
- **Detecting `vars` for Add by URL:** after the staging clone, collect every `${NAME}` prefix in `(model ...)` paths, drop built-ins (`KICAD*_3DMODEL_DIR`, `KIPRJMOD`, `CUSTOM_3DMODEL_DIR`, `KICAD_USER_3DMODEL_DIR`). For each remaining name, take the remainder of one model path (`X.3dshapes/file.step`) and search the clone for a folder `D` where `D/<remainder>` exists; `vars[NAME] = relpath(D)`. This is verifiable, not guessed. If none is found, Add proceeds with a visible "3D models will not resolve" warning. Absolute or `${KIPRJMOD}` model paths are reported as non-portable, never rewritten (editing upstream files is out of scope).
- **Collisions:** two catalog entries wanting the same variable name with different folders, or a variable already set in KiCad to a different path, refuse the Add and say why. KiCad reads variables at start, so the result view says "restart KiCad".
- **Scanner's 3D rule:** `_check_model_files` already treats non-Custom sources leniently (`scan.model_absolute` warning only for non-`${}` paths). Add a check that a catalog `${VAR}` model path resolves through the manifest `vars` (optional; MEDIUM value).

### Operations, safety and git

- **Add:** validate URL (see below) -> `git clone --depth 1 --single-branch` into `ThirdParty/.staging/<id>` -> scan staging for `*.kicad_sym` and `*.pretty` (KiCad 5 `.lib` repos and PCM-zip-only repos yield none: report "no KiCad v6+ libraries found" and delete staging) -> detect licence file and `vars` -> **preview** (libraries found, licence path, variables to set, size) -> on confirm rename to `ThirdParty/<id>`, write manifest atomically, `scan_source(id)`, add-only table entries via `add_library_entries`, path-var confirm. A failed or cancelled clone never leaves a folder the scanner can see.
- **Update:** refuse (offer discard) if `git status --porcelain` is not clean; `fetch --depth 1 origin <ref>`, show old -> new short commit, `reset --hard FETCH_HEAD` (not `merge --ff-only`: with `--depth 1` the new tip need not descend from the old shallow tip). Never auto-update at startup; "Check for updates" is an explicit action using `ls-remote`.
- **Remove:** preview lists the folder, the table entries that will go (managed URIs under `ThirdParty/<id>/`), and the variables left in KiCad (reported, not unset). Delete with a read-only-clearing `rmtree` (git object files are read-only on Windows). Remove table entries in the same step (dangling entries are visible errors in KiCad), through a new `table_generator.remove_library_entries`.
- **`gitnet.py` rules (MEDIUM, needs a threat-model plan like 06-SECURITY):** `https://github.com/<owner>/<repo>[.git]` only by default (Add by URL spec says GitHub); reject credentials in the URL, non-https schemes, scp-like syntax, `ext::`, `file:`, leading `-`; always pass `--` before the URL; `-c protocol.allow=never -c protocol.https.allow=always`; no submodule recursion; `GIT_TERMINAL_PROMPT=0` (already in `gitops._env`); `-c core.longpaths=true` (Wurth paths are long on Windows). The Windows-only `core.symlinks` default (false) already protects against symlink escape; keep it explicit. Tests use a local bare repo through an injected `allow_file=True` policy, never by loosening production.
- **Keep `gitops.ALLOWED_SUBCOMMANDS` offline.** `test_layering.py` documents `gitops` as "the only module that starts git". Preserve that by extracting `gitops.launch()` and having `gitnet` call it with its own allow-list; extend the layering test so commit-path modules may not import `gitnet`.
- **Threading:** run ops on the existing generic `TaskWorker` (`widgets/import_dialog.py:343`; move it to a neutral module when the catalog dialog needs it) with progress and a cancel that terminates the git subprocess.
- **LFS (LOW-MEDIUM):** a library that stores STEP files in Git LFS clones as pointer files without `git lfs`. Detect pointer files in the staging validation (small text starting `version https://git-lfs`) and warn.

### Wurth as the first catalog entry

Curated entry `WurthElektronik` with `vars = {"WE_3DMODEL_DIR": "3dmodels"}`. The `wurth` pytest marker corpus (tests) then needs a manual clone or the catalog; see Repo split.

## Table model: recommendation

| Option | Fit | Verdict |
|--------|-----|---------|
| **Global tables** (`sym-lib-table`, `fp-lib-table` in the newest KiCad config folder), `${KICAD_LIB_GITHUB}` URIs | Libraries available in every project; the atomic/catalog goal; Pin Atomic Libraries pins nicknames in global chooser config; managed marker, merge, backups, D-26 all built on it; already the owner's real flow | **Recommended** |
| Per-project tables (`${KIPRJMOD}` or `${KICAD_LIB_GITHUB}` in the project folder) | Same two files, same writer (`write_tables(dest)` works on any folder). Portable only with `${KIPRJMOD}`-relative paths, which a collection outside the project is not. Must be re-generated per project, chooser pins do not follow. | Support as an advanced Destination, not as the model |
| KiCad PCM style (`${KICAD<n>_3RD_PARTY}`, `installed_packages.json`, `PCM_` prefix) | Needs per-package `metadata.json` and repository packaging; arbitrary GitHub libs have neither; PCM owns its own table entries. Official PCM entry format was not retrievable from KiCad docs in this pass (LOW confidence on details). | Reject for v3.0 |

How Generate Tables changes:

1. **Destination default** becomes the newest KiCad config folder (`find_kicad_config_dir()` already exists and sorts versions numerically), not `str(REPO_ROOT)` (`main_window.py:487`). The repo root stays offered only when no KiCad config exists. The "Destination" label becomes "KiCad tables folder"; a project folder remains choosable (advanced).
2. **Removal:** libraries that disappear (catalog Remove) have their managed entries removed with a preview; today a deselected library is removed by the merge, which already works, so Remove can call `remove_library_entries` or simply rescan and Generate.
3. **Path variables:** `sync_kicad_path_vars` writes `KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR` and catalog `vars`, each with the existing `VAR: old -> new` confirm.
4. **No change** to the managed-marker rule, add-only post-install updates, backup numbering, or the restore dialog.

KiCad 10's nested library tables remain out of scope (PROJECT.md).

## Repo split

Phase 3 is mostly git operations and documentation; the only code changes are removing the legacy-root fallback and repointing the test guard.

| Item | Goes to | Notes |
|------|---------|-------|
| `kicad_lib_manager/`, `kicad_lib_manager.py`, `pyproject.toml`, `requirements*.txt`, `.gitattributes` | **tool repo** (public) | add `LICENSE`, `README` (install, first run), CI |
| `tests/` (143 files, fixtures 85 K) | tool repo | passes without the collection; see below |
| `.planning/` (11 MB) | tool repo | owner's decision; scrub personal paths if wanted |
| `downloaded_examples/ul_CSD85301Q2.zip` | tool repo **only if licence allows**, else replace by a synthetic builder in `tests/zipfixtures.py` | used by `ul_package` fixture, `test_edits`, `test_roundtrip_corpus` (SHA-pinned); the other vendor samples are already untracked |
| `reports/`, `research_notes/` | tool repo (design notes) or drop | check content before publishing |
| `CLAUDE.md` | **split**: tool repo keeps architecture, conventions, GUI behaviour, Python env, running; collection repo gets library naming, atomic rule, path variables, "Importing Parts" manual route, git workflow, submodule notes | `tests/test_docs_atomic.py` reads CLAUDE.md and `research/LIBRARY-NAMING.md`; repoint it at the tool-repo copy |
| `Custom/` submodule, `WurthElektronik/KiCad-Library` submodule, `.gitmodules`, `Custom/MIGRATION-ATOMIC.md` | **private collection** | Wurth leaves the collection repo in phase 4 |
| `catalog.json`, `.gitignore` for `ThirdParty/` | private collection | created in phase 4 |

**History:** recommended direction is the reverse of the obvious one. Keep the existing private repo as the collection (a final "remove app code" commit; its history stays private) and create the public tool repo from a filtered copy (`git filter-repo --path kicad_lib_manager --path tests --path pyproject.toml ...`). Before publishing, check `git log --all -- downloaded_examples` and the largest blobs for licence-restricted vendor files and personal data in `.planning`. Do this interactively (milestone text already says so); the licence is chosen here.

**Dev workflow after the split:**

- Tool repo clone with worktrees as today. The app is run with `--library-root <scratch collection>` or `KICAD_LIBMGR_ROOT`; never against the owner's live collection during development. D-26 then correctly shows the amber "KiCad reads another folder" warning, which is the safety net.
- A scratch collection is produced by `collection.create_collection()` plus the existing synthetic builders (`tests/customfixtures.write_synthetic_custom`, `atomic_custom`); promote the opt-in `KICAD_ATOMIC_UAT_DIR` builder in `tests/test_atomic_uat.py:290` to a small dev script that no longer reads a live `Custom/`.
- The owner's real imports, Generate, Pin, migration and commits run from the installed app pointed at the main collection checkout, exactly like D-26 prescribes today.

**Tests without the private collection:**

- Already tolerant: `test_edits._symbol_inputs` and `test_kicad_files._custom_files` parametrise `custom-absent` and skip; the `wurth` marker tests skip when the submodule is absent; `tests/README.md` states the suite passes whatever `Custom/` holds.
- Needs change: `conftest._live_custom_untouched` guards `REPO_ROOT/"Custom"` (no-op when absent, but remove it with the split); `test_edits.py:28` references a v1 library file (`Connector_USB_GCT.kicad_sym`) that no longer exists after the migration (dead reference); `test_atomic_uat.py:290` reads the live `Custom/`.
- Introduce one opt-in env var, `KICAD_TEST_CORPUS` (a folder of real KiCad libs, for example a catalog Wurth clone or KiCad's stock libraries), used by `test_roundtrip_corpus.py` and the `wurth` stress test; unset means skip with a stated reason (matches the `tests/README.md` skip table).
- New synthetic fixtures needed: `synthetic_collection` (root + `Custom/` + `ThirdParty/<id>` + `catalog.json`) and a local bare "GitHub" repo for catalog tests. `tests/gitfixtures.make_superproject` already builds bare remotes, a parent and a Custom submodule and is the template.
- CI on the public repo: Windows runner, `pytest -n auto -m "not slow"`; `kicad_cli` tests skip with a reason when KiCad 10 is absent.

**Phase 1 note (test speed-up) relevant to later phases:** pytest-xdist runs one session guard per worker (cheap). The shared git fixture idea (build a superproject once, copy per test) is unsafe if copied naively: submodule config holds absolute remote URLs and `core.worktree`; copy the whole fixture root including its bare remotes and rewrite the two URLs with `git config`, or keep building per test for the few commit-step tests. Real kicad-cli tests and app-data backups (`fsutil.default_backup_dir()` under `%LOCALAPPDATA%`) must use per-test temp roots under xdist; the engine already takes `backup_root`.

## Installer and frozen-app paths

| Concern | Finding | Action |
|---------|---------|--------|
| Resource files | None. User Guide is embedded HTML (`help_dialog.py`), no icons or data files read relative to `__file__` | no bundle data needed; the curated list is a `.py` module for the same reason |
| `Path(__file__)` | only `main_window.py:46` (deleted) and `scan_cache.py:264` | see next row |
| Saved-scan freshness | `scan_cache._code_signature()` parses and hashes the `.py` sources under the package; in a frozen app they are absent, the function returns `""`, and `payload["code"] != code or not code` forces a full scan every start (`scan_cache.py:544, 625`) | when `getattr(sys, "frozen", False)`, return `VERSION + build stamp` from `_build_info.py` |
| Settings | `QSettings` IniFormat UserScope under `%APPDATA%/KiCadExtLibManager/settings.ini`; scan cache and migration draft beside it; backups under `%LOCALAPPDATA%/KiCadExtLibManager/backups` | all outside the install folder, so a read-only `Program Files` install is fine; do not move them |
| Git | `gitops.find_git` uses `shutil.which("git")` and refuses a git inside the repo/collection | installer checks Git is present (milestone); the app already reports `git.not_found` |
| Qt modules | code imports only `QtCore`, `QtGui`, `QtWidgets` | freeze with PySide6 Essentials; the dev venv also has webengine and pdf addons that would bloat a naive freeze |
| Entry | `kicad_lib_manager.py` | add `--library-root`; set `sys.frozen`-safe application name before `QSettings` use (already constant) |
| Freeze tool | PyInstaller supports Python 3.14 since 6.15.0 (changelog, MEDIUM-HIGH); Nuitka lists 3.14 but PySide6 6.12 on 3.14 was not confirmed (LOW) | do a throwaway freeze spike early (during phase 2 or 7), not first in phase 8 |
| Version string | none exists | `_build_info.py`, shown in About, written by the build script |

## Patterns to Follow

### Pattern 1: Plan, preview, apply for catalog operations
**What:** every catalog operation returns a pure plan (what folder, which entries, which variables) first; apply runs only after confirmation and returns `list[Issue]`.
**Why:** matches the importer/migration/commit-step contracts and the PROJECT.md safety rule ("no write without a preview").
```python
plan = catalog.ops.plan_add(root, url)          # clones to .staging, validates, no registration
if plan.ok and user_confirms(plan): issues = catalog.ops.apply_add(root, plan)
```

### Pattern 2: One source-of-truth module for folder names
**What:** `collection.py` constants and `source_of`; a layering/AST test fails if a service contains the literal `"Custom"` outside `collection.py` and the documented exceptions.
**Why:** the 25-site literal coupling is the main thing that would make a second layout (or a rename) expensive.

### Pattern 3: Validate before register
**What:** a catalog clone is scanned and judged in `.staging`; the manifest and `ThirdParty/<id>` exist only for a library that passed.
**Why:** a half-valid clone must never reach the scanner, the tables or `kicad_common.json`.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Network git through `gitops`
**What:** adding `clone`/`fetch` to `ALLOWED_SUBCOMMANDS`.
**Why bad:** the allow-list is the proof that the commit path can never touch a remote (GIT-05, 26/26 threats closed).
**Instead:** `catalog/gitnet.py` with its own allow-list and URL policy, sharing only the process launcher.

### Anti-Pattern 2: A variable per catalog library for library URIs
**What:** `${LIB_<ID>}/...` in tables.
**Why bad:** breaks marker-based ownership, multiplies `kicad_common.json` writes, and a missed write leaves the library unresolvable.
**Instead:** `${KICAD_LIB_GITHUB}/ThirdParty/<id>/...`; per-library variables only for the 3D variable upstream footprints hard-code.

### Anti-Pattern 3: Renaming `Custom/` or `KICAD_LIB_GITHUB` for the public app
**What:** cosmetic renames to suit a public audience.
**Why bad:** invalidates the owner's tables, KiCad projects and path variables for no functional gain.
**Instead:** keep both names; document them.

### Anti-Pattern 4: Scanning clones with `rglob` and a top-level-only skip list
**What:** current `_collect_files` / `_walk`.
**Why bad:** walks every `.git/objects` folder of every clone.
**Instead:** prune `.git` at every depth.

### Anti-Pattern 5: Scan cache that depends on source files
**What:** `_code_signature` hashing `.py` files.
**Why bad:** silently disables the saved scan in the frozen build.
**Instead:** frozen-aware signature.

## Scalability Considerations

The relevant scale is collection size, not users.

| Concern | Own parts only | + Wurth (about 7.6k footprints) | + several large catalog libs |
|---------|----------------|----------------------------------|------------------------------|
| Full scan | seconds | about 70 s (63 s is the 3D path check) | grows linearly; per-source Skip already exists |
| Startup | saved scan | saved scan (fingerprint stat walk, `.git` pruned) | stat walk cost grows with file count; keep it a stat walk |
| Add/Update scan | n/a | `scan_source` only the changed source | same |
| Disk | MB | `--depth 1` clone | one shallow clone per entry |

## Suggested Build Order

Respecting the owner's phase order; dependencies in brackets.

1. **Test speed-up** (none). xdist, `slow` marker, shared git fixtures with the copy caveat above. Result: later phases run a fast suite.
2. **Choose library folder** (1). New `collection.py` (constants, `source_of`, resolve/inspect/create), `settings` keys, `library_root_dialog`, `MainWindow(library_root)` replacing `REPO_ROOT` (5 test harnesses), `--library-root`/env override, `configured_library_folder`, parent-mode `none`, `.git`-pruning scanner and scan-cache walkers, literal `"Custom"` -> constants, `RepoLayout` fields. Keep the legacy in-repo fallback. Start the freeze spike (tool and 3.14 viability) here, because its outcome constrains phases 7-8.
3. **Repo split** (2). Interactive. Remove fallback and submodules from the tool repo, filter-repo the public repo, split CLAUDE.md, repoint test guard and `KICAD_TEST_CORPUS`, LICENSE, README, CI. The private collection keeps Wurth as a submodule until phase 4; `source_of` handles both layouts.
4. **Library catalog** (2, 3). In this order: (a) `gitnet` + `gitops.launch()` extraction + layering test + threat model; (b) `manifest`, `curated`, `scan_source`, `sync_kicad_path_vars(extra_vars)`; (c) `ops` add/update/remove with local-bare-repo tests; (d) `catalog_dialog`; (e) convert the owner's Wurth (submodule removal, Catalog Add, one Generate, set `WE_3DMODEL_DIR` through the new sync) from the main checkout.
5. **Table model** (4). Default Destination = newest KiCad config folder, `remove_library_entries`, wording, Help text. The decision itself is taken here (global); catalog Add in phase 4 already uses the current Destination and add-only entries.
6. **Menu regroup** (2, 4, 5). Pure `main_window` restructure into File / Libraries / KiCad / Help; earlier phases add their actions to the existing File menu. Update menu/shortcut tests and the User Guide numbering.
7. **Python 3.14 minimum** (none, placed before 8). `[project]` with `requires-python = ">=3.14"` (pyproject currently has only pytest config), README, `requirements` pins, drop the 3.10 import check scope in `tests/test_annotations_resolve.py`.
8. **Installer + freeze** (7, spike from 2). `_build_info.py`, frozen-aware `_code_signature`, freeze spec (PySide6 Essentials only), NSIS script with Git check, build script, smoke test of the frozen exe starting with a saved scan reused.

Strict dependencies: 2 before 3 (app must run outside the repo before the code leaves it); 2 before 4 (root and manifest location); 3 before 4e (Wurth leaves the collection repo only after the tool repo no longer carries it); 4 before 5 and 6; 7 before 8.

## Open Questions for the Owner

1. Should an explicit "Choose library folder..." choice outrank `KICAD_LIB_GITHUB` (recommended), or only apply when the variable is unset (milestone wording)?
2. Is `ul_CSD85301Q2.zip` redistributable in a public repo, or should the suite use a synthetic zip?
3. Is `.planning/` published as is, or scrubbed (it holds workstation paths and part data)?
4. Keep the private collection a parent repo with `Custom` as submodule (recommended, keeps the bump) or flatten it?
5. Curated list contents and licence gate: show the upstream licence file in the Add preview, and refuse libraries with no licence file?

## Sources

- Code and tests of this repository, branch `feature/part-importer` (grep and reads of `main_window.py`, `library_scanner.py`, `scan_cache.py`, `settings.py`, `table_generator.py`, `kicad_setup.py`, `gitops.py`, `importer/commit_step.py`, `importer/commit_plan.py`, `importer/layout.py`, `importer/verify.py`, `tests/conftest.py`, `tests/test_layering.py`, `tests/README.md`) (HIGH)
- `WurthElektronik/KiCad-Library` checkout: footprints use `${WE_3DMODEL_DIR}`, its own `fp-lib-table` uses `${WE_FOOTPRINT_DIR}`; the owner's `kicad_common.json` sets `WE_3DMODEL_DIR` by hand (HIGH)
- [PyInstaller changelog](https://pyinstaller.org/en/latest/CHANGES.html): Python 3.14 support added in 6.15.0 (MEDIUM-HIGH)
- [PyInstaller Advanced Topics](https://pyinstaller.org/en/latest/advanced-topics.html): `sys.frozen` and `sys._MEIPASS`, onedir resource layout (MEDIUM)
- [Qt for Python and Nuitka](https://doc.qt.io/qtforpython/deployment/deployment-nuitka.html) and [Nuitka 4.2 release notes](https://nuitka.net/posts/nuitka-release-42.html): 3.14 support claimed, PySide6 6.12 on 3.14 unconfirmed (LOW)
- [KiCad third-party libraries](https://www.kicad.org/libraries/third_party) and secondary PCM descriptions (`KICAD<n>_3RD_PARTY`, `installed_packages.json`): PCM table-entry format not verified against KiCad source (LOW)
