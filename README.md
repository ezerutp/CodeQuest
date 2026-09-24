# CodeQuest

> Aprende el proyecto que tú mismo construiste.

CodeQuest es una aplicación de escritorio que analiza el repositorio donde la ejecutas
y convierte su código real en ejercicios interactivos. La primera versión soporta
proyectos **Java · Spring Boot · Maven/Gradle**.

Versión actual: **0.3.0**. Ver [docs/PLAN.md](docs/PLAN.md) para la arquitectura y el roadmap.

## Modos de juego

Todas las preguntas salen del código de tu proyecto:

| Modo | Qué haces | IA |
|------|-----------|----|
| Alternativas | Eliges qué hace una anotación o un supertipo en tu código | No |
| Verdadero o falso | Decides si una afirmación sobre tu código es cierta | No |
| Encuentra el error | Señalas la línea que se cambió en tu código | No |
| Corrige el código | Editas el fragmento hasta dejarlo sin el error | No |
| Comparaciones | Explicas la diferencia entre lo que usas y su alternativa (`@RestController` vs `@Controller`…) | No |
| Explícame este código | Describes con tus palabras qué hace un método; Claude lo evalúa | Sí |

Los errores de *Encuentra el error* y *Corrige el código* se aplican sobre una copia en memoria:
tu proyecto nunca se modifica.

## Requisitos

- Python 3.12+
- (Opcional) `ANTHROPIC_API_KEY` para las funciones con IA

## Instalación

```bash
cd /ruta/CodeQuest
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # añade ",ai" para instalar también el SDK de Anthropic
```

## Uso

```bash
cd mi-proyecto-spring
codequest                          # analiza el directorio actual
codequest ../otro-proyecto         # o una ruta concreta
codequest --debug                  # logs detallados en la terminal
```

Sin instalar el paquete:

```bash
cd mi-proyecto-spring
python /ruta/CodeQuest/main.py
```

## IA (opcional)

CodeQuest funciona completo sin IA. Para activar las funciones con Claude:

```bash
pip install -e ".[ai]"
export ANTHROPIC_API_KEY=...          # nunca se guarda ni se registra
export CODEQUEST_AI_MODEL=...         # opcional; por defecto claude-opus-5
```

La IA sirve para:

- **Completar la base de conocimiento** (*Conceptos → Completar con IA*): genera explicaciones
  para las anotaciones que tu proyecto usa y CodeQuest aún no conoce. Solo envía el nombre y el
  import de cada elemento (p. ej. `lombok.Data`), nunca código.
- **"Explícamelo con mi código"** (tras responder una pregunta): explica el concepto sobre tu
  código real. Envía el fragmento de la pregunta y solo las firmas de las clases relacionadas,
  y te pide confirmación la primera vez.

## Privacidad y seguridad

- CodeQuest **solo lee** el proyecto analizado; nunca escribe en él.
- El progreso (SQLite) y los logs se guardan en el directorio de datos del usuario, no en el repo.
  La base solo guarda qué preguntas respondiste y cómo, nunca tu código.
- La API key solo se lee de la variable de entorno. Nunca se muestra, guarda ni registra.
- Solo se enviarán fragmentos de código a la IA en los ejercicios marcados con **IA**.

## Desarrollo

```bash
pytest
```

Estructura: `core/` (lógica, sin Qt) · `ui/` (PySide6) · `app/` (arranque).
Detalles en [docs/PLAN.md](docs/PLAN.md#c-estructura-del-repositorio).
