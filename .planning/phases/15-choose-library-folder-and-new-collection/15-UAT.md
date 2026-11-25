---
status: complete
phase: 15-choose-library-folder-and-new-collection
source: [15-01-SUMMARY.md, 15-02-SUMMARY.md, 15-03-SUMMARY.md, 15-04-SUMMARY.md, 15-05-SUMMARY.md, 15-06-SUMMARY.md, 15-07-SUMMARY.md, 15-08-SUMMARY.md, 15-09-SUMMARY.md, 15-10-SUMMARY.md, 15-11-SUMMARY.md, 15-12-SUMMARY.md]
started: 2026-11-23T10:00:00Z
updated: 2026-11-23T12:00:00Z
---

## Current Test

number: -
name: automated offscreen run complete (on-screen pass pending after gap closure)
expected: |
  -
awaiting: none - automated UAT complete (offscreen + native on-screen)

## Method

The owner asked for the manual UAT to be automated. A script drove the real app (`startup.run`, real windows, `QT_QPA_PLATFORM=offscreen` because the owner was using the PC) in fully isolated scratch state (APPDATA, LOCALAPPDATA, HOME, USERPROFILE, KICAD_CONFIG_HOME, scratch copy of the real kicad_common.json, scratch collections), clicking buttons with QTest and saving screenshots with `widget.grab()`. Evidence: scratchpad `uat15/UAT-REPORT.md`, `uat15/shots/` (52 PNGs), `uat15/logs/`, scripts `uat15/scripts/run_all.py` (offscreen, ~2.5 min) and `run_onscreen.py` (native, ~4 min, hands off). Real-file integrity: all 425 recorded entries (real KiCadExtLibManager folders, real kicad_common.json, HEAD/status of the 4 real repos) identical before and after; settings.ini sha256 128bd8f8…0f69c11, kicad_common.json sha256 f6a8528b…5f0d6.

## Tests

### 1. First run with empty settings and no KICAD_LIB_GITHUB
expected: setup window with three rows, KiCad row disabled when the variable is unset (enabled when set); Quit exits 0 with "No library folder chosen; exiting." and writes no settings
result: pass

### 2. Change Folder, KiCad path-variable question No then Yes, Use KiCad's Folder
expected: switch rescans; VAR: old -> new offered after the scan; No leaves kicad_common.json byte-identical and logs that KiCad still points at the old folder; Yes writes both variables absolute with forward slashes after a backup; Use KiCad's Folder asks nothing and removes library/root
result: pass

### 3. New Collection in a Documents folder, first part imported and committed
expected: skeleton created, git init -b main in Custom with no commit, app switches to it and shows the empty-collection page with focus on Import Part...; the UL sample imports; the commit panel shows no parent option; the first commit holds only the three part files; skeleton files stay untracked
result: pass
resolved_note: \"Fixed by gap-closure plans 15-13..15-16; re-run offscreen and native on-screen 2026-11-23 pass.\"
original_report: "Automated run: skeleton, git init, import, first commit of only the 3 part files, hidden parent option and untracked skeleton all pass, but the empty-collection page never shows: the skeleton's empty Atomic_Footprints.pretty counts as one footprint library ('Found 0 symbol libraries, 1 footprint libraries') and _show_list_page needs both counts zero, so focus lands on the Symbols tree instead of Import Part... (shot s3_03_main_empty_collection.png)"
severity: major

### 4. 200-character path at 900 px and 175% scaling
expected: the Library folder row elides in the middle with the full path as tooltip; the window works at 900 px; the main window and the three dialogs fit at 175%
result: pass
resolved_note: \"Fixed by gap-closure plans 15-13..15-16; re-run offscreen and native on-screen 2026-11-23 pass.\"
original_report: "Automated run: row elision, tooltip and Change Folder... placement pass and all dialogs fit at 175%, but (a) the New Collection dialog lays out at its minimum height 80-100 px below its size hint, so its footnote overlaps the README.md line of the preview by 16-25 px at 100% and 175%, from setup and from Choose (shots s4b_04_new_collection.png, s4c_03_new_collection_from_setup.png, s1b_row1_new_collection_prefilled.png); (b) the Choose dialog clips a wrapped strip row: the amber path-length warning shows only its first line (s2_02_choose_B_strip.png); (c) the main window cannot be 900 px wide: the pre-existing toolbar sets a 965 px minimum"
severity: major

