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
