"""Phase 17 tracer: one library goes from a git repository to a scanned, table-ready catalog entry.

A file:// bare repository stands in for GitHub. The three tests that clone are slow (they build a
real repository); the pinned-argv tests start no process and run in the quick suite.
"""

import json
import os
import subprocess
import threading
from pathlib import Path

import gitfixtures  # noqa: F401  (imported so the slow-marker tripwire can see the running test)
import pytest
from catalogfixtures import LIB_FILES, make_upstream, upstream_url
from collectionfixtures import make_collection
from gitfixtures import GIT, requires_git

from kicad_lib_manager.catalog import gitnet, manifest, ops
from kicad_lib_manager.catalog.gitnet import NetGit
from kicad_lib_manager.catalog.ops import AddSource, Staged, register_add, stage_add
from kicad_lib_manager.library_scanner import scan_all
from kicad_lib_manager.models import Severity
from kicad_lib_manager.procs import StreamOutcome
from kicad_lib_manager.table_generator import generate_fp_lib_table, generate_sym_lib_table

NO_LIBRARIES_TEXT = "This repository holds no KiCad symbol or footprint libraries, so there is nothing to add."


def _source(url: str, id: str = "Demo") -> AddSource:
    return AddSource(id=id, name=id, url=url, branch="main", vars={}, licence_spdx="MIT")


def _net() -> NetGit:
    return NetGit(exe=Path(GIT), allow_file=True)


def _staging_is_empty(root: Path) -> bool:
    staging = root / "ThirdParty" / ops.STAGING_DIR
    return not staging.exists() or not any(staging.iterdir())


@pytest.mark.slow
@requires_git
def test_add_one_library_end_to_end(tmp_path):
    root = make_collection(tmp_path / "col")
    bare, sha = make_upstream(tmp_path / "up", LIB_FILES)

    staged = stage_add(root, _source(upstream_url(bare)), _net())
    assert isinstance(staged, Staged), staged
    assert staged.folder.parent == root / "ThirdParty" / ops.STAGING_DIR
    assert staged.commit == sha

    issues = register_add(root, staged)
    assert not [i for i in issues if i.severity is Severity.ERROR], issues

    clone = root / "ThirdParty" / "Demo"
    assert (clone / ".git").is_dir()
    assert _staging_is_empty(root)
    assert not (root / ".gitmodules").exists()
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    shallow = subprocess.run(
        [GIT, "-C", str(clone), "rev-parse", "--is-shallow-repository"], env=env, capture_output=True, timeout=60
    )
    assert shallow.stdout.decode().strip() == "true"

    raw = (root / manifest.MANIFEST_NAME).read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    data = json.loads(raw.decode("utf-8"))
    assert data["format"] == 1
    (entry,) = data["libraries"]
    assert (entry["id"], entry["url"], entry["branch"], entry["commit"]) == ("Demo", upstream_url(bare), "main", sha)

    result = scan_all(root)
    symbol = next(lib for lib in result.symbol_libs if lib.rel_path == "ThirdParty/Demo/symbols/Demo.kicad_sym")
    footprint = next(lib for lib in result.footprint_libs if lib.rel_path == "ThirdParty/Demo/footprints/Demo.pretty")
    assert symbol.source == "Demo" and footprint.source == "Demo"
    # Generate Tables writes the selected libraries
    symbol.selected = footprint.selected = True
    sym_table = generate_sym_lib_table([symbol])
    fp_table = generate_fp_lib_table([footprint])
    assert "${KICAD_LIB_GITHUB}/ThirdParty/Demo/symbols/Demo.kicad_sym" in sym_table.content
    assert "${KICAD_LIB_GITHUB}/ThirdParty/Demo/footprints/Demo.pretty" in fp_table.content


