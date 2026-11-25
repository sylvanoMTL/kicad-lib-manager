"""Qt-free helpers that build a library collection skeleton in a tmp folder (Phase 15).

Imported as `from collectionfixtures import make_collection`, like the other fixture modules.
"""

import subprocess
from pathlib import Path

from kicad_lib_manager.gitops import GitContext


def make_collection(root: Path, *, symbols: bool = True, footprints: bool = True) -> Path:
    """Create root/Custom/Symbols and root/Custom/Footprints/Atomic_Footprints.pretty; no git, no files."""
    root = Path(root)
    (root / "Custom").mkdir(parents=True, exist_ok=True)
    if symbols:
        (root / "Custom" / "Symbols").mkdir(exist_ok=True)
    if footprints:
        (root / "Custom" / "Footprints" / "Atomic_Footprints.pretty").mkdir(parents=True, exist_ok=True)
    return root


def recording_git(answers: dict[str, tuple[int, str]]):
    """A GitContext whose runner never starts a process, and the list of argv lists it was called with.

    answers maps the git subcommand (argv[6]: exe, pathspec flag, -c, option, -C, folder, subcommand) to
    (exit code, stdout); a subcommand that is not listed answers (0, "").
    """
    calls: list[list[str]] = []

    def runner(argv, **kwargs):
        calls.append(list(argv))
        code, out = answers.get(argv[6] if len(argv) > 6 else argv[0], (0, ""))
        return subprocess.CompletedProcess(argv, code, stdout=out.encode("utf-8"), stderr=b"")

    return GitContext(Path("git"), runner), calls
