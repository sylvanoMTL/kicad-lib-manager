"""Row statuses and the update check of the library catalog (Phase 17 plan 10; CAT-01, CAT-07, D-02, D-05, D-06, D-12, D-19, D-31, D-32).

Quick tests on synthetic collections. The update check runs through a starter that answers ls-remote per
address, so no process starts and no network is touched.
"""

import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from catalogfixtures import make_third_party
from collectionfixtures import make_collection

from kicad_lib_manager.catalog import addons, curated, licences, manifest, status
from kicad_lib_manager.catalog.gitnet import NetGit
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.library_scanner import scan_all
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.procs import StreamOutcome

SHA = "a" * 40
OTHER = "d" * 40
NOW = datetime(2026, 11, 27, 12, 0, 0)
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")
THIRD = replace(SPARKFUN, id="ThirdOne", name="Third One", url="https://github.com/x/third.git")


def _entry(id, *, url=None, branch="main", commit=SHA, spdx="MIT", vars=None):
    return CatalogEntry(
        id=id,
        url=url or f"https://github.com/acme/{id.lower()}.git",
        branch=branch,
        commit=commit,
        vars=vars or {},
        licence_spdx=spdx,
        added_on="2026-11-01",
    )


def _collection(tmp_path, *folders):
    root = make_collection(tmp_path / "col")
    for id in folders:
        make_third_party(root, id, {"a.kicad_sym": "(kicad_symbol_lib)"})
    return root


def _by_id(rows):
    return {row.id: row for row in rows}


# -- row_statuses --------------------------------------------------------------------------


def test_rows_for_every_case(tmp_path):
    root = _collection(tmp_path, "SparkFun", "demo", "Stray")  # ThirdOne has an entry but no folder
    (root / "ThirdParty" / ".staging" / "Half.ab12cd34").mkdir(parents=True)
    (root / "ThirdParty" / ".hidden").mkdir()
    spark = _entry("SparkFun", url=SPARKFUN.url, spdx="CC-BY-4.0")
    mf = Manifest((spark, _entry("demo", url="https://github.com/acme/demo-lib.git"), _entry("ThirdOne", url=THIRD.url)))

    rows = status.row_statuses(root, mf, curated=(SPARKFUN, WURTH, THIRD))
    by_id = _by_id(rows)

    assert set(by_id) == {"SparkFun", "WurthElektronik", "ThirdOne", "demo", "Stray"}  # no .staging, no dot folder
    assert by_id["WurthElektronik"].state is status.State.NOT_INSTALLED and by_id["WurthElektronik"].entry is None
    assert by_id["SparkFun"].state is status.State.INSTALLED and by_id["SparkFun"].entry == spark
    assert by_id["SparkFun"].curated is SPARKFUN and by_id["SparkFun"].name == "SparkFun"
    assert by_id["demo"].state is status.State.INSTALLED and by_id["demo"].name == "acme/demo-lib"
    assert by_id["demo"].curated is None
    assert by_id["ThirdOne"].state is status.State.FOLDER_MISSING and by_id["ThirdOne"].name == "Third One"
    assert by_id["Stray"].state is status.State.NOT_IN_CATALOG and by_id["Stray"].name == "Stray"
    assert by_id["Stray"].entry is None and by_id["Stray"].folder == root / "ThirdParty" / "Stray"


def test_unlisted_folder_of_a_curated_id_is_the_curated_row(tmp_path):
    root = _collection(tmp_path, "sparkfun")  # letter case differs, as on Windows
    rows = status.row_statuses(root, Manifest(), curated=(SPARKFUN, WURTH))
    by_id = _by_id(rows)
    assert len(rows) == 2 and by_id["SparkFun"].state is status.State.NOT_IN_CATALOG
    assert by_id["SparkFun"].folder.name == "sparkfun"


def test_licence_and_size_columns(tmp_path):
    root = _collection(tmp_path, "SparkFun", "demo")
    mf = Manifest((_entry("SparkFun", url=SPARKFUN.url, spdx="CC-BY-4.0"), _entry("demo", spdx="GPL-3.0")))
    by_id = _by_id(status.row_statuses(root, mf, curated=(SPARKFUN, WURTH)))
    assert (by_id["SparkFun"].licence_label, by_id["SparkFun"].size_mb) == ("CC BY 4.0", SPARKFUN.size_mb)
    assert by_id["SparkFun"].size_text == status.size_text(SPARKFUN.size_mb)
    assert by_id["WurthElektronik"].licence_label == "Proprietary"
    assert by_id["WurthElektronik"].licence_class is licences.LicenceClass.PROPRIETARY
    assert (by_id["demo"].licence_label, by_id["demo"].licence_class) == ("GPL 3.0", licences.LicenceClass.SHARE_ALIKE)
    assert (by_id["demo"].size_mb, by_id["demo"].size_text) == (None, "Unknown")


