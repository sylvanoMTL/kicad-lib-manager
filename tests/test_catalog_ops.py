"""Add and Reinstall as plan, stage and commit (Phase 17 plan 07; CAT-02, CAT-03, CAT-05, CAT-06, CAT-08..CAT-10).

Everything runs on synthetic collections through fake_net (no process starts, no network); free space and
the KiCad process list are faked. The ops functions are reached as attributes of the module so a missing
function fails its own test.
"""

import hashlib
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from catalogfixtures import LIB_FILES, fake_net
from collectionfixtures import make_collection

from kicad_lib_manager import fsutil
from kicad_lib_manager.catalog import curated, licences, manifest, ops, urls
from kicad_lib_manager.catalog.githubapi import RepoInfo
from kicad_lib_manager.catalog.gitnet import NetGit
from kicad_lib_manager.catalog.manifest import CatalogEntry
from kicad_lib_manager.models import Issue, Severity
from kicad_lib_manager.procs import StreamOutcome

MB = 1024 * 1024
SHA = "a" * 40
SPARKFUN = curated.curated_by_id("SparkFun")
WURTH = curated.curated_by_id("WurthElektronik")


def _free(mb):
    return lambda path: SimpleNamespace(total=10**13, used=0, free=int(mb * MB))


def _running(*names):
    return lambda: list(names)


def _drive(root: Path) -> str:
    return Path(root).resolve().anchor.rstrip("\\/") or "/"


def _errors(issues):
    return [i for i in issues if i.severity is Severity.ERROR]


def _staging_is_empty(root: Path) -> bool:
    staging = root / "ThirdParty" / ".staging"
    return not staging.exists() or not any(staging.iterdir())


def _install(root, source, net=None, *, acknowledged=False, today="2026-11-27", free=100000, mf=None):
    """plan, stage and register one library; return (plan, staged, issues)."""
    mf = manifest.load(root) if mf is None else mf
    plan = ops.plan_add(root, source, mf, free_space=_free(free), running=_running())
    assert plan.refusals == (), plan.refusals
    staged = ops.stage_add(root, plan, net or fake_net()[0], free_space=_free(free))
    assert isinstance(staged, ops.Staged), staged
    return plan, staged, ops.register_add(root, staged, acknowledged=acknowledged, today=today)


def _checked(url="https://github.com/a/b", *, info=None, branch="main", info_issue=None):
    ref = urls.parse_github_url(url)
    return ops.CheckedRepo(ref, info, branch, info_issue)


# -- the happy path and the licence tick ---------------------------------------------------


def test_curated_add_happy_path(tmp_path):
    root = make_collection(tmp_path / "col")
    net, calls = fake_net()
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.refusals == () and plan.name == "SparkFun" and plan.folder == root / "ThirdParty" / "SparkFun"
    assert plan.licence is licences.LicenceClass.OPEN and plan.licence_text_known is True
    assert (plan.size_mb, plan.needs_mb, plan.margin_mb, plan.free_mb) == (69, 310, 500, 5000)
    assert plan.reinstall is False and plan.legacy_prefix is None

    seen = []
    staged = ops.stage_add(root, plan, net, progress=lambda text, percent: seen.append(percent), free_space=_free(5000))
    assert isinstance(staged, ops.Staged), staged
    assert [p for p in seen if p is not None] == [40, 70]
    assert staged.folder.parent == root / "ThirdParty" / ".staging"
    assert staged.commit == SHA and staged.report.symbol_libs == ("Demo",) and staged.report.footprint_libs == ("Demo",)
    (clone,) = [c for c in calls if "clone" in c]
    assert "--branch=main" in clone and "https://github.com/sparkfun/SparkFun-KiCad-Libraries.git" in clone

    issues = ops.register_add(root, staged, acknowledged=False, today="2026-11-27")
    assert _errors(issues) == []
    success = [i for i in issues if i.code == "catalog.added"]
    assert [i.text for i in success] == ["Added SparkFun to the catalog: 1 symbol libraries, 1 footprint libraries."]
    assert success[0].severity is Severity.SUCCESS
    assert (root / "ThirdParty" / "SparkFun" / ".git").is_dir() and _staging_is_empty(root)

    entry = manifest.load(root).find("SparkFun")
    assert entry.vars == {"SPARKFUN_KICAD_LIBRARY": ""}
    assert (entry.licence_spdx, entry.commit, entry.added_on) == ("CC-BY-4.0", SHA, "2026-11-27")
    assert (entry.url, entry.branch) == (SPARKFUN.url, "main")
    assert (entry.acknowledged, entry.acknowledged_on) == (False, "")


