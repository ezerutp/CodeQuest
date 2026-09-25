"""Cliente JSON-RPC mínimo del protocolo LSP sobre la entrada/salida estándar de un proceso.

Un hilo lee los mensajes del servidor: las respuestas despiertan a quien hizo la petición y las
notificaciones van a un único callback. `request()` bloquea, así que se llama desde un worker,
nunca desde el hilo de la UI.
"""

import json
import logging
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

log = logging.getLogger(__name__)

NotificationHandler = Callable[[str, Any], None]  # (método, parámetros)


class LspError(RuntimeError):
    """El servidor devolvió un error, se cerró o no respondió a tiempo."""


@dataclass
class _Pending:
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: str | None = None


def encode_message(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def read_message(stream: IO[bytes]) -> dict[str, Any] | None:
    """Lee un mensaje (cabeceras + cuerpo). None si el flujo terminó."""
    length: int | None = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        name, _, value = line.decode("ascii", errors="replace").partition(":")
        if name.strip().lower() == "content-length":
            length = int(value.strip())
    if length is None:
        raise LspError("Mensaje LSP sin Content-Length")
    body = stream.read(length)
    if len(body) < length:
        return None
    return json.loads(body.decode("utf-8"))


class LspClient:
    def __init__(self, command: Sequence[str], cwd: Path, on_notification: NotificationHandler | None = None,
                 stderr_log: Path | None = None) -> None:
        self._on_notification = on_notification
        self._lock = threading.Lock()  # escrituras en stdin y contador de ids
        self._next_id = 1
        self._pending: dict[int, _Pending] = {}
        self._closed = threading.Event()
        stderr = stderr_log.open("ab") if stderr_log is not None else subprocess.DEVNULL
        try:
            self._process = subprocess.Popen(list(command), cwd=cwd, stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE, stderr=stderr)
        finally:
            if stderr_log is not None:
                stderr.close()  # el proceso hijo ya tiene su copia del descriptor
        self._reader = threading.Thread(target=self._read_loop, name="lsp-reader", daemon=True)
        self._reader.start()

    @property
    def is_running(self) -> bool:
        return not self._closed.is_set() and self._process.poll() is None

    def request(self, method: str, params: Any, timeout: float = 30.0) -> Any:
        pending = _Pending()
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._pending[request_id] = pending
        try:
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            if not pending.done.wait(timeout):
                raise LspError(f"{method}: el servidor no respondió en {timeout:.0f} s")
        finally:
            with self._lock:
                self._pending.pop(request_id, None)
        if pending.error is not None:
            raise LspError(f"{method}: {pending.error}")
        return pending.result

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self, timeout: float = 5.0) -> None:
        """Cierre ordenado (shutdown + exit); si el servidor no termina, se le obliga."""
        if self.is_running:
            try:
                self.request("shutdown", None, timeout=timeout)
                self.notify("exit", None)
            except LspError as exc:
                log.info("Cierre del servidor de lenguaje sin respuesta: %s", exc)
        try:
            self._process.wait(timeout)
        except subprocess.TimeoutExpired:
            log.info("El servidor de lenguaje no terminó tras exit: se detiene")
            self._process.terminate()
            try:
                self._process.wait(timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._closed.set()
        for stream in (self._process.stdin, self._process.stdout):
            if stream is not None:
                stream.close()

    # --- interno --------------------------------------------------------------------

    def _send(self, message: dict[str, Any]) -> None:
        stdin = self._process.stdin
        if stdin is None or not self.is_running:
            raise LspError("El servidor de lenguaje no está en marcha")
        try:
            with self._lock:
                stdin.write(encode_message(message))
                stdin.flush()
        except (OSError, ValueError) as exc:
            raise LspError(f"No se pudo escribir al servidor de lenguaje: {exc}") from exc

    def _read_loop(self) -> None:
        stdout = self._process.stdout
        try:
            while stdout is not None and (message := read_message(stdout)) is not None:
                self._dispatch(message)
        except (OSError, ValueError, LspError) as exc:
            if not self._closed.is_set():
                log.warning("Lectura del servidor de lenguaje interrumpida: %s", exc)
        finally:
            self._closed.set()
            with self._lock:
                pending = list(self._pending.values())
            for item in pending:  # nadie se queda esperando una respuesta que no llegará
                item.error = "el servidor de lenguaje se cerró"
                item.done.set()

    def _dispatch(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method is None:  # respuesta a una petición nuestra
            with self._lock:
                pending = self._pending.get(message.get("id"))  # type: ignore[arg-type]
            if pending is not None:
                if "error" in message:
                    pending.error = str(message["error"].get("message", message["error"]))
                pending.result = message.get("result")
                pending.done.set()
        elif "id" in message:  # petición del servidor (configuración, registro de capacidades…)
            try:
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": None})
            except LspError:
                pass
        elif self._on_notification is not None:
            try:
                self._on_notification(method, message.get("params"))
            except Exception:  # un error en el callback no debe matar el hilo lector
                log.exception("Error procesando la notificación %s", method)
