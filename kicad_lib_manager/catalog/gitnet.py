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
LS_REMOTE_TIMEOUT = 20.0
FETCH_TIMEOUT = 3600.0

# GIT_CONFIG_GLOBAL, which keeps the user's own git settings out of every call, arrived in Git 2.32.0
# (Documentation/RelNotes/2.32.0.adoc: "introduce GIT_CONFIG_GLOBAL to override the global configuration
# file"); an older git ignores it, so the catalog refuses network actions below it (D-29, RESEARCH A2).
MIN_NET_GIT = (2, 32)
# CVE-2025-48384 is fixed in 2.49.1 (and 2.50.1 on the next line); an older git only gets a warning (D-11).
MIN_NET_GIT_WARN = (2, 49, 1)

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_USERINFO_RE = re.compile(r"(https?://)[^/@\s]+@")
# a branch name that cannot be read as an option or as a refspec (no colon, no leading dash or dot)
_BRANCH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._/-]*")
_STAGE_RE = re.compile(r"(Counting objects|Compressing objects|Receiving objects|Resolving deltas|Updating files):\s+(\d+)%")
# the share of the whole progress bar each git stage covers
_BANDS = {
    "Counting objects": (0, 5),
    "Compressing objects": (5, 10),
    "Receiving objects": (10, 70),
    "Resolving deltas": (70, 80),
    "Updating files": (80, 100),
}

# The only keys a clone's .git/config may hold: what git itself writes for a shallow clone of one branch
# (RESEARCH Pitfall 4). Compared in lower case; sections whose subsection is free (branch.<name>, gc, maintenance)
# are matched by prefix below.
_ALLOWED_CONFIG_KEYS = frozenset(
    {
        "core.repositoryformatversion",
        "core.filemode",
        "core.bare",
        "core.logallrefupdates",
        "core.symlinks",
        "core.ignorecase",
        "core.autocrlf",
        "core.longpaths",
        "core.fscache",
        "core.precomposeunicode",
        "core.protectntfs",
        "remote.origin.url",
        "remote.origin.fetch",
        "remote.origin.tagopt",
        "lfs.repositoryformatversion",  # git-lfs writes it
    }
)
_ALLOWED_BRANCH_KEYS = frozenset({"remote", "merge"})
_ALLOWED_SECTIONS = frozenset({"gc", "maintenance"})
_HEADER_RE = re.compile(r'\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\](.*)$')
_KEY_RE = re.compile(r"([A-Za-z][A-Za-z0-9-]*)\s*(?:=.*)?$")


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


def _last_line(run: NetRun) -> str:
    """The last stderr line git printed, without any user:password, or a fixed phrase when it printed none."""
    return strip_userinfo(run.lines[-1]) if run.lines else "git gave no reason"


def _bad_url(url: str) -> Issue | None:
    """An address that carries a user name or password is never passed to git (CAT-11, CAT-03)."""
    if _USERINFO_RE.match(url):
        return Issue(Severity.ERROR, "git.bad_url", "The address must not contain a user name or a password.")
    return None


def _check_branch(branch: str) -> None:
    """Raise ValueError for a branch name git could read as an option or a refspec; branch is a positional argument."""
    if not _BRANCH_RE.fullmatch(branch) or ".." in branch or branch.endswith("/"):
        raise ValueError(f"{branch!r} is not a plain branch name")


def _check_rev(rev: str) -> None:
    """Raise ValueError unless rev is a full commit id or HEAD (a rev is a positional argument, never an option)."""
    if rev != "HEAD" and not _SHA_RE.fullmatch(rev):
        raise ValueError(f"{rev!r} is not a commit id")


def _not_a_clone(clone: Path) -> Issue | None:
    """Refuse a folder without its own .git folder before any git runs, so no command climbs into the collection."""
    if not (Path(clone) / ".git").is_dir():
        return Issue(Severity.ERROR, "git.not_a_clone", f"{clone} is not a downloaded library folder.")
    return None


