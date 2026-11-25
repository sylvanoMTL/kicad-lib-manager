# Phase 15: Choose Library Folder and New Collection - Pattern Map

**Mapped:** 2026-11-23
**Files analyzed:** 22 new or modified source files (plus test files, listed last)
**Analogs found:** 22 / 22 (the three dialogs and `collection.py` have role-match analogs only)

All analog paths were checked as git-tracked source (`git ls-files` run inside `kicad_lib_manager/`: `widgets/backup_dialog.py`, `widgets/import_result.py`, `tests/conftest.py`, `tests/gitfixtures.py`, `tests/test_gitops.py`, `tests/test_layering.py` are tracked; the rest are the package modules named in RESEARCH and live in the tracked package). No gitignored mirror path appears below.

Excerpts below were read this session. Line numbers are for the current worktree; `main_window.py` shifts as plans edit it, so re-grep before use.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `kicad_lib_manager/collection.py` (NEW) | service (Qt-free domain) | transform / file-I/O | `kicad_lib_manager/importer/layout.py` + `kicad_setup.same_folder` | role-match |
| `kicad_lib_manager/procs.py` (NEW) | utility (leaf) | request-response | `gitops.run_git` subprocess block (`gitops.py:115-152`) | exact (extract) |
| `kicad_lib_manager/startup.py` (NEW) | service/entry | request-response | `kicad_lib_manager.py` + `main_window._detect_kicad` | role-match |
| `kicad_lib_manager.py` | entry point | request-response | itself (17 lines) | exact |
| `kicad_lib_manager/gitops.py` | service (git) | request-response | `gitops.create_tag` (`:362`) | exact |
| `kicad_lib_manager/kicad_setup.py` | service (config) | request-response | `checkout_mismatch` (`:288`) | exact |
| `kicad_lib_manager/library_scanner.py` | service | file-I/O | itself (`_collect_files`, `_path_var_refusal`) | exact |
| `kicad_lib_manager/scan_cache.py` | service | file-I/O | itself (`_walk`, `:80-95`) | exact |
| `kicad_lib_manager/settings.py` | store | CRUD | `load_dest_history` / `add_dest_to_history` (`:94-111`) | exact |
| `kicad_lib_manager/importer/commit_step.py` | service | request-response | itself (`_parent_state`, `CommitProbe`) | exact |
| `kicad_lib_manager/widgets/commit_panel.py` | component | event-driven | itself (`apply_probe`, `:390-405`) | exact |
| `kicad_lib_manager/main_window.py` | controller/orchestrator | event-driven | itself (`_sync_path_vars`, `_check_checkout`, `_set_scan_running`) | exact |
| `kicad_lib_manager/widgets/choose_folder_dialog.py` (NEW) | component (dialog) | request-response (off-thread check) | `widgets/backup_dialog.py` + `TaskWorker` | role-match |
| `kicad_lib_manager/widgets/new_collection_dialog.py` (NEW) | component (dialog) | CRUD (create) | `widgets/backup_dialog.py` + `TaskWorker` | role-match |
| `kicad_lib_manager/widgets/first_run_dialog.py` (NEW) | component (dialog) | request-response | `widgets/backup_dialog.py` | role-match |
| Literal `"Custom"` sweep: `atomic_check.py`, `atomic_fixes.py`, `changes.py`, `importer/{commit_gate,commit_step,incoming,layout,planner}.py`, `importer/migration/{gate,inventory}.py`, `library_scanner.py`, `main_window.py`, `scan_cache.py` | utility (constants) | transform | `importer/layout.py:24` (`repo_root / "Custom"`) | exact |
| `kicad_lib_manager/importer/kicad_cli.py`, `kicad_process.py` | service | request-response | `gitops.run_git` | exact (swap call to `procs.run_process`) |
| `kicad_lib_manager/widgets/help_dialog.py`, `CLAUDE.md` | docs | static | itself | exact |
| Tests: `test_collection.py`, `test_collection_git.py`(slow), `test_startup.py`, `test_settings_library.py`, `test_procs.py`, `test_main_window_root.py`, `test_library_root_dialogs.py`, `collectionfixtures.py` (all NEW) | test | - | `tests/test_main_window.py` (harness), `tests/test_gitops.py`, `tests/test_layering.py`, `tests/gitfixtures.py` | role-match |
| Tests edited: 5 harnesses, `test_layering.py`, `test_importer_layering.py`, `test_gitops.py`, `test_kicad_config.py`, `test_commit_step.py`, wording tests | test | - | themselves | exact |