def test_rows_sorted_by_name_and_stable(tmp_path):
    root = _collection(tmp_path, "SparkFun", "zeta", "Alpha", "Stray")
    mf = Manifest((_entry("SparkFun", url=SPARKFUN.url), _entry("zeta"), _entry("Alpha")))
    plain = status.row_statuses(root, mf, curated=(SPARKFUN, WURTH))
    names = [row.name for row in plain]
    assert names == sorted(names, key=str.casefold)

    updates = {"zeta": status.UpdateState("zeta", status.Check.AVAILABLE, OTHER, NOW)}
    with_update = status.row_statuses(root, mf, curated=(SPARKFUN, WURTH), updates=updates)
    assert [row.id for row in with_update] == [row.id for row in plain]
    assert _by_id(with_update)["zeta"].state is status.State.UPDATE_AVAILABLE


def test_unreadable_manifest_makes_every_row_unknown(tmp_path):
    root = _collection(tmp_path, "SparkFun", "Stray")
    broken = Issue(Severity.ERROR, "catalog.unreadable", "The library list could not be read.")
    rows = status.row_statuses(root, broken, curated=(SPARKFUN, WURTH))
    assert {row.id for row in rows} == {"SparkFun", "WurthElektronik", "Stray"}
    assert {row.state for row in rows} == {status.State.UNKNOWN}


def test_empty_collection_rows(tmp_path):
    root = make_collection(tmp_path / "col")  # no catalog.json and no ThirdParty folder
    rows = status.row_statuses(root, manifest.load(root))
    assert [row.name for row in rows] == sorted((c.name for c in curated.CURATED), key=str.casefold)
    assert {row.id for row in rows} == {c.id for c in curated.CURATED}
    assert {row.state for row in rows} == {status.State.NOT_INSTALLED}

    (root / "ThirdParty").mkdir()
    again = status.row_statuses(root, manifest.load(root))
    assert {row.id for row in again} == {c.id for c in curated.CURATED}


def test_half_made_staging_folder_never_becomes_a_row(tmp_path):
    root = _collection(tmp_path, "SparkFun")
    half = root / "ThirdParty" / ".staging" / "Demo.0badc0de"
    half.mkdir(parents=True)
    (half / "partial.pack").write_text("x", encoding="utf-8")
    mf = Manifest((_entry("SparkFun", url=SPARKFUN.url),))
    ids = {row.id for row in status.row_statuses(root, mf, curated=(SPARKFUN, WURTH))}
    assert ids == {"SparkFun", "WurthElektronik"}

    # after the interruption is cleaned up the rows are rebuilt from disk and show the true state
    (half / "partial.pack").unlink()
    half.rmdir()
    again = _by_id(status.row_statuses(root, mf, curated=(SPARKFUN, WURTH)))
    assert again["SparkFun"].state is status.State.INSTALLED


@pytest.mark.parametrize(
    ("check", "remote", "expected"),
    [
        (status.Check.AVAILABLE, OTHER, status.State.UPDATE_AVAILABLE),
        (status.Check.AVAILABLE, SHA, status.State.INSTALLED),  # the remote equals the recorded commit
        (status.Check.CURRENT, SHA, status.State.INSTALLED),
        (status.Check.UNKNOWN, None, status.State.INSTALLED),
        (status.Check.BRANCH_GONE, None, status.State.INSTALLED),
        (status.Check.NOT_CHECKED, None, status.State.INSTALLED),
    ],
)
def test_update_available_only_when_remote_differs(tmp_path, check, remote, expected):
    root = _collection(tmp_path, "demo")
    mf = Manifest((_entry("demo"),))
    updates = {"demo": status.UpdateState("demo", check, remote, NOW)}
    row = _by_id(status.row_statuses(root, mf, curated=(), updates=updates))["demo"]
    assert row.state is expected and row.update == updates["demo"]


def test_update_state_of_a_missing_folder_does_not_change_it(tmp_path):
    root = _collection(tmp_path)
    mf = Manifest((_entry("demo"),))
    updates = {"demo": status.UpdateState("demo", status.Check.AVAILABLE, OTHER, NOW)}
    row = _by_id(status.row_statuses(root, mf, curated=(), updates=updates))["demo"]
    assert row.state is status.State.FOLDER_MISSING


