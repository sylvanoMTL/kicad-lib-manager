# Phase 14: Test Suite Speed-Up - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-22
**Phase:** 14-test-suite-speed-up
**Areas discussed:** New test dependencies, What bare pytest runs

---

## New test dependencies

| Option | Description | Selected |
|--------|-------------|----------|
| pytest-xdist 3.8.0 + pytest-timeout 2.4.0, stdlib lock | Recommended; no filelock, stdlib exclusive lock file for the git template | ✓ |
| Also add filelock | The pattern from the xdist docs | |
| xdist only | No timeout plugin | |

**User's choice:** Accept all
**Notes:** —

---

## What bare pytest runs

| Option | Description | Selected |
|--------|-------------|----------|
| Full suite, parallel | Bare pytest runs everything with xdist; quick run via -m "not slow"; GSD gate timeout raised | |
| Quick run, parallel | Bare pytest skips slow tests and fits the 600 s gate; full run is an explicit command | |
| Serial, as today | Bare pytest stays serial and complete; parallel runs are explicit | |
| You decide | Claude's discretion | ✓ |

**User's choice:** You decide
**Notes:** Claude chose the quick parallel run as bare pytest (see CONTEXT.md, Claude's Discretion).

---

## Decided autonomously

[auto] [Parallelism] — Q: "Worker count and distribution mode" → Selected: "Measure -n 4/6/8 with loadfile and worksteal, keep the fastest with ten identical runs, record it in pyproject" (reversible technical — decided autonomously: one addopts value)
[auto] [Parallelism] — Q: "Per-test timeout" → Selected: "pytest-timeout, thread method, 300 s default, explicit longer timeouts on known-long tests" (reversible technical — decided autonomously: config value plus markers)
[auto] [Markers] — Q: "What counts as slow" → Selected: "Real git, Würth corpus, kicad-cli, chosen from --durations" (reversible technical — decided autonomously: a marker on test functions)
[auto] [Isolation] — Q: "Real user state under parallel workers" → Selected: "Autouse fixture redirecting APPDATA, LOCALAPPDATA, HOME and QSettings, clearing KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR" (reversible technical — decided autonomously: test-only fixture)
[auto] [Isolation] — Q: "Git template fixtures under xdist" → Selected: "Built once per run under a stdlib lock in the shared base temp, removed at session end" (reversible technical — decided autonomously: local change in gitfixtures.py)
[auto] [Isolation] — Q: "Live Custom/ guard under xdist" → Selected: "Session-scoped guard runs in every worker" (reversible technical — decided autonomously: mechanism unchanged)
[auto] [Measurement] — Q: "Baseline" → Selected: "One serial --durations=50 run before any change, before/after times in the SUMMARY" (reversible technical — decided autonomously: documentation only)

## Claude's Discretion

- What bare pytest runs: the quick parallel run (-m "not slow" via addopts); the full run is an explicit documented command.

## Deferred Ideas

- GitHub Actions CI on Windows — Phase 16 / Phase 21.