## Pattern Assignments

### `kicad_lib_manager/settings.py` (store, CRUD) - add `library/root`, `library/recent`

**Analog:** same file, `load_dest_history` / `add_dest_to_history` (lines 94-111) and `load_import_dir` (64-72).

Pre-existing header and constants (lines 8-18):
```python
import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

_MAX_DEST_HISTORY = 10
```
List helper to copy for `load_library_recent` / `add_library_recent` (lines 94-111). Keep the single-element-`str` guard; the new add must dedupe on `normcase(normpath)` but keep the user's spelling:
```python
def load_dest_history() -> list[str]:
    s = get_settings()
    val = s.value("dest_history", [])
    if isinstance(val, str):
        return [val] if val else []
    return list(val) if val else []


def add_dest_to_history(path: str) -> list[str]:
    history = load_dest_history()
    if path in history:
        history.remove(path)
    history.insert(0, path)
    history = history[:_MAX_DEST_HISTORY]
    s = get_settings()
    s.setValue("dest_history", history)
    return history
```
Single-value helper to copy for `load_library_root` (untrusted value, re-check at use, lines 64-77); add `clear_library_root` as `get_settings().remove("library/root")`:
```python
def load_import_dir() -> Path | None:
    s = get_settings()
    val = s.value("import/last_dir", "")
    if val:
        p = Path(str(val))
        if p.is_dir():
            return p
    return None
```
Add a new `# ── Library folder ───...` divider (project comment convention, e.g. line 62 `# ── Import folder ──...`). A `list` value for `library/root` must be treated defensively (RESEARCH Pitfall 11).

---

### `kicad_lib_manager/gitops.py` (service, request-response) - `init` + `init_repository`

**Analog:** same file. Allow-list at lines 21-25; `create_tag` at 362-369 is the model for a one-subcommand wrapper with a fail-before-start guard.

```python
ALLOWED_SUBCOMMANDS = frozenset({
    "--version", "rev-parse", ..., "check-ignore",
    "tag",  # Phase 13 MIG-01: the pre-atomic recovery tag only, a lightweight tag the code names, never -f/--force
})
```
Add `"init",  # Phase 15 ROOT-06: new collection only, never a clone, never a remote`. Wrapper to copy (lines 362-369):
```python
def create_tag(ctx: GitContext, repo: Path, name: str) -> GitRun | Issue:
    """... raises ValueError before anything starts for an odd name."""
    if not _TAG_NAME_RE.fullmatch(name):
        raise ValueError(f"{name!r} is not an allowed tag name")
    return run_git(ctx, repo, "tag", name)
```
New: `init_repository(ctx, repo, branch="main")` -> `run_git(ctx, repo, "init", "--template=", "-b", branch)`. Gate `-b` on `git_version(ctx) >= (2, 28)` in `collection.create_collection` (version helper at `gitops.py:159`; `MIN_GIT_VERSION = (2, 25)` at line 28 stays). `find_git(repo_root, which=...)` (lines 74-85) is what the New Collection "Git not found" row uses; it re-detects per call.

`run_git` subprocess block to extract into `procs.py` (lines 115-152): the `run = ctx.runner or subprocess.run` line, `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)`, `capture_output=True`, `stdin=subprocess.DEVNULL` unless `input=`, timeout and `OSError` mapped to `Issue` stays in the caller.

---

### `kicad_lib_manager/procs.py` (utility leaf, request-response)

**Analog:** `gitops.run_git` (excerpt above) and the two other starters:

