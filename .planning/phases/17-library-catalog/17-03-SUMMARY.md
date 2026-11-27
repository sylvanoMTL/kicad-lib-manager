---
phase: 17-library-catalog
plan: 03
subsystem: catalog
tags: [git, hardened-argv, ls-remote, fetch, layering, ast, slow-tests, tdd]

requires:
  - phase: 17-library-catalog
    provides: catalog.gitnet tracer runner (NetGit, _argv, _env, _execute, clone_shallow, head_commit), procs.start_process, tests/catalogfixtures.py
provides:
  - catalog.gitnet full surface (ls_remote, default_branch, fetch_shallow, reset_hard, status_entries, changed_paths, tree_paths, read_blob, config_problems, version_issues, percent, parse_name_status)
  - AST layering rules for the catalog package and the commit-path import closure (tests/test_catalog_layering.py)
  - real-git proofs of the hardened behaviour on file:// repositories (tests/test_catalog_gitnet_git.py, slow)
affects: [17-04, 17-05, 17-06, 17-07, 17-10, 17-11, 17-13]

plan_head_before: c7bf90123c3889513c13cf32065594204c6953e8
plan_head_after: 01ed59d07063c3be617897a0cd491de919328a96

actuals:
  tokens: 17600
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Every in-clone git call: .git folder pre-check, then GIT_DIR and GIT_WORK_TREE name the clone, decisions on exit codes and plumbing output only"
    - "Commit-path closure rule: BFS over the package import graph (lazy imports included) from the commit-path roots must not reach catalog.gitnet or catalog.githubapi"
    - "Layering tests parametrized over the catalog modules present on disk, so later plans add modules without a skip or an edit here"

key-files:
  created:
    - tests/test_gitnet.py
    - tests/test_catalog_layering.py
    - tests/test_catalog_gitnet_git.py
  modified:
    - kicad_lib_manager/catalog/gitnet.py

key-decisions:
  - "MIN_NET_GIT = (2, 32): GIT_CONFIG_GLOBAL arrived in Git 2.32.0; below it the user's global git config would apply, so network actions are refused (D-29)"
  - "MIN_NET_GIT_WARN = (2, 49, 1) by plain tuple comparison, as D-11 and the plan say (see Issues Encountered for 2.50.0)"
  - "An address with a user name or password is refused with git.bad_url before git starts, in clone_shallow, ls_remote, default_branch and fetch_shallow (the plan's credential prohibition)"
  - "config_problems treats a line its reader does not understand as a problem, so an empty list means the whole config was understood"

requirements-completed: [CAT-11, CAT-07, CAT-04]

