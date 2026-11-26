"""scripts/split/uri_diff.py: the resolved-URI snapshot and compare of KiCad's global tables (Phase 16, D-22).

The script is a stdlib-only file under scripts/ (not a package), so the tests load it by path.
Every test works on copies in tmp_path; the script only ever reads the tables folder it is given.
"""

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "split" / "uri_diff.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tables"


def _load():
    spec = importlib.util.spec_from_file_location("split_uri_diff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["split_uri_diff"] = module
    spec.loader.exec_module(module)
    return module


uri_diff = _load()


def _tables(folder: Path, **files: str) -> Path:
    """A tables folder: sym= / fp= name a fixture each, copied as sym-lib-table / fp-lib-table."""
    folder.mkdir(parents=True, exist_ok=True)
    if "sym" in files:
        (folder / "sym-lib-table").write_bytes((FIXTURES / files["sym"]).read_bytes())
    if "fp" in files:
        (folder / "fp-lib-table").write_bytes((FIXTURES / files["fp"]).read_bytes())
    return folder


def _text_table(folder: Path, kind: str, entries: list[tuple[str, str]]) -> Path:
    """Write sym-lib-table or fp-lib-table with (name, uri) lib entries."""
    folder.mkdir(parents=True, exist_ok=True)
    head = "sym_lib_table" if kind == "sym" else "fp_lib_table"
    lines = [f"({head}", "  (version 7)"]
    for name, uri in entries:
        lines.append(f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))')
    lines.append(")")
    (folder / f"{kind}-lib-table").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def _run(args: list[str], capsys) -> tuple[int, str]:
    code = uri_diff.main(args)
    return code, capsys.readouterr().out