def test_model_warnings_do_not_change_state(tmp_path):
    root = make_collection(tmp_path / "col")
    make_third_party(
        root,
        "Lib",
        {
            "a.kicad_sym": '(kicad_symbol_lib (symbol "S" (property "Reference" "U")))\n',
            "fp.pretty/A.kicad_mod": '(footprint "A"\n  (model "${LIBVAR}/missing.step")\n)\n',
        },
    )
    scan = scan_all(root, kicad_fp_dir=tmp_path / "nokicad" / "footprints", model_vars={"Lib": {"LIBVAR": ""}})
    assert any(issue.code == "scan.model_missing" for issue in scan.issues)

    rows = status.row_statuses(root, Manifest((_entry("Lib", vars={"LIBVAR": ""}),)), curated=())
    assert _by_id(rows)["Lib"].state is status.State.INSTALLED


@pytest.mark.parametrize(
    ("mb", "text"),
    [(None, "Unknown"), (0, "0 MB"), (999, "999 MB"), (1000, "1.0 GB"), (2674, "2.7 GB"), (12000, "12.0 GB")],
)
def test_size_text(mb, text):
    assert status.size_text(mb) == text


# -- check_updates -------------------------------------------------------------------------


def _remote(answers, calls=None, after_first=None):
    """A NetGit whose ls-remote answers by address: a sha, "missing", "unreachable" or "timeout"."""

    def starter(argv, *, env=None, stop=None, timeout=None, on_line=None, capture_stdout=False):
        url = argv[argv.index("--") + 1]
        if calls is not None:
            calls.append(url)
        if after_first is not None and calls is not None and len(calls) == 1:
            after_first()
        answer = answers[url]
        if answer == "missing":
            return StreamOutcome(2, b"", (), False, False)
        if answer == "unreachable":
            return StreamOutcome(128, b"", ("fatal: unable to access",), False, False)
        if answer == "timeout":
            return StreamOutcome(None, b"", (), False, True)
        ref = argv[-1]
        return StreamOutcome(0, f"{answer}\t{ref}\n".encode(), (), False, False)

    return NetGit(exe=Path("git-under-test"), starter=starter)


def _installed(tmp_path, entries):
    root = make_collection(tmp_path / "col")
    for entry in entries:
        make_third_party(root, entry.id, {"a.kicad_sym": "(kicad_symbol_lib)"})
    mf = Manifest(tuple(entries))
    assert manifest.save(root, mf) is None
    return root, mf


def _four(tmp_path):
    entries = [
        _entry("one", url="https://github.com/a/one.git"),
        _entry("two", url="https://github.com/a/two.git"),
        _entry("three", url="https://github.com/a/three.git"),
        _entry("four", url="https://github.com/a/four.git"),
    ]
    root, mf = _installed(tmp_path, entries)
    answers = {
        "https://github.com/a/one.git": SHA,
        "https://github.com/a/two.git": OTHER,
        "https://github.com/a/three.git": "missing",
        "https://github.com/a/four.git": "unreachable",
    }
    return root, mf, answers


def test_check_updates_states(tmp_path):
    root, mf, answers = _four(tmp_path)
    seen = []

    states = status.check_updates(root, mf, _remote(answers), on_one=lambda id, state: seen.append(id), now=lambda: NOW)

    assert {id: s.check for id, s in states.items()} == {
        "one": status.Check.CURRENT,
        "two": status.Check.AVAILABLE,
        "three": status.Check.BRANCH_GONE,
        "four": status.Check.UNKNOWN,
    }
    assert states["two"].remote_sha == OTHER and states["one"].remote_sha == SHA
    assert states["three"].remote_sha is None and states["four"].remote_sha is None
    assert {s.checked_at for s in states.values()} == {NOW}
    assert all(s.id == id for id, s in states.items()) and sorted(seen) == sorted(states)


def test_check_stops_after_a_timeout(tmp_path):
    root, mf, answers = _four(tmp_path)
    answers["https://github.com/a/four.git"] = "timeout"
    calls = []
    first = sorted(mf.libraries, key=lambda e: e.id.casefold())[0]
    answers[first.url] = "timeout"

    states = status.check_updates(root, mf, _remote(answers, calls), now=lambda: NOW)

    assert calls == [first.url]  # no further ls-remote runs
    assert {s.check for s in states.values()} == {status.Check.UNKNOWN} and len(states) == 4


