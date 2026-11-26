---
phase: 16-repo-split
verified: 2026-11-26T12:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .githooks/commit-msg
  - .githooks/pre-push
  - .github/workflows/ci.yml
  - .planning/phases/16-repo-split/16-01-PLAN.md
  - .planning/phases/16-repo-split/16-01-SUMMARY.md
  - .planning/phases/16-repo-split/16-02-PLAN.md
  - .planning/phases/16-repo-split/16-02-SUMMARY.md
  - .planning/phases/16-repo-split/16-03-PLAN.md
  - .planning/phases/16-repo-split/16-03-SUMMARY.md
  - .planning/phases/16-repo-split/16-04-PLAN.md
  - .planning/phases/16-repo-split/16-04-SUMMARY.md
  - .planning/phases/16-repo-split/16-05-PLAN.md
  - .planning/phases/16-repo-split/16-05-SUMMARY.md
  - .planning/phases/16-repo-split/16-06-PLAN.md
  - .planning/phases/16-repo-split/16-06-SUMMARY.md
  - .planning/phases/16-repo-split/16-07-PLAN.md
  - .planning/phases/16-repo-split/16-07-SUMMARY.md
  - .planning/phases/16-repo-split/16-08-PLAN.md
  - .planning/phases/16-repo-split/16-08-SUMMARY.md
  - .planning/phases/16-repo-split/16-09-PLAN.md
  - .planning/phases/16-repo-split/16-09-SUMMARY.md
  - .planning/phases/16-repo-split/16-10-PLAN.md
  - .planning/phases/16-repo-split/16-10-SUMMARY.md
  - .planning/phases/16-repo-split/16-11-PLAN.md
  - .planning/phases/16-repo-split/16-11-SUMMARY.md
  - .planning/phases/16-repo-split/16-12-PLAN.md
  - .planning/phases/16-repo-split/16-12-SUMMARY.md
  - .planning/phases/16-repo-split/16-13-PLAN.md
  - .planning/phases/16-repo-split/16-13-SUMMARY.md
  - .planning/phases/16-repo-split/16-14-PLAN.md
  - .planning/phases/16-repo-split/16-14-SUMMARY.md
  - .planning/phases/16-repo-split/16-15-PLAN.md
  - .planning/phases/16-repo-split/16-15-SUMMARY.md
  - .planning/phases/16-repo-split/16-16-PLAN.md
  - .planning/phases/16-repo-split/16-16-SUMMARY.md
  - .planning/phases/16-repo-split/16-17-PLAN.md
  - .planning/phases/16-repo-split/16-17-SUMMARY.md
  - .planning/phases/16-repo-split/16-18-PLAN.md
  - .planning/phases/16-repo-split/16-18-SUMMARY.md
  - CLAUDE.md
  - LICENSE
  - README.md
  - kicad_lib_manager/collection.py
  - pyproject.toml
  - scripts/check_skip_budget.py
  - scripts/prepublish_scan.py
  - scripts/split/cutover_collection.py
  - scripts/split/uri_diff.py
  - tests/ulfixtures.py
  - tests/zipfixtures.py
covered_digest: "v4:sha256:23f6493456cb3390c85162b85d62439fe5c342fd2731545daeabc2062893c103"
behavior_unverified: 0
overrides_applied: 0
re_verification: false
gaps: []
human_verification:
  - test: "Start the Library Manager the way it will be started from now on (from the tool checkout, `.\\env\\Scripts\\python.exe kicad_lib_manager.py`, with the owner's real settings), then open KiCad's Symbol and Footprint library managers."
    expected: "The Library folder row shows the main checkout of the collection with the tag `KiCad's folder` or `your choice`; the scan lists the Custom and WurthElektronik libraries; KiCad lists the same libraries as before the split and none is marked missing."
    why_human: "Needs the owner's real settings and a running KiCad GUI. The resolved-URI compare (identical, 428 entries, 0 missing) and the headless scan below are the automated proof; this is the owner's own confirmation (plan 16-15 task 3 human-check, recorded as pending in 16-15-SUMMARY.md and 16-16-SUMMARY.md)."
  - test: "Before the next `git push` of the tool checkout: rewrite the local unpushed commit that holds workstation paths (blob of `.planning/phases/16-repo-split/16-15-SUMMARY.md` in commit 917e3ec, scrubbed later in c5b3a8e), for example by folding c5b3a8e into 917e3ec, then confirm `python scripts/prepublish_scan.py --tree --history` exits 0 on the local repository."
    expected: "The local history scans clean, so the pre-push hook lets the 11 unpushed documentation commits and this report through."
    why_human: "History rewrite of the owner's local branch is the owner's call. The pre-push hook is working as designed and refuses the push; nothing of the finding is on GitHub."