@pytest.fixture(autouse=True)
def _no_kicad_variables(monkeypatch):
    for name in ("KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "KICAD10_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_snapshot_resolves_and_marks_existence(tmp_path, capsys):
    tables = _tables(tmp_path / "cfg", sym="basic.sym-lib-table")
    lib = tmp_path / "Libs"
    (lib / "Custom" / "Symbols").mkdir(parents=True)
    (lib / "Custom" / "Symbols" / "Fixture_A.kicad_sym").write_text("x", encoding="utf-8")
    out = tmp_path / "snap.json"
    code, text = _run(
        ["snapshot", "--tables-dir", str(tables), "--var", f"KICAD_LIB_GITHUB={lib}", "--out", str(out)], capsys
    )
    assert code == 0
    snap = json.loads(out.read_text(encoding="utf-8"))
    by_name = {entry["name"]: entry for entry in snap["entries"]}
    assert by_name["Fixture_A"]["resolved"] == "<LIB>/Custom/Symbols/Fixture_A.kicad_sym"
    assert by_name["Fixture_A"]["expanded"] is True
    assert by_name["Fixture_A"]["exists"] is True
    assert by_name["Fixture_B"]["expanded"] is True
    assert by_name["Fixture_B"]["exists"] is False
    assert by_name["Fixture_A"]["table"] == "sym-lib-table"
    assert by_name["Fixture_A"]["type"] == "KiCad"
    assert snap["vars"]["KICAD_LIB_GITHUB"] == "<LIB>"
    assert [m["name"] for m in snap["missing"]] == ["Fixture_B"]
    assert "uri_diff: 2 entries, 1 missing" in text
    assert "Fixture_B" in text


def test_builtin_variables_are_text(tmp_path, capsys):
    tables = _text_table(
        tmp_path / "cfg", "sym", [("Device", "${KICAD10_SYMBOL_DIR}/Device.kicad_sym")]
    )
    out = tmp_path / "snap.json"
    code, text = _run(["snapshot", "--tables-dir", str(tables), "--out", str(out)], capsys)
    assert code == 0
    snap = json.loads(out.read_text(encoding="utf-8"))
    entry = snap["entries"][0]
    assert entry["expanded"] is False
    assert entry["exists"] is False
    assert entry["resolved"] == "${KICAD10_SYMBOL_DIR}/Device.kicad_sym"
    assert snap["missing"] == []
    assert "0 missing" in text


def test_escaped_names_and_uris():
    text = (FIXTURES / "escaped.sym-lib-table").read_text(encoding="utf-8")
    entries = uri_diff.parse_table(text, "sym-lib-table")
    assert len(entries) == 1
    assert entries[0].name == "Escaped_Lib"
    assert entries[0].type == "KiCad"
    assert entries[0].uri == "C:\\KiCad\\libs\\Escaped.kicad_sym"


def test_parse_handles_field_order_and_flags():
    reordered = uri_diff.parse_table((FIXTURES / "reordered.fp-lib-table").read_text(encoding="utf-8"), "fp-lib-table")
    assert {(e.name, e.uri) for e in reordered} == {
        ("Reordered", "${KICAD_LIB_GITHUB}/Custom/Footprints/Reordered.pretty"),
        ("Minimal", "/abs/path/Minimal.pretty"),
    }
    flags = uri_diff.parse_table((FIXTURES / "flags.fp-lib-table").read_text(encoding="utf-8"), "fp-lib-table")
    assert [e.name for e in flags] == ["Disabled_Lib", "Hidden_Lib", "Future_Lib"]


def test_root_prefix_is_a_whole_segment(tmp_path):
    root = tmp_path / "Libs"
    inside = f"{root.as_posix()}/Custom/a.kicad_sym"
    sibling = f"{tmp_path.as_posix()}/Libs-old/a.kicad_sym"
    assert uri_diff.normalise(inside, str(root)) == "<LIB>/Custom/a.kicad_sym"
    assert uri_diff.normalise(sibling, str(root)) == sibling
    assert uri_diff.normalise(root.as_posix(), str(root)) == "<LIB>"
    assert uri_diff.normalise(inside, None) == inside


@pytest.mark.skipif(sys.platform != "win32", reason="case and slash direction only matter on Windows")
def test_root_prefix_ignores_case_and_slashes_on_windows(tmp_path):
    root = tmp_path / "Libs"
    shouted = str(root).upper().replace("/", "\\") + "\\Custom\\a.kicad_sym"
    assert uri_diff.normalise(shouted, str(root)) == "<LIB>/Custom/a.kicad_sym"
    old = str(tmp_path / "Libs-old").replace("/", "\\") + "\\a.kicad_sym"
    assert uri_diff.normalise(old, str(root)) == old.replace("\\", "/")


def test_empty_tables_exit_2(tmp_path, capsys):
    out = tmp_path / "snap.json"
    nothing = tmp_path / "nothing"
    nothing.mkdir()
    code, _ = _run(["snapshot", "--tables-dir", str(nothing), "--out", str(out)], capsys)
    assert code == 2
    assert not out.exists()
    only_empty = _tables(tmp_path / "only_empty", sym="empty.sym-lib-table")
    code, _ = _run(["snapshot", "--tables-dir", str(only_empty), "--out", str(out)], capsys)
    assert code == 2
    assert not out.exists()


def test_reordered_table_compares_identical(tmp_path, capsys):
    # the fixture's absolute /abs/path entry cannot exist here, so it is pointed under the library root
    # (the file keeps its out-of-order fields and entry order)
    fixture = (FIXTURES / "reordered.fp-lib-table").read_text(encoding="utf-8")
    assert "/abs/path/" in fixture
    reordered = tmp_path / "a"
    reordered.mkdir()
    (reordered / "fp-lib-table").write_text(fixture.replace("/abs/path/", "${KICAD_LIB_GITHUB}/Abs/"), encoding="utf-8")
    sorted_dir = _text_table(
        tmp_path / "b",
        "fp",
        [
            ("Minimal", "${KICAD_LIB_GITHUB}/Abs/Minimal.pretty"),
            ("Reordered", "${KICAD_LIB_GITHUB}/Custom/Footprints/Reordered.pretty"),
        ],
    )
    lib = tmp_path / "Libs"
    (lib / "Abs" / "Minimal.pretty").mkdir(parents=True)
    (lib / "Custom" / "Footprints" / "Reordered.pretty").mkdir(parents=True)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for tables, out in ((reordered, first), (sorted_dir, second)):
        code, _ = _run(["snapshot", "--tables-dir", str(tables), "--var", f"KICAD_LIB_GITHUB={lib}", "--out", str(out)], capsys)
        assert code == 0
    names = [e["name"] for e in json.loads(first.read_text(encoding="utf-8"))["entries"]]
    assert names == sorted(names)
    # the file's entry order is left out of the comparison, and so is the descr text
    entries_a = json.loads(first.read_text(encoding="utf-8"))["entries"]
    entries_b = json.loads(second.read_text(encoding="utf-8"))["entries"]
    assert entries_a == entries_b
    code, text = _run(["compare", str(first), str(second)], capsys)
    assert code == 0
    assert "uri_diff: identical, 2 entries" in text


def test_duplicate_names_are_reported(tmp_path, capsys):
    tables = _text_table(
        tmp_path / "cfg",
        "sym",
        [("Twice", "/one/Twice.kicad_sym"), ("Twice", "/two/Twice.kicad_sym"), ("Once", "/one/Once.kicad_sym")],
    )
    out = tmp_path / "snap.json"
    code, text = _run(["snapshot", "--tables-dir", str(tables), "--out", str(out)], capsys)
    assert code == 0
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert [e["name"] for e in snap["entries"]].count("Twice") == 2
    assert [d["name"] for d in snap["duplicates"]] == ["Twice"]
    assert "duplicate" in text
    assert "Twice" in text


def _snap(tmp_path: Path, capsys, name: str, entries: list[tuple[str, str]], lib: Path) -> Path:
    tables = _text_table(tmp_path / f"cfg_{name}", "sym", entries)
    out = tmp_path / f"{name}.json"
    code, _ = _run(["snapshot", "--tables-dir", str(tables), "--var", f"KICAD_LIB_GITHUB={lib}", "--out", str(out)], capsys)
    assert code == 0
    return out


def _named(lines: list[str]) -> list[tuple[str, str]]:
    """(kind, entry name) of every removed, added, changed or missing line, sorted and de-duplicated, so a wrong entry cannot pass."""
    pattern = re.compile(r"^(removed|added|changed|missing)(?: \(\w+\))?: \S+ (\S+?)(?::| ->| \()")
    named = []
    for line in lines:
        match = pattern.match(line)
        if match:
            named.append((match.group(1), match.group(2)))
    return sorted(set(named))


def test_compare_reports_differences(tmp_path, capsys):
    lib = tmp_path / "Libs"
    (lib / "Custom").mkdir(parents=True)
    for stem in ("A", "B", "C"):
        (lib / "Custom" / f"{stem}.kicad_sym").write_text("x", encoding="utf-8")
    base = [
        ("A", "${KICAD_LIB_GITHUB}/Custom/A.kicad_sym"),
        ("B", "${KICAD_LIB_GITHUB}/Custom/B.kicad_sym"),
        ("C", "${KICAD_LIB_GITHUB}/Custom/C.kicad_sym"),
    ]
    before = _snap(tmp_path, capsys, "before", base, lib)

    same = _snap(tmp_path, capsys, "same", base, lib)
    code, text = _run(["compare", str(before), str(same)], capsys)
    assert code == 0
    assert text.strip() == "uri_diff: identical, 3 entries, 0 missing"

    removed = _snap(tmp_path, capsys, "removed", base[:2], lib)
    code, text = _run(["compare", str(before), str(removed)], capsys)
    assert code == 1
    lines = text.splitlines()
    assert "removed: sym-lib-table C (${KICAD_LIB_GITHUB}/Custom/C.kicad_sym)" in lines
    assert _named(lines) == [("removed", "C")]

    added = _snap(tmp_path, capsys, "added", [*base, ("D", "${KICAD_LIB_GITHUB}/Custom/D.kicad_sym")], lib)
    code, text = _run(["compare", str(before), str(added)], capsys)
    assert code == 1
    lines = text.splitlines()
    assert "added: sym-lib-table D (${KICAD_LIB_GITHUB}/Custom/D.kicad_sym)" in lines
    # D has no file on disk, so it is also reported missing; no other entry is named
    assert _named(lines) == [("added", "D"), ("missing", "D")]

    changed = _snap(
        tmp_path, capsys, "changed", [base[0], base[1], ("C", "${KICAD_LIB_GITHUB}/Custom/Other.kicad_sym")], lib
    )
    code, text = _run(["compare", str(before), str(changed)], capsys)
    assert code == 1
    lines = text.splitlines()
    assert any(line.startswith("changed: sym-lib-table C: ") for line in lines)
    assert _named(lines) == [("changed", "C"), ("missing", "C")]

    (lib / "Custom" / "B.kicad_sym").unlink()
    gone = _snap(tmp_path, capsys, "gone", base, lib)
    code, text = _run(["compare", str(before), str(gone)], capsys)
    assert code == 1
    lines = text.splitlines()
    assert any(line.startswith("missing (") and " sym-lib-table B -> " in line for line in lines)
    # B also shows as changed (its path no longer resolves); no other entry is named
    assert _named(lines) == [("changed", "B"), ("missing", "B")]


def test_compare_flags_missing_even_when_lists_match(tmp_path, capsys):
    lib = tmp_path / "Libs"
    lib.mkdir()
    entries = [("Gone", "${KICAD_LIB_GITHUB}/Custom/Gone.kicad_sym")]
    first = _snap(tmp_path, capsys, "one", entries, lib)
    second = _snap(tmp_path, capsys, "two", entries, lib)
    code, text = _run(["compare", str(first), str(second)], capsys)
    assert code == 1
    assert "missing" in text
    assert "Gone" in text


def _disabled_table(folder: Path, disabled: bool) -> Path:
    """sym-lib-table with one present library and one stale library whose file is gone."""
    folder.mkdir(parents=True, exist_ok=True)
    flag = "(disabled)" if disabled else ""
    (folder / "sym-lib-table").write_text(
        "(sym_lib_table\n  (version 7)\n"
        '  (lib (name "Here")(type "KiCad")(uri "${KICAD_LIB_GITHUB}/Custom/Here.kicad_sym")(options "")(descr ""))\n'
        f'  (lib (name "Stale")(type "KiCad")(uri "${{KICAD_LIB_GITHUB}}/Custom/Stale.kicad_sym")(options "")(descr ""){flag})\n'
        ")\n",
        encoding="utf-8",
    )
    return folder


def _disabled_snap(tmp_path: Path, capsys, name: str, disabled: bool) -> tuple[Path, str]:
    lib = tmp_path / "Libs"
    (lib / "Custom").mkdir(parents=True, exist_ok=True)
    (lib / "Custom" / "Here.kicad_sym").write_text("x", encoding="utf-8")
    tables = _disabled_table(tmp_path / f"cfg_{name}", disabled)
    out = tmp_path / f"{name}.json"
    code, text = _run(["snapshot", "--tables-dir", str(tables), "--var", f"KICAD_LIB_GITHUB={lib}", "--out", str(out)], capsys)
    assert code == 0
    return out, text


def test_parse_reads_the_disabled_flag():
    flags = uri_diff.parse_table((FIXTURES / "flags.fp-lib-table").read_text(encoding="utf-8"), "fp-lib-table")
    assert {e.name: e.disabled for e in flags} == {"Disabled_Lib": True, "Hidden_Lib": False, "Future_Lib": False}


def test_disabled_entry_with_a_gone_file_is_a_note_not_missing(tmp_path, capsys):
    """KiCad never loads a disabled library, so its gone file cannot break anything (owner, Phase 16)."""
    first, text = _disabled_snap(tmp_path, capsys, "one", disabled=True)
    assert "2 entries, 0 missing" in text
    assert "disabled, file not found: sym-lib-table Stale" in text
    snap = json.loads(first.read_text(encoding="utf-8"))
    assert snap["missing"] == []
    assert [item["name"] for item in snap["disabled_missing"]] == ["Stale"]
    second, _ = _disabled_snap(tmp_path, capsys, "two", disabled=True)
    code, text = _run(["compare", str(first), str(second)], capsys)
    assert code == 0
    assert "uri_diff: identical, 2 entries, 0 missing" in text
    assert "note: disabled, file not found (before): sym-lib-table Stale" in text


def test_enabled_entry_with_a_gone_file_is_still_missing(tmp_path, capsys):
    first, text = _disabled_snap(tmp_path, capsys, "one", disabled=False)
    assert "2 entries, 1 missing" in text
    second, _ = _disabled_snap(tmp_path, capsys, "two", disabled=False)
    code, text = _run(["compare", str(first), str(second)], capsys)
    assert code == 1
    assert "missing (before): sym-lib-table Stale" in text


def test_disabled_flag_change_is_a_difference(tmp_path, capsys):
    before, _ = _disabled_snap(tmp_path, capsys, "one", disabled=True)
    after, _ = _disabled_snap(tmp_path, capsys, "two", disabled=False)
    code, text = _run(["compare", str(before), str(after)], capsys)
    assert code == 1
    assert "changed: sym-lib-table Stale: disabled True -> False" in text


def _hashes(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_nothing_is_written_to_the_tables_folder(tmp_path, capsys):
    tables = _tables(tmp_path / "cfg", sym="basic.sym-lib-table", fp="reordered.fp-lib-table")
    (tables / "kicad_common.json").write_text(json.dumps({"environment": {"vars": {"KICAD_LIB_GITHUB": str(tmp_path)}}}), encoding="utf-8")
    before = _hashes(tables)
    listing = sorted(p.name for p in tables.iterdir())
    out = tmp_path / "snap.json"
    code, _ = _run(["snapshot", "--tables-dir", str(tables), "--out", str(out)], capsys)
    assert code == 0
    assert out.exists()
    assert sorted(p.name for p in tables.iterdir()) == listing
    assert _hashes(tables) == before


def test_variable_order_is_flag_then_json_then_environment(tmp_path, capsys, monkeypatch):
    tables = _tables(tmp_path / "cfg", sym="basic.sym-lib-table")
    from_json = tmp_path / "FromJson"
    from_flag = tmp_path / "FromFlag"
    from_env = tmp_path / "FromEnv"
    (tables / "kicad_common.json").write_text(
        json.dumps({"environment": {"vars": {"KICAD_LIB_GITHUB": str(from_json)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("KICAD_LIB_GITHUB", str(from_env))
    out = tmp_path / "snap.json"

    def first_resolved(*extra: str) -> str:
        code, _ = _run(["snapshot", "--tables-dir", str(tables), "--lib-root", str(from_json), "--out", str(out), *extra], capsys)
        assert code == 0
        return json.loads(out.read_text(encoding="utf-8"))["entries"][0]["resolved"]

    tail = "/Custom/Symbols/Fixture_A.kicad_sym"
    # kicad_common.json beats the process environment; --var beats both
    assert first_resolved() == "<LIB>" + tail
    assert first_resolved("--var", f"KICAD_LIB_GITHUB={from_flag}") == from_flag.as_posix() + tail
    # without kicad_common.json the process environment is used
    (tables / "kicad_common.json").unlink()
    code, _ = _run(["snapshot", "--tables-dir", str(tables), "--lib-root", str(from_env), "--out", str(out)], capsys)
    assert code == 0
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["entries"][0]["resolved"] == "<LIB>" + tail
    assert snap["vars"]["CUSTOM_3DMODEL_DIR"] is None


def test_no_env_ignores_the_process_environment(tmp_path, capsys, monkeypatch):
    tables = _tables(tmp_path / "cfg", sym="basic.sym-lib-table")
    monkeypatch.setenv("KICAD_LIB_GITHUB", str(tmp_path / "FromEnv"))
    out = tmp_path / "snap.json"
    code, _ = _run(["snapshot", "--tables-dir", str(tables), "--out", str(out)], capsys)
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["expanded"] is True
    code, _ = _run(["snapshot", "--tables-dir", str(tables), "--no-env", "--out", str(out)], capsys)
    assert code == 0
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["entries"][0]["expanded"] is False
    assert snap["vars"]["KICAD_LIB_GITHUB"] is None


def test_redact_home_replaces_whole_segments_only():
    home = "/srv/work/someone"
    snap = {"vars": {"A": home + "/kicad", "B": None}, "entries": [{"resolved": home}, {"resolved": home + "2/x"}, {"resolved": "/opt/x"}]}
    assert uri_diff.redact_home(snap, home) == {
        "vars": {"A": "<HOME>/kicad", "B": None},
        "entries": [{"resolved": "<HOME>"}, {"resolved": home + "2/x"}, {"resolved": "/opt/x"}],
    }
    assert uri_diff.redact_home("text", "") == "text"


def test_redact_home_flag_rewrites_the_snapshot(tmp_path, capsys, monkeypatch):
    elsewhere = tmp_path / "elsewhere" / "x.kicad_sym"
    tables = _text_table(tmp_path / "cfg", "sym", [("Outside", elsewhere.as_posix())])
    monkeypatch.setattr(uri_diff.Path, "home", classmethod(lambda cls: tmp_path))
    out = tmp_path / "snap.json"
    base = ["snapshot", "--tables-dir", str(tables), "--lib-root", str(tmp_path / "Libs"), "--out", str(out)]
    assert _run(base, capsys)[0] == 0
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["resolved"] == elsewhere.as_posix()
    assert _run([*base, "--redact-home"], capsys)[0] == 0
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["resolved"] == "<HOME>/elsewhere/x.kicad_sym"


def test_null_vars_and_unreadable_json_count_as_empty(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "kicad_common.json").write_text('{"environment": {"vars": null}}', encoding="utf-8")
    assert uri_diff.read_vars(cfg) == {}
    (cfg / "kicad_common.json").write_text("{not json", encoding="utf-8")
    assert uri_diff.read_vars(cfg) == {}
    assert uri_diff.read_vars(tmp_path / "nowhere") == {}


def test_vars_command(tmp_path, capsys):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "kicad_common.json").write_text(
        json.dumps({"environment": {"vars": {"KICAD_LIB_GITHUB": "/some/where"}}}), encoding="utf-8"
    )
    code, text = _run(["vars", "--config-dir", str(cfg)], capsys)
    assert code == 0
    assert "KICAD_LIB_GITHUB: /some/where" in text
    assert "CUSTOM_3DMODEL_DIR: not set" in text


def test_find_config_dir_takes_the_newest_version_folder(tmp_path, monkeypatch):
    base = tmp_path / "kicad"
    for version in ("9.0", "10.0", "8.0", "notes"):
        (base / version).mkdir(parents=True)
    monkeypatch.setattr(uri_diff, "_config_base", lambda: base)
    assert uri_diff.find_config_dir() == base / "10.0"
    monkeypatch.setattr(uri_diff, "_config_base", lambda: tmp_path / "absent")
    assert uri_diff.find_config_dir() is None


def test_expand_orders_and_reports():
    assert uri_diff.expand("${A}/x", {"A": "/root"}) == ("/root/x", True)
    assert uri_diff.expand("$(A)/x", {"A": "/root"}) == ("/root/x", True)
    assert uri_diff.expand("${B}/x", {"A": "/root"}) == ("${B}/x", False)
    assert uri_diff.expand("/plain/x", {}) == ("/plain/x", True)
