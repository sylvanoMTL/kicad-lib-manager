---
phase: 16-repo-split
fixed_at: 2026-11-26T18:30:00Z
review_path: .planning/phases/16-repo-split/16-REVIEW.md
iteration: 1
findings_in_scope: 17
fixed: 17
skipped: 0
status: all_fixed
---

# Phase 16: Code Review Fix Report

**Fixed at:** 2026-11-26
**Source review:** .planning/phases/16-repo-split/16-REVIEW.md
**Iteration:** 1

The previous fix report (CR-01, CR-02 and WR-01 to WR-20) is in commit a705743; this report replaces it in the
phase folder and covers the findings of the re-review: WR-21 to WR-23 and IN-01 to IN-14.

**Summary:**
- Findings in scope: 17 (WR-21 to WR-23, IN-01 to IN-14)
- Fixed: 17
- Skipped: 0

Where the fixes ran: in an isolated git worktree of this clone on a temporary branch, using the project venv by absolute
path. The 17 commits were then fast-forwarded onto `main`, the worktree and the temporary branch were removed, and nothing
was pushed. The gates below ran in that worktree (same tree as `main` at da807fd); the final scan ran in the main checkout.
Every changed file kept its CRLF line endings (checked by counting LF-only lines in all 17 changed files: none).

## Verification

- Quick suite (`python -m pytest`, parallel, `slow` skipped): 4045 passed, 3 skipped in 95 s. The 3 skips are the two
  symlink-privilege skips and the real-config skip, within the budget of 10. Run once at the end, in the worktree.
- The CI floor was measured the way CI runs: with KiCad hidden (`KICAD_TEST_HIDE_KICAD=1`) the quick run gave 4031 passed,
  3 skipped (corpus and needs_kicad tests deselected); that number is recorded beside `--min-passed 3500` (IN-05).
- Targeted runs with `--full` (slow tests included): `tests/test_prepublish_scan.py` 28 passed, `tests/test_cutover_collection.py`
  11 passed, `tests/test_split_export.py` 38 passed. The timing tests of IN-09 and IN-10 were run three times serially
  (`-n 0`): `tests/test_help_dialog.py` 74 passed three times, `tests/test_choose_folder_dialog.py` plus
  `tests/test_new_collection_dialog.py` 40 passed three times.
- Pre-publish scan `python scripts/prepublish_scan.py --tree --history` in the main checkout after the last commit: **1 finding,
  exit 1**: `workstation_path` at `.planning/phases/16-repo-split/16-REVIEW.md:170`. See "Needs a decision" below. Before the
  IN-12 commit the scan was clean (426 files, 544 blobs, 64 commits); with the last commit, no other file or commit is flagged.

## Needs a decision

The IN-12 fix (a JSON-escaped UNC path is now read with its doubled backslashes collapsed) newly flags one existing,
committed line: line 170 of `16-REVIEW.md` quotes, as an example in the text of IN-12, a doubled-backslash UNC path whose
user folder is written `<name>`. `<name>` is not in the placeholder list (`bob`, `alice`, `user`, `username`, `<user>`,
`<username>`), which is the owner's decision, so the rule reports it. The rule was not weakened to hide this. The file is a
planning artifact outside this fix's scope, and the same text is in the blob of the (unpushed) review commit 7e75d79, so a
push would be refused by the pre-push hook and by CI until either (a) the quoted example in `16-REVIEW.md` is reworded to use
`<user>` and the review commit is amended or rewritten before the push (origin/main is at a1c90c9, so only 7e75d79 and the 17
fix commits are unpushed), or (b) the owner adds `<name>` to the placeholder list.

## Fixed Issues

### WR-21: A placeholder user folder is matched by its first word only, so a real profile folder that starts with a placeholder name is treated as a sample

**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 4e1284a
**Status:** fixed: requires human verification (a rule change)
**Applied fix:** The user folder is read up to the next separator, quote, backtick or end of line, spaces included, and
compared whole (trailing blanks trimmed). A folder named with a placeholder name, a space and a surname now reports
`workstation_path` for the backslash, doubled-backslash, slash, git-bash, WSL, URL-encoded and UNC spellings; the bare placeholder
(with trailing blanks, or a quote right after it) stays a sample. The placeholder-user rule itself is unchanged. New test
`test_a_profile_folder_with_a_space_is_read_whole_not_by_its_first_word`. The scan of the tree and history was unchanged by it.

### WR-22: The planning-sync conflict check reports false conflicts: on a second sync with the same `--since` and on any checkout that converts line endings

