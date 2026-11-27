"""Helpers for the library catalog tests (Phase 17; plain helper module, not collected).

make_upstream builds a bare git repository with git plumbing only (no work tree), so a test can
clone it through a file:// address. It starts git, so a test that calls it must be marked slow.
make_third_party writes an installed library without git, for quick tests.
"""

import os
import subprocess
from pathlib import Path

import gitfixtures

SYMBOL_TEXT = """(kicad_symbol_lib
  (version 20231120)
  (generator "kicad_symbol_editor")
  (generator_version "8.0")
  (symbol "R_Demo"
    (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "Value" "R_Demo" (at 0 -2 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Demo:R_0603" (at 0 -4 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "R_Demo_1_1"
      (pin passive line (at 0 3.81 270) (length 1.27)
        (name "~" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27)))))
      (pin passive line (at 0 -3.81 90) (length 1.27)
        (name "~" (effects (font (size 1.27 1.27))))
        (number "2" (effects (font (size 1.27 1.27)))))
    )
  )
)
"""

FOOTPRINT_TEXT = """(footprint "R_0603"
  (version 20240108)
  (generator "pcbnew")
  (layer "F.Cu")
  (pad "1" smd rect (at -0.8 0) (size 0.8 0.9) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "2" smd rect (at 0.8 0) (size 0.8 0.9) (layers "F.Cu" "F.Paste" "F.Mask"))
)
"""

# A minimal library repository: one symbol library and one footprint library, no 3D model
LIB_FILES = {
    "symbols/Demo.kicad_sym": SYMBOL_TEXT,
    "footprints/Demo.pretty/R_0603.kicad_mod": FOOTPRINT_TEXT,
}

