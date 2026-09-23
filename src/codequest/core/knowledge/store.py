"""Escritura de conceptos en la carpeta del usuario: un YAML por concepto.

Solo escribe en la carpeta de datos de CodeQuest, nunca en el proyecto analizado.
"""

import logging
import os
import re
import tempfile
from pathlib import Path

import yaml

from codequest.core.knowledge.loader import SUPPORTED_VERSION
from codequest.core.knowledge.models import Concept, ConceptSource

log = logging.getLogger(__name__)

_UNSAFE_FILENAME = re.compile(r"[^a-z0-9._-]+")


class _Literal(str):
    """Texto multilínea que se escribe como bloque `|` para que sea fácil de editar."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(_Literal, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))


def concept_to_yaml(concept: Concept) -> str:
    matches: dict[str, list[str]] = {}
    if concept.matches.annotations:
        matches["annotations"] = list(concept.matches.annotations)
    if concept.matches.supertypes:
        matches["supertypes"] = list(concept.matches.supertypes)
    document = {
        "version": SUPPORTED_VERSION,
        "source": concept.source.value,
        "concepts": [{
            "id": concept.id,
            "title": concept.title,
            "topic": concept.topic.value,
            "matches": matches,
            "summary": concept.summary,
            "explanation": _Literal(concept.explanation.strip() + "\n"),
            "analogy": concept.analogy,
            "distractors": list(concept.distractors),
            "youtube_query": concept.youtube_query,
        }],
    }
    return yaml.dump(document, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=1000)


class KnowledgeStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, concept_id: str) -> Path:
        return self.directory / f"{_UNSAFE_FILENAME.sub('-', concept_id.lower()).strip('-')}.yaml"

    def save(self, concept: Concept) -> Path:
        if concept.source is ConceptSource.BUILTIN:
            raise ValueError("Los conceptos integrados no se guardan en la carpeta del usuario")
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.path_for(concept.id)
        # Escritura atómica: un corte a mitad nunca deja un YAML a medias.
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".tmp-", suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(concept_to_yaml(concept))
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        log.info("Concepto guardado: %s", target)
        return target

    def delete(self, concept_id: str) -> bool:
        path = self.path_for(concept_id)
        if not path.is_file():
            return False
        path.unlink()
        log.info("Concepto borrado: %s", path)
        return True
