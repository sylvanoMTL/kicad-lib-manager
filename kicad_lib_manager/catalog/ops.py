from dataclasses import dataclass
from pathlib import Path

from ..models import Issue, Severity

STAGING_DIR = ".staging"


@dataclass(frozen=True)
class AddSource:
    id: str
    name: str
    url: str
    branch: str
    vars: dict
    licence_spdx: str | None


@dataclass(frozen=True)
class Staged:
    source: AddSource
    folder: Path
    commit: str


def stage_add(root, source, net, *, progress=None, cancel=None):
    return Issue(Severity.ERROR, "catalog.not_implemented", "not implemented")


def register_add(root, staged, *, acknowledged=False, acknowledged_on=""):
    return [Issue(Severity.ERROR, "catalog.not_implemented", "not implemented")]
