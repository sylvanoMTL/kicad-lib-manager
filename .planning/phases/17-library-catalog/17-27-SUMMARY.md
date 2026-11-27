---
phase: 17-library-catalog
plan: 27
subsystem: startup
tags: [scratch-switch, isolation, startup, settings, backups, kicad-config, tdd]

requires:
  - phase: 17-library-catalog
    provides: settings.addon_index_file (17-22), the owner-check finding 8 and decision D-35 (17-17), the add-on list copy beside settings.ini (17-24)
provides:
  - "--scratch-root PATH / KICAD_LIBMGR_SCRATCH_ROOT: one folder that holds the app's settings ini, saved scans, add-on list copy and migration drafts, its backups and the folder it reads and writes KiCad's settings in"
  - kicad_lib_manager.userdirs, the Qt-free scratch state (set_scratch_root, scratch_root, settings_base, kicad_config_base, backup_base)
  - settings.use_scratch_settings, scratch-aware fsutil.default_backup_dir and library_scanner.find_kicad_config_dir
  - startup.check_scratch_folder, startup.scratch_root_arg, startup.apply_scratch_root
affects: [17-19, 17-20, 17-26]

plan_head_before: 14839dd1a454b011ef7f03f3e280b7f9e6626d5e
plan_head_after: 3f16b2f52c8e7138854f67657b4668ce16652daa

actuals:
  tokens: 33000
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Process-wide scratch state lives in one Qt-free leaf module (userdirs) that fsutil and library_scanner read at call time; every backup and KiCad-settings read or write already went through those two functions, so no caller changed"
    - "The conftest reset fixture depends on _isolated_user_state, so it is torn down first and puts back the QSettings folder and KICAD_CONFIG_HOME of that test's own isolated home"

key-files:
  created:
    - kicad_lib_manager/userdirs.py
    - tests/test_scratch_root.py
  modified:
    - kicad_lib_manager/startup.py
    - kicad_lib_manager/settings.py
    - kicad_lib_manager/fsutil.py
    - kicad_lib_manager/library_scanner.py
    - kicad_lib_manager.py
    - tests/conftest.py
    - tests/test_startup.py
    - tests/test_layering.py

key-decisions:
  - "Names: option --scratch-root, variable KICAD_LIBMGR_SCRATCH_ROOT; the command line wins over the variable (as for --library-root / KICAD_LIBMGR_ROOT). A variable that is set but blank is a bad value (exit 2), unlike KICAD_LIBMGR_ROOT where blank means unset"
  - "Layout under the scratch folder PATH: PATH/settings (QSettings path; the ini is PATH/settings/KiCadExtLibManager/settings.ini, and scan_cache, migration_draft and addon_index sit beside it), PATH/backups (every backup, including kicad_common/<version> and eeschema/<version> and the importer, migration and atomic-fix backups), PATH/kicad (KiCad's version folders, e.g. PATH/kicad/10.0/kicad_common.json). PATH/settings and PATH/kicad are created by the start; PATH/backups is created by the writers when they back up"
  - "While the switch is set os.environ KICAD_CONFIG_HOME is PATH/kicad, so kicad-cli (started with the inherited environment) reads the scratch KiCad settings; default_backup_dir returns PATH/backups for every platform value; find_kicad_config_dir without a base reads PATH/kicad and returns None when it holds no version folder (never the real settings); an explicit base still wins"
  - "The check order at start (startup._start_scratch), before any setting is read, any QSettings object is built or KICAD_CONFIG_HOME is changed: value blank, folder missing, not a folder, not writable (PATH/settings is created and a probe file written and removed). The check lives in startup.check_scratch_folder and is looked up at call time, so a test can replace it"
  - "tests/test_layering.py got userdirs as a stdlib-only leaf, allowed for fsutil and library_scanner, and in the Qt-free import list (a necessary consequence of the new import, the plan did not list the file)"

patterns-established:
  - "The start note comes first in the window's log: startup._start_scratch returns the Issue and start_window puts it before the resolution notes, so the first log line names the scratch folder"

requirements-completed: [CAT-12, CAT-09]

