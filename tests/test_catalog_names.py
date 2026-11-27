"""The one name of a catalog library (Phase 17 plan 21; CAT-01; owner finding 6 of the 17-17 check).

A curated library keeps its friendly name, a library added by web address is '{owner}/{repo}', and a folder the
record does not list keeps its folder name. The list, the Details heading, the catalog pages and every line the
catalog writes take the name from catalog.names. Quick tests: no git process, no network.
"""

from catalogfixtures import LIB_FILES, fake_net
from collectionfixtures import make_collection

from kicad_lib_manager.catalog import curated, manifest, names, ops, status, urls
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest

FOURMS_URL = "https://github.com/4ms/4ms-kicad-lib.git"
FOURMS_ID = "4ms-4ms-kicad-lib"
FOURMS_NAME = "4ms/4ms-kicad-lib"
SHA = "a" * 40


def entry(id=FOURMS_ID, url=FOURMS_URL, *, vars=None):
    return CatalogEntry(
        id=id, url=url, branch="main", commit=SHA, vars=vars or {}, licence_spdx="MIT",
        acknowledged=False, acknowledged_on="", added_on="2026-11-20",
    )


def _free(mb):
    return lambda path: type("Usage", (), {"free": mb * 1024 * 1024})()


def _no_kicad():
    return []


def _checked(url=FOURMS_URL):
    return ops.CheckedRepo(urls.parse_github_url(url), None, "main", None)


# -- the name rule ----------------------------------------------------------------------------


def test_a_curated_library_keeps_its_friendly_name():
    assert names.display_name("SparkFun") == "SparkFun"
    assert names.display_name("sparkfun") == "SparkFun"  # the letter case of the id is ignored
    assert names.display_name("WurthElektronik") == curated.curated_by_id("WurthElektronik").name
    # a curated id wins over the address of its entry
    sparkfun = entry("SparkFun", url="https://github.com/sparkfun/SparkFun-KiCad-Libraries.git")
    assert names.display_name("SparkFun", sparkfun) == "SparkFun"


def test_an_address_added_library_is_owner_slash_repo():
    assert names.display_name(FOURMS_ID, entry()) == FOURMS_NAME
    assert names.display_name(FOURMS_ID, url="https://github.com/4ms/4ms-kicad-lib") == FOURMS_NAME


def test_other_entries_and_ids_without_an_entry_give_the_id():
    local = entry("demo", url="file:///somewhere/demo.git")
    assert names.display_name("demo", local) == "demo"
    assert names.display_name("Stray") == "Stray"
    assert names.display_name(FOURMS_ID) == FOURMS_ID  # no entry: nothing says where it came from


def test_source_names_maps_every_curated_id_and_every_entry_id():
    mf = Manifest((entry(), entry("demo", url="file:///somewhere/demo.git")))
    mapping = names.source_names(mf)
    assert mapping[FOURMS_ID] == FOURMS_NAME and mapping["demo"] == "demo"
    assert all(mapping[known.id] == known.name for known in curated.CURATED)


# -- the list row ------------------------------------------------------------------------------


def test_the_list_row_is_named_through_names(tmp_path):
    root = make_collection(tmp_path / "col")
    third = root / "ThirdParty"
    (third / FOURMS_ID).mkdir(parents=True)
    rows = status.row_statuses(root, Manifest((entry(),)), curated=curated.CURATED)
    assert [row.name for row in rows if row.id == FOURMS_ID] == [FOURMS_NAME]


# -- the plans and the lines the catalog writes ------------------------------------------------


def test_the_plan_of_a_checked_address_is_named_owner_slash_repo(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, _checked(), manifest.load(root), free_space=_free(5000), running=_no_kicad)
    assert plan.refusals == ()
    assert plan.name == FOURMS_NAME and plan.source.name == FOURMS_NAME
    assert plan.source.id == FOURMS_ID and plan.folder == root / "ThirdParty" / FOURMS_ID  # the folder name is the id


def test_the_added_line_names_the_library_owner_slash_repo(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, _checked(), manifest.load(root), free_space=_free(5000), running=_no_kicad)
    staged = ops.stage_add(root, plan, fake_net(LIB_FILES)[0], free_space=_free(5000))
    assert isinstance(staged, ops.Staged), staged
    issues = ops.register_add(root, staged, acknowledged=True, today="2026-11-27")
    success = [i.text for i in issues if i.code == "catalog.added"]
    assert success == [f"Added {FOURMS_NAME} to the catalog: 1 symbol libraries, 1 footprint libraries."]


def test_the_plans_of_a_listed_address_library_carry_the_name(tmp_path):
    root = make_collection(tmp_path / "col")
    listed = entry()
    mf = Manifest((listed,))
    reinstall = ops.plan_reinstall(root, listed, mf, free_space=_free(5000), running=_no_kicad)
    assert reinstall.name == FOURMS_NAME and reinstall.source.name == FOURMS_NAME
    removal = ops.plan_remove(root, FOURMS_ID, mf, running=_no_kicad)
    assert removal.name == FOURMS_NAME and removal.id == FOURMS_ID
    update = ops.plan_update(root, listed, fake_net()[0], running=_no_kicad)  # the folder is missing: the refusal names it
    assert update.code == "catalog.folder_missing" and f"Reinstall {FOURMS_NAME} to download it again." in update.text


def test_the_already_listed_refusals_name_it_the_same_way(tmp_path):
    root = make_collection(tmp_path / "col")
    mf = Manifest((entry(),))
    again = ops.plan_add(root, _checked(), mf, free_space=_free(5000), running=_no_kicad)
    assert [i.text for i in again.refusals] == [f"This library is already in your catalog as {FOURMS_NAME}. Select it in the list."]
    same = ops.check_repository(root, FOURMS_URL, mf, fake_net()[0], repo_info=lambda owner, repo: None)
    assert same.text == f"This library is already in your catalog as {FOURMS_NAME}. Select it in the list."


def test_the_variable_conflict_names_the_address_library(tmp_path):
    other = entry(vars={"SHARED_VAR": ""})
    refusal = ops._var_conflict(Manifest((other,)), "Another", ["SHARED_VAR"])
    assert refusal is not None
    assert f"which {FOURMS_NAME} already uses" in refusal.text and f"Remove {FOURMS_NAME} first" in refusal.text
