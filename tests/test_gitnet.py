"""The full catalog git runner, pinned per function (Phase 17 plan 03; CAT-11, CAT-07, CAT-04).

Every test here uses a recording NetGit.starter that returns canned StreamOutcome values, so no
process starts and the quick run stays free of git. The real behaviour of the flags is proven on
local repositories in tests/test_catalog_gitnet_git.py (slow).
"""

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from kicad_lib_manager.catalog import gitnet
from kicad_lib_manager.catalog.gitnet import NetGit, NetRun, RemoteHead
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.procs import StreamOutcome

SHA = "a" * 40
URL = "https://example.org/a/b.git"
# built at run time: a literal user@host in a tracked file is flagged by the pre-publish scan
USER_URL = "https://user:pw" + "@" + "github.com/a/b"


@dataclass
class Call:
    argv: list
    env: dict
    timeout: float
    capture_stdout: bool


def out(code=0, stdout="", lines=()):
    return StreamOutcome(code, stdout.encode("utf-8"), tuple(lines), False, False)


class Recorder:
    """A NetGit.starter that answers from a queue (the last answer repeats) and feeds the lines to on_line."""

    def __init__(self, *answers):
        self.answers = list(answers) or [out()]
        self.calls: list[Call] = []

    def __call__(self, argv, *, env, stop, timeout, on_line, capture_stdout):
        self.calls.append(Call(list(argv), env, timeout, capture_stdout))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        for line in answer.lines:
            if on_line is not None:
                on_line(line)
        return answer


def make_net(recorder, *, allow_file=False):
    return NetGit(exe=Path("git-under-test"), allow_file=allow_file, starter=recorder)


def tail(call, sub):
    """The argv from the subcommand on."""
    return call.argv[call.argv.index(sub) :]


def make_clone(tmp_path, name="Lib"):
    clone = tmp_path / name
    (clone / ".git").mkdir(parents=True)
    return clone


def assert_in_clone_env(call, clone):
    assert call.env["GIT_DIR"] == str(clone / ".git")
    assert call.env["GIT_WORK_TREE"] == str(clone)
    at = call.argv.index("-C")
    assert call.argv[at + 1] == str(clone)


# -- ls-remote ----------------------------------------------------------------


def test_ls_remote_argv_is_pinned():
    rec = Recorder(out(0, f"{SHA}\trefs/heads/main\n"))
    result = gitnet.ls_remote(make_net(rec), URL, "main")
    assert result == RemoteHead(SHA)
    (call,) = rec.calls
    assert tail(call, "ls-remote") == ["ls-remote", "--exit-code", "--", URL, "refs/heads/main"]
    assert call.timeout == gitnet.LS_REMOTE_TIMEOUT
    assert call.capture_stdout is True
    assert "GIT_DIR" not in call.env and "-C" not in call.argv


@pytest.mark.parametrize(
    ("code", "expected"),
    [(2, "git.branch_missing"), (128, "git.unreachable"), (1, "git.unreachable")],
)
def test_ls_remote_exit_codes(code, expected):
    result = gitnet.ls_remote(make_net(Recorder(out(code, "", ("fatal: nope",)))), URL, "main")
    assert isinstance(result, Issue)
    assert (result.code, result.severity) == (expected, Severity.ERROR)


def test_ls_remote_timeout_and_unusable_answer():
    timed_out = StreamOutcome(None, b"", (), False, True)
    assert gitnet.ls_remote(make_net(Recorder(timed_out)), URL, "main").code == "git.timeout"
    # exit 0 with nothing readable is not a head
    assert gitnet.ls_remote(make_net(Recorder(out(0, ""))), URL, "main").code == "git.unreachable"
    assert gitnet.ls_remote(make_net(Recorder(out(0, "nonsense\n"))), URL, "main").code == "git.unreachable"


def test_default_branch_parses_symref():
    stdout = f"ref: refs/heads/master\tHEAD\n{SHA}\tHEAD\n"
    rec = Recorder(out(0, stdout))
    assert gitnet.default_branch(make_net(rec), URL) == ("master", SHA)
    (call,) = rec.calls
    assert tail(call, "ls-remote") == ["ls-remote", "--symref", "--", URL, "HEAD"]
    assert call.capture_stdout is True