def _in_clone(
    net: NetGit,
    clone: Path,
    sub: str,
    args,
    *,
    timeout: float = LOCAL_TIMEOUT,
    capture_stdout: bool = True,
    cancel=None,
    on_line: Callable[[str], None] | None = None,
) -> NetRun | Issue:
    """One git call inside an installed clone: the .git pre-check, then GIT_DIR / GIT_WORK_TREE name the clone."""
    refusal = _not_a_clone(clone)
    if refusal is not None:
        return refusal
    argv = _argv(net, sub, args, clone=Path(clone))
    return _execute(
        net, argv, _env(Path(clone)), cancel=cancel, timeout=timeout, on_line=on_line, capture_stdout=capture_stdout
    )


def _percent_lines(progress: Callable[[str, int | None], None] | None) -> Callable[[str], None]:
    def on_line(line: str) -> None:
        if progress is not None:
            progress(strip_userinfo(line), percent(line))

    return on_line


@dataclass(frozen=True)
class RemoteHead:
    """The commit a remote branch points at, as ls-remote reports it."""

    sha: str


def version_issues(version: tuple[int, ...] | None) -> tuple[Issue | None, Issue | None]:
    """(refusal, warning) for the network actions of the catalog; the commit path keeps gitops.MIN_GIT_VERSION."""
    if version is None:
        return (
            Issue(
                Severity.ERROR,
                "git.not_found",
                "Git was not found. The catalog needs Git to download libraries. "
                "Install Git for Windows, then reopen the catalog.",
            ),
            None,
        )
    shown = ".".join(str(part) for part in version)
    if tuple(version) < MIN_NET_GIT:
        return (
            Issue(
                Severity.ERROR,
                "git.too_old",
                f"Your Git is version {shown}. The catalog needs Git 2.32 or newer to download libraries safely. "
                "Update Git for Windows, then try again.",
            ),
            None,
        )
    if tuple(version) < MIN_NET_GIT_WARN:
        return (
            None,
            Issue(
                Severity.WARNING,
                "git.old_version",
                f"Your Git is version {shown}. Versions before 2.49.1 have a known security flaw when they download "
                "code from the internet. The catalog still works. Update Git for Windows when you can.",
            ),
        )
    return None, None


def percent(line: str) -> int | None:
    """Where one --progress stderr line puts the whole download (0-100), or None for a line that is not progress."""
    found = _STAGE_RE.search(line)
    if found is None:
        return None
    low, high = _BANDS[found.group(1)]
    return low + (high - low) * int(found.group(2)) // 100


def parse_name_status(raw: str) -> list[tuple[str, str]]:
    """The (status letter, path) pairs of `diff-tree --name-status -z` output."""
    parts = raw.split("\0")
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2) if parts[i]]


def _unreachable() -> Issue:
    return Issue(
        Severity.ERROR,
        "git.unreachable",
        "The repository could not be reached. Check the address and your internet connection. "
        "A private repository cannot be added.",
    )


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
    refusal = _bad_url(url)
    if refusal is not None:
        return refusal
    argv = _argv(
        net,
        "clone",
        [
            "--depth", "1", "--single-branch", f"--branch={branch}", "--no-tags", "--template=", "--progress",
            "--config=core.autocrlf=false", "--config=core.longpaths=true", "--config=core.symlinks=false",
            "--", url, str(dest),
        ],
    )  # fmt: skip
    run = _execute(net, argv, _env(), cancel=cancel, timeout=CLONE_TIMEOUT, on_line=_percent_lines(progress))
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return Issue(Severity.ERROR, "git.clone_failed", f"The download failed: {_last_line(run)}")
    return run


def ls_remote(net: NetGit, url: str, branch: str, *, cancel=None) -> RemoteHead | Issue:
    """The commit a branch of url points at; asks the server only and downloads nothing (D-12, CAT-07).

    Exit code 2 means the branch does not exist, any other failure means the repository could not be reached.
    """
    _check_branch(branch)
    refusal = _bad_url(url)
    if refusal is not None:
        return refusal
    ref = f"refs/heads/{branch}"
    argv = _argv(net, "ls-remote", ["--exit-code", "--", url, ref])
    run = _execute(net, argv, _env(), cancel=cancel, timeout=LS_REMOTE_TIMEOUT, capture_stdout=True)
    if isinstance(run, Issue):
        return run
    if run.returncode == 2:
        return Issue(Severity.ERROR, "git.branch_missing", f"The branch {branch} was not found in that repository.")
    if run.returncode != 0:
        return _unreachable()
    for line in run.stdout.decode("utf-8", errors="replace").splitlines():
        sha, _, name = line.partition("\t")
        if name == ref and _SHA_RE.fullmatch(sha):
            return RemoteHead(sha)
    return _unreachable()