coverage:
  - id: D1
    description: "catalog.gitnet offers ls_remote, default_branch, fetch_shallow, reset_hard, status_entries, changed_paths, tree_paths, read_blob with pinned argv and the in-clone environment, deciding on exit codes only"
    requirement: "CAT-07"
    verification:
      - kind: unit
        ref: "tests/test_gitnet.py (29 tests, recording starter)"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_ls_remote_codes"
        status: pass
    human_judgment: false
  - id: D2
    description: "fetch_shallow then reset_hard(previewed sha) moves a clone after a normal advance and after a force-push to an unrelated history"
    requirement: "CAT-04"
    verification:
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_fetch_then_reset_after_an_advance_and_a_force_push"
        status: pass
    human_judgment: false
  - id: D3
    description: "A hostile global core.hooksPath hook runs for a plain git clone but not for clone_shallow; LFS files stay pointers and no hook file appears"
    requirement: "CAT-11"
    verification:
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_hostile_global_hooks_do_not_run"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_lfs_pointer_stays_a_pointer"
        status: pass
    human_judgment: false
  - id: D4
    description: "file:// is refused by the protocol policy unless NetGit.allow_file is set, so production clones can only use https"
    requirement: "CAT-11"
    verification:
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_file_url_is_refused_without_allow_file"
        status: pass
    human_judgment: false
  - id: D5
    description: "No command in a folder without its own .git can climb into the collection repository; GIT_DIR/GIT_WORK_TREE stop discovery even for an empty .git folder"
    requirement: "CAT-11"
    verification:
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_in_clone_calls_never_reach_the_parent"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_gitnet_git.py#test_in_clone_env_stops_discovery_even_for_a_fake_git_folder"
        status: pass
    human_judgment: false
  - id: D6
    description: "The commit path (gitops, importer, commit panel, import and migration windows, changes, atomic_fixes) cannot reach catalog.gitnet or catalog.githubapi, however many modules lie between; a synthetic tree that breaks the rule fails the test"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_catalog_layering.py#test_commit_path_cannot_reach_the_network"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_layering.py#test_guard_flags_a_commit_path_that_reaches_the_network"
        status: pass
    human_judgment: false
  - id: D7
    description: "The catalog package is Qt-free and subprocess-free, imports only where ALLOWED says, names no gitops commit or init function; gitnet imports only models and procs; gitops.ALLOWED_SUBCOMMANDS unchanged"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_catalog_layering.py (per-module rules and synthetic guard proofs), tests/test_gitops.py"
        status: pass
    human_judgment: false
  - id: D8
    description: "version_issues refuses below Git 2.32 and warns below 2.49.1 with the UI-SPEC text; config_problems lists every clone config key outside the allow-list"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_gitnet.py#test_version_issues, #test_config_problems_allow_list, #test_config_problems_sees_what_a_careless_parser_misses"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 03: Hardened catalog git runner Summary

**catalog/gitnet.py now has every network and in-clone git call Add, Update, Reinstall and the update check need (ls-remote, shallow fetch plus reset to the previewed sha, plumbing reads, version policy, clone-config allow-list), with argv pinned in the quick run, AST rules that cut the commit path off from it, and slow real-git proofs of the hook, LFS, protocol and no-climb behaviour.**

## Performance

- **Duration:** about 11 min
- **Started:** 2026-11-27T08:51:30Z
- **Completed:** 2026-11-27T09:03Z
- **Tasks:** 2
- **Files:** 1 modified, 3 created

## Final signatures (read by plans 17-04, 17-07, 17-10)

```python
# kicad_lib_manager/catalog/gitnet.py  (added or changed by this plan)
MIN_NET_GIT = (2, 32); MIN_NET_GIT_WARN = (2, 49, 1); LS_REMOTE_TIMEOUT = 20.0; FETCH_TIMEOUT = 3600.0
@dataclass(frozen=True) class RemoteHead: sha: str
def version_issues(version: tuple[int, ...] | None) -> tuple[Issue | None, Issue | None]   # (refusal, warning)
def ls_remote(net, url, branch, *, cancel=None) -> RemoteHead | Issue
def default_branch(net, url, *, cancel=None) -> tuple[str, str] | Issue                      # (branch, sha)
def fetch_shallow(net, clone, url, branch, *, progress=None, cancel=None) -> str | Issue     # fetched sha
def reset_hard(net, clone, sha) -> NetRun | Issue                                            # ValueError unless 40 lower-case hex
def status_entries(net, clone) -> list[str] | Issue                                          # rename source not counted twice
def changed_paths(net, clone, sha) -> list[tuple[str, str]] | Issue                          # ValueError unless sha is 40 hex
def tree_paths(net, clone, rev) -> list[str] | Issue                                         # rev: 40 hex or HEAD, else ValueError
def read_blob(net, clone, rev, path) -> bytes | None
def config_problems(clone) -> list[str]                                                      # [] only for a fully understood, allow-listed config
def percent(line) -> int | None;  def parse_name_status(raw) -> list[tuple[str, str]]
# changed: clone_shallow progress now receives (text, percent|None); head_commit now has the .git pre-check
```

Issue codes added: `git.not_found`, `git.too_old`, `git.old_version`, `git.branch_missing`, `git.unreachable`, `git.not_a_clone`, `git.fetch_failed`, `git.reset_failed` (all from the plan), plus `git.bad_url` and `git.read_failed` (see Deviations). ValueError is raised for a branch name that could be read as an option or refspec, for a non-sha passed to reset_hard / changed_paths, and for a rev that is not a sha or `HEAD`.

