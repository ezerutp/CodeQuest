from pathlib import Path

import pytest

from codequest.core.analysis.java.models import JavaClass, TypeKind
from codequest.core.analysis.java.parser import RegexJavaParser
from codequest.core.project.models import SourceFile

BASE = "src/main/java/com/example/shop"


def parse(project: Path, relative: str) -> list[JavaClass]:
    path = project / relative
    file = SourceFile(path=path, relative_path=relative, size=path.stat().st_size)
    return RegexJavaParser().parse(file, file.read_text())


def parse_one(project: Path, relative: str) -> JavaClass:
    classes = parse(project, relative)
    assert len(classes) == 1, [c.name for c in classes]
    return classes[0]


def parse_text(text: str, relative: str = "src/main/java/X.java") -> list[JavaClass]:
    file = SourceFile(path=Path(relative), relative_path=relative, size=len(text))
    return RegexJavaParser().parse(file, text)


def test_entity_header_annotations_and_fields(shop_project: Path) -> None:
    user = parse_one(shop_project, f"{BASE}/entity/User.java")

    assert user.qualified_name == "com.example.shop.entity.User"
    assert user.kind is TypeKind.CLASS
    assert [a.name for a in user.annotations] == ["Entity", "Table"]
    # Paréntesis anidados y llaves dentro de los argumentos de la anotación.
    assert user.annotation("Table").arguments == (
        'name = "users", uniqueConstraints = @UniqueConstraint(columnNames = {"email"})'
    )
    assert (user.start_line, user.end_line) == (10, 45)
    assert [f.name for f in user.fields] == ["id", "name", "greeting", "orders", "role"]
    orders = next(f for f in user.fields if f.name == "orders")
    assert orders.type == "List<Order>"
    assert [a.name for a in orders.annotations] == ["OneToMany"]
    assert (orders.start_line, orders.end_line) == (24, 25)
    assert "jakarta.persistence.*" in user.imports


def test_strings_and_comments_do_not_break_structure(shop_project: Path) -> None:
    user = parse_one(shop_project, f"{BASE}/entity/User.java")

    assert [m.name for m in user.methods] == ["User", "User", "getId", "getOrders"]
    assert [m.is_constructor for m in user.methods] == [True, True, False, False]


def test_controller_methods_parameters_and_mappings(shop_project: Path) -> None:
    controller = parse_one(shop_project, f"{BASE}/controller/UserController.java")

    assert controller.annotation("RequestMapping").string_values() == ("/api/users",)
    methods = {m.name: m for m in controller.methods}
    assert set(methods) == {"UserController", "list", "getUser", "create", "delete"}

    get_user = methods["getUser"]
    assert get_user.return_type == "ResponseEntity<UserDTO>"
    assert get_user.annotations[0].string_values() == ("/{id}",)
    assert get_user.signature == "getUser(Long id)"
    assert [a.name for a in get_user.parameters[0].annotations] == ["PathVariable"]
    assert (get_user.start_line, get_user.end_line) == (25, 28)

    create = methods["create"]
    assert [p.name for p in create.parameters] == ["dto", "notify"]
    assert [a.name for a in create.parameters[0].annotations] == ["Valid", "RequestBody"]
    assert create.parameters[1].type == "boolean"

    # @SuppressWarnings({...}) contiene llaves dentro de paréntesis.
    assert [a.name for a in methods["delete"].annotations] == ["SuppressWarnings", "DeleteMapping"]


def test_service_generics_varargs_throws_and_lambda_field(shop_project: Path) -> None:
    service = parse_one(shop_project, f"{BASE}/service/UserServiceImpl.java")

    assert service.interfaces == ("UserService",)
    assert [f.name for f in service.fields] == ["BY_NAME", "userRepository"]
    by_name = service.fields[0]
    assert by_name.modifiers == ("private", "static", "final")
    assert by_name.type == "Comparator<UserDTO>"

    update = next(m for m in service.methods if m.name == "updateUser")
    assert update.return_type == "UserDTO"
    assert [(p.type, p.name) for p in update.parameters] == [
        ("Long", "id"), ("UserDTO", "dto"), ("String...", "tags"),
    ]
    assert update.throws == ("IllegalStateException", "UserNotFoundException")
    assert [a.name for a in update.annotations] == ["Transactional"]


def test_repository_interface(shop_project: Path) -> None:
    repo = parse_one(shop_project, f"{BASE}/repository/UserRepository.java")

    assert repo.kind is TypeKind.INTERFACE
    assert repo.superclass is None
    assert repo.interfaces == ("JpaRepository<User, Long>",)
    search = next(m for m in repo.methods if m.name == "searchByName")
    assert not search.has_body
    assert search.annotations[0].name == "Query"
    assert "LIKE %:name%" in search.annotations[0].arguments


def test_enum_constants_with_bodies(shop_project: Path) -> None:
    role = parse_one(shop_project, f"{BASE}/entity/Role.java")

    assert role.kind is TypeKind.ENUM
    assert role.enum_constants == ("ADMIN", "CUSTOMER", "GUEST")
    assert [f.name for f in role.fields] == ["label"]
    assert [m.name for m in role.methods] == ["Role", "canBuy"]


def test_record_components(shop_project: Path) -> None:
    dto = parse_one(shop_project, f"{BASE}/dto/UserDTO.java")

    assert dto.kind is TypeKind.RECORD
    assert [(f.type, f.name) for f in dto.fields] == [("Long", "id"), ("String", "name")]
    assert [a.name for a in dto.fields[1].annotations] == ["NotBlank"]


def test_nested_class_and_anonymous_class_initializer(shop_project: Path) -> None:
    config, nested = parse(shop_project, f"{BASE}/config/SecurityConfig.java")

    assert config.name == "SecurityConfig"
    assert [m.name for m in config.methods] == ["passwordEncoder"]  # no el encode() anónimo
    assert nested.name == "Nested" and nested.enclosing == "SecurityConfig"
    assert nested.qualified_name == "com.example.shop.config.SecurityConfig.Nested"
    assert [(f.type, f.name) for f in nested.fields] == [("int[]", "ports")]


def test_annotation_type(shop_project: Path) -> None:
    audited = parse_one(shop_project, f"{BASE}/util/Audited.java")

    assert audited.kind is TypeKind.ANNOTATION
    assert [m.name for m in audited.methods] == ["value"]


def test_generic_class_with_bounded_type_parameters() -> None:
    (cls,) = parse_text("""
        package p;
        public abstract class Base<T extends Comparable<T>, ID> extends Parent<T> implements A, B<ID> {
            protected Map<String, List<T>> cache = new HashMap<>();
            public abstract <R> R convert(T value);
        }
    """)

    assert cls.superclass == "Parent<T>"
    assert cls.interfaces == ("A", "B<ID>")
    assert cls.fields[0].type == "Map<String, List<T>>"
    convert = cls.methods[0]
    assert (convert.return_type, convert.name, convert.has_body) == ("R", "convert", False)


def test_multiple_top_level_types_and_multi_declarators() -> None:
    first, second = parse_text("""
        class First { int a, b = 2; }
        interface Second extends First, Comparable<Second> {}
    """)

    assert [f.name for f in first.fields] == ["a", "b"]
    assert second.interfaces == ("First", "Comparable<Second>")


@pytest.mark.parametrize("text", [
    "",
    "package only;",
    "class Broken {",
    "public class X { void m( { }",
    "@Weird( class Y {}",
])
def test_malformed_input_does_not_raise(text: str) -> None:
    parse_text(text)