def default_branch(net: NetGit, url: str, *, cancel=None) -> tuple[str, str] | Issue:
    """(default branch name, its commit) of url, for adding a library by address (`ls-remote --symref`)."""
    refusal = _bad_url(url)
    if refusal is not None:
        return refusal
    argv = _argv(net, "ls-remote", ["--symref", "--", url, "HEAD"])
    run = _execute(net, argv, _env(), cancel=cancel, timeout=LS_REMOTE_TIMEOUT, capture_stdout=True)
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return _unreachable()
    branch = sha = None
    for line in run.stdout.decode("utf-8", errors="replace").splitlines():
        head, _, name = line.partition("\t")
        if name == "HEAD" and head.startswith("ref: refs/heads/"):
            branch = head[len("ref: refs/heads/") :]
        elif name == "HEAD" and _SHA_RE.fullmatch(head):
            sha = head
    if branch is None or sha is None:
        return Issue(Severity.ERROR, "git.branch_missing", "The repository has no default branch to download.")
    return branch, sha


def head_commit(net: NetGit, clone: Path) -> str | Issue:
    """The 40-hex commit the clone has checked out."""
    run = _in_clone(net, clone, "rev-parse", ["--verify", "HEAD^{commit}"])
    if isinstance(run, Issue):
        return run
    sha = run.stdout.decode("utf-8", errors="replace").strip()
    if run.returncode != 0 or not _SHA_RE.fullmatch(sha):
        return Issue(Severity.ERROR, "git.no_commit", "The download holds no commit.")
    return sha


def fetch_shallow(
    net: NetGit,
    clone: Path,
    url: str,
    branch: str,
    *,
    progress: Callable[[str, int | None], None] | None = None,
    cancel=None,
) -> str | Issue:
    """Fetch branch of url (depth 1) into clone without touching the work tree; returns the fetched commit.

    url is the manifest address, never the clone's own origin (RESEARCH Pitfall 4). The returned commit is
    the one to preview and later pass to reset_hard; FETCH_HEAD is never used again.
    """
    _check_branch(branch)
    refusal = _bad_url(url) or _not_a_clone(clone)
    if refusal is not None:
        return refusal
    args = ["--depth", "1", "--no-tags", "--no-recurse-submodules", "--progress", "--", url, branch]
    run = _in_clone(
        net, clone, "fetch", args,
        timeout=FETCH_TIMEOUT, capture_stdout=False, cancel=cancel, on_line=_percent_lines(progress),
    )  # fmt: skip
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return Issue(Severity.ERROR, "git.fetch_failed", f"The update could not be downloaded: {_last_line(run)}")
    parsed = _in_clone(net, clone, "rev-parse", ["--verify", "FETCH_HEAD^{commit}"], cancel=cancel)
    if isinstance(parsed, Issue):
        return parsed
    sha = parsed.stdout.decode("utf-8", errors="replace").strip()
    if parsed.returncode != 0 or not _SHA_RE.fullmatch(sha):
        return Issue(Severity.ERROR, "git.fetch_failed", "The update could not be downloaded: git returned no commit.")
    return sha


def reset_hard(net: NetGit, clone: Path, sha: str) -> NetRun | Issue:
    """Move the clone's work tree and branch to sha, the commit that was previewed; raises ValueError for anything else."""
    if not _SHA_RE.fullmatch(sha):
        raise ValueError(f"{sha!r} is not a full lower-case commit id")
    run = _in_clone(net, clone, "reset", ["--hard", "-q", sha], capture_stdout=False)
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return Issue(Severity.ERROR, "git.reset_failed", f"The update could not be applied: {_last_line(run)}")
    return run


def _read_failed(what: str, run: NetRun) -> Issue:
    return Issue(
        Severity.ERROR, "git.read_failed", f"Git could not read {what} of the downloaded library: {_last_line(run)}"
    )


