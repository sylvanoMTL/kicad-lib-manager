"""Self-checks for the synthetic vendor fixtures and the D-01 originality guard.

The vendor downloads are licence-restricted and both GitHub repos are public, so the committed
builders in vendorfixtures and ulfixtures must be written from scratch. These tests prove the
builders parse, carry each vendor's markers, stay tiny and reproducible, and share no bytes or
three-line windows with the owner's real downloads, and that the synthetic Ultra Librarian sample
keeps the real one's structure. The real zips live in the downloaded_examples/ folder of the
library collection named by KICAD_TEST_CORPUS (the tests that need them carry the corpus mark and
are deselected without it); they are only read member by member in memory, never extracted,
copied or printed.
"""

import hashlib
import importlib.util
import io
import re
import sys
import time
import types
import zipfile
from pathlib import Path

import pytest
import zipfixtures as zf
from corpusfixtures import corpus_path
from ulfixtures import UL_MEMBER_NAMES, ul_members, ul_sample_zip
from vendorfixtures import (
    SAMACSYS_LICENSE,
    SAMACSYS_PART,
    SAMACSYS_PART_INFO,
    samacsys_footprint,
    samacsys_members,
    samacsys_symbol,
    snapeda_footprint,
    snapeda_members,
    snapeda_model_members,
    snapeda_symbol,
)

from kicad_lib_manager.importer.adapters.samacsys import parse_part_info
from kicad_lib_manager.importer.detect import detect_candidate
from kicad_lib_manager.importer.package import open_package
from kicad_lib_manager.kicad_files import file_kind, find_property, find_symbols, list_properties, parse_bytes
from kicad_lib_manager.models import Issue

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_SCRIPT = REPO_ROOT / "scripts" / "prepublish_scan.py"
SAMPLES = corpus_path("downloaded_examples")
REAL_ZIPS = {
    "snapeda": SAMPLES / "USB4145-03-0170-C_REVA2.zip",
    "samacsys": SAMPLES / "LIB_RS3-1212S_H3.zip",
    "snapeda_model": SAMPLES / "194150990-659-usb4145-03-0170-c.zip",
    "ul": SAMPLES / "ul_CSD85301Q2.zip",
}
REAL_PART_NAMES = (b"USB4145-03-0170-C", b"usb4145-03-0170-c", b"RS3-1212S")
MAX_MEMBER_BYTES = 4096


def _all_members():
    """Every member of the builders: the model-carrying SnapEDA variant, SamacSys, the SnapEDA model download and the UL sample."""
    ul = [(info.filename, data) for info, data in ul_members()]
    return [*snapeda_members(with_model=True), *samacsys_members(), *snapeda_model_members(), *ul]


def _parsed(name, data):
    loaded = parse_bytes(data, name)
    assert not isinstance(loaded, Issue), (name, loaded)
    return loaded


def test_fixture_members_parse():
    for name, data in _all_members():
        lower = name.lower()
        if lower.endswith(".kicad_sym"):
            loaded = _parsed(name, data)
            assert file_kind(loaded.root) == "kicad_symbol_lib", name
            assert len(find_symbols(loaded.root)) == 1, name
        elif lower.endswith(".kicad_mod"):
            loaded = _parsed(name, data)
            expected = "module" if name.startswith(f"{SAMACSYS_PART}/") else "footprint"
            assert file_kind(loaded.root) == expected, name
        elif lower.endswith((".step", ".stp")):
            assert data.startswith(b"ISO-10303-21;"), name


def test_fixture_markers_present():
    symbol = snapeda_symbol()
    assert b"\r" not in symbol
    assert symbol.startswith(b"\n(kicad_symbol_lib")
    loaded = _parsed("snapeda.kicad_sym", symbol)
    node = find_symbols(loaded.root)[0].node
    assert find_property(node, "SnapEDA_Link") is not None
    assert find_property(node, "SNAPEDA_PN") is not None
    assert find_property(node, "Datasheet") is None
    assert b"\r" not in snapeda_footprint()

    sam_symbol = samacsys_symbol()
    assert sam_symbol.count(b"\r\n") == sam_symbol.count(b"\n")
    assert b"(generator SamacSys_ECAD_Model)" in sam_symbol
    footprint = samacsys_footprint()
    assert footprint.startswith(b'(module "PSU7"')
    assert f"(model {SAMACSYS_PART}.stp ".encode() in footprint
    assert b"SamacSys" in SAMACSYS_LICENSE
    info = parse_part_info(SAMACSYS_PART_INFO.decode())
    assert {"manufacturer", "partnumber", "partcategory"} <= set(info)


def test_fixture_members_small():
    for name, data in _all_members():
        assert len(data) < MAX_MEMBER_BYTES, (name, len(data))


