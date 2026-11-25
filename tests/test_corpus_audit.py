"""Static audit that keeps the public suite from reading repository data again (D-18, PITFALLS 11).

The public tests run from a fresh clone that holds neither the Custom or WurthElektronik submodules nor the vendor
downloads. This module reads test source files only (no git, no Qt) and fails when a test module builds a path from
the repository root to that data, when a skip reason names a missing vendor download, Custom submodule or KiCad
install (those cases are deselected through the corpus and needs_kicad marks, never skipped), or when a module that
reads the corpus carries no corpus mark. The detectors are proven on planted lines first.
"""

import re

from runfixtures import TESTS_DIR

# Modules exempt from the audits: the helper that owns the corpus path and the conftest that gates on it
_HELPER = "corpusfixtures.py"
_NOT_MARKED_CHECKED = {"conftest.py", _HELPER}


# The spellings a test uses for the repository root, then a slash and a quoted data folder name
_ROOT = r"(?:\bREPO_ROOT|\bREPO|Path\(__file__\)\.resolve\(\)\.(?:parent\.parent|parents\[1\]))"
_DATA = r"""["'](?:Custom|WurthElektronik|downloaded_examples|\.planning)["']"""
_REPO_DATA_RE = re.compile(rf"{_ROOT}\s*/\s*{_DATA}|{_ROOT}\.joinpath\(\s*{_DATA}")

# A skip call, then (through its balanced closing parenthesis) a reason that names a missing corpus-type resource
_SKIP_CALL_RE = re.compile(r"(?:pytest\.skip|pytest\.mark\.skipif|pytest\.mark\.skip|\bskipif)\(")
_SKIP_REASON_RE = re.compile(r"not present|not checked out|kicad install", re.IGNORECASE)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _call_text(text: str, start: int) -> str:
    """The call text from the opening parenthesis at index start to its balanced close (to the end when unbalanced)."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def repo_data_lines(text: str) -> list[int]:
    """Line numbers (1-based) that build a path from the repository root to repository data."""
    return sorted({_line_of(text, match.start()) for match in _REPO_DATA_RE.finditer(text)})


def corpus_skip_lines(text: str) -> list[int]:
    """Line numbers (1-based) of a skip whose reason names a missing vendor download, Custom submodule or KiCad install."""
    lines = set()
    for match in _SKIP_CALL_RE.finditer(text):
        call = _call_text(text, match.end() - 1)  # match.end() - 1 is the opening parenthesis
        if _SKIP_REASON_RE.search(call):
            lines.add(_line_of(text, match.start()))
    return sorted(lines)


def _sources() -> list:
    return [path for path in sorted(TESTS_DIR.glob("*.py")) if path.name != _HELPER]


def _planted(*pieces: str) -> str:
    return "".join(pieces)


# ── The detectors, proven on planted lines ────────────────────────────────────────


def test_audit_finds_planted_paths():
    """Each repository-root spelling followed by a data folder is found; scratch and corpus paths are not."""
    root_spellings = [
        _planted("REPO_ROOT", " / ", '"', "Custom", '"'),
        _planted("REPO", " / ", '"', "WurthElektronik", '"'),
        _planted("Path(__file__).resolve().parent.parent", " / ", '"', "downloaded_examples", '"'),
        _planted("Path(__file__).resolve().parents[1]", " / ", '"', ".planning", '"'),
    ]
    clean = [
        _planted("tmp_path", " / ", '"', "Custom", '"'),
        _planted("repos.parent", " / ", '"', ".planning", '"'),
        _planted("corpus_", "path(", '"', "Custom", '"', ")"),
        _planted("REPO_ROOT", " / ", '"', "tests", '"'),
    ]
    text = "\n".join(["import x"] + [f"a = {line}" for line in root_spellings] + [f"b = {line}" for line in clean])

    assert repo_data_lines(text) == [2, 3, 4, 5]
    assert repo_data_lines("\n".join(clean)) == []


def test_audit_finds_planted_skips():
    """A skip that names a missing download, submodule or KiCad install is found; the opt-in and symlink skips are not."""
    flagged = [
        _planted("    pytest.skip(", '"the sample is not ', "present", '"', ")"),
        _planted('@pytest.mark.skipif(not LIVE, reason="Custom submodule not ', "checked out", '")'),
        _planted('@pytest.mark.skipif(not LIVE, reason="no KiCad ', "install", ' found")'),
    ]
    split = _planted("@pytest.mark.skipif(\n", "    not LIVE,\n", '    reason="no KiCad ', "install", ' found",\n)')
    ignored = [
        'pytest.mark.skipif(not os.environ.get("KICAD_IMPORT_UAT_DIR"), reason="set KICAD_IMPORT_UAT_DIR to run it")',
        'pytest.mark.skipif(not os.environ.get("KICAD_ATOMIC_UAT_DIR"), reason="set KICAD_ATOMIC_UAT_DIR to run it")',
        'pytest.skip("directory links are not available here")',
    ]

    assert corpus_skip_lines("\n".join(["import x"] + flagged)) == [2, 3, 4]
    assert corpus_skip_lines("x = 1\n" + split) == [2]
    assert corpus_skip_lines("\n".join(ignored)) == []


# ── The repository-wide audits ────────────────────────────────────────────────────


def test_no_test_module_reads_repo_data():
    """No test module builds a path from the repository root to Custom, WurthElektronik, downloaded_examples or .planning."""
    offenders = []
    for path in _sources():
        for number in repo_data_lines(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}:{number}")

    assert not offenders, "use corpus_path(...) behind the corpus mark, or a scratch folder: " + ", ".join(offenders)


def test_no_corpus_type_skips():
    """No skip reason names a missing vendor download, Custom submodule or KiCad install: those tests are deselected."""
    offenders = []
    for path in _sources():
        for number in corpus_skip_lines(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}:{number}")

    assert not offenders, "mark the test corpus or needs_kicad instead of skipping it: " + ", ".join(offenders)


def test_corpus_readers_are_marked():
    """A module that calls the corpus path helpers carries the corpus (or wurth) mark, so a closed gate deselects it."""
    unmarked = []
    for path in _sources():
        if path.name in _NOT_MARKED_CHECKED:
            continue
        text = path.read_text(encoding="utf-8")
        if not re.search(r"\bcorpus_(?:path|root)\(", text):
            continue
        if "pytest.mark.corpus" not in text and "pytest.mark.wurth" not in text:
            unmarked.append(path.name)

    assert not unmarked, "these modules read the corpus without a corpus mark: " + ", ".join(unmarked)