### 5. Dead network drive as the remembered folder
expected: the next choice is used within about 5 s with a log line naming the skipped folder
result: pass

### 6. CR-02 relative paths end up absolute
expected: relative --library-root and a typed relative folder become absolute in the row, title, library/root, library/recent, the VAR question and the written KICAD_LIB_GITHUB
result: pass

### 7. WR-01 File menu with a dead Recent entry
expected: the menu opens at once and the dead entry drops after the background check
result: pass

### 8. WR-03 closing during a slow folder check
expected: the process exits cleanly with no late switch, scan or settings write
result: pass
resolved_note: \"Fixed by gap-closure plans 15-13..15-16; re-run offscreen and native on-screen 2026-11-23 pass.\"
original_report: "Automated run: no settings write and no late switch, but the process crashes on exit: 'QThread: Destroyed while thread '' is still running' (fatal), exit code 0xC0000409. Reproduced with a pending switch check (s8) and with only the Recent-entry existence check running (s8b); the control without a dead entry (s8c) exits 0. The still-running workers are parked in the module-level PARKED_WORKERS list (import_dialog.py) and destroyed at interpreter shutdown while blocked in Path.is_dir() on the dead UNC path (logs s8.stderr.txt, s8b.stderr.txt)."
severity: blocker

### 9. Destination after a switch (found during the run)
expected: (owner decision 2026-11-23) when Destination is the old library folder or empty, a switch changes it to the new library folder; a Destination the user picked elsewhere stays
result: pass
resolved_note: \"Fixed by gap-closure plans 15-13..15-16; re-run offscreen and native on-screen 2026-11-23 pass.\"
original_report: "Automated run: after switching A -> B with an empty Destination history the Destination box still shows A, so Generate Tables would write B's tables into A."
severity: major

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Re-run after gap closure (offscreen, 2026-11-23, app code at HEAD 860e05e)

All scenarios re-run with the refreshed app copy: s1a-d, s2, s3 (21/21 checks, empty-collection page and Import Part... focus now shown), s4a, s4c, s4d, s5, s6, s7 pass; s8/s8b/s8c (after updating the driver to the new background-task API) exit 0 in ~0.03 s with 2 / 1 / 0 checks still blocked at close, no 'QThread: Destroyed', no settings write. s4b: the only failures are the accepted 965 px minimum width and one new minor item: at 175% on a 1920x1080 screen (logical 1097x617) the taller New Collection dialog is placed at y=157 with height 465, so its frame ends 5 px below the available area (to confirm in the on-screen pass). Real-file integrity identical before/after (425 entries). Full suite after the gap fixes: 12173 passed, 6 skipped.

## Native on-screen pass (2026-11-23, owner hands off, real Windows platform plugin, desktop scale 1.0 + QT_SCALE_FACTOR 1.75)

All 12 on-screen scenario runs exit 0, no timeouts, no stray processes, real-file integrity unchanged. Every check passes except the accepted minimum width (natively 973-974 px with the Windows style; owner accepted the real toolbar minimum, Phase 19 rework). The New Collection dialog fits the screen at 175% natively (the 5 px offscreen-only overflow does not occur), its footnote sits below the preview, the empty-collection page shows for a new collection, and closing with a blocked check shows no crash dialog. Cosmetic follow-up noticed in the shots: the declined-offer log line reads "KiCad still points at (not set)." when KICAD_LIB_GITHUB is unset.

## Notes (not gaps)

- Owner decision 2026-11-23: the main window's real minimum width (965 px, set by the pre-existing toolbar) is accepted for Phase 15; the UI-SPEC 900 px note is amended and the toolbar is reworked with the Phase 19 menu regroup.
- The owner's manual step "first run from the main checkout" cannot show the first-run window while the legacy fallback (the app's own folder, when it holds a collection) exists — by design until Phase 16 removes it; the automated run used a `git archive HEAD` copy outside any collection.
- Cosmetic, not gaps: first-run heading label ~60 px tall for 17 px of text (large empty bands); "Linked Footprints" header cut at ~900 px (predates Phase 15).
- Still to run after gap closure: native on-screen pass (`uat15/scripts/run_onscreen.py`, ~4 min, owner hands off) to confirm native rendering at 900/965 px and true 175%, and that no crash dialog appears on exit.

