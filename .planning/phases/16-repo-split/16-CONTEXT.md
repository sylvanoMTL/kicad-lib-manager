# Phase 16: Repo Split - Context

**Gathered:** 2026-11-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the one repo `sylvanoMTL/kicad_libraries` into two:

- a **new public tool repo** `sylvanoMTL/kicad-lib-manager` holding the app code, tests, pyproject, a scrubbed current `.planning/`, CI and docs, and no library content;
- the **existing repo `kicad_libraries`, made private**, which becomes the library collection (`Custom` and WurthElektronik submodules, collection docs, no code) and keeps the full old history as the private archive.

The owner's KiCad keeps reading the same main checkout with the same path variables, and every table URI resolves before and after. Requirements: SPLIT-01..SPLIT-08. New capabilities (catalog, project-local tables, installer) are later phases.

Note: this file is itself carried into the public tool repo, so it goes through the same scrub (D-09). It names no owner email address on purpose.

</domain>

<decisions>
## Implementation Decisions

### Direction and history (D1, D13)
- **D-01:** The existing `sylvanoMTL/kicad_libraries` becomes the **private collection**. It keeps its full history (all 1,812 commits, the `Custom` and `WurthElektronik/KiCad-Library` gitlinks, `.gitmodules`, tags `v1.0`/`v2.0`). The code is removed in one final "remove app code" commit. KiCad's checkout keeps its git identity and remote. — **Reversibility:** costly — undoing means re-adding the code tree and repointing every dev workflow doc
- **D-02:** The tool repo is a **new repo with a fresh history**. Its first commit is an **allow-listed copy** of today's tree (named paths only, so anything unnamed is absent), not a filtered history. `git filter-repo` is not used. — **Reversibility:** one-way — once public, the first commit's content can't be recalled; the allow-list and the scan (D-09) are the guard
- **D-03:** Tool repo name: **`kicad-lib-manager`** (matches the package `kicad_lib_manager`).
- **D-04:** Collection repo name stays **`sylvanoMTL/kicad_libraries`**, with no remote change in the main checkout.
- **D-05:** `.planning/` in the tool repo is a **scrubbed current set**: `PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `state.json`/`config.json` as needed for GSD, `research/`, `codebase/`, `todos/` and the v3.0 phase dirs (`phases/14-*`, `15-*`, `16-*`), with workstation paths replaced by placeholders. The v1/v2 milestone archives (`milestones/`), `quick/`, `debug/`, `MILESTONES.md`/`RETROSPECTIVE.md` (if they carry v1/v2 detail) stay **only** in the private collection's history. The planner decides the exact allow-list per file after a content pass.
- **D-06:** **Before the split:** merge `feature/part-importer` into `main`, push the `v2.0` tag to `kicad_libraries`, delete the 8 stray `worktree-agent-*` branches (local), and split from `main`.
- **D-07:** The collection's final tree keeps only the `Custom` gitlink, the `WurthElektronik/KiCad-Library` gitlink, `.gitmodules`, `.gitignore` (env/, generated `sym-lib-table`/`fp-lib-table`, backups, `downloaded_examples/*`), a **collection README** and a **short collection CLAUDE.md**. It removes `kicad_lib_manager/`, `kicad_lib_manager.py`, `tests/`, `pyproject.toml`, `requirements*.txt`, `.planning/`, `reports/`, `research_notes/`, `.gitattributes` if it is code-only, and the tracked `downloaded_examples/ul_CSD85301Q2.zip` (the file stays on disk as untracked local data).
- **D-08:** Venvs: the tool checkout gets its **own `env/` (Python 3.14, PySide6 6.12)**. The main checkout's `env/` and `env-py311/` are deleted only after the new venv runs the app against the main checkout.

### Visibility and identity (D14)
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

### Licence and vendor data (D10, D12)
- **D-14:** Licence: **MIT** (`LICENSE` at the root, with SPDX `license = "MIT"` in pyproject when the metadata is added). It covers the code only.
- **D-15:** `ul_CSD85301Q2.zip` is replaced in the public repo by a **synthetic builder** in `tests/`. It produces an Ultra-Librarian-shaped zip with the same folder layout, file kinds and quirks the UL adapter relies on. The `ul_package` fixture uses the builder. The real zip stays local in the collection's `downloaded_examples/` and is used only by the opt-in corpus run (D-17). — **Reversibility:** reversible
- **D-16:** `reports/` and `research_notes/` are **left out** of the tool repo. They stay in the private collection's history only.
- **D-16b:** The tool README carries a short note: the tool ships no libraries; libraries you add keep their own licences (KiCad CC-BY-SA, Würth's own terms); test fixtures are synthetic. No THIRD-PARTY-NOTICES in this phase (Phase 21).

### Cutover, tests and dev workflow
- **D-17:** Tool checkout at **`<tool-checkout>`**, a plain clone with its own `env/` and a local GSD install (`.claude/` stays gitignored). The `Kicad_Libraries-importer` worktree is **retired** (`git worktree remove`) once the tool checkout passes its tests. Claude's auto-memory for this project moves to the new project path.
- **D-18:** Tests that need real vendor samples, the Würth corpus or the live `Custom/` get a registered **`corpus` marker** and run **only when `KICAD_TEST_CORPUS` names a collection folder** (the owner's main checkout). Otherwise they are **deselected** (reported as a separate count), never quietly skipped. Every other test that today reads `Custom`, `WurthElektronik`, `downloaded_examples`, `.planning` or `REPO_ROOT /` is rebuilt on synthetic fixtures, or deleted when it only tested this repo's layout. Each of the ~25 affected modules is classified in the plan. The existing `wurth` marker folds into or sits beside `corpus` (planner's call).
- **D-19:** **Skip budget:** a fresh-clone quick run has **at most 10 skips** (room for the `kicad_cli`/`local_kicad` skips on a machine without KiCad). Corpus tests don't count, since they're deselected. CI fails above the budget.
- **D-19b:** (added 2026-11-24 at plan time, owner's choice after research measured 15 skips on a runner without KiCad) Tests that need an installed KiCad's stock libraries get a registered **`needs_kicad` marker** and are **deselected with a printed count** when KiCad isn't found, the same way as `corpus`. The D-19 budget stays at **at most 10 skips**; `needs_kicad` tests don't count toward it.
- **D-20:** **Windows CI:** GitHub Actions on `windows-latest`, on push and PR. One job runs bare `pytest` (the quick parallel run, no corpus, no KiCad), the skip-budget check and the pre-publish scan script. No `--full` in CI.
- **D-21:** **CLAUDE.md split:**
  - the tool `CLAUDE.md` holds the project overview, Python env, running the GUI, GUI behaviour, menu shortcuts, tests and the dev workflow (SPLIT-08), with no workstation paths;
  - the collection `CLAUDE.md` plus README hold naming, the atomic rule, path variables, manual import and git workflow;
  - the owner's workstation specifics (main checkout path, the `KICAD_LIB_GITHUB`/`CUSTOM_3DMODEL_DIR` values, the D-26 rule's concrete folders) go into an **untracked `CLAUDE.local.md`** in the tool checkout;
  - `.claude/CLAUDE.md` (the GSD-generated one) follows the same rule.
- **D-22:** **KiCad unchanged proof:** a **resolved-URI diff**. A script resolves every URI in KiCad's global `sym-lib-table` and `fp-lib-table` (plus the `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` values) before and after. It needs **zero missing and an identical list**. The owner chose this as the required check; a 3D-model path check, a manual KiCad project open and an app rescan are not required (they may be run as extras).
- **D-23:** **Rehearsal:** a **full dry run on `git clone --no-local` copies** in a scratch folder: build the tool repo, make the collection's remove-code commit, run the tests from a fresh clone, and run the URI diff against a scratch copy. The live run then repeats the same scripted steps after a `git bundle` of both repos and a `pre-split` tag. The live run happens from the main checkout KiCad reads (D-26), never from this worktree.

### Locked from earlier phases (not re-asked)
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 16: Repo Split": goal, success criteria, notes (rehearsal, D-26, CI, corpus opt-in, CLAUDE.md split)
- `.planning/REQUIREMENTS.md` §"Repo split (SPLIT)": SPLIT-01..SPLIT-08
- `.planning/PROJECT.md`: Key Decisions table (D-26, the atomic naming), the description of `Custom/`

### Research
- `.planning/research/SUMMARY.md`: Phase 3 (repo split) delivers list, open decisions D1/D10/D12/D13/D14, the verified public-repo fact
- `.planning/research/PITFALLS.md`: Read This First items 1, 4, 5; Pitfalls 8 (splitting the checkout KiCad reads), 9 (private content in public history), 10 (filter-repo/gitlinks: mostly avoided by D-02, but the gitlink and `.gitmodules` rules still apply to the collection's remove-code commit), 11 (tests green by skipping), 12 (submodule assumptions), 22 (licences)
- `.planning/research/STACK.md` and `.planning/research/ARCHITECTURE.md`: their split-direction sections (D1 trade-off; superseded by D-01/D-02)

### Codebase maps
- `.planning/codebase/TESTING.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONCERNS.md`

### Prior phase context
- `.planning/phases/15-choose-library-folder-and-new-collection/`: collection resolution, `Source.LEGACY`, the `parent_mode` commit step, the scratch-collection test pattern
- `.planning/phases/14-test-suite-speed-up/`: markers, isolation fixtures, run-level guards (`tests/README.md`)

### Docs to split
- `CLAUDE.md` (root) and `.claude/CLAUDE.md`: split per D-21
- `README.md`: becomes the tool README; a new collection README is written
- `tests/README.md`: markers and guards, updated for `corpus` / `KICAD_TEST_CORPUS`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `kicad_lib_manager/collection.py`: the folder check, resolve and create. `Source.LEGACY` (line ~97, "the folder this app runs from") gets removed.
- `kicad_lib_manager/procs.py` `run_process()` and `gitops.py`: use these for any scripted git step that runs from the app side. Split scripts can be plain stdlib scripts.
- `tests/conftest.py`: the `ul_package` fixture (line ~501) gets the synthetic builder, and `_live_custom_untouched` (line ~545) gets repointed.
- `tests/gitfixtures.py`: the superproject and collection fixtures (both commit shapes) are already synthetic.
- Phase 15 `create_collection` and the scratch-collection tests: the pattern for corpus-free tests.

### Established Patterns
- `pyproject.toml` today holds only `[tool.pytest.ini_options]` (strict markers, `-n 8 --dist worksteal -m 'not slow'`, timeout 300). The `corpus` marker must be registered there, and the default `-m` expression must deselect it.
- The test run-level guards ("the test run changed the real app state", "the test run changed the live Custom/ folder") must keep working when no collection is present.
- `.gitignore` already treats `downloaded_examples/*` as local, with only the UL zip excepted. After D-07 the exception is dropped.

### Integration Points
- KiCad reads the main checkout through `KICAD_LIB_GITHUB` and `CUSTOM_3DMODEL_DIR` (values in CLAUDE.md "KiCad Path Variables"). Neither changes in this phase.
- Global `sym-lib-table`/`fp-lib-table` in the KiCad config dir: the input to the URI diff (D-22).
- `gh` CLI is authenticated for `sylvanoMTL` (used for repo creation and visibility).

### Facts found while scouting (2026-11-24)
- 1,812 commits, one author email; 8 local `worktree-agent-*` branches; tags `v1.0`, `v2.0` (local, `v2.0` unpushed).
- Tracked top level: `.planning` (677 files, 14 MB), `tests` (164), `kicad_lib_manager` (85), `research_notes` (4), `reports` (1), `downloaded_examples/ul_CSD85301Q2.zip`, `Custom` and `WurthElektronik/KiCad-Library` gitlinks, root files.
- About 296 tracked files contain workstation paths, and about 237 test files mention `REPO_ROOT`, `Custom`, Wurth, `downloaded_examples` or `.planning` (a broad grep; the real reads-outside-`tests/` set is the ~25 modules from PITFALLS).
- Both GitHub repos are PUBLIC, with 0 forks and 0 stars (`gh repo view`, re-checked 2026-11-24).
- In this worktree `Custom` is checked out at 8f7d454 while the parent records d78f3f7. Settle this from the main checkout before the split.

</code_context>

<specifics>
## Specific Ideas

- Order of trust: rehearse everything, bundle and tag, then repeat the same scripted steps live. Build the tool repo private, then scan, then fresh-clone test against GitHub's copy, and only then does the owner flip it to public.
- The collection stays exactly where KiCad looks. The split must not need any change in KiCad Preferences > Configure Paths.
- The public test count must be honest: corpus tests are deselected and counted, not skipped, and the skip budget is enforced in CI.

</specifics>

<deferred>
## Deferred Ideas

- THIRD-PARTY-NOTICES (PySide6/Qt LGPL and others): Phase 21.
- A nightly `--full` CI run: not chosen now; revisit with the Phase 21 release gate.
- Extra KiCad checks (3D-model path check, a manual project open in KiCad 10, an app rescan comparison): not required by the owner; optional extras.
- Python 3.14 minimum in the pyproject metadata: Phase 20.

### Reviewed Todos (not folded)
- "Stop the migration dialog's draft and rebuild timers when it closes" (`todos/pending/2026-11-23-migration-dialog-stop-timers-on-close.md`): unrelated app follow-up that matched on keywords only; left for a quick task.

</deferred>

---

*Phase: 16-repo-split*
*Context gathered: 2026-11-24*
