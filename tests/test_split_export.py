"""scripts/split: the tool-repo allow-list, the planning scrub and the export checker (Phase 16, D-02, D-05, D-16).

Every planted workstation path below is assembled from pieces at run time, so this file's own text
scans clean with every rule of scripts/prepublish_scan.py.
"""

import importlib
import os
import re
import subprocess
from pathlib import Path

import pytest
from gitfixtures import GIT, requires_git

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / "scripts" / "split"
ALLOW_LIST = SPLIT / "allowlist.txt"

REQUIRED_FILES = (
    "kicad_lib_manager/__init__.py",
    "kicad_lib_manager.py",
    "tests/test_a.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "LICENSE",
    "README.md",
    "CLAUDE.md",
    "scripts/a.py",
    ".github/workflows/ci.yml",
)

# Sample paths: nothing here is a contiguous workstation path
WORKTREE = "C:/Work/Trees/tool-wt"
MAIN = "C:/Work/Trees/main-checkout"
HOME = "C:/" + "Users/" + "someone"
REPOS = "C:/Git_Repo" + "_Clones"
PYTEST_OF = "pytest" + "-of-"


@pytest.fixture
def split(monkeypatch):
    """The scripts/split modules, importable by name (a script run from its folder sees its siblings the same way)."""
    monkeypatch.syspath_prepend(str(SPLIT))

    class Modules:
        scrub = importlib.import_module("scrub")
        verify_export = importlib.import_module("verify_export")
        build_tool_repo = importlib.import_module("build_tool_repo")
        sync_planning = importlib.import_module("sync_planning")

    return Modules


def _spellings(path: str) -> list[str]:
    forward = path
    backslash = path.replace("/", "\\")
    bash = "/" + path[0].lower() + path[2:]
    return [forward, backslash, bash]


# -- the allow-list -------------------------------------------------------------------------------


def test_allow_list_decisions(split):
    allow = split.verify_export.load_allow_list(ALLOW_LIST)
    for rel in (
        "kicad_lib_manager/main_window.py",
        "kicad_lib_manager.py",
        "tests/fixtures/sexpr/a.kicad_mod",
        ".planning/phases/16-repo-split/16-CONTEXT.md",
        ".planning/PROJECT.md",
        ".planning/research/PITFALLS.md",
        "scripts/split/build_tool_repo.py",
        ".githooks/pre-push",
        ".github/workflows/ci.yml",
        "LICENSE",
    ):
        assert allow.allowed(rel), rel
    for rel in (
        "tests_old/x.py",
        ".planning/phases/14-test-suite-speed-up/measurements/a.log",
        ".planning/milestones/v2.0-ROADMAP.md",
        ".planning/quick/x.md",
        ".planning/debug/x.md",
        "Custom/Symbols/a.kicad_sym",
        "WurthElektronik/KiCad-Library/a.kicad_sym",
        "downloaded_examples/x.zip",
        ".gitmodules",
        "research_notes/a.md",
        "reports/r.md",
        ".planning/MILESTONES.md",
        ".planning/RETROSPECTIVE.md",
        "stray.txt",
    ):
        assert not allow.allowed(rel), rel


def test_allow_list_has_no_collection_content_line():
    lines = [line.strip() for line in ALLOW_LIST.read_text(encoding="utf-8").splitlines()]
    entries = [line for line in lines if line and not line.startswith("#")]
    for entry in entries:
        assert not re.match(r"(?i)^!?(Custom|WurthElektronik|downloaded_examples|reports|research_notes)\b", entry), entry
        assert not entry.startswith("/") and ".." not in entry.split("/"), entry


def test_include_prefix_is_a_whole_path_segment(split, tmp_path):
    path = tmp_path / "list.txt"
    path.write_text("# comment\n\ntests/\nLICENSE\n!tests/skip/\n", encoding="utf-8")
    allow = split.verify_export.load_allow_list(path)
    assert allow.allowed("tests/a.py")
    assert allow.allowed("tests/sub/b.py")
    assert not allow.allowed("tests_old/a.py")
    assert not allow.allowed("tests")
    assert allow.allowed("LICENSE")
    assert not allow.allowed("LICENSE.txt")
    assert not allow.allowed("tests/skip/c.py")


# -- the scrub ------------------------------------------------------------------------------------