`importer/kicad_cli.py:70-79`:
```python
    run = runner or subprocess.run
    try:
        result = run(
            [str(exe), *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
```
`kicad_process.py:25-33` (Windows `tasklist`, same flag) and `:35-41` (POSIX `ps`, no flag, `timeout=5`).

Constraints the new leaf must honour (RESEARCH Inventory 6): look up `subprocess.run` at call time (`tests/test_kicad_process.py:30` does `monkeypatch.setattr(kicad_process.subprocess, "run", ...)`), keep `import subprocess` in `kicad_process.py` for `subprocess.SubprocessError`, keep the `runner(argv, **kwargs)` call shape and `kwargs["creationflags"]` assertions (`tests/test_gitops.py:103`, `tests/test_kicad_cli.py:147`). Docstring style: module docstring stating what it is the only place for (copy `gitops.py` lines 1-7). Add `"procs": set()` to `tests/test_layering.py` `ALLOWED`.

---

### `kicad_lib_manager/collection.py` (service, Qt-free, transform + file-I/O)

**Analogs:** `importer/layout.py` (constants and Path layout, lines 1-31), `kicad_setup.same_folder` (233-242), `kicad_setup.wrong_checkout` (253-264), `kicad_lib_manager/models.py` dataclass style, `gitops.find_git` (Issue return convention).

Layout analog to replace with constants (`importer/layout.py:15-31`):
```python
@dataclass(frozen=True)
class RepoLayout:
    repo_root: Path
    custom_dir: Path
    ...
    @classmethod
    def for_repo(cls, repo_root: Path) -> "RepoLayout":
        custom = repo_root / "Custom"
        return cls(
            repo_root=repo_root,
            custom_dir=custom,
            symbols_dir=custom / "Symbols",
            footprints_dir=custom / "Footprints",
            models_dir=custom / "3DModels",
        )
```
Folder comparison to reuse (do not write a second one), `kicad_setup.py:233-242`:
```python
def same_folder(a: str, b: str) -> bool:
    def _key(value: str) -> str:
        return os.path.normcase(os.path.normpath(str(Path(value.strip()).resolve())))
    return _key(a) == _key(b)
```
Note layering: `collection` is allowed `{"models", "fsutil", "gitops"}` (RESEARCH). `same_folder` lives in `kicad_setup` (which imports `library_scanner`), and `library_scanner` will import `collection`, so do not import `kicad_setup` from `collection`; re-implement the 3-line `_key` privately or move `same_folder` into `collection` and have `kicad_setup` import it. Planner decides; flag it.

Message convention: return `list[Issue]` / `Issue(Severity.X, "code.name", text)` (see `gitops.find_git`: `Issue(Severity.WARNING, "git.not_found", "git was not found on PATH")`). Contents per RESEARCH: constants (`OWN_DIR`, `SYMBOLS_DIR`, `FOOTPRINTS_DIR`, `MODELS_DIR`, `SHARED_FOOTPRINT_LIBRARY`, `THIRD_PARTY_DIR`, `PATH_LENGTH_WARNING`), `source_of`, `check_folder` (rows as data, stop at first failure; writable probe by `tempfile.TemporaryFile(dir=folder)`, not `os.access`), `validate_collection_name`, `resolve_library_root(candidates, check)`, `create_collection` (cleanup with read-only-clearing rmtree; pattern: `tests/gitfixtures.remove_tree`).

---

### `kicad_lib_manager/startup.py` (NEW) and `kicad_lib_manager.py` (entry)

**Analog:** `kicad_lib_manager.py` (whole file, 17 lines):
```python
#!/usr/bin/env python3
"""KiCad Library Manager - PySide6 GUI for managing KiCad library tables."""

import sys
from PySide6.QtWidgets import QApplication
from kicad_lib_manager.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```
Keep `main()` thin (project rule); move parsing/resolve to `startup.py`: `argparse.ArgumentParser(add_help=False).parse_known_args(sys.argv[1:])`, `QApplication([sys.argv[0], *rest])`, `MainWindow(library_root, source, startup_notes)`. `tests/test_annotations_resolve.py` also parses `kicad_lib_manager.py` against the 3.10 grammar.

