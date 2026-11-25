---
phase: 16-repo-split
plan: 05
subsystem: tooling
tags: [split, kicad-tables, git, remove-code-commit, stdlib, pytest]

requires:
  - phase: 16-repo-split
    provides: "decisions D-01, D-04, D-07, D-21, D-22, D-23 (16-CONTEXT.md) and the rehearsed cutover commands (16-RESEARCH.md)"
provides:
  - "scripts/split/uri_diff.py: read-only resolved-URI snapshot and compare of KiCad's global tables (D-22)"
  - "scripts/split/cutover_collection.py: dry-run-first remove-code commit for the collection (D-01, D-07)"
  - "scripts/split/collection/{README.md,CLAUDE.md,gitignore}: the collection's own docs and ignore file (D-21)"
affects: [16-12 rehearsal, 16-13 live run prerequisites, 16-15 live cutover, 16-14 CLAUDE.local.md]

actuals:
  tokens: 17000
  tasks: 2
  commits: 4

plan_head_before: ed3a784ac0375414f438f462d178cf46254173e1
plan_head_after: 1a6e8761627400174e24ffe115331c4e8fa92987

tech-stack:
  added: []
  patterns:
    - "split scripts are stdlib-only files under scripts/split/, loaded by path in tests (no package, no import of the app)"
    - "dry run by default, refusals before any write, post-commit checks that name the difference"

key-files:
  created:
    - scripts/split/uri_diff.py
    - scripts/split/cutover_collection.py
    - scripts/split/collection/README.md
    - scripts/split/collection/CLAUDE.md
    - scripts/split/collection/gitignore
    - tests/test_uri_diff.py
    - tests/test_cutover_collection.py
  modified: []

key-decisions:
  - "uri_diff parses the tables with a small tokenizer (strings, nesting) instead of one regex, so a descr holding parentheses or a quoted (uri ...) cannot produce a false entry; it still never imports the app"
  - "expanded means no ${VAR} or $(VAR) is left unresolved, so a plain absolute URI is checked for existence too; only an unresolved built-in such as ${KICAD10_SYMBOL_DIR} is compared as text and never counted as missing"
  - "compare fails on entry differences and missing entries only; a difference in the recorded KICAD_LIB_GITHUB or CUSTOM_3DMODEL_DIR values is printed as a note line and does not change the exit code"
  - "cutover_collection treats a submodule showing as modified in git status as an uncommitted tracked change and refuses, which also settles the recorded-versus-checked-out gitlink question (Pitfall 14) before the live run"

requirements-completed: [SPLIT-02, SPLIT-05]

coverage:
  - id: D1
    description: "uri_diff snapshot resolves every table URI read-only, marks existence, writes the library root as <LIB> on a whole path segment, sorts by (table, name) and exits 2 on empty tables"
    requirement: SPLIT-02
    verification:
      - kind: unit
        ref: "tests/test_uri_diff.py (17 tests, python -m pytest tests/test_uri_diff.py -n 0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "uri_diff compare exits 0 only for identical entry lists with zero missing and names added, removed, changed and missing entries otherwise"
    requirement: SPLIT-02
    verification:
      - kind: unit
        ref: "tests/test_uri_diff.py#test_compare_reports_differences"
        status: pass
    human_judgment: false
  - id: D3
    description: "cutover_collection dry run writes nothing; --apply leaves exactly .gitignore, .gitmodules, CLAUDE.md, README.md and both gitlinks with unchanged SHAs, .gitmodules bytes and remote URL, and keeps untracked data"
    requirement: SPLIT-02
    verification:
      - kind: integration
        ref: "tests/test_cutover_collection.py#test_dry_run_writes_nothing and #test_apply_keeps_gitlinks_and_untracks_samples (slow, --full -m slow)"
        status: pass
    human_judgment: false
  - id: D4
    description: "cutover_collection refuses (exit 1, nothing written) off main, with a dirty tracked file, without a gitlink, or with an unexpected tracked path"
    requirement: SPLIT-02
    verification:
      - kind: integration
        ref: "tests/test_cutover_collection.py#test_refusals (slow)"
        status: pass
    human_judgment: false
  - id: D5
    description: "the collection CLAUDE.md, README.md and gitignore carry the naming convention, atomic rule, path variables, manual import route, git workflow and a pointer to kicad-lib-manager, with no workstation path"
    requirement: SPLIT-05
    verification:
      - kind: unit
        ref: "tests/test_cutover_collection.py (template tests: claude_md_carries_the_conventions, readme_sections, gitignore, no_workstation_path)"
        status: pass
    human_judgment: true
    rationale: "Whether the wording reads well to the owner and a future collection reader is a judgment; the tests only pin headings, tokens and the absence of local paths"