def test_scrub_maps_and_generic_rules(split):
    scrub = split.scrub
    mapping = scrub.parse_map([f"{WORKTREE}=", f"{MAIN}=<main-checkout>"])
    # the longest OLD comes first
    assert [old for old, _ in scrub.parse_map(["C:/a=x", "C:/a/b/c=y", "C:/a/b=z"])][0] == "C:/a/b/c"

    for spelling in _spellings(WORKTREE):
        assert scrub.scrub_text(f"@{spelling}/.claude/gsd-core/x.md", mapping) == "@.claude/gsd-core/x.md"
    sep_back = WORKTREE.replace("/", "\\")
    assert scrub.scrub_text(f"see {sep_back}\\.claude\\x.md", mapping) == "see .claude\\x.md"
    for spelling in _spellings(MAIN):
        assert scrub.scrub_text(f"cd {spelling}/Custom", mapping) == "cd <main-checkout>/Custom"
        assert scrub.scrub_text(f"root={spelling}", mapping) == "root=<main-checkout>"
    # case is ignored
    assert scrub.scrub_text(f"@{WORKTREE.upper()}/.claude/y.md", mapping) == "@.claude/y.md"
    # a longer folder name is not the mapped folder
    assert scrub.scrub_text(f"{WORKTREE}-old/x", mapping) == f"{WORKTREE}-old/x"

    assert scrub.scrub_text(f"cache {HOME}/AppData/Local/x", mapping) == "cache <home>/AppData/Local/x"
    assert scrub.scrub_text(f"cache {HOME.replace('/', chr(92))}\\AppData", mapping) == "cache <home>\\AppData"
    assert scrub.scrub_text(f"clone {REPOS}/Other/x.py", mapping) == "clone <repos-folder>/Other/x.py"
    assert scrub.scrub_text("clone /c/" + "Git_Repo" + "_Clones/Other", mapping) == "clone <repos-folder>/Other"
    assert scrub.scrub_text(f"temp {PYTEST_OF}someone/pytest-3", mapping) == f"temp {PYTEST_OF}<user>/pytest-3"
    # the CI runner's folder is not a person's
    assert scrub.scrub_text(f"temp {PYTEST_OF}runner/x", mapping) == f"temp {PYTEST_OF}runner/x"


def test_scrub_sees_a_path_after_a_quoted_line_break(split):
    scrub = split.scrub
    quoted = chr(92) + "n"
    assert scrub.scrub_text("a" + quoted + HOME + "/x", []) == "a" + quoted + "<home>/x"
    assert scrub.scrub_text("a" + quoted + "/c/" + "Users/someone/x", []) == "a" + quoted + "<home>/x"
    assert scrub.scrub_text("a" + chr(92) + "t" + REPOS + "/b", []) == "a" + chr(92) + "t<repos-folder>/b"


def test_scrub_without_a_map_still_applies_the_generic_rules(split):
    scrub = split.scrub
    text = f"{HOME}/a and {REPOS}/b"
    assert scrub.scrub_text(text, []) == "<home>/a and <repos-folder>/b"
    # a document's own placeholder name, and a prompt that ends in a bracket
    assert scrub.scrub_text("C:/" + "Users/<owner>/x", []) == "<home>/x"
    assert scrub.scrub_text("C:\\" + "Users\\someone>dir", []) == "<home>>dir"


def test_parse_map_rejects_a_bad_item(split):
    with pytest.raises(ValueError):
        split.scrub.parse_map(["no-equals-sign"])
    with pytest.raises(ValueError):
        split.scrub.parse_map(["=NEW"])


def test_scrub_is_idempotent_and_byte_safe(split, tmp_path):
    scrub = split.scrub
    mapping = scrub.parse_map([f"{WORKTREE}=", f"{MAIN}=<main-checkout>"])
    text = f"a {WORKTREE}/x\r\nb {MAIN}\r\nc {HOME}/d\r\nd {PYTEST_OF}someone/q\r\n"
    once = scrub.scrub_text(text, mapping)
    assert scrub.scrub_text(once, mapping) == once
    assert "\r\n" in once and once.count("\n") == once.count("\r\n")

    plain = "line one\r\nline two\r\n\r\ntabs\tand ünïcode\r\n"
    assert scrub.scrub_text(plain, mapping) == plain

    root = tmp_path / "export"
    (root / ".planning").mkdir(parents=True)
    (root / "outside.md").write_bytes(f"{HOME}/x\n".encode())
    clean = root / ".planning" / "clean.md"
    clean.write_bytes(plain.encode("utf-8"))
    dirty = root / ".planning" / "dirty.md"
    dirty.write_bytes(text.encode("utf-8"))
    binary = root / ".planning" / "blob.bin"
    binary_bytes = b"\x00\x01" + f"{HOME}/x".encode() + b"\x00"
    binary.write_bytes(binary_bytes)
    invalid = root / ".planning" / "latin1.txt"
    invalid_bytes = b"caf\xe9 " + f"{HOME}/x".encode()
    invalid.write_bytes(invalid_bytes)

    changed = scrub.scrub_tree(root, [".planning"], mapping)
    assert changed == [".planning/dirty.md"]
    assert clean.read_bytes() == plain.encode("utf-8")
    assert binary.read_bytes() == binary_bytes
    assert invalid.read_bytes() == invalid_bytes
    assert (root / "outside.md").read_bytes() == f"{HOME}/x\n".encode()
    assert dirty.read_bytes().decode("utf-8") == once
    assert scrub.scrub_tree(root, [".planning"], mapping) == []


