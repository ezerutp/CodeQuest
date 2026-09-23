# CodeQuest — Plan de arquitectura y MVP

> Documento vivo. Describe cómo funciona CodeQuest, cómo está organizado y en qué
> orden lo construimos. Se actualiza cuando tomamos una decisión importante.

---

## A. Análisis de la idea

### Cómo funciona (flujo de alto nivel)

```text
 codequest (cwd)
     │
     ▼
 ProjectDetector ──► ProjectInfo          ¿es código? ¿Java? ¿Spring? ¿Maven/Gradle?
     │
     ▼  (worker thread)
 ProjectScanner ──► [SourceFile]          recorre el árbol, ignora target/, .git/, ...
     │
     ▼
 JavaAnalyzer ────► [JavaClass]           parsing simple (regex), sustituible
     │
     ▼
 SpringBootAnalyzer ► ProjectModel        asigna roles: ENTITY, SERVICE, CONTROLLER...
     │
     ├──────────────► UI: Dashboard / Explorador   (solo lectura de modelos)
     │
     ▼
 QuestionGenerator ─► [Question]          reglas + KnowledgeBase (sin IA)
     │        ▲
     │        └── AITutor (opcional) ◄── ContextBuilder ◄── ProjectModel
     ▼
 GameMode / GameSession ─► Evaluation ─► ProgressRepository (SQLite)
```

1. Al arrancar se toma `Path.cwd()` (o una ruta pasada por argumento) y el
   `ProjectDetector` decide qué tipo de proyecto es. Es rápido: solo mira marcadores.
2. El escaneo y análisis completo corre en un hilo de trabajo (`QThread`) para no
   congelar la UI. El resultado es un `ProjectModel`: un índice en memoria de clases,
   métodos, anotaciones y roles.
3. La UI solo **lee** modelos. Nunca parsea código ni llama a Anthropic.
4. Los ejercicios se generan combinando **hechos del proyecto** (“`UserService.updateUser`
   tiene `@Transactional`”) con **conocimiento general** (“qué es `@Transactional`,
   analogía, distractores típicos”).
5. Si hay IA, se usa para lo que las reglas no pueden hacer bien: evaluar respuestas
   abiertas, explicar con el contexto del proyecto, generar pistas. Si no, todo sigue
   funcionando con el banco local.
6. Cada intento se guarda en SQLite (fuera del repositorio analizado) para calcular
   progreso, temas débiles y, más adelante, XP y rachas.

### Arquitectura recomendada: tres capas

| Capa | Paquete | Depende de | Regla |
|------|---------|------------|-------|
| Dominio / núcleo | `codequest.core` | stdlib + `pyyaml` (+ `anthropic` opcional en `core/ai/providers`) | **No importa Qt.** Testeable con pytest puro. |
| Servicios de aplicación | `codequest.services` | `core` | Casos de uso: “analizar proyecto”, “siguiente ejercicio”, “registrar respuesta”. |
| Presentación | `codequest.ui` | `services`, modelos de `core` | Widgets, páginas, workers Qt. Sin lógica de negocio. |

**Por qué:** la regla nº 7/8/9 (separar negocio de UI, nada de análisis ni Anthropic
dentro de widgets) se cumple por construcción si `core` no puede importar Qt. Además
permite, en el futuro, una versión CLI o web reutilizando el mismo núcleo.

### Componentes principales

- **Detección y escaneo**: `ProjectDetector`, `ProjectScanner`.
- **Análisis**: `SourceParser` (interfaz) → `RegexJavaParser` (MVP) → futuro
  `TreeSitterJavaParser`. `FrameworkAnalyzer` (interfaz) → `SpringBootAnalyzer`.
  Un `AnalyzerRegistry` elige los analizadores que aplican a cada proyecto.
- **Conocimiento**: `KnowledgeBase` con conceptos (`@Transactional`, `@RestController`,
  `JpaRepository`…), cada uno con explicación, analogía, distractores y preguntas plantilla.
- **Ejercicios**: `QuestionGenerator` (reglas), `Question`, `BaseGameMode` y sus modos,
  `GameSession`.
- **IA**: `AIProvider` (interfaz mínima), `AnthropicProvider`, `AITutor` (prompts y
  parseo de respuestas), `ContextBuilder` (selección de contexto mínimo).
