"""Roles de React."""

from enum import StrEnum


class ReactRole(StrEnum):
    COMPONENT = "component"
    HOOK = "hook"
    SERVICE = "service"
    TYPE = "type"
    ENUM = "enum"
    UTILITY = "utility"
