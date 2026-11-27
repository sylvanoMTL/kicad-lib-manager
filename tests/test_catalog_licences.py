"""Licence labels and the acknowledgement rule of the catalog (Phase 17 plan 04; D-10, UI-SPEC "Licence labels")."""

import pytest

from kicad_lib_manager.catalog.licences import LicenceClass, licence_class, licence_label, needs_tick

OPEN = LicenceClass.OPEN
SHARE = LicenceClass.SHARE_ALIKE


@pytest.mark.parametrize(
    "spdx, label, cls",
    [
        ("MIT", "MIT", OPEN),
        ("BSD-2-Clause", "BSD", OPEN),
        ("BSD-3-Clause", "BSD", OPEN),
        ("Apache-2.0", "Apache 2.0", OPEN),
        ("ISC", "ISC", OPEN),
        ("Unlicense", "Unlicense", OPEN),
        ("CC0-1.0", "CC0 1.0", OPEN),
        ("CC-BY-3.0", "CC BY 3.0", OPEN),
        ("CC-BY-4.0", "CC BY 4.0", OPEN),
        ("CC-BY-SA-3.0", "CC BY-SA 3.0", SHARE),
        ("CC-BY-SA-4.0", "CC BY-SA 4.0", SHARE),
        ("GPL-2.0", "GPL 2.0", SHARE),
        ("GPL-3.0", "GPL 3.0", SHARE),
        ("GPL-3.0-only", "GPL 3.0", SHARE),
        ("GPL-3.0-or-later", "GPL 3.0", SHARE),
        ("LGPL-2.1", "LGPL 2.1", SHARE),
        ("LGPL-3.0", "LGPL 3.0", SHARE),
        ("AGPL-3.0", "AGPL 3.0", SHARE),
        ("MPL-2.0", "MPL 2.0", SHARE),
        ("EPL-1.0", "EPL 1.0", SHARE),
        ("EPL-2.0", "EPL 2.0", SHARE),
        # the versionless names KiCad's add-on list uses
        ("CC-BY-SA", "CC BY-SA", SHARE),
        ("CC-BY", "CC BY", OPEN),
    ],
)
def test_every_row_of_the_ui_spec_table(spdx, label, cls):
    assert licence_label(spdx) == label
    assert licence_class(spdx) is cls


def test_spdx_ids_compare_case_insensitively():
    assert licence_label("mit") == "MIT"
    assert licence_class("cc-by-sa-4.0") is SHARE


def test_a_proprietary_entry_is_labelled_proprietary_whatever_the_spdx_id():
    assert licence_label(None, proprietary=True) == "Proprietary"
    assert licence_label("NOASSERTION", proprietary=True) == "Proprietary"
    assert licence_label("MIT", proprietary=True) == "Proprietary"
    assert licence_class(None, proprietary=True) is LicenceClass.PROPRIETARY


@pytest.mark.parametrize("spdx", [None, "", "NOASSERTION", "other", "Other"])
def test_nothing_or_the_generic_value_is_not_stated(spdx):
    assert licence_label(spdx) == "Not stated"
    assert licence_class(spdx) is LicenceClass.NOT_STATED


@pytest.mark.parametrize("spdx", ["WTFPL", "Zlib", "Artistic-2.0"])
def test_an_id_outside_the_table_is_other(spdx):
    assert licence_label(spdx) == "Other (see the licence file)"
    assert licence_class(spdx) is LicenceClass.OTHER


def test_unreadable_github_is_unknown():
    assert licence_label(None, known=False) == "Unknown"
    assert licence_class("MIT", known=False) is LicenceClass.UNKNOWN


def test_proprietary_wins_over_unknown_because_the_curated_list_knows_it():
    assert licence_class(None, proprietary=True, known=False) is LicenceClass.PROPRIETARY


def test_only_open_licences_need_no_tick():
    assert needs_tick(OPEN) is False
    for cls in LicenceClass:
        if cls is not OPEN:
            assert needs_tick(cls) is True, cls


def test_the_class_set_is_the_documented_one():
    assert {c.name for c in LicenceClass} == {"OPEN", "SHARE_ALIKE", "PROPRIETARY", "NOT_STATED", "OTHER", "UNKNOWN"}


def test_labels_never_show_a_raw_spdx_id_for_the_table_rows():
    for spdx in ("BSD-3-Clause", "GPL-3.0-or-later", "NOASSERTION", "Apache-2.0"):
        assert licence_label(spdx) != spdx


def test_cern_ohl_from_kicads_list_stays_other():
    assert licence_label("CERN-OHL") == "Other (see the licence file)"
    assert licence_class("CERN-OHL") is LicenceClass.OTHER
    assert needs_tick(licence_class("cc-by-sa")) is True and needs_tick(licence_class("CC-BY")) is False
