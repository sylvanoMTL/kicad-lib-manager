"""KiCad's add-on list as catalog listings (Phase 17 plan 22; D-33, D-36, CAT-01, CAT-09, CAT-11).

No network: every test hands read_index an `opener` stand-in built on tests/fixtures/addons/packages.json,
a small hand-made copy of KiCad's packages file. The opener is called as opener(request, timeout, limit).
"""

import datetime
import hashlib
import http.client
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from kicad_lib_manager.catalog import addons
from kicad_lib_manager.catalog.addons import Listing, parse_packages, read_index
from kicad_lib_manager.models import Issue, Severity

FIXTURE = Path(__file__).parent / "fixtures" / "addons" / "packages.json"
PACKAGES_URL = "https://gitlab.com/kicad/addons/repository/-/raw/main/packages-v1.json"
AT = "@"  # a link with a user name is built from parts, so no line looks like an e-mail address


def _fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def _download_urls() -> set[str]:
    data = json.loads(_fixture_bytes())
    return {v["download_url"] for p in data["packages"] for v in p.get("versions", [])}


def _repository(packages: bytes, url: str = PACKAGES_URL, *, sha: str | None = None) -> bytes:
    """What repository.json says about a packages file (its address and SHA-256)."""
    published = hashlib.sha256(packages).hexdigest() if sha is None else sha
    return json.dumps({"packages": {"url": url, "sha256": published}}).encode("utf-8")


class FakeNet:
    """An opener(request, timeout, limit) stand-in: answers by address, records every request."""

    def __init__(self, answers: dict[str, tuple[int, bytes] | Exception]):
        self.answers = answers
        self.asked: list[str] = []
        self.limits: list[int] = []

    def __call__(self, request, timeout, limit):
        url = request.full_url
        assert url not in _download_urls(), f"a package zip was requested: {url}"
        self.asked.append(url)
        self.limits.append(limit)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _net(packages: bytes | None = None, **kwargs) -> FakeNet:
    packages = _fixture_bytes() if packages is None else packages
    return FakeNet(
        {
            addons.REPOSITORY_URL: (200, kwargs.get("repository") or _repository(packages)),
            PACKAGES_URL: (200, packages),
        }
    )


def _by_id(listings) -> dict[str, Listing]:
    return {x.identifier: x for x in listings}


def test_read_index_from_the_network_then_the_cache(tmp_path):
    cache = tmp_path / "addon_index" / "packages-v1.json"
    first_net = _net()
    first = read_index(cache_file=cache, opener=first_net)
    assert first.issue is None and first.from_cache is False and first.copy_date == ""
    assert len(first.listings) == 11
    assert first_net.asked == [addons.REPOSITORY_URL, PACKAGES_URL]
    assert cache.read_bytes() == _fixture_bytes()

    second_net = _net()
    second = read_index(cache_file=cache, opener=second_net)
    assert second.issue is None and second.from_cache is True
    assert second_net.asked == [addons.REPOSITORY_URL]
    assert second.listings == first.listings


def test_only_libraries_are_listed():
    listings = parse_packages(_fixture_bytes())
    assert not isinstance(listings, Issue)
    ids = {x.identifier for x in listings}
    assert len(listings) == 11
    assert not ids & {"org.example.plugin", "org.example.theme", "org.example.broken"}


def test_4ms_listing():
    listing = _by_id(parse_packages(_fixture_bytes()))["com.github.4ms.4ms-kicad-lib"]
    assert listing.name == "4ms Kicad Libraries"
    assert listing.licence == "Unlicense"
    assert listing.description == "Kicad symbol and footprint libraries, with a focus on components used in analog and DSP audio."
    assert listing.url == "https://github.com/4ms/4ms-kicad-lib.git"
    assert listing.page == "https://github.com/4ms/4ms-kicad-lib"
    assert listing.install_mb == 222
    assert listing.addable is True and listing.reason == ""


def test_download_urls_are_never_requested(tmp_path):
    net = _net()
    read_index(cache_file=tmp_path / "copy.json", opener=net)
    read_index(cache_file=tmp_path / "copy.json", opener=net)
    assert set(net.asked) == {addons.REPOSITORY_URL, PACKAGES_URL}
    assert not set(net.asked) & _download_urls()


# -- which listings can be added (Task 2) ------------------------------------------------------------

