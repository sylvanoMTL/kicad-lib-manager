# Tests

This folder holds the pytest suite for the KiCad Library Manager and its part importer.

## How to run

Run these from the repository root with the project's virtual environment.

- Install the test dependencies first: `.\env\Scripts\python.exe -m pip install -r requirements-dev.txt`.
  Install them in the venv you run the tests from.
  The main checkout's venv is the app's runtime venv, so it needs them only when you run the tests there.
  Without pytest-xdist installed, pytest stops with `unrecognized arguments: -n`.
- Quick run: `.\env\Scripts\python.exe -m pytest`.
  It runs in parallel workers and skips the tests marked slow.
  It is the same run the GSD test gate uses.
- Full run: `.\env\Scripts\python.exe -m pytest --full`.
  It runs the slow tests too.
- Serial reference: `.\env\Scripts\python.exe -m pytest --full -n 0`.
- One module of slow tests: `.\env\Scripts\python.exe -m pytest tests/test_commit_step.py --full`.
  Without `--full` a module whose tests are all slow ends with `no tests ran` (exit code 5).
- Only the tests that run the real kicad-cli 10 binary: `.\env\Scripts\python.exe -m pytest -m kicad_cli`.
- Only the WurthElektronik corpus: `$env:KICAD_TEST_CORPUS = "<collection folder>"`, then `.\env\Scripts\python.exe -m pytest --full -m wurth`.
  The `wurth` tests are corpus tests, so without `KICAD_TEST_CORPUS` they are deselected.
- The corpus run (the tests that read a real library collection and the real vendor downloads):
  `$env:KICAD_TEST_CORPUS = "<collection folder>"` in PowerShell, then bare `.\env\Scripts\python.exe -m pytest`, or `--full -m corpus` for the slow ones too.
  `<collection folder>` is a folder that holds `Custom/` (see "Corpus and KiCad-install tests" below).
- Reproduce a CI runner without KiCad: `$env:KICAD_TEST_HIDE_KICAD = "1"`, then bare `.\env\Scripts\python.exe -m pytest`.
  Clear a variable again with `Remove-Item Env:KICAD_TEST_CORPUS`.
- Debugging: add `-n 0`.
  `--pdb`, `-s` and `breakpoint()` need it, because a worker has no terminal.
- Shell-safe fallback for `--full`: `-m "slow or not slow"`.
  Windows PowerShell 5.1 drops an empty `-m ""`, so `--full` or this spelling are the safe ones.

The quick run stays under 10 minutes, so it fits the GSD gate, and the full run takes at most half the serial time.
The measured times are in `.planning/phases/14-test-suite-speed-up/MEASUREMENTS.md`.
Bare `pytest` already prints the reason for every skip (`-ra` is set in `pyproject.toml`).

## Slow tests

A test is slow when it creates a real git repository, reads the Wurth corpus, runs kicad-cli, or is among the 50 slowest tests measured in `.planning/phases/14-test-suite-speed-up/BASELINE.md`.
The quick run skips them with the default `-m 'not slow'`; `--full` clears that.
Tests that use the `wurth` or `kicad_cli` marks or the `kicad_cli_path` fixture are marked slow automatically.
The other tests are marked `@pytest.mark.slow` by hand.
Strict markers stay on, so a misspelled mark is an error.

A test that creates a real git repository must carry `@pytest.mark.slow`, otherwise it fails with one of two messages.
- A test that uses a repository builder from `tests/gitfixtures.py` fails before any git work: `<nodeid> builds a real git repository: mark it @pytest.mark.slow`.
- A test that starts git itself fails at teardown, with or without `@requires_git`: `<nodeid> creates a real git repository (<command>): mark it @pytest.mark.slow`.
  The command is `git init`, `git clone`, `git submodule add` or `git submodule update --init`.

### Publishing-control tests that CI does not run

