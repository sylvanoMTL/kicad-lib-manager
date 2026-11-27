from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..models import Issue, Severity


@dataclass(frozen=True)
class NetGit:
    exe: Path
    allow_file: bool = False
    starter: Callable | None = None


@dataclass(frozen=True)
class NetRun:
    returncode: int
    stdout: bytes
    lines: tuple[str, ...]


def _argv(net, sub, args, *, clone=None):
    raise ValueError("not implemented")


def clone_shallow(net, url, branch, dest, *, progress=None, cancel=None):
    return Issue(Severity.ERROR, "catalog.not_implemented", "not implemented")