PROGRAM_TEXT = (
    "This library is part of the repository of a program, not a library repository of its own, "
    "so the catalog cannot add it yet. Install it with KiCad's Plugin and Content Manager instead."
)
PACKED_TEXT = (
    "This library is kept in its repository as a packed file, not as library files, "
    "so the catalog cannot add it yet. Install it with KiCad's Plugin and Content Manager instead."
)
NO_LINK_TEXT = (
    "KiCad's add-on list names no repository for this library, so the catalog cannot add it. "
    "Install it with KiCad's Plugin and Content Manager instead."
)


def _other_host_text(host: str) -> str:
    return (
        f"This library is kept on {host}, and the catalog only downloads from GitHub so far. "
        "Install it with KiCad's Plugin and Content Manager instead."
    )


def _fixture_listings() -> dict[str, Listing]:
    return _by_id(parse_packages(_fixture_bytes()))


def _document(*packages) -> bytes:
    return json.dumps({"packages": list(packages)}).encode("utf-8")


def _package(identifier="org.example.one", **changes) -> dict:
    package = {
        "identifier": identifier,
        "name": "One",
        "description": "A library.",
        "license": "MIT",
        "type": "library",
        "resources": {"github": "https://github.com/o/r"},
        "versions": [],
    }
    package.update(changes)
    return package


def _parse_one(**changes) -> Listing | None:
    result = parse_packages(_document(_package(**changes)))
    assert not isinstance(result, Issue), result
    assert len(result) <= 1
    return result[0] if result else None


def test_program_repositories_are_not_addable():
    for identifier, page in (
        ("com.github.yaqwsx.kikit-library", "https://github.com/yaqwsx/KiKit"),
        ("com.github.buganini.kikakuka-footprints", "https://github.com/buganini/Kikakuka"),
    ):
        listing = _fixture_listings()[identifier]
        assert listing.addable is False and listing.url == ""
        assert listing.page == page
        assert listing.reason == PROGRAM_TEXT


def test_other_hosts_are_not_addable():
    listings = _fixture_listings()
    for identifier, page, host in (
        ("com.gitlab.franzee.kicad-addons.generic", "https://gitlab.com/franzee/kicad-addons/", "gitlab.com"),
        (
            "org.fabcloud.gitlab.electronics.kicad",
            "https://gitlab.fabcloud.org/pub/libraries/electronics/kicad",
            "gitlab.fabcloud.org",
        ),
        ("de.jaseg.kimesh.footprints", "https://git.jaseg.de/kimesh.git", "git.jaseg.de"),
    ):
        listing = listings[identifier]
        assert listing.addable is False and listing.url == ""
        assert listing.page == page
        assert listing.reason == _other_host_text(host)


def test_packed_file_in_the_repository_is_not_addable():
    nuova = _fixture_listings()["com.github.tormyvancool.NuovaElettronica"]
    assert nuova.addable is False and nuova.url == ""
    assert nuova.page == "https://github.com/tormyvancool/NuovaElettronica"
    assert nuova.reason == PACKED_TEXT
    # a release download of the library's own repository is not a packed file
    assert _fixture_listings()["com.github.4ms.4ms-kicad-lib"].addable is True


def test_raw_file_links_of_the_same_repository_are_packed():
    for download in (
        "https://github.com/o/r/raw/main/lib.zip",
        "https://raw.githubusercontent.com/O/R/main/lib.zip",
    ):
        listing = _parse_one(versions=[{"version": "1", "status": "stable", "download_url": download}])
        assert listing.addable is False and listing.reason == PACKED_TEXT
    other = _parse_one(
        versions=[{"version": "1", "status": "stable", "download_url": "https://github.com/x/y/raw/m/a.zip"}]
    )
    assert other.addable is True


def test_alternate_takes_its_github_link_and_the_licence_is_kept():
    listings = _fixture_listings()
    alternate = listings["com.github.dawidcislo.alternate-kicad-library"]
    assert alternate.addable is True
    assert alternate.url == "https://github.com/DawidCislo/Alternate-KiCad-Library.git"
    assert alternate.licence == "CC-BY-SA"
    keyswitch = listings["com.github.perigoso.keyswitch-kicad-library"]
    assert keyswitch.addable is True and keyswitch.url == "https://github.com/perigoso/keyswitch-kicad-library.git"
    assert listings["com.github.circuitbreakersrobotics.CB-KiCAD-Libraries"].install_mb is None
    assert listings["com.github.sparkfun.SparkFun-KiCad-Libraries"].addable is True


