"""scripts/catalog/wurth_to_catalog.py: the one-off removal of the WurthElektronik submodule (Phase 17, CAT-12, D-24..D-27, D-30).

The quick tests cover the pure helpers and the argument errors; they start no git. The slow tests run the script
in process on a throwaway parent repository with two submodules (Custom and WurthElektronik/KiCad-Library) built from
local bare repositories, a ThirdParty/WurthElektronik clone, catalog.json and a scratch KiCad config folder. They
never touch a real checkout and never use the network.
"""

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import catalogfixtures
import pytest
from gitfixtures import make_superproject, remove_tree, requires_git

from kicad_lib_manager.catalog import manifest as catalog_manifest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "catalog" / "wurth_to_catalog.py"

OLD = "WurthElektronik/KiCad-Library"
TAG = "pre-wurth-catalog"
MESSAGE = "Replace the Wurth submodule by the catalog entry"


def _load():
    spec = importlib.util.spec_from_file_location("catalog_wurth_to_catalog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["catalog_wurth_to_catalog"] = module
    spec.loader.exec_module(module)
    return module


wurth = _load()


@pytest.fixture(autouse=True)
def _no_kicad_running(monkeypatch):
    # a KiCad open on the machine that runs the tests must not refuse the script
    monkeypatch.setattr(wurth, "kicad_running", lambda: [])


# -- the pure helpers (quick) ---------------------------------------------------------------------


def _row(table, name, uri, resolved, **extra):
    return {
        "table": table,
        "name": name,
        "type": "KiCad",
        "uri": uri,
        "resolved": resolved,
        "expanded": True,
        "exists": True,
        "disabled": False,
        **extra,
    }


def test_rewrite_snapshot():
    before = {
        "lib_root": "<LIB>",
        "vars": {"KICAD_LIB_GITHUB": "<LIB>", "CUSTOM_3DMODEL_DIR": "<LIB>/Custom/3DModels"},
        "entries": [
            _row("sym-lib-table", "WE_A", "${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library/symbols/A.kicad_sym",
                 "<LIB>/WurthElektronik/KiCad-Library/symbols/A.kicad_sym"),
            _row("fp-lib-table", "WE_A", "<LIB>/WurthElektronik/KiCad-Library/footprints/A.pretty",
                 "<LIB>/WurthElektronik/KiCad-Library/footprints/A.pretty"),
            _row("fp-lib-table", "WE_Root", "${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library",
                 "<LIB>/WurthElektronik/KiCad-Library"),
            _row("sym-lib-table", "Atomic_X", "${KICAD_LIB_GITHUB}/Custom/Symbols/Atomic_X.kicad_sym",
                 "<LIB>/Custom/Symbols/Atomic_X.kicad_sym"),
            _row("sym-lib-table", "Lookalike", "${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library-old/a.kicad_sym",
                 "<LIB>/WurthElektronik/KiCad-Library-old/a.kicad_sym"),
        ],
    }
    original = copy.deepcopy(before)
    moved = wurth.rewrite_snapshot(before)
    assert before == original  # the input is not changed
    rows = moved["entries"]
    assert rows[0]["uri"] == "${KICAD_LIB_GITHUB}/ThirdParty/WurthElektronik/symbols/A.kicad_sym"
    assert rows[0]["resolved"] == "<LIB>/ThirdParty/WurthElektronik/symbols/A.kicad_sym"
    assert rows[1]["uri"] == "<LIB>/ThirdParty/WurthElektronik/footprints/A.pretty"
    assert rows[2]["uri"] == "${KICAD_LIB_GITHUB}/ThirdParty/WurthElektronik"
    assert rows[2]["resolved"] == "<LIB>/ThirdParty/WurthElektronik"
    # every other field, every other entry and the rest of the snapshot stay as they were
    assert rows[0]["name"] == "WE_A" and rows[0]["exists"] is True and rows[0]["expanded"] is True
    assert rows[3] == original["entries"][3]
    assert rows[4] == original["entries"][4]
    assert moved["vars"] == original["vars"]


def test_rewrite_then_compare_is_identical_only_when_nothing_else_moved():
    before = {"entries": [_row("sym-lib-table", "WE_A", "${KICAD_LIB_GITHUB}/WurthElektronik/KiCad-Library/a.kicad_sym",
                               "<LIB>/WurthElektronik/KiCad-Library/a.kicad_sym")]}
    after = {"entries": [_row("sym-lib-table", "WE_A", "${KICAD_LIB_GITHUB}/ThirdParty/WurthElektronik/a.kicad_sym",
                              "<LIB>/ThirdParty/WurthElektronik/a.kicad_sym")]}
    assert wurth.uri_diff.compare(wurth.rewrite_snapshot(before), after) == []
    after["entries"][0]["name"] = "WE_B"
    assert wurth.uri_diff.compare(wurth.rewrite_snapshot(before), after)


def _kicad_common(folder: Path, value: str | None) -> bytes:
    folder.mkdir(parents=True)
    vars_ = {} if value is None else {"WE_3DMODEL_DIR": value}
    data = json.dumps({"environment": {"vars": vars_}}, indent=2).encode("utf-8")
    (folder / "kicad_common.json").write_bytes(data)
    return data


def test_stale_var_lines(tmp_path):
    base = tmp_path / "kicad"
    new = "C:/lib/ThirdParty/WurthElektronik/3dmodels"
    old = "C:\\lib\\WurthElektronik\\KiCad-Library\\3dmodels"
    written = {
        "10.0": _kicad_common(base / "10.0", new),
        "9.0": _kicad_common(base / "9.0", old),
        "8.0": _kicad_common(base / "8.0", None),
    }
    (base / "not-a-version").mkdir()
    lines = wurth.stale_var_lines(base, new)
    assert len(lines) == 1, lines
    assert "9.0" in lines[0] and old in lines[0] and new in lines[0]
    assert "10.0" not in lines[0] and "8.0" not in lines[0]
    # nothing is written
    for version, data in written.items():
        assert (base / version / "kicad_common.json").read_bytes() == data
    assert wurth.stale_var_lines(tmp_path / "missing", new) == []


def _snapshots(tmp_path):
    for name in ("before.json", "after.json"):
        (tmp_path / name).write_text(json.dumps({"entries": []}), encoding="utf-8")
    return str(tmp_path / "before.json"), str(tmp_path / "after.json")


def test_argument_errors_exit_2(tmp_path, capsys):
    before, after = _snapshots(tmp_path)
    repo = str(tmp_path)

    assert wurth.main([]) == 2  # --repo, --before and --after are required
    capsys.readouterr()

    assert wurth.main(["--repo", repo, "--before", before, "--after", after, "--apply"]) == 2
    assert "--backup-dir" in capsys.readouterr().out

    assert wurth.main(["--repo", repo, "--before", before, "--after", after, "--apply", "--backup-dir", str(tmp_path / "b")]) == 2
    assert "--message" in capsys.readouterr().out

    assert wurth.main(["--repo", repo, "--before", before, "--after", after, "--apply", "--backup-dir", str(tmp_path / "b"), "--message", "  "]) == 2
    assert "--message" in capsys.readouterr().out

    assert wurth.main(["--repo", str(tmp_path / "nope"), "--before", before, "--after", after]) == 2
    assert "not a folder" in capsys.readouterr().out

    assert wurth.main(["--repo", repo, "--before", str(tmp_path / "missing.json"), "--after", after]) == 2
    assert "snapshot" in capsys.readouterr().out

    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    assert wurth.main(["--repo", repo, "--before", before, "--after", str(tmp_path / "bad.json")]) == 2
    assert "snapshot" in capsys.readouterr().out

    (tmp_path / "other.json").write_text(json.dumps({"hello": 1}), encoding="utf-8")
    assert wurth.main(["--repo", repo, "--before", str(tmp_path / "other.json"), "--after", after]) == 2
    assert "snapshot" in capsys.readouterr().out


def test_help_names_the_apply_options(capsys):
    assert wurth.main(["--help"]) == 0
    out = capsys.readouterr().out
    for option in ("--apply", "--backup-dir", "--rollback-tag", "--config-dir", "--before", "--after", "--message"):
        assert option in out, option


def test_only_local_git_commands_can_run(tmp_path):
    # the one place git starts refuses a network or destructive command before anything runs
    for args in (
        ("clean", "-fd"),
        ("push", "origin", "main"),
        ("fetch",),
        ("pull",),
        ("clone", "x", "y"),
        ("ls-remote", "origin"),
        ("submodule", "update", "--remote"),
        ("submodule", "update", "--init"),
        ("reset", "--hard"),
    ):
        with pytest.raises(ValueError):
            wurth._git(tmp_path, *args)
    assert not {"clean", "push", "fetch", "pull", "clone", "ls-remote", "reset", "update-ref"} & set(wurth.ALLOWED_GIT)


def test_way_back_steps_name_the_tag_and_the_moved_data(tmp_path):
    repo, backup = tmp_path / "repo", tmp_path / "backup"
    module_dir = repo / ".git" / "modules" / "WurthElektronik"
    steps = wurth.way_back(repo, module_dir, backup, TAG, include_move=True)
    assert steps[0] == ("move", backup / "wurth-modules", module_dir)
    git_steps = [step[1:] for step in steps if step[0] == "git"]
    assert ("checkout", TAG, "--", ".gitmodules", ".gitignore", "README.md", "CLAUDE.md", OLD) in git_steps
    assert ("submodule", "update", "--init", "--", OLD) in git_steps
    assert not any(step[0] == "move" for step in wurth.way_back(repo, module_dir, backup, TAG, include_move=False))


# -- a throwaway collection with the Wurth submodule and its catalog replacement (slow) -----------------

WURTH_FILES = {
    "symbols/WE_Test.kicad_sym": catalogfixtures.SYMBOL_TEXT,
    "footprints/WE_Test.pretty/WE_R.kicad_mod": (
        '(footprint "WE_R"\n  (version 20240108)\n  (generator "pcbnew")\n  (layer "F.Cu")\n'
        '  (model "${WE_3DMODEL_DIR}/X.3dshapes/x.step"\n'
        "    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n)\n"
    ),
    "3dmodels/X.3dshapes/x.step": "ISO-10303-21;\nEND-ISO-10303-21;\n",
}
CUSTOM_SYMBOL = "Atomic_Battery_Management"


def _sym_table(entries: dict[str, str]) -> str:
    body = "".join(f'  (lib (name "{n}")(type "KiCad")(uri "{u}")(options "")(descr ""))\n' for n, u in entries.items())
    return f"(sym_lib_table\n  (version 7)\n{body})\n"


def _fp_table(entries: dict[str, str]) -> str:
    body = "".join(f'  (lib (name "{n}")(type "KiCad")(uri "{u}")(options "")(descr ""))\n' for n, u in entries.items())
    return f"(fp_lib_table\n  (version 7)\n{body})\n"


class WurthCollection:
    """A parent repo with Custom and WurthElektronik/KiCad-Library submodules plus the state after the catalog Add."""

    def __init__(self, root: Path, monkeypatch, *, real_templates: bool = False):
        self.root = root
        self.repos = make_superproject(root / "sp")
        self.parent = self.repos.parent
        self.git = lambda *args, check=True: self.repos.git(self.parent, *args, check=check)
        # git inside the script sees the fixture's own identity and no machine-wide settings
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(self.repos.root / "gitconfig"))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")

        self.bare, self.upstream_sha = catalogfixtures.make_upstream(root / "we", WURTH_FILES, branch="main")
        self.url = catalogfixtures.upstream_url(self.bare)
        self.git("submodule", "add", self.url, OLD)
        (self.parent / "notes.txt").write_text("notes\n", encoding="utf-8")
        (self.parent / "CLAUDE.md").write_text("old claude\n", encoding="utf-8")
        (self.parent / ".gitignore").write_text("old\n", encoding="utf-8")
        self.git("add", "--", "notes.txt", "CLAUDE.md", ".gitignore", ".gitmodules", OLD)
        self.git("commit", "-q", "-m", "Collection with the Wurth submodule")

        # what the app did: a clone in ThirdParty, the ignore line, catalog.json (all uncommitted)
        (self.parent / "ThirdParty").mkdir()
        self.clone = self.parent / "ThirdParty" / "WurthElektronik"
        self.repos.git(self.parent, "clone", "-q", self.url, str(self.clone))
        (self.parent / ".gitignore").write_text("old\nThirdParty/\n", encoding="utf-8")
        entry = catalog_manifest.CatalogEntry(
            id="WurthElektronik",
            url="https://github.com/WurthElektronik/KiCad-Library.git",
            branch="master",
            commit=self.upstream_sha,
            vars={"WE_3DMODEL_DIR": "3dmodels"},
            acknowledged=True,
            acknowledged_on="2026-11-27",
            added_on="2026-11-27",
        )
        assert catalog_manifest.save(self.parent, catalog_manifest.Manifest((entry,))) is None
        assert isinstance(catalog_manifest.load(self.parent), catalog_manifest.Manifest)

        # KiCad's config folders: 10.0 already holds the new value, 9.0 the old one (D-30)
        self.new_value = f"{self.parent.as_posix()}/ThirdParty/WurthElektronik/3dmodels"
        self.old_value = f"{self.parent}/WurthElektronik/KiCad-Library/3dmodels".replace("/", "\\")
        self.config = root / "kicad_config"
        _kicad_common(self.config / "10.0", self.new_value)
        _kicad_common(self.config / "9.0", self.old_value)

        # the two uri_diff snapshots (before the Add, after Generate Tables)
        lib = self.parent.as_posix()
        for name, where in (("before", OLD), ("after", "ThirdParty/WurthElektronik")):
            tables = root / f"tables_{name}"
            tables.mkdir()
            (tables / "sym-lib-table").write_text(
                _sym_table({
                    CUSTOM_SYMBOL: f"${{KICAD_LIB_GITHUB}}/Custom/Symbols/{CUSTOM_SYMBOL}.kicad_sym",
                    "WE_Test": f"${{KICAD_LIB_GITHUB}}/{where}/symbols/WE_Test.kicad_sym",
                }),
                encoding="utf-8",
            )
            (tables / "fp-lib-table").write_text(
                _fp_table({
                    "Atomic_Footprints": "${KICAD_LIB_GITHUB}/Custom/Footprints/Atomic_Footprints.pretty",
                    "WE_Test": f"${{KICAD_LIB_GITHUB}}/{where}/footprints/WE_Test.pretty",
                }),
                encoding="utf-8",
            )
            snap = wurth.uri_diff.snapshot(tables, variables={"KICAD_LIB_GITHUB": lib}, lib_root=lib)
            assert snap["missing"] == [], snap["missing"]
            (root / f"{name}.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
        self.before, self.after = root / "before.json", root / "after.json"
        self.backup = root / "backup"
        self.templates = root / "templates"
        self.templates.mkdir()
        (self.templates / "README.md").write_text("# Collection\n\nThirdParty and catalog.json.\n", encoding="utf-8")
        (self.templates / "CLAUDE.md").write_text("# CLAUDE\n\ncatalog.json lists ThirdParty.\n", encoding="utf-8")
        if not real_templates:
            monkeypatch.setattr(wurth, "TEMPLATES", self.templates)

    def args(self, *extra: str, apply: bool = False, backup: Path | None = None) -> list[str]:
        argv = ["--repo", str(self.parent), "--before", str(self.before), "--after", str(self.after),
                "--config-dir", str(self.config)]
        if apply:
            argv += ["--apply", "--backup-dir", str(backup or self.backup), "--message", MESSAGE]
        elif backup is not None:
            argv += ["--backup-dir", str(backup)]
        return [*argv, *extra]

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def state(self) -> dict:
        files = sorted(p.relative_to(self.parent).as_posix() for p in self.parent.rglob("*") if ".git" not in p.parts and p.is_file())
        return {
            "head": self.head(),
            "status": self.git("status", "--porcelain"),
            "index": self.git("ls-files", "-s"),
            "tags": self.git("tag"),
            "gitmodules": (self.parent / ".gitmodules").read_bytes(),
            "files": files,
            "modules": sorted(p.name for p in (self.parent / ".git" / "modules").iterdir()),
            "backup": self.backup.exists(),
        }


@pytest.mark.slow
@requires_git
def test_fixture_state_passes_the_plan(tmp_path, monkeypatch):
    coll = WurthCollection(tmp_path, monkeypatch)
    found = wurth.plan(coll.parent, json.loads(coll.before.read_text("utf-8")), json.loads(coll.after.read_text("utf-8")),
                       config_dir=coll.config, backup_dir=coll.backup, tag=TAG)
    assert found.problems == []
    assert found.module_dir == coll.parent / ".git" / "modules" / "WurthElektronik"
    assert found.head == coll.head()
    assert len(found.custom_commit) == 40
    assert len(found.stale_lines) == 1 and "9.0" in found.stale_lines[0]


@pytest.mark.slow
@requires_git
def test_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch)
    before = coll.state()
    rc = wurth.main(coll.args(backup=coll.backup))
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "dry run" in out.lower()
    # every step of the sequence, in the order it will run
    needles = ["git bundle create", "git bundle verify", f"git tag {TAG}", "git submodule deinit", "git rm",
               "move the module data", "write README.md", "git add", "git commit"]
    positions = [out.index(needle) for needle in needles]
    assert positions == sorted(positions), positions
    assert "--message" in out  # the apply command line is shown
    # the doc changes, the D-30 line and the way back
    assert "README.md" in out and "--- " in out and "+++ " in out
    assert "KiCad 9.0" in out and coll.old_value in out and coll.new_value in out
    assert f"checkout {TAG}" in out and "submodule update --init" in out
    assert coll.state() == before


