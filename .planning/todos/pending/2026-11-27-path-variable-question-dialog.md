---
title: Replace the "Change KiCad path variables?" message box with a dialog that shows a Now / After table
created: 2026-11-27
source: owner during the 17-17 real-network check (confirmed the proposal below)
area: app
---

The question asked after a folder switch and after a catalog Add or Reinstall is a plain message box:
the paths wrap mid-word, the "separate from Install Part and Generate Tables" note comes before the
point, the buttons are Yes / No, and it never names the KiCad settings file it writes.

Owner-confirmed layout (2026-11-27), one dialog for both callers:

- Title `Change KiCad path variables?`; bold lead `Point KiCad at this library folder?` with the folder in Mono under it.
- Table Variable | Now | After, one row per variable that would change (a catalog variable such as
  SPARKFUN_KICAD_LIBRARY gets its own row; an unset one reads `not set` under Now). Paths elided in the
  middle, never wrapped, full path in the tooltip.
- Consequence line: `After KiCad restarts, all your KiCad projects use the libraries in this folder.`
- Grey lines: `KiCad settings file: <path to kicad_common.json>`, then `Not needed for Install Part or
  Generate Tables; your answer does not undo anything they did.`
- Buttons `Keep Current Variables` (default, Esc) and `Change Variables` (must be clicked).
- Keep the existing log lines, the "will offer the change again" behaviour on a No, and the catalog's
  finishing state (`_catalog_finish_after_vars`).

The owner will not re-test this by hand: cover it with offscreen tests (button roles and default, Esc,
rows for folder and catalog variables, `not set`, the settings-file line, elided paths) and update the
User Guide and CLAUDE.md wording. Do it after Phase 17 (quick task), before Phase 19's menu regroup.
