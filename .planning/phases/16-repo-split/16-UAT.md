---
status: complete
phase: 16-repo-split
source: [16-VERIFICATION.md]
started: 2026-11-26T11:40:00Z
updated: 2026-11-26T16:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. KiCad still shows the same libraries when the app runs from the tool checkout
expected: Start the Library Manager from the tool checkout (`.\env\Scripts\python.exe kicad_lib_manager.py`, with the owner's real settings), then open KiCad's Symbol and Footprint library managers. The Library folder row shows the main checkout of the collection with the tag `KiCad's folder` or `your choice`; the scan lists the Custom and WurthElektronik libraries; KiCad lists the same libraries as before the split and none is marked missing.
result: pass
evidence: Owner's screenshots 2026-11-26. App: Library folder is the main checkout with the tag `KiCad's folder`, no amber tag; 10 `Atomic_` symbol libraries and `Atomic_Footprints` under Custom, WurthElektronik listed, all OK; log `Found 412 symbol libraries, 44 footprint libraries`, `Atomic check: all 21 symbols pass`, `No warnings.` KiCad: the USBlitz project symbol table lists the 10 `Atomic_` libraries via `${KICAD_LIB_GITHUB}` (= the main checkout); every uri in the project `sym-lib-table` (10) and `fp-lib-table` (1, `Atomic_Footprints.pretty`) resolves to an existing path.

### 2. The local history scans clean before the next push
expected: The unpushed local commit 917e3ec (blob of `.planning/phases/16-repo-split/16-15-SUMMARY.md` with workstation paths, scrubbed later in c5b3a8e) is rewritten out of the unpushed history, for example by folding c5b3a8e into 917e3ec; then `python scripts/prepublish_scan.py --tree --history` exits 0 on the local repository, so the pre-push hook lets the unpushed documentation commits through.
result: pass
evidence: Owner approved the rewrite 2026-11-26. `git filter-branch --prune-empty --index-filter` over `origin/main..main` replaced the dirty blob c1fdde7 of `16-15-SUMMARY.md` with the scrubbed blob a5506eb (from c5b3a8e) in 917e3ec and the merge 8ecf685; c5b3a8e became empty and was pruned (20 unpushed commits -> 19, merges kept, messages unchanged). The final tree equals the tree before the rewrite; the dirty blob is no longer reachable from `main`. The old branch is kept as a git bundle in the split backup folder (`kicad-lib-manager-pre-rewrite-2026-11-26.bundle`, verified) and the `refs/original` backup ref was deleted. `prepublish_scan.py --tree --history` then printed `prepublish_scan: clean (424 files, 463 blobs, 24 commits)`, exit 0. Nothing was pushed.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
