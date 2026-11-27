#!/usr/bin/env python3
"""Inert skeleton of the Wurth conversion script (Phase 17, plan 17-09); the behaviour follows in the next commit."""

import copy
import importlib.util
import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from kicad_lib_manager.kicad_process import kicad_running  # noqa: E402,F401


def _load_uri_diff():
    path = TOOL_ROOT / "scripts" / "split" / "uri_diff.py"
    spec = importlib.util.spec_from_file_location("wurth_uri_diff", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wurth_uri_diff"] = module
    spec.loader.exec_module(module)
    return module


uri_diff = _load_uri_diff()

DEFAULT_TAG = "pre-wurth-catalog"
TEMPLATES = Path(__file__).resolve().parent / "collection"
ALLOWED_GIT = frozenset()


@dataclass
class ConversionPlan:
    problems: list[str] = field(default_factory=list)


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _git(repo, *args, timeout=600):
    return subprocess.CompletedProcess(args, 0, b"", b"")


def rewrite_snapshot(snap):
    return copy.deepcopy(snap)


def stale_var_lines(config_base, new_value):
    return []


def plan(repo, before, after, *, config_dir=None, backup_dir=None, tag=DEFAULT_TAG):
    return ConversionPlan()


def way_back(repo, module_dir, backup_dir, tag, *, include_move):
    return []


def apply(repo, plan_, *, backup_dir, tag, message):
    return 0


def main(argv=None):
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
