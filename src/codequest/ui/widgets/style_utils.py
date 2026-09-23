from PySide6.QtWidgets import QWidget


def repolish(widget: QWidget) -> None:
    """Vuelve a aplicar el QSS tras cambiar una propiedad usada en un selector."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Cambia una propiedad usada por un selector QSS y fuerza el re-estilo."""
    widget.setProperty(name, value)
    repolish(widget)
