---
phase: "16"
slug: "repo-split"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-24"
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-qt 4.5.0 + pytest-xdist 3.8.0 + pytest-timeout 2.4.0 (`requirements-dev.txt`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.\env\Scripts\python.exe -m pytest` |
| **Full suite command** | `.\env\Scripts\python.exe -m pytest --full` (corpus: set `KICAD_TEST_CORPUS` to the collection folder first) |
| **Estimated runtime** | ~100 seconds (quick), ~7 min (`--full`) |

---

## Sampling Rate

- **After every task commit:** Run `.\env\Scripts\python.exe -m pytest tests/<touched modules> -n 0 -q -p no:cacheprovider`, plus `python scripts/prepublish_scan.py --tree` once the scan script exists
- **After every plan wave:** Run `.\env\Scripts\python.exe -m pytest`
- **Before `/gsd-verify-work`:** fresh-clone quick run (no `downloaded_examples/`, no collection) green and within the skip budget; corpus run green on the workstation; scan exit 0 on the exported tree and on GitHub's copy; URI diff identical with 0 missing
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Filled in by the planner and the executor from the plans. Requirement-level map from research:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| SPLIT-01 | exported tool tree is a subset of the allow-list, no `Custom`/`WurthElektronik`/`downloaded_examples` | script check + unit | `python scripts/split/verify_export.py <dir> --allow-list scripts/split/allowlist.txt`; `pytest tests/test_split_export.py --full` | ✅ | ✅ green |
| SPLIT-02 | before/after resolved URI lists identical, zero missing | script + unit | `pytest tests/test_uri_diff.py tests/test_cutover_collection.py --full`; `python scripts/split/uri_diff.py compare before.json after.json` | ✅ | ✅ green |
| SPLIT-03 | blocking classes detected; clean export exits 0 | unit + slow git-history test | `pytest tests/test_prepublish_scan.py tests/test_githooks.py --full`; `python scripts/prepublish_scan.py --tree --history` | ✅ | ✅ green |
| SPLIT-04 | fresh clone without collection passes within budget | CI + local fresh clone | `pytest --junitxml=junit.xml` then `python scripts/check_skip_budget.py junit.xml ...`; `pytest tests/test_skip_budget.py tests/test_ci_workflow.py` | ✅ | ✅ green |
| SPLIT-04 | corpus deselection prints counts; bad `KICAD_TEST_CORPUS` fails | meta-test | `pytest tests/test_corpus_gate.py tests/test_markers.py tests/test_corpus_audit.py` | ✅ | ✅ green |
| SPLIT-04 | UL builder adapter-compatible and deterministic | unit | `pytest tests/test_vendorfixtures.py tests/test_ulfixtures.py tests/test_zipfixtures.py` (the real-sample structure check runs under `corpus`) | ✅ | ✅ green |
| SPLIT-05/06/08 | LICENSE, README install/first run, collection docs, dev workflow | doc check | `pytest tests/test_docs_split.py tests/test_cutover_collection.py`; `tests/test_startup.py`, `tests/test_collection.py` for the start without the code folder | ✅ | ✅ green |
| SPLIT-07 | visibility set | manual | `gh repo view <repo> --json visibility` | manual | ✅ checked 2026-11-26: `kicad-lib-manager` PUBLIC, `kicad_libraries` and `kicad_custom_library` PRIVATE |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Per-plan map (from the PLAN files, 2026-11-24; the Wave 0 files above are created by these plans, so every task has an automated verify):

| Plan | Tasks | Requirement | Automated verify (summary) |
|------|-------|-------------|----------------------------|
| 16-01 | 2 | SPLIT-04 | `tests/test_ulfixtures.py`, `test_adapters.py`, `test_zipfixtures.py`; then the 31 Bucket A modules with the real zip moved out: the 18 that reach the sample through zipfixtures on the generated zip as it is, the 12 with their own path (plus `test_snapeda_adapter`, `test_suggest_atomic`) on a copied-in stand-in |
| 16-02 | 2 | SPLIT-08 | `tests/test_startup.py`, `test_collection.py`; window, help and grammar tests |
| 16-03 | 3 | SPLIT-03, SPLIT-04 | `tests/test_prepublish_scan.py` (quick and slow), `test_skip_budget.py`, `test_ci_workflow.py`; code-area keep-set scan |
| 16-04 | 3 | SPLIT-01, SPLIT-03 | `tests/test_split_export.py` (quick and slow), `tests/test_githooks.py` (slow); scan of its own files (wave 2, after 16-03) |
| 16-05 | 2 | SPLIT-02, SPLIT-05 | `tests/test_uri_diff.py`, `tests/test_cutover_collection.py` (quick and slow) |
| 16-06 | 2 | SPLIT-04 | `tests/test_corpus_gate.py`, `test_markers.py`, `test_isolation.py`, `test_manifests.py`; HIDE run |
| 16-07 | 2 | SPLIT-05, 06, 08 | `tests/test_docs_split.py`; test_docs_atomic.py gone |
| 16-08..16-10 | 2 each | SPLIT-04 | converted modules with `KICAD_TEST_CORPUS=` blank and set to the feature checkout; `KICAD_TEST_HIDE_KICAD=1` |
| 16-11 | 3 | SPLIT-03, 04, 08 | `tests/test_corpus_audit.py`; fresh-clone quick runs plus `check_skip_budget.py` with and without KiCad; corpus run; kept-planning keep-set scan (every rule but workstation_path) |
| 16-12 | 3 | SPLIT-01..04 | `verify_export.py`, `prepublish_scan.py`, budget, `uri_diff.py compare`, ls-tree, corpus run (scratch) |
| 16-13..16-16 | 3 each (16-16: 4, two of them checkpoints) | SPLIT-01, 02, 03, 04, 05, 07, 08 | bundle verify, `gh repo view` visibility, ls-remote, `uri_diff.py compare`, ls-tree, CI conclusion, final scan of GitHub's copy, retirement inventory sections, recorded owner decision, refs unchanged since the final scan |
| 16-17 | 2 | SPLIT-04 | wave 2: `test_samacsys_adapter`, `test_gate_reasons`, `test_generated_text`, `test_official_footprint`, `test_roundtrip_corpus`, `test_kicad_files`, `test_edits` with the real zip moved out |
| 16-18 | 2 | SPLIT-04 | wave 2: `test_import_dialog`, `test_import_form`, `test_main_window_import`, `test_install_gate`, `test_install_e2e`, `test_suggest_atomic`, `test_snapeda_adapter` with the real zip moved out, no sample skip |

---

## Wave 0 Requirements

- [x] `tests/test_prepublish_scan.py`, `scripts/prepublish_scan.py`
- [x] `tests/test_corpus_gate.py` (marker, deselection count, bad `KICAD_TEST_CORPUS`)
- [x] `tests/test_skip_budget.py`, `scripts/check_skip_budget.py`
- [x] `tests/test_uri_diff.py`, `scripts/split/uri_diff.py`
- [x] `tests/test_docs_split.py` (replaces the `test_docs_atomic.py` cases that read the split docs; `test_docs_atomic.py` is gone)
- [x] UL builder tests in `tests/test_vendorfixtures.py`, plus the corpus originality test
- [x] Framework install: none (pins already in `requirements-dev.txt`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Both existing repos set private | SPLIT-07 | owner-confirmed outward-facing change | `gh repo view sylvanoMTL/kicad_libraries --json visibility`, same for `kicad_custom_library` |
| Tool repo flipped public | SPLIT-07 | the owner flips it (D-12) | `gh repo view sylvanoMTL/kicad-lib-manager --json visibility` after the owner's flip |
| KiCad still loads libraries from the main checkout | SPLIT-02 | live KiCad config; the URI diff is the required proof (D-22) | run the URI diff before and after the live split from the main checkout |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the six owner checkpoints in 16-12..16-16 are human gates by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-26 (validate-phase audit: 0 gaps; the requirement tests pass, 354 without the collection and 9 more with `KICAD_TEST_CORPUS` set to the main checkout)

## Validation Audit 2026-11-26

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
