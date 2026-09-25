"""Caso de uso "servidor de lenguaje Java": arrancar jdtls para el proyecto y pedirle sugerencias.

Todas las operaciones bloquean (arrancar puede tardar desde unos segundos hasta minutos la primera
vez, mientras Maven descarga dependencias), así que se llaman desde un worker. jdtls trabaja sobre
una copia espejo del proyecto (`core/lsp/mirror.py`); el texto editado se le envía en memoria.
"""

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from codequest.core.lsp.client import LspClient, LspError
from codequest.core.lsp.jdtls import MIN_JAVA_VERSION, JavaRuntime, JdtlsInstallation, find_java
from codequest.core.lsp.mirror import sync_mirror
from codequest.core.lsp.models import CompletionList, ServerState, ServerStatus, completion_list

log = logging.getLogger(__name__)

READY_TIMEOUT_S = 600  # la primera importación de Maven puede descargar cientos de MB
COMPLETION_TIMEOUT_S = 10

# Ajustes de jdtls: sin compilar (no hace falta para sugerir) y sin tocar la configuración de build.
SERVER_SETTINGS: dict[str, Any] = {"java": {
    "autobuild": {"enabled": False},
    "import": {"generatesMetadataFilesAtProjectRoot": False},
    "maven": {"downloadSources": False},
    "configuration": {"updateBuildConfiguration": "disabled"},
    "completion": {"guessMethodArguments": False},
}}

ClientFactory = Callable[..., LspClient]
StatusCallback = Callable[[ServerStatus], None]


class LanguageServerCancelled(Exception):
    pass


