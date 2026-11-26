# Phase 15 — UI Review

**Audited:** 2026-11-26
**Baseline:** 15-UI-SPEC.md (approved 2026-11-23, with the 2026-11-23 owner-test amendment)
**Screenshots:** not captured (PySide6 desktop app, no dev server or URL; code-level audit only)
**Interaction captures:** off (`interaction_capture: false`)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Nearly all spec strings present verbatim; first-commit git identity sentence missing and the existing wording uses jargon (`user.name`, `user.email`) |
| 2. Visuals | 3/4 | Layout follows the spec (row above toolbar, two-button dialog footers, check strip); Open dialog path field is not in Mono; first-run row 1 path rendering unverified against the Mono rule |
| 3. Color | 3/4 | Accent limited to the two primary buttons and progress chunk as specified; amber/error/success always paired with a glyph; dark-mode and high-contrast behaviour is an open assumption in the spec |
| 4. Typography | 3/4 | Only the three declared styles (Body 9pt, Heading 10pt bold, Mono 9pt Consolas) are used; the Open dialog Folder field and check-strip paths are not Mono as the spec requires |
| 5. Spacing | 3/4 | Margins and spacing use the theme tokens (SP_MD 16, SP_SM 8, SP_XS 4) as the spec declares; no pixel-level or rendered check was run, so the score reflects code evidence only |
| 6. Experience Design | 3/4 | Busy refusals, checking strip, Creating... state, focus rules, Esc/Quit and debounce are all implemented; the commit-panel first-commit identity guidance is missing and the Recent/first-run states rely on the UAT record rather than code evidence |

**Overall: 18/24**

---

## Top 3 Priority Fixes

1. **First commit of a new collection gives no plain-language identity guidance** — the owner sees git's own wording ("git does not know who you are: set user.name and user.email, or ...") with no instruction on what to type — Add the spec sentence to the commit outcome path for `parent_mode = none`: `Git has no name or email set. Run git config --global user.name "Your Name" and git config --global user.email "you@example.com", then commit again.` (ERROR colour). Sites: `kicad_lib_manager/importer/commit_step.py:182` and `kicad_lib_manager/importer/migration/precheck.py:83`.

2. **Folder paths are not set in Mono in the Open Library Collection window** — the Folder field and the check-strip path text use the system font, so paths look different from the Library folder row and the New Collection preview, against the spec's "every folder path is Mono" rule — Apply `QFont(theme.MONO_FAMILY, theme.MONO_PT)` to `self._field` in `choose_folder_dialog.py` (near line 85) and to the path text of the check rows; confirm the first-run row 1 path is Mono (`first_run_dialog.py:107` sets it only on one branch).

3. **Dark-mode and high-contrast themes are unverified on every new surface** — the amber, red and green text colours and the `LogPanel` black text assume the light Windows palette; the spec marks this as an unresolved planner assumption and the UAT did not cover it — Run one manual pass with Windows dark mode and high-contrast enabled over the main window, Open Library Collection, New Collection and the first-run window; if text becomes unreadable, set explicit foreground and background pairs for the strips instead of relying on the palette.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Verified present verbatim in source (file reference in parentheses):
- Menu labels `New Library Collection...`, `Open Library Collection...`, `Use KiCad's Folder`, `Recent Library Collections`, `Show Library Folder in Explorer` (`main_window.py:107-115`).
- Tooltips: `Create a new, empty library collection and switch to it`, `Open a folder that already holds a library collection`, `Open another library collection` (`main_window.py:108-145`).
- Dialog titles `Set Up Your Library Folder`, `Open Library Collection`, `New Collection` (`first_run_dialog.py:55`, `choose_folder_dialog.py:46`, `new_collection_dialog.py:107`).
- Back buttons `Keep Current Folder`, `Back to Setup`, `Back to Open` (`choose_folder_dialog.py:27`, `new_collection_dialog.py:30`).
- Empty-state heading and body (`main_window.py:154-155`), the empty-folder and not-a-collection rows (`collection.py`), the custom-folder row (`collection.py:210`), the wrong-folder warning (`kicad_setup.py:268-270`), `Created a new collection in` and `No library folder chosen; exiting.` (`main_window.py`, `startup.py`).
- Plain-language style is kept in dialog bodies (`_BODY` constants in all three dialogs).

Findings:
- **WARNING** — Commit outcome for a missing git identity does not carry the spec sentence. The existing text (`importer/commit_step.py:182`, `importer/migration/precheck.py:83`) reads `git does not know who you are: set user.name and user.email, or ...`. The owner asked for plain language with no raw field names; `user.name` and `user.email` are the raw git keys. Replace with the spec sentence (see Fix 1).
- **WARNING** — The spec's required copy for the Explorer status tip (`Open {path} in Explorer`) and the legacy source tag (`the folder this app runs from`) are not in the code. The legacy tag was removed with the Phase 16 change (`collection.py` `Source` enum has four members); this is consistent with the Phase 16 note in the spec, so it is recorded as spec drift, not a defect.
- **INFO** — The User Guide and help text (`widgets/help_dialog.py`) omit the Check Atomic Parts busy state (deferred item IN-01 in 15-REVIEW-DISPOSITION.md). Copy-only, not user-blocking.

### Pillar 2: Visuals (3/4)