- **Persistencia**: `Database` (sqlite3 + migraciones), `ProgressRepository`.
- **UI**: `MainWindow`, `Sidebar`, páginas, widgets reutilizables (`Card`, `StatTile`,
  `CodeEditor`, `ChoiceButton`, `StatusBadge`…), `theme` (paleta + QSS modular).

### Riesgos técnicos

| Riesgo | Mitigación |
|--------|-----------|
| **Parsing con regex es frágil** (genéricos anidados, anotaciones multilínea con paréntesis, comentarios y strings que contienen `{`, records, clases internas). | Parser detrás de la interfaz `SourceParser`; pre-procesar eliminando comentarios/strings; contar llaves para delimitar métodos; tests con fixtures Java reales; migrar a `tree-sitter-java` en v1.0. |
| **Lombok** (`@Data`, `@RequiredArgsConstructor`) oculta getters/constructores. | Tratar Lombok como conceptos de la KB; no asumir que un método “no existe”. |
| **Calidad de preguntas por reglas**: repetitivas o triviales. | Plantillas variadas, distractores por concepto, anti-repetición usando el historial; IA para enriquecer. |
| **Coste, latencia y privacidad de la IA**. | Envío de fragmentos mínimos (`ContextBuilder`), indicador visible “✨ usará IA”, llamadas en worker, caché de explicaciones por concepto, límites de tokens. |
| **Respuestas de la IA mal formadas** (JSON roto). | Salida estructurada, validación, fallback al feedback local. |
| **Hilos en Qt**: tocar widgets desde un worker crashea. | Workers emiten señales con modelos inmutables; la UI actualiza en el hilo principal. |
| **Repositorios grandes / multi-módulo** Maven/Gradle. | Límite de tamaño por archivo, poda de carpetas ignoradas, búsqueda de `src/main/java` en submódulos. |
| **“Encuentra el error” necesita mutaciones creíbles**. | Catálogo de mutaciones seguras y específicas (cambiar `@GetMapping`→`@PostMapping`, `save`→`findById`, quitar `@Transactional`), nunca sobre el archivo real. |
| **Emojis a color** no se renderizan en Qt en todos los sistemas (verificado en Fedora con Noto COLRv1). | Iconos vectoriales con `qtawesome` (Material Design Icons) detrás de nombres semánticos en `ui/icons.py`. Sin emojis en la UI. |
| **Modificar el proyecto del usuario por error**. | Ver sección “Seguridad”: acceso de solo lectura por diseño. |

### Decisiones importantes (y por qué)

1. **Layout `src/`** (`src/codequest/...`) + `pyproject.toml` con entry point
   `codequest`. Evita importar accidentalmente el código sin instalar y permite
   `pip install -e .` → comando `codequest` disponible en cualquier directorio.
   Se mantiene `main.py` en la raíz para `python /ruta/CodeQuest/main.py`.
2. **Los datos de CodeQuest nunca se guardan en el proyecto analizado.** SQLite y logs
   viven en el directorio de datos del usuario (`platformdirs`:
   `~/.local/share/codequest/`, `%APPDATA%\codequest` …).
3. **Identidad del proyecto (MVP):** `project_id = sha256(ruta canónica)[:16]`. Guardamos
   también `git remote origin` (sin credenciales) y el nombre como metadatos. Si el
   usuario mueve la carpeta y el remote coincide, se puede re-vincular (v0.3).
   Simple, determinista y sin escribir nada en el repo del usuario.
4. **`AIProvider` mínimo**: un único método `complete(request) -> AIResponse`. Los
   prompts y el parseo viven en `AITutor`. Así añadir `OpenAIProvider` o un modelo
   local es implementar un método, no reescribir cada tarea.
5. **KnowledgeBase en Python primero, YAML después.** En el MVP un módulo Python con
   dataclasses (tipado, sin dependencias). En v0.2 se mueve a
   `resources/knowledge/*.yaml` con el mismo esquema.
6. **Preguntas identificadas por clave estable**, no por su texto:
   `rule_id + clase + miembro` (p. ej. `annotation.transactional:UserService#updateUser`).
   Permite historial y repetición espaciada sin guardar código en la base de datos.