Config read for the KiCad candidate: add `configured_library_folder(config_base=None) -> str | None` to `kicad_setup.py` by copying `checkout_mismatch` (lines 288-305):
```python
    config_dir = find_kicad_config_dir(config_base)
    if not config_dir:
        return None
    common_path = config_dir / COMMON_FILE
    if not common_path.exists():
        return None
    read = _read_config(common_path)
    if isinstance(read, Issue):
        return None
    _src, _config, old_vars = read
    return wrong_checkout(repo_root, old_vars.get("KICAD_LIB_GITHUB"))   # replace with old_vars.get(...) str check
```

---

### `kicad_lib_manager/kicad_setup.py` - D-26 copy and field rename

**Analog:** same file lines 245-285. Current copy to replace with the UI-SPEC wording (Copywriting table rows "Wrong-folder warning" / "Wrong-folder refusal"):
```python
@dataclass(frozen=True)
class CheckoutMismatch:
    app_folder: str
    kicad_folder: str

def wrong_checkout_refusal(m: CheckoutMismatch, action: str) -> str:
    return (
        f"{action}: this app runs from {m.app_folder}, but KiCad reads its libraries "
        f"from {m.kicad_folder} (KICAD_LIB_GITHUB). Run the app from {m.kicad_folder}, "
        ...
def wrong_checkout_warning(m: CheckoutMismatch) -> str:
    return (
        f"KiCad reads its libraries from {m.kicad_folder}, but this app runs from "
        ...  push them from here, then pull there."
```
Signatures need no change (`wrong_checkout(repo_root, configured)` already takes the folder). Tests that assert the old strings must change in the same plan: `tests/test_checkout_check.py:127-131`, `test_checkout_warning.py:181,249`, `test_kicad_setup.py:326`, `test_migration_dialog_run.py:202`, `test_help_dialog.py:115-126` (requires the word `push`), plus User Guide text at `widgets/help_dialog.py:246-255,270-272`. `_chooser_refusal` (`:308`) keeps refusing (Pin).

---

### `kicad_lib_manager/library_scanner.py` - `.git` prune, constants, refusal relaxed, `would_change_path_vars`

**Skip walker, current code (lines 417-426):**
```python
def _in_skip_dir(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).parts
    return rel[0] in SKIP_DIRS if rel else False


def _collect_files(root: Path, pattern: str) -> list[Path]:
    return sorted(
        f for f in root.rglob(pattern)
        if not _in_skip_dir(f, root)
    )
```
Plus `find_footprint_libs` at ~459: `d for d in root.rglob("*.pretty") if d.is_dir() and not _in_skip_dir(d, root)`. Replace both with one `os.walk` helper that prunes `dirnames` equal to `.git` at every depth (and still applies `SKIP_DIRS` at top level), returning the same sorted `Path` list. Existing test to extend: `tests/test_scanner_skip_dirs.py`.

**Refusal to relax (lines 130-150, in `_path_var_refusal`):** keep the worktree branch (`config.worktree_refused`, reword to "the library folder is a git worktree"), delete this branch (owner decision 2026-11-23):
```python
    if is_configured and _norm_path(configured) != _norm_path(repo_str):
        return Issue(Severity.WARNING, "config.other_checkout_refused", ...)
```
Update `tests/test_kicad_config.py:515-528` (must now ask, default No) and keep `:543` (`same checkout in another spelling`). Add the `would_change_path_vars(repo_root, *, config_base=None) -> bool` predicate from `_read_config` + `_plan_changes` (no log lines, so `config.var_ok` is not emitted after a switch). The f-string at `library_scanner.py:274` `f"{repo_str}/Custom/3DModels"` is also a literal-sweep site.

---

### `kicad_lib_manager/scan_cache.py` - `.git` prune

