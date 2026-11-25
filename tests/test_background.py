"""The daemon-thread runner of widgets/background.py: delivery thread, failure text, cancel, isolation."""
import sys
import threading

import pytest

from kicad_lib_manager.widgets import background
from kicad_lib_manager.widgets.background import run_in_background, running_tasks


def test_result_is_delivered_on_the_gui_thread(qtbot):
    gui = threading.get_ident()
    got = []
    task = run_in_background(lambda: 41 + 1, lambda value: got.append((value, threading.get_ident())))
    qtbot.waitUntil(task.is_done, timeout=30000)
    assert got == [(42, gui)]


def test_function_runs_on_a_daemon_thread(qtbot):
    seen = []

    def fn():
        thread = threading.current_thread()
        seen.append((thread.daemon, thread is threading.main_thread()))
        return None

    task = run_in_background(fn, lambda _value: None)
    qtbot.waitUntil(task.is_done, timeout=30000)
    assert seen == [(True, False)]


def test_exception_is_delivered_as_text(qtbot):
    results, failures = [], []

    def fn():
        raise ValueError("boom")

    task = run_in_background(fn, results.append, failures.append)
    qtbot.waitUntil(task.is_done, timeout=30000)
    assert failures == ["ValueError: boom"] and results == []


def test_cancelled_task_delivers_nothing(qtbot):
    gate = threading.Event()
    results, failures = [], []
    task = run_in_background(lambda: gate.wait(10), results.append, failures.append)
    try:
        task.cancel()
        assert task.is_done() and task.is_running()
    finally:
        gate.set()
    qtbot.waitUntil(lambda: not task.is_running(), timeout=30000)
    qtbot.wait(50)
    assert results == [] and failures == []


def test_running_tasks_counts_a_blocked_task(qtbot):
    before = running_tasks()
    gate = threading.Event()
    task = run_in_background(lambda: gate.wait(10), lambda _value: None)
    try:
        assert running_tasks() == before + 1
    finally:
        gate.set()
    qtbot.waitUntil(task.is_done, timeout=30000)
    qtbot.waitUntil(lambda: running_tasks() == before, timeout=30000)


def test_a_raising_callback_does_not_stop_the_next_delivery(qtbot, monkeypatch):
    """Code review WR-09: both outcomes are in one drain, so only the guard keeps the second delivery."""
    reported = []
    monkeypatch.setattr(sys, "excepthook", lambda *info: reported.append(info[1]))
    got = []

    def bad(_value):
        raise RuntimeError("callback failed")

    dispatcher = background._dispatcher()
    first = run_in_background(lambda: 1, bad)
    qtbot.waitUntil(lambda: not first.is_running(), timeout=30000)
    second = run_in_background(lambda: 2, got.append)
    # No tick between the puts: nothing is delivered until the one drain below
    dispatcher._timer.stop()
    qtbot.waitUntil(lambda: not second.is_running(), timeout=30000)
    assert not first.is_done() and not second.is_done()

    dispatcher._drain()  # one drain must deliver both: the first raises, the second still arrives

    assert [str(exc) for exc in reported] == ["callback failed"]
    assert got == [2]
    assert first.is_done() and second.is_done()
    assert not dispatcher._timer.isActive()


def test_poll_timer_stops_when_nothing_is_outstanding(qtbot):
    timer = background._dispatcher()._timer
    task = run_in_background(lambda: 1, lambda _value: None)
    assert timer.isActive()
    qtbot.waitUntil(task.is_done, timeout=30000)
    qtbot.waitUntil(lambda: not timer.isActive(), timeout=30000)


def test_a_base_exception_from_fn_leaves_no_stuck_task(qtbot):
    """Code review WR-10: SystemExit is reported as a failure and the task, timer and counter settle."""
    before = running_tasks()
    timer = background._dispatcher()._timer
    failures = []

    def fn():
        raise SystemExit(3)

    task = run_in_background(fn, lambda _value: None, failures.append)
    qtbot.waitUntil(task.is_done, timeout=30000)
    assert failures == ["SystemExit: 3"]
    qtbot.waitUntil(lambda: not timer.isActive(), timeout=30000)
    qtbot.waitUntil(lambda: running_tasks() == before, timeout=30000)
    assert not task.is_running()


def test_a_failing_thread_start_leaves_no_stuck_task(qtbot, monkeypatch):
    """Code review WR-10: when the thread cannot start, the caller sees the error and nothing stays pending."""
    before = running_tasks()
    dispatcher = background._dispatcher()
    real_start = threading.Thread.start

    def start(self):
        if self.name == "wr10-start-fails":
            raise RuntimeError("can't start new thread")
        return real_start(self)

    monkeypatch.setattr(threading.Thread, "start", start)
    with pytest.raises(RuntimeError, match="can't start new thread"):
        run_in_background(lambda: 1, lambda _value: None, name="wr10-start-fails")
    assert running_tasks() == before
    assert not dispatcher._pending
    assert not dispatcher._timer.isActive()
