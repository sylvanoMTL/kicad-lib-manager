---
phase: 16-repo-split
reviewed: 2026-11-26T11:13:00Z
depth: standard
files_reviewed: 91
files_reviewed_list:
  - .gitattributes
  - .githooks/commit-msg
  - .githooks/pre-push
  - .github/workflows/ci.yml
  - .gitignore
  - CLAUDE.md
  - LICENSE
  - README.md
  - kicad_lib_manager/collection.py
  - kicad_lib_manager/main_window.py
  - kicad_lib_manager/startup.py
  - kicad_lib_manager/widgets/help_dialog.py
  - pyproject.toml
  - scripts/check_skip_budget.py
  - scripts/prepublish_scan.py
  - scripts/split/allowlist.txt
  - scripts/split/build_tool_repo.py
  - scripts/split/collection/CLAUDE.md
  - scripts/split/collection/README.md
  - scripts/split/cutover_collection.py
  - scripts/split/scrub.py
  - scripts/split/sync_planning.py
  - scripts/split/uri_diff.py
  - scripts/split/verify_export.py
  - tests/README.md
  - tests/conftest.py
  - tests/corpusfixtures.py
  - tests/test_adapters.py
  - tests/test_atomic_dialog.py
  - tests/test_atomic_targets.py
  - tests/test_atomic_uat.py
  - tests/test_background.py
  - tests/test_categories.py
  - tests/test_checkout_warning.py
  - tests/test_choose_folder_dialog.py
  - tests/test_ci_workflow.py
  - tests/test_collection.py
  - tests/test_commit_step.py
  - tests/test_corpus_audit.py
  - tests/test_corpus_gate.py
  - tests/test_cutover_collection.py
  - tests/test_dialog_geometry.py
  - tests/test_docs_split.py
  - tests/test_edits.py
  - tests/test_first_run_dialog.py
  - tests/test_footprint_index.py
  - tests/test_footprint_text.py
  - tests/test_gate_reasons.py
  - tests/test_generated_text.py
  - tests/test_githooks.py
  - tests/test_help_dialog.py
  - tests/test_import_content.py
  - tests/test_import_dialog.py
  - tests/test_import_form.py
  - tests/test_importer_layering.py
  - tests/test_install_e2e.py
  - tests/test_install_gate.py
  - tests/test_install_verify.py
  - tests/test_isolation.py
  - tests/test_kicad_files.py
  - tests/test_locate_text_caps.py
  - tests/test_main_window.py
  - tests/test_main_window_chooser.py
  - tests/test_main_window_import.py
  - tests/test_main_window_migration.py
  - tests/test_main_window_root.py
  - tests/test_markers.py
  - tests/test_migration_dialog.py
  - tests/test_migration_dialog_files.py
  - tests/test_migration_dialog_run.py
  - tests/test_naming_sanitize.py
  - tests/test_new_collection_dialog.py
  - tests/test_official_footprint.py
  - tests/test_prepublish_scan.py
  - tests/test_real_vendor_samples.py
  - tests/test_roundtrip_corpus.py
  - tests/test_samacsys_adapter.py
  - tests/test_scanner_issues.py
  - tests/test_sexpr.py
  - tests/test_siblings.py
  - tests/test_skip_budget.py
  - tests/test_snapeda_adapter.py
  - tests/test_split_export.py
  - tests/test_startup.py
  - tests/test_stems.py
  - tests/test_suggest_atomic.py
  - tests/test_ulfixtures.py
  - tests/test_uri_diff.py
  - tests/test_vendorfixtures.py
  - tests/ulfixtures.py
  - tests/zipfixtures.py
findings:
  critical: 2
  warning: 20
  info: 10
  total: 32
  necessity: 0
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-11-26T11:13:00Z
**Depth:** standard
**Files Reviewed:** 91
**Status:** issues_found

## Summary

The evaluation scope for this phase degraded: the repository starts at a one-commit import, so no task commits are reachable. The scope (91 files) was rebuilt from the phase's task commits and the SUMMARY key-files, and the review was split across three reviewers. This report covers the production code, scripts, hooks, CI and test infrastructure (28 files). The test-module part is merged in from two further reviewers.

What held up. The allow-list export path is sound: `build_tool_repo.py` exports from `git archive` of a ref (never the working tree), refuses links and gitlinks, filters every member through the allow-list plus the hard-deny list, and re-verifies the written tree. `sync_planning.py` cannot write outside `.planning/` (the resolve-based containment check also stops a symlink escape). `uri_diff.py` is read-only apart from `--out`, and refuses an `--out` that would overwrite a file it reads. The startup and collection changes are consistent: the `LEGACY` source and its `is_collection(app_dir)` candidate are gone, no reference to them remains, and `APP_DIR` is now used only to refuse a new collection inside the code folder, so the code folder can no longer become the library folder. The corpus gate in `tests/conftest.py` deselects (never skips), merges worker counts correctly and fails closed on a bad `KICAD_TEST_CORPUS`. A tree scan of this checkout is clean and the output format never prints matched text.

The main weaknesses are in `scripts/prepublish_scan.py`, the gate for a now-public repository. It has demonstrated false negatives (an email or a drive-letter path directly after a JSON `\n` or `\t` escape), it never looks at annotated tag objects, and its owner-specific rules switch off silently when the local git config is absent (always the case in CI). `cutover_collection.py` can delete its own templates mid-run when started from the checkout it is cutting over. Findings were confirmed by running the scanner's functions on synthetic strings (no repository was written).

### Test modules (reviewer B, merged)

