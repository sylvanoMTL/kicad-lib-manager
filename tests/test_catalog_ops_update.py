"""Update and Remove as plan and apply (Phase 17 plan 10; CAT-04, CAT-10, D-05..D-09, D-13, D-21).

Everything runs on synthetic collections through fake_net (no process starts, no network). The ops functions
are reached as attributes of the module so a missing function fails its own test.
"""

import hashlib
import os
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from catalogfixtures import fake_net, make_third_party, write_git_config
from collectionfixtures import make_collection

from kicad_lib_manager import fsutil
from kicad_lib_manager.catalog import manifest, ops
from kicad_lib_manager.catalog.manifest import CatalogEntry, Manifest
from kicad_lib_manager.models import (
    FootprintLibrary,
    Issue,
    ScanResult,
    Severity,
    SymbolLibrary,
)

OLD = "a" * 40
NEW = "b" * 40
NEWER = "c" * 40
URL = "https://github.com/a/demo.git"

DIRTY_TEXT = (
    "{name} cannot be updated: files in {folder} were changed after it was added. Catalog libraries are managed "
    "copies, and an update would overwrite your changes. Keep your own changes in Custom/ instead."
)
KEPT_TEXT = (
    "Could not remove {name}: {reason}. Close anything that uses files in {folder}, then try again. "
    "The catalog entry was kept."
)

BEFORE = ["symbols/A.kicad_sym", "fp/B.pretty/x.kicad_mod"]
AFTER = ["symbols/A.kicad_sym", "symbols/C.kicad_sym"]
DIFF = [("M", "symbols/A.kicad_sym"), ("A", "symbols/C.kicad_sym"), ("D", "fp/B.pretty/x.kicad_mod")]


def _running(*names):
    return lambda: list(names)