def test_check_honours_cancel(tmp_path):
    root, mf, answers = _four(tmp_path)
    stop = threading.Event()
    stop.set()
    calls = []
    states = status.check_updates(root, mf, _remote(answers, calls), cancel=stop, now=lambda: NOW)
    assert calls == [] and {s.check for s in states.values()} == {status.Check.NOT_CHECKED}

    stop = threading.Event()
    calls = []
    states = status.check_updates(root, mf, _remote(answers, calls, after_first=stop.set), cancel=stop, now=lambda: NOW)
    assert len(calls) == 1
    checked = [s for s in states.values() if s.check is not status.Check.NOT_CHECKED]
    assert len(checked) == 1


def test_check_writes_nothing(tmp_path):
    root, mf, answers = _four(tmp_path)
    record = root / "catalog.json"
    before, mtime = record.read_bytes(), record.stat().st_mtime_ns
    tree = {p: p.stat().st_mtime_ns for p in (root / "ThirdParty").rglob("*")}

    first = status.check_updates(root, mf, _remote(answers), now=lambda: NOW)
    second = status.check_updates(root, mf, _remote(answers), now=lambda: NOW)

    assert first == second  # idempotent: two checks give the same states
    assert (record.read_bytes(), record.stat().st_mtime_ns) == (before, mtime)
    assert {p: p.stat().st_mtime_ns for p in (root / "ThirdParty").rglob("*")} == tree
    assert not (root / "ThirdParty" / ".staging").exists()


def test_check_skips_entries_without_folder(tmp_path):
    root, mf, answers = _four(tmp_path)
    (root / "ThirdParty" / "two" / "a.kicad_sym").unlink()
    (root / "ThirdParty" / "two" / ".git").rmdir()
    (root / "ThirdParty" / "two").rmdir()
    calls = []

    states = status.check_updates(root, mf, _remote(answers, calls), now=lambda: NOW)

    assert set(states) == {"one", "three", "four"}
    assert "https://github.com/a/two.git" not in calls


def test_check_uses_each_entry_branch(tmp_path):
    entry = _entry("dev", url="https://github.com/a/dev.git", branch="develop")
    root, mf = _installed(tmp_path, [entry])
    refs = []

    def starter(argv, **kwargs):
        refs.append(argv[-1])
        return StreamOutcome(0, f"{SHA}\t{argv[-1]}\n".encode(), (), False, False)

    states = status.check_updates(root, mf, NetGit(exe=Path("git-under-test"), starter=starter), now=lambda: NOW)
    assert refs == ["refs/heads/develop"] and states["dev"].check is status.Check.CURRENT


# -- the summary line ----------------------------------------------------------------------


def test_update_count(tmp_path):
    root, mf, answers = _four(tmp_path)
    states = status.check_updates(root, mf, _remote(answers), now=lambda: NOW)
    assert status.update_count(states, mf) == 1
    assert status.update_count({}, mf) == 0
    ghost = {"nope": status.UpdateState("nope", status.Check.AVAILABLE, OTHER, NOW)}
    assert status.update_count(ghost, mf) == 0  # an id that is not in the catalog is not counted


@pytest.mark.parametrize(
    ("names", "line"),
    [
        ([], None),
        (["SparkFun"], "1 catalog library has an update: SparkFun"),
        (["SparkFun", "Espressif"], "2 catalog libraries have updates: SparkFun, Espressif"),
        (["A", "B", "C", "D"], "4 catalog libraries have updates: A, B, C, D"),
        (["A", "B", "C", "D", "E"], "5 catalog libraries have updates: A, B, C, D and 1 more"),
        (["A", "B", "C", "D", "E", "F", "G"], "7 catalog libraries have updates: A, B, C, D and 3 more"),
    ],
)
def test_updates_line_forms(names, line):
    assert status.updates_line(names) == line


# -- the libraries of KiCad's add-on list (plan 17-25, D-33) -------------------------------------------

ADDON_FIXTURE = Path(__file__).parent / "fixtures" / "addons" / "packages.json"
LISTINGS = addons.parse_packages(ADDON_FIXTURE.read_bytes())
FOUR_MS_ID = "com.github.4ms.4ms-kicad-lib"
FOUR_MS_URL = "https://github.com/4ms/4ms-kicad-lib.git"