7. **Estilos**: paleta de tokens en Python + varios `.qss` pequeños con placeholders
   `${token}`. Cambiar de tema = cambiar la paleta.
8. **Iconos con `qtawesome`**, no emojis: se renderizan igual en todos los sistemas y se
   colorean con la paleta. Las maquetas de este documento usan emojis solo como ilustración.
9. **Sin IA no hay bloqueo**: toda funcionalidad tiene un camino local; la IA solo
   mejora.
10. **Parser por texto enmascarado (GCQ-01).** Comentarios y strings se sustituyen por
    espacios conservando offsets; después se recorre el código contando llaves/paréntesis
    y las regex solo se aplican a cabeceras cortas. Evita que `"{"` o un `class` en un
    comentario rompan la estructura, y las líneas siguen siendo exactas para los snippets.
    Coste medido: ~100 µs por método (un proyecto de 60 clases, ~50 ms).
11. **Los roles viven en `ProjectModel.roles`, no en `JavaClass`.** Los modelos Java son
    inmutables (seguros entre hilos) y el parser no depende de Spring.
12. **Interfaces sin anotaciones no se clasifican por paquete**: `UserService` +
    `UserServiceImpl (@Service)` cuentan como 1 service, no 2. Las clases de `src/test/`
    se parsean pero no cuentan en las estadísticas.
13. **Roles adicionales** a los de la especificación: `MAPPER`, `COMPONENT` (un `@Component`
    sin otra convención) y `ANNOTATION` (anotaciones propias). `@ControllerAdvice` cuenta
    como `EXCEPTION`, y `@SpringBootApplication` como `CONFIGURATION`.
14. **Resaltado de sintaxis sin Qt (GCQ-02).** `core/analysis/java/lexer.py` tokeniza línea a
    línea con estado (comentario de bloque / text block abiertos); `JavaHighlighter` solo
    asigna colores de la paleta. El lexer se prueba con pytest y servirá a otros lenguajes.
15. **Numeración real en fragmentos.** `CodeEditor.set_code(texto, first_line=42)` numera
    desde la línea 42 del archivo, y `highlight_lines()` usa esa misma numeración; así las
    preguntas pueden citar "línea 42" igual que el IDE del estudiante.
16. **Árbol de paquetes compactado** (`core/analysis/package_tree.py`): `com.example.shop`
    se muestra como un nodo, como las carpetas compactas de VS Code.
17. **Distractores solo escritos a mano (GCQ-03).** Usar el resumen de otro concepto como
    opción falsa puede crear ambigüedad (un `@Service` también "registra un bean"). La
    `KnowledgeBase` valida al arrancar ≥3 distractores por concepto y un test impide que la
    respuesta correcta sea >10 % más larga que el distractor más largo (se adivinaría).
18. **Preguntas sin código.** `Question` guarda un `SnippetRef` (archivo, líneas, línea a
    resaltar); el texto se lee al mostrarla. El generador es puro y testeable, y la base de
    datos nunca guardará código.
19. **Rondas variadas.** El generador agrupa por concepto y reparte round-robin: 10
    controllers no producen 10 preguntas de `@RestController`.
20. **Catálogo de modos en `core/games/catalog.py`**: dashboard y Aprender muestran lo mismo.
21. **Base de conocimiento en YAML por capas (GCQ-04)**: integrada (`resources/knowledge/`,
    prioritaria) + carpeta del usuario (`platformdirs`, fuentes `user`/`ai`). Cada concepto
    declara qué anotaciones/supertipos explica (`matches`), así los conceptos de la caché son
    autosuficientes. Todo concepto pasa la misma validación. Formato: `docs/KNOWLEDGE.md`.
    `core` pasa a depender de `pyyaml` (con el parser C de libyaml si está disponible).
22. **Huecos de conocimiento**: `core/knowledge/coverage.py` lista lo que el proyecto usa y no
    tiene concepto, con su import real (`lombok.Data`). Es la entrada de GCQ-05: generar esos
    conceptos con IA, enviando solo el nombre y el import, nunca código del proyecto.
