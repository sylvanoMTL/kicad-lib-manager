---
phase: 17-library-catalog
plan: 04
subsystem: catalog
tags: [validation, untrusted-json, curated-list, licences, path-variables, tdd]

requires:
  - phase: 17-library-catalog
    provides: catalog.manifest load and save (17-01), the Issue and Severity model
provides:
  - catalog.urls (address policy, ids, branches, repository key)
  - catalog.manifest validated load, deterministic save, variable rules, path_vars, added_on
  - catalog.licences (labels, classes, tick rule)
  - catalog.curated (WurthElektronik and SparkFun curated, three candidates, empty REJECTED)
affects: [17-05, 17-06, 17-07, 17-08, 17-10, 17-11, 17-13, 17-17, 17-18]

plan_head_before: 7c6a12b1b3b3a2d6e05f24460d295a8f87b38441
plan_head_after: 244ba652a74c5954b714db1642ac23ad13114114

actuals:
  tokens: 16500
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One rule set for every value that reaches git, a folder name or KiCad settings: urls.parse_github_url, valid_id, valid_branch, manifest.valid_var_name, safe_var_folder"
    - "Untrusted JSON: size cap before json.loads, typed field checks, one Issue in plain words for the first problem, never a raise"
    - "App data as a Python module (curated.py), as manufacturers.py does; no JSON file to ship"

key-files:
  created:
    - kicad_lib_manager/catalog/urls.py
    - kicad_lib_manager/catalog/licences.py
    - kicad_lib_manager/catalog/curated.py
    - tests/test_catalog_urls.py
    - tests/test_catalog_manifest.py
    - tests/test_catalog_vars.py
    - tests/test_catalog_curated.py
    - tests/test_catalog_licences.py
  modified:
    - kicad_lib_manager/catalog/manifest.py

key-decisions:
  - "manifest.load takes a keyword allow_file (default False): a file:// address in catalog.json is refused unless a test asks for it, so a plan whose tests register a file:// upstream twice through ops must pass allow_file=True to load"
  - "valid_var_name also refuses system and loader names (PATH, APPDATA, LD_*, DYLD_*, PYTHON*) and KiCad's CONFIG/DATA/CACHE/STATE/DOCUMENTS_HOME and KICAD_PATH, because KiCad exports its variables into its own process (CAT-10 hardening beyond the plan list)"
  - "default_id is cut to 63 characters (then a trailing dot is dropped) so every address GitHub allows gives an id valid_id accepts"
  - "valid_id also refuses Custom and ThirdParty (casefolded), the folders the collection already uses next to a catalog id"
  - "A file:// address (tests only) gets owner '' and the folder name as repo and default id; it must be a valid id"
  - "known_dirty paths are checked with safe_var_folder (relative, forward slashes, no .., no drive, not empty)"
  - "path_vars takes entries in id order, so a variable two libraries both set gets the same value whatever the entry order"

requirements-completed: [CAT-03, CAT-05, CAT-06, CAT-09, CAT-10]

coverage:
  - id: D1
    description: "Only https://github.com/<owner>/<repo> addresses are accepted (.git, trailing slash, /tree/ and /blob/ tails dropped); every other scheme, host, port, user info, query or fragment gets the UI-SPEC refusal text without echoing the address"
    requirement: "CAT-03"
    verification:
      - kind: unit
        ref: "tests/test_catalog_urls.py#test_refused_addresses_give_the_one_plain_text"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_urls.py#test_accepted_spellings_give_one_reference"
        status: pass
    human_judgment: false
  - id: D2
    description: "Ids, branches and repository keys: folder-safe ids (no .staging, device names, dots, trailing dot or space), option-safe branches, case-insensitive repo_key"
    requirement: "CAT-03"
    verification:
      - kind: unit
        ref: "tests/test_catalog_urls.py (valid_id, valid_branch, repo_key tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "catalog.json is validated on read (size cap before parsing, typed fields, case-insensitive duplicate ids, newer format read-only) with one plain-words Issue, an empty catalog when missing, and written byte-identically"
    requirement: "CAT-05"
    verification:
      - kind: unit
        ref: "tests/test_catalog_manifest.py"
        status: pass
      - kind: integration
        ref: "tests/test_catalog_tracer.py --full (register_add output still loads)"
        status: pass
    human_judgment: false
  - id: D4
    description: "KiCad, Plugin and Content Manager, this app's and system variable names are refused; library variables give forward-slash paths under ThirdParty/<id>"
    requirement: "CAT-10"
    verification:
      - kind: unit
        ref: "tests/test_catalog_vars.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "The curated list holds WurthElektronik (proprietary, WE_3DMODEL_DIR=3dmodels, legacy prefix) and SparkFun (CC BY 4.0, SPARKFUN_KICAD_LIBRARY); 4ms, Alternate-KiCad-Library and Espressif are candidates only, never found by curated_by_id"
    requirement: "CAT-09"
    verification:
      - kind: unit
        ref: "tests/test_catalog_curated.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "Licence display names, classes and the tick rule follow the UI-SPEC Licence labels table"
    requirement: "CAT-09"
    verification:
      - kind: unit
        ref: "tests/test_catalog_licences.py"
        status: pass
    human_judgment: false
  - id: D7
    description: "The measured values in curated.py (sizes, install sizes, library counts, SparkFun licence) match what research recorded on 2026-11-27"
    requirement: "CAT-09"
    verification: []
    human_judgment: true
    rationale: "The values come from research measurements and GitHub's API; no test can re-measure them. The owner-run verification of plan 17-17 confirms them against the real network."