def test_link_rules():
    for link in (
        f"https://user{AT}github.com/o/r",  # a user name
        "http://github.com/o/r",  # not https
        "https://github.com/o",  # not a repository page
        "https://github.com/o/r/issues",  # not a repository page
        "https://github.com/o/r?tab=readme",  # a query
        "https://github.com/o/r#readme",  # a fragment
    ):
        listing = _parse_one(resources={"github": link})
        assert listing.addable is False and listing.url == "" and listing.page == "", link
        assert listing.reason == NO_LINK_TEXT, link
    assert _parse_one(resources={}).reason == NO_LINK_TEXT
    # a link that is no repository page is skipped and the next key is tried
    skipped = _parse_one(resources={"github": "https://github.com/o", "homepage": "https://github.com/o/r"})
    assert skipped.addable is True and skipped.url == "https://github.com/o/r.git"
    userinfo = _parse_one(resources={"git": f"https://user{AT}gitlab.com/x/y", "github": "https://github.com/o/r"})
    assert userinfo.addable is True and userinfo.url == "https://github.com/o/r.git"
    # the key order is git, github, gitlab, repository, homepage, source; letter case ignored
    assert _parse_one(resources={"homepage": "https://github.com/o/a", "git": "https://github.com/o/b"}).url.endswith(
        "/b.git"
    )
    assert _parse_one(resources={"homepage": "https://github.com/o/a", "GITHUB": "https://github.com/o/c"}).url.endswith(
        "/c.git"
    )
    assert _parse_one(resources={"Source": "https://github.com/o/s", "Website": "https://github.com/o/w"}).url.endswith(
        "/s.git"
    )
    assert _parse_one(resources={"Website": "https://github.com/o/w"}).reason == NO_LINK_TEXT


def test_fields_are_checked():
    bad = [
        _package("org.example.a", name="n" * 101),
        _package("org.example.b", description="d" * 501),
        _package("org.example.c", license="l" * 65),
        _package("has space"),
        _package("org.example.d", resources={"github": 7}),
        _package("org.example.e", resources={"k%d" % i: "https://github.com/o/r" for i in range(21)}),
        _package("org.example.f", resources={"github": "https://github.com/o/" + "r" * 300}),
        _package("org.example.g", name=""),
        _package("org.example.h", name="\x00\x1b"),
        _package("org.example.i", license=7),
        _package("org.example.j", resources=["https://github.com/o/r"]),
        _package("org.example.k", versions="1.0"),
        _package("-leading-dash"),
    ]
    assert parse_packages(_document(*bad, "not a package", 7, None)) == ()
    ok = parse_packages(_document(_package(name="A\x00B\x1bC", description="x\x07y\x00z", license="MIT")))
    assert [(x.name, x.description) for x in ok] == [("ABC", "xyz")]


def test_the_list_is_cut_at_500_and_sorted_by_name():
    many = [_package(f"org.example.p{i}", name=f"Lib {i:04d}") for i in range(600)]
    result = parse_packages(_document(*many))
    assert len(result) == addons.MAX_LISTINGS == 500
    assert [x.name for x in result] == sorted(x.name for x in result)
    mixed = parse_packages(_document(_package("org.example.b", name="beta"), _package("org.example.a", name="Alpha")))
    assert [x.name for x in mixed] == ["Alpha", "beta"]


def test_a_repeated_identifier_is_listed_once():
    result = parse_packages(_document(_package("org.example.a", name="First"), _package("org.example.a", name="Second")))
    assert [x.name for x in result] == ["First"]


# -- hardening: hosts, redirects, sizes, the published SHA-256, offline (Task 3) ---------------------

OFFLINE_TEXT = "KiCad's add-on list could not be read: the server could not be reached."
SLOW_TEXT = "KiCad's add-on list could not be read: the server took too long to answer."
CHANGED_TEXT = (
    "KiCad's add-on list could not be read: the downloaded list does not match the check value KiCad publishes for it."
)
ODD_TEXT = "KiCad's add-on list could not be read: the answer was not in a form this app understands."

# the real opener, taken at import: the suite's no-network guard replaces addons._default_opener per test
REAL_OPENER = addons._default_opener


def _offline(error=None):
    error = error or urllib.error.URLError("no network")

    def opener(request, timeout, limit):
        raise error

    return opener