@pytest.mark.slow
@requires_git
def test_refusals(tmp_path, monkeypatch, capsys):
    def attempt(name: str, reason: str, *, prepare=None, backup=None, flags=None, apply=True):
        monkeypatch.setattr(wurth, "kicad_running", lambda: [])
        coll = WurthCollection(tmp_path / name, monkeypatch)
        if prepare is not None:
            prepare(coll)
        target = backup(coll) if backup is not None else None
        before = coll.state()
        argv = flags(coll) if flags is not None else coll.args(apply=apply, backup=target)
        rc = wurth.main(argv)
        out = capsys.readouterr().out
        assert rc == 1, f"{name}: {out}"
        assert reason in out, f"{name}: {out}"
        assert "nothing was written" in out, f"{name}: {out}"
        assert coll.state() == before, name
        assert target is None or not target.exists(), name

    attempt("kicad", "KiCad is running", prepare=lambda c: monkeypatch.setattr(wurth, "kicad_running", lambda: ["kicad"]))
    attempt("branch", "not on main", prepare=lambda c: c.git("switch", "-q", "-c", "other"))
    attempt("dirty", "uncommitted tracked changes", prepare=lambda c: (c.parent / "notes.txt").write_text("changed\n", encoding="utf-8"))
    attempt("untracked", "untracked", prepare=lambda c: (c.parent / "stray.txt").write_text("x\n", encoding="utf-8"))
    attempt("not_ignored", "ThirdParty is not ignored", prepare=lambda c: (c.parent / ".gitignore").write_text("old\n", encoding="utf-8"))
    attempt("tag_exists", "already exists", prepare=lambda c: c.git("tag", TAG))

    def wrong_var(c):
        _kicad_common_rewrite(c.config / "10.0", c.old_value)

    attempt("var", "WE_3DMODEL_DIR", prepare=wrong_var)
    attempt("var_slashes", "WE_3DMODEL_DIR", prepare=lambda c: _kicad_common_rewrite(c.config / "10.0", c.new_value.replace("/", "\\")))
    def no_config(c):
        shutil.rmtree(c.config / "10.0")
        shutil.rmtree(c.config / "9.0")

    attempt("no_config", "no KiCad configuration folder", prepare=no_config)

    def no_entry(c):
        assert catalog_manifest.save(c.parent, catalog_manifest.Manifest(())) is None

    attempt("no_entry", "no WurthElektronik entry", prepare=no_entry)

    def no_catalog(c):
        (c.parent / "catalog.json").unlink()

    attempt("no_catalog", "no WurthElektronik entry", prepare=no_catalog)

    attempt("no_clone_git", ".git", prepare=lambda c: remove_tree(c.clone / ".git"))

    def odd_config(c):
        with open(c.clone / ".git" / "config", "a", encoding="utf-8") as handle:
            handle.write("[core]\n\tfsmonitor = evil\n")

    attempt("odd_config", "unexpected git settings", prepare=odd_config)

    def changed_snapshot(c):
        data = json.loads(c.after.read_text("utf-8"))
        for row in data["entries"]:
            if row["name"] == "WE_Test" and row["table"] == "sym-lib-table":
                row["name"] = "WE_Other"
        c.after.write_text(json.dumps(data), encoding="utf-8")

    attempt("snapshot", "snapshots differ", prepare=changed_snapshot)

    def missing_after(c):
        data = json.loads(c.after.read_text("utf-8"))
        data["entries"][-1]["exists"] = False
        c.after.write_text(json.dumps(data), encoding="utf-8")

    attempt("missing_after", "missing", prepare=missing_after)

    def unrelated_snapshot(c):
        c.before.write_text(json.dumps({"entries": []}), encoding="utf-8")
        c.after.write_text(json.dumps({"entries": []}), encoding="utf-8")

    attempt("empty_snapshots", "holds no", prepare=unrelated_snapshot)
    attempt("model", "3D model", prepare=lambda c: (c.clone / "3dmodels" / "X.3dshapes" / "x.step").unlink())

    def other_repo(c):
        c.repos.git(c.root, "init", "-q", str(c.root / "other"))

    attempt("backup_in_worktree", "git work tree", prepare=other_repo, backup=lambda c: c.root / "other" / "backup")
    attempt("backup_in_repo", "inside the repository", backup=lambda c: c.parent / "backup")

    def bundle_exists(c):
        c.backup.mkdir()
        (c.backup / "pre-wurth.bundle").write_bytes(b"x")

    def modules_exist(c):
        (c.backup / "wurth-modules").mkdir(parents=True)

    attempt("bundle_exists", "already exists", prepare=bundle_exists)
    attempt("modules_exist", "already exists", prepare=modules_exist)


