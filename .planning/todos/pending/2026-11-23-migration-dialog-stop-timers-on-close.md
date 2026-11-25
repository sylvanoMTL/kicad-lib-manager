---
title: Stop the migration dialog's draft and rebuild timers when it closes
created: 2026-11-23
source: Phase 14 debug session (.planning/debug/resolved/xdist-worker-native-crash.md)
area: app
---

`MigrationDialog` (kicad_lib_manager/widgets/migration_dialog.py) never stops `_draft_timer`
(800 ms) or `_rebuild_timer` (300 ms) on close, and `is_busy()`/`done()` only look at running
workers; `ImportDialog._shutdown()` does stop its timers. In the tests this let a closed dialog
start a TaskWorker that its deferred delete then destroyed while running (Qt fatal
"QThread: Destroyed while thread is still running"); the test harness was fixed in dd5f5fb.

Not observed in the app, but the same pattern is possible: MainWindow deleteLater()s the dialog
from its finished handler, and a timer due in that event-loop pass could start a worker that the
delete then destroys.

Suggested fix: stop both timers when the window really closes (in `done()` before
`super().done(r)`, and in the delayed close in `_reap`); if a draft save is pending, run it as a
worker and let the existing "close waits without blocking" path delay the close so the last edit
is kept (D-14). Add a test that closes the dialog with a pending timer and checks no worker starts.
