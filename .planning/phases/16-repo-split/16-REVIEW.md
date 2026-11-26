---
phase: 16-repo-split
reviewed: 2026-11-26T16:00:00Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - .githooks/commit-msg
  - .githooks/pre-push
  - .github/workflows/ci.yml
  - scripts/prepublish_scan.py
  - scripts/split/build_tool_repo.py
  - scripts/split/cutover_collection.py
  - scripts/split/scrub.py
  - scripts/split/sync_planning.py
  - tests/README.md
  - tests/test_background.py
  - tests/test_choose_folder_dialog.py
  - tests/test_corpus_audit.py
  - tests/test_cutover_collection.py
  - tests/test_first_run_dialog.py
  - tests/test_githooks.py
  - tests/test_help_dialog.py
  - tests/test_import_dialog.py
  - tests/test_main_window.py
  - tests/test_migration_dialog_run.py
  - tests/test_new_collection_dialog.py
  - tests/test_prepublish_scan.py
  - tests/test_sexpr.py
  - tests/test_split_export.py
  - tests/test_uri_diff.py
  - scripts/split/uri_diff.py
  - tests/zipfixtures.py
  - tests/ulfixtures.py
  - tests/test_markers.py
  - tests/test_ci_workflow.py
  - kicad_lib_manager/widgets/background.py
  - kicad_lib_manager/widgets/new_collection_dialog.py
findings:
  critical: 0
  warning: 3
  info: 14
  total: 17
  necessity: 0
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-11-26T16:00:00Z
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Incremental re-review of the 23 fix commits since 64a908a (the fixes for CR-01, CR-02, WR-01 to WR-20, plus 8264819, which makes the pre-publish scan treat placeholder user folders as samples). The 24 changed files were read against `git diff 64a908a HEAD`, and the new code was exercised on synthetic strings and on throwaway repositories (no repository of the project was written). I ran the modules the fixes touch with `--full` (113 passed) and the scan over this checkout (`--tree --history`: clean, 426 files, 530 blobs, 56 commits).

Verdict on the previous Critical and Warning findings. All of them are fixed and none of the fixes introduced a Critical defect:

- CR-01: `history_tags` reads every annotated tag object (nested ones too, through the object walk) and applies the identity and message checks. Confirmed with the slow test and by reading the walk.
- CR-02 and WR-07: the path and address rules run on the line and on a copy with `\n`, `\r`, `\t` replaced by a space. Confirmed on `\n` and `\t` before an address and before drive-letter, git-bash, WSL and URL-encoded paths. `scrub.py` mirrors it.
- WR-01 to WR-06: the pre-push hook refuses without `prepublish.denyTermsFile`, the scan prints the note, binary data is decoded and scanned instead of skipped, names and refs go through the text rules, each blob is judged by every path it had, the vendor list and magics are wider and the fixtures exemption is narrow.
- WR-08 to WR-11, WR-17 (verified against `background.py`: the outcome is queued before `_returned` is set, so waiting on the event pumps no loop turn), WR-12 to WR-16, WR-18 to WR-20: fixed as described in the fix report.

The false-negative direction of the scan, which is the serious one for a public repository, has one new gap, introduced by the placeholder-user decision (8264819): the user folder is read as the first whitespace-delimited word, so a real profile folder whose first word is a placeholder name passes (WR-21). The other two new warnings are in the one-off split scripts: the planning-sync conflict check reports false conflicts (WR-22) and the cutover's tag check accepts a branch (WR-23).

Info findings IN-01 to IN-10 from the previous review were all re-checked against the current code and all still apply; none was dropped. They are carried below with the same ids and titles and updated line numbers. New Info findings start at IN-11.

## Warnings

### WR-21: A placeholder user folder is matched by its first word only, so a real profile folder that starts with a placeholder name is treated as a sample

