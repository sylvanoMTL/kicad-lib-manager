"""Licence labels of the library catalog (Phase 17 plan 04). Stub: replaced by the implementation."""

from enum import Enum


class LicenceClass(Enum):
    OPEN = "open"
    SHARE_ALIKE = "share-alike"
    PROPRIETARY = "proprietary"
    NOT_STATED = "not stated"
    OTHER = "other"
    UNKNOWN = "unknown"


def licence_label(spdx: str | None, *, proprietary: bool = False, known: bool = True) -> str:
    return ""


def licence_class(spdx: str | None, *, proprietary: bool = False, known: bool = True) -> LicenceClass:
    return LicenceClass.UNKNOWN


def needs_tick(cls: LicenceClass) -> bool:
    return False
