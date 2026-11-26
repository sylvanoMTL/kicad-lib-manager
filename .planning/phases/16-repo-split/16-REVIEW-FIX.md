---
phase: 16-repo-split
fixed_at: 2026-11-26T14:30:00Z
review_path: .planning/phases/16-repo-split/16-REVIEW.md
iteration: 1
findings_in_scope: 22
fixed: 22
skipped: 0
status: all_fixed
---

# Phase 16: Code Review Fix Report

**Fixed at:** 2026-11-26
**Source review:** .planning/phases/16-repo-split/16-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 22 (CR-01, CR-02, WR-01 to WR-20; Info findings out of scope)
- Fixed: 22
- Skipped: 0

Where the fixes ran: in the main checkout of the tool repository on branch `main`, not in a separate git worktree
(the coordinator asked for commits in this clone and was waiting on this run). Every gate below ran in that checkout, so the
numbers can be reproduced from it. No file was pushed; nothing outside the findings was changed except one clean-up commit
(afdf90b) that restored the CRLF line endings two test files had lost while they were edited.

## Fixed Issues

### CR-01: The history scan never inspects annotated tag objects
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 272591e
**Applied fix:** New `history_tags` reads every annotated tag object the object walk lists (nested tags too), takes tagger name and
address and the message, and runs them through `scan_identity` and `scan_message` (reported as `tag:<id>`). Slow test with a tagger
address that is not a noreply address and a session line in the tag message; a lightweight tag and an allowed annotated tag stay clean.
Status: fixed: requires human verification (new walk logic; checked on throwaway repositories only).

### CR-02: An email or drive-letter path right after a JSON escape sequence is invisible to the scan
**Files modified:** `scripts/prepublish_scan.py`, `scripts/split/scrub.py`, `tests/test_prepublish_scan.py`, `tests/test_split_export.py`
**Commit:** c4c3457
**Applied fix:** `_line_hits` matches the path and email patterns on the original line and on a copy where the quoted line-break
escapes (backslash then n, r or t) are replaced by a space. `scrub.py` accepts the same escapes before a drive-letter or git-bash path
(and carries the WSL, URL-encoded and UNC spellings of WR-07). Tests cover all three escapes before an address, an owner address and
both path styles, and that an escape hiding nothing stays quiet.
Status: fixed: requires human verification (regex logic).
Consequence to know about: the widened rules now flag two lines of `16-REVIEW.md` itself, which quotes the review's own sample strings
(see the scan result below). That is the new rule working; it is not an active leak.

### WR-01: Owner-specific rules switch off silently, and CI never has them
**Files modified:** `scripts/prepublish_scan.py`, `.githooks/pre-push`, `.github/workflows/ci.yml`, `tests/test_prepublish_scan.py`, `tests/test_githooks.py`
**Commit:** a84d05a
**Applied fix:** The scan prints `prepublish_scan: no owner deny list in use ...` to stderr when neither deny source gives anything.
The pre-push hook refuses (exit 1) when `prepublish.denyTermsFile` is empty unless `PREPUBLISH_ALLOW_NO_DENY_LIST=1` is set. The CI
step carries a comment that owner terms are enforced by the hook only (the workflow text avoids the words the CI text test forbids).
Tests: the note, and the hook's refusal, opt-out and normal path.

### WR-02: History walk decides the vendor-file check from one path per blob
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 0da43ab
**Applied fix:** `blob_paths` collects every path a blob had from the raw log of all commits; `history_blobs` yields the other paths and
the scan judges each (`scan_alias`). Slow test: the same bytes under an exempt fixture name and a vendor name, the vendor name
deleted later; verified to fail without the fix.
Status: fixed: requires human verification.

### WR-03: The commit-msg hook is weaker than the scan that will later reject the history
**Files modified:** `.githooks/commit-msg`, `scripts/split/build_tool_repo.py`, `tests/test_githooks.py`, `tests/test_split_export.py`
**Commit:** 279c899
**Applied fix:** The hook uses `grep -v -i -E` with an optional-indent trailer pattern and the URL pattern; `clean_message` compares
case-insensitively. Tests run the hook on a message file with lower-case, indented, tabbed and upper-case variants.

### WR-04: Text rules are skipped for any blob with a NUL in its first 8 KiB, for UTF-16 without a BOM, and for other encodings
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 30ac20a
**Applied fix:** `_decode` always returns text: UTF-32 and UTF-16 with a BOM, UTF-16 and UTF-32 without one (by the share of NUL bytes),
and any other NUL-bearing data read like `strings` (NULs become line breaks). `scan_blob` no longer returns early on binary data.
This tree and history still scan with no new finding from binary files (see the scan result).
Status: fixed: requires human verification (a binary file now gets text rules; no false positive appeared on this repository).

### WR-05: File names, folder names and ref names are not run through the text rules
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 3dfed6b
**Applied fix:** `scan_blob`, `scan_alias` and `scan_ref(name, rules)` pass the path or ref name through the text rules and report the
same rule names with the path or `ref:<name>` as place. `scan_ref` keeps working without rules.

