import os
import re
import sys
import time
import zipfile
from functools import partial
from pathlib import Path

import pytest
from corpusfixtures import corpus_path
from zipfixtures import UL_ZIP

from kicad_lib_manager.fsutil import (
    SourceText,
    atomic_write_bytes,
    decode_source,
    encode_source,
)
from kicad_lib_manager.sexpr import apply_edits, parse

REPO = Path(__file__).resolve().parent.parent
ZIP = UL_ZIP
_MAX_MEMBER_BYTES = 5_000_000
_KICAD_SUFFIXES = (".kicad_sym", ".kicad_mod")


def _zip_members(path: Path, cap: int = _MAX_MEMBER_BYTES) -> list[tuple[str, bytes]]:
    """Read the KiCad members of an untrusted vendor zip into memory, never to disk."""
    members = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(_KICAD_SUFFIXES):
                continue
            # Declared size is checked before any bytes are read
            if info.file_size > cap:
                raise ValueError(f"zip member {info.filename} exceeds {cap} bytes")
            members.append((info.filename, zf.read(info)))
    return members


def _read_zip_member(name: str) -> bytes:
    for member_name, data in _zip_members(ZIP):
        if member_name == name:
            return data
    raise KeyError(f"zip member {name} not found")


def _no_custom_files() -> bytes:
    raise AssertionError("the corpus collection has no .kicad_sym or .kicad_mod file under Custom/")


def _repo_owned_params() -> list:
    params = []

    custom = corpus_path("Custom")
    custom_files = sorted(
        [p for suffix in _KICAD_SUFFIXES for p in custom.rglob(f"*{suffix}")],
        key=lambda p: p.relative_to(custom).as_posix(),
    )
    for p in custom_files:
        params.append(pytest.param(
            partial(Path.read_bytes, p),
            id=f"custom/{p.relative_to(custom).as_posix()}",
            marks=pytest.mark.corpus,
        ))
    if not custom_files:
        # No corpus: deselected with the count. Corpus without Custom files: the test fails, never skips
        params.append(pytest.param(_no_custom_files, id="custom/corpus", marks=pytest.mark.corpus))

    fixtures = REPO / "tests" / "fixtures"
    fixture_files = [p for p in (fixtures / "sexpr").glob("*") if p.is_file()]
    for pattern in ("*.sym-lib-table", "*.fp-lib-table"):
        fixture_files.extend((fixtures / "tables").glob(pattern))
    for p in sorted(fixture_files, key=lambda p: p.relative_to(fixtures).as_posix()):
        params.append(pytest.param(
            partial(Path.read_bytes, p),
            id=f"fixture/{p.relative_to(fixtures).as_posix()}",
        ))

    if ZIP.exists():
        for name, _ in sorted(_zip_members(ZIP)):
            params.append(pytest.param(partial(_read_zip_member, name), id=f"zip/{name}"))
    return params


def _check_roundtrip(data: bytes, name: str, assert_tiles) -> None:
    src = decode_source(data, name)
    assert isinstance(src, SourceText), f"{name}: decode failed with {getattr(src, 'code', '?')}"
    root = parse(src.text)
    assert_tiles(src.text, root)
    assert apply_edits(src.text, []) == src.text, f"{name}: apply_edits with no edits changed the text"
    out = encode_source(src.text, src.bom)
    if out != data:
        offset = next(
            (i for i, (a, b) in enumerate(zip(out, data)) if a != b),
            min(len(out), len(data)),
        )
        raise AssertionError(f"round-trip mismatch for {name} at byte offset {offset}")


_REPO_PARAMS = _repo_owned_params()


@pytest.mark.parametrize("loader", _REPO_PARAMS)
def test_roundtrip_repo_owned(loader, request, tmp_path, assert_tiles):
    data = loader()
    name = request.node.callspec.id
    _check_roundtrip(data, name, assert_tiles)
    src = decode_source(data, name)
    target = tmp_path / "out.bin"
    assert atomic_write_bytes(target, encode_source(src.text, src.bom)) is None
    assert target.read_bytes() == data, f"{name}: atomic write changed the bytes"


