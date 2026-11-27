"""The hardened catalog git runner against real git on local repositories (Phase 17 plan 03; slow).

Every test builds a bare repository with git plumbing (tests/catalogfixtures.py) and talks to it through a
file:// address, the only transport a test may use: https is the only transport production allows, and no
test touches the network. NetGit(allow_file=True) lets the file protocol through; a test that proves the
refusal builds the runner without it.
"""

import os
import subprocess
from pathlib import Path

import gitfixtures  # noqa: F401  (imported so the slow-marker tripwire can see the running test)
import pytest
from catalogfixtures import FOOTPRINT_TEXT, LIB_FILES, advance_upstream, make_upstream, upstream_url
from gitfixtures import GIT, remove_tree, requires_git

from kicad_lib_manager.catalog import gitnet
from kicad_lib_manager.catalog.gitnet import NetGit, NetRun, RemoteHead
from kicad_lib_manager.models import Issue

pytestmark = [pytest.mark.slow, requires_git]

FOOTPRINT = "footprints/Demo.pretty/R_0603.kicad_mod"
LFS_POINTER = "version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64 + "\nsize 12345\n"


def _net(*, allow_file: bool = True) -> NetGit:
    return NetGit(exe=Path(GIT), allow_file=allow_file)


def _plain_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(extra)
    return env


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    run = subprocess.run(
        [GIT, *args], cwd=cwd, env=env or _plain_env(GIT_CONFIG_GLOBAL=os.devnull), capture_output=True, timeout=120
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
    return run.stdout.decode("utf-8", errors="replace")


@pytest.fixture
def work(tmp_path):
    """A scratch folder whose git trees (read-only object files) are removed even on Windows."""
    folder = tmp_path / "work"
    folder.mkdir()
    yield folder
    remove_tree(folder)


def _clone(work: Path, files=None, *, branch: str = "main"):
    """Build an upstream and shallow-clone it through clone_shallow; return (bare, upstream sha, clone folder)."""
    bare, sha = make_upstream(work / "up", files if files is not None else LIB_FILES, branch=branch)
    dest = work / "clone"
    result = gitnet.clone_shallow(_net(), upstream_url(bare), branch, dest)
    assert isinstance(result, NetRun), result
    return bare, sha, dest


def _hook_files(clone: Path) -> list[str]:
    hooks = clone / ".git" / "hooks"
    return sorted(p.name for p in hooks.iterdir()) if hooks.is_dir() else []


def test_clone_persists_safe_config(work):
    _, sha, clone = _clone(work)
    config = (clone / ".git" / "config").read_text(encoding="utf-8").lower()
    for line in ("autocrlf = false", "longpaths = true", "symlinks = false", "tagopt = --no-tags"):
        assert line in config, line
    assert _hook_files(clone) == []
    assert gitnet.head_commit(_net(), clone) == sha
    # the config git wrote itself passes the allow-list that guards every later call
    assert gitnet.config_problems(clone) == []


def test_hostile_global_hooks_do_not_run(work, monkeypatch):
    marker = work / "hook-ran"
    hooks = work / "hostile-hooks"
    hooks.mkdir()
    hook = hooks / "post-checkout"
    hook.write_text(f'#!/bin/sh\necho ran > "{marker.as_posix()}"\n', encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    global_config = work / "hostile.gitconfig"
    global_config.write_text(f"[core]\n\thooksPath = {hooks.as_posix()}\n", encoding="utf-8")
    # the user's own git setup is hostile in every place git looks for it
    home = work / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(global_config.read_text(encoding="utf-8"), encoding="utf-8")
    hostile = _plain_env(GIT_CONFIG_GLOBAL=str(global_config), HOME=str(home), USERPROFILE=str(home))

    bare, _ = make_upstream(work / "up", LIB_FILES)
    url = upstream_url(bare)
    # control: a plain clone with that configuration runs the hook
    _git(work, "-c", "protocol.file.allow=always", "clone", "-q", url, str(work / "plain"), env=hostile)
    assert marker.exists(), "the control clone did not run the hostile hook, so this test proves nothing"
    marker.unlink()

    for name, value in hostile.items():
        if name in ("GIT_CONFIG_GLOBAL", "HOME", "USERPROFILE"):
            monkeypatch.setenv(name, value)
    result = gitnet.clone_shallow(_net(), url, "main", work / "hardened")
    assert isinstance(result, NetRun), result
    assert not marker.exists(), "the hostile post-checkout hook ran during the catalog's clone"
    assert _hook_files(work / "hardened") == []


def test_lfs_pointer_stays_a_pointer(work):
    files = {
        **LIB_FILES,
        ".gitattributes": "*.step filter=lfs diff=lfs merge=lfs -text\n",
        "models/Demo.step": LFS_POINTER,
    }
    _, _, clone = _clone(work, files)
    assert (clone / "models" / "Demo.step").read_text(encoding="utf-8").startswith("version https://git-lfs")
    assert _hook_files(clone) == []
    # a later call in the clone (which would run git-lfs and install hooks without the overrides) adds none
    assert gitnet.status_entries(_net(), clone) == []
    assert _hook_files(clone) == []


def test_file_url_is_refused_without_allow_file(work):
    bare, _ = make_upstream(work / "up", LIB_FILES)
    result = gitnet.clone_shallow(_net(allow_file=False), upstream_url(bare), "main", work / "clone")
    assert isinstance(result, Issue) and result.code == "git.clone_failed", result
    assert not (work / "clone" / ".git").exists()
    # the same address works once the test opts in, so the refusal came from the protocol policy
    assert isinstance(gitnet.clone_shallow(_net(), upstream_url(bare), "main", work / "clone"), NetRun)


def test_ls_remote_codes(work):
    bare, sha = make_upstream(work / "up", LIB_FILES)
    url = upstream_url(bare)
    assert gitnet.ls_remote(_net(), url, "main") == RemoteHead(sha)
    missing_branch = gitnet.ls_remote(_net(), url, "nope")
    assert isinstance(missing_branch, Issue) and missing_branch.code == "git.branch_missing"
    gone = gitnet.ls_remote(_net(), upstream_url(work / "no-such.git"), "main")
    assert isinstance(gone, Issue) and gone.code == "git.unreachable"
    # asking downloads nothing: the caller's folder holds no repository afterwards
    assert not (work / "no-such.git").exists()


def test_default_branch_from_symref(work):
    bare, sha = make_upstream(work / "up", LIB_FILES, branch="trunk")
    assert gitnet.default_branch(_net(), upstream_url(bare)) == ("trunk", sha)
    gone = gitnet.default_branch(_net(), upstream_url(work / "no-such.git"))
    assert isinstance(gone, Issue) and gone.code == "git.unreachable"


def test_fetch_then_reset_after_an_advance_and_a_force_push(work):
    bare, first, clone = _clone(work)
    url = upstream_url(bare)
    assert gitnet.status_entries(_net(), clone) == []

    # a normal advance: one file changed, one added
    changed = {**LIB_FILES, FOOTPRINT: FOOTPRINT_TEXT.replace("0.8 0.9", "0.9 1.0"), "footprints/Demo.pretty/R_0805.kicad_mod": FOOTPRINT_TEXT}
    second = advance_upstream(bare, changed)
    fetched = gitnet.fetch_shallow(_net(), clone, url, "main")
    assert fetched == second
    assert gitnet.head_commit(_net(), clone) == first  # the fetch moved nothing
    assert sorted(gitnet.changed_paths(_net(), clone, second)) == [
        ("A", "footprints/Demo.pretty/R_0805.kicad_mod"),
        ("M", FOOTPRINT),
    ]
    assert "footprints/Demo.pretty/R_0805.kicad_mod" in gitnet.tree_paths(_net(), clone, second)
    assert gitnet.read_blob(_net(), clone, second, "footprints/Demo.pretty/R_0805.kicad_mod") == FOOTPRINT_TEXT.encode()
    assert gitnet.read_blob(_net(), clone, second, "no/such/file") is None
    assert isinstance(gitnet.reset_hard(_net(), clone, second), NetRun)
    assert gitnet.head_commit(_net(), clone) == second
    assert (clone / "footprints" / "Demo.pretty" / "R_0805.kicad_mod").is_file()

    # a force-push to an unrelated history: a root commit with a different tree
    forced = advance_upstream(bare, {"symbols/Other.kicad_sym": LIB_FILES["symbols/Demo.kicad_sym"]}, orphan=True)
    assert gitnet.fetch_shallow(_net(), clone, url, "main") == forced
    paths = dict((path, letter) for letter, path in gitnet.changed_paths(_net(), clone, forced))
    assert paths["symbols/Other.kicad_sym"] == "A" and paths[FOOTPRINT] == "D"
    assert isinstance(gitnet.reset_hard(_net(), clone, forced), NetRun)
    assert gitnet.head_commit(_net(), clone) == forced
    assert not (clone / FOOTPRINT).exists() and (clone / "symbols" / "Other.kicad_sym").is_file()
    assert gitnet.config_problems(clone) == []  # fetch and reset leave nothing outside the allow-list


def test_fetch_of_a_missing_branch_is_an_issue(work):
    bare, _, clone = _clone(work)
    result = gitnet.fetch_shallow(_net(), clone, upstream_url(bare), "nope")
    assert isinstance(result, Issue) and result.code == "git.fetch_failed", result


def test_fetch_progress_reaches_the_callback(work):
    bare, _, clone = _clone(work)
    advance_upstream(bare, {**LIB_FILES, "README.md": "second\n"})
    seen = []
    assert isinstance(gitnet.fetch_shallow(_net(), clone, upstream_url(bare), "main", progress=lambda t, p: seen.append((t, p))), str)
    assert all(isinstance(text, str) and (percent is None or 0 <= percent <= 100) for text, percent in seen)


def test_in_clone_calls_never_reach_the_parent(work):
    # a collection that is itself a git repository, holding ThirdParty/X without a .git folder of its own
    root = work / "collection"
    folder = root / "ThirdParty" / "X"
    folder.mkdir(parents=True)
    (folder / "file.txt").write_text("committed\n", encoding="utf-8")
    plain = _plain_env(GIT_CONFIG_GLOBAL=os.devnull)
    identity = ["-c", "user.name=T", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    _git(root, "init", "-q", "-b", "main", env=plain)
    _git(root, "add", "-A", env=plain)
    _git(root, *identity, "commit", "-q", "-m", "x", env=plain)
    (folder / "file.txt").write_text("edited by the owner\n", encoding="utf-8")
    before = _git(root, "status", "--porcelain=v1", env=plain)
    assert "file.txt" in before

    net = _net()
    sha = "a" * 40
    results = [
        gitnet.status_entries(net, folder),
        gitnet.fetch_shallow(net, folder, "https://example.org/a/b.git", "main"),
        gitnet.reset_hard(net, folder, sha),
        gitnet.changed_paths(net, folder, sha),
        gitnet.tree_paths(net, folder, "HEAD"),
        gitnet.head_commit(net, folder),
    ]
    assert all(isinstance(r, Issue) and r.code == "git.not_a_clone" for r in results), results
    assert gitnet.read_blob(net, folder, "HEAD", "file.txt") is None
    assert _git(root, "status", "--porcelain=v1", env=plain) == before
    assert (folder / "file.txt").read_text(encoding="utf-8") == "edited by the owner\n"


def test_in_clone_env_stops_discovery_even_for_a_fake_git_folder(work):
    # an empty .git folder passes the folder pre-check; GIT_DIR then makes git fail instead of using the parent
    root = work / "collection"
    folder = root / "ThirdParty" / "Y"
    (folder / ".git").mkdir(parents=True)
    (folder / "file.txt").write_text("committed\n", encoding="utf-8")
    plain = _plain_env(GIT_CONFIG_GLOBAL=os.devnull)
    _git(root, "init", "-q", "-b", "main", env=plain)
    result = gitnet.status_entries(_net(), folder)
    assert isinstance(result, Issue) and result.code == "git.read_failed", result


def test_status_lists_edits_and_untracked(work):
    _, _, clone = _clone(work)
    (clone / FOOTPRINT).write_text("edited\n", encoding="utf-8")
    (clone / "new.txt").write_text("new\n", encoding="utf-8")
    (clone / "sub").mkdir()
    (clone / "sub" / "deep.txt").write_text("deep\n", encoding="utf-8")
    assert sorted(gitnet.status_entries(_net(), clone)) == [FOOTPRINT, "new.txt", "sub/deep.txt"]


def test_progress_lines_of_a_real_clone_carry_percent(work):
    bare, _ = make_upstream(work / "up", LIB_FILES)
    seen = []
    result = gitnet.clone_shallow(_net(), upstream_url(bare), "main", work / "clone", progress=lambda t, p: seen.append((t, p)))
    assert isinstance(result, NetRun)
    assert seen, "git printed no progress line"
    assert all(percent is None or 0 <= percent <= 100 for _, percent in seen)
