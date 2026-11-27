---
phase: 17-library-catalog
plan: 16
subsystem: docs
tags: [user-guide, help-dialog, claude-md, readme, test-docs, library-catalog]

requires:
  - phase: 17-library-catalog
    provides: the catalog window, its flows and the main-window follow-up (plans 17-11 to 17-15)
provides:
  - the Library Catalog page of the User Guide (nine sections, after Importing Parts) and the Ctrl+Shift+L shortcut row
  - the Library Catalog bullet group, the Ctrl+Shift+L shortcut row and the catalog folders in CLAUDE.md
  - the third-party libraries paragraph in README.md and the slow catalog modules in tests/README.md
affects: [17-17, 17-18, 17-19, 17-20]

actuals:
  tokens: 9658
  tasks: 2
  commits: 3
plan_head_before: 29f1b6284d5418d05dbe0be3787f732dd9ee6ef1
plan_head_after: 4b030c9a305e3e3c2aab4fb16fd7ff648f10b6ab

tech-stack:
  added: []
  patterns:
    - "A guide page is checked section by section against the claims of the code it describes (buttons, defaults, refusals), with a plain-language word list"

key-files:
  created: []
  modified:
    - kicad_lib_manager/widgets/help_dialog.py
    - tests/test_help_dialog.py
    - CLAUDE.md
    - README.md
    - tests/README.md
    - tests/test_docs_split.py

key-decisions:
  - "The catalog page describes what 17-11 to 17-15 built, not only what the UI-SPEC planned: the Würth carry-over, the Set Path Variables... button, the Keep Library default with Esc, the silent start check and the manual check that logs an unreachable GitHub"
  - "The page uses only the file name catalog.json from the record and no word of the plain-language deny list (clone, manifest, submodule, SPDX, LFS); Git itself and its version numbers are named because the window names them"
  - "CLAUDE.md names the Git LFS refusal and ls-remote, because it is the developer guide, while the User Guide says 'kept in a way the catalog does not support'"

requirements-completed: [CAT-01, CAT-10, CAT-11]

coverage:
  - id: D1
    description: "The User Guide has a Library Catalog page with the nine agreed sections, placed right after Importing Parts, opened by the catalog window's Help and F1"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_sections"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_is_after_importing"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_opens_from_the_catalog_topic"
        status: pass
    human_judgment: false
  - id: D2
    description: "The page states the behaviours of the built window: PCM never touched, the final write that cannot be stopped, Keep Library as the default of Remove, licences never refuse, the silent start check that writes nothing, path variable questions with No as default"
    requirement: CAT-10
    verification:
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_says_what_the_catalog_leaves_alone"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_says_the_final_write_cannot_be_stopped"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_removing_defaults_to_keeping_the_library"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_update_checks_write_nothing_and_stay_silent_offline"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Keyboard Shortcuts page, CLAUDE.md Menu Shortcuts and the numbered outline carry Ctrl+Shift+L and the shifted numbers (catalog 4.5, migrating 4.6, restoring 4.7)"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_help_dialog.py#test_help_shortcuts_complete"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_help_outline_numbers_follow_the_menu_order"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_claude_md_names_the_catalog"
        status: pass
    human_judgment: false
  - id: D4
    description: "README.md, CLAUDE.md and tests/README.md describe the catalog and its slow local-repository modules (CAT-11) without a workstation path, user name or private repository"
    requirement: CAT-11
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_readme_names_the_catalog"
        status: pass
      - kind: unit
        ref: "tests/test_docs_split.py#test_tests_readme_lists_the_catalog_slow_modules"
        status: pass
      - kind: other
        ref: "env/Scripts/python.exe scripts/prepublish_scan.py --tree --path CLAUDE.md --path README.md --path tests/README.md --path kicad_lib_manager/widgets/help_dialog.py (clean)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The wording of the guide page reads well to the owner (plain language, the right level of detail, nothing missing)"
    verification: []
    human_judgment: true
    rationale: "Whether the text is clear and complete for a reader is a judgment no test makes; the tests pin the claims and the word list only"

duration: 6min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 16: Library Catalog Documentation Summary

**The User Guide has a nine-section Library Catalog page after Importing Parts (outline 4.5) with the Ctrl+Shift+L shortcut, and CLAUDE.md, README.md and tests/README.md describe the catalog as it was really built, checked by new doc tests and a clean pre-publish scan.**

## Performance

- **Duration:** about 6 min after the dispatch bundle and the summaries 17-01 to 17-15 were read
- **Started:** 2026-11-27T12:21:31Z
- **Completed:** 2026-11-27T12:27:00Z
- **Tasks:** 2 (task 1 a RED test commit then a GREEN feat commit; task 2 one docs commit with its tests)
- **Files modified:** 6

## Accomplishments