def _issue(result, text: str) -> Issue:
    assert isinstance(result.issue, Issue), result
    assert result.issue.code == "addons.unreadable"
    assert result.issue.severity is Severity.ERROR
    assert result.issue.text == text
    return result.issue


def _set_copy_date(cache: Path, year: int, month: int, day: int) -> None:
    stamp = datetime.datetime(year, month, day, 12, 0).timestamp()
    os.utime(cache, (stamp, stamp))


@pytest.mark.parametrize(
    "url",
    [
        "http://gitlab.com/kicad/addons/repository/-/raw/main/packages-v1.json",
        "https://example.invalid/packages-v1.json",
        f"https://user{AT}gitlab.com/kicad/addons/repository/-/raw/main/packages-v1.json",
        "https://gitlab.com:8443/kicad/addons/packages-v1.json",
        "https://gitlab.com/kicad/addons/packages-v1.json?token=1",
        "https://gitlab.com/kicad/addons/packages-v1.json#x",
        "ftp://gitlab.com/packages-v1.json",
        "https://gitlab.com.example.invalid/packages-v1.json",
        "file:///packages-v1.json",
    ],
)
def test_packages_url_on_another_host_is_refused(url, tmp_path):
    net = FakeNet({addons.REPOSITORY_URL: (200, _repository(b"{}", url=url))})
    result = read_index(cache_file=tmp_path / "copy.json", opener=net)
    _issue(result, ODD_TEXT)
    assert result.listings == () and result.from_cache is False and result.copy_date == ""
    assert net.asked == [addons.REPOSITORY_URL]


def test_the_published_address_may_be_any_path_on_an_allowed_host():
    other = "https://repository.kicad.org/packages-v1.json"
    body = _fixture_bytes()
    net = FakeNet({addons.REPOSITORY_URL: (200, _repository(body, url=other)), other: (200, body)})
    result = read_index(cache_file=None, opener=net)
    assert result.issue is None and len(result.listings) == 11
    assert net.asked == [addons.REPOSITORY_URL, other]


def _redirect(newurl: str):
    handler = addons._SameHostRedirect()
    request = urllib.request.Request("https://repository.kicad.org/repository.json")
    return handler.redirect_request(request, None, 301, "Moved", {}, newurl)


@pytest.mark.parametrize(
    "target",
    [
        "https://repository.kicad.org/packages-v1.json",
        "https://gitlab.com/kicad/addons/repository/-/raw/main/packages-v1.json",
    ],
)
def test_redirect_stays_on_allowed_hosts(target):
    assert _redirect(target) is not None


@pytest.mark.parametrize(
    "target",
    [
        "https://example.invalid/x",
        "http://repository.kicad.org/x",
        "https://repository.kicad.org.example.invalid/x",
        f"https://user{AT}gitlab.com/x",
        "https://gitlab.com:8443/x",
        "file:///etc/passwd",
        "ftp://gitlab.com/x",
        "https://github.com/a/b",
    ],
)
def test_redirect_anywhere_else_is_refused(target):
    assert _redirect(target) is None


def test_oversized_answers_are_refused(tmp_path):
    big_repository = b" " * (addons.MAX_REPOSITORY_BYTES + 1)
    net = FakeNet({addons.REPOSITORY_URL: (200, big_repository)})
    result = read_index(cache_file=tmp_path / "copy.json", opener=net)
    _issue(result, ODD_TEXT)
    assert net.limits == [addons.MAX_REPOSITORY_BYTES + 1]

    big_packages = b" " * (addons.MAX_PACKAGES_BYTES + 1)
    net = FakeNet(
        {addons.REPOSITORY_URL: (200, _repository(big_packages)), PACKAGES_URL: (200, big_packages)},
    )
    result = read_index(cache_file=tmp_path / "copy.json", opener=net)
    _issue(result, ODD_TEXT)
    assert net.limits == [addons.MAX_REPOSITORY_BYTES + 1, addons.MAX_PACKAGES_BYTES + 1]
    assert not (tmp_path / "copy.json").exists()


class _Response:
    status = 200

    def __init__(self, reads):
        self.reads = reads

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, count=-1):
        self.reads.append(count)
        return b"x" * 5


def test_the_default_opener_reads_at_most_the_limit(monkeypatch):
    reads = []

    class Opener:
        def open(self, request, timeout=None):
            return _Response(reads)

    monkeypatch.setattr(addons, "_build_opener", lambda: Opener())
    request = urllib.request.Request(addons.REPOSITORY_URL)
    assert REAL_OPENER(request, 3.0, 11) == (200, b"xxxxx")
    assert reads == [11]