**Files modified:** `scripts/split/sync_planning.py`, `tests/test_split_export.py`
**Commit:** 3909d2c
**Status:** fixed: requires human verification (comparison logic)
**Applied fix:** The conflict check now compares the committed bytes of the destination (`git show HEAD:<path>`, no line-ending
conversion; equal to the working copy because the clean check has already passed) with the scrubbed `--since` version, for both
the changed and the added case; a file that is not committed counts as edited. The docstring and the `--since` help text now say
that `--since` is the ref the checkout was last brought to: the build tag for the first sync, then the `--ref` of the previous
sync. I chose the "require --since to be the previous --ref and say so" option from the review instead of recording a
`.synced-ref` file, so that no new file is added to an allow-listed folder; a second sync that still passes the older tag reports
conflicts, as documented. New slow tests: a second sync from the last synced ref has no conflict, and a clean checkout with
`core.autocrlf=true` (working copy in CRLF) syncs without a conflict (the second test fails on the old code).

### WR-23: The cutover's safety-net check accepts a branch name and never looks at the bundle

**Files modified:** `scripts/split/cutover_collection.py`, `tests/test_cutover_collection.py`
**Commit:** 5e01802
**Status:** fixed: requires human verification (a check)
**Applied fix:** The check resolves `refs/tags/NAME^{commit}`, so a branch or a remote-tracking ref of that name no longer passes
("does not exist"). A dry run without `--pre-split-tag` now prints "no safety net checked yet: pass --pre-split-tag NAME ...", and a
dry run given a tag checks it too. The optional `--pre-split-bundle FILE` with `git bundle verify` was not added: the docstring says
the bundle is not looked at. New refusal cases (`branch_for_tag`, `dry_stale_tag`) and an assertion on the dry-run note.

### IN-01: `uri_diff.py` resolves variables with the process environment as the lowest priority

**Files modified:** `scripts/split/uri_diff.py`, `tests/test_uri_diff.py`
**Commit:** b2b0cbf
**Applied fix:** The module docstring documents the precedence (process environment, then `kicad_common.json`, then `--var`) and
says KiCad may prefer an operating-system variable, so both snapshots of a proof should come from the same shell. New `snapshot`
options: `--no-env` (ignore the process environment) and `--redact-home` (write the user's home folder as `<HOME>` in the snapshot,
whole path segments only). The default order and output are unchanged, so existing snapshots still compare; redaction is opt-in
because both snapshots of a proof must use the same flag. New tests for both options and for the segment rule.

### IN-02: `tests/zipfixtures.py` builds the sample zip into the shared system temp at import time

**Files modified:** `tests/ulfixtures.py`, `tests/zipfixtures.py`
**Commit:** decc72e
**Applied fix:** The sample-zip cache folder is now per user (`kicad_lib_manager_tests-<user name, sanitised>` under the system
temp folder, with a fixed fallback name when no user name is known), so another user of a shared temp folder cannot pre-create it.
The `zipfixtures.py` docstring now names the exception (`UL_ZIP`, built at import into that cache). The build was not made lazy:
`UL_ZIP` is imported by name in many test modules and used as a default argument, so a lazy form would still run at import and
would need edits in a dozen modules; an unwritable temp folder fails every test anyway (`tmp_path` needs it).

### IN-03: `str.splitlines()` shifts reported line numbers

**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** 35e05f0
**Status:** fixed: requires human verification (line splitting)
**Applied fix:** The per-line scan splits on CRLF, CR or LF only, so form feed, `\x1c`-`\x1e`, `\x85`, U+2028 and U+2029 no
longer shift the reported number; the `_decode` docstring says that for NUL-bearing data the number counts runs. I left the two
other `splitlines()` uses alone on purpose: the corpus-window builder reports no number, and the commit and tag message scan keeps
the wider split because it looks for a session trailer at the start of a line (more line starts is the safer direction there). New
test `test_reported_line_numbers_follow_the_editor_not_str_splitlines`.

### IN-04: `build_tool_repo.py` cleanup swallows its own failures and the scrub covers only `.planning`

**Files modified:** `scripts/split/build_tool_repo.py`, `tests/test_split_export.py`
**Commit:** ba07eff
**Applied fix:** `_rmtree` and `_clear` now return the items they could not remove, and a failed build appends "the clean-up could
not remove N item(s) of the failed export; delete them by hand: ..." to its error (the exit code is kept). Parent folders that
`mkdir(parents=True)` created are removed again when empty. The scrub was not extended: it would also rewrite the made-up sample
folders that `CLAUDE.md` and the docs quote (the generic home rule replaces any user name), so the module docstring now states
that the push scan is the only guard for a path in any file other than `.planning`. New tests for the parent removal and for the
failure report.

### IN-05: `--min-passed 3500` is a bare constant in CI

**Files modified:** `.github/workflows/ci.yml`
**Commit:** 3cefe27
**Applied fix:** A comment above the step records the measured count (4031 passed, 3 skipped on 2026-11-26 with KiCad hidden, the
corpus and needs_kicad tests deselected) and says to measure again when tests move between markers or a large group is added or
removed. The floor itself is unchanged (3500). `tests/test_ci_workflow.py` still passes.

### IN-06: `test_markers.py` cannot be collected on Python 3.10

