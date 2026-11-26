---
phase: 16
review: 16-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "The history scan never inspects annotated tag objects"
  - id: CR-02
    severity: critical
    disposition: open
    title: "An email or drive-letter path right after a JSON escape sequence is invisible to the scan"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Owner-specific rules switch off silently, and CI never has them"
  - id: WR-02
    severity: warning
    disposition: open
    title: "History walk decides the vendor-file check from one path per blob"
  - id: WR-03
    severity: warning
    disposition: open
    title: "The commit-msg hook is weaker than the scan that will later reject the history"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Text rules are skipped for any blob with a NUL in its first 8 KiB, for UTF-16 without a BOM, and for other encodings"
  - id: WR-05
    severity: warning
    disposition: open
    title: "File names, folder names and ref names are not run through the text rules"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Vendor-file detection is by suffix and two magic prefixes only"
  - id: WR-07
    severity: warning
    disposition: open
    title: "Workstation-path patterns miss WSL, URL-encoded and UNC spellings"
  - id: WR-08
    severity: warning
    disposition: open
    title: "`cutover_collection.py` reads its templates from inside the folder it is about to delete"
  - id: WR-09
    severity: warning
    disposition: open
    title: "The cutover never checks the safety net its messages promise"
  - id: WR-10
    severity: warning
    disposition: open
    title: "`sync_planning.py` overwrites uncommitted work in the tool checkout and cannot see conflicts"
  - id: WR-11
    severity: warning
    disposition: open
    title: "`build_tool_repo.py` writes any `--email` into the first public commit"
  - id: WR-12
    severity: warning
    disposition: open
    title: "`test_compare_reports_differences` assertions are satisfied by any diff line (reviewer B)"
  - id: WR-13
    severity: warning
    disposition: open
    title: "Every behavioural test of the publishing controls is `slow`, so CI never runs it (reviewer B)"
  - id: WR-14
    severity: warning
    disposition: open
    title: "The scan's history walk is never tested on a blob that left the tree (reviewer B)"
  - id: WR-15
    severity: warning
    disposition: open
    title: "The corpus audit can be bypassed by common spellings, and its mark check is per module (reviewer B)"
  - id: WR-16
    severity: warning
    disposition: open
    title: "The allow-list tests would not notice private local files being admitted (reviewer B)"
  - id: WR-17
    severity: warning
    disposition: open
    title: "`test_a_raising_callback_does_not_stop_the_next_delivery` can still deliver `first` before the poll timer is stopped (reviewer C)"
  - id: WR-18
    severity: warning
    disposition: open
    title: "Two off-thread waits kept a 250 ms and a 1 s budget while their siblings went to 30 s (reviewer C)"
  - id: WR-19
    severity: warning
    disposition: open
    title: "Further small waits left in the same modules that the fix commits otherwise raised (reviewer C)"
  - id: WR-20
    severity: warning
    disposition: open
    title: "Worker hold gates of 5 s are now shorter than the 30 s waits placed before the assertions that rely on the held state (reviewer C)"
  - id: IN-01
    severity: info
    disposition: open
    title: "`uri_diff.py` resolves variables with the process environment as the lowest priority"
  - id: IN-02
    severity: info
    disposition: open
    title: "`tests/zipfixtures.py` builds the sample zip into the shared system temp at import time"
  - id: IN-03
    severity: info
    disposition: open
    title: "`str.splitlines()` shifts reported line numbers"
  - id: IN-04
    severity: info
    disposition: open
    title: "`build_tool_repo.py` cleanup swallows its own failures and the scrub covers only `.planning`"
  - id: IN-05
    severity: info
    disposition: open
    title: "`--min-passed 3500` is a bare constant in CI"
  - id: IN-06
    severity: info
    disposition: open
    title: "`test_markers.py` cannot be collected on Python 3.10 (reviewer B)"
  - id: IN-07
    severity: info
    disposition: open
    title: "Dead loop in `test_read_only_git_allow_list_is_exact` (reviewer B)"
  - id: IN-08
    severity: info
    disposition: open
    title: "`test_ci_workflow.py` checks match comments and any step (reviewer B)"
  - id: IN-09
    severity: info
    disposition: open
    title: "`test_owner_choice_is_remembered_after_close_escape_and_parent_deleted` fixed the Escape branch but not the Close-button branch (reviewer C)"
  - id: IN-10
    severity: info
    disposition: open
    title: "Debounce tests assert \"nothing started yet\" after a 100 ms wall-clock wait against a 300 ms debounce (reviewer C)"
open: 32
total: 32
recorded: 2026-11-26T11:15:31.153Z
---

# Phase 16: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| CR-02 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| WR-07 | warning | open | - |
| WR-08 | warning | open | - |
| WR-09 | warning | open | - |
| WR-10 | warning | open | - |
| WR-11 | warning | open | - |
| WR-12 | warning | open | - |
| WR-13 | warning | open | - |
| WR-14 | warning | open | - |
| WR-15 | warning | open | - |
| WR-16 | warning | open | - |
| WR-17 | warning | open | - |
| WR-18 | warning | open | - |
| WR-19 | warning | open | - |
| WR-20 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |
| IN-09 | info | open | - |
| IN-10 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