**Analog:** same file, `_walk` lines 80-95:
```python
                if is_dir:
                    if skip_top and not prefix and name in SKIP_DIRS:
                        continue
                    if name.lower().endswith(".pretty"):
                        folders.append(rel)
                    if not is_link:
                        stack.append((entry.path, rel + "/"))
                    continue
```
Add `if name == ".git": continue` above, unconditionally at any depth (library_entries calls `_walk` with `skip_top=False`, so the existing check does not cover it). Both walkers must agree or the saved scan goes stale. No cache `FORMAT` bump (RESEARCH Inventory 7).

---

### `kicad_lib_manager/importer/commit_step.py` and `widgets/commit_panel.py` - `parent_mode`

**Analog:** same files. `CommitProbe` (lines 40-67, frozen dataclass with defaults; add `parent_mode: str = "gitlink"` so existing `CommitProbe(...)` constructions in `tests/test_commit_panel.py:564,578` keep working). `_parent_state` (lines 182-195):
```python
def _parent_state(ctx: GitContext, cplan: CommitPlan) -> tuple[bool, str, str | None, str | None]:
    root = cplan.repo_root
    top = gitops.show_toplevel(ctx, root)
    if top is None or not _same_dir(top, root):
        return False, f"no parent git repository at {root.as_posix()}", None, None
    branch = gitops.current_branch(ctx, root)
    busy = gitops.busy_operation(ctx, root)
    ...
    return True, "", branch, gitops.committed_gitlink(ctx, root, cplan.custom_rel)
```
New `none` rule: `show_toplevel == root` AND `ls-files -s -- Custom` prints a `160000` entry gives `gitlink`, else `none`. The probe currently sets `parent_dir=cplan.repo_root` unconditionally (`commit_step.py:295`); that is why the panel always shows `Parent repo:`.

Panel presentation to change (`widgets/commit_panel.py:390-405` region):
```python
        if probe.state == "ready" and not probe.parent_ok:
            self._parent_reason.setText(f"Parent commit unavailable: {probe.parent_reason}")
            self._parent_reason.show()
        else:
            self._parent_reason.hide()
```
Hide (not disable) `_parent_check` (227), `_parent_label` (159), `_parent_reason` (232), plus `_preview_heading`, `_parent_preview`, `_earlier_label` (via the existing `show_parent` gate at ~711-713) when `probe.parent_mode == "none"`; `bump_parent()` (306) already returns False for a disabled box. Test updates: `tests/test_commit_step.py:542` (slow) becomes `parent_mode == "none"`. The two `_not_pushed(upstream, "Custom", branch)` calls (`commit_step.py:697,872`) are literal-sweep sites.

---

### `kicad_lib_manager/main_window.py` (controller, event-driven)

**Analog:** same file. Constructor wiring and flags to extend (lines 228-290): signature `MainWindow.__init__(self)` becomes `(self, library_root, source=..., startup_notes=())`; store `self._root`. Flags to reuse for the busy guard: `self._import_dialog`, `self._atomic_dialog`, `self._migration_dialog`, `self._pending_post_install`, `self._pending_migration`, `self._path_var_busy`, `self._chooser_busy`, and `self._worker` (scan).

Two-flag "consume after scan" shape to copy for the post-switch offer (lines 258-266, consumed in `_on_scan_finished`/`_finish_scan`):
```python
        self._pending_migration = False
        self._migration_scan_started = False
        self._generate_after_scan = False
```
Add `self._offer_vars_after_scan = False`, consumed at the end of `_finish_scan` (line ~714), then call `_sync_path_vars()` only when `would_change_path_vars(self._root, config_base=...)`.

First-scan state reset (Pitfall 2; `_startup_pending` set at line 247, cleared at 716): `_switch_root` must set `self._scan_result = None` and `self._startup_pending = True` before `_start_scan()` (full scan, no `reuse_cache`).

