"""KiCad's official add-on list as catalog listings (Phase 17; D-33, D-36, CAT-01, CAT-09, CAT-11).

read_index asks https://repository.kicad.org/repository.json for the address and SHA-256 of the packages
file, reads that file (or reuses the copy kept beside settings.ini when its SHA-256 is the published one)
and turns its library packages into Listing values. Never raises. Imports models, fsutil and catalog.urls
only; Qt-free. The package zip a version names (download_url) is never requested: the catalog downloads the
git repository named in the package's links instead.
"""

import hashlib
import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from .. import fsutil
from ..models import Issue, Severity
from . import urls

REPOSITORY_URL = "https://repository.kicad.org/repository.json"
MAX_REPOSITORY_BYTES = 64 * 1024
MAX_PACKAGES_BYTES = 8 * 1024 * 1024
MAX_LISTINGS = 500
MAX_NAME = 100
MAX_DESCRIPTION = 500
MAX_LICENCE = 64
MAX_RESOURCES = 20
MAX_LINK = 300
TIMEOUT = 10.0
_USER_AGENT = "kicad-lib-manager"
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# the order the links of a package are tried in (letter case ignored); a Website link is never taken
LINK_KEYS = ("git", "github", "gitlab", "repository", "homepage", "source")
# The library is a subfolder of a program's repository, so that repository is not a library repository.
PROGRAM_REPOSITORIES = frozenset({"com.github.yaqwsx.kikit-library", "com.github.buganini.kikakuka-footprints"})

_INSTEAD = "Install it with KiCad's Plugin and Content Manager instead."
PROGRAM_TEXT = (
    "This library is part of the repository of a program, not a library repository of its own, "
    f"so the catalog cannot add it yet. {_INSTEAD}"
)
OTHER_HOST_TEXT = "This library is kept on {host}, and the catalog only downloads from GitHub so far. " + _INSTEAD
PACKED_TEXT = (
    "This library is kept in its repository as a packed file, not as library files, "
    f"so the catalog cannot add it yet. {_INSTEAD}"
)
NO_LINK_TEXT = f"KiCad's add-on list names no repository for this library, so the catalog cannot add it. {_INSTEAD}"
ODD_TEXT = "KiCad's add-on list could not be read: the answer was not in a form this app understands."


@dataclass(frozen=True)
class Listing:
    identifier: str
    name: str
    description: str
    licence: str | None  # KiCad's licence name as it stands in the list
    url: str  # the git address the catalog downloads; '' when the listing cannot be added
    page: str  # the library's own page without .git, '' when the list gives none
    install_mb: int | None  # the newest version's size on disk in whole decimal MB
    addable: bool
    reason: str  # the plain reason a listing cannot be added yet; '' when it can


@dataclass(frozen=True)
class IndexRead:
    listings: tuple[Listing, ...]
    issue: Issue | None
    from_cache: bool
    copy_date: str  # YYYY-MM-DD the kept copy was last read, set only for an offline read of that copy


def _unreadable(text: str) -> Issue:
    return Issue(Severity.ERROR, "addons.unreadable", text)


def _clean(text: str) -> str:
    """text with every control character dropped; a tab or line break becomes a space."""
    return "".join(" " if ch in "\t\n\r" else ch for ch in text if ch in "\t\n\r" or ch.isprintable()).strip()


def _usable_link(text) -> SplitResult | None:
    """The parts of an https link that has a host and no user name, port, query or fragment, else None."""
    if not isinstance(text, str) or len(text) > MAX_LINK:
        return None
    if any(ord(ch) <= 32 or ord(ch) == 127 for ch in text) or any(ch in text for ch in "\\?#"):
        return None
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc or port is not None:
        return None
    return parts


def _find_link(resources: dict) -> tuple[urls.RepoRef | None, tuple[str, str] | None] | None:
    """The first usable link in the key order: (RepoRef, None) for a GitHub repository, (None, (host, link)) else."""
    by_key: dict[str, str] = {}
    for key, value in resources.items():
        by_key.setdefault(key.casefold(), value)
    for key in LINK_KEYS:
        parts = _usable_link(by_key.get(key))
        if parts is None:
            continue
        if parts.hostname == urls.GITHUB_HOST:
            ref = urls.parse_github_url(by_key[key])
            if isinstance(ref, Issue):  # a GitHub page that is not a repository: try the next key
                continue
            return ref, None
        return None, (parts.hostname, by_key[key])
    return None


def _packed(ref: urls.RepoRef, download) -> bool:
    """True when download names a file stored inside the same repository (compared as text, never requested)."""
    if not isinstance(download, str):
        return False
    try:
        parts = urlsplit(download)
    except ValueError:
        return False
    segments = parts.path.strip("/").split("/")
    if len(segments) < 3:
        return False
    in_repository = parts.hostname == urls.GITHUB_HOST and segments[2] == "raw"
    if not in_repository and parts.hostname != "raw.githubusercontent.com":
        return False
    return urls.repo_key(f"https://{urls.GITHUB_HOST}/{segments[0]}/{segments[1]}") == urls.repo_key(ref.https_url)