CI runs the quick `pytest` only (`.github/workflows/ci.yml` must not contain `--full`).
The behavioural tests of the publishing controls that need a real git repository are slow, so CI never runs them:
`tests/test_githooks.py` (pre-push block, the commit-msg hook as a git hook), `tests/test_prepublish_scan.py` (exit codes and the history walk on a repository),
`tests/test_cutover_collection.py` and `tests/test_split_export.py` (the export builder, the planning sync, the cutover).
The commit-msg hook itself is tested in the quick form (the hook run on a message file, no repository), and the scan's unit tests run in CI.
The library catalog has four more slow modules that start real git: `tests/test_catalog_tracer.py` (one library from add to scan), `tests/test_catalog_gitnet_git.py` (the hardened git runner),
`tests/test_catalog_ops_git.py` (add, update, remove against real repositories) and `tests/test_wurth_to_catalog.py` (the one-off Wurth conversion script).
They use local `file://` repositories that the tests build themselves and never the network (CAT-11), so they are safe to run offline.
The rest of the catalog tests are quick and use fake git runners.
Run the slow ones before every publish:

```
.\env\Scripts\python.exe -m pytest --full tests/test_githooks.py tests/test_prepublish_scan.py tests/test_cutover_collection.py tests/test_split_export.py tests/test_catalog_tracer.py tests/test_catalog_gitnet_git.py tests/test_catalog_ops_git.py tests/test_wurth_to_catalog.py
```

## Timeouts

Every test has 300 s (`timeout = 300`, thread method, in `pyproject.toml`).
`test_wurth_corpus_parse_budget` has 900 s.

Under workers a timeout ends the worker, and the failure report reads two lines:
`TIMEOUT <nodeid> after <N> s: pytest-timeout ended the worker (rerun with -n 0 to see its stack dump)`, above xdist's `worker 'gwN' crashed while running '<nodeid>'`.
A crash without the first line is a real crash, not a timeout.
Rerun that test with `-n 0 --timeout=<s>` to get pytest-timeout's own `Timeout` banner and the stack dump.

## Your own settings stay out

Every test gets its own empty user folders (`APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`) and its own QSettings ini.
`KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR` and `WE_3DMODEL_DIR` are removed; a test that needs one sets it with `monkeypatch`.
`KICAD_CONFIG_HOME` points at the test's own folder, so kicad-cli reads and writes its config there and never reads yours.
No test reads your real KiCad config unless you set `KICAD_TEST_REAL_CONFIG=1`, which opts in the read-only `local_kicad` tests.

Two run-level guards compare your real folders before and after the run:
- `the test run changed the real app state: <paths>` fails the run.
- `warning: KiCad's own config changed during the run (was KiCad open?): <paths>` only warns.

Both name paths only, never contents.
If you used the app or KiCad during a run, run the suite again.

## Shared git templates

The git repository builders copy a template that is built once per run in the pytest base temp, under a lock, and removed at the end of the run.
Old `gitfixture_template_*` folders in `%TEMP%` from runs before Phase 14 can be deleted by hand; the tests never delete them.
Pass `--basetemp` only as a one-off (for example a short path), never in `addopts`: pytest wipes it at start, so two runs at once would destroy each other.

## Regression gate

A run of only slow test files without `--full` ends with `no tests ran` (exit code 5).
The GSD regression gate can hit this when the earlier phase's test files are all slow.
Add `--full` for those files.

## Corpus and KiCad-install tests

The tool repository holds no library data, so a fresh clone has no `Custom/`, no WurthElektronik submodule and no vendor downloads.
Tests that need such data or a KiCad install are closed behind two markers, and a closed test is deselected with a printed count, never skipped.

- `corpus`: the test reads a real library collection: the real vendor downloads under `<collection>/downloaded_examples/`, the collection's live `Custom/`, or the WurthElektronik corpus.
  `wurth` implies `corpus` (and `slow`).
  The collection is named by `KICAD_TEST_CORPUS`, a folder that holds `Custom/`.
  Without it (unset or blank) every corpus test is deselected and the run prints:
  `deselected: <n> corpus (set KICAD_TEST_CORPUS to a collection folder to run them)`.
