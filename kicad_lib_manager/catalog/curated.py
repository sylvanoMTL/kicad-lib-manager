"""The libraries the app itself offers in the catalog (Phase 17; CAT-09, CAT-10, D-22, D-28, D-33).

D-22 sets the rule: a library is CURATED only after the owner-run verification passed, and a failure is
recorded in REJECTED with its reason (a rejected library stays installable by its web address). WurthElektronik
and SparkFun are required by CAT-09 and are CURATED. Plans 17-17 and 17-18 applied the results of the owner-run
verification of 2026-11-27 and D-33 (KiCad's add-on list is in the catalog; KiCad's review counts as the D-22
check for what it lists), so the list is now:

- SparkFun passed (30 symbol and 21 footprint libraries, 6 3D models not found, as expected) and stays CURATED.
- 4ms passed by web address (25 / 29 libraries, no 3D model missing, 266 on KiCad's own path variables, 325 MB
  on disk, links PCM_Espressif, upstream). KiCad's add-on list holds it, so it is not curated: it comes from
  that list.
- Alternate-KiCad-Library worked (39 / 63 libraries; about 6,900 footprints with 3D models on a fixed KiCad 5.99
  folder). KiCad's add-on list holds it with its licence CC-BY-SA, so it is not curated: it comes from that
  list.
- Espressif failed and is REJECTED: its 3D models point into the add-on folder of KiCad's Plugin and Content
  Manager, which the catalog never sets, and it is not in KiCad's add-on list.

CANDIDATES is empty; the Candidate type stays for the tests and for a later verification round. A candidate is
never shown in the catalog list, never found by curated_by_id and never counted as curated.

Values were measured on 2026-11-27 (plan 17 research): the size is GitHub's packed size of the repository,
the install size is the disk the finished clone uses (the working tree plus history, rounded up with a margin:
SparkFun 302 MB measured, the Wurth checked-out tree alone 9.6 GB), the library counts come from a scan of
the clone, and the variables are the ones the libraries' own 3D model paths use. SparkFun's licence is the
one its README states ("released under the Creative Commons Attribution 4.0 International license"); GitHub
reports none. Wurth's terms are proprietary and are not in GitHub's licence field. legacy_prefix is the
folder the Wurth library used to sit in, so a later conversion can find the old table entries (D-28).
licence_url is the page that holds the licence terms (checked on GitHub on 2026-11-27, 17-17 check); it is empty
when there is none, and the licence page then links to the repository page instead.

A curated variable never names a KiCad or Plugin and Content Manager variable (CAT-10); the manifest rules
refuse those. Imports models and licences only. Qt-free.
"""

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
    vars: dict[str, str] = field(default_factory=dict)
    symbol_libs: int = 0
    footprint_libs: int = 0
    legacy_prefix: str | None = None
    licence_url: str = ""  # the page that holds the licence terms; "" opens the repository page instead

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
    vars: dict[str, str] = field(default_factory=dict)
    research: str = ""
    licence_url: str = ""  # the page that holds the licence terms; "" opens the repository page instead


CURATED: tuple[CuratedEntry, ...] = (
    CuratedEntry(
        id="WurthElektronik",
        name="Würth Elektronik",
        description="Symbols, footprints and 3D models for Würth Elektronik parts.",
        url="https://github.com/WurthElektronik/KiCad-Library.git",
        branch="master",
        licence_spdx=None,
        proprietary=True,
        size_mb=2674,  # 2,738,361 KB from the GitHub API
        install_mb=12000,
        vars={"WE_3DMODEL_DIR": "3dmodels"},
        symbol_libs=402,
        footprint_libs=43,
        legacy_prefix="WurthElektronik/KiCad-Library/",
        licence_url="https://github.com/WurthElektronik/KiCad-Library/blob/master/License_Terms_WE_KiCad_library.pdf",
    ),
    CuratedEntry(
        id="SparkFun",
        name="SparkFun",
        description="Symbols, footprints and 3D models for SparkFun parts and boards.",
        url="https://github.com/sparkfun/SparkFun-KiCad-Libraries.git",
        branch="main",
        licence_spdx="CC-BY-4.0",
        proprietary=False,
        size_mb=69,
        install_mb=310,
        vars={"SPARKFUN_KICAD_LIBRARY": ""},
        symbol_libs=30,
        footprint_libs=21,
        licence_url="https://github.com/sparkfun/SparkFun-KiCad-Libraries#license",
    ),
)

# Empty since plan 17-18: 4ms and Alternate-KiCad-Library come from KiCad's add-on list (D-33), Espressif is REJECTED
CANDIDATES: tuple[Candidate, ...] = ()

# (web address, plain reason): a library that failed the owner-run verification; it stays installable by its address
REJECTED: tuple[tuple[str, str], ...] = (
    (
        "https://github.com/espressif/kicad-libraries.git",
        "Its 3D models point into the add-on folder of KiCad's Plugin and Content Manager "
        "(KICAD8_3RD_PARTY and KICAD9_3RD_PARTY), which the catalog never sets, so its models show only when "
        "KiCad's manager has installed it too, and it is not in KiCad's add-on list. You can still add it by "
        "its web address.",
    ),
)


def curated_by_id(id: str) -> CuratedEntry | None:
    """The curated entry with this id, compared case-insensitively; a candidate is never found."""
    key = id.casefold() if isinstance(id, str) else ""
    return next((entry for entry in CURATED if entry.id.casefold() == key), None)