coverage:
  - id: D1
    description: "--scratch-root / KICAD_LIBMGR_SCRATCH_ROOT moves the settings ini, saved scans, add-on list copy and migration drafts under PATH/settings before anything is read, and the first log line names the folder at warning level"
    requirement: CAT-12
    verification:
      - kind: unit
        ref: "tests/test_scratch_root.py#test_scratch_root_moves_the_settings"
        status: pass
      - kind: unit
        ref: "tests/test_scratch_root.py#test_scratch_line_is_logged_first"
        status: pass
      - kind: unit
        ref: "tests/test_scratch_root.py#test_without_the_switch_nothing_moves"
        status: pass
    human_judgment: false
  - id: D2
    description: "Backups and KiCad's settings folder follow the switch (PATH/backups, PATH/kicad, KICAD_CONFIG_HOME for kicad-cli); a full run with the switch leaves the stand-ins for the real folders unchanged"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_scratch_root.py#test_backups_go_to_the_scratch_folder"
        status: pass
      - kind: unit
        ref: "tests/test_scratch_root.py#test_kicad_settings_come_from_the_scratch_folder"
        status: pass
      - kind: unit
        ref: "tests/test_scratch_root.py#test_real_folders_are_never_touched"
        status: pass
    human_judgment: false
  - id: D3
    description: "The environment variable alone moves the folders, the command line wins; blank, missing, file and unwritable values stop the start with exit code 2 and a reason before any setting is read, with no fallback"
    requirement: CAT-12
    verification:
      - kind: unit
        ref: "tests/test_scratch_root.py#test_env_switch_and_precedence"
        status: pass
      - kind: unit
        ref: "tests/test_scratch_root.py#test_bad_scratch_values_exit_2"
        status: pass
      - kind: unit
        ref: "tests/test_startup.py#test_parse_args_removes_the_scratch_switch_from_the_qt_arguments"
        status: pass
    human_judgment: false
  - id: D4
    description: "The per-test isolation of tests/conftest.py is only strengthened: the switch is cleared after every test and the QSettings folder and KICAD_CONFIG_HOME are put back"
    verification:
      - kind: unit
        ref: "tests/test_scratch_root.py#test_the_scratch_state_is_cleared_between_tests"
        status: pass
      - kind: integration
        ref: "env/Scripts/python.exe -m pytest -q (quick parallel run with the run-level guards): 5331 passed, 3 skipped"
        status: pass
    human_judgment: true
    rationale: "That no fixture of conftest.py was removed or narrowed is a review judgment (the plan marks the prohibition verification: judgment); the diff only adds one autouse fixture"

duration: 17min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 27: Scratch switch for owner checks Summary

**`--scratch-root` / `KICAD_LIBMGR_SCRATCH_ROOT` moves the app's settings ini, saved scans, backups and KiCad's settings folder under one checked scratch folder, with a first-line warning in the log and exit code 2 for a bad value, so owner rehearsals can no longer leak into the real folders (D-35).**

## Performance

- **Duration:** about 17 min (the start time was not recorded by a persisting shell; taken from the commit times and the clock)
- **Started:** 2026-11-27T17:45Z (approximate)
- **Completed:** 2026-11-27T18:02Z
- **Tasks:** 3
- **Files modified:** 10 (2 created)

## For plans 17-19 and 17-26: the switch as coded

- **Option and variable:** `--scratch-root PATH` and `KICAD_LIBMGR_SCRATCH_ROOT`; the command line wins. It combines with `--library-root` / `KICAD_LIBMGR_ROOT` (use it for the collection of the rehearsal).
- **Folders under PATH:** `settings` (the ini `settings/KiCadExtLibManager/settings.ini`, with `scan_cache`, `migration_draft` and `addon_index` beside it), `backups` (every backup of the app and of KiCad's settings), `kicad` (KiCad's version folders; `KICAD_CONFIG_HOME` is set to it for kicad-cli). PATH must exist before the start; the app creates `settings` and `kicad`.
- **To rehearse against KiCad's settings:** put a copy of a `kicad_common.json` in `PATH/kicad/<version>/` (an empty `PATH/kicad` means "KiCad's settings not found", never the real ones). The real KiCad settings, the real ini and the real backups are not read or written while the switch is set.
- **Start line (warning level, first line of the log), as coded:** `Working in the scratch folder {folder}: the app's settings, saved scans and backups and KiCad's settings are read and written there, and your real ones are not touched.`
- **Refusals (stderr, a message box when there is no stderr; exit code 2; before any setting is read):** `Not using the scratch folder {folder} (set by --scratch-root): {reason}` or `... (set by KICAD_LIBMGR_SCRATCH_ROOT): {reason}`, with the reason `the value is empty` (folder shown empty), `it does not exist`, `it is not a folder` or `the app cannot write there`. A set but blank variable is refused like a blank option.
- **Not covered by the switch (by design):** what the app reads from KiCad's install folders (stock libraries), the folders a user picks in file dialogs, the collection itself, and the Windows environment variables of other programs. A rehearsal that starts KiCad itself must set `KICAD_CONFIG_HOME` for KiCad separately.

## Accomplishments

- New Qt-free `userdirs` module holds the scratch state; `startup` checks and applies the switch before any setting is read, then logs the note first.
- `fsutil.default_backup_dir` and `library_scanner.find_kicad_config_dir` follow the switch, so every existing backup and KiCad-settings read or write (path variables, Pin Atomic Libraries, importer, migration, atomic fixes) is moved without changing a caller.
- `test_real_folders_are_never_touched` proves with temp folders only that a start, a saved choice, a saved scan, the add-on list copy and a confirmed path-variable change leave the stand-ins for the real settings, backups and KiCad config byte-for-byte and time-for-time unchanged.
- conftest gets an autouse reset that clears the switch and restores the QSettings folder and `KICAD_CONFIG_HOME` after every test.

