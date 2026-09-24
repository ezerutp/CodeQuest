from pathlib import Path

from codequest.core.analysis.java.conventions import JavaConventionsAnalyzer
from codequest.core.analysis.java.parser import TreeSitterJavaParser
from codequest.core.analysis.roles import ComponentRole as R
from codequest.core.analysis.spring.analyzer import SpringBootAnalyzer
from codequest.core.project.scanner import ProjectScanner

EXPECTED_SPRING_ROLES = {
    "ShopApplication": R.CONFIGURATION,
    "SecurityConfig": R.CONFIGURATION,
    "Nested": R.CONFIGURATION,  # por el paquete config
    "UserController": R.CONTROLLER,
    "UserDTO": R.DTO,
    "Order": R.ENTITY,
    "User": R.ENTITY,
    "Role": R.ENUM,
    "GlobalExceptionHandler": R.EXCEPTION,
    "ShopException": R.EXCEPTION,
    "UserNotFoundException": R.EXCEPTION,  # hereda de ShopException -> RuntimeException
    "UserRepository": R.REPOSITORY,
    "OrderRepository": R.REPOSITORY,
    "UserService": R.OTHER,  # interfaz sin anotaciones: no se cuenta dos veces
    "UserServiceImpl": R.SERVICE,
    "DateUtils": R.UTILITY,
    "JwtHelper": R.UTILITY,  # @Component, pero su nombre indica utilidad
    "AuditListener": R.COMPONENT,  # @Component sin convención de nombre ni paquete
    "Audited": R.ANNOTATION,
    "UserControllerTest": R.OTHER,
}


def _classes(project: Path):
    parser = TreeSitterJavaParser()
    return [c for f in ProjectScanner().scan(project).files if parser.supports(f)
            for c in parser.parse(f, f.read_text())]


def test_spring_roles(shop_project: Path) -> None:
    classes = _classes(shop_project)
    roles = SpringBootAnalyzer().classify(classes)

    by_simple_name = {c.name: roles[c.qualified_name] for c in classes}
    assert by_simple_name == EXPECTED_SPRING_ROLES


def test_conventions_without_spring(shop_project: Path) -> None:
    classes = _classes(shop_project)
    roles = JavaConventionsAnalyzer().classify(classes)
    by_simple_name = {c.name: roles[c.qualified_name] for c in classes}

    assert by_simple_name["User"] is R.OTHER  # sin Spring, @Entity no se interpreta
    assert by_simple_name["Role"] is R.ENUM
    assert by_simple_name["UserNotFoundException"] is R.EXCEPTION
    assert by_simple_name["UserDTO"] is R.DTO
