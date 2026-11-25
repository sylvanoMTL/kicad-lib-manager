# Phase 16: Repo Split - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-24
**Phase:** 16-repo-split
**Areas discussed:** Direction & history, Visibility & identity, Licence & vendor data, Cutover/tests/dev workflow

---

## Direction & history

| Option | Description | Selected |
|--------|-------------|----------|
| Collection keeps history, tool gets a fresh one | kicad_libraries becomes the private collection (code removed in a final commit); new tool repo from an allow-listed copy, no filter-repo | ✓ |
| Collection keeps history, tool gets filtered history | Tool repo via filter-repo allow-list and scrubbing | |
| Tool keeps this repo's history | kicad_libraries becomes the public tool repo; collection a fresh git init | |

| Option (tool repo name) | Selected |
|--------|----------|
| kicad-lib-manager | ✓ |
| kicad-external-lib-manager | |
| You decide | |

| Option (.planning) | Selected |
|--------|----------|
| Carry a scrubbed current set (v3.0 + project docs; v1/v2 archives stay private) | ✓ |
| Carry all of it, scrubbed | |
| Keep it out of the public repo | |

| Option (branches) | Selected |
|--------|----------|
| Merge feature/part-importer first, push v2.0, drop agent branches | ✓ |
| Split from feature/part-importer as is | |

Follow-ups: collection name stays `kicad_libraries` ✓ (vs rename); collection final tree = libraries + collection docs only ✓ (vs also keeping .planning or reports/research_notes); venv moves to the tool checkout ✓ (vs keeping the old venvs).

---

## Visibility & identity

| Question | Options | Selected |
|----------|---------|----------|
| kicad_libraries visibility | Make private / Keep public | Make private |
| kicad_custom_library visibility | Make private / Keep public | Make private |
| Tool commit identity | noreply email + trailers (session URL dropped) / gmail as today / noreply, no trailers | noreply email + trailers |
| Blocking scan hits (multi) | Workstation paths, Owner email/name, Vendor files and part data, Secrets | All four |
| Real MPNs and Atomic_ names in fixtures | Allowed / Replace with made-up ones | Allowed |
| When the tool repo goes public | Create private, flip after scan / Create public directly | Create private, owner flips |

---

## Licence & vendor data

| Question | Options | Selected |
|----------|---------|----------|
| Tool licence | MIT / GPL-3.0-or-later / Apache-2.0 | MIT |
| ul_CSD85301Q2.zip | Synthetic builder replaces it / Keep the real zip | Synthetic builder |
| reports/ and research_notes/ | Leave out / Publish under docs/research/ | Leave out |
| Third-party content | README note only / Also THIRD-PARTY-NOTICES now | README note only |

---

## Cutover, tests & dev workflow

| Question | Options | Selected |
|----------|---------|----------|
| Tool checkout location | <tool-checkout>, retire worktree / keep this worktree path | kicad-lib-manager, retire worktree |
| Corpus tests | corpus marker opt-in via KICAD_TEST_CORPUS / skip when absent with budget | corpus marker |
| Skip budget | ≤ 10 skips, CI fails above / zero outside corpus / you decide | ≤ 10 |
| CLAUDE.md split | Tool + collection + untracked CLAUDE.local.md / tool keeps workstation paths | Tool + collection + local |
| CI | Quick run on push+PR windows-latest / plus nightly --full | Quick run on push+PR |
| KiCad check (multi) | Resolved-URI diff, 3D model path check, manual KiCad open, app rescan | Resolved-URI diff only |
| Rehearsal | Full dry run on --no-local clones / only risky git steps | Full dry run |

---

## Claude's Discretion

- Exact allow-list for the tool repo's first commit and the per-file .planning keep/drop list
- Scan implementation, pyproject metadata timing, README structure, how the Claude-Session line is kept out, plan order within the fixed sequencing

## Deferred Ideas

- THIRD-PARTY-NOTICES (Phase 21); nightly --full CI; extra KiCad checks; Python 3.14 metadata (Phase 20)
- Todo "migration dialog timers" reviewed, not folded