def _kicad_common_rewrite(folder: Path, value: str) -> None:
    (folder / "kicad_common.json").write_text(json.dumps({"environment": {"vars": {"WE_3DMODEL_DIR": value}}}), encoding="utf-8")


def _tree_modes(coll: WurthCollection) -> dict[str, tuple[str, str]]:
    found = {}
    for line in coll.git("ls-tree", "-r", "HEAD").splitlines():
        meta, _, path = line.partition("\t")
        mode, _, sha = meta.split(" ")
        found[path] = (mode, sha)
    return found


@pytest.mark.slow
@requires_git
def test_apply_converts(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch)
    old_head = coll.head()
    old_tree = _tree_modes(coll)
    custom_before = old_tree["Custom"]
    wurth_sha = old_tree[OLD][1]
    clone_files = sorted(p.relative_to(coll.clone).as_posix() for p in coll.clone.rglob("*") if ".git" not in p.parts and p.is_file())

    rc = wurth.main(coll.args(apply=True))
    out = capsys.readouterr().out
    assert rc == 0, out

    # the way back first: a verified bundle, a lightweight tag at the old HEAD
    verified = subprocess.run(["git", "-C", str(coll.parent), "bundle", "verify", str(coll.backup / "pre-wurth.bundle")],
                              capture_output=True, env=coll.repos.env)
    assert verified.returncode == 0, verified.stderr
    assert coll.git("rev-parse", f"refs/tags/{TAG}").strip() == old_head
    assert coll.git("cat-file", "-t", TAG).strip() == "commit"  # lightweight

    # the submodule is gone from the tree, the module list and .gitmodules; Custom is as it was
    tree = _tree_modes(coll)
    assert OLD not in tree and not any(path.startswith("WurthElektronik") for path in tree)
    assert tree["Custom"] == custom_before
    assert "WurthElektronik" not in (coll.parent / ".gitmodules").read_text("utf-8")
    assert not (coll.parent / "WurthElektronik").exists()

    # the module data was moved, not deleted
    moved = coll.backup / "wurth-modules"
    assert (moved / "KiCad-Library" / "HEAD").is_file()
    assert not (coll.parent / ".git" / "modules" / "WurthElektronik").exists()
    assert coll.git("-C", str(moved / "KiCad-Library"), "rev-parse", "HEAD").strip() == wurth_sha

    # one commit with the given message holding the five files and the gitlink removal
    assert coll.git("log", "-1", "--format=%s").strip() == MESSAGE
    assert coll.git("rev-parse", "HEAD~1").strip() == old_head
    changed = {}
    for line in coll.git("show", "--name-status", "--format=", "HEAD").splitlines():
        status, _, path = line.partition("\t")
        changed[path] = status
    assert changed == {".gitignore": "M", "catalog.json": "A", ".gitmodules": "M", "README.md": "M", "CLAUDE.md": "M", OLD: "D"}
    assert (coll.parent / "README.md").read_text("utf-8") == (coll.templates / "README.md").read_text("utf-8")
    assert (coll.parent / "CLAUDE.md").read_text("utf-8") == (coll.templates / "CLAUDE.md").read_text("utf-8")

    # the post-checks held and the clone in ThirdParty was not touched
    assert coll.git("status", "--porcelain").strip() == ""
    ignored = subprocess.run(["git", "-C", str(coll.parent), "check-ignore", "-q", "ThirdParty"], capture_output=True, env=coll.repos.env)
    assert ignored.returncode == 0
    assert [line.split()[1] for line in coll.git("submodule", "status").splitlines()] == ["Custom"]
    assert sorted(p.relative_to(coll.clone).as_posix() for p in coll.clone.rglob("*") if ".git" not in p.parts and p.is_file()) == clone_files
    for text in ("checkout " + TAG, "submodule update --init", "wurth-modules"):
        assert text in out, text
    assert "KiCad 9.0" in out
    # the older config is only named, never edited
    assert json.loads((coll.config / "9.0" / "kicad_common.json").read_text("utf-8"))["environment"]["vars"]["WE_3DMODEL_DIR"] == coll.old_value