def test_default_branch_without_a_symref_or_without_an_answer():
    assert gitnet.default_branch(make_net(Recorder(out(0, f"{SHA}\tHEAD\n"))), URL).code == "git.branch_missing"
    assert gitnet.default_branch(make_net(Recorder(out(128, "", ("fatal: x",)))), URL).code == "git.unreachable"


def test_branch_names_cannot_inject_a_refspec_or_an_option():
    rec = Recorder()
    net = make_net(rec)
    for bad in ("main:other", "-x", "", "a b", "../x"):
        with pytest.raises(ValueError):
            gitnet.ls_remote(net, URL, bad)
        with pytest.raises(ValueError):
            gitnet.fetch_shallow(net, Path("."), URL, bad)
    assert rec.calls == []


def test_an_address_with_a_user_name_is_refused_before_git_starts(tmp_path):
    rec = Recorder()
    net = make_net(rec)
    clone = make_clone(tmp_path)
    results = [
        gitnet.ls_remote(net, USER_URL, "main"),
        gitnet.default_branch(net, USER_URL),
        gitnet.fetch_shallow(net, clone, USER_URL, "main"),
        gitnet.clone_shallow(net, USER_URL, "main", tmp_path / "dest"),
    ]
    assert [r.code for r in results] == ["git.bad_url"] * 4
    assert "pw" not in " ".join(r.text for r in results)
    assert rec.calls == []


# -- fetch and reset ---------------------------------------------------------------