Reviewer B covered the 11 new Phase 16 test modules in full and the Phase 16 hunks of the 37 converted
modules (diff plus the current files around each hunk). Method for the converted modules: every
`corpus_path` / `corpus_root` reader was listed (`grep` over `tests/`) and each test that touches a
corpus constant (`ATXK_ZIP`, `REAL_SAMACSYS`, `REAL_ZIPS`, `SAMPLES`, `_custom_files`, `_custom_texts`,
`_stock`, `_LIVE_FP_DIR`) was checked for its `corpus` or `needs_kicad` mark.

What holds up:
- The conversions are sound. Every test that reads the real vendor downloads, the live `Custom/` or the
  Wurth corpus carries `corpus` (directly, through `requires_*` aliases, through parameter marks, or through
  `wurth`), and every stock-KiCad reader carries `needs_kicad`. Inside an open corpus a missing file now
  fails with an assertion instead of skipping.
- No corpus test writes into the collection: the readers copy to `tmp_path` or only read, and
  `test_corpus_gate.py::test_guard_watches_the_corpus_custom` proves the session guard catches a write.
- No test result depends on worker order. Child runs use their own `--basetemp` and marker file, and the
  loaded scripts are held in private module objects.
- `Path.read_text` translates CRLF, so the README, CLAUDE.md and template heading checks do not break under
  `core.autocrlf=true`.

No Critical issues. The weaknesses are in the tests that guard the publishing controls (pre-publish scan,
hooks, export allow-list, cutover) and in the guard tests themselves: several would not fail on a real
regression, and the behavioural tests of the security scripts never run in CI.

### Post-split GUI-test timing fixes (reviewer C, merged)

Scope: the post-split hunks (2712099..HEAD) of 21 test modules, read against the current files. The hunks are almost entirely `waitUntil` / `waitSignal` timeout bumps (5000/10000 to 30000), plus a set of real structural fixes: a wait after a close/reject before asserting `not isVisible()`, `qtbot.wait(200)` replaced by a wait for the result page in `test_migration_dialog_run.py`, the gate registered before the progress steps in `blocking_apply`, and waits added before the `staging.exists()` assertions.

The structural fixes are sound. I checked each one against the production code:

- `MigrationDialog._on_run_done` (`kicad_lib_manager/widgets/migration_dialog.py:1681-1690`) shows the result page last, after the draft is cleared and `migrated` is emitted, so the assertions that follow the page wait are safe.
- `_path_var_busy` and `_chooser_busy` are set synchronously, so the `settle` helpers cannot pass before the action starts.
- Every other `gates.append(...)` fake in `tests/test_import_dialog.py` already registers its gate before emitting progress.
- No `waitSignal` is missing a timeout, and none uses `raising=False`.
- The pasted multi-line `lambda ..., timeout=30000` forms are syntactically correct.

I found no critical issues. Four warnings and two info items remain, all about timing races the fix commits left open or made less effective. The main points: one race in `test_background.py` that the timeout bump cannot fix, two waits that still carry a 250 ms or 1 s budget, a set of waits that kept small timeouts, and worker-side hold gates (5 s) that are now shorter than the 30 s waits in front of them.

## Critical Issues

### CR-01: The history scan never inspects annotated tag objects

**File:** `scripts/prepublish_scan.py:466-476`
**Issue:** `history_blobs` reads every object listed by `rev-list --objects --all` through `cat-file --batch` but yields only `kind == b"blob"`; commit, tree and tag objects are read and discarded. Commits are covered separately by `history_commits` (`git log --all`), but nothing reads an annotated tag. A tag object carries a tagger identity (name and email) and a free-text message, both of which are published by a push of tags (the phase itself talks about a pre-split tag). A real email or a workstation path in a tagger line or tag message passes `--history` clean, and `commit_identity` / `session_trailer` / text rules are never applied to it. `scan_ref` only looks at the ref name.
**Fix:** In `history_blobs` (or a new walker), yield tag objects too and run them through the same identity and message checks, for example with `git for-each-ref --format='%(refname)%00%(taggername)%00%(taggeremail)%00%(contents)%01' refs/tags` (annotated tags have a non-empty `taggeremail`). Apply `scan_identity` (strip the angle brackets from `%(taggeremail)`) and `scan_message` to each. Add a test with an annotated tag that carries a non-noreply tagger email.

### CR-02: An email or drive-letter path right after a JSON escape sequence is invisible to the scan

**File:** `scripts/prepublish_scan.py:78, 89-91` (same pattern family in `scripts/split/scrub.py:41-45`)
**Issue:** Confirmed by running `_line_hits`. The email pattern starts with `(?<![\\\w.%+-])`, which rejects a match start that follows a backslash or a word character. In JSON-escaped or log text, `"Author:\tuser@example.org"` and `"a\nuser@example.org"` give no `email` hit: the characters `\t`/`\n` are a backslash and a letter, so every possible start position inside `tfoo@...` / `nfoo@...` is rejected. The drive-letter rule `\b[a-z]:[\\/]+(?:users|git_repo_clones)` has the same problem: `"x\nC:\\Users\\bob\\a"` gives no hit, because `n` and `C` are both word characters and `\b` fails. Planning state files (`.planning/*.json`), junit files, JSON logs and transcripts quote multi-line text exactly this way. `scrub.py` uses the same lookbehinds (`(?<![A-Za-z0-9_.])[a-z]:`), so the export scrub misses the same paths and the scan then misses them too: the two safety nets fail together. The current tree has no such text (grepped), so this is latent, not an active leak.
**Fix:** Drop the backslash from the email lookbehind and handle escapes explicitly, for example normalise the line before matching: `line = re.sub(r"\\[nrt]", " ", line)` (run the patterns on both the original and the unescaped line). For the drive rule, replace `\b` with `(?<![A-Za-z0-9])` after the same normalisation, or allow a preceding `\\[nrt]`. Mirror the change in `scrub.py` and add test cases for `\n`, `\t` and `\r` before an email and before a path.

