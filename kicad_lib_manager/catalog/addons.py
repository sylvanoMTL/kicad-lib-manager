"""KiCad's official add-on list as catalog listings (Phase 17; D-33, D-36, CAT-01, CAT-09, CAT-11).

read_index asks https://repository.kicad.org/repository.json for the address and SHA-256 of the packages
file, reads that file (or reuses the copy kept beside settings.ini when its SHA-256 is the published one)
and turns its library packages into Listing values. Never raises. Imports models, fsutil and catalog.urls
only; Qt-free. The package zip a version names (download_url) is never requested: the catalog downloads the
git repository named in the package's links instead.
"""

import hashlib
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import fsutil
from ..models import Issue, Severity
from . import urls

REPOSITORY_URL = "https://repository.kicad.org/repository.json"
MAX_REPOSITORY_BYTES = 64 * 1024
MAX_PACKAGES_BYTES = 8 * 1024 * 1024
MAX_LISTINGS = 500
TIMEOUT = 10.0
_USER_AGENT = "kicad-lib-manager"


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


def _listing(package: dict) -> Listing | None:
    if not isinstance(package.get("identifier"), str) or not isinstance(package.get("name"), str):
        return None
    resources = package.get("resources")
    link = None
    if isinstance(resources, dict):
        for value in resources.values():
            if isinstance(value, str):
                ref = urls.parse_github_url(value)
                if not isinstance(ref, Issue):
                    link = ref
                    break
    versions = package.get("versions")
    size = versions[0].get("install_size") if isinstance(versions, list) and versions else None
    install_mb = -(-size // 1_000_000) if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None
    return Listing(
        identifier=package["identifier"],
        name=package["name"],
        description=package.get("description", ""),
        licence=package.get("license"),
        url=link.https_url if link is not None else "",
        page=f"https://github.com/{link.owner}/{link.repo}" if link is not None else "",
        install_mb=install_mb,
        addable=link is not None,
        reason="",
    )


def parse_packages(data: bytes) -> tuple[Listing, ...] | Issue:
    """The library packages of KiCad's packages file as listings sorted by name, or an addons.unreadable Issue."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        return _unreadable("KiCad's add-on list could not be read: the answer was not in a form this app understands.")
    packages = document.get("packages") if isinstance(document, dict) else None
    if not isinstance(packages, list):
        return _unreadable("KiCad's add-on list could not be read: the answer was not in a form this app understands.")
    found = []
    for package in packages:
        if isinstance(package, dict) and package.get("type") == "library":
            listing = _listing(package)
            if listing is not None:
                found.append(listing)
    return tuple(sorted(found, key=lambda x: x.name.casefold()))


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
