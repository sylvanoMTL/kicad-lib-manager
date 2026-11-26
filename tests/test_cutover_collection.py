"""scripts/split/cutover_collection.py and the collection templates (Phase 16, D-01, D-07, D-21).

The quick tests read the three templates and the script's constants. The slow tests run the script
in a throwaway superproject (a parent repo with two gitlinks) and never touch a real checkout.
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from gitfixtures import make_superproject, remote_refs, requires_git

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "split" / "cutover_collection.py"
TEMPLATES = ROOT / "scripts" / "split" / "collection"

WURTH = "WurthElektronik/KiCad-Library"


def _load():
    spec = importlib.util.spec_from_file_location("split_cutover_collection", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["split_cutover_collection"] = module
    spec.loader.exec_module(module)
    return module


cutover = _load()


def _text(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _headings(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if line.startswith("## ")}


# -- the templates and constants (quick) ----------------------------------------------------------


def test_collection_claude_md_carries_the_conventions():
    text = _text("CLAUDE.md")
    for heading in (
        "## Collection Overview",
        "## Repository Structure",
        "## KiCad Path Variables",
        "## Library Naming Convention",
        "## Importing Parts",
        "## Adding a New Library Submodule",
        "## Git Workflow",
    ):
        assert heading in _headings(text), heading
    for token in (
        "Atomic_<",
        "Atomic_Footprints.pretty",
        "${CUSTOM_3DMODEL_DIR}",
        "atomic rule",
        "MPN",
        "Manufacturer",
        "Datasheet",
        "Description",
        "KICAD_LIB_GITHUB",
        "CUSTOM_3DMODEL_DIR",
        "WE_3DMODEL_DIR",
        "kicad-lib-manager",
    ):
        assert token in text, token
    # the v1 naming scheme is gone for good
    assert "<Type>_<SubCategory>_<Manufacturer>" not in text
    assert "Symbol and footprint folder names must match" not in text


def test_collection_readme_sections():
    text = _text("README.md")
    for heading in (
        "## Contents",
        "## Setup",
        "## KiCad configuration",
        "## Working with the library manager",
        "## Naming and the atomic rule",
        "## Licences",
    ):
        assert heading in _headings(text), heading
    assert "--recurse-submodules" in text
    assert "kicad-lib-manager" in text


def test_collection_gitignore():
    lines = [line.strip() for line in _text("gitignore").splitlines()]
    for wanted in ("sym-lib-table", "fp-lib-table", "env/", "*_backup_*", "downloaded_examples/*"):
        assert wanted in lines, wanted
    assert not any(line.startswith("!downloaded_examples") for line in lines)


def test_templates_hold_no_workstation_path():
    # assembled from pieces so this file does not trip the pre-publish scan itself
    drive = "[A-Za-z]:"
    folders = "(?:" + "Us" + "ers|Git_" + "Repo_Clones)"
    pattern = re.compile(drive + r"[\\/]+" + folders + r"[\\/]", re.IGNORECASE)
    for name in ("README.md", "CLAUDE.md", "gitignore"):
        assert not pattern.search(_text(name)), name


def test_remove_list_never_names_a_kept_path():
    remove = set(cutover.REMOVE)
    assert not remove & set(cutover.KEEP)
    assert not remove & set(cutover.UNTRACK)
    assert "." not in remove
    assert "" not in remove
    assert all("/" not in entry and not entry.startswith("..") for entry in remove)
    # the two gitlinks and the module file are kept, and every written file has a template
    assert {"Custom", WURTH, ".gitmodules", ".gitignore"} <= set(cutover.KEEP)
    for target, template in cutover.WRITE.items():
        assert (TEMPLATES / template).is_file(), target
    assert cutover.UNTRACK == ("downloaded_examples",)
    assert set(cutover.CACHE_NAMES) == {"__pycache__", ".pytest_cache"}


def test_cache_only_rule():
    assert cutover.is_cache_path("kicad_lib_manager/__pycache__/a.pyc")
    assert cutover.is_cache_path(".pytest_cache/v/cache/x")
    assert not cutover.is_cache_path("tests/notes.txt")
    assert not cutover.is_cache_path("tests/__pycache__x/a.pyc")


# -- the script in a throwaway superproject (slow) -------------------------------------------------

CODE_FILES = {
    "kicad_lib_manager/a.py": "print('app')\n",
    "kicad_lib_manager.py": "print('entry')\n",
    "tests/t.py": "def test_x():\n    pass\n",
    "scripts/s.py": "print('s')\n",
    ".githooks/commit-msg": "#!/bin/sh\n",
    ".github/workflows/ci.yml": "name: ci\n",
    "pyproject.toml": "[tool.pytest.ini_options]\n",
    "requirements.txt": "PySide6\n",
    "requirements-dev.txt": "pytest\n",
    ".planning/p.md": "plan\n",
    "reports/r.md": "report\n",
    "research_notes/n.md": "notes\n",
    ".gitattributes": "* text=auto\n",
    "README.md": "old readme\n",
    "CLAUDE.md": "old claude\n",
    "LICENSE": "licence\n",
    ".gitignore": "old\n",
    "downloaded_examples/ul.zip": "zip bytes\n",
}


class Collection:
    """A superproject with the Custom and WurthElektronik gitlinks and the code files committed."""

    def __init__(self, root: Path, *, wurth: bool = True, extra: dict[str, str] | None = None):
        self.repos = make_superproject(root)
        self.parent = self.repos.parent
        git = self.repos.git
        if wurth:
            git(self.parent, "submodule", "add", self.repos.custom_remote.as_posix(), WURTH)
        files = {**CODE_FILES, **(extra or {})}
        for rel, text in files.items():
            path = self.parent / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        git(self.parent, "add", "--", *files)
        git(self.parent, "commit", "-q", "-m", "Collection with code")
        self.files = files

    def git(self, *args: str, check: bool = True) -> str:
        return self.repos.git(self.parent, *args, check=check)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def gitlinks(self) -> dict[str, str]:
        found = {}
        for line in self.git("ls-tree", "-r", "HEAD").splitlines():
            meta, _, path = line.partition("\t")
            mode, _, sha = meta.split(" ")
            if mode == "160000":
                found[path] = sha
        return found

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.parent), *args],
            env={**self.repos.env, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )


@pytest.mark.slow
@requires_git
def test_dry_run_writes_nothing(tmp_path):
    coll = Collection(tmp_path)
    assert coll.git("status", "--porcelain").strip() == ""
    head, links = coll.head(), coll.gitlinks()
    assert set(links) == {"Custom", WURTH}
    before_files = sorted(p.relative_to(coll.parent).as_posix() for p in coll.parent.rglob("*") if ".git" not in p.parts and p.is_file())

    done = coll.run()
    out = done.stdout
    assert done.returncode == 0, out + done.stderr
    for entry in cutover.REMOVE:
        if any(rel == entry or rel.startswith(entry + "/") for rel in coll.files):
            assert entry in out, entry
    assert "downloaded_examples" in out
    for written in ("README.md", "CLAUDE.md", ".gitignore"):
        assert written in out
    for path, sha in links.items():
        assert path in out
        assert sha in out
    assert "dry run" in out.lower()

    assert coll.head() == head
    assert coll.git("status", "--porcelain").strip() == ""
    after_files = sorted(p.relative_to(coll.parent).as_posix() for p in coll.parent.rglob("*") if ".git" not in p.parts and p.is_file())
    assert after_files == before_files


@pytest.mark.slow
@requires_git
def test_apply_keeps_gitlinks_and_untracks_samples(tmp_path):
    coll = Collection(tmp_path)
    head, links = coll.head(), coll.gitlinks()
    gitmodules = (coll.parent / ".gitmodules").read_bytes()
    remote = coll.git("config", "--get", "remote.origin.url").strip()
    refs = remote_refs(coll.repos)
    # data that must survive: an untracked venv, a cache-only leftover and a leftover holding a real file
    (coll.parent / "env").mkdir()
    (coll.parent / "env" / "keep.txt").write_text("venv\n", encoding="utf-8")
    (coll.parent / "kicad_lib_manager" / "__pycache__").mkdir()
    (coll.parent / "kicad_lib_manager" / "__pycache__" / "a.pyc").write_bytes(b"\0")
    (coll.parent / "tests" / "notes.txt").write_text("keep me\n", encoding="utf-8")

    done = coll.run("--apply")
    assert done.returncode == 0, done.stdout + done.stderr

    listed = {line.partition("\t")[2] for line in coll.git("ls-tree", "-r", "HEAD").splitlines()}
    assert listed == {".gitignore", ".gitmodules", "CLAUDE.md", "README.md", "Custom", WURTH}
    assert coll.gitlinks() == links
    assert (coll.parent / ".gitmodules").read_bytes() == gitmodules
    assert coll.git("config", "--get", "remote.origin.url").strip() == remote
    assert coll.head() != head
    assert coll.git("log", "-1", "--format=%s").strip() == cutover.DEFAULT_MESSAGE
    assert coll.git("status", "--porcelain", "--untracked-files=no").strip() == ""
    assert remote_refs(coll.repos) == refs

    # the collection's own docs replaced the old ones
    assert "## Library Naming Convention" in (coll.parent / "CLAUDE.md").read_text(encoding="utf-8")
    assert "## Contents" in (coll.parent / "README.md").read_text(encoding="utf-8")
    assert "downloaded_examples/*" in (coll.parent / ".gitignore").read_text(encoding="utf-8")

    # the vendor sample stays on disk, untracked and ignored
    zip_path = coll.parent / "downloaded_examples" / "ul.zip"
    assert zip_path.read_text(encoding="utf-8") == "zip bytes\n"
    assert coll.git("ls-files", "--", "downloaded_examples").strip() == ""
    ignored = subprocess.run(
        ["git", "-C", str(coll.parent), "check-ignore", "-q", "downloaded_examples/ul.zip"],
        env=coll.repos.env,
        capture_output=True,
    )
    assert ignored.returncode == 0

    # untracked data is untouched; a cache-only leftover folder goes, one with a real file is reported and kept
    assert (coll.parent / "env" / "keep.txt").read_text(encoding="utf-8") == "venv\n"
    assert not (coll.parent / "kicad_lib_manager").exists()
    assert (coll.parent / "tests" / "notes.txt").is_file()
    assert "tests/notes.txt" in done.stdout
    for name in ("pyproject.toml", "scripts", ".planning", "LICENSE", ".gitattributes"):
        assert not (coll.parent / name).exists(), name


def test_templates_inside_the_repository_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(cutover, "TEMPLATES", tmp_path / "collection")
    monkeypatch.setattr(cutover, "_git", lambda repo, *a: subprocess.CompletedProcess(a, 1, b"", b""))
    found = cutover.plan(tmp_path)
    assert any("inside the repository" in problem for problem in found.problems), found.problems


@pytest.mark.slow
@requires_git
def test_refusals(tmp_path):
    def attempt(name: str, reason: str, *, prepare=None, wurth: bool = True, extra=None, flags=("--apply",)):
        coll = Collection(tmp_path / name, wurth=wurth, extra=extra)
        if prepare is not None:
            prepare(coll)
        head = coll.head()
        status = coll.git("status", "--porcelain")
        present = sorted(p.relative_to(coll.parent).as_posix() for p in coll.parent.rglob("*") if ".git" not in p.parts and p.is_file())
        done = coll.run(*flags)
        assert done.returncode == 1, f"{name}: {done.stdout}{done.stderr}"
        assert reason in done.stdout, f"{name}: {done.stdout}"
        assert coll.head() == head
        assert coll.git("status", "--porcelain") == status
        assert sorted(p.relative_to(coll.parent).as_posix() for p in coll.parent.rglob("*") if ".git" not in p.parts and p.is_file()) == present

    attempt("dirty", "uncommitted", prepare=lambda c: (c.parent / "pyproject.toml").write_text("changed\n", encoding="utf-8"))
    attempt("branch", "not on main", prepare=lambda c: c.git("switch", "-c", "other"))
    attempt("no_wurth", "gitlink", wurth=False)
    attempt("unexpected", "extra/x.txt", extra={"extra/x.txt": "x\n"})
    # the dry run refuses too
    attempt("dry_dirty", "uncommitted", prepare=lambda c: (c.parent / "pyproject.toml").write_text("changed\n", encoding="utf-8"), flags=())