## Warnings

### WR-01: Owner-specific rules switch off silently, and CI never has them

**File:** `scripts/prepublish_scan.py:515-527`; `.github/workflows/ci.yml:29`; `.githooks/pre-push:25`
**Issue:** The `owner_email` and `owner_term` rules depend on `--deny-*` flags or on `prepublish.denyEmailsFromRepo` / `prepublish.denyTermsFile` in the clone's local git config. When neither exists, `_build_rules` builds empty deny lists without a word, and the run ends in `prepublish_scan: clean (...)`. The CI job runs the bare command, so it never applies owner terms or owner emails (the generic `email` and `workstation_path` rules still run). A fresh clone with `core.hooksPath` enabled but no `prepublish.*` keys gets the same silent downgrade at the push hook, where it matters most. "Clean" then claims more than was checked.
**Fix:** Print one line to stderr when the deny lists are empty (`prepublish_scan: no owner deny list in use`), and let the pre-push hook refuse when `git config --get prepublish.denyTermsFile` is empty unless an explicit opt-out variable is set. For CI, either feed the term list through an Actions secret written to a temp file and passed with `--deny-terms-file`, or state in the workflow comment that owner terms are only enforced locally.

### WR-02: History walk decides the vendor-file check from one path per blob

**File:** `scripts/prepublish_scan.py:431-436, 249-252`
**Issue:** `rev-list --objects` prints each object once, with the first path it meets, and `paths` keeps only that. `scan_blob` then applies the `tests/fixtures/` exemption and the vendor suffix test to that single path. A licence-restricted file committed under two names (for example once under `tests/fixtures/x.zip` and once as `downloaded_examples/x.zip`, or once as `notes.txt` and once as `part.step`) is judged by whichever path comes first. The second name, which is the one that makes it a vendor file in the published tree, is never evaluated.
**Fix:** Collect all paths per blob (walk `git log --all --raw --no-abbrev -z` or `git rev-list --all` with `ls-tree -r`) and flag `vendor_file` when any path is non-exempt and has a vendor suffix; or check the magic bytes independent of path as well.

### WR-03: The commit-msg hook is weaker than the scan that will later reject the history

**File:** `.githooks/commit-msg:9`; `scripts/split/build_tool_repo.py:71`; `scripts/prepublish_scan.py:106`
**Issue:** The scan treats a session trailer as `(?i)^\s*Claude-Session:` (any case, optional indent). The hook deletes only lines that start with exactly `Claude-Session:` at column 0, case-sensitive, and `clean_message` strips with a case-sensitive `startswith` after `lstrip()`. A line such as `claude-session: ...` or ` Claude-Session: ...` survives the hook, enters history, and then blocks every push at `session_trailer` with no way out except a history rewrite. The hook also matches the URL part case-sensitively (`claude\.ai/code/session`) while the scan's URL rule is case-insensitive.
**Fix:** Use `grep -v -i -E -e '^[[:space:]]*Claude-Session:' -e 'claude\.ai/code/session'` in the hook and `line.lstrip().lower().startswith(_TRAILER.lower())` in `clean_message`, so the hook is never weaker than the scan.

### WR-04: Text rules are skipped for any blob with a NUL in its first 8 KiB, for UTF-16 without a BOM, and for other encodings

**File:** `scripts/prepublish_scan.py:213-219`
**Issue:** `_decode` returns `None` (skip all text rules) when a NUL byte appears in the first 8192 bytes, and a UTF-16 file without a byte order mark always has NULs. Confirmed: `_decode("user@example.org".encode("utf-16-le"))` is `None`, and a text file that merely starts with a NUL byte gets no email, path, secret or term scan at all. Non-UTF-8 single-byte text is decoded with `errors="replace"`, which is fine for ASCII hits, but UTF-32 and UTF-16 without BOM are not handled. A `.txt` or `.json` that has the NUL trick is not a vendor suffix, so nothing else flags it.
**Fix:** Treat a blob as binary only when it is not decodable and the fraction of NUL bytes is high; additionally try `utf-16-le`/`utf-16-be` decoding when more than about 30 percent of the even or odd bytes are NUL, and scan the decoded text. At minimum report a non-vendor-suffix blob that is skipped as binary (a `binary_skipped` note on `--list-allowed`) so the skip is visible.

### WR-05: File names, folder names and ref names are not run through the text rules

**File:** `scripts/prepublish_scan.py:293-294, 393-400, 241-265`
**Issue:** `scan_ref` only matches `worktree-agent-`; a branch or tag name that contains an owner term, an email or a path never hits `owner_term`, `email` or `workstation_path`. Tracked path names are used only for the vendor suffix test and for the `where` column; a file called with the owner's name or a local path fragment passes. Both names are published.
**Fix:** In `scan_blob`/`tree_files` and `scan_ref`, pass the path or ref name through `_line_hits` and report the hits under the same rule names with `where` = `path` or `ref:<name>`.

### WR-06: Vendor-file detection is by suffix and two magic prefixes only

**File:** `scripts/prepublish_scan.py:47-65, 249-252`
**Issue:** Common licence-restricted or binary vendor deliverables slip past: `.tar.gz`/`.tgz`/`.gz`/`.xz`/`.bz2`, `.stl`, `.lbr`, `.olb`, `.bxl`, `.epw`, `.SchDoc`/`.PcbLib` families, `.xlsx`, `.csv` BOMs; a renamed 7z, gzip or PDF has no magic entry (only `PK\x03\x04` and `ISO-10303-21`). Anything under `tests/fixtures/` is exempt wholesale, and its binary content (a deflated zip, for instance) is also skipped by the text rules because it contains NUL bytes, so an archive placed there is never inspected at all.
**Fix:** Add the missing suffixes and magics (`\x1f\x8b`, `7z\xbc\xaf\x27\x1c`, `%PDF-`, `Rar!`), and for the fixtures exemption restrict it to the suffixes the fixtures really use (`.kicad_sym`, `.kicad_mod`, a named list) rather than the whole folder. Optionally open `.zip` blobs and run the text rules over their members (the corpus code already has the zip walking).

