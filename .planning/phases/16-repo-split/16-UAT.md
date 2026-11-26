---
status: testing
phase: 16-repo-split
source: [16-VERIFICATION.md]
started: 2026-11-26T11:40:00Z
updated: 2026-11-26T11:40:00Z
---

## Current Test

number: 1
name: KiCad still shows the same libraries when the app runs from the tool checkout
expected: |
  The Library folder row shows the main checkout of the collection with the tag `KiCad's folder` or `your choice`; the scan lists the Custom and WurthElektronik libraries; KiCad's Symbol and Footprint library managers list the same libraries as before the split and none is marked missing.
awaiting: user response

## Tests

### 1. KiCad still shows the same libraries when the app runs from the tool checkout
expected: Start the Library Manager from the tool checkout (`.\env\Scripts\python.exe kicad_lib_manager.py`, with the owner's real settings), then open KiCad's Symbol and Footprint library managers. The Library folder row shows the main checkout of the collection with the tag `KiCad's folder` or `your choice`; the scan lists the Custom and WurthElektronik libraries; KiCad lists the same libraries as before the split and none is marked missing.
result: [pending]

### 2. The local history scans clean before the next push
expected: The unpushed local commit 917e3ec (blob of `.planning/phases/16-repo-split/16-15-SUMMARY.md` with workstation paths, scrubbed later in c5b3a8e) is rewritten out of the unpushed history, for example by folding c5b3a8e into 917e3ec; then `python scripts/prepublish_scan.py --tree --history` exits 0 on the local repository, so the pre-push hook lets the unpushed documentation commits through.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
