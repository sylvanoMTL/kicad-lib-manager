# Pitfalls Research

**Domain:** Turning an existing personal PySide6 KiCad library manager into a public, installable Windows app (milestone v3.0 Public Library Manager)
**Researched:** 2026-11-22
**Confidence:** MEDIUM-HIGH. Findings about this codebase and the owner's repos are HIGH (read from the code, `git`, `gh`). Third-party tool behaviour is MEDIUM (official docs plus one-search checks); items marked LOW or "unverified" are called out in place.

Phase numbers below follow the milestone order: **P1** test speed-up, **P2** app chooses library folder, **P3** repo split, **P4** library catalog, **P5** table model, **P6** menu regroup, **P7** Python 3.14 minimum, **P8** NSIS installer + freeze tool.

## Read This First (findings that change the plan)

1. **Both GitHub repos are already PUBLIC.** `gh repo view` reports `sylvanoMTL/kicad_libraries` (the parent, holds the code, `.planning/`, tracked `reports/` and `research_notes/`) and `sylvanoMTL/kicad_custom_library` (the "private" `Custom/` parts) as `visibility: PUBLIC`, 0 forks, 0 stars (HIGH, checked 2026-11-22). CLAUDE.md and PROJECT.md call `Custom/` "private". So the split does not prevent a leak, it can only stop *future* exposure and tidy what a new public repo carries. Rewriting history cannot recall commits that anyone has cloned or that GitHub still serves by SHA ([GitHub: removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) says other clones can re-introduce the data and that cached views and PR refs need separate handling). The owner must decide whether "private" is a real requirement (flip the two repos to private) or only a preference.
2. **The frozen app silently loses the "instant last scan" feature.** `scan_cache._code_signature()` hashes the package's `.py` source files by reading them from `Path(__file__).parent`; a PyInstaller/Nuitka build has no readable `.py` files, so it returns `""`, and `check` treats `not code` as "saved scan was made by a different version of this app", forcing the ~100 s full Wurth scan on every start (HIGH, read from `scan_cache.py` lines 244-264 and 538-546). Nothing fails, so no test notices.
3. **`REPO_ROOT = Path(__file__).parent.parent` is used at about 15 call sites in `main_window.py`** (scan, cache key, layout, migration, commit, D-26 check). In a frozen app that path is the install folder (Program Files or `_internal`), so an app that forgets one call site scans or writes inside its own install directory (HIGH, grep).
4. **A large share of the test suite reads files that will not exist in the public tool repo.** Tests reference `REPO_ROOT / "Custom"`, `"WurthElektronik"`, `"downloaded_examples"` and `.planning` (about 25 test modules, for example `test_real_vendor_samples.py`, `test_roundtrip_corpus.py`, `test_adapters.py`, `test_commit_step.py`, `test_docs_atomic.py`, the `ul_package` fixture in `conftest.py`). Real-sample tests "skip when absent", so a public CI run goes green while skipping the format tests (HIGH, grep).
5. **The commit/migration code assumes `Custom/` is a git submodule of the parent** (parent gitlink bump, `make_superproject` fixtures, `pre-atomic` tag lives in the Custom repo). If the collection stops being "parent + Custom submodule", GIT-01..06, the commit panel and their fixtures change, not just paths (HIGH, PROJECT.md and `tests/gitfixtures.py`).

---

## Critical Pitfalls

### Pitfall 1: Session fixtures and module-level caches run once per xdist worker, not once per run

**What goes wrong:** `tests/gitfixtures.py` keeps a module-level `_templates` dict and builds each superproject template with `tempfile.mkdtemp(prefix="gitfixture_template_")` ("several seconds" each, two variants for autocrlf). Under `pytest -n 8` every worker is a separate process, so each builds its own template (the speed-up is smaller than expected), and the `mkdtemp` folders are never removed, so every run leaks N x 2 repo trees into `%TEMP%`. `_live_custom_untouched` (session, autouse) runs once per worker, each digesting the live `Custom/` before and after, and each worker's "after" can also see another worker's legitimate scratch changes only if anything touches the live tree, which is exactly what it must catch.

