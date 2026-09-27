"""TypeScriptLanguageService contra un servidor LSP falso que se comporta como typescript-language-server."""

import json
import sys
import threading
from pathlib import Path

from codequest.core.lsp.client import LspClient
from codequest.core.lsp.models import ServerState
from codequest.core.lsp.typescript_server import TypeScriptServerInstallation
from codequest.services.typescript_language_service import TypeScriptLanguageService

SERVER = Path(__file__).parent / "fixtures" / "fake_lsp_server.py"
APP = "export function App() {\n  const [n] = useState(0);\n  return <b>{n}</b>;\n}\n"


def _service(tmp_path: Path) -> tuple[TypeScriptLanguageService, Path]:
    received = tmp_path / "received.jsonl"

    def factory(command: list[str], cwd: Path, **kwargs: object) -> LspClient:
        return LspClient([sys.executable, str(SERVER), "ts", str(received)], cwd=cwd, **kwargs)

    return TypeScriptLanguageService(TypeScriptServerInstallation(tmp_path / "ts"), factory), received


def _received(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_ready_after_initialize_without_a_ready_notification(tmp_path: Path) -> None:
    service, received = _service(tmp_path)
    try:
        assert service.start(tmp_path, "id").state is ServerState.READY
        init = next(m for m in _received(received) if m.get("method") == "initialize")
        # Sin esta capacidad, typescript-language-server no publica ningún error.
        assert "publishDiagnostics" in init["params"]["capabilities"]["textDocument"]
    finally:
        service.stop()


def test_diagnostics_wait_for_the_semantic_pass_and_open_tsx_as_react(tmp_path: Path) -> None:
    service, received = _service(tmp_path)
    try:
        service.start(tmp_path, "id")
        broken = service.diagnostics("src/App.tsx", APP.replace("useState(", "useStat("), wait=5)
        assert [(d.line, d.message) for d in broken] == [(2, "Cannot find name 'useStat'.")]
        assert service.diagnostics("src/App.tsx", APP, wait=5) == ()  # no devuelve los errores anteriores
        opened = next(m for m in _received(received) if m.get("method") == "textDocument/didOpen")
        assert opened["params"]["textDocument"]["languageId"] == "typescriptreact"
    finally:
        service.stop()


def test_stop_wakes_up_whoever_is_waiting_for_diagnostics(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    service.start(tmp_path, "id")
    service.diagnostics("src/App.tsx", APP, wait=5)  # ya cargado: la siguiente espera usa `wait`
    result: list[object] = []
    waiter = threading.Thread(target=lambda: result.append(service.diagnostics("src/Otro.tsx", APP, wait=30)))
    waiter.start()
    service.stop()
    waiter.join(timeout=5)
    assert not waiter.is_alive() and result in ([None], [()])