---

# Phase 16: Repo Split Verification Report

**Phase Goal:** The app code lives in a public tool repo that holds nothing private, and the owner's libraries live in a private collection repo with no code, while the owner's KiCad keeps working exactly as before
**Verified:** 2026-11-26
**Status:** human_needed
**Re-verification:** No, initial verification

All automated evidence supports the goal. The one open decision is the owner's own look at KiCad's library managers, which no script can make. One local, unpushed history problem needs the owner's attention before the next push (see Anti-Patterns and Human Verification). Paths below are repo-relative or placeholders: `<tool-checkout>`, `<main-checkout>` (the collection's main checkout), `<backup-folder>`.

## Goal Achievement

### Observable Truths (ROADMAP success criteria, the contract)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | The tool repo holds the app code, tests, pyproject, planning and build scripts and no library content; the collection repo holds `Custom` and the third-party libraries and no code | VERIFIED | Tool repo: `git ls-files` shows only `kicad_lib_manager/`, `kicad_lib_manager.py`, `tests/`, `scripts/`, `.planning/`, `.githooks/`, `.github/`, `pyproject.toml`, requirements, README, LICENSE, CLAUDE.md. No `.gitmodules`, no `Custom/`, no `WurthElektronik`, no `downloaded_examples`, no zip, step, wrl, pdf or `.pretty` entry in the tree or in any commit (`git log --all --name-only`). The only `.kicad_sym`/`.kicad_mod` files are 9 tiny synthetic fixtures under `tests/fixtures/sexpr/` (checked: `FIX_R`, `Fixture_Lib:FIX_FP`). `Source.LEGACY` and `REPO_ROOT` are gone from `kicad_lib_manager/`; `collection.check_folder` classifies the tool checkout as `not_collection`. Collection (read-only look at the main checkout): `HEAD` = `origin/main` = 4f39aa9 ("Remove the app code"), tracked entries are exactly `.gitignore`, `.gitmodules`, `CLAUDE.md`, `README.md` and the gitlinks `Custom` and `WurthElektronik`; no `.py`, `.toml`, `.github` anywhere in it or in `Custom`. |
| 2 | The owner's KiCad keeps working after the split: every table URI resolves, zero missing libraries before and after | VERIFIED (automated); owner's GUI confirmation pending | `scripts/split/uri_diff.py compare` of the live records `<backup-folder>/live/uri-before.json` and `uri-after.json`: "identical, 428 entries, 0 missing". A fresh snapshot of KiCad's current global tables taken today compared with `uri-before.json`: "identical, 428 entries, 0 missing" (output kept in the session scratchpad only). The 6 disabled WurthElektronik symbol entries whose files are absent appear as notes on both sides; the owner accepted them in 16-13 (a disabled entry is never loaded). Headless: `collection.check_folder(<main-checkout>)` = `collection`; `scan_all(<main-checkout>)` lists 412 symbol and 44 footprint libraries, the same as the 16-15 smoke start. The KiCad GUI view is human item 1. |
| 3 | The visibility of both GitHub repos is decided and set, and a pre-publish scan of the tool repo's full history finds no owner paths, vendor downloads, part data or other private or licence-restricted content | VERIFIED for what GitHub holds; local unpushed history does NOT scan clean (WARNING) | `gh repo view`: `kicad-lib-manager` PUBLIC (licence MIT), `kicad_libraries` PRIVATE, `kicad_custom_library` PRIVATE. `git ls-remote origin` = 967688b, equal to `<backup-folder>/live/final-refs.txt`. I cloned GitHub's copy fresh (5 commits, 416 files) and ran `scripts/prepublish_scan.py --tree --history` with the owner deny-terms file and the commit emails of the collection repo: `clean (416 files, 440 blobs, 5 commits)`. CI run 45672175120 on 967688b ran the same scan: `clean (416 files, 440 blobs, 5 commits)`. My own grep over every revision of that clone for `C:/Users`, the owner's user name and personal mail domains found only the scan's own pattern text; every address in it is `noreply`, `example.invalid` or similar; no vendor zip or library file at any depth. All 5 commits are authored by the GitHub noreply identity; the only `Co-Authored-By` trailers are the permitted ones; no `Claude-Session`. Local branch: see the Anti-Patterns row and human item 2. |
| 4 | A fresh clone of the tool repo, without the collection, passes the test suite within a stated skip budget, with a synthetic sample in place of the TI vendor zip | VERIFIED | CI run 45672175120 (windows-latest, clone of GitHub, no collection, no KiCad): `4004 passed, 1 skipped`, `deselected: 41 corpus`, `deselected: 15 needs_kicad`, `skip budget: 4004 passed, 1 skipped (max 10), 0 failed, 0 errors` (`scripts/check_skip_budget.py ... --max-skips 10 --min-passed 3500`). 16-11 recorded 4013 / 3 skipped with KiCad and 3998 / 3 without. The TI download is replaced by `tests/ulfixtures.py` (all member bodies written from scratch) behind `tests/zipfixtures.UL_ZIP`; no real download exists in the tree or history. I ran the 11 Phase 16 modules myself (`test_ci_workflow`, `test_corpus_audit`, `test_corpus_gate`, `test_cutover_collection`, `test_docs_split`, `test_githooks`, `test_legacy_rules`, `test_prepublish_scan`, `test_skip_budget`, `test_split_export`, `test_uri_diff`): 114 passed. The orchestrator's separate run (354 passed without the collection, 9 corpus tests passed with `KICAD_TEST_CORPUS`) is consistent. The code and tests of the local HEAD equal GitHub's 967688b (`git diff origin/main HEAD` touches only `.planning/`). |
| 5 | The tool repo has a chosen licence, a README covering install and first run, the developer docs and the documented dev workflow; the collection README covers naming, the atomic rule and the path variables | VERIFIED | Tool repo: `LICENSE` is MIT, GitHub reports `mit`; `README.md` has Install, First run, Choosing or creating a collection, Development (tests, `--library-root`, `KICAD_LIBMGR_ROOT`, hooks) and Libraries and licences sections; `CLAUDE.md` has a Dev Workflow section (main checkout for real use and corpus, scratch collections for development and tests, `KICAD_TEST_CORPUS`, `KICAD_TEST_HIDE_KICAD`); `tests/README.md` documents markers and the skip budget; `tests/test_docs_split.py` passes. Collection (`<main-checkout>`): `README.md` has "KiCad configuration" (`KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR`), "Naming and the atomic rule" (`Atomic_<stem>`, `Atomic_Footprints`, the rule list) and "Working with the library manager"; `CLAUDE.md` has KiCad Path Variables, Library Naming Convention, Importing Parts, Git Workflow; neither holds a workstation path or email. |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified). Two owner actions remain (Human Verification).

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `LICENSE`, `README.md`, `CLAUDE.md`, `pyproject.toml` | Public tool-repo docs and config | VERIFIED | Present in GitHub's copy and the local tree, substantive, no private content |
| `.github/workflows/ci.yml` | Windows CI: scan, quick tests, skip budget | VERIFIED | Last run on main green |
| `scripts/prepublish_scan.py`, `scripts/check_skip_budget.py` | Gate tooling | VERIFIED | Wired in CI and `.githooks/pre-push`; tests pass; the scan detected the local problem described below |
| `scripts/split/uri_diff.py`, `cutover_collection.py` and the export scripts | Split tooling, proof of KiCad unchanged | VERIFIED | `uri_diff.py compare` run by me against the live records and a fresh snapshot |
| `tests/ulfixtures.py`, `tests/zipfixtures.py` | Synthetic UL sample | VERIFIED | Built from scratch; used by the Bucket A modules |
| `kicad_lib_manager/collection.py` | Library root is chosen, never the code folder | VERIFIED | Run against both folders: collection accepted, tool checkout refused |
| Collection `README.md`, `CLAUDE.md`, `.gitignore`, `.gitmodules` | Docs and gitlinks, no code | VERIFIED | Tracked tree is exactly these plus two gitlinks |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Tool app | Collection | `--library-root`, `KICAD_LIBMGR_ROOT`, saved choice, `KICAD_LIB_GITHUB` | WIRED | `check_folder` and `scan_all` ran against the main checkout: 412 symbol, 44 footprint libraries |
| KiCad tables | Collection files | `${KICAD_LIB_GITHUB}`, `${CUSTOM_3DMODEL_DIR}` | WIRED | 428 resolved entries identical before and after, today too |
| Pre-push hook | Scan | `.githooks/pre-push` runs `scripts/prepublish_scan.py --tree --history` | WIRED | Currently refuses the local branch (correct behaviour, see below) |
| CI | Skip budget | `ci.yml` steps | WIRED | Budget line present in the run log |

