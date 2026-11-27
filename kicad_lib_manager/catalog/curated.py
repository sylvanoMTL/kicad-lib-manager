"""The libraries the app itself offers in the catalog (Phase 17; CAT-09, CAT-10, D-22, D-28).

D-22 sets the rule. WurthElektronik and SparkFun are required by CAT-09 and are CURATED. 4ms,
Alternate-KiCad-Library and Espressif are only CANDIDATES: a candidate is never shown in the catalog list,
never found by curated_by_id and never counted as curated. It becomes curated only after the owner-run
verification of plan 17-17 passed, and plan 17-18 applies the result: a pass moves the candidate to CURATED,
a failure moves it to REJECTED with its reason (REJECTED starts empty). A rejected library stays installable
by its web address.

Values were measured on 2026-11-27 (plan 17 research): the size is GitHub's packed size of the repository,
the install size is the disk the finished clone uses (the working tree plus history, rounded up with a margin:
SparkFun 302 MB measured, the Wurth checked-out tree alone 9.6 GB), the library counts come from a scan of
the clone, and the variables are the ones the libraries' own 3D model paths use. SparkFun's licence is the
one its README states ("released under the Creative Commons Attribution 4.0 International license"); GitHub
reports none. Wurth's terms are proprietary and are not in GitHub's licence field. legacy_prefix is the
folder the Wurth library used to sit in, so a later conversion can find the old table entries (D-28).
licence_url is the page that holds the licence terms (checked on GitHub on 2026-11-27, 17-17 check); it is empty
when there is none (Espressif), and the licence page then links to the repository page instead.

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

CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        id="4ms",
        name="4ms",
        url="https://github.com/4ms/4ms-kicad-lib.git",
        branch="master",
        licence_spdx="Unlicense",
        size_mb=58,
        vars={"KICAD_4MS_LIBS": ""},
        research="Passed the research clone: 25 symbol and 29 footprint libraries, no 3D model missing.",
        licence_url="https://github.com/4ms/4ms-kicad-lib/blob/master/UNLICENSE",
    ),
    Candidate(
        id="Alternate-KiCad-Library",
        name="Alternate KiCad Library",
        url="https://github.com/DawidCislo/Alternate-KiCad-Library.git",
        branch="main",
        licence_spdx=None,
        size_mb=181,
        research=(
            "Not downloaded yet: it is larger than the research limit. It has no 3D models of its own and "
            "about 11,000 footprints, so the first scan is long. GitHub states no licence for it."
        ),
        licence_url="https://github.com/DawidCislo/Alternate-KiCad-Library#readme",
    ),
    Candidate(
        id="Espressif",
        name="Espressif",
        url="https://github.com/espressif/kicad-libraries.git",
        branch="main",
        licence_spdx=None,
        size_mb=72,
        research=(
            "Its 3D models use KiCad Plugin and Content Manager path variables (KICAD8_3RD_PARTY), which the "
            "catalog never sets; expected to fail the verification."
        ),
    ),
)

# (web address, plain reason): filled by plan 17-18 from the owner-run verification
REJECTED: tuple[tuple[str, str], ...] = ()


def curated_by_id(id: str) -> CuratedEntry | None:
    """The curated entry with this id, compared case-insensitively; a candidate is never found."""
    key = id.casefold() if isinstance(id, str) else ""
    return next((entry for entry in CURATED if entry.id.casefold() == key), None)
