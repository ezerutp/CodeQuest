from PySide6.QtWidgets import QWidget


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Cambia una propiedad usada por un selector QSS y fuerza el re-estilo."""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