### WR-07: Workstation-path patterns miss WSL, URL-encoded and UNC spellings

**File:** `scripts/prepublish_scan.py:76-87`
**Issue:** Confirmed no hit for `/mnt/c/Users/bob/a` (the git-bash rule requires the character before `/c/` not to be a word character, and in `/mnt/c/` it is `t`), for `file:///C%3A/Users/bob/x`, and for `\\server\share\Users\bob`. The same gaps exist in `scrub.py`, so the export scrub leaves them in place.
**Fix:** Add `(?i)/mnt/[a-z]/(?:users|git_repo_clones)/`, a `%3[aA][/\\]+(?:users|git_repo_clones)` form, and `\\\\[^\\\s]+\\[^\\\s]+\\users\\`; extend `scrub.py` the same way.

### WR-08: `cutover_collection.py` reads its templates from inside the folder it is about to delete

**File:** `scripts/split/cutover_collection.py:66, 231-233, 301-306`
**Issue:** `TEMPLATES` is `Path(__file__).parent / "collection"`. If the script is started from the collection checkout itself (`--repo .` while `scripts/` is still tracked there, which it is before the cutover), the plan check at 231-233 passes, then `git rm -r ... scripts ...` deletes `scripts/split/collection/` from disk, and `shutil.copyfile` at 306 raises `FileNotFoundError` with nothing caught. The checkout is left half-applied: README.md, CLAUDE.md, code and planning removed from disk and index, no commit. It is recoverable (`git restore --staged --worktree .`), but this is the owner's live library checkout, and the script's own message at 251 does not cover an uncaught exception.
**Fix:** Read the three template files into memory in `plan()` (store the bytes on the plan) and write from those; additionally refuse in `plan()` when `TEMPLATES.resolve()` is inside `repo.resolve()`. Wrap the apply steps so an exception prints the recovery command.

### WR-09: The cutover never checks the safety net its messages promise

**File:** `scripts/split/cutover_collection.py:251, 315`; `scripts/split/cutover_collection.py:88-90, 360-364`
**Issue:** Messages say "The pre-split bundle and tag restore the previous state", but nothing verifies that a tag or bundle exists, that HEAD is that tag, or that the new tool repository has actually been pushed before the code leaves the collection. A subprocess timeout (`timeout=600` in `_git`) raises `subprocess.TimeoutExpired`, which only the first call in `main` is guarded against; later calls end in a traceback. When `_run` fails after the `--cached` untrack succeeded, the index is left with staged deletions and no hint how to undo them.
**Fix:** Add an explicit `--pre-split-tag NAME` (required with `--apply`) and refuse unless `git rev-parse NAME^{commit}` equals `HEAD`; catch `TimeoutExpired` in `_git`; print `git reset -q` as the way back when a step fails after staging.

### WR-10: `sync_planning.py` overwrites uncommitted work in the tool checkout and cannot see conflicts

**File:** `scripts/split/sync_planning.py:67-90`
**Issue:** For every added or modified allowed `.planning/` path the file is overwritten (line 82) and removed files are deleted (85), with no check that `--dest` is clean and no check that the destination copy changed since `--since`. The tool checkout is where planning is now edited (this checkout shows a modified `.planning/config.json`), so a sync after the tool repo's own edits silently replaces them with the private repo's version. The script says the caller commits, but by then the local edit is already gone from the working tree.
**Fix:** Refuse when `git -C dest status --porcelain -- .planning` is not empty, and skip (report `conflict <path>`) any file whose destination blob differs from the `since` version when the source also changed.

### WR-11: `build_tool_repo.py` writes any `--email` into the first public commit

**File:** `scripts/split/build_tool_repo.py:247, 221-228`
**Issue:** The identity is taken from the command line without any check, then set as local `user.email` and used for the commit. A personal address typed by mistake lands in a commit that is only caught later by the push scan, and only if the hook is enabled and the scan sees it (the local-config dependence in WR-01). The new repository also gets `core.hooksPath` but none of the `prepublish.*` keys, so its pre-push scan starts without owner terms.
**Fix:** Refuse (exit 2) an email that is not allow-listed by the scan's own rule (reuse `prepublish_scan.is_allowed_email` or a copy), with an explicit override flag, and print a reminder to set `prepublish.denyTermsFile` in the new clone.

### WR-12: `test_compare_reports_differences` assertions are satisfied by any diff line (reviewer B)

**File:** `tests/test_uri_diff.py:234`, `:239`, `:246`, `:252`
**Issue:** The four checks are `any("removed" in line and "C" in line ...)`, `"added"` with `"D"`,
`"changed"` with `"C"` and `"missing"` with `"B"`. A single capital letter is a substring of every line
that `scripts/split/uri_diff.py` prints, whatever entry it names. The `removed` and `added` lines carry the
URI (`${KICAD_LIB_GITHUB}/Custom/...`), which contains `C`, `D` (in `KICAD`) and `B` (in `GITHUB`). The
`missing` line carries the resolved path `<LIB>/Custom/...`, which contains `B` (in `LIB`). So `compare`
could report the wrong library as removed, added or missing and these assertions would still pass. The
exit-code checks are right, but the point of the test (the diff names the right entry) is untested, and
this is the tool that proves KiCad's tables resolve the same after the cutover (D-22).
**Fix:** Assert the full line, which the script builds as `removed: {table} {name} ({uri})`:
```python
assert "removed: sym-lib-table C (${KICAD_LIB_GITHUB}/Custom/C.kicad_sym)" in text.splitlines()
assert "added: sym-lib-table D (${KICAD_LIB_GITHUB}/Custom/D.kicad_sym)" in text.splitlines()
assert any(line.startswith("changed: sym-lib-table C: ") for line in text.splitlines())
assert any(line.startswith("missing (") and " sym-lib-table B -> " in line for line in text.splitlines())
```
and also assert that the other entries (`A`, and `B` or `C` where unaffected) do not appear in a
`removed`, `added`, `changed` or `missing` line.