@pytest.mark.slow
@requires_git
def test_repository_without_libraries_is_refused(tmp_path):
    root = make_collection(tmp_path / "col")
    bare, _ = make_upstream(tmp_path / "up", {"README.md": "no libraries here\n"})

    staged = stage_add(root, _source(upstream_url(bare)), _net())
    assert not isinstance(staged, Staged)
    assert staged.code == "catalog.no_libraries"
    assert staged.text == NO_LIBRARIES_TEXT
    assert _staging_is_empty(root)
    assert not (root / "ThirdParty" / "Demo").exists()
    assert not (root / manifest.MANIFEST_NAME).exists()


@pytest.mark.slow
@requires_git
def test_cancel_during_clone_removes_staging(tmp_path):
    root = make_collection(tmp_path / "col")
    bare, _ = make_upstream(tmp_path / "up", LIB_FILES)
    cancel = threading.Event()
    seen = []

    def progress(text, percent):
        seen.append(text)
        cancel.set()

    result = stage_add(root, _source(upstream_url(bare)), _net(), progress=progress, cancel=cancel)
    assert seen, "git printed no line before it ended"
    assert not isinstance(result, Staged)
    assert result.code == "git.cancelled"
    assert _staging_is_empty(root)
    assert not (root / "ThirdParty" / "Demo").exists()


def _recorded_clone(net_args: dict, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_INDEX_FILE", "stray-index")
    monkeypatch.setenv("GIT_WORK_TREE", "stray-tree")
    seen = []

    def starter(argv, **kwargs):
        seen.append((list(argv), kwargs))
        return StreamOutcome(0, b"", (), False, False)

    net = NetGit(exe=Path("git-under-test"), starter=starter, **net_args)
    dest = tmp_path / "dest"
    result = gitnet.clone_shallow(net, "https://example.org/a/b.git", "main", dest)
    assert isinstance(result, gitnet.NetRun), result
    ((argv, kwargs),) = seen
    return argv, kwargs, dest


def test_hardened_argv_and_env(tmp_path, monkeypatch):
    argv, kwargs, dest = _recorded_clone({}, monkeypatch, tmp_path)
    at = argv.index("clone")
    prefix, tail = argv[:at], argv[at:]
    assert prefix[:2] == ["git-under-test", "--literal-pathspecs"]
    config = [prefix[i + 1] for i, item in enumerate(prefix) if item == "-c"]
    for key in (
        "protocol.allow=never", "protocol.https.allow=always", "credential.helper=", "core.askPass=",
        "core.hooksPath=", "core.fsmonitor=false", "transfer.bundleURI=false", "submodule.recurse=false",
        "filter.lfs.process=", "filter.lfs.smudge=", "filter.lfs.required=false", "diff.external=",
    ):
        assert key in config, key
    assert "protocol.file.allow=always" not in config
    assert tail == [
        "clone", "--depth", "1", "--single-branch", "--branch=main", "--no-tags", "--template=", "--progress",
        "--config=core.autocrlf=false", "--config=core.longpaths=true", "--config=core.symlinks=false",
        "--", "https://example.org/a/b.git", str(dest),
    ]

    env = kwargs["env"]
    allowed = {"GIT_TERMINAL_PROMPT", "GIT_CONFIG_GLOBAL", "GIT_OPTIONAL_LOCKS", "GIT_LFS_SKIP_SMUDGE"}
    assert {k for k in env if k.upper().startswith("GIT_")} == allowed
    assert env["GCM_INTERACTIVE"] == "Never" and env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_LFS_SKIP_SMUDGE"] == "1" and env["LC_ALL"] == "C"


def test_file_protocol_is_allowed_only_when_asked(tmp_path, monkeypatch):
    argv, _, _ = _recorded_clone({"allow_file": True}, monkeypatch, tmp_path)
    config = [argv[i + 1] for i, item in enumerate(argv) if item == "-c"]
    assert "protocol.file.allow=always" in config and "protocol.allow=never" in config


def test_a_subcommand_outside_the_list_is_refused():
    net = NetGit(exe=Path("git-under-test"))
    with pytest.raises(ValueError):
        gitnet._argv(net, "push", ["--force"])