## Version sources (D-29, D-11)

- **2.32:** the installed Git's own release notes, `Documentation/RelNotes/2.32.0.adoc` lines 89 to 92 ("introduce GIT_CONFIG_GLOBAL to override the global configuration file"), found under `mingw64/share/doc/git-doc/RelNotes/` of the Git for Windows 2.49.0 install. This closes assumption A2 of the research.
- **2.49.1:** CVE-2025-48384, as recorded in 17-RESEARCH (NVD: fixed in 2.43.7, 2.44.4, 2.45.4, 2.46.4, 2.47.3, 2.48.2, 2.49.1 and 2.50.1). Not re-fetched in this run (no network access to those pages was needed).

## Layering ALLOWED map as written (tests/test_catalog_layering.py)

Keys and values are dotted names relative to `kicad_lib_manager`:

```
catalog            set()
catalog.urls       {models}
catalog.licences   set()
catalog.gitnet     {models, procs}
catalog.githubapi  {models}
catalog.manifest   {models, fsutil, collection, catalog.urls}
catalog.curated    {models, catalog.licences}
catalog.validate   {models, fsutil, kicad_files, collection, library_scanner}
catalog.ops        {models, fsutil, collection, gitops, kicad_process, library_scanner, catalog.manifest, catalog.validate,
                    catalog.urls, catalog.curated, catalog.gitnet, catalog.githubapi, catalog.licences}
catalog.status     {models, collection, catalog.manifest, catalog.curated, catalog.gitnet, catalog.licences}
catalog.selection  {models, collection}
```

The commit-path roots are `gitops`, `changes`, `atomic_fixes`, `widgets.commit_panel`, `widgets.import_dialog`, `widgets.migration_dialog` and every `importer.*` module; the test fails if one of those names disappears (a rename cannot empty the rule). Forbidden commit names: `commit_paths, commit_gitlink, add_intent, unstage, create_tag, init_repository, run_git`.

## Test counts

- `tests/test_gitnet.py`: 29 test functions (31 cases), quick, no process started.
- `tests/test_catalog_layering.py`: quick, AST only, 0 skipped (together with `test_layering.py` and `test_importer_layering.py`: 73 passed).
- `tests/test_catalog_gitnet_git.py`: 13 slow tests on local bare repositories (with `test_catalog_tracer.py` under `--full`: 19 passed).
- Guards unchanged and green: `tests/test_gitops.py` (EXPECTED_ALLOWED), `tests/test_procs.py`, `tests/test_procs_stream.py`, `tests/test_annotations_resolve.py`.

## Task Commits

1. **Task 1 RED:** `342edc6` (test) 29 tests for the full runner, plus stub signatures so they fail on the planned assertions
2. **Task 1 GREEN:** `52d77d3` (feat) the full hardened gitnet surface
3. **Task 2:** `01ed59d` (test) layering rules and the slow real-git proofs

TDD note: the RED run was 27 failed, 4 passed (the 4 that passed on the stubs check facts that already held: the subcommand set, the 2.32 and 2.25 floors, the refusal of `push`/`submodule`). The failures were assertion failures against stub return values (`None`, empty), not import errors. `gsd_run check tdd-red-evidence` was not run: the plan is `type: execute` and `workflow.tdd_mode` is off. Task 2's tests exercise code that Task 1 already wrote, so they passed on the first run (apart from two mistakes in the tests themselves, below); no flag in gitnet had to be changed after a slow proof.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Refuse an address with user info before git starts**
- **Found during:** Task 1
- **Issue:** the plan's prohibition says URLs with user info are refused (CAT-11, CAT-03), but 17-01 only stripped user info from output.
- **Fix:** `_bad_url` returns Issue `git.bad_url` ("The address must not contain a user name or a password.") in `clone_shallow`, `ls_remote`, `default_branch` and `fetch_shallow`; tested without a process start.
- **Files modified:** kicad_lib_manager/catalog/gitnet.py, tests/test_gitnet.py
- **Commit:** 52d77d3