23. **IA (GCQ-05).** `AIProvider.complete(AIRequest) -> AIResponse` con esquema JSON opcional;
    los errores del SDK se traducen a `AIError` (tipo + mensaje en español). `AnthropicProvider`
    usa `claude-opus-5` (configurable con `CODEQUEST_AI_MODEL`), salida estructurada
    (`output_config.format`) y `fallbacks: "default"` ante rechazos. La IA nunca decide `id` ni
    `matches` de un concepto; si no conoce el elemento lo dice (`known: false`) y no se inventa
    nada. Lo generado pasa la validación común (un reintento con el motivo) y se guarda como
    `source: ai`. La generación corre en `BackgroundTask`; la `KnowledgeBase` solo se modifica
    en el hilo principal.
24. **"Explícamelo con mi código" (GCQ-07).** `ContextBuilder` envía como código real solo el
    fragmento de la pregunta (≤60 líneas); de la clase y de hasta 2 dependencias directas
    (tipos del proyecto en campos, parámetros o retorno) envía un resumen generado desde el
    modelo, sin cuerpos. Tope de 8000 caracteres. Consentimiento explícito la primera vez por
    proyecto y sesión, con la lista de lo que se envía. El prompt trata el código como material
    de estudio, no como instrucciones. Caché por pregunta y respuesta durante la sesión; una
    respuesta que llega tras pasar de pregunta se descarta.

### Seguridad sobre el repositorio

- El núcleo solo **lee** archivos del proyecto (`Path.read_text`). No existe ninguna
  función de escritura sobre el proyecto en el MVP.
- “Corrige el código” trabaja sobre una **copia en memoria** del fragmento.
- Si en el futuro se ofrece “aplicar cambio al archivo real”, pasará por un único
  componente (`WorkspaceWriter`) que exige confirmación explícita y muestra un diff.
- La API key solo se lee de `ANTHROPIC_API_KEY`; nunca se imprime, registra ni guarda.
  El logging tiene un filtro que enmascara cualquier cadena con forma de key.
- Las URLs de git remote se guardan sin usuario/token.

### Qué dejamos para después

Parser real (tree-sitter), modos FindError/FixCode/Comparison/WhatIf, XP/niveles/rachas,
repetición espaciada, multi-proveedor IA, YouTube, tema claro, i18n, empaquetado
(PyInstaller/pipx), soporte de otros lenguajes (Python, TypeScript/NestJS, Kotlin).

---

## B. Roadmap

### MVP (v0.1) — “Conozco tu proyecto y te hago preguntas”

Estado: ✅ 1, 2, 3, 4, 5, 6, 11 (GCQ-01) · ✅ 7, 8 (GCQ-02) · ✅ 9, 10 (GCQ-03) · ✅ base de conocimiento en YAML y huecos (GCQ-04) · ✅ 12: IA y conceptos con IA (GCQ-05), "Explícamelo con mi código" (GCQ-07) · ⏳ 13 (GCQ-08).

1. App PySide6 con tema oscuro, sidebar y navegación.
2. Detección de `cwd` y del tipo de proyecto (Java · Spring Boot · Maven/Gradle).
3. Escaneo de archivos en worker thread.
4. Parser Java simple: clases, anotaciones, campos, métodos, imports, herencia.
5. Clasificación: Entity, Repository, Service, Controller (+ Enum, DTO, Config, Exception básicos).
6. Dashboard con estadísticas reales.
7. Explorador del proyecto (árbol + panel de detalle de clase).
8. `CodeEditor` con números de línea y resaltado Java (solo lectura / editable).
9. Modo **Alternativas** con preguntas generadas por reglas.
10. Botón **“No sé”** con explicación educativa + analogía (+ acción YouTube preparada).
11. Detección de `ANTHROPIC_API_KEY` e indicador de estado.
12. Integración básica con Claude: “Explícamelo mejor” con contexto mínimo.
13. SQLite: proyecto, sesiones, intentos, dominio por concepto.

### v0.2 — “Aprendo con mis palabras”
- Modo **Explícame este código** evaluado por Claude (feedback pedagógico).
- Modo **Verdadero/Falso**.
- Página **Progreso** (dominio por tema, historial) y página **Conceptos** (KB navegable).
- Página **Configuración** (modelo, activar/desactivar IA, privacidad, tamaño de fuente).
- “Practicar esta clase” desde el explorador.
- KnowledgeBase en YAML.