**File:** `scripts/prepublish_scan.py:121-125, 235-254`
**Issue:** `_path_user` takes the user folder from `_SEGMENT_PATTERN`, which stops at whitespace. Windows profile folders can contain a space (a first name and a surname). Confirmed by running `_line_hits`: a drive-letter path into a folder named with the first name `Bob`, a space and a surname, a folder named `Alice` plus a surname, and a folder named `User Name` all return no `workstation_path` hit, because the segment read is only `Bob`, `Alice` or `User`, which are in `PLACEHOLDER_USERS`. The same happens for the git-bash, WSL, URL-encoded and UNC spellings, which all read the user through the same segment pattern. Names such as `Bobby` or `bob.smith` are correctly not placeholders, so the whole-segment intent of the rule is clear; only the space case breaks it. For a public repository this is a false negative of the serious kind: a real person's folder with a common first name leaves the workstation unseen by the scan. The macOS and Linux patterns cannot contain a space (`[^/\s]+`), so they are not affected. The test `test_a_placeholder_user_folder_is_a_sample_not_a_workstation_path` covers `bobby`, `users2` and a clone folder but no name with a space.
**Fix:** Read the user folder up to the next path separator, quote or end of line, spaces included, and compare that whole text:
```python
_SEGMENT_PATTERN = re.compile(r"[\\/]*([^\\/\"'`]+)")
...
following = _SEGMENT_PATTERN.match(text, match.end())
return following.group(1).rstrip() if following else ""
```
Prose that continues after a sample (`... bob and more`) then reads as a longer name and is reported, which is the safe direction; confirm on the tree that no existing sample line is affected (the tree scan is clean today and should stay so), and add test cases for a placeholder name followed by a space and a surname, with a backslash, a slash and a UNC share.

### WR-22: The planning-sync conflict check reports false conflicts: on a second sync with the same `--since` and on any checkout that converts line endings

**File:** `scripts/split/sync_planning.py:80-89, 106-109` (help text at line 136)
**Issue:** `_edited_in_dest` compares the working-copy bytes of the destination file with the scrubbed export of the `--since` tag. Two ways this is wrong, both reproduced on throwaway repositories:
1. After a first sync has been applied and committed, a second sync from the same `--since` tag (the help text says it is "the tag the tool repository was built from") finds that every file changed by both syncs differs from the `since` version, and prints `conflict <path>` and exits 1 for it, although nobody edited anything in the tool checkout. For an `A` file changed again the second check at lines 108-109 does the same. The conflict test is only right when `--since` is the ref that was synced last, which the help text and the docstring do not say.
2. On a Windows tool checkout with `core.autocrlf=true` the working copy holds CRLF bytes while the export bytes are LF. With the repository clean (`git status` empty) every modified file was reported as `conflict` in my run. `_require_clean_planning` has already proved that the working copy equals the committed content, so the working bytes are the wrong thing to compare.
The sync then never copies the files it exists for, and the owner will conclude that the script is broken or will hand-copy the files without the scrub.
**Fix:** Compare against the committed blob of the destination instead of the working file: `_git(dest, "show", f"HEAD:{path}")` (no line-ending conversion, and equal to the working copy because the folder is clean). Make the base of the comparison the last synced ref, not the build tag: record it (a one-line file such as `.planning/.synced-ref`, or require `--since` to be the previous `--ref` and say so in the help text), and add a slow test that runs two syncs in a row and expects no conflict on the second.

### WR-23: The cutover's safety-net check accepts a branch name and never looks at the bundle

**File:** `scripts/split/cutover_collection.py:208-214, 398-401`
**Issue:** The new check runs `git rev-parse --verify -q NAME^{commit}`. That resolves any ref called NAME, so a branch (or a remote-tracking ref) named like the tag passes, although a branch moves with the next commit and restores nothing. The messages still say "the pre-split bundle and tag restore the previous state", yet no bundle is looked at; the dry run (no `--pre-split-tag`) performs no check at all and prints a plan that looks acceptable. The WR-09 fix text says the tag "must exist and name HEAD"; for a branch that is true only until the next commit.
**Fix:** Resolve the full ref name: `git rev-parse --verify -q refs/tags/NAME^{commit}`. Optionally take `--pre-split-bundle FILE` and run `git bundle verify FILE` in the same check, and make the dry run report "no safety net checked yet" when no tag was given.

## Info

### IN-01: `uri_diff.py` resolves variables with the process environment as the lowest priority

**File:** `scripts/split/uri_diff.py:379-380`
**Issue:** The order is process environment, then `kicad_common.json`, then `--var`. As far as I know KiCad lets a variable defined in the operating system win over the config file, which is the reverse. Both snapshots in a before/after proof use the same order, so the comparison stays valid unless the shell environment differs between the two runs; the numbers shown for one snapshot may differ from what KiCad resolves. The snapshot also writes every non-library-root resolved path verbatim (for instance a KiCad install or a user folder) into `--out`; if that file is stored in an allow-listed planning folder, the scan will flag it. Still the same in the current code (the help text at line 428 documents only the `--var` priority).
**Fix:** Document the precedence in the docstring, and offer `--no-env` to ignore the process environment; normalise or redact paths under the user's home in the snapshot.

### IN-02: `tests/zipfixtures.py` builds the sample zip into the shared system temp at import time

**File:** `tests/zipfixtures.py:27`; `tests/ulfixtures.py:297-326`
**Issue:** `UL_ZIP = ul_sample_zip()` runs when any test module imports `zipfixtures`, in every xdist worker, and writes under `<system temp>/kicad_lib_manager_tests/<hash>/`. The module docstring (line 9) still says builders write only under the path the test passes. The parallel build itself is safe (content-addressed folder, per-process temp name, `os.replace` with a hash re-check), but an unwritable temp folder turns into a collection error for every module, and on a shared Linux `/tmp` the predictable folder can be pre-created by another user (a denial of service only, the content is hash-checked once at creation).
**Fix:** Build lazily (a function or a session fixture) and put the cache under a per-user folder (`tempfile.gettempdir()` plus the user name, or `tmp_path_factory.getbasetemp().parent` as `_git_template_root` does); fix the docstring.

### IN-03: `str.splitlines()` shifts reported line numbers

**File:** `scripts/prepublish_scan.py:180`, `:310`, `:379`
**Issue:** `splitlines()` also splits on form feed, `\x1c`-`\x1e`, `\x85`, `U+2028` and `U+2029`, so the line number in a finding can differ from the editor's number for files that contain them. The binary-data path of `_decode` now turns NUL bytes into line breaks on purpose (the test pins that numbering), which makes the numbers for such files a count of NUL-separated runs rather than editor lines. Not a correctness gap for detection, but it misleads whoever fixes the hit.
**Fix:** Split on `\n` (`text.split("\n")`, dropping a trailing `\r`), and say in `_decode`'s docstring that for NUL-bearing data the number is a run count.

### IN-04: `build_tool_repo.py` cleanup swallows its own failures and the scrub covers only `.planning`

**File:** `scripts/split/build_tool_repo.py:150-156, 221`
**Issue:** `_force_remove` ignores an `OSError` on the retry, so a failed clean-up of a rejected export leaves part of it on disk while the message says the destination was cleaned; the parent folders created by `mkdir(parents=True)` are never removed. Path scrubbing runs on `.planning` only (`scrub_tree(dest, [".planning"], mapping)`); a workstation path in `CLAUDE.md`, `scripts/` or tests is left to the push scan.
**Fix:** Count and report what could not be removed; extend `scrub_tree` to `CLAUDE.md` and `README.md` or document that the scan is the only guard there.

### IN-05: `--min-passed 3500` is a bare constant in CI

**File:** `.github/workflows/ci.yml:40`
**Issue:** The floor has no stated relation to the suite size and the CI run deselects the `needs_kicad` and `corpus` tests, so the value is only right if someone measured it on a runner; it will silently drift or fail the first time tests are moved between markers. No other defect found in the workflow (permissions are read-only, a job timeout is set, the scan runs before pytest, `fetch-depth: 0` is set so the history scan sees all commits). The new comment before the scan step states honestly that owner names are enforced by the pre-push hook only.
**Fix:** Record the measured count next to the number (a comment with the date) and review it when markers change.

### IN-06: `test_markers.py` cannot be collected on Python 3.10

**File:** `tests/test_markers.py:4`
**Issue:** `import tomllib` is at module level for the new `test_corpus_and_needs_kicad_are_registered`. `tomllib` arrived in Python 3.11, while the project rules (`.claude/CLAUDE.md`, "Python 3.10+") and `tests/README.md` ("`tomllib` missing on Python 3.10: `tests/test_manifests.py` skips through `importorskip`") still treat 3.10 as supported. On 3.10 the whole module, including the older marker meta-tests, fails at import. CI pins 3.14, so nothing fails today.
**Fix:** `tomllib = pytest.importorskip("tomllib")` inside the one test (import `pytest` at the top), or state 3.11 as the new minimum in the README.

### IN-07: Dead loop in `test_read_only_git_allow_list_is_exact`

**File:** `tests/test_markers.py:102-111`
**Issue:** Line 103 asserts `_READ_ONLY_GIT_TESTS == {}`, so the `for ident in _READ_ONLY_GIT_TESTS` loop below can never execute. The test now reduces to checking that a dict literal is empty, and the loop is code for a case the assertion forbids (the docstring says it is kept for a future test).
**Fix:** Drop the loop and the equality test, keep `_READ_ONLY_GIT_TESTS` and its use in `test_requires_git_tests_are_slow`, and add the exactness check back when the first entry exists.

### IN-08: `test_ci_workflow.py` checks match comments and any step

**File:** `tests/test_ci_workflow.py:20-26`, `:29-31`, `:34-42`
**Issue:** The runner, Python version, `fetch-depth` and `timeout-minutes` checks are substring tests on the whole file, so a commented-out line or a value in a different job satisfies them. `test_step_order` takes the first occurrence of each command, so a second, earlier copy of the scan line (for example in a comment) would pass while the real step moved. `permissions: contents: read` is matched only at the top level, so a job-level `permissions:` that grants write is not seen. The comment the WR-01 fix added to the workflow shows the weakness: the test file's own `--full` check has to be satisfied by avoiding a word in the comment text.
**Fix:** Strip `#` comment lines before matching (`text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))`), assert there is no `write` permission anywhere (`assert not re.search(r"(?m)^\s*\w[\w-]*:\s*write\s*$", text)`), and require each command to occur exactly once.