**2. [Rule 2 - Missing critical] Validate positional branch and rev arguments**
- **Found during:** Task 1
- **Issue:** a branch is a positional fetch/ls-remote argument (`main:other` would be a refspec, `-x` an option) and a rev is a positional ls-tree/cat-file argument.
- **Fix:** `_check_branch` and `_check_rev` raise ValueError before any git runs (the same shape as the plan's `reset_hard` rule).
- **Commit:** 52d77d3

**3. [Rule 2 - Missing critical] head_commit gets the .git pre-check**
- **Found during:** Task 1
- **Issue:** the plan says every in-clone call refuses a folder without its own `.git`; 17-01's `head_commit` ran without the check.
- **Fix:** it now goes through the same `_in_clone` helper (behaviour for a real clone is unchanged; 17-01 tests still pass).
- **Commit:** 52d77d3

**4. [Rule 3 - Blocking] Two extra Issue codes and the 17-01 percent hook**
- `git.read_failed` is the code for a failing status, diff-tree or ls-tree (the plan lists no code for them); `clone_shallow` now passes `percent(line)` where 17-01 passed `None`, as 17-01's summary announced.
- **Commit:** 52d77d3

**5. [Test mistakes fixed before the commit]** `test_guard_flags_violation[upward-import]` imported `run_git`, which the commit-name rule also flags; it now imports `git_version`. The force-push test compared `changed_paths` in git's tree order; it now sorts. Both are test-only, found in the first run of the new module.

**Total deviations:** 4 auto-fixed (3 Rule 2, 1 Rule 3) plus 1 test correction. **Impact:** all strengthen the plan's stated prohibitions and must-haves; no scope beyond the gitnet runner.

## Issues Encountered

- **Git 2.50.0 gets no old-Git warning.** The plan and D-11 say "warn below 2.49.1" and pin (2, 49, 1) and (2, 50, 1) as quiet, which a tuple comparison gives; 2.50.0 is also in the CVE-2025-48384 range (fixed in 2.50.1) but is compared as newer than 2.49.1. The catalog is unaffected by the CVE class (no submodule recursion, `core.symlinks=false`), so this is only the warning text; the UI plan or the owner may want an exact fixed-versions table.
- `config_problems` reads the file as text and does not understand every corner of git's config syntax (for example a quoted multi-line value): such a line is reported as `unreadable line N`, which blocks ops in a clone with a non-empty list. A config git wrote for these clones passes (checked on real clones, including after fetch and reset).

## Known Stubs

None. The RED-commit stubs were all replaced in 52d77d3.

## Threat Flags

None beyond the plan's threat model; T-17-05 (config allow-list, in-clone `-c` overrides), T-17-06 (https only, helper cleared, user info refused), T-17-07 (`.git` pre-check plus GIT_DIR/GIT_WORK_TREE) and T-17-08 (commit-path closure rule) are mitigated and proven as planned.

## Next Phase Readiness

Plans 17-07 and 17-10 can build plan_update and apply on `fetch_shallow` + `changed_paths` + `tree_paths` + `read_blob` + `reset_hard`, and must call `config_problems(clone)` before any in-clone git call. Plan 17-04 adds `catalog.urls`, which should reuse the userinfo rule (`gitnet._USERINFO_RE` is private; urls validates its own https shape). Later plans that add catalog modules only extend nothing here unless they need an import outside the ALLOWED entry above.

## Self-Check: PASSED

Created files exist (tests/test_gitnet.py, tests/test_catalog_layering.py, tests/test_catalog_gitnet_git.py; gitnet.py modified); commits 342edc6, 52d77d3 and 01ed59d are on main; the plan's three automated commands pass (test_gitnet + test_gitops + test_procs; layering trio 73 passed with 0 skipped; slow module 13 passed under `--full`); acceptance greps print 1, 1, 29 (at least 11), 1, 1, 1; prepublish scan clean on all four files.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
