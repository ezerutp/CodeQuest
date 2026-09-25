"""Ejecución de tareas pesadas fuera del hilo de la UI.

Patrón: un QObject "worker" se mueve a un QThread y llama al servicio (sin Qt).
Los resultados vuelven por señales; como el receptor (AnalysisRunner) vive en el
hilo principal, Qt los entrega en ese hilo y la UI puede actualizarse sin riesgo.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from codequest.core.analysis.model import ProjectModel
from codequest.core.project.models import ProjectInfo
from codequest.services.project_service import AnalysisCancelled, ProjectService

log = logging.getLogger(__name__)

_PROGRESS_INTERVAL_S = 0.05  # no inundar la cola de eventos con una señal por archivo


class _AnalysisWorker(QObject):
    progress = Signal(int, int, int)  # generación, hechos, total
    finished = Signal(int, object)  # generación, ProjectModel
    failed = Signal(int, str)
    done = Signal(int)  # generación; se emite siempre al terminar

    def __init__(self, service: ProjectService, info: ProjectInfo, generation: int,
                 cancel: threading.Event) -> None:
        super().__init__()
        self._service = service
        self._info = info
        self._generation = generation
        self._cancel = cancel
        self._last_emit = 0.0

    @Slot()
    def run(self) -> None:
        try:
            model = self._service.analyze(self._info, on_progress=self._report, cancel=self._cancel)
            self.finished.emit(self._generation, model)
        except AnalysisCancelled:
            log.info("Análisis cancelado: %s", self._info.name)
        except Exception as exc:
            log.exception("Falló el análisis de %s", self._info.root)
            self.failed.emit(self._generation, str(exc))
        finally:
            self.done.emit(self._generation)

    def _report(self, done: int, total: int) -> None:
        now = time.monotonic()
        if done == total or now - self._last_emit >= _PROGRESS_INTERVAL_S:
            self._last_emit = now
            self.progress.emit(self._generation, done, total)


class AnalysisRunner(QObject):
    """Lanza análisis en segundo plano. Un análisis nuevo cancela el anterior."""

    started = Signal()
    progress = Signal(int, int)
    finished = Signal(object)  # ProjectModel
    failed = Signal(str)

    def __init__(self, service: ProjectService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._generation = 0
        self._cancel: threading.Event | None = None
        self._active: dict[int, tuple[QThread, _AnalysisWorker]] = {}

    def start(self, info: ProjectInfo) -> None:
        self.cancel()
        self._generation += 1
        generation = self._generation
        self._cancel = threading.Event()

        thread = QThread()
        worker = _AnalysisWorker(self._service, info, generation, self._cancel)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.done.connect(self._on_done)

        # Guardamos referencias: sin ellas Python podría destruir los objetos en mitad del trabajo.
        self._active[generation] = (thread, worker)
        thread.start()
        self.started.emit()

    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    def shutdown(self, timeout_ms: int = 3000) -> None:
        """Cancela y espera a los hilos activos. Llamar al cerrar la ventana."""
        self.cancel()
        for thread, _ in list(self._active.values()):
            thread.quit()
            if not thread.wait(timeout_ms):
                log.warning("Un hilo de análisis no terminó a tiempo")

    @Slot(int, int, int)
    def _on_progress(self, generation: int, done: int, total: int) -> None:
        if generation == self._generation:
            self.progress.emit(done, total)

    @Slot(int, object)
    def _on_finished(self, generation: int, model: ProjectModel) -> None:
        if generation == self._generation:
            self.finished.emit(model)

    @Slot(int, str)
    def _on_failed(self, generation: int, message: str) -> None:
        if generation == self._generation:
            self.failed.emit(message)

    @Slot(int)
    def _on_done(self, generation: int) -> None:
        # Corre en el hilo principal. run() ya terminó: el hilo cierra enseguida y
        # al soltar las referencias Python libera worker y thread de forma segura.
        entry = self._active.pop(generation, None)
        if entry is not None:
            thread, _worker = entry
            thread.quit()
            thread.wait()


TaskFunction = Callable[[Callable[[int, int], None], threading.Event], Any]


class _TaskWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(self, function: TaskFunction, cancel: threading.Event) -> None:
        super().__init__()
        self._function = function
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._function(self.progress.emit, self._cancel))
        except Exception as exc:  # la UI muestra el error; el detalle queda en el log
            log.exception("Falló una tarea en segundo plano")
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class BackgroundTask(QObject):
    """Ejecuta una función (p. ej. una llamada a la IA) en un QThread. Una a la vez.

    La función recibe `(on_progress, cancel_event)`; su resultado llega por `finished`
    en el hilo principal.
    """

    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _TaskWorker | None = None
        self._cancel = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    def start(self, function: TaskFunction) -> bool:
        if self.is_running:
            return False
        self._cancel = threading.Event()
        self._thread = QThread()
        self._worker = _TaskWorker(function, self._cancel)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self.finished)
        self._worker.failed.connect(self.failed)
        self._worker.done.connect(self._on_done)
        self._thread.start()
        return True

    def cancel(self) -> None:
        self._cancel.set()

    def shutdown(self, timeout_ms: int = 3000) -> None:
        self.cancel()
        if self._thread is not None:
            self._thread.quit()
            if not self._thread.wait(timeout_ms):
                log.warning("Una tarea en segundo plano no terminó a tiempo")

    @Slot()
    def _on_done(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None


class SignalRelay(QObject):
    """Lleva valores de un hilo de trabajo al hilo principal: se crea en el hilo principal y su
    `emitted.emit` se pasa como callback al servicio; Qt entrega la señal en el hilo del receptor."""

    emitted = Signal(object)


class LatestOnlyTask(QObject):
    """Como BackgroundTask, pero para peticiones que se quedan viejas (sugerencias al escribir): si
    llega una nueva mientras otra corre, solo se guarda la última y se lanza al terminar la actual."""

    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task = BackgroundTask(self)
        self._task.finished.connect(self._on_done)
        self._task.failed.connect(lambda message: self._on_done(None))
        self._pending: TaskFunction | None = None

    def submit(self, function: TaskFunction) -> None:
        if not self._task.start(function):
            self._pending = function

    def shutdown(self, timeout_ms: int = 3000) -> None:
        self._pending = None
        self._task.shutdown(timeout_ms)

    def _on_done(self, result: object) -> None:
        if result is not None:
            self.finished.emit(result)
        if self._pending is not None:
            function, self._pending = self._pending, None
            # El hilo anterior se libera tras esta señal: se lanza en la siguiente vuelta del bucle.
            QTimer.singleShot(0, lambda: self.submit(function))