### v0.3 — “Juego de verdad”
- Modos **Encuentra el error** (mutaciones locales + evaluación IA) y **Corrige el código**.
- Modo **Comparaciones** basado en tecnologías detectadas.
- XP, niveles, rachas, temas débiles, repetición espaciada (SM-2 simplificado).
- Mensaje de bienvenida contextual (“Ayer practicamos Controllers…”).
- Re-vinculación de proyectos movidos (por git remote).

### v1.0 — “Plataforma”
- Parser basado en `tree-sitter` y soporte multi-módulo robusto.
- Modo **¿Qué pasaría si…?**.
- Proveedores OpenAI / Gemini / modelo local.
- Plugins de lenguaje (Kotlin, Python, TypeScript) usando el `AnalyzerRegistry`.
- Tema claro, i18n (es/en), empaquetado distribuible, integración YouTube real.

---

## C. Estructura del repositorio

```text
CodeQuest/
├── main.py                      # Atajo: python main.py (añade src/ al path)
├── pyproject.toml               # Metadatos, dependencias, entry point `codequest`
├── requirements.txt             # Dependencias de ejecución (para quien no use pip -e)
├── requirements-dev.txt         # pytest, etc.
├── docs/PLAN.md                 # Este documento
├── src/codequest/
│   ├── __main__.py              # python -m codequest
│   ├── app/                     # Arranque: args, logging, QApplication, contexto
│   ├── core/                    # Núcleo SIN Qt
│   │   ├── project/             #   detector, scanner, modelos de proyecto/archivos
│   │   ├── analysis/            #   parsers de lenguaje + analizadores de framework
│   │   │   ├── java/            #     modelos Java, RegexJavaParser
│   │   │   └── spring/          #     SpringBootAnalyzer, roles de componentes
│   │   ├── knowledge/           #   KnowledgeBase y conceptos
│   │   ├── questions/           #   Question, QuestionGenerator, reglas
│   │   ├── games/               #   BaseGameMode, modos, GameSession, Evaluation
│   │   ├── ai/                  #   AIProvider, AnthropicProvider, AITutor, ContextBuilder
│   │   └── persistence/         #   Database (sqlite), repositorios
│   ├── services/                # Casos de uso que orquestan core (sin Qt)
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── navigation.py        # Sidebar
│   │   ├── pages/               # Una página por sección
│   │   ├── widgets/             # Componentes reutilizables
│   │   ├── dialogs/
│   │   ├── workers.py           # QThread/QRunnable que llaman a services
│   │   ├── theme/               # Paleta de tokens + cargador de QSS
│   │   ├── icons.py             # Nombres semánticos → iconos qtawesome
│   │   └── styles/              # QSS modulares: base, sidebar, cards, buttons...
│   └── resources/               # icons/, knowledge/*.yaml (v0.2)
└── tests/                       # Tests de core y services (sin UI)
```

Cambios respecto a la propuesta original y por qué:
- `analyzers/` → `analysis/java` + `analysis/spring`: cada lenguaje/framework trae sus
  propios modelos y parser; añadir Kotlin es añadir una carpeta.
- Se añade `services/`: evita que la UI conozca 6 componentes de `core` para hacer una
  acción; la UI habla con un servicio.
- `knowledge/` separado de `questions/`: conocimiento general ≠ generación de preguntas.
- `ui/theme/` + `ui/styles/` modulares (regla nº 17).
- `ui/workers.py` explícito (regla nº 18/19).

---

## D. Modelos y clases principales

### Proyecto
| Clase | Responsabilidad |
|-------|-----------------|
| `ProjectInfo` | Identidad y tipo del proyecto: raíz, nombre, marcadores, lenguaje, framework, build tool, git remote. Inmutable. |
| `ProjectDetector` | Dado un directorio, produce `ProjectInfo`. Solo mira marcadores y archivos de build. |
| `SourceFile` | Archivo relevante: ruta relativa, tipo, tamaño. Carga el contenido bajo demanda (solo lectura). |
| `ProjectScanner` | Recorre el árbol podando carpetas ignoradas y devuelve `[SourceFile]`. Nada más. |
| `ProjectModel` | Resultado del análisis: `ProjectInfo` + archivos + clases + índices (por rol, por nombre). Lo consume la UI y el generador. |

