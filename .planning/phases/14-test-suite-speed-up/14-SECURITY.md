---
phase: "14"
slug: "test-suite-speed-up"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-23"
---

# Phase 14 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → dev venv | pytest-xdist, pytest-timeout (and execnet) installed into `env/` | third-party code run on every test run (exact pins) |
| Test process → owner's machine state | tests run beside the owner's real `%APPDATA%/KiCadExtLibManager`, KiCad config and live `Custom/` | settings, scan cache, backups, KiCad tables (owner data) |
| xdist workers ↔ shared run folder | workers share the git template, lock and timeout records under the run's base temp | test fixtures only |
| measure.py → committed logs | measurement logs and results committed to a repository that becomes public | pytest output tails (paths) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-14-SC | Tampering | pip install of pytest-xdist 3.8.0, pytest-timeout 2.4.0 (execnet 2.1.2) | high | mitigate | exact `==` pins in requirements-dev.txt; owner approved the three pytest-dev packages 2026-11-22 (14-CONTEXT.md); no other package added (tests/test_manifests.py) | closed |
| T-14-01 | Tampering | half-built git template read by another worker | medium | mitigate | `.done` marker written last (tests/gitfixtures.py:207); a failed build leaves no marker and is rebuilt (WR-01 fix 0877972) | closed |
| T-14-02 | Denial of service | lock file left by a dead worker | medium | mitigate | lock in this run's base temp; `_TEMPLATE_WAIT` 240 s then an AssertionError naming the lock (gitfixtures.py:153,210); delete-pending tolerated (WR-02 fix 7ba3f27) | closed |
| T-14-03 | Tampering | `pytest_sessionfinish` cleanup | medium | mitigate | removes only `<controller base temp>/git_templates` (conftest.py:225-235); no system-temp glob | closed |
| T-14-04 | Denial of service | a hung test stalling the run | medium | mitigate | `timeout = 300`, `timeout_method = "thread"` (pyproject.toml); hung meta-tests in tests/test_isolation.py | closed |
| T-14-18 | Repudiation | timeout record mis-attributing a crash | low | mitigate | record written by the firing timer in the run's own base temp, matched by node id (conftest hooks; test_isolation `-k hung`) | closed |
| T-14-05 | Repudiation | quick run silently losing coverage or building repos | low | mitigate | builder tripwire `_require_slow`; collection gate 7/58 for the three git-gated modules | closed |
| T-14-06 | Denial of service | orphan pytest workers after a measure.py timeout | medium | mitigate | new process group + `taskkill /T /F` / `os.killpg` (measure.py:225-286) | closed |
| T-14-07 | Information disclosure | measurement logs in a public repository | low | mitigate | only the last 300 lines kept, home folder redacted to `~` (measure.py:66,244; self-test line 797) | closed |
| T-14-08 | Repudiation | hand-picked timings | low | mitigate | verdicts computed from results.jsonl by measure.py; SUMMARY copies MEASUREMENTS.md | closed |
| T-14-16 | Elevation of privilege | Defender exclusion (MEASURE.md step 6 lever 2) | medium | mitigate | lever only with the owner's explicit yes; never applied — the contingency was not needed (half-of-baseline met) | closed |
| T-14-09 | Repudiation | marker rules drifting silently | low | mitigate | AST/collection audits in tests/test_markers.py; `measure.py slow-coverage` 0/0 | closed |
| T-14-19 | Tampering | `_RepoWatchPopen` changing app behaviour | low | mitigate | pass-through subclass, restored in `finally` after every test (conftest.py:143 ff.) | closed |
| T-14-10 | Tampering | a test writing the owner's real settings, cache, backups or KiCad config | high | mitigate | autouse `_isolated_user_state`; run-level app-state guard fails the run on a change (test_isolation `-k user_state_guard`) | closed |
| T-14-11 | Information disclosure | guard messages | low | mitigate | digests only; messages list paths, never contents | closed |
| T-14-12 | Tampering | KiCad config changed by the owner during a run | low | accept | warning only, see Accepted Risks | closed |
| T-14-17 | Information disclosure | tests reading the real KiCad config | medium | mitigate | `local_kicad` opt-in behind `KICAD_TEST_REAL_CONFIG=1`; `KICAD_CONFIG_HOME` per test (test_isolation kicad-cli test; local_kicad 2 passed / 1 skipped) | closed |
| T-14-13 | Tampering | a worker writing the live `Custom/` | high | mitigate | session guard `_live_custom_untouched` in every worker; xdist meta-test in tests/test_customfixtures.py | closed |
| T-14-14 | Tampering | hand-edited -n/--dist | low | mitigate | value from `measure.py choose`; `choose --check-pyproject` exits 0 at c89a726 | closed |
| T-14-15 | Information disclosure | test docs in a public repository | low | accept | see Accepted Risks | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-14-01 | T-14-12 | The owner may use KiCad during a long run, so a KiCad config change only warns (naming the files); tests' kicad-cli writes only the per-test KICAD_CONFIG_HOME | orchestrator decision under the owner's "You decide" (14-CONTEXT.md) | 2026-11-22 |
| AR-14-02 | T-14-15 | Docs describe commands and messages only; no personal paths beyond `%APPDATA%`-style variables | plan 14-06 | 2026-11-22 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-23 | 20 | 20 | 0 | secure-phase 14 (orchestrator, L1 grep-depth; register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-23