Busy toggling to extend (lines 559-577): add the four new actions, the Recent submenu and `Change Folder...` to the tuple, but not Open in Explorer:
```python
    def _set_scan_running(self, running: bool):
        for control in (
            self._rescan_btn, self._act_rescan, self._act_set_kicad_path,
            self._act_generate, self._generate_btn, self._act_import,
            self._import_btn, self._select_all_btn, self._deselect_all_btn,
            self._act_check_atomic, self._act_setup_chooser,
        ):
            control.setEnabled(not running)
```
Off-thread worker + request-counter pattern (lines 1473-1500, `_path_var_workers`; never reuse a worker, keep finished workers and `wait()` them):
```python
        worker = TaskWorker(lambda progress: kicad_running(), parent=self)
        self._path_var_workers.append(worker)
        self._path_var_check = worker
        worker.result.connect(self._on_path_var_check)
        worker.failed.connect(self._on_path_var_check_failed)
        worker.finished.connect(lambda w=worker: self._on_path_var_check_finished(w))
        worker.start()
```
`TaskWorker` is defined at `widgets/import_dialog.py:343` (signals `result`, `failed`, `progress`; do not shadow `finished`).

`REPO_ROOT` replacement map (RESEARCH Inventory 1, 16 code references): line 487 `items = [str(REPO_ROOT)]`; 583 and 1262 `migration_reason(RepoLayout.for_repo(REPO_ROOT))`; 630-631 and 673-674 scan workers and `scan_cache_file(REPO_ROOT)`; 1023, 1047 `repo_root=REPO_ROOT`; 1181-1182 `ImportDialog(REPO_ROOT, RepoLayout.for_repo(REPO_ROOT), ...)`; 1225 `AtomicCheckDialog`; 1266 `MigrationDialog(REPO_ROOT, ...)`; 1380 `checkout_mismatch(REPO_ROOT, config_base=CHECKOUT_CONFIG_BASE)`; 1501 `sync_kicad_path_vars(REPO_ROOT, ...)`; 1586 `sync_kicad_chooser(REPO_ROOT, ...)`. Delete the constant at line 46. Keep the five injection constants (`IMPORT_CORE`, `IMPORT_BACKUP_ROOT`, `ATOMIC_BACKUP_ROOT`, `CHECKOUT_CONFIG_BASE`, `MIGRATION_CORE`, lines 49-57). `main_window.py:1324` is a literal-sweep site.

D-26 check to keep, with the app folder replaced by the library folder (lines 1371-1392):
```python
        mismatch = checkout_mismatch(REPO_ROOT, config_base=CHECKOUT_CONFIG_BASE)
        if mismatch is None:
            if after == "generate":
                self._checkout_banner.hide()
            return None
        text = wrong_checkout_warning(mismatch)
        self._log_issues([Issue(Severity.WARNING, CHECKOUT_MISMATCH, text)])
```
Log routing: messages go through `self._log_issues(issues)`; severity is decided from `Severity`, and legacy string phrases (`Warning:`, `removed`, `Failed`, `Could not`, `not found`) are contracts. No new `QMessageBox`; the existing `self._question(...)` / `_confirm_path_var_changes` are the sanctioned confirms.

Menu build site: `_build_menu` at line 291. Add the four new actions at the top of File, above Import Part. Double every `&` in displayed menu text only; keep the real path in `data()` and tooltip (Pitfall 12). Open in Explorer: `QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))`.

---

### `kicad_lib_manager/widgets/choose_folder_dialog.py`, `new_collection_dialog.py`, `first_run_dialog.py` (components)

**Analog:** `widgets/backup_dialog.py` (lines 1-50) for dialog skeleton, folder row with `Browse...`, and `QDialogButtonBox` with renamed buttons; `TaskWorker` (`widgets/import_dialog.py:343-365`) for the off-thread check; `ElidedLabel` (`widgets/import_result.py:26`) for every long path; `centre_window` (`import_dialog.py:195`).

