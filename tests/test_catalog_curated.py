"""The app's own list of curated libraries and its candidates (Phase 17 plan 04; CAT-09, CAT-10, D-22, D-28).

No test pins the exact set of curated ids: it checks that the required ones are present and that the lists
stay consistent, so plan 17-18 can promote a candidate without editing unrelated tests.
"""

import pytest

from kicad_lib_manager.catalog import curated
from kicad_lib_manager.catalog.curated import CANDIDATES, CURATED, REJECTED, Candidate, CuratedEntry, curated_by_id
from kicad_lib_manager.catalog.licences import LicenceClass
from kicad_lib_manager.catalog.manifest import safe_var_folder, valid_var_name
from kicad_lib_manager.catalog.urls import RepoRef, parse_github_url, repo_key, valid_id

REQUIRED_IDS = {"WurthElektronik", "SparkFun"}


def test_the_two_required_libraries_are_curated():
    assert REQUIRED_IDS <= {e.id for e in CURATED}


def test_curated_entries_have_the_documented_type():
    assert all(isinstance(e, CuratedEntry) for e in CURATED)
    assert all(isinstance(c, Candidate) for c in CANDIDATES)


@pytest.mark.parametrize("entry", CURATED, ids=lambda e: e.id)
def test_every_curated_entry_passes_the_catalog_rules(entry):
    assert valid_id(entry.id)
    assert entry.id.casefold() not in {"custom", "thirdparty", ".staging"}
    ref = parse_github_url(entry.url)
    assert isinstance(ref, RepoRef), entry.url
    assert entry.url == ref.https_url
    assert entry.name and entry.description.endswith(".")
    assert entry.size_mb > 0 and entry.install_mb >= entry.size_mb
    assert entry.symbol_libs > 0 and entry.footprint_libs > 0
    for name, folder in entry.vars.items():
        assert valid_var_name(name), name
        assert safe_var_folder(folder), (name, folder)
    assert isinstance(entry.licence, LicenceClass)


def test_curated_ids_and_repositories_are_unique():
    ids = [e.id.casefold() for e in CURATED]
    assert len(ids) == len(set(ids))
    keys = [repo_key(e.url) for e in CURATED]
    assert len(keys) == len(set(keys))


def test_wurth_elektronik_facts():
    entry = curated_by_id("WurthElektronik")
    assert entry.licence is LicenceClass.PROPRIETARY
    assert entry.proprietary is True
    assert entry.vars == {"WE_3DMODEL_DIR": "3dmodels"}
    assert entry.legacy_prefix == "WurthElektronik/KiCad-Library/"
    assert (entry.symbol_libs, entry.footprint_libs) == (402, 43)
    assert entry.install_mb >= 10000
    assert entry.branch == "master"
    assert repo_key(entry.url) == "wurthelektronik/kicad-library"


def test_sparkfun_facts():
    entry = curated_by_id("SparkFun")
    assert entry.licence_spdx == "CC-BY-4.0"
    assert entry.licence is LicenceClass.OPEN
    assert entry.proprietary is False
    assert entry.vars == {"SPARKFUN_KICAD_LIBRARY": ""}
    assert (entry.symbol_libs, entry.footprint_libs) == (30, 21)
    assert entry.branch == "main"
    assert repo_key(entry.url) == "sparkfun/sparkfun-kicad-libraries"
    assert entry.install_mb >= 302


LICENCE_URLS = {
    "WurthElektronik": "https://github.com/WurthElektronik/KiCad-Library/blob/master/License_Terms_WE_KiCad_library.pdf",
    "SparkFun": "https://github.com/sparkfun/SparkFun-KiCad-Libraries#license",
    "4ms": "https://github.com/4ms/4ms-kicad-lib/blob/master/UNLICENSE",
    "Alternate-KiCad-Library": "https://github.com/DawidCislo/Alternate-KiCad-Library#readme",
    "Espressif": "",
}