def _hashes(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _entry(id="Demo", *, commit=OLD, known_dirty=(), vars=None):
    return CatalogEntry(
        id=id,
        url=URL,
        branch="main",
        commit=commit,
        vars=vars or {},
        licence_spdx="MIT",
        acknowledged=False,
        acknowledged_on="",
        added_on="2026-11-01",
        known_dirty=tuple(known_dirty),
    )


def _installed(tmp_path, id="Demo", *, files=None, **entry_kwargs):
    """A collection with one listed library on disk (a clone folder with a valid .git/config); (root, entry)."""
    root = make_collection(tmp_path / "col")
    folder = make_third_party(root, id, files or {"symbols/A.kicad_sym": "(kicad_symbol_lib)", "fp/B.pretty/x.kicad_mod": "(footprint)"})
    write_git_config(folder)
    entry = _entry(id, **entry_kwargs)
    assert manifest.save(root, Manifest((entry,))) is None
    return root, entry


def _net(**kwargs):
    kwargs.setdefault("sha", OLD)
    kwargs.setdefault("fetch_sha", NEW)
    kwargs.setdefault("tree", {"HEAD": BEFORE, NEW: AFTER})
    kwargs.setdefault("diff_tree", DIFF)
    return fake_net(**kwargs)


def _subcommands(calls):
    names = []
    for argv in calls:
        at = 2
        while at < len(argv) and argv[at] in ("-c", "-C"):
            at += 2
        names.append(argv[at])
    return names


def _planned(root, entry, **net_kwargs):
    net, calls = _net(**net_kwargs)
    plan = ops.plan_update(root, entry, net, running=_running())
    assert isinstance(plan, ops.UpdatePlan), plan
    return plan, calls


# -- Update: the preview -------------------------------------------------------------------


def test_update_preview(tmp_path):
    root, entry = _installed(tmp_path)
    folder = root / "ThirdParty" / "Demo"
    before = _hashes(folder)
    net, calls = _net()

    plan = ops.plan_update(root, entry, net, running=_running("pcbnew.exe"))

    assert isinstance(plan, ops.UpdatePlan), plan
    assert (plan.name, plan.folder, plan.entry) == ("Demo", folder, entry)
    assert (plan.old, plan.new) == (OLD, NEW)
    assert (plan.files_changed, plan.added, plan.removed) == (3, ("C",), ("B",))
    assert (plan.current, plan.dirty, plan.refusal) == (False, (), None)
    assert plan.kicad_open == ("pcbnew.exe",)
    assert _hashes(folder) == before  # nothing is written
    assert "reset" not in _subcommands(calls)
    (fetch,) = [c for c in calls if "fetch" in _subcommands([c])]
    assert URL in fetch and "main" in fetch  # the manifest address and branch, never the clone's origin


def test_update_already_current(tmp_path):
    root, entry = _installed(tmp_path)
    plan, calls = _planned(root, entry, fetch_sha=OLD)
    assert (plan.current, plan.old, plan.new) == (True, OLD, OLD)
    assert (plan.files_changed, plan.added, plan.removed, plan.refusal) == (0, (), (), None)
    assert "reset" not in _subcommands(calls)


def test_dirty_tree_refuses_with_files(tmp_path):
    root, entry = _installed(tmp_path)
    net, calls = _net(status=" M a.kicad_mod\n?? new.txt")

    plan = ops.plan_update(root, entry, net, running=_running())

    assert isinstance(plan, ops.UpdatePlan), plan
    assert plan.dirty == ("a.kicad_mod", "new.txt")
    folder = (root / "ThirdParty" / "Demo").as_posix()
    assert plan.refusal.severity is Severity.ERROR and plan.refusal.code == "catalog.dirty"
    assert plan.refusal.text == DIRTY_TEXT.format(name="Demo", folder=folder)
    assert "fetch" not in _subcommands(calls)  # nothing was downloaded


def test_known_dirty_files_are_not_a_change(tmp_path):
    root, entry = _installed(tmp_path, known_dirty=("footprints/lib.pretty/a.kicad_mod",))
    plan, _ = _planned(root, entry, status=" M Footprints/Lib.pretty/A.kicad_mod\n?? new.txt")
    assert plan.dirty == ("new.txt",) and plan.refusal.code == "catalog.dirty"

    plan, _ = _planned(root, entry, status=" M Footprints/Lib.pretty/A.kicad_mod")
    assert plan.dirty == () and plan.refusal is None


def test_unexpected_git_settings_refuse_before_git(tmp_path):
    root, entry = _installed(tmp_path)
    write_git_config(root / "ThirdParty" / "Demo", "[core]\n\tfsmonitor = evil.exe\n")
    net, calls = _net()

    answer = ops.plan_update(root, entry, net, running=_running())

    assert isinstance(answer, Issue) and answer.code == "catalog.unexpected_settings"
    assert answer.severity is Severity.ERROR and "core.fsmonitor" in answer.text
    assert calls == []  # git never ran


def test_missing_folder_is_an_issue(tmp_path):
    root, entry = _installed(tmp_path)
    assert fsutil.remove_tree(root / "ThirdParty" / "Demo", inside=root / "ThirdParty") is None
    net, calls = _net()
    answer = ops.plan_update(root, entry, net, running=_running())
    assert isinstance(answer, Issue) and answer.severity is Severity.ERROR
    assert calls == []


def test_fetch_failure_is_an_issue(tmp_path):
    root, entry = _installed(tmp_path)
    net, _ = _net(fetch_error="fatal: unable to access")
    answer = ops.plan_update(root, entry, net, running=_running())
    assert isinstance(answer, Issue) and answer.code == "git.fetch_failed"


def test_lfs_in_new_commit_refuses(tmp_path):
    root, entry = _installed(tmp_path)
    attrs = b"*.step filter=lfs diff=lfs merge=lfs -text\n"
    plan, calls = _planned(
        root,
        entry,
        tree={"HEAD": BEFORE, NEW: [*AFTER, ".gitattributes"]},
        blobs={f"{NEW}:.gitattributes": attrs},
    )
    assert plan.refusal is not None and plan.refusal.code == "catalog.lfs"
    assert plan.refusal.severity is Severity.ERROR and "Git LFS" in plan.refusal.text
    assert "reset" not in _subcommands(calls)


def test_library_leaving_with_a_surviving_name_is_still_reported(tmp_path):
    """Found by the real-git proof: a footprint library Demo that leaves is removed even when a symbol library Demo stays."""
    root, entry = _installed(tmp_path)
    before = ["symbols/Demo.kicad_sym", "fp/Demo.pretty/a.kicad_mod"]
    after = ["symbols/Demo.kicad_sym", "symbols/Extra.kicad_sym", "fp/New.pretty/b.kicad_mod"]
    plan, _ = _planned(root, entry, tree={"HEAD": before, NEW: after}, diff_tree=[("D", before[1]), ("A", after[1]), ("A", after[2])])
    assert (plan.added, plan.removed) == (("Extra", "New"), ("Demo",))


def test_attributes_without_lfs_do_not_refuse(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(
        root,
        entry,
        tree={"HEAD": BEFORE, NEW: [*AFTER, ".gitattributes"]},
        blobs={f"{NEW}:.gitattributes": b"# no filter here\n*.sym text eol=lf\n"},
    )
    assert plan.refusal is None


# -- Update: apply -------------------------------------------------------------------------


def test_apply_update_resets_to_the_planned_sha(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    net, calls = _net(fetch_sha=NEWER, status=["", "", "?? Case.txt"])  # the remote moved again after the preview

    issues = ops.apply_update(root, plan, net)

    (reset,) = [c for c in calls if "reset" in _subcommands([c])]
    assert reset[-1] == NEW and NEWER not in reset and "FETCH_HEAD" not in reset
    assert [i.code for i in issues][:2] == ["catalog.updated", "catalog.update_removed"]
    assert issues[0].severity is Severity.SUCCESS
    assert issues[0].text == f"Updated Demo to {NEW[:7]}: 1 libraries added, 1 removed."
    assert issues[1].severity is Severity.WARNING
    assert issues[1].text == "Update of Demo removed 1 libraries: B. Projects that use them lose those parts."


def test_apply_update_writes_the_new_commit_and_baseline(tmp_path):
    root, entry = _installed(tmp_path, known_dirty=("old.txt",))
    plan, _ = _planned(root, entry, status="?? old.txt")
    net, _ = _net(status=["?? old.txt", "?? Case.txt"])  # the recheck, then the status after the reset

    issues = ops.apply_update(root, plan, net)

    assert not [i for i in issues if i.severity is Severity.ERROR], issues
    saved = manifest.load(root).find("Demo")
    assert saved.commit == NEW and saved.known_dirty == ("case.txt",)
    assert (saved.url, saved.branch, saved.added_on, saved.licence_spdx) == (URL, "main", "2026-11-01", "MIT")


def test_apply_update_rechecks_clean_tree(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    net, calls = _net(status=" M edited.kicad_mod")  # the user edited a file after the preview

    issues = ops.apply_update(root, plan, net)

    assert [i.code for i in issues] == ["catalog.dirty"]
    assert "reset" not in _subcommands(calls)
    assert manifest.load(root).find("Demo").commit == OLD


def test_apply_update_rechecks_the_lfs_rule(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    net, calls = _net(tree={"HEAD": BEFORE, NEW: [*AFTER, "sub/.gitattributes"]}, blobs={f"{NEW}:sub/.gitattributes": b"*.step filter=lfs\n"})

    issues = ops.apply_update(root, plan, net)

    assert [i.code for i in issues] == ["catalog.lfs"]
    assert "reset" not in _subcommands(calls)
    assert manifest.load(root).find("Demo").commit == OLD


def test_apply_update_rechecks_unexpected_settings(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    write_git_config(root / "ThirdParty" / "Demo", "[alias]\n\tx = !calc\n")
    net, calls = _net()
    issues = ops.apply_update(root, plan, net)
    assert [i.code for i in issues] == ["catalog.unexpected_settings"] and calls == []


def test_apply_update_twice_is_a_no_op(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    first_net, _ = _net()
    assert not [i for i in ops.apply_update(root, plan, first_net) if i.severity is Severity.ERROR]

    after_net, calls = _net(sha=NEW)  # the clone is at the planned commit now
    issues = ops.apply_update(root, plan, after_net)

    assert "reset" not in _subcommands(calls)
    assert issues[0].code == "catalog.updated" and issues[0].severity is Severity.SUCCESS
    assert manifest.load(root).find("Demo").commit == NEW


def test_stopped_update_leaves_every_file_unchanged(tmp_path):
    root, entry = _installed(tmp_path)
    folder = root / "ThirdParty" / "Demo"
    plan, _ = _planned(root, entry)
    before, record = _hashes(folder), (root / "catalog.json").read_bytes()
    stop = threading.Event()
    stop.set()
    net, calls = _net()

    issues = ops.apply_update(root, plan, net, cancel=stop)

    assert [i.code for i in issues] == ["git.cancelled"]
    assert "reset" not in _subcommands(calls)
    assert _hashes(folder) == before and (root / "catalog.json").read_bytes() == record


def test_apply_update_refuses_a_refused_plan(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry, status="?? new.txt")
    net, calls = _net()
    issues = ops.apply_update(root, plan, net)
    assert [i.code for i in issues] == ["catalog.dirty"] and calls == []


def test_apply_update_failed_reset_changes_nothing(tmp_path):
    root, entry = _installed(tmp_path)
    plan, _ = _planned(root, entry)
    net, calls = _net()
    starter = net.starter

    def failing(argv, **kwargs):
        if "reset" in _subcommands([argv]):
            from kicad_lib_manager.procs import StreamOutcome

            return StreamOutcome(128, b"", ("fatal: could not reset",), False, False)
        return starter(argv, **kwargs)

    issues = ops.apply_update(root, plan, replace(net, starter=failing))
    assert [i.code for i in issues] == ["git.reset_failed"]
    assert manifest.load(root).find("Demo").commit == OLD


# -- Remove --------------------------------------------------------------------------------

REMOVE_FILES = {"symbols/Sym.kicad_sym": "(kicad_symbol_lib)", "fp/Fp.pretty/a.kicad_mod": "(footprint)", "models/m.step": "x" * 1000}


def _listed(tmp_path, id="Demo", **kwargs):
    return _installed(tmp_path, id, files=REMOVE_FILES, **kwargs)


def _staging_is_empty(root: Path) -> bool:
    staging = root / "ThirdParty" / ".staging"
    return not staging.exists() or not any(staging.iterdir())


def test_remove_plan_names_folder_size_libraries_vars(tmp_path):
    root, entry = _listed(tmp_path, vars={"DEMO_MODELS": "models"})
    folder = root / "ThirdParty" / "Demo"
    expected = sum(len(text.encode()) for text in REMOVE_FILES.values())

    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running("kicad.exe"))

    assert isinstance(plan, ops.RemovePlan)
    assert (plan.id, plan.name, plan.folder, plan.exists, plan.listed) == ("Demo", "Demo", folder, True, True)
    assert plan.size_bytes >= expected and plan.size_bytes == ops.size_on_disk(folder)
    assert plan.nicknames == ("Fp", "Sym") and plan.vars == ("DEMO_MODELS",)
    assert plan.kicad_open == ("kicad.exe",)


def test_remove_plan_takes_nicknames_from_the_scan(tmp_path):
    root, _ = _listed(tmp_path)
    scan = ScanResult(
        symbol_libs=[
            SymbolLibrary("Alpha", "ThirdParty/Demo/symbols/Alpha.kicad_sym", "Demo"),
            SymbolLibrary("Other", "ThirdParty/Other/symbols/Other.kicad_sym", "Other"),
            SymbolLibrary("Mine", "Custom/Symbols/Mine.kicad_sym", "Custom"),
        ],
        footprint_libs=[FootprintLibrary("Beta", "ThirdParty/Demo/fp/Beta.pretty", "Demo")],
    )
    plan = ops.plan_remove(root, "Demo", manifest.load(root), scan=scan, running=_running())
    assert plan.nicknames == ("Alpha", "Beta")


def test_remove_happy_path(tmp_path):
    root, _ = _listed(tmp_path)
    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())

    issues = ops.apply_remove(root, plan)

    assert not (root / "ThirdParty" / "Demo").exists() and _staging_is_empty(root)
    assert manifest.load(root).find("Demo") is None
    assert issues[0].code == "catalog.removed" and issues[0].severity is Severity.SUCCESS
    assert issues[0].text == (
        "Removed Demo from the catalog. Generate Tables drops its libraries from your KiCad library tables."
    )


def test_remove_rename_failure_keeps_everything(tmp_path, monkeypatch):
    root, _ = _listed(tmp_path)
    folder = root / "ThirdParty" / "Demo"
    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    before, record = _hashes(folder), (root / "catalog.json").read_bytes()
    real = os.replace

    def locked(src, dst, *args, **kwargs):
        if Path(src) == folder:
            raise PermissionError(13, "Access is denied")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", locked)
    monkeypatch.setattr(ops, "_RENAME_DELAY", 0)

    issues = ops.apply_remove(root, plan)

    assert [i.code for i in issues] == ["catalog.remove_failed"] and issues[0].severity is Severity.ERROR
    assert issues[0].text == KEPT_TEXT.format(name="Demo", reason="Access is denied", folder=folder.as_posix())
    assert _hashes(folder) == before and (root / "catalog.json").read_bytes() == record
    assert _staging_is_empty(root)


def test_remove_save_failure_moves_folder_back(tmp_path, monkeypatch):
    root, _ = _listed(tmp_path)
    folder = root / "ThirdParty" / "Demo"
    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    before, record = _hashes(folder), (root / "catalog.json").read_bytes()
    monkeypatch.setattr(manifest, "save", lambda root, mf: Issue(Severity.ERROR, "fs.write_failed", "Could not write catalog.json: disk full"))

    issues = ops.apply_remove(root, plan)

    assert issues[0].code == "catalog.remove_failed" and "The catalog entry was kept." in issues[0].text
    assert _hashes(folder) == before and (root / "catalog.json").read_bytes() == record
    assert _staging_is_empty(root)


def test_remove_delete_failure_leaves_a_leftover_for_clean_staging(tmp_path, monkeypatch):
    root, _ = _listed(tmp_path)
    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    real = fsutil.remove_tree
    monkeypatch.setattr(fsutil, "remove_tree", lambda *a, **k: Issue(Severity.ERROR, "fs.remove_failed", "Could not delete x: in use"))

    issues = ops.apply_remove(root, plan)

    assert issues[0].code == "catalog.removed"  # the library is gone from the catalog and from ThirdParty/Demo
    assert [i.code for i in issues if i.severity is Severity.WARNING] == ["catalog.remove_leftover"]
    assert not (root / "ThirdParty" / "Demo").exists() and manifest.load(root).find("Demo") is None
    (leftover,) = list((root / "ThirdParty" / ".staging").iterdir())
    assert leftover.name.startswith("Demo.removing.")

    monkeypatch.setattr(fsutil, "remove_tree", real)
    assert ops.clean_staging(root, older_than_s=0, now=lambda: 10**12) == []
    assert _staging_is_empty(root)


def test_remove_folder_already_gone(tmp_path):
    root, _ = _listed(tmp_path)
    assert fsutil.remove_tree(root / "ThirdParty" / "Demo", inside=root / "ThirdParty") is None

    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    assert (plan.exists, plan.listed, plan.size_bytes, plan.nicknames) == (False, True, 0, ())
    issues = ops.apply_remove(root, plan)

    assert issues[0].code == "catalog.removed" and manifest.load(root).find("Demo") is None


def test_remove_unlisted_folder(tmp_path):
    root = make_collection(tmp_path / "col")
    make_third_party(root, "Stray", REMOVE_FILES)
    assert not (root / "catalog.json").exists()

    plan = ops.plan_remove(root, "Stray", manifest.load(root), running=_running())
    assert (plan.listed, plan.exists, plan.vars) == (False, True, ())
    issues = ops.apply_remove(root, plan)

    assert not (root / "ThirdParty" / "Stray").exists() and _staging_is_empty(root)
    assert issues[0].code == "catalog.removed" and issues[0].severity is Severity.SUCCESS
    assert not (root / "catalog.json").exists()  # no catalog change (D-06)


def test_remove_keeps_the_other_entries(tmp_path):
    root, entry = _listed(tmp_path)
    other = replace(entry, id="Other")
    make_third_party(root, "Other", REMOVE_FILES)
    assert manifest.save(root, Manifest((entry, other))) is None

    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    ops.apply_remove(root, plan)

    assert [e.id for e in manifest.load(root).libraries] == ["Other"] and (root / "ThirdParty" / "Other").is_dir()


@pytest.mark.parametrize("target", ["Custom", ".staging", "..", "sub/dir"])
def test_remove_never_leaves_third_party(tmp_path, target):
    root, _ = _listed(tmp_path)
    (root / "Custom" / "Symbols" / "Atomic_Device.kicad_sym").write_text("(kicad_symbol_lib)", encoding="utf-8")
    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    own_before = _hashes(root / "Custom")
    forged = replace(plan, folder=root / "ThirdParty" / target if target != "Custom" else root / "Custom", id=target)

    issues = ops.apply_remove(root, forged)

    assert issues and all(i.severity is Severity.ERROR for i in issues)
    assert _hashes(root / "Custom") == own_before and (root / "ThirdParty" / "Demo").is_dir()
    assert manifest.load(root).find("Demo") is not None


def test_remove_never_touches_kicad_files(tmp_path):
    config = tmp_path / "kicad_config"
    (config / "3rdparty" / "pkg").mkdir(parents=True)
    (config / "3rdparty" / "pkg" / "lib.txt").write_text("pcm library", encoding="utf-8")
    (config / "installed_packages.json").write_text('{"packages": []}', encoding="utf-8")
    (config / "sym-lib-table").write_text('(sym_lib_table (lib (name "PCM_x")(uri "${KICAD9_3RD_PARTY}/x")))', encoding="utf-8")
    (config / "fp-lib-table").write_text("(fp_lib_table)", encoding="utf-8")
    before = _hashes(config)
    root, _ = _listed(tmp_path, vars={"DEMO_MODELS": "models"})
    own = root / "Custom" / "Symbols" / "Atomic_Device.kicad_sym"
    own.write_text("(kicad_symbol_lib)", encoding="utf-8")
    own_before = _hashes(root / "Custom")

    plan = ops.plan_remove(root, "Demo", manifest.load(root), running=_running())
    ops.apply_remove(root, plan)

    assert _hashes(config) == before and _hashes(root / "Custom") == own_before
    assert {p.name for p in root.iterdir()} <= {"Custom", "ThirdParty", "catalog.json"}


def test_size_on_disk_counts_files_and_follows_no_links(tmp_path):
    folder = tmp_path / "f"
    (folder / "a" / "b").mkdir(parents=True)
    (folder / "x.bin").write_bytes(b"1" * 10)
    (folder / "a" / "b" / "y.bin").write_bytes(b"1" * 25)
    assert ops.size_on_disk(folder) == 35
    assert ops.size_on_disk(tmp_path / "missing") == 0


def test_library_names_from_tree_paths():
    names = ops._library_names(
        [
            "symbols/A.kicad_sym",
            "fp/B.pretty/x.kicad_mod",
            "fp/B.pretty/y.kicad_mod",
            "fp/Empty.pretty/readme.txt",
            "README.md",
            "3d/m.step",
        ]
    )
    assert names == {"A", "B"}