_IDENTITY = {
    "GIT_AUTHOR_NAME": "Upstream",
    "GIT_AUTHOR_EMAIL": "upstream@example.invalid",
    "GIT_COMMITTER_NAME": "Upstream",
    "GIT_COMMITTER_EMAIL": "upstream@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def _env(bare: Path, index: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(_IDENTITY)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_DIR=str(bare), GIT_INDEX_FILE=str(index))
    return env


def _git(env: dict[str, str], *args: str, input: bytes | None = None) -> str:
    run = subprocess.run([gitfixtures.GIT, *args], env=env, input=input, capture_output=True, timeout=120)
    if run.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed ({run.returncode}): {run.stderr.decode('utf-8', 'replace')}")
    return run.stdout.decode("utf-8", errors="replace").strip()


def _commit_tree(bare: Path, files: dict[str, str], branch: str, *, parent: str | None) -> str:
    index = bare.parent / f"{bare.name}.index"
    if index.exists():
        index.unlink()
    env = _env(bare, index)
    for path, text in files.items():
        sha = _git(env, "hash-object", "-w", "--stdin", input=text.encode("utf-8"))
        _git(env, "update-index", "--add", "--cacheinfo", f"100644,{sha},{path}")
    tree = _git(env, "write-tree")
    args = ["commit-tree", tree, "-m", "upstream"]
    if parent:
        args += ["-p", parent]
    commit = _git(env, *args)
    _git(env, "update-ref", f"refs/heads/{branch}", commit)
    index.unlink(missing_ok=True)
    return commit


def make_upstream(base: Path, files: dict[str, str], *, branch: str = "main") -> tuple[Path, str]:
    """Build a bare repository under base holding exactly files on branch; return (bare folder, commit sha)."""
    gitfixtures._require_slow()
    base = Path(base).resolve()
    base.mkdir(parents=True, exist_ok=True)
    bare = base / "upstream.git"
    env = _env(bare, base / "upstream.git.index")
    env.pop("GIT_DIR")
    _git(env, "init", "--bare", "-q", "-b", branch, str(bare))
    return bare, _commit_tree(bare, files, branch, parent=None)


def advance_upstream(bare: Path, files: dict[str, str], *, orphan: bool = False, branch: str = "main") -> str:
    """Replace the tree of branch with files in a new commit (a root commit when orphan, a force-push shape); return its sha."""
    gitfixtures._require_slow()
    env = _env(bare, bare.parent / f"{bare.name}.index")
    parent = None if orphan else _git(env, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    return _commit_tree(bare, files, branch, parent=parent)


def upstream_url(bare: Path) -> str:
    """The file:// address of a bare repository."""
    return Path(bare).resolve().as_uri()


def make_third_party(root: Path, id: str, files: dict[str, str]) -> Path:
    """Write root/ThirdParty/<id>/ with files and an empty .git folder, no git; for quick tests."""
    folder = Path(root) / "ThirdParty" / id
    for rel, text in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (folder / ".git").mkdir(parents=True, exist_ok=True)
    return folder


def fake_net(
    files=LIB_FILES,
    *,
    sha: str = "a" * 40,
    status: str = "",
    clone_error: str | None = None,
    symref: tuple[str, str] = ("main", "b" * 40),
    fetch_sha: str | None = None,
    tree: list[str] | None = None,
    blobs: dict[str, bytes] | None = None,
    ls_remote: str | None = None,
):
    """A NetGit whose starter starts no process; return (net, calls) where calls lists every argv.

    The starter reads the subcommand from argv (after the -c pairs and -C) and answers from the keywords:
    clone writes files (path -> text) and an empty .git folder into the destination and prints two progress
    lines (and ends as cancelled when stop() is true after a line, leaving the partial folder, like a killed
    git; clone_error makes it fail with that stderr line and writes nothing), rev-parse gives sha (fetch_sha
    for FETCH_HEAD), status gives the porcelain entries of status (one path per line, with the two status
    letters), ls-remote gives symref (branch, commit) for --symref and ls_remote (default sha) for a branch,
    fetch succeeds, ls-tree lists tree (default: the keys of files), diff-tree is empty and cat-file gives
    blobs[path] or fails.
    """
    from kicad_lib_manager.catalog.gitnet import NetGit
    from kicad_lib_manager.procs import StreamOutcome

    calls: list[list[str]] = []
    listed = list(files) if tree is None else list(tree)

    def ok(stdout: bytes = b"") -> StreamOutcome:
        return StreamOutcome(0, stdout, (), False, False)

    def starter(argv, *, env=None, stop=None, timeout=None, on_line=None, capture_stdout=False):
        calls.append(list(argv))
        at = 2
        while at < len(argv) and argv[at] in ("-c", "-C"):
            at += 2
        sub, args = argv[at], list(argv[at + 1 :])
        if sub == "clone":
            if clone_error is not None:
                return StreamOutcome(128, b"", (clone_error,), False, False)
            dest = Path(args[-1])
            (dest / ".git").mkdir(parents=True)
            lines = ["Receiving objects:  50% (1/2)", "Receiving objects: 100% (2/2)"]
            for line in lines:
                if on_line is not None:
                    on_line(line)
                if stop is not None and stop():
                    return StreamOutcome(None, b"", tuple(lines), True, False)
            for rel, text in files.items():
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="\n")
            return StreamOutcome(0, b"", tuple(lines), False, False)
        if sub == "rev-parse":
            wanted = fetch_sha or sha if any(a.startswith("FETCH_HEAD") for a in args) else sha
            return ok(f"{wanted}\n".encode())
        if sub == "status":
            entries = [line for line in status.splitlines() if line]
            return ok(("\0".join(entries) + "\0").encode() if entries else b"")
        if sub == "ls-remote":
            if "--symref" in args:
                return ok(f"ref: refs/heads/{symref[0]}\tHEAD\n{symref[1]}\tHEAD\n".encode())
            ref = args[-1]
            return ok(f"{ls_remote or sha}\t{ref}\n".encode())
        if sub == "ls-tree":
            return ok(("\0".join(listed) + "\0").encode() if listed else b"")
        if sub == "cat-file":
            key = args[-1].partition(":")[2]
            if blobs is not None and key in blobs:
                return ok(blobs[key])
            return StreamOutcome(128, b"", ("fatal: path does not exist",), False, False)
        return ok()  # fetch, diff-tree, reset

    return NetGit(exe=Path("git-under-test"), starter=starter), calls
