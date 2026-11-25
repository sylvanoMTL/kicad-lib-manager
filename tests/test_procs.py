"""procs.run_process: the one child-process starter (Phase 15, ROOT-06 note).

Pure tests use a recording runner and start no process. An AST rule holds that no other module
under kicad_lib_manager/ starts a process on its own.
"""

import ast
import subprocess
from pathlib import Path

from kicad_lib_manager import procs
from kicad_lib_manager.procs import run_process

PACKAGE = Path(procs.__file__).resolve().parent
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_STARTERS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
_OS_STARTERS = ("system", "popen", "startfile", "spawn", "exec")


def _recorder():
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    return runner, calls


def test_run_process_sets_the_window_flag():
    runner, calls = _recorder()
    run_process(("tool", "--x"), runner=runner)
    ((argv, kwargs),) = calls
    assert argv == ["tool", "--x"] and isinstance(argv, list)
    assert kwargs["creationflags"] == NO_WINDOW
    assert kwargs["capture_output"] is True
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert "shell" not in kwargs


def test_run_process_keeps_input():
    runner, calls = _recorder()
    run_process(["tool"], runner=runner, input=b"x")
    ((_, kwargs),) = calls
    assert kwargs["input"] == b"x"
    assert "stdin" not in kwargs


def test_run_process_keeps_caller_options():
    runner, calls = _recorder()
    run_process(["tool"], runner=runner, capture_output=False, text=True, timeout=3, env={"A": "1"}, creationflags=0x8)
    ((_, kwargs),) = calls
    assert kwargs["capture_output"] is False
    assert kwargs["text"] is True and kwargs["timeout"] == 3 and kwargs["env"] == {"A": "1"}
    assert kwargs["creationflags"] == 0x8 | NO_WINDOW


def test_run_process_looks_up_subprocess_run_at_call_time(monkeypatch):
    seen = []

    def patched(argv, **kwargs):
        seen.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", patched)
    run_process(["tool"])
    assert len(seen) == 1 and seen[0][0] == ["tool"]


def test_run_process_passes_exceptions_through():
    def timing_out(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    def failing(argv, **kwargs):
        raise OSError("no such file")

    for runner, expected in ((timing_out, subprocess.TimeoutExpired), (failing, OSError)):
        try:
            run_process(["tool"], runner=runner)
        except expected:
            pass
        else:  # pragma: no cover
            raise AssertionError("the exception was swallowed")


def _starter_references(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "subprocess" and node.attr in _STARTERS:
                found.append(f"subprocess.{node.attr}")
            if node.value.id == "os" and node.attr.startswith(_OS_STARTERS):
                found.append(f"os.{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            found.extend(f"from subprocess import {a.name}" for a in node.names if a.name in _STARTERS)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found.extend(f"from os import {a.name}" for a in node.names if a.name.startswith(_OS_STARTERS))
    return found


def test_only_procs_starts_processes():
    offenders = {}
    scanned = 0
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name == "procs.py" and path.parent == PACKAGE:
            continue
        scanned += 1
        found = _starter_references(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            offenders[path.relative_to(PACKAGE).as_posix()] = found
    assert scanned > 10
    assert not offenders, f"only procs.py may start a process: {offenders}"