**Why it happens:** pytest-xdist workers are separate processes, so session-scoped fixtures execute once per worker; the documented way to do work exactly once is a `FileLock` plus a shared directory from `tmp_path_factory.getbasetemp().parent` ([pytest-xdist how-to](https://pytest-xdist.readthedocs.io/en/stable/how-to.html)).

**How to avoid:** Build the git template once with the documented `FileLock` pattern in `tmp_path_factory.getbasetemp().parent`, return the path directly when `worker_id == "master"`, have workers `copytree` it, and clean it in a session finalizer instead of `mkdtemp`. Keep the guard as a controller-side check (`pytest_sessionstart`/`pytest_sessionfinish` gated on `not hasattr(config, "workerinput")`) so it runs once, not N times.

**Warning signs:** `-n 4` gives well under 4x; `%TEMP%\gitfixture_template_*` folders pile up; the guard failure message appears several times; run time of the first test per worker is 10+ s.

**Phase to address:** P1.

---

### Pitfall 2: Tests share the real user's state under parallel workers (QSettings, scan cache, KiCad config, live collection)

**What goes wrong:** The app's state lives in `%APPDATA%/KiCadExtLibManager/settings.ini` and `scan_cache/` (`settings.get_settings()`), plus KiCad's real config tree. Tests redirect these per file with their own monkeypatch preambles (the `settings.get_settings().fileName()` lines in several test modules), not with one global autouse fixture. Under xdist, any test that forgets the redirect now races other workers on the same real `settings.ini` (QSettings sync is not cross-process safe) and the same real `scan_cache`. P2 makes it worse: "default folder = `KICAD_LIB_GITHUB` from KiCad's config" means new code paths read the owner's real `kicad_common.json` and can resolve to the owner's real collection, which tests could then write through Generate Tables, Install or Pin.

**Why it happens:** Isolation grew test by test; it was fine in a serial 30-minute run where one bad test is found eventually.

**How to avoid:** One autouse, function-scoped fixture in `conftest.py` that points `QSettings` at a per-test file (`QSettings.setPath` or patching `get_settings`), sets `APPDATA`/`LOCALAPPDATA`/`HOME` to a per-worker temp folder, and clears `KICAD_LIB_GITHUB`/`KICAD_CONFIG_HOME`-style env. Extend the live-collection guard to whatever the resolved library folder is (the owner's `KICAD_LIB_GITHUB`), not just `REPO_ROOT/"Custom"`. Add a test that fails if `get_settings().fileName()` is outside `tmp_path`.

**Warning signs:** a test passes serially and fails with `-n`; `settings.ini` on the real machine changes after a test run; "last scan" behaves differently after a test run.

**Phase to address:** P1 (isolation fixture), re-checked in P2 (new folder-resolution code).

---

### Pitfall 3: Order dependence and shared caches revealed by distributing tests

**What goes wrong:** Hidden order dependence appears when the order changes: `functools.lru_cache` on `_code_signature`, the unlocked shared caches in `footprint_index`/`siblings` (already logged as Phase 10 WR-01), module globals patched by tests (`REPO_ROOT`, `MIGRATION_CORE`, `CHECKOUT_CONFIG_BASE` "test seams"), and tests that leave Qt windows or `QThread`s running. `tests/conftest.py` already has a teardown hook that joins every `QThread` child with a 60 s wait, which under CPU oversubscription becomes a serial stall, not a failure.

**Why it happens:** `--dist load` (default) hands tests to workers in arbitrary order, so a module that was always preceded by its setup in a serial run no longer is.

**How to avoid:** Start with `--dist loadfile` (keeps module-level state together) and only move to `load` after the suite passes ten times in a row with `-p randomly` or `--random-order`; mark window-heavy modules `xdist_group`. Treat every "passes alone, fails in the full run" as a real shared-state bug, not a flaky test: reset the `lru_cache`/globals in an autouse fixture.

**Warning signs:** failures that move between runs; `QThread: Destroyed while thread is still running`; failures only at `-n >= 4`.

**Phase to address:** P1.

---

### Pitfall 4: QApplication, kicad-cli and CPU oversubscription under `-n auto`

**What goes wrong:** pytest-qt creates one `QApplication` per process, which is fine and correct for offscreen runs, but eight workers each loading PySide6 6.12 use several hundred MB, and the `kicad_cli` marked tests launch real `kicad-cli 10` processes that all use the same KiCad user config folder and are themselves multi-threaded. Timeouts tuned for a serial run (60 s `DEFAULT_TIMEOUT` in `kicad_cli.py`, 120 s git timeout in fixtures, the Wurth "stress/perf corpus" tests that assert time or memory) then fail under load.

**Why it happens:** `-n auto` uses logical cores; the test mix is process-heavy (git, kicad-cli) rather than pure Python.

**How to avoid:** Cap workers (`-n 4` as a first measured value, not `auto`), put the `kicad_cli` and `wurth` tests in one `xdist_group` so they run serially on one worker, and run perf/timing-asserting tests only in the `slow` serial pass. Do not raise timeouts globally to hide this.

**Warning signs:** timeout failures only with `-n`; the machine is unusable during a run; kicad-cli reports config lock or crash on parallel runs (unverified, test it).

**Phase to address:** P1.

---

### Pitfall 5: Windows file locking and read-only git objects break temp cleanup

**What goes wrong:** Fixture repos contain `.git/objects` files marked read-only, so `shutil.rmtree` raises `PermissionError` unless it has an `onexc` handler; Defender real-time scanning and the Windows search indexer hold new files briefly, so a `copytree` of a template or an immediate rmtree intermittently fails with `WinError 32`. A cleanup failure after the test passed is reported as an error at teardown and gets blamed on the wrong test. Worker temp folders (`popen-gw0` etc. under the pytest base temp) are kept for three runs by default and fill the disk with git repos.

**How to avoid:** Use a shared `rmtree` helper with `onexc` that clears the read-only bit and retries a few times (the app already has retry logic in `fsutil.py`, reuse the idea, not the module, in tests); set `--basetemp` to a short path on a drive excluded from Defender (also keeps MAX_PATH away); set `tmp_path_retention_count = 0` for the speed-up runs.

**Warning signs:** `PermissionError: [WinError 5/32]` at teardown; run time varies by a factor of two between runs with identical code.

**Phase to address:** P1.

---

### Pitfall 6: Git config and environment leakage into fixtures (and, later, into the catalog)

**What goes wrong:** The fixtures correctly set `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, strip every `GIT_*` variable and write repo-local identity, signing and `core.hooksPath`. Copies of the session template keep absolute paths in their config, which `_local_config` rewrites (the comment says so). Parallel workers or a changed template that skips this step silently inherit the owner's global config: an absolute `core.hooksPath`, `commit.gpgsign=true` (a signing prompt hangs a test), `init.templateDir` hooks, `core.autocrlf`, `safe.directory` differences. New catalog tests (P4) need network git calls that the current allow-list deliberately forbids.

**How to avoid:** Keep one `git_env()` helper used by every fixture and by the app's runner. Add a meta-test that runs `git config --show-origin --list` inside a fixture repo and asserts every value comes from the repo-local file or the fixture's own global file. For P4 tests use `file://` bare repos with `-c protocol.file.allow=always` (already used) rather than the network; never let a test reach GitHub.

**Warning signs:** a test passes on the owner's machine and fails in a clean CI VM; a hang with no output (a prompt or signing agent).

**Phase to address:** P1, then P4.

---

### Pitfall 7: Duration measurement noise and the `slow` marker hiding coverage

**What goes wrong:** `--durations` on a single run is dominated by noise: cold file cache, Defender scanning freshly created repos, template-build time attributed to whichever test builds first, and fixture setup counted in the first test of each module. A `slow` marker that is *deselected by default* means the day-to-day run no longer covers the 30-minute set, and a regression only shows when someone remembers the full run. The GSD execution gate has a 600 s default timeout (owner memory: "~9500 tests take ~29 min; GSD gate default 600 s always times out"), so a fast subset that is still over 10 minutes keeps timing out.

**How to avoid:** Measure wall-clock of the whole run (3 runs, discard the first), plus `--durations=0 --durations-min=1`, per worker with `-p no:randomly`; attribute setup time with `--setup-show` only when investigating. Define two named commands: a fast default (target under 8-10 minutes so the GSD gate passes) and a full run that CI/pre-release always runs, and add a test that counts `slow`-marked tests so the marker cannot grow unnoticed. Register the marker in `pyproject.toml` (strict markers already on).

**Warning signs:** the "fast" run gets slower each phase; `slow` count grows; nobody runs the full suite before a release.

**Phase to address:** P1 (and a release gate in P8).

---

### Pitfall 8: Splitting the repo in the working checkout that KiCad reads

**What goes wrong:** The main checkout `<main-checkout>` is what `KICAD_LIB_GITHUB` names (D-26), and KiCad reads 89+ Wurth libraries and the `Atomic_` libraries from it. Doing the history rewrite, file deletion or submodule surgery there can leave KiCad pointing at a half-converted tree (the 2026-10-21 incident repeated: Generate from the wrong folder repointed KiCad and 89 libraries went missing). The checkout also contains `env/` and `env-py311/` venvs and local-only files (`downloaded_examples/*`, `sym-lib-table`, `fp-lib-table`, backups) that `git clean` or a re-clone would delete.

**How to avoid:** Do all rewriting in fresh `git clone --no-local` copies under a scratch folder, take `git bundle create` backups and tags (`pre-split`) of both repos first, and only swap into the KiCad-read path at the end by a rename. Keep the **collection's relative layout identical** (`Custom/Symbols`, `Custom/Footprints`, `Custom/3DModels`, the Wurth/catalog library paths) so existing `${KICAD_LIB_GITHUB}/Custom/...` URIs and `${CUSTOM_3DMODEL_DIR}` keep working; verify with a before/after diff of the resolved URI list from the global `sym-lib-table` and `fp-lib-table`, and by opening one of the owner's real projects in KiCad 10 with no "library not found" errors.

**Warning signs:** KiCad Symbol Editor shows missing libraries; `kicad_common.json` changed; ERC "library not found" in a known-good project.

**Phase to address:** P3 (rehearse on a scratch clone, then do it interactively as planned).

---

### Pitfall 9: Private or restricted content ending up in the public history

**What goes wrong:** The tool repo's history contains: `.planning/` (11 MB, workstation paths `<home>`, `<repos-folder>/...` in 13+ files), root `CLAUDE.md` (owner workstation paths and "the owner's workstation"), tracked `reports/` and `research_notes/` (third-party research text), the tracked `downloaded_examples/ul_CSD85301Q2.zip` (a Texas Instruments Ultra Librarian vendor package; `.gitignore` documents a Phase 7 decision to keep it tracked while SnapEDA/SamacSys files stay local), 1,584 commits authored as `sylvanoMTL` under the owner's commit email, 978 `Co-Authored-By` trailers, one `Claude-Session` URL in a commit message, eight stray `worktree-agent-*` branches, and two tags. Fixtures of the owner's actual part names (the `CURRENT_ATOMIC_SYMBOL_LIBS` mirror) are synthetic format mirrors, so they are low risk.

**Why it happens:** A deny-list rewrite (`--invert-paths` for the paths you remember) misses things; `git filter-repo --replace-text` only touches file blobs, not commit messages, author lines, tags or branch names ([git-filter-repo manual, from knowledge, verify against `--help`]).

**How to avoid:** (a) Prefer an **allow-list**: `git filter-repo --path kicad_lib_manager --path tests --path pyproject.toml ...` so anything not named is absent. (b) Or, since there are 0 stars, 0 forks and 1,584 commits of GSD churn, seriously consider a **fresh squashed history** for the public repo and keep the old repo as the private archive; this is the cheapest way to be certain. (c) If history is kept: `--mailmap` for identity (only if the owner wants it hidden; the address is already public in the current repos), `--replace-message` for the session URL, `--replace-text` for paths, and push only explicit branches and tags, never `--mirror` (GitHub rejects the read-only `refs/pull/*` refs, per the GitHub doc above). (d) Decide `.planning/` explicitly: PROJECT.md puts it in the public repo, so scrub paths in the working tree too, not just history. (e) Replace the tracked UL zip with a synthetic builder and rewrite the tests first (see Pitfall 11).

**Warning signs:** `git log --all -S"<home>"` or `-S"@gmail.com"` returns hits in the filtered clone; `git rev-list --objects --all | grep downloaded_examples` finds the zip; `git for-each-ref` lists `worktree-agent-*`.

**Phase to address:** P3. Add a pre-publish scan (gitleaks or a simple grep script) as a P3 exit criterion.

---

### Pitfall 10: git filter-repo mistakes on Windows and with gitlinks

**What goes wrong:** `git-filter-repo` is not installed on this machine (`git filter-repo` is "not a git command", checked). Known failure modes: it refuses non-fresh clones (the `--force` escape hatch is the footgun), it removes the `origin` remote (so a later `git push` goes nowhere or, after re-adding, to the wrong repo), tags are rewritten and the recorded `Custom` gitlink SHAs in old parent commits point at commits that must still exist in `kicad_custom_library`. If the filter removes `Custom/` and `WurthElektronik/KiCad-Library` paths but leaves `.gitmodules`, or the reverse, `git submodule status` and `git clone --recurse-submodules` fail with "no submodule mapping found in .gitmodules for path ..." (git behaviour, HIGH from experience). Doc references to commit hashes ("Custom bbd48c5, parent c6920f5") become dangling after any rewrite.

**How to avoid:** Never rewrite `kicad_custom_library` history (the parent's gitlinks, the `pre-atomic` tag and `Custom/MIGRATION-ATOMIC.md` all depend on those SHAs); only the tool repo is rewritten. In the tool repo remove both gitlinks *and* `.gitmodules` together. Install with `pip install git-filter-repo` into a throwaway venv, run `--analyze` first, work on a fresh clone, set the new `origin` explicitly, push explicit refs, then `git clone` the result into an empty folder and run the suite there (this finds hidden dependencies, see Pitfall 11).

**Warning signs:** `git submodule status` errors; `git count-objects -v` shows the big `.planning` blobs still present after the filter (`git gc --prune=now --aggressive` after `git reflog expire`).

**Phase to address:** P3.

---

### Pitfall 11: The public repo's tests go green by skipping

**What goes wrong:** After the split the tool repo has no `Custom/`, no `WurthElektronik/`, no `downloaded_examples/`. About 25 test modules touch those paths. The session guard "does nothing when Custom/ is not checked out", real-sample tests skip, `test_roundtrip_corpus` and the `wurth` tests lose their corpus, and `test_docs_atomic`/`test_commit_step` read `.planning` or docs. A public CI run reports "9,689 passed" with hundreds skipped, and the format importers (the app's core value) are no longer exercised against real downloads.

**How to avoid:** Before the split, list every test that reads outside `tests/` (grep for `REPO_ROOT /`) and classify each: rebuild from synthetic fixtures, move to a "needs private corpus" marker with an explicit private-corpus job, or delete. Fail CI if the skipped count exceeds a recorded budget. Keep a small redistributable sample set (self-made, or vendor files whose licence allows it) in `tests/fixtures`, and keep the licence-restricted samples in the private collection repo that the owner's own pre-release run points at via an env var.

**Warning signs:** skipped count jumps from 4 to hundreds; a vendor-format regression ships green.

**Phase to address:** P3 (design) and P1 (markers), with the budget check in P8's release gate.

---

### Pitfall 12: Submodule and gitlink assumptions baked into the commit flow

**What goes wrong:** GIT-01..06, the Result commit panel, the migration (tag `pre-atomic` in `Custom`, parent commit), and the `make_superproject` fixtures all model "parent repo + `Custom` submodule". After the split the collection is "Custom + third-party libraries, no code"; whether `Custom/` stays a submodule or becomes a folder in the collection repo changes what "commit the part" means. Flattening a submodule into a folder without `filter-repo --to-subdirectory-filter` + merge loses the `Custom` history and the `pre-atomic` tag. Keeping both a gitlink and the same files in the tree (the "adding embedded git repository" warning) produces a pseudo-submodule with no `.gitmodules` entry.

**How to avoid:** Make the decision explicit and early in P3 (recommendation: keep `Custom/` as a submodule of the collection repo for the owner, so history and commit code are untouched, and let the "new empty collection" feature of P2 create a single-repo layout with a `Custom/` folder; the commit code must then handle both "Custom is its own repo" and "Custom is a folder of the collection repo" through one `RepoLayout` method). Test both shapes with fixtures before shipping P2's "create new collection".

**Warning signs:** `git status` in the collection shows `Custom` as "modified content" forever; `git add .` prints "adding embedded git repository".

**Phase to address:** P2 (layout abstraction) and P3.

---

### Pitfall 13: "Create a new empty collection" loses empty folders and fails on a fresh machine

**What goes wrong:** Git does not store empty directories. The skeleton `Custom/` with `Atomic_Footprints.pretty` and `3DModels` disappears after push and clone, and the planner then "refuses a Custom without Symbols/ and Footprints/" (the existing `populate_custom` comment states this). `git init` on a machine with no `user.name`/`user.email` lets the first commit fail, and the default branch name differs between Git versions ("master" vs "main").

**How to avoid:** Write `.gitkeep` in every skeleton folder (the fixtures already do), run `git init -b main`, never auto-commit the skeleton (or commit with an explicit, clearly generic identity only after asking), refuse to create inside a non-empty folder, inside the install folder, or at a drive root, and preview exactly what will be created. Add a test that clones the created collection to another folder and runs a scan.

**Phase to address:** P2.

---

### Pitfall 14: Remembered library folder versus KiCad's variable; the dev worktree rule outliving its reason

**What goes wrong:** Order of precedence matters: KiCad's `KICAD_LIB_GITHUB` (read from `kicad_common.json`, which differs per KiCad major version directory) versus a remembered setting versus a "Choose library folder..." prompt. Common mistakes: a stale remembered path beats a newer KiCad variable; a path that no longer exists is silently used (the existing Destination box already skips deleted folders, the library folder needs the same rule); a network or removable drive that is absent at start blocks startup behind a modal dialog (the architecture notes already flag a blocking modal in the constructor); D-26's "refuse from a git worktree" logic becomes wrong once the app is no longer inside the collection, but the *mismatch* warning (chosen folder differs from KiCad's variable) stays essential. The scan cache is keyed by repo folder, so switching folders mid-session with a scan worker running needs the existing busy guard.

**How to avoid:** Resolve once into an explicit `LibraryContext` (root, layout, source) passed to every service, and replace `REPO_ROOT` module globals by it; the tests' seams (`REPO_ROOT` monkeypatching) move to that object. Keep the variable name `KICAD_LIB_GITHUB` forever, because it is already baked into the generated tables and the owner's projects, even though it now sounds GitHub-specific. Never write `kicad_common.json` without the existing preview/confirm flow.

**Warning signs:** the app opens on the install folder; a second launch uses a different folder than the first; D-26 warnings fire for correct setups.

**Phase to address:** P2.

---

### Pitfall 15: Cloning untrusted GitHub repositories (the catalog)

**What goes wrong:** (1) Hooks from the remote repo are not cloned, but the *user's own* global `core.hooksPath`, `init.templateDir`, `core.fsmonitor`, credential helpers and filters apply to the clone, so a post-checkout hook from the user's setup runs against untrusted content. (2) `git clone --recurse-submodules` fetches further untrusted URLs and, on affected Git versions, has had arbitrary file-write bugs (CVE-2025-48384, CISA known-exploited, via carriage-return handling in `.gitmodules`; fixed in 2.49.1 and later point releases per the [GitHub blog](https://github.blog/open-source/git/git-security-vulnerabilities-announced-6/)); the box here runs git 2.49.0, one patch behind that fix. (3) LFS: if a repo uses Git LFS and `git-lfs` is not installed, the 3D models are text pointer files and the 3D model check reports them missing or corrupt. (4) Official KiCad 3D packages and some third-party repos are multi-GB; an unbounded clone fills the disk. (5) The existing git runner is an allow-list with no remote subcommand by design (D-06); widening it casually to add `clone` would give package-derived names network power.

**How to avoid:** Add a separate, narrow `catalog_git` runner: only `clone`, `fetch`, `ls-remote`, `rev-parse`, `status`, `reset`; `-c core.hooksPath=<empty dir> -c init.templateDir= -c core.fsmonitor=false -c protocol.file.allow=never -c credential.helper= -c core.autocrlf=false`; `https://` only, host allow-list shown to the user for "Add by URL"; no `--recurse-submodules` by default (show submodules found and ask); check the repo size before cloning where the API allows it (GitHub repo API `size`), show it, and cap it; detect `.gitattributes` with `filter=lfs` and warn "needs Git LFS". Require git >= 2.49.1 or show a warning with the version. Clone into a temp sibling and rename on success.

**Warning signs:** a hook script running on clone; `.step` files of a few hundred bytes starting with `version https://git-lfs`; disk usage jumps by GBs.

**Phase to address:** P4.

---

### Pitfall 16: A git credential prompt or long clone hangs the GUI thread or runs invisibly

**What goes wrong:** A private or mistyped URL triggers a credential prompt. `GIT_TERMINAL_PROMPT=0` stops the terminal prompt, but on Windows Git Credential Manager has its own GUI prompt, which can appear behind the app window or never be answered; there is documented hanging of automation behind GCM ([Atlassian Jira BAM-18205](https://jira.atlassian.com/browse/BAM-18205)), and GCM documents `GCM_INTERACTIVE` (Never disables prompts) ([GCM environment docs](https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/environment.md)). I found no source confirming that `GIT_TERMINAL_PROMPT=0` also suppresses the GCM dialog; treat that as unverified and test it. Killing the Python `Popen` leaves `git-remote-https` and `index-pack` children running and a half-written clone folder; Defender then locks files in it so cleanup fails.

**How to avoid:** Run catalog git on a `QThread`, with `stdin=DEVNULL`, `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never` and `-c credential.helper=` for public clones (public GitHub needs no credentials, so an authentication failure should be reported as "not public or not found", not retried), a timeout and a Cancel button that kills the process tree (`taskkill /T /F /PID` on Windows), and a retry-on-lock rmtree of the temp clone. Show progress from `--progress` on stderr.

**Warning signs:** the progress dialog never ends; a git credential window exists in the taskbar; `git.exe` processes remain after Cancel.

**Phase to address:** P4 (the runner), P8 (verify in the frozen app).

---

### Pitfall 17: Windows path length and line-ending damage to KiCad files

**What goes wrong:** Deeply nested third-party libraries (3D model folders with long names) hit MAX_PATH (260) when the collection folder is itself long (the owner's is already `<main-checkout>/...`). Git for Windows has `core.longpaths` off by default and the OS-level Win32 long path policy is a separate switch; per-clone `-c core.longpaths=true` was reported not to reach child processes in one mailing-list thread, so a global setting is more reliable ([Git for Windows: long paths](https://gitforwindows.org/git-cannot-create-a-file-or-directory-with-a-long-path)). Separately, Git for Windows' default `core.autocrlf=true` rewrites LF to CRLF in `.kicad_sym`, `.kicad_mod`, `.step` on checkout; KiCad tolerates both, but the app's lossless round-trip layer "keeps CRLF/LF", the scan fingerprint sees changed bytes, `git diff` is noisy, and a later `reset --hard` flips endings again.

**How to avoid:** Clone with `-c core.longpaths=true -c core.autocrlf=false` and persist both in the repo-local config so later fetch/reset agree; on a clone failure with "Filename too long" or "unable to create file", report the path and the two fixes (enable long paths, choose a shorter library folder). Warn at P2 when the chosen folder path exceeds roughly 100 characters. For a *new* empty collection, write a `.gitattributes` (`*.kicad_sym -text`, `*.kicad_mod -text`, `*.step binary`); do not add one retroactively to the owner's existing collection (it would renormalize every file).

**Warning signs:** `error: unable to create file ...: Filename too long`; every file shows modified right after a clean clone; the round-trip tests fail on a fresh Windows machine only.

**Phase to address:** P4 (clone flags), P2 (path-length warning, `.gitattributes` for new collections).

---

### Pitfall 18: Shallow clones, update semantics and local edits in catalog clones

**What goes wrong:** `--depth 1` is attractive (size, speed) but `git pull` on a shallow clone fails or re-downloads when upstream force-pushes or rewrites history, blobless/treeless filters (`--filter=blob:none`) fetch lazily and break offline use, and "Update" on a clone the user edited loses or conflicts with their changes. Libraries that rebase their default branch (some vendor repos do) turn `pull --ff-only` into an error the UI cannot explain.

**How to avoid:** Catalog clones are managed read-only caches, never edited: `clone --depth 1 --single-branch`, update by `fetch --depth 1 origin <branch>` + `reset --hard FETCH_HEAD` only after `git status --porcelain` is clean, otherwise refuse with the dirty file list. Record the commit SHA in the manifest on every install/update so state is reproducible; Remove = delete folder + manifest entry + regenerate tables (preview first, as everywhere else). Tell the user "local changes belong in Custom/".

**Phase to address:** P4.

---

### Pitfall 19: Nickname collisions and the `Lib:FP` contract

**What goes wrong:** Library nickname = file/folder stem, and third-party symbols reference footprints as `Nick:Footprint`, and KiCad schematics and boards store `Nick:Name` too. A catalog library whose stem equals a KiCad stock library (`Connector`, `Device`, `Package_QFP`, ...), another catalog library, or an owner `Atomic_` library collides; KiCad requires a unique nickname per table and lets a project table shadow a global one with the same nickname (the nickname, not the path, decides, per [KiCad 6 docs](https://docs.kicad.org/6.0/ca/pcbnew/pcbnew_footprints_and_libraries.html) and [forum](https://forum.kicad.info/t/search-order-of-package-footprint-libraries/13199); older docs, MEDIUM). The tempting fix (auto-suffix `Device_2`) silently breaks every symbol's Footprint field, every schematic that already uses the library, and the stock-library cross-reference. The existing HARD-08 handling keeps same-nickname peers distinct in the UI and leaves the first selected; the catalog multiplies the situations. Also hard-coded layout assumptions exist: `verify.py` uses `layout.repo_root / "WurthElektronik"` and "searched recursively, the rest are flat".

**How to avoid:** Detect collisions at *add* time against (a) KiCad stock nicknames (the app already reads the default footprint dir; do the same for symbols), (b) installed catalog libraries, (c) `Atomic_`/Custom libraries, and show them in the preview; the default action is "do not enable this library's tables" with a clear reason, never an automatic rename. Make layout discovery generic (find `*.kicad_sym` and `*.pretty` at any depth with a skip list, as the scanner does) and remove the `WurthElektronik` string assumptions in `verify.py`.

**Warning signs:** two entries with the same name in the generated table; a symbol shows a footprint from the wrong library; "footprint not found" after enabling a second library.

**Phase to address:** P4 (and P5 for how it interacts with project tables).

---

### Pitfall 20: Third-party libraries expect path variables the app does not define; moving Wurth breaks 3D models

**What goes wrong:** Third-party footprints reference models through variables (`${WE_3DMODEL_DIR}` for Würth, `${KICAD*_3DMODEL_DIR}` for KiCad, `${KIPRJMOD}`, vendor-specific names). The app writes only `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` into `kicad_common.json` and the owner set `WE_3DMODEL_DIR` by hand; the code has no knowledge of it (grep found no `WE_3DMODEL_DIR`). A catalog-managed Wurth moves its folder (today `WurthElektronik/KiCad-Library`, bundled with its own `fp-lib-table`/`sym-lib-table`, a PDF licence and a disclaimer), so a variable that points at the old location now resolves to nothing: every Wurth footprint shows without a model, no error in the table, only in the 3D viewer.

**How to avoid:** At add time scan the library's `.kicad_mod` files (the 3D-model path scan already does this and takes ~100 s for Würth, so run it once and store the set of variables in the manifest) and show "needs variable X; currently defined as Y / not defined". Offer to set it through the existing confirm-before-write `kicad_common.json` flow, defaulting to the catalog path. For the Wurth migration, keep the old path working until Generate Tables has been run and a rescan reports zero missing models, and call out that KiCad needs a restart for new path variables. Ignore the vendor's bundled `fp-lib-table`/`sym-lib-table` when scanning (confirm `SKIP_DIRS`/table handling covers them).

**Warning signs:** 3D viewer empty for a library that used to work; the scan's 3D-path warnings jump after moving a library.

**Phase to address:** P4.

---

### Pitfall 21: Replacing the Wurth submodule with a catalog clone

**What goes wrong:** Removing a submodule properly needs `git submodule deinit -f`, `git rm`, and deleting `.git/modules/<path>`; skipping the last step makes a later add at the same path fail with "a git directory for ... is found locally". A plain clone placed inside the collection repo without being ignored is seen as an embedded repository (`git add .` creates a gitlink with no `.gitmodules` entry, the dangling-gitlink problem of Pitfall 10, now in the owner's private collection). If catalog libraries move to a new folder, the 89 generated URIs change; unless Generate Tables runs, KiCad loses them (the 2026-10-21 incident).

**How to avoid:** Recommendation (research question): **plain clones + a manifest** in the collection, with the catalog folder in the collection's `.gitignore`. The manifest (URL, branch, pinned SHA, library list, required variables) is the reproducible record; submodules force the collection repo to track a pointer for every library and tie commit flows to git plumbing. Write the Wurth migration as a previewed, single transaction: clone to the new place, verify the library set matches the old, regenerate tables, rescan, only then remove the old submodule (with all three steps above) and keep a rollback tag.

**Phase to address:** P4 (and P3 for where the folder lives).

---

### Pitfall 22: Redistributing a curated list and licences

**What goes wrong:** A curated catalog entry is a URL, but a catalog that also bundles library *content* in the installer or repo makes the project a redistributor. KiCad's official libraries are CC-BY-SA 4.0 with an exception that covers *designs*, and the KiCad licence page states the exception does *not* apply when libraries are shared as a collection, so such a collection is share-alike ([KiCad libraries licence](https://www.kicad.org/libraries/license/), [SPDX KiCad-libraries-exception](https://www.spdx.org/licenses/KiCad-libraries-exception.html)). Würth ships its own licence terms and a disclaimer PDF in the repo; other vendors differ or give none.

**How to avoid:** The curated list is metadata only (name, GitHub URL, a short description, a licence field filled from the GitHub API or the repo's LICENSE at add time), never library content; the installer ships no libraries; the UI shows each library's licence before the first clone and "no licence found" as a warning, not a silent default; "Add by URL" gets a licence-unknown notice. Also check the app's own tests for copied stock-library content (current fixtures are synthetic, which is the right pattern). The code licence chosen in P3 should not claim to cover third-party library content. Not legal advice.

**Phase to address:** P3 (code licence), P4 (list format and UI).

---

### Pitfall 23: Per-project tables silently shadowing global tables

**What goes wrong:** KiCad reads a project `fp-lib-table`/`sym-lib-table` next to the `.kicad_pro` in addition to the global one, and a same-nickname entry in the project table wins (see the sources in Pitfall 19; MEDIUM). If P5 decides "per-project" for Generate Tables, the owner's existing projects (which resolve `Atomic_*` through the *global* table) now get a project table that shadows them; entries KiCad itself created in project tables (it creates them when remapping legacy projects, sometimes with a numeric suffix such as `Devices1`, per the [KiCad developers list](https://archive.lists.launchpad.net/kicad-developers/msg32246.html)) are not "managed" by the URI marker `${KICAD_LIB_GITHUB}/`, and `${KIPRJMOD}` relative entries are legitimately project-owned. The app has no "current project" concept at all, so a project mode needs a project picker, remembered per project, and KiCad has no API to tell the app which project is open.

**How to avoid:** Decide **global as the default and only automatic mode**; offer project tables only as an explicit "Export tables for this project" action that writes entries to a chosen project folder, merges (never replaces; the HARD-01 verbatim-preservation logic already exists), and reports any nickname that would shadow a global one. Never auto-create project tables for the owner's existing projects. Keep the table model decision one sentence in the User Guide.

**Warning signs:** the same nickname appears in both tables with different URIs; a project shows libraries that the global table no longer lists.

**Phase to address:** P5.

---

### Pitfall 24: Writing tables while KiCad runs; nickname changes breaking existing schematics

**What goes wrong:** KiCad reads tables at startup or project load and writes `kicad_common.json` on exit; external edits are not picked up by an open editor, and KiCad may overwrite a changed `kicad_common.json` when it closes. The app already handles this for the common config (the Phase 5 WR-06 running-KiCad check and the REV-05 dialog; live re-test still backlog 999.3), but a *project* table has no equivalent check (KiCad writes lock files like `~<project>.kicad_pro.lck` next to open projects; MEDIUM, from KiCad behaviour, verify). Separately, schematics store `lib_id` as `Nick:Symbol` plus an embedded copy of the symbol in `lib_symbols`, and boards store `Nick:FP`; renaming a nickname leaves orphaned cached symbols and unfixable footprints (the owner's own migration needed the old -> new map and KiCad's "Edit Symbol Library Links" for this reason).

**How to avoid:** Extend the running-KiCad check to project folders (lock file or process check) before any project-table write; require nickname stability as a hard rule (nickname = file stem, forever; catalog update must never change stems, and an upstream library that renames a stem shows up as "removed + added" with a warning). Keep the app's old -> new map approach for any unavoidable rename.

**Phase to address:** P5 (project writes), P4 (stem stability on update).

---

### Pitfall 25: Frozen app resource paths, `__file__` assumptions and the dead scan cache

**What goes wrong:** Besides the dead cache and the `REPO_ROOT` default (Read This First 2-3): `Path(__file__)` points into `_internal`/`_MEIPASS` for data; any file read relative to the package (docs, icons, a `catalog.json` curated list shipped with the app) must be declared as bundled data and found via `sys._MEIPASS`/`importlib.resources`, or it fails only in the frozen build. Writing next to the executable fails under Program Files (per-machine install is not user-writable). The built-in Help is embedded Python strings in `help_dialog.py` (good: no data files), but P4's curated list and any version file are new data files.

**How to avoid:** One `paths.py` (`app_dir()`, `data_dir()`, `resource(name)`) with `getattr(sys, "frozen", False)` handling; a frozen smoke test in CI that launches the built exe with `--smoke` (import everything, open the main window offscreen, scan a tiny fixture collection, exit 0). Replace `_code_signature()` with a build-time version constant (generated at build; keep the source hash only for unfrozen dev runs) and add a test that asserts the signature is non-empty in a frozen build.

**Warning signs:** "The saved scan was made by a different version of this app" on every start of the installed build; file-not-found only in the installed app; the app creating folders inside Program Files.

**Phase to address:** P2 (no `REPO_ROOT` in services), P8 (frozen smoke test and scan-cache signature).

---

### Pitfall 26: PySide6 plugins, bloated bundles and mixed bindings in the frozen build

**What goes wrong:** Typical failure is "could not find or load the Qt platform plugin windows" in the frozen exe while the app runs from source: missing `platforms/qwindows.dll`, or Qt DLLs picked from a system or other-venv install. The Qt docs advise building from a clean virtual environment because a system-wide PySide6/Shiboken6 is used in preference to the venv one ([Qt for Python and PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)); PyInstaller's PySide6 hook collects only one Qt binding package, so a PyQt in the build env conflicts. The owner's venv has the full `PySide6` meta-package (Essentials, Addons, WebEngine and PDF were seen in `env/Lib/site-packages`); the app only needs QtWidgets/QtGui/QtCore (+ `QTextBrowser`), so a naive build can balloon to several hundred MB by collecting WebEngine.

**How to avoid:** Build only from a dedicated clean venv with `PySide6-Essentials` pinned to the same version (6.12.0) instead of the full meta-package and explicit `--exclude-module` for unused Qt modules; commit the `.spec` file; after each build, run the frozen smoke test on a *clean Windows VM* with no Python or KiCad (a dev machine masks missing DLLs and plugins). Qt's own recommended deployment tools are `pyside6-deploy` (Nuitka-based) and plain Nuitka/PyInstaller; a Qt forum moderator comment that PyInstaller "does not really support PySide6" is anecdotal (LOW), the official Qt doc page exists and works.

**Phase to address:** P8.

---

### Pitfall 27: Python 3.14 support in freeze tools, and which one to pick

**What goes wrong:** Choosing a freeze tool on a 3.14-only interpreter. PyInstaller added Python 3.14 support in 6.15.0 (2025-08-03) and the line has been maintained since (latest seen 6.22.3, 2026-09-12; [PyInstaller changelog](https://pyinstaller.org/en/stable/CHANGES.html), HIGH). Nuitka lists official 3.14 support from release 42 (2026-08-24) ([Nuitka 4.2 post](https://nuitka.net/posts/nuitka-release-42.html), MEDIUM); I could not confirm a PySide6-on-3.14 Nuitka build specifically, test it before committing. A freeze tool pinned too low builds against an unsupported interpreter and fails at runtime (not at build). Free-threaded 3.14t builds are not supported by PySide6 wheels (unverified here), so make sure the build interpreter is the regular python.org build.

**How to avoid:** Pin the freeze tool and PySide6 in `requirements-build.txt` and have a spike in P8's first plan that builds an empty PySide6 window on Python 3.14.4 with each candidate, runs it on a clean VM and checks the Defender result (Pitfall 28). Don't fix the tool choice from this document alone.

**Phase to address:** P8 (spike first), P7 (declare the minimum).

---

### Pitfall 28: Windows Defender and SmartScreen false positives

**What goes wrong:** PyInstaller executables are flagged by AV engines often enough to be a known FAQ; discussion points at the shared bootloader, `--onefile` self-extraction to `%TEMP%`, and low reputation of a new unsigned binary. Recorded evidence is anecdotal (Python forum, PyInstaller mailing list, Microsoft Q&A). PyInstaller's own changelog mentions fixes involving "anti-virus programs injecting DLLs into onefile parent processes" (6.13.0, HIGH that it exists). One developer blog claims Nuitka builds are flagged far less (LOW, single uncontrolled account). Recompiling the bootloader is untested as a remedy.

**How to avoid:** Ship **onedir inside the NSIS installer**, not onefile (the installer already provides single-file distribution, and onefile adds a per-launch extract-and-scan and a slower start); sign the installer and exe (research a free route for open source, for example a signing programme for OSS; unverified here) because reputation, not signatures of content, drives SmartScreen; build releases from GitHub Actions on a tagged commit and publish SHA-256 sums; run each release candidate through a clean Windows 11 VM with Defender cloud protection on and VirusTotal; keep the Microsoft false-positive submission portal in the release checklist (one user reported it worked, another reported a decline).

**Warning signs:** the exe vanishes after download; SmartScreen "unknown publisher" every release; VirusTotal detections from a handful of engines.

**Phase to address:** P8.

---

### Pitfall 29: Subprocess console windows, a hidden git, and PATH differences in the frozen app

**What goes wrong:** A windowed build launched from the Start Menu has no console, so a `subprocess` call without `CREATE_NO_WINDOW` flashes a console window per git/kicad-cli/tasklist call. The existing code sets the flag at the three sites found in `gitops.py`, `importer/kicad_cli.py` and `kicad_process.py`; a *new* catalog runner or a `subprocess.run` added in P2 (`git init`) will forget it. Child processes in a frozen app also inherit PyInstaller's modified environment (library search path entries, `_MEIPASS`, possibly `PYTHONHOME`), which can make `git.exe` or `kicad-cli.exe` load the wrong DLLs. The Start Menu launch also has a *stale PATH*: Git installed after login, or by a per-user installer, is not on the process PATH, so `shutil.which("git")` fails even though Git is installed. `locate_kicad_cli` finds kicad-cli from the footprint folder (`parents[2]/bin`), not PATH, which is good, but the KiCad footprint discovery itself hard-codes `C:/Program Files/KiCad` (per-user KiCad installs are missed).

**How to avoid:** One `run_process()` helper that always sets `creationflags=CREATE_NO_WINDOW`, `stdin=DEVNULL`, a sanitised environment (drop `_MEIPASS`-related and `PYTHON*` variables when frozen) and a timeout; a test that greps the package for `subprocess.` uses outside that helper. Find git by: `shutil.which`, then registry `HKCU`/`HKLM` `Software\GitForWindows\InstallPath` (Git for Windows writes both, depending on a per-user or machine install; [registry reference](https://samibs.github.io/Registry-Keys-for-Open-Source-Applications-on-Windows/git/), MEDIUM), then `Program Files\Git\cmd\git.exe`, and re-detect each time git is needed (a user may install Git while the app is open) with a clear "Install Git" message. Add `%LOCALAPPDATA%\Programs\KiCad` to the KiCad probes.

**Phase to address:** P2 (single process helper), P4, P8.

---

### Pitfall 30: NSIS installer detecting Git, per-user versus per-machine, updates over a running install

**What goes wrong:** (1) The Git for Windows installer is Inno Setup (it registers a `Git_is1` uninstall key), and a per-user install writes only to `HKCU\Software\GitForWindows`; an installer that checks only `HKLM` or only PATH reports "Git not installed" for a working per-user install. (2) NSIS is a 32-bit installer by default: without `SetRegView 64` it reads the 32-bit registry view and misses 64-bit entries. (3) Blocking the install when Git is missing is the wrong default: the app is useful without Git (scanning, generating tables, importing a part without committing) and Git is needed only for the catalog and commits. (4) Upgrades: overwriting a running exe or its DLLs fails ("Error opening file for writing"), a per-user and a per-machine install of the same app coexist and shadow each other, and an uninstaller that deletes `%APPDATA%\KiCadExtLibManager` or the user's collection destroys settings and, worst, the library. (5) A public rebrand changes the QSettings organisation/app name and silently drops the owner's history, saved scan and Help position.

**How to avoid:** Detect Git in order HKCU, HKLM, `Git_is1` uninstall keys (both hives, 64-bit view), then default paths; make the check advisory ("Git not found. The catalog and Commit need it. Continue / Open download page"). Choose one execution level (recommendation: per-user, `RequestExecutionLevel user`, install under `$LOCALAPPDATA\Programs`, no admin prompt, which also avoids Program Files being non-writable); use one fixed AppId and uninstall key, version compare on upgrade, and an app-running check (a named mutex or `FindWindow`) before copying. The uninstaller removes only its own program folder (offer, default No, to remove settings; never touch collections). Keep the existing `APP_ORG`/`APP_NAME` constants or add an explicit settings migration if the public name differs.

**Phase to address:** P8.

---

### Pitfall 31: Python 3.14 minimum, the owner's other venv, and the lost annotation guard

**What goes wrong:** (1) The main checkout keeps `env-py311`; `requires-python = ">=3.14"` makes `pip install -e .` refuse on it, which is intended, but running `python kicad_lib_manager.py` from source on 3.11 keeps working until someone uses a 3.12+ construct, then fails with a `SyntaxError` at import; this is the symptom the 3.10 compatibility test existed to prevent. (2) On 3.14, annotations are evaluated lazily (PEP 649), so an annotation naming an undefined class passes at import and in tests; this is exactly why `tests/test_annotations_resolve.py` was added after the NameError seen on the 3.11 venv (G-13-1-a). Dropping the 3.10 check *and* that test together removes the only undefined-name check, with no lint config in the repo. (3) README and docs claiming 3.10+ in several places (CLAUDE.md, PROJECT.md, STACK notes, the test docstrings) will contradict `pyproject.toml`.

**How to avoid:** Keep an undefined-name check on 3.14 (add `ruff` with `F821` to `requirements-dev.txt`, or evaluate every annotation with `annotationlib.get_annotations(obj, format=Format.FORWARDREF)` in the existing test, which is a rewrite of that test, not a deletion). Delete `env-py311` deliberately and say so in the changelog, and add one test that `pyproject.toml`'s `requires-python`, the README and CLAUDE.md agree. Drop the `3.10-grammar` assertion but not the import check.

**Phase to address:** P7.

---

### Pitfall 32: Menu regroup breaking shortcuts, tests and docs

**What goes wrong:** The regroup into File / Libraries / KiCad / Help moves actions that tests locate by text or object, the User Guide and the saved Help topic reference menu paths ("File > Import Part...", "Help > User Guide"), CLAUDE.md lists shortcuts, and an action that moves from a menu with a parent widget to another can lose its shortcut context. The Help window saves its last section by key (`help/last_topic`), so renaming section keys loses that place.

**How to avoid:** Move `QAction` objects, don't recreate them; keep every shortcut string and verify with one test that enumerates all actions and asserts the shortcut table from CLAUDE.md; update the Help text, CLAUDE.md and the README in the same plan; keep Help section keys stable.

**Phase to address:** P6.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Make `slow` tests skipped by default and never run them in CI | The default run is fast | Coverage silently erodes (Pitfall 7) | Only with a mandatory full run before every release |
| Keep `REPO_ROOT` global and "just set it" at startup | Small diff in P2 | Every frozen/test path still has the hidden default; tests keep monkeypatching a global | Never, pass a context |
| Bundle the curated catalog JSON inside the app | No network at first start | Needs app update to change the list; licence text goes stale | Yes as a seed, with a refresh from the repo's raw URL later |
| Use `--mirror` push or `--force` filter-repo | Quick | Leaks stray branches, PR refs fail, wrong remote (Pitfalls 9, 10) | Never |
| Auto-rename colliding nicknames | The collision disappears | Breaks `Lib:FP` references and existing schematics (Pitfall 19) | Never |
| PyInstaller `--onefile` for the distributable | One file | Slower start, more AV flags, temp-dir residue (Pitfall 28) | Only for a portable zip, not the installer |
| Block the installer on missing Git | Simple | Frustrates users who only scan/generate (Pitfall 30) | Never, make it advisory |
| Delete the 3.10 grammar test and the annotation test together | Less code | No undefined-name check on a lazy-annotation interpreter (Pitfall 31) | Only if replaced by ruff F821 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| pytest-xdist | Session fixture assumed "once per run" | `FileLock` + `tmp_path_factory.getbasetemp().parent`, handle `worker_id == "master"` ([docs](https://pytest-xdist.readthedocs.io/en/stable/how-to.html)) |
| pytest-qt | One QApplication per xdist worker is fine; leaving threads running at teardown is not | Keep the existing QThread-join hook, one window per test, cap workers |
| git (catalog) | Reusing the owner's global config, hooks and credential helper | Dedicated runner with `-c core.hooksPath=<empty> -c credential.helper= ...`, `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never` |
| GitHub | Using the unauthenticated API for size/licence without handling the rate limit (60/hour) | Cache results in the manifest, degrade to "unknown" without failing the add |
| KiCad config | Writing `kicad_common.json` or tables while KiCad runs | Existing running-KiCad check, extended to project folders |
| KiCad tables | Treating a table entry as managed by nickname | Managed by the `${KICAD_LIB_GITHUB}/` URI marker only, project-relative entries stay untouched |
| kicad-cli | Relying on PATH from a frozen Start Menu launch | Locate from the footprint folder (already done) plus Program Files and `%LOCALAPPDATA%\Programs\KiCad` probes |
| NSIS | Reading the 32-bit registry view, only `HKLM` | `SetRegView 64`, check `HKCU` and `HKLM`, advisory result |
| PyInstaller | Building in the dev venv with the full PySide6 meta-package | Clean venv, `PySide6-Essentials` pinned, committed `.spec` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full 3D-model path scan for every new catalog library | Add takes ~100 s for a Würth-sized library | Run on a worker with Skip (existing pattern), cache the result in the manifest by commit SHA | Libraries over ~10k footprints |
| Full scan on every start in the frozen app (dead scan cache) | Slow start, "different version" message every time | Build-time version constant for the cache signature | Immediately in the frozen build |
| `git clone` without size check or depth | Multi-GB download, disk full | Size check, `--depth 1`, cap | Any KiCad 3D package repo |
| Many xdist workers each starting `kicad-cli` | Timeouts, UI freeze | `xdist_group` for the `kicad_cli` marker | `-n` above 4 on a typical desktop |
| Generate Tables with hundreds of catalog libraries | Large merged tables, slow KiCad start | Preview counts; let the user enable per library | Several hundred `.pretty` folders |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Cloning with `--recurse-submodules` by default | Untrusted submodule URLs and past git CVEs (CVE-2025-48384, per the GitHub blog above) | No recursion by default, require git >= 2.49.1 or warn |
| Running the owner's hooks on clones of third-party repos | Code from the user's global hooks runs against untrusted content | `-c core.hooksPath=<empty dir>` for catalog operations |
| Accepting any URL in "Add by URL" | `file://`, `ssh://`, `ext::` transports or credentials in URLs | Allow `https://github.com/<owner>/<repo>[.git]` only (host allow-list), reject embedded credentials, `protocol.allow` limited to https |
| Writing tables from a manifest without a preview | A tampered manifest changes KiCad's libraries | Same preview-before-write rule; manifest entries validated, URLs re-shown |
| Leaving paths, author identity or session URLs in the public history | Privacy leak (partly moot, repos are already public) | Allow-list filter or fresh history, pre-publish scan (Pitfall 9) |
| Unsigned installer and exe | SmartScreen blocks, users disable AV | Signing, SHA-256 sums, Actions-built release |
| Treating a signed-off "no hooks on clone" as complete | LFS filters and `.gitattributes` run through the user's git | Explicit `filter` and LFS detection |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| First launch of the public app shows the owner-centric `Custom` / `Atomic_` language | A new user has no idea what an atomic rule or `Custom` is | Welcome page: "Choose or create a library folder", explain `Custom/`, link to the User Guide |
| A modal "choose folder" dialog in the main window constructor | Blocks startup, hostile in tests | Resolve non-modally after the window shows (the constructor-modal anti-pattern is already documented) |
| Catalog Update/Remove without a preview | Violates the project's preview-before-write rule; libraries vanish from KiCad | Preview list of tables to add/remove and projects affected, then confirm |
| Git missing at runtime with a cryptic error | User thinks the catalog is broken | One "Git not found" panel with a download link and a re-detect button |
| A long clone with a frozen progress bar | User kills the app mid-clone | Progress text, Cancel, temp-folder clone |
| Library Manager tells users to restart KiCad but never says why | Missing libraries look like a bug | The existing "reopen KiCad's editors" notice, reused after every table or variable change |

## "Looks Done But Isn't" Checklist

- [ ] **xdist speed-up:** often missing a per-worker template build and a once-only live-collection guard; verify one guard failure message and `ls %TEMP%` shows no leaked `gitfixture_template_*` after two runs.
- [ ] **xdist speed-up:** passes only with `--dist load` once; verify ten consecutive green runs with random ordering and `-n 4`.
- [ ] **Library folder:** works from the dev checkout, fails when launched from another working directory; verify by running the app from `C:\` with `KICAD_LIB_GITHUB` unset and set.
- [ ] **New collection:** looks fine locally; verify a clone of it elsewhere still scans (empty folders need `.gitkeep`).
- [ ] **Repo split:** tool repo builds; verify a fresh clone into an empty folder runs the full suite with the skipped count within budget and no `<home>`, no gmail address, no `Claude-Session`, no `downloaded_examples/*` in `git log --all`.
- [ ] **Repo split:** verify the owner's real KiCad project opens with no missing libraries from the swapped-in collection, and `kicad_common.json` is unchanged.
- [ ] **Catalog add:** clone works on the dev machine; verify on a path over 260 characters, a repo using LFS, a private URL (fails fast, no hang), and after Cancel mid-clone (no leftover folder, no `git.exe` process).
- [ ] **Catalog collisions:** verify a library named like a KiCad stock library is reported and not auto-renamed.
- [ ] **Wurth migration:** verify 3D models still resolve (zero missing after rescan) and Generate Tables ran before the old submodule was removed.
- [ ] **Table model:** verify the owner's existing project still resolves `Atomic_*` and no project table was created unprompted.
- [ ] **Frozen app:** verify on a clean VM: starts, no console flashes, last-scan reuse works (non-empty signature), Git detected from `HKCU`, kicad-cli found, Help opens, no writes under the install folder.
- [ ] **Installer:** verify upgrade over a running instance, per-user and per-machine coexistence, uninstall leaves `%APPDATA%\KiCadExtLibManager` and collections alone.
- [ ] **Python 3.14 minimum:** verify an undefined name in an annotation is still caught by a test or ruff, and README, `pyproject.toml` and CLAUDE.md agree.
- [ ] **Menu regroup:** verify every shortcut in the CLAUDE.md list still fires and the Help text names the new menu paths.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Private data pushed to the public repo | HIGH | Treat as exposed; rotate nothing (no secrets), but delete and re-create the public repo from a clean history, request GitHub cache purge for cached views if needed (GitHub support), update README links |
| KiCad lost libraries after the split or Wurth move | LOW | Restore the `pre-split` tag/bundle in the original path, rerun Generate Tables from the collection (backups `*_backup_N` exist), reopen KiCad |
| Auto-renamed nicknames broke schematics | HIGH | Revert the table, use KiCad's Edit Symbol Library Links with an old -> new map (the migration's map pattern) |
| Dangling gitlink / `.gitmodules` mismatch | MEDIUM | `git rm --cached <path>`; restore or remove the `.gitmodules` entry; remove `.git/modules/<path>` |
| Half-cloned catalog folder after cancel/kill | LOW | Delete the temp sibling (retry for AV locks), clear the manifest entry |
| xdist flakiness blocking the suite | MEDIUM | Fall back to `-n 0` for the gate, bisect with `--dist loadfile`, fix the shared state, re-enable |
| Frozen build flagged by Defender | MEDIUM | Submit to Microsoft, publish hashes, rebuild unsigned onedir, sign, retest on a clean VM |
| Installer upgrade left a broken install | LOW | Uninstall (program folder only), reinstall; user data is untouched by design |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Session fixtures per worker, template leak | P1 | One template build per run (log line), no leaked temp folders |
| 2 Shared real user state | P1, re-check P2 | Meta-test: settings and cache paths inside `tmp_path`; guard covers the resolved folder |
| 3 Order dependence and shared caches | P1 | Ten green runs, random order, `-n 4` |
| 4 QApplication / kicad-cli oversubscription | P1 | `xdist_group` for `kicad_cli` and `wurth`, no timeout failures |
| 5 Windows locking and read-only git objects | P1 | Clean teardown over 3 runs, no `WinError 32` |
| 6 Git config and env leakage | P1, P4 | Meta-test on `git config --show-origin`; catalog tests use `file://` |
| 7 Duration noise, `slow` marker coverage | P1, P8 | Fast run under the GSD gate time; full run is a release step |
| 8 Splitting in the KiCad-read checkout | P3 | Scratch-clone rehearsal; URI list unchanged; owner project opens clean |
| 9 Private/restricted content in public history | P3 | History grep and pre-publish scan clean |
| 10 filter-repo and gitlink mistakes | P3 | `git submodule status` clean; fresh-clone suite runs |
| 11 Public tests green by skipping | P3 (P1 markers) | Skip budget enforced in CI |
| 12 Submodule assumptions in commit flow | P2, P3 | Both repo shapes covered by fixtures |
| 13 Empty collection skeleton | P2 | Clone-and-scan test of a created collection |
| 14 Library folder resolution | P2 | `LibraryContext` everywhere; no `REPO_ROOT` in services |
| 15 Cloning untrusted repos | P4 | Narrow runner, hooks-path and recursion tests |
| 16 Credential prompt / hang / cancel | P4, P8 | Private-URL test fails fast; Cancel kills children |
| 17 Path length and CRLF | P4, P2 | Long-path and autocrlf fixtures |
| 18 Shallow/update semantics | P4 | Dirty-clone update refuses; SHA recorded |
| 19 Nickname collisions and `Lib:FP` | P4, P5 | Collision preview; no auto-rename |
| 20 Third-party path variables | P4 | Variables listed per library; Wurth 3D check zero missing |
| 21 Submodule to catalog migration | P4 | Previewed transaction, rollback tag |
| 22 Licences and curated list | P3, P4 | Licence shown before clone; list is metadata only |
| 23 Per-project tables shadowing global | P5 | Global default; project export only on request |
| 24 KiCad running; nickname stability | P5, P4 | Project lock check; stem-stability test |
| 25 Frozen resource paths, dead scan cache | P2, P8 | Frozen smoke test; non-empty signature |
| 26 PySide6 plugins and bundle size | P8 | Clean-VM run; build size recorded |
| 27 Python 3.14 freeze support | P7, P8 | Spike on 3.14.4 with each tool |
| 28 Defender / SmartScreen | P8 | VM run and VirusTotal in the release checklist |
| 29 Console windows, PATH, hidden git | P2, P4, P8 | Single process helper test; Git found from `HKCU` |
| 30 NSIS Git detection, per-user, upgrades | P8 | Per-user and per-machine matrix; upgrade over running app |
| 31 Python 3.14 minimum and annotation guard | P7 | ruff F821 or forward-ref test; docs agree |
| 32 Menu regroup | P6 | Shortcut enumeration test |

## Research Flags for Roadmap

- **P3 needs an interactive decision session first:** are the two repos to be made private (Read This First 1); allow-list vs fresh history; whether `Custom/` stays a submodule of the collection (Pitfall 12); whether `.planning/` and `CLAUDE.md` are public.
- **P4 needs deeper research at plan time:** GitHub API limits and licence detection, an LFS strategy, the manifest schema, and a list of real third-party KiCad libraries and their layouts (non-standard folder structures are common).
- **P8 needs a spike before planning:** PyInstaller vs Nuitka on 3.14.4 with PySide6 6.12, size, start time and Defender behaviour on a clean VM; code-signing options.
- **P1, P2, P5, P6, P7:** standard patterns; the pitfalls above are enough.

## Sources

- Codebase reads (HIGH): `.planning/PROJECT.md`, `.planning/codebase/CONCERNS.md`, `tests/conftest.py`, `tests/gitfixtures.py`, `tests/customfixtures.py`, `kicad_lib_manager/scan_cache.py`, `kicad_lib_manager/importer/kicad_cli.py`, `kicad_lib_manager/gitops.py`, `kicad_lib_manager/main_window.py` (REPO_ROOT call sites), `.gitignore`, `.gitmodules`, `git log`, `gh repo view` output on 2026-11-22.
- pytest-xdist how-to (session fixtures once per worker, FileLock pattern, `worker_id`): https://pytest-xdist.readthedocs.io/en/stable/how-to.html (HIGH)
- PyInstaller changelog (3.14 support in 6.15.0; latest 6.22.3; anti-virus DLL injection fix 6.13.0): https://pyinstaller.org/en/stable/CHANGES.html (HIGH)
- Nuitka release 42 (Python 3.14 official support): https://nuitka.net/posts/nuitka-release-42.html ; Qt for Python and Nuitka: https://doc.qt.io/qtforpython/deployment/deployment-nuitka.html (MEDIUM)
- Qt for Python and PyInstaller (clean venv, single binding): https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html (MEDIUM)
- PyInstaller antivirus false positives (anecdotal): https://discuss.python.org/t/pyinstaller-false-positive/43171 , https://github.com/pyinstaller/pyinstaller/issues/5579 , https://dev.to/weisshufer/from-pyinstaller-to-nuitka-convert-python-to-exe-without-false-positives-19jf (LOW)
- GitHub guidance on removing sensitive data (clones, PR refs, force-push limits): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository (HIGH)
- Git security releases (CVE-2025-48384 fixed in 2.49.1 and others): https://github.blog/open-source/git/git-security-vulnerabilities-announced-6/ (HIGH)
- Git for Windows long paths: https://gitforwindows.org/git-cannot-create-a-file-or-directory-with-a-long-path (MEDIUM)
- Git Credential Manager `GCM_INTERACTIVE`: https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/environment.md ; hang case https://jira.atlassian.com/browse/BAM-18205 (MEDIUM; the `GIT_TERMINAL_PROMPT` interaction is unverified)
- Git for Windows registry keys (`InstallPath` in HKCU and HKLM, `Git_is1`): https://samibs.github.io/Registry-Keys-for-Open-Source-Applications-on-Windows/git/ (MEDIUM, third-party reference)
- KiCad library licence (CC-BY-SA 4.0 with exception; collections are share-alike): https://www.kicad.org/libraries/license/ , https://www.spdx.org/licenses/KiCad-libraries-exception.html (HIGH)
- KiCad table precedence (project overrides global by nickname): https://docs.kicad.org/6.0/ca/pcbnew/pcbnew_footprints_and_libraries.html , https://forum.kicad.info/t/search-order-of-package-footprint-libraries/13199 , https://archive.lists.launchpad.net/kicad-developers/msg32246.html (MEDIUM, older docs and forum)
- From general knowledge, unverified in this session (LOW-MEDIUM): git-filter-repo behaviours (refuses non-fresh clones, drops `origin`, does not touch commit messages without `--replace-message`), submodule removal steps, KiCad `.lck` lock files, PySide6 wheels and free-threaded Python.

---
*Pitfalls research for: public Windows KiCad library manager (v3.0)*
*Researched: 2026-11-22*
