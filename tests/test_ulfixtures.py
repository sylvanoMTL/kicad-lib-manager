"""Self-tests of the synthetic Ultra Librarian sample builder (SPLIT-04, D-15).

tests/ulfixtures.py writes an Ultra-Librarian-shaped zip from scratch, so the public suite does
not need the licence-restricted TI download. These tests pin the facts the other test modules
rely on: member order and names, CRLF ASCII bodies, byte-for-byte determinism, the content
addressed build under the system temp folder, and what the Ultra Librarian adapter and the
footprint facts make of the sample.
"""

import hashlib
import re
import sys
import tempfile
import zipfile

import pytest
from ulfixtures import (
    UL_DATE_TIME,
    UL_FOOTPRINT_MEMBER,
    UL_MEMBER_NAMES,
    UL_MODEL_MEMBER,
    UL_SYMBOL_MEMBER,
    UL_ZIP_NAME,
    ul_footprint,
    ul_members,
    ul_model,
    ul_sample_zip,
    ul_symbol,
    ul_zip_bytes,
)
from zipfixtures import REPO_ROOT, UL_ZIP

from kicad_lib_manager.importer import footprint_text as ft
from kicad_lib_manager.importer.detect import detect_candidate
from kicad_lib_manager.importer.package import open_package
from kicad_lib_manager.kicad_files import LoadedFile, footprint_name, parse_bytes

EXPECTED_MEMBERS = [
    "DLV0006A.stp",
    "ImportGuides.html",
    "readme.txt",
    "KiCADv6/2026-10-18_09-12-49.kicad_sym",
    "KiCADv6/ImportGuide.html",
    "KiCADv6/footprints.pretty/DQK0006B.kicad_mod",
]
UL_TEXTS = ["Texas WSON-6 DQK, 2x2mm, 0.65mm pitch"]


def _members() -> dict[str, bytes]:
    return {info.filename: data for info, data in ul_members()}


def test_member_order_and_names():
    with zipfile.ZipFile(ul_sample_zip()) as zf:
        assert [i.filename for i in zf.infolist()] == EXPECTED_MEMBERS
    assert list(UL_MEMBER_NAMES) == EXPECTED_MEMBERS
    assert (UL_SYMBOL_MEMBER, UL_FOOTPRINT_MEMBER, UL_MODEL_MEMBER) == (
        EXPECTED_MEMBERS[3],
        EXPECTED_MEMBERS[5],
        EXPECTED_MEMBERS[0],
    )


def test_members_are_crlf_ascii_without_bom():
    members = _members()
    assert list(members) == EXPECTED_MEMBERS
    for name, data in members.items():
        assert data, name
        text = data.decode("ascii")  # raises on a non-ASCII byte
        assert not data.startswith(b"\xef\xbb\xbf"), name
        assert "\n" in text, name
        assert text.count("\n") == text.count("\r\n"), f"{name} has a bare LF"


def test_two_builds_are_identical():
    assert ul_zip_bytes() == ul_zip_bytes()
    with zipfile.ZipFile(ul_sample_zip()) as zf:
        for info in zf.infolist():
            assert info.date_time == UL_DATE_TIME, info.filename
            assert info.compress_type == zipfile.ZIP_DEFLATED, info.filename


def test_sample_zip_is_content_addressed():
    path = ul_sample_zip()
    assert path.name == UL_ZIP_NAME == "ul_CSD85301Q2.zip"
    assert path.parent.name == hashlib.sha256(ul_zip_bytes()).hexdigest()[:12]
    assert path.read_bytes() == ul_zip_bytes()
    before = path.stat().st_mtime_ns
    assert ul_sample_zip() == path
    assert path.stat().st_mtime_ns == before


@pytest.mark.skipif(sys.platform != "win32", reason="held-open handles block os.replace only on win32")
def test_sample_zip_build_survives_a_held_open_target(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    target = ul_sample_zip()
    assert target.is_relative_to(tmp_path)
    with open(target, "rb"):
        again = ul_sample_zip()
        assert again == target
    assert target.read_bytes() == ul_zip_bytes()
    assert not list(target.parent.glob("*.tmp-*"))


def test_zipfixtures_points_at_the_sample():
    assert UL_ZIP == ul_sample_zip()
    assert "downloaded_examples" not in UL_ZIP.parts


def test_adapter_claims_the_sample():
    with open_package(UL_ZIP, REPO_ROOT) as package:
        candidate, _ = detect_candidate(package)
        assert candidate is not None
        assert candidate.vendor == "UltraLibrarian"
        assert candidate.confidence == 1.0
        assert [s.name for s in candidate.symbols] == ["CSD85301Q2"]
        assert [f.name for f in candidate.footprints] == ["DQK0006B"]
        assert [m.filename for m in candidate.models] == ["DLV0006A.stp"]
        assert candidate.footprints[0].model_paths == ()


def test_symbol_shape():
    text = ul_symbol().decode("ascii").replace("\r\n", "\n")
    assert text.split("\n")[0] == "(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)"
    assert re.findall(r'^  \(symbol "([^"]+)"', text, re.M) == ["CSD85301Q2"]
    assert re.findall(r'^    \(symbol "([^"]+)"', text, re.M) == ["CSD85301Q2_1_1", "CSD85301Q2_2_1"]
    props = re.findall(r'\(property "([^"]+)" "([^"]*)" \(id (\d+)\)', text)
    assert [(k, v) for k, v, _ in props] == [
        ("Reference", "U"),
        ("Value", "CSD85301Q2"),
        ("Footprint", "DQK0006B"),
        ("Datasheet", "https://www.ti.com/lit/gpn/csd85301q2"),
        ("ki_keywords", "CSD85301Q2"),
        ("ki_locked", ""),
        ("ki_fp_filters", "DQK0006B"),
    ]
    assert [int(i) for _, _, i in props] == list(range(7))
    pins = re.findall(r'\(pin unspecified line [^\n]*\n\s+\(name "([^"]+)"', text)
    assert pins == ["S1", "G1", "D1", "D1", "D2", "S2", "G2", "D2"]
    assert len(re.findall(r"\(pin ", text)) == 8


def test_footprint_shape():
    data = ul_footprint()
    text = data.decode("ascii")
    assert "(model" not in text
    assert text.startswith('(footprint "DQK0006B" (version 20211014) (generator pcbnew)')
    loaded = parse_bytes(data, "fixture")
    assert isinstance(loaded, LoadedFile), loaded
    facts = ft.footprint_facts(footprint_name(loaded.root).node, code="DQK0006B", maker="TI", texts=UL_TEXTS)
    assert facts.pads == 8
    assert facts.pitch == 0.65
    assert facts.body == (2.1, 2.1)
    assert facts.family == "WSON-6"


def test_model_starts_with_step_magic():
    assert ul_model().startswith(b"ISO-10303-21;\r\n")