duration: 40min
completed: 2026-11-24
status: complete
---

# Phase 16 Plan 05: Collection-side split scripts Summary

**Two stdlib scripts and three templates: a read-only before/after resolved-URI proof for KiCad's global tables, and a dry-run-first remove-code commit that keeps both gitlinks, .gitmodules and the remote while giving the collection its own README, CLAUDE.md and .gitignore.**

## Performance

- **Duration:** about 40 min
- **Completed:** 2026-11-24T13:43Z
- **Tasks:** 2 (both TDD: RED commit, then GREEN commit)
- **Files:** 7 created, 0 modified

## Accomplishments

- `uri_diff.py snapshot` reads `sym-lib-table`, `fp-lib-table` and `kicad_common.json` read-only, expands `${VAR}` from `--var`, then `environment.vars`, then the process environment, and records every entry with its resolved path, whether it expanded and whether it exists. The library root becomes `<LIB>` on a whole path segment only (case and slash direction ignored on Windows), so a scratch collection and the live one compare equal.
- `uri_diff.py compare` exits 0 only when the entry lists are identical and nothing is missing, printing `uri_diff: identical, <n> entries, 0 missing`; otherwise exit 1 with `added:`, `removed:`, `changed:` and `missing (before|after):` lines. `vars` prints the two path variables from `kicad_common.json` ("not set" when absent).
- `cutover_collection.py` is a dry run unless `--apply` is given. Refusals run before any write in both modes. After the commit it checks the exact tree, both gitlink SHAs, the `.gitmodules` bytes and the remote URL, then removes leftover code folders only when they hold nothing but `__pycache__` / `.pytest_cache` content; a leftover with a real file is reported and kept.
- The collection templates carry the naming convention (`Atomic_<stem>`, the shared `Atomic_Footprints.pretty`), the atomic rule, `KICAD_LIB_GITHUB` / `CUSTOM_3DMODEL_DIR` / `WE_3DMODEL_DIR`, the manual import route, the git workflow and a pointer to `sylvanoMTL/kicad-lib-manager`, without a workstation path.

## REMOVE list as committed

`REMOVE` in `scripts/split/cutover_collection.py` (top-level entries, removed with `git rm -r` only when present in the index):