def test_the_licence_addresses_were_checked_by_the_owner_on_2026_11_27():
    known = {e.id: e for e in (*CURATED, *CANDIDATES)}  # a candidate promoted by plan 17-18 keeps its address
    assert {"WurthElektronik", "SparkFun"} <= set(known)
    for id, url in LICENCE_URLS.items():
        if id in known:
            assert known[id].licence_url == url, id


def test_a_library_without_a_licence_address_has_an_empty_one():
    # a missing address is "", never None: the licence page then opens the repository page instead
    for entry in (*CURATED, *CANDIDATES):
        assert isinstance(entry.licence_url, str)
    assert Candidate("x", "X", "https://github.com/x/x.git", "main", None, 1).licence_url == ""


@pytest.mark.parametrize("entry", (*CURATED, *CANDIDATES), ids=lambda e: e.id)
def test_a_licence_address_is_a_secure_page_of_the_librarys_own_repository(entry):
    if not entry.licence_url:
        return
    own = entry.url.removesuffix(".git").casefold()
    assert entry.licence_url.startswith("https://") and entry.licence_url.casefold().startswith(own)
    assert " " not in entry.licence_url


def test_only_wurth_elektronik_has_a_legacy_prefix():
    assert [e.id for e in CURATED if e.legacy_prefix is not None] == ["WurthElektronik"]


def test_a_curated_variable_is_never_a_kicad_or_pcm_variable():
    for entry in CURATED:
        for name in entry.vars:
            assert not name.startswith("KICAD") or name.startswith("KICAD_"), name
            assert valid_var_name(name)


def test_curated_by_id_is_case_insensitive_and_curated_only():
    assert curated_by_id("sparkfun") is curated_by_id("SparkFun")
    assert curated_by_id("WURTHELEKTRONIK").id == "WurthElektronik"
    assert curated_by_id("Nope") is None
    assert curated_by_id("") is None


@pytest.mark.parametrize("candidate", CANDIDATES, ids=lambda c: c.id)
def test_every_candidate_is_well_formed(candidate):
    assert valid_id(candidate.id)
    assert isinstance(parse_github_url(candidate.url), RepoRef)
    assert candidate.research.strip()
    assert candidate.name and candidate.size_mb > 0 and candidate.branch
    for name, folder in candidate.vars.items():
        assert valid_var_name(name) and safe_var_folder(folder)


def test_the_three_conditional_libraries_are_candidates():
    ids = {c.id for c in CANDIDATES}
    keys = {repo_key(c.url) for c in CANDIDATES}
    # containment only: plan 17-18 moves a passed candidate to CURATED and a failed one to REJECTED
    for key in ("4ms/4ms-kicad-lib", "dawidcislo/alternate-kicad-library", "espressif/kicad-libraries"):
        assert key in keys or key in {repo_key(e.url) for e in CURATED} or key in {repo_key(url) for url, _ in REJECTED}
    assert len(ids) == len(CANDIDATES)


def test_a_candidate_is_never_listed_found_or_counted_as_curated():
    for candidate in CANDIDATES:
        assert curated_by_id(candidate.id) is None
    curated_ids = {e.id.casefold() for e in CURATED}
    assert not curated_ids & {c.id.casefold() for c in CANDIDATES}
    assert not {repo_key(e.url) for e in CURATED} & {repo_key(c.url) for c in CANDIDATES}


def test_curated_and_rejected_never_share_a_repository():
    rejected = {repo_key(url) for url, _reason in REJECTED}
    assert not {repo_key(e.url) for e in CURATED} & rejected
    assert not {repo_key(c.url) for c in CANDIDATES} & rejected


def test_rejected_entries_carry_a_url_and_a_reason():
    for url, reason in REJECTED:
        assert isinstance(parse_github_url(url), RepoRef)
        assert reason.strip()


def test_espressif_is_a_candidate_with_the_pcm_reason_while_it_is_unverified():
    keys = {repo_key(c.url): c for c in CANDIDATES}
    if "espressif/kicad-libraries" in keys:
        assert "Plugin and Content Manager" in keys["espressif/kicad-libraries"].research


def test_the_module_documents_the_d22_rule():
    assert "D-22" in curated.__doc__ and "REJECTED" in curated.__doc__