def test_stage_add_still_accepts_a_plain_source(tmp_path):
    root = make_collection(tmp_path / "col")
    source = ops.AddSource("Demo", "Demo", "https://github.com/a/demo.git", "main", {}, "MIT")
    staged = ops.stage_add(root, source, fake_net()[0])
    assert isinstance(staged, ops.Staged), staged
    assert _errors(ops.register_add(root, staged)) == []
    assert manifest.load(root).find("Demo").commit == SHA


def test_proprietary_needs_the_tick(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, WURTH, manifest.load(root), free_space=_free(100000), running=_running())
    assert plan.licence is licences.LicenceClass.PROPRIETARY and plan.legacy_prefix == "WurthElektronik/KiCad-Library/"
    staged = ops.stage_add(root, plan, fake_net()[0], free_space=_free(100000))
    assert isinstance(staged, ops.Staged), staged

    refused = ops.register_add(root, staged, acknowledged=False, today="2026-11-27")
    assert [i.code for i in refused] == ["catalog.licence_not_acknowledged"]
    assert staged.folder.is_dir() and not (root / "ThirdParty" / "WurthElektronik").exists()
    assert not (root / "catalog.json").exists()

    done = ops.register_add(root, staged, acknowledged=True, today="2026-11-27")
    assert _errors(done) == []
    entry = manifest.load(root).find("WurthElektronik")
    assert (entry.acknowledged, entry.acknowledged_on, entry.licence_spdx) == (True, "2026-11-27", None)
    assert entry.vars == {"WE_3DMODEL_DIR": "3dmodels"}


# -- disk space ------------------------------------------------------------------------------


def test_disk_space_refusal_prints_three_numbers(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, WURTH, manifest.load(root), free_space=_free(1000), running=_running())
    drive = _drive(root)
    (refusal,) = plan.refusals
    assert (refusal.code, refusal.severity) == ("catalog.no_space", Severity.ERROR)
    assert refusal.text == (
        f"There is not enough free space on {drive} for Würth Elektronik. It needs about 12 GB plus a safety margin "
        f"of 3 GB, and {drive} has 1 GB free. Free some space, then try again."
    )
    assert (plan.needs_mb, plan.margin_mb, plan.free_mb) == (12000, 3000, 1000)
    net, calls = fake_net()
    result = ops.stage_add(root, plan, net, free_space=_free(1000))
    assert result == refusal and calls == []

    small = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(700), running=_running())
    assert small.refusals[0].text == (
        f"There is not enough free space on {drive} for SparkFun. It needs about 310 MB plus a safety margin "
        f"of 500 MB, and {drive} has 700 MB free. Free some space, then try again."
    )


def test_disk_space_boundary(tmp_path):
    root = make_collection(tmp_path / "col")
    mf = manifest.load(root)
    enough = ops.plan_add(root, WURTH, mf, free_space=_free(15000), running=_running())
    assert enough.refusals == ()
    short = ops.plan_add(root, WURTH, mf, free_space=_free(14999), running=_running())
    assert [i.code for i in short.refusals] == ["catalog.no_space"]


def test_unknown_size_makes_no_space_check(tmp_path):
    root = make_collection(tmp_path / "col")
    unknown = _checked(info=None, info_issue=Issue(Severity.ERROR, "api.unknown", "offline"))
    plan = ops.plan_add(root, unknown, manifest.load(root), free_space=_free(1), running=_running())
    assert plan.refusals == () and plan.size_mb is None and plan.needs_mb is None and plan.margin_mb is None
    assert plan.licence is licences.LicenceClass.UNKNOWN and plan.licence_text_known is False


def test_size_rule_for_add_by_url(tmp_path):
    root = make_collection(tmp_path / "col")
    info = RepoInfo("a/b", 70000, "main", "MIT", False, False)
    plan = ops.plan_add(root, _checked(info=info), manifest.load(root), free_space=_free(5000), running=_running())
    # 70000 KB is 69 MB rounded up; needed = 6 x 69 + 500; the margin is the larger of 500 MB and a quarter of that
    assert (plan.size_mb, plan.needs_mb, plan.margin_mb) == (69, 914, 500)
    assert plan.name == "a-b" and plan.folder == root / "ThirdParty" / "a-b"
    assert plan.source.url == "https://github.com/a/b.git" and plan.source.branch == "main"
    assert plan.licence is licences.LicenceClass.OPEN and plan.licence_text_known is True

    big = RepoInfo("a/b", 4000 * 1024, "main", "MIT", False, False)
    bigplan = ops.plan_add(root, _checked(info=big), manifest.load(root), free_space=_free(50000), running=_running())
    assert (bigplan.size_mb, bigplan.needs_mb, bigplan.margin_mb) == (4000, 24500, 6125)