`kicad_lib_manager`, `kicad_lib_manager.py`, `tests`, `scripts`, `.githooks`, `.github`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.planning`, `reports`, `research_notes`, `.gitattributes`, `LICENSE`, `README.md`, `CLAUDE.md`

- `UNTRACK = ("downloaded_examples",)` (`git rm -r --cached`, files stay on disk)
- `KEEP = (".gitignore", ".gitmodules", "Custom", "WurthElektronik/KiCad-Library")`
- `WRITE = {"README.md": "README.md", "CLAUDE.md": "CLAUDE.md", ".gitignore": "gitignore"}` (target -> template under `scripts/split/collection/`)
- `CACHE_NAMES = ("__pycache__", ".pytest_cache")`
- `DEFAULT_MESSAGE = "Remove the app code: the library manager now lives in sylvanoMTL/kicad-lib-manager"`
- CLI: `python scripts/split/cutover_collection.py --repo DIR [--apply] [--message TEXT]`, exit 0 / 1 / 2. `--repo` must be the repository's top folder.

## Snapshot JSON shape

```json
{
  "lib_root": "<LIB>",
  "vars": {"KICAD_LIB_GITHUB": "<LIB>", "CUSTOM_3DMODEL_DIR": "<LIB>/Custom/3DModels"},
  "entries": [
    {"table": "sym-lib-table", "name": "Fixture_A", "type": "KiCad",
     "uri": "${KICAD_LIB_GITHUB}/Custom/Symbols/Fixture_A.kicad_sym",
     "resolved": "<LIB>/Custom/Symbols/Fixture_A.kicad_sym", "expanded": true, "exists": true}
  ],
  "duplicates": [{"table": "sym-lib-table", "name": "Twice", "count": 2}],
  "missing": [{"table": "sym-lib-table", "name": "Fixture_B", "resolved": "<LIB>/Custom/Symbols/Fixture_B.kicad_sym"}]
}
```

`lib_root` is `null` when no library root is known; a variable that is not set is `null` in `vars`. `entries` are sorted by (table, name, uri); `table` is `sym-lib-table` or `fp-lib-table`. `snapshot` prints `uri_diff: <n> entries, <m> missing` plus one line per missing entry and per duplicate name. Commands: `vars [--config-dir DIR]`, `snapshot --tables-dir DIR [--config-dir DIR] [--var NAME=VALUE ...] [--lib-root DIR] --out FILE`, `compare BEFORE AFTER`.

## Task Commits

1. **Task 1: Resolved-URI snapshot and compare (D-22)**
   - RED `755fb88` test(16-05): 17 tests plus a skeleton script
   - GREEN `590d380` feat(16-05): the implementation
2. **Task 2: Remove-code commit for the collection, with its README, CLAUDE.md and .gitignore**
   - RED `8d9775a` test(16-05): 6 quick and 3 slow tests plus a skeleton script
   - GREEN `1a6e876` feat(16-05): the script and the three templates

**Plan metadata:** the SUMMARY commit follows this file (docs(16-05)).

## RED evidence

`gsd_run check tdd-red-evidence` is not installed in the worktree, so the RED assessment is manual and semantic.

- Task 1 RED: `python -m pytest tests/test_uri_diff.py -n 0` ran 17 tests, 17 failed on their planned assertions (the skeleton returns `99`, `[]`, `""`), none on an import or collection error.
- Task 2 RED: with the templates moved aside, the 6 quick tests failed (5 on a missing template file or an empty constant, `test_cache_only_rule` on its assertion) and the 3 slow tests built the superproject and failed on `returncode == 99` and the missing output. The template tests fail on a missing file by design: the file is the unit under test.

## Verification

- `python -m pytest tests/test_uri_diff.py -n 0 -q -p no:cacheprovider`: 17 passed.
- `python -m pytest tests/test_cutover_collection.py -n 0 -q -p no:cacheprovider`: 6 passed, 3 deselected.
- `python -m pytest tests/test_cutover_collection.py --full -m slow -n 0 -q -p no:cacheprovider`: 3 passed.
- Acceptance greps: `def snapshot|compare|parse_table|normalise` count 4, `kicad_lib_manager` imports in uri_diff 0, the three named tests present (3), quoted `clean|push|reset` in cutover_collection 0, three CLAUDE.md headings 3, `downloaded_examples/*` line 1 and `!downloaded_examples` 0, workstation-path matches 0.
- The whole suite was not run (orchestrator owns it after the wave merge). The `Custom/` and `WurthElektronik/KiCad-Library` submodules are not checked out in this worktree; none of these tests reads them (the slow tests build their own superproject in a temp folder).

## Deviations from Plan

None - plan executed exactly as written. Small implementation choices inside the plan's latitude are listed under key-decisions (tokenizer instead of one regex, `expanded` meaning "no variable left unresolved", variable differences reported as notes).

**Total deviations:** 0 auto-fixed.

## Issues Encountered

- A first draft of the slow-test helper listed gitlinks with a non-recursive `git ls-tree HEAD`, which shows `WurthElektronik` as a tree and hides the second gitlink; the helper now uses `ls-tree -r`, so the "both gitlinks keep their SHAs" assertions cover both. Test-side fix only, found before the first GREEN commit.

## Known Stubs

None.

## Threat Flags

None. The scripts only read KiCad's tables (opened read-only, one output file at `--out`, refused if it would overwrite a file it reads) and run git in the folder named by `--repo`. No network, no push, no package install.

## Notes for later plans

- 16-12 (rehearsal): run `cutover_collection.py` on a `git clone --no-local` copy after initialising both submodules offline, and `uri_diff.py snapshot` on a scratch folder holding copies of the two tables and `kicad_common.json` with `--lib-root` pointing at the scratch collection.
- 16-13 / 16-15 (live run): the live checkout must be on `main` with a clean tracked state, including the `Custom` gitlink matching the checked-out commit; the script refuses otherwise. The owner's GUI must be closed first because the app runs from `kicad_lib_manager/` in that checkout.
- 16-14: the workstation bullet of today's "KiCad Path Variables" section is not in the collection template on purpose; it belongs in the untracked `CLAUDE.local.md`.
- The `.gitattributes` removal assumes plan 16-09 has dropped its `downloaded_examples` line (the file is code-only by then); the script removes it whatever its content.

## Self-Check: PASSED

- Files present: `scripts/split/uri_diff.py`, `scripts/split/cutover_collection.py`, `scripts/split/collection/README.md`, `scripts/split/collection/CLAUDE.md`, `scripts/split/collection/gitignore`, `tests/test_uri_diff.py`, `tests/test_cutover_collection.py` (all committed).
- Commits present on this branch: `755fb88`, `590d380`, `8d9775a`, `1a6e876`.

---
*Phase: 16-repo-split*
*Completed: 2026-11-24*
