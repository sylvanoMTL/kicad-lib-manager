"""Static audit that keeps the public suite from reading repository data again (D-18, PITFALLS 11).

The public tests run from a fresh clone that holds neither the Custom or WurthElektronik submodules, the collection's ThirdParty folder nor the vendor
downloads. This module reads test source files only (no git, no Qt) and fails when a test module builds a path from
the repository root to that data, when a skip reason names a missing vendor download, Custom submodule or KiCad
install (those cases are deselected through the corpus and needs_kicad marks, never skipped), or when a module that
reads the corpus carries no corpus mark. The detectors are proven on planted lines first.
"""

import ast
import re

from runfixtures import TESTS_DIR

# Modules exempt from the audits: the helper that owns the corpus path and the conftest that gates on it
_HELPER = "corpusfixtures.py"
_NOT_MARKED_CHECKED = {"conftest.py", _HELPER}


# The spellings a test uses for the repository root (any name that ends in ROOT or REPO, such as REPO_ROOT or ROOT),
# then a slash and a quoted data folder name, which may carry a path after it ("Custom/Symbols")
_ROOT = r"(?:\b\w*(?:ROOT|REPO)\b|Path\(__file__\)(?:\.resolve\(\))?\.(?:parent\.parent|parents\[1\]))"
_DATA = r"""["'](?:Custom|WurthElektronik|ThirdParty|downloaded_examples|\.planning)(?:["']|[/\\])"""
_REPO_DATA_RE = re.compile(rf"{_ROOT}\s*/\s*{_DATA}|{_ROOT}\.joinpath\(\s*{_DATA}|os\.path\.join\(\s*{_ROOT}\s*,\s*{_DATA}")

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


_REASON_NAME_RE = re.compile(r"\breason\s*=\s*([A-Za-z_]\w*)")


def _constant_text(text: str, name: str) -> str:
    """The right-hand side of the module-level assignment `name = ...`, continuation lines included."""
    match = re.search(rf"(?ms)^{re.escape(name)}\s*=\s*(.*?)(?=^\S|\Z)", text)
    return match.group(1) if match else ""


def corpus_skip_lines(text: str) -> list[int]:
    """Line numbers (1-based) of a skip whose reason names a missing vendor download, Custom submodule or KiCad install.

    The reason may be written in the call or held by a module-level constant that the call names (reason=NAME).
    """
    lines = set()
    for match in _SKIP_CALL_RE.finditer(text):
        call = _call_text(text, match.end() - 1)  # match.end() - 1 is the opening parenthesis
        if _SKIP_REASON_RE.search(call):
            lines.add(_line_of(text, match.start()))
            continue
        for named in _REASON_NAME_RE.findall(call):
            if _SKIP_REASON_RE.search(_constant_text(text, named)):
                lines.add(_line_of(text, match.start()))
    return sorted(lines)


_CORPUS_READERS = {"corpus_path", "corpus_root"}


def _names(node: ast.AST) -> set[str]:
    """Every identifier the node uses (names and attributes; string text is not code and is left out)."""
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
    return found


def _has_corpus_mark(node: ast.AST) -> bool:
    """True when the node uses pytest.mark.corpus or pytest.mark.wurth."""
    return any(
        isinstance(child, ast.Attribute)
        and child.attr in ("corpus", "wurth")
        and isinstance(child.value, ast.Attribute)
        and child.value.attr == "mark"
        for child in ast.walk(node)
    )


def unmarked_corpus_tests(text: str) -> list[str]:
    """Names of the test functions that reach corpus data without a corpus or wurth mark.

    Reaching means calling corpus_path / corpus_root, or using a module-level name (constant or helper) whose
    definition does, directly or through another such name. A definition whose parameters carry their own
    corpus mark (`marks=pytest.mark.corpus`) is not counted: the gate deselects those parameters one by one.
    A mark may sit on the test, on its class, in a module-level pytestmark, in a parametrize `marks=` argument,
    or behind a module-level alias (a name, or a decorator function, that applies such a mark).
    """
    tree = ast.parse(text)
    definitions: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("test"):
            definitions[node.name] = node
    if any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        and _has_corpus_mark(node)
        for node in tree.body
    ):
        return []

    aliases = {name for name, node in definitions.items() if _has_corpus_mark(node)}
    reaching = {
        name
        for name, node in definitions.items()
        if _names(node) & _CORPUS_READERS and not (name in aliases and "marks" in _keywords(node))
    }
    grew = True
    while grew:
        grew = False
        for name, node in definitions.items():
            if name in aliases:
                continue
            if name not in reaching and (_names(node) & reaching) - {name}:
                reaching.add(name)
                grew = True
        for name, node in definitions.items():
            if name not in aliases and _names(node) & aliases:
                aliases.add(name)
                grew = True

    def is_marked(decorators: list[ast.expr]) -> bool:
        return any(_has_corpus_mark(d) or _names(d) & aliases for d in decorators)

    offenders: list[str] = []

    def visit(nodes: list[ast.stmt], class_marked: bool) -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, class_marked or is_marked(node.decorator_list))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                body = ast.Module(body=node.body, type_ignores=[])
                reads = bool(_names(body) & (_CORPUS_READERS | reaching))
                if reads and not (class_marked or is_marked(node.decorator_list)):
                    offenders.append(node.name)

    visit(tree.body, False)
    return offenders


