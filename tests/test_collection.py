"""The folder check, the resolve order and source_of (Phase 15, ROOT-02 and ROOT-07).

collection.py is Qt-free, so this module needs no window and no Qt harness.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from collectionfixtures import make_collection

from kicad_lib_manager import collection
from kicad_lib_manager.collection import Candidate, FolderCheck, Source, check_folder, resolve_library_root
from kicad_lib_manager.models import Severity

MISSING = "This folder does not exist. Choose another folder."


@pytest.fixture
def no_length_row(monkeypatch):
    """A tmp_path can already be over 100 characters: keep the length row out of tests about the others."""
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 10_000)


def texts(check: FolderCheck) -> list[tuple[str, str]]:
    return [(row.kind, row.text) for row in check.rows]


def test_check_rows_missing(tmp_path):
    result = check_folder(tmp_path / "nope")
    assert texts(result) == [("fail", MISSING)]
    assert result.state == "missing" and not result.usable and result.reason == MISSING


@pytest.mark.parametrize("blank", ["", "   "])
def test_check_rows_blank_text_is_missing(blank, monkeypatch, tmp_path):
    # Path("") is the working directory: a blank text must never be checked as one
    monkeypatch.chdir(make_collection(tmp_path / "cwd"))
    result = check_folder(blank)
    assert result.state == "missing"
    assert texts(result) == [("fail", MISSING)]


def test_check_rows_file(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    assert texts(check_folder(target)) == [("fail", "This is a file, not a folder. Choose a folder.")]
    assert check_folder(target).state == "file"


def test_check_rows_not_writable(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(tempfile, "TemporaryFile", refuse)
    result = check_folder(make_collection(tmp_path / "lib"))
    assert result.state == "not_writable"
    assert texts(result) == [
        ("pass", "This folder exists"),
        ("fail", "You cannot write to this folder. Choose one you can write to."),
    ]


@pytest.mark.parametrize("kwargs", [{"footprints": False}, {"symbols": False}])
def test_check_rows_collection_with_symbols_or_footprints_only(tmp_path, kwargs, no_length_row):
    root = tmp_path / "lib"
    (root / "Custom").mkdir(parents=True)
    if kwargs == {"footprints": False}:
        (root / "Custom" / "Symbols").mkdir()
    else:
        (root / "Custom" / "Footprints").mkdir()
    result = check_folder(root)
    assert result.state == "collection" and result.usable
    assert texts(result) == [
        ("pass", "This folder exists"),
        ("pass", "You can write to this folder"),
        ("pass", "It is a library collection"),
    ]
    assert result.rows[2].hint == " (Custom holds Symbols or Footprints)"
    assert result.rows[2].shown == "✓ It is a library collection"


def test_check_rows_current_folder_in_another_spelling(tmp_path):
    root = make_collection(tmp_path / "lib")
    (root / "sub").mkdir()
    result = check_folder(root / "sub" / "..", current=root)
    assert result.state == "current" and result.usable
    assert texts(result)[-1] == ("plain", "You are already using this library folder.")
    assert result.rows[-1].shown == "You are already using this library folder."
    # Not the folder in use: the plain collection row
    assert check_folder(root, current=tmp_path / "other").state == "collection"


def test_check_rows_empty_folder(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    result = check_folder(folder)
    assert result.state == "empty" and result.can_create_here and not result.usable
    assert texts(result) == [
        ("pass", "This folder exists"),
        ("pass", "You can write to this folder"),
        ("plain", "This folder is empty, so it is not a library collection yet. Press New Library Collection... to start one in it."),
    ]
    assert result.reason == ""
    # The writable probe left nothing behind
    assert list(folder.iterdir()) == []


def test_check_rows_drive_root(monkeypatch, tmp_path):
    drive = Path(tmp_path.anchor)
    # The real drive root is neither empty nor writable here: stand-ins for those two facts
    monkeypatch.setattr(collection, "_is_empty", lambda folder: True)
    monkeypatch.setattr(collection, "is_collection", lambda folder: False)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda dir=None: open(os.devnull, "rb"))
    result = check_folder(drive)
    assert result.state == "drive_root" and not result.can_create_here
    assert texts(result)[-1] == (
        "fail",
        f"{drive} is a whole drive. A collection needs its own folder: choose or create a folder inside it.",
    )


def test_check_rows_custom_folder_picked(tmp_path):
    root = make_collection(tmp_path / "lib")
    result = check_folder(root / "Custom")
    assert result.state == "custom_folder"
    assert texts(result)[-1] == (
        "fail",
        f"This looks like the Custom folder of a collection. Choose its parent folder instead: {root}.",
    )
    # Case-insensitive on the name
    renamed = tmp_path / "other" / "CUSTOM"
    (renamed / "Symbols").mkdir(parents=True)
    assert check_folder(renamed).state == "custom_folder"


def test_check_rows_not_a_collection(tmp_path):
    folder = tmp_path / "stuff"
    folder.mkdir()
    (folder / "readme.txt").write_text("x", encoding="utf-8")
    result = check_folder(folder)
    assert result.state == "not_collection" and not result.usable
    assert texts(result)[-1] == (
        "fail",
        "This is not a library collection: it has no Custom folder with Symbols or Footprints inside. "
        "To start a new collection, use New Library Collection... with an empty or new folder.",
    )
    # A Custom folder without Symbols or Footprints is not a collection either
    (folder / "Custom").mkdir()
    assert check_folder(folder).state == "not_collection"


def test_rows_stop_at_the_first_failure(tmp_path, no_length_row):
    result = check_folder(tmp_path / "nope")
    assert len(result.rows) == 1
    assert [row.kind for row in check_folder(make_collection(tmp_path / "lib")).rows] == ["pass"] * 3


def test_length_constant():
    assert collection.PATH_LENGTH_WARNING == 100


def test_length_boundary(monkeypatch, tmp_path):
    root = make_collection(tmp_path / "lib")
    length = len(str(root))
    assert check_folder(root).length == length
    # Exactly at the limit: no warning; one over: one warning
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", length)
    at_limit = check_folder(root)
    assert [row.kind for row in at_limit.rows] == ["pass", "pass", "pass"]
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", length - 1)
    over = check_folder(root)
    assert [row.kind for row in over.rows] == ["pass", "pass", "pass", "warn"]
    assert f"{length} characters" in over.rows[-1].text
    assert over.rows[-1].text.startswith("The path is ")
    assert over.rows[-1].shown.startswith("⚠ ")
    assert over.usable
    # A folder that is not a collection never gets a length row
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "x.txt").write_text("x", encoding="utf-8")
    assert "warn" not in [row.kind for row in check_folder(plain).rows]


def test_writable_probe_leaves_nothing(tmp_path):
    root = make_collection(tmp_path / "lib")
    before = sorted(p.name for p in root.iterdir())
    check_folder(root)
    assert sorted(p.name for p in root.iterdir()) == before


# ── resolve_library_root ────────────────────────────────────────────────────

def fake_check(usable: set, states: dict | None = None):
    """A check that passes for the folders named in usable; the others fail with their state."""
    states = states or {}

    def check(path):
        name = str(path)
        if name in usable:
            return FolderCheck(Path(name), (), "collection", len(name))
        state = states.get(name, "missing")
        return FolderCheck(
            Path(name), (collection.CheckRow("fail", f"reason of {name}"),), state, len(name),
        )

    return check


def cands(**paths) -> list[Candidate]:
    return [Candidate(Path(paths[s.name.lower()]), s) for s in Source if s.name.lower() in paths]


def test_source_has_four_members():
    assert [s.name for s in Source] == ["CLI", "ENV", "CHOSEN", "KICAD"]


def test_resolve_order():
    everything = cands(cli="a", env="b", chosen="c", kicad="d")
    usable = {"a", "b", "c", "d"}
    # Each rank wins when every candidate passes and the ranks above it are not offered or fail softly
    for expected, offered, drop in [
        ("a", 0, ""), ("b", 1, ""), ("c", 2, ""), ("d", 2, "c"),
    ]:
        result = resolve_library_root(everything[offered:], check=fake_check(usable - set(drop)))
        assert str(result.root) == os.path.abspath(expected)  # CR-02: the root is always absolute
        assert result.fatal is None
    # A failing CLI or ENV is fatal with the exact line and no root even when later candidates pass
    result = resolve_library_root(everything, check=fake_check({"b", "c", "d"}))
    assert result.root is None and result.source is None
    assert result.fatal == "--library-root: a cannot be used: reason of a"
    result = resolve_library_root(everything[1:], check=fake_check({"c", "d"}))
    assert result.root is None
    assert result.fatal == "KICAD_LIBMGR_ROOT: b cannot be used: reason of b"


def test_resolve_returns_the_source_of_the_winner():
    result = resolve_library_root(cands(chosen="c", kicad="d"), check=fake_check({"d"}))
    assert result.source is Source.KICAD and result.root == Path(os.path.abspath("d"))


def test_chosen_skipped_notes():
    # Deleted CHOSEN, KiCad wins
    result = resolve_library_root(cands(chosen="c", kicad="d"), check=fake_check({"d"}))
    assert [(n.severity, n.code, n.text) for n in result.notes] == [(
        Severity.WARNING, "library.chosen_skipped",
        "The library folder you chose earlier no longer exists: c. Using KiCad's folder (d) instead.",
    )]
    assert result.notice is None
    # Unusable CHOSEN, KiCad wins
    result = resolve_library_root(
        cands(chosen="c", kicad="d"), check=fake_check({"d"}, {"c": "not_collection"}),
    )
    assert [n.text for n in result.notes] == [
        "The library folder you chose earlier cannot be used (reason of c): c. "
        "Using KiCad's folder (d) instead.",
    ]
    # Nothing wins: the note asks for a choice and the notice names the folder
    result = resolve_library_root(cands(chosen="c"), check=fake_check(set()))
    assert result.root is None and result.fatal is None
    assert [n.text for n in result.notes] == [
        "The library folder you chose earlier no longer exists: c. Choose a library folder to continue.",
    ]
    assert result.notice == "The library folder you used before is gone: c."
    result = resolve_library_root(cands(chosen="c"), check=fake_check(set(), {"c": "not_writable"}))
    assert result.notice == "The library folder you used before cannot be used (reason of c): c."
    assert result.notes[0].text == (
        "The library folder you chose earlier cannot be used (reason of c): c. "
        "Choose a library folder to continue."
    )


def test_kicad_skipped_note():
    result = resolve_library_root(cands(kicad="d"), check=fake_check(set()))
    assert [(n.severity, n.code, n.text) for n in result.notes] == [(
        Severity.WARNING, "library.kicad_skipped", "Not using KiCad's folder d: reason of d",
    )]
    assert result.root is None and result.source is None


def test_notes_keep_their_order():
    result = resolve_library_root(cands(chosen="c", kicad="d"), check=fake_check(set()))
    assert [n.code for n in result.notes] == ["library.kicad_skipped", "library.chosen_skipped"]
    assert result.notes[1].text.endswith("Choose a library folder to continue.")


def test_no_candidates_resolves_nothing():
    result = resolve_library_root([], check=fake_check(set()))
    assert result.root is None and result.fatal is None and result.notes == ()


# ── source_of and folder identity ───────────────────────────────────────────

def test_source_of():
    assert collection.source_of("Custom/Symbols/A.kicad_sym") == "Custom"
    assert collection.source_of("WurthElektronik/KiCad-Library/x.pretty") == "WurthElektronik"
    assert collection.source_of("ThirdParty/sparkfun/x.pretty") == "sparkfun"
    assert collection.source_of("") == "Unknown"


def test_same_folder_ignores_separators_and_trailing_slash(tmp_path):
    root = tmp_path / "lib"
    root.mkdir()
    assert collection.same_folder(root, str(root) + os.sep)
    assert collection.same_folder(root, str(root).replace("\\", "/"))
    assert collection.same_folder(f"  {root}  ", root)
    assert not collection.same_folder(root, tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="case-insensitive paths are a Windows rule")
def test_same_folder_ignores_case_on_windows(tmp_path):
    root = tmp_path / "Lib"
    root.mkdir()
    assert collection.same_folder(root, str(root).upper())
    assert collection.folder_key(root) == collection.folder_key(str(root).lower())


def test_is_collection(tmp_path):
    assert not collection.is_collection(tmp_path / "nope")
    assert collection.is_collection(make_collection(tmp_path / "a", footprints=False))
    assert collection.is_collection(make_collection(tmp_path / "b", symbols=False))
    bare = tmp_path / "c"
    (bare / "Custom").mkdir(parents=True)
    assert not collection.is_collection(bare)


def test_no_answer_row():
    result = collection.no_answer(Path("Z:/lib"))
    assert result.state == "no_answer" and not result.usable
    assert texts(result) == [("fail", "The drive did not answer within 5 seconds.")]


# ── New collection: names, checks and creation (Phase 15-06, ROOT-06) ───────

from collectionfixtures import recording_git  # noqa: E402

from kicad_lib_manager.collection import (  # noqa: E402
    check_new_collection,
    create_collection,
    validate_collection_name,
)

GIT_ANSWERS = {"--version": (0, "git version 2.49.0.windows.1"), "init": (0, "")}
CHARS_ROW = 'A folder name cannot contain \\ / : * ? " < > | or end with a space or a dot.'
EMPTY_NAME = "Enter a name for the collection folder."
NO_GIT = "Git was not found. A collection needs Git to commit your parts. Install Git for Windows, then try again."
NO_PARENT = "The parent folder does not exist. Choose an existing folder."
SKELETON = [
    "Custom",
    "Custom/.gitignore",
    "Custom/3DModels",
    "Custom/3DModels/.gitkeep",
    "Custom/Footprints",
    "Custom/Footprints/Atomic_Footprints.pretty",
    "Custom/Footprints/Atomic_Footprints.pretty/.gitkeep",
    "Custom/README.md",
    "Custom/Symbols",
    "Custom/Symbols/.gitkeep",
]


def tree(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def new_rows(parent, name, *, git_found=True, app_dir=None, environ=None):
    result = check_new_collection(
        parent, name, git_found=git_found, app_dir=app_dir or Path("Z:/no/such/app"), environ=environ or {}
    )
    return result, [(row.kind, row.text) for row in result.rows]


@pytest.mark.parametrize(
    "name",
    ["a/b", "a\\b", "a:b", "a*", "a?", 'a"', "a<", "a>", "a|", "a\x00", "a\x1f", "name.", "name ", ".", ".."],
)
def test_name_rules_refuse_characters(name):
    row = validate_collection_name(name)
    assert row is not None and row.kind == "fail" and row.text == CHARS_ROW


def test_name_rules_empty():
    row = validate_collection_name("")
    assert row is not None and row.text == EMPTY_NAME


@pytest.mark.parametrize("name", ["CON", "con", "Nul.txt", "COM1", "LPT9", "COM¹", "LPT³", "prn", "Aux", "com9.log"])
def test_name_rules_refuse_reserved(name):
    row = validate_collection_name(name)
    assert row is not None and row.text == f"{name} is a reserved name in Windows. Choose another name."


@pytest.mark.parametrize("name", ["KiCad_Libraries", "R&D Parts", "Librairies été", "COM10", "CONSOLE", "a.b"])
def test_name_rules_accept(name):
    assert validate_collection_name(name) is None


def test_new_rows_in_order(tmp_path):
    result, rows = new_rows(tmp_path / "missing", "", git_found=False)
    assert rows == [("fail", NO_GIT), ("fail", NO_PARENT), ("fail", EMPTY_NAME)]
    assert result.target is None and result.blocked


def test_new_rows_empty_parent_text():
    assert new_rows("", "x")[1] == [("fail", NO_PARENT)]
    assert new_rows("   ", "x")[1] == [("fail", NO_PARENT)]


def test_new_rows_parent_is_a_file(tmp_path):
    (tmp_path / "f").write_text("x", encoding="utf-8")
    assert new_rows(tmp_path / "f", "x")[1] == [("fail", NO_PARENT)]


def test_new_rows_parent_not_writable(tmp_path, monkeypatch, no_length_row):
    def deny(*args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(collection.tempfile, "TemporaryFile", deny)
    rows = new_rows(tmp_path, "x")[1]
    assert rows == [("fail", f"You cannot write to {tmp_path}. Choose a folder you can write to.")]


def test_new_rows_bad_name_and_reserved(tmp_path):
    assert new_rows(tmp_path, "a|b")[1] == [("fail", CHARS_ROW)]
    assert new_rows(tmp_path, "NUL")[1] == [("fail", "NUL is a reserved name in Windows. Choose another name.")]


def test_new_rows_valid_gives_none(tmp_path, no_length_row):
    result, rows = new_rows(tmp_path, "KiCad_Libraries")
    assert rows == [] and not result.blocked and not result.existing_empty
    assert result.target == tmp_path / "KiCad_Libraries"


def test_new_rows_program_files(tmp_path, no_length_row):
    pf = tmp_path / "Program Files"
    (pf / "Inside").mkdir(parents=True)
    env = {"ProgramFiles": str(pf)}
    inside = pf / "Inside" / "Lib"
    text = (
        f"{inside} is inside Program Files, which programs cannot normally write to. "
        "Choose a folder in your Documents or on another drive."
    )
    assert new_rows(pf / "Inside", "Lib", environ=env)[1] == [("fail", text)]
    # the folder itself counts as inside it
    rows = new_rows(pf.parent, "Program Files", environ=env)[1]
    assert rows and rows[0][1].startswith(f"{pf} is inside Program Files")


@pytest.mark.parametrize("var", ["ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"])
def test_new_rows_program_files_variables(tmp_path, no_length_row, var):
    pf = tmp_path / "PF"
    pf.mkdir()
    rows = new_rows(pf, "Lib", environ={var: str(pf)})[1]
    assert len(rows) == 1 and "is inside Program Files" in rows[0][1]


def test_new_rows_program_files_sibling_is_not_refused(tmp_path, no_length_row):
    (tmp_path / "Program Files").mkdir()
    (tmp_path / "Program Files Extra").mkdir()
    env = {"ProgramFiles": str(tmp_path / "Program Files")}
    assert new_rows(tmp_path / "Program Files Extra", "Lib", environ=env)[1] == []


def test_new_rows_app_folder(tmp_path, no_length_row):
    app = tmp_path / "app"
    (app / "sub").mkdir(parents=True)
    text = f"{app / 'sub' / 'Lib'} is inside the app's own folder ({app}). Choose another location."
    assert new_rows(app / "sub", "Lib", app_dir=app)[1] == [("fail", text)]
    rows = new_rows(tmp_path, "app", app_dir=app)[1]
    # the app folder itself (non-empty here) is refused like one inside it, first
    assert rows[0] == ("fail", f"{app} is inside the app's own folder ({app}). Choose another location.")
    # a sibling with the same prefix is not inside it
    (tmp_path / "app2").mkdir()
    assert new_rows(tmp_path / "app2", "Lib", app_dir=app)[1] == []


def test_new_rows_target_is_a_file(tmp_path, no_length_row):
    (tmp_path / "x").write_text("x", encoding="utf-8")
    assert new_rows(tmp_path, "x")[1] == [("fail", f"{tmp_path / 'x'} is a file. Choose another name.")]


def test_new_rows_target_holds_a_collection(tmp_path, no_length_row):
    make_collection(tmp_path / "x")
    text = f"{tmp_path / 'x'} already holds a library collection. Use File > Open Library Collection... to open it."
    assert new_rows(tmp_path, "x")[1] == [("fail", text)]


def test_new_rows_target_not_empty(tmp_path, no_length_row):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f.txt").write_text("x", encoding="utf-8")
    text = f"{tmp_path / 'x'} is not empty. Choose an empty folder or a new name."
    assert new_rows(tmp_path, "x")[1] == [("fail", text)]


def test_new_rows_existing_empty_is_used(tmp_path, no_length_row):
    (tmp_path / "x").mkdir()
    result, rows = new_rows(tmp_path, "x")
    assert result.existing_empty and not result.blocked
    assert rows == [("plain", "This folder already exists and is empty. It will be used.")]


def test_new_rows_length_warning_is_last(tmp_path, monkeypatch):
    (tmp_path / "x").mkdir()
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 5)
    # the parent also counts as Program Files, so a fail row comes before the plain line and the warning
    result, rows = new_rows(tmp_path, "x", environ={"ProgramFiles": str(tmp_path)})
    assert [kind for kind, _ in rows] == ["fail", "plain", "warn"]
    assert rows[2][1] == (
        f"The path is {len(str(tmp_path / 'x'))} characters long. KiCad and git can fail on long Windows paths. "
        "A shorter folder such as C:/KiCad_Libraries is safer."
    )
    assert result.blocked


def test_new_rows_length_warning_alone_does_not_block(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "PATH_LENGTH_WARNING", 5)
    result, rows = new_rows(tmp_path, "x")
    assert [kind for kind, _ in rows] == ["warn"] and not result.blocked


def test_new_rows_git_row_first_with_other_rows(tmp_path, no_length_row):
    (tmp_path / "x").write_text("x", encoding="utf-8")
    rows = new_rows(tmp_path, "x", git_found=False)[1]
    assert [text for _, text in rows] == [NO_GIT, f"{tmp_path / 'x'} is a file. Choose another name."]


def test_create_makes_the_skeleton(tmp_path, no_length_row):
    ctx, calls = recording_git(GIT_ANSWERS)
    target = tmp_path / "Libs"
    assert create_collection(target, ctx, app_dir=tmp_path / "app", environ={}) == []
    assert tree(target) == SKELETON
    inits = [argv for argv in calls if argv[6] == "init"]
    assert len(inits) == 1 and inits[0][6:] == ["init", "--template=", "-b", "main"]
    assert Path(inits[0][5]) == target / "Custom"
    for rel in ("Custom/.gitignore", "Custom/README.md"):
        assert b"\r" not in (target / rel).read_bytes()
    for rel in (
        "Custom/Symbols/.gitkeep",
        "Custom/3DModels/.gitkeep",
        "Custom/Footprints/Atomic_Footprints.pretty/.gitkeep",
    ):
        assert (target / rel).read_bytes() == b""
    assert (target / "Custom/.gitignore").read_text(encoding="utf-8") == collection.GITIGNORE_TEXT
    assert (target / "Custom/README.md").read_text(encoding="utf-8") == collection.README_TEXT


def test_create_uses_an_existing_empty_target(tmp_path, no_length_row):
    ctx, _ = recording_git(GIT_ANSWERS)
    target = tmp_path / "Empty"
    target.mkdir()
    assert create_collection(target, ctx, app_dir=tmp_path / "app", environ={}) == []
    assert tree(target) == SKELETON
    assert collection.is_collection(target)


def test_create_never_commits(tmp_path, no_length_row):
    ctx, calls = recording_git(GIT_ANSWERS)
    create_collection(tmp_path / "Libs", ctx, app_dir=tmp_path / "app", environ={})
    assert {argv[6] for argv in calls} <= {"--version", "init"}


def test_text_constants():
    lines = collection.GITIGNORE_TEXT.splitlines()
    assert lines[0] == "# KiCad temporary and backup files"
    assert lines[1:] == [
        "*.bak", "*.bck", "*-backups", "*.kicad_prl", "*~", "_autosave-*", "*.tmp", "fp-info-cache", "~*.lck",
        "\\#auto_saved_files#",
    ]
    assert collection.GITIGNORE_TEXT.endswith("\n") and "\r" not in collection.GITIGNORE_TEXT
    assert collection.README_TEXT.startswith("# KiCad library collection\n")
    assert "\r" not in collection.README_TEXT and collection.README_TEXT.endswith("\n")
    assert "${CUSTOM_3DMODEL_DIR}/<file>" in collection.README_TEXT
    assert "Nothing was committed when it was created" in collection.README_TEXT


def test_create_refuses_old_git(tmp_path, no_length_row):
    ctx, calls = recording_git({"--version": (0, "git version 2.27.0.windows.1")})
    target = tmp_path / "Libs"
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [(i.severity, i.code) for i in issues] == [(Severity.ERROR, "collection.git_too_old")]
    assert issues[0].text == (
        "Git 2.28 or newer is needed to create a collection (found 2.27.0). Update Git for Windows, then try again."
    )
    assert not target.exists() and [a for a in calls if a[6] == "init"] == []


def test_create_refuses_missing_git(tmp_path, no_length_row):
    ctx, calls = recording_git({"--version": (1, "")})
    target = tmp_path / "Libs"
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [(i.severity, i.code, i.text) for i in issues] == [(Severity.ERROR, "collection.git_missing", NO_GIT)]
    assert not target.exists() and [a for a in calls if a[6] == "init"] == []


def test_create_refuses_a_non_empty_target(tmp_path, no_length_row):
    ctx, calls = recording_git(GIT_ANSWERS)
    target = tmp_path / "Full"
    target.mkdir()
    (target / "mine.txt").write_text("keep", encoding="utf-8")
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.refused"]
    assert issues[0].text == f"{target} is not empty. Choose an empty folder or a new name."
    assert tree(target) == ["mine.txt"] and calls == []


def test_create_refuses_a_drive_root(tmp_path):
    ctx, calls = recording_git(GIT_ANSWERS)
    root = Path(tmp_path.anchor)
    issues = create_collection(root, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.refused"]
    assert issues[0].text == (
        f"{root} is a whole drive. A collection needs its own folder: choose or create a folder inside it."
    )
    assert calls == []


def test_create_refuses_program_files_and_app_folder(tmp_path, no_length_row):
    ctx, calls = recording_git(GIT_ANSWERS)
    pf = tmp_path / "Program Files"
    app = tmp_path / "app"
    pf.mkdir()
    app.mkdir()
    one = create_collection(pf / "Libs", ctx, app_dir=app, environ={"ProgramFiles": str(pf)})
    two = create_collection(app / "Libs", ctx, app_dir=app, environ={})
    assert "is inside Program Files" in one[0].text and one[0].code == "collection.refused"
    assert "is inside the app's own folder" in two[0].text
    assert calls == [] and tree(pf) == [] and tree(app) == []


def test_create_cleans_up_after_failure(tmp_path, no_length_row):
    ctx, _ = recording_git({"--version": (0, "git version 2.49.0"), "init": (128, "fatal: nope.")})
    target = tmp_path / "Libs"
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [(i.severity, i.code) for i in issues] == [(Severity.ERROR, "collection.create_failed")]
    assert issues[0].text == (
        "Could not create the collection: fatal: nope. Choose another name or folder, then try again."
    )
    assert not target.exists()


def test_create_failure_keeps_a_pre_existing_target(tmp_path, no_length_row):
    ctx, _ = recording_git({"--version": (0, "git version 2.49.0"), "init": (128, "boom")})
    target = tmp_path / "Empty"
    target.mkdir()
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed"]
    assert target.is_dir() and tree(target) == []


def test_create_failure_on_a_write_error_cleans_up(tmp_path, monkeypatch, no_length_row):
    ctx, _ = recording_git(GIT_ANSWERS)
    real_open = os.open

    def failing_open(path, flags, *args, **kwargs):
        if str(path).endswith("README.md"):
            raise OSError(5, "Access is denied", str(path))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(collection.os, "open", failing_open)
    target = tmp_path / "Libs"
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed"]
    assert issues[0].text.startswith("Could not create the collection: Access is denied")
    assert not target.exists()


def test_create_reports_leftovers(tmp_path, monkeypatch, no_length_row):
    ctx, _ = recording_git({"--version": (0, "git version 2.49.0"), "init": (128, "boom")})

    def stuck(folder):
        raise OSError("in use")

    monkeypatch.setattr(collection, "_remove_tree", stuck)
    target = tmp_path / "Libs"
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed", "collection.leftovers"]
    assert issues[1].text == f"Some folders were left behind in {target}. Delete them and try again."


def test_create_twice_is_refused(tmp_path, no_length_row):
    ctx, _ = recording_git(GIT_ANSWERS)
    target = tmp_path / "Libs"
    assert create_collection(target, ctx, app_dir=tmp_path / "app", environ={}) == []
    before = {rel: (target / rel).read_bytes() for rel in SKELETON if (target / rel).is_file()}
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.refused"]
    assert issues[0].text == (
        f"{target} already holds a library collection. Use File > Open Library Collection... to open it."
    )
    assert before == {rel: (target / rel).read_bytes() for rel in before}
    assert tree(target) == SKELETON


def test_create_removes_read_only_git_files_after_a_late_failure(tmp_path, no_length_row):
    import stat
    import subprocess

    from kicad_lib_manager.gitops import GitContext

    def runner(argv, **kwargs):
        if argv[6] == "init":
            objects = Path(argv[5]) / ".git" / "objects"
            objects.mkdir(parents=True)
            frozen = objects / "pack"
            frozen.write_bytes(b"x")
            frozen.chmod(stat.S_IREAD)
            return subprocess.CompletedProcess(argv, 128, stdout=b"", stderr=b"late failure")
        return subprocess.CompletedProcess(argv, 0, stdout=b"git version 2.49.0", stderr=b"")

    target = tmp_path / "Libs"
    issues = create_collection(target, GitContext(Path("git"), runner), app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed"]
    assert not target.exists()


# ── Review fixes (Phase 15 code review) ─────────────────────────────────────

def _raising_init_context(error):
    """A GitContext whose runner answers --version and raises `error` when git init starts."""
    import subprocess

    from kicad_lib_manager.gitops import GitContext

    def runner(argv, **kwargs):
        if argv[6] == "init":
            raise error
        return subprocess.CompletedProcess(argv, 0, stdout=b"git version 2.49.0", stderr=b"")

    return GitContext(Path("git"), runner)


@pytest.mark.parametrize(
    "error, shown",
    [
        (__import__("subprocess").TimeoutExpired("git", 30), "did not finish within"),
        (FileNotFoundError(2, "The system cannot find the file specified"), "Could not run git"),
    ],
)
def test_create_cleans_up_when_git_init_returns_an_issue(tmp_path, no_length_row, error, shown):
    """CR-01: run_git turns a timeout or an OS error into an Issue; that must clean up, not raise."""
    target = tmp_path / "Libs"
    ctx = _raising_init_context(error)
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [(i.severity, i.code) for i in issues] == [(Severity.ERROR, "collection.create_failed")]
    assert shown in issues[0].text
    assert not target.exists()
    # a retry is allowed: the failed attempt left nothing that makes the folder look like a collection
    ok_ctx, _ = recording_git(GIT_ANSWERS)
    assert create_collection(target, ok_ctx, app_dir=tmp_path / "app", environ={}) == []


def test_create_cleans_up_after_an_unexpected_exception(tmp_path, no_length_row):
    target = tmp_path / "Libs"
    ctx = _raising_init_context(RuntimeError("boom"))
    issues = create_collection(target, ctx, app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed"]
    assert "RuntimeError: boom" in issues[0].text
    assert not target.exists()


def test_check_folder_makes_a_relative_folder_absolute(tmp_path, monkeypatch, no_length_row):
    """CR-02: a typed relative folder is checked, reported and kept as an absolute path."""
    make_collection(tmp_path / "Lib")
    monkeypatch.chdir(tmp_path)
    result = check_folder("Lib")
    assert result.usable and result.path.is_absolute()
    assert result.path == tmp_path / "Lib"
    assert check_folder(Path("Lib")).path.is_absolute()
    assert check_folder("Missing").path.is_absolute()  # also the failing rows name the real folder
    assert collection.no_answer("Lib").path.is_absolute()


def test_blank_folder_text_stays_blank_not_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert check_folder("  ").state == "missing"
    assert collection.absolute_folder("  ") == Path("")


def test_resolve_makes_the_winner_absolute(tmp_path, monkeypatch, no_length_row):
    make_collection(tmp_path / "Lib")
    monkeypatch.chdir(tmp_path)
    result = resolve_library_root([Candidate(Path("Lib"), Source.CHOSEN)])
    assert result.root == tmp_path / "Lib" and result.root.is_absolute()


def test_new_collection_check_makes_the_target_absolute(tmp_path, monkeypatch, no_length_row):
    monkeypatch.chdir(tmp_path)
    result, rows = new_rows(".", "Libs2")
    assert result.target == tmp_path / "Libs2" and result.target.is_absolute()
    assert not result.blocked, rows
    result, _ = new_rows("sub/..", "Libs3")
    assert result.target == tmp_path / "Libs3"


def test_create_collection_with_a_relative_target_builds_it_in_place(tmp_path, monkeypatch, no_length_row):
    monkeypatch.chdir(tmp_path)
    ctx, _ = recording_git(GIT_ANSWERS)
    assert create_collection(Path("Libs"), ctx, app_dir=tmp_path / "app", environ={}) == []
    assert tree(tmp_path / "Libs") == SKELETON


@pytest.mark.parametrize("name", [".git", ".GIT", ".Git"])
def test_name_rules_refuse_dot_git(name):
    row = validate_collection_name(name)
    assert row is not None and row.kind == "fail"
    assert row.text == (
        "A collection cannot be named .git: git keeps its own data in a folder with that name. Choose another name."
    )


@pytest.mark.parametrize("name", [" Libs", "  x", " .git"])
def test_name_rules_refuse_a_leading_space(name):
    row = validate_collection_name(name)
    assert row is not None and row.text == "A folder name cannot start with a space. Choose another name."


@pytest.mark.parametrize("name", [".gitignore", ".github", "a.git", ".git2"])
def test_name_rules_accept_names_that_only_look_like_git(name):
    assert validate_collection_name(name) is None


def test_new_collection_check_blocks_dot_git(tmp_path, no_length_row):
    result, rows = new_rows(tmp_path, ".git")
    assert result.blocked and result.target is None
    assert rows == [("fail", collection._GIT_NAME_TEXT)]


def test_cleanup_keeps_what_another_program_wrote_into_the_target(tmp_path, no_length_row):
    """WR-06: only this call's own paths go; the target folder is removed only when it is empty."""
    import subprocess

    from kicad_lib_manager.gitops import GitContext

    target = tmp_path / "Libs"

    def runner(argv, **kwargs):
        if argv[6] == "init":
            (target / "notes.txt").write_text("not ours", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 128, stdout=b"", stderr=b"late failure")
        return subprocess.CompletedProcess(argv, 0, stdout=b"git version 2.49.0", stderr=b"")

    issues = create_collection(target, GitContext(Path("git"), runner), app_dir=tmp_path / "app", environ={})
    assert [i.code for i in issues] == ["collection.create_failed", "collection.leftovers"]
    assert tree(target) == ["notes.txt"]
    assert (target / "notes.txt").read_text(encoding="utf-8") == "not ours"


def test_same_spelling_never_touches_the_disk(tmp_path, monkeypatch):
    def no_resolve(self, *args, **kwargs):
        raise AssertionError("resolve touches the disk")

    monkeypatch.setattr(Path, "resolve", no_resolve)
    (tmp_path / "x").mkdir()
    assert collection.same_spelling(tmp_path / "x", str(tmp_path) + "/x/../x/")
    assert not collection.same_spelling(tmp_path / "x", tmp_path / "y")
