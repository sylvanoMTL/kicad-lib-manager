---
phase: 15
review: 15-REVIEW.md
fix_report: 15-REVIEW-FIX.md
total: 20
open: 0
fixed: 15
deferred: 5
---

# Phase 15 review disposition

| ID | Severity | Disposition | Source |
|----|----------|-------------|--------|
| CR-01 | critical | fixed | 9fcbb80 (15-REVIEW-FIX.md) |
| CR-02 | critical | fixed | 8e09959 (15-REVIEW-FIX.md) |
| WR-01 | warning | fixed | 05cea7d (15-REVIEW-FIX.md) |
| WR-02 | warning | fixed | b075e8d (15-REVIEW-FIX.md) |
| WR-03 | warning | fixed | 3d65576 (15-REVIEW-FIX.md) |
| WR-04 | warning | fixed | 98bd872 (15-REVIEW-FIX.md) |
| WR-05 | warning | fixed | bf8a826 (15-REVIEW-FIX.md) |
| WR-06 | warning | fixed | 03449f0 (15-REVIEW-FIX.md) |
| WR-07 | warning | fixed | 2bd1b88 (15-REVIEW-FIX.md) |
| IN-02 | info | fixed | 04a85b2 (15-REVIEW-FIX.md) |
| IN-01 | info | deferred | help text omits Check Atomic Parts as a busy state; help copy follows the UI-SPEC - candidate for the Phase 19 menu/help pass |
| IN-03 | info | deferred | the "only procs starts a process" AST guard can be bypassed by import aliases or QProcess; hardening candidate, no bypass exists in the code today |
| WR-08 | warning | fixed | 358c5e4, 1d1bac6 (15-REVIEW-FIX.md pass 2) |
| WR-09 | warning | fixed | d169f71 (15-REVIEW-FIX.md pass 2) |
| WR-10 | warning | fixed | 92260e8 (15-REVIEW-FIX.md pass 2) |
| IN-04 | info | fixed | 91a189d (15-REVIEW-FIX.md pass 2) |
| IN-05 | info | deferred | fit_height_to_content never clamps to the screen; native 175% UAT shows all dialogs fit on 1920x1080 |
| IN-06 | info | deferred | run_in_background's GUI-thread-only contract is documented, not enforced; all callers are GUI-thread code |
| IN-07 | info | deferred | brittle TaskWorker( call-count guard in test_exit_with_hung_check.py; acceptable until main_window's remaining TaskWorkers move to the runner |
| UAT-COS-01 | cosmetic | fixed | 13c5503 (unset-variable log wording; new copy, owner to confirm at sign-off) |
