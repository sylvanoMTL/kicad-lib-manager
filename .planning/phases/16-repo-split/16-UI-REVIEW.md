# Phase 16 — UI Review

**Audited:** 2026-11-26
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for this phase). Scope limited to the user-facing surfaces Phase 16 changed.
**Screenshots:** not captured (PySide6 desktop app; code-only review, as directed)
**Interaction captures:** off (`interaction_capture: false`)

---

## Scope

Phase 16 is a repository split. Its only user-facing changes (per 16-02-SUMMARY.md and 16-07-SUMMARY.md) are:

1. `kicad_lib_manager/widgets/help_dialog.py`: the User Guide's "Which folder is used at start" list lost its code-folder item. It now lists four sources, then the setup window.
2. `kicad_lib_manager/main_window.py`: `MainWindow.__init__` default `source` is `Source.CHOSEN`, so a window built without a source shows the tag "your choice".
3. `kicad_lib_manager/startup.py` and `kicad_lib_manager/collection.py`: the code-folder candidate and `Source.LEGACY` are deleted. No visible widget change, but it changes which folder and tag the user sees at start.
4. `README.md` (tool README, 16-07): the four-source start order.

All other pillars are untouched by this phase and are reported as N/A (unchanged), not re-scored.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Start-order text is correct and plain, but the Library folder tags and the help text expose raw identifiers (`KICAD_LIBMGR_ROOT`, `--library-root`), which the project's plain-language rule forbids for user-facing text. Pre-existing, not introduced here. |
| 2. Visuals | N/A (unchanged) | No layout, widget or style change in Phase 16. |
| 3. Color | N/A (unchanged) | No colour change. The amber mismatch tag path is unchanged. |
| 4. Typography | N/A (unchanged) | No font or weight change. |
| 5. Spacing | N/A (unchanged) | No spacing change. |
| 6. Experience Design | 3/4 | The start now ends at the setup window instead of the code folder, and the log and User Guide say so. Gap: the `MainWindow` default `source` can silently label a folder "your choice" if a caller omits it, and the tag text is not self-explaining for the two command-line sources. |

**Overall (scored pillars only): 6/8.** The four untouched pillars are not scored, so this is not comparable to a full 24-point audit.

---

## Top Priority Fixes

1. **Raw identifiers in the Library folder tag** — the tags `set by --library-root` and `set by KICAD_LIBMGR_ROOT` (collection.py lines 93-94, shown in the main window row) are developer identifiers, and the project rule says user-facing text must be plain language. User impact: a non-developer owner reading the row cannot tell what to change. Fix: change the tag texts to plain wording such as `set when the app started` and `set by a start option`, and move the exact flag or variable name into the row's tooltip and the User Guide's code-styled reference. Keep the tag texts stable in `Source` because the help dialog quotes them; update both together.

2. **Silent default source on MainWindow** — `kicad_lib_manager/main_window.py:319` `source: Source = Source.CHOSEN`. A caller that forgets to pass the source labels the folder "your choice" even when it came from KiCad or the command line. User impact: the row can tell a false origin, which is the exact confusion this phase's SPLIT-08 work removes. Fix: make `source` a required keyword (no default) so every construction site states its origin; update the six test harnesses named in 16-02-PLAN.md (they can pass `Source.CHOSEN` explicitly).

3. **User Guide start list still names raw variable and flag in prose** — `kicad_lib_manager/widgets/help_dialog.py` lines 118-124 list `--library-root` and `KICAD_LIBMGR_ROOT` as the first two start sources. Plain-language rule applies. User impact: moderate; the owner is the main user, but the guide is the in-app explanation. Fix: lead each item with plain words ("a folder named on the command line", "a folder set in the environment") and keep the flag in a `<code>` aside.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

- Verified: `help_dialog.py` lines 118-127 now read four sources then "otherwise the setup window opens". The code-folder item is gone; no string matches "the folder the app runs from", "code folder" or "app folder" in `kicad_lib_manager/` or `README.md` (grep, 0 hits in user-facing text).
- Verified: `_chosen_note` (`collection.py` ~line 269) names only KiCad's folder: "Using KiCad's folder (path) instead." and "Choose a library folder to continue." Plain and correct.
- Finding (WARNING): raw identifiers in user-facing text. `collection.py:93-94` tags `set by --library-root`, `set by KICAD_LIBMGR_ROOT`; `help_dialog.py:118-124` repeats them. Pre-existing from Phase 15, but the Phase 16 rewrite of the start list is the natural point to fix it.
- Finding (INFO): `help_dialog.py` line 148 says "as your choice", which is consistent with the tag. Good.

### Pillar 2: Visuals (N/A, unchanged)

No layout or widget change. Not scored.

### Pillar 3: Color (N/A, unchanged)

The tag colour logic (`main_window.py` `_refresh_root_tag`, muted vs amber) is untouched. Not scored.

### Pillar 4: Typography (N/A, unchanged)

No font or weight change. Not scored.

### Pillar 5: Spacing (N/A, unchanged)

No spacing change. Not scored.

### Pillar 6: Experience Design (3/4)

- Verified: with the code-folder candidate removed, `startup.py` `build_candidates` yields CLI, ENV, CHOSEN, KICAD only. A start with nothing usable opens the setup window (help text states this). A remembered folder that fails, with KiCad's folder usable, logs the "Using KiCad's folder instead" note. These are the intended experiences.
- Verified: `README.md` line 47 gives the same four-source order, consistent with the help dialog.
- Finding (WARNING): silent default in `main_window.py:319` (see Fix 2). The default creates a path where the row can mislabel the origin; no test-visible symptom, but the row is the only place the user learns where the folder came from.
- Finding (INFO): an owner whose checkout was itself a collection, and who relied on the old fallback, now gets the setup window on first start after the change. The User Guide explains the order, but there is no one-line notice in the log at that moment. Consider one log line when the start falls through to the setup window, naming that the app no longer uses its own folder.
- Finding (INFO): the first-run window appearing where the app used to start silently is a behaviour change the owner should expect; this is intended (SPLIT-08) and is documented.

---

## Files Audited

- `.planning/phases/16-repo-split/16-02-SUMMARY.md`
- `.planning/phases/16-repo-split/16-02-PLAN.md`
- `.planning/phases/16-repo-split/16-07-SUMMARY.md`
- `.planning/phases/16-repo-split/16-CONTEXT.md`
- `kicad_lib_manager/widgets/help_dialog.py` (Library Folder section, lines ~110-160)
- `kicad_lib_manager/main_window.py` (MainWindow.__init__ line ~319, `_show_root`, `_refresh_root_tag` ~lines 815-838)
- `kicad_lib_manager/collection.py` (`Source` lines ~91-96, `_chosen_note` ~255-270, `resolve_library_root` ~273-305)
- `kicad_lib_manager/startup.py` (`build_candidates` lines ~64-98)
- `README.md` (First run and folder order, lines ~23-47)