def test_fixtures_are_deterministic(monkeypatch):
    assert snapeda_members(with_model=True) == snapeda_members(with_model=True)
    assert samacsys_members() == samacsys_members()
    assert snapeda_symbol() == snapeda_symbol()
    assert samacsys_symbol() == samacsys_symbol()

    # zipfile stamps each member with the wall clock; freeze it to compare whole archives byte for byte
    frozen = types.SimpleNamespace(**{k: getattr(time, k) for k in dir(time) if not k.startswith("__")})
    frozen.time = lambda: 1_700_000_000.0
    monkeypatch.setattr(zipfile, "time", frozen)
    for members in (snapeda_members(with_model=True), samacsys_members()):
        assert zf.zip_bytes(members) == zf.zip_bytes(members)
        with zipfile.ZipFile(io.BytesIO(zf.zip_bytes(members))) as archive:
            assert [(i.filename, archive.read(i)) for i in archive.infolist()] == members


def _real_member_hashes(path):
    """SHA-256 of every file member of a real zip, read in memory one by one (never extracted)."""
    hashes = set()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                hashes.add(hashlib.sha256(archive.read(info)).hexdigest())
    return hashes


@pytest.mark.corpus
@pytest.mark.parametrize("vendor", ["snapeda", "samacsys", "snapeda_model", "ul"])
def test_fixture_originality(vendor):
    real = REAL_ZIPS[vendor]
    real_hashes = _real_member_hashes(real)  # a missing download inside an open corpus is an error, not a skip
    assert real_hashes
    for name, data in _all_members():
        assert hashlib.sha256(data).hexdigest() not in real_hashes, f"{name} is a byte copy of a real {vendor} member"
        if vendor == "ul":
            continue  # CSD85301Q2, DQK0006B and DLV0006A are public part numbers the UL builder may carry (D-10)
        for part_name in REAL_PART_NAMES:
            assert part_name not in data, f"{name} contains the real part name {part_name!r}"


def _load_scan_script():
    """Load scripts/prepublish_scan.py by path: a `scripts` package on sys.path could be shadowed by an installed one."""
    spec = importlib.util.spec_from_file_location("prepublish_scan", SCAN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("prepublish_scan", module)
    spec.loader.exec_module(module)
    return module


def _real_text_windows(path):
    """Three-line windows of every member of a real zip, read in memory (the text stays inside the set)."""
    scan = _load_scan_script()
    found = set()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                found |= scan.windows(archive.read(info).decode("utf-8", errors="replace"))
    return found


@pytest.mark.corpus
@pytest.mark.parametrize("vendor", ["snapeda", "samacsys", "snapeda_model", "ul"])
def test_builders_share_no_three_line_window(vendor):
    """No builder member holds three consecutive lines of 25+ characters that a real member of this download holds."""
    scan = _load_scan_script()
    real_windows = _real_text_windows(REAL_ZIPS[vendor])
    shared = [name for name, data in _all_members() if scan.windows(data.decode("utf-8", errors="replace")) & real_windows]
    assert not shared, f"builder members share three consecutive lines with a real {vendor} member: {shared}"


def _same(label, real, synthetic):
    """Fail naming only what differs, never printing the real values."""
    if real != synthetic:
        pytest.fail(f"{label} of the synthetic UL sample differs from the real one")


def _ul_facts(zip_path):
    """Everything the structure comparison looks at in one UL zip, read in memory (the real zip is never extracted)."""
    with zipfile.ZipFile(zip_path) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        bodies = {i.filename: archive.read(i) for i in infos}
    names = [i.filename for i in infos]
    symbol_text = next(b for n, b in bodies.items() if n.endswith(".kicad_sym")).decode("utf-8")
    footprint_text = next(b for n, b in bodies.items() if n.endswith(".kicad_mod")).decode("utf-8")
    loaded = parse_bytes(symbol_text.encode("utf-8"), "ul.kicad_sym")
    assert not isinstance(loaded, Issue), loaded
    symbols = find_symbols(loaded.root)
    with open_package(zip_path, REPO_ROOT) as package:
        candidate, _ = detect_candidate(package)
    assert candidate is not None
    return {
        "member names and order": names,
        "adapter vendor": candidate.vendor,
        "adapter confidence": candidate.confidence,
        "adapter symbol names": [s.name for s in candidate.symbols],
        "adapter footprint names": [f.name for f in candidate.footprints],
        "adapter model names": [m.filename for m in candidate.models],
        "symbol names": [s.name for s in symbols],
        "symbol property names": [p.name for p in list_properties(symbols[0].node)],
        "pin names": re.findall(r'\(name "([^"]*)"', symbol_text),
        "pad count": len(re.findall(r'\(pad "', footprint_text)),
        "line endings": {n: b.count(b"\n") == b.count(b"\r\n") for n, b in bodies.items()},
    }


@pytest.mark.corpus
def test_ul_builder_matches_the_real_sample_structure():
    """The synthetic UL zip has the real one's members, adapter result, property and pin names, pad count and CRLF."""
    real = _ul_facts(REAL_ZIPS["ul"])
    synthetic = _ul_facts(ul_sample_zip())
    assert real["member names and order"] and tuple(synthetic["member names and order"]) == UL_MEMBER_NAMES
    for label, value in real.items():
        if label == "line endings":
            continue
        _same(label, value, synthetic[label])
    # every member of both zips is CRLF only (the real one has no bare LF; the builder must not either)
    assert all(real["line endings"].values()), "a member of the real UL sample has a bare LF: the builder rule needs a look"
    assert all(synthetic["line endings"].values()), "a member of the synthetic UL sample has a bare LF"
