---
phase: "17"
slug: "library-catalog"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-27"
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + pytest-qt + pytest-xdist + pytest-timeout (`requirements-dev.txt`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `env/Scripts/python.exe -m pytest tests/<module>.py -n 0` (one module); whole quick run `env/Scripts/python.exe -m pytest` |
| **Full suite command** | `env/Scripts/python.exe -m pytest --full` (one slow module: `env/Scripts/python.exe -m pytest tests/<module>.py --full -n 0`) |
| **Estimated runtime** | ~90 seconds (quick), ~7 min (`--full`) |

Real git (`file://` bare repositories) only runs in `@pytest.mark.slow` tests (the conftest tripwire fails any non-slow test that starts `git init` / `git clone`). The quick run covers the catalog logic through pure functions, a `FakeNet` for the add / update / remove / reinstall state machines, recording-starter argv tests for `catalog/gitnet.py`, and real Python child processes for `procs.StreamedProcess`. See `17-RESEARCH.md` § Validation Architecture.

---

## Sampling Rate

- **After every task commit:** Run the task's own test module(s) with `-n 0`
- **After every plan wave:** Run `env/Scripts/python.exe -m pytest` (quick run); after a wave that adds or edits slow modules, also run those modules with `--full -n 0`
- **Before `/gsd-verify-work`:** `env/Scripts/python.exe -m pytest --full` must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled from the PLAN files during execution) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

New test modules named in `17-RESEARCH.md` § "Phase Requirements -> Test Map" (`test_catalog_*.py`, `test_gitnet.py`, `test_procs_stream.py`, `test_scan_catalog.py`, `test_wurth_convert.py`, `test_main_window_catalog.py`), the `make_third_party` builder beside `tests/collectionfixtures.make_collection`, the `FakeNet` fixture and the slow `file://` bare-repo builder. New slow modules are added to the "run before every publish" list in `tests/README.md`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-network clone, scan, 3D paths and path variables of Würth, SparkFun, Alternate-KiCad-Library | CAT-09 | Tests never use the network (D-22, owner-run) | Add each through the real catalog on the owner's machine; record pass/fail and reason |
| Würth conversion rehearsal and live run with the three pass checks | CAT-12 | Touches the owner's main checkout KiCad reads (D-24..D-27) | Rehearsal on a `--no-local` copy with a scratch KiCad config, then the live run behind the rollback tag |
| Git Credential Manager window does not appear for a private URL | CAT-11 | Could open a window on the owner's desktop | Owner runs the command recorded in `17-RESEARCH.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
