---
phase: "15"
slug: "choose-library-folder-and-new-collection"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-23"
---

# Phase 15 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Command line / environment → startup | `--library-root`, `KICAD_LIBMGR_ROOT` name the folder the app scans and writes | folder paths (untrusted input) |
| QSettings / KiCad config → app | remembered `library/root`, `library/recent`, KiCad's `KICAD_LIB_GITHUB` | stored paths that may be stale or tampered |
| App → owner's KiCad config | `KICAD_LIB_GITHUB` / `CUSTOM_3DMODEL_DIR` written to `kicad_common.json` | owner's KiCad settings (write needs Yes) |
| App → filesystem (New Collection) | folders and files created under a user-chosen parent | user's files (must never be overwritten or deleted) |
| App → git subprocess | `git init` and commit step | argv to an external program |
| Background threads → GUI thread | folder checks on daemon threads, results delivered on the GUI thread | check outcomes |

---

## Threat Register

Evidence (file:line or test) is in the gsd-security-auditor verdict of 2026-11-23; paths below are under `kicad_lib_manager/` unless they start with `tests/`.

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-15-SC | Tampering | package installs | high | mitigate | no dependency change in the phase (requirements.txt / pyproject unchanged); stdlib + PySide6 only | closed |
| T-15-01 | Tampering | startup override | high | mitigate | a failing CLI/ENV override is fatal (exit 2) before any window, never a fallback (collection.py resolve, startup.py; tests/test_startup.py, tests/test_collection.py) | closed |
| T-15-02 | Tampering | legacy fallback | medium | mitigate | `Source.LEGACY` only when the app folder is itself a collection (startup.py) | closed |
| T-15-03 | Denial of service | startup folder check | medium | mitigate | daemon thread with a 5 s join, then `no_answer` (startup.py) | closed |
| T-15-04 | Information disclosure | folder path shown | low | accept | see Accepted Risks | closed |
| T-15-05 | Tampering | `git init` argv | high | mitigate | allow-list, list argv, no shell, branch-name fullmatch (gitops.py; tests/test_gitops.py) | closed |
| T-15-06 | Elevation of privilege | git template hooks | medium | mitigate | `--template=` (gitops.py; real-git test with a hostile global template) | closed |
| T-15-07 | Tampering | ad-hoc process starts | medium | mitigate | `procs.run_process` is the only `subprocess.run` caller; AST guard tests/test_procs.py | closed |
| T-15-08 | Tampering | parent gitlink bump | high | mitigate | `_parent_mode` + `_precheck` refuse a bump for `none` before any write; panel hides the option (importer/commit_step.py, widgets/commit_panel.py) | closed |
| T-15-09 | Repudiation | unseen commit | low | accept | see Accepted Risks | closed |
| T-15-10 | Tampering | KiCad path variables after the relaxed refusal | high | mitigate | worktree refusal kept; no write without confirm (default No); re-read, backup, atomic write (library_scanner.py, main_window.py; tests/test_kicad_config.py) | closed |
| T-15-11 | Denial of service | walking `.git` | medium | mitigate | `.git` pruned at any depth in scanner and scan cache | closed |
| T-15-12 | Tampering | library planted in `.git` | low | mitigate | same pruning | closed |
| T-15-13 | Tampering | stored `library/*` values | medium | mitigate | type-guarded readers; every use re-checked (settings.py, startup.py, main_window.py) | closed |
| T-15-14 | Tampering | `KICAD_LIB_GITHUB` from KiCad config | medium | mitigate | non-blank str only; consumers check the folder before use (kicad_setup.py) | closed |
| T-15-15 | Tampering | collection name | high | mitigate | `validate_collection_name` (separators, control chars, trailing dot/space, `.git`, leading space, device names); parent identity check; re-validated in `create_collection` | closed |
| T-15-16 | Elevation of privilege | creation in Program Files / app folder | medium | mitigate | whole-path-part containment checks, re-run in `create_collection` | closed |
| T-15-17 | Tampering | data loss on create/cleanup | high | mitigate | refuses non-empty/existing; `mkdir` without exist_ok; `O_EXCL` files; cleanup removes only recorded paths, target `rmdir` only when empty | closed |
| T-15-18 | Repudiation | automatic commit | medium | mitigate | `create_collection` only runs `git init`; real-git test asserts no HEAD | closed |
| T-15-19 | Denial of service | dialog freeze on slow drive | low | mitigate | checks and creation on daemon threads with a request counter | closed |
| T-15-20 | Tampering | switch during a job | high | mitigate | `_switch_refusal` covers scan, import, migration, KiCad write, Check Atomic Parts; checked in request, switch and Choose | closed |
| T-15-21 | Tampering | KiCad config after a switch | high | mitigate | offer only when it would change, via the existing default-No confirm; never at a plain start | closed |
| T-15-22 | Spoofing | `&`/long names in Recent | low | mitigate | `&` doubled in display only, elided text, full path in tooltip/data | closed |
| T-15-23 | Elevation of privilege | Open Library Folder | low | mitigate | refuses when not a directory; only `QDesktopServices.openUrl(fromLocalFile)` | closed |
| T-15-24 | Tampering | stale check result | medium | mitigate | request counter drops older results | closed |
| T-15-25 | Denial of service | dialog freeze on unreachable drive | medium | mitigate | background check with a "Checking the folder..." state | closed |
| T-15-26 | Spoofing | markup in labels | low | mitigate | `PlainText` / `html.escape` in all three dialogs | closed |
| T-15-27 | Tampering | unchecked dialog result | medium | mitigate | dialogs return the checked path; callers re-check before switching | closed |
| T-15-28 | Tampering | `Custom` literal drift | medium | mitigate | AST guard tests/test_custom_literals.py; collection.py Qt-free and layered | closed |
| T-15-29 | Tampering | stored/foreign folder used unchecked | high | mitigate | every path goes through `check_folder` before `_switch_root` / start | closed |
| T-15-30 | Tampering | settings saved for an unconfirmed folder | medium | mitigate | `save_library_root` only after a usable check (two call sites) | closed |
| T-15-31 | Denial of service | first-run behind a modal | low | mitigate | resolve and first-run before the main window exists | closed |
| T-15-32 | Tampering | e2e test touching owner state | high | mitigate | conftest run-level digest guard, per-test isolation, live-Custom guard; tmp_path only | closed |
| T-15-33 | Information disclosure | docs naming owner paths | low | accept | see Accepted Risks | closed |
| T-15-34 | Tampering | importer `Custom` literal | medium | mitigate | per-module AST guard over the importer package | closed |
| T-15-35 | Denial of service | QThread abort at close | medium | mitigate | daemon-thread runner (widgets/background.py); close cancels without waiting; child-process exit tests | closed |
| T-15-36 | Tampering | late result after close | medium | mitigate | `cancel()` drops late outcomes; `_closing` + counter checks | closed |
| T-15-37 | Tampering | Qt touched off the GUI thread | medium | mitigate | worker only runs `fn` and enqueues; delivery from a GUI-thread QTimer drain; base exceptions and failed starts handled (WR-10) | closed |
| T-15-38 | Information disclosure (withheld) | clipped strip rows | low | mitigate | `fit_height_to_content`; geometry tests | closed |
| T-15-39 | Spoofing (misleading UI) | footnote over preview | low | mitigate | refit on draw/show/width change; geometry tests incl. 1.75 scale | closed |
| T-15-40 | Denial of service | parked QThreads in dialogs | medium | mitigate | dialogs on `run_in_background`; child modes and AST guard | closed |
| T-15-41 | Tampering | creation abandoned mid-write | medium | mitigate | creation never cancelled; every close path refuses while creating | closed |
| T-15-42 | Tampering | late dialog answer | low | mitigate | `_cancel_tasks()` + `_closing` + request counters | closed |
| T-15-43 | Tampering | Generate into the old folder | medium | mitigate | Destination follows the new folder when it was the old one or blank; history pruned off the GUI thread (WR-08) | closed |
| T-15-44 | Tampering | chosen Destination overwritten | medium | mitigate | follow only when blank or same spelling as the old root | closed |
| T-15-45 | Tampering | old saved scan reused | low | mitigate | scan cache FORMAT 3 checked before decode; strict flag decoding | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-15-01 | T-15-04 | The library folder path appears in the title, row and log: the user's own folder shown to the same user; nothing leaves the machine | plan 15-01 | 2026-11-23 |
| AR-15-02 | T-15-09 | A commit needs the Commit click in the panel that lists files and message; `run_commit` is reachable only from `commit_requested`; `create_collection` never commits | plan 15-03 | 2026-11-23 |
| AR-15-03 | T-15-33 | CLAUDE.md already names the owner's checkout paths and the repo visibility is decided in Phase 16; the User Guide uses generic examples only | plan 15-11 | 2026-11-23 |

*Accepted risks do not resurface in future audit runs.*

Deferred review hardening (non-gate, see 15-REVIEW-DISPOSITION.md): IN-03 (process-starter AST guard bypassable by aliases/QProcess — no such use today), IN-06 (GUI-thread-only contract of `run_in_background` documented, not enforced), IN-07 (brittle TaskWorker call-count guard).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-23 | 46 | 46 | 0 | gsd-security-auditor (ASVS L1, block on high; 651 targeted tests passed) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-23
