---
phase: 17-library-catalog
plan: 26
subsystem: docs
tags: [docs, ui-spec, user-guide, claude-md, readme, kicad-addon-list, scratch-switch, plain-language, tdd]

requires:
  - phase: 17-library-catalog
    provides: the check count, sizes and Remove counts (17-21), the refreshing overlay and log summaries (17-23), the add-on names (17-24), KiCad's add-on list in the window (17-25), the scratch switch (17-27)
provides:
  - 17-UI-SPEC.md updated for plans 17-21 to 17-25 and 17-27 (reading line, listing rows, Cannot be added yet, Listed in, Add from KiCad's list, Names in KiCad, the refreshing state, the new log lines, UI Considerations rows)
  - the Library Catalog page of the User Guide with KiCad's add-on list, the three cannot-be-added-yet cases, the PCM_ names, the refreshing state and the one-line log summaries
  - the Library Folder page names --scratch-root and KICAD_LIBMGR_SCRATCH_ROOT
  - CLAUDE.md and README.md describe the add-on list, the add-on name rule and the scratch switch
affects: [17-18, 17-19, 17-20]

plan_head_before: 3ba566ece39deedd425380f36caffff20ff1f2cd
plan_head_after: 85fe527da51f868f169c61b19cc1b19792515aef

actuals:
  tokens: 16400
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - "the UI-SPEC check imports the code constants (catalog_dialog, catalog_pages, refresh_overlay, addons, validate, startup) and asserts every one is in the spec text, so the contract copies the code exactly"
    - "guide and doc tests read the rendered text of one h3 section (_catalog_section) and assert claims by phrase"

key-files:
  created: []
  modified:
    - .planning/phases/17-library-catalog/17-UI-SPEC.md
    - kicad_lib_manager/widgets/help_dialog.py
    - tests/test_help_dialog.py
    - tests/test_docs_split.py
    - CLAUDE.md
    - README.md

key-decisions:
  - "The new guide section 'If a library cannot be added yet' sits after 'Adding by web address' (the Add flows come first, then what cannot be added); CATALOG_SECTIONS in the tests follows"
  - "The refreshing text in the guide quotes the part that is fixed ('Refreshing the library list after adding' and the library's name) because the code builds the verb and the name into the line; the UI-SPEC lists the four verbs"
  - "The plain-language test refuses PCM not followed by an underscore, and also the word staging; the guide names the prefix only as 'start with PCM_' and in the example PCM_Espressif"
  - "CLAUDE.md puts all add-on-list text in the Library Catalog bullets of GUI Behavior and the scratch switch in Running the GUI and Dev Workflow, as the plan says"

requirements-completed: [CAT-01, CAT-09, CAT-10]

coverage:
  - id: D1
    description: "17-UI-SPEC.md holds every text and state of plans 17-21 to 17-25 and 17-27, copied from the code constants, each marked owner-approved 2026-11-27 (17-17 check) or D-33 to D-36"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "scratchpad p26_verify_spec.py (one python -c over about 50 strings, 24 of them code constants imported from the modules)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The User Guide's Library Catalog page explains KiCad's add-on list, why some libraries cannot be added yet, the PCM_ names and KiCad's own entry kept, the refreshing state and the log summaries, in plain words"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_names_kicads_list"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_explains_cannot_be_added_yet"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_explains_the_names"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_mentions_the_refresh_and_the_log"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_catalog_page_plain_language"
        status: pass
    human_judgment: false
  - id: D3
    description: "CLAUDE.md and README.md say the catalog also lists KiCad's add-on list, the name rule, and that KiCad's own Plugin and Content Manager is never touched (CAT-10)"
    requirement: CAT-10
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_docs_name_kicads_add_on_list_and_keep_its_manager_untouched"
        status: pass
    human_judgment: false
  - id: D4
    description: "The scratch switch is documented in CLAUDE.md (Running the GUI, Dev Workflow), README.md and the User Guide's Library Folder page; no workstation path is written"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_docs_split.py#test_docs_name_the_scratch_switch_where_library_root_is"
        status: pass
      - kind: unit
        ref: "tests/test_help_dialog.py#test_guide_mentions_the_scratch_switch"
        status: pass
    human_judgment: false
  - id: D5
    description: "Whether the guide's new paragraphs read as plain and short enough for the owner"
    verification: []
    human_judgment: true
    rationale: "Wording quality for a non-technical reader is the owner's judgment; the tests refuse deny-list words and the bare abbreviation but cannot judge readability"

duration: 22min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 26: Docs for the add-on list, the refreshing state and the scratch switch Summary

**The binding UI contract, the User Guide, CLAUDE.md and README.md now describe the catalog as plans 17-21 to 17-25 and 17-27 built it: KiCad's add-on list with its dated offline copy, "Cannot be added yet", "Listed in", "Names in KiCad", the refreshing overlay, the one-line log summaries and the `--scratch-root` switch.**

## Performance

- **Duration:** about 22 min
- **Completed:** 2026-11-27T18:14Z
- **Tasks:** 2 (Task 2 with a RED/GREEN cycle for the guide and another for CLAUDE.md and README.md)
- **Files modified:** 6 (no file created apart from this summary)

## Accomplishments

- **17-UI-SPEC.md** (79 lines added). The list section gained the reading line (its four states and the hide rule), the rows from KiCad's add-on list with the merge rules, and the trees' catalog names; the status table gained `Cannot be added yet` with its four reasons as coded in `catalog/addons.py`. The Details table gained `Listed in` (with the dated copy text) and the size-on-disk and listing details. A new subsection "Add from KiCad's list" holds the check step, the licence page, the refusal mode, the name rule (D-34) and the rule that KiCad's own manager is never touched; the Add preview gained `Names in KiCad`. A new section "Main window: refreshing after a catalog change" holds the overlay (wheel size and timing, text, bar, count, accessible names, disabled controls, how it ends). The Log lines table gained the four summary lines, the add-on folder 3D model warning and the scratch start line; Settings and Persistence names the kept copy of the list and the scratch folders; UI Considerations gained 13 rows (C15 to C17 and the changed surfaces); the User Guide surfaces list the new sections.
- **User Guide** (`help_dialog.py`). "What the catalog is" names KiCad's add-on list (reviewed by the KiCad team), the reading line, the dated copy offline and the only-own-list fallback, "Listed in", and the Size column's size on disk. "Adding a library" explains adding from that list, the footprint-file count of the check, the "Names in KiCad" preview part with the PCM_Espressif example, the own-names case, that KiCad's own entry is kept and KiCad's copy left alone, the refreshing state in the main window and the one log line per library. New section "If a library cannot be added yet" (program repository, another site than GitHub, packed file; install it with KiCad's Plugin and Content Manager). "Removing" says the counts are by kind. The Library Folder page's development paragraph gained the `--scratch-root` sentence.
- **CLAUDE.md and README.md.** Library Catalog bullets for the add-on list, the names, progress and counts, and the refreshing state; the structure line names `addons.py`; Running the GUI and Dev Workflow document `--scratch-root` / `KICAD_LIBMGR_SCRATCH_ROOT`; README's third-party paragraph and its `--library-root` paragraph each gained their sentence. No owner folder, path-variable value or e-mail was written.

## Claims checked against the code

Each doc statement was matched to a constant or function: the reading-line, copy and listed-in texts (`catalog_dialog`), the names texts (`catalog_pages`), the four reason texts (`catalog.addons`), the warning texts (`catalog.validate`), the overlay text, size, colours and timings (`refresh_overlay`), the summary lines (`library_scanner._catalog_summary_text`), the scratch note and folders (`startup`, `userdirs` as listed in the 17-27 summary). One scope note: the UI-SPEC says the overlay "receives at most 101 counts"; that is the 17-23 summary's number, not re-measured here.

## Task Commits

1. **Task 1: UI contract** - `0f277f4` (docs). One automated check over about 50 strings, 24 of them the code constants imported from the modules, instead of one grep (plan-checker warning W2); it also ran the four acceptance greps.
2. **Task 2: User Guide** - RED `bd525dd` (test), GREEN `b743bbd` (feat)
3. **Task 2: CLAUDE.md and README.md** - RED `0cdfffc` (test), GREEN `85fe527` (docs)

**Plan metadata:** the docs commit that holds this file, STATE.md and ROADMAP.md.

### TDD RED evidence (semantic assessment)

`workflow.tdd_mode` was not passed, so the classifier was not run; pytest's own report was read. Guide RED: 7 tests failed for the planned reason (the new section, phrases and the scratch sentence did not exist: `test_catalog_page_sections`, `..._names_kicads_list`, `..._explains_cannot_be_added_yet`, `..._explains_the_names`, `..._mentions_the_refresh_and_the_log`, `test_guide_mentions_the_scratch_switch`, and the outline count test that follows the section list); the plain-language test already passed (no bare abbreviation was ever on the page) and is kept as a pin. Doc RED: both new `test_docs_split.py` tests failed on a missing token of CLAUDE.md.

## Files Created/Modified

- `.planning/phases/17-library-catalog/17-UI-SPEC.md` - the contract updated
- `kicad_lib_manager/widgets/help_dialog.py` - the Library Catalog and Library Folder pages (CRLF kept)
- `tests/test_help_dialog.py` - five new tests, the extended plain-language test, the section list (CRLF kept)
- `tests/test_docs_split.py` - two new doc tests (CRLF kept)
- `CLAUDE.md`, `README.md` - the bullets and sentences (CRLF kept)

## Decisions Made

See key-decisions. The plan is `type: execute`; the RED commits are format-based as in plans 17-21 to 17-27.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Doc tests for CLAUDE.md and README.md**
- **Found during:** Task 2
- **Issue:** the plan's file list names only `tests/test_help_dialog.py`, but CLAUDE.md and README.md had no check that they say what the app does; `tests/test_docs_split.py` already holds that kind of check (SPLIT-05, SPLIT-06)
- **Fix:** two tests in `tests/test_docs_split.py` (the add-on list and CAT-10, the scratch switch and the no-workstation-path rule), written RED first
- **Files modified:** tests/test_docs_split.py
- **Committed in:** `0cdfffc`, `85fe527`

**2. [Rule 1 - Bug, test] A backspace character in the first draft of a test regex**
- **Found during:** Task 2
- **Issue:** the draft of `test_catalog_page_plain_language` carried a second regex whose `\b` was written in a non-raw string and became a backspace character in the committed RED file
- **Fix:** the redundant regex was removed in the GREEN commit; the plan's own rule (`PCM` not followed by an underscore) stays
- **Files modified:** tests/test_help_dialog.py
- **Committed in:** `b743bbd`

**3. [Plan wording] The refreshing text is quoted by its fixed part**
- The plan's behaviour block says the guide names 'Refreshing the library list...'; the app's line is `Refreshing the library list after {verb} {name}. ...`, so the guide and its test use `Refreshing the library list after adding` and the library's name.

**Total deviations:** 3 (1 missing critical, 1 test bug, 1 wording). **Impact:** none on scope.

## Issues Encountered

- A first helper script with a bash heredoc ended with an unmatched-quote error from the tool and wrote nothing; the script was written to a file with the Write tool instead.

## Known Stubs

None.

## Threat Flags

None. No code path, network endpoint or file access was added; the pre-publish scan of the whole tree is clean (T-17-67).

## User Setup Required

None.

## Next Phase Readiness

- 17-18 and 17-19 can rehearse against a contract and guide that match the app; the human checks of 17-25 (real list, offline copy, Add 4ms, Alternate's tick, the Cannot be added yet rows) and the look of the refreshing wheel (17-23) are still the owner's.
- The owner may want to read the new guide paragraphs for tone (D5).

## Self-Check: PASSED

- All six modified files exist; commits `0f277f4`, `bd525dd`, `b743bbd`, `0cdfffc`, `85fe527` are ancestors of HEAD; `git rev-list --count 3ba566e..HEAD` was 5 before this file.
- Acceptance greps: `Refreshing the library list after` 1, `Cannot be added yet` 2, `Names in KiCad` 4, `symbol and {f} footprint libraries` 2 in the UI-SPEC; `KiCad's add-on list` 7 and `scratch-root` 1 in `help_dialog.py`; `add-on list` 4 and `scratch-root` 3 in CLAUDE.md.
- `-n 0`: tests/test_help_dialog.py, test_docs_split.py, test_corpus_audit.py, test_custom_literals.py (225 passed); the guide tests of test_import_dialog.py and test_main_window.py (`-k guide`, 13 passed). The pre-publish scan of the whole tree is clean.

---
*Phase: 17-library-catalog*
*Completed: 2026-11-27*
