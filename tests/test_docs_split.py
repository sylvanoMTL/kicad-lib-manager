"""Doc checks for the tool repo (SPLIT-05, SPLIT-06, SPLIT-08): LICENSE, README.md and CLAUDE.md say what
the shipped code does, so the docs and the app cannot drift apart. Reads only the tracked Markdown and text
files and two main_window text constants -- never a library collection. A heading the checks expect but cannot
find fails with an assertion message naming it, never a ValueError.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Built from pieces so this file never matches the pre-publish scan's own path rules
_PATH_FOLDERS = "|".join(("Users", "Git_Repo_Clones"))
_WORKSTATION_PATH = re.compile(r"(?i)\b[a-z]:[\\/]+(?:" + _PATH_FOLDERS + r")[\\/]")
_GIT_BASH_PATH = re.compile(r"(?i)(?<![\w.])/[a-z]/(?:" + _PATH_FOLDERS + r")/")
_AT_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _heading_at(text: str, heading: str, start: int = 0) -> re.Match | None:
    """The first line of `text` at or after `start` that is exactly `heading`."""
    return re.compile(r"(?m)^" + re.escape(heading) + r"[ \t]*$").search(text, start)


def _section(text: str, heading: str, *other_headings: str) -> str:
    """The text between `heading` and the next of `other_headings` (or end of file)."""
    found = _heading_at(text, heading)
    assert found is not None, f"missing heading {heading!r}"
    rest = text[found.end():]
    cut = len(rest)
    for other in other_headings:
        match = _heading_at(rest, other)
        if match is not None:
            cut = min(cut, match.start())
    return rest[:cut]


def test_missing_heading_fails_with_its_name():
    with pytest.raises(AssertionError) as caught:
        _section("x", "## Nope")
    assert "## Nope" in str(caught.value)


def test_license_is_mit_for_the_handle():
    text = _read("LICENSE")
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 sylvanoMTL" in text
    assert "Permission is hereby granted, free of charge" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text


README_HEADINGS = (
    "## Install",
    "## First run",
    "## Choosing or creating a collection",
    "## Development",
    "## Libraries and licences",
    "## Licence",
)


def test_readme_covers_install_and_first_run():
    text = _read("README.md")
    for heading in README_HEADINGS:
        assert _heading_at(text, heading) is not None, f"README.md is missing heading {heading!r}"

    install = _section(text, "## Install", *README_HEADINGS)
    for token in ("py -3.14 -m venv env", "requirements.txt"):
        assert token in install, f"Install is missing {token!r}"

    first_run = _section(text, "## First run", *README_HEADINGS)
    for token in (
        "Set Up Your Library Folder",
        "Use KiCad's Folder",
        "Open Library Collection...",
        "New Library Collection...",
        "KICAD_LIB_GITHUB",
        "CUSTOM_3DMODEL_DIR",
    ):
        assert token in first_run, f"First run is missing {token!r}"


def test_readme_libraries_note():
    text = _read("README.md")
    libraries = _section(text, "## Libraries and licences", *README_HEADINGS)
    for token in ("ships no libraries", "CC-BY-SA", "synthetic"):
        assert token in libraries, f"Libraries and licences is missing {token!r}"
    licence = _section(text, "## Licence", *README_HEADINGS)
    assert "MIT" in licence
    assert "LICENSE" in licence


def test_readme_folder_order():
    text = _read("README.md")
    choosing = _section(text, "## Choosing or creating a collection", *README_HEADINGS)
    order = (
        "--library-root",
        "KICAD_LIBMGR_ROOT",
        "the folder you chose last time",
        "KICAD_LIB_GITHUB",
        "first-run window",
    )
    positions = []
    for token in order:
        assert token in choosing, f"Choosing or creating a collection is missing {token!r}"
        positions.append(choosing.index(token))
    assert positions == sorted(positions), "the library-folder order is not stated in order"
    assert "the folder this app runs from" not in text
    assert "the folder the app runs from" not in text


def test_readme_dev_workflow():
    text = _read("README.md")
    development = _section(text, "## Development", *README_HEADINGS)
    for token in (
        "--library-root",
        "KICAD_LIBMGR_ROOT",
        "the command line wins",
        "requirements-dev.txt",
        "KICAD_TEST_CORPUS",
        "needs no collection",
    ):
        assert token in development, f"Development is missing {token!r}"


@pytest.mark.parametrize("relative", ["README.md", "LICENSE", "CLAUDE.md"])
def test_docs_hold_no_workstation_path(relative):
    text = _read(relative)
    assert _WORKSTATION_PATH.search(text) is None, f"{relative} holds a workstation path"
    assert _GIT_BASH_PATH.search(text) is None, f"{relative} holds a workstation path"
    for address in _AT_ADDRESS.findall(text):
        assert "noreply" in address, f"{relative} holds an email address"


# ── CLAUDE.md (the tool's developer guide) ──────────────────────────────────

CLAUDE_HEADINGS = (
    "## Project Overview",
    "## Repository Structure",
    "## Importing Parts",
    "## Python Environment",
    "## Running the GUI",
    "### GUI Behavior",
    "### Menu Shortcuts",
    "## Running the Tests",
    "## Dev Workflow",
    "## Git Workflow",
)

# They live in the collection docs (scripts/split/collection/CLAUDE.md)
MOVED_HEADINGS = (
    "## KiCad Path Variables",
    "## Library Naming Convention",
    "## Adding a New Library Submodule",
)


def test_claude_md_sections():
    text = _read("CLAUDE.md")
    for heading in CLAUDE_HEADINGS:
        assert _heading_at(text, heading) is not None, f"CLAUDE.md is missing heading {heading!r}"
    for heading in MOVED_HEADINGS:
        assert _heading_at(text, heading) is None, f"CLAUDE.md still has {heading!r}: it belongs to the collection docs"


def test_claude_md_names_the_new_actions():
    from kicad_lib_manager.main_window import MIGRATE_TEXT, SETUP_CHOOSER_TEXT

    text = _read("CLAUDE.md")

    migrate_text = MIGRATE_TEXT.replace("&", "")
    setup_chooser_text = SETUP_CHOOSER_TEXT.replace("&", "")
    assert migrate_text in text
    assert setup_chooser_text in text
    assert "Ctrl+Shift+M" in text
    assert "Ctrl+Shift+K" in text

    gui_behavior = _section(text, "### GUI Behavior", "### Menu Shortcuts")
    assert "KICAD_LIB_GITHUB" in gui_behavior
    assert "another folder" in gui_behavior


def test_claude_md_describes_the_library_folder():
    text = _read("CLAUDE.md")
    gui_behavior = _section(text, "### GUI Behavior", "### Menu Shortcuts")
    for token in (
        "New Library Collection...",
        "Open Library Collection...",
        "Use KiCad's Folder",
        "Recent Library Collections",
        "Show Library Folder in Explorer",
        "Change Folder...",
        "separate from Install Part and Generate Tables",
        "--library-root",
    ):
        assert token in gui_behavior, f"GUI Behavior is missing {token!r}"
    assert "new collection" in gui_behavior.casefold()

    # edge SPLIT-08 ordering: four sources in this order, then the first-run window
    assert (
        "`--library-root`, `KICAD_LIBMGR_ROOT`, the folder you chose last time, KiCad's `KICAD_LIB_GITHUB`"
        in gui_behavior
    )
    assert "the folder this app runs from" not in text
    assert "the folder the app runs from" not in text

    running = _section(text, "## Running the GUI", "### GUI Behavior")
    assert "KICAD_LIBMGR_ROOT" in running or "--library-root" in running
    # no shortcut was added for the library folder
    shortcuts = _section(text, "### Menu Shortcuts", "## Running the Tests")
    assert "Library Folder" not in shortcuts
    assert "Library Collection" not in shortcuts


def test_claude_md_names_the_catalog():
    """Phase 17 (CAT-01, CAT-10, CAT-11): the shortcut, the GUI behaviour and the folders of the library catalog."""
    text = _read("CLAUDE.md")
    gui_behavior = _section(text, "### GUI Behavior", "### Menu Shortcuts")
    for token in (
        "Library Catalog...",
        "Ctrl+Shift+L",
        "(n updates)",
        "catalog.json",
        "ThirdParty",
        "Plugin and Content Manager",
        "Add by URL...",
        "Update available",
        "Problem: folder missing",
        "Problem: not in the catalog",
        "Reinstall This Library",
        "Keep Library",
        "cannot be stopped",
        "Git 2.32",
        "ThirdParty/WurthElektronik",
        "never commits",
    ):
        assert token in gui_behavior, f"GUI Behavior is missing {token!r}"

    shortcuts = _section(text, "### Menu Shortcuts", "## Running the Tests")
    assert "- `Ctrl+Shift+L` — Library Catalog..." in shortcuts

    structure = _section(text, "## Repository Structure", "## Importing Parts")
    assert "`catalog/`" in structure
    assert "`scripts/catalog/`" in structure

    running = _section(text, "## Running the Tests", *CLAUDE_HEADINGS)
    assert "file://" in running and "network" in running


def test_readme_names_the_catalog():
    text = _read("README.md")
    libraries = _section(text, "## Libraries and licences", *README_HEADINGS)
    for token in ("Library Catalog...", "ThirdParty", "catalog.json", "own licence"):
        assert token in libraries, f"Libraries and licences is missing {token!r}"


def test_tests_readme_lists_the_catalog_slow_modules():
    text = _read("tests/README.md")
    command = _section(text, "### Publishing-control tests that CI does not run", "## Timeouts")
    for module in (
        "test_catalog_tracer.py",
        "test_catalog_gitnet_git.py",
        "test_catalog_ops_git.py",
        "test_wurth_to_catalog.py",
    ):
        assert module in command, f"the publish command is missing {module}"
        assert (REPO_ROOT / "tests" / module).is_file(), f"{module} does not exist"
    assert "file://" in command and "never the network" in command


def test_claude_md_dev_workflow():
    text = _read("CLAUDE.md")
    workflow = _section(text, "## Dev Workflow", *CLAUDE_HEADINGS)
    for token in (
        "--library-root",
        "KICAD_LIBMGR_ROOT",
        "the command line wins",
        "KICAD_TEST_CORPUS",
        "KICAD_TEST_HIDE_KICAD",
        "scratch",
        "needs no collection",
        "CLAUDE.local.md",
    ):
        assert token in workflow, f"Dev Workflow is missing {token!r}"

    running = _section(text, "## Running the Tests", *CLAUDE_HEADINGS)
    for token in ("corpus", "needs_kicad", "check_skip_budget.py"):
        assert token in running, f"Running the Tests is missing {token!r}"


def test_claude_md_git_workflow():
    text = _read("CLAUDE.md")
    git = _section(text, "## Git Workflow", *CLAUDE_HEADINGS)
    for token in (
        "Claude-Session",
        "Co-Authored-By",
        "noreply",
        "core.hooksPath .githooks",
        "prepublish_scan.py",
    ):
        assert token in git, f"Git Workflow is missing {token!r}"
