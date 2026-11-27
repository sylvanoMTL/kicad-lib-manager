# Phase 17: Library Catalog - Pattern Map

**Mapped:** 2026-11-27
**Files analyzed:** 26 new/modified (plus tests)
**Analogs found:** 25 / 26 (paths are repo-relative; every analog is git-tracked)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `kicad_lib_manager/procs.py` (add `StreamedProcess`, `start_process`) | utility | streaming | `kicad_lib_manager/procs.py` `run_process` | exact (same file) |
| `kicad_lib_manager/catalog/__init__.py` | config | none | `kicad_lib_manager/importer/__init__.py` (docstring only) | exact |
| `kicad_lib_manager/catalog/urls.py` | utility | transform | `kicad_lib_manager/gitops.py` `_TAG_NAME_RE`/`_BRANCH_NAME_RE` validators | role-match |
| `kicad_lib_manager/catalog/gitnet.py` | service | request-response + streaming | `kicad_lib_manager/gitops.py` (`GitContext`, `_env`, allow-list) | role-match |
| `kicad_lib_manager/catalog/githubapi.py` | service | request-response | `gitops.py` Issue-returning style; no urllib analog | partial |
| `kicad_lib_manager/catalog/manifest.py` | service | CRUD (JSON file) | `kicad_lib_manager/scan_cache.py` + `library_scanner._read_config` | role-match |
| `kicad_lib_manager/catalog/curated.py` | config | static data | `kicad_lib_manager/manufacturers.py` (canonical table) | role-match |
| `kicad_lib_manager/catalog/validate.py` | service | file-I/O, transform | `kicad_lib_manager/library_scanner.py` (`_check_model_files`, `_walk_matches`) | role-match |
| `kicad_lib_manager/catalog/ops.py` | service | batch / plan-preview-apply | `kicad_lib_manager/library_scanner.py` `rescan_library`, `gitops.py` | role-match |
| `kicad_lib_manager/catalog/status.py` | service | transform + background | `kicad_lib_manager/widgets/background.py` (check pattern) | role-match |
| `kicad_lib_manager/widgets/catalog_dialog.py` | component | event-driven | `kicad_lib_manager/widgets/help_dialog.py` + `import_dialog.py` (`TaskWorker`, close-waits) | role-match |
| `kicad_lib_manager/library_scanner.py` (model_vars, kicad-embed, `.staging` prune, `scan_source`, `remove_source`, `extra_vars`) | service | transform | same file: `rescan_library`, `_desired_path_vars`, `sync_kicad_path_vars` | exact |
| `kicad_lib_manager/scan_cache.py` (`.staging` prune, `catalog.json` fingerprint) | service | file-I/O | same file `_walk` | exact |
| `kicad_lib_manager/table_generator.py` (`library_description` via `source_of`) | service | transform | `collection.source_of` | exact |
| `kicad_lib_manager/main_window.py` (menu, busy refusal, startup check, post-Add) | controller | event-driven | same file: `_act_import`, `_switch_refusal`, `_guide_window`, `run_in_background` uses | exact |
| `kicad_lib_manager/widgets/migration_dialog.py` (stop timers in `done()`; folded todo) | component | event-driven | `widgets/import_dialog.py` `done`/`_reap` | role-match |
| `kicad_lib_manager/importer/verify.py` (generalise Würth prefix) | service | transform | same file | exact |
| `scripts/catalog/wurth_to_catalog.py` | script | batch (dry-run/apply) | `scripts/split/cutover_collection.py` | exact |
| `tests/test_procs.py`, `tests/test_gitops.py`, `tests/test_layering.py` (register `catalog.*`) | test | n/a | same files | exact |
| `tests/test_catalog_layering.py` | test | n/a | `tests/test_importer_layering.py` | exact |
| `tests/test_catalog_gitnet.py` (slow, `file://`) | test | n/a | `tests/gitfixtures.py` + `tests/test_gitops.py` | role-match |
| `tests/test_catalog_*.py` (manifest, urls, validate, ops, status) | test | n/a | `tests/collectionfixtures.py` `make_collection` | role-match |
| `tests/test_catalog_dialog.py` | test | n/a | `tests/test_help_dialog.py`, `tests/test_import_dialog.py` | role-match |
| `tests/catalogfixtures.py` | test util | n/a | `tests/gitfixtures.py` | role-match |
| `tests/test_wurth_to_catalog.py` | test | n/a | `tests/test_cutover_collection.py` | exact |
| User Guide page, `CLAUDE.md` entries | docs | n/a | `widgets/help_dialog.py` page registry | role-match |

