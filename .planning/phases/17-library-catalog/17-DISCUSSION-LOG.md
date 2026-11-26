# Phase 17: Library Catalog - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-26
**Phase:** 17-library-catalog
**Areas discussed:** Where clones live, Update / licence / git, Catalog window & Add flow, Würth conversion (plus one folded todo)

---

## Todo cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| Leave it pending | Keep the migration-timers todo as a separate quick task | |
| Fold into Phase 17 | Add it as a small extra plan | ✓ |

## Where clones live

| Question | Options | Selected |
|----------|---------|----------|
| Clone location (D2) | `ThirdParty/<id>/` (Würth moves once) / `<Vendor>/<Repo>/` (Würth stays) | `ThirdParty/<id>/` |
| Manifest in git | App writes, never commits / Offer a confirmed commit / Git-ignored, local only | App writes, never commits |
| Add by URL licence and size | GitHub API, then confirm in staging / Staging clone only | GitHub API, then staging |
| Manifest entry, folder missing | Problem + Reinstall / Problem only | Problem + Reinstall |
| `ThirdParty/` folder not in manifest | Show as Problem, never touch / Ignore it | Show as Problem, never touch |

## Update, licence, git

| Question | Options | Selected |
|----------|---------|----------|
| Update method (D7) | fetch + reset on a clean tree / fetch + fast-forward only | fetch + reset on a clean tree |
| Licence gate (D11) | Warn + acknowledge / Refuse unknown licences / Show only | Warn + acknowledge |
| Minimum git (D6) | Warn, allow / Refuse below 2.49.1 | Warn, allow |
| Startup check | git ls-remote / GitHub API with ETag | git ls-remote |
| Git LFS | Refuse in staging / Warn, install anyway | Refuse in staging |
| Update preview | Fetch, then show the changes / Commit summary only | Fetch, then show the changes |
| Update all | Per library only / Update all + per library | Per library only |
| KiCad running | Warn, allow / Refuse while KiCad runs | Warn, allow |
| Disk space | Check and refuse if short / No check | Check and refuse if short |

## Catalog window & Add flow

| Question | Options | Selected |
|----------|---------|----------|
| Window kind | Non-modal window / Window-modal dialog | Non-modal window |
| Menu | File > Library Catalog... Ctrl+Shift+L / File, no shortcut / Toolbar button too | File + Ctrl+Shift+L |
| After Add | Rescan + path vars + Generate offer / Rescan only | Rescan + path vars + Generate offer |
| Update notice | Log line + menu badge / Log line only / Amber row in the folder bar | Log line + menu badge |
| Nickname collision | Warn; colliding libs start unchecked / Warn only / Block the Add | Warn; colliding libs start unchecked |
| Remove scope | Folder + manifest, tables via Generate / Also run Generate + unset vars | Folder + manifest, tables via Generate |
| Unverified curated entries | Verify each in this phase / Ship Würth + SparkFun only | Verify each in this phase |

## Würth conversion

| Question | Options | Selected |
|----------|---------|----------|
| Mechanism | Real catalog Add + scripted cleanup / In-app "Convert submodule" / Fully scripted | Real catalog Add + scripted cleanup |
| Rehearsal | Scratch copy first / Live only with a rollback tag | Scratch copy first |
| Pass check | Nickname set + 0 missing + 3D check / Rescan zero missing only | Nickname set + 0 missing + 3D check |
| Old submodule data | Move to the backup folder / Delete it | Move to the backup folder |

## Claude's Discretion

- Add by URL folder name, `catalog.json` schema, `.gitignore` line for `ThirdParty/`, disk-space margin, timeouts, Cancel process-tree kill, whether the conversion commit stages `catalog.json`, generalising the Würth-specific code and tests, User Guide and CLAUDE.md entries, plan order.

## Deferred Ideas

- Update all; tag/commit pinning; remote curated list; GitLab hosts; atomic quality report for third-party clones; unsetting path variables on Remove.
