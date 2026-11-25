---
phase: 14
review: 14-REVIEW.md
fix_report: 14-REVIEW-FIX.md
total: 9
open: 0
fixed: 4
deferred: 5
---

# Phase 14 review disposition

| ID | Severity | Disposition | Source |
|----|----------|-------------|--------|
| WR-01 | warning | fixed | 0877972 (14-REVIEW-FIX.md) |
| WR-02 | warning | fixed | 7ba3f27 (14-REVIEW-FIX.md) |
| WR-03 | warning | fixed | d2f430f (14-REVIEW-FIX.md) |
| WR-04 | warning | fixed | 28457e6 (14-REVIEW-FIX.md) |
| IN-01 | info | deferred | template .gitmodules URL names the shared remote; nothing syncs it today - revisit if a test runs submodule sync/update on a copy |
| IN-02 | info | deferred | measure.py _rc maps pytest exit 1 to 0 in one helper; verdicts use the recorded exit codes, checked against results.jsonl by the reviewer |
| IN-03 | info | deferred | _join_widget_threads ignores QThread.wait(60000) result; a 60 s hang would already fail by the 300 s timeout path - harness hardening candidate |
| IN-04 | info | deferred | meta-test elapsed < 30 s / 2 s timeout flake risk; 0 failures across 14 quick and 26 full parallel runs this phase |
| IN-05 | info | deferred | app-state guard message could hint to rerun when the owner used the GUI during a run; documentation polish |