### WR-13: Every behavioural test of the publishing controls is `slow`, so CI never runs it (reviewer B)

**File:** `tests/test_githooks.py:80`, `:91`, `:99`; `tests/test_prepublish_scan.py:290`;
`tests/test_cutover_collection.py:200`, `:229`, `:282`; `tests/test_split_export.py:359`, `:423`, `:457`;
`tests/test_ci_workflow.py:47`
**Issue:** The commit-msg session-line stripper (D-13), the pre-push block (D-09), the scan's exit codes
on a real repository, the cutover dry run, apply and refusals, and the export builder and planning sync
all carry `@pytest.mark.slow`. `ci.yml` runs only `python -m pytest --junitxml=junit.xml`, whose `addopts`
include `-m 'not slow'`, and `test_nothing_risky` forbids `--full` anywhere in the workflow text. So the
only security-control behaviour CI exercises is the unit-level part of the scan
(`scan_blob`, `scan_message`, ...) and the budget script. A regression in a hook or in the scan's CLI
passes CI and is found only when the owner runs `--full` by hand. The commit-msg hook does not need a git
repository at all (it takes a message file path), and the pre-push hook test does not need one beyond
`git rev-parse --show-toplevel`.
**Fix:** Give the cheap hook cases a quick form: run `sh .githooks/commit-msg <file>` directly against a
message file in `tmp_path` (no `git init`, so no `slow`), and run the pre-push stub case from a bare
`tmp_path` with a plain `git init` only if it must stay slow. For the genuinely git-bound tests, add a CI
step that runs just those modules with `--full` (for example
`python -m pytest --full tests/test_githooks.py tests/test_prepublish_scan.py tests/test_cutover_collection.py tests/test_split_export.py`)
and relax the `--full` text check in `test_nothing_risky` to allow exactly that step. Alternatively record
the decision that CI skips them and state in `tests/README.md` that they must be run before each publish.

### WR-14: The scan's history walk is never tested on a blob that left the tree (reviewer B)

**File:** `tests/test_prepublish_scan.py:290-337`
**Issue:** The only end-to-end test plants the workstation path in `notes.txt` and commits it, so the path
is in both the working tree and the history. The result (3 findings, deduplicated) is the same whether or
not `history_blobs` works, because the tree scan alone yields the `workstation_path` finding. The
`session_trailer` and `ref_name` findings prove the commit-message and ref walks, but nothing proves that a
secret or private path that was committed and then deleted or overwritten is still reported by
`--history`. That case is the reason the history scan exists (the public repo must have a clean history).
The orphan-branch step proves unreachable history is ignored, but not that reachable old blobs are read.
Also untested through `main`: `--tree` alone, `--history` alone, `--path`, `--deny-terms-file`,
`--deny-emails-from-repo`, and the `prepublish.*` git-config values the pre-push setup relies on (a missing
configured terms file must fail closed).
**Fix:** Extend `test_exit_codes_and_output` (or add a sibling test):
```python
# commit a planted path, then remove it in a later commit; the tree is clean, the history is not
(repo / "old.txt").write_text("path = " + planted + "\n", encoding="utf-8"); add, commit
_git(repo, "rm", "-q", "old.txt"); _git(repo, "commit", "-q", "-m", "drop old")
code, out = _scan(repo, "--tree");    assert code == 0, out
code, out = _scan(repo, "--history"); assert code == 1 and "workstation_path" in out
```
and add one case that sets `git config prepublish.denyTermsFile <missing file>` and expects exit code 2.

### WR-15: The corpus audit can be bypassed by common spellings, and its mark check is per module (reviewer B)

**File:** `tests/test_corpus_audit.py:20-22`, `:25-26`, `:135-147` (evidence: `tests/test_sexpr.py:666`, `:680`)
**Issue:** This audit is what keeps the public suite from reading repository data again (SPLIT-04), but:
1. `_ROOT` knows only `REPO_ROOT`, `REPO` and the literal `Path(__file__).resolve().parent.parent` /
   `parents[1]`. Four of the new modules name the repository root `ROOT` (`test_cutover_collection.py`,
   `test_split_export.py`, `test_uri_diff.py`, `test_githooks.py`), so `ROOT / "Custom"` is not seen. It
   also misses `Path(__file__).parent.parent` (no `resolve()`), `os.path.join(REPO_ROOT, "Custom")` and
   `REPO_ROOT / "Custom" / ...` written as one string.
2. `_DATA` requires the folder name to end at the closing quote, so `REPO_ROOT / "downloaded_examples/x.zip"`
   and `REPO_ROOT / "Custom/Symbols"` are not seen. The planted-path test covers none of these spellings.
3. The skip detector reads the reason only inside the balanced `skipif(...)` call. The old pattern
   `_SKIP = "... not present ..."` followed by `skipif(cond, reason=_SKIP)` (the style the removed
   `test_real_vendor_samples.py` code used) is not seen.