## Pattern Assignments

### `kicad_lib_manager/procs.py` (utility, streaming) - add `StreamedProcess`

**Analog:** `kicad_lib_manager/procs.py` lines 1-25 (whole file). Only this file may hold `Popen`/taskkill; `tests/test_procs.py::test_only_procs_starts_processes` (lines 95-125) and `tests/test_gitops.py:238` (`importers == {"gitops.py","kicad_process.py","importer/kicad_cli.py","procs.py"}`) pin that.

```python
import subprocess
from collections.abc import Callable, Sequence

def run_process(argv: Sequence[str], *, runner: Callable | None = None, **kwargs):
    kwargs.setdefault("capture_output", True)
    if "input" not in kwargs and "stdin" not in kwargs:
        kwargs["stdin"] = subprocess.DEVNULL
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    run = runner if runner is not None else subprocess.run
    return run(list(argv), **kwargs)   # `runner` is the test seam; look up subprocess.* per call
```
Copy: argv always a list, `CREATE_NO_WINDOW` OR-ed into creationflags (plus `CREATE_NEW_PROCESS_GROUP`), `starter=` test seam mirrors `runner=`, taskkill goes through `run_process`. Update `tests/test_layering.py` ALLOWED only if `procs` imports change (it must stay `set()`).

### `kicad_lib_manager/catalog/gitnet.py` (service)

**Analog:** `kicad_lib_manager/gitops.py` lines 1-40 and `_env` (93-111).

Imports to copy (gitnet imports only `models` and `procs`, never `subprocess`, never `gitops`):
```python
from .models import Issue, Severity
from .procs import run_process
```
(inside `catalog/` use `from ..models import Issue, Severity` and `from ..procs import ...`.)

Env pattern to copy and invert (strip every `GIT_*`, then set fixed vars):
```python
env = {k: v for k, v in source.items() if not k.upper().startswith("GIT_")}
env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_EDITOR": "true", "LC_ALL": "C"})
```
Differences (RESEARCH "The git command lines"): add `GIT_CONFIG_GLOBAL=<devnull>`, `GCM_INTERACTIVE=Never`, `GIT_LFS_SKIP_SMUDGE=1`, and `GIT_DIR`/`GIT_WORK_TREE` for any in-clone call (C10). Do NOT widen `gitops.ALLOWED_SUBCOMMANDS` (pinned by `tests/test_gitops.py` lines 35-39, 75-77). Own constant `NET_SUBCOMMANDS`; decisions on exit codes and plumbing output, never stderr text. Return `Issue(Severity.ERROR, "git.unreachable", ...)` instead of raising, per gitops.

### `catalog/urls.py`, `catalog/manifest.py` validators (utility)

**Analog:** `gitops.py` lines 36-39:
```python
_TAG_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_BRANCH_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
```
Use `re.fullmatch` on module-private compiled constants (`_ID_RE`, `_BRANCH_RE`, `_VAR_RE`); values passed to git come only from these validators.

### `catalog/manifest.py` (service, JSON CRUD)

**Analog:** `library_scanner._read_config` (returns `Issue` on bad file) and `fsutil.atomic_write_text`/`read_source`. Pattern: `load()` returns `Manifest | Issue`, missing file = empty manifest, bad JSON = Issue, never raises; `save()` writes atomically via `fsutil` (UTF-8, LF). Path variables use `str(root).replace("\\", "/")` as in `_desired_path_vars` (below). Dataclasses `@dataclass(frozen=True)` for entries; `field(default_factory=...)` for mutables (CONVENTIONS).

### `catalog/curated.py` (config, static data)

**Analog:** `kicad_lib_manager/manufacturers.py` (canonical table as a Python module, frozen-safe, imports `models` only). Register in `tests/test_layering.py` ALLOWED.