- `HELP_PAGES["catalog"]` with the sections What the catalog is, Adding a library, Adding by web address, Licences, Updating, Removing, If a library shows a problem, Update checks and Path variables; the TOC entry right after Importing Parts; the shortcut row; the Library Tree page now names "each catalog library, for example WurthElektronik or SparkFun". The numbers shift as decided: importing 4.4, catalog 4.5, migrating 4.6, restoring 4.7; the saved place is keyed by name, so it survives.
- Every claim of the page was checked against the code of plans 17-11 to 17-15 (button names from `catalog_dialog.py` and `catalog_pages.py`, the Git 2.32 and 2.49.1 limits from `gitnet.py`, the refusal and dirty-folder text from `ops.py`, the update-check behaviour from `main_window.py`).
- CLAUDE.md: a Library Catalog bullet group in GUI Behavior (menu entry and count, window, statuses, Add, Update, Remove, Reinstall, the after-job follow-up with the Würth carry-over, Git, busy rules, the update check), `Ctrl+Shift+L — Library Catalog...` in Menu Shortcuts (it was missing since 17-12), `catalog/` and `scripts/catalog/` in Repository Structure, and a line that the catalog tests never use the network.
- README.md: third-party libraries come through File > Library Catalog... into `ThirdParty/`, recorded in `catalog.json`, each keeping its own licence.
- tests/README.md: the four slow catalog modules are in the run-before-publish command with the note that they use local `file://` repositories only.
- Tests: `test_catalog_page_sections`, `test_catalog_page_is_after_importing`, `test_catalog_topic_is_a_guide_page`, `test_catalog_page_opens_from_the_catalog_topic` and eight claim tests including `test_catalog_page_plain_language` in `tests/test_help_dialog.py`; `test_claude_md_names_the_catalog`, `test_readme_names_the_catalog` and `test_tests_readme_lists_the_catalog_slow_modules` in `tests/test_docs_split.py`.

## Task Commits

1. **Task 1: User Guide page, outline numbers, shortcut row** - RED `74e8e8e` (test), GREEN `333bccc` (feat)
2. **Task 2: CLAUDE.md, README.md, tests/README.md** - `4b030c9` (docs, with its tests)

**Plan metadata:** the docs commit that carries this SUMMARY, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `kicad_lib_manager/widgets/help_dialog.py` - the catalog page, the TOC entry, the shortcut row, the Library Tree source example
- `tests/test_help_dialog.py` - catalog page tests, `MENU_NUMBERS`, the shortcut check, the section count of the outline
- `CLAUDE.md` - Library Catalog group, shortcut row, structure lines, no-network note
- `README.md` - the third-party libraries paragraph
- `tests/README.md` - the four slow catalog modules in the publish command
- `tests/test_docs_split.py` - three doc checks

## Decisions Made

See `key-decisions` above.

## TDD Gate Compliance

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1 | `74e8e8e` test(17-16) | `333bccc` feat(17-16) |
| 2 | not `tdd="true"`: its tests are in the same docs commit `4b030c9` | `4b030c9` |

RED evidence (semantic assessment): the plan is `type: execute` and pytest is not one of the report formats of the `tdd-red-evidence` classifier, so it was not run (as in plans 17-01 to 17-15); the run was read by hand. Task 1: 16 of 88 tests failed on the planned missing behaviour (`KeyError: 'catalog'` for the missing page and outline key, and the missing `Ctrl+Shift+L` row), the other 72 passed; none failed on an import, collection or fixture fault. After GREEN one test of the existing outline check still failed (`40 == 25 + 6`: it counted the sections of the old pages and had to include the nine new ones); that was a test update, not a refactor. No refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The outline section count of an older test did not know the new page**
- **Found during:** Task 1 (first GREEN run)
- **Issue:** `test_help_outline_numbers_follow_the_menu_order` asserted 25 section anchors plus the library_folder sections; the new page adds nine
- **Fix:** the expected count is now `25 + len(CATALOG_SECTIONS) + len(library_folder sections)`
- **Files modified:** tests/test_help_dialog.py
- **Verification:** 88 tests of the module pass
- **Committed in:** 333bccc

**2. [Plan note] The plain-language test is stricter than the plan's list**
- The plan listed the words ls-remote, clone, SPDX, manifest and submodule; the test also refuses refspec, `--depth` and LFS, and the field names of the record. Its drive-letter check uses a look-behind so that `https://` does not count as a drive.

**3. [Plan note] Extra content where the plan was silent**
- The page also covers the Git 2.32 and 2.49.1 notes, the busy rules and the Stop the current job? question, the Würth carry-over, the red note for an unreadable `catalog.json`, and that the missing upstream 3D models are warnings; all of it is in the code of 17-11 to 17-15.

---

**Total deviations:** 1 auto-fixed (1 bug in a test), 2 notes. **Impact:** no must_have weakened.

## Issues Encountered

- A Python string with a doubled backslash in a patch script did not match the test's regular expression; the file tool made that one edit.

## Known Stubs

None.

## Threat Flags

None. T-17-42 (docs naming workstation paths or private repositories) is mitigated: `prepublish_scan.py --tree` on every changed doc and the phase folder is clean, and `test_docs_hold_no_workstation_path` still passes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The documentation of the phase is complete for the code of plans 17-01 to 17-15. Plans 17-17 and 17-18 may change the curated list (the guide names only Würth Elektronik and SparkFun as examples, so a change there needs no guide edit). The look of the page in the real window and its wording are for the verify-work UAT.

## Self-Check: PASSED

- Files found: kicad_lib_manager/widgets/help_dialog.py, tests/test_help_dialog.py, CLAUDE.md, README.md, tests/README.md, tests/test_docs_split.py.
- Commits `74e8e8e`, `333bccc`, `4b030c9` are on main (3 commits measured from the ledger base `29f1b62`).
- Acceptance greps: `("catalog", "Library Catalog")` 1, `Ctrl+Shift+L` in help_dialog.py 2, in CLAUDE.md 2, `Library Catalog` in CLAUDE.md 3, `ThirdParty` in README.md 1, `test_catalog_ops_git.py` in tests/README.md 2.
- Plan verification: test_help_dialog (88) and test_docs_split pass with `-n 0`; test_corpus_audit, test_custom_literals, test_docs_split and test_help_dialog pass together (214 tests); the guide tests of test_import_dialog and test_main_window pass (34); the pre-publish scan of the changed files is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