### IN-09: `test_owner_choice_is_remembered_after_close_escape_and_parent_deleted` fixed the Escape branch but not the Close-button branch

**File:** `tests/test_help_dialog.py:832-838`
**Issue:** The earlier commit added `waitUntil(lambda: not dialog.isVisible())` before the Escape branch's assert, but the `how == "close"` branch two lines above still clicks the Close button and asserts `not dialog.isVisible()` immediately. If the close needed a wait on CI, so does this branch (the other close paths in the same file were all given one). In production the Close button and Escape both end in `reject()`, so they cannot differ; the branches are simply inconsistent.
**Fix:** Add `qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=30000)` after the Close click, or factor a `_wait_hidden(qtbot, dialog)` helper used by every branch.

### IN-10: Debounce tests assert "nothing started yet" after a 100 ms wall-clock wait against a 300 ms debounce

**File:** `tests/test_choose_folder_dialog.py:244-245`, `tests/test_new_collection_dialog.py:237-238`
**Issue:** Both tests type quickly, call `qtbot.wait(100)`, and assert `rec.calls == []` / `rec.checks == []` ("nothing before the 300 ms are over"). `qtbot.wait(100)` returns after at least 100 ms, not at 100 ms: on a stalled runner the main thread can be held longer than the 300 ms debounce, the timer then fires, the worker records a call, and the negative assertion fails. A negative assertion on elapsed time cannot be fixed by a longer timeout; it needs a clock-free form. The WR-18 fix applied exactly that form to the browse test in `test_new_collection_dialog.py` (it now reads `_debounce.interval()`), which shows these two tests sit beside the corrected one.
**Fix:** Assert on state instead of on time: check that the debounce timer is still active (for example `assert dialog._debounce.isActive()` right after the last `setText`) and that no check task exists yet, then let `settle` run.