### `catalog/validate.py` (service, file-I/O)

**Analog:** `library_scanner._check_model_files` (the rule to extend; non-Custom paths starting `${` are currently skipped, line ~659) and `collection.source_of`:
```python
# collection.py:22 and 81-88
THIRD_PARTY_DIR = "ThirdParty"
def source_of(rel_path: str) -> str:
    ...
    if parts and parts[0] == THIRD_PARTY_DIR and len(parts) > 1 and parts[1]:
        return parts[1]
```
Imports allowed: `models`, `kicad_files`, `collection` (register in ALLOWED).

### `catalog/ops.py` (service, plan -> preview -> apply)

**Analog:** `library_scanner.rescan_library` (lines 873+): copy the "return an `Issue` instead of raising", `copy.deepcopy(previous)` and `previous is never mutated` conventions; and `sync_kicad_path_vars` docstring shape: functions that write return `list[Issue]`, writes only after a confirm callback answers, a `running()` callable injected for KiCad-open checks (`kicad_process.kicad_running`, D-14).

### `kicad_lib_manager/library_scanner.py` (extend)

**Analog (path vars)** lines 217-262:
```python
def _desired_path_vars(repo_root: Path) -> dict[str, str]:
    repo_str = str(repo_root).replace("\\", "/")
    return {"KICAD_LIB_GITHUB": repo_str,
            "CUSTOM_3DMODEL_DIR": f"{repo_str}/{OWN_DIR}/{MODELS_DIR}"}

def would_change_path_vars(repo_root: Path, *, config_base: Path | None = None) -> bool:
    ...
    return bool(_plan_changes(old_vars, _desired_path_vars(repo_root))[0])

def sync_kicad_path_vars(repo_root, *, config_base=None, backup_root=None, running=None, confirm=None) -> list[Issue]:
```
Add keyword `extra_vars: Mapping[str, str] | None = None`, merge into `desired` before `_plan_changes`; keyword-only, default None keeps existing callers/tests unchanged.

**Analog (scan_source/remove_source)** `rescan_library` lines 873-935: signature `(repo_root, previous, ..., kicad_fp_dir=None) -> X | Issue`, `merged = copy.deepcopy(previous)`, `_full_needed(msg)` Issue with code `rescan.full_needed` when only a full scan is right.

### `kicad_lib_manager/scan_cache.py` and `_walk_matches`

**Analog:** `scan_cache._walk(start, rel_dir, *, skip_top)` (line 64): iterative stack walk with `os.scandir`, `complete` flag on `OSError`. Add the `ThirdParty/.staging` prune in this and in `library_scanner._walk_matches` identically (RESEARCH C5).

### `kicad_lib_manager/widgets/catalog_dialog.py` (component, event-driven)

**Analog 1 (non-modal, parentless window):** `main_window.py` lines 2420-2450:
```python
def _guide_window(self) -> HelpDialog:
    if self._guide is None:
        self._guide = HelpDialog()  # no parent: a parent would let a window-modal dialog block it
        centre_window(self._guide, self)
    return self._guide
```
Same for `show()`, `raise_()`, `activateWindow()`; theme constants from `widgets/theme.py` (`SP_MD`, `AMBER`, `ACCENT`, ...), never raw colours (UI-01). Imports pattern from `help_dialog.py` lines 1-27 (`from PySide6.QtWidgets import (...)`, `from .theme import ...`).

**Analog 2 (worker, close-waits):** `widgets/import_dialog.py`:
```python
class TaskWorker(QThread):                       # line 343
    progress = Signal(str, int, int); result = Signal(object); failed = Signal(str)
    def run(self):
        try:
            self.value = self._fn(self.progress.emit)
            self.result.emit(self.value)
        except Exception as e:  # thread boundary only
            self.failed.emit(f"{type(e).__name__}: {e}")

def _spawn(self, fn, tag=None):                  # line 1590
    worker = TaskWorker(fn, parent=self, tag=tag)
    self._workers.append(worker)
    worker.finished.connect(lambda w=worker: self._reap(w))
    return worker
# _reap: worker.wait(2000) bounded; never deleteLater a finished worker (access violation observed)
```
Close rule (lines 3662-3694): `done()` returns without closing while a job runs, enters a Finishing state and closes by itself later; `closeEvent` calls `done(Rejected)` and `event.ignore()` when busy. Catalog: ask to cancel the running job, set the cancel `threading.Event`, then close once the worker finished; stop every `QTimer` in `done()` before `super().done(r)` (D-16 and folded todo). Reuse `TaskWorker` by import (do not copy it).