def test_free_space_drop_during_download_stops_it(tmp_path):
    root = make_collection(tmp_path / "col")
    state = {"free": 100000}
    plan = ops.plan_add(root, WURTH, manifest.load(root), free_space=_free(100000), running=_running())
    assert plan.refusals == ()

    def progress(text, percent):
        state["free"] = 100  # the disk fills up after the first line

    net, _ = fake_net()
    result = ops.stage_add(root, plan, net, progress=progress, free_space=lambda p: SimpleNamespace(free=state["free"] * MB))
    drive = _drive(root)
    assert isinstance(result, Issue) and result.code == "catalog.no_space"
    assert result.text == (
        f"There is not enough free space on {drive} for Würth Elektronik. It needs about 12 GB plus a safety margin "
        f"of 3 GB, and {drive} has 100 MB free. Free some space, then try again."
    )
    assert _staging_is_empty(root) and not (root / "ThirdParty" / "WurthElektronik").exists()


# -- folders and addresses -----------------------------------------------------------------


def test_existing_folder_refusals(tmp_path):
    root = make_collection(tmp_path / "col")
    _install(root, SPARKFUN)
    again = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    (listed,) = again.refusals
    assert (listed.code, listed.text) == (
        "catalog.already_listed",
        "This library is already in your catalog as SparkFun. Select it in the list.",
    )

    other = make_collection(tmp_path / "other")
    (other / "ThirdParty" / "SparkFun").mkdir(parents=True)
    plan = ops.plan_add(other, SPARKFUN, manifest.load(other), free_space=_free(5000), running=_running())
    (in_way,) = plan.refusals
    assert in_way.code == "catalog.unlisted_in_way"
    assert in_way.text == (
        "The folder SparkFun already exists in ThirdParty but is not in the catalog. Remove it first "
        '(it is listed as "Problem: not in the catalog"), then add the library again.'
    )
    assert ops.stage_add(other, plan, fake_net()[0]) == in_way


def test_a_folder_that_differs_only_in_case_is_in_the_way(tmp_path):
    root = make_collection(tmp_path / "col")
    (root / "ThirdParty" / "sparkfun").mkdir(parents=True)
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert [i.code for i in plan.refusals] == ["catalog.unlisted_in_way"]


def _no_lookup(owner, repo):
    raise AssertionError("the lookup must not run")


def test_check_repository_refuses_a_bad_address(tmp_path):
    root = make_collection(tmp_path / "col")
    result = ops.check_repository(root, "http://github.com/a/b", manifest.load(root), fake_net()[0], repo_info=_no_lookup)
    assert isinstance(result, Issue) and result.code == "catalog.bad_url"


def test_check_repository_refuses_a_curated_duplicate_in_any_case(tmp_path):
    root = make_collection(tmp_path / "col")
    result = ops.check_repository(
        root, "https://github.com/SPARKFUN/sparkfun-kicad-libraries", manifest.load(root), fake_net()[0], repo_info=_no_lookup
    )
    assert isinstance(result, Issue) and result.code == "catalog.already_listed"
    assert result.text == "This library is already in your catalog as SparkFun. Select it in the list."


def test_check_repository_refuses_a_repository_already_in_the_catalog(tmp_path):
    root = make_collection(tmp_path / "col")
    mf = manifest.Manifest((CatalogEntry("Mine", "https://github.com/Some/Thing.git", "main"),))
    result = ops.check_repository(root, "https://github.com/some/thing/tree/dev", mf, fake_net()[0], repo_info=_no_lookup)
    assert isinstance(result, Issue) and result.code == "catalog.already_listed"
    assert result.text == "This library is already in your catalog as Mine. Select it in the list."


def test_check_repository_not_found_or_private(tmp_path):
    root = make_collection(tmp_path / "col")
    gone = Issue(Severity.ERROR, "api.not_found", "GitHub could not find this repository, or it is private.")
    result = ops.check_repository(root, "https://github.com/a/b", manifest.load(root), fake_net()[0], repo_info=lambda o, r: gone)
    assert result == gone