def _classify(identifier: str, resources: dict, download) -> tuple[str, str, bool, str]:
    """(url, page, addable, reason) of one library package (D-33)."""
    found = _find_link(resources)
    ref, other = found if found is not None else (None, None)
    if ref is not None:
        page = f"https://{urls.GITHUB_HOST}/{ref.owner}/{ref.repo}"
    else:
        page = other[1] if other is not None else ""
    if identifier in PROGRAM_REPOSITORIES:
        return "", page, False, PROGRAM_TEXT
    if found is None:
        return "", "", False, NO_LINK_TEXT
    if ref is None:
        return "", page, False, OTHER_HOST_TEXT.format(host=other[0])
    if _packed(ref, download):
        return "", page, False, PACKED_TEXT
    return ref.https_url, page, True, ""


def _text_field(package: dict, key: str, limit: int, *, required: bool) -> str | None:
    """The cleaned text of a field; None (the package is skipped) when it is no text, too long or, if required, empty."""
    value = package.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        return None
    text = _clean(value)
    if len(text) > limit or (required and not text):
        return None
    return text


def _listing(package: dict) -> Listing | None:
    identifier = package.get("identifier")
    if not isinstance(identifier, str) or _ID_RE.fullmatch(identifier) is None:
        return None
    name = _text_field(package, "name", MAX_NAME, required=True)
    description = _text_field(package, "description", MAX_DESCRIPTION, required=False)
    licence = _text_field(package, "license", MAX_LICENCE, required=False)
    resources = package.get("resources", {})
    versions = package.get("versions", [])
    if name is None or description is None or licence is None or not isinstance(versions, list):
        return None
    if not isinstance(resources, dict) or len(resources) > MAX_RESOURCES:
        return None
    if not all(isinstance(v, str) and len(v) <= MAX_LINK for v in resources.values()):
        return None
    newest = versions[0] if versions and isinstance(versions[0], dict) else {}
    size = newest.get("install_size")
    install_mb = -(-size // 1_000_000) if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None
    url, page, addable, reason = _classify(identifier, resources, newest.get("download_url"))
    return Listing(identifier, name, description, licence or None, url, page, install_mb, addable, reason)


def parse_packages(data: bytes) -> tuple[Listing, ...] | Issue:
    """The library packages of KiCad's packages file as listings sorted by name, or an addons.unreadable Issue.

    A package that fails a check is skipped; the list is cut at MAX_LISTINGS.
    """
    try:
        document = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        return _unreadable(ODD_TEXT)
    packages = document.get("packages") if isinstance(document, dict) else None
    if not isinstance(packages, list):
        return _unreadable(ODD_TEXT)
    found: dict[str, Listing] = {}
    for package in packages:
        if len(found) >= MAX_LISTINGS:
            break
        if isinstance(package, dict) and package.get("type") == "library":
            listing = _listing(package)
            if listing is not None:
                found.setdefault(listing.identifier, listing)
    return tuple(sorted(found.values(), key=lambda x: (x.name.casefold(), x.identifier)))


def _default_opener(request: urllib.request.Request, timeout: float, limit: int) -> tuple[int, bytes]:
    """(status, body of at most limit bytes) of one request."""
    with urllib.request.build_opener().open(request, timeout=timeout) as response:
        return response.status, response.read(limit)


def _get(opener, url: str, timeout: float, cap: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}, method="GET")
    status, body = (opener or _default_opener)(request, timeout, cap + 1)
    if status != 200 or len(body) > cap:
        raise ValueError(url)
    return body


def read_index(
    *,
    cache_file: Path | None,
    opener: Callable[[urllib.request.Request, float, int], tuple[int, bytes]] | None = None,
    timeout: float = TIMEOUT,
) -> IndexRead:
    """KiCad's library listings: the kept copy when it is the published one, else a fresh read (never raises).

    opener(request, timeout, limit) returns (status, body of at most limit bytes) or raises; the default one
    uses urllib. cache_file is the copy kept beside settings.ini (None keeps nothing).
    """
    repository = json.loads(_get(opener, REPOSITORY_URL, timeout, MAX_REPOSITORY_BYTES))["packages"]
    published = repository["sha256"]
    if cache_file is not None and cache_file.is_file():
        kept = cache_file.read_bytes()
        if hashlib.sha256(kept).hexdigest() == published:
            listings = parse_packages(kept)
            if not isinstance(listings, Issue):
                return IndexRead(listings, None, True, "")
    body = _get(opener, repository["url"], timeout, MAX_PACKAGES_BYTES)
    listings = parse_packages(body)
    if isinstance(listings, Issue):
        return IndexRead((), listings, False, "")
    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        fsutil.atomic_write_bytes(cache_file, body)
    return IndexRead(listings, None, False, "")
