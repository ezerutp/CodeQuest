"""Integración con un jdtls real. Lento y necesita Java 21 y red (Maven): solo se ejecuta con
CODEQUEST_JDTLS_HOME apuntando a un jdtls extraído, p. ej.
    CODEQUEST_JDTLS_HOME=~/jdtls pytest tests/test_jdtls_integration.py
"""

import os
from pathlib import Path

import pytest

from codequest.core.lsp.jdtls import JdtlsInstallation
from codequest.services.java_language_service import JavaLanguageService

JDTLS_HOME = os.environ.get("CODEQUEST_JDTLS_HOME")
pytestmark = pytest.mark.skipif(not JDTLS_HOME, reason="define CODEQUEST_JDTLS_HOME para probar con jdtls real")

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.0</version></parent>
  <groupId>com.example</groupId><artifactId>demo</artifactId><version>0.0.1</version>
  <properties><java.version>21</java.version></properties>
  <dependencies><dependency><groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId></dependency></dependencies>
</project>"""
CONTROLLER = """package com.example.demo;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
public class CategoriaController {
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void eliminar(@PathVariable Long id) { }
}
"""


def test_real_jdtls_suggests_spring_constants_without_touching_the_project(tmp_path: Path) -> None:
    project = tmp_path / "student"
    source = project / "src/main/java/com/example/demo/CategoriaController.java"
    source.parent.mkdir(parents=True)
    (project / "pom.xml").write_text(POM)
    source.write_text(CONTROLLER)
    before = sorted(p.relative_to(project) for p in project.rglob("*"))

    service = JavaLanguageService(JdtlsInstallation(Path(JDTLS_HOME).expanduser()), tmp_path / "data")
    try:
        assert service.start(project, "demo").is_ready, service.status.detail
        edited = CONTROLLER.replace("HttpStatus.NO_CONTENT", "HttpStatus.")
        line = edited.split("\n").index("    @ResponseStatus(HttpStatus.)")
        items = service.complete("src/main/java/com/example/demo/CategoriaController.java", edited,
                                 line, len("    @ResponseStatus(HttpStatus."))
        assert "NO_CONTENT" in {item.insert_text for item in items}
    finally:
        service.stop()
    assert sorted(p.relative_to(project) for p in project.rglob("*")) == before
