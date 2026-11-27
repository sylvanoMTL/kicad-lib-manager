---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 0
total_count: 2
last_updated: 2026-11-27T10:53:40.541Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 17 | stub | kicad_lib_manager/widgets/catalog_dialog.py | 382 | Add by URL... button has no action yet (plan 17-13 attaches the Add by URL page) | open |  | 2026-11-27T10:53:39.885Z |  |
| 2 | 17 | stub | kicad_lib_manager/widgets/catalog_dialog.py | 1247 | is_job_running and holds_download answer False until plan 17-13 adds the catalog jobs | open |  | 2026-11-27T10:53:40.541Z |  |

````json
[
  {
    "id": 1,
    "kind": "stub",
    "phase": "17",
    "file": "kicad_lib_manager/widgets/catalog_dialog.py",
    "line": 382,
    "description": "Add by URL... button has no action yet (plan 17-13 attaches the Add by URL page)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-27T10:53:39.885Z",
    "resolved_at": null,
    "milestone": "v3.0"
  },
  {
    "id": 2,
    "kind": "stub",
    "phase": "17",
    "file": "kicad_lib_manager/widgets/catalog_dialog.py",
    "line": 1247,
    "description": "is_job_running and holds_download answer False until plan 17-13 adds the catalog jobs",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-27T10:53:40.541Z",
    "resolved_at": null,
    "milestone": "v3.0"
  }
]
````
