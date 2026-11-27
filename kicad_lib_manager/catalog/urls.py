"""Address, id and branch rules of the library catalog (Phase 17 plan 04). Stub: replaced by the implementation."""

from dataclasses import dataclass

from ..models import Issue, Severity

GITHUB_HOST = "github.com"


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    https_url: str
    default_id: str


def parse_github_url(text: str, *, allow_file: bool = False) -> RepoRef | Issue:
    return Issue(Severity.ERROR, "catalog.bad_url", "")


def default_id(owner: str, repo: str) -> str:
    return ""


def valid_id(text: str) -> bool:
    return False


def valid_branch(text: str) -> bool:
    return False


def repo_key(url: str) -> str:
    return ""
