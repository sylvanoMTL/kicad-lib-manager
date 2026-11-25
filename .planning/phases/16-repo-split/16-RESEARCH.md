# Phase 16: Repo Split - Research

**Researched:** 2026-11-24
**Domain:** splitting one git repo into a public Python/PySide6 tool repo and a private KiCad library collection; pytest corpus gating; pre-publish leak scan; Windows CI; KiCad URI proof
**Confidence:** HIGH for the in-repo findings (measured in a throwaway `git clone --no-local` of this worktree this session); MEDIUM for GitHub Actions details (documentation-cited, not run); LOW only where tagged `[ASSUMED]`.

Note on this file: it is carried into the public tool repo with the rest of `phases/16-*`, so it goes through the same scrub as CONTEXT.md (D-09). It writes no owner email address or full name; where one matters it says "the owner's commit email". The verbatim constraints block below still holds one workstation path (D-17), which the scrub step replaces with a placeholder.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Direction and history (D1, D13)
- **D-01:** The existing `sylvanoMTL/kicad_libraries` becomes the **private collection**. It keeps its full history (all 1,812 commits, the `Custom` and `WurthElektronik/KiCad-Library` gitlinks, `.gitmodules`, tags `v1.0`/`v2.0`). The code is removed in one final "remove app code" commit. KiCad's checkout keeps its git identity and remote. — **Reversibility:** costly — undoing means re-adding the code tree and repointing every dev workflow doc
- **D-02:** The tool repo is a **new repo with a fresh history**. Its first commit is an **allow-listed copy** of today's tree (named paths only, so anything unnamed is absent), not a filtered history. `git filter-repo` is not used. — **Reversibility:** one-way — once public, the first commit's content can't be recalled; the allow-list and the scan (D-09) are the guard
- **D-03:** Tool repo name: **`kicad-lib-manager`** (matches the package `kicad_lib_manager`).
- **D-04:** Collection repo name stays **`sylvanoMTL/kicad_libraries`**, with no remote change in the main checkout.
- **D-05:** `.planning/` in the tool repo is a **scrubbed current set**: `PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `state.json`/`config.json` as needed for GSD, `research/`, `codebase/`, `todos/` and the v3.0 phase dirs (`phases/14-*`, `15-*`, `16-*`), with workstation paths replaced by placeholders. The v1/v2 milestone archives (`milestones/`), `quick/`, `debug/`, `MILESTONES.md`/`RETROSPECTIVE.md` (if they carry v1/v2 detail) stay **only** in the private collection's history. The planner decides the exact allow-list per file after a content pass.
- **D-06:** **Before the split:** merge `feature/part-importer` into `main`, push the `v2.0` tag to `kicad_libraries`, delete the 8 stray `worktree-agent-*` branches (local), and split from `main`.
- **D-07:** The collection's final tree keeps only the `Custom` gitlink, the `WurthElektronik/KiCad-Library` gitlink, `.gitmodules`, `.gitignore` (env/, generated `sym-lib-table`/`fp-lib-table`, backups, `downloaded_examples/*`), a **collection README** and a **short collection CLAUDE.md**. It removes `kicad_lib_manager/`, `kicad_lib_manager.py`, `tests/`, `pyproject.toml`, `requirements*.txt`, `.planning/`, `reports/`, `research_notes/`, `.gitattributes` if it is code-only, and the tracked `downloaded_examples/ul_CSD85301Q2.zip` (the file stays on disk as untracked local data).
- **D-08:** Venvs: the tool checkout gets its **own `env/` (Python 3.14, PySide6 6.12)**. The main checkout's `env/` and `env-py311/` are deleted only after the new venv runs the app against the main checkout.

#### Visibility and identity (D14)
- **D-09:** Pre-publish scan of the tool repo (working tree and the full history it will push). **Blocking hits:**
  - workstation paths (`<home>`, `<repos-folder>`, AppData paths, in both slash styles);
  - the owner's email addresses (every address in `git log --format=%ae` of the old repo plus the git config) and the owner's full name (the GitHub handle `sylvanoMTL` is allowed);
  - vendor files and part data: any `.zip`, `.step`/`.stp`/`.wrl`, `.kicad_sym` or `.kicad_mod` outside `tests/fixtures`, and copied Custom symbol or footprint content;
  - secrets (tokens, keys, credential-looking strings, as a gitleaks-style pattern set).
  The scan is a script in the tool repo, run locally, in CI (D-20), and as the exit criterion before the flip to public. — **Reversibility:** one-way — a miss is published
- **D-10:** Public manufacturer part numbers (e.g. CSD85301Q2, USB4145-03-0170-C) and the generic `Atomic_<KiCad stem>` library names in fixtures (e.g. `CURRENT_ATOMIC_SYMBOL_LIBS`) are **allowed**. Only real vendor files and copied Custom content are blocked.
- **D-11:** **`kicad_libraries` → private** and **`kicad_custom_library` → private**, set with `gh repo edit --visibility private` (owner-confirmed step). The main checkout then fetches `Custom` with the owner's credentials (Git Credential Manager). CLAUDE.md/PROJECT.md wording about "private" becomes true. — **Reversibility:** reversible
- **D-12:** The tool repo is **created private**. The scan and a fresh-clone test run happen against what GitHub holds, then the **owner flips it to public** as the last step. Claude does not flip it.
- **D-13:** The tool repo's commit identity is **`sylvanoMTL` with the GitHub noreply email** (`<id>+sylvanoMTL@users.noreply.github.com`), set locally in that repo (`git config user.email`, not global). `Co-Authored-By: Claude ...` trailers are kept. The **`Claude-Session` URL line is dropped** from commits pushed to the public repo (the attribution lines for this repo omit it; the GSD commit helper or a commit-msg hook in the tool checkout strips it).

#### Licence and vendor data (D10, D12)
- **D-14:** Licence: **MIT** (`LICENSE` at the root, with SPDX `license = "MIT"` in pyproject when the metadata is added). It covers the code only.
- **D-15:** `ul_CSD85301Q2.zip` is replaced in the public repo by a **synthetic builder** in `tests/`. It produces an Ultra-Librarian-shaped zip with the same folder layout, file kinds and quirks the UL adapter relies on. The `ul_package` fixture uses the builder. The real zip stays local in the collection's `downloaded_examples/` and is used only by the opt-in corpus run (D-17). — **Reversibility:** reversible
- **D-16:** `reports/` and `research_notes/` are **left out** of the tool repo. They stay in the private collection's history only.
- **D-16b:** The tool README carries a short note: the tool ships no libraries; libraries you add keep their own licences (KiCad CC-BY-SA, Würth's own terms); test fixtures are synthetic. No THIRD-PARTY-NOTICES in this phase (Phase 21).

#### Cutover, tests and dev workflow
- **D-17:** Tool checkout at **`<tool-checkout>`**, a plain clone with its own `env/` and a local GSD install (`.claude/` stays gitignored). The `Kicad_Libraries-importer` worktree is **retired** (`git worktree remove`) once the tool checkout passes its tests. Claude's auto-memory for this project moves to the new project path.
- **D-18:** Tests that need real vendor samples, the Würth corpus or the live `Custom/` get a registered **`corpus` marker** and run **only when `KICAD_TEST_CORPUS` names a collection folder** (the owner's main checkout). Otherwise they are **deselected** (reported as a separate count), never quietly skipped. Every other test that today reads `Custom`, `WurthElektronik`, `downloaded_examples`, `.planning` or `REPO_ROOT /` is rebuilt on synthetic fixtures, or deleted when it only tested this repo's layout. Each of the ~25 affected modules is classified in the plan. The existing `wurth` marker folds into or sits beside `corpus` (planner's call).
- **D-19:** **Skip budget:** a fresh-clone quick run has **at most 10 skips** (room for the `kicad_cli`/`local_kicad` skips on a machine without KiCad). Corpus tests don't count, since they're deselected. CI fails above the budget.
- **D-20:** **Windows CI:** GitHub Actions on `windows-latest`, on push and PR. One job runs bare `pytest` (the quick parallel run, no corpus, no KiCad), the skip-budget check and the pre-publish scan script. No `--full` in CI.
- **D-21:** **CLAUDE.md split:**
  - the tool `CLAUDE.md` holds the project overview, Python env, running the GUI, GUI behaviour, menu shortcuts, tests and the dev workflow (SPLIT-08), with no workstation paths;
  - the collection `CLAUDE.md` plus README hold naming, the atomic rule, path variables, manual import and git workflow;
  - the owner's workstation specifics (main checkout path, the `KICAD_LIB_GITHUB`/`CUSTOM_3DMODEL_DIR` values, the D-26 rule's concrete folders) go into an **untracked `CLAUDE.local.md`** in the tool checkout;
  - `.claude/CLAUDE.md` (the GSD-generated one) follows the same rule.
- **D-22:** **KiCad unchanged proof:** a **resolved-URI diff**. A script resolves every URI in KiCad's global `sym-lib-table` and `fp-lib-table` (plus the `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` values) before and after. It needs **zero missing and an identical list**. The owner chose this as the required check; a 3D-model path check, a manual KiCad project open and an app rescan are not required (they may be run as extras).
- **D-23:** **Rehearsal:** a **full dry run on `git clone --no-local` copies** in a scratch folder: build the tool repo, make the collection's remove-code commit, run the tests from a fresh clone, and run the URI diff against a scratch copy. The live run then repeats the same scripted steps after a `git bundle` of both repos and a `pre-split` tag. The live run happens from the main checkout KiCad reads (D-26), never from this worktree.

#### Locked from earlier phases (not re-asked)
- `kicad_custom_library` history is never rewritten (gitlinks, the `pre-atomic` tag, `MIGRATION-ATOMIC.md` depend on its SHAs).
- WurthElektronik stays a submodule in the collection until Phase 17.
- The Phase 15 legacy own-folder fallback (`Source.LEGACY` in `collection.py`) is removed in this phase.
- The conftest live-collection guard (`_live_custom_untouched`) is repointed at the corpus collection.
- The commit step's `parent_mode` (`gitlink` for the owner's collection, `none` for new collections) is unchanged.
- The app keeps its library-folder resolution order (`--library-root` / `KICAD_LIBMGR_ROOT` > chosen > `KICAD_LIB_GITHUB` > first run).

### Claude's Discretion
- The exact allow-list of paths for the tool repo's first commit, and the per-file `.planning/` keep/drop list within D-05.
- The scan's implementation (a stdlib Python script rather than a new dependency, unless gitleaks is clearly better).
- Whether `pyproject.toml` gains `[project]` metadata now or in Phase 20/21 (the licence field at minimum).
- The README's structure (install, first run, choosing or creating a collection, dev workflow).
- How the `Claude-Session` line is kept out of the public commits (attribution config, hook, or the commit helper).
- Plan order and wave split, within: rehearsal before live, scan before the flip, tests green from a fresh clone before the worktree is retired.

### Deferred Ideas (OUT OF SCOPE)
- THIRD-PARTY-NOTICES (PySide6/Qt LGPL and others): Phase 21.
- A nightly `--full` CI run: not chosen now; revisit with the Phase 21 release gate.
- Extra KiCad checks (3D-model path check, a manual project open in KiCad 10, an app rescan comparison): not required by the owner; optional extras.
- Python 3.14 minimum in the pyproject metadata: Phase 20.
- Reviewed todo "Stop the migration dialog's draft and rebuild timers when it closes": unrelated app follow-up, left for a quick task.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPLIT-01 | Public tool repo holds app code, tests, pyproject, planning and build scripts, no library content | Allow-list (section "Tool-repo allow-list") built from `git ls-files`; `git archive` export; 85+164+root files measured |
| SPLIT-02 | Private collection holds `Custom` + third-party libs, no code; KiCad keeps working (every table URI resolves, zero missing before vs after) | Remove-code commit rehearsal (gitlinks and `.gitmodules` survive, measured); URI-diff design + working prototype; `--no-local` rehearsal with `insteadOf` submodule init (measured) |
| SPLIT-03 | Public history has nothing private or licence-restricted; scan | Scan design (classes, patterns, blob-once history walk), counts of what trips today by class and area |
| SPLIT-04 | Suite passes from a fresh clone without the collection within a skip budget; synthetic sample replaces the TI zip | Measured: 3911 passed / 29 skipped with the zip; 377 failed + 2 errors in 31 modules without it; UL builder spec; no-KiCad skip count (13 after corpus moves) vs budget 10 |
| SPLIT-05 | Docs split: developer docs in tool repo; naming, atomic rule, path variables in collection README | Section map of the current CLAUDE.md/README to the two targets; `test_docs_atomic` impact |
| SPLIT-06 | Licence chosen and added; README covers install and first run | MIT per D-14; README skeleton; current README is collection-oriented and moves to the collection |
| SPLIT-07 | Visibility of both repos decided and set | `gh repo edit` flags verified from `--help`; both repos PUBLIC today (read-only `gh repo view`); tool repo name free |
| SPLIT-08 | Dev workflow documented (tool runs against a chosen collection) | `--library-root` / `KICAD_LIBMGR_ROOT` / `KICAD_TEST_CORPUS` triad; scratch-collection test pattern; README + tool CLAUDE.md + untracked `CLAUDE.local.md` |
</phase_requirements>

## Summary

The code half of the split is mostly done already: the quick suite runs green in a clone that has no `Custom/` and no `WurthElektronik` content. The one real dependency of the public suite on private-ish data is the tracked TI vendor zip. Removing it makes 377 tests fail and 2 error across 31 modules (measured), because `tests/zipfixtures.py:25` and 14 more modules each build their own path to `downloaded_examples/ul_CSD85301Q2.zip`. That makes the synthetic Ultra Librarian builder (D-15) the critical-path work item: write it once in `tests/vendorfixtures.py` (where the SnapEDA and SamacSys synthetic builders already live), point `zipfixtures.UL_ZIP`, `conftest.ul_package` and the 14 local constants at it, and 31 modules recover without per-test edits. The builder must reproduce a short list of structural quirks (member order, CRLF everywhere, KiCad 6 `(id N)` property syntax, two symbol units, eight pins and pads, a lower-case `.stp` name) listed in the UL builder section.

The second finding changes a locked number. D-19 allows 10 skips for a runner without KiCad. Measured on a clone with KiCad hidden: 45 skips, of which 13 remain once vendor-sample and `Custom` skips become deselected corpus tests (and 2 of those are symlink skips that may not occur on a GitHub runner). Twelve come from tests that need an installed KiCad's stock libraries. So CI would fail its own budget with 13 or 15. Recommendation: treat "needs a KiCad install" the same way as `corpus` (a registered marker that is deselected with a printed count), which leaves 3 skips. That is an open question for the owner because D-19 named the KiCad skips as the expected ones.

The history half is simpler than the milestone research feared. Because the tool repo starts fresh from an allow-listed `git archive` export, the pre-publish scan mostly guards the tree. Today's tree trips it in about 55 files of the planned keep-set for workstation paths (40 of them are Phase 14 timing logs that should simply be dropped, 15 are content files to scrub) plus `CLAUDE.md`, 3 hits in 2 test files, and one research file that contains the owner's commit email. No vendor file, `.kicad_sym`/`.kicad_mod` copy or secret trips it apart from the one zip and one false-positive string in `tests/test_isolation.py`. A shingle comparison of the tracked tree against the live `Custom/` and every vendor zip found 0 shared windows of three long lines. The collection-side cutover was rehearsed in a scratch clone: a `git rm` of an explicit path list leaves both gitlinks and `.gitmodules` untouched; `git rm --cached` leaves the vendor zip on disk; leftover `__pycache__` folders stay behind and must not be cleaned with `git clean -x`.

**Primary recommendation:** do all test-suite surgery (UL builder, `corpus` gate, `needs_kicad` gate, `Source.LEGACY` removal, guard repoint, scan and budget scripts, CI file) on `feature/part-importer` before the split, prove it from a `--no-local` clone with no `downloaded_examples/` and no collection, and only then run the scripted cutover (rehearsal first, live second) with the URI-diff before/after as the gate for the collection side.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| App code, tests, planning, CI, licence | Tool repo (public) | — | D-01/D-02: the only place code lives after the split |
| Own libraries, third-party submodules, collection docs | Collection repo (private) | — | D-01/D-07: no code, only gitlinks, `.gitmodules`, README, CLAUDE.md, `.gitignore` |
| Which collection the app works on | App runtime (`--library-root`, `KICAD_LIBMGR_ROOT`, chosen, `KICAD_LIB_GITHUB`) | Collection (a folder with `Custom/`) | Unchanged resolution order; `Source.LEGACY` removed |
| Corpus tests (real vendor zips, Würth, live `Custom/`) | Collection checkout named by `KICAD_TEST_CORPUS` | Tool repo test harness (marker + deselection) | Real data never enters the public repo (D-18) |
| Public-suite vendor samples | Tool repo `tests/` synthetic builders | — | D-15 |
| Leak prevention | Tool repo script `scripts/prepublish_scan.py` | CI job, local pre-flip run | D-09/D-20 |
| KiCad keeps working | Collection checkout (unchanged layout) + KiCad config | URI-diff script run on the workstation | D-22 |
| Visibility, repo creation, flip to public | GitHub (`gh`, owner-confirmed) | — | D-11/D-12 |
| Commit identity and trailers | Tool checkout local git config + hook | Claude Code attribution settings | D-13 |

## Standard Stack

Nothing new is installed by this phase. The scripts are stdlib Python.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.4 on the workstation (`env`), `3.14` on CI | Scripts (`scan`, `skip budget`, `uri diff`, `split`) | Same interpreter the app runs on `[VERIFIED: env/Scripts/python.exe, 3.14.4 + pytest 9.1.1 + PySide6 6.12.0 printed this session]` |
| PySide6 | 6.12.0 (pinned) | The app and pytest-qt | `requirements.txt` line 1: `PySide6==6.12.0` |
| pytest + plugins | `pytest==9.1.1`, `pytest-qt==4.5.0`, `pytest-xdist==3.8.0`, `pytest-timeout==2.4.0` | The suite and its gate | `requirements-dev.txt` verbatim pins |
| git | 2.49.0.windows.1 | Export, rehearsal, scan walk | `[VERIFIED: git --version]` |
| gh | 2.88.1 | Create private repo, set visibility | `[VERIFIED: gh --version]`; authenticated on this machine `[VERIFIED: gh auth status]` |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `actions/checkout` | v7 (latest tag v7.0.1) | CI checkout | `[CITED: github.com/actions/checkout/releases]` |
| `actions/setup-python` | v7 (latest tag v7.1.0) | CI Python 3.14 + pip cache | `[CITED: github.com/actions/setup-python/releases]` |
| `windows-latest` | Windows Server 2025 image (`windows-2025-vs2026`), 4 vCPU / 16 GB on public repos | CI runner | `[CITED: github.com/actions/runner-images; docs.github.com hosted runners]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib scan script | gitleaks | gitleaks is not installed here (`command -v gitleaks` empty); it covers secrets only, not the owner-specific classes (workstation paths, identity, vendor kinds, copied content). Keep the stdlib script; gitleaks can be added later as an extra CI step `[ASSUMED]` |
| `git filter-repo` | allow-listed `git archive` export | D-02 already decided; the export is also what makes the history scan trivial |
| `-m 'not slow and not corpus'` expression | conftest deselection with a printed count | The expression hides the count and breaks the existing `--full` rewrite at `tests/conftest.py:63-64`; deselection in `pytest_collection_modifyitems` plus a count file matches D-18 ("reported as a separate count") |

**Installation:** none new. CI runs `pip install -r requirements-dev.txt`.

**Version verification:** versions above come from the repo's own pins and from the interpreter in `env/` (printed this session). No new package is introduced, so no registry lookup was needed for new names.

## Package Legitimacy Audit

No package is added by this phase. The existing pinned dependencies were run through the seam anyway.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| PySide6 | PyPI | years (6.12.0 published 2026-10-08) | unknown (PyPI exposes none) | pyside.org | SUS (reason `unknown-downloads` only) | Approved: already pinned and in use since v1; not a new install |
| pytest | PyPI | years | unknown | github.com/pytest-dev/pytest | SUS (`too-new` = latest release 2026-10-27; `unknown-downloads`) | Approved: pinned 9.1.1, in use |
| pytest-qt | PyPI | years | unknown | github.com/pytest-dev/pytest-qt | SUS (`unknown-downloads`) | Approved: pinned, in use |
| pytest-xdist | PyPI | years | unknown | github.com/pytest-dev/pytest-xdist | SUS (`unknown-downloads`) | Approved: pinned, in use |
| pytest-timeout | PyPI | years | unknown | (seam output truncated at 60 lines) | SUS expected (same reason) | Approved: pinned, in use |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** all five, only because the seam cannot read PyPI download counts; they are the project's long-standing pins, so no `checkpoint:human-verify` is needed. `[VERIFIED: gsd-tools query package-legitimacy check --ecosystem pypi ... run this session]`

## Architecture Patterns

### System Architecture Diagram

```
 feature/part-importer (this worktree)                     PRE-SPLIT CODE WORK (waves 0-1)
   |  UL builder, corpus + needs_kicad gate, LEGACY removal, guard repoint,
   |  scan + budget scripts, CI yaml, docs split drafts, LICENSE
   v
 merge to main --> push v2.0 --> delete 8 worktree-agent-* branches       (D-06, interactive)
   |
   +--> git bundle (both repos) + tag pre-split  -------------------> bundles kept outside the repos
   |
   v
 scratch: git clone --no-local  (rehearsal, then the same script live)
   |
   |  A. TOOL REPO BUILD                              B. COLLECTION CUTOVER
   |  git archive pre-split -- <allow-list>           git rm explicit code paths
   |    -> scrub .planning (placeholders, drop logs)  git rm --cached downloaded_examples zip
   |    -> new LICENSE/README/CLAUDE.md/.github       edit .gitignore, write README + CLAUDE.md
   |    -> git init, local identity (noreply)         commit "remove app code"
   |    -> prepublish_scan (tree + history)           URI diff: before vs after (zero missing)
   |    -> gh repo create --private, push
   |    -> CI (windows-latest): pytest + budget + scan
   |    -> fresh clone of GitHub copy: venv + quick pytest
   v
 owner flips tool repo to public (manual)   gh repo edit --visibility private x2 (owner-confirmed)
   |
   v
 retire worktree (git worktree remove), new tool checkout + own env/, memory path moved
```

### Recommended Project Structure (tool repo, first commit)
```
kicad_lib_manager/        # 85 tracked files today (app package)
kicad_lib_manager.py      # launcher
tests/                    # 164 tracked files; fixtures/ kept (synthetic)
scripts/                  # prepublish_scan.py, check_skip_budget.py, split/ (scripted cutover + uri_diff.py)
.githooks/commit-msg      # strips Claude-Session lines (enabled with core.hooksPath)
.github/workflows/ci.yml
.planning/                # scrubbed current set (see allow-list)
pyproject.toml  requirements.txt  requirements-dev.txt
LICENSE  README.md  CLAUDE.md  .gitignore  .gitattributes
```

### Pattern 1: Allow-listed export, not a filtered history
**What:** from a scratch clone at the `pre-split` tag, `git archive pre-split -- <path> <path> ...` into the new folder, then script the scrub and `git init`. Anything not named is absent by construction.
**When:** building the tool repo (D-02).
**Evidence:** `git ls-files` top level today: `.planning` 679, `tests` 164, `kicad_lib_manager` 85, `research_notes` 4, `reports` 1, `downloaded_examples` 1, `Custom` and `WurthElektronik` gitlinks, root files `.gitattributes .gitignore .gitmodules CLAUDE.md README.md pyproject.toml requirements.txt requirements-dev.txt kicad_lib_manager.py` `[VERIFIED: git ls-files, this session]`.

### Pattern 2: `corpus` gate in conftest (deselect with a count)
**What:** register `corpus` (and `needs_kicad`) in `pyproject.toml` markers; in `tests/conftest.py` `pytest_collection_modifyitems` (already `tryfirst`, line 66) remove marked items unless the gate is open, call `config.hook.pytest_deselected(items=...)`, and write the count where the controller can read it.
**Why the count needs a file:** under xdist the final summary prints no deselected count. Quick run output ended `3911 passed, 29 skipped, 4 warnings in 100.15s` even though the `slow` tests are deselected by `-m`. `[VERIFIED: scratch run output]` and `grep -rn deselect env/Lib/site-packages/xdist/*.py` returns nothing. The suite already uses the pattern: workers write `<run temp>/timeouts/<worker>.txt` and the controller reads them in the terminal summary (`tests/conftest.py` lines 53 `_run_temp`, 268, 290). Copy that.
**Hook:** `def pytest_deselected(items: Sequence[Item]) -> None:` `[VERIFIED: env/Lib/site-packages/_pytest/hookspec.py:436]`; its docstring says it "must be *called* from `pytest_collection_modifyitems`" when items are deselected.
**Fail loudly:** when `KICAD_TEST_CORPUS` is set but is not a folder with `Custom/`, raise `pytest.UsageError` (an owner who set it wants the corpus). When set and valid, corpus tests run and a missing file inside the corpus is a test failure, not a skip.

### Pattern 3: Synthetic UL builder next to the SnapEDA/SamacSys ones
`tests/vendorfixtures.py` already says (module docstring): "The builders copy each vendor's layout, file names, property names and markers, never its geometry, models or licence text". Add `ul_members()` / `ul_zip(path)` in the same style and give `zipfixtures` a lazily built `UL_ZIP`. Member `ZipInfo` objects need a fixed `date_time` so the bytes are deterministic (a plain `writestr(name, data)` stamps the current time).

### Pattern 4: Scan as pure functions plus a thin git walk
Pure `scan_text(path, bytes, rules) -> list[Finding]` and `scan_path(path, rules)` are unit-testable in the quick run (no git). The git walk (blobs once, commit messages, ref names) is covered by one `@pytest.mark.slow` test that builds a small repo with planted violations (the suite's rule: any test that creates a git repo must be slow).

### Anti-Patterns to Avoid
- **`git rm -r .` or `git clean -fdx` in the main checkout.** The first removes the gitlinks; the second deletes `env/`, `downloaded_examples/*` and generated tables (all ignored, untracked, and in use). Use the explicit path list below.
- **`-m 'not slow and not corpus'` in `addopts`.** Hides the count; `--full` logic at `tests/conftest.py:63-64` only rewrites the exact string `not slow`.
- **Module-level `pytest.mark.skipif(not path.exists())` for corpus data.** That is the "green by skipping" mode PITFALLS 11 warns about; use the marker so the count is printed.
- **Scanning with the owner's identifiers hard-coded in the scan script.** The script is public. Read identity terms from the old repo's `git log` and from an untracked local file at run time.

## Test-Module Classification (D-18, focus 1)

Measured, not estimated. Method: (a) `git clone --no-local` of this worktree into the scratchpad; (b) quick run with the UL zip present and no collection: **3911 passed, 29 skipped, 0 failed, 100 s** (16 CPUs); (c) same clone with `downloaded_examples/` removed: **377 failed, 3528 passed, 31 skipped, 2 errors, 895 s**. All `[VERIFIED: scratch runs this session]`. The 8,016 `test_roundtrip_wurth_file` params only exist where the Würth submodule is checked out (collect-only in this worktree: `8018/12230 tests collected` for `-m wurth`).

### Bucket A: rebuild on the synthetic UL builder (central change, no per-test edits)
Failures without the zip, per module (these 31 modules are the work): `test_import_dialog` 201, `test_shared_footprints` 21, `test_install_e2e` 19, `test_atomic_targets` 17, `test_generated_text` 15, `test_install_plan` 14, `test_install_apply` 12, `test_official_footprint` 10, `test_import_preview` 10, `test_adapters` 9, `test_package_zip` 7, `test_install_options_clear` 7, `test_kicad_files` 4, `test_import_form` 4, `test_zipfixtures` 3, `test_roundtrip_corpus` 3, `test_install_gate` 3, `test_footprint_text` 3, `test_vendor_install` 2, `test_package_folder` 2, `test_main_window_import` 2 (+2 errors), `test_candidate_names` 2, and one each in `test_sexpr`, `test_samacsys_adapter`, `test_real_vendor_samples`, `test_keywords`, `test_gate_reasons`, `test_field_cleanup`, `test_edits`, `test_customfixtures`, `test_commit_plan`.

Where the path is defined (change to `from zipfixtures import UL_ZIP`):
- `tests/zipfixtures.py:25` `UL_ZIP = REPO_ROOT / "downloaded_examples" / "ul_CSD85301Q2.zip"` (imported by 14 modules)
- own constants: `test_adapters.py:22`, `test_edits.py:29`, `test_gate_reasons.py:23`, `test_generated_text.py:27`, `test_import_dialog.py:31`, `test_import_form.py:96`, `test_install_gate.py:28`, `test_kicad_files.py:27`, `test_main_window_import.py:1161`, `test_official_footprint.py:112`, `test_roundtrip_corpus.py:22` (`ZIP`), `test_samacsys_adapter.py:46`, `test_snapeda_adapter.py:12`, `test_suggest_atomic.py:31`
- inline: `tests/conftest.py:506` (`ul_package`), `tests/test_install_e2e.py:176`
- `ul_package` consumers: `test_atomic_targets`, `test_collection_git`, `test_commit_plan`, `test_customfixtures`, `test_field_cleanup`, `test_generated_text`, `test_import_dialog`, `test_import_preview`, `test_install_apply`, `test_install_e2e`, `test_install_gate`, `test_install_options_clear`, `test_install_plan`, `test_keywords`, `test_official_footprint`, `test_shared_footprints`, `test_vendor_install`.
- Hard-coded real values the builder must satisfy: `tests/customfixtures.py:40` `UL_PART_TOKENS = ("CSD85301Q2", "DQK0006B", "DLV0006A")`; `tests/installfixtures.py:36` `UL_DESCRIPTION = "Dual N-channel MOSFET, 30 V"` (not from the zip); `tests/test_adapters.py:22-25` member names and `UL_IGNORED = ["ImportGuides.html", "readme.txt", "KiCADv6/ImportGuide.html"]`.
- `test_zipfixtures.py:159` hashes `UL_ZIP.read_bytes()` before and after `unpack_sample` to prove it does not modify the zip; it keeps working on a generated file.

### Bucket B: mark `corpus` (run only with `KICAD_TEST_CORPUS`)
| Module / test | Reads | Note |
|---|---|---|
| `test_roundtrip_corpus.py` `test_roundtrip_wurth_file` (8,016 params), `test_wurth_corpus_parse_budget` | `REPO / "WurthElektronik"` (line 260, 268) | already `wurth` + slow |
| `test_roundtrip_corpus.py` `_repo_owned_params` custom branch (lines 49-67, 44 `custom/*` params) | `REPO / "Custom"` | split the parametrisation: `fixture/*` and `zip/*` params stay public (synthetic zip), `custom/*` params become corpus |
| `test_roundtrip_corpus.py` `test_ul_zip_is_pinned_and_tracked` (line 117) | pins `ZIP_SHA256` of the real zip and asserts it is git-tracked | delete (the zip is untracked after the split; the scan covers "no zip tracked"); an optional corpus test may pin the real zip's hash |
| `test_scanner_issues.py` `test_live_custom_model_findings_are_zero` (line 273), `test_wurth_model_paths_stay_quiet` (line 284) | live `Custom/Footprints`, `WurthElektronik` | `wurth` mark exists at 284 |
| `test_kicad_files.py` `test_live_custom_symbols` (362), `test_live_custom_footprints` (377); `custom = REPO_ROOT / "Custom"` at line 51 | live `Custom/` | corpus |
| `test_edits.py` `custom-*` params (lines 163-182), skip at 106 | live `Custom/Symbols/*.kicad_sym` | corpus; `CUSTOM_SYMBOL` at line 28 |
| `test_naming_sanitize.py` `test_sanitize_live_custom_names_unchanged` (188), line 290 `Custom/3DModels` | live `Custom/` | corpus |
| `test_locate_text_caps.py` line 336 (`Custom`) | live `Custom/` | corpus |
| `test_sexpr.py` `test_reference_corpus_includes_the_custom_library_files` (line 649, skip 680) | live `Custom/` | corpus |
| `test_atomic_uat.py` `test_uat_atomic_scratch` (line 292) | live `Custom/` into a scratch copy | already also gated by `KICAD_ATOMIC_UAT_DIR`; add corpus |
| `test_real_vendor_samples.py` all `test_real_*` (lines 71-335) | the five real zips in `downloaded_examples/` | corpus; they already skip by file name today |
| `test_vendorfixtures.py` `test_fixture_originality` (line 124) | real SnapEDA/SamacSys/3D zips | corpus; add the UL builder to its originality check |
| `test_footprint_text.py` `_sample_footprint` users (line 282-290) | real ATXK, SamacSys, SnapEDA zips | corpus (3 tests); the UL-based tests stay public |
| `test_categories.py` (line 14, skip 35) | real SamacSys zip | corpus |
| `test_atomic_targets.py` `requires_atxk` (2 uses), `test_gate_reasons.py` `requires_atxk` (2 uses) | real ATXK zip (`downloaded_examples/ul_ATXK-H14-D-32-768KHZ-E50-T3.zip`) | corpus |
| `test_suggest_atomic.py:57` `skipif(not UL_ZIP.is_file())` | the UL zip | becomes public once `UL_ZIP` is the builder; remove the `skipif` |

`wurth` marker: registered at `pyproject.toml:11` (`"wurth: needs the WurthElektronik submodule checked out (stress/perf corpus)"`) and made slow automatically in `tests/conftest.py:66-77`. Recommendation: keep `wurth` as a subset that implies `corpus` and `slow` (so `-m wurth` still works and the slow gate in `test_markers.py` keeps passing).

### Bucket C: delete or rewrite (tests of this repo's layout only)
| Test | Why |
|---|---|
| `test_docs_atomic.py::test_library_naming_has_update_note` (reads `.planning/research/LIBRARY-NAMING.md`) and `::test_project_md_marks_migration_delivered` (reads `.planning/PROJECT.md`) | test planning prose, no app behaviour: delete |
| `test_docs_atomic.py::test_claude_md_describes_atomic_scheme` and the `path_vars` block of `::test_claude_md_names_the_new_actions` (asserts the owner's main-checkout `.../Custom/3DModels` path string at line 62, and calls `_section(text, "## KiCad Path Variables", ...)`, which raises `ValueError` once that heading is gone) | those sections move to the collection CLAUDE.md: delete the atomic-scheme test, keep the GUI-behaviour assertions against the tool CLAUDE.md |
| `test_real_vendor_samples.py::test_vendor_zips_stay_local` and its entry in `test_markers._READ_ONLY_GIT_TESTS` (line 9) | asserts `git ls-files downloaded_examples == [the UL zip]`; after the split nothing under `downloaded_examples` may be tracked: replace by the scan rule |
| `test_collection.py` / `test_startup.py` `Source.LEGACY` cases | see LEGACY removal below |

### Bucket D: unchanged
Everything that reads only `kicad_lib_manager/` or builds scratch collections: `test_layering`, `test_importer_layering`, `test_annotations_resolve`, `test_custom_literals`, `test_exit_with_hung_check`, `test_library_table_widget`, `test_manifests` (reads `pyproject.toml`, `requirements*.txt`), `test_fixtures` (git check-ignore on `tests/fixtures`, needs the clone to be a git repo), `test_scanner_skip_dirs` (keep: the collection checkout still holds an ignored `downloaded_examples/`, so `SKIP_DIRS` must keep it), `test_scan_cache`, `test_main_window*` and the many tests that pass `REPO_ROOT` to `open_package(path, REPO_ROOT)` only as the "staging must not be inside the repo" argument.

### Bucket E: meta-tests that name moved things
- `test_isolation.py::test_timeout_config` (line 167-180) parses `tests/test_roundtrip_corpus.py` for `test_wurth_corpus_parse_budget`'s `pytest.mark.timeout(>=600)`; keep it passing by keeping that test where it is (corpus-marked), or retarget it.
- `test_isolation.py` asserts `"-m 'not slow'" in ini["addopts"]` (line 168): do not change that string.
- `test_markers.py::test_wurth_and_kicad_cli_tests_are_slow` (collect with `-m "(wurth or kicad_cli) and not slow"` returns 5): extend for the new markers.

### Skip budget (D-19), measured
| Situation | Skips | Source |
|---|---|---|
| Workstation, KiCad 10 installed, no corpus, today's code | 29 | 2 symlink + 1 `local_kicad` + 26 vendor-sample/`Custom` skips `[VERIFIED: run_with_ul]` |
| Same, after Bucket B (those 26 become deselected) | **3** | 2 symlink (`test_model_source.py:201`, `test_package_folder.py:105`) + 1 `local_kicad` (`test_roundtrip_corpus.py:205`) |
| Runner **without** KiCad, after Bucket B | **15** (13 if the runner may create symlinks) | simulated by pointing `find_kicad_footprint_dir` at a missing folder in the scratch clone: 45 skips, 30 corpus-type removed |

The 12 no-KiCad skips: `test_footprint_text.py:325` (1), `test_generated_text.py:503,512,523,533,544` (5), `test_official_footprint.py:459` (1), `test_siblings.py:248,261` (2), `test_stems.py:213` (1), `test_footprint_index.py:206` (1), `test_install_verify.py:515` (1). A thirteenth, `test_real_vendor_samples.py:188`, is corpus.

So D-19's "at most 10" fails by 3 to 5 on the CI runner. Options in "Open Questions".

## UL Builder Specification (D-15, focus 2)

Source inspected: the 6 members of `downloaded_examples/ul_CSD85301Q2.zip` extracted into the scratchpad (since deleted) `[VERIFIED: zipfile listing this session]`. What the tests and adapter rely on:

| Fact | Value (verbatim from the real sample) | Relied on by |
|---|---|---|
| Member order | `DLV0006A.stp`, `ImportGuides.html`, `readme.txt`, `KiCADv6/2026-10-18_09-12-49.kicad_sym`, `KiCADv6/ImportGuide.html`, `KiCADv6/footprints.pretty/DQK0006B.kicad_mod` | `test_adapters.py`: `[pf.kind for pf in package.files] == ["model","symbol","footprint"]`, staged names `model_000.stp`, `sym_001.kicad_sym`, `fp_002.kicad_mod`, `package.ignored == UL_IGNORED` (zip order), progress calls `(0,3),(1,3),(2,3)` |
| Zip file name | stem starts `ul_` (`ul_CSD85301Q2.zip`) | `UltraLibrarianAdapter.detect`: +1 point for `package.source.stem.casefold().startswith("ul_")` |
| UL score | folder `KiCADv6` (+4), `ImportGuide(s).html` (+3), timestamp symbol name matching `^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.kicad_sym$` (+2), `ul_` (+1); needs >= 5 (`UL_CLAIM_POINTS = 5`) | `test_ultra_sample_end_to_end` asserts `candidate.confidence == 1.0` (all four = 10 points); `kicad_lib_manager/importer/adapters/ultralibrarian.py` |
| Line endings | every member is CRLF only (symbol 702 CRLF, 0 bare LF; footprint 38; STEP 4,507; html 97; readme 8), no BOM, ASCII only | EOL-preservation tests that read the sample; builder must write `\r\n` |
| Symbol file | first line `(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)`; one symbol `"CSD85301Q2"` with sub-units `CSD85301Q2_1_1` and `CSD85301Q2_2_1` (`test_install_e2e.py:230` expects `[f"{SYMBOL}_2_1_1", f"{SYMBOL}_2_2_1"]` after renaming); 8 pins, names `S1 G1 D1 D1 D2 S2 G2 D2`, electrical type `unspecified`, style `line`; KiCad 6 property syntax `(property "Reference" "U" (id 0) (at 0 2.54 0) ...)` with `(id N)` | `part_meta` tests, `test_install_plan` (subs `PART_X_1_1`...), siblings/pin-count logic |
| Properties (in order) | `Reference`="U", `Value`="CSD85301Q2", `Footprint`="DQK0006B" (no library prefix), `Datasheet`="https://www.ti.com/lit/gpn/csd85301q2", `ki_keywords`="CSD85301Q2", `ki_locked`="" (empty), `ki_fp_filters`="DQK0006B". No `Manufacturer`, `MPN` or `Description` | `test_ultra_sample_part_meta` (`description == ""`, `manufacturer == ""`, `keywords == "CSD85301Q2"`, `fp_filters == "DQK0006B"`), `test_field_rules`, atomic-gate "missing field" tests |
| Footprint file | `(footprint "DQK0006B" (version 20211014) (generator pcbnew)`, `(layer "F.Cu")`, `(tags "CSD85301Q2 ")` (trailing space), `(attr smd)`, `fp_text reference "REF**"`, `fp_text value DQK0006B` (unquoted atom), `fp_text user "${REFERENCE}"`, a second `fp_text user "u"` on `F.SilkS`, `fp_line`s on `F.Fab` (a 2.1 mm square, width 0.1) and `F.SilkS`, one `fp_circle`; **no `(model ...)`**; 8 SMD rect pads "1".."8": six small at x = +-0.975, y in {-0.65, 0, 0.65}, two thermal (`0.9 x 0.625`) at x = 0, y = +-0.488 | `test_footprint_text.py:36-47`: `facts.pads == 8`, `facts.pitch == 0.65`, `facts.body == (2.1, 2.1)`, `facts.family == "WSON-6"` (family comes from the `texts` argument, not the file); `test_install_e2e.py` `candidate.footprints[0].model_paths == ()` |
| Model | `DLV0006A.stp`, starts `ISO-10303-21;` + CRLF; real size 192,031 bytes | `_model_magic` check in `adapters/base.py` (needs the magic), `candidate.models[0].filename == "DLV0006A.stp"`; the body can be a few hundred bytes of generic STEP header and a handful of entities, written from scratch |
| Ignored members | `ImportGuides.html` (root; no `<!DOCTYPE>` and no meta refresh), `KiCADv6/ImportGuide.html` (has `<!DOCTYPE html>` and a `<meta http-equiv="refresh" ...>` to the vendor help page), `readme.txt` (notes text) | `UL_IGNORED` and the `intake.ignored_members` Issue text; content can be short placeholder text |
| Zip bytes | deflate; the real members carry 2025/2026 timestamps | give every `ZipInfo` an explicit fixed `date_time` so the generated bytes are reproducible; `zip_bytes()` in `tests/zipfixtures.py:40` passes plain names, which get the current time |

Where it lives: `tests/vendorfixtures.py` (it imports only the stdlib and `zipfixtures`). Naming: keep the real part numbers; D-10 allows public MPNs. Do not copy geometry: write the symbol with a plain 8-pin box and the footprint with clean numbers (0.45 x 0.30 pads), not the vendor's `0.449999` artefacts. Add an originality test in the corpus group that asserts no builder member is a byte copy of the real UL members (pattern: `test_vendorfixtures.py:124`).

Where `UL_ZIP` should be created: `zipfixtures.UL_ZIP` is an import-time constant used by about 30 modules, so it cannot be a session fixture. Recommended: build once at import into a content-addressed folder under `tempfile.gettempdir()` (`kicad_lib_manager_tests/<sha12>/ul_CSD85301Q2.zip`), writing to a temp name and `os.replace` so parallel xdist workers cannot see a half-written file. The file name must stay `ul_CSD85301Q2.zip` (the `ul_` stem point). `[ASSUMED: this location choice; the alternative is a gitignored `tests/_generated/` folder]`.

## Pre-Publish Scan Design (D-09, D-10, focus 3)

A stdlib script `scripts/prepublish_scan.py`; exit 0 clean, 1 on any blocking hit, 2 on usage error. Three inputs: the working tree (`git ls-files -co --exclude-standard`, so untracked-but-committable files count), every blob reachable from the refs it will push, and every commit message, author/committer identity and ref name.

### Rule classes
| Class | Detection | Scope | Today's hits in the planned tool tree |
|---|---|---|---|
| `workstation_path` | `(?i)\b[a-z]:[\\/]+(users|git_repo_clones)[\\/]`, git-bash style `(?i)/[a-z]/(users|git_repo_clones)/`, `(?i)/Users/[^/\s]+/`, `/home/(?!runner\b)[^/\s]+/`, `pytest-of-<user>\s\\/]+` | all text | **about 55 files in the keep-set** (15 content files + 40 timing logs), `CLAUDE.md` (1), `tests/test_docs_atomic.py:62-63` and `tests/test_migration_dialog_run.py:172` (3 hits, 2 files). Distinct strings: `.../Kicad_Libraries-importer/env/Scripts/python.exe` (17), `.../Kicad_Libraries` (6), `.../Kicad_Libraries-importer` (4), a home folder (3), `.../.claude/gsd-core/workflows/...` embedded in PLAN `@`-references (22 each, two files) `[VERIFIED: git grep this session]` | <!-- scan: allow workstation_path -->
| `owner_identity` | emails: every address in the old repo's `git log --format=%ae%n%ce` plus `git config user.email`, given at run time (`--deny-emails-from-repo PATH`); full name from an untracked `--deny-terms-file`; plus a generic rule: any email not in an allow-list (`@example.invalid`, `@example.com`, `@users.noreply.github.com`, `noreply@anthropic.com`, `noreply@github.com`) | all text, commit identities | the owner's commit email appears in **one** tracked file, `.planning/research/PITFALLS.md` (line 127); the full name appears in that line's address and in `research_notes/` (excluded). The git author name on all 1,812 commits is the GitHub handle (allowed). 29 `@example.invalid` test addresses are allowed |
| `vendor_file` | path suffix in `.zip .7z .rar .step .stp .wrl .igs .iges .pdf .kicad_sym .kicad_mod .kicad_pcb .kicad_sch .kicad_pro .lib .dcm` outside `tests/fixtures/`; magic bytes `PK\x03\x04` or `ISO-10303-21` in any blob outside `tests/fixtures/` | all blobs | **1**: `downloaded_examples/ul_CSD85301Q2.zip`. `tests/fixtures/` holds 9 `sexpr/*` and 5 `tables/*` files, all original synthetic text (`build_fixtures.py` docstring says so; 9,981 bytes in total) |
| `copied_custom` | exact blob hash equal to any file of the corpus checkout, and a shingle test: 3 consecutive lines of >= 25 characters from a corpus `.kicad_sym`/`.kicad_mod` (or vendor-zip text member) appearing in a scanned text blob | needs `--corpus PATH`, so local and pre-flip only, not in CI | **0 shared windows** (736 windows from `Custom/` plus every vendor zip vs every tracked text file outside the excluded archives). A 2-line / 18-char variant produced 3 false hits: generic KiCad boilerplate (`(offset (xyz 0 0 0))`...) in `tests/fixtures/sexpr/*.kicad_mod`. Keep the 3-line, 25-char rule |
| `secret` | gitleaks-style set: `gh[pousr]_[A-Za-z0-9]{36,}`, `github_pat_[A-Za-z0-9_]{50,}`, `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, `xox[baprs]-[A-Za-z0-9-]{10,}`, `AIza[0-9A-Za-z_-]{35}`, `sk-ant-[A-Za-z0-9_-]{20,}`, `eyJ[A-Za-z0-9_-]{10,}\.eyJ`, and `(?i)(api[_-]?key|secret|token|passw(or)?d)\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{16,}["']` | all text | **1 false positive**: `tests/test_isolation.py:310` `_SECRET = "secret-token-1405"` matches the generic rule (17 chars). Needs an inline `# scan: allow secret` marker or an allow file entry |
| `session_trailer` | commit message matches `Claude-Session:` or `claude.ai/code/session` | commit messages | 152 of the old repo's commit messages carry it; zero tracked files do. The new history must have none |
| `ref_names` | branches/tags matching `worktree-agent-*` | refs | the 8 local branches (D-06 deletes them) |

### History walk (cheap because the history is new and small)
`git rev-list --objects --all` gives (blob sha, path); stream unique blobs once through `git cat-file --batch`; scan bytes with the compiled rules; keep the path from the object list for the report. Then `git log --all --format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x01` for identity and messages, `git for-each-ref` for ref names. On CI use `fetch-depth: 0`. Output names the rule, path (or commit sha) and line, never the matched secret/email text.

### Skeleton
```python
# scripts/prepublish_scan.py  (stdlib only; sketch)
import re, subprocess, sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Finding:
    rule: str
    where: str   # "path:line" or "commit:<sha12>" or "ref:<name>"

RULES = {
    "workstation_path": re.compile(rb"(?i)\b[a-z]:[\\/]+(?:users|git_repo_clones)[\\/]|/[a-z]/(?:users|git_repo_clones)/|pytest-of-<user>
    "secret_github": re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}"),
    # ... the rest of the table
}
VENDOR_SUFFIXES = {".zip", ".step", ".stp", ".wrl", ".kicad_sym", ".kicad_mod"}  # + the rest

def scan_blob(path: str, data: bytes, allow: set[tuple[str, str]]) -> list[Finding]:
    out = []
    in_fixtures = path.startswith("tests/fixtures/")
    if not in_fixtures and path.lower().endswith(tuple(VENDOR_SUFFIXES)):
        out.append(Finding("vendor_file", path))
    for line_no, line in enumerate(data.splitlines(), 1):
        for name, rx in RULES.items():
            if rx.search(line) and (path, name) not in allow:
                out.append(Finding(name, f"{path}:{line_no}"))
    return out

def history_blobs(repo: str):
    listing = subprocess.run(["git", "-C", repo, "rev-list", "--objects", "--all"],
                             capture_output=True, text=True, check=True).stdout
    paths = {}
    for row in listing.splitlines():
        sha, _, path = row.partition(" ")
        if path:
            paths.setdefault(sha, path)
    # stream paths.keys() through `git cat-file --batch` and yield (path, bytes)
```
(The `git cat-file --batch` loop is the only fiddly part; read the `<sha> <type> <size>` header, then exactly `size` bytes plus a newline.)

### What to do with today's hits
Drop, don't scrub: the 40 files under `.planning/phases/14-test-suite-speed-up/measurements/` (timing logs, 680 KB, `pytest-of-<user> and AppData paths in each). Scrub with scripted placeholders: the remaining ~16 files (replace the main-checkout, worktree and home paths with `<main-checkout>`, `<worktree>`, `<home>`, and `@c:/.../.claude/gsd-core/...` with `@.claude/gsd-core/...`). Rewrite by hand: the line in `PITFALLS.md` that contains the commit email, the three test-file path literals, the secret-looking `_SECRET` string (add the allow marker). The scan runs after the scrub in the rehearsal and must exit 0.

## Tool-Repo Allow-List (D-02, D-05, D-16, focus 4)

### Top level
| Path | Decision | Note |
|---|---|---|
| `kicad_lib_manager/`, `kicad_lib_manager.py` | keep | 85 files; `Source.LEGACY` removed beforehand |
| `tests/` | keep | 164 files; `tests/fixtures/` stays |
| `pyproject.toml`, `requirements.txt`, `requirements-dev.txt` | keep | add `corpus` and `needs_kicad` markers; licence field if metadata is added now |
| `.gitignore` | keep, edit | drop the `!downloaded_examples/ul_CSD85301Q2.zip` exception (line 34); keep `downloaded_examples/*`; add `.gsd/`, `.pytest_cache/`, `.ruff_cache/`, `CLAUDE.local.md`; `.claude/` already ignored (line 12) |
| `.gitattributes` | keep, edit | 2 lines today: `tests/fixtures/** -text` (keep) and `downloaded_examples/** -text` (drop) |
| `CLAUDE.md`, `README.md` | rewrite | per D-21; current README describes the collection |
| `LICENSE`, `.github/workflows/ci.yml`, `scripts/`, `.githooks/` | new | |
| `.gitmodules`, `Custom`, `WurthElektronik/`, `downloaded_examples/`, `reports/` (1 file), `research_notes/` (4 files) | absent | D-02, D-16 |

### `.planning/`
| Path | Files / size | Carries | Decision |
|---|---|---|---|
| `PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `config.json`, `state.json` | 6 files, about 110 KB | no workstation path hits in the content scan; `config.json` holds GSD toggles only, no secrets | keep (D-05) |
| `research/` | 6 files, 250 KB | `PITFALLS.md` has the commit email and 5 path hits; `SUMMARY.md` etc. carry the milestone research | keep, scrub |
| `codebase/` | 7 files, 86 KB | `STACK.md` has a path, an AppData path and the owner's user name | keep, scrub |
| `todos/` | 2 files | none | keep |
| `phases/14-*` | 67 files | 40 of them are `measurements/*.log`; `14-01-SUMMARY`, `14-05-PLAN`, `14-RESEARCH`, `BASELINE`, `MEASURE` carry paths | keep minus `measurements/` and the ignored `__pycache__` folder; scrub the rest. `tests/README.md` links to `BASELINE.md` and `MEASUREMENTS.md`, so keep those two |
| `phases/15-*` | 44 files | 7 files carry paths (the `15-13..16-PLAN`, `15-11-PLAN`, `15-REVIEW-FIX`, `15-UI-SPEC`) | keep, scrub |
| `phases/16-*` | `16-CONTEXT.md` (2 path hits), `16-DISCUSSION-LOG.md` (1), this file | scrub |
| `MILESTONES.md` (9 KB), `RETROSPECTIVE.md` (11 KB) | no scan hits | both are v1/v2 history. D-05 says they stay private "if they carry v1/v2 detail"; they do. Recommend drop both; owner may keep `MILESTONES.md` as a public changelog |
| `milestones/` (523 files, 9.7 MB), `quick/` (6), `debug/` (14) | 217 + 4 + 4 files with path hits | stay in the private history only (D-05) |

## Windows CI (D-20, focus 5)

```yaml
# .github/workflows/ci.yml  (sketch; not run)
name: ci
on: [push, pull_request]
permissions:
  contents: read
jobs:
  test:
    runs-on: windows-latest
    timeout-minutes: 30
    steps:
      - run: git config --global core.autocrlf false          # before checkout
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }                               # the scan walks history
      - uses: actions/setup-python@v7
        with:
          python-version: "3.14"
          cache: pip
          cache-dependency-path: requirements*.txt
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m pytest --junitxml=junit.xml            # bare pytest, quick run, no corpus
      - run: python scripts/check_skip_budget.py junit.xml --max-skips 10 --min-passed 3500
      - run: python scripts/prepublish_scan.py --tree --history
```
Facts and judgements:
- `windows-latest` is Windows Server 2025 (`windows-2025-vs2026`) `[CITED: github.com/actions/runner-images]`; 4 vCPU / 16 GB on public repos, standard runners free on public repos `[CITED: docs.github.com/en/actions/reference/runners/github-hosted-runners]`. The tool repo starts **private** (D-12), where Actions minutes are metered and Windows counts at a multiplier `[ASSUMED]`; a run of a few minutes is fine.
- Offscreen Qt: `tests/conftest.py:15-16` sets `os.environ["QT_QPA_PLATFORM"] = "offscreen"` before Qt imports, and pytest-qt needs no display. PySide6 6.12.0 has a cp314 Windows wheel (it is installed in `env/` under 3.14.4) `[VERIFIED]`. First CI run confirms it on the runner `[ASSUMED]`.
- xdist: `addopts` already has `-n 8 --dist worksteal`; on 4 vCPU that is oversubscribed but valid. Expect roughly 4x the 100 s measured on 16 CPUs, so plan on 5-8 minutes `[ASSUMED]`.
- `core.autocrlf`: Git for Windows images default to `true` `[ASSUMED]`, which would rewrite tracked text files to CRLF at checkout. `.gitattributes` protects `tests/fixtures/**` (`-text`) but not other tests that read tracked files byte-exactly. Setting it false before checkout is cheap insurance; verify on the first run.
- Skip budget script: `check_skip_budget.py` parses `testsuite@skipped` and `@tests` from the junit file; also enforce a `--min-passed` floor, because a silent mass deselection would otherwise look green (PITFALLS 11). Measured baseline for the floor: 3,911 passed.
- The deselected counts (corpus, needs_kicad) are not in junit; print them from `pytest_terminal_summary` and let the script grep them from the step log if desired.
- Pin the action tags to major versions as above; for a stricter posture pin to commit SHAs `[ASSUMED]`. Do not use `pull_request_target`.
- Not needed on the runner: KiCad (no `kicad_cli` tests in the quick run; they are slow-marked), the collection, `downloaded_examples/`, a git identity (git-repo-creating tests are slow).

## Collection-Side Cutover (D-01, D-06, D-07, D-22, D-23, focus 6)

### 1. Remove-code commit (rehearsed this session in a scratch `--no-local` clone)
```bash
git rm -r -q --cached downloaded_examples            # file stays on disk, becomes untracked
git rm -r -q kicad_lib_manager kicad_lib_manager.py tests .planning pyproject.toml \
  requirements.txt requirements-dev.txt reports research_notes .gitattributes README.md CLAUDE.md
# then write the new README.md + CLAUDE.md, edit .gitignore (drop the zip exception), git add, commit
```
Result in the scratch clone `[VERIFIED: git ls-files / git ls-tree this session]`: remaining tracked files were exactly `.gitignore`, `.gitmodules`, and the two gitlinks, with the same SHAs:
`160000 commit bbd48c5f3648e10e769840e29c72c64926a7f433	Custom` and `160000 commit ddb5a9ea669b907f009f764b245e39d32ac15bd1	WurthElektronik/KiCad-Library`. `.gitmodules` entries (verbatim): `path = WurthElektronik/KiCad-Library` / `url = https://github.com/WurthElektronik/KiCad-Library.git` and `path = Custom` / `url = https://github.com/sylvanoMTL/kicad_custom_library.git`.
Observations for the live run:
- Leftover untracked folders (`kicad_lib_manager/`, `tests/` holding `__pycache__`) remain after `git rm`; remove them by name after checking they hold only caches. Never `git clean -x` (see anti-patterns).
- `git rm` on a path that lists the gitlinks would drop them; always use the explicit list. After the commit, assert with `git ls-tree HEAD` that both `160000` lines are unchanged.
- The owner's GUI must be closed first: the live app in the main checkout runs from `kicad_lib_manager/`.
- `README.md` and `CLAUDE.md` are replaced, not just removed, in the same commit (the collection needs both, D-07).

### 2. Rehearsal that can init submodules offline
`git clone --no-local` leaves `Custom` and `WurthElektronik/KiCad-Library` as empty folders, so URIs under them cannot resolve. Verified: this initialises `Custom` from a local copy in 1.5 s, leaves the registered URL pointing at GitHub, and checks out the recorded SHA:
```bash
git -c protocol.file.allow=always \
    -c "url.<local path to a Custom working copy>.insteadOf=https://github.com/sylvanoMTL/kicad_custom_library.git" \
    submodule update --init Custom
# prints: Submodule path 'Custom': checked out 'bbd48c5f3648e10e769840e29c72c64926a7f433'
```
`[VERIFIED: run in the scratch clone]`. Do the same for the Würth submodule with its own `insteadOf`. The rehearsal must never `git push` (the submodule's origin is still the GitHub URL).

### 3. Resolved-URI diff (D-22)
Stdlib script `scripts/split/uri_diff.py` with `snapshot --tables-dir DIR --lib-root DIR --out FILE` and `compare A B`:
1. read `sym-lib-table` and `fp-lib-table` (and `kicad_common.json` `environment.vars`) from KiCad's config folder, or from a scratch copy of them in the rehearsal (copy the two files into a scratch folder; never write to KiCad's folder);
2. take every `(lib (name ...)(type ...)(uri "..."))`, expand `${VAR}` from, in order, `--var NAME=VALUE`, `environment.vars`, the process environment (`KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR`); built-ins such as `${KICAD9_SYMBOL_DIR}` are reported as `expanded: false` and compared as text;
3. `exists` = the resolved path exists; replace the library root prefix by `<LIB>` so a scratch collection and the live one compare equal;
4. `compare` passes only if the lists are identical and the missing count is 0.
A working prototype (about 40 lines) ran against a generated table in the scratch clone: for a symbol file that exists it printed `<LIB>/custom/symbols/... True True`; for a missing file `True False`; for a `${KICAD9_SYMBOL_DIR}` entry `False False` `[VERIFIED: prototype run]`. The table entry shape is the repo's own fixture `tests/fixtures/tables/basic.sym-lib-table`: `(lib (name "Fixture_A")(type "KiCad")(uri "${KICAD_LIB_GITHUB}/Custom/Symbols/Fixture_A.kicad_sym")(options "")(descr ""))`. This research did not read KiCad's live config files (read-only constraint); the executor must record the real table count before the live cutover.

### 4. `Source.LEGACY` removal (all places)
| File | Line | Change |
|---|---|---|
| `kicad_lib_manager/collection.py` | 97 `LEGACY = "the folder this app runs from"` | delete the member |
| same | 273 `where = f"the folder this app runs from ({nxt.path})"` in `_chosen_note` | the `else` branch goes; `nxt` can only be KICAD now. Keep `APP_DIR` (line 25): `check_new_collection` still refuses a new collection inside the app folder (lines 416-460) |
| same | 306 comment `# a failing LEGACY candidate adds nothing` | delete |
| `kicad_lib_manager/startup.py` | 70, 72, 99-100 (`build_candidates(..., app_dir=APP_DIR)`, docstring "CLI, ENV, CHOSEN, KICAD, LEGACY", `if is_collection(app_dir): add(Candidate(Path(app_dir), Source.LEGACY))`); 165 and 184 (`start_window(app_dir=...)` passes it through) | drop the parameter and the branch |
| `kicad_lib_manager/main_window.py` | 319 `source: Source = Source.LEGACY,` | needs a new default (suggest `Source.CHOSEN`); 6 test call sites build `MainWindow(` without `source` |
| `kicad_lib_manager/widgets/help_dialog.py` | 125-126 | the `<li>the folder the app runs from, when it is a collection ...` item goes |
| `CLAUDE.md` | GUI Behavior "Library folder" bullet | text and the tag list lose "the folder this app runs from" |
| tests | `test_collection.py` (6 mentions: `cands(... legacy="e")` at 217, `result.source is Source.LEGACY` at 276, the `_chosen_note` text assertions at 254 and 287, `test_legacy_failure_is_silent`, `test_notes_keep_their_order`), `test_startup.py` (163, 244-255 `test_full_order` last case, 337/344/511 `app_dir=` args, `seams.app_dir` at 37/69) | delete or rewrite; the order test ends at KICAD |

### 5. Repoint `_live_custom_untouched` (`tests/conftest.py:545-552`)
Current body: `yield from guard_custom(REPO_ROOT / "Custom")`. `guard_custom` (`tests/customfixtures.py:460-476`) already "Does nothing when there was no Custom/ to watch at the start", so a corpus-free run is safe. Change the argument to `corpus_root() / "Custom"` when `KICAD_TEST_CORPUS` is valid, else nothing. Keep the failure text `the test run changed the live Custom/ folder: <paths>`; `tests/README.md` and `CLAUDE.md` quote it.

### 6. Keeping `Claude-Session` out of public commits (D-13)
Three layers, because one is not enough:
1. **Instruction:** the session's attribution reminder says a user's CLAUDE.md or memory rule takes precedence over its lines, so put one rule in the tool CLAUDE.md: never add a `Claude-Session:` line or session URL to commits in this repo. Keep `Co-Authored-By`.
2. **Settings:** Claude Code has `attribution.sessionUrl` ("Omit the claude.ai session link from cloud and Remote Control commits") `[CITED: code.claude.com/docs/en/settings-reference, settings index]`; it is a boolean, added in v2.1.183, and issue-tracker reports say empty `attribution.commit`/`pr` strings alone did not remove the link `[CITED: web search results, claudeissues.com threads 41873, 83226]`. Set `{"attribution": {"sessionUrl": false}}` in the tool checkout's `.claude/settings.local.json` (ignored by git). Reliability for local sessions is unproven: treat as a convenience.
3. **Hard stop:** a tracked `.githooks/commit-msg` that deletes lines matching `^Claude-Session:` and any `claude.ai/code/session` URL, enabled once with `git config core.hooksPath .githooks` in the tool checkout; plus the scan's `session_trailer` rule over all commit messages in CI and before the flip. The GSD commit helper (`gsd-tools query commit`) goes through `git commit`, so the hook covers it `[ASSUMED]`.

### 7. Order of operations for the live run
bundle both repos and tag `pre-split` -> merge `feature/part-importer` into `main`, push `v2.0`, delete the 8 stray branches (D-06) -> URI snapshot **before** -> build the tool repo from a scratch clone at `pre-split` -> scan -> `gh repo create ... --private`, push -> CI green -> fresh clone of the GitHub copy, own `env/`, quick pytest -> remove-code commit in the main checkout, then URI snapshot **after** and `compare` -> `gh repo edit sylvanoMTL/kicad_libraries --visibility private --accept-visibility-change-consequences`, same for `kicad_custom_library` (the flag is required: `[VERIFIED: gh repo edit --help]` "When the `--visibility` flag is used, `--accept-visibility-change-consequences` flag is required.") -> owner flips the tool repo public -> retire the worktree (`git worktree remove --force` after copying the worktree-only real zips to the collection's `downloaded_examples/`; ignored files block a plain remove) -> move the auto-memory folder to the new project path.

## Project Constraints (from CLAUDE.md)

Directives the plan must keep (root `CLAUDE.md` and `.claude/CLAUDE.md`):
- Python 3.10+ syntax floor today (venv on 3.14, PySide6 6.12, stdlib only otherwise "unless a dependency is clearly justified"): every script in this phase is stdlib; no new dependency.
- Windows 11 primary, standard CPython (not MSYS2); keep the existing cross-platform branches working.
- Safety: no write without a preview first; writes to KiCad files and the repo atomic or backed up; git commits need explicit confirmation. The live cutover is interactive and every irreversible step (visibility, flip, branch deletion, worktree removal) is owner-confirmed.
- Tests: `.\env\Scripts\python.exe -m pytest` (quick, parallel, skips `slow`); `--full` for the rest; a test that creates a real git repository must carry `@pytest.mark.slow` (enforced with the messages `<nodeid> builds a real git repository: mark it @pytest.mark.slow` and `... creates a real git repository (<command>): mark it @pytest.mark.slow`); every test has a 300 s timeout; every test gets its own empty user folders, QSettings ini and KiCad config folder; the run-level guards `the test run changed the real app state` and `the test run changed the live Custom/ folder` must keep working when no collection is present.
- Naming and structure conventions: snake_case modules, `_on_<event>` handlers, `Path` for all filesystem work, `list[str]` message returns from side-effecting helpers, services do not import Qt, `main_window` is never imported from lower modules.
- GSD enforcement: edits start through a GSD command; this phase is interactive (`/gsd-discuss-phase` then step-by-step execution, not `/gsd-autonomous`).
- D-26 (wrong-checkout rule): the live split runs from the main checkout KiCad reads, never from a worktree.
- Docs that currently quote moved or removed text: `CLAUDE.md` GUI Behavior bullet on the library folder, `tests/README.md` (expected-skips table: "On the workstation the expected skips are exactly six"), `kicad_lib_manager/widgets/help_dialog.py` (User Guide). All three need the same edits as the code.

## Runtime State Inventory

This phase moves the app to a new path and the libraries stay put, so the five categories were answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `%APPDATA%/KiCadExtLibManager/settings.ini` (chosen library folder `library/root`, recent collections, destination history, window geometry) and `scan_cache/<one file per library folder>` hold the main checkout path, which does not change. The scan cache compares a code signature (`kicad_lib_manager/scan_cache.py:269` `return _code_signature_of(Path(__file__).parent)`), so the first start of the app from the new tool checkout does one full rescan | none; expect one full scan after the move. Not a data migration |
| Live service config | KiCad's `kicad_common.json` `environment.vars` (`KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR`, `WE_3DMODEL_DIR`) and the global `sym-lib-table`/`fp-lib-table` with `${KICAD_LIB_GITHUB}/...` URIs point at the main checkout's library folders; GitHub repo visibility; Git Credential Manager entry used to fetch the soon-private `Custom` | none for KiCad (layout identical; proven by the URI diff). GitHub: `gh repo edit` x2 (owner-confirmed). After D-11 a fresh `git submodule update` of the collection needs the owner's credentials |
| OS-registered state | Not inspected (no read of the owner's shell or Task Scheduler). Possible: a desktop or Start-menu shortcut, a terminal profile or an alias that runs `kicad_lib_manager.py` from the main checkout `[ASSUMED]` | owner checks before removing `kicad_lib_manager.py` from the main checkout; repoint to the tool checkout's `env\Scripts\python.exe kicad_lib_manager.py` |
| Secrets/env vars | `KICAD_LIBMGR_ROOT` (optional), `KICAD_LIB_GITHUB`, `CUSTOM_3DMODEL_DIR`, `WE_3DMODEL_DIR`: names unchanged. New: `KICAD_TEST_CORPUS` | document `KICAD_TEST_CORPUS` in tests/README and the tool CLAUDE.md; no secret is renamed |
| Build artifacts / installed packages | Main checkout: `env/` and `env-py311/` venvs bound to that path, `__pycache__`, `.pytest_cache`, `.ruff_cache`. This worktree: `env/`, `.venv/`, `.claude/` (GSD install and local settings), `.gsd/`, `.planning/phases/14-*/__pycache__`, five real vendor zips in `downloaded_examples/` (ignored, untracked). The auto-memory folder is keyed by the project path | new `env/` in the tool checkout first (D-08), delete the old venvs only afterwards; local GSD install in the tool checkout; copy the five zips to the collection's `downloaded_examples/` before `git worktree remove --force`; move the memory folder |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Public tool history | a filtered rewrite of 1,812 commits | `git archive <tag> -- <allow-list>` into a new repo (D-02) | allow-list semantics: anything unnamed is absent; no `filter-repo` + gitlink risk |
| Zip fixtures | raw `zipfile` writes in each test | `zipfixtures.make_zip` / `zip_bytes` plus an explicit `ZipInfo(date_time=...)` | existing helpers handle duplicates, encryption, corruption; fixed dates give reproducible bytes |
| UL/SnapEDA/SamacSys sample packages | copies of vendor files | builders in `tests/vendorfixtures.py` | the module already states the licence rule and has the pattern and an originality test |
| Marker/deselect reporting under xdist | a custom plugin | `pytest_collection_modifyitems` + `config.hook.pytest_deselected(items=...)` + the existing `<run temp>/timeouts/` file pattern | the hook is the supported way; the file pattern is already in `tests/conftest.py` |
| Resolving KiCad table URIs | a new S-expression parser | one regex over `(lib (name ...)(type ...)(uri ...))` for the proof script; the app's own `table_generator.parse_lib_table` for app code | the tables are flat and the proof must be independent of the app code being split |
| Repo creation and visibility | REST calls | `gh repo create --private`, `gh repo edit --visibility ... --accept-visibility-change-consequences` | verified flags; owner-confirmed |
| Git work in scripts that run from the app side | `subprocess.run(["git", ...])` | `kicad_lib_manager.procs.run_process()` and `gitops.py` (the CONTEXT's reusable assets) | consistent timeouts and no console flashes. The split scripts themselves can be plain stdlib |
| Secrets patterns | invented regexes | the gitleaks rule shapes listed in the scan section | well-known shapes with low false-positive rates |

**Key insight:** every hard part of this phase has an existing in-repo pattern (vendor builders, the run-temp reporting files, `guard_custom`, scratch collections, `RepoLayout`); the risk is in the wiring, not in new technology.

## Common Pitfalls

### Pitfall 1: The public suite goes green by skipping
**What goes wrong:** with real samples and `Custom/` absent, today's tests skip quietly; a vendor-format regression ships green (PITFALLS 11).
**Why:** module-level `skipif(not path.exists())` and in-test `pytest.skip(...)`.
**Avoid:** the `corpus` marker deselects with a printed count; the budget script enforces both a skip ceiling and a `--min-passed` floor (3,911 measured); the owner runs the corpus suite (`KICAD_TEST_CORPUS`) before each release and before the flip.
**Warning signs:** passed count drops, deselected count rises, a new `pytest.skip` in a diff.

### Pitfall 2: The synthetic UL package drifts from what Ultra Librarian really ships
**What goes wrong:** the builder keeps the 31 modules green while the real format changes or the builder omits a quirk (CRLF, `(id N)` properties).
**Avoid:** keep the real zip as corpus data and add one corpus test that runs the UL adapter on both and compares the structural facts (member names, kinds, property names, pad/pin counts); the originality test stops the builder becoming a byte copy.

### Pitfall 3: Non-deterministic zip bytes
**What goes wrong:** `zf.writestr(name, data)` stamps the current time, so two builds differ (the existing determinism assertion at `test_vendorfixtures.py` compares two builds made a moment apart; whether it can flake across a 2-second DOS-time boundary is unverified), and a content-addressed cache key changes every run.
**Avoid:** `ZipInfo(name, date_time=(2026,10,18,9,12,48))` with `compress_type=ZIP_DEFLATED` for every member.

### Pitfall 4: Parallel workers racing on the generated UL file
**Avoid:** write to `<name>.tmp-<pid>` then `os.replace`; the content-addressed folder makes a second writer produce identical bytes.

### Pitfall 5: Deselected count invisible under xdist
**Avoid:** worker-written count files read by the controller (see Pattern 2). Do not rely on pytest's own `N deselected` line.

### Pitfall 6: The skip budget is unreachable on a clean runner
Measured 13-15 skips without KiCad (see skip budget). Decide before writing the budget script (Open Question 1).

### Pitfall 7: `git rm` / `git clean` damage in the checkout KiCad reads
`git rm -r .` removes the gitlinks; `git clean -fdx` deletes `env/`, `downloaded_examples/*` and generated tables. Explicit path list; verify `git ls-tree HEAD` afterwards; bundle and `pre-split` tag first (PITFALLS 8).

### Pitfall 8: The scan leaks what it finds, or hard-codes the owner
Print rule name and `path:line` only; take identity terms from the old repo and an untracked file at run time (the script is public).

### Pitfall 9: A generic secret rule flags a test string
`tests/test_isolation.py:310` `_SECRET = "secret-token-1405"` matches. Add an inline allow marker; do not weaken the rule. <!-- scan: allow secret -->

### Pitfall 10: This phase's own planning files are in the tree being scanned
CONTEXT.md, DISCUSSION-LOG.md and this file carry workstation paths. Scrub them with the others before the first commit of the tool repo; run the scan on the exported tree, not only on the old one.

### Pitfall 11: Removing the worktree deletes the only copy of ignored data
The worktree holds the five real vendor zips (ignored, untracked) in `downloaded_examples/`. `git worktree remove` refuses on ignored/untracked content without `--force`. Copy them to the collection's `downloaded_examples/` first and diff the folder listing. (The main checkout was not inspected; check it first, it may already have them.)

### Pitfall 12: `test_pyproject_is_pytest_config_only` forbids `[project]`
`tests/test_manifests.py` asserts `set(data) == {"tool"}`, and `test_installed_versions_match_pins` asserts exact installed versions (`pytest==9.1.1` etc.). Adding `[project]` metadata in this phase means editing that test; D-14 allows deferring the SPDX field to Phase 20. Recommendation: LICENSE file now, metadata later.

### Pitfall 13: `_section()` raises when a heading moves
`tests/test_docs_atomic.py` uses `text.index(heading)`. After the CLAUDE.md split, a missing heading is a `ValueError` at test time, not a clean failure. Rewrite or delete those tests in the same plan as the doc split.

### Pitfall 14: Recorded gitlink versus checked-out submodule
CONTEXT.md notes `Custom` checked out at one SHA while the parent records another. In this worktree both are `bbd48c5` (`git submodule status` showed a leading space, `git ls-tree HEAD Custom` showed `bbd48c5f3648e10e769840e29c72c64926a7f433`), so the note refers to another checkout or is stale `[VERIFIED: this worktree]`. Settle it from the main checkout before the split; the remove-code commit must not move either gitlink.

### Pitfall 15: Windows line-ending conversion on the runner
See CI section: set `core.autocrlf false` before checkout; keep `tests/fixtures/** -text`.

## Code Examples

### `corpus` and `needs_kicad` gate (sketch for `tests/conftest.py`)
```python
CORPUS_ENV = "KICAD_TEST_CORPUS"

def corpus_root() -> Path | None:
    raw = os.environ.get(CORPUS_ENV, "").strip()
    if not raw:
        return None
    root = Path(raw)
    if not (root / "Custom").is_dir():
        raise pytest.UsageError(f"{CORPUS_ENV}={raw!r} is not a library collection (no Custom/ folder)")
    return root

@pytest.hookimpl(tryfirst=True)               # same ordering as the existing slow-marking hook (line 66)
def pytest_collection_modifyitems(config, items):
    held: dict[str, list] = {"corpus": [], "needs_kicad": []}
    if corpus_root() is None:
        held["corpus"] = [i for i in items if i.get_closest_marker("corpus")]
    if find_kicad_footprint_dir() is None:
        held["needs_kicad"] = [i for i in items if i.get_closest_marker("needs_kicad")]
    gone = {id(i) for group in held.values() for i in group}
    if gone:
        config.hook.pytest_deselected(items=[i for g in held.values() for i in g])
        items[:] = [i for i in items if id(i) not in gone]
    _record_deselected(config, {name: len(group) for name, group in held.items()})   # worker -> run temp file
```
Corpus tests then get paths from one helper (`corpus_root() / "downloaded_examples" / name`), never from `REPO_ROOT`.

### UL builder skeleton (for `tests/vendorfixtures.py`)
```python
UL_ZIP_NAME = "ul_CSD85301Q2.zip"
UL_MEMBERS_ORDER = ("DLV0006A.stp", "ImportGuides.html", "readme.txt",
                    "KiCADv6/2026-10-18_09-12-49.kicad_sym", "KiCADv6/ImportGuide.html",
                    "KiCADv6/footprints.pretty/DQK0006B.kicad_mod")

def _crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")

def ul_members() -> list[tuple[zipfile.ZipInfo, bytes]]:
    data = {"DLV0006A.stp": _crlf(_STEP_TEXT), ...}      # each body written from scratch
    return [(zipfile.ZipInfo(name, date_time=(2026, 10, 18, 9, 12, 48)), data[name]) for name in UL_MEMBERS_ORDER]

def ul_zip(path: Path) -> Path:
    return make_zip(path, ul_members())                  # zipfixtures.make_zip accepts ZipInfo members
```
(`ZipInfo.compress_type` must be set to `ZIP_DEFLATED` per member; the default for a bare `ZipInfo` is stored.)

### commit-msg hook (`.githooks/commit-msg`)
```sh
#!/bin/sh
sed -i -e '/^Claude-Session:/d' -e '/claude\.ai\/code\/session/d' "$1"
```
Enable once per clone: `git config core.hooksPath .githooks`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| History rewrite with `git filter-repo --path ...` (milestone research option a) | fresh history from an allow-listed `git archive` | decided D-02 | scan walks a tiny history; the 1,812-commit archive stays private |
| Corpus tests skip when data is absent | deselect with a printed count, fail loudly when `KICAD_TEST_CORPUS` is set but wrong | this phase | no quiet green |
| `actions/checkout@v4`/`setup-python@v5` era snippets | `@v7` tags (`checkout` v7.0.1, `setup-python` v7.1.0 at research time) | 2026 | `[CITED: GitHub releases pages]`; v6 of setup-python moved to Node 24 and needs runner >= 2.327.1 |

**Deprecated/outdated:** Claude Code's `includeCoAuthoredBy` is deprecated in favour of `attribution` `[CITED: settings-reference index]`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Building `UL_ZIP` at import into a content-addressed temp folder is the least invasive design (alternative: a gitignored `tests/_generated/`) | UL builder | Planner picks the other location; low |
| A2 | gitleaks can be added later as an extra CI step | Stack | none |
| A3 | Git for Windows on `windows-latest` defaults to `core.autocrlf=true` | CI | If false already, the step is harmless |
| A4 | GitHub Windows runners can create symlinks, so the 2 symlink skips do not occur | Skip budget | CI count is 15 instead of 13 |
| A5 | CI wall time 5-8 minutes on 4 vCPU (extrapolated from 100 s on 16 CPUs) | CI | Set `timeout-minutes` higher |
| A6 | Private-repo Actions minutes are metered (Windows at a multiplier) and a few runs fit the free allowance | CI | Owner may need to wait for the flip to public before heavy CI |
| A7 | The GSD commit helper calls `git commit`, so `core.hooksPath` hooks apply | Cutover 6 | Strip the trailer another way |
| A8 | PySide6 6.12.0 + pytest-qt run offscreen on the runner without extra system libraries | CI | First CI run fails on Qt platform plugin; add a step |
| A9 | Pinning actions to major tags is acceptable; SHA pinning is stricter | CI | Owner preference |
| A10 | No shortcut, alias or scheduled task points at the main checkout's `kicad_lib_manager.py` | Runtime state | Launcher breaks after the remove-code commit |
| A11 | `attribution.sessionUrl: false` stops the session URL line in local sessions | Cutover 6 | The hook and the scan still catch it |
| A12 | The owner's `gh` token has the scope to change repo visibility | Cutover 7 | `gh repo edit` fails; re-auth |
| A13 | The runner image has Git and Windows PowerShell on PATH (the `test_commit_step.py:1228` PowerShell test and git-based tests need them) | CI | Two tests skip or fail |

## Open Questions (RESOLVED)

All seven were settled at plan time (2026-11-24). Each answer below is the one the Phase 16 plans implement.

1. **Skip budget versus a runner without KiCad (needs an owner/planner decision).**
   - Known: after the corpus move, a machine with KiCad has 3 skips; a runner without it has 15 (13 without symlink skips); D-19 says at most 10 and names the KiCad skips as the expected ones.
   - Unclear: whether to raise the budget (to 15) or to take the 12 KiCad-install tests out of the skip count.
   - Recommendation: add a `needs_kicad` marker handled exactly like `corpus` (deselected with a printed count when no KiCad install is found), leaving 3 skips and a budget of 10 that means something. Keep the 12 tests in the owner's quick run on the workstation.
   - **RESOLVED (D-19b, the owner's choice):** a registered `needs_kicad` marker, deselected with a printed count when KiCad is not found, like `corpus`; the budget stays at most 10 skips and `needs_kicad` tests do not count toward it. Plan 16-06 Task 2 adds the marker and the `KICAD_TEST_HIDE_KICAD` switch, plan 16-10 marks the twelve stock-library tests, and plan 16-03 Task 2 enforces the budget in CI (`--max-skips 10 --min-passed 3500`).
2. **Where the generated UL zip lives** (A1). Recommendation: content-addressed temp folder.
   - **RESOLVED:** a content-addressed temp folder. `ul_sample_zip()` in `tests/ulfixtures.py` (plan 16-01 Task 1) writes the zip under the system temp folder, in a folder named after the first 12 hex characters of its SHA-256, through a temporary name and `os.replace`; there is no gitignored `tests/_generated/`.
3. **`MILESTONES.md` and `RETROSPECTIVE.md`.** Neither trips the scan; both are v1/v2 history. Recommendation: drop `RETROSPECTIVE.md`; keep `MILESTONES.md` only if the owner wants a public changelog.
   - **RESOLVED (D-05, planner's allow-list call):** both stay out of the tool repo. They are not on `scripts/split/allowlist.txt`, and `scripts/split/verify_export.py` hard-denies `.planning/MILESTONES.md` and `.planning/RETROSPECTIVE.md` (plan 16-04 Task 1). Both stay in the private collection's history. A public changelog is not part of this phase.
4. **State of the main checkout** (not inspected here by constraint): the checked-out `Custom` SHA versus the recorded gitlink, whether the five real zips are already in its `downloaded_examples/`, and whether `env-py311/` is still needed.
   - **RESOLVED (answered live, by named tasks):** plan 16-13 Task 1, the read-only preflight, reports `git submodule status` of the main checkout against the recorded gitlinks and compares its `downloaded_examples/` with the feature checkout's. A gitlink mismatch is settled by the owner in plan 16-13 Task 2 (the option that records the checked-out `Custom` commit, or leave it as it is). The real downloads missing from the main checkout are copied and hash-compared in plan 16-16 Task 1, before the worktree is retired. `env-py311/` is listed by plan 16-15 Task 1, and the owner decides in plan 16-15 Task 2 whether it is deleted after the smoke start (D-08).
5. **The `wurth` marker.** Recommendation: keep it as a subset marker implying `corpus` and `slow`; `test_manifests.py:57` asserts a `wurth:` marker exists, so removing it needs a test edit.
   - **RESOLVED:** `wurth` stays as a subset marker that implies `corpus` and `slow`. Plan 16-06 adds the `corpus` mark to every `wurth` item and rewords the marker (Task 1 and Task 2), so the `wurth:` check in `test_manifests.py` still holds.
6. **`[project]` metadata now or Phase 20.** Recommendation: Phase 20 (Pitfall 12).
   - **RESOLVED:** Phase 20. This phase adds no `[project]` table, so `test_manifests.py`'s `set(data) == {"tool"}` stays true (plan 16-06). The MIT licence ships as the `LICENSE` file (plan 16-07 Task 1, D-14), and the SPDX `license` field comes with the metadata in Phase 20.
7. **`attribution.sessionUrl` behaviour** is only documented in the settings index plus third-party issue threads; test it with one throwaway commit in the private tool repo before relying on it.
   - **RESOLVED (not relied on):** plan 16-14 Task 3 sets `attribution.sessionUrl: false` only as a convenience. Three layers are the guarantee: the commit-msg hook `.githooks/commit-msg` (plan 16-04, `test_commit_msg_strips_the_session_line`), the rehearsal's throwaway hook commit (plan 16-12 Task 2 step 6), and the scan's `session_trailer` rule (plan 16-03). The throwaway commit the question asks for is that rehearsal check, and it does not depend on the setting.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 + `env/` | all scripts and tests | yes | 3.14.4 | none needed |
| git | export, rehearsal, scan | yes | 2.49.0.windows.1 | none |
| gh (authenticated) | repo create, visibility | yes | 2.88.1 | web UI |
| KiCad install | `needs_kicad` tests, `kicad_cli` tests | yes on the workstation | 10.0 and 9.0 under `Program Files\KiCad` | deselected on CI by design |
| gitleaks | optional extra scan | no | — | stdlib script (chosen) |
| Network to GitHub | repo create, CI, fresh-clone test | yes (read-only calls worked) | — | — |
| Node | GSD tooling | yes | v26.13.1 | — |
| Target repo name `sylvanoMTL/kicad-lib-manager` | create | free (`gh repo view` reports it cannot be resolved) | — | pick another name (D-03 locked) |
| Both existing repos | cutover | PUBLIC today, 0 forks, 0 stars, default branch `main` (`gh repo view --json`) `[VERIFIED]` | — | — |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-qt 4.5.0 + pytest-xdist 3.8.0 + pytest-timeout 2.4.0 (`requirements-dev.txt`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; `addopts = "-ra --strict-markers -n 8 --dist worksteal -m 'not slow'"` (line 4) |
| Quick run command | `.\env\Scripts\python.exe -m pytest` (3,911 passed / 29 skipped / 100 s in a scratch clone with the zip, no collection) |
| Full suite command | `.\env\Scripts\python.exe -m pytest --full`; corpus: `$env:KICAD_TEST_CORPUS = "<main checkout>"` then either command |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLIT-01 | exported tool tree is a subset of the allow-list and has no `Custom`/`WurthElektronik`/`downloaded_examples` | script check on the export | `python scripts/split/verify_export.py <dir> --allow-list scripts/split/allowlist.txt` | no, Wave 0 |
| SPLIT-02 | before/after resolved URI lists identical, zero missing | script + unit test of the resolver on fixture tables | `python scripts/split/uri_diff.py compare before.json after.json`; `pytest tests/test_uri_diff.py` | no, Wave 0 |
| SPLIT-03 | blocking classes detected; clean export exits 0 | unit (pure functions) + one slow git-history test | `pytest tests/test_prepublish_scan.py`; `python scripts/prepublish_scan.py --tree --history` | no, Wave 0 |
| SPLIT-04 | fresh clone without collection passes within budget | CI job + local fresh-clone run | `pytest --junitxml=junit.xml` then `python scripts/check_skip_budget.py junit.xml --max-skips 10 --min-passed 3500`; `pytest tests/test_skip_budget.py` | no, Wave 0 |
| SPLIT-04 | `corpus`/`needs_kicad` deselection prints counts, wrong `KICAD_TEST_CORPUS` fails | meta-test via `runfixtures.run_pytest` (pattern in `test_isolation.py`) | `pytest tests/test_corpus_gate.py` | no, Wave 0 |
| SPLIT-04 | UL builder is adapter-compatible and deterministic | unit | `pytest tests/test_vendorfixtures.py -k ultra` | partly (file exists, tests new) |
| SPLIT-05/06 | LICENSE present; README has install and first-run sections; collection docs carry naming, atomic rule, path variables | doc check | `pytest tests/test_docs_split.py` (replaces `test_docs_atomic.py`) | no, Wave 0 |
| SPLIT-07 | visibility set | manual, evidence in the plan summary | `gh repo view <repo> --json visibility` | manual |
| SPLIT-08 | dev workflow documented (`--library-root`, `KICAD_LIBMGR_ROOT`, `KICAD_TEST_CORPUS`) | doc check | same `test_docs_split.py` | no, Wave 0 |

### Sampling Rate
- **Per task commit:** `.\env\Scripts\python.exe -m pytest tests/<touched modules>` and `python scripts/prepublish_scan.py --tree` once the script exists.
- **Per wave merge:** bare `pytest` (about 100 s locally).
- **Phase gate:** the scratch fresh-clone run with no `downloaded_examples/` and no collection green and within budget; the corpus run (`KICAD_TEST_CORPUS`) green on the workstation; scan exit 0 on the exported tree and on the pushed GitHub copy; URI diff identical with 0 missing.

### Wave 0 Gaps
- [ ] `tests/test_prepublish_scan.py`, `scripts/prepublish_scan.py`
- [ ] `tests/test_corpus_gate.py` (marker, deselection count, bad `KICAD_TEST_CORPUS`)
- [ ] `tests/test_skip_budget.py`, `scripts/check_skip_budget.py`
- [ ] `tests/test_uri_diff.py`, `scripts/split/uri_diff.py`
- [ ] `tests/test_docs_split.py` (replaces the deleted `test_docs_atomic.py` cases)
- [ ] UL builder tests in `tests/test_vendorfixtures.py` and the corpus originality test
- [ ] Framework install: none (pins already in `requirements-dev.txt`)

## Security Domain

`security_enforcement` is on in `.planning/config.json` (`"security_enforcement": true`, `"security_asvs_level": 1`), so this section applies. The phase has no network service, authentication or user input surface; the risks are leakage and supply chain.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture / data classification | yes | allow-list export; scan classes in this document |
| V2 Authentication | no (git and `gh` credentials are the owner's, held by Git Credential Manager and the keyring) | never write a token into a file, URL or `.gitmodules` |
| V3 Session Management | no | — |
| V4 Access Control | yes (repo visibility) | private-first, owner-confirmed flip (D-12), `gh repo edit` with the explicit acceptance flag |
| V5 Input Validation | yes, minor | the scan reads untrusted blob bytes: bounded reads, regexes without catastrophic backtracking, no `eval`; scripts take paths as arguments and run with `python -I` when pointed at extracted data |
| V6 Cryptography | no (SHA-256/1 only for identity of content, not security) | — |
| V8 Data Protection | yes | no owner identity, workstation path, vendor file or copied part data in the public tree or history |
| V14 Configuration | yes | CI `permissions: contents: read`, no `pull_request_target`, no secrets in the workflow, actions pinned by tag or SHA |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Owner email, name or workstation path published | Information disclosure | `owner_identity` and `workstation_path` rules, scrub script, scan before push and before the flip |
| Licence-restricted vendor content published (TI zip, Würth data) | Information disclosure / legal | `vendor_file` rule outside `tests/fixtures`, shingle rule against the corpus, synthetic builder, originality test |
| Secret committed (token in a doc, URL with credentials in `.gitmodules`) | Information disclosure | `secret` rules; `.gitmodules` is not copied to the tool repo |
| Session URL or private context in commit messages | Information disclosure | hook + attribution setting + `session_trailer` rule over history |
| Malicious or compromised GitHub Action | Tampering | official `actions/*` only, major-tag or SHA pin, read-only token |
| Rehearsal pushes to the real remote | Tampering | rehearsal clones keep the real remote URL; scripts never call `git push`; the plan states it and the scratch config removes remotes after cloning `[ASSUMED: add `git remote remove origin` in the scratch step]` |
| `git rm` / `git clean` destroys the live checkout KiCad reads | Denial of service (to the owner's KiCad) | bundle + `pre-split` tag first, explicit path list, URI diff gate |
| Real vendor zip opened by a script that runs code from the extracted folder | Elevation / tampering | extract into a new empty folder, run `python -I`, pass paths as arguments (this session did exactly that) |

## Sources

### Primary (HIGH confidence, read or run this session)
- Repo files: `tests/conftest.py` (lines 15-16, 53, 63-77, 426, 501-552), `tests/zipfixtures.py` (24-28, 40, 138-163), `tests/vendorfixtures.py`, `tests/customfixtures.py` (40, 460-476), `tests/installfixtures.py` (36), `tests/test_adapters.py`, `tests/test_roundtrip_corpus.py`, `tests/test_real_vendor_samples.py`, `tests/test_docs_atomic.py`, `tests/test_isolation.py`, `tests/test_markers.py`, `tests/test_manifests.py`, `tests/README.md`, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.gitmodules`, `kicad_lib_manager/collection.py`, `startup.py`, `main_window.py` (319), `importer/adapters/ultralibrarian.py`, `importer/detect.py`, `widgets/help_dialog.py`, `.planning/config.json`.
- Measured runs in a throwaway `git clone --no-local` under the scratchpad (since deleted): quick run with and without the UL zip, with KiCad hidden; remove-code rehearsal; local-path submodule init; URI snapshot prototype; shingle prototype against `Custom/` and the vendor zips.
- `env/Lib/site-packages/_pytest/hookspec.py:436` (`pytest_deselected`), `env/Lib/site-packages/xdist/*.py` (no deselect forwarding).
- `gh repo edit --help`, `gh repo create --help`, `gh repo view --json` (read-only), `git --version`, `gsd-tools query package-legitimacy check`.

### Secondary (MEDIUM confidence, official documentation)
- github.com/actions/setup-python/releases (v7.1.0; v6 moved to Node 24), github.com/actions/checkout/releases (v7.0.1), github.com/actions/runner-images (`windows-latest` = Windows Server 2025), docs.github.com hosted-runners reference (4 vCPU / 16 GB for public repos, free on public repos), code.claude.com/docs/en/settings-reference (index entries for `attribution.sessionUrl`, `attribution.commit`, deprecated `includeCoAuthoredBy`).

### Tertiary (LOW confidence, needs validation)
- Third-party issue threads on whether `attribution.sessionUrl` and empty `attribution` strings remove the session URL from local commits (claudeissues.com 41873, 83226); GitHub Actions private-repo minute metering; runner `core.autocrlf` default.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new; versions read from the repo and the interpreter.
- Architecture and cutover: HIGH for git behaviour and the rehearsal (run); MEDIUM for the live run's unknowns (main checkout not inspected).
- Test classification and skip counts: HIGH (measured); the corpus-group size under a real corpus (8,000+ Würth params) is from collect-only in this worktree.
- CI: MEDIUM (documentation-cited, not executed).
- Pitfalls: HIGH for those reproduced, MEDIUM for platform-default claims tagged ASSUMED.

**Research date:** 2026-11-24
**Valid until:** 2026-12-08 for GitHub Actions versions and Claude Code settings behaviour (fast-moving); the in-repo findings stay valid until the code or tests change.

