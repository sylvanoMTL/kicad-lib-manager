"""The one name of a library in the catalog (Phase 17 plan 21; CAT-01).

A curated library keeps its friendly name ("SparkFun"), a library added by web address is "{owner}/{repo}"
("4ms/4ms-kicad-lib", never its folder name "4ms-4ms-kicad-lib"), and a folder the record does not list keeps its
folder name. The list, the Details heading, every catalog page and every line the catalog writes take the name
from here. Qt-free.
"""

from collections.abc import Collection

from ..models import Issue
from . import urls
from .curated import CURATED, CuratedEntry
from .manifest import CatalogEntry, Manifest


def display_name(
    id: str,
    entry: CatalogEntry | None = None,
    *,
    url: str | None = None,
    curated: Collection[CuratedEntry] = CURATED,
) -> str:
    """The name to show for a library id: the name recorded when it was added, else the curated name (letter case of
    the id ignored), else owner/repo, else the id.

    The recorded name keeps one name for the library in the window, the trees and the log, also offline (D-33).
    owner/repo comes from the web address of the catalog entry, or from url when a repository is only checked and
    has no entry yet. An address that is not a GitHub repository (a file:// address of a test) and an id with
    nothing known about it give the id.
    """
    if entry is not None and entry.name:
        return entry.name
    key = id.casefold()
    for known in curated:
        if known.id.casefold() == key:
            return known.name
    address = url if url is not None else (entry.url if entry is not None else "")
    if address:
        ref = urls.parse_github_url(address, allow_file=True)
        if not isinstance(ref, Issue) and ref.owner:
            return f"{ref.owner}/{ref.repo}"
    return id


def source_names(mf: Manifest, *, curated: Collection[CuratedEntry] = CURATED) -> dict[str, str]:
    """Every curated id and every listed entry id mapped to its display name."""
    mapping = {known.id: known.name for known in curated}
    for entry in mf.libraries:
        mapping[entry.id] = display_name(entry.id, entry, curated=curated)
    return mapping
