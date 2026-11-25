"""A folder check blocked on a dead drive at close must not abort the process at exit (UAT gap 1, WR-03).

The real MainWindow runs in a child process (tests/hungcheckchild.py): a QThread still blocked at
interpreter shutdown aborts with exit code 0xC0000409, a daemon thread is simply abandoned.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from collectionfixtures import make_collection

CHILD = Path(__file__).with_name("hungcheckchild.py")


@pytest.mark.parametrize("mode", ["switch", "recent", "choose", "first-run", "new-collection"])
def test_exit_is_clean_with_a_check_blocked_at_close(mode, tmp_path):
    make_collection(tmp_path / "a")
    make_collection(tmp_path / "b")
    done = subprocess.run(
        [sys.executable, str(CHILD), mode, str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        cwd=str(CHILD.parent.parent),
    )
    report = f"returncode={done.returncode}\nstdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    # Without the marker the test proves nothing
    assert "BLOCKED_AT_CLOSE=1" in done.stdout, report
    # The exit code is the primary signal: the abort can leave stderr empty
    assert done.returncode == 0, report
    assert "QThread: Destroyed" not in done.stderr, report


PACKAGE = Path(__file__).resolve().parent.parent / "kicad_lib_manager"
FOLDER_CHECK_MODULES = ("choose_folder_dialog.py", "first_run_dialog.py", "new_collection_dialog.py")


def _names(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.alias):
            found.add(node.name.split(".")[-1])
    return found


def test_folder_checks_never_use_a_qthread():
    """A QThread blocked on a dead drive aborts the process at exit: the dialogs' checks use daemon threads only."""
    for name in FOLDER_CHECK_MODULES:
        tree = ast.parse((PACKAGE / "widgets" / name).read_text(encoding="utf-8"))
        used = _names(tree) & {"TaskWorker", "QThread"}
        assert not used, f"{name} uses {sorted(used)}"
    main_tree = ast.parse((PACKAGE / "main_window.py").read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(main_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "TaskWorker"
    ]
    assert len(calls) == 2, "main_window.py keeps TaskWorker only for the two KiCad-open checks"
    for path in PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("join_workers", "PARKED_WORKERS", "JOIN_BUDGET_MS"):
            assert needle not in text, f"{path.name} still names {needle}"