Dialog skeleton and folder row (backup_dialog.py:13-36):
```python
class BackupDialog(QDialog):
    def __init__(self, default_folder: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Backup")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit(default_folder)
        folder_row.addWidget(self._folder_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
```
Button box with renamed buttons (backup_dialog.py:41-47):
```python
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Restore")
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
```
Rules from UI-SPEC and project conventions: no `Cancel` text (use `Keep Current Folder` / `Back to Setup` / `Back to Choose`), `setAutoDefault(False)` on every button, 300 ms `QTimer` debounce plus a request counter so a stale check result is ignored, `blockSignals` pairs, `PRIMARY_BUTTON_QSS` from `widgets/theme.py` on `Use This Folder` and `Create Collection` only, widgets take `parent=None` and call `super().__init__(parent)`, Qt enums fully qualified, set `Qt.TextFormat.PlainText` on path labels. Window-modal over the main window via `dialog.open()` (see how `AtomicCheckDialog` is opened, `main_window.py:~1223-1229`); the first-run window is the only application-modal one. Keep each file small (`import_dialog.py` is 3615 lines). Import cycle risk: if `ElidedLabel` import from `import_result` creates a cycle, move it to its own `widgets/` module (UI-SPEC).

---

### Literal `"Custom"` sweep (utility, constants)

**Analog:** the one place already deriving from layout, `importer/commit_plan.py` (`custom_rel` from the layout, not a literal), and `layout.py:24`. Replace each exact string constant equal to `"Custom"` or starting with `"Custom/"` with `collection.OWN_DIR` / `collection.SYMBOLS_DIR` etc. Sites (RESEARCH Inventory 3): `atomic_check.py` 433, 528, 665; `atomic_fixes.py` 27, 28, 29; `changes.py` 25; `importer/commit_gate.py` 541; `importer/commit_step.py` 697, 872; `importer/incoming.py` 38; `importer/layout.py` 24; `importer/migration/gate.py` 25, 80, 215; `importer/migration/inventory.py` 307; `importer/planner.py` 911; `library_scanner.py` 557, 600, 914 (and f-string at 274); `main_window.py` 1324; `scan_cache.py` 43, 44, 174.

Layering edits this forces (`tests/test_layering.py` `ALLOWED`, lines 14-37): add `"collection": {"models", "fsutil", "gitops"}`, `"procs": set()`, add `"collection"` to `atomic_check`, `atomic_fixes`, `changes`, `library_scanner`, `scan_cache`; `"gitops": {"models", "procs"}`; `"kicad_process": {"procs"}`; extend the `_CODE` import list (lines 40-50) with `kicad_lib_manager.collection, kicad_lib_manager.procs` (the Qt-free proof). Same for `tests/test_importer_layering.py` entries for `importer.layout`, `importer.incoming`, `importer.commit_gate`, `importer.commit_step`, `importer.migration.gate`, `importer.kicad_cli`. New AST test: use the `_custom_literals` walk from RESEARCH "Layering test for the literal" (it covers the `/Custom` f-string piece).

---

### Tests (new)

**Main-window harness analog:** `tests/test_main_window.py:70-115`. The factory currently does:
```python
        monkeypatch.setattr(main_window, "REPO_ROOT", repo)
        monkeypatch.setattr(main_window, "CHECKOUT_CONFIG_BASE", config_base)
        monkeypatch.setattr(main_window, "load_kicad_fp_dir", lambda: fp_dir)
        monkeypatch.setattr(main_window, "scan_all", fake_scan)
        monkeypatch.setattr(main_window, "sync_kicad_path_vars", fake_sync)
        ...
        w = main_window.MainWindow()
        qtbot.addWidget(w)
        if wait:
            qtbot.waitUntil(lambda: w._worker is None, timeout=5000)
```
Change the `REPO_ROOT` setattr and `MainWindow()` to `main_window.MainWindow(repo)` in the five harness files: `tests/test_main_window.py:78`, `test_main_window_chooser.py:102`, `test_main_window_import.py:97`, `test_main_window_migration.py:152`, `test_checkout_warning.py:84`. Do not touch the ~385 other `REPO_ROOT` matches in `tests/` (per-file constants). Reuse the fixture's `fake_question` / `make.answer` / `make.questions` and the `make.running` fake for the KiCad-open check in `test_main_window_root.py`.