@pytest.mark.slow
@requires_git
def test_apply_stops_at_the_first_failure_and_prints_the_way_back(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch)
    old_head = coll.head()
    real = wurth._git

    def failing(repo, *args, **kwargs):
        if args[:2] == ("submodule", "deinit"):
            return subprocess.CompletedProcess(args, 1, b"", b"boom from git")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(wurth, "_git", failing)
    rc = wurth.main(coll.args(apply=True))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "boom from git" in out
    assert f"checkout {TAG}" in out
    # the steps before the failure ran, the ones after did not
    assert (coll.backup / "pre-wurth.bundle").is_file()
    assert coll.git("rev-parse", f"refs/tags/{TAG}").strip() == old_head
    assert coll.head() == old_head
    assert not (coll.backup / "wurth-modules").exists()
    assert (coll.parent / ".git" / "modules" / "WurthElektronik").is_dir()
    assert OLD in _tree_modes(coll)


@pytest.mark.slow
@requires_git
def test_apply_then_way_back_restores_the_submodule(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch)
    old_tree = _tree_modes(coll)
    old_gitmodules = (coll.parent / ".gitmodules").read_bytes()
    model = Path(OLD) / "3dmodels" / "X.3dshapes" / "x.step"

    assert wurth.main(coll.args(apply=True)) == 0
    out = capsys.readouterr().out
    assert not (coll.parent / OLD).exists()

    # run the steps the script prints, with no network allowed (protocol.file disabled)
    steps = wurth.way_back(coll.parent, coll.parent / ".git" / "modules" / "WurthElektronik", coll.backup, TAG, include_move=True)
    assert steps
    for step in steps:
        if step[0] == "move":
            _, source, target = step
            assert str(source) in out and str(target) in out
            shutil.move(str(source), str(target))
        else:
            args = step[1:]
            line = "git -C " + str(coll.parent) + " " + " ".join(args)
            assert line in out, line
            done = subprocess.run(
                ["git", "-C", str(coll.parent), "-c", "protocol.file.allow=never", *args],
                capture_output=True,
                env=coll.repos.env,
                timeout=120,
            )
            assert done.returncode == 0, (args, done.stderr.decode("utf-8", "replace"))

    # the submodule is back at its old commit, checked out from the local objects
    assert coll.git("ls-files", "-s", "--", OLD).split()[0] == "160000"
    assert coll.git("ls-files", "-s", "--", OLD).split()[1] == old_tree[OLD][1]
    status = coll.git("submodule", "status", "--", OLD).strip()
    assert status.startswith(old_tree[OLD][1]), status  # no '-' (not initialised) and no '+' (moved)
    assert (coll.parent / model).is_file()
    assert (coll.parent / ".gitmodules").read_bytes() == old_gitmodules
    assert (coll.parent / ".gitignore").read_text("utf-8") == "old\n"
    assert (coll.parent / "CLAUDE.md").read_text("utf-8") == "old claude\n"
    assert _tree_modes(coll)["Custom"] == old_tree["Custom"]


