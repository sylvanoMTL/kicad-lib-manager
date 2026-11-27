"""The curated libraries of the catalog (Phase 17 plan 04). Stub: replaced by the implementation."""

from dataclasses import dataclass, field

from .licences import LicenceClass, licence_class


@dataclass(frozen=True)
class CuratedEntry:
    id: str
    name: str
    description: str
    url: str
    branch: str
    licence_spdx: str | None
    proprietary: bool
    size_mb: int
    install_mb: int
    vars: dict = field(default_factory=dict)
    symbol_libs: int = 0
    footprint_libs: int = 0
    legacy_prefix: str | None = None

    @property
    def licence(self) -> LicenceClass:
        return licence_class(self.licence_spdx, proprietary=self.proprietary)


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    url: str
    branch: str
    licence_spdx: str | None
    size_mb: int
    vars: dict = field(default_factory=dict)
    research: str = ""


CURATED: tuple[CuratedEntry, ...] = ()
CANDIDATES: tuple[Candidate, ...] = ()
REJECTED: tuple[tuple[str, str], ...] = ()


def curated_by_id(id: str) -> CuratedEntry | None:
    return None