- `needs_kicad`: the test reads the stock KiCad footprints and symbols folders of an installed KiCad.
  Without an install, or with `KICAD_TEST_HIDE_KICAD=1`, these tests are deselected and the run prints:
  `deselected: <m> needs_kicad (no KiCad install found)`.
  `KICAD_TEST_HIDE_KICAD` (any value but blank or `0`) also makes the scanner find no KiCad, so a workstation behaves like a CI runner.
  The line is absent when KiCad is found, because nothing is deselected.
- A `KICAD_TEST_CORPUS` that is not a collection is a usage error (exit code 4) instead of a silent deselect:
  `KICAD_TEST_CORPUS=<value> is not a library collection: <no such folder | not a folder | it has no Custom folder>`.
- The counts are the same with workers and with `-n 0`.
- The public tests use synthetic samples only.
  The Ultra Librarian sample is built by `tests/ulfixtures.py`; the SnapEDA and SamacSys samples by `tests/vendorfixtures.py`.
  No vendor zip is stored in the repository.
- `tests/test_corpus_audit.py` keeps it that way.
  It fails when a test module builds a path from the repository root to `Custom`, `WurthElektronik`, `downloaded_examples` or `.planning`, when a skip reason says a vendor download, the Custom submodule or a KiCad install is missing, or when a module that calls `corpus_path` or `corpus_root` carries no `corpus` mark.
  Read repository data through `corpus_path(...)` from `tests/corpusfixtures.py` behind the mark.

## Skip budget

A run from a fresh clone must pass within a budget of skips (at most 10), so a closed gate cannot hide a broken suite by skipping it.
Corpus and needs_kicad tests are deselected and do not count against it.
CI checks the budget with `python scripts/check_skip_budget.py junit.xml --max-skips 10 --min-passed 3500` after a run with `--junitxml=junit.xml`.
The check fails on any failure or error, on more than 10 skips, and on fewer than 3500 passed.

Measured on 2026-11-24 on the workstation (Windows 11, CPython 3.14) from a `git clone --no-local` of the branch with `downloaded_examples/` deleted and `Custom/` and `WurthElektronik/KiCad-Library` empty, quick run with workers:

| Run | Passed | Skipped | Deselected | Time |
| --- | --- | --- | --- | --- |
| KiCad installed | 4013 | 3 | 41 corpus | 2 min 3 s |
| `KICAD_TEST_HIDE_KICAD=1` | 3998 | 3 | 41 corpus, 15 needs_kicad | 1 min 41 s |
| `KICAD_TEST_CORPUS` set to a collection | 4083 | 3 | none | 2 min 14 s |

The three skips are the same in all runs: the two symlink skips and the `local_kicad` opt-in (see "Expected skips").

## The rule: never touch the live Custom/

The suite must never write to the live `Custom/` folder, and no test result may depend on which parts it holds.
Adding or removing a real part in `Custom/` must not change a test result.
Only a corpus run (`KICAD_TEST_CORPUS` set) reads a live `Custom/`, and only that of the collection it names.

- Tests that need a target library use one of two synthetic `Custom/` fixtures from `tests/conftest.py`, built by `tests/customfixtures.py`.
  Both write into a temporary folder and never contain the Ultra Librarian sample part.
  - `synthetic_custom` (`write_synthetic_custom` with the default `naming="v1"`) keeps today's v1 names.
    It writes one library per format version (20211014, 20231120, 20241209, 20251024) and models the live tree for the scan tests.
  - `atomic_custom` (`naming="atomic"`) holds the `Atomic_` install targets, with their footprints in one `Atomic_Footprints.pretty`.
    The install and importer tests use it.
- Every test that names a footprint location goes through `footprint_library_for` in `tests/zipfixtures.py`, so the name of the shared footprint library lives in one place.
- Do not copy real libraries into fixtures.
  The one exception is the opt-in atomic UAT builder (`tests/test_atomic_uat.py`): it reads the live `Custom/` only to make a scratch copy outside the repository and never writes it, and it does not run unless `KICAD_ATOMIC_UAT_DIR` is set.
  The other opt-in builder (`KICAD_IMPORT_UAT_DIR`) does not read the live `Custom/` at all.
