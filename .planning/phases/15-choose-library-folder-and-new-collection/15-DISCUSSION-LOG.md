# Phase 15: Choose Library Folder and New Collection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-23
**Phase:** 15-choose-library-folder-and-new-collection
**Areas discussed:** What counts as a collection, Showing the folder, First run, KiCad path variables, New collection location

---

## What counts as a collection

| Option | Description | Selected |
|--------|-------------|----------|
| Needs Custom/ (Recommended) | A folder with `Custom/` (Symbols/ or Footprints/); an empty folder is offered "Create a new collection here"; any other folder is refused with the reason | ✓ |
| Any folder, warn | Accept any existing, writable folder; warn when `Custom/` is missing | |
| Needs a git repo | Also require `Custom/` to be a git work tree | |

**User's choice:** Needs Custom/ (Recommended)

---

## Showing the folder

| Option | Description | Selected |
|--------|-------------|----------|
| Window title | Path in the title bar; no space used, long paths cut off | |
| Line above the lists | "Library folder: C:/..." above the lists with a change button | |
| Status bar | Permanent label bottom right | |
| You decide | Claude picks during planning | ✓ |

**User's choice:** You decide

---

## First run

| Option | Description | Selected |
|--------|-------------|----------|
| App closes | Nothing to work on; the window returns next start | |
| Empty main window | Main window with a Choose library folder prompt instead of the lists | |
| You decide | Claude picks during planning | ✓ |

**User's choice:** You decide

---

## KiCad path variables

| Option | Description | Selected |
|--------|-------------|----------|
| Right after switch | Ask straight after switching to a folder KiCad doesn't point at | |
| At Generate/Install | Keep today's timing | |
| You decide | Claude picks during planning | ✓ |

**User's choice:** You decide

---

## New collection location

| Option | Description | Selected |
|--------|-------------|----------|
| Pick a parent + name | Parent folder plus a typed name; the app makes the folder | |
| Pick an empty folder | Standard folder dialog; a non-empty pick is refused | |
| You decide | Claude picks during planning | ✓ |

**User's choice:** You decide

---

## Claude's Discretion

- Showing the folder: proposal "Library folder: <path>" line above the lists plus the folder name in the window title.
- First run closed without a choice: proposal the app closes.
- KiCad path variables: proposal offer right after the switch, Generate/Install keep offering while it differs.
- New collection location: proposal parent folder plus name; an empty folder chosen in Choose library folder... is offered to become the collection.

## Decided autonomously

[auto] [Resolve order] — Q: "How the override, the chosen folder and KiCad's folder rank" → Selected: "--library-root over KICAD_LIBMGR_ROOT over remembered folder over KICAD_LIB_GITHUB over first-run window (D3)" (reversible technical — decided autonomously: one resolve function)
[auto] [Settings] — Q: "Where the choice is stored" → Selected: "QSettings library/root and library/recent (max 10) via settings.py" (reversible technical — decided autonomously: helpers can read an old key)
[auto] [Deleted folder] — Q: "A remembered folder that no longer exists" → Selected: "skipped with a log line, next choice used, Recent lists only existing folders" (reversible technical — decided autonomously: local rule)
[auto] [Path length] — Q: "Long folder paths" → Selected: "warning over about 100 characters, not a refusal" (reversible technical — decided autonomously: one constant)
[auto] [Wrong-folder rule] — Q: "What the D-26 check compares" → Selected: "resolved library folder vs KICAD_LIB_GITHUB; Run/Pin refuse, Generate/Install warn" (reversible technical — decided autonomously: the check takes a path argument)
[auto] [Dev worktree] — Q: "Running from the importer worktree" → Selected: "resolves like any start; dev and UAT use the override; legacy in-repo fallback until Phase 16" (reversible technical — decided autonomously: follows from D3)
[auto] [New collection files] — Q: "Where .gitignore and README go" → Selected: "inside Custom/, .gitkeep in empty folders, no automatic commit" (reversible technical — decided autonomously: plain files)
[auto] [Menus] — Q: "Where the new actions live" → Selected: "File menu: Choose library folder..., Use KiCad's folder, Recent library folders, Open library folder in Explorer" (reversible technical — decided autonomously: menu wiring)
[auto] [Open in Explorer] — Q: "How the folder is opened" → Selected: "QDesktopServices.openUrl" (reversible technical — decided autonomously: one call)
[auto] [Dialog modality] — Q: "Blocking or not" → Selected: "first-run window app-modal at startup only; later dialogs window-modal or non-blocking" (reversible technical — decided autonomously: a dialog flag)

## Deferred Ideas

- Removing the legacy in-repo fallback (Phase 16), clone location and catalog.json (Phase 17), project-local tables (Phase 18), menu regroup (Phase 19).
