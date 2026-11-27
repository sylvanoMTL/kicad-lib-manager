"""The only module that starts a child process (Phase 15; streaming and cancellable since Phase 17).

Every start passes the no-console-window flag on Windows, so no console flashes in a windowed or
frozen app; argv is always a list, never a shell string. run_process runs a short child to its end;
start_process starts a long one (a download) whose stderr is streamed line by line and whose whole
process tree can be ended. Stdlib only.
"""

import codecs
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# Callers catch timeouts and the like without importing subprocess
ProcessError = subprocess.SubprocessError

_LINE_SPLIT = re.compile(r"[\r\n]")
_KEEP_LINES = 40
# After the child has exited, how long a pipe held open by a grandchild is waited for
_EXIT_GRACE = 2.0


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
    """How a streamed child ended; lines keeps the last 40 stderr lines."""

    returncode: int | None
    stdout: bytes
    lines: tuple[str, ...]
    cancelled: bool
    timed_out: bool


def kill_tree(pid: int, *, platform: str | None = None, runner: Callable | None = None) -> None:
    """End a process and all its children; never raises (a process that is already gone is fine)."""
    if (platform or sys.platform) == "win32":
        root = os.environ.get("SystemRoot") or os.environ.get("windir") or "C:\\Windows"
        exe = os.path.join(root, "System32", "taskkill.exe")
        try:
            run_process([exe, "/T", "/F", "/PID", str(pid)], runner=runner, timeout=15)
        except (OSError, ProcessError):
            pass
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


_EOF = object()


class StreamedProcess:
    """A started child whose stderr is read by a thread, so a caller can poll, stop and time out.

    Built only by start_process. stderr is split on carriage returns and newlines (git redraws its
    progress with \\r); stdout is kept as bytes when it was captured.
    """

    def __init__(self, popen, *, capture_stdout: bool = False):
        self._proc = popen
        self.pid = popen.pid
        self._lines: queue.SimpleQueue = queue.SimpleQueue()
        self._stdout = bytearray()
        self._kill_lock = threading.Lock()
        self._killed = False
        self._threads = []
        if popen.stderr is not None:
            self._threads.append(self._spawn(self._read_stderr))
        self._stdout_thread = None
        if capture_stdout and popen.stdout is not None:
            self._stdout_thread = self._spawn(self._read_stdout)
            self._threads.append(self._stdout_thread)

    @staticmethod
    def _spawn(target) -> threading.Thread:
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread

    def _read_stderr(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending = ""
        try:
            while True:
                chunk = self._proc.stderr.read1(4096)
                if not chunk:
                    break
                parts = _LINE_SPLIT.split(pending + decoder.decode(chunk))
                pending = parts.pop()
                for part in parts:
                    if part:
                        self._lines.put(part)
            pending += decoder.decode(b"", final=True)
            if pending:
                self._lines.put(pending)
        except (OSError, ValueError):
            pass  # the pipe was closed under the reader
        finally:
            self._lines.put(_EOF)

    def _read_stdout(self) -> None:
        try:
            while True:
                chunk = self._proc.stdout.read1(65536)
                if not chunk:
                    break
                self._stdout.extend(chunk)
        except (OSError, ValueError):
            pass

    def kill(self) -> None:
        """End the child and its children, once; later calls do nothing."""
        with self._kill_lock:
            if self._killed:
                return
            self._killed = True
        kill_tree(self.pid)
        try:
            self._proc.kill()
        except (OSError, AttributeError):
            pass

    def run(
        self,
        *,
        stop: Callable[[], bool] | None = None,
        timeout: float | None = None,
        on_line: Callable[[str], None] | None = None,
        poll: float = 0.2,
    ) -> StreamOutcome:
        """Wait for the child, handing each stderr line to on_line.

        stop() and the clock are checked after every line and at least every poll seconds, also while the
        child prints nothing. On stop or timeout the child and its children are ended before this returns.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        tail: deque[str] = deque(maxlen=_KEEP_LINES)
        cancelled = timed_out = eof = False
        exited_at: float | None = None

        def take(item) -> None:
            nonlocal eof
            if item is _EOF:
                eof = True
                return
            tail.append(item)
            if on_line is not None:
                on_line(item)

        while True:
            try:
                take(self._lines.get(timeout=poll))
            except queue.Empty:
                pass
            if stop is not None and stop():
                cancelled = True
                self.kill()
                break
            if deadline is not None and time.monotonic() >= deadline:
                timed_out = True
                self.kill()
                break
            if eof:
                break
            if self._proc.poll() is not None:
                # a grandchild may hold the pipe open after the child is gone
                exited_at = exited_at or time.monotonic()
                if time.monotonic() - exited_at > _EXIT_GRACE:
                    break
        try:
            returncode = self._proc.wait(timeout=15)
        except ProcessError:
            returncode = None
        for thread in self._threads:
            thread.join(timeout=2)
        while not eof:
            try:
                take(self._lines.get_nowait())
            except queue.Empty:
                break
        return StreamOutcome(returncode, bytes(self._stdout), tuple(tail), cancelled, timed_out)


def start_process(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    cwd=None,
    capture_stdout: bool = False,
    popen: Callable | None = None,
) -> StreamedProcess:
    """Start a child without waiting: no stdin, stderr piped for streaming, its own process group.

    `popen` stands in for subprocess.Popen in tests; subprocess.Popen is looked up per call. Exceptions
    from the start (OSError) pass through to the caller.
    """
    options: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "env": env,
        "cwd": cwd,
    }
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        options["start_new_session"] = True
    start = popen if popen is not None else subprocess.Popen
    return StreamedProcess(start(list(argv), **options), capture_stdout=capture_stdout)