4. `test_corpus_readers_are_marked` passes a module when `pytest.mark.corpus` or `pytest.mark.wurth` appears
   anywhere in its text, not when each reader is marked. In `tests/test_sexpr.py`,
   `test_tokenizer_matches_reference_parser` reads `_custom_texts()` (line 666) with no mark. In a corpus run
   its input silently grows with the live `Custom/`, and a live part can fail it outside the marked health
   checks; the audit still passes because `test_reference_corpus_includes_the_custom_library_files` carries
   the mark.
No offender exists today (checked by grep), so this is a guard weakness, not a live bug.
**Fix:** Widen `_ROOT` to any identifier ending in `ROOT`/`REPO` (`\b\w*(?:ROOT|REPO)\b`), let `_DATA` match
the name followed by a quote or `/` (`["'](?:Custom|...)(?:["']|/)`), and add `os.path.join(` and
`Path(__file__).parent.parent` spellings with planted cases. For the skip detector, also flag any
`reason=<name>` whose constant is defined in the module with a matching text. For the mark rule, check per
function: collect functions (and module-level helpers they call) that reach `corpus_path` / `corpus_root`
or a module constant built from them, and require each test to carry `corpus` / `wurth`. At minimum mark
`test_tokenizer_matches_reference_parser`'s corpus part with a separate `@pytest.mark.corpus` test and make
the unmarked test use `ul + forms + noise` only.

### WR-16: The allow-list tests would not notice private local files being admitted (reviewer B)

**File:** `tests/test_split_export.py:66-97`, `:100-105`
**Issue:** `scripts/split/allowlist.txt` is the control for what leaves the private repository, and it
admits `tests/`, `scripts/`, `.github/` and `.githooks/` whole. The negative sample in
`test_allow_list_decisions` and the pattern in `test_allow_list_has_no_collection_content_line` name the
collection folders and the milestone, quick and debug notes, but not the owner-local files the checkout
actually holds: `CLAUDE.local.md`, `.claude/` (its `settings.local.json` is the example in the project
rules), `.env`, `junit.xml`, `env/`, or a deny-terms file. Someone adding `.claude/` or `CLAUDE.local.md`
to the allow-list, or a `!`-less prefix such as `CLAUDE` , would pass every test here (only the default-deny
case `stray.txt` is covered). `test_verify_export_flags_a_path_outside_the_list` has the same blind spot.
**Fix:** Add `CLAUDE.local.md`, `.claude/settings.local.json`, `.claude/anything`, `.env`, `junit.xml`,
`env/Scripts/python.exe` and `deny-terms.txt` to the `not allow.allowed(...)` list and to the `extra`
parametrization, and extend the shipped-list regex to refuse entries that start with `.claude`, `env/`, `.env`
or contain `.local.`:
```python
assert not re.search(r"(?i)(^|/)(\.claude|env|\.env)(/|$)|\.local\.|deny-terms", entry), entry
```

### WR-17: `test_a_raising_callback_does_not_stop_the_next_delivery` can still deliver `first` before the poll timer is stopped (reviewer C)

**File:** `tests/test_background.py:79-85`
**Issue:** The test needs both outcomes to sit in the queue until the single `dispatcher._drain()` call. `first` is started and the test then runs `qtbot.waitUntil(lambda: not first.is_running(), timeout=30000)`. `waitUntil` processes events between its polls, and the dispatcher's poll timer (`POLL_MS = 15` in `kicad_lib_manager/widgets/background.py:28`) is already running because `first` is pending. If the daemon thread has not finished by the first poll, which is likely on a loaded runner, the wait loop spins the event loop. The 15 ms timer then fires and `_drain` delivers `first` through `bad`, which raises into `sys.excepthook`. `first._finished` is now True, so `assert not first.is_done() and not second.is_done()` at line 85 fails. The timer is only stopped at line 83, after `second` has started. Raising 5000 to 30000 does not touch this; it is an ordering race, not a time budget. The same sequence also makes `reported` hold the exception before the intended drain.
**Fix:** Do not process events between starting `first` and stopping the timer. Wait on the thread's own event, which pumps nothing:
```python
first = run_in_background(lambda: 1, bad)
assert first._returned.wait(30)          # no event loop turn, so the 15 ms timer cannot fire
second = run_in_background(lambda: 2, got.append)
dispatcher._timer.stop()                 # add() restarts the timer, so stop it after the second start
assert second._returned.wait(30)
assert not first.is_done() and not second.is_done()
```

### WR-18: Two off-thread waits kept a 250 ms and a 1 s budget while their siblings went to 30 s (reviewer C)

**File:** `tests/test_new_collection_dialog.py:399`, `tests/test_help_dialog.py:1126`
**Issue:**
- `test_new_collection_dialog.py:399`: `qtbot.waitUntil(lambda: len(rec.checks) > calls, timeout=250)` waits for a check that runs on a daemon thread (`rec.checks` is appended on the worker). The 250 ms bound is meant to prove "not after the 300 ms debounce", but on a runner under xdist load, thread start plus the 15 ms poll can exceed 250 ms and fail the test without any product regression. The adjacent waits in this module (`settle`, line 100, and the `accepted` signals) were raised to 30000.
- `test_help_dialog.py:1126`: `qtbot.waitUntil(lambda: _expanded_page_keys(dialog) == expected, timeout=1000)` waits for the fold that follows a keyboard move. The page folding is event-loop driven and, as the neighbouring hunks show, needed 30 s of slack on CI (the `_heading_is_in_view` and `_current_key` waits in the same file). 1 s is the one budget in the file that was not raised.
**Fix:** For line 399, assert the intent directly and not through a tight clock. Wait with the 30 s budget for the check to appear, then assert it started before the debounce could have fired (for example by stopping or counting the debounce timer: `assert not dialog._debounce.isActive()` taken at the moment the check is seen). For line 1126, use `timeout=30000` like its neighbours.