### Data-Flow Trace (Level 4)

Not applicable: the phase moves files and docs and adds gates; no rendered dynamic data. The scan of the collection above shows the app reads real library content from the split-out folder.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| URI compare, before vs after | `scripts/split/uri_diff.py compare uri-before.json uri-after.json` | identical, 428 entries, 0 missing | PASS |
| URI compare, before vs today | `uri_diff.py snapshot` of KiCad's current tables, then `compare` | identical, 428 entries, 0 missing | PASS |
| Collection recognised | `collection.check_folder(<main-checkout>)` / `(<tool-checkout>)` | `collection` / `not_collection` | PASS |
| Collection scanned | `scan_all(<main-checkout>)` | 412 symbol libraries, 44 footprint libraries | PASS |
| GitHub copy scan | `prepublish_scan.py --tree --history` in a fresh clone | clean (416 files, 440 blobs, 5 commits) | PASS |
| Phase 16 test modules | `pytest` on the 11 modules | 114 passed | PASS |
| Local repo scan | `prepublish_scan.py --tree` / `--history` | tree clean (421 files); history 5 `workstation_path` findings | see Anti-Patterns |

### Probe Execution

The phase declares probes by name only through the scan and uri_diff scripts exercised above; no `scripts/*/tests/probe-*.sh` exists. SKIPPED (no probe scripts).