**Git tripwire (must respect):** `tests/conftest.py:129-131` fails any non-slow test whose argv command is `init` or `clone`:
```python
        if command in ("init", "clone"):
            return f"git {command}"
```
So any test that really runs `create_collection` is `@pytest.mark.slow` (use `tests/gitfixtures.py` helpers and `remove_tree`); quick tests inject a recording `GitContext.runner` (a fake that never reaches `Popen`). `tests/test_gitops.py`: add `"init"` to `EXPECTED_ALLOWED` (line 26); `test_allow_list_is_exact_and_safe` (line 66) stays exact; `:366` asserts `argv[6]` is allow-listed. The slow end-to-end test template is RESEARCH Inventory 8 (`build_plan` -> `apply_plan` -> `build_commit_plan` -> `probe_commit` -> `run_commit` on `downloaded_examples/ul_CSD85301Q2.zip`, set `GIT_AUTHOR_*` / `GIT_COMMITTER_*` with `monkeypatch.setenv`; conftest isolation gives an empty HOME with no identity).

## Shared Patterns

### Qt-free service returning `Issue` lists
**Source:** `kicad_lib_manager/gitops.py:74-85` (`find_git`), `kicad_setup.py:288-305`
**Apply to:** `collection.py`, `procs` callers, `startup.py` helpers
Return `Issue(Severity.X, "area.code", text)` or `list[Issue]`; never raise for user-facing failures; `MainWindow` routes to `self._log_issues(...)`. Read helpers return `None` on failure.

### Off-thread work
**Source:** `widgets/import_dialog.py:343-365` (`TaskWorker`) and `main_window.py:1473-1500`
**Apply to:** Choose dialog check, New Collection check and create, one-click switches, startup folder check (the startup check has no event loop yet: use a `daemon=True` thread joined with about 5 s timeout, not `ThreadPoolExecutor`).

### Untrusted stored values
**Source:** `settings.py:64-72, 94-100`
**Apply to:** `library/root`, `library/recent`, `KICAD_LIBMGR_ROOT`, `--library-root`
Re-run `check_folder` on every use; display filters to existing folders, the saved list is never rewritten by a display.

### Same-folder comparison
**Source:** `kicad_setup.py:233-242` (`same_folder`)
**Apply to:** D-26 check, Use KiCad's Folder enabled state, "already using this folder", recent-list dedupe key (`normcase(normpath)`), path-variable refusal (`_norm_path` in `library_scanner`).

### Safe writes
**Source:** `kicad_lib_manager/fsutil.py` (`atomic_write_text`, `atomic_write_bytes`, `backup_file`)
**Apply to:** any KiCad config write. The new collection's files are all new inside a fresh folder, so plain writes are acceptable but cleanup on failure must remove only what was created, tolerating read-only `.git` entries.

### Python 3.10 grammar gate
**Source:** `tests/test_annotations_resolve.py`
**Apply to:** every new module and `kicad_lib_manager.py`: no PEP 695, no `except A, B:`, no nested same-quote f-strings; `X | None` annotations are fine.

### Naming / style
`snake_case` modules, `_private` helpers, `UPPER_SNAKE` module constants, event handlers `_on_<event>`, widget attributes `self._<name>`, one-line triple-double-quoted docstrings for public functions, 4-space indent, double quotes, comments above the code.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `startup.py` first-run hand-off (resolve before `MainWindow`, held notes flushed into `LogPanel`) | entry | request-response | No existing pre-window startup flow; `main()` just builds the window. Use RESEARCH Pattern 1 and the System Architecture Diagram. |
| `QStackedLayout` empty-collection page | component | - | No existing stacked page in `main_window.py`; build per UI-SPEC "Empty collection". |
| Library-folder row / `Change Folder...` / source tag | component | - | No existing row above the toolbar; closest layout analog is the toolbar row built in `_build_ui` (line 392) and `ElidedLabel`. |
| `validate_collection_name` (Windows reserved names) | utility | transform | No existing name validator in the package; use the Microsoft rules in RESEARCH Pitfall 6. |

## Metadata

**Analog search scope:** `kicad_lib_manager/` (package, `importer/`, `widgets/`), `kicad_lib_manager.py`, `tests/` (conftest, layering, gitops, main_window harness)
**Files scanned:** about 30 read or grepped
**Pattern extraction date:** 2026-11-23
