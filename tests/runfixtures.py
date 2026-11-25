"""Child pytest runs for the harness meta-tests (plain helper module, not collected).

run_pytest starts `python -m pytest` on a throwaway folder outside the repository, with the repo's own
tests/conftest.py loaded as a plugin, so a meta-test exercises the real hooks and fixtures. Why each flag:

- `-p conftest` loads tests/conftest.py as a plugin (the child folder has no conftest of its own), so the
  child runs the repo's fixtures and hooks.
- `-c <repo>/pyproject.toml` brings the repo's markers (an unregistered marker still fails) and timeout settings.
- `--rootdir` and `--confcutdir` pin the child to its own folder. `--confcutdir` is required: without it pytest
  walked the whole temp folder for 78 s while this was planned and failed on a vanished folder.
- `-o addopts=-ra --strict-markers` removes the repo's `-n`, `--dist` and `-m` defaults, so each meta-test
  states the worker count and marker selection it needs.
- `--basetemp` is always a folder the caller owns, outside the repository (pytest wipes it at start).
"""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"


def child_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment of a child run: PYTEST_* variables dropped, tests/ and the repo on PYTHONPATH.

    PYTEST_XDIST_WORKER, PYTEST_CURRENT_TEST and PYTEST_ADDOPTS of the parent run must not leak into the child.
    """
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PYTEST_")}
    env["PYTHONPATH"] = os.pathsep.join([str(TESTS_DIR), str(REPO_ROOT)])
    if extra:
        env.update(extra)
    return env


def write_tree(root: Path, files: Mapping[str, str]) -> Path:
    """Write each relative name with its UTF-8 text under root (parents created) and return root."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run_pytest(
    run_dir: Path,
    *args: str,
    basetemp: Path,
    env: Mapping[str, str] | None = None,
    timeout: float = 180,
) -> subprocess.CompletedProcess[str]:
    """Run pytest on run_dir in a child process with the repo conftest loaded; stdout and stderr are captured."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            "conftest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            "--rootdir",
            str(run_dir),
            "--confcutdir",
            str(run_dir),
            "-o",
            "addopts=-ra --strict-markers",
            "--basetemp",
            str(basetemp),
            *args,
            str(run_dir),
        ],
        cwd=run_dir,
        env=child_env(env),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def collect_repo(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    """Collect (never run) the repo suite in a child process; the caller's -m states the selection.

    `-o addopts=--strict-markers` drops the repo's `-n` and default `-m 'not slow'`, so the child collects
    serially with the repo's own pyproject and tests/conftest.py.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=--strict-markers",
            *args,
        ],
        cwd=REPO_ROOT,
        env=child_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
