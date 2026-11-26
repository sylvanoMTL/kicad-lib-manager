---
phase: "16"
slug: "repo-split"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-26"
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| licence-restricted vendor downloads → public test code, logs and results | the real downloads are local data; only their shape may reach `tests/`, and a test must not pass (or skip quietly) only because a download sits in the checkout | vendor file content (licence-restricted) |
| private repository and owner workstation → public tool repository | the first commit, every later commit, commit messages and docs cross here | owner paths, emails, private terms, session URLs |
| repository content → scan output | the scan reads private and untrusted bytes and writes a log that may be public (CI) | rule and place only |
| GitHub Actions marketplace → CI job | third-party action code runs with the job's token | read-only token |
| test suite → the owner's collection | with `KICAD_TEST_CORPUS` set, corpus tests read the collection KiCad uses | live library files (read-only) |
| split scripts and session → the checkout KiCad reads, KiCad's configuration | the URI proof reads KiCad's tables; the merge and remove-code commit land in the owner's live library folder | owner's live libraries and KiCad settings |
| session → GitHub | visibility changes and pushes are outward-facing | repository visibility and history |
| importer worktree → deletion | ignored local data, submodule repositories and reflog-only commits lived only there | local-only data |
| code checkout → library folder | the folder the app's code lives in must never become the folder it writes tables and parts into | library writes |
| xdist workers → shared temp file | several worker processes build and read the same generated zip | test fixture bytes |

---

## Threat Register

