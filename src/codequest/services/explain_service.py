"""Caso de uso: "Explícamelo con mi código"."""

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider
from codequest.core.ai.code_explainer import CodeExplainer
from codequest.core.ai.context import CodeContext, ContextBuilder
from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import Evaluation


class ExplainService:
    def __init__(self, provider: AIProvider | None) -> None:
        self._provider = provider
        self._explainer = CodeExplainer(provider) if provider else None
        self._cache: dict[str, str] = {}  # clave de pregunta -> explicación (solo durante la sesión)

    @property
    def can_explain(self) -> bool:
        return self._explainer is not None

    @property
    def provider_name(self) -> str | None:
        return self._provider.name if self._provider else None

    @staticmethod
    def build_context(model: ProjectModel, evaluation: Evaluation) -> CodeContext:
        """Hilo principal (lee como mucho un fragmento). Sirve también para pedir consentimiento."""
        question = evaluation.question
        return ContextBuilder(model).build(question.class_name, question.snippet)

    def cached(self, evaluation: Evaluation) -> str | None:
        return self._cache.get(self._key(evaluation))

    def explain(self, evaluation: Evaluation, context: CodeContext) -> str:
        """Bloqueante: ejecutar en un worker. Lanza AIError."""
        if self._explainer is None:
            raise AIError(AIErrorKind.UNAVAILABLE)
        key = self._key(evaluation)
        if key not in self._cache:
            self._cache[key] = self._explainer.explain(evaluation, context)
        return self._cache[key]

    def clear(self) -> None:
        """Al cambiar de proyecto, las explicaciones anteriores dejan de aplicar."""
        self._cache.clear()

    @staticmethod
    def _key(evaluation: Evaluation) -> str:
        # La explicación depende de la pregunta y de la respuesta elegida (aclara el error concreto).
        return f"{evaluation.question.key}|{evaluation.outcome}|{evaluation.answer}"