## Gaps

- truth: "Closing the app while a background folder check is still blocked (dead network drive) exits cleanly: no QThread destroyed while running, exit code 0, no late switch, scan or settings write"
  status: resolved
  reason: "Automated UAT: fatal 'QThread: Destroyed while thread '' is still running', exit 0xC0000409 (s8, s8b); parked workers in import_dialog.PARKED_WORKERS are destroyed at interpreter shutdown while blocked in Path.is_dir() on a dead UNC path"
  severity: blocker
  test: 8
  root_cause: "Blocking filesystem checks run on QThread workers; at shutdown a worker still blocked in a syscall cannot finish, and the parked QThread object is destroyed while running. Needs a design where a hung check can never be a live QThread at exit (e.g. checks on daemon Python threads posting results back via a Qt signal/queued call, or leaking the parked QThread objects past interpreter teardown)."
  artifacts: ["kicad_lib_manager/widgets/import_dialog.py (join_workers, PARKED_WORKERS)", "kicad_lib_manager/main_window.py (_root_check_workers, recent-folder existence worker, closeEvent)", "kicad_lib_manager/widgets/choose_folder_dialog.py", "kicad_lib_manager/widgets/first_run_dialog.py", "kicad_lib_manager/widgets/new_collection_dialog.py", "kicad_lib_manager/startup.py (5 s startup check)"]
  missing: ["a test that runs the app in a child process with a check blocked past close and asserts exit code 0 and no 'QThread: Destroyed' on stderr"]
  debug_session: ""
  resolved_by: "gap-closure plans 15-13..15-16"
  resolved_at: "2026-11-23"
- truth: "A new (or any) collection with no symbols and no footprints shows the 'No libraries in this collection yet' page after its scan, with focus on Import Part..."
  status: resolved
  reason: "Automated UAT: the skeleton's empty Atomic_Footprints.pretty counts as 1 footprint library, so the empty page never shows and focus goes to the Symbols tree (s3_03_main_empty_collection.png)"
  severity: major
  test: 3
  root_cause: "_show_list_page treats any footprint library as content; an empty .pretty folder (no .kicad_mod) should not count"
  artifacts: ["kicad_lib_manager/main_window.py (_show_list_page / empty-page condition)"]
  missing: ["a test with the real create_collection skeleton (empty Atomic_Footprints.pretty) asserting the empty page and the Import Part... focus"]
  debug_session: ""
  resolved_by: "gap-closure plans 15-13..15-16"
  resolved_at: "2026-11-23"
- truth: "The New Collection dialog never draws content over other content (footnote below the preview, not over it) at 100% and 175%, opened from setup or Choose; the Choose dialog shows wrapped strip rows in full"
  status: resolved
  reason: "Automated UAT: footnote overlaps the README.md preview line by 16-25 px; dialog sits 80-100 px below its size hint; Choose clips the amber path-length warning to its first line (s4b_04, s4c_03, s1b_row1, s2_02)"
  severity: major
  test: 4
  root_cause: "Dialog minimum height below the layout's size hint (fixed/maximum height or missing size constraint) and word-wrapped labels in the strip not reporting height-for-width"
  artifacts: ["kicad_lib_manager/widgets/new_collection_dialog.py", "kicad_lib_manager/widgets/choose_folder_dialog.py"]
  missing: ["geometry tests: no child widget rectangles overlap in the New Collection dialog at default and 1.75 scale; a wrapped strip row's label height fits its text"]
  debug_session: ""
  resolved_by: "gap-closure plans 15-13..15-16"
  resolved_at: "2026-11-23"
- truth: "After a library folder switch, Destination follows the folder when it was the old library folder or empty; a Destination the user picked elsewhere stays (owner decision 2026-11-23)"
  status: resolved
  reason: "Automated UAT: after A -> B with an empty Destination history the box still shows A; Generate would write B's tables into A"
  severity: major
  test: 9
  root_cause: "_switch_root does not touch the Destination combo"
  artifacts: ["kicad_lib_manager/main_window.py (_switch_root, _populate_dest_combo, settings dest_history)"]
  missing: ["tests: switch A->B with Destination == A -> B; with empty history -> B; with Destination = a project folder elsewhere -> unchanged"]
  debug_session: ""
  resolved_by: "gap-closure plans 15-13..15-16"
  resolved_at: "2026-11-23"