**Files modified:** `tests/test_markers.py`
**Commit:** ee8f14f
**Applied fix:** The module-level `import tomllib` is gone; the one test that reads `pyproject.toml` does
`tomllib = pytest.importorskip("tomllib")`. Checked by reading, because only a 3.14 venv exists here: the module's remaining imports
are `ast`, `pytest` and `runfixtures`, all available on 3.10, and `tomllib` appears only inside that test. Not changed, out of
this finding's scope: `tests/test_isolation.py` also has a module-level `import tomllib`, so it still cannot be collected on 3.10.

### IN-07: Dead loop in `test_read_only_git_allow_list_is_exact`

**Files modified:** `tests/test_markers.py`
**Commit:** bcc14a6
**Applied fix:** The test (an assertion that the dict is empty, followed by a loop over it) is removed. `_READ_ONLY_GIT_TESTS` and
its use in `test_requires_git_tests_are_slow` stay, and the comment above the dict says to add the exactness check back with the
first entry.

### IN-08: `test_ci_workflow.py` checks match comments and any step

**Files modified:** `tests/test_ci_workflow.py`
**Commit:** 0f25c62
**Applied fix:** Comment lines are stripped before every check; each command in the step-order test must occur exactly once; the
runner, timeout and trigger checks are line-anchored and there must be a single `runs-on`; the Python version is read from the
setup-python step and `fetch-depth: 0` from the checkout step; no `write` permission (or `write-all`) may appear at any level. Checked
by mutating a copy of the workflow (commented runner, job-level write, moved scan step, commented fetch depth): each was caught.

### IN-09: `test_owner_choice_is_remembered_after_close_escape_and_parent_deleted` fixed the Escape branch but not the Close-button branch

**Files modified:** `tests/test_help_dialog.py`
**Commit:** ed088b2
**Applied fix:** The Close branch waits with `qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=30000)` before its assertion,
the same pattern as the Escape branch. `tests/test_help_dialog.py` ran three times serially: 74 passed each time.

### IN-10: Debounce tests assert "nothing started yet" after a 100 ms wall-clock wait against a 300 ms debounce

**Files modified:** `tests/test_choose_folder_dialog.py`, `tests/test_new_collection_dialog.py`
**Commit:** da807fd
**Applied fix:** Both tests no longer wait 100 ms. Right after the last edit they assert that the debounce timer is still active and
that no check has started; no event is processed between the edit and the assertion, so the result does not depend on the clock. The
later settle and the "one check for three edits" assertions are unchanged. The two modules ran three times serially: 40 passed each time.

### IN-11: `_decode` reads UTF-32 big-endian without a byte order mark as garbage, so its text is not scanned

**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** a7e4cd3
**Status:** fixed: requires human verification (decoding heuristic)
**Applied fix:** Before the UTF-16 branches, `_decode` tests the 4-byte stride: when bytes 1, 2 and 3 of each group are mostly NUL
it decodes UTF-32 little endian, when bytes 0, 1 and 2 are it decodes UTF-32 big endian (same 30 % share as the UTF-16 test). The
encoding test now lists UTF-32 big and little endian without a BOM; UTF-16 and plain binary noise still behave as before.

### IN-12: A JSON-escaped UNC path and other JSON escapes still hide a path or an address

**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** d2d2a2d
**Status:** fixed: requires human verification (rule change; it flags one existing committed line, see "Needs a decision")
**Applied fix:** A second variant of each line has every doubled backslash collapsed (a JSON-escaped UNC share starts with four),
and the escape variant now also covers `\f`, `\b` and the `\u000x`, `\u001x`, `\u0085`, U+2028 and U+2029 escapes. Two
refinements were needed so ordinary text stays quiet: an escape preceded by a backslash is an escaped backslash and not an escape
(`\\b` is a separator and a letter), and an escape is replaced by a line break, which also ends a user folder name that now may
hold spaces (WR-21), so a placeholder folder followed by a path part such as `notes` or `file` stays a sample. New test
`test_json_escapes_beyond_n_r_t_and_a_doubled_unc_path_do_not_hide_a_finding`.

### IN-13: Annotated tags with an empty tagger address skip the identity check, and the name in the tag header is never read

**Files modified:** `scripts/prepublish_scan.py`, `tests/test_prepublish_scan.py`
**Commit:** db4bf69
**Status:** fixed: requires human verification (scan logic)
**Applied fix:** `history_tags` now also returns the name from the `tag <name>` header line (its tuples have five fields instead of
four). `run` applies the identity check whenever the tagger line has a name or an address (an empty address is never allow-listed),
and runs the header name through the text rules at `tag:<id>`. New slow test with hand-written tag objects: a tagger with a name and
an empty address is reported as `commit_identity`, and an owner term in the header name of a tag published under another ref name is
reported as `owner_term`.

### IN-14: Formatting slip in the marker pattern definition

**Files modified:** `scripts/prepublish_scan.py`
**Commit:** 5925b54
**Applied fix:** `_MARKER_PATTERN = re.compile(...)` now has the space after `=`.

---

_Fixed: 2026-11-26T18:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