def test_listing_rows(tmp_path):
    root = _collection(tmp_path)
    rows = status.row_statuses(root, Manifest(()), curated=(SPARKFUN, WURTH), listings=LISTINGS)
    by_id = _by_id(rows)
    # SparkFun is listed once, as the curated row
    assert [row.name for row in rows].count("SparkFun KiCad Libraries") == 0
    assert by_id["SparkFun"].origin == "curated" and by_id["SparkFun"].listing is None
    assert by_id["SparkFun"].description == SPARKFUN.description
    four = by_id["4ms-4ms-kicad-lib"]
    assert four.name == "4ms Kicad Libraries" and four.origin == "addon" and four.state is status.State.NOT_INSTALLED
    assert four.licence_label == "Unlicense" and four.size_mb == 222 and four.size_text == "222 MB"
    assert four.listing is not None and four.addable and four.reason == "" and four.entry is None and four.curated is None
    alternate = by_id["DawidCislo-Alternate-KiCad-Library"]
    assert alternate.name == "Alternate Kicad Library" and alternate.licence_label == "CC BY-SA"
    assert alternate.licence_class is licences.LicenceClass.SHARE_ALIKE
    kikit = by_id["com.github.yaqwsx.kikit-library"]
    assert kikit.addable is False and kikit.reason and kikit.origin == "addon" and kikit.state is status.State.NOT_INSTALLED
    assert kikit.listing is not None and kikit.folder == root / "ThirdParty" / "com.github.yaqwsx.kikit-library"
    # a listing with no size has an unknown one
    assert by_id["circuitbreakersrobotics-CB_KiCAD_Libraries"].size_text == "Unknown"
    # every addable listing and every not addable one has a row, the plugin and the theme have none
    assert len(rows) == 2 + sum(1 for item in LISTINGS if item.identifier != "com.github.sparkfun.SparkFun-KiCad-Libraries")
    assert [row.name.casefold() for row in rows] == sorted(row.name.casefold() for row in rows)


def test_a_recorded_library_takes_its_listing(tmp_path):
    root = _collection(tmp_path, "4ms-4ms-kicad-lib", "fork")
    by_url = _entry("4ms-4ms-kicad-lib", url=FOUR_MS_URL)
    by_id = replace(_entry("fork", url="https://github.com/someone/fork.git"), addon_id=FOUR_MS_ID)
    rows = status.row_statuses(root, Manifest((by_url,)), curated=(SPARKFUN,), listings=LISTINGS)
    row = _by_id(rows)["4ms-4ms-kicad-lib"]
    four = next(item for item in LISTINGS if item.identifier == FOUR_MS_ID)
    assert row.state is status.State.INSTALLED and row.entry == by_url and row.origin == "addon"
    assert row.listing == four and row.description == four.description and row.name == "4ms Kicad Libraries"
    assert [r.id for r in rows].count("4ms-4ms-kicad-lib") == 1  # the listing is not a second row
    # matched by the add-on id when the address differs
    rows = status.row_statuses(root, Manifest((by_id,)), curated=(SPARKFUN,), listings=LISTINGS)
    row = _by_id(rows)["fork"]
    assert row.listing == four and row.origin == "addon" and row.state is status.State.INSTALLED
    assert "4ms-4ms-kicad-lib" in _by_id(rows)  # its own folder still gives the listing's row, which is not in the catalog
    # the recorded name wins over KiCad's
    named = replace(by_url, name="My 4ms")
    row = _by_id(status.row_statuses(root, Manifest((named,)), curated=(SPARKFUN,), listings=LISTINGS))["4ms-4ms-kicad-lib"]
    assert row.name == "My 4ms"


def test_listing_folder_without_an_entry_is_not_in_the_catalog(tmp_path):
    root = _collection(tmp_path, "4ms-4ms-kicad-lib", "Stray")
    rows = _by_id(status.row_statuses(root, Manifest(()), curated=(SPARKFUN,), listings=LISTINGS))
    row = rows["4ms-4ms-kicad-lib"]
    assert row.state is status.State.NOT_IN_CATALOG and row.name == "4ms Kicad Libraries" and row.listing is not None
    assert rows["Stray"].origin == "folder" and rows["Stray"].listing is None
    assert _by_id(status.row_statuses(root, Manifest(()), curated=(), listings=()))["Stray"].origin == "folder"


def test_origins_without_listings(tmp_path):
    root = _collection(tmp_path, "demo")
    rows = _by_id(status.row_statuses(root, Manifest((_entry("demo", url="https://github.com/acme/demo-lib.git"),)), curated=(SPARKFUN,)))
    assert rows["demo"].origin == "url" and rows["SparkFun"].origin == "curated"
    assert rows["demo"].description == "" and rows["demo"].addable
