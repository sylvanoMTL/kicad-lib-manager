"""create_collection with a real git (Phase 15-06, ROOT-06, D4): slow, builds a real repository."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from gitfixtures import GIT, import_files, make_superproject, remove_tree, requires_git
from installfixtures import UL_DESCRIPTION

from kicad_lib_manager import collection
from kicad_lib_manager.collection import check_folder, create_collection, is_collection
from kicad_lib_manager.gitops import GitContext, find_git
from kicad_lib_manager.importer import commit_step
from kicad_lib_manager.importer.applier import apply_plan
from kicad_lib_manager.importer.commit_plan import build_commit_plan, default_message
from kicad_lib_manager.importer.layout import RepoLayout
from kicad_lib_manager.importer.plan import InstallOptions
from kicad_lib_manager.importer.planner import build_plan
from kicad_lib_manager.library_scanner import scan_all
from kicad_lib_manager.models import Issue

LIBRARY = "Atomic_Battery_Management"
SKELETON = [
    ".gitignore",
    "3DModels/.gitkeep",
    "Footprints/Atomic_Footprints.pretty/.gitkeep",
    "README.md",
    "Symbols/.gitkeep",
]


def _git(folder, *args):
    return subprocess.run([GIT, "-C", str(folder), *args], capture_output=True, timeout=60)


@pytest.mark.slow
@requires_git
def test_create_collection_with_real_git(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10_000)
    exe = find_git(tmp_path / "no-such-app-folder")
    assert not isinstance(exe, Issue), exe
    target = tmp_path / "KiCad_Libraries"
    try:
        assert create_collection(target, GitContext(exe), app_dir=tmp_path / "app", environ={}) == []
        custom = target / "Custom"
        head = _git(custom, "symbolic-ref", "--short", "HEAD")
        assert head.returncode == 0 and head.stdout.decode().strip() == "main"
        # D4: nothing is committed
        assert _git(custom, "rev-parse", "-q", "--verify", "HEAD").returncode != 0
        status = _git(custom, "status", "--porcelain", "-uall").stdout.decode().splitlines()
        assert all(line.startswith("?? ") for line in status)
        assert sorted(line[3:] for line in status) == [
            ".gitignore",
            "3DModels/.gitkeep",
            "Footprints/Atomic_Footprints.pretty/.gitkeep",
            "README.md",
            "Symbols/.gitkeep",
        ]
        # the collection root is a plain folder
        assert not (target / ".git").exists()
        assert is_collection(target)
        assert check_folder(target).state == "collection"
    finally:
        if target.exists():
            remove_tree(target)


def _identity(monkeypatch):
    """The four variables gitops keeps; the conftest gives every test an empty HOME."""
    for name, value in (
        ("GIT_AUTHOR_NAME", "Test Author"),
        ("GIT_AUTHOR_EMAIL", "author@example.invalid"),
        ("GIT_COMMITTER_NAME", "Test Author"),
        ("GIT_COMMITTER_EMAIL", "author@example.invalid"),
    ):
        monkeypatch.setenv(name, value)


def _new_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10_000)
    exe = find_git(tmp_path / "no-such-app-folder")
    assert not isinstance(exe, Issue), exe
    ctx = GitContext(exe)
    target = tmp_path / "KiCad_Libraries"
    assert create_collection(target, ctx, app_dir=tmp_path / "app", environ={}) == []
    return target, ctx


@pytest.mark.slow
@requires_git
def test_new_collection_first_part_commits(tmp_path, monkeypatch, ul_package):
    """ROOT-06, D4: a brand-new collection takes the Ultra Librarian sample through import and commit."""
    _identity(monkeypatch)
    package, candidate = ul_package
    target, ctx = _new_collection(tmp_path, monkeypatch)
    custom = target / "Custom"
    try:
        layout = RepoLayout.for_repo(target)
        plan = build_plan(candidate, InstallOptions(library=LIBRARY, description=UL_DESCRIPTION), layout)
        assert not plan.blocked, plan.issues
        result = apply_plan(plan, backup_root=tmp_path / "bk")
        assert result.ok, result.issues

        cplan = build_commit_plan(result, plan, vendor_label="Ultra Librarian")
        assert cplan.issues == ()
        probe = commit_step.probe_commit(cplan, git=ctx)
        assert probe.state == "ready", probe
        assert probe.branch == "main"
        assert probe.parent_mode == "none"
        assert probe.parent_dir is None
        assert probe.gate is not None and not probe.gate.refused
        assert probe.other_changes == len(SKELETON)

        outcome = commit_step.run_commit(cplan, default_message(cplan), False, expected_branch="main", git=ctx)
        assert outcome.committed and not outcome.failed, outcome
        assert outcome.parent_commit is None

        log = _git(custom, "log", "--format=%s").stdout.decode().splitlines()
        assert len(log) == 1
        parents = _git(custom, "rev-list", "--parents", "-n", "1", "HEAD").stdout.decode().split()
        assert len(parents) == 1  # a root commit
        shown = sorted(_git(custom, "show", "--name-only", "--format=", "HEAD").stdout.decode().split())
        assert shown == sorted(f.rel for f in cplan.files)
        assert shown == [
            "3DModels/CSD85301Q2.stp",
            "Footprints/Atomic_Footprints.pretty/DQK0006B.kicad_mod",
            f"Symbols/{LIBRARY}.kicad_sym",
        ]
        # the skeleton files are still untracked
        status = _git(custom, "status", "--porcelain", "-uall").stdout.decode().splitlines()
        assert sorted(line[3:] for line in status if line.startswith("?? ")) == SKELETON
        assert len(status) == len(SKELETON)

        scanned = scan_all(target)
        sym = {lib.nickname: lib for lib in scanned.symbol_libs}
        fps = {lib.nickname: lib for lib in scanned.footprint_libs}
        assert sym[LIBRARY].source == "Custom"
        assert fps["Atomic_Footprints"].source == "Custom"
    finally:
        if target.exists():
            remove_tree(target)


@pytest.mark.slow
@requires_git
@pytest.mark.parametrize("shape", ["none", "gitlink"])
def test_every_collection_shape_commits(shape, tmp_path, monkeypatch):
    """ROOT-09: the probe reports the shape and run_commit succeeds; only the gitlink shape bumps a parent commit."""
    _identity(monkeypatch)
    files = {"Footprints/Atomic_Footprints.pretty/FP1.kicad_mod": b'(footprint "FP1")\n'}
    root = tmp_path / ("coll" if shape == "none" else "git")
    try:
        if shape == "none":
            target, ctx = _new_collection(tmp_path, monkeypatch)
            repos = SimpleNamespace(parent=target, custom=target / "Custom")
            parent_repo = None
        else:
            repos = make_superproject(root)
            ctx = GitContext(Path(GIT))
            parent_repo = repos.parent
        before = None
        if parent_repo is not None:
            before = _git(parent_repo, "rev-parse", "HEAD").stdout.decode().strip()

        cplan = import_files(repos, files)
        probe = commit_step.probe_commit(cplan, git=ctx)
        assert probe.state == "ready", probe
        assert probe.parent_mode == shape
        assert (probe.parent_dir is None) == (shape == "none")

        bump = shape == "gitlink"
        outcome = commit_step.run_commit(cplan, default_message(cplan), bump, expected_branch="main", git=ctx)
        assert outcome.committed and not outcome.failed, outcome
        if shape == "gitlink":
            assert outcome.parent_commit
            after = _git(parent_repo, "rev-parse", "HEAD").stdout.decode().strip()
            assert after != before
        else:
            assert outcome.parent_commit is None
            assert not (repos.parent / ".git").exists()
    finally:
        if root.exists():
            remove_tree(root)
        if shape == "none" and (tmp_path / "KiCad_Libraries").exists():
            remove_tree(tmp_path / "KiCad_Libraries")
