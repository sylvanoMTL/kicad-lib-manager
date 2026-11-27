"""procs.start_process and StreamedProcess on real Python children (Phase 17, CAT-11).

The children are Python only (never git), so the quick-run repository tripwire does not fire and the
module is not slow. Every wait is bounded.
"""

import io
import os
import subprocess
import sys
import time
from pathlib import Path

from kicad_lib_manager.procs import kill_tree, run_process, start_process

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _python(script: str) -> list[str]:
    return [sys.executable, "-I", "-c", script]


def test_lines_split_on_carriage_return_and_newline():
    seen = []
    script = "import sys; sys.stderr.buffer.write(b'a 10%\\rb 20%\\nc\\n'); sys.stderr.flush()"
    outcome = start_process(_python(script)).run(on_line=seen.append)
    assert seen == ["a 10%", "b 20%", "c"]
    assert outcome.returncode == 0 and not outcome.cancelled and not outcome.timed_out
    assert outcome.lines == ("a 10%", "b 20%", "c")


def test_last_partial_line_reaches_on_line():
    seen = []
    script = "import sys; sys.stderr.buffer.write(b'first\\nlast without newline'); sys.stderr.flush()"
    start_process(_python(script)).run(on_line=seen.append)
    assert seen == ["first", "last without newline"]


def test_stdout_is_captured_when_asked():
    script = "import sys; sys.stdout.buffer.write(b'hello'); sys.stdout.flush()"
    assert start_process(_python(script), capture_stdout=True).run().stdout == b"hello"
    assert start_process(_python(script)).run().stdout == b""


def test_stop_is_polled_while_the_child_is_silent():
    started = time.monotonic()
    process = start_process(_python("import time; time.sleep(60)"))
    outcome = process.run(stop=lambda: time.monotonic() - started > 0.5)
    assert outcome.cancelled and not outcome.timed_out
    assert time.monotonic() - started < 5
    assert outcome.returncode is not None  # the child has ended


def test_timeout_ends_the_child():
    started = time.monotonic()
    outcome = start_process(_python("import time; time.sleep(60)")).run(timeout=0.5)
    assert outcome.timed_out and not outcome.cancelled
    assert time.monotonic() - started < 5
    assert outcome.returncode is not None


def _is_running(pid: int) -> bool:
    if sys.platform == "win32":
        exe = os.path.join(os.environ.get("SystemRoot", ""), "System32", "tasklist.exe")
        done = run_process([exe, "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], timeout=30)
        return f'"{pid}"' in done.stdout.decode("utf-8", errors="replace")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_kill_ends_the_grandchild():
    script = (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(60)'])\n"
        "sys.stderr.write('grandchild %d\\n' % g.pid); sys.stderr.flush()\n"
        "time.sleep(60)\n"
    )
    process = start_process(_python(script))
    found: list[int] = []

    def on_line(line: str) -> None:
        if line.startswith("grandchild "):
            found.append(int(line.split()[1]))
            process.kill()

    outcome = process.run(on_line=on_line, timeout=30)
    assert found and not outcome.timed_out
    deadline = time.monotonic() + 5
    while _is_running(found[0]) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _is_running(found[0]), "the grandchild survived the kill"


class _FakePopen:
    def __init__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        self.pid = 4242
        self.stderr = io.BytesIO(b"")
        self.stdout = None


def test_start_process_flags():
    made = []

    def popen(argv, **kwargs):
        made.append(_FakePopen(argv, **kwargs))
        return made[-1]

    start_process(("tool", Path("x")), popen=popen)
    (fake,) = made
    assert fake.argv == ["tool", Path("x")] and isinstance(fake.argv, list)
    assert fake.kwargs["stdin"] is subprocess.DEVNULL
    assert fake.kwargs["stdout"] is subprocess.DEVNULL
    assert fake.kwargs["stderr"] is subprocess.PIPE
    assert "shell" not in fake.kwargs
    if sys.platform == "win32":
        assert fake.kwargs["creationflags"] & NO_WINDOW and fake.kwargs["creationflags"] & NEW_GROUP
    else:
        assert fake.kwargs["start_new_session"] is True


def test_kill_tree_uses_taskkill_on_windows():
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    kill_tree(123, platform="win32", runner=runner)
    ((argv,),) = [(c,) for c in calls]
    assert argv[0].lower().endswith("taskkill.exe")
    assert argv[-4:] == ["/T", "/F", "/PID", "123"]