### WR-19: Further small waits left in the same modules that the fix commits otherwise raised (reviewer C)

**File:** `tests/test_import_dialog.py:5111`, `tests/test_import_dialog.py:5153`, `tests/test_import_dialog.py:3538`, `tests/test_new_collection_dialog.py:146`, `tests/test_new_collection_dialog.py:239`, `tests/test_new_collection_dialog.py:255`, `tests/test_new_collection_dialog.py:257`, `tests/test_new_collection_dialog.py:426`, `tests/test_choose_folder_dialog.py:368`, `tests/test_first_run_dialog.py:138`, `tests/test_first_run_dialog.py:284`, `tests/test_main_window.py:2096`
**Issue:** A scan of every `waitUntil` / `waitSignal` call in the 21 modules (balanced-paren parse, not line grep) leaves these still under 30000 ms, or on pytest-qt's 5000 ms default:
- `test_import_dialog.py:5111` and `:5153` wait on `dialog.width() == width` with no timeout (5 s default). The identical wait in `resize_and_wait` (`:6289-6292`) was raised to 30000 by these commits.
- `test_import_dialog.py:3538` waits 5000 for a result-view layout (`_scroll.width() == view.width()`).
- `test_new_collection_dialog.py:239`, `:255`, `:257`, `:426` wait 3000 for a worker thread to record a check (the same `rec.checks` race as the bumped `:260`, `:337`, `:356`, `:371`, `:436` in the same file); `:146` is a 5 s default focus wait.
- `test_choose_folder_dialog.py:368`, `test_first_run_dialog.py:138` and `:284` wait 2000 for focus after `show()`, in modules whose other waits all went to 30000.
- `test_main_window.py:2096` is the worst of these: the wait runs inside a modal-box probe callback, with a 2000 ms budget, and a timeout there is swallowed into `seen["error"]` and only reported after the box is closed, which makes a CI slowdown look like a product failure in a different line.

These are the same kind of event-loop or thread-start dependent waits that turned CI red, so they are the next ones to flake.
**Fix:** Give each an explicit `timeout=30000` (for `:5111` and `:5153`, reuse `resize_and_wait(qtbot, dialog, width, 720)`). A shared module constant for the CI budget would keep this from drifting again.

### WR-20: Worker hold gates of 5 s are now shorter than the 30 s waits placed before the assertions that rely on the held state (reviewer C)

**File:** `tests/test_main_window.py:1613`, `tests/test_main_window.py:1617`, `tests/test_main_window.py:1620`, `tests/test_main_window.py:1662`, `tests/test_main_window.py:1664`, `tests/test_migration_dialog_run.py:143`
**Issue:** These tests hold the worker open with `gate.wait(5)`, then let the GUI side wait up to 30 s to reach the held state (for example the Skip button reading "Skip WurthElektronik" and enabled, in `test_skip_is_offered_while_symbols_are_read`, and the running page in `test_run_applies_on_a_worker_with_tag_first`). If the GUI is slower than 5 s to get there, the gate expires on its own, the worker runs on to the next phase (the button text changes, or the running page is left), and the awaited state is gone. The 30 s budget then gives no extra tolerance: the test fails at the 30 s timeout with a symptom unrelated to the cause. Raising the waits from 5000 to 30000 without raising the gate hold made the failure slower, not rarer. The gates that the test releases in a `finally` before any long wait (`test_main_window.py:542`, `:563`, `:643`, `test_main_window_migration.py:306`, `:579`) are not affected in practice, since the awaited state is already true when `waitUntil` starts.
**Fix:** Hold the gates for longer than the longest wait, for example `gate.wait(60)` (the tests always `set()` them in `finally`, so a long hold costs nothing on success), or make them `gate.wait()` with the existing `finally: ...set()` as the only release.

## Info

### IN-01: `uri_diff.py` resolves variables with the process environment as the lowest priority

**File:** `scripts/split/uri_diff.py:379-381`
**Issue:** The order is process environment, then `kicad_common.json`, then `--var`. As far as I know KiCad lets a variable defined in the operating system win over the config file, which is the reverse. Both snapshots in a before/after proof use the same order, so the comparison stays valid unless the shell environment differs between the two runs; the numbers shown for one snapshot may differ from what KiCad resolves. The snapshot also writes every non-library-root resolved path verbatim (for instance a KiCad install or a user folder) into `--out`; if that file is stored in an allow-listed planning folder, the scan will flag it.
**Fix:** Document the precedence in the docstring, and offer `--no-env` to ignore the process environment; normalise or redact paths under the user's home in the snapshot.

### IN-02: `tests/zipfixtures.py` builds the sample zip into the shared system temp at import time

**File:** `tests/zipfixtures.py:27`; `tests/ulfixtures.py:297-326`
**Issue:** `UL_ZIP = ul_sample_zip()` runs when any test module imports `zipfixtures`, in every xdist worker, and writes under `<system temp>/kicad_lib_manager_tests/<hash>/`. The module docstring (line 9) still says builders write only under the path the test passes. The parallel build itself is safe (content-addressed folder, per-process temp name, `os.replace` with a hash re-check), but an unwritable temp folder turns into a collection error for every module, and on a shared Linux `/tmp` the predictable folder can be pre-created by another user (a denial of service only, the content is hash-checked once at creation).
**Fix:** Build lazily (a function or a session fixture) and put the cache under a per-user folder (`tempfile.gettempdir()` plus the user name, or `tmp_path_factory.getbasetemp().parent` as `_git_template_root` does); fix the docstring.

### IN-03: `str.splitlines()` shifts reported line numbers

