"""The catalog lifecycle against real git on local repositories (Phase 17 plan 10; slow; CAT-04, CAT-07, CAT-11).

Add, Update, Remove, Reinstall and the update check run against bare repositories built with git plumbing and
reached through file:// addresses, the only transport a test may use; no test touches the network.
"""

import hashlib
import os
import subprocess
from pathlib import Path

import gitfixtures  # noqa: F401  (imported so the slow-marker tripwire can see the running test)
import pytest
from catalogfixtures import (
    FOOTPRINT_TEXT,
    LIB_FILES,
    SYMBOL_TEXT,
    advance_upstream,
    case_collision_upstream,
    delete_branch,
    make_third_party,
    make_upstream,
    upstream_url,
)
from collectionfixtures import make_collection
from gitfixtures import GIT, remove_tree, requires_git

from kicad_lib_manager.catalog import manifest, ops, status
from kicad_lib_manager.catalog.gitnet import NetGit
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.models import Issue, Severity

pytestmark = [pytest.mark.slow, requires_git]

LFS_ATTRIBUTES = "*.step filter=lfs diff=lfs merge=lfs -text\n"
EXTRA_SYMBOL = SYMBOL_TEXT.replace("R_Demo", "R_Extra")
# the second version of LIB_FILES: a new symbol library arrives and the footprint library leaves
V2 = {"symbols/Demo.kicad_sym": SYMBOL_TEXT, "symbols/Extra.kicad_sym": EXTRA_SYMBOL}


def _net() -> NetGit:
    return NetGit(exe=Path(GIT), allow_file=True)


@pytest.fixture
def work(tmp_path):
    """A scratch folder whose git trees (read-only object files) are removed even on Windows."""
    folder = tmp_path / "work"
    folder.mkdir()
    yield folder
    remove_tree(folder)


def _errors(issues):
    return [i for i in issues if i.severity is Severity.ERROR]


def _add(root: Path, bare: Path, id: str = "Demo") -> CatalogEntry:
    """Add the library the way the window does (stage, then register) and return its catalog entry."""
    source = ops.AddSource(id=id, name=id, url=upstream_url(bare), branch="main", vars={}, licence_spdx="MIT")
    staged = ops.stage_add(root, source, _net())
    assert isinstance(staged, ops.Staged), staged
    assert not _errors(ops.register_add(root, staged, allow_file=True))
    entry = manifest.load(root, allow_file=True).find(id)
    assert entry is not None
    return entry


def _entry(root: Path, id: str = "Demo") -> CatalogEntry:
    return manifest.load(root, allow_file=True).find(id)


def _head(clone: Path) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    run = subprocess.run([GIT, "-C", str(clone), "rev-parse", "HEAD"], env=env, capture_output=True, timeout=60)
    return run.stdout.decode().strip()


