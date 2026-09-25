import sys
import threading
from pathlib import Path

import pytest

from codequest.core.lsp.client import LspClient
from codequest.core.lsp.jdtls import JavaRuntime, JdtlsInstallation, config_dir_name
from codequest.core.lsp.models import ServerState
from codequest.services.java_language_service import JavaLanguageService, LanguageServerCancelled

SERVER = Path(__file__).parent / "fixtures" / "fake_lsp_server.py"
JAVA = JavaRuntime(Path("/jdk/bin/java"), "21.0.4", 21)
CONTROLLER = "class C {\n    @ResponseStatus(HttpStatus.)\n    void eliminar() {}\n}\n"


def _installation(root: Path, installed: bool = True) -> JdtlsInstallation:
    if installed:
        (root / "plugins").mkdir(parents=True)
        (root / "plugins" / "org.eclipse.equinox.launcher_1.jar").write_text("jar")
        (root / config_dir_name()).mkdir()
    return JdtlsInstallation(root)


def _project(root: Path) -> Path:
    (root / "src/main/java").mkdir(parents=True)
    (root / "pom.xml").write_text("<project/>")
    (root / "src/main/java/C.java").write_text(CONTROLLER)
    return root


def _service(tmp_path: Path, mode: str = "ok", java: JavaRuntime | None = JAVA,
             installed: bool = True) -> tuple[JavaLanguageService, list[str], Path]:
    commands: list[str] = []
    received = tmp_path / "received.jsonl"

    def factory(command: list[str], cwd: Path, **kwargs: object) -> LspClient:
        commands.append(command)
        return LspClient([sys.executable, str(SERVER), mode, str(received)], cwd=cwd, **kwargs)

    service = JavaLanguageService(_installation(tmp_path / "server", installed), tmp_path / "projects",
                                  java_finder=lambda: java, client_factory=factory)
    return service, commands, received


def test_check_reports_missing_install_or_java(tmp_path: Path) -> None:
    assert _service(tmp_path / "a", installed=False)[0].check().state is ServerState.NOT_INSTALLED
    assert _service(tmp_path / "b", java=None)[0].check().state is ServerState.NO_JAVA
    old = JavaRuntime(Path("/jdk/bin/java"), "17.0.2", 17)
    status = _service(tmp_path / "c", java=old)[0].check()
    assert status.state is ServerState.NO_JAVA and "17.0.2" in status.detail
    assert _service(tmp_path / "d")[0].check().detail == "Java 21.0.4"


def test_start_uses_a_mirror_and_completes_from_memory(tmp_path: Path) -> None:
    project = _project(tmp_path / "student")
    service, commands, received = _service(tmp_path)
    states = []
    status = service.start(project, "abc123", on_status=lambda s: states.append(s.state))
    assert status.is_ready and states[0] is ServerState.STARTING and states[-1] is ServerState.READY

    mirror = tmp_path / "projects" / "abc123" / "mirror"
    assert (mirror / "src/main/java/C.java").read_text() == CONTROLLER
    assert commands[0][commands[0].index("-data") + 1] == str(tmp_path / "projects" / "abc123" / "workspace")
    assert mirror.as_uri() in received.read_text()  # jdtls importa la copia, nunca el proyecto
    assert project.as_uri() + "/" not in received.read_text()

    items = service.complete("src/main/java/C.java", CONTROLLER, 1, len("    @ResponseStatus(HttpStatus."))
    assert [item.insert_text for item in items] == ["NO_CONTENT", "OK"]
    edited = CONTROLLER.replace("HttpStatus.", "HttpStatus.O")
    assert service.complete("src/main/java/C.java", edited, 1, 5) == []  # didChange, no didOpen
    assert received.read_text().count("textDocument/didOpen") == 1
    assert (project / "src/main/java/C.java").read_text() == CONTROLLER

    assert service.start(project, "abc123") is service.status and len(commands) == 1  # ya en marcha
    service.stop()
    assert service.status.state is ServerState.STOPPED and service.complete("C.java", "", 0, 0) == []


def test_server_that_dies_while_starting_fails(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path, mode="crash")
    status = service.start(_project(tmp_path / "student"), "id")
    assert status.state is ServerState.FAILED


def test_start_can_be_cancelled(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path, mode="silent")
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    with pytest.raises(LanguageServerCancelled):
        service.start(_project(tmp_path / "student"), "id", cancel=cancel)
    assert service.status.state is ServerState.STOPPED