**File:** `scripts/prepublish_scan.py:224`, `:141`
**Issue:** `splitlines()` also splits on form feed, `\x1c`-`\x1e`, `\x85`, `U+2028` and `U+2029`, so the line number in a finding can differ from the editor's number for files that contain them. Not a correctness gap for detection, but it misleads whoever fixes the hit.
**Fix:** Split on `\n` (`text.split("\n")`, dropping a trailing `\r`).

### IN-04: `build_tool_repo.py` cleanup swallows its own failures and the scrub covers only `.planning`

**File:** `scripts/split/build_tool_repo.py:135-141, 196`
**Issue:** `_force_remove` ignores an `OSError` on the retry, so a failed clean-up of a rejected export leaves part of it on disk while the message says the destination was cleaned; the parent folders created by `mkdir(parents=True)` are never removed. Path scrubbing runs on `.planning` only; a workstation path in `CLAUDE.md`, `scripts/` or tests is left to the push scan.
**Fix:** Count and report what could not be removed; extend `scrub_tree` to `CLAUDE.md` and `README.md` or document that the scan is the only guard there.

### IN-05: `--min-passed 3500` is a bare constant in CI

**File:** `.github/workflows/ci.yml:38`
**Issue:** The floor has no stated relation to the suite size and the CI run deselects the `needs_kicad` and `corpus` tests, so the value is only right if someone measured it on a runner; it will silently drift or fail the first time tests are moved between markers. No other defect found in the workflow (permissions are read-only, a job timeout is set, the scan runs before pytest, `fetch-depth: 0` is set so the history scan sees all commits).
**Fix:** Record the measured count next to the number (a comment with the date) and review it when markers change.

### IN-06: `test_markers.py` cannot be collected on Python 3.10 (reviewer B)

**File:** `tests/test_markers.py:4`
**Issue:** `import tomllib` is at module level for the new `test_corpus_and_needs_kicad_are_registered`.
`tomllib` arrived in Python 3.11, while the project rules (`.claude/CLAUDE.md`, "Python 3.10+") and
`tests/README.md` ("`tomllib` missing on Python 3.10: `tests/test_manifests.py` skips through
`importorskip`") still treat 3.10 as supported. On 3.10 the whole module, including the older marker
meta-tests, fails at import. CI pins 3.14, so nothing fails today.
**Fix:** `tomllib = pytest.importorskip("tomllib")` inside the one test (import `pytest` at the top), or
state 3.11 as the new minimum in the README.

### IN-07: Dead loop in `test_read_only_git_allow_list_is_exact` (reviewer B)

**File:** `tests/test_markers.py:103-111`
**Issue:** Line 103 asserts `_READ_ONLY_GIT_TESTS == {}`, so the `for ident in _READ_ONLY_GIT_TESTS` loop below
can never execute. The test now reduces to checking that a dict literal is empty, and the loop is code for a
case the assertion forbids (the docstring says it is kept for a future test).
**Fix:** Drop the loop and the equality test, keep `_READ_ONLY_GIT_TESTS` and its use in
`test_requires_git_tests_are_slow`, and add the exactness check back when the first entry exists.

### IN-08: `test_ci_workflow.py` checks match comments and any step (reviewer B)

**File:** `tests/test_ci_workflow.py:22-26`, `:36-41`
**Issue:** The runner, Python version, `fetch-depth` and `timeout-minutes` checks are substring tests on the
whole file, so a commented-out line or a value in a different job satisfies them. `test_step_order` takes the
first occurrence of each command, so a second, earlier copy of the scan line (for example in a comment)
would pass while the real step moved. `permissions: contents: read` is matched only at the top level, so a
job-level `permissions:` that grants write is not seen.
**Fix:** Strip `#` comment lines before matching (`text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))`),
assert there is no `write` permission anywhere (`assert not re.search(r"(?m)^\s*\w[\w-]*:\s*write\s*$", text)`),
and require each command to occur exactly once.

### IN-09: `test_owner_choice_is_remembered_after_close_escape_and_parent_deleted` fixed the Escape branch but not the Close-button branch (reviewer C)

**File:** `tests/test_help_dialog.py:833-838`
**Issue:** The commit added `waitUntil(lambda: not dialog.isVisible())` before the Escape branch's assert, but the `how == "close"` branch two lines above still clicks the Close button and asserts `not dialog.isVisible()` immediately. If the close needed a wait on CI, so does this branch (the other close paths in the same file were all given one: `:1106`, `:964`). In production the Close button and Escape both end in `reject()`, so they cannot differ; the branches are simply inconsistent.
**Fix:** Add `qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=30000)` after the Close click, or factor a `_wait_hidden(qtbot, dialog)` helper used by every branch.

### IN-10: Debounce tests assert "nothing started yet" after a 100 ms wall-clock wait against a 300 ms debounce (reviewer C)

**File:** `tests/test_choose_folder_dialog.py:244-245`, `tests/test_new_collection_dialog.py:237-238`
**Issue:** Both tests type quickly, call `qtbot.wait(100)`, and assert `rec.calls == []` / `rec.checks == []` ("nothing before the 300 ms are over"). `qtbot.wait(100)` returns after at least 100 ms, not at 100 ms: on a stalled runner the main thread can be held longer than the 300 ms debounce, the timer then fires, the worker records a call, and the negative assertion fails. A negative assertion on elapsed time cannot be fixed by a longer timeout; it needs a clock-free form. These tests were not touched by the fix commits, but they sit directly beside waits that were.
**Fix:** Assert on state instead of on time: check that the debounce timer is still active (for example `assert dialog._debounce.isActive()` right after the last `setText`) and that no check task exists yet, then let `settle` run.

---

_Reviewed: 2026-11-26T11:13:00Z_
_Reviewers: Claude (gsd-code-reviewer), parts A, B and C merged by the orchestrator_
_Depth: standard_
