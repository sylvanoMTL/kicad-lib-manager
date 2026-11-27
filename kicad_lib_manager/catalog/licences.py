"""Licence labels and the acknowledgement rule of the library catalog (Phase 17; D-10, UI-SPEC "Licence labels").

GitHub reports a licence as an SPDX id (or nothing, or the generic "other"); the screens show the display
names of the UI-SPEC table, never the id. KiCad's add-on list also names licences, some without a version
(CC-BY-SA, CC-BY). Open licences need no tick in the Add preview; share-alike, proprietary, not stated,
unrecognised and unknown ones do. Stdlib only. Qt-free.
"""

import re
from enum import Enum


class LicenceClass(Enum):
    OPEN = "open"
    SHARE_ALIKE = "share-alike"
    PROPRIETARY = "proprietary"
    NOT_STATED = "not stated"
    OTHER = "other"
    UNKNOWN = "unknown"


PROPRIETARY_LABEL = "Proprietary"
NOT_STATED_LABEL = "Not stated"
OTHER_LABEL = "Other (see the licence file)"
UNKNOWN_LABEL = "Unknown"

# open licences by casefolded SPDX id (cc-by is KiCad's versionless name)
_OPEN = {
    "mit": "MIT",
    "bsd-2-clause": "BSD",
    "bsd-3-clause": "BSD",
    "apache-2.0": "Apache 2.0",
    "isc": "ISC",
    "unlicense": "Unlicense",
    "cc0-1.0": "CC0 1.0",
    "cc-by": "CC BY",
    "cc-by-3.0": "CC BY 3.0",
    "cc-by-4.0": "CC BY 4.0",
}
# share-alike names that carry no version (as KiCad's add-on list writes them), by casefolded id
_SHARE_ALIKE_FIXED = {"cc-by-sa": "CC BY-SA"}
# share-alike families: (pattern on the casefolded id, label prefix); the version is the first group
_SHARE_ALIKE = (
    (re.compile(r"cc-by-sa-(\d\.\d)"), "CC BY-SA"),
    (re.compile(r"(a?l?gpl)-(\d(?:\.\d)?)(?:-only|-or-later|\+)?"), None),
    (re.compile(r"mpl-(\d\.\d)"), "MPL"),
    (re.compile(r"epl-(\d\.\d)"), "EPL"),
)
# what GitHub reports when it found no licence it could name
_NOT_STATED = frozenset({"", "noassertion", "other", "none"})


def _share_alike_label(key: str) -> str | None:
    if key in _SHARE_ALIKE_FIXED:
        return _SHARE_ALIKE_FIXED[key]
    for pattern, prefix in _SHARE_ALIKE:
        found = pattern.fullmatch(key)
        if found is None:
            continue
        if prefix is None:  # the GPL family keeps its own letters
            return f"{found.group(1).upper()} {found.group(2)}"
        return f"{prefix} {found.group(1)}"
    return None


def _classify(spdx: str | None, proprietary: bool, known: bool) -> tuple[LicenceClass, str]:
    if proprietary:
        return LicenceClass.PROPRIETARY, PROPRIETARY_LABEL
    if not known:
        return LicenceClass.UNKNOWN, UNKNOWN_LABEL
    key = (spdx or "").strip().casefold()
    if key in _NOT_STATED:
        return LicenceClass.NOT_STATED, NOT_STATED_LABEL
    if key in _OPEN:
        return LicenceClass.OPEN, _OPEN[key]
    label = _share_alike_label(key)
    if label is not None:
        return LicenceClass.SHARE_ALIKE, label
    return LicenceClass.OTHER, OTHER_LABEL


def licence_label(spdx: str | None, *, proprietary: bool = False, known: bool = True) -> str:
    """The display name of a licence. known=False means GitHub could not be read for an entry not on the curated list."""
    return _classify(spdx, proprietary, known)[1]


def licence_class(spdx: str | None, *, proprietary: bool = False, known: bool = True) -> LicenceClass:
    return _classify(spdx, proprietary, known)[0]


def needs_tick(cls: LicenceClass) -> bool:
    """True when the Add preview asks the user to tick that they have read the licence (D-10)."""
    return cls is not LicenceClass.OPEN
