---
phase: 15-choose-library-folder-and-new-collection
plan: 02
subsystem: process-start
tags: [subprocess, gitops, git-init, layering, ROOT-06]
requires: []
provides:
  - "procs.run_process(argv, *, runner=None, **kwargs): the one child-process starter"
  - "gitops.init_repository(ctx, repo, branch='main') and 'init' in ALLOWED_SUBCOMMANDS"
  - "gitops.INIT_MIN_VERSION = (2, 28)"
affects: [15-06 collection.create_collection, Phase 17 network git, Phase 21 frozen app]
tech-stack:
  added: []
  patterns: ["single process choke point with an AST rule", "allow-list edit held by an exact-set test"]
key-files:
  created:
    - kicad_lib_manager/procs.py
    - tests/test_procs.py
  modified:
    - kicad_lib_manager/gitops.py
    - kicad_lib_manager/kicad_process.py
    - kicad_lib_manager/importer/kicad_cli.py
    - tests/test_gitops.py
    - tests/test_layering.py
    - tests/test_importer_layering.py
decisions:
  - "run_process looks subprocess.run up per call, so every existing runner seam (GitContext.runner, run_cli(runner=), a patched subprocess.run) keeps working"
  - "init runs with --template= so a user-global init.templateDir cannot plant hooks in a new collection"
metrics:
  tasks: 2
  completed: 2026-11-23
status: complete
actuals:
  tokens: 14000
  tasks: 2
  commits: 4
plan_head_before: 14b857f9b99f67b25795f88084877b20a9b377ec
plan_head_after: 1503c2bcd54b303fc1e54516c296ef63d78ce8f8
---

# Phase 15 Plan 02: One process starter and an allow-listed git init Summary

`procs.run_process` is now the only place the app starts a child process (no-console-window flag, captured output, no stdin by default), and `gitops.init_repository` runs `git init --template= -b main` through the allow-list for new collections.

## What was built

- **Task 1** (RED `7e13e55`, GREEN `9afa4ed`): `kicad_lib_manager/procs.py` with `run_process`. `gitops.run_git`, `importer/kicad_cli.run_cli` and `kicad_process.kicad_running` (tasklist and ps) all start through it; the per-call `CREATE_NO_WINDOW` expressions are gone from those three modules. `tests/test_procs.py` covers the flag, the `input`/`stdin` rule, option pass-through (a caller's `creationflags` is OR-ed), call-time lookup of `subprocess.run`, exception pass-through, and an AST rule (`test_only_procs_starts_processes`) that no other module under `kicad_lib_manager/` references a subprocess starter or `os.system/popen/startfile/spawn*/exec*`. Layering tables know `procs` (leaf; gitops, kicad_process and importer.kicad_cli may import it) and the Qt-free import proof loads it.
- **Task 2** (RED `3c68f80`, GREEN `1503c2b`): `"init"` added to `ALLOWED_SUBCOMMANDS`, `INIT_MIN_VERSION = (2, 28)`, `_BRANCH_NAME_RE`, and `init_repository`, which raises `ValueError` before git starts for an odd branch (empty, leading dash, space, `..`, slash). `test_allow_list_is_exact_and_safe` stays exact with `init` added to `EXPECTED_ALLOWED`. The slow real-git test plants a hook in a user-global template (HOME `.gitconfig` `init.templateDir`), runs `init_repository`, and asserts the unborn branch is `main` and `.git/hooks` has no non-sample file. Checked that it fails when `--template=` is removed.

## Verification

- `pytest tests/test_procs.py tests/test_gitops.py tests/test_kicad_cli.py tests/test_kicad_process.py tests/test_layering.py tests/test_importer_layering.py -n 0 -q`: 141 passed.
- `pytest tests/test_gitops.py --full -m slow -k init_repository_real`: 1 passed.
- Acceptance greps: `def run_process` 1; `CREATE_NO_WINDOW` in the three modules 0; `run_process(` 4; `"procs"` in test_layering 3; `def init_repository` 1.

## Deviations from Plan

**1. [Rule 1 - Bug in existing test] `test_only_known_modules_import_subprocess` needed `procs.py`**
- **Found during:** Task 1
- **Issue:** The existing test pins the set of modules that import `subprocess` to gitops, kicad_process and kicad_cli; the new `procs.py` must import it, so the test failed. The plan said the existing tests pass unchanged, which was not quite right for this one.
- **Fix:** added `"procs.py"` to the expected set in `tests/test_gitops.py`.
- **Commit:** `9afa4ed`

**2. Acceptance-criterion count off by one (no code change)**
- `grep -c '"init",' kicad_lib_manager/gitops.py` prints 2, not 1: the allow-list entry and the `run_git(ctx, repo, "init", "--template=", ...)` call both match the pattern. Intent (init is allow-listed exactly once) holds; the exact-set test proves it.

**Total deviations:** 1 auto-fixed (Rule 1), 1 criterion-wording note. **Impact:** none on scope.

## Known Stubs

None.

## Threat Flags

None. T-15-05, T-15-06 and T-15-07 are mitigated as planned (fixed argv through `run_git`, `--template=` with a real-git test, AST rule for `procs`).

## Self-Check: PASSED

- Files exist: procs.py, tests/test_procs.py, edited modules and tests.
- Commits present on this branch: 7e13e55, 9afa4ed, 3c68f80, 1503c2b.
