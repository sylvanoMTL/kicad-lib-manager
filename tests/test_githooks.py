"""The tracked git hooks of the tool checkout (Phase 16, D-13, D-09).

commit-msg deletes the Claude-Session line and any claude.ai session URL line from a commit message and
keeps the Co-Authored-By line; pre-push runs scripts/prepublish_scan.py --tree --history and blocks the
push when it exits non-zero. Each test works in a throwaway repository; the session URL is assembled at
run time so this file scans clean, and the pre-push test uses a stub scan, not the real script.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from gitfixtures import GIT, requires_git

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".githooks"

SESSION_URL = "https://claude.ai/" + "code/session_" + "01ABCDEFGHIJKL"
TRAILER = "Claude-" + "Session: " + SESSION_URL
CO_AUTHOR = "Co-Authored-By: Claude Test <noreply@anthropic.com>"


def _env(repo: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.pop("PREPUBLISH_ALLOW_NO_DENY_LIST", None)
    env.update(GIT_CONFIG_GLOBAL=str(repo.parent / "nogitconfig"), GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    # the stub scan and the hook's interpreter lookup need a working python on PATH
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def _git(repo: Path, *args: str) -> str:
    run = subprocess.run([GIT, *args], cwd=repo, env=_env(repo), capture_output=True, timeout=120)
    if run.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed (exit {run.returncode}): {run.stderr.decode('utf-8', 'replace')}")
    return run.stdout.decode("utf-8", "replace")


def _hook_repo(tmp_path: Path) -> Path:
    """A throwaway repository whose core.hooksPath is a copy of the tracked .githooks folder."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (
        ("user.name", "Fixture User"),
        ("user.email", "fixture@example.invalid"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", ".githooks"),
    ):
        _git(repo, "config", key, value)
    shutil.copytree(HOOKS, repo / ".githooks")
    return repo


def _commit(repo: Path, message: str) -> str:
    """Commit one new file with the message through a file (so the hook sees the whole text); return the stored message."""
    (repo / "file.txt").write_text(message, encoding="utf-8")
    _git(repo, "add", "file.txt")
    (repo / "message.txt").write_bytes(message.encode("utf-8"))
    _git(repo, "commit", "-q", "-F", "message.txt")
    return _git(repo, "log", "-1", "--format=%B").rstrip("\n")


def _sh() -> str | None:
    """The POSIX shell Git for Windows ships (or sh on PATH elsewhere)."""
    found = shutil.which("sh")
    if found:
        return found
    exec_path = Path(_git(Path.cwd(), "--exec-path").strip())
    for parent in exec_path.parents:
        for candidate in (parent / "usr" / "bin" / "sh.exe", parent / "bin" / "sh.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


def _run_commit_msg(tmp_path: Path, message: str) -> str:
    """Run the commit-msg hook on a message file (it needs no repository, so no git init) and return the stored text."""
    shell = _sh()
    if shell is None:
        pytest.skip("no POSIX shell to run the hook")
    path = tmp_path / "message.txt"
    path.write_bytes(message.encode("utf-8"))
    done = subprocess.run([shell, str(HOOKS / "commit-msg"), str(path)], env=_env(tmp_path), capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return path.read_bytes().decode("utf-8").rstrip("\n")


def test_commit_msg_strips_the_session_line(tmp_path):
    message = f"Add the thing\n\nBody line one.\n\nsee {SESSION_URL} for the session\n{CO_AUTHOR}\n{TRAILER}\n"
    stored = _run_commit_msg(tmp_path, message)
    assert stored == f"Add the thing\n\nBody line one.\n\n{CO_AUTHOR}"
    assert "Claude-Session" not in stored
    assert "claude.ai" not in stored


@pytest.mark.slow
@requires_git
def test_commit_msg_runs_as_a_git_hook(tmp_path):
    """The same hook, wired through core.hooksPath and a real commit."""
    repo = _hook_repo(tmp_path)
    stored = _commit(repo, f"Add the thing\n\n{CO_AUTHOR}\n{TRAILER}\n")
    assert stored == f"Add the thing\n\n{CO_AUTHOR}"


def test_commit_msg_is_never_weaker_than_the_scan(tmp_path):
    """The scan matches the trailer in any case and indented, the URL in any case; the hook must too."""
    variants = ["claude-" + "session: abc", "  Claude-" + "Session: abc", "\tCLAUDE-" + "SESSION: abc", "see " + SESSION_URL.upper()]
    stored = _run_commit_msg(tmp_path, "Subject\n" + "\n".join(variants) + "\nbody\n" + CO_AUTHOR + "\n")
    assert stored.splitlines() == ["Subject", "body", CO_AUTHOR]


def test_commit_msg_keeps_ordinary_messages(tmp_path):
    message = f"Fix the parser\n\nClaude wrote the first draft; a session of review followed.\n\n{CO_AUTHOR}\n"
    assert _run_commit_msg(tmp_path, message) == message.rstrip("\n")


@pytest.mark.slow
@requires_git
def test_pre_push_blocks_on_a_failing_scan(tmp_path):
    repo = _hook_repo(tmp_path)
    shell = _sh()
    if shell is None:
        pytest.skip("no POSIX shell to run the hook")
    scripts = repo / "scripts"
    scripts.mkdir()

    def run_hook(exit_code: int, **extra_env: str) -> subprocess.CompletedProcess:
        stub = "import sys\nopen('scan_args.txt', 'w').write(' '.join(sys.argv[1:]))\nsys.exit(%d)\n" % exit_code
        (scripts / "prepublish_scan.py").write_text(stub, encoding="utf-8")
        return subprocess.run(
            [shell, ".githooks/pre-push", "origin", "https://example.invalid/repo.git"],
            cwd=repo,
            env={**_env(repo), **extra_env},
            input=b"",
            capture_output=True,
            timeout=120,
        )

    # without prepublish.denyTermsFile the hook refuses before the scan runs, unless the opt-out is set
    refused = run_hook(0)
    assert refused.returncode != 0
    assert "prepublish.denyTermsFile" in refused.stderr.decode("utf-8", "replace")
    assert not (repo / "scan_args.txt").exists()
    opted_out = run_hook(0, PREPUBLISH_ALLOW_NO_DENY_LIST="1")
    assert opted_out.returncode == 0
    assert (repo / "scan_args.txt").read_text(encoding="utf-8") == "--tree --history"
    (repo / "scan_args.txt").unlink()

    _git(repo, "config", "prepublish.denyTermsFile", "deny-terms.txt")
    failing = run_hook(1)
    assert failing.returncode != 0
    assert "nothing was pushed" in failing.stderr.decode("utf-8", "replace")
    assert (repo / "scan_args.txt").read_text(encoding="utf-8") == "--tree --history"

    (repo / "scan_args.txt").unlink()
    passing = run_hook(0)
    assert passing.returncode == 0
    assert (repo / "scan_args.txt").read_text(encoding="utf-8") == "--tree --history"
