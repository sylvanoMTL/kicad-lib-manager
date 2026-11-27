"""The one GitHub lookup of Add by URL (Phase 17; D-04, D-23, CAT-03, CAT-11).

repo_info asks api.github.com for the size, default branch and licence of a public repository before
anything is downloaded. The request carries no token, password, cookie or personal detail (a generic
User-Agent only), redirects stay inside https://api.github.com/, and the answer is untrusted: a body over
256 KB is refused and every field is type-checked. A repository GitHub does not show without sign-in
(not found or private) is api.not_found; anything else that goes wrong (offline, slow, rate limit, odd
answer) is api.unknown, which never blocks an Add (the staging check still runs). Never raises.
Imports models only; Qt-free.
"""

import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from ..models import Issue, Severity

API_HOST = "api.github.com"
MAX_API_BYTES = 256 * 1024
API_TIMEOUT = 10.0
_API_PREFIX = f"https://{API_HOST}/"
_USER_AGENT = "kicad-lib-manager"
_OWNER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
_REPO_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")

NOT_FOUND_TEXT = "GitHub could not find this repository, or it is private. The catalog only adds public repositories."
SLOW_TEXT = "GitHub took too long to answer. Try again later."
OFFLINE_TEXT = "GitHub could not be reached. Check your internet connection, then try again."
ODD_TEXT = "GitHub gave an answer this app could not use."


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    size_kb: int  # GitHub's packed size of the repository, not the disk a clone uses
    default_branch: str
    spdx: str | None  # GitHub's licence id; "NOASSERTION" stays as it is, no licence gives None
    private: bool
    archived: bool


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when it stays inside https://api.github.com/ (a renamed repository redirects there)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not isinstance(newurl, str) or not newurl.startswith(_API_PREFIX):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> urllib.request.OpenerDirector:
    """An opener with no proxy-auth, cookie or credential handler of its own and the redirect rule above."""
    return urllib.request.build_opener(_SameHostRedirect())


def _default_opener(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    """(status, body capped at MAX_API_BYTES + 1) of one request; an HTTP error status is an answer, not a raise."""
    try:
        with _build_opener().open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_API_BYTES + 1)
    except urllib.error.HTTPError as e:
        return e.code, b""


def _unknown(text: str) -> Issue:
    return Issue(Severity.ERROR, "api.unknown", text)


def _not_found() -> Issue:
    return Issue(Severity.ERROR, "api.not_found", NOT_FOUND_TEXT)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse(body: bytes) -> RepoInfo | Issue:
    if len(body) > MAX_API_BYTES:
        return _unknown(ODD_TEXT)
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, RecursionError):
        return _unknown(ODD_TEXT)
    if not isinstance(data, dict):
        return _unknown(ODD_TEXT)
    full_name, size, branch = data.get("full_name"), data.get("size"), data.get("default_branch")
    private, archived, licence = data.get("private", False), data.get("archived", False), data.get("license")
    if not isinstance(full_name, str) or not _is_int(size) or size < 0 or not isinstance(branch, str):
        return _unknown(ODD_TEXT)
    if not isinstance(private, bool) or not isinstance(archived, bool):
        return _unknown(ODD_TEXT)
    spdx = None
    if licence is not None:
        spdx = licence.get("spdx_id") if isinstance(licence, dict) else 0
        if spdx is not None and not isinstance(spdx, str):
            return _unknown(ODD_TEXT)
    if private:
        return _not_found()
    return RepoInfo(full_name, size, branch, spdx, private, archived)


def repo_info(
    owner: str,
    repo: str,
    *,
    opener: Callable[[urllib.request.Request, float], tuple[int, bytes]] | None = None,
    timeout: float = API_TIMEOUT,
) -> RepoInfo | Issue:
    """What GitHub says about owner/repo: RepoInfo, api.not_found (missing or private) or api.unknown (never raises).

    owner and repo come from urls.parse_github_url; they are checked again here, so nothing else can reach the
    request address. opener(request, timeout) returns (status, body) or raises; the default one uses urllib.
    """
    if not isinstance(owner, str) or not isinstance(repo, str):
        return _unknown(ODD_TEXT)
    if _OWNER_RE.fullmatch(owner) is None or _REPO_RE.fullmatch(repo) is None or not repo.strip("."):
        return _unknown(ODD_TEXT)
    request = urllib.request.Request(
        f"{_API_PREFIX}repos/{owner}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": _USER_AGENT,
        },
        method="GET",
    )
    try:
        status, body = (opener or _default_opener)(request, timeout)
    except (TimeoutError, socket.timeout):
        return _unknown(SLOW_TEXT)
    except urllib.error.URLError as e:
        return _unknown(SLOW_TEXT if isinstance(e.reason, (TimeoutError, socket.timeout)) else OFFLINE_TEXT)
    except (OSError, ValueError):
        return _unknown(OFFLINE_TEXT)
    if status == 404:
        return _not_found()
    if status != 200:
        return _unknown(ODD_TEXT)
    return _parse(body)
