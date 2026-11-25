"""Folder checks that may block on a dead network drive, run on daemon threads.

A check such as Path.is_dir() on a disconnected UNC path can block for tens of seconds. It must
never run on a QThread: a QThread still blocked when the interpreter shuts down is destroyed
while running, and Qt aborts the process ("QThread: Destroyed while thread is still running",
exit code 0xC0000409). A daemon threading.Thread blocked the same way is simply abandoned at
exit, and no QThread object exists to be destroyed, so the abort cannot happen by construction.

Design:
- run_in_background starts one daemon thread per check. The thread only runs the check function
  and puts its outcome on a module-level queue.SimpleQueue; it never touches Qt.
- One module-level dispatcher QObject, created lazily on the GUI thread, owns a QTimer (POLL_MS)
  that runs only while an outcome is outstanding. Each tick drains the queue and calls the
  callbacks on the GUI thread, unless the task was cancelled.
- cancel() drops the outcome and releases the callbacks at once; the thread is abandoned and
  never joined.

A signal emitted from the worker thread was rejected: it would touch a Qt object from a thread
the interpreter is tearing down.
"""
import queue
import sys
import threading
from typing import Callable

from PySide6.QtCore import QCoreApplication, QObject, QTimer

POLL_MS = 15

_outcomes: "queue.SimpleQueue[tuple[BackgroundTask, bool, object]]" = queue.SimpleQueue()
_count_lock = threading.Lock()
_started_not_returned = 0


class BackgroundTask:
    """One check running on a daemon thread; created by run_in_background, used from the GUI thread."""

    def __init__(self, name: str, on_result: Callable[[object], None],
                 on_failed: Callable[[str], None] | None):
        self.name = name
        self._on_result: Callable[[object], None] | None = on_result
        self._on_failed: Callable[[str], None] | None = on_failed
        self._returned = threading.Event()
        self._finished = False  # outcome delivered or task cancelled (GUI thread only)

    def is_running(self) -> bool:
        """True while the check function has not returned."""
        return not self._returned.is_set()

    def is_done(self) -> bool:
        """True once the outcome was delivered or the task was cancelled."""
        return self._finished

    def cancel(self) -> None:
        """Never deliver the outcome; the callbacks are released at once and the thread is not waited for."""
        self._finished = True
        self._on_result = None
        self._on_failed = None
        dispatcher = _existing_dispatcher()
        if dispatcher is not None:
            dispatcher.forget(self)

    def _deliver(self, ok: bool, payload: object) -> None:
        callback = self._on_result if ok else self._on_failed
        self._finished = True
        self._on_result = None
        self._on_failed = None
        if callback is not None:
            callback(payload)


class _Dispatcher(QObject):
    """Drains the outcome queue on the GUI thread while a task is outstanding."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pending: set[BackgroundTask] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._drain)

    def add(self, task: BackgroundTask) -> None:
        self._pending.add(task)
        if not self._timer.isActive():
            self._timer.start()

    def forget(self, task: BackgroundTask) -> None:
        self._pending.discard(task)
        self._stop_if_idle()

    def _stop_if_idle(self) -> None:
        if not self._pending and self._timer.isActive():
            self._timer.stop()

    def _drain(self) -> None:
        while True:
            try:
                task, ok, payload = _outcomes.get_nowait()
            except queue.Empty:
                break
            # A cancelled task (or a late outcome of one) is dropped
            if task not in self._pending:
                continue
            self._pending.discard(task)
            try:
                task._deliver(ok, payload)
            except Exception:
                # One failing callback must not stop the next delivery
                sys.excepthook(*sys.exc_info())
        self._stop_if_idle()


_dispatcher_obj: _Dispatcher | None = None


def _existing_dispatcher() -> "_Dispatcher | None":
    """The dispatcher when it was created and its object is still alive; None otherwise."""
    global _dispatcher_obj
    if _dispatcher_obj is None:
        return None
    try:
        _dispatcher_obj.objectName()
    except RuntimeError:
        _dispatcher_obj = None
    return _dispatcher_obj


def _dispatcher() -> _Dispatcher:
    """The module's dispatcher, created on first use on the GUI thread (test-facing: tests read its timer)."""
    global _dispatcher_obj
    found = _existing_dispatcher()
    if found is not None:
        return found
    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("run_in_background needs a QCoreApplication")
    _dispatcher_obj = _Dispatcher(app)
    return _dispatcher_obj


def running_tasks() -> int:
    """How many started checks have not returned yet."""
    with _count_lock:
        return _started_not_returned


def run_in_background(
    fn: Callable[[], object],
    on_result: Callable[[object], None],
    on_failed: Callable[[str], None] | None = None,
    *,
    name: str = "library-folder-check",
) -> BackgroundTask:
    """Run fn on a daemon thread; call on_result(value) or on_failed(text) later on the GUI thread.

    GUI thread only. The failure text is "ExceptionName: message".
    """
    global _started_not_returned
    dispatcher = _dispatcher()
    task = BackgroundTask(name, on_result, on_failed)

    def work():
        global _started_not_returned
        try:
            try:
                outcome = (True, fn())
            except BaseException as exc:
                # SystemExit, KeyboardInterrupt and the like too: without an outcome the task would
                # stay pending and the poll timer would run forever
                outcome = (False, f"{type(exc).__name__}: {exc}")
            _outcomes.put((task, outcome[0], outcome[1]))
        finally:
            with _count_lock:
                _started_not_returned -= 1
            task._returned.set()

    with _count_lock:
        _started_not_returned += 1
    dispatcher.add(task)
    thread = threading.Thread(target=work, daemon=True, name=name)
    try:
        thread.start()
    except BaseException:
        # No thread will ever report: release the task, the counter and the poll timer
        with _count_lock:
            _started_not_returned -= 1
        task._returned.set()
        task.cancel()
        raise
    return task