- Library folder row is the first item above the toolbar, with `ElidedLabel` (middle elision, full path tooltip, accessible name `Library folder`), a source tag and `Change Folder...` with tooltip `Open another library collection` (`main_window.py:695-712`). Matches the spec layout.
- The three dialogs use the spec's outer margins (SP_MD) and button rows with PRIMARY_BUTTON_QSS on exactly the two accent buttons (`choose_folder_dialog.py:125`, `new_collection_dialog.py:217`).
- The first-run window uses three framed option rows and a Quit button (`first_run_dialog.py:117-139`), matching the layout diagram.
- **WARNING** — The UAT run recorded that the Open dialog's amber path-length row clipped to one line and that the New Collection dialog's footnote overlapped the preview by 16-25 px. The 2026-11-23 gap-closure (plans 15-13 to 15-16) reports both fixed on re-run; this audit did not re-measure geometry, so the fix is taken from the UAT record.
- **WARNING** — The main window has a 965 px minimum width set by the pre-existing toolbar. The spec accepts this, but the 900 px target in the UAT was not met (UAT item 4c). Known, deferred to Phase 19.

### Pillar 3: Color (3/4)

- Accent (`ACCENT`/`PRIMARY_BUTTON_QSS`) appears only on `Open Collection` and `Create Collection` plus the indeterminate progress chunk, as the spec's reserved list requires (`choose_folder_dialog.py:125`, `new_collection_dialog.py:217`). First-run window has no accent button, as specified.
- Semantic colours come from `theme.py` constants (`AMBER`, `ERROR`, `SUCCESS`, `MUTED`, `SURFACE`, `BORDER`); no new hex value is introduced in the three dialogs.
- Every coloured row carries a glyph or word (`✖`, `⚠`, `✓`), satisfying the colour-is-not-only-cue rule.
- **WARNING** — The spec lists Windows dark mode and high-contrast themes as an unresolved assumption (Resolved table, `overflow` row). Nothing in the code or UAT covers it. See Fix 3.

### Pillar 4: Typography (3/4)

- Only `HEADING_PT` (10pt bold) and the system default body size are used; `setPointSize` is not called outside the heading (`choose_folder_dialog.py:70`, `first_run_dialog.py:76,170`, `new_collection_dialog.py:134`). Three styles, as declared.
- Mono is applied to the Library folder row path (`main_window.py`), the New Collection `Will create:` line (`new_collection_dialog.py:167`) and the first-run row 1 description branch (`first_run_dialog.py:107`).
- **WARNING** — The Open Library Collection `Folder` `QLineEdit` (`choose_folder_dialog.py:83-86`) is set without a font, so the path it shows is the system font. The spec states every folder path is Mono. See Fix 2.
- **WARNING** — Check-strip row labels (`choose_folder_dialog.py:226-241`) render the path-bearing rows (for example the `Choose a folder` placeholder and the path-length row) in the body font; the spec puts folder paths in Mono throughout.

### Pillar 5: Spacing (3/4)

- Dialog margins and spacing use the theme tokens: outer margins SP_MD (16), form and button gaps SP_SM (8), strip padding SP_SM and row gaps SP_XS (4) (`choose_folder_dialog.py:65-116`, `first_run_dialog.py:71-166`, `new_collection_dialog.py:129-210`). All values sit on the 4px scale declared by the spec.
- Minimum control heights of 28px are set on the Change Folder button (`main_window.py`) and the dialog controls (`_MIN_CONTROL_HEIGHT = 28`).
- Score is 3, not 4, because no rendered or measured check was run on this audit. The owner's UAT measured overlap at 100% and 175% and the record says it is fixed, but that evidence is not re-verified here.

### Pillar 6: Experience Design (3/4)

Implemented and verified in code:
- Busy refusals with one warning log line and one 5 s status message (`main_window.py`, spec copy in `Busy refusal` rows).
- Off-GUI-thread folder checks with the `Checking the folder...` strip and an indeterminate bar; Open Collection disabled while it runs (`choose_folder_dialog.py:266-269`).
- Creation runs in a `TaskWorker` with `Creating...` and the form disabled; Esc and the back button ignored while it runs (`new_collection_dialog.py:379`).
- Focus rules: Folder field on open, Name field with text selected on New Collection, Symbols tree or Import Part... after a switch (`main_window.py:1024`).
- `Esc` and Quit paths in the first-run window: exit code 0 and the stderr line (`startup.py`).
- Empty-collection page is shown after a completed scan with zero libraries and hidden while a scan runs (`main_window.py:154-155`); UAT item 3 records the earlier focus bug as fixed.
- Recent folders are checked on a worker so a dead drive does not freeze File (`main_window.py:577-582`).

Findings:
- **WARNING** — First-commit identity failure gives no plain instruction (see Pillar 1 and Fix 1). A new-collection owner who has never set git identity hits this path on the first commit.
- **WARNING** — Behaviour in the first-run row 1 when KiCad's folder check fails depends on a Mono branch and a disabled button; the disabled-state copy is in code, but the UAT record is the only evidence the button stays visible at 560 px.

---

## Files Audited

- `.planning/phases/15-choose-library-folder-and-new-collection/15-UI-SPEC.md`
- `.planning/phases/15-choose-library-folder-and-new-collection/15-UAT.md`
- `.planning/phases/15-choose-library-folder-and-new-collection/15-REVIEW-DISPOSITION.md`
- `kicad_lib_manager/widgets/choose_folder_dialog.py`
- `kicad_lib_manager/widgets/first_run_dialog.py`
- `kicad_lib_manager/widgets/new_collection_dialog.py`
- `kicad_lib_manager/main_window.py` (library folder row, File menu, busy state, empty-collection copy, switch sequence)
- `kicad_lib_manager/collection.py` (folder check rows, Source tags, Program Files and reserved-name checks)
- `kicad_lib_manager/startup.py` (first-run exit line, Created a new collection log)
- `kicad_lib_manager/kicad_setup.py` (wrong-folder warning copy)
- `kicad_lib_manager/importer/commit_step.py` and `importer/migration/precheck.py` (git identity wording)
- `kicad_lib_manager/widgets/help_dialog.py` (help copy, deferred IN-01)
- `kicad_lib_manager/widgets/theme.py` (token names only)
