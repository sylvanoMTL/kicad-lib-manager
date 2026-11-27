"""The network git runner of the library catalog (Phase 17, CAT-11): the only code that lets git talk to a remote.

Kept apart from gitops on purpose: gitops never touches another repository, so its subcommand allow-list
and its tests stay as they are. Every call here is a list argv with a hardened -c prefix and an environment
built from scratch, so nothing a downloaded library or the user's own git setup carries can run a program
(hooks, LFS filters, fsmonitor, external diff, credential helpers) or ask a question. Processes are started
only through procs. Qt-free; imports only models and procs.
"""

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import procs
from ..models import Issue, Severity

NET_SUBCOMMANDS = frozenset({"clone", "fetch", "ls-remote", "reset", "status", "rev-parse", "diff-tree", "ls-tree", "cat-file"})

# Passed as -c <item> on every call. credential.helper and core.askPass are cleared so no helper window
# opens; protocol.allow=never plus an https allowance refuses every other transport; the rest switch off
# what a downloaded repository could use to run a program.
_BASE_CONFIG = (
    "credential.helper=",
    "core.askPass=",
    "protocol.allow=never",
    "protocol.https.allow=always",
    "core.hooksPath=",
    "core.fsmonitor=false",
    "transfer.bundleURI=false",
    "submodule.recurse=false",
    "http.sslVerify=true",
    "http.lowSpeedLimit=1000",
    "http.lowSpeedTime=60",
    "filter.lfs.process=",
    "filter.lfs.smudge=",
    "filter.lfs.required=false",
    "diff.external=",
    "core.pager=cat",
    "core.quotepath=false",
)
CLONE_TIMEOUT = 4 * 3600.0  # a large library is many GB
LOCAL_TIMEOUT = 300.0

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_USERINFO_RE = re.compile(r"(https?://)[^/@\s]+@")


@dataclass(frozen=True)
class NetGit:
    """The git executable, whether file:// addresses are allowed (tests only), and a stand-in for the starter."""

    exe: Path
    allow_file: bool = False
    starter: Callable | None = None


@dataclass(frozen=True)
class NetRun:
    returncode: int
    stdout: bytes
    lines: tuple[str, ...]


def _argv(net: NetGit, sub: str, args, *, clone: Path | None = None) -> list[str]:
    """The full argv of one network-runner call; raises ValueError for a subcommand outside NET_SUBCOMMANDS."""
    if sub not in NET_SUBCOMMANDS:
        raise ValueError(f"git {sub} is not allowed")
    items = list(_BASE_CONFIG)
    if net.allow_file:
        items.append("protocol.file.allow=always")
    argv = [str(net.exe), "--literal-pathspecs"]
    for item in items:
        argv += ["-c", item]
    if clone is not None:
        argv += ["-C", str(clone)]
    return [*argv, sub, *args]


def _env(clone: Path | None = None, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of the environment without any GIT_* variable, plus the fixed safe values.

    Inside a clone GIT_DIR and GIT_WORK_TREE name it, so a folder without .git never resolves to the
    collection repository above it.
    """
    source = os.environ if environ is None else environ
    env = {k: v for k, v in source.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_TERMINAL_PROMPT="0",
        GCM_INTERACTIVE="Never",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_OPTIONAL_LOCKS="0",
        GIT_LFS_SKIP_SMUDGE="1",
        LC_ALL="C",
    )
    if clone is not None:
        env.update(GIT_DIR=str(Path(clone) / ".git"), GIT_WORK_TREE=str(clone))
    return env


def strip_userinfo(text: str) -> str:
    """Remove user:password@ from every http(s) address in text."""
    return _USERINFO_RE.sub(r"\1", text)


def _execute(
    net: NetGit,
    argv: list[str],
    env: dict[str, str],
    *,
    cancel=None,
    timeout: float,
    on_line: Callable[[str], None] | None = None,
    capture_stdout: bool = False,
) -> NetRun | Issue:
    """Run one git command to its end; stop, timeout and start failures come back as Issues, any exit code as a NetRun."""
    stop = cancel.is_set if cancel is not None else None
    try:
        if net.starter is not None:
            outcome = net.starter(
                argv, env=env, stop=stop, timeout=timeout, on_line=on_line, capture_stdout=capture_stdout
            )
        else:
            outcome = procs.start_process(argv, env=env, capture_stdout=capture_stdout).run(
                stop=stop, timeout=timeout, on_line=on_line
            )
    except OSError:
        return Issue(Severity.ERROR, "git.not_started", "Git could not be started.")
    if outcome.cancelled:
        return Issue(Severity.INFO, "git.cancelled", "Stopped.")
    if outcome.timed_out or outcome.returncode is None:
        return Issue(Severity.ERROR, "git.timeout", "GitHub took too long to answer. Try again later.")
    return NetRun(outcome.returncode, outcome.stdout, outcome.lines)


def clone_shallow(
    net: NetGit,
    url: str,
    branch: str,
    dest: Path,
    *,
    progress: Callable[[str, int | None], None] | None = None,
    cancel=None,
) -> NetRun | Issue:
    """Download one branch of url, depth 1, into dest (which must not exist); progress gets (line, percent or None)."""
    argv = _argv(
        net,
        "clone",
        [
            "--depth", "1", "--single-branch", f"--branch={branch}", "--no-tags", "--template=", "--progress",
            "--config=core.autocrlf=false", "--config=core.longpaths=true", "--config=core.symlinks=false",
            "--", url, str(dest),
        ],
    )  # fmt: skip

    def on_line(line: str) -> None:
        if progress is not None:
            progress(strip_userinfo(line), None)

    run = _execute(net, argv, _env(), cancel=cancel, timeout=CLONE_TIMEOUT, on_line=on_line)
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        last = strip_userinfo(run.lines[-1]) if run.lines else "git gave no reason"
        return Issue(Severity.ERROR, "git.clone_failed", f"The download failed: {last}")
    return run


def head_commit(net: NetGit, clone: Path) -> str | Issue:
    """The 40-hex commit the clone has checked out."""
    argv = _argv(net, "rev-parse", ["--verify", "HEAD^{commit}"], clone=clone)
    run = _execute(net, argv, _env(clone), timeout=LOCAL_TIMEOUT, capture_stdout=True)
    if isinstance(run, Issue):
        return run
    sha = run.stdout.decode("utf-8", errors="replace").strip()
    if run.returncode != 0 or not _SHA_RE.fullmatch(sha):
        return Issue(Severity.ERROR, "git.no_commit", "The download holds no commit.")
    return sha
