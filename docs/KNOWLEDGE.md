# Base de conocimiento

CodeQuest separa el **conocimiento general** (qué es `@Transactional`, una analogía,
alternativas falsas verosímiles) del **código del proyecto** (dónde lo usa el estudiante).
Las preguntas se generan cruzando ambos.

## Capas

Los conceptos se cargan en orden de prioridad. Si dos conceptos reclaman el mismo `id`,
la misma anotación o el mismo supertipo, gana el primero y el otro se descarta con un
aviso en la página **Conceptos**.

| Capa | Dónde | Origen (`source`) |
|------|-------|-------------------|
| Integrada | `src/codequest/resources/knowledge/*.yaml` (dentro del paquete) | `builtin` |
| Del usuario | carpeta de datos de CodeQuest → `knowledge/` (Linux: `~/.local/share/codequest/knowledge/`) | `user` o `ai` |

- La capa integrada es contenido revisado a mano. Si un archivo integrado no es válido, la
  aplicación no arranca: es un bug que detectan los tests.
- En la carpeta del usuario, un archivo inválido se omite y se informa. Un archivo del
  usuario nunca puede declararse `builtin` ni reemplazar un concepto integrado.
- La ruta exacta se muestra en **Conceptos → Abrir carpeta**.

## Formato

Un archivo puede contener uno o varios conceptos:

```yaml
version: 1
source: user          # opcional, solo en la carpeta del usuario: user | ai
concepts:
  - id: lombok.data                 # único y estable
    title: "@Data"
    topic: other                    # web | di | jpa | data | transactions | validation | errors | config | other
    matches:                        # qué explica este concepto (nombres simples)
      annotations: [Data]
      supertypes: []
    summary: Genera getters, setters, equals, hashCode y toString de la clase.
    explanation: |
      Primer párrafo.

      Segundo párrafo (separados por una línea en blanco).
    analogy: Es como un sello que rellena por ti los formularios repetitivos.
    distractors:                    # al menos 3, falsos pero verosímiles
      - Guarda automáticamente la clase en la base de datos al crearla.
      - Convierte la clase en un DTO que solo puede leerse desde la API REST.
      - Marca la clase como inmutable para que ningún campo pueda cambiar.
    youtube_query: Lombok @Data explicado
```

## Reglas de calidad

Todo concepto, venga de donde venga, se valida al cargarse (`core/knowledge/validation.py`):

- Todos los campos de texto son obligatorios.
- `matches` indica al menos una anotación o supertipo.
- Al menos **3 distractores distintos**, y ninguno igual a la respuesta.
- **La respuesta correcta (`summary`) no puede ser más de un 10 % más larga que el distractor
  más largo.** Si la correcta destaca por longitud, se acierta sin saber.

Consejos para escribir buen contenido:

- `summary` es una frase corta que contesta "¿qué hace esto?". Los detalles van en `explanation`.
- Los distractores deben describir algo que suene a Spring pero sea falso. No uses el resumen
  de otro concepto: puede ser parcialmente cierto (un `@Service` también "registra un bean")
  y la pregunta quedaría ambigua.
- La analogía conecta con algo cotidiano; mejor en una o dos frases.

## Huecos

Después del análisis, la página **Conceptos** lista lo que el proyecto usa y CodeQuest no
sabe explicar. Esos elementos no generan preguntas. Se ignoran las anotaciones del propio
lenguaje (`@Override`, `@Deprecated`, meta-anotaciones), las anotaciones y tipos definidos en
el proyecto y los supertipos básicos de Java (`Serializable`, `RuntimeException`…).