### IN-11: `_decode` reads UTF-32 big-endian without a byte order mark as garbage, so its text is not scanned

**File:** `scripts/prepublish_scan.py:297-305`
**Issue:** The heuristic tests only the share of NUL bytes among the odd bytes first (little endian). For UTF-32 big-endian text without a BOM (`00 00 00 61`) half of the odd bytes are NUL, so it takes the `utf-16-le` branch and decodes to CJK characters; confirmed by running `_decode` on an encoded address, which gives no readable text. UTF-32 little endian without a BOM works by accident (the NULs are dropped). The new test lists only `utf-32-le` as the BOM-less case.
**Fix:** Test the 4-byte stride: when `head[0::4]`, `head[1::4]` and `head[2::4]` are mostly NUL decode as `utf-32-be`, when `head[1::4]`, `head[2::4]` and `head[3::4]` are mostly NUL as `utf-32-le`, before the UTF-16 branches; add `utf-32-be` to the encoding test.

### IN-12: A JSON-escaped UNC path and other JSON escapes still hide a path or an address

**File:** `scripts/prepublish_scan.py:112, 146, 262-265`
**Issue:** The UNC pattern requires exactly two leading backslashes and refuses a start after another backslash. In JSON the escaped form is four backslashes (`\\\\server\\share\\Users\\<name>`), which gives no hit for a real user name (confirmed). The variant rule only handles `\n`, `\r`, `\t`; a `\u000a` or `\f` escape in front of an address still shields it. Planning state and junit files are the likely carriers, but the current tree and history are clean, so this is latent.
**Fix:** Add a second variant with `\\\\` collapsed to `\\` (and `\\` to `\` for the drive rule already handled), and extend `_ESCAPE_PATTERN` to `\\(?:[nrtfb]|u000[0-9a-f])`; add cases for both.

### IN-13: Annotated tags with an empty tagger address skip the identity check, and the name in the tag header is never read

**File:** `scripts/prepublish_scan.py:532-554, 720-724`
**Issue:** `run` applies `scan_identity` to a tag only `if email:`, so a tag whose tagger line has a name but an empty address (`Name <>`) is never checked for an owner term in the name. `history_tags` also discards the `tag <name>` line of the object header; the published ref name is scanned, but an annotated tag object can carry a different header name (a tag object created for one name and published under another).
**Fix:** Call `scan_identity` whenever a tagger line exists (an empty address then counts as not allow-listed) and run the header name through `_name_findings(name, f"tag:{sha[:12]}", rules)`.

### IN-14: Formatting slip in the marker pattern definition

**File:** `scripts/prepublish_scan.py:147`
**Issue:** `_MARKER_PATTERN =re.compile(...)` lacks the space after `=` (the only such line in the file). Cosmetic, but it is a sign the lines of this block were edited without a formatter in this repository, which has none configured.
**Fix:** Write `_MARKER_PATTERN = re.compile(...)`.

---

_Reviewed: 2026-11-26T16:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
