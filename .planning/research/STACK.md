# Stack Research — v3.0 Public Library Manager

**Domain:** turning a personal PySide6 desktop app (Python 3.14, stdlib + PySide6 only) into a public, installable Windows app that manages an external KiCad library collection
**Researched:** 2026-11-22
**Scope:** only what is NEW for v3.0. The existing validated stack (Python 3.14.4, PySide6 6.12.0, stdlib S-expression layer, subprocess git runner, pytest 9.1.1 + pytest-qt 4.5.0) is not re-researched.
**Overall confidence:** MEDIUM-HIGH. Versions were checked against PyPI / release pages on 2026-11-22. Three things were also measured on this machine (xdist run, PyInstaller build, Nuitka build; see "Measured on this machine"). Items marked UNVERIFIED were not confirmed.

## Headline decisions

| Decision | Recommendation | Confidence |
|----------|----------------|------------|
| Test parallelism | `pytest-xdist==3.8.0`, `-n 6..8` (not `auto`), plus `pytest-timeout==2.4.0` as a CI safety net. No `pytest-randomly`. | HIGH (ran on this suite) |
| Freeze tool | **PyInstaller 6.22.3, onedir** (not onefile), built from a committed `.spec`. Nuitka 4.3.5 works too and is the fallback if antivirus flags the build. | MEDIUM-HIGH |
| Installer | **NSIS 3.13** (3.12 is installed locally; either works), per-user install, Git check in `.onInit`, no bundled Git. | HIGH |
| Packaging metadata | `pyproject.toml` with **hatchling**, `requires-python = ">=3.14"`, `[project.gui-scripts]`, PEP 735 `[dependency-groups]`. Keep the flat layout. | HIGH |
| Catalog git operations | **Keep subprocess git.** No GitPython, pygit2 or dulwich. Add a second, separate network allow-list module. | HIGH |
| Catalog storage | Plain `git clone` into the collection + a committed JSON manifest (URL, branch, pinned commit). Not submodules. | MEDIUM (architecture call) |
| Repo split | Keep the existing repo and its history as the public tool repo; create the library collection as a fresh repo. `git-filter-repo 2.47.0` only to scrub history. | MEDIUM-HIGH |
| New runtime dependencies | **None** (stdlib `urllib`, `json`, `winreg`, `subprocess` cover everything). | HIGH |

## Recommended Stack

