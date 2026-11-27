"""catalog.json is untrusted input: validated on read, deterministic on write (Phase 17 plan 04; CAT-05, D-02).

Quick tests on a scratch folder; no git, no network.
"""

import json
from pathlib import Path

import pytest

from kicad_lib_manager.catalog import manifest
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.models import Issue, Severity

SHA = "1f1f7b8fdacd76f334bb0c0d83074d8ffedcc95c"
SPARKFUN_URL = "https://github.com/sparkfun/SparkFun-KiCad-Libraries.git"
WURTH_URL = "https://github.com/WurthElektronik/KiCad-Library.git"


def _entry(**changes) -> dict:
    base = {
        "id": "SparkFun",
        "url": SPARKFUN_URL,
        "branch": "main",
        "commit": SHA,
        "vars": {"SPARKFUN_KICAD_LIBRARY": ""},
        "licence": {"spdx": "CC-BY-4.0", "acknowledged": True, "acknowledged_on": "2026-11-27"},
        "added_on": "2026-11-27",
        "known_dirty": [],
    }
    base.update(changes)
    return base


def _write(root: Path, libraries: list, **top) -> Path:
    data = {"format": 1, "libraries": libraries}
    data.update(top)
    path = root / manifest.MANIFEST_NAME
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _refused(root: Path, *, code: str = "catalog.unreadable") -> Issue:
    result = manifest.load(root)
    assert isinstance(result, Issue), result
    assert result.code == code
    assert result.severity is Severity.ERROR
    return result


def test_a_missing_file_is_an_empty_catalog(tmp_path):
    result = manifest.load(tmp_path)
    assert isinstance(result, Manifest) and result.libraries == ()


def test_an_empty_list_is_valid(tmp_path):
    _write(tmp_path, [])
    result = manifest.load(tmp_path)
    assert isinstance(result, Manifest) and result.libraries == ()


def test_round_trip_keeps_every_field(tmp_path):
    first = CatalogEntry(
        id="SparkFun",
        url=SPARKFUN_URL,
        branch="main",
        commit=SHA,
        vars={"SPARKFUN_KICAD_LIBRARY": ""},
        licence_spdx="CC-BY-4.0",
        acknowledged=True,
        acknowledged_on="2026-11-27",
        added_on="2026-11-26",
        known_dirty=("symbols/x.kicad_sym",),
    )
    second = CatalogEntry(id="WurthElektronik", url=WURTH_URL, branch="master", vars={"WE_3DMODEL_DIR": "3dmodels"})
    assert manifest.save(tmp_path, Manifest((second, first))) is None
    loaded = manifest.load(tmp_path)
    assert isinstance(loaded, Manifest)
    assert loaded.find("sparkfun") == first
    assert loaded.find("WurthElektronik") == second
    assert loaded.find("WurthElektronik").licence_spdx is None
    assert loaded.find("SparkFun").acknowledged_on == "2026-11-27"
    assert loaded.find("SparkFun").added_on == "2026-11-26"


def test_save_is_sorted_by_casefold_id_and_byte_identical_twice(tmp_path):
    entries = [
        CatalogEntry(id="zeta", url="https://github.com/o/zeta.git", branch="main"),
        CatalogEntry(id="Alpha", url="https://github.com/o/alpha.git", branch="main"),
        CatalogEntry(id="beta", url="https://github.com/o/beta.git", branch="main"),
    ]
    assert manifest.save(tmp_path, Manifest(tuple(entries))) is None
    first = (tmp_path / manifest.MANIFEST_NAME).read_bytes()
    assert manifest.save(tmp_path, Manifest(tuple(reversed(entries)))) is None
    second = (tmp_path / manifest.MANIFEST_NAME).read_bytes()
    assert first == second
    ids = [e["id"] for e in json.loads(first.decode("utf-8"))["libraries"]]
    assert ids == ["Alpha", "beta", "zeta"]
    assert first.endswith(b"\n") and b"\r" not in first and not first.endswith(b"\n\n")


