from enum import StrEnum


class ComponentRole(StrEnum):
    """Papel que cumple una clase dentro de la arquitectura del proyecto."""

    ENTITY = "entity"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    DTO = "dto"
    CONFIGURATION = "configuration"
    ENUM = "enum"
    EXCEPTION = "exception"
    UTILITY = "utility"
    MAPPER = "mapper"
    COMPONENT = "component"
    ANNOTATION = "annotation"
    OTHER = "other"