### WR-06: Vendor-file detection is by suffix and two magic prefixes only
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 6a00484
**Applied fix:** More suffixes (archives, STL, EAGLE, OrCAD, Altium families, spreadsheets, CSV) and magics (gzip, 7z, PDF, RAR).
Under `tests/fixtures/` only the two small text suffixes the fixtures use are exempt, and a magic hit is never exempt. Not done:
the optional idea of opening zip blobs and scanning their members (the review marked it optional); a fixture archive is now
flagged by name or magic instead of being skipped.

### WR-07: Workstation-path patterns miss WSL, URL-encoded and UNC spellings
**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py` (and `scripts/split/scrub.py`, done in the CR-02 commit)
**Commit:** 586c268 (scan side); scrub side in c4c3457
**Applied fix:** Three new patterns (WSL mount, URL-encoded drive colon, UNC share with a user folder) and the matching scrub rules.

### WR-08: `cutover_collection.py` reads its templates from inside the folder it is about to delete
**Files modified:** `scripts/split/cutover_collection.py`, `tests/test_cutover_collection.py`
**Commit:** 34d946d
**Applied fix:** `plan()` reads the three templates into memory and `apply` writes from those bytes; `plan()` refuses when the
templates folder lies inside the repository being cut over; a failed step prints the way back (`git reset -q` then `git checkout -- .`).
The script is a one-off kept for the record and was only run against throwaway repositories in tests.

### WR-09: The cutover never checks the safety net its messages promise
**Files modified:** `scripts/split/cutover_collection.py`, `tests/test_cutover_collection.py`
**Commit:** 02e47d0
**Applied fix:** `--pre-split-tag NAME` is required with `--apply` (exit 2 otherwise) and the tag must exist and name HEAD (checked in
the dry run too); a git timeout becomes a failed step instead of a traceback; failed steps print the way back (from WR-08). Not
possible to check from the script: that the new tool repository was pushed before the code leaves the collection; the docstring
now states it as a prerequisite.

### WR-10: `sync_planning.py` overwrites uncommitted work in the tool checkout and cannot see conflicts
**Files modified:** `scripts/split/sync_planning.py`, `tests/test_split_export.py`
**Commit:** 8c87748
**Applied fix:** Refuses (exit 2) when `.planning/` of the destination has uncommitted changes; a file whose destination copy no longer
matches the export of the `--since` tag is printed as `conflict <path>`, left alone, and the command exits 1. Slow test for both.
Status: fixed: requires human verification (the conflict rule assumes the same `--map` as the build).

### WR-11: `build_tool_repo.py` writes any `--email` into the first public commit
**Files modified:** `scripts/split/build_tool_repo.py`, `tests/test_split_export.py`
**Commit:** e7193e1
**Applied fix:** `build` refuses (exit 2) an email the scan's own `is_allowed_email` rejects unless `--allow-any-email` is given,
before anything is written; on success it prints a reminder to set `prepublish.denyTermsFile` in the new clone.

### WR-12: `test_compare_reports_differences` assertions are satisfied by any diff line
**Files modified:** `tests/test_uri_diff.py`
**Commit:** 0541570
**Applied fix:** The four checks name the entry: the full removed and added lines are asserted, and a helper lists the (kind, entry)
pairs of every difference line so a wrong entry cannot pass. The real output also reports the added, changed and gone entries as
missing or changed, so the expected sets include those and nothing else.

### WR-13: Every behavioural test of the publishing controls is `slow`, so CI never runs it
**Files modified:** `tests/test_githooks.py`, `tests/README.md`
**Commit:** 3f86cf1
**Applied fix:** The commit-msg hook tests now run the hook on a message file with no `git init`, so they are quick and run in CI
(one slow test keeps the hook wired through `core.hooksPath` and a real commit). For the git-bound tests the review's alternative was
taken: `tests/README.md` records that CI never runs them and lists the one `--full` command to run before every publish. A CI
`--full` step was not added: the CI text test forbids it, and it could not be checked from here.

### WR-14: The scan's history walk is never tested on a blob that left the tree
**Files modified:** `tests/test_prepublish_scan.py`
**Commit:** 2ceaa2c
**Applied fix:** Slow test: a planted path committed and removed (tree clean, history not), `--tree` alone, `--history` alone, `--path`,
`--deny-terms-file`, `prepublish.denyTermsFile` and `prepublish.denyEmailsFromRepo`, and a missing configured terms file exiting 2.

### WR-15: The corpus audit can be bypassed by common spellings, and its mark check is per module
**Files modified:** `tests/test_corpus_audit.py`, `tests/test_sexpr.py`
**Commit:** 8e1177a
**Applied fix:** Root names ending in ROOT or REPO, a path after the folder name, `os.path.join` and a bare `parent.parent` are found;
a skip reason held in a module constant is found; a new per-test audit (AST based: reader calls, module names that reach them, mark
aliases, parametrize marks, class and module marks) replaces trusting one mark per module. `test_tokenizer_matches_reference_parser`
no longer reads the live Custom files; they moved to a new `corpus`-marked test. Planted-case tests cover each new spelling.

### WR-16: The allow-list tests would not notice private local files being admitted
**Files modified:** `tests/test_split_export.py`
**Commit:** b957481
**Applied fix:** The owner-local files named by the review join the negative sample and the verify-export parametrization, and the
shipped-list check refuses entries that name `.claude`, `env`, `.env`, `.local.`, deny-terms or junit.

### WR-17: `test_a_raising_callback_does_not_stop_the_next_delivery` can still deliver `first` early
**Files modified:** `tests/test_background.py`
**Commit:** c41be07
**Applied fix:** The test waits on each task's own `_returned` event (no event loop turn, so the 15 ms poll timer cannot drain) and
stops the timer after the second start. Module run three times serially: 9 passed each time.

### WR-18: Two off-thread waits kept a 250 ms and a 1 s budget
**Files modified:** `tests/test_new_collection_dialog.py`, `tests/test_help_dialog.py`
**Commit:** 3afc64d
**Applied fix:** The "at once, not after the debounce" intent is asserted off the timer (`_debounce.interval() == 0` right after the
click) with the 30 s wait for the check; the help fold wait is 30 s. Both modules run three times serially: green.

### WR-19: Further small waits left in the same modules
**Files modified:** `tests/test_import_dialog.py`, `tests/test_new_collection_dialog.py`, `tests/test_choose_folder_dialog.py`, `tests/test_first_run_dialog.py`, `tests/test_main_window.py`
**Commit:** 3a400b6
**Applied fix:** Each listed wait now has `timeout=30000`. For the two `dialog.width()` waits the timeout was added to the existing
condition instead of switching to `resize_and_wait`, because that helper also waits for the height. A shared budget constant was not
introduced. The three small dialog modules ran three times serially: green.

### WR-20: Worker hold gates of 5 s are shorter than the 30 s waits placed before the assertions that rely on them
**Files modified:** `tests/test_main_window.py`, `tests/test_migration_dialog_run.py`
**Commit:** 527b585
**Applied fix:** The six listed gates are held for 60 s (the tests release them in `finally`). `test_main_window.py`,
`test_migration_dialog_run.py` and `test_import_dialog.py` ran with `--full -n 4`: 370 passed.

## Skipped Issues

None.

## Verification

All of it ran in the main checkout (no worktree).

- Quick suite (`python -m pytest`, run once at the end): **4037 passed, 3 skipped, 4 warnings in 99 s**, 42 corpus tests deselected
  (no corpus folder set). The 3 skips are the two Windows symlink-privilege skips and the real-KiCad-config opt-in; the skip budget is 10.
- Slow modules the fixes touch, run with `--full` while working: `test_prepublish_scan.py`, `test_githooks.py`,
  `test_cutover_collection.py`, `test_split_export.py`, `test_help_dialog.py`, `test_uri_diff.py`: all green;
  `test_import_dialog.py`, `test_main_window.py`, `test_migration_dialog_run.py` with `--full -n 4`: 370 passed.
- Pre-publish scan (`scripts/prepublish_scan.py --tree --history`, run once at the end): **exit 1, 2 findings**:
  `workstation_path` at `.planning/phases/16-repo-split/16-REVIEW.md:171` and `:215`. Both are the review's own quoted sample
  strings (a drive path after a JSON line-break escape, and a WSL-style path). They are caught because CR-02 and WR-07 widened the
  rules; they were clean before (425 files, 471 blobs, 27 commits). The file is committed (so it is in the tree and the history) and
  this fixer may not edit `.planning/` other than this report. **Action for the owner before the next push:** reword those two lines
  of `16-REVIEW.md` (describe the sample instead of quoting it) or append an inline allow marker for the `workstation_path` rule; the
  history cannot be left clean without that edit being committed first in a way the owner chooses (a new commit is enough for the tree
  scan, but the old blob stays in history, so a marker is the practical route, or rewrite only if the history is still unpublished).
  Without it the pre-push hook and CI will fail on those two lines.

## Notes for the owner

- `.githooks/pre-push` now refuses a push from a clone without `prepublish.denyTermsFile` (WR-01). This clone has it set, so
  nothing changes here; a fresh clone needs the key or `PREPUBLISH_ALLOW_NO_DENY_LIST=1`.
- `cutover_collection.py --apply` now needs `--pre-split-tag` (WR-09); `sync_planning.py` can exit 1 on conflicts (WR-10);
  `build_tool_repo.py` needs `--allow-any-email` for a non-noreply address (WR-11). All three are one-off scripts and were only
  exercised on throwaway repositories.

---

_Fixed: 2026-11-26_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