def test_save_writes_a_fixed_key_order(tmp_path):
    entry = CatalogEntry(id="SparkFun", url=SPARKFUN_URL, branch="main", added_on="2026-11-27")
    manifest.save(tmp_path, Manifest((entry,)))
    data = json.loads((tmp_path / manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert list(data) == ["format", "libraries"]
    assert list(data["libraries"][0]) == ["id", "url", "branch", "commit", "vars", "licence", "added_on", "known_dirty"]
    assert list(data["libraries"][0]["licence"]) == ["spdx", "acknowledged", "acknowledged_on"]


def test_save_keeps_non_ascii_text(tmp_path):
    entry = CatalogEntry(id="Wuerth", url=WURTH_URL, branch="main", known_dirty=("symbols/W\u00fcrth.kicad_sym",))
    manifest.save(tmp_path, Manifest((entry,)))
    assert "W\u00fcrth" in (tmp_path / manifest.MANIFEST_NAME).read_text(encoding="utf-8")


def test_the_folder_of_an_entry_is_derived_never_stored(tmp_path):
    entry = CatalogEntry(id="SparkFun", url=SPARKFUN_URL, branch="main")
    assert manifest.entry_folder(tmp_path, entry) == tmp_path / "ThirdParty" / "SparkFun"
    assert manifest.entry_folder(tmp_path, "SparkFun") == tmp_path / "ThirdParty" / "SparkFun"
    manifest.save(tmp_path, Manifest((entry,)))
    assert "ThirdParty" not in (tmp_path / manifest.MANIFEST_NAME).read_text(encoding="utf-8")


def test_a_file_over_one_megabyte_is_refused_before_it_is_parsed(tmp_path, monkeypatch):
    path = tmp_path / manifest.MANIFEST_NAME
    path.write_bytes(b" " * (manifest.MAX_MANIFEST_BYTES + 1))

    def boom(*_args, **_kwargs):
        raise AssertionError("json.loads must not see an oversized file")

    monkeypatch.setattr(manifest.json, "loads", boom)
    issue = _refused(tmp_path)
    assert "1 MB" in issue.text


def test_a_file_of_exactly_the_limit_is_still_read(tmp_path):
    body = json.dumps({"format": 1, "libraries": []}).encode("utf-8")
    (tmp_path / manifest.MANIFEST_NAME).write_bytes(body + b" " * (manifest.MAX_MANIFEST_BYTES - len(body)))
    assert isinstance(manifest.load(tmp_path), Manifest)


@pytest.mark.parametrize("body", [b"not json", b"[]", b"null", b"3", b'{"libraries": []}', b"\xff\xfe\x00"])
def test_unreadable_files_give_one_issue(tmp_path, body):
    (tmp_path / manifest.MANIFEST_NAME).write_bytes(body)
    _refused(tmp_path)


@pytest.mark.parametrize("fmt", ["1", 1.5, True, None, 0, -1, [1]])
def test_a_format_that_is_not_a_positive_int_is_refused(tmp_path, fmt):
    _write(tmp_path, [], format=fmt)
    assert "version" in _refused(tmp_path).text


def test_a_higher_format_is_read_only(tmp_path):
    _write(tmp_path, [_entry()], format=2)
    issue = _refused(tmp_path, code="catalog.newer_format")
    assert "newer" in issue.text and "read-only" in issue.text


def test_libraries_must_be_a_list_of_objects(tmp_path):
    _write(tmp_path, {"a": 1})
    _refused(tmp_path)
    _write(tmp_path, ["text"])
    _refused(tmp_path)


@pytest.mark.parametrize(
    "changes, words",
    [
        ({"id": ".staging"}, "library name"),
        ({"id": "CON"}, "library name"),
        ({"id": "a/b"}, "library name"),
        ({"id": ""}, "library name"),
        ({"id": 5}, "library name"),
        ({"id": None}, "library name"),
        ({"url": "http://github.com/o/r.git"}, "web address"),
        ({"url": "https://gitlab.com/o/r.git"}, "web address"),
        ({"url": "file:///tmp/x"}, "web address"),
        ({"url": 5}, "web address"),
        ({"branch": "-x"}, "branch"),
        ({"branch": "a..b"}, "branch"),
        ({"branch": ""}, "branch"),
        ({"branch": 5}, "branch"),
        ({"commit": "abc"}, "version"),
        ({"commit": SHA.upper()}, "version"),
        ({"commit": SHA + "0"}, "version"),
        ({"commit": 5}, "version"),
        ({"vars": {"kicad9_3rd_party": ""}}, "path variable"),
        ({"vars": {"KICAD9_3RD_PARTY": ""}}, "path variable"),
        ({"vars": {"KICAD_LIB_GITHUB": ""}}, "path variable"),
        ({"vars": {"OK_VAR": "../x"}}, "path variable"),
        ({"vars": {"OK_VAR": "a/../x"}}, "path variable"),
        ({"vars": {"OK_VAR": "C:/x"}}, "path variable"),
        ({"vars": {"OK_VAR": "/x"}}, "path variable"),
        ({"vars": {"OK_VAR": 5}}, "path variable"),
        ({"vars": ["OK_VAR"]}, "path variable"),
        ({"licence": "MIT"}, "licence"),
        ({"licence": {"spdx": 5, "acknowledged": False, "acknowledged_on": ""}}, "licence"),
        ({"licence": {"spdx": None, "acknowledged": "yes", "acknowledged_on": ""}}, "licence"),
        ({"licence": {"spdx": None, "acknowledged": True, "acknowledged_on": "yesterday"}}, "licence"),
        ({"added_on": "27.11.2026"}, "date"),
        ({"added_on": 5}, "date"),
        ({"known_dirty": "x"}, "changed files"),
        ({"known_dirty": [5]}, "changed files"),
        ({"known_dirty": ["../x"]}, "changed files"),
    ],
)
def test_each_invalid_field_gives_catalog_unreadable_in_plain_words(tmp_path, changes, words):
    _write(tmp_path, [_entry(**changes)])
    issue = _refused(tmp_path)
    assert words in issue.text, issue.text
    # plain words: no raw key name of the file reaches the text
    for raw in ('"url"', '"branch"', '"commit"', '"vars"', '"licence"', "added_on", "known_dirty", "acknowledged"):
        assert raw not in issue.text


def test_an_entry_missing_a_required_field_is_refused(tmp_path):
    for key in ("id", "url", "branch"):
        entry = _entry()
        del entry[key]
        _write(tmp_path, [entry])
        _refused(tmp_path)


def test_optional_fields_may_be_absent(tmp_path):
    _write(tmp_path, [{"id": "SparkFun", "url": SPARKFUN_URL, "branch": "main"}])
    loaded = manifest.load(tmp_path)
    assert isinstance(loaded, Manifest)
    entry = loaded.find("SparkFun")
    assert (entry.commit, entry.vars, entry.licence_spdx, entry.acknowledged, entry.added_on) == ("", {}, None, False, "")


def test_the_issue_names_the_library_when_it_is_known(tmp_path):
    _write(tmp_path, [_entry(branch="-x")])
    assert "SparkFun" in _refused(tmp_path).text


def test_ids_that_differ_only_by_case_are_refused(tmp_path):
    _write(tmp_path, [_entry(id="SparkFun"), _entry(id="sparkfun", url="https://github.com/o/other.git")])
    issue = _refused(tmp_path)
    assert "capital letters" in issue.text


def test_the_same_id_twice_is_refused(tmp_path):
    _write(tmp_path, [_entry(), _entry()])
    _refused(tmp_path)


def test_variables_that_pass_the_rules_are_loaded(tmp_path):
    _write(
        tmp_path,
        [_entry(id="WurthElektronik", url=WURTH_URL, branch="master", vars={"WE_3DMODEL_DIR": "3dmodels", "ONE_MORE": "a/b"})],
    )
    entry = manifest.load(tmp_path).find("WurthElektronik")
    assert entry.vars == {"WE_3DMODEL_DIR": "3dmodels", "ONE_MORE": "a/b"}


def test_a_file_url_is_refused_unless_the_caller_allows_it(tmp_path):
    url = (tmp_path / "up.git").resolve().as_uri()
    _write(tmp_path, [_entry(id="Demo", url=url, branch="main")])
    _refused(tmp_path)
    loaded = manifest.load(tmp_path, allow_file=True)
    assert isinstance(loaded, Manifest) and loaded.find("Demo").url == url


def test_load_never_raises_on_an_unreadable_path(tmp_path):
    (tmp_path / manifest.MANIFEST_NAME).mkdir()
    assert isinstance(manifest.load(tmp_path), Issue)


def test_save_returns_an_issue_instead_of_raising(tmp_path):
    result = manifest.save(tmp_path / "missing" / "deeper", Manifest())
    assert result is None or isinstance(result, Issue)


def test_what_save_writes_load_accepts(tmp_path):
    entries = (
        CatalogEntry(id="SparkFun", url=SPARKFUN_URL, branch="main", commit=SHA, vars={"SPARKFUN_KICAD_LIBRARY": ""}),
        CatalogEntry(id="4ms", url="https://github.com/4ms/4ms-kicad-lib.git", branch="master", vars={"KICAD_4MS_LIBS": ""}),
    )
    assert manifest.save(tmp_path, Manifest(entries)) is None
    loaded = manifest.load(tmp_path)
    assert isinstance(loaded, Manifest)
    assert {e.id for e in loaded.libraries} == {"SparkFun", "4ms"}
