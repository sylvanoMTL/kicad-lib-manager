"""The one name of a catalog library (Phase 17 plan 21; CAT-01; owner finding 6 of the 17-17 check).

A curated library keeps its friendly name, a library added by web address is '{owner}/{repo}', and a folder the
record does not list keeps its folder name. The list, the Details heading, the catalog pages and every line the
catalog writes take the name from catalog.names. Quick tests: no git process, no network.
"""

from dataclasses import replace

from catalogfixtures import LIB_FILES, SYMBOL_TEXT, fake_net, make_third_party, write_git_config
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


# -- the recorded name, the name rule and KiCad's add-on id (plan 17-24, D-33, D-34) -------------

RECORDED = "4ms Kicad Libraries"
ADDON_ID = "com.github.4ms.4ms-kicad-lib"
OLD = "a" * 40
NEW = "b" * 40
BEFORE = ["symbols/A.kicad_sym", "fp/B.pretty/x.kicad_mod"]
AFTER = ["symbols/A.kicad_sym", "symbols/C.kicad_sym"]
DIFF = [("M", "symbols/A.kicad_sym"), ("A", "symbols/C.kicad_sym"), ("D", "fp/B.pretty/x.kicad_mod")]


def _recorded(**changes):
    return replace(entry(), name=RECORDED, nickname_prefix=manifest.PCM_PREFIX, addon_id=ADDON_ID, **changes)


def _installed_pcm(tmp_path):
    root = make_collection(tmp_path / "col")
    files = {"symbols/A.kicad_sym": "(kicad_symbol_lib)", "fp/B.pretty/x.kicad_mod": "(footprint)"}
    write_git_config(make_third_party(root, FOURMS_ID, files))
    listed = _recorded()
    assert manifest.save(root, Manifest((listed,))) is None
    return root, listed


def test_the_recorded_name_comes_first():
    assert names.display_name(FOURMS_ID, _recorded()) == RECORDED  # over owner/repo
    assert names.display_name(FOURMS_ID, entry()) == FOURMS_NAME  # an entry with no recorded name
    sparkfun = replace(entry("SparkFun", url="https://github.com/sparkfun/SparkFun-KiCad-Libraries.git"), name="Spark")
    assert names.display_name("SparkFun", sparkfun) == "Spark"
    assert names.display_name("SparkFun") == "SparkFun"  # no entry: the curated name
    mapping = names.source_names(Manifest((_recorded(),)))
    assert mapping[FOURMS_ID] == RECORDED


def test_a_curated_source_records_its_name_and_a_fixed_rule():
    for known in curated.CURATED:
        source = ops._curated_source(known)
        assert (source.name, source.nickname_prefix) == (known.name, "")  # fixed: its links are never asked
    assert ops._checked_source(_checked()).nickname_prefix is None  # an address decides from the links
    assert ops._checked_source(_checked()).default_prefix == ""


def test_a_curated_library_keeps_its_names_whatever_its_links_say(tmp_path):
    root = make_collection(tmp_path / "col")
    known = curated.curated_by_id("SparkFun")
    plan = ops.plan_add(root, known, manifest.load(root), free_space=_free(50000), running=_no_kicad)
    links = SYMBOL_TEXT.replace('"Demo:R_0603"', '"PCM_Demo:R_0603"')
    net = fake_net({**LIB_FILES, "symbols/Demo.kicad_sym": links})[0]
    staged = ops.stage_add(root, plan, net, free_space=_free(50000))
    assert isinstance(staged, ops.Staged), staged
    assert staged.report.nickname_prefix == "" and staged.report.symbol_libs == ("Demo",)
    ops.register_add(root, staged, acknowledged=True, today="2026-11-27")
    recorded = manifest.load(root).find("SparkFun")
    assert (recorded.name, recorded.nickname_prefix) == (known.name, "")


def test_reinstall_keeps_the_name_rule(tmp_path):
    root = make_collection(tmp_path / "col")
    listed = _recorded()
    mf = Manifest((listed,))
    assert manifest.save(root, mf) is None

    plan = ops.plan_reinstall(root, listed, mf, free_space=_free(5000), running=_no_kicad)

    assert plan.name == RECORDED
    assert (plan.source.nickname_prefix, plan.source.addon_id) == ("PCM_", ADDON_ID)  # fixed, not asked again
    staged = ops.stage_add(root, plan, fake_net(LIB_FILES)[0], free_space=_free(5000))  # plain links in the download
    assert isinstance(staged, ops.Staged), staged
    assert staged.report.nickname_prefix == "PCM_" and staged.report.symbol_libs == ("PCM_Demo",)
    assert not [i for i in ops.register_add(root, staged, today="2026-11-27") if i.severity.name == "ERROR"]
    again = manifest.load(root).find(FOURMS_ID)
    assert (again.name, again.nickname_prefix, again.addon_id) == (RECORDED, "PCM_", ADDON_ID)


def test_reinstall_of_an_entry_without_a_recorded_name_records_the_shown_one(tmp_path):
    root = make_collection(tmp_path / "col")
    listed = entry()
    mf = Manifest((listed,))
    assert manifest.save(root, mf) is None
    plan = ops.plan_reinstall(root, listed, mf, free_space=_free(5000), running=_no_kicad)
    staged = ops.stage_add(root, plan, fake_net(LIB_FILES)[0], free_space=_free(5000))
    ops.register_add(root, staged, today="2026-11-27")
    again = manifest.load(root).find(FOURMS_ID)
    assert (again.name, again.nickname_prefix, again.addon_id) == (FOURMS_NAME, "", "")


def test_update_names_added_and_removed_libraries_with_the_prefix(tmp_path):
    root, listed = _installed_pcm(tmp_path)
    net, _calls = fake_net(sha=OLD, fetch_sha=NEW, tree={"HEAD": BEFORE, NEW: AFTER}, diff_tree=DIFF)

    plan = ops.plan_update(root, listed, net, running=_no_kicad)

    assert isinstance(plan, ops.UpdatePlan), plan
    assert (plan.added, plan.removed) == (("PCM_C",), ("PCM_B",))
    net, _calls = fake_net(sha=OLD, fetch_sha=NEW, tree={"HEAD": BEFORE, NEW: AFTER}, diff_tree=DIFF)
    issues = ops.apply_update(root, plan, net)
    removed = [i.text for i in issues if i.code == "catalog.update_removed"]
    assert removed == [f"Update of {RECORDED} removed 1 libraries: PCM_B. Projects that use them lose those parts."]


def test_remove_from_the_files_on_disk_names_prefixed_libraries(tmp_path):
    root, _listed = _installed_pcm(tmp_path)
    plan = ops.plan_remove(root, FOURMS_ID, manifest.load(root), running=_no_kicad)
    assert plan.name == RECORDED
    assert plan.nicknames == ("PCM_A", "PCM_B")
    assert (plan.symbol_nicknames, plan.footprint_nicknames) == (("PCM_A",), ("PCM_B",))
