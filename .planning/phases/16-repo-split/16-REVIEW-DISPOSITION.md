---
phase: 16
review: 16-REVIEW.md
titles: json
findings:
  - id: WR-21
    severity: warning
    disposition: fixed
    title: "A placeholder user folder is matched by its first word only, so a real profile folder that starts with a placeholder name is treated as a sample"
  - id: WR-22
    severity: warning
    disposition: fixed
    title: "The planning-sync conflict check reports false conflicts: on a second sync with the same `--since` and on any checkout that converts line endings"
  - id: WR-23
    severity: warning
    disposition: fixed
    title: "The cutover's safety-net check accepts a branch name and never looks at the bundle"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "`uri_diff.py` resolves variables with the process environment as the lowest priority"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "`tests/zipfixtures.py` builds the sample zip into the shared system temp at import time"
  - id: IN-03
    severity: info
    disposition: fixed
    title: "`str.splitlines()` shifts reported line numbers"
  - id: IN-04
    severity: info
    disposition: fixed
    title: "`build_tool_repo.py` cleanup swallows its own failures and the scrub covers only `.planning`"
  - id: IN-05
    severity: info
    disposition: fixed
    title: "`--min-passed 3500` is a bare constant in CI"
  - id: IN-06
    severity: info
    disposition: fixed
    title: "`test_markers.py` cannot be collected on Python 3.10"
  - id: IN-07
    severity: info
    disposition: fixed
    title: "Dead loop in `test_read_only_git_allow_list_is_exact`"
  - id: IN-08
    severity: info
    disposition: fixed
    title: "`test_ci_workflow.py` checks match comments and any step"
  - id: IN-09
    severity: info
    disposition: fixed
    title: "`test_owner_choice_is_remembered_after_close_escape_and_parent_deleted` fixed the Escape branch but not the Close-button branch"
  - id: IN-10
    severity: info
    disposition: fixed
    title: "Debounce tests assert \"nothing started yet\" after a 100 ms wall-clock wait against a 300 ms debounce"
  - id: IN-11
    severity: info
    disposition: fixed
    title: "`_decode` reads UTF-32 big-endian without a byte order mark as garbage, so its text is not scanned"
  - id: IN-12
    severity: info
    disposition: fixed
    title: "A JSON-escaped UNC path and other JSON escapes still hide a path or an address"
  - id: IN-13
    severity: info
    disposition: fixed
    title: "Annotated tags with an empty tagger address skip the identity check, and the name in the tag header is never read"
  - id: IN-14
    severity: info
    disposition: fixed
    title: "Formatting slip in the marker pattern definition"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "The history scan never inspects annotated tag objects"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "An email or drive-letter path right after a JSON escape sequence is invisible to the scan"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Owner-specific rules switch off silently, and CI never has them"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "History walk decides the vendor-file check from one path per blob"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "The commit-msg hook is weaker than the scan that will later reject the history"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "Text rules are skipped for any blob with a NUL in its first 8 KiB, for UTF-16 without a BOM, and for other encodings"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "File names, folder names and ref names are not run through the text rules"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "Vendor-file detection is by suffix and two magic prefixes only"
  - id: WR-07
    severity: warning
    disposition: fixed
    title: "Workstation-path patterns miss WSL, URL-encoded and UNC spellings"
  - id: WR-08
    severity: warning
    disposition: fixed
    title: "`cutover_collection.py` reads its templates from inside the folder it is about to delete"
  - id: WR-09
    severity: warning
    disposition: fixed
    title: "The cutover never checks the safety net its messages promise"
  - id: WR-10
    severity: warning
    disposition: fixed
    title: "`sync_planning.py` overwrites uncommitted work in the tool checkout and cannot see conflicts"
  - id: WR-11
    severity: warning
    disposition: fixed
    title: "`build_tool_repo.py` writes any `--email` into the first public commit"
  - id: WR-12
    severity: warning
    disposition: fixed
    title: "`test_compare_reports_differences` assertions are satisfied by any diff line (reviewer B)"
  - id: WR-13
    severity: warning
    disposition: fixed
    title: "Every behavioural test of the publishing controls is `slow`, so CI never runs it (reviewer B)"
  - id: WR-14
    severity: warning
    disposition: fixed
    title: "The scan's history walk is never tested on a blob that left the tree (reviewer B)"
  - id: WR-15
    severity: warning
    disposition: fixed
    title: "The corpus audit can be bypassed by common spellings, and its mark check is per module (reviewer B)"
  - id: WR-16
    severity: warning
    disposition: fixed
    title: "The allow-list tests would not notice private local files being admitted (reviewer B)"
  - id: WR-17
    severity: warning
    disposition: fixed
    title: "`test_a_raising_callback_does_not_stop_the_next_delivery` can still deliver `first` before the poll timer is stopped (reviewer C)"
  - id: WR-18
    severity: warning
    disposition: fixed
    title: "Two off-thread waits kept a 250 ms and a 1 s budget while their siblings went to 30 s (reviewer C)"
  - id: WR-19
    severity: warning
    disposition: fixed
    title: "Further small waits left in the same modules that the fix commits otherwise raised (reviewer C)"
  - id: WR-20
    severity: warning
    disposition: fixed
    title: "Worker hold gates of 5 s are now shorter than the 30 s waits placed before the assertions that rely on the held state (reviewer C)"
open: 0
total: 39
recorded: 2026-11-26T18:35:10.522Z
---

# Phase 16: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-21 | warning | fixed | 16-REVIEW-FIX.md |
| WR-22 | warning | fixed | 16-REVIEW-FIX.md |
| WR-23 | warning | fixed | 16-REVIEW-FIX.md |
| IN-01 | info | fixed | 16-REVIEW-FIX.md |
| IN-02 | info | fixed | 16-REVIEW-FIX.md |
| IN-03 | info | fixed | 16-REVIEW-FIX.md |
| IN-04 | info | fixed | 16-REVIEW-FIX.md |
| IN-05 | info | fixed | 16-REVIEW-FIX.md |
| IN-06 | info | fixed | 16-REVIEW-FIX.md |
| IN-07 | info | fixed | 16-REVIEW-FIX.md |
| IN-08 | info | fixed | 16-REVIEW-FIX.md |
| IN-09 | info | fixed | 16-REVIEW-FIX.md |
| IN-10 | info | fixed | 16-REVIEW-FIX.md |
| IN-11 | info | fixed | 16-REVIEW-FIX.md |
| IN-12 | info | fixed | 16-REVIEW-FIX.md |
| IN-13 | info | fixed | 16-REVIEW-FIX.md |
| IN-14 | info | fixed | 16-REVIEW-FIX.md |
| CR-01 | critical | fixed | 16-REVIEW-FIX.md (not in the current review) |
| CR-02 | critical | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-01 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-02 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-03 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-04 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-05 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-06 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-07 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-08 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-09 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-10 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-11 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-12 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-13 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-14 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-15 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-16 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-17 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-18 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-19 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |
| WR-20 | warning | fixed | 16-REVIEW-FIX.md (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
