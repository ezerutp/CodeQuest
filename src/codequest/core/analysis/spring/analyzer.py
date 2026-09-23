"""Clasificación de componentes de Spring Boot."""

from collections.abc import Mapping, Sequence

from codequest.core.analysis.java.conventions import JavaConventionsAnalyzer, simple_type_name
from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.roles import ComponentRole
from codequest.core.project.models import Framework, ProjectInfo

# Anotación de clase -> rol. Prioridad sobre las convenciones de nombre.
ANNOTATION_ROLES: Mapping[str, ComponentRole] = {
    "Entity": ComponentRole.ENTITY,
    "Embeddable": ComponentRole.ENTITY,
    "MappedSuperclass": ComponentRole.ENTITY,
    "Document": ComponentRole.ENTITY,
    "RestController": ComponentRole.CONTROLLER,
    "Controller": ComponentRole.CONTROLLER,
    "RestControllerAdvice": ComponentRole.EXCEPTION,
    "ControllerAdvice": ComponentRole.EXCEPTION,
    "Service": ComponentRole.SERVICE,
    "Repository": ComponentRole.REPOSITORY,
    "SpringBootApplication": ComponentRole.CONFIGURATION,
    "Configuration": ComponentRole.CONFIGURATION,
    "ConfigurationProperties": ComponentRole.CONFIGURATION,
    "EnableWebSecurity": ComponentRole.CONFIGURATION,
    "Mapper": ComponentRole.MAPPER,
}

REPOSITORY_BASES = frozenset({
    "Repository", "CrudRepository", "ListCrudRepository", "PagingAndSortingRepository",
    "ListPagingAndSortingRepository", "JpaRepository", "JpaSpecificationExecutor",
    "MongoRepository", "ReactiveCrudRepository", "R2dbcRepository",
})


class SpringBootAnalyzer(JavaConventionsAnalyzer):
    def supports(self, project: ProjectInfo) -> bool:
        return project.framework is Framework.SPRING_BOOT

    def classify(self, classes: Sequence[JavaClass]) -> Mapping[str, ComponentRole]:
        by_name = {c.name: c for c in classes}
        return {c.qualified_name: self._spring_role(c, by_name) for c in classes}

    def _spring_role(self, cls: JavaClass, by_name: Mapping[str, JavaClass]) -> ComponentRole:
        for annotation in cls.annotations:
            if role := ANNOTATION_ROLES.get(annotation.name):
                return role
        if self._is_repository(cls, by_name):
            return ComponentRole.REPOSITORY
        role = self.role_for(cls, by_name)
        if role is ComponentRole.OTHER and cls.has_annotation("Component"):
            return ComponentRole.COMPONENT
        return role

    @staticmethod
    def _is_repository(cls: JavaClass, by_name: Mapping[str, JavaClass], depth: int = 0) -> bool:
        """Interfaz que hereda (directa o indirectamente) de un repositorio de Spring Data."""
        if depth > 5:
            return False
        for parent in cls.interfaces:
            name = simple_type_name(parent)
            if name in REPOSITORY_BASES:
                return True
            if (base := by_name.get(name)) and SpringBootAnalyzer._is_repository(base, by_name, depth + 1):
                return True
        return False