def test_scrub_cli_prints_the_changed_files(split, tmp_path, capsys):
    root = tmp_path / "export"
    (root / ".planning").mkdir(parents=True)
    (root / ".planning" / "a.md").write_text(f"@{WORKTREE}/.claude/x\n", encoding="utf-8")
    code = split.scrub.main(["--root", str(root), "--prefix", ".planning", "--map", f"{WORKTREE}="])
    assert code == 0
    assert ".planning/a.md" in capsys.readouterr().out
    assert (root / ".planning" / "a.md").read_text(encoding="utf-8") == "@.claude/x\n"
    assert split.scrub.main(["--root", str(root / "missing"), "--prefix", ".planning"]) == 2


# -- the export checker ---------------------------------------------------------------------------


def _export(root: Path, files=REQUIRED_FILES) -> Path:
    for rel in files:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    return root


def _verify(split, root: Path) -> list[str]:
    return split.verify_export.verify(root, split.verify_export.load_allow_list(ALLOW_LIST))


def test_verify_export_passes_a_complete_tree(split, tmp_path, capsys):
    root = _export(tmp_path / "export")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x\n", encoding="utf-8")
    assert _verify(split, root) == []
    code = split.verify_export.main([str(root), "--allow-list", str(ALLOW_LIST)])
    out = capsys.readouterr().out
    assert code == 0
    assert f"verify_export: ok ({len(REQUIRED_FILES)} files)" in out


@pytest.mark.parametrize(
    "extra",
    ["extra.txt", ".gitmodules", "Custom/a.kicad_sym", "downloaded_examples/x.zip", "tests_old/x.py", "WurthElektronik/a.md", ".planning/milestones/m.md"],
)
def test_verify_export_flags_a_path_outside_the_list(split, tmp_path, capsys, extra):
    root = _export(tmp_path / "export")
    (root / extra).parent.mkdir(parents=True, exist_ok=True)
    (root / extra).write_text("x\n", encoding="utf-8")
    problems = _verify(split, root)
    assert len(problems) == 1 and extra in problems[0]
    code = split.verify_export.main([str(root), "--allow-list", str(ALLOW_LIST)])
    out = capsys.readouterr().out
    assert code == 1
    assert extra in out and "verify_export: 1 problem(s)" in out


def test_verify_export_flags_a_missing_required_entry(split, tmp_path):
    root = _export(tmp_path / "export")
    (root / "LICENSE").unlink()
    assert _verify(split, root) == ["required entry LICENSE matched no file"]
    (root / "tests" / "test_a.py").unlink()
    problems = _verify(split, root)
    assert "required entry tests/ matched no file" in problems
    assert "required entry LICENSE matched no file" in problems


def test_verify_export_flags_an_empty_export_and_a_missing_folder(split, tmp_path, capsys):
    root = tmp_path / "empty"
    root.mkdir()
    assert _verify(split, root) == ["the export is empty"]
    assert split.verify_export.main([str(root), "--allow-list", str(ALLOW_LIST)]) == 1
    assert split.verify_export.main([str(tmp_path / "nope"), "--allow-list", str(ALLOW_LIST)]) == 2
    assert split.verify_export.main([str(root), "--allow-list", str(tmp_path / "nope.txt")]) == 2
    capsys.readouterr()


def test_shipped_allow_list_names_every_required_entry(split):
    allow = split.verify_export.load_allow_list(ALLOW_LIST)
    for entry in split.verify_export.REQUIRED:
        probe = entry + "x" if entry.endswith("/") else entry
        assert allow.allowed(probe), entry


# -- the builder and the planning sync ------------------------------------------------------------