- A session guard in `tests/conftest.py` fails the run if the live `Custom/` changes while the suite runs, and names the paths: `the test run changed the live Custom/ folder: <paths>`.
  It watches `<KICAD_TEST_CORPUS>/Custom` during a corpus run and nothing otherwise (a fresh clone has no live `Custom/` to watch).
  The guard runs in every worker.
  If you edit `Custom/` by hand during a corpus run, run the suite again.

## Expected skips

Each row is one condition that makes tests skip. `pytest -rs` prints the message in the second column.

| Condition | Message printed by `pytest -rs` | Why | How to enable |
| --- | --- | --- | --- |
| No kicad-cli 10 | `kicad-cli not found (these tests need KiCad 10)`, `could not run kicad-cli version at <exe>: <detail>`, or `needs kicad-cli 10, found <version> at <exe>` | The real-binary tests pin KiCad 10 (format 20251024, generator 10.0) and skip on any other major version. | Install KiCad 10. The newest install is used. |
| Symlinks not permitted | `symlinks not permitted here: [WinError 1314] A required privilege is not held by the client: ...` | Creating a symbolic link needs a privilege that a normal Windows account does not have. | Turn on Windows Developer Mode, or run the tests from an elevated shell. |
| `KICAD_IMPORT_UAT_DIR` unset | `set KICAD_IMPORT_UAT_DIR to build the manual UAT scratch install` | This test builds a scratch install for the owner to open in KiCad 10. It is not an automated check. | Set `KICAD_IMPORT_UAT_DIR` to a folder outside the repository, then run `tests/test_install_e2e.py::test_uat_scratch_install -s` and open the result in KiCad 10. |
| `KICAD_ATOMIC_UAT_DIR` unset | `set KICAD_ATOMIC_UAT_DIR to build the atomic-check UAT scratch repo` | This test builds a scratch copy of the repo with Atomic_ libraries for the owner to open in the app. It is not an automated check. | Set `KICAD_ATOMIC_UAT_DIR` to a folder outside the repository, run `tests/test_atomic_uat.py::test_uat_atomic_scratch -s`, then start the command it prints. |
| `local_kicad` | `reads your real KiCad config tables: set KICAD_TEST_REAL_CONFIG=1 to run` (the `local/opt-in` item of `tests/test_roundtrip_corpus.py`) | These tests are opt-in. Without the variable they collect as one skipped item and nothing reads your real KiCad config. With it they read your KiCad library tables read-only; when there are none the skip is `no KiCad user config tables found`. | Set `KICAD_TEST_REAL_CONFIG=1`. Deselect them with `-m "not local_kicad"`. |
| Case-sensitive folder cannot be made | `could not make a case-sensitive folder: <reason>` | `tests/test_case_sensitive_install.py` proves case-twin rollback and overwrite on a real case-sensitive folder (VER-02). | On Windows 11, `fsutil file setCaseSensitiveInfo` works without admin rights on an NTFS volume; on macOS use a case-sensitive APFS volume. |

In the quick run on the workstation the expected skips are three (measured, see "Skip budget"): the two symlink skips (`tests/test_model_source.py` and `tests/test_package_folder.py`) and the `local_kicad` opt-in skip.
The `KICAD_IMPORT_UAT_DIR` and `KICAD_ATOMIC_UAT_DIR` skips and the kicad-cli 10 skips appear only in a `--full` run, because those tests are slow.
A missing vendor download, Custom submodule or KiCad install is not a skip any more: those tests are deselected (see "Corpus and KiCad-install tests").
Anything else that is skipped is a finding.

## Other conditional skips

These skip only on a machine that lacks something. None of them skip on the workstation.