def _tree_hashes(clone: Path) -> dict[str, str]:
    """The working tree of a clone without its .git folder."""
    return {
        p.relative_to(clone).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(clone.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(clone).parts
    }


def _plan(root: Path, entry: CatalogEntry) -> ops.UpdatePlan:
    plan = ops.plan_update(root, entry, _net(), running=lambda: [])
    assert isinstance(plan, ops.UpdatePlan), plan
    return plan


def _staging_is_empty(root: Path) -> bool:
    staging = root / "ThirdParty" / ".staging"
    return not staging.exists() or not any(staging.iterdir())


def test_add_update_remove_cycle(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    clone = root / "ThirdParty" / "Demo"
    assert entry.commit == first and _head(clone) == first
    assert _plan(root, entry).current is True  # nothing new yet

    second = advance_upstream(bare, V2)
    plan = _plan(root, entry)
    assert (plan.current, plan.old, plan.new, plan.refusal) == (False, first, second, None)
    assert plan.files_changed == 2  # one file added, one deleted
    assert plan.added == ("Extra",) and plan.removed == ("Demo",)  # the footprint library Demo is gone
    assert not (clone / "symbols" / "Extra.kicad_sym").exists()  # the preview changed no file

    issues = ops.apply_update(root, plan, _net())

    assert not _errors(issues), issues
    assert issues[0].code == "catalog.updated" and issues[0].text.startswith(f"Updated Demo to {second[:7]}: 1 libraries added")
    assert _head(clone) == second and _entry(root).commit == second
    assert (clone / "symbols" / "Extra.kicad_sym").is_file() and not (clone / "footprints").exists()
    assert _plan(root, _entry(root)).current is True

    removal = ops.plan_remove(root, "Demo", manifest.load(root, allow_file=True), running=lambda: [])
    assert (removal.exists, removal.listed, removal.nicknames) == (True, True, ("Demo", "Extra"))
    assert removal.size_bytes > 0
    done = ops.apply_remove(root, removal, allow_file=True)

    assert done[0].code == "catalog.removed" and not _errors(done), done
    assert not clone.exists() and _entry(root) is None and _staging_is_empty(root)


def test_update_after_force_push(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    forced = advance_upstream(bare, {**V2, "NOTES.md": "rewritten history\n"}, orphan=True)  # no common ancestor

    plan = _plan(root, entry)
    assert (plan.old, plan.new, plan.refusal) == (first, forced, None)
    assert plan.added == ("Extra",)

    issues = ops.apply_update(root, plan, _net())

    assert not _errors(issues), issues
    clone = root / "ThirdParty" / "Demo"
    assert _head(clone) == forced and _entry(root).commit == forced
    assert (clone / "NOTES.md").read_text(encoding="utf-8") == "rewritten history\n"


def test_dirty_refusal_lists_the_edit(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    advance_upstream(bare, V2)
    clone = root / "ThirdParty" / "Demo"
    (clone / "symbols" / "Demo.kicad_sym").write_text("(kicad_symbol_lib) ; my edit\n", encoding="utf-8")
    (clone / "mine.txt").write_text("notes", encoding="utf-8")
    before = _tree_hashes(clone)

    plan = _plan(root, entry)

    assert plan.refusal is not None and plan.refusal.code == "catalog.dirty"
    assert sorted(plan.dirty) == ["mine.txt", "symbols/Demo.kicad_sym"]
    assert "Keep your own changes in Custom/ instead." in plan.refusal.text
    assert ops.apply_update(root, plan, _net())[0].code == "catalog.dirty"
    assert _tree_hashes(clone) == before and _head(clone) == first  # the edits survive and nothing was reset


def test_case_collision_baseline_keeps_update_possible(work):
    root = make_collection(work / "col")
    bare, first = case_collision_upstream(work / "up")
    entry = _add(root, bare)
    if os.name == "nt":  # a case-insensitive file system: git reports one of the two files as changed (RESEARCH C8)
        assert "footprints/lib.pretty/a.kicad_mod" in entry.known_dirty

    second = advance_upstream(bare, {**LIB_FILES, "Footprints/Lib.pretty/a.kicad_mod": FOOTPRINT_TEXT, "footprints/Lib.pretty/a.kicad_mod": FOOTPRINT_TEXT + "\n", "README.md": "v2\n"})
    plan = _plan(root, entry)

    assert plan.dirty == () and plan.refusal is None and plan.new == second  # the baseline keeps Update possible
    issues = ops.apply_update(root, plan, _net())
    assert not _errors(issues), issues
    assert _head(root / "ThirdParty" / "Demo") == second
    assert _plan(root, _entry(root)).refusal is None  # and it stays possible after the reset


def test_lfs_adopted_later_is_refused(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    advance_upstream(bare, {**LIB_FILES, ".gitattributes": LFS_ATTRIBUTES, "models/Demo.step": "pointer"})
    clone = root / "ThirdParty" / "Demo"
    before = _tree_hashes(clone)

    plan = _plan(root, entry)

    assert plan.refusal is not None and plan.refusal.code == "catalog.lfs"
    assert ops.apply_update(root, plan, _net())[0].code == "catalog.lfs"
    assert _tree_hashes(clone) == before and _head(clone) == first and _entry(root).commit == first


def test_reinstall_after_manual_delete(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    _add(root, bare)
    clone = root / "ThirdParty" / "Demo"
    remove_tree(clone)  # the user deleted the folder by hand; the catalog still lists it
    mf = manifest.load(root, allow_file=True)
    rows = status.row_statuses(root, mf, curated=())
    assert [(row.id, row.state) for row in rows] == [("Demo", status.State.FOLDER_MISSING)]

    second = advance_upstream(bare, V2)
    plan = ops.plan_reinstall(root, mf.find("Demo"), mf, running=lambda: [])
    assert plan.refusals == ()
    staged = ops.stage_add(root, plan, _net())
    assert isinstance(staged, ops.Staged), staged
    issues = ops.register_add(root, staged, allow_file=True)

    assert issues[0].code == "catalog.reinstalled" and not _errors(issues), issues
    assert _head(clone) == second and _entry(root).commit == second
    assert _entry(root).added_on == mf.find("Demo").added_on
    assert status.row_statuses(root, manifest.load(root, allow_file=True), curated=())[0].state is status.State.INSTALLED
    assert _staging_is_empty(root)


def test_check_updates_against_real_remotes(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    gone_bare, gone_sha = make_upstream(work / "up_gone", LIB_FILES)
    entries = [
        entry,
        CatalogEntry(id="Gone", url=upstream_url(gone_bare), branch="main", commit=gone_sha, licence_spdx="MIT"),
        CatalogEntry(id="Away", url=upstream_url(work / "no-such.git"), branch="main", commit=first, licence_spdx="MIT"),
    ]
    for extra in ("Gone", "Away"):
        make_third_party(root, extra, LIB_FILES)
    mf = Manifest(tuple(entries))
    record = (root / "catalog.json").read_bytes()

    states = status.check_updates(root, mf, _net())
    assert states["Demo"].check is status.Check.CURRENT and states["Demo"].remote_sha == first
    assert states["Gone"].check is status.Check.CURRENT
    assert states["Away"].check is status.Check.UNKNOWN and states["Away"].remote_sha is None

    second = advance_upstream(bare, V2)
    delete_branch(gone_bare, "main")
    states = status.check_updates(root, mf, _net())

    assert states["Demo"].check is status.Check.AVAILABLE and states["Demo"].remote_sha == second
    assert states["Gone"].check is status.Check.BRANCH_GONE
    assert status.check_updates(root, mf, _net()).keys() == states.keys()
    assert status.update_count(states, mf) == 1
    rows = {row.id: row for row in status.row_statuses(root, mf, curated=(), updates=states)}
    assert rows["Demo"].state is status.State.UPDATE_AVAILABLE and rows["Gone"].state is status.State.INSTALLED
    assert (root / "catalog.json").read_bytes() == record  # a check never writes
    assert _head(root / "ThirdParty" / "Demo") == first  # and never downloads


def test_reset_uses_the_previewed_commit(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    previewed = advance_upstream(bare, V2)
    plan = _plan(root, entry)
    assert plan.new == previewed

    newer = advance_upstream(bare, {**V2, "LATER.md": "a third version\n"})  # the remote moved again after the preview
    assert newer != previewed
    issues = ops.apply_update(root, plan, _net())

    assert not _errors(issues), issues
    clone = root / "ThirdParty" / "Demo"
    assert _head(clone) == previewed and _entry(root).commit == previewed
    assert not (clone / "LATER.md").exists()
    # the next look finds the newer commit as a new update
    follow = _plan(root, _entry(root))
    assert (follow.old, follow.new, follow.current) == (previewed, newer, False)


def test_unreadable_remote_is_an_issue_not_a_change(work):
    root = make_collection(work / "col")
    bare, first = make_upstream(work / "up", LIB_FILES)
    entry = _add(root, bare)
    remove_tree(bare)  # the upstream disappeared
    clone = root / "ThirdParty" / "Demo"
    before = _tree_hashes(clone)

    answer = ops.plan_update(root, entry, _net(), running=lambda: [])

    assert isinstance(answer, Issue) and answer.severity is Severity.ERROR
    assert _tree_hashes(clone) == before and _head(clone) == first
