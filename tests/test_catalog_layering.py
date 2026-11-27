"""Layering guard for the library catalog package, kicad_lib_manager/catalog/ (Phase 17 plan 03; CAT-11, D-03).

Catalog modules are read with ``ast`` only, never imported, so the rules also hold for a module
a later plan has not written yet. The rules are proven on synthetic trees in ``tmp_path``
(``test_guard_*``); the checks on the real package are parametrized over the catalog modules that
exist on disk, so a module that is not there yet adds no skipped test.

Rules held for every catalog module:
- it is registered in ALLOWED (a module that needs another import edits ALLOWED in the same
  commit and says why; plans 17-04 to 17-14 add their modules here without editing this file);
- its relative imports resolve into its ALLOWED entry;
- it never imports PySide6, shiboken6, subprocess or kicad_lib_manager by absolute name, so
  procs stays the only process starter and the catalog stays Qt-free;
- it names no gitops commit or init function (D-03: the catalog adds no commit path);
- the package ``__init__.py`` holds nothing but a docstring.

One rule is about the rest of the application (CAT-11): the commit path cannot reach the
network. The transitive import closure of gitops, every importer module, the commit panel,
the import and migration windows, changes and atomic_fixes must not contain catalog.gitnet or
catalog.githubapi, however many modules lie between them.
"""

import ast
from collections import deque
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "kicad_lib_manager"

# Allowed package-internal imports per catalog module, keyed and written as dotted names relative to
# kicad_lib_manager. Only modules found on disk are checked, so an entry for a module a later plan
# writes raises no error until the module exists.
ALLOWED: dict[str, set[str]] = {
    "catalog": set(),
    "catalog.urls": {"models"},
    "catalog.licences": set(),
    "catalog.gitnet": {"models", "procs"},
    "catalog.githubapi": {"models"},
    "catalog.manifest": {"models", "fsutil", "collection", "catalog.urls"},
    "catalog.curated": {"models", "catalog.licences"},
    "catalog.validate": {"models", "fsutil", "kicad_files", "collection", "library_scanner"},
    "catalog.ops": {
        "models",
        "fsutil",
        "collection",
        "gitops",
        "kicad_process",
        "library_scanner",
        "catalog.manifest",
        "catalog.validate",
        "catalog.urls",
        "catalog.curated",
        "catalog.gitnet",
        "catalog.githubapi",
        "catalog.licences",
    },
    "catalog.status": {
        "models",
        "collection",
        "catalog.manifest",
        "catalog.curated",
        "catalog.gitnet",
        "catalog.licences",
        "catalog.urls",  # a library added by address is named owner/repo
    },
    "catalog.selection": {"models", "collection"},
}

FORBIDDEN_TOP = ("PySide6", "shiboken6", "subprocess", "kicad_lib_manager")
# the gitops functions that commit, stage, tag or create a repository (and its generic git runner)
COMMIT_NAMES = frozenset(
    {"commit_paths", "commit_gitlink", "add_intent", "unstage", "create_tag", "init_repository", "run_git"}
)
# the modules only the network side may import
NETWORK_MODULES = ("catalog.gitnet", "catalog.githubapi")
# the commit path: these modules, and every importer module
COMMIT_ROOTS = (
    "gitops",
    "changes",
    "atomic_fixes",
    "widgets.commit_panel",
    "widgets.import_dialog",
    "widgets.migration_dialog",
)


# -- pure helpers --------------------------------------------------------------


