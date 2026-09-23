"""Interfaces de la capa de análisis. Permiten cambiar el parser o añadir frameworks."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.roles import ComponentRole
from codequest.core.project.models import ProjectInfo, SourceFile


class SourceParser(ABC):
    """Convierte un archivo fuente en modelos de clases."""

    @abstractmethod
    def supports(self, file: SourceFile) -> bool: ...

    @abstractmethod
    def parse(self, file: SourceFile, text: str) -> list[JavaClass]: ...


class FrameworkAnalyzer(ABC):
    """Asigna un rol a cada clase según las convenciones de un framework."""

    @abstractmethod
    def supports(self, project: ProjectInfo) -> bool: ...

    @abstractmethod
    def classify(self, classes: Sequence[JavaClass]) -> Mapping[str, ComponentRole]:
        """Devuelve {qualified_name: rol}."""