## Task Commits

1. **Task 1 (tracer): scratch settings and start line** - RED `b363e5a` (test), GREEN `0769c5d` (feat)
2. **Task 2: backups and KiCad's settings folder follow the switch** - RED `c530863` (test), GREEN `8c538c5` (feat)
3. **Task 3: bad values, variable, precedence, usage text** - RED `d5c10cd` (test), GREEN `3f16b2f` (feat)

**Plan metadata:** the docs commit that follows this file.

### TDD RED evidence (semantic assessment)

`workflow.tdd_mode` was not passed by the orchestrator, so the gate classifier was not run; pytest's own report was read instead.

- Task 1 RED: `test_scratch_root_moves_the_settings` failed on its planned assertion (the ini was in the per-test qsettings folder, not under PATH/settings) and `test_scratch_line_is_logged_first` failed on the planned text (the first line was `Library folder: ... (set by --library-root)`). Two guard tests (`test_without_the_switch_nothing_moves`, the cleared-state test) failed with an ImportError for the not yet existing `userdirs` module: expected for a new module, not counted as RED evidence.
- Task 2 RED: the three tests failed on their planned assertions (backup folder not the scratch one, the real-looking KiCad folder found instead of None, no variable written in the scratch KiCad settings).
- Task 3 RED: eight parametrised cases of `test_bad_scratch_values_exit_2` failed because the start went on (the guard "a setting was read after a bad scratch value" fired) or raised while creating a folder. The variable and precedence tests and the `parse_args` test already passed after Task 1, which implemented the variable and the argument as the Task 1 action says.

## Files Created/Modified

- `kicad_lib_manager/userdirs.py` - the scratch state and the three derived folders
- `kicad_lib_manager/startup.py` - option, variable, `scratch_root_arg`, `apply_scratch_root`, `check_scratch_folder`, `_start_scratch`, the note first in the notes
- `kicad_lib_manager/settings.py` - `use_scratch_settings`
- `kicad_lib_manager/fsutil.py`, `kicad_lib_manager/library_scanner.py` - scratch-aware `default_backup_dir` and `find_kicad_config_dir`
- `kicad_lib_manager.py` - usage text
- `tests/test_scratch_root.py` - 16 test cases (new); `tests/test_startup.py` - one parse test; `tests/conftest.py` - the reset fixture; `tests/test_layering.py` - `userdirs` leaf

## Decisions Made

See `key-decisions` above. `CLAUDE.md` (Running the GUI) does not mention the switch yet: the plan lists no documentation file, so the owner-facing text is left for a later plan or quick task.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Layering test knew no `userdirs`**
- **Found during:** Task 2 (after adding the `userdirs` import to `fsutil` and `library_scanner`)
- **Issue:** `tests/test_layering.py::test_imports_point_only_downward[fsutil]` and `[library_scanner]` failed with "imports upward: {'userdirs'}"
- **Fix:** added `userdirs` as a stdlib-only leaf, allowed for `fsutil` and `library_scanner`, and to the Qt-free import list
- **Files modified:** tests/test_layering.py (not in the plan's file list)
- **Verification:** `tests/test_layering.py` passes
- **Committed in:** `8c538c5`

---

**Total deviations:** 1 auto-fixed (1 blocking). **Impact on plan:** none on behaviour; the layering table must name every module the package has.

## Issues Encountered

- One shell call (a stray `python3 -` ahead of the venv Python) hung and was moved to the background; it changed nothing that the later edits did not redo. The file `tests/test_scratch_root.py` ended up with LF line endings (new files in this repo are LF in git); no existing CRLF file was converted.

## Known Stubs

None.

## Threat Flags

None: the plan's threat model (T-17-69, T-17-70, T-17-71) is covered by `test_real_folders_are_never_touched`, `test_bad_scratch_values_exit_2` and `test_scratch_line_is_logged_first`.

## Next Phase Readiness

17-19 and 17-26 can start the app with `--scratch-root` (see "For plans 17-19 and 17-26"). 17-20 has no scratch step and keeps the switch off. The quick parallel run with the run-level guards passes (5331 passed, 3 skipped).

## Self-Check: PASSED

- Created files exist: `kicad_lib_manager/userdirs.py`, `tests/test_scratch_root.py`.
- Commits `b363e5a`, `0769c5d`, `c530863`, `8c538c5`, `d5c10cd`, `3f16b2f` are ancestors of HEAD; `git rev-list --count 14839dd..HEAD` was 6 before this file.
- Acceptance greps and the three automated commands pass; the extra modules named by the orchestrator (startup, settings, main_window_root, kicad_setup, fsutil, scan_cache, corpus_audit, custom_literals, layering, annotations_resolve, exit_with_hung_check, isolation, corpus_gate, customfixtures, catalog_layering, importer_layering, catalog_path_vars) pass with `-n 0`: 620 passed.
- Pre-publish scan clean before every commit.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
