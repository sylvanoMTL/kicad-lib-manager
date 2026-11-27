"""The one GitHub lookup of Add by URL (Phase 17, D-04, D-23). Stub: filled in by the GREEN commit."""

from dataclasses import dataclass

from ..models import Issue, Severity

API_HOST = "api.github.com"
MAX_API_BYTES = 256 * 1024
API_TIMEOUT = 10.0


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    size_kb: int
    default_branch: str
    spdx: str | None
    private: bool
    archived: bool


def repo_info(owner, repo, *, opener=None, timeout=API_TIMEOUT):
    return Issue(Severity.ERROR, "api.unknown", "not implemented")
