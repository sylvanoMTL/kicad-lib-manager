---
phase: 17-library-catalog
plan: 01
subsystem: catalog
tags: [git, subprocess, staging, catalog-json, hardened-argv, tdd]

requires:
  - phase: 15-collection
    provides: collection.THIRD_PARTY_DIR and source_of, procs.run_process, fsutil.atomic_write_text
provides:
  - procs.start_process and StreamedProcess (streaming, cancellable, process-tree kill)
  - catalog.gitnet hardened network git runner (clone_shallow, head_commit)
  - catalog.manifest (catalog.json load/save)
  - catalog.ops stage_add / register_add / discard_staging (tracer scope)
  - tests/catalogfixtures.py (plumbing-built file:// upstream)
affects: [17-03, 17-04, 17-05, 17-06, 17-07, 17-10, 17-11, 17-13]

plan_head_before: dc3d5222fe0ada39b94cdb6a536020bf3af281fd
plan_head_after: cad7a0d6b5035ae637bf2b070cc239f69ea12423

actuals:
  tokens: 10500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Network git only through catalog.gitnet; every call a list argv with a hardened -c prefix and a from-scratch environment"
    - "Download into ThirdParty/.staging/<id>.<hex>/, check, then os.replace into ThirdParty/<id>/ and record in catalog.json"
    - "Test seam: NetGit.starter returns a procs.StreamOutcome, so quick tests start no process"

key-files:
  created:
    - kicad_lib_manager/catalog/__init__.py
    - kicad_lib_manager/catalog/gitnet.py
    - kicad_lib_manager/catalog/manifest.py
    - kicad_lib_manager/catalog/ops.py
    - tests/catalogfixtures.py
    - tests/test_catalog_tracer.py
    - tests/test_procs_stream.py
  modified:
    - kicad_lib_manager/procs.py

key-decisions:
  - "progress callbacks of clone_shallow and stage_add receive (text, percent) with percent always None until plan 17-03 adds percent(); later plans already expect the two-argument form"
  - "core.quotepath=false is part of _BASE_CONFIG (passed as -c), not a separate argument"
  - "run() checks stop() after every queued item, so a cancel set from a progress line is seen even when git ends within milliseconds, and a stop seen after the child exited still reports cancelled"
  - "A pipe held open by a grandchild after the child exits is waited for 2 s, then run() returns"

requirements-completed: [CAT-02, CAT-05, CAT-11]

coverage:
  - id: D1
    description: "A file:// library goes through staging into ThirdParty/<id>, catalog.json, the scan (source <id>) and the managed table URIs, with no .gitmodules and a shallow clone"
    requirement: "CAT-05"
    verification:
      - kind: integration
        ref: "tests/test_catalog_tracer.py#test_add_one_library_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "A repository with no KiCad libraries is refused with the plain-language text and leaves no staging folder, no ThirdParty/<id> and no catalog.json"
    requirement: "CAT-02"
    verification:
      - kind: integration
        ref: "tests/test_catalog_tracer.py#test_repository_without_libraries_is_refused"
        status: pass
    human_judgment: false
  - id: D3
    description: "Cancel during a download ends git and returns git.cancelled with the staging folder deleted"
    requirement: "CAT-11"
    verification:
      - kind: integration
        ref: "tests/test_catalog_tracer.py#test_cancel_during_clone_removes_staging"
        status: pass
      - kind: unit
        ref: "tests/test_procs_stream.py#test_stop_is_polled_while_the_child_is_silent"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every catalog git call carries the hardened -c prefix and an environment with GIT_* stripped and the fixed safe values; subcommands outside the list are refused"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_catalog_tracer.py#test_hardened_argv_and_env"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tracer.py#test_file_protocol_is_allowed_only_when_asked"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tracer.py#test_a_subcommand_outside_the_list_is_refused"
        status: pass
    human_judgment: false
  - id: D5
    description: "procs is still the only process starter; catalog imports neither subprocess nor gitops"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_procs.py::test_only_procs_starts_processes, tests/test_gitops.py, tests/test_layering.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "StreamedProcess splits stderr on CR/LF, captures stdout, times out, and kills the whole process tree (grandchild) on Windows"
    requirement: "CAT-11"
    verification:
      - kind: unit
        ref: "tests/test_procs_stream.py (8 tests)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 01: Catalog tracer Summary

**A shallow `file://` clone goes through a hardened, cancellable git runner into `ThirdParty/.staging/`, is checked, renamed to `ThirdParty/<id>/`, recorded in an atomic `catalog.json`, and shows up in `scan_all` and the managed table URIs, with `procs` still the only process starter.**

## Performance

- **Duration:** about 45 min (includes a halt at the first commit, see Issues Encountered)
- **Completed:** 2026-11-27T08:45Z
- **Tasks:** 2
- **Files:** 1 modified, 7 created

## Final signatures (read by plans 17-03, 17-04, 17-07)

```python
# kicad_lib_manager/procs.py
ProcessError = subprocess.SubprocessError
@dataclass(frozen=True)
class StreamOutcome: returncode: int | None; stdout: bytes; lines: tuple[str, ...]; cancelled: bool; timed_out: bool
def start_process(argv, *, env=None, cwd=None, capture_stdout=False, popen=None) -> StreamedProcess
class StreamedProcess:  # pid, kill(), run(*, stop=None, timeout=None, on_line=None, poll=0.2) -> StreamOutcome
def kill_tree(pid, *, platform=None, runner=None) -> None

# kicad_lib_manager/catalog/gitnet.py
@dataclass(frozen=True) class NetGit: exe: Path; allow_file: bool = False; starter: Callable | None = None
@dataclass(frozen=True) class NetRun: returncode: int; stdout: bytes; lines: tuple[str, ...]
def clone_shallow(net, url, branch, dest, *, progress=None, cancel=None) -> NetRun | Issue   # progress(text, percent|None)
def head_commit(net, clone) -> str | Issue
def _argv(net, sub, args, *, clone=None) -> list[str]; def _env(clone=None, environ=None) -> dict
def _execute(net, argv, env, *, cancel=None, timeout, on_line=None, capture_stdout=False) -> NetRun | Issue
def strip_userinfo(text) -> str

# kicad_lib_manager/catalog/ops.py
@dataclass(frozen=True) class AddSource: id, name, url, branch, vars, licence_spdx
@dataclass(frozen=True) class Staged: source, folder, commit
def stage_add(root, source, net, *, progress=None, cancel=None) -> Staged | Issue
def register_add(root, staged, *, acknowledged=False, acknowledged_on="") -> list[Issue]
def discard_staging(staged) -> None;  def library_folder(root, id) -> Path
```

Exact `_BASE_CONFIG` (each passed as `-c <item>`, after `--literal-pathspecs`; `protocol.file.allow=always` is appended only when `NetGit.allow_file`):

```
credential.helper=            core.askPass=
protocol.allow=never          protocol.https.allow=always
core.hooksPath=               core.fsmonitor=false
transfer.bundleURI=false      submodule.recurse=false
http.sslVerify=true           http.lowSpeedLimit=1000       http.lowSpeedTime=60
filter.lfs.process=           filter.lfs.smudge=            filter.lfs.required=false
diff.external=                core.pager=cat                core.quotepath=false
```

Environment: copy of `os.environ` minus every `GIT_*` key, then `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, `GIT_CONFIG_GLOBAL=<null device>`, `GIT_OPTIONAL_LOCKS=0`, `GIT_LFS_SKIP_SMUDGE=1`, `LC_ALL=C`; with a clone also `GIT_DIR=<clone>/.git` and `GIT_WORK_TREE=<clone>`.

Constants: `NET_SUBCOMMANDS`, `CLONE_TIMEOUT = 4 h`, `LOCAL_TIMEOUT = 300 s`, `STAGING_DIR = ".staging"`, `MANIFEST_NAME = "catalog.json"`, `FORMAT = 1`. Issue codes: `git.not_started`, `git.cancelled`, `git.timeout`, `git.clone_failed`, `git.no_commit`, `catalog.unreadable`, `catalog.folder_exists`, `catalog.no_libraries`, `catalog.added`, plus `catalog.write_failed` and `catalog.move_failed` (new, ops).

## Test counts

- `tests/test_catalog_tracer.py`: 6 tests (3 slow with a real `file://` upstream, 3 quick with a recording starter).
- `tests/test_procs_stream.py`: 8 tests (real Python children, none slow, none skipped).
- Guards unchanged and green: `tests/test_procs.py`, `tests/test_gitops.py`, `tests/test_layering.py` (68 passed), `tests/test_annotations_resolve.py`.

## Task Commits

1. **Task 1 RED:** `6c8446c` (test) failing tracer tests plus stub scaffold
2. **Task 1 GREEN:** `70a5ef3` (feat) procs streaming starter, gitnet, manifest, ops
3. **Task 2:** `cad7a0d` (test) StreamedProcess proven on real children

TDD note for Task 1: RED failed on the planned assertions (`isinstance(..., Staged)`, `catalog.no_libraries` code, empty progress record, `NetRun`), not on import errors, because the RED commit carried stub modules and the `StreamOutcome` type. The `gsd_run check tdd-red-evidence` classifier was not run: the plan is `type: execute` and `workflow.tdd_mode` is off. Task 2's tests passed on first run because Task 1's GREEN already contained the `StreamedProcess` implementation they exercise (the tracer cannot run without it); there was no separate RED for Task 2 and no race needed fixing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tracer test generated tables from unselected libraries**
- **Found during:** Task 1 GREEN
- **Issue:** `generate_sym_lib_table` emits only libraries with `selected=True`, so the planned assertion saw an empty table.
- **Fix:** the test selects the scanned libraries first (as Generate Tables does) and also asserts the footprint table URI.
- **Files modified:** tests/test_catalog_tracer.py
- **Committed in:** 70a5ef3

**Total deviations:** 1 auto-fixed (test assertion). **Impact:** none on the production design.

## Issues Encountered

- The first dispatch halted before any commit: main counted as a protected branch and `git.allow_default_branch_commits` was not set. The owner then set it (commit dc3d522) and the run resumed with the RED work intact.

## Known Stubs

None. `percent` is always `None` in `progress(text, percent)` by design until plan 17-03.

## Threat Flags

None beyond the plan's threat model (T-17-01 to T-17-03 mitigated as planned; the hostile-hook slow test is plan 17-03).

## Next Phase Readiness

Ready for 17-02 (independent) and for 17-03/17-04 which extend `gitnet` and `manifest` without changing these shapes.

## Self-Check: PASSED

All created files exist; commits 6c8446c, 70a5ef3, cad7a0d are on main; the plan's two automated verify commands pass (tracer 6 passed, guard modules 68 passed, stream module 14 passed with procs tests, 0 skipped); prepublish scan clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