### `kicad_lib_manager/widgets/migration_dialog.py` (folded todo)

**Analog:** `import_dialog.py` `done()` (3662): stop `_draft_timer` and `_rebuild_timer` first, then run the existing close-waits path so a pending draft save still runs as a worker. Test: close with a pending timer, assert no worker starts.

### `kicad_lib_manager/main_window.py` (controller)

**Menu analog** lines 435-440:
```python
self._act_import = QAction("&Import Part...", self)
self._act_import.setShortcut(QKeySequence("Ctrl+I"))
self._act_import.setToolTip("Import a vendor package (.zip or folder) into Custom/")
self._act_import.setStatusTip("Import a vendor package (.zip or folder) into Custom/")
self._act_import.triggered.connect(lambda: self._open_import())
file_menu.addAction(self._act_import)
```
New `_act_catalog` with `Ctrl+Shift+L`, placed beside it; add it to the enable/disable group near line 1153 only if it must grey out.

**Busy refusal analog** lines 847-860: add one branch `if self._catalog_busy(): return _BUSY_CATALOG` (new module constant beside `_BUSY_IMPORT`, `_BUSY_MIGRATION`); the window being open does NOT refuse, only a running job does (D-16).

**Startup background check analog** line 886 / 1064 / 592: `task = run_in_background(work, on_result, on_failed, name="recent-folder-check")` from `widgets/background.py`. Use a daemon thread (module docstring: never a QThread for a check that can block). Keep `self._catalog_check: BackgroundTask | None` and `.cancel()` it in the close path like `_dest_check`.

### `kicad_lib_manager/table_generator.py`

**Analog:** line 58 `source = rel_path.split("/", 1)[0]` becomes `collection.source_of(rel_path)`; add `collection` to the `table_generator` entry in `tests/test_layering.py` ALLOWED (line 19: currently `{"fsutil","kicad_files","models","sexpr"}`), or pass the source in (RESEARCH C4).

### `scripts/catalog/wurth_to_catalog.py` (script, dry-run/apply)

**Analog:** `scripts/split/cutover_collection.py` (lines 13-36, 395-436):
```python
parser.add_argument("--repo", required=True, ...)
parser.add_argument("--apply", action="store_true", help="... without it the plan is only printed")
parser.add_argument("--pre-split-tag", metavar="NAME", ...)   # rename: --rollback-tag
if args.apply and not args.pre_split_tag:
    print("cutover: --apply needs ..."); return 2
found = plan(repo, tag)
if found.problems:
    for p in found.problems: print(f"cutover: refused: {p}")
    print("cutover: nothing was written"); return 1
_report(found, args.apply)
if not args.apply:
    print("cutover: dry run only, nothing was written; run again with --apply ..."); return 0
return apply(repo, found, message)
```
Copy: module docstring with usage and exit codes (0 done/dry run, 1 refused, 2 unusable input), `plan()` returning a dataclass with `problems`, `_remove_tree` with `_force_remove` (read-only `.git` files on Windows), `_post_checks`, `_print_way_back`. This script is stdlib-only and may use `subprocess` (scripts are outside `kicad_lib_manager/`, so the pinned-importer test does not scan it). It must move `.git/modules/WurthElektronik/...` to a `--backup-dir` argument (D-27), print the stale KiCad 9.0 `WE_3DMODEL_DIR` line (D-30), and reuse `scripts/split/uri_diff.py` for pass check (1).

## Test Patterns

### `tests/test_catalog_layering.py`
**Analog:** `tests/test_importer_layering.py` (docstring rules, `ALLOWED` dict keyed by dotted module, `ast` reading, synthetic-tree `test_guard_*` proofs in `tmp_path`). Rules: every `catalog.*` module registered; `catalog.gitnet` imports only `{models, procs}`; no module in `gitops`, `importer.*`, `install`/commit path imports `catalog.gitnet`; no `import subprocess` in `catalog/*`; `catalog/__init__.py` docstring only.

