"""catalog.json: the record of the third-party libraries cloned into ThirdParty/<id>/ (Phase 17, CAT-05).

One plain JSON file at the collection root, written atomically as UTF-8 with LF line endings. Reading never
raises: a missing file is an empty catalog, an unreadable one is an Issue. Full field validation comes with
the manifest checks of a later plan. Qt-free.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import fsutil
from ..models import Issue, Severity

MANIFEST_NAME = "catalog.json"
FORMAT = 1


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    url: str
    branch: str
    commit: str = ""
    vars: dict[str, str] = field(default_factory=dict)
    licence_spdx: str | None = None
    acknowledged: bool = False
    acknowledged_on: str = ""
    known_dirty: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    libraries: tuple[CatalogEntry, ...] = ()

    def find(self, id: str) -> CatalogEntry | None:
        """The entry with this id, compared case-insensitively."""
        key = id.casefold()
        return next((entry for entry in self.libraries if entry.id.casefold() == key), None)

    def with_entry(self, entry: CatalogEntry) -> "Manifest":
        """A copy with entry added, or replacing the entry of the same id."""
        key = entry.id.casefold()
        kept = tuple(e for e in self.libraries if e.id.casefold() != key)
        return Manifest((*kept, entry))


def _entry_from(raw: dict) -> CatalogEntry:
    licence = raw.get("licence") or {}
    return CatalogEntry(
        id=str(raw["id"]),
        url=str(raw["url"]),
        branch=str(raw["branch"]),
        commit=str(raw.get("commit", "")),
        vars={str(k): str(v) for k, v in (raw.get("vars") or {}).items()},
        licence_spdx=licence.get("spdx"),
        acknowledged=bool(licence.get("acknowledged", False)),
        acknowledged_on=str(licence.get("acknowledged_on", "")),
        known_dirty=tuple(str(p) for p in raw.get("known_dirty") or ()),
    )


def load(root: Path) -> Manifest | Issue:
    """Read root/catalog.json; a missing file is an empty Manifest, an unreadable one an Issue."""
    path = Path(root) / MANIFEST_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Manifest()
    except (OSError, UnicodeDecodeError) as e:
        return Issue(Severity.ERROR, "catalog.unreadable", f"The library list could not be read: {getattr(e, 'strerror', None) or e}")
    try:
        data = json.loads(text)
        return Manifest(tuple(_entry_from(raw) for raw in data["libraries"]))
    except (ValueError, KeyError, TypeError, AttributeError):
        return Issue(Severity.ERROR, "catalog.unreadable", f"The library list {MANIFEST_NAME} is not in a form this app understands.")


def _entry_to(entry: CatalogEntry) -> dict:
    return {
        "id": entry.id,
        "url": entry.url,
        "branch": entry.branch,
        "commit": entry.commit,
        "vars": dict(entry.vars),
        "licence": {
            "spdx": entry.licence_spdx,
            "acknowledged": entry.acknowledged,
            "acknowledged_on": entry.acknowledged_on,
        },
        "known_dirty": list(entry.known_dirty),
    }


def save(root: Path, manifest: Manifest) -> Issue | None:
    """Write root/catalog.json atomically (entries sorted by id); an Issue on failure."""
    entries = sorted(manifest.libraries, key=lambda e: e.id.casefold())
    data = {"format": FORMAT, "libraries": [_entry_to(e) for e in entries]}
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return fsutil.atomic_write_text(Path(root) / MANIFEST_NAME, text)