def test_check_repository_passes_owner_and_repo_to_the_lookup(tmp_path):
    root = make_collection(tmp_path / "col")
    asked = []
    info = RepoInfo("a/b", 70000, "dev", "MIT", False, False)

    def lookup(owner, repo):
        asked.append((owner, repo))
        return info

    net, calls = fake_net()
    result = ops.check_repository(root, "https://github.com/a/b.git", manifest.load(root), net, repo_info=lookup)
    assert isinstance(result, ops.CheckedRepo)
    assert asked == [("a", "b")] and (result.info, result.branch, result.info_issue) == (info, "dev", None)
    assert result.ref.default_id == "a-b" and calls == []


def test_check_repository_falls_back_to_the_symref_when_github_is_unreachable(tmp_path):
    root = make_collection(tmp_path / "col")
    unknown = Issue(Severity.ERROR, "api.unknown", "GitHub could not be reached.")
    net, calls = fake_net(symref=("trunk", "c" * 40))
    result = ops.check_repository(root, "https://github.com/a/b", manifest.load(root), net, repo_info=lambda o, r: unknown)
    assert isinstance(result, ops.CheckedRepo), result
    assert (result.branch, result.info, result.info_issue) == ("trunk", None, unknown)
    assert any("--symref" in call for call in calls)


def test_check_repository_distrusts_a_branch_name_from_github(tmp_path):
    root = make_collection(tmp_path / "col")
    info = RepoInfo("a/b", 10, "--upload-pack=x", "MIT", False, False)
    net, calls = fake_net(symref=("main", "c" * 40))
    result = ops.check_repository(root, "https://github.com/a/b", manifest.load(root), net, repo_info=lambda o, r: info)
    assert isinstance(result, ops.CheckedRepo) and result.branch == "main"
    assert any("--symref" in call for call in calls)


def test_check_repository_unreachable_everywhere_is_an_issue(tmp_path):
    root = make_collection(tmp_path / "col")
    unknown = Issue(Severity.ERROR, "api.unknown", "offline")
    net = NetGit(exe=Path("git-under-test"), starter=lambda argv, **kw: StreamOutcome(128, b"", ("fatal",), False, False))
    result = ops.check_repository(root, "https://github.com/a/b", manifest.load(root), net, repo_info=lambda o, r: unknown)
    assert isinstance(result, Issue) and result.code == "git.unreachable"