def test_an_http_error_from_the_default_opener_is_an_answer(monkeypatch):
    class Failing:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, None)

    monkeypatch.setattr(addons, "_build_opener", lambda: Failing())
    request = urllib.request.Request(addons.REPOSITORY_URL)
    assert REAL_OPENER(request, 3.0, 11) == (503, b"")


def test_the_requests_are_anonymous_with_a_generic_user_agent(tmp_path):
    seen = []

    def spy(request, timeout, limit):
        seen.append((request, timeout))
        return net(request, timeout, limit)

    net = _net()
    read_index(cache_file=None, opener=spy, timeout=4.5)
    assert len(seen) == 2
    for request, timeout in seen:
        headers = {k.lower(): v for k, v in request.header_items()}
        assert headers == {"user-agent": "kicad-lib-manager"}
        assert request.get_method() == "GET" and request.data is None
        assert timeout == 4.5


def test_changed_packages_file_is_refused(tmp_path):
    cache = tmp_path / "addon_index" / "packages-v1.json"
    net = _net(repository=_repository(_fixture_bytes(), sha="0" * 64))
    result = read_index(cache_file=cache, opener=net)
    _issue(result, CHANGED_TEXT)
    assert result.listings == () and result.from_cache is False
    assert not cache.exists()


def test_a_cache_that_is_not_the_published_file_is_not_used(tmp_path):
    cache = tmp_path / "addon_index" / "packages-v1.json"
    cache.parent.mkdir()
    cache.write_bytes(_document(_package("org.example.old", name="Old copy")))
    net = _net()
    result = read_index(cache_file=cache, opener=net)
    assert result.issue is None and result.from_cache is False
    assert net.asked == [addons.REPOSITORY_URL, PACKAGES_URL]
    assert len(result.listings) == 11
    assert cache.read_bytes() == _fixture_bytes()


@pytest.mark.parametrize("published", ["xyz", "A" * 63, "g" * 64, 7, None])
def test_a_published_check_value_must_be_64_hex_characters(published, tmp_path):
    repository = json.dumps({"packages": {"url": PACKAGES_URL, "sha256": published}}).encode("utf-8")
    net = FakeNet({addons.REPOSITORY_URL: (200, repository), PACKAGES_URL: (200, _fixture_bytes())})
    result = read_index(cache_file=tmp_path / "copy.json", opener=net)
    _issue(result, ODD_TEXT)
    assert not (tmp_path / "copy.json").exists()


def test_a_list_without_a_published_check_value_is_read_but_always_fetched_again(tmp_path):
    cache = tmp_path / "copy.json"
    repository = json.dumps({"packages": {"url": PACKAGES_URL}}).encode("utf-8")
    for _ in range(2):
        net = FakeNet({addons.REPOSITORY_URL: (200, repository), PACKAGES_URL: (200, _fixture_bytes())})
        result = read_index(cache_file=cache, opener=net)
        assert result.issue is None and result.from_cache is False and len(result.listings) == 11
        assert net.asked == [addons.REPOSITORY_URL, PACKAGES_URL]


def _failure_cases():
    deep = b"[" * 20000
    return [
        ("offline", urllib.error.URLError("no network"), OFFLINE_TEXT),
        ("os error", ConnectionResetError("reset"), OFFLINE_TEXT),
        ("incomplete", http.client.IncompleteRead(b"ab"), OFFLINE_TEXT),
        ("timeout", TimeoutError("slow"), SLOW_TEXT),
        ("socket timeout", socket.timeout("slow"), SLOW_TEXT),
        ("url timeout", urllib.error.URLError(TimeoutError("slow")), SLOW_TEXT),
        ("http 500", (500, b"oops"), ODD_TEXT),
        ("not json", (200, b"<html>not json</html>"), ODD_TEXT),
        ("not utf-8", (200, b"\xff\xfe\x00"), ODD_TEXT),
        ("deeply nested", (200, deep), ODD_TEXT),
        ("no packages key", (200, b'{"other": 1}'), ODD_TEXT),
        ("a list", (200, b"[]"), ODD_TEXT),
    ]