### Requirements Coverage

All eight IDs appear in the PLAN frontmatter (`requirements:`) and in the SUMMARY `requirements-completed:` lists; none is orphaned.

| Requirement | Source Plans | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| SPLIT-01 | 16-04, 16-12, 16-14 | Public tool repo, no library content | SATISFIED | Truth 1 |
| SPLIT-02 | 16-05, 16-12, 16-13, 16-15 | Private collection, no code, KiCad unchanged | SATISFIED (automated); owner GUI confirmation pending | Truths 1 and 2 |
| SPLIT-03 | 16-03, 16-04, 16-11, 16-12, 16-14, 16-16 | History holds nothing private or restricted | SATISFIED for the public repo; local unpushed history needs a rewrite before the next push | Truth 3 |
| SPLIT-04 | 16-01, 16-03, 16-06, 16-08 to 16-12, 16-14, 16-17, 16-18 | Suite passes from a fresh clone within a skip budget | SATISFIED | Truth 4 |
| SPLIT-05 | 16-05, 16-07, 16-15 | Docs split | SATISFIED | Truth 5 |
| SPLIT-06 | 16-07 | Licence and README | SATISFIED | Truth 5 |
| SPLIT-07 | 16-13, 16-16 | Visibility decided and set | SATISFIED | Tool repo PUBLIC, `kicad_libraries` and `kicad_custom_library` PRIVATE (read through `gh`) |
| SPLIT-08 | 16-02, 16-07, 16-11, 16-14 | Dev workflow documented | SATISFIED | `CLAUDE.md` Dev Workflow, README Development |