### Register in `tests/test_layering.py`
```python
ALLOWED = {
    "models": set(), "fsutil": {"models"}, "procs": set(),
    "gitops": {"models", "procs"},   # catalog.gitnet analog: {"models", "procs"}
    ...
}
```
Add `catalog.*` keys there or in the new layering test (pick one; the foundation test also asserts no-Qt for foundation modules: `test_foundation_modules_load_no_qt`, line 60).

### Process-start guards
`tests/test_procs.py:95-125` (`_starter_references`, `test_only_procs_starts_processes`) needs no change if gitnet stays subprocess-free; add a procs test for `StreamedProcess` using the `starter=` seam, and a pinned-argv quick test for gitnet modeled on `tests/collectionfixtures.py` `recording_git` (lines 23-37: runner that appends argv and returns `subprocess.CompletedProcess(argv, code, stdout=bytes, stderr=b"")`). Real-git `file://` tests use `tests/gitfixtures.py` (`_build`, `remove_tree`, `commit_file`, `advance_remote_main`) and MUST carry `@pytest.mark.slow`; they add `protocol.file.allow=always` through `NetGit(allow_file=True)`.

### Dialog tests
`tests/test_help_dialog.py` (non-modal window, parentless), `tests/test_import_dialog.py` (worker close-waits, "Finishing"); fake the net with `NetGit.starter` so no process starts. Collections for scans: `tests/collectionfixtures.py::make_collection`.

## Shared Patterns

### Issue returns, no raising
**Source:** `kicad_lib_manager/gitops.py`, `library_scanner._read_config`, `rescan_library`. Services return `X | Issue` or `list[Issue]` (`Issue(Severity.ERROR, "code.dotted", "plain text")`); `except Exception` only at the thread boundary (`TaskWorker.run`). Keep message phrases plain-language (no raw field names; memory: plain-language UI).

### Qt-free services, downward imports
**Source:** `tests/test_layering.py` lines 14-30: `models` <- `fsutil` <- `kicad_files`/`collection` <- scanner/generator; widgets import services, never the reverse; `main_window` imports nothing back.

### Background work
**Source:** `widgets/background.py` (daemon thread + module queue + dispatcher) for the startup `ls-remote` check; `TaskWorker` + `_spawn`/`_reap` for user-triggered jobs. Never `deleteLater` a finished worker; bound `wait(2000)`.

### Atomic file writes
**Source:** `kicad_lib_manager/fsutil.py` `atomic_write_text`, `read_source`, `backup_file` for `catalog.json` and `.gitignore`.

### Paths
`str(root).replace("\\", "/")` for path-variable values; `Path.as_posix()` for table URIs; `pathlib.Path` everywhere.

### Tests
Per-test isolation of git config, ini and KiCad config is in `tests/conftest.py`; a test creating a real repo needs `@pytest.mark.slow` or it fails; skip budget is 10 on a quick run, so avoid new skips.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `kicad_lib_manager/catalog/githubapi.py` | service | No HTTP client exists in the app; `urllib.request` is new. Follow RESEARCH signatures (`repo_info(owner, repo, *, opener=None, timeout=10.0) -> RepoInfo | Issue`), with `opener=` as the test seam like `runner=` in procs. Offline or 403 returns an `api.unknown` Issue and never blocks Add. |
| `procs.StreamedProcess` reader thread and taskkill cancel | utility | Nothing streams a child process today; use RESEARCH Pattern 1 (verified experiment) with the `run_process`-style seam. |

## Metadata

**Analog search scope:** `kicad_lib_manager/` (procs, gitops, library_scanner, scan_cache, table_generator, collection, main_window, widgets/background, help_dialog, import_dialog), `scripts/split/`, `tests/`.
**Files scanned:** about 20 read or grepped; RESEARCH.md read to line 409 (module signatures and git argv), CONTEXT.md in full.
**Pattern extraction date:** 2026-11-27