- Case-sensitive volume: `case-sensitive volume` (`tests/test_commit_plan.py`).
- Directory links unavailable: `directory links are not available here` (`tests/test_install_apply.py`).
- Junctions unavailable: `junctions are a Windows feature` and `could not create a junction here` (`tests/test_package_folder.py`).
- Git not on PATH: `git is not on PATH` (`tests/gitfixtures.py`, `tests/test_fixtures.py`, `tests/test_package_zip.py`).
- Windows PowerShell missing: `Windows PowerShell not found (the paste-safety test runs the generated command in it)` (`tests/test_commit_step.py`).
  It runs on the workstation.
- A zipfile feature missing: `this Python's zipfile has no <name>` (`tests/test_package_zip.py`).
- Installed KiCad is not version 10: `installed KiCad is not version 10` (`tests/test_stems.py`, `tests/test_siblings.py`).
  `tests/test_real_vendor_samples.py` prints `no KiCad 10 install with a stock symbols folder` for the same two conditions together.
  Without any KiCad these tests are deselected through `needs_kicad`, so the skip only shows when an older KiCad is installed.
- `tomllib` missing on Python 3.10: `tests/test_manifests.py` skips through `importorskip`.
- Windows-only behaviour on another platform:
  `held-open handles block os.replace only on win32`, `case is only ignored on Windows`,
  `replacing a case twin leaves one entry only on NTFS (research spike S7)`.
- Importer package folder missing: `the kicad_lib_manager/importer package folder is missing from this checkout` (`tests/test_importer_layering.py`).

## Migration tests (Phase 13)

Every migration test builds its own `Custom/` under `tmp_path` from `tests/migrationfixtures.py`
(a rich synthetic v1 tree, never the live repo's `Custom/`), and its git repos with
`tests/gitfixtures.py` (throwaway repos, never the live Custom submodule or parent repo).

- `tests/test_migration_full.py`, `tests/test_migration_commit.py`,
  `tests/test_migration_precheck.py` and `tests/test_commit_deletions.py` need a real git
  binary (`requires_git`) to exercise the tag, commit and precheck paths against a throwaway
  repo; they skip with `git is not on PATH` where git is unavailable.
- `tests/test_migration_families.py::test_real_kicad_loads_derived_library` is marked
  `@pytest.mark.kicad_cli` and skips with the same reason as the "No kicad-cli 10" row above
  (`kicad-cli not found (these tests need KiCad 10)`, or the version-mismatch variant) when
  KiCad 10's command-line tool is absent.

## Corpus health checks (read-only)

A few tests read the live `Custom/` of the collection on purpose (decision D-04).
They carry the `corpus` mark, so they run only with `KICAD_TEST_CORPUS` set, and they never write to it.
They fail when a live part breaks a rule, so a red result there is a finding about the live data, not a test bug.

- `test_kicad_files.py::test_live_custom_symbols`
- `test_naming_sanitize.py::test_sanitize_live_custom_names_unchanged`
- `test_scanner_issues.py::test_live_custom_model_findings_are_zero`
- the `custom/...` cases of the round-trip corpus in `test_roundtrip_corpus.py`
- the live-symbol tests of `test_edits.py`

## WurthElektronik corpus timing

The `wurth` tests read the pinned submodule commit `2e6e51b1bd78f89b31c358214642ba7e795872e0`.
Measured on 2026-10-25 on the workstation (Windows 11, CPython 3.14):

- Files in the corpus: 6034.
- Parsing every file once (`test_wurth_corpus_parse_budget`): 69.5 s, about 0.012 s per file.
- Whole `-m wurth` run: about 8 min 45 s.

The parse budget is `max(60 s, 0.05 s x number of files)` (`_WURTH_PARSE_BUDGET_PER_FILE` in `tests/test_roundtrip_corpus.py`).
For this corpus the budget is about 302 s.
The earlier fixed 60 s limit was too tight for 6034 files.

Current corpus, measured on 2026-11-22: 8016 files.
The parse budget for it is about 401 s (0.05 s x 8016).
The test has a 900 s timeout, and the parse itself took 46.52 s in the serial baseline (`.planning/phases/14-test-suite-speed-up/BASELINE.md`).