def _keywords(node: ast.AST) -> set[str]:
    return {kw.arg for child in ast.walk(node) if isinstance(child, ast.keyword) for kw in [child] if kw.arg}


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


def test_audit_finds_widened_path_spellings():
    """Any root name that ends in ROOT or REPO, a path inside the quoted folder, os.path.join and a bare parent.parent."""
    flagged = [
        _planted("ROOT", " / ", '"', "Custom", '"'),
        _planted("SOURCE_REPO", " / ", '"', "Custom/Symbols", '"'),
        _planted("REPO_ROOT", " / ", '"', "downloaded_examples/x.zip", '"'),
        _planted("Path(__file__).parent.parent", " / ", '"', "WurthElektronik", '"'),
        _planted("os.path.join(", "REPO_ROOT, ", '"', "Custom", '"', ")"),
    ]
    clean = [
        _planted("ROOT", " / ", '"', "scripts", '"'),
        _planted("tmp_path", " / ", '"', "Custom/Symbols", '"'),
        _planted("os.path.join(", "tmp_path, ", '"', "Custom", '"', ")"),
    ]
    assert repo_data_lines("\n".join(flagged)) == [1, 2, 3, 4, 5]
    assert repo_data_lines("\n".join(clean)) == []


def test_audit_finds_third_party_paths():
    """A path from the repository root to the collection's ThirdParty folder is found; the corpus helper's path is not."""
    flagged = [
        _planted("REPO_ROOT", " / ", '"', "ThirdParty", '"'),
        _planted("ROOT", " / ", '"', "ThirdParty/WurthElektronik", '"'),
        _planted("os.path.join(", "REPO_ROOT, ", '"', "ThirdParty", '"', ")"),
    ]
    reader = _planted("corpus_", "path")
    clean = [_planted("tmp_path", " / ", '"', "ThirdParty", '"'), f"{reader}('ThirdParty', 'SparkFun')"]
    assert repo_data_lines("\n".join(flagged)) == [1, 2, 3]
    assert repo_data_lines("\n".join(clean)) == []
    # inside a corpus-marked test the helper's path is the allowed way in; unmarked, it is still found
    marked = f"import pytest\n@pytest.mark.corpus\ndef test_a():\n    {reader}('ThirdParty')\n"
    assert unmarked_corpus_tests(marked) == []
    assert unmarked_corpus_tests(marked.replace("@pytest.mark.corpus\n", "")) == ["test_a"]


def test_audit_finds_a_skip_reason_held_in_a_constant():
    text = _planted('_SKIP = "sample ', "not ", "present", ' here"\n', "@pytest.mark.skipif(not LIVE, reason=_SKIP)\n")
    assert corpus_skip_lines(text) == [2]
    harmless = '_SKIP = "set the switch to run it"\n@pytest.mark.skipif(not LIVE, reason=_SKIP)\n'
    assert corpus_skip_lines(harmless) == []


def test_audit_checks_the_mark_per_test():
    """A module with one marked test does not excuse an unmarked one that reaches the corpus."""
    reader = _planted("corpus_", "path")
    text = (
        "import pytest\n"
        f"DATA = {reader}('Custom')\n"
        f"def _helper():\n    return DATA.read_text()\n"
        "requires = pytest.mark.corpus\n"
        "@pytest.mark.corpus\ndef test_marked():\n    _helper()\n"
        "@requires\ndef test_alias():\n    _helper()\n"
        "def test_unmarked():\n    _helper()\n"
        f"def test_direct():\n    {reader}('x')\n"
        "def test_fine():\n    assert 1 + 1 == 2\n"
        "class TestGroup:\n    def test_in_class(self):\n        _helper()\n"
        "@pytest.mark.parametrize('x', [pytest.param(1, marks=pytest.mark.corpus)])\ndef test_param(x):\n    _helper()\n"
    )
    assert unmarked_corpus_tests(text) == ["test_unmarked", "test_direct", "test_in_class"]
    assert unmarked_corpus_tests("pytestmark = pytest.mark.corpus\n" + text) == []
    # the helper's text mentioning the reader in a string is not a reader
    assert unmarked_corpus_tests(f"def test_a():\n    assert '{reader}(x)'\n") == []


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
    """No test module builds a path from the repository root to Custom, WurthElektronik, ThirdParty, downloaded_examples or .planning."""
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


def test_every_corpus_reading_test_is_marked():
    """Per test, not per module: a test that reaches the corpus carries the corpus (or wurth) mark itself."""
    offenders = []
    for path in _sources():
        if path.name in _NOT_MARKED_CHECKED:
            continue
        for name in unmarked_corpus_tests(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}::{name}")

    assert not offenders, "these tests reach the corpus without a corpus mark: " + ", ".join(offenders)


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
