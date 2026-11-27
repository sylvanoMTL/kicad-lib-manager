"""KiCad's add-on list as catalog listings (Phase 17 plan 22; D-33, D-36, CAT-01, CAT-09, CAT-11).

No network: every test hands read_index an `opener` stand-in built on tests/fixtures/addons/packages.json,
a small hand-made copy of KiCad's packages file. The opener is called as opener(request, timeout, limit).
"""

import hashlib
import json
from pathlib import Path

from kicad_lib_manager.catalog import addons
from kicad_lib_manager.catalog.addons import Listing, parse_packages, read_index
from kicad_lib_manager.models import Issue

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