# -- the collection doc templates (Task 2) ----------------------------------------------------------------

TEMPLATES = ROOT / "scripts" / "catalog" / "collection"
PHASE_16_TEMPLATES = ROOT / "scripts" / "split" / "collection"


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_templates_describe_the_catalog_layout():
    for name in ("README.md", "CLAUDE.md"):
        text = _template(name)
        assert "ThirdParty" in text, name
        assert "catalog.json" in text, name
        # the Phase 16 templates carry both of these; the layout after the conversion has neither
        assert "submodule add" not in text, name
        assert "--recurse-submodules" not in text, name
        assert "submodule update --remote" not in text, name
        assert "Custom" in text and "KICAD_LIB_GITHUB" in text and "CUSTOM_3DMODEL_DIR" in text and "WE_3DMODEL_DIR" in text, name
    # the Phase 16 ones really do, so the checks above can fail
    old = (PHASE_16_TEMPLATES / "README.md").read_text(encoding="utf-8") + (PHASE_16_TEMPLATES / "CLAUDE.md").read_text(encoding="utf-8")
    assert "submodule add" in old and "--recurse-submodules" in old
    claude = _template("CLAUDE.md")
    for token in ("Atomic_<", "Atomic_Footprints.pretty", "atomic rule", "MPN", "Manufacturer", "Datasheet", "Description",
                  "Ctrl+Shift+L", "Problem: folder missing", "Reinstall", "kicad-lib-manager"):
        assert token in claude, token
    assert "## Adding a Third-Party Library" in claude
    assert "## Adding a New Library Submodule" not in claude
    readme = _template("README.md")
    assert "Custom` is the only submodule" in readme
    assert "KiCad-Library" not in readme  # the old nested submodule folder is gone from the layout
    assert "Problem: folder missing" in readme


