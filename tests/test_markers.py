"""Meta-tests for the slow marker and strict markers (Phase 14, TEST-06)."""

import ast

import pytest
from runfixtures import REPO_ROOT, TESTS_DIR, collect_repo, run_pytest, write_tree

# Tests carrying requires_git that only read this checkout and create no repository (id -> reason).
# Empty since the vendor zips left the tool repo; kept for a future read-only git test. With the first entry,
# add a test that each entry exists, carries requires_git and is not slow (the check that was removed while empty).
_READ_ONLY_GIT_TESTS: dict[str, str] = {}

_OFFENDER_HINT = (
    "mark it @pytest.mark.slow (it creates a real git repository) or, if it only reads this checkout, "
    "add it to _READ_ONLY_GIT_TESTS with a reason"
)


def _tail(done) -> str:
    return (done.stdout + done.stderr)[-3000:]


def _lines(*lines: str) -> str:
    return "\n".join(lines) + "\n"


# ── Collection audits ─────────────────────────────────────────────────────────────


def test_wurth_and_kicad_cli_tests_are_slow():
    """No test marked wurth, kicad_cli or kicad_cli_path escapes the slow mark."""
    done = collect_repo("-m", "(wurth or kicad_cli) and not slow")

    assert done.returncode == 5, _tail(done)


def test_slow_marker_is_registered_and_used():
    """The slow marker is registered (strict markers pass) and at least one test carries it."""
    done = collect_repo("-m", "slow")

    assert done.returncode == 0, _tail(done)
    assert "collected" in done.stdout, _tail(done)


def test_corpus_and_needs_kicad_are_registered():
    """pyproject registers corpus and needs_kicad, and the wurth entry says it implies corpus."""
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+; the module must still import on 3.10
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = data["tool"]["pytest"]["ini_options"]["markers"]

    assert any(marker.startswith("corpus:") for marker in markers)
    assert any(marker.startswith("needs_kicad:") for marker in markers)
    wurth = [marker for marker in markers if marker.startswith("wurth:")]
    assert len(wurth) == 1 and "implies corpus" in wurth[0]


# ── Static audit of requires_git ──────────────────────────────────────────────────


def _is_slow(node: ast.expr) -> bool:
    return ast.unparse(node) == "pytest.mark.slow"


def _module_is_slow(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
            if any(_is_slow(value) for value in values):
                return True
    return False


def _test_functions(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            yield node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                    yield child


def test_requires_git_tests_are_slow():
    """Every test decorated requires_git is slow, except the allow-listed read-only ones."""
    offenders = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _module_is_slow(tree):
            continue
        for func in _test_functions(tree):
            decorators = func.decorator_list
            if not any(isinstance(d, ast.Name) and d.id == "requires_git" for d in decorators):
                continue
            if any(_is_slow(d) for d in decorators):
                continue
            ident = f"{path.name}::{func.name}"
            if ident not in _READ_ONLY_GIT_TESTS:
                offenders.append(ident)

    assert not offenders, f"{_OFFENDER_HINT}: {offenders}"


# ── Child runs ────────────────────────────────────────────────────────────────────


def test_kicad_cli_fixture_users_are_slow(tmp_path):
    """A test that requests kicad_cli_path is mapped to slow, so the quick selection finds nothing."""
    run_dir = write_tree(
        tmp_path / "run",
        {"test_cli_user.py": _lines("def test_uses_cli(kicad_cli_path):", "    assert kicad_cli_path")},
    )

    done = run_pytest(run_dir, "--collect-only", "-q", "-m", "not slow", basetemp=tmp_path / "bt")

    assert done.returncode == 5, _tail(done)


def test_full_option_runs_slow_tests(tmp_path):
    """--full turns the quick selection `-m 'not slow'` into the full one."""
    text = _lines(
        "import pytest",
        "",
        "",
        "@pytest.mark.slow",
        "def test_slow():",
        "    pass",
        "",
        "",
        "def test_plain():",
        "    pass",
    )
    run_dir = write_tree(tmp_path / "run", {"test_pair.py": text})

    quick = run_pytest(run_dir, "-n", "0", "-m", "not slow", basetemp=tmp_path / "bt1")
    full = run_pytest(run_dir, "-n", "0", "-m", "not slow", "--full", basetemp=tmp_path / "bt2")

    assert quick.returncode == 0, _tail(quick)
    assert "1 passed, 1 deselected" in quick.stdout, _tail(quick)
    assert full.returncode == 0, _tail(full)
    assert "2 passed" in full.stdout, _tail(full)


def test_unregistered_marker_still_fails(tmp_path):
    """Strict markers stay on: a test with an unknown marker fails the run, naming it."""
    text = _lines("import pytest", "", "", "@pytest.mark.not_registered_here", "def test_one():", "    pass")
    run_dir = write_tree(tmp_path / "run", {"test_unregistered.py": text})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt")

    assert done.returncode != 0, _tail(done)
    assert "not_registered_here" in done.stdout + done.stderr, _tail(done)


def test_unmarked_git_test_fails_loudly(tmp_path):
    """An unmarked test that builds a real git repository fails at once and the output names it."""
    text = _lines(
        "from gitfixtures import make_superproject",
        "",
        "",
        "def test_builds(tmp_path):",
        "    make_superproject(tmp_path / 'r')",
    )
    run_dir = write_tree(tmp_path / "run", {"test_unmarked_git.py": text})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt")

    assert done.returncode != 0, _tail(done)
    assert "test_unmarked_git.py::test_builds builds a real git repository: mark it @pytest.mark.slow" in done.stdout, _tail(done)


def test_unmarked_own_git_repo_fails_loudly(tmp_path):
    """An unmarked test that starts git init or git clone fails at teardown, naming itself; status and slow tests do not."""
    text = _lines(
        "import shutil",
        "import subprocess",
        "",
        "import pytest",
        "",
        'GIT = shutil.which("git") or "git"',
        "",
        "",
        "def _run(argv):",
        "    try:",
        "        subprocess.run(argv, capture_output=True, timeout=60)",
        "    except FileNotFoundError:",
        "        pass",
        "",
        "",
        "def test_inits(tmp_path):",
        '    _run([GIT, "-c", "init.defaultBranch=main", "init", str(tmp_path / "a")])',
        "",
        "",
        "def test_clones_by_string(tmp_path):",
        "    _run(f'\"{GIT}\" clone \"{tmp_path / \"missing\"}\" \"{tmp_path / \"dest\"}\"')",
        "",
        "",
        "def test_status(tmp_path):",
        '    _run([GIT, "-C", str(tmp_path), "status"])',
        "",
        "",
        "@pytest.mark.slow",
        "def test_slow_init(tmp_path):",
        '    _run([GIT, "init", str(tmp_path / "b")])',
    )
    run_dir = write_tree(tmp_path / "run", {"test_own_git.py": text})

    done = run_pytest(run_dir, "-n", "0", basetemp=tmp_path / "bt")

    out = done.stdout
    assert done.returncode != 0, _tail(done)
    assert "test_own_git.py::test_inits creates a real git repository (git init): mark it @pytest.mark.slow" in out, _tail(done)
    assert (
        "test_own_git.py::test_clones_by_string creates a real git repository (git clone): mark it @pytest.mark.slow" in out
    ), _tail(done)
    assert "2 errors" in out, _tail(done)
    assert "test_status creates" not in out, _tail(done)
    assert "test_slow_init creates" not in out, _tail(done)