### Core Technologies (new for v3.0)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pytest-xdist | 3.8.0 (2025-06-30, latest on PyPI/GitHub; `requires_python>=3.9`; depends on `execnet>=2.1`, `pytest>=7`) | Run the 9689-test suite in parallel workers | Pure Python, one dependency (execnet 2.1.2). PyPI classifiers stop at 3.13 but it ran cleanly on Python 3.14.4 + PySide6 6.12.0 + pytest-qt 4.5.0 here (266 tests, `-n 8`, all passed). |
| pytest-timeout | 2.4.0 (2025-05-05; classifiers stop at 3.13, pure Python) | Fail a hung test instead of hanging CI | The suite joins QThreads with `thread.wait(60000)`. A deadlocked worker would otherwise hold a CI job for hours. Pin 2.4.0: **2.5.0 (2026-08-16) was yanked** ("accidental breaking change"). Never loosened to `>=`. |
| PyInstaller | 6.22.3 (2026-09-12; `requires_python <3.16,>=3.8`; Python 3.14 support since 6.15.0, 2025-08-03) | Freeze the app to a onedir folder | Built this app on Python 3.14.4 + PySide6 6.12.0 in 66 s, 123 MB, started and stayed alive. Built-in `hook-PySide6` / `hook-shiboken6`. Licence is GPL-2.0+ with a bootloader exception that allows any licence for the frozen output. |
| NSIS | 3.13 (2026-09-27; Chocolatey package `nsis` 3.13.0). 3.12 (Apr 2026) is what is installed locally. | Windows installer / uninstaller | Tiny (1.6 MB), scriptable, already installed on the dev machine, free, no runtime. Supports Unicode, LZMA solid compression, per-user execution level. |
| hatchling | current (build-system only) | `pyproject.toml` build backend | One-line wheel config for a flat layout (`packages = ["kicad_lib_manager"]`) and a version read from a file. setuptools' auto-discovery fails on this repo (many top-level folders: `tests`, `Custom`, `reports`, ...), hatchling needs no discovery rules. Only used for `pip install -e .` / building a wheel; the installer is the distribution channel. |
| git (CLI, already required) | >= 2.25 enforced today (`MIN_GIT_VERSION`); dev machine 2.49.0; runner image has 2.56.1 | Catalog clone / fetch / update | Already a hard dependency; the NSIS check makes it a declared one. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| filelock | latest (pure Python; it is xdist's own `testing` extra) | Build the shared git "template repo" once across xdist workers | Dev dependency only. The xdist docs' recommended one-time-setup pattern (`tmp_path_factory.getbasetemp().parent` + `FileLock`). Without it every worker rebuilds both template variants (autocrlf on/off) at several seconds each. Stdlib alternative: an `os.mkdir` lock dir, but `filelock` is clearer. |
| git-filter-repo | 2.47.0 (2024-12-04; single Python script, `requires_python>=3.6`; still the latest release) | One-off history scrub when splitting repos | Developer tool, not an app dependency. Install with `pipx install git-filter-repo` (recommended by its INSTALL.md) or `pip install git-filter-repo`. Not installed here today (`git filter-repo` is not a git command). On Windows, if the shebang fails run `python git-filter-repo ...`. |
| stdlib `urllib.request` | 3.14 | Fetch the curated catalog JSON and optional GitHub metadata | In a QThread worker, Qt-free, easily faked in tests. Always send a `User-Agent` (GitHub rejects requests without one). |
| stdlib `winreg` | 3.14 | Locate Git for Windows when it is not on PATH | Same lookup order as the installer (see Git detection). Guard with `sys.platform == "win32"`. |
| stdlib `tomllib` | 3.14 (read-only) | Optional | Only if the curated list or manifest is TOML. It cannot write, so the writable manifest is JSON. |
| pyinstaller-hooks-contrib | 2026.10 (pulled in by PyInstaller) | Extra hooks | Comes with PyInstaller; pin it indirectly through the build group. |

### Development / Build Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub Actions `windows-latest` (Windows Server 2025, image 20261116.335.1 at time of check) | Test on PR; build installer on tag | Image has Python 3.14.10 in the tool cache, Git 2.56.1, Inno Setup 6.7.1, WiX 3.14. **NSIS is not preinstalled**: `choco install nsis --version 3.13.0 -y` (Chocolatey on the image: UNVERIFIED, expected). |
| `gh` CLI (preinstalled on runners) | Upload the installer to the GitHub Release | Use `gh release create/upload` with `permissions: contents: write` instead of a third-party action. |
| SignPath Foundation or Azure Artifact Signing | Code signing | Deferred, see Code signing. Ship unsigned first, make signing a drop-in CI step. |
| Windows Defender CLI `MpCmdRun.exe -Scan -ScanType 3 -File <dir>` | Local antivirus check of a build | Both test builds scanned clean here (see Measured). |

## Measured on this machine (2026-11-22, Windows 11, Python 3.14.4, PySide6 6.12.0, 16 logical cores)

All experiments ran from a scratch directory (`--target` installs, `PYTHONPATH`), nothing was added to the project `env/`.

| Experiment | Result |
|------------|--------|
| xdist smoke: `test_gitops`, `test_commit_gate`, `test_commit_step`, `test_commit_plan`, `test_atomic_scan` with `-n 8 -p no:randomly` | 266 passed in 133 s. Session guard `_live_custom_untouched` and the offscreen `QApplication` worked per worker. pytest 9.2.0 was used (pip resolved it in the scratch dir); pytest 9.1.1 is the project pin and xdist only needs `>=7`. |
| Serial `test_commit_step.py` (git-heavy) | 123 passed in 295 s (about 2.4 s per test, slowest 8.5 s). Under `-n 8` the same tests took up to 14 s each: parallel git processes on Windows contend (process creation, file system, Defender real-time scanning). **Do not expect a linear 8x.** Not a like-for-like comparison (different file sets); a proper before/after needs the first phase task to run `--durations`. |
| PyInstaller 6.22.3 onedir, `--windowed`, default hooks, no excludes | 66 s build, `KLM.exe` + `_internal/` = **123 MB**; PySide6 folder 96 MB (includes `Qt6Quick`, `Qt6Qml`, `Qt6Pdf`, `Qt6Svg`, `Qt6VirtualKeyboard`, 19.7 MB `opengl32sw.dll`). LZMA zip of the folder = **38 MB** (about the installer size). Process started offscreen and stayed alive 8 s. No QtWebEngine in the bundle. |
| Nuitka 4.3.5 standalone, `--enable-plugin=pyside6`, MSVC 14.3 (VS Build Tools 2022 present, no download needed) | 5 min 11 s cold build (8 jobs, 91 C files, empty cache), `.dist` folder = **84 MB**, started offscreen and stayed alive 8 s. Smaller than PyInstaller out of the box because it only ships the Qt modules the app imports. |
| Windows Defender custom scan of both unsigned output folders | "found no threats" for both. One data point on one machine; VirusTotal was NOT run. |

Smoke level only: neither build was exercised through the GUI (dialogs, git commit, import). A real freeze acceptance test is a phase task.

## PyInstaller vs Nuitka (decision)

| Criterion | PyInstaller 6.22.3 | Nuitka 4.3.5 |
|-----------|--------------------|--------------|
| Python 3.14 | Supported since 6.15.0; 6.22.x is current | Officially supported since 4.2 (2026-08-24); 4.3 adds more 3.14 fixes |
| PySide6 6.12 | Works (measured). Hook in core PyInstaller. | Works (measured). Built-in `pyside6` plugin; it is the backend of Qt's own `pyside6-deploy`. |
| Build time / CI cost | 66 s | 311 s cold (cache helps). Needs a C compiler; runner has MSVC. |
| Bundle size (as built) | 123 MB (38 MB compressed) | 84 MB |
| Startup time | Not measured. onedir has no extraction step. | Not measured. Compiled code, expected comparable or faster. |
| Antivirus | Prebuilt bootloader is a known false-positive magnet (anecdotal). Mitigation: onedir, no UPX, signing, optionally `pip install pyinstaller --no-binary` to build the bootloader. | Anecdotally fewer detections but not immune (a Qt forum thread reports Defender flagging a pyside6-deploy/Nuitka build, and onefile is flagged for both). Evidence on both sides is anecdotal: LOW. |
| Licence of the tool | GPL-2.0+ with bootloader exception; output may be under any licence. | AGPL-3.0 with a runtime exception for compiled output (wording not verified from the official LICENSE; MEDIUM). Commercial plugins are optional and not needed. |
| Debuggability / ecosystem | Largest user base, hook ecosystem, easy `--debug` | Compiler errors are less friendly; fewer Stack Overflow answers |

**Recommendation: PyInstaller, onedir, for v3.0.** It builds in about a minute, the iteration loop matters while freeze-specific bugs are being found (see Integration gotchas), and onedir keeps Qt as replaceable DLLs on disk, which is the cleanest way to meet the LGPL. Add a one-time VirusTotal + Defender check of the signed installer; **if the build is flagged and signing does not clear it, switch the `build` job to Nuitka standalone** (the NSIS script only needs a different source folder). Do not use onefile with either tool: it extracts to `%TEMP%` on every launch and is the mode most often flagged.

**Do not trim Qt by hand-deleting DLLs.** If the 123 MB matters, use `--exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf --exclude-module PySide6.QtVirtualKeyboard` in the spec and re-test; leave `Qt6Svg` and the imageformats/iconengines plugins. 38 MB installer is acceptable; defer.

### LGPL / licensing of PySide6 in a frozen app

- PySide6 and Qt are LGPL-3.0 (or GPL / commercial). Using the LGPL option is fine for an app of any licence.
- Obligations (not legal advice): ship the LGPL-3.0 text and a notice that the app uses Qt/PySide6 under LGPLv3; keep Qt as separately replaceable libraries (onedir does this; onefile is a grey area); give the user a way to get the corresponding Qt source (a written offer or a pointer the maintainers control; the Qt mailing list view is that a link to the Qt Project's own source page is not enough if you do not control it).
- Practical: put `licenses/LGPL-3.0.txt` and a `THIRD-PARTY-NOTICES.txt` (PySide6, Qt, Python, PyInstaller bootloader) next to the exe, show them in Help > About, and say in the README where the Qt source can be obtained (the tool repo can mirror the `pyside-setup`/Qt source tarball reference for 6.12.0).
- Choose the tool repo's own licence before the first public release. SignPath Foundation also requires an OSI-approved licence (see Code signing).
- Source for this section is a mix of the PyInstaller licence page (HIGH) and Qt forum / mailing-list threads (LOW). Re-verify with Qt's official LGPL compliance page in the packaging phase.

## NSIS installer details

**Install scope: per-user.** `RequestExecutionLevel user`, `InstallDir "$LOCALAPPDATA\Programs\KiCad Library Manager"`, uninstall entry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\KiCadLibraryManager`. Reasons: no UAC prompt, the app only touches per-user things (`%APPDATA%\KiCadExtLibManager`, the user's KiCad config, the user's library folder), and a per-user install can self-update later. Skip `MultiUser.nsh` (all-users mode) for v3.0.

**Git detection (installer, `.onInit` or a pre-install page), in this order:**

1. `SetRegView 64`; `ReadRegStr $0 HKLM "SOFTWARE\GitForWindows" "InstallPath"`, then the same under `HKCU "Software\GitForWindows"` (per-user Git installs write HKCU). Git for Windows writes these values since 2.6.1; `InstallPath` is the base folder (for example `C:\Program Files\Git`).
2. If found, `IfFileExists "$0\cmd\git.exe"`.
3. Fallback: `nsExec::ExecToStack 'git --version'` (PATH lookup) and check the exit code and the text starts with `git version`.
4. Not found: `MessageBox MB_YESNOCANCEL` offering to open the download page with `ExecShell "open" "https://git-scm.com/download/win"` (mention `winget install --id Git.Git -e` in the text), and let the user **continue anyway**. Git is a soft requirement for the installer (the app shows its own "git not found" state at runtime and everything non-git still works). In silent mode (`IfSilent`) skip the prompt and just log.
5. Do **not** bundle the Git installer (50+ MB, goes stale). Do not auto-download it.

**App-side mirror (stdlib):** `find_git` today is `shutil.which("git")`. Add the same registry fallback (`winreg`, HKLM then HKCU, then `<InstallPath>\cmd\git.exe`). Reason: an app started from the installer's "Run" checkbox or Explorer right after Git was installed has a stale PATH and would report "git not found" until the user signs out. Keep the existing refusal of a git found inside the library folder.

**Uninstaller:** `WriteUninstaller "$INSTDIR\Uninstall.exe"`; write `DisplayName`, `DisplayVersion`, `Publisher`, `UninstallString`, `QuietUninstallString`, `DisplayIcon`, `EstimatedSize`, `NoModify=1`, `NoRepair=1`. Remove the install folder, Start Menu / desktop shortcuts, the HKCU key. **Never delete the user's library folder.** Ask (default No) before deleting `%APPDATA%\KiCadExtLibManager` (settings, saved scan, backups).

**Upgrades:** the PyInstaller folder is not additive; stale DLLs in `_internal` cause import errors. Before copying, run the previous uninstaller silently or `RMDir /r "$INSTDIR\_internal"`, then install. Pass the version in from `pyproject` (`makensis /DAPP_VERSION=3.0.0 installer.nsi`).

**Other:** `Unicode true`; MUI2 with a licence page showing the app licence and the LGPL notice; `SetCompressor /SOLID lzma`; embed `VIProductVersion` for Explorer details. Bump `MIN_GIT_VERSION` messaging in the installer text (2.25).

## Code signing (deferred, drop-in)

| Option | Cost | Fit | Confidence |
|--------|------|-----|------------|
| Unsigned first release | free | Works; users see SmartScreen "unknown publisher" and click More info > Run anyway. Document it in the README. | HIGH |
| SignPath Foundation | free for OSI-licensed open source | Needs a public repo, an OSI licence, **a previous release**, MFA on GitHub and SignPath, signs from GitHub Actions. Certificate names "SignPath Foundation" as publisher; releases must carry "Free code signing provided by SignPath.io, certificate by SignPath Foundation". No proprietary components allowed. Approval is not automatic. | MEDIUM |
| Azure Artifact Signing (formerly Trusted Signing; GA announced 2026-01-12) | paid (price UNVERIFIED) | One secondary source (Feb 2026) says Public Trust for individuals was limited to US and Canada. Check Microsoft's current eligibility before relying on it. | LOW-MEDIUM |
| Classic OV / EV certificate | paid | Overkill for a personal open-source tool. | HIGH |

Plan: first public release unsigned (also satisfies SignPath's "prior release" rule), then apply to SignPath and add a signing step for `KLM.exe`, `Uninstall.exe` and the installer.

## pyproject.toml layout

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kicad-lib-manager"
dynamic = ["version"]
description = "Manage and import KiCad libraries"
readme = "README.md"
requires-python = ">=3.14"
license = "MIT"                       # SPDX expression (PEP 639); choose the real licence before release
license-files = ["LICENSE", "THIRD-PARTY-NOTICES.txt"]
dependencies = ["PySide6-Essentials==6.12.0"]   # see note below

[project.gui-scripts]                 # Windows: no console window
kicad-lib-manager = "kicad_lib_manager.app:main"

[dependency-groups]                   # PEP 735
dev   = ["pytest==9.1.1", "pytest-qt==4.5.0", "pytest-xdist==3.8.0", "pytest-timeout==2.4.0", "filelock"]
build = ["pyinstaller==6.22.3"]

[tool.hatch.version]
path = "kicad_lib_manager/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["kicad_lib_manager"]

[tool.pytest.ini_options]
# existing block stays; add:
#   addopts = "-ra --strict-markers"   (unchanged)
#   timeout = 300, markers += "slow: ..."
```

Notes:
- **Keep the flat layout.** Moving to `src/` would break `pythonpath = ["."]`, `REPO_ROOT` in tests and thousands of path assumptions for no benefit.
- **Entry point lives in the package.** Today the entry script is the root `kicad_lib_manager.py`, which has the same name as the package (the package wins on import, so the script can only be run, never imported). Move `main()` into `kicad_lib_manager/app.py`; keep the root script as a 3-line shim that PyInstaller uses as its entry (it worked as-is in the test build).
- **Single version source:** `kicad_lib_manager/_version.py` with `__version__`. Use it for the About dialog, NSIS `/DAPP_VERSION`, and the frozen build. `importlib.metadata` does not work in a frozen app without dist-info.
- `PySide6-Essentials` instead of the `PySide6` meta package: the app imports only `QtCore`, `QtGui`, `QtWidgets`. The meta package drags in Addons (the dev venv currently also holds `pyside6_webengine` and `pyside6_pdf`). Essentials is the same wheel family and version (6.12.0 installed as a dependency of PySide6 here). **UNVERIFIED in this repo:** run the suite once against an Essentials-only venv before switching. Keep `qt_api = "pyside6"`.
- `pip install --group dev` needs pip >= 25.1 (venv has pip 26.0.1). Keep `requirements.txt` as a one-line generated file only if CLAUDE.md-style docs still reference it; otherwise delete it and document `pip install -e . --group dev`.
- `requires-python = ">=3.14"` is a declaration of what is supported and tested, not a code requirement today (the code is 3.10+ syntax). Add a one-line guard in `app.main()` that shows a clear message on older Python, and say it in README.
- `[project.scripts]` would open a console window on Windows; use `gui-scripts`.

## Test-suite speed-up (feature 1) — stack specifics

**Install:** `pytest-xdist==3.8.0`, `pytest-timeout==2.4.0`, `filelock` (dev group).

**Run:** `pytest -n 6 --dist=worksteal -m "not slow"` locally; `-n auto` in CI (public-repo Windows runners have about 4 vCPU: MEDIUM). On the 16-core dev box start at 6 to 8: more workers hit the git/process contention measured above. `-n 0` disables distribution when debugging.

**How xdist interacts with the existing fixtures:**

| Existing piece | Under xdist | Action |
|----------------|-------------|--------|
| `_live_custom_untouched` (session, autouse) | Runs **once per worker**, not once per run: each worker digests `Custom/` at its own start and end and fails its own teardown. It worked in the smoke run. Cost is the digest of 20 MB per worker. A worker's failure is reported as an error on that worker. | Keep. But after the repo split `Custom/` is no longer in the tool repo and the guard becomes a no-op (it already does nothing when `Custom/` is absent). Re-point it at whatever live library folder the app would default to (KICAD_LIB_GITHUB) or delete it deliberately. |
| `gitfixtures._templates` + `_template()` (module dict, `tempfile.mkdtemp`) | Per process, so **every worker builds both variants** (autocrlf True/False, several seconds each) and leaks the folders. | Build once under a `FileLock` in `tmp_path_factory.getbasetemp().parent` (xdist's documented one-time-setup pattern), `copytree` per test as now. Delete the mkdtemp folders in teardown. |
| `_build()` uses `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, per-root gitconfig | Safe: no shared global state, each test has its own root. | None. |
| `QT_QPA_PLATFORM=offscreen` forced at conftest import | One `QApplication` per worker process; fine (pytest-qt 4.5.0 ran). | None. |
| `pytest_runtest_teardown` hook joining QThreads | Per worker; unaffected. | Keep; `pytest-timeout` is the backstop if a thread never finishes. |
| Module-level state (`main_window.REPO_ROOT`, caches, `lru_cache` code signature) | Isolated per worker process, which hides order dependence. | Fine for speed. Do not add `pytest-randomly` on top. |
| Tests that touch real KiCad config (`local_kicad`) and `kicad_cli` | Opt-in / skip-with-reason already. | Keep them out of the default xdist run or run them in a separate serial job. |

**`slow` marker:** register in `[tool.pytest.ini_options].markers` (`--strict-markers` is already on, so an unregistered marker fails collection). Generate the list from `--durations=40 --durations-min=2.0` output, mark those, and default local runs to `-m "not slow"`; CI runs the full suite on a schedule or before a release tag, the fast subset on every push.

**Bigger lever than xdist:** the cost is git processes, not Python. Per-test `copytree` of a template superproject plus several git calls costs about 2.4 s on Windows. Cut the number of tests that need a real repo (use the runner's existing fake `GitContext.runner` seam for logic tests), keep real-git tests for the integration layer. Excluding the pytest base temp directory from Defender real-time scanning on the dev box is a likely win but was **not measured**.

## Catalog git operations (feature 4)

**Decision: stay on subprocess `git`.**

| Option | Verdict | Why |
|--------|---------|-----|
| subprocess `git` (current) | **Use** | Git is a declared installer prerequisite anyway. Credential helpers (Git Credential Manager ships with Git for Windows), proxy settings, `core.longpaths`, `autocrlf`, hooks and SSH config all come free. The existing `gitops.run_git` has argv discipline, env scrubbing, `CREATE_NO_WINDOW`, timeouts and a test seam. Zero new packaging weight. |
| dulwich (pure Python; 1.2.21 has cp314 Windows wheels; `porcelain.clone(..., progress=...)`) | No | Removes the Git prerequisite but then credentials, submodules, long paths and line-ending handling are your problem. The app commits through real git anyway. |
| pygit2 (libgit2 binding) | No | Native wheel (adds MB to the frozen build, 3.14 wheel availability UNVERIFIED), credential callbacks must be rewritten to reach GCM. |
| GitPython | No | Shells out to git anyway, so it adds a dependency and an abstraction with no benefit. |

**Keep the current safety property.** `gitops.ALLOWED_SUBCOMMANDS` deliberately holds nothing that talks to another repository, and the app never pushes. Do not weaken it. Add a **separate module** (for example `gitnet.py`) with its own allow-list `{clone, fetch, ls-remote, merge, reset, rev-parse}` and no `push`/`pull` (use `fetch` + `merge --ff-only`). Reuse `_env()` and `find_git`.

**Clone recipe (all arguments built by code, never typed text):**

```
git -c core.longpaths=true -c core.autocrlf=false -c protocol.ext.allow=never \
    clone --progress --depth 1 --single-branch -- <https-url> <dest>
```

- Validate the URL before anything runs: `https://github.com/<owner>/<repo>[.git]` for the curated list; "Add by URL" accepts https only, rejects `ext::`, `file:`, `-`-leading values, and always passes `--` before the URL. Do not use `--recurse-submodules` for third-party repos.
- `core.longpaths=true`: KiCad libraries with 3D models hit the 260-character Windows path limit. `core.autocrlf=false`: third-party `.kicad_sym` / `.kicad_mod` line endings must not be rewritten (the repo already has autocrlf tests for this reason).
- **Progress:** use `subprocess.Popen` in a QThread (not `run`), read stderr incrementally and split on `\r` and `\n`; parse `Receiving objects:  42% (123/456), 1.2 MiB | 2.1 MiB/s` with one regex; emit a Qt signal. `--progress` is required because stderr is not a TTY. Cancel with `terminate()` then remove the partial folder.
- **Update:** `git fetch --depth 1 origin <branch>` then `git merge --ff-only FETCH_HEAD` (or `reset --hard FETCH_HEAD` for untouched clones). "Update available" check: `git ls-remote origin HEAD` compared with local `HEAD`. Shallow is fine for read-only third-party libraries; offer "full history" as an option only if asked for.
- **Remove:** `shutil.rmtree(path, onexc=_clear_readonly)` (git object files are read-only on Windows; `onexc` exists since Python 3.12).
- Timeouts: network operations need minutes, not the 30 s default; use a separate constant and keep the cancel button live.

**Plain clones + manifest vs submodules (decision: plain clones + manifest):**

| Concern | Plain clone + `libraries.json` | Submodule per library |
|---------|--------------------------------|-----------------------|
| One-click add | `git clone` then one manifest line | `git submodule add` edits `.gitmodules` and index; needs a superproject commit to be consistent |
| Remove | delete folder + manifest line | `deinit`, `git rm`, delete `.git/modules/...`; easy to leave junk |
| Update | `fetch` + `merge --ff-only` in the clone | update + stage the new pointer + commit in the superproject |
| Reproducibility | manifest records URL, branch and pinned commit; "Restore libraries" re-clones on a new PC | pointer in the superproject (built in) |
| State the app must track | one JSON file | `.gitmodules`, gitlinks, `.git/modules` |
| Detached HEAD surprises | none | submodule is detached by default |

The scanner already treats any folder as a source (first path segment), so plain clones need no scanner change; the existing `WurthElektronik` submodule keeps working and can be migrated later or left as is (catalog should mark it "managed by submodule: update/remove disabled"). Git-ignore the clone folders in the collection repo and commit the manifest.

**Manifest and curated list:** JSON via stdlib. Ship the curated list as a data file inside the app (PyInstaller `datas` entry in the spec; read via a helper that handles `sys._MEIPASS` / `sys.frozen`) and optionally refresh it from the tool repo's raw URL with `urllib` (fallback to the bundled copy offline).

**GitHub API (unauthenticated):** `GET https://api.github.com/repos/{owner}/{repo}` returns description, `default_branch`, `pushed_at`, `archived`, `license.spdx_id`, `stargazers_count`. The limit is **60 requests/hour per IP** (shared with everyone behind the same NAT). Verdict: **useful but not required.** Put the display metadata (name, description, licence, tags, branch) in the curated JSON so the catalog works offline and costs zero API calls; use the API only for "Add by URL" enrichment (one call per added repo) and cache the result with its `ETag`. Whether a 304 response is free against the unauthenticated limit: UNVERIFIED (the rate-limit page does not say). Always send `User-Agent` and `Accept: application/vnd.github+json`; surface a clear "rate limit reached, try later" message from `X-RateLimit-Remaining` / 403 / 429. Never require a token in v3.0.

## Repo split tooling (feature 3)

- Facts: this repo has 1584 commits, all by one author, pack size 6.76 MiB, 789 tracked files, two gitlinks (`Custom`, `WurthElektronik/KiCad-Library`). Custom and the Wurth library are separate repos already, so their history does not live here. The history here is code, tests and `.planning`.
- **Tool repo (public): keep this repository and its history** (rename it on GitHub; old URLs redirect). Remove the submodule paths with a normal commit, or scrub history with `git filter-repo --invert-paths --path Custom --path WurthElektronik --path .gitmodules` if the private library URL in `.gitmodules` history must not be public. Run on a **fresh clone**, never on the working repo (filter-repo removes `origin` and rewrites every hash).
- **Check before going public (from this repo's own state, not external research):** `downloaded_examples/ul_CSD85301Q2.zip` is a tracked vendor download (Phase 7 D-01/D-02 kept vendor files local "except the UL sample") and `tests/test_*` plus the `ul_package` fixture depend on it. Redistributing a licence-restricted vendor package publicly is a legal decision. Either replace it with a synthetic package or strip it with `git filter-repo --invert-paths --path downloaded_examples/ul_CSD85301Q2.zip` and update the tests. Also scan history for personal paths and `.planning` content the owner does not want public.
- **Collection repo (private): a fresh `git init`**, not a filter-repo derivative. Its content is `Custom` (still a submodule pointing at the existing `kicad_custom_library` repo, whose own history is untouched), the catalog manifest and `.gitignore`. Carrying over 1584 code commits would only add noise. If the superproject's pointer-bump history is wanted, `git filter-repo --path .gitmodules --path Custom --path WurthElektronik` on a second fresh clone yields it.
- filter-repo with gitlinks: expected to treat them as ordinary tree entries (UNVERIFIED here, the search found nothing on submodules); rehearse on a throwaway clone and diff `git ls-tree -r HEAD` before and after.
- Install filter-repo with `pipx install git-filter-repo`. `git filter-repo --version` is not available on this machine today.

## CI (GitHub Actions on `windows-latest`)

Two workflows, no third-party actions beyond `actions/checkout` and `actions/setup-python` (use the current major of each; version UNVERIFIED).

1. **`ci.yml`** on push/PR: `setup-python` 3.14, `pip install -e . --group dev`, `pytest -n auto -m "not slow" --timeout=300`. The `kicad_cli`, `local_kicad` and `wurth` tests already skip with a stated reason on a clean runner. Full suite on a nightly schedule.
2. **`release.yml`** on `push: tags: ['v*']`: checkout, setup-python 3.14, `pip install -e . --group build`, `choco install nsis --version 3.13.0 -y`, `pyinstaller kicad_lib_manager.spec`, a **frozen smoke test** (start `KLM.exe` with `QT_QPA_PLATFORM=offscreen`, assert it stays alive a few seconds; add a `--selftest` flag that imports the scanner and exits 0), `makensis /DAPP_VERSION=${tag#v} installer\installer.nsi`, compute `sha256` of the installer, `gh release create $tag KiCadLibManager-Setup-X.Y.Z.exe checksums.txt --generate-notes` with `permissions: contents: write`. Version consistency check: fail if the tag does not equal `_version.py`.

Runner image notes (checked): Windows Server 2025 image has Python 3.14.10 cached, Git 2.56.1, Inno Setup 6.7.1, no NSIS. Inno Setup being preinstalled (it is what Git for Windows itself uses) is a real alternative to NSIS if the NSIS step ever becomes annoying; the milestone has chosen NSIS, so do not switch without cause.

## Integration gotchas for the frozen app (must be handled, not stack choices)

| Gotcha | Where | Fix |
|--------|-------|-----|
| `REPO_ROOT = Path(__file__).parent.parent.resolve()` (module constant in `main_window.py`, used about 10 times and monkeypatched by tests) | Inside a freeze, `__file__` points into `_internal`. In v3.0 it must become the chosen library folder (KICAD_LIB_GITHUB default, else remembered in QSettings). | Replace the constant with a resolved "library root" provider, keep the monkeypatch seam name for tests. |
| `scan_cache._code_signature()` hashes the **`.py` sources** reachable from the scanner (`(package / name).read_bytes()`); returns `""` on `OSError` | A frozen build has no `.py` files, so the signature silently becomes `""` or fails. Behaviour of the saved-scan freshness check with `""` is unverified. | When `getattr(sys, "frozen", False)`, use `__version__` (+ build id) as the signature. Add a frozen-build test. |
| `__version__` | `importlib.metadata` fails frozen | `_version.py` as the single source |
| Data files (curated catalog JSON, licence texts, icon) | Not collected automatically | `datas=[...]` in the spec and a `resource_path()` helper using `sys._MEIPASS` |
| `--windowed` build: `sys.stdout` / `sys.stderr` are `None` | Any bare `print` or a library writing to stderr | The app already captures subprocess output; add a file logger under `%APPDATA%\KiCadExtLibManager\logs` for the frozen build |
| Qt picks the wrong PySide6 | Qt's PyInstaller guide warns it can pick a system PySide6/shiboken6 instead of the venv's | Build in a clean venv that has exactly the pinned PySide6 |
| `find_git` and PATH | see Git detection | `winreg` fallback |
| UPX | Raises antivirus detections | Do not install UPX on the build machine; set `upx=False` in the spec |

## Installation

```bash
# Dev (from the repo root, venv on Python 3.14)
py -m venv env
.\env\Scripts\python.exe -m pip install -e . --group dev

# Build the frozen app
.\env\Scripts\python.exe -m pip install --group build
.\env\Scripts\python.exe -m PyInstaller kicad_lib_manager.spec
"C:\Program Files (x86)\NSIS\makensis.exe" /DAPP_VERSION=3.0.0 installer\installer.nsi

# One-off tools (not project dependencies)
pipx install git-filter-repo
choco install nsis --version 3.13.0     # or the installer from nsis.sourceforge.io
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Parallel tests | pytest-xdist | `pytest-parallel`, hand-rolled `multiprocessing` | xdist is the maintained standard and works with pytest-qt |
| Test ordering | fixed order | pytest-randomly 5.1.0 | Shuffles 9689 tests that share module-level state; failures would be noise at this stage. Use once, ad hoc, as a diagnostic if coupling is suspected. Not installed by default (it also reseeds `random` globally). |
| Retries | none | pytest-rerunfailures | Would hide real git-fixture flakiness |
| Freeze | PyInstaller | Nuitka 4.3.5 | Works and is 39 MB smaller, but 5x slower to build; keep as the AV fallback |
| Freeze | PyInstaller | `pyside6-deploy` | It wraps Nuitka with a `pysidedeploy.spec`; less control, same trade-offs as Nuitka |
| Freeze | PyInstaller | cx_Freeze, py2exe, briefcase | Smaller communities, no advantage here |
| Installer | NSIS | Inno Setup 6.7.1 (preinstalled on runners, used by Git for Windows) | Equally capable; NSIS is the milestone's decision and is already installed locally |
| Installer | NSIS | MSI/WiX, MSIX | Heavier tooling and certificate requirements for a personal tool |
| Install scope | per-user | all-users (`MultiUser.nsh`) | UAC prompt and extra branches for no benefit |
| Build backend | hatchling | setuptools, uv_build, flit | setuptools needs explicit discovery rules in this multi-folder repo; the others add nothing |
| Git library | subprocess git | dulwich, pygit2, GitPython | See Catalog git operations |
| Catalog storage | plain clones + manifest | submodules | See the comparison table |
| Network client | stdlib `urllib` in a worker thread | `requests`, `QNetworkAccessManager` | One or two simple GET calls; `requests` adds a dependency, QtNetwork is already bundled but ties catalog logic to Qt and is harder to test headless |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyInstaller `--onefile` (or Nuitka `--onefile`) | Extracts to `%TEMP%` every launch, slower start, most often flagged by antivirus, grey area for LGPL relinking | onedir inside an NSIS installer |
| UPX compression | Raises false-positive rates | No UPX |
| pytest-timeout 2.5.0 | Yanked (2026-08-16) | 2.4.0 |
| `pytest-xdist` `-n auto` on the 16-core dev machine | Oversubscribes git/process work (measured contention) | `-n 6` to `-n 8`, tune with `--durations` |
| GitPython / pygit2 / dulwich for the catalog | Duplicate or weaken what git already does | subprocess git behind a second allow-list module |
| Submodules for third-party catalog entries | Every add/update/remove becomes a superproject commit and `.gitmodules` edit | Plain clones + JSON manifest with pinned commit |
| Bundling the Git installer | Stale and large | Detect, warn, link, let the user continue |
| Moving to `src/` layout in v3.0 | Breaks the test suite's path assumptions for no gain | Flat layout with explicit hatch `packages` |
| `[project.scripts]` for the GUI | Opens a console on Windows | `[project.gui-scripts]` |
| `importlib.metadata.version()` in the app | Missing in the frozen build | `_version.py` |
| A GitHub token requirement | Public tool, no secrets to manage | Unauthenticated API, optional, cached, curated data offline |
| Third-party GitHub Actions for NSIS/release | Supply-chain surface | `choco`, `gh`, `makensis` directly |
| Running `filter-repo` on the working repo | Rewrites all hashes, drops `origin` | Fresh clone, rehearse, then push to a new remote |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.14.4 | PySide6 6.12.0 | Confirmed here: 9689-test suite runs on this combination; PyInstaller and Nuitka builds start. |
| Python 3.14.4 | pytest-xdist 3.8.0 / execnet 2.1.2 | Confirmed here (266 tests green). PyPI classifiers list only up to 3.13; changelog never mentions 3.14. |
| pytest 9.1.1 and 9.2.0 | pytest-xdist 3.8.0, pytest-qt 4.5.0 | xdist needs pytest>=7. Verified here with 9.2.0 only; the project pins 9.1.1. pytest-qt 4.5.0 (2025-07-01) is still the latest. |
| pytest-timeout 2.4.0 | Python 3.14 | Pure Python; plugin was loaded in the smoke run but no timeout was configured, so the timeout path itself is untested here. |
| PyInstaller 6.22.3 | Python 3.14.4, PySide6 6.12.0 | Confirmed here (build + start). Python 3.15 support also landing (6.21.0+). |
| Nuitka 4.3.5 | Python 3.14.4, PySide6 6.12.0, MSVC 14.3 | Confirmed here (build + start). Official 3.14 support since 4.2. Needs a C compiler; the runner image has MSVC. |
| NSIS 3.12 / 3.13 | Windows 10/11 | 3.12 installed locally; 3.13 current. Release notes for 3.13 could not be fetched (redirect). |
| Git for Windows | `SOFTWARE\GitForWindows\InstallPath` | Written to HKLM since 2.6.1; per-user installs write HKCU. |
| pip >= 25.1 | PEP 735 `--group` | venv has 26.0.1. |
| hatchling | PEP 639 `license` SPDX string | Use the string form, not the deprecated table form. |
| git-filter-repo 2.47.0 | Git 2.49.0 (dev machine) | Run `git filter-repo --version` after install; exact minimum git version not re-checked. |

## Open items for phase-level research

1. Frozen-app acceptance test: drive the real GUI paths (import, generate tables, commit) from the frozen exe; verify `scan_cache` behaviour with no `.py` files.
2. Startup time of both freezes (cold and warm); not measured.
3. VirusTotal result for the signed installer; decide PyInstaller vs Nuitka finally on that.
4. Code-signing eligibility (SignPath application; Azure Artifact Signing country rules and price).
5. LGPL compliance wording with Qt's official page; tool repo licence choice.
6. Essentials-only PySide6 venv run of the full suite.
7. filter-repo on a throwaway clone including gitlinks; decision on the tracked UL sample.
8. Whether a plain-folder `Custom/` (no submodule) mode for brand-new collections changes the commit logic that assumes "commit in the Custom submodule first, then the parent".

## Sources

- PyPI JSON / project pages (HIGH): pytest-xdist 3.8.0 (`https://pypi.org/pypi/pytest-xdist/json`), pytest-timeout 2.4.0 with yanked 2.5.0 (`https://pypi.org/pypi/pytest-timeout/json`), pytest-qt 4.5.0 (`https://pypi.org/pypi/pytest-qt/json`), PyInstaller 6.22.3 (`https://pypi.org/pypi/pyinstaller/json`), git-filter-repo 2.47.0 (`https://pypi.org/pypi/git-filter-repo/json`), Nuitka classifiers incl. 3.14 and AGPL (`https://pypi.org/pypi/nuitka/json`)
- pytest-xdist changelog and how-to (HIGH): `https://pytest-xdist.readthedocs.io/en/latest/changelog.html`, `https://pytest-xdist.readthedocs.io/en/latest/how-to.html` (session fixtures run once per worker; FileLock pattern); GitHub releases API for pytest-dev/pytest-xdist
- PyInstaller changelog (HIGH): `https://pyinstaller.org/en/latest/CHANGES.html` (3.14 support 6.15.0; 6.22.3 on 2026-09-12); PyInstaller licence page (`https://pyinstaller.org/en/stable/license.html`)
- Nuitka changelog and release posts (HIGH): `https://nuitka.net/doc/Changelog.html` (4.3 current), `https://nuitka.net/posts/nuitka-release-42.html` (3.14 official, 2026-08-24, NSIS installer option `--windows-create-installer`); Nuitka commercial licence page (MEDIUM for the runtime-exception wording)
- NSIS download page (`https://nsis.sourceforge.io/Download`, 3.13 on 2026-09-27) and Chocolatey `nsis` 3.13.0 (HIGH); local `makensis /VERSION` = v3.12
- GitHub runner image readme (HIGH): `https://raw.githubusercontent.com/actions/runner-images/main/images/windows/Windows2025-Readme.md` (Python 3.14.10, Git 2.56.1, Inno Setup 6.7.1, NSIS absent)
- Git for Windows registry detection: community registry reference (`https://samibs.github.io/Registry-Keys-for-Open-Source-Applications-on-Windows/git/`), Stack Overflow answer cited via search, `find_git` crate behaviour (MEDIUM, community sources)
- git-filter-repo INSTALL.md and man page (HIGH for install and `--invert-paths` / `--subdirectory-filter`; submodule behaviour UNVERIFIED)
- GitHub REST rate limits (`https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api`): 60 requests/hour unauthenticated (HIGH)
- Python Packaging User Guide, writing pyproject.toml (HIGH): `gui-scripts`, `requires-python`, PEP 735 dependency groups, PEP 639 licence expressions
- dulwich on PyPI (cp314 Windows wheels, porcelain clone progress) (MEDIUM); pygit2 / GitPython not researched in depth
- Code signing: SignPath Foundation terms and open-source page (`https://signpath.org/terms`), Microsoft Artifact Signing GA post (`https://techcommunity.microsoft.com/blog/microsoft-security-blog/-/4482789`) (MEDIUM); one blog post for country eligibility (LOW)
- Antivirus and LGPL discussions: Qt forum / Microsoft Q&A / dev.to / Qt mailing-list threads (LOW, anecdotal)
- Local measurements in this session (HIGH for this machine): xdist smoke run, serial `test_commit_step.py`, PyInstaller and Nuitka builds and Defender scans (scratch directory, not committed)
- Project files read: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `tests/conftest.py`, `tests/gitfixtures.py`, `kicad_lib_manager/gitops.py`, `kicad_lib_manager/scan_cache.py`, `kicad_lib_manager/main_window.py`

---
*Stack research for: v3.0 Public Library Manager (installable Windows app over an external KiCad library collection)*
*Researched: 2026-11-22*