Register authored at plan time (a `<threat_model>` block in all 18 plans); no SUMMARY raised a new threat flag. Evidence was checked at grep depth (ASVS L1) on 2026-11-26 in the tool checkout; the live-run mitigations (T-16-22..T-16-36) are evidenced by the 16-12..16-16 SUMMARYs and the records in the backup folder's `live/`, which sits outside every repository.

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-16-SC | Tampering | package installs (all plans) | high | mitigate | no new package; `requirements.txt` / `requirements-dev.txt` hold only the existing pins (PySide6, pytest, pytest-qt, pytest-xdist, pytest-timeout); CI installs `requirements-dev.txt` (`.github/workflows/ci.yml:32`) | closed |
| T-16-01 | Information disclosure | `tests/ulfixtures.py` member bodies | high | mitigate | bodies written from scratch; `test_fixture_originality` and `test_builders_share_no_three_line_window` (`tests/test_vendorfixtures.py:141`, `:175`); scan rule `copied_content` | closed |
| T-16-02 | Denial of service | `ul_sample_zip()` under xdist workers | medium | mitigate | content-addressed target, temp name plus `os.replace` (`tests/ulfixtures.py:302`), `PermissionError` retry with a hash re-check (`:320`); `test_sample_zip_build_survives_a_held_open_target` (`tests/test_ulfixtures.py:94`) | closed |
| T-16-03 | Tampering | startup resolve order | medium | mitigate | `Source.LEGACY` and the code-folder candidate deleted (no match under `kicad_lib_manager/`); `test_code_folder_collection_is_never_used` (`tests/test_startup.py:153`), `test_source_has_four_members` (`tests/test_collection.py:216`); the app-folder refusal is kept (`kicad_lib_manager/collection.py:411`) | closed |
| T-16-04 | Information disclosure | scan output | high | mitigate | `format_finding` prints rule and place only (`scripts/prepublish_scan.py:124`); `test_owner_email_and_terms` (`tests/test_prepublish_scan.py:72`) | closed |
| T-16-05 | Information disclosure | `scripts/prepublish_scan.py` source | high | mitigate | owner identity read at run time (`--deny-emails-from-repo`, `--deny-terms-file`, the clone's local git config); home-folder rules built from pieces so the script never matches itself; tree scan of the tool checkout clean (418 files) | closed |
| T-16-06 | Tampering | `.github/workflows/ci.yml` | medium | mitigate | `permissions: contents: read` (`ci.yml:6`), official actions by major tag, no `pull_request_target`, no `secrets.` reference; `tests/test_ci_workflow.py` (4 tests) | closed |
| T-16-07 | Information disclosure | binary and oversized blobs | medium | mitigate | vendor suffix and magic checks on every blob (`VENDOR_MAGICS`); a blob over the 20 MB cap is a `large_blob` finding (`scripts/prepublish_scan.py:39`, `:69`) | closed |
| T-16-08 | Denial of service | regex scanning of untrusted blobs | low | mitigate | line-by-line matching with bounded quantifiers and no nested repetition; 20 MB cap per blob | closed |
| T-16-09 | Information disclosure | `build_tool_repo` export | high | mitigate | allow-list export from a git ref, gitlink refusal (`scripts/split/build_tool_repo.py`), `HARD_DENY` and `REQUIRED` checks (`scripts/split/verify_export.py:25`, `:40`); verify and full scan before the first push (16-12, 16-14) | closed |
| T-16-10 | Information disclosure | commit messages in the tool repo | high | mitigate | tracked commit-msg hook strips the session line (`test_commit_msg_strips_the_session_line`, `tests/test_githooks.py:82`); `session_trailer` rule over history; the pre-push hook runs `--tree --history` (`.githooks/pre-push:25`) | closed |
| T-16-11 | Tampering | scrub of exported text | low | mitigate | the scrub touches `.planning/` text only, idempotent and byte-safe (`test_scrub_is_idempotent_and_byte_safe`, `tests/test_split_export.py:167`) | closed |
| T-16-12 | Denial of service | `cutover_collection` apply (owner's KiCad) | high | mitigate | dry run by default, explicit remove list, gitlink / `.gitmodules` / remote post-checks, refusals before any write (`test_apply_keeps_gitlinks_and_untracks_samples`, `test_refusals`, `tests/test_cutover_collection.py:231`, `:284`); live run only after the bundles, the `pre-split` tag and the owner's decision (16-13, 16-15) | closed |
| T-16-13 | Tampering | `uri_diff` reading KiCad's folder | medium | mitigate | read-only opens, output only to `--out`, refused when it would overwrite an input (`test_nothing_is_written_to_the_tables_folder`, `tests/test_uri_diff.py:337`) | closed |
| T-16-14 | Denial of service | untracked data in the collection | high | mitigate | no `git clean` or `reset` in `scripts/split/cutover_collection.py`; `downloaded_examples` untracked with `--cached` so the files stay | closed |
| T-16-15 | Repudiation | public results green by skipping | high | mitigate | gated tests are deselected with a printed count, a wrong `KICAD_TEST_CORPUS` is a usage error (`test_corpus_closed_deselects_with_a_count`, `test_wrong_corpus_is_a_usage_error`, `tests/test_corpus_gate.py:45`, `:80`); CI skip ceiling and passed floor (`scripts/check_skip_budget.py`) | closed |
| T-16-16 | Tampering | the corpus collection's `Custom/` during a corpus run | high | mitigate | `_live_custom_untouched` guards `<corpus>/Custom` in every worker (`tests/conftest.py:638`; `test_guard_watches_the_corpus_custom`, `tests/test_corpus_gate.py:107`) | closed |
| T-16-17 | Information disclosure | LICENSE, README.md, CLAUDE.md | high | mitigate | the copyright holder is the GitHub handle (`LICENSE:3`); `test_docs_hold_no_workstation_path` (`tests/test_docs_split.py:132`); workstation specifics live in the ignored `CLAUDE.local.md` | closed |
| T-16-18 | Tampering | corpus `Custom/` during the 16-08 corpus run | high | mitigate | the tests only read; the 16-06 guard watches `<corpus>/Custom`; the corpus runs of 2026-11-26 printed no guard failure | closed |
| T-16-19 | Information disclosure | real vendor data in the public tree | high | mitigate | corpus-only reads through `corpus_path`; originality and shared-window tests; `downloaded_examples/*` ignored with no `!` exception (`.gitignore:33`); scan rules `vendor_file` and `copied_content` | closed |
| T-16-20 | Repudiation | `needs_kicad` deselection hiding failures | medium | mitigate | deselected with a printed count (`test_hidden_kicad_deselects_needs_kicad`, `tests/test_corpus_gate.py:125`); the workstation run executes them against KiCad 10 | closed |
| T-16-21 | Repudiation | audit false negatives, a proof run that still sees private data | medium | mitigate | detectors proven on planted lines (`tests/test_corpus_audit.py`); fresh-clone runs with `downloaded_examples` deleted and `Custom` empty (16-11); the budget check enforces a ceiling and a floor | closed |
| T-16-22 | Tampering | scratch clones pushing to GitHub | high | mitigate | origin removed on the source clone, push URL `DISABLED` on the collection clone, nothing pushed (16-12 SUMMARY) | closed |
| T-16-23 | Information disclosure | deny-terms file | high | mitigate | written by the owner in the backup folder, which is outside every repository (rechecked 2026-11-26); passed by path only, never printed or copied (16-12 SUMMARY) | closed |
| T-16-24 | Tampering | KiCad's configuration and the main checkout during the rehearsal | high | mitigate | only copies of the KiCad files were snapshotted; the main checkout was only read (16-12 SUMMARY) | closed |
| T-16-25 | Denial of service | merge into `main` of the checkout KiCad reads | high | mitigate | read-only preflight, owner decision, verified bundles of both repos first, fast-forward (16-13 SUMMARY) | closed |
| T-16-26 | Elevation of privilege | visibility change without consent | high | mitigate | only after the owner's go, with `--accept-visibility-change-consequences`, verified PRIVATE with `gh repo view` (16-13 SUMMARY) | closed |
| T-16-27 | Information disclosure | pushing `v2.0` and the merged `main` to a public repo | medium | mitigate | both collection repos made private before any push (16-13 SUMMARY); both still PRIVATE on 2026-11-26 | closed |
| T-16-28 | Information disclosure | the first push of the tool repo | high | mitigate | `verify_export` and the full scan (owner emails, deny terms, corpus) before the push; owner decision on the listing; created private; a fresh clone of GitHub's copy scanned clean (16-14 SUMMARY) | closed |
| T-16-29 | Elevation of privilege | making the tool repo public | high | mitigate | created with `--private` (16-14); the flip was the owner's own action after the final scan (16-16); PUBLIC on 2026-11-26 | closed |
| T-16-30 | Information disclosure | `CLAUDE.local.md`, `.claude/`, `env/` in the tool checkout | medium | mitigate | all three ignored (`git check-ignore`, 2026-11-26); the pre-push hook scans every later push (see the audit note below) | closed |
| T-16-31 | Denial of service | remove-code commit in the checkout KiCad reads | high | mitigate | drift check against the baseline, dry run, owner decision, the script's post-checks, URI compare identical with 0 missing before the push, the `pre-split` bundle and tag as the way back (16-15 SUMMARY) | closed |
| T-16-32 | Tampering | acting on the wrong checkout | high | mitigate | MAIN equal to KiCad's `KICAD_LIB_GITHUB` and to the tool checkout's `prepublish.denyEmailsFromRepo` (16-15 Task 1) | closed |
| T-16-33 | Information disclosure | owner settings touched by the smoke start | low | mitigate | offscreen smoke start with every user folder, QSettings and `KICAD_CONFIG_HOME` redirected to scratch folders (16-15 SUMMARY) | closed |
| T-16-34 | Denial of service | worktree removal losing local data | medium | mitigate | read-only inventory first; downloads copied with equal SHA-256; the old memory folder moved, not deleted; branch tips and bundles keep the history (16-16 SUMMARY) | closed |
| T-16-35 | Information disclosure | the flip publishing an unscanned history | high | mitigate | final scan of a fresh clone of GitHub's copy, CI green on that commit, refs unchanged since the scan: `live/final-refs.txt` equals `git ls-remote` of GitHub's copy on 2026-11-26 (`main` at 967688b) | closed |
| T-16-36 | Tampering | acting on a stale or unapproved removal list | high | mitigate | the owner's answer recorded in `retire-decision.txt` before acting; the inventory retaken and compared (`retire-recheck.txt`) (16-16 SUMMARY) | closed |
| T-16-37 | Repudiation | 16-17 modules green only because the real zip is present | medium | mitigate | the verify commands moved the real zip out first; no test reads the real download path (the remaining mentions of the file name are the synthetic builder's `UL_ZIP_NAME`, `tests/ulfixtures.py:28`, and dialog-label assertions); the 16-11 static audit | closed |
| T-16-38 | Repudiation | 16-18 modules green, or quietly skipped, because of the real zip | medium | mitigate | as T-16-37; the vendor-sample `skipif` is deleted (no match in `tests/`) | closed |
| T-16-39 | Information disclosure | kept `.planning` files | high | mitigate | the 16-11 Task 3 keep-set scan; full scans of the exported tree (16-12, 16-14) and of GitHub's copy (16-16); tree scan of the tool checkout clean on 2026-11-26 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

*Accepted risks do not resurface in future audit runs.*

**Audit note (follow-up for the owner, not an open threat).** On 2026-11-26 the history pass of `scripts/prepublish_scan.py` reports 5 `workstation_path` findings, all in the blob of `.planning/phases/16-repo-split/16-15-SUMMARY.md` committed in 917e3ec, the version from before the scrub in c5b3a8e. The tree pass is clean. 917e3ec is one of the local commits not yet on GitHub (GitHub's `main` is still 967688b), so nothing private was published. The tracked pre-push hook runs `--tree --history` and will refuse the next push until that blob is out of the unpushed history, for example by squashing the unpushed commits so the unscrubbed version is not reachable. That rewrite is the owner's call.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-26 | 40 | 40 | 0 | secure-phase orchestrator, grep-level check (ASVS L1, block on high; short-circuit: register authored at plan time, 0 open, so no auditor spawn); 354 requirement tests passed without the collection, 9 corpus tests with it; scan tree clean, history 5 findings in one unpushed commit (audit note) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-26
