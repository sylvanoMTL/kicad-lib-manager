---
phase: 17-library-catalog
plan: 17
subsystem: verification
tags: [owner-check, real-network, library-catalog, d-22, cat-09]

requires:
  - phase: 17-library-catalog
    provides: the catalog window, its flows and the main-window follow-up (plans 17-11 to 17-16)
provides:
  - the owner-run D-22 results for SparkFun, 4ms, Alternate-KiCad-Library and Espressif
  - the owner-run Cancel and real-update checks (offline and private-address checks skipped by the owner)
  - decision D-33 (the catalog lists KiCad's official add-on index libraries by their git links) and the findings list for the fix plan before 17-18
affects: [17-18, 17-19, 17-20]

actuals:
  tasks: 2
  commits: 6

key-files:
  created:
    - .planning/todos/pending/2026-11-27-path-variable-question-dialog.md
  modified:
    - kicad_lib_manager/widgets/catalog_pages.py
    - kicad_lib_manager/catalog/curated.py
    - kicad_lib_manager/catalog/ops.py
    - kicad_lib_manager/widgets/help_dialog.py
    - scripts/prepublish_scan.py
    - .planning/phases/17-library-catalog/17-CONTEXT.md
    - .planning/phases/17-library-catalog/17-UI-SPEC.md
    - CLAUDE.md

key-decisions:
  - "D-33 (owner): the catalog reads KiCad's official add-on index live and clones each library's git repository named in its Resources; KiCad's review counts as the D-22 check; it never touches what KiCad's own manager installed"
  - "Index libraries go into the library tables under KiCad's add-on nickname convention (PCM_ prefix), because packages link each other that way (Espressif's and 4ms's symbols link PCM_Espressif)"
  - "The path-variable question becomes a dialog with a Now / After table and named buttons (owner-confirmed design, todo for after Phase 17)"

requirements-completed: []
---

# 17-17: Owner real-network check of the library catalog

The owner ran the catalog for real in a scratch collection with a scratch copy of KiCad's settings
(`$env:APPDATA` pointed at the scratch folder). The real KiCad settings file and the main checkout were not
written: the real `kicad_common.json` kept its earlier date and only the scratch copy changed. The scratch
folder was deleted afterwards.

## D-22 results

| Library | Way in | Result | Symbol / footprint libraries | 3D models | Other numbers and notes |
|---------|--------|--------|------------------------------|-----------|-------------------------|
| SparkFun | curated list | **pass** | 30 / 21 (as expected) | 6 not found (as expected); 2 on KiCad's own path variables | path variable question set `SPARKFUN_KICAD_LIBRARY`; SparkFun-Camera links a footprint library `lcd-tft` SparkFun does not ship (upstream data); removed cleanly (folder and record gone) |
| 4ms | Add by URL | **pass** | 25 / 29 (as expected) | 0 not found; 266 on KiCad's own path variables (stock models) | 325 MB on disk; `KICAD_4MS_LIBS` set; `4ms_IC` links `PCM_Espressif` (a KiCad add-on library, upstream); removed cleanly |
| Alternate-KiCad-Library | Add by URL | **works, with a caveat** | 39 / 63 (as expected) | about 6,900 footprints point their 3D models at a fixed `C:/Program Files/KiCad/5.99/...` folder | licence "not stated by the repository" on GitHub (KiCad's index gives CC-BY-SA); download and check under about 3.5 min; the main window's read took about 2 min 40 s with no sign of work |
| Espressif | Add by URL | **fail, as recorded** | 1 / 1 | 45 on the KiCad add-on manager's own variables | every symbol links its footprint as `PCM_Espressif:...`, so all 51 show Missing FP; the owner added it to see the result, then removed it |

Download times and SparkFun's size on disk were not measured.

## Safety checks

| Check | Result |
|-------|--------|
| Cancel during a real download | **pass**: log `Stopped adding SparkFun. Nothing was added.`; no git process left; `ThirdParty/.staging` empty; the record unchanged |
| Real update | **pass**: SparkFun made one commit older (the orchestrator ran the fetch and reset in the scratch copy for the owner); the start check showed `Library Catalog... (1 update)`; Update Library brought the copy and the record to the newest commit; the menu went back to plain text |
| Offline start | skipped by the owner |
| Private address | skipped by the owner |

## Fixed during the check

- `00881f3`: the review pages kept their buttons below the rows in a short pane (the amber Git line takes room): the page text now scrolls on its own and the button row stays in view. Regression test reproduces the owner's window.
- `70bf975`, `81177e5`: the licence page says what happens next ("Step 1 of 2 ... Nothing is added yet: on the next page you choose Add Library or Discard Download"), has a **Read the licence** link to the licence itself (Würth's PDF, SparkFun's README section, 4ms's UNLICENSE; the repository page otherwise) with the tick under it, and shows the size on the button (`Download and Check (about 69 MB)`). Owner-approved; UI-SPEC, User Guide and CLAUDE.md updated.
- `cccefb7`: the pre-publish scan treats addresses on the reserved `.example` / `.invalid` names as never real (a 17-07 test URL blocked the push).

## Findings for the fix plan (before 17-18)

1. **Progress while checking a download** (owner request): a progress bar with a file count in the job bar (`Checking Alternate KiCad Library... 38% (4,210 of 11,050 files)`).
2. **Refreshing state in the main window** (owner design): after a catalog Add, Remove or Update, a large spinning wheel over both library lists with "Refreshing the library list after adding {name}. Large libraries can take a minute.", a progress bar and a file count; the lists and Generate Tables disabled until it ends.
3. **Log flood**: per-file 3D model and footprint warnings (thousands for Alternate, 51 for Espressif) become one summary line per library with the first few examples.
4. **Size "Unknown"** in the list for an installed library added by web address, while the Remove page knows its size on disk.
5. **Remove page count** "Libraries that leave your scan (43)" merges symbol and footprint libraries that share a name; say "25 symbol and 29 footprint libraries".
6. **Name of a library added by web address**: `4ms-4ms-kicad-lib` in the trees and some log lines, `4ms/4ms-kicad-lib` in others.
7. **D-33**: the catalog lists KiCad's official add-on index (17 libraries today), takes name, description and licence from it (Alternate's CC-BY-SA), clones the Resources git link, and uses the `PCM_` nickname convention so links between packages resolve.
8. The `$env:APPDATA` setup of this plan does not isolate the app's own settings (Qt asks Windows for the folder) or its backups (`AppData\Local`): the real app settings remembered the scratch collection, and two backups of the scratch KiCad settings landed among the real ones (deleted with the owner's yes). A later owner check needs a real isolation switch, or the steps must say so.

Also noted: the path-variable question names the collection folder in its consequence line even for a catalog variable (added to the dialog todo), and the Generate Tables tooltip names the table files (for Phase 19).

## Self-Check: PASSED

- D-22 results table: one row per library with pass or fail, reason and numbers (download times not measured).
- Safety results: Cancel and update recorded; offline and private address recorded as skipped by the owner.
- No workstation path, user name or private address in this file.