@pytest.mark.parametrize("where", ["repository", "packages"])
@pytest.mark.parametrize("label, answer, text", _failure_cases(), ids=[c[0] for c in _failure_cases()])
def test_offline_slow_and_odd_answers(label, answer, text, where, tmp_path):
    if where == "repository":
        answers = {addons.REPOSITORY_URL: answer}
    else:
        # repository.json is good and publishes the check value of the (odd) packages answer
        odd_body = isinstance(answer, tuple) and answer[0] == 200
        published_for = answer[1] if odd_body else _fixture_bytes()
        answers = {addons.REPOSITORY_URL: (200, _repository(published_for)), PACKAGES_URL: answer}
    result = read_index(cache_file=tmp_path / "copy.json", opener=FakeNet(answers))
    _issue(result, text)
    assert result.listings == () and result.from_cache is False and result.copy_date == ""
    assert not (tmp_path / "copy.json").exists()


def test_a_repository_answer_without_the_packages_entry_is_odd():
    for answer in (b'{"packages": 7}', b'{"packages": {}}', b'{"packages": {"url": 7, "sha256": "' + b"0" * 64 + b'"}}'):
        net = FakeNet({addons.REPOSITORY_URL: (200, answer)})
        _issue(read_index(cache_file=None, opener=net), ODD_TEXT)


def test_offline_uses_the_kept_copy(tmp_path):
    cache = tmp_path / "addon_index" / "packages-v1.json"
    good = read_index(cache_file=cache, opener=_net())
    assert good.issue is None
    _set_copy_date(cache, 2026, 11, 20)

    offline = read_index(cache_file=cache, opener=_offline())
    _issue(offline, OFFLINE_TEXT)
    assert offline.listings == good.listings and offline.from_cache is True
    assert offline.copy_date == "2026-11-20"
    assert cache.read_bytes() == _fixture_bytes()

    # a later successful read that reuses the copy unchanged sets its date to that day
    reused = read_index(cache_file=cache, opener=_net())
    assert reused.issue is None and reused.from_cache is True and reused.copy_date == ""
    again = read_index(cache_file=cache, opener=_offline(TimeoutError("slow")))
    _issue(again, SLOW_TEXT)
    assert again.copy_date == datetime.date.today().isoformat()


def test_a_refused_changed_file_leaves_the_earlier_copy_and_its_date(tmp_path):
    cache = tmp_path / "addon_index" / "packages-v1.json"
    read_index(cache_file=cache, opener=_net())
    _set_copy_date(cache, 2026, 11, 20)
    changed = _document(_package("org.example.new", name="New"))
    net = FakeNet(
        {addons.REPOSITORY_URL: (200, _repository(changed, sha="1" * 64)), PACKAGES_URL: (200, changed)},
    )
    result = read_index(cache_file=cache, opener=net)
    _issue(result, CHANGED_TEXT)
    assert len(result.listings) == 11 and result.from_cache is True and result.copy_date == "2026-11-20"
    assert cache.read_bytes() == _fixture_bytes()


def test_a_kept_copy_that_does_not_parse_gives_no_listings(tmp_path):
    cache = tmp_path / "copy.json"
    for bad in (b"not json", b'{"packages": 3}', b"[" * 20000, b"\xff"):
        cache.write_bytes(bad)
        result = read_index(cache_file=cache, opener=_offline())
        _issue(result, OFFLINE_TEXT)
        assert result.listings == () and result.from_cache is False and result.copy_date == ""


def test_an_oversized_kept_copy_is_not_read(tmp_path):
    cache = tmp_path / "copy.json"
    cache.write_bytes(b" " * (addons.MAX_PACKAGES_BYTES + 1))
    result = read_index(cache_file=cache, opener=_offline())
    assert result.listings == () and result.from_cache is False


def test_a_failed_cache_write_is_not_an_error(tmp_path):
    blocker = tmp_path / "addon_index"
    blocker.write_bytes(b"a file where the folder should be")
    result = read_index(cache_file=blocker / "packages-v1.json", opener=_net())
    assert result.issue is None and len(result.listings) == 11


def test_suite_never_reads_the_list(tmp_path):
    result = read_index(cache_file=None)
    _issue(result, OFFLINE_TEXT)
    assert result.listings == () and result.from_cache is False
    # the guard also covers a read that has a kept copy: it is the offline answer with the copy
    cache = tmp_path / "copy.json"
    cache.write_bytes(_fixture_bytes())
    kept = read_index(cache_file=cache)
    _issue(kept, OFFLINE_TEXT)
    assert len(kept.listings) == 11 and kept.from_cache is True
