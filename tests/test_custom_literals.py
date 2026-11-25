"""The literal Custom lives only in collection.py (Phase 15).

The folder names of the collection are read from kicad_lib_manager.collection (OWN_DIR, SYMBOLS_DIR,
FOOTPRINTS_DIR, MODELS_DIR), so Phase 16 (repo split) and Phase 17 (catalogs under ThirdParty/) change
one module. These tests read every module with ``ast`` and never import the scanned code, with one
exception: test_shared_footprint_library_matches imports the two constants it compares.

A site is a string constant equal to "Custom", or starting with "Custom/" or "/Custom" (f-string pieces
included). Docstrings are not sites; neither is an f-string starting "Custom's".
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "kicad_lib_manager"


def custom_literals(source: str) -> list[tuple[int, str]]:
    """(line, value) of every Custom path literal in source, docstrings excluded."""
    tree = ast.parse(source)
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in docstrings:
            continue
        value = node.value
        if value == "Custom" or value.startswith("Custom/") or value.startswith("/Custom"):
            found.append((node.lineno, value))
    return sorted(found)


def package_modules() -> list[str]:
    """Posix paths relative to kicad_lib_manager of every .py module except collection.py."""
    return sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "__pycache__" not in path.parts and path.relative_to(PACKAGE).as_posix() != "collection.py"
    )


IMPORTER_MODULES = [m for m in package_modules() if m.startswith("importer/")]


def test_guard_sees_fstring_pieces_and_skips_docstrings():
    source = (
        '"""Module doc about Custom/Symbols."""\n'
        "def f(name):\n"
        '    """Reads Custom/ files."""\n'
        '    a = f"{name}/Custom/x"\n'
        '    b = "Custom/Symbols"\n'
        '    c = f"Custom\'s branch {name}"\n'
        '    d = "Custom"\n'
        '    e = f"/Custom/{name}"\n'
        "    return a, b, c, d, e\n"
    )
    values = [value for _, value in custom_literals(source)]
    assert "Custom/Symbols" in values
    assert "Custom" in values
    assert "/Custom/" in values
    assert not any("Module doc" in v or "Reads" in v for v in values)
    assert not any(v.startswith("Custom's") for v in values)
    assert "/Custom/x" in values  # the piece after {name} of an f-string


@pytest.mark.parametrize("module", IMPORTER_MODULES, ids=str)
def test_no_custom_literal_in_importer(module):
    found = custom_literals((PACKAGE / module).read_text(encoding="utf-8"))
    assert not found, f"{module} holds the Custom literal; read it from collection.py: " + ", ".join(
        f"line {line}: {value!r}" for line, value in found
    )


@pytest.mark.parametrize("module", [m for m in package_modules() if not m.startswith("importer/")], ids=str)
def test_no_custom_literal(module):
    found = custom_literals((PACKAGE / module).read_text(encoding="utf-8"))
    assert not found, f"{module} holds the Custom literal; read it from collection.py: " + ", ".join(
        f"line {line}: {value!r}" for line, value in found
    )


def test_shared_footprint_library_matches():
    """importer.stems keeps its own SHARED_FOOTPRINT_LIBRARY; this holds it equal to collection's."""
    from kicad_lib_manager import collection
    from kicad_lib_manager.importer import stems

    assert stems.SHARED_FOOTPRINT_LIBRARY == collection.SHARED_FOOTPRINT_LIBRARY