Note for the orchestrator: `.planning/REQUIREMENTS.md` still shows SPLIT-01 to SPLIT-08 as `[ ]` / Pending; update the checkboxes and the traceability table when this phase is closed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `.planning/phases/16-repo-split/16-15-SUMMARY.md` (blob of local commit 917e3ec) | 93, 97, 103, 119, 133 | `workstation_path` found by `prepublish_scan.py --history` | WARNING | Local history only. Commit 917e3ec is one of 11 unpushed local commits; c5b3a8e scrubbed the text later, so `--tree` is clean, but history still holds the first version. GitHub's main (967688b) does not contain it (verified by a fresh clone and scan). The pre-push hook will refuse the next push until the local history is rewritten. This does not make SPLIT-03 fail for the public repo; it must be fixed before the phase's remaining 11 documentation commits and this report are pushed. |
| `scripts/prepublish_scan.py` | n/a | Open review findings CR-01 (annotated tag objects not scanned) and CR-02 (a path or email right after a JSON escape sequence is invisible) in `16-REVIEW.md`, disposition open | WARNING | The scan is the instrument behind SPLIT-03. It is not proven to be exhaustive. Compensation done in this verification: an independent `git grep` over every revision of GitHub's copy for owner paths, user name and personal mail domains found nothing, and the repo has no tags. Advisory, not blocking. |
| Debt markers (TBD, FIXME, XXX) | n/a | Not searched in Phase 16 code beyond the review | INFO | Review 16-REVIEW.md lists no unreferenced marker as critical; not re-scanned here. |

### Human Verification Required

#### 1. KiCad sees the same libraries, started from the tool checkout

**Test:** Start the app from the tool checkout with the owner's real settings (`.\env\Scripts\python.exe kicad_lib_manager.py`), then open KiCad's Symbol and Footprint library managers.
**Expected:** The Library folder row shows the main checkout with the tag `KiCad's folder` or `your choice`; the scan lists the Custom and WurthElektronik libraries; KiCad lists the same libraries as before the split, none marked missing (apart from the 6 disabled WurthElektronik symbol entries the owner already accepted).
**Why human:** Real settings and a running KiCad; the URI compare is the required automated proof and passes. Carried over from plan 16-15 task 3 (`<human-check>` harvested from the plan).

#### 2. Make the local history pushable

**Test:** Rewrite the local branch so commit 917e3ec no longer holds the first version of `16-15-SUMMARY.md` (fold c5b3a8e into it), then run `python scripts/prepublish_scan.py --tree --history` in the tool checkout.
**Expected:** exit 0; the pre-push hook then accepts the push.
**Why human:** Rewriting the owner's local unpushed history is the owner's decision. Nothing private is on GitHub.

### Gaps Summary

No gap blocks the phase goal. The goal holds on the evidence: the public repo (GitHub 967688b) holds only code, tests, docs and planning, scans clean over its full history, passes CI from a fresh clone with 4004 passed and 1 skipped against a budget of 10, and the owner's KiCad tables resolve identically (428 entries, 0 missing) before the split, after it and today. Visibility is set (tool repo public, both library repos private). Status is `human_needed` because the owner has not yet confirmed the KiCad GUI view and because the local unpushed history must be cleaned before the next push.

---

_Verified: 2026-11-26_
_Verifier: Claude (gsd-verifier)_