### Análisis
| Clase | Responsabilidad |
|-------|-----------------|
| `SourceParser` (ABC) | `parse(SourceFile) -> list[JavaClass]`. Interfaz para sustituir el parser. |
| `RegexJavaParser` | Implementación MVP: package, imports, clases, anotaciones, campos, métodos, rangos de líneas. |
| `JavaClass` / `JavaMethod` / `JavaField` / `JavaAnnotation` | Modelos del código. Guardan nombre, tipo, anotaciones, modificadores y **rango de líneas** (no el código). |
| `CodeSnippet` | Referencia a un fragmento: archivo + líneas + texto extraído al momento de mostrar. |
| `ComponentRole` (enum) | ENTITY, CONTROLLER, SERVICE, REPOSITORY, DTO, CONFIGURATION, ENUM, EXCEPTION, UTILITY, OTHER. |
| `FrameworkAnalyzer` (ABC) | `supports(ProjectInfo)` y `enrich(ProjectModel)`. |
| `SpringBootAnalyzer` | Asigna roles por anotaciones, herencia (`extends JpaRepository`) y convenciones de nombre/paquete; registra anotaciones usadas. |

### Conocimiento y preguntas
| Clase | Responsabilidad |
|-------|-----------------|
| `Concept` | Entrada de la KB: id (`spring.transactional`), título, explicación, analogía, distractores, tags (tema: JPA, Web, DI…). |
| `KnowledgeBase` | Carga y consulta conceptos por anotación, tipo o tema. |
| `Question` | Pregunta lista para jugar: clave estable, modo, enunciado, `CodeSnippet`, alternativas, índice correcto, `Explanation`, conceptos, origen (local/IA). |
| `QuestionRule` (ABC) | Regla que, a partir de hechos del `ProjectModel` + KB, produce preguntas. Ej: `AnnotationPurposeRule`. |
| `QuestionGenerator` | Ejecuta reglas, baraja, evita repetir lo reciente, prioriza temas débiles. |

### Juego
| Clase | Responsabilidad |
|-------|-----------------|
| `BaseGameMode` (ABC) | `id`, `title`, `requires_ai`, `next_exercise()`, `evaluate(answer) -> Evaluation`. |
| `MultipleChoiceMode`, `ExplainCodeMode`, … | Implementaciones concretas. |
| `Evaluation` | Resultado: correcto/parcial/incorrecto, feedback, conceptos afectados, XP, si usó IA. |
| `GameSession` | Una partida: modo, ejercicios, resultados, racha interna. Emite eventos para persistir. |

### IA
| Clase | Responsabilidad |
|-------|-----------------|
| `AIStatus` | Estado detectado (proveedor, disponible, motivo). Nunca contiene la key. |
| `AIProvider` (ABC) | `complete(AIRequest) -> AIResponse`. |
| `AnthropicProvider` | Implementación con el SDK oficial; lee la key del entorno en el momento de crear el cliente. |
| `ContextBuilder` | Selecciona el contexto mínimo (método, clase, dependencias directas) con presupuesto de caracteres. |
| `AITutor` | Tareas pedagógicas: explicar, evaluar explicación, generar pista. Construye prompts y valida la salida. |

### Persistencia y servicios
| Clase | Responsabilidad |
|-------|-----------------|
| `Database` | Conexión sqlite3, esquema y migraciones (`PRAGMA user_version`). |
| `ProgressRepository` | Proyectos, sesiones, intentos, dominio por concepto. No guarda código. |
| `ProjectService` | Detectar + escanear + analizar → `ProjectModel`. |
| `LearningService` | Crea sesiones de juego, pide preguntas, registra respuestas, calcula progreso. |

Esquema SQLite inicial:
```text
projects(id PK, name, root_path, git_remote, first_seen, last_opened)
sessions(id PK, project_id FK, mode, started_at, ended_at)
attempts(id PK, session_id FK, question_key, concept_id, mode, outcome,
         used_dont_know, used_ai, answered_at)
concept_mastery(project_id, concept_id, correct, incorrect, last_seen, PK(project_id, concept_id))
```

---

## E. Pantallas