OWNER_NAME = "Fixture Owner"
OWNER_EMAIL = "1+fixture-owner@users.noreply.github.com"
SESSION_URL = "https://claude.ai/" + "code/session_" + "01ABCDEFGHIJKL"


def _git(cwd: Path, *args: str) -> str:
    """Run git in cwd with no global or system config; return stdout text, raise on a failure."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=str(cwd.parent / "nogitconfig"), GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    run = subprocess.run([GIT, *args], cwd=cwd, env=env, capture_output=True, timeout=120)
    if run.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed (exit {run.returncode}): {run.stderr.decode('utf-8', 'replace')}")
    return run.stdout.decode("utf-8", "replace")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _write(repo: Path, rel: str, text: str = "x\n") -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def _make_source(tmp_path: Path) -> Path:
    """A private-repo stand-in: every required entry, planning files, collection content, a gitlink, tagged pre-split."""
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (
        ("user.name", "Fixture User"),
        ("user.email", "fixture@example.invalid"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        _git(repo, "config", key, value)
    for rel in REQUIRED_FILES:
        _write(repo, rel)
    _write(repo, ".planning/STATE.md", f"@{WORKTREE}/.claude/gsd-core/x.md\ncache {HOME}/AppData\n")
    _write(repo, ".planning/todos/x.md")
    _write(repo, ".planning/phases/16-repo-split/16-01-SUMMARY.md")
    _write(repo, ".planning/phases/14-test-suite-speed-up/measurements/a.log")
    _write(repo, ".planning/milestones/x.md")
    _write(repo, "reports/r.md")
    _write(repo, "downloaded_examples/x.zip")
    _write(repo, ".gitmodules", "[submodule]\n")
    _commit_all(repo, "base")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},Custom")
    _git(repo, "commit", "-q", "-m", "add a gitlink")
    _git(repo, "tag", "pre-split")
    _write(repo, "kicad_lib_manager/untracked.py")
    return repo


EXPECTED_TRACKED = sorted(
    (
        *REQUIRED_FILES,
        ".planning/STATE.md",
        ".planning/todos/x.md",
        ".planning/phases/16-repo-split/16-01-SUMMARY.md",
    )
)


def _build(split, source: Path, dest: Path, **extra):
    allow = split.verify_export.load_allow_list(ALLOW_LIST)
    mapping = split.scrub.parse_map([f"{WORKTREE}="])
    return split.build_tool_repo.build(
        source, "pre-split", dest, allow, mapping=mapping, name=OWNER_NAME, email=OWNER_EMAIL, **extra
    )


@pytest.mark.slow
@requires_git
def test_build_exports_only_the_allow_list(split, tmp_path):
    source = _make_source(tmp_path)
    dest = tmp_path / "tool"
    summary = _build(split, source, dest)
    assert dest.is_dir() and summary

    assert sorted(_git(dest, "ls-files").splitlines()) == EXPECTED_TRACKED
    for absent in ("Custom", "downloaded_examples", "reports", ".gitmodules", ".planning/milestones", "kicad_lib_manager/untracked.py"):
        assert not (dest / absent).exists(), absent
    state = (dest / ".planning" / "STATE.md").read_text(encoding="utf-8")
    assert state == "@.claude/gsd-core/x.md\ncache <home>/AppData\n"

    assert _git(dest, "rev-list", "--count", "HEAD").strip() == "1"
    assert _git(dest, "branch", "--show-current").strip() == "main"
    identity = _git(dest, "log", "-1", "--format=%an|%ae|%cn|%ce").strip()
    assert identity == f"{OWNER_NAME}|{OWNER_EMAIL}|{OWNER_NAME}|{OWNER_EMAIL}"
    assert _git(dest, "config", "core.hooksPath").strip() == ".githooks"
    message = _git(dest, "log", "-1", "--format=%B")
    last = [line for line in message.splitlines() if line.strip()][-1]
    assert last.startswith("Co-Authored-By: Claude ")
    assert split.build_tool_repo.DEFAULT_MESSAGE.rstrip("\n").endswith(last)
    assert "Claude-Session" not in message and "claude.ai" not in message
    assert split.verify_export.verify(dest, split.verify_export.load_allow_list(ALLOW_LIST)) == []


def test_build_drops_a_session_line_from_a_given_message(split):
    clean = split.build_tool_repo.clean_message
    message = f"Import\n\nCo-Authored-By: Claude Test <noreply@anthropic.com>\nClaude-Session: {SESSION_URL}\n"
    assert clean(message) == "Import\n\nCo-Authored-By: Claude Test <noreply@anthropic.com>\n"
    assert clean(f"Import\n\nsee {SESSION_URL} for more\nbody\n") == "Import\n\nbody\n"
    assert clean("Plain subject\n\nbody line\n") == "Plain subject\n\nbody line\n"
    # any case, any indent, as the scan's session_trailer and session_url rules see them
    for variant in ("claude-" + "session: abc", "  Claude-" + "Session: abc", "CLAUDE-" + "SESSION: abc", f"see {SESSION_URL.upper()}"):
        assert clean(f"Import\n{variant}\nbody\n") == "Import\nbody\n", variant
    assert clean(split.build_tool_repo.DEFAULT_MESSAGE) == split.build_tool_repo.DEFAULT_MESSAGE


def test_a_failed_build_is_cleaned_up_even_with_read_only_git_objects(split, tmp_path):
    import stat

    for created in (True, False):
        dest = tmp_path / f"dest-{created}"
        objects = dest / ".git" / "objects" / "ab"
        objects.mkdir(parents=True)
        blob = objects / "cdef"
        blob.write_bytes(b"x")
        blob.chmod(stat.S_IREAD)
        (dest / "file.txt").write_text("x\n", encoding="utf-8")
        split.build_tool_repo._clear(dest, created)
        assert dest.exists() is not created
        if dest.exists():
            assert list(dest.iterdir()) == []


def test_build_refuses_a_non_empty_dest(split, tmp_path, capsys):
    dest = tmp_path / "tool"
    dest.mkdir()
    (dest / "keep.txt").write_text("x\n", encoding="utf-8")
    argv = ["--source", str(tmp_path), "--ref", "pre-split", "--dest", str(dest)]
    argv += ["--allow-list", str(ALLOW_LIST), "--name", OWNER_NAME, "--email", OWNER_EMAIL]
    assert split.build_tool_repo.main(argv) == 2
    assert f"destination is not empty: {dest}" in capsys.readouterr().err
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "x\n"


@pytest.mark.slow
@requires_git
def test_sync_planning_copies_the_delta(split, tmp_path):
    source = _make_source(tmp_path)
    dest = tmp_path / "tool"
    _build(split, source, dest)

    _write(source, ".planning/phases/16-repo-split/16-13-SUMMARY.md", f"see {WORKTREE}/x and {HOME}/y\n")
    _write(source, ".planning/STATE.md", f"changed {MAIN}/z\n")
    (source / ".planning" / "todos" / "x.md").unlink()
    _write(source, ".planning/quick/q.md")
    _write(source, ".planning/phases/14-test-suite-speed-up/measurements/b.log")
    _write(source, "kicad_lib_manager/a.py", "changed\n")
    _commit_all(source, "later work")

    allow = split.verify_export.load_allow_list(ALLOW_LIST)
    mapping = split.scrub.parse_map([f"{WORKTREE}=", f"{MAIN}=<main-checkout>"])
    lines = split.sync_planning.sync(source, "main", "pre-split", dest, allow, mapping)
    assert lines == [
        "M .planning/STATE.md",
        "skip .planning/phases/14-test-suite-speed-up/measurements/b.log",
        "A .planning/phases/16-repo-split/16-13-SUMMARY.md",
        "skip .planning/quick/q.md",
        "D .planning/todos/x.md",
    ]
    summary = dest / ".planning" / "phases" / "16-repo-split" / "16-13-SUMMARY.md"
    assert summary.read_text(encoding="utf-8") == "see x and <home>/y\n"
    assert (dest / ".planning" / "STATE.md").read_text(encoding="utf-8") == "changed <main-checkout>/z\n"
    assert not (dest / ".planning" / "todos" / "x.md").exists()
    assert not (dest / ".planning" / "quick").exists()
    assert not (dest / ".planning" / "phases" / "14-test-suite-speed-up").exists()
    assert not (dest / "kicad_lib_manager" / "a.py").exists()


@pytest.mark.slow
@requires_git
def test_sync_planning_refuses_an_unknown_ref(split, tmp_path, capsys):
    source = tmp_path / "not-a-repository"
    source.mkdir()
    dest = tmp_path / "tool"
    dest.mkdir()
    argv = ["--source", str(source), "--ref", "nope", "--since", "pre-split", "--dest", str(dest)]
    assert split.sync_planning.main([*argv, "--allow-list", str(ALLOW_LIST)]) == 2
    assert "nope" in capsys.readouterr().err
