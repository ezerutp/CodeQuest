"""Caso de uso "servidor de lenguaje TypeScript": arrancar typescript-language-server.

Mismo patrón que JavaLanguageService: el servidor se arranca en un worker y
ofrece completions y diagnostics. A diferencia de jdtls, no hace falta copia
espejo porque el servidor de TypeScript no escribe archivos en el proyecto.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from codequest.core.lsp.client import LspClient, LspError
from codequest.core.lsp.models import (
    CompletionList,
    Diagnostic,
    ServerState,
    ServerStatus,
    completion_list,
    diagnostics,
)
from codequest.core.lsp.typescript_server import TypeScriptServerInstallation

log = logging.getLogger(__name__)

READY_TIMEOUT_S = 60
COMPLETION_TIMEOUT_S = 10
DIAGNOSTICS_WAIT_S = 5.0

ClientFactory = Callable[..., LspClient]
StatusCallback = Callable[[ServerStatus], None]


class LanguageServerCancelled(Exception):
    pass


class TypeScriptLanguageService:
    def __init__(self, installation: TypeScriptServerInstallation,
                 client_factory: ClientFactory = LspClient) -> None:
        self.installation = installation
        self._client_factory = client_factory
        self._lock = threading.RLock()
        self._client: LspClient | None = None
        self._project_id: str | None = None
        self._project_root: Path | None = None
        self._versions: dict[str, int] = {}
        self._published = threading.Condition()
        self._diagnostics: dict[str, tuple[Diagnostic, ...]] = {}
        self._publications: dict[str, int] = {}
        self._ready = threading.Event()
        self._status = ServerStatus(ServerState.STOPPED)
        self._on_status: StatusCallback | None = None

    @property
    def status(self) -> ServerStatus:
        return self._status

    def check(self) -> ServerStatus:
        """Estado sin arrancar nada: ¿está npx disponible?"""
        if self._status.state in (ServerState.STARTING, ServerState.READY):
            return self._status
        if not self.installation.is_installed:
            return self._set_status(ServerStatus(ServerState.NOT_INSTALLED,
                                                  "No se encontró npx. Instala Node.js 18+."))
        return self._set_status(ServerStatus(ServerState.STOPPED, "Node.js disponible"))

    def start(self, project_root: Path, project_id: str, on_status: StatusCallback | None = None,
              cancel: threading.Event | None = None) -> ServerStatus:
        """Arranca typescript-language-server para este proyecto."""
        with self._lock:
            if self._client is not None and self._client.is_running and self._project_id == project_id:
                return self._status
            self.stop()
            self._on_status = on_status
            if not self.installation.is_installed:
                return self._set_status(ServerStatus(ServerState.NOT_INSTALLED,
                                                      "No se encontró npx. Instala Node.js 18+."))
            self._set_status(ServerStatus(ServerState.STARTING, "Iniciando typescript-language-server…"))
            self._ready.clear()
            try:
                self._client = self._client_factory(
                    self.installation.command,
                    cwd=project_root,
                    on_notification=self._on_notification,
                )
                self._project_id = project_id
                self._project_root = project_root
                self._versions = {}
                self._client.request("initialize", _initialize_params(project_root), timeout=READY_TIMEOUT_S)
                self._client.notify("initialized", {})
            except (OSError, ValueError, LspError) as exc:
                log.warning("No se pudo iniciar typescript-language-server: %s", exc)
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED, str(exc)))
            client = self._client
        return self._wait_ready(client, cancel)

    def complete(self, relative_path: str, text: str, line: int, column: int) -> CompletionList:
        """Sugerencias en `line`/`column` (0-based; columna en unidades UTF-16)."""
        with self._lock:
            client, uri = self._client, self._send_document(relative_path, text)
            if client is None or uri is None:
                return CompletionList()
        try:
            result = client.request("textDocument/completion", {
                "textDocument": {"uri": uri}, "position": {"line": line, "character": column}},
                timeout=COMPLETION_TIMEOUT_S)
        except LspError as exc:
            log.info("Sin sugerencias de typescript-language-server: %s", exc)
            return CompletionList()
        return completion_list(result)

    def diagnostics(self, relative_path: str, text: str, wait: float = DIAGNOSTICS_WAIT_S
                    ) -> tuple[Diagnostic, ...] | None:
        """Errores de TypeScript del archivo con el texto `text` (en memoria)."""
        with self._lock:
            if self._client is None or not self._ready.is_set():
                return None
            uri = (self._project_root / relative_path).as_uri() if self._project_root else None
            if uri is None:
                return None
            with self._published:
                seen = self._publications.get(uri, 0)
            if self._send_document(relative_path, text) is None:
                return None
        with self._published:
            self._published.wait_for(lambda: self._publications.get(uri, 0) > seen, timeout=wait)
            return self._diagnostics.get(uri, ())

    def stop(self) -> None:
        with self._lock:
            client, self._client = self._client, None
            self._project_id = None
            self._project_root = None
            self._ready.clear()
            with self._published:
                self._diagnostics.clear()
                self._publications.clear()
        if client is not None:
            client.close(timeout=3)
            if self._status.state in (ServerState.STARTING, ServerState.READY):
                self._set_status(ServerStatus(ServerState.STOPPED))

    # --- interno --------------------------------------------------------------------

    def _send_document(self, relative_path: str, text: str) -> str | None:
        """Abre o actualiza el documento en el servidor (con `_lock` tomado)."""
        client = self._client
        if client is None or self._project_root is None or not self._ready.is_set():
            return None
        uri = (self._project_root / relative_path).as_uri()
        version = self._versions.get(uri, 0) + 1
        self._versions[uri] = version
        if version == 1:
            client.notify("textDocument/didOpen", {"textDocument": {
                "uri": uri, "languageId": "typescript", "version": version, "text": text}})
        else:
            client.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": version},
                                                     "contentChanges": [{"text": text}]})
        return uri

    def _wait_ready(self, client: LspClient, cancel: threading.Event | None) -> ServerStatus:
        waited = 0.0
        while not self._ready.wait(0.25):
            waited += 0.25
            if cancel is not None and cancel.is_set():
                self.stop()
                raise LanguageServerCancelled
            if not client.is_running:
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED,
                                                      "typescript-language-server se cerró al arrancar"))
            if waited >= READY_TIMEOUT_S:
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED,
                                                      "typescript-language-server tardó demasiado en arrancar"))
        return self._set_status(ServerStatus(ServerState.READY))

    def _on_notification(self, method: str, params: Any) -> None:
        """Hilo lector del cliente LSP: cuándo está listo y los errores publicados."""
        if not isinstance(params, dict):
            return
        if method == "textDocument/publishDiagnostics":
            uri = str(params.get("uri"))
            with self._published:
                self._diagnostics[uri] = diagnostics(params)
                self._publications[uri] = self._publications.get(uri, 0) + 1
                self._published.notify_all()
            return
        # typescript-language-server no envía un evento "listo" como jdtls;
        # consideramos que está listo cuando responde al initialize
        if method == "window/logMessage":
            message = str(params.get("message", ""))
            if "Initializing" in message or "ready" in message.lower():
                self._ready.set()

    def _set_status(self, status: ServerStatus) -> ServerStatus:
        changed = status != self._status
        self._status = status
        if changed:
            log.info("typescript-language-server: %s %s", status.state, status.detail)
            if self._on_status is not None:
                self._on_status(status)
        return status


def _initialize_params(project_root: Path) -> dict[str, Any]:
    return {
        "processId": None,
        "rootUri": project_root.as_uri(),
        "workspaceFolders": [{"uri": project_root.as_uri(), "name": project_root.name}],
        "capabilities": {"textDocument": {"completion": {"completionItem": {"snippetSupport": False}}}},
    }