def test_templates_hold_no_workstation_path():
    import re

    # assembled from pieces so this file does not trip the pre-publish scan itself
    drive = "[A-Za-z]:"
    folders = "(?:" + "Us" + "ers|Git_" + "Repo_Clones)"
    pattern = re.compile(drive + "[" + chr(92) + "/]+" + folders + "[" + chr(92) + "/]", re.IGNORECASE)
    for name in ("README.md", "CLAUDE.md"):
        assert not pattern.search(_template(name)), name


def test_doc_diff_shows_changes_only():
    nl, cr = chr(10), chr(13)
    same = 'a' + nl + 'b' + nl
    assert wurth.doc_diff(same, same, 'README.md') == []
    assert wurth.doc_diff('a' + cr + nl + 'b' + cr + nl, same, 'README.md') == []  # line endings alone are not a change
    diff = wurth.doc_diff('a' + nl + 'old' + nl, 'a' + nl + 'new' + nl, 'README.md')
    assert diff[0] == '--- a/README.md' and diff[1] == '+++ b/README.md (template)'
    assert '-old' in diff and '+new' in diff


@pytest.mark.slow
@requires_git
def test_dry_run_shows_a_diff_for_each_doc_that_differs(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch, real_templates=True)
    (coll.parent / "README.md").write_text(_template("README.md"), encoding="utf-8")
    coll.git("add", "--", "README.md")
    coll.git("commit", "-q", "-m", "README already matches")
    before = coll.state()
    assert wurth.main(coll.args(backup=coll.backup)) == 0
    out = capsys.readouterr().out
    assert "--- a/CLAUDE.md" in out and "+++ b/CLAUDE.md (template)" in out  # the fixture's old CLAUDE.md differs
    assert "-old claude" in out and "+## Adding a Third-Party Library" in out
    assert "--- a/README.md" not in out
    assert "README.md already matches the template" in out
    assert coll.state() == before


@pytest.mark.slow
@requires_git
def test_apply_writes_the_real_templates(tmp_path, monkeypatch, capsys):
    coll = WurthCollection(tmp_path, monkeypatch, real_templates=True)
    assert wurth.main(coll.args(apply=True)) == 0
    capsys.readouterr()
    assert (coll.parent / "README.md").read_bytes() == (TEMPLATES / "README.md").read_bytes()
    assert (coll.parent / "CLAUDE.md").read_bytes() == (TEMPLATES / "CLAUDE.md").read_bytes()
    assert "ThirdParty" in coll.git("show", "HEAD:CLAUDE.md")