def module_key(path: Path, package_root: Path) -> str:
    """The dotted key of a file below package_root; an __init__ keeps its package key."""
    parts = list(path.relative_to(package_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def discover(package_root: Path, folder: str | None = "catalog") -> dict[str, Path]:
    """Map the key of every .py file under package_root/folder (the whole package when folder is None) to its path."""
    base = package_root / folder if folder else package_root
    if not base.is_dir():
        return {}
    return {module_key(p, package_root): p for p in sorted(base.rglob("*.py"))}


def resolve_relative(key: str, is_package: bool, level: int, module: str | None) -> str:
    """The dotted target of a relative import made from the module with this key."""
    parts = key.split(".")
    containing = parts if is_package else parts[:-1]
    up = level - 1
    if up > len(containing):
        # Climbs out of kicad_lib_manager: never a member of any ALLOWED entry
        return ".." + (module or "")
    base = containing[: len(containing) - up]
    if module:
        base = base + module.split(".")
    return ".".join(base)


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def relative_targets(key: str, path: Path, tree: ast.Module) -> set[str]:
    """Every package-internal target a relative import in the module names (the module, or each imported name)."""
    is_package = path.name == "__init__.py"
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            if node.module:
                found.add(resolve_relative(key, is_package, node.level, node.module))
            else:
                found.update(resolve_relative(key, is_package, node.level, a.name) for a in node.names)
    return found


def registration_errors(key: str, allowed: dict[str, set[str]] = ALLOWED) -> list[str]:
    if key in allowed:
        return []
    return [f"{key}: not registered in ALLOWED (add it to tests/test_catalog_layering.py)"]


def import_errors(key: str, path: Path, allowed: dict[str, set[str]] = ALLOWED) -> list[str]:
    if key not in allowed:
        return []
    return [
        f"{key}: imports {target}, which its ALLOWED entry forbids"
        for target in sorted(relative_targets(key, path, _tree(path)) - allowed[key])
    ]


def forbidden_import_errors(key: str, path: Path) -> list[str]:
    errors: list[str] = []
    for node in ast.walk(_tree(path)):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        errors.extend(
            f"{key}: absolute import of {name} is forbidden"
            for name in names
            if name.split(".")[0] in FORBIDDEN_TOP
        )
    return errors


def init_errors(key: str, path: Path) -> list[str]:
    if path.name == "__init__.py" and any(not _is_docstring(n) for n in _tree(path).body):
        return [f"{key}: package __init__.py must hold no code, only a docstring"]
    return []


def commit_name_errors(key: str, path: Path) -> list[str]:
    """One error per use of a commit, stage, tag or init function name, imported, called or attached."""
    seen: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            seen.add(node.id)
        elif isinstance(node, ast.Attribute):
            seen.add(node.attr)
        elif isinstance(node, ast.alias):
            seen.add(node.name.split(".")[-1])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen.add(node.name)
    return [f"{key}: names {name}, a commit path function (D-03)" for name in sorted(seen & COMMIT_NAMES)]


def catalog_errors(package_root: Path, allowed: dict[str, set[str]] = ALLOWED) -> list[str]:
    """Every per-module violation under package_root/catalog (used by the synthetic proofs)."""
    errors: list[str] = []
    for key, path in discover(package_root).items():
        errors += registration_errors(key, allowed)
        errors += import_errors(key, path, allowed)
        errors += forbidden_import_errors(key, path)
        errors += init_errors(key, path)
        errors += commit_name_errors(key, path)
    return errors


def import_graph(package_root: Path) -> dict[str, set[str]]:
    """Module key -> the keys of the package modules it imports, lazy imports inside functions included.

    A package import such as ``from ..catalog import gitnet`` adds the package and, when it exists as a
    module, the imported name; importing a module also imports its parent packages, which are added too.
    """
    modules = discover(package_root, None)
    graph: dict[str, set[str]] = {}
    for key, path in modules.items():
        tree = _tree(path)
        is_package = path.name == "__init__.py"
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = resolve_relative(key, is_package, node.level, node.module)
                elif node.module and node.module.split(".")[0] == "kicad_lib_manager":
                    base = ".".join(node.module.split(".")[1:])
                else:
                    continue
                found.add(base)
                found.update(f"{base}.{alias.name}" if base else alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == "kicad_lib_manager":
                        found.add(".".join(parts[1:]))
        for target in list(found):
            parts = target.split(".")
            found.update(".".join(parts[:i]) for i in range(1, len(parts)))
        graph[key] = {t for t in found if t in modules and t != key}
    return graph


def commit_path_roots(modules) -> list[str]:
    modules = set(modules)
    roots = [k for k in COMMIT_ROOTS if k in modules]
    roots += sorted(k for k in modules if k == "importer" or k.startswith("importer."))
    return roots


def reach_errors(package_root: Path) -> list[str]:
    """One message per commit-path root that reaches a network module, with the chain of imports."""
    graph = import_graph(package_root)
    errors: list[str] = []
    for root in commit_path_roots(graph):
        parent: dict[str, str | None] = {root: None}
        queue = deque([root])
        while queue:
            current = queue.popleft()
            for target in sorted(graph.get(current, ())):
                if target not in parent:
                    parent[target] = current
                    queue.append(target)
        for network in NETWORK_MODULES:
            if network in parent:
                chain, node = [], network
                while node is not None:
                    chain.append(node)
                    node = parent[node]
                errors.append(f"{root}: reaches {network} ({' -> '.join(reversed(chain))})")
    return errors


# -- synthetic self-tests (never skipped) --------------------------------------


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _clean_files() -> dict[str, str]:
    return {
        "models.py": "class Issue: ...\n",
        "procs.py": "",
        "gitops.py": "def commit_paths(): ...\ndef run_git(): ...\n",
        "collection.py": "from .models import Issue\n",
        "catalog/__init__.py": '"""Catalog."""\n',
        "catalog/gitnet.py": "from .. import procs\nfrom ..models import Issue\n",
        "catalog/manifest.py": "from ..models import Issue\nfrom ..collection import THIRD_PARTY_DIR\nfrom . import urls\n",
        "catalog/urls.py": "from ..models import Issue\n",
        "catalog/ops.py": "from ..models import Issue\nfrom . import gitnet, manifest\nfrom .gitnet import NetGit\n",
        "importer/__init__.py": '"""Importer."""\n',
        "importer/plan.py": "from ..models import Issue\n",
        "widgets/__init__.py": "",
        "widgets/commit_panel.py": "from .. import gitops\n",
    }


def test_guard_clean_tree_reports_nothing(tmp_path):
    root = tmp_path / "pkg"
    _write_tree(root, _clean_files())
    assert catalog_errors(root) == []
    assert reach_errors(root) == []


VIOLATIONS = [
    pytest.param("catalog/extra.py", "", "catalog.extra", "not registered", id="unregistered"),
    pytest.param(
        "catalog/gitnet.py", "\nfrom ..gitops import git_version\n", "catalog.gitnet", "imports gitops", id="upward-import"
    ),
    pytest.param(
        "catalog/gitnet.py", "\nfrom . import ops\n", "catalog.gitnet", "imports catalog.ops", id="sibling-not-allowed"
    ),
    pytest.param("catalog/urls.py", "\nimport PySide6.QtCore\n", "catalog.urls", "PySide6", id="qt-import"),
    pytest.param("catalog/urls.py", "\nimport shiboken6\n", "catalog.urls", "shiboken6", id="shiboken-import"),
    pytest.param("catalog/urls.py", "\nimport subprocess\n", "catalog.urls", "subprocess", id="subprocess-import"),
    pytest.param(
        "catalog/urls.py", "\nfrom subprocess import run\n", "catalog.urls", "subprocess", id="subprocess-from-import"
    ),
    pytest.param(
        "catalog/urls.py",
        "\nfrom kicad_lib_manager.models import Issue\n",
        "catalog.urls",
        "kicad_lib_manager",
        id="absolute-package-import",
    ),
    pytest.param("catalog/__init__.py", "\nX = 1\n", "catalog", "must hold no code", id="init-holds-code"),
    pytest.param(
        "catalog/ops.py",
        "\ndef go(ctx):\n    gitops.commit_paths(ctx)\n",
        "catalog.ops",
        "commit_paths",
        id="commit-call",
    ),
    pytest.param("catalog/urls.py", "\ndef run_git():\n    pass\n", "catalog.urls", "run_git", id="own-run-git"),
]


@pytest.mark.parametrize(("rel", "addition", "key", "fragment"), VIOLATIONS)
def test_guard_flags_violation(tmp_path, rel, addition, key, fragment):
    root = tmp_path / "pkg"
    files = _clean_files()
    files[rel] = files.get(rel, "") + addition
    _write_tree(root, files)
    errors = catalog_errors(root)
    assert len(errors) == 1, errors
    assert errors[0].startswith(key) and fragment in errors[0], errors


def test_guard_resolves_relative_imports():
    assert resolve_relative("catalog.gitnet", False, 2, "models") == "models"
    assert resolve_relative("catalog.gitnet", False, 2, "procs") == "procs"
    assert resolve_relative("catalog.ops", False, 1, "gitnet") == "catalog.gitnet"
    assert resolve_relative("catalog", True, 1, "gitnet") == "catalog.gitnet"
    assert resolve_relative("catalog.ops", False, 4, "models").startswith("..")


def test_guard_module_key_and_discover(tmp_path):
    root = tmp_path / "pkg"
    _write_tree(root, _clean_files())
    found = discover(root)
    assert sorted(found) == ["catalog", "catalog.gitnet", "catalog.manifest", "catalog.ops", "catalog.urls"]
    assert module_key(root / "catalog" / "__init__.py", root) == "catalog"
    assert discover(tmp_path / "missing") == {}


REACH = [
    pytest.param(
        {"importer/plan.py": "from ..catalog import gitnet\n"},
        "importer.plan: reaches catalog.gitnet (importer.plan -> ",
        id="importer-direct",
    ),
    pytest.param(
        {"widgets/commit_panel.py": "from ..catalog.ops import stage_add\n"},
        "widgets.commit_panel: reaches catalog.gitnet (widgets.commit_panel -> catalog.ops -> catalog.gitnet)",
        id="through-ops",
    ),
    pytest.param(
        {"gitops.py": "from .helper import go\n", "helper.py": "from .catalog.gitnet import NetGit\n"},
        "gitops: reaches catalog.gitnet (gitops -> helper -> catalog.gitnet)",
        id="through-a-helper",
    ),
    pytest.param(
        {"changes.py": "def late():\n    from .catalog import githubapi\n", "catalog/githubapi.py": ""},
        "changes: reaches catalog.githubapi (changes -> catalog.githubapi)",
        id="lazy-import-of-githubapi",
    ),
    pytest.param(
        {"atomic_fixes.py": "import kicad_lib_manager.catalog.gitnet\n"},
        "atomic_fixes: reaches catalog.gitnet (atomic_fixes -> catalog.gitnet)",
        id="absolute-import",
    ),
    pytest.param(
        {"widgets/import_dialog.py": "from . import helper\n", "widgets/helper.py": "from .. import catalog\nfrom ..catalog import ops\n"},
        "widgets.import_dialog: reaches catalog.gitnet (widgets.import_dialog -> widgets.helper -> catalog.ops -> catalog.gitnet)",
        id="two-hops-then-ops",
    ),
]


@pytest.mark.parametrize(("extra", "expected"), REACH)
def test_guard_flags_a_commit_path_that_reaches_the_network(tmp_path, extra, expected):
    root = tmp_path / "pkg"
    files = {**_clean_files(), **extra}
    _write_tree(root, files)
    errors = reach_errors(root)
    assert any(e.startswith(expected) for e in errors), errors


def test_guard_allows_the_catalog_to_use_the_network_itself(tmp_path):
    # the catalog windows are not on the commit path; only the roots are measured
    root = tmp_path / "pkg"
    files = {**_clean_files(), "widgets/catalog_dialog.py": "from ..catalog import ops, gitnet\n"}
    _write_tree(root, files)
    assert reach_errors(root) == []


# -- real-module checks (parametrized over the modules on disk) ------------------------

REAL = discover(PACKAGE)


def test_the_catalog_package_exists():
    assert "catalog" in REAL and "catalog.gitnet" in REAL


@pytest.mark.parametrize("key", sorted(REAL))
def test_every_catalog_module_is_registered(key):
    assert registration_errors(key) == []


@pytest.mark.parametrize("key", sorted(REAL))
def test_catalog_imports_point_only_where_allowed(key):
    assert import_errors(key, REAL[key]) == []


@pytest.mark.parametrize("key", sorted(REAL))
def test_catalog_is_qt_free_and_subprocess_free(key):
    assert forbidden_import_errors(key, REAL[key]) == []


@pytest.mark.parametrize("key", sorted(REAL))
def test_catalog_names_no_commit_function(key):
    assert commit_name_errors(key, REAL[key]) == []


def test_catalog_init_holds_no_code():
    assert init_errors("catalog", REAL["catalog"]) == []


def test_gitnet_imports_only_models_and_procs():
    assert relative_targets("catalog.gitnet", REAL["catalog.gitnet"], _tree(REAL["catalog.gitnet"])) <= {"models", "procs"}


def test_commit_path_cannot_reach_the_network():
    graph = import_graph(PACKAGE)
    # every root exists, so a rename cannot quietly empty the rule
    missing = [k for k in COMMIT_ROOTS if k not in graph]
    assert missing == []
    assert "importer.planner" in commit_path_roots(graph)
    assert "catalog.gitnet" in graph
    errors = reach_errors(PACKAGE)
    assert errors == [], "\n".join(errors)