def test_a_licence_that_github_does_not_state_needs_the_licence_file(tmp_path):
    root = make_collection(tmp_path / "col")
    info = RepoInfo("a/b", 100, "main", "NOASSERTION", False, False)
    plan = ops.plan_add(root, _checked(info=info), manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.licence is licences.LicenceClass.NOT_STATED and plan.licence_text_known is False


# -- path variables ---------------------------------------------------------------------------


def test_duplicate_path_variable_is_refused(tmp_path):
    root = make_collection(tmp_path / "col")
    mf = manifest.Manifest((CatalogEntry("Other", "https://github.com/x/other.git", "main", vars={"WE_3DMODEL_DIR": "stuff"}),))
    plan = ops.plan_add(root, WURTH, mf, free_space=_free(100000), running=_running())
    (refusal,) = plan.refusals
    assert refusal.code == "catalog.var_in_use"
    assert refusal.text == (
        "This library needs the path variable WE_3DMODEL_DIR, which Other already uses for its own folder. "
        "Remove Other first, then add this library."
    )
    # the library that owns the variable is not in conflict with itself
    own = manifest.Manifest((CatalogEntry("WurthElektronik", WURTH.url, "master", vars={"WE_3DMODEL_DIR": "3dmodels"}),))
    reinstall = ops.plan_reinstall(root, own.find("WurthElektronik"), own, free_space=_free(100000), running=_running())
    assert reinstall.refusals == ()


MODEL_FILES = {
    "symbols/Demo.kicad_sym": LIB_FILES["symbols/Demo.kicad_sym"],
    "footprints/Demo.pretty/R_0603.kicad_mod": '(footprint "R_0603"\n  (model "${MY_MODELS}/shapes/a.step")\n)\n',
    "shapes/a.step": "solid\n",
}


def test_a_detected_variable_that_another_library_uses_refuses_the_download(tmp_path):
    root = make_collection(tmp_path / "col")
    mf = manifest.Manifest((CatalogEntry("Other", "https://github.com/x/other.git", "main", vars={"MY_MODELS": ""}),))
    manifest.save(root, mf)
    info = RepoInfo("a/b", 100, "main", "MIT", False, False)
    plan = ops.plan_add(root, _checked(info=info), mf, free_space=_free(5000), running=_running())
    assert plan.refusals == ()
    result = ops.stage_add(root, plan, fake_net(MODEL_FILES)[0], free_space=_free(5000))
    assert isinstance(result, Issue) and result.code == "catalog.var_in_use"
    assert "MY_MODELS" in result.text and "Other" in result.text
    assert _staging_is_empty(root)


def test_a_detected_variable_is_recorded_for_an_add_by_url(tmp_path):
    root = make_collection(tmp_path / "col")
    info = RepoInfo("a/b", 100, "main", "MIT", False, False)
    _, staged, issues = _install(root, _checked(info=info), fake_net(MODEL_FILES)[0])
    assert _errors(issues) == []
    assert staged.report.vars == {"MY_MODELS": ""}
    assert manifest.load(root).find("a-b").vars == {"MY_MODELS": ""}


# -- refusals after the download -------------------------------------------------------------


def test_validation_refusal_deletes_staging(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    result = ops.stage_add(root, plan, fake_net({"a.lib": "EESchema-LIBRARY\n"})[0], free_space=_free(5000))
    assert isinstance(result, Issue) and result.code == "catalog.kicad5_only"
    assert _staging_is_empty(root) and not (root / "ThirdParty" / "SparkFun").exists()
    assert not (root / "catalog.json").exists()


def test_a_failed_clone_deletes_staging(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    result = ops.stage_add(root, plan, fake_net(clone_error="fatal: boom")[0], free_space=_free(5000))
    assert isinstance(result, Issue) and result.code == "git.clone_failed" and "boom" in result.text
    assert _staging_is_empty(root)


def test_the_user_cancel_stops_the_download_and_deletes_staging(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    cancel = threading.Event()
    result = ops.stage_add(
        root, plan, fake_net()[0], progress=lambda t, p: cancel.set(), cancel=cancel, free_space=_free(5000)
    )
    assert isinstance(result, Issue) and result.code == "git.cancelled"
    assert _staging_is_empty(root)


def test_the_check_names_stock_own_and_other_catalog_libraries(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    staged = ops.stage_add(
        root, plan, fake_net()[0], stock_fp={"Demo"}, stock_sym=set(), own={}, other_catalog={"Demo": "Other"},
        free_space=_free(5000),
    )
    assert isinstance(staged, ops.Staged), staged
    assert [(c.nickname, c.kind, c.clashes_with) for c in staged.report.collisions] == [
        ("Demo", "Symbol", "Other"),
        ("Demo", "Footprint", "a KiCad library"),
    ]
    issues = ops.register_add(root, staged, today="2026-11-27")
    clash = [i for i in issues if i.code == "catalog.name_clashes"]
    assert len(clash) == 1 and clash[0].severity is Severity.WARNING
    assert clash[0].text.startswith("2 libraries of SparkFun have the same name as libraries you already have and start unticked: ")


# -- the record, .gitignore and the folder move ---------------------------------------------


def _git_root(tmp_path, gitignore: bytes | None):
    root = make_collection(tmp_path / "col")
    (root / ".git").mkdir()
    if gitignore is not None:
        (root / ".gitignore").write_bytes(gitignore)
    return root


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b"*.pyc\r\n", b"*.pyc\r\n/ThirdParty/\r\n"),
        (b"a\r\nb", b"a\r\nb\r\n/ThirdParty/\r\n"),
        (b"*.pyc\n", b"*.pyc\n/ThirdParty/\n"),
        (b"\xef\xbb\xbfa\n", b"\xef\xbb\xbfa\n/ThirdParty/\n"),
        (b"", b"/ThirdParty/\n"),
        (None, b"/ThirdParty/\n"),
    ],
)
def test_gitignore_line_is_appended_keeping_endings_and_bom(tmp_path, before, after):
    root = _git_root(tmp_path, before)
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.gitignore == ("create" if before is None else "append")
    _, _, issues = _install(root, SPARKFUN)
    assert (root / ".gitignore").read_bytes() == after
    codes = [i.code for i in issues]
    assert "catalog.gitignore_changed" in codes and "catalog.record_changed" in codes
    line = next(i for i in issues if i.code == "catalog.gitignore_changed")
    assert line.text == f"Added the line /ThirdParty/ to {root.as_posix()}/.gitignore."


@pytest.mark.parametrize("present", [b"ThirdParty/\n", b"/ThirdParty/\n", b"# x\n/ThirdParty\r\n", b"ThirdParty\n"])
def test_an_existing_gitignore_line_counts_as_present(tmp_path, present):
    root = _git_root(tmp_path, present)
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.gitignore == ""
    _, _, issues = _install(root, SPARKFUN)
    assert (root / ".gitignore").read_bytes() == present
    assert "catalog.gitignore_changed" not in [i.code for i in issues]


def test_a_root_that_is_not_a_git_repository_gets_no_gitignore(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.gitignore == ""
    _, _, issues = _install(root, SPARKFUN)
    assert not (root / ".gitignore").exists()
    assert not {"catalog.gitignore_changed", "catalog.record_changed"} & {i.code for i in issues}


def test_manifest_write_failure_moves_the_folder_back(tmp_path, monkeypatch):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    staged = ops.stage_add(root, plan, fake_net()[0], free_space=_free(5000))
    failure = Issue(Severity.ERROR, "fs.write_failed", "Could not write catalog.json: disk full")
    monkeypatch.setattr(ops.manifest, "save", lambda root, mf: failure)
    issues = ops.register_add(root, staged, today="2026-11-27")
    assert issues == [failure]
    assert staged.folder.is_dir() and not (root / "ThirdParty" / "SparkFun").exists()
    assert not (root / ".gitignore").exists()


def test_an_unreadable_record_stops_before_anything_moves(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    staged = ops.stage_add(root, plan, fake_net()[0], free_space=_free(5000))
    (root / "catalog.json").write_text("{broken", encoding="utf-8")
    issues = ops.register_add(root, staged, today="2026-11-27")
    assert [i.code for i in issues] == ["catalog.unreadable"]
    assert staged.folder.is_dir() and not (root / "ThirdParty" / "SparkFun").exists()


def test_known_dirty_baseline_is_recorded_casefolded(tmp_path):
    root = make_collection(tmp_path / "col")
    net, _ = fake_net(status=" M Footprints/a.kicad_mod\n?? Lib/B.pretty/x.kicad_mod")
    _, staged, issues = _install(root, SPARKFUN, net)
    assert staged.known_dirty == ("footprints/a.kicad_mod", "lib/b.pretty/x.kicad_mod")
    assert _errors(issues) == []
    assert manifest.load(root).find("SparkFun").known_dirty == staged.known_dirty


def test_a_clean_clone_records_no_baseline(tmp_path):
    root = make_collection(tmp_path / "col")
    _, staged, _ = _install(root, SPARKFUN)
    assert staged.known_dirty == () and manifest.load(root).find("SparkFun").known_dirty == ()


# -- reinstall ----------------------------------------------------------------------------------


def test_reinstall_keeps_the_acknowledgement(tmp_path):
    root = make_collection(tmp_path / "col")
    entry = CatalogEntry(
        "WurthElektronik", WURTH.url, "master", commit="c" * 40, vars={"WE_3DMODEL_DIR": "3dmodels"}, licence_spdx=None,
        acknowledged=True, acknowledged_on="2026-01-02", added_on="2026-01-01",
    )
    mf = manifest.Manifest((entry,))
    assert manifest.save(root, mf) is None
    plan = ops.plan_reinstall(root, entry, mf, free_space=_free(100000), running=_running())
    assert plan.reinstall is True and plan.refusals == () and plan.acknowledged_on == "2026-01-02"
    assert plan.name == "Würth Elektronik" and plan.licence is licences.LicenceClass.PROPRIETARY

    net, calls = fake_net(sha="d" * 40)
    staged = ops.stage_add(root, plan, net, free_space=_free(100000))
    assert isinstance(staged, ops.Staged), staged
    (clone,) = [c for c in calls if "clone" in c]
    assert WURTH.url in clone and "--branch=master" in clone
    issues = ops.register_add(root, staged, acknowledged=False, today="2026-11-27")
    assert _errors(issues) == []
    done = [i for i in issues if i.code == "catalog.reinstalled"]
    assert [i.text for i in done] == ["Reinstalled Würth Elektronik: 1 symbol libraries, 1 footprint libraries."]
    updated = manifest.load(root).find("WurthElektronik")
    assert updated.commit == "d" * 40
    assert (updated.acknowledged, updated.acknowledged_on, updated.added_on) == (True, "2026-01-02", "2026-01-01")
    assert updated.vars == {"WE_3DMODEL_DIR": "3dmodels"}


# -- the licence address (owner-approved 2026-11-27, 17-17 check) --------------------------------

WURTH_LICENCE_URL = "https://github.com/WurthElektronik/KiCad-Library/blob/master/License_Terms_WE_KiCad_library.pdf"
SPARKFUN_LICENCE_URL = "https://github.com/sparkfun/SparkFun-KiCad-Libraries#license"


def test_a_plain_source_has_no_licence_address():
    source = ops.AddSource("Demo", "Demo", "https://github.com/a/demo.git", "main", {}, "MIT")
    assert source.licence_url == ""


def test_a_curated_add_carries_the_licence_address_of_its_entry(tmp_path):
    root = make_collection(tmp_path / "col")
    wurth = ops.plan_add(root, WURTH, manifest.load(root), free_space=_free(100000), running=_running())
    sparkfun = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert wurth.source.licence_url == WURTH.licence_url == WURTH_LICENCE_URL
    assert sparkfun.source.licence_url == SPARKFUN.licence_url == SPARKFUN_LICENCE_URL


def test_a_reinstall_of_a_curated_library_carries_the_licence_address(tmp_path):
    root = make_collection(tmp_path / "col")
    entry = CatalogEntry("SparkFun", SPARKFUN.url, "main", commit="c" * 40, licence_spdx="CC-BY-4.0")
    mf = manifest.Manifest((entry,))
    plan = ops.plan_reinstall(root, entry, mf, free_space=_free(5000), running=_running())
    assert plan.reinstall is True and plan.source.licence_url == SPARKFUN_LICENCE_URL


def test_a_library_added_by_address_has_no_licence_address(tmp_path):
    root = make_collection(tmp_path / "col")
    info = RepoInfo("a/b", 70000, "main", "MIT", False, False)
    plan = ops.plan_add(root, _checked(info=info), manifest.load(root), free_space=_free(5000), running=_running())
    assert plan.source.licence_url == ""
    other = CatalogEntry("Mine", "https://github.com/Some/Thing.git", "main", commit="c" * 40)
    again = ops.plan_reinstall(root, other, manifest.Manifest((other,)), free_space=_free(5000), running=_running())
    assert again.source.licence_url == ""  # not a curated library: the page falls back to the repository page


def test_reinstall_of_a_folder_that_exists_is_refused(tmp_path):
    root = make_collection(tmp_path / "col")
    _install(root, SPARKFUN)
    mf = manifest.load(root)
    plan = ops.plan_reinstall(root, mf.find("SparkFun"), mf, free_space=_free(5000), running=_running())
    assert [i.code for i in plan.refusals] == ["catalog.folder_exists"]


# -- KiCad open, staging leftovers, net status ----------------------------------------------


def test_kicad_open_warns_only(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running("pcbnew"))
    assert plan.kicad_open == ("pcbnew",) and plan.refusals == ()
    quiet = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    assert quiet.kicad_open == ()


def test_clean_staging_age_rule(tmp_path):
    root = make_collection(tmp_path / "col")
    staging = root / "ThirdParty" / ".staging"
    old, young = staging / "Old.1234abcd", staging / "Young.5678ef01"
    for folder in (old, young):
        (folder / ".git" / "objects").mkdir(parents=True)
        (folder / "a.txt").write_text("x", encoding="utf-8")
    now = 1_000_000.0
    os.utime(old, (now - 7200, now - 7200))
    os.utime(young, (now - 600, now - 600))
    assert ops.clean_staging(root, older_than_s=3600, now=lambda: now) == []
    assert not old.exists() and young.is_dir()
    assert ops.clean_staging(make_collection(tmp_path / "none"), now=lambda: now) == []


def test_discard_staging_deletes_the_download(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    staged = ops.stage_add(root, plan, fake_net()[0], free_space=_free(5000))
    assert staged.folder.is_dir()
    ops.discard_staging(staged)
    assert not staged.folder.exists() and (root / "ThirdParty").is_dir()


def test_discard_staging_refuses_a_folder_outside_staging(tmp_path):
    root = make_collection(tmp_path / "col")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("x", encoding="utf-8")
    staged = ops.Staged(ops.AddSource("Demo", "Demo", "https://github.com/a/b.git", "main", {}, "MIT"), elsewhere, SHA)
    ops.discard_staging(staged)
    assert (elsewhere / "keep.txt").exists()


def test_net_status_versions(tmp_path):
    root = make_collection(tmp_path / "col")
    which = lambda name: "fake-git-folder/git.exe"  # noqa: E731
    old = ops.net_status(root, which=which, version=lambda exe: (2, 31, 0))
    assert old.net is None and old.refusal.code == "git.too_old" and old.warning is None
    warn = ops.net_status(root, which=which, version=lambda exe: (2, 40, 1))
    assert warn.net is not None and warn.refusal is None and warn.warning.code == "git.old_version"
    assert warn.version == (2, 40, 1) and warn.net.allow_file is False
    fine = ops.net_status(root, which=which, version=lambda exe: (2, 50, 0))
    assert fine.net is not None and fine.refusal is None and fine.warning is None
    missing = ops.net_status(root, which=lambda name: None)
    assert missing.net is None and missing.refusal.code == "git.not_found"
    assert missing.refusal.text.startswith("Git was not found. The catalog needs Git to download libraries.")
    unreadable = ops.net_status(root, which=which, version=lambda exe: None)
    assert unreadable.net is None and unreadable.refusal.code == "git.not_found"


# -- CAT-10: nothing outside the collection is written ------------------------------------


def _hashes(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def test_writes_stay_inside_the_collection(tmp_path):
    config = tmp_path / "kicad_config"
    (config / "3rdparty" / "pkg").mkdir(parents=True)
    (config / "3rdparty" / "pkg" / "lib.txt").write_text("pcm library", encoding="utf-8")
    (config / "installed_packages.json").write_text('{"packages": []}', encoding="utf-8")
    (config / "sym-lib-table").write_text('(sym_lib_table (lib (name "PCM_x")(uri "${KICAD9_3RD_PARTY}/x")))', encoding="utf-8")
    (config / "fp-lib-table").write_text("(fp_lib_table)", encoding="utf-8")
    before = _hashes(config)

    root = _git_root(tmp_path, b"*.pyc\n")
    (root / "Custom" / "Symbols" / "Atomic_Device.kicad_sym").write_text("(kicad_symbol_lib)", encoding="utf-8")
    own_before = _hashes(root / "Custom")
    top_before = {p.name for p in root.iterdir()}

    _install(root, SPARKFUN)
    # the folder goes missing, then Reinstall brings it back
    assert fsutil.remove_tree(root / "ThirdParty" / "SparkFun", inside=root / "ThirdParty") is None
    mf = manifest.load(root)
    plan = ops.plan_reinstall(root, mf.find("SparkFun"), mf, free_space=_free(5000), running=_running())
    staged = ops.stage_add(root, plan, fake_net()[0], free_space=_free(5000))
    assert _errors(ops.register_add(root, staged, today="2026-11-28")) == []

    assert _hashes(config) == before
    assert _hashes(root / "Custom") == own_before
    assert {p.name for p in root.iterdir()} - top_before <= {"ThirdParty", "catalog.json", ".gitignore"}


# -- the check's file count (17-21: finding 1 of the owner check) ----------------------------


_MOD_TEXT = '(footprint "F" (layer "F.Cu"))\n'
_SYM_TEXT = '(kicad_symbol_lib (symbol "S" (property "Reference" "U")))\n'


def _write_tree(folder: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="")
    return folder


def _validate(folder: Path, **kwargs):
    from kicad_lib_manager.catalog import validate

    return validate.validate_staging(folder, stock_fp=set(), stock_sym=set(), own={}, other_catalog={}, **kwargs)


def test_check_reports_footprint_progress(tmp_path):
    folder = _write_tree(
        tmp_path / "d", {"L.pretty/a.kicad_mod": _MOD_TEXT, "L.pretty/b.kicad_mod": _MOD_TEXT, "M.pretty/c.kicad_mod": _MOD_TEXT}
    )
    counts: list[tuple[int, int]] = []
    report = _validate(folder, progress=lambda done, total: counts.append((done, total)))
    assert not isinstance(report, Issue), report
    assert counts == [(1, 3), (2, 3), (3, 3)]


def test_check_without_footprints_reports_nothing(tmp_path):
    counts: list[tuple[int, int]] = []

    def record(done, total):
        counts.append((done, total))

    symbols_only = _write_tree(tmp_path / "s", {"only.kicad_sym": _SYM_TEXT})
    assert not isinstance(_validate(symbols_only, progress=record), Issue)
    empty = _write_tree(tmp_path / "e", {"readme.txt": "nothing\n"})
    assert isinstance(_validate(empty, progress=record), Issue)
    assert counts == []


def test_stage_add_forwards_the_check_count(tmp_path):
    root = make_collection(tmp_path / "col")
    plan = ops.plan_add(root, SPARKFUN, manifest.load(root), free_space=_free(5000), running=_running())
    counts: list[tuple[int, int]] = []
    staged = ops.stage_add(
        root, plan, fake_net()[0], free_space=_free(5000), check_progress=lambda done, total: counts.append((done, total))
    )
    assert isinstance(staged, ops.Staged), staged
    n = sum(1 for name in LIB_FILES if name.endswith(".kicad_mod"))
    assert counts and counts[-1] == (n, n)
