"""Run engine work off the UI thread."""
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

_alive = set()  # keep signal objects alive until their job finishes


class WorkerSignals(QObject):
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    """Call fn(*args, **kwargs) in the global thread pool. If with_progress, fn gets progress=<callable>."""

    def __init__(self, fn, *args, with_progress=False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()
        if with_progress:
            self.kwargs["progress"] = self.signals.progress.emit
        _alive.add(self.signals)
        self.signals.finished.connect(lambda s=self.signals: _alive.discard(s))

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 - surfaced to the UI
            name = type(e).__name__
            if name == "Cancelled":
                self.signals.error.emit("__cancelled__")
            else:
                self.signals.error.emit(f"{e}\n\n{traceback.format_exc()}")
        else:
            self.signals.result.emit(res)
        finally:
            self.signals.finished.emit()


def run_async(fn, *args, on_result=None, on_error=None, on_progress=None, **kwargs):
    w = Worker(fn, *args, with_progress=on_progress is not None, **kwargs)
    if on_result:
        w.signals.result.connect(on_result)
    if on_error:
        w.signals.error.connect(on_error)
    if on_progress:
        w.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(w)
    return w


class LatestJob(QObject):
    """At most one job running; while it runs only the newest request is kept (older ones are dropped).
    Optional delay debounces rapid requests (slider drags)."""
    result = Signal(object)
    busy = Signal(bool)

    def __init__(self, fn, delay_ms=0, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._pending = None
        self._running = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._kick)
        self.delay_ms = delay_ms

    def request(self, **params):
        self._pending = params
        if self.delay_ms:
            self._timer.start(self.delay_ms)
        else:
            self._kick()

    def _kick(self):
        if self._running or self._pending is None:
            return
        params, self._pending = self._pending, None
        self._running = True
        self.busy.emit(True)
        w = Worker(self.fn, **params)
        w.signals.result.connect(self._done)
        w.signals.error.connect(self._failed)
        QThreadPool.globalInstance().start(w)

    def _done(self, res):
        self._running = False
        self.result.emit(res)
        if self._pending is not None:
            self._kick()
        else:
            self.busy.emit(False)

    def _failed(self, msg):
        self._running = False
        print("preview job failed:", msg)
        if self._pending is not None:
            self._kick()
        else:
            self.busy.emit(False)