class JavaLanguageService:
    def __init__(self, installation: JdtlsInstallation, projects_dir: Path, stderr_log: Path | None = None,
                 java_finder: Callable[[], JavaRuntime | None] | None = None,
                 client_factory: ClientFactory = LspClient) -> None:
        self.installation = installation
        self._projects_dir = projects_dir  # <datos>/jdtls/projects/<id>/{mirror,workspace}
        self._stderr_log = stderr_log
        self._find_java = java_finder or (lambda: find_java(os.environ.get("JAVA_HOME")))
        self._client_factory = client_factory
        self._lock = threading.RLock()
        self._client: LspClient | None = None
        self._project_id: str | None = None
        self._mirror: Path | None = None
        self._versions: dict[str, int] = {}  # uri -> versión del documento abierto
        self._ready = threading.Event()
        self._status = ServerStatus(ServerState.STOPPED)
        self._on_status: StatusCallback | None = None

    @property
    def status(self) -> ServerStatus:
        return self._status

    def check(self) -> ServerStatus:
        """Estado sin arrancar nada: ¿está instalado y hay un Java compatible?"""
        if self._status.state in (ServerState.STARTING, ServerState.READY):
            return self._status
        if not self.installation.is_installed:
            return self._set_status(ServerStatus(ServerState.NOT_INSTALLED))
        java = self._find_java()
        if java is None or not java.is_supported:
            return self._set_status(_no_java(java))
        return self._set_status(ServerStatus(ServerState.STOPPED, f"Java {java.version}"))

    def start(self, project_root: Path, project_id: str, on_status: StatusCallback | None = None,
              cancel: threading.Event | None = None) -> ServerStatus:
        """Arranca jdtls para este proyecto (si ya está en marcha para él, no hace nada)."""
        with self._lock:
            if self._client is not None and self._client.is_running and self._project_id == project_id:
                return self._status
            self.stop()
            self._on_status = on_status
            if not self.installation.is_installed:
                return self._set_status(ServerStatus(ServerState.NOT_INSTALLED))
            java = self._find_java()
            if java is None or not java.is_supported:
                return self._set_status(_no_java(java))
            self._set_status(ServerStatus(ServerState.STARTING, "Preparando una copia del proyecto…"))
            base = self._projects_dir / project_id
            mirror, workspace = base / "mirror", base / "workspace"
            try:
                sync_mirror(project_root, mirror)
                workspace.mkdir(parents=True, exist_ok=True)
                self._set_status(ServerStatus(ServerState.STARTING, "Iniciando jdtls…"))
                self._ready.clear()
                self._client = self._client_factory(self.installation.command(java, workspace), cwd=base,
                                                    on_notification=self._on_notification,
                                                    stderr_log=self._stderr_log)
                self._project_id, self._mirror, self._versions = project_id, mirror, {}
                self._client.request("initialize", _initialize_params(mirror), timeout=120)
                self._client.notify("initialized", {})
            except (OSError, ValueError, LspError) as exc:
                log.warning("No se pudo iniciar jdtls: %s", exc)
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED, str(exc)))
            client = self._client
        return self._wait_ready(client, cancel)

    def complete(self, relative_path: str, text: str, line: int, column: int) -> CompletionList:
        """Sugerencias en `line`/`column` (0-based; la columna en unidades UTF-16, como pide LSP) del
        archivo con el texto `text`, que está en memoria: el archivo del proyecto (y de la copia) no cambia."""
        with self._lock:
            client, mirror = self._client, self._mirror
            if client is None or mirror is None or not self._ready.is_set():
                return CompletionList()
            uri = (mirror / relative_path).as_uri()
            version = self._versions.get(uri, 0) + 1
            self._versions[uri] = version
            if version == 1:
                client.notify("textDocument/didOpen", {"textDocument": {
                    "uri": uri, "languageId": "java", "version": version, "text": text}})
            else:
                client.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": version},
                                                         "contentChanges": [{"text": text}]})
        try:
            result = client.request("textDocument/completion", {
                "textDocument": {"uri": uri}, "position": {"line": line, "character": column}},
                timeout=COMPLETION_TIMEOUT_S)
        except LspError as exc:
            log.info("Sin sugerencias de jdtls: %s", exc)
            return CompletionList()
        return completion_list(result)

    def stop(self) -> None:
        with self._lock:
            client, self._client = self._client, None
            self._project_id = self._mirror = None
            self._ready.clear()
        if client is not None:
            client.close(timeout=3)
            if self._status.state in (ServerState.STARTING, ServerState.READY):
                self._set_status(ServerStatus(ServerState.STOPPED))

    # --- interno --------------------------------------------------------------------

    def _wait_ready(self, client: LspClient, cancel: threading.Event | None) -> ServerStatus:
        waited = 0.0
        while not self._ready.wait(0.25):
            waited += 0.25
            if cancel is not None and cancel.is_set():
                self.stop()
                raise LanguageServerCancelled
            if not client.is_running:
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED, "jdtls se cerró al arrancar"))
            if waited >= READY_TIMEOUT_S:
                self.stop()
                return self._set_status(ServerStatus(ServerState.FAILED, "jdtls tardó demasiado en arrancar"))
        return self._set_status(ServerStatus(ServerState.READY))

    def _on_notification(self, method: str, params: Any) -> None:
        """Hilo lector del cliente LSP: solo nos interesa saber cuándo termina de importar el proyecto."""
        if method != "language/status" or not isinstance(params, dict):
            return
        if params.get("type") == "ServiceReady":
            self._ready.set()
        elif params.get("type") == "Starting" and self._status.state is ServerState.STARTING:
            message = str(params.get("message") or "")
            if "Importing" in message or "http" in message:
                self._set_status(ServerStatus(ServerState.STARTING, "Importando el proyecto y sus dependencias…"))

    def _set_status(self, status: ServerStatus) -> ServerStatus:
        changed = status != self._status
        self._status = status
        if changed:
            log.info("jdtls: %s %s", status.state, status.detail)
            if self._on_status is not None:
                self._on_status(status)
        return status


def _no_java(java: JavaRuntime | None) -> ServerStatus:
    if java is None:
        return ServerStatus(ServerState.NO_JAVA, f"No se encontró Java. Instala un JDK {MIN_JAVA_VERSION} o superior.")
    return ServerStatus(ServerState.NO_JAVA,
                        f"Tienes Java {java.version}; jdtls necesita Java {MIN_JAVA_VERSION} o superior.")


def _initialize_params(mirror: Path) -> dict[str, Any]:
    return {
        "processId": os.getpid(),
        "rootUri": mirror.as_uri(),
        "workspaceFolders": [{"uri": mirror.as_uri(), "name": mirror.parent.name}],
        "capabilities": {"textDocument": {"completion": {"completionItem": {"snippetSupport": False}}}},
        "initializationOptions": {"settings": SERVER_SETTINGS, "extendedClientCapabilities": {}},
    }