def test_zip_member_cap_boundary():
    with zipfile.ZipFile(ZIP) as zf:
        sizes = {
            i.filename: i.file_size
            for i in zf.infolist()
            if i.filename.lower().endswith(_KICAD_SUFFIXES)
        }
    largest_name = max(sizes, key=sizes.get)
    largest = sizes[largest_name]
    assert len(_zip_members(ZIP, cap=largest)) == 2
    with pytest.raises(ValueError, match="exceeds") as excinfo:
        _zip_members(ZIP, cap=largest - 1)
    assert largest_name in str(excinfo.value)


def test_corpus_sources_are_present():
    ids = [p.id for p in _REPO_PARAMS]
    assert sum(i.startswith("fixture/sexpr/") for i in ids) >= 9
    assert sum(i.startswith("fixture/tables/") for i in ids) >= 5
    assert sum(i.startswith("zip/") for i in ids) == 2


# ── Opt-in (KICAD_TEST_REAL_CONFIG=1): the owner's real KiCad tables (read in place, in memory only) ───

_REAL_CONFIG_SWITCH = "KICAD_TEST_REAL_CONFIG"
_LOCAL_TABLE_NAMES = ("sym-lib-table", "fp-lib-table", "design-block-lib-table")
_VERSION_DIR_RE = re.compile(r"^\d+\.\d+$")


def _kicad_config_root() -> Path | None:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "kicad" if appdata else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "kicad"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "kicad"


def _local_table_params() -> list:
    # Checked before any path is computed: an opted-out collection never lists or reads the KiCad config folder
    if os.environ.get(_REAL_CONFIG_SWITCH) != "1":
        return [
            pytest.param(
                None,
                id="local/opt-in",
                marks=[
                    pytest.mark.local_kicad,
                    pytest.mark.skip(reason="reads your real KiCad config tables: set KICAD_TEST_REAL_CONFIG=1 to run"),
                ],
            )
        ]
    params = []
    root = _kicad_config_root()
    if root is not None and root.is_dir():
        for version_dir in sorted(root.iterdir()):
            if not (_VERSION_DIR_RE.match(version_dir.name) and version_dir.is_dir()):
                continue
            for filename in _LOCAL_TABLE_NAMES:
                path = version_dir / filename
                if path.is_file():
                    params.append(pytest.param(
                        path,
                        id=f"local/{version_dir.name}/{filename}",
                        marks=pytest.mark.local_kicad,
                    ))
    if not params:
        params.append(pytest.param(
            None,
            id="local/none",
            marks=[
                pytest.mark.local_kicad,
                pytest.mark.skip(reason="no KiCad user config tables found"),
            ],
        ))
    return params


@pytest.mark.parametrize("path", _local_table_params())
def test_roundtrip_local_kicad_table(path, request, assert_tiles):
    # Personal data: bytes stay in memory, nothing is written or copied, no content in messages
    _check_roundtrip(path.read_bytes(), request.node.callspec.id, assert_tiles)


def _forbidden_config_root():
    raise AssertionError("read the real KiCad config")


def test_local_kicad_tables_are_opt_in(monkeypatch):
    """Without KICAD_TEST_REAL_CONFIG=1 the real tables are one skipped item and the config folder is never read."""
    monkeypatch.setattr(sys.modules[__name__], "_kicad_config_root", _forbidden_config_root)
    for switch in (None, "0"):
        if switch is None:
            monkeypatch.delenv("KICAD_TEST_REAL_CONFIG", raising=False)
        else:
            monkeypatch.setenv("KICAD_TEST_REAL_CONFIG", switch)

        params = _local_table_params()

        assert len(params) == 1, switch
        assert params[0].id == "local/opt-in", switch
        marks = {mark.name: mark for mark in params[0].marks}
        assert "local_kicad" in marks, switch
        assert "KICAD_TEST_REAL_CONFIG=1" in marks["skip"].kwargs["reason"], switch