duration: 9min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 04: Catalog rules and curated data Summary

**One tested rule set now guards every address, id, branch, variable name and variable folder that reaches git or KiCad (https://github.com only, folder-safe ids, option-safe branches, KiCad/PCM/system variables refused), catalog.json is validated on read and byte-deterministic on write, and the app ships Wurth Elektronik and SparkFun as its two curated libraries with 4ms, Alternate-KiCad-Library and Espressif held as candidates.**

## Performance

- **Duration:** about 9 min
- **Started:** 2026-11-27T09:04Z
- **Completed:** 2026-11-27T09:13Z
- **Tasks:** 2 (each with a RED and a GREEN commit)
- **Files:** 1 modified, 8 created

## Final signatures (read by plans 17-05, 17-07, 17-10, 17-18)

```python
# kicad_lib_manager/catalog/urls.py   (imports models only)
GITHUB_HOST = "github.com"; BAD_URL_TEXT; MAX_ID = 63; MAX_BRANCH = 128
@dataclass(frozen=True) class RepoRef: owner, repo, https_url, default_id
def parse_github_url(text, *, allow_file=False) -> RepoRef | Issue   # Issue code catalog.bad_url
def default_id(owner, repo) -> str;  def valid_id(text) -> bool;  def valid_branch(text) -> bool
def repo_key(url) -> str          # "owner/repo" casefolded, the casefolded path for file://, else the stripped casefold

# kicad_lib_manager/catalog/manifest.py   (added or changed)
MAX_MANIFEST_BYTES = 1024 * 1024
CatalogEntry(id, url, branch, commit="", vars={}, licence_spdx=None, acknowledged=False,
             acknowledged_on="", added_on="", known_dirty=())            # added_on is new: ISO date or ""
def entry_folder(root, entry_or_id) -> Path          # root/ThirdParty/<id>
def valid_var_name(name) -> bool;  def safe_var_folder(text) -> bool
def path_vars(root, entries) -> dict[str, str]
def load(root, *, allow_file=False) -> Manifest | Issue     # catalog.unreadable | catalog.newer_format
def save(root, manifest) -> Issue | None                   # sorted by casefold id, fixed key order, vars sorted

# kicad_lib_manager/catalog/licences.py   (stdlib only)
class LicenceClass(Enum): OPEN, SHARE_ALIKE, PROPRIETARY, NOT_STATED, OTHER, UNKNOWN
def licence_label(spdx, *, proprietary=False, known=True) -> str
def licence_class(spdx, *, proprietary=False, known=True) -> LicenceClass
def needs_tick(cls) -> bool

# kicad_lib_manager/catalog/curated.py   (imports licences only)
CuratedEntry(id, name, description, url, branch, licence_spdx, proprietary, size_mb, install_mb,
             vars, symbol_libs, footprint_libs, legacy_prefix=None)   # .licence -> LicenceClass
Candidate(id, name, url, branch, licence_spdx, size_mb, vars, research)
CURATED, CANDIDATES, REJECTED = (), curated_by_id(id) -> CuratedEntry | None
```

Saved key order of one entry: `id, url, branch, commit, vars, licence {spdx, acknowledged, acknowledged_on}, added_on, known_dirty`.

## Curated values as written

| id | name | url | branch | licence | size_mb | install_mb | vars | symbol/footprint libs | legacy_prefix |
|----|------|-----|--------|---------|---------|------------|------|-----------------------|---------------|
| WurthElektronik | Würth Elektronik | https://github.com/WurthElektronik/KiCad-Library.git | master | proprietary (spdx None) | 2674 | 12000 | WE_3DMODEL_DIR = 3dmodels | 402 / 43 | WurthElektronik/KiCad-Library/ |
| SparkFun | SparkFun | https://github.com/sparkfun/SparkFun-KiCad-Libraries.git | main | CC-BY-4.0 (open) | 69 | 310 | SPARKFUN_KICAD_LIBRARY = "" | 30 / 21 | none |

Candidates (never shown, never found by `curated_by_id`): 4ms (`4ms/4ms-kicad-lib`, master, Unlicense, 58 MB, `KICAD_4MS_LIBS=""`), Alternate-KiCad-Library (`DawidCislo/Alternate-KiCad-Library`, main, no licence stated, 181 MB, not cloned yet), Espressif (`espressif/kicad-libraries`, main, no licence stated, 72 MB, expected to fail on KiCad Plugin and Content Manager variables). `REJECTED = ()`; plan 17-18 applies the owner-run results of 17-17.

## Licence table as implemented

| GitHub reports | Shown as | Class | Tick |
|----------------|----------|-------|------|
| MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, Unlicense, CC0-1.0 | MIT, BSD, BSD, Apache 2.0, ISC, Unlicense, CC0 1.0 | open | no |
| CC-BY-3.0, CC-BY-4.0 | CC BY 3.0, CC BY 4.0 | open | no |
| CC-BY-SA-3.0/4.0, GPL/LGPL/AGPL (with or without -only, -or-later, +), MPL-2.0, EPL-1.0/2.0 | CC BY-SA 4.0, GPL 3.0, LGPL 2.1, AGPL 3.0, MPL 2.0, EPL 2.0 | share-alike | yes |
| curated entry flagged proprietary | Proprietary | proprietary | yes |
| None, empty, NOASSERTION, other | Not stated | not stated | yes |
| any other id | Other (see the licence file) | other | yes |
| GitHub not reached, not curated (`known=False`) | Unknown | unknown | yes |

Ids compare case-insensitively. A proprietary flag wins over everything, including `known=False`.

## Manifest refusal texts (plain words, first problem only; `{name}` is the library id when it is plain, else "a library")

- Too large: `The library list is larger than 1 MB, so it was not read.`
- Not readable text / not JSON / not an object: `The library list catalog.json is not in a form this app understands.` or `... is not a text file this app can read.`
- Format missing, not an integer or below 1: `The library list has no version number this app understands.`
- Format above 1 (code `catalog.newer_format`): `The library list was written by a newer version of this app, so it is read-only here. Update the app to change it.`
- No list of libraries: `The library list catalog.json holds no list of libraries.`
- Entry not an object: `The library list holds an entry that is not a library record.`
- Id: `The library name {name} cannot be used as a folder name.` or `A library in the list has no usable library name.`
- Same id under casefold: `Two libraries in the list are called {a} and {b}. Names that differ only in capital letters are the same folder on Windows.`
- URL: `The web address of {name} is not a GitHub repository address.`
- Branch: `The branch of {name} is not a branch name this app can use.`
- Commit: `The version of {name} is not a 40-character version code.`
- Variables: `The path variables of {name} are not in a form this app understands.`, `{name} has a path variable that cannot be used.`, `{name} has a path variable that points outside its folder.`
- Licence record: `The licence record of {name} is not in a form this app understands.`
- Added date: `The date {name} was added is not a date this app understands.`
- Changed files: `The list of changed files of {name} is not in a form this app understands.`

## Test counts

- `tests/test_catalog_urls.py` 106, `tests/test_catalog_manifest.py` 70, `tests/test_catalog_vars.py` 68 (244 together), `tests/test_catalog_curated.py` 19 and `tests/test_catalog_licences.py` 36 (55 together); all quick, no process, no network, 0 skipped with the final lists.
- Guards unchanged and green: `tests/test_catalog_layering.py`, `tests/test_layering.py`, `tests/test_annotations_resolve.py` (66 passed); `tests/test_catalog_tracer.py --full` (6 passed, so register_add output still loads).

## Task Commits

1. **Task 1 RED:** `64d22c7` (test) failing tests plus inert stubs of urls.py and the manifest additions
2. **Task 1 GREEN:** `4d2134c` (feat) urls.py and the validated manifest
3. **Task 2 RED:** `6842938` (test) failing tests plus inert licences.py and curated.py stubs
4. **Task 2 GREEN:** `244ba65` (feat) licences.py and curated.py

TDD note: both RED commits failed on the planned assertions (stub functions returned inert values, so the failures were wrong results, not import or syntax errors). The plan is `type: execute` and `workflow.tdd_mode` is off, so the `gsd_run check tdd-red-evidence` classifier was not run (same as 17-01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Variable-name deny list widened beyond the plan's patterns**
- **Found during:** Task 1
- **Issue:** the plan's regex `^[A-Z][A-Z0-9_]{2,63}$` minus KiCad's patterns would still accept `PATH`, `APPDATA`, `LD_PRELOAD` and similar; KiCad exports its variables into its own process, so a hand-edited or foreign catalog.json could set them (CAT-10 and threat T-17-10).
- **Fix:** also refuse a named set of system names, the prefixes `LD_`, `DYLD_`, `PYTHON`, KiCad's `KICAD_*_HOME` names and `KICAD_PATH`. `WE_3DMODEL_DIR`, `SPARKFUN_KICAD_LIBRARY` and `KICAD_4MS_LIBS` still pass.
- **Files modified:** kicad_lib_manager/catalog/manifest.py, tests/test_catalog_vars.py
- **Committed in:** 4d2134c

**2. [Rule 1 - Bug] default_id could exceed what valid_id accepts**
- **Found during:** Task 1
- **Issue:** GitHub allows an owner of 39 and a repo of 100 characters, so `<owner>-<repo>` can be 140 characters while ids are limited to 63.
- **Fix:** default_id cuts to 63 characters, then drops a trailing dot; a test proves every accepted address gives a valid id.
- **Files modified:** kicad_lib_manager/catalog/urls.py, tests/test_catalog_urls.py
- **Committed in:** 4d2134c

**3. [Rule 2 - Missing critical] valid_id refuses Custom and ThirdParty**
- **Found during:** Task 1
- **Issue:** the curated test requires that no curated id is Custom or ThirdParty, but an id typed through Add by URL had no such rule; a library named `Custom` would share the source name of the user's own library.
- **Fix:** valid_id refuses `custom`, `thirdparty` and `.staging` (casefolded).
- **Files modified:** kicad_lib_manager/catalog/urls.py
- **Committed in:** 4d2134c

**4. [Rule 3 - Blocking] `allow_file` seam on manifest.load**
- **Found during:** Task 1
- **Issue:** the tracer and the slow tests register `file://` upstreams, which the stricter manifest must refuse in production.
- **Fix:** `load(root, *, allow_file=False)`; `ops.register_add` is unchanged (its first registration loads a missing file, so the tracer passes). A later test that registers two file:// libraries through `ops` in one root has to read the manifest with `allow_file=True` or extend `register_add` with the same keyword.
- **Files modified:** kicad_lib_manager/catalog/manifest.py
- **Committed in:** 4d2134c

---

**Total deviations:** 4 auto-fixed (2 missing critical, 1 bug, 1 blocking). **Impact:** all inside the plan's files and stricter than specified; no change to a signature a later plan reads except the new optional keyword and the new `added_on` field.

## Issues Encountered

- `urllib.parse.urlsplit` has no `params` attribute (only `urlparse` does): the first GREEN run failed on it; the check was dropped because `;` is already refused as a character.
- `manifest.py` was rewritten with CRLF line endings (the other new files and `ops.py` are CRLF in the repository too, while the plan 17-01 copy of `manifest.py` was LF), so the diff of that file shows every line as changed; `git diff --ignore-cr-at-eol` shows the real 228 insertions and 25 deletions.

## Known Stubs

None. The `REJECTED` tuple is empty by design until plan 17-18 applies the owner-run verification.

## Threat Flags

None beyond the plan's threat model: T-17-09 (manifest size cap, typed fields, derived folders), T-17-10 (variable names, widened as described) and T-17-11 (address policy) are mitigated and tested.

## Next Phase Readiness

Ready for 17-05 onward. Plans that call `manifest.load` on a root holding a `file://` catalog entry (tests only) pass `allow_file=True`. Plan 17-18 moves candidates into CURATED or REJECTED; no test pins the curated id set.

## Self-Check: PASSED

All nine files exist; commits 64d22c7, 4d2134c, 6842938 and 244ba65 are on main; both plan verify commands, the four acceptance greps and the python acceptance one-liner pass; layering, annotation and tracer guards green; prepublish scan clean on every new file.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