### Layout general
```text
┌──────────────┬──────────────────────────────────────────────────────┐
│ ◆ CodeQuest  │                                                      │
│              │                   (página activa)                    │
│ 🏠 Inicio    │                                                      │
│ 🎮 Aprender  │                                                      │
│ 📂 Mi proyecto│                                                     │
│ 📊 Progreso  │                                                      │
│ 🧠 Conceptos │                                                      │
│ ⚙ Ajustes    │                                                      │
│              │                                                      │
│ ──────────── │                                                      │
│ PROYECTO     │                                                      │
│ my-shop-api  │                                                      │
│ ● Claude     │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

### Dashboard (Inicio)
```text
 👋 Volvamos a tu proyecto
 ┌───────────────────────────────────────────────────────────────┐
 │ my-shop-api                               [Cambiar proyecto]  │
 │ [Spring Boot] [Java] [Maven]    ~/repos/my-shop-api           │
 │                                                               │
 │ Progreso ███████░░░ 72%              [ ▶ Continuar aprendiendo ]│
 └───────────────────────────────────────────────────────────────┘
 ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
 │ 74     ││ 10     ││ 10     ││ 10     ││ 10     │
 │Archivos││Entities││Control.││Services││Repos   │
 └────────┘└────────┘└────────┘└────────┘└────────┘
 MODOS DE JUEGO
 ┌──────────────┐┌──────────────┐┌──────────────┐
 │🎯 Alternativas││🧠 Explícame  ││🐛 Encuentra  │
 │ Responde...  ││ ✨ usa IA    ││ Próximamente │
 └──────────────┘└──────────────┘└──────────────┘
 (… 🔧 Corrige · ⚔ Comparaciones · 🎲 Aleatorio)
```

### Aprender (selector de modo)
Grid de modos con descripción, badge “🖥 Local” / “✨ IA” y estado bloqueado si
requiere IA no disponible. Filtros: “Todo el proyecto”, “Por rol”, “Por concepto”.

### Juego (Alternativas)
```text
 🎯 Alternativas · Pregunta 3/10                 🖥 Procesado localmente
 ┌───────────────────────────────────────────────────────────────┐
 │ En tu método updateUser(), ¿qué propósito tiene @Transactional?│
 └───────────────────────────────────────────────────────────────┘
 ┌ UserService.java · líneas 42–51 ──────────────────────────────┐
 │ 42  @Transactional                                            │
 │ 43  public User updateUser(Long id, UserDTO dto) {            │
 │ ...                                                           │
 └───────────────────────────────────────────────────────────────┘
 [ A  Convierte el método en un endpoint HTTP             ]
 [ B  Ejecuta las operaciones dentro de una transacción   ]
 [ C  Convierte el resultado a JSON                        ]
 [ D  Inyecta el Repository                                ]
                     [ 🤷 No sé la respuesta ]   [ Siguiente → ]

 ── tras responder / “No sé” ──
 ┌ ✅ Correcto / 💡 La respuesta correcta es B ───────────────────┐
 │ explicación… │ 💡 Analogía … │ [🎥 Buscar en YouTube] [✨ Explícamelo con mi código] │
 └───────────────────────────────────────────────────────────────┘
```

### Mi proyecto (explorador)
```text
 ┌ Árbol ─────────────────┐┌ UserService.java ───────────────────────┐
 │ ▾ com.example.app      ││ [Service]  com.example.app.service       │
 │   ▾ controller         ││ Anotaciones: @Service @Transactional     │
 │     UserController     ││ Métodos: findAll() findById() save() ... │
 │   ▾ service            ││ [ 🎯 Practicar esta clase ]              │
 │     UserService   ◄    ││ ┌ código (solo lectura) ───────────────┐ │
 │   ▸ repository         ││ │ 1 package com.example...             │ │
 │   ▸ entity             ││ └──────────────────────────────────────┘ │
 └────────────────────────┘└──────────────────────────────────────────┘
 Filtro: [Todos ▾]  🔍 buscar clase…
```

### Progreso (v0.2)
Nivel y XP (v0.3), barra de dominio por tema (Spring Web, JPA, DI, Transacciones),
lista de conceptos débiles con botón “Practicar”, clases practicadas, historial de sesiones.

### Configuración (v0.2)
IA: estado, proveedor, modelo, interruptor “usar IA”, aviso de privacidad (qué se envía).
Apariencia: tema, tamaño de fuente del editor. Datos: ubicación de la base de datos,
“borrar progreso de este proyecto”.
