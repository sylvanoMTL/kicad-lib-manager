"""Address, id and branch rules of the library catalog (Phase 17; CAT-03, D-01, D-23).

Every address, folder name and branch that later reaches git or the file system passes one of the
functions here first. Only https://github.com/<owner>/<repo> addresses are accepted (a file:// address
only when a test asks for it), so no other scheme, host, port, user name or query can reach git. Names
compare case-insensitively because GitHub names and Windows folders ignore case; the folder keeps GitHub's
spelling. Imports models only. Qt-free.
"""

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from ..models import Issue, Severity

GITHUB_HOST = "github.com"
BAD_URL_TEXT = (
    "Only web addresses that start with https://github.com/ can be added. Paste the address of the repository page."
)
MAX_ID = 63
MAX_BRANCH = 128

_OWNER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
_REPO_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,%d}" % (MAX_ID - 1))
_BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,%d}" % (MAX_BRANCH - 1))
_DRIVE_RE = re.compile(r"/[A-Za-z]:")
# Windows device names: a folder called CON, or CON.anything, cannot be made
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"} | {f"COM{n}" for n in range(1, 10)} | {f"LPT{n}" for n in range(1, 10)})
# names the collection already uses as folders next to a catalog id; an id of the same name would be confusing
_TAKEN_IDS = frozenset({".staging", "custom", "thirdparty"})


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    https_url: str
    default_id: str


def _bad() -> Issue:
    # the typed address is never echoed: it may carry a password
    return Issue(Severity.ERROR, "catalog.bad_url", BAD_URL_TEXT)


def default_id(owner: str, repo: str) -> str:
    """The folder name offered for a repository: <owner>-<repo> as GitHub spells it, a trailing dot dropped."""
    return f"{owner}-{repo}"[:MAX_ID].rstrip(".")


def valid_id(text: str) -> bool:
    """True when text can be the name of a ThirdParty/<id> folder on every platform."""
    if not isinstance(text, str) or _ID_RE.fullmatch(text) is None:
        return False
    if text.endswith((".", " ")) or not text.strip("."):
        return False
    if text.casefold() in _TAKEN_IDS or text.split(".", 1)[0].upper() in _RESERVED:
        return False
    return True


def valid_branch(text: str) -> bool:
    """True when text is a branch name that git cannot read as an option or a refspec."""
    if not isinstance(text, str) or _BRANCH_RE.fullmatch(text) is None:
        return False
    if ".." in text or "//" in text or text.endswith(("/", ".")):
        return False
    return not any(part.startswith(".") or part.endswith(".lock") for part in text.split("/"))


def _file_path(url: str) -> str | None:
    """The folder path of a file:// address, or None when it has none."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "file" or parts.query or parts.fragment or not parts.path:
        return None
    path = unquote(parts.path)
    if _DRIVE_RE.match(path):  # file:///C:/x -> C:/x
        path = path[1:]
    return path.rstrip("/") or None


def _github_ref(text: str) -> RepoRef | None:
    if any(ord(ch) <= 32 or ord(ch) == 127 for ch in text) or any(ch in text for ch in "?#;\\"):
        return None
    try:
        parts = urlsplit(text)
    except ValueError:  # for example an unclosed [ in the host
        return None
    if parts.scheme != "https" or parts.netloc.casefold() != GITHUB_HOST or parts.query or parts.fragment:
        return None
    segments = parts.path.strip("/").split("/")
    if len(segments) < 2 or "" in segments:
        return None
    if len(segments) > 2 and (segments[2] not in ("tree", "blob") or len(segments) < 4):
        return None
    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    if _OWNER_RE.fullmatch(owner) is None or _REPO_RE.fullmatch(repo) is None or not repo.strip("."):
        return None
    return RepoRef(owner, repo, f"https://{GITHUB_HOST}/{owner}/{repo}.git", default_id(owner, repo))


def parse_github_url(text: str, *, allow_file: bool = False) -> RepoRef | Issue:
    """The repository an address names, or an Issue catalog.bad_url (D-23).

    A trailing .git, a trailing slash and a /tree/... or /blob/... tail are accepted and dropped. allow_file
    lets a file:// address through for tests that use a local repository; production never sets it.
    """
    if not isinstance(text, str):
        return _bad()
    text = text.strip()
    if allow_file and text.casefold().startswith("file:"):
        path = _file_path(text)
        if path is None:
            return _bad()
        name = path.rsplit("/", 1)[-1]
        name = name[: -len(".git")] if name.endswith(".git") else name
        if not name or not valid_id(name):
            return _bad()
        return RepoRef("", name, text, name)
    ref = _github_ref(text)
    return ref if ref is not None else _bad()


def repo_key(url: str) -> str:
    """A casefolded key that is equal for every spelling of one repository: owner/repo, or the file path.

    A text that is no address gives its stripped casefold, so two odd texts still compare.
    """
    text = url.strip() if isinstance(url, str) else ""
    ref = _github_ref(text)
    if ref is not None:
        return f"{ref.owner}/{ref.repo}".casefold()
    path = _file_path(text) if text.casefold().startswith("file:") else None
    return (path or text).casefold()
