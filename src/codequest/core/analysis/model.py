"""Resultado del análisis de un proyecto: lo que consumen la UI y el generador de preguntas."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.roles import ComponentRole
from codequest.core.project.models import ProjectInfo, SourceFile


@dataclass(frozen=True, slots=True, eq=False)
class ProjectModel:
    info: ProjectInfo
    files: tuple[SourceFile, ...]
    classes: tuple[JavaClass, ...]
    roles: Mapping[str, ComponentRole]
    errors: tuple[str, ...] = ()  # "ruta: motivo" de archivos que no se pudieron analizar
    duration_seconds: float = 0.0
    truncated: bool = False
    skipped_large: tuple[str, ...] = field(default=())

    def role_of(self, cls: JavaClass) -> ComponentRole:
        return self.roles.get(cls.qualified_name, ComponentRole.OTHER)

    @property
    def main_classes(self) -> tuple[JavaClass, ...]:
        """Clases de producción: excluye src/test/."""
        return tuple(c for c in self.classes if not c.is_test)

    def classes_with_role(self, role: ComponentRole) -> tuple[JavaClass, ...]:
        return tuple(c for c in self.main_classes if self.role_of(c) is role)

    def role_counts(self) -> Counter[ComponentRole]:
        return Counter(self.role_of(c) for c in self.main_classes)

    def annotation_usage(self) -> Counter[str]:
        """Cuántas veces aparece cada anotación (clases, campos, métodos y parámetros)."""
        usage: Counter[str] = Counter()
        for cls in self.main_classes:
            usage.update(a.name for a in cls.annotations)
            for f in cls.fields:
                usage.update(a.name for a in f.annotations)
            for m in cls.methods:
                usage.update(a.name for a in m.annotations)
                for p in m.parameters:
                    usage.update(a.name for a in p.annotations)
        return usage
