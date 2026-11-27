---
phase: 17-library-catalog
plan: 25
subsystem: catalog
tags: [catalog, kicad-addon-list, catalog-window, offline-copy, add-flow, tdd]

requires:
  - phase: 17-library-catalog
    provides: addons.read_index / Listing / IndexRead and settings.addon_index_file (17-22), the add-on name rule, AddSource.default_prefix / addon_id and CatalogEntry.name / addon_id (17-24), the decisions D-33 to D-37 (17-17)
provides:
  - status.row_statuses(listings=) and Row.listing / description / addable / reason / origin
  - ops.check_repository(listings=), CheckedRepo.listing, the listing source (KiCad's name, licence fallback, PCM_ default, add-on id), ops.LISTING_SPACE_FACTOR
  - the catalog window reads KiCad's add-on list off the GUI thread, lists it, marks the odd ones, and adds one through the same checks as every Add
  - catalog_pages.NAMES_HEADING and the Names in KiCad section of the Add preview; LicencePage.show_refusal
affects: [17-26, 17-27]

plan_head_before: 80078c33793912df2affcfac5d1d0836f725ba88
plan_head_after: 2e2beb9dab4b0abfe694cca21b8555a67a4601b7

actuals:
  tokens: 18700
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "catalog.status and catalog.ops read a listing by attribute and never import catalog.addons (a network module); only the window imports it"
    - "the window's list of KiCad's add-ons follows the generation-number rule of the other background tasks: a late answer after a close or a root change is dropped"
    - "a live list read once is kept for the window's life; a failed read (no list, or only the kept copy) is tried again at the next show or root change"

key-files:
  created: []
  modified:
    - kicad_lib_manager/catalog/status.py
    - kicad_lib_manager/catalog/ops.py
    - kicad_lib_manager/widgets/catalog_dialog.py
    - kicad_lib_manager/widgets/catalog_pages.py
    - tests/test_catalog_status.py
    - tests/test_catalog_ops.py
    - tests/test_catalog_dialog.py
    - tests/test_catalog_dialog_add.py
    - tests/test_catalog_dialog_geometry.py
    - tests/test_catalog_pages.py

key-decisions:
  - "The merge rules as coded (status.row_statuses): (1) curated rows first; a listing whose git address or page has the repo_key of a curated library is dropped (curated wins: its licence, size, variables and description are used); (2) a recorded library that is not curated takes the listing whose identifier equals its addon_id, else whose address or page has the repo_key of its address, and its row gets that listing, its description, origin 'addon', and the name entry.name or KiCad's name or names.display_name; with no listing its origin is 'addon' when it carries an addon_id and 'url' otherwise; (3) every other listing is a row of its own: an addable one with id urls.default_id(owner, repo), a not-addable one with its identifier, state NOT_INSTALLED, or NOT_IN_CATALOG when a ThirdParty folder of that id exists (a listing whose id is already a row is skipped); (4) a stray folder is origin 'folder'; rows stay sorted by name then id"
  - "Row fields: listing (the object read by attribute), description (curated description or KiCad's), addable (False only for a listing row with no entry), reason, origin (curated, addon, url or folder). A listing row's licence is KiCad's own (known=True: its review counts as the D-22 check), its size KiCad's install_mb"
  - "The read and retry rule: the window starts read_index (default: addons.read_index with settings.addon_index_file()) on a daemon task with every other background check; state is reading, ok, copy (an IndexRead with an issue and the kept copy's listings, shown with its date), failed (an issue and nothing) or idle. Only ok sets _index_ok, which keeps the live list for the window's life; copy and failed are tried again at the next show after a close and at a root change. Nothing is logged for a failed read (a crash of the read function is logged like the other steps)"
  - "A listing source (ops._checked_source): name KiCad's, id owner-repo, licence GitHub's when GitHub names one (a class other than NOT_STATED) else KiCad's, licence_known always True, nickname_prefix None with default_prefix 'PCM_' and addon_id the identifier; sizes (ops.plan_add): size_mb is KiCad's install_mb (GitHub's rounded size when KiCad gives none), needs_mb is 6 x GitHub's MB + 500 when GitHub answered, else LISTING_SPACE_FACTOR (2) x install_mb + 500, else None (no space check)"
  - "check_repository order: parse, already listed (record, curated list), the listing of that repository (by address or page), refusal 'catalog.not_addable' with the listing's reason when it cannot be added, then the GitHub lookup; the listing is attached to the CheckedRepo"
  - "The line about KiCad's list is hidden while a review page is open, so the licence, preview, update and remove pages keep their buttons in view at 760 x 520 (the line costs about 22 px)"

patterns-established:
  - "A listing flow is an Add whose check starts from the Details page: _Flow(kind add, listed=True), the list locked to the row, the job strip 'Checking the repository...', then the licence page (or its refusal mode with Back to List only), then the shared download, preview and register"

requirements-completed: [CAT-01, CAT-02, CAT-03, CAT-09]

coverage:
  - id: D1
    description: "The catalog lists the libraries of KiCad's add-on list beside the curated ones, read off the GUI thread; each is one row with KiCad's name, licence label, install size and Not installed; a curated library is listed once; an installed one is one row with the listing's description"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_status.py#test_listing_rows"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_status.py#test_a_recorded_library_takes_its_listing"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_add_from_kicads_list"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_search_finds_listing_descriptions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Offline, the kept copy's libraries show beside the curated list with the date; with no copy only the curated list; nothing is logged; a later show tries again and a live list is kept"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_reading_line_states"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_unread_list_line_and_retry"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_offline_copy_is_shown_with_its_date"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_kicads_list_unread_keeps_the_curated_list"
        status: pass
    human_judgment: false
  - id: D3
    description: "A library the catalog cannot add yet shows Cannot be added yet with its reason, has no Add This Library, and Add by URL of its repository is refused with that reason before any GitHub lookup"
    requirement: CAT-03
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_not_addable_rows"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_url_of_a_not_addable_listing_is_refused"
        status: pass
    human_judgment: false
  - id: D4
    description: "Add This Library on a listing runs the GitHub check, then the licence page with KiCad's name, the cleaned address, GitHub's licence or KiCad's and the size; a refused check shows its reason with Back to List only; Alternate Kicad Library asks for the CC BY-SA tick; the staged source carries KiCad's name, id and the PCM_ default"
    requirement: CAT-02
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_refused_check_from_the_list"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog_add.py#test_add_alternate_from_the_list"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_listing_licence_fallback"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_listing_sizes"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_listing_source_rule"
        status: pass
    human_judgment: false
  - id: D5
    description: "Add by URL of a repository that KiCad's list holds adds it as that listing; an installed listing is still refused as already listed"
    requirement: CAT-03
    verification:
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_url_of_a_listed_repository"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_ops.py#test_an_installed_listing_is_already_listed"
        status: pass
    human_judgment: false
  - id: D6
    description: "The Details page says where a library is listed (KiCad's add-on list, with the copy's date offline; this app's own list; its web address; nothing for a stray folder) and a not-installed listing shows its description, link, about size and Known after it is added"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_listed_in_row"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_dialog.py#test_listing_details"
        status: pass
    human_judgment: false
  - id: D7
    description: "The Add preview has a Names in KiCad section for a library that gets KiCad's add-on names or one of KiCad's list that keeps its own"
    requirement: CAT-09
    verification:
      - kind: unit
        ref: "tests/test_catalog_pages.py#test_names_section"
        status: pass
    human_judgment: false
  - id: D8
    description: "With the new line and every strip shown at 760 x 520 the list keeps 120 px and the toolbar stays visible"
    requirement: CAT-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_dialog_geometry.py#test_all_strips_and_the_reading_line_at_minimum_height"
        status: pass
    human_judgment: false
  - id: D9
    description: "With network the catalog lists 18 rows before anything is installed; offline after an earlier online start the same rows with the dated line; Add 4ms Kicad Libraries from the list ends Installed under its own names; Alternate Kicad Library asks for the CC BY-SA tick"
    verification: []
    human_judgment: true
    rationale: "Needs the real list, GitHub and a real clone; it is the first part of the 17-19 owner rehearsal (D-37), not a test"

duration: 19min
completed: 2026-11-27
status: complete
---

# Phase 17 Plan 25: KiCad's add-on list in the catalog window Summary

**The catalog window lists KiCad's reviewed add-on libraries beside the curated ones (live, or the kept copy with its date offline), explains the ones it cannot add yet, and adds a listed library by cloning its GitHub repository through the same check, licence page, download check and preview as every other Add, under KiCad's name and licence and the add-on name rule.**

## Performance

- **Duration:** 19 min
- **Completed:** 2026-11-27
- **Tasks:** 3 (1 tracer, 2 auto, all TDD)
- **Files modified:** 10 (4 source, 6 test)

## Accomplishments

- **The rows.** `row_statuses(listings=)` merges KiCad's listings with the curated list, the record and the ThirdParty folders (rules in key-decisions). `Row` gains `listing`, `description`, `addable`, `reason` and `origin` with defaults, so every earlier row and fake keeps working.
- **The read.** `CatalogServices.read_index` (default: `addons.read_index` with the app's kept copy) runs on a daemon task beside the Git check, with the generation number of the other tasks. A muted, unframed line under the strips reads `Reading KiCad's add-on list...`, then disappears after a live read, or reads `Showing KiCad's add-on list from {date}. The current list could not be read right now.` (the kept copy's libraries are listed; the reason is the tooltip) or `KiCad's add-on list could not be read right now, so only this app's own list is shown.` Nothing goes to the log. A live read is kept for the window's life; the other two outcomes are read again at the next show and at a root change.
- **The odd ones.** A listing the catalog cannot add yet has the muted status `Cannot be added yet` (reason as tooltip), its reason as a muted line under the description, no Add This Library and its page as Repository link. `Listed in` says `KiCad's add-on list (reviewed by the KiCad team)` (with the copy's date while the copy is shown), `This app's own list` or `Added by its web address`, and nothing for a stray folder. A not-installed listing shows `Known after it is added` for libraries and path variables. Search also matches descriptions and listing pages.
- **The Add.** Add This Library on a listing runs the GitHub check (`Checking the repository...`, Cancel Check, list locked), then `plan_add`, then the licence page `Add {KiCad's name}` with the cleaned address, GitHub's licence when it names one else KiCad's, the size and the install folder; a refused check (or a crash of it) shows its reason on that page with Back to List only; Cancel Check goes back to the row. From there Download and Check, the preview and Add Library are the shared ones, so no listing can skip a step.
- **Add by URL** of a listed repository attaches its listing (same name, licence, rule, add-on id); of one the catalog cannot add yet it answers `catalog.not_addable` with the listing's reason before any GitHub lookup; an installed one is still `already listed`.
- **Names in KiCad.** The Add preview, after the path variables, says either that the libraries get the names KiCad gives add-on libraries (rule PCM_) or that a library of KiCad's list keeps its own names, with the first footprint (else symbol) library as the example; none for a curated or address-added library with its own names.

## Task Commits

1. **Task 1 (tracer): a library of KiCad's list appears and reaches its licence page** - RED `926c52e`, GREEN `7f647d9`. Tracer verified end-to-end (dialog, status, geometry, update modules and both layering tests pass) before expanding.
2. **Task 2: merged rows, not-addable rows, Details and the reading line** - RED `33d79cd`, GREEN `5f6ba37`
3. **Task 3: sizes, not-addable refusal, Names in KiCad** - RED `d9deca6`, GREEN `2e2beb9`

**Plan metadata:** the docs commit that holds this file, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `kicad_lib_manager/catalog/status.py` - listing rows, `Row` fields
- `kicad_lib_manager/catalog/ops.py` - `CheckedRepo.listing`, `check_repository(listings=)`, the listing source, `LISTING_SPACE_FACTOR`, the sizes
- `kicad_lib_manager/widgets/catalog_dialog.py` - the read, the line, `Cannot be added yet`, `Listed in`, the listed flow
- `kicad_lib_manager/widgets/catalog_pages.py` - `LicencePage.show_refusal`, the Names in KiCad section
- the six test modules named in the frontmatter

## Decisions Made

See key-decisions. RED commits are format-based as in plans 17-21 and 17-22: the plan is `type: execute`, so the `tdd-red-evidence` classifier gate of `type: tdd` plans was not run and no evidence record was written. The Task 1 REDs fail on `TypeError: CatalogServices.__init__() got an unexpected keyword argument 'read_index'` (the planned missing feature), Task 2's on a missing `_index_line` / `Listed in` field / `Cannot be added yet` status (7 dialog tests and the geometry case), Task 3's on `LISTING_SPACE_FACTOR`, the missing refusal and `NAMES_HEADING` (3 tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] The line about KiCad's list is hidden while a review page is open**
- **Found during:** Task 2 (`test_review_page_buttons_stay_in_view_in_a_short_pane[760x520]` failed once the line existed)
- **Issue:** the line costs about 22 px of the 520 px window; with the amber Git strip the licence page's Download and Check button fell below the pane's visible area
- **Fix:** `_update_index_line` (called from `_refresh_actions`) hides the line while `_page_kind` is set and works the splitter out again after a layout pass (`layout().activate()` first, otherwise the split used the old height)
- **Files modified:** kicad_lib_manager/widgets/catalog_dialog.py
- **Verification:** the existing short-pane test passes unchanged
- **Committed in:** `5f6ba37`

**2. [Plan wording] The two-strip geometry case at 760 x 520 cannot also keep the long strips uncut with the line shown**
- **Found during:** Task 2
- **Issue:** the plan asks that with the line and every strip shown the list keeps 120 px and the toolbar stays visible; with a 290-character reason in the record strip the wrapped strip text is cut (111 px of the 138 it needs) because the splitter is already at its minimum
- **Fix:** the existing `test_all_strips_at_minimum_height` keeps all its assertions and runs with the list already read (line hidden); the new `test_all_strips_and_the_reading_line_at_minimum_height` asserts the plan's two conditions (list at least 120 px, toolbar visible) plus the close button, the size and no overlap, not the clipped-label check
- **Files modified:** tests/test_catalog_dialog_geometry.py
- **Committed in:** `5f6ba37`

**3. [Plan sequencing] The whole merge of `row_statuses` and the licence fallback were written in Task 1**
- **Issue:** the Task 1 tracer needs the merge with curated and recorded rows (to avoid a second row for an installed library) and the licence fallback (the licence page must show KiCad's licence with no GitHub answer), so the Task 2 status tests and `test_add_alternate_from_the_list` already passed at their RED commits
- **Impact:** none on behaviour; the RED commits say so

**4. [Rule 2 - Missing Critical] A listing with no size of its own shows GitHub's size**
- **Issue:** the plan sets `size_mb` to the listing's `install_mb`, which is None for a listing with no versions (CB KiCAD Libraries)
- **Fix:** `size_mb` is KiCad's `install_mb` when it has one, else GitHub's rounded size, else None
- **Files modified:** kicad_lib_manager/catalog/ops.py

---

**Total deviations:** 4 (2 missing-critical, 2 plan wording or sequencing). **Impact on plan:** none on scope.

## Issues Encountered

- Run with `-n 0`: the plan's four modules plus tests/test_catalog_dialog.py, test_catalog_dialog_add.py, test_catalog_dialog_geometry.py, test_catalog_dialog_update.py, test_catalog_pages.py, test_catalog_status.py, test_catalog_ops.py, test_catalog_ops_update.py, test_main_window_catalog*.py, test_corpus_audit.py, test_custom_literals.py, test_layering.py, test_catalog_layering.py, test_annotations_resolve.py, test_exit_with_hung_check.py and test_catalog_addons.py (717 passed), and with `--full` test_catalog_ops_git.py and test_catalog_tracer.py (17 passed). The whole quick parallel run named in Task 3's acceptance criteria was not run: the executor brief reserves it for the orchestrator's post-wave gate.
- A script that wrote a test file with `Path.write_text` turned its line endings into CRLF on Windows; it was caught by the diff before any commit and redone with `newline=""`.

## User Setup Required

None - no external service configuration required.

## Human checks left for verify-work (17-19 rehearsal, D-37)

- With network: open the catalog; the list holds 18 rows before anything is installed (Wurth Elektronik, SparkFun once, 16 others of today's 17 listings), the reading line goes away.
- Offline after an earlier online start: the same rows, with `Showing KiCad's add-on list from {date}...`; with no earlier start only the two curated rows and the plain `could not be read` line.
- Add `4ms Kicad Libraries` from the list: licence page, Download and Check, preview with `Names in KiCad` (own names), Add Library ends Installed; its footprint links resolve in KiCad.
- Add `Alternate Kicad Library`: the CC BY-SA tick is asked.
- Select KiKit, Kikakuka, Nuova Elettronica, the GitLab add-ons and KiMesh: `Cannot be added yet`, the reason, no Add button.

## Next Phase Readiness

- 17-26 and 17-27 can rely on `Row.origin` / `Row.listing`, `CheckedRepo.listing` and the recorded name and add-on id of a library added from KiCad's list. `main_window.py`, `settings.py`, `fsutil.py`, `startup.py`, `library_scanner.py` and `tests/conftest.py` were not touched.

## Self-Check: PASSED
