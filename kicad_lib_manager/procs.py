"""The only module that starts a child process (Phase 15).

Every start passes the no-console-window flag on Windows, so no console flashes in a windowed or
frozen app; argv is always a list, never a shell string. Stdlib only.
"""

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass


def run_process(argv: Sequence[str], *, runner: Callable | None = None, **kwargs):
    """Run one child process and return its CompletedProcess; exceptions pass through to the caller.

    Output is captured unless the caller says otherwise, and the child gets no stdin unless the caller
    passes input (or its own stdin). `runner` stands in for subprocess.run in tests; subprocess.run
    is looked up per call, so a test may replace it after import.
    """
    kwargs.setdefault("capture_output", True)
    if "input" not in kwargs and "stdin" not in kwargs:
        kwargs["stdin"] = subprocess.DEVNULL
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    run = runner if runner is not None else subprocess.run
    return run(list(argv), **kwargs)


@dataclass(frozen=True)
class StreamOutcome:
    returncode: int | None
    stdout: bytes
    lines: tuple[str, ...]
    cancelled: bool
    timed_out: bool