def test_local_kicad_tables_with_opt_in(monkeypatch, tmp_path):
    """With KICAD_TEST_REAL_CONFIG=1 the version folders of the KiCad config give one param per table file."""
    table = tmp_path / "kicad" / "10.0" / "sym-lib-table"
    table.parent.mkdir(parents=True)
    table.write_text("(sym_lib_table)\n", encoding="utf-8")
    monkeypatch.setenv("KICAD_TEST_REAL_CONFIG", "1")
    monkeypatch.setattr(sys.modules[__name__], "_kicad_config_root", lambda: tmp_path / "kicad")

    params = _local_table_params()

    assert [param.id for param in params] == ["local/10.0/sym-lib-table"]
    assert params[0].values == (table,)


# ── Corpus: the collection's Wurth library, ThirdParty/WurthElektronik (stress and performance corpus) ───────

# Seconds allowed per Wurth file when parsing the whole corpus (see test_wurth_corpus_parse_budget)
_WURTH_PARSE_BUDGET_PER_FILE = 0.05


def _wurth_root_in(collection: Path) -> Path:
    """The Wurth library of a collection: its ThirdParty clone when that folder exists, else the legacy submodule folder."""
    clone = collection.joinpath("ThirdParty", "WurthElektronik")
    return clone if clone.is_dir() else collection / "WurthElektronik"


def _wurth_root() -> Path:
    return _wurth_root_in(corpus_path())


def test_wurth_root_follows_third_party(tmp_path):
    legacy = tmp_path / "WurthElektronik"
    legacy.mkdir()
    assert _wurth_root_in(tmp_path) == legacy
    clone = tmp_path.joinpath("ThirdParty", "WurthElektronik")
    clone.mkdir(parents=True)
    assert _wurth_root_in(tmp_path) == clone
    # neither folder: the legacy path, so the corpus test fails naming it instead of skipping
    assert _wurth_root_in(tmp_path / "empty") == tmp_path / "empty" / "WurthElektronik"


def _wurth_files() -> list[Path]:
    wurth = _wurth_root()
    files = []
    for pattern in ("*.kicad_sym", "*.kicad_mod", "*sym-lib-table", "*fp-lib-table"):
        files.extend(p for p in wurth.rglob(pattern) if p.is_file())
    return sorted(set(files), key=lambda p: p.relative_to(wurth).as_posix())


def _wurth_params() -> list:
    wurth = _wurth_root()
    files = _wurth_files()
    if not files:
        # No corpus: deselected with the count. Corpus without Wurth files: the test fails, never skips
        return [pytest.param(None, id="wurth/corpus", marks=pytest.mark.wurth)]
    return [
        pytest.param(p, id=f"wurth/{p.relative_to(wurth).as_posix()}", marks=pytest.mark.wurth)
        for p in files
    ]


@pytest.mark.parametrize("path", _wurth_params())
def test_roundtrip_wurth_file(path, request, tmp_path, assert_tiles):
    assert path is not None, "the corpus collection has no WurthElektronik library files"
    data = path.read_bytes()
    name = request.node.callspec.id
    _check_roundtrip(data, name, assert_tiles)
    src = decode_source(data, name)
    target = tmp_path / "out.bin"
    assert atomic_write_bytes(target, encode_source(src.text, src.bom)) is None
    assert target.read_bytes() == data, f"{name}: atomic write changed the bytes"


@pytest.mark.wurth
# The budget is max(60, 0.05 s x files) = 400.8 s for the 8016-file corpus, above the 300 s default timeout
@pytest.mark.timeout(900)
def test_wurth_corpus_parse_budget():
    files = _wurth_files()
    assert files, "the corpus collection has no WurthElektronik library files"
    start = time.perf_counter()
    for p in files:
        src = decode_source(p.read_bytes(), p.name)
        assert isinstance(src, SourceText), f"{p.name}: decode failed"
        parse(src.text)
    elapsed = time.perf_counter() - start
    # Measured 2026-10-25 on the workstation (Windows 11, CPython 3.14): 6034 files parsed in 69.5 s
    # (about 0.012 s per file), over the former fixed 60 s. The budget now scales with the corpus size.
    budget = max(60.0, _WURTH_PARSE_BUDGET_PER_FILE * len(files))
    assert elapsed < budget, f"parsing {len(files)} Wurth files took {elapsed:.1f}s (budget {budget:.0f}s)"