def test_fetch_argv_is_pinned(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder(out(0, "", ("Receiving objects:  50% (1/2)",)), out(0, f"{SHA}\n"))
    seen = []
    result = gitnet.fetch_shallow(make_net(rec), clone, URL, "main", progress=lambda t, p: seen.append((t, p)))
    assert result == SHA
    fetch, parse = rec.calls
    assert tail(fetch, "fetch") == [
        "fetch", "--depth", "1", "--no-tags", "--no-recurse-submodules", "--progress", "--", URL, "main",
    ]  # fmt: skip
    assert tail(parse, "rev-parse") == ["rev-parse", "--verify", "FETCH_HEAD^{commit}"]
    assert fetch.timeout == gitnet.FETCH_TIMEOUT
    for call in (fetch, parse):
        assert_in_clone_env(call, clone)
    assert seen == [("Receiving objects:  50% (1/2)", 40)]


def test_fetch_failures_come_back_as_issues(tmp_path):
    clone = make_clone(tmp_path)
    failed = gitnet.fetch_shallow(make_net(Recorder(out(128, "", ("fatal: no",)))), clone, URL, "main")
    assert (failed.code, failed.severity) == ("git.fetch_failed", Severity.ERROR)
    assert "fatal: no" in failed.text
    # a fetch that worked but whose commit cannot be read is also a failure
    garbled = gitnet.fetch_shallow(make_net(Recorder(out(0), out(0, "not-a-sha\n"))), clone, URL, "main")
    assert garbled.code == "git.fetch_failed"
    parse_failed = gitnet.fetch_shallow(make_net(Recorder(out(0), out(128))), clone, URL, "main")
    assert parse_failed.code == "git.fetch_failed"


def test_reset_refuses_a_non_sha(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder()
    net = make_net(rec)
    for bad in ("main", "HEAD", "A" * 40, "a" * 39, "a" * 41, "--hard", ""):
        with pytest.raises(ValueError):
            gitnet.reset_hard(net, clone, bad)
    assert rec.calls == []
    result = gitnet.reset_hard(net, clone, SHA)
    assert isinstance(result, NetRun)
    (call,) = rec.calls
    assert tail(call, "reset") == ["reset", "--hard", "-q", SHA]
    assert_in_clone_env(call, clone)


def test_reset_failure_is_an_issue(tmp_path):
    clone = make_clone(tmp_path)
    result = gitnet.reset_hard(make_net(Recorder(out(128, "", ("fatal: bad",)))), clone, SHA)
    assert (result.code, result.severity) == ("git.reset_failed", Severity.ERROR)


def test_in_clone_calls_refuse_a_folder_without_git(tmp_path):
    folder = tmp_path / "NoGit"
    folder.mkdir()
    rec = Recorder()
    net = make_net(rec)
    results = [
        gitnet.status_entries(net, folder),
        gitnet.changed_paths(net, folder, SHA),
        gitnet.tree_paths(net, folder, "HEAD"),
        gitnet.fetch_shallow(net, folder, URL, "main"),
        gitnet.reset_hard(net, folder, SHA),
        gitnet.head_commit(net, folder),
    ]
    for result in results:
        assert isinstance(result, Issue)
        assert (result.code, result.severity) == ("git.not_a_clone", Severity.ERROR)
        assert str(folder) in result.text
    assert gitnet.read_blob(net, folder, "HEAD", "a") is None
    assert rec.calls == []


def test_a_git_file_is_not_a_clone_either(tmp_path):
    folder = tmp_path / "Linked"
    folder.mkdir()
    (folder / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    rec = Recorder()
    assert gitnet.status_entries(make_net(rec), folder).code == "git.not_a_clone"
    assert rec.calls == []


# -- reading a clone --------------------------------------------------------------------


def test_parse_name_status():
    assert gitnet.parse_name_status("M\0a.kicad_mod\0A\0b.kicad_sym\0") == [("M", "a.kicad_mod"), ("A", "b.kicad_sym")]
    assert gitnet.parse_name_status("") == []
    assert gitnet.parse_name_status("D\0only/path\0") == [("D", "only/path")]


def test_status_entries_lists_paths_once(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder(out(0, " M x\0?? y\0"))
    assert gitnet.status_entries(make_net(rec), clone) == ["x", "y"]
    (call,) = rec.calls
    assert tail(call, "status") == ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    assert call.capture_stdout is True
    assert_in_clone_env(call, clone)
    # a rename is followed by its source path, which is not counted again
    assert gitnet.status_entries(make_net(Recorder(out(0, "R  new\0old\0 M z\0"))), clone) == ["new", "z"]
    assert gitnet.status_entries(make_net(Recorder(out(0, ""))), clone) == []
    assert gitnet.status_entries(make_net(Recorder(out(128, "", ("fatal: x",)))), clone).code == "git.read_failed"


def test_changed_paths_uses_plumbing_diff_tree(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder(out(0, "M\0a.kicad_mod\0D\0old/b.kicad_sym\0"))
    result = gitnet.changed_paths(make_net(rec), clone, SHA)
    assert result == [("M", "a.kicad_mod"), ("D", "old/b.kicad_sym")]
    (call,) = rec.calls
    assert tail(call, "diff-tree") == [
        "diff-tree", "-r", "--no-renames", "--name-status", "-z", "--no-commit-id", "HEAD", SHA,
    ]  # fmt: skip
    assert "diff" not in call.argv  # never the porcelain diff (RESEARCH C11)
    assert_in_clone_env(call, clone)
    assert gitnet.changed_paths(make_net(Recorder(out(128))), clone, SHA).code == "git.read_failed"
    with pytest.raises(ValueError):
        gitnet.changed_paths(make_net(Recorder()), clone, "HEAD")


def test_tree_paths_and_read_blob(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder(out(0, "a.txt\0sub/b.txt\0"))
    assert gitnet.tree_paths(make_net(rec), clone, SHA) == ["a.txt", "sub/b.txt"]
    assert tail(rec.calls[0], "ls-tree") == ["ls-tree", "-r", "--name-only", "-z", SHA]
    assert gitnet.tree_paths(make_net(Recorder(out(128))), clone, "HEAD").code == "git.read_failed"

    blob = Recorder(out(0, "* text=auto\n"))
    assert gitnet.read_blob(make_net(blob), clone, SHA, "sub/.gitattributes") == b"* text=auto\n"
    assert tail(blob.calls[0], "cat-file") == ["cat-file", "blob", f"{SHA}:sub/.gitattributes"]
    # rc 128 is "no such file"
    assert gitnet.read_blob(make_net(Recorder(out(128))), clone, SHA, "none") is None
    for bad in ("--output=x", "main", ""):
        with pytest.raises(ValueError):
            gitnet.tree_paths(make_net(Recorder()), clone, bad)
        with pytest.raises(ValueError):
            gitnet.read_blob(make_net(Recorder()), clone, bad, "x")


def test_head_commit_keeps_working_inside_a_clone(tmp_path):
    clone = make_clone(tmp_path)
    rec = Recorder(out(0, f"{SHA}\n"))
    assert gitnet.head_commit(make_net(rec), clone) == SHA
    assert_in_clone_env(rec.calls[0], clone)


# -- progress, versions, config ---------------------------------------------------------


def test_percent_bands():
    assert gitnet.percent("Receiving objects:  50% (1/2)") == 40
    assert gitnet.percent("Updating files: 100% (3/3)") == 100
    assert gitnet.percent("Updating files:   0% (0/3)") == 80
    assert gitnet.percent("Counting objects: 100% (5/5)") == 5
    assert gitnet.percent("Compressing objects:  50% (1/2)") == 7
    assert gitnet.percent("Resolving deltas:  50% (1/2)") == 75
    assert gitnet.percent("remote: Receiving objects:  10% (1/9), 1.2 MiB | 2.0 MiB/s") == 16
    assert gitnet.percent("Cloning into 'x'...") is None
    assert gitnet.percent("") is None


def test_clone_progress_carries_the_percent(tmp_path):
    rec = Recorder(out(0, "", ("Cloning into 'x'...", "Receiving objects:  50% (1/2)")))
    seen = []
    result = gitnet.clone_shallow(make_net(rec), URL, "main", tmp_path / "dest", progress=lambda t, p: seen.append((t, p)))
    assert isinstance(result, NetRun)
    assert seen == [("Cloning into 'x'...", None), ("Receiving objects:  50% (1/2)", 40)]


def test_version_issues():
    refusal, warning = gitnet.version_issues(None)
    assert (refusal.code, refusal.severity, warning) == ("git.not_found", Severity.ERROR, None)
    assert "Install Git for Windows" in refusal.text

    refusal, warning = gitnet.version_issues((2, 31, 9))
    assert (refusal.code, refusal.severity, warning) == ("git.too_old", Severity.ERROR, None)
    assert "2.31.9" in refusal.text and "2.32" in refusal.text

    refusal, warning = gitnet.version_issues((2, 49, 0))
    assert refusal is None
    assert (warning.code, warning.severity) == ("git.old_version", Severity.WARNING)
    assert "2.49.0" in warning.text and "2.49.1" in warning.text and "The catalog still works." in warning.text

    refusal, warning = gitnet.version_issues((2, 32))
    assert refusal is None and warning.code == "git.old_version" and "2.32" in warning.text
    assert gitnet.version_issues((2, 49, 1)) == (None, None)
    assert gitnet.version_issues((2, 50, 1)) == (None, None)
    assert gitnet.version_issues((3, 0)) == (None, None)


def test_the_net_floor_is_independent_of_the_commit_path_floor():
    from kicad_lib_manager import gitops

    assert gitnet.MIN_NET_GIT == (2, 32)
    assert gitops.MIN_GIT_VERSION == (2, 25)


SAFE_CONFIG = """[core]
\trepositoryformatversion = 0
\tfilemode = false
\tbare = false
\tlogallrefupdates = true
\tsymlinks = false
\tignorecase = true
\tautocrlf = false
\tlongpaths = true
[remote "origin"]
\turl = https://example.org/a/b.git
\tfetch = +refs/heads/main:refs/remotes/origin/main
\ttagopt = --no-tags
[branch "main"]
\tremote = origin
\tmerge = refs/heads/main
[gc]
\tauto = 0
[maintenance]
\tauto = false
[lfs]
\trepositoryformatversion = 0
"""


def write_config(tmp_path, text):
    clone = make_clone(tmp_path)
    (clone / ".git" / "config").write_text(text, encoding="utf-8")
    return clone


def test_config_problems_allow_list(tmp_path):
    clone = write_config(tmp_path, SAFE_CONFIG)
    assert gitnet.config_problems(clone) == []
    extra = SAFE_CONFIG.replace(
        "[gc]",
        '[core]\n\tfsmonitor = x\n\tsshCommand = y\n[alias]\n\tx = !calc\n[credential]\n\thelper = h\n[gc]',
    )
    clone = write_config(tmp_path / "two", extra)
    assert sorted(gitnet.config_problems(clone)) == sorted(
        ["core.fsmonitor", "core.sshCommand", "alias.x", "credential.helper"]
    )


def test_config_problems_sees_what_a_careless_parser_misses(tmp_path):
    text = (
        "[core] fsmonitor = evil\n"  # a key on the header line
        '[remote "other"]\n\turl = https://example.org/x.git\n'  # only origin is expected
        '[branch "main"]\n\tpushremote = other\n'
        '[include]\n\tpath = ../elsewhere\n'
        '[credential "https://example.org"]\n\thelper = x\n'
        "[core]\n# a comment\n; another\n\tbare = false\n\tpager = less\\\n\t  continued\n"
        "this is not a setting\n"
    )
    problems = gitnet.config_problems(write_config(tmp_path, text))
    assert "core.fsmonitor" in problems
    assert "remote.other.url" in problems
    assert "branch.main.pushremote" in problems
    assert "include.path" in problems
    assert "credential.https://example.org.helper" in problems
    assert "core.pager" in problems
    assert any(p.startswith("unreadable line") for p in problems)
    assert "core.bare" not in problems


def test_config_problems_without_a_git_folder_or_a_config(tmp_path):
    folder = tmp_path / "NoGit"
    folder.mkdir()
    assert gitnet.config_problems(folder) == ["no .git folder"]
    bare_clone = make_clone(tmp_path)
    assert gitnet.config_problems(bare_clone) == ["no .git/config"]


# -- argv policy and secrets ----------------------------------------------------------


def test_unknown_subcommand_is_refused():
    net = NetGit(exe=Path("git-under-test"))
    for sub in ("push", "submodule", "config", "gc", "checkout"):
        with pytest.raises(ValueError):
            gitnet._argv(net, sub, [])


def test_net_subcommands_are_exactly_the_planned_set():
    assert gitnet.NET_SUBCOMMANDS == {
        "clone", "fetch", "ls-remote", "reset", "status", "rev-parse", "diff-tree", "ls-tree", "cat-file",
    }  # fmt: skip


def test_stderr_userinfo_is_stripped(tmp_path):
    lines = (f"remote: trying {USER_URL}", f"fatal: unable to access '{USER_URL}/': refused")
    rec = Recorder(out(128, "", lines))
    seen = []
    result = gitnet.clone_shallow(
        make_net(rec), "https://github.com/a/b", "main", tmp_path / "dest", progress=lambda t, p: seen.append(t)
    )
    assert result.code == "git.clone_failed"
    assert "pw" not in result.text and "user" not in result.text and "github.com/a/b" in result.text
    assert seen and all("pw" not in text for text in seen)

    clone = make_clone(tmp_path)
    fetched = gitnet.fetch_shallow(make_net(Recorder(out(128, "", lines))), clone, URL, "main")
    assert "pw" not in fetched.text


def test_the_environment_is_scrubbed_for_every_call(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "stray")
    monkeypatch.setenv("GIT_INDEX_FILE", "stray")
    clone = make_clone(tmp_path)
    rec = Recorder()
    net = make_net(rec)
    gitnet.ls_remote(net, URL, "main")
    gitnet.status_entries(net, clone)
    for call in rec.calls:
        assert call.env["GIT_CONFIG_GLOBAL"] == os.devnull
        assert call.env["GIT_TERMINAL_PROMPT"] == "0" and call.env["GCM_INTERACTIVE"] == "Never"
        assert call.env.get("GIT_INDEX_FILE") is None
    assert rec.calls[0].env.get("GIT_DIR") is None
    assert rec.calls[1].env["GIT_DIR"] == str(clone / ".git")