def status_entries(net: NetGit, clone: Path) -> list[str] | Issue:
    """The path of every changed or untracked file in the clone (`status --porcelain=v1 -z`), each counted once.

    A rename or copy entry is followed by its source path in the next NUL field; that one is skipped.
    """
    run = _in_clone(net, clone, "status", ["--porcelain=v1", "-z", "--untracked-files=all"])
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return _read_failed("the changes", run)
    fields = run.stdout.decode("utf-8", errors="replace").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:  # the empty field after the last NUL
            continue
        if entry[0] in "RC" or entry[1] in "RC":
            index += 1
        paths.append(entry[3:])
    return paths


def changed_paths(net: NetGit, clone: Path, sha: str) -> list[tuple[str, str]] | Issue:
    """(status letter, path) of every file that differs between the clone's HEAD and sha (plumbing diff-tree, no textconv)."""
    if not _SHA_RE.fullmatch(sha):
        raise ValueError(f"{sha!r} is not a full lower-case commit id")
    run = _in_clone(
        net, clone, "diff-tree", ["-r", "--no-renames", "--name-status", "-z", "--no-commit-id", "HEAD", sha]
    )
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return _read_failed("the differences", run)
    return parse_name_status(run.stdout.decode("utf-8", errors="replace"))


def tree_paths(net: NetGit, clone: Path, rev: str) -> list[str] | Issue:
    """Every file path in the tree of rev (a commit id or HEAD)."""
    _check_rev(rev)
    run = _in_clone(net, clone, "ls-tree", ["-r", "--name-only", "-z", rev])
    if isinstance(run, Issue):
        return run
    if run.returncode != 0:
        return _read_failed("the file list", run)
    return [path for path in run.stdout.decode("utf-8", errors="replace").split("\0") if path]


def read_blob(net: NetGit, clone: Path, rev: str, path: str) -> bytes | None:
    """The content of path at rev, or None when there is no such file (or git could not answer)."""
    _check_rev(rev)
    run = _in_clone(net, clone, "cat-file", ["blob", f"{rev}:{path}"])
    if isinstance(run, Issue) or run.returncode != 0:
        return None
    return run.stdout


def _config_key_problem(section: str, subsection: str | None, key: str) -> bool:
    """True when this setting is not one git writes itself for a clone made by the catalog."""
    section_l, key_l = section.lower(), key.lower()
    if section_l in _ALLOWED_SECTIONS:
        return False
    if section_l == "branch" and subsection is not None:
        return key_l not in _ALLOWED_BRANCH_KEYS
    name = f"{section_l}.{subsection}.{key_l}" if subsection is not None else f"{section_l}.{key_l}"
    return name not in _ALLOWED_CONFIG_KEYS


def config_problems(clone: Path) -> list[str]:
    """Every setting of the clone's .git/config outside the allow-list, read as text without running git.

    A file git itself wrote holds none of them; a restored or hand-edited one may name programs git would run
    (core.fsmonitor, core.sshCommand, aliases, credential helpers, includes). A line this reader does not
    understand counts as a problem too, so the list is empty only for a config that is fully understood.
    """
    folder = Path(clone) / ".git"
    if not folder.is_dir():
        return ["no .git folder"]
    try:
        text = (folder / "config").read_bytes().decode("utf-8-sig", errors="replace")
    except FileNotFoundError:
        return ["no .git/config"]
    except OSError:
        return ["unreadable .git/config"]
    problems: list[str] = []
    section: str | None = None
    subsection: str | None = None
    continued = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        was_continued, continued = continued, raw.rstrip().endswith("\\")
        if was_continued or not line or line[0] in "#;":
            continue
        rest = line
        header = _HEADER_RE.match(line)
        if header is not None:
            section, subsection, rest = header.group(1), header.group(2), header.group(3).strip()
            if subsection is None and "." in section:  # the old [section.subsection] spelling
                section, _, subsection = section.partition(".")
                subsection = subsection.lower()
            continued = False
            if not rest or rest[0] in "#;":
                continue
            continued = rest.rstrip().endswith("\\")
        found = _KEY_RE.match(rest) if section is not None else None
        if found is None:
            problems.append(f"unreadable line {number}")
            continue
        key = found.group(1)
        if _config_key_problem(section, subsection, key):
            problems.append(f"{section.lower()}.{subsection}.{key}" if subsection is not None else f"{section.lower()}.{key}")
    return problems
