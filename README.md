# CodeQuest

> Aprende el proyecto que tú mismo construiste.

CodeQuest es una aplicación de escritorio que analiza el repositorio donde la ejecutas
y convierte su código real en ejercicios interactivos. La primera versión soporta
proyectos **Java · Spring Boot · Maven/Gradle**.

Versión actual: **0.4.0**. Ver [docs/PLAN.md](docs/PLAN.md) para la arquitectura y el roadmap.

## Modos de juego

Todas las preguntas salen del código de tu proyecto:

| Modo | Qué haces | IA |
|------|-----------|----|
| Alternativas | Eliges qué hace una anotación o un supertipo en tu código | No |
| Verdadero o falso | Decides si una afirmación sobre tu código es cierta | No |
| Encuentra el error | Señalas la línea que se cambió en tu código | No |
| Corrige el código | Editas el fragmento hasta dejarlo sin el error; «Probar» revisa tu versión sin enviarla | No |
| Comparaciones | Explicas la diferencia entre lo que usas y su alternativa (`@RestController` vs `@Controller`…) | No |
| Explícame este código | Describes con tus palabras qué hace un método; Claude lo evalúa | Sí |

Los errores de *Encuentra el error* y *Corrige el código* se aplican sobre una copia en memoria:
tu proyecto nunca se modifica.

## Autocompletado de Java (opcional)

En *Corrige el código* el editor puede sugerir mientras escribes, como VS Code: al escribir `.` o
pulsar Ctrl+Espacio (`HttpStatus.` → `NO_CONTENT`, `NOT_FOUND`…), y «Probar» muestra también los
errores de compilación reales (`HttpStatus.FOO`, un método que no existe…). Usa
[jdtls](https://github.com/eclipse-jdtls/eclipse.jdt.ls), el mismo servidor de Java que VS Code.

Se activa desde *Configuración → Autocompletado de Java → Descargar* (unos 51 MB, desde
download.eclipse.org) y necesita **Java 21 o superior**. Arranca solo al abrir un proyecto Java; la
primera vez tarda más porque Maven o Gradle descargan las dependencias del proyecto. Sin jdtls
todo funciona igual.

## Requisitos

- Python 3.12+
- (Opcional) Java 21+ para el autocompletado de Java
- (Opcional) `ANTHROPIC_API_KEY` para las funciones con IA

## Instalación

Para usar CodeQuest como un programa más (Linux y macOS):

```bash
git clone https://github.com/ezerutp/CodeQuest.git
cd CodeQuest
./install.sh          # o ./install.sh --ai para las funciones con IA
```

El script crea un entorno propio en `~/.local/lib/codequest` y deja el comando `codequest` en
`~/.local/bin`, así que no hace falta activar ningún entorno virtual. Para actualizar, `git pull`
y vuelve a ejecutar `./install.sh`. Para quitarlo, `./install.sh --uninstall`: tu progreso y tus
conceptos se conservan.

### Para desarrollar

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
pip install -e ".[ai]"               # o, si usas el instalador: ./install.sh --ai
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

- CodeQuest **solo lee** el proyecto analizado; nunca escribe en él. jdtls trabaja sobre una copia
  del código en la carpeta de datos de CodeQuest, porque escribe archivos propios en lo que abre.
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
