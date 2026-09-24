"""Caso de uso: "Explícamelo con mi código"."""

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider
from codequest.core.ai.code_explainer import CodeExplainer
from codequest.core.ai.context import CodeContext, ContextBuilder
from codequest.core.ai.explanation_grader import ExplanationFeedback, ExplanationGrader
from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import Evaluation
from codequest.core.questions.models import Question


class ExplainService:
    def __init__(self, provider: AIProvider | None) -> None:
        self._provider = provider
        self._explainer = CodeExplainer(provider) if provider else None
        self._grader = ExplanationGrader(provider) if provider else None
        self._cache: dict[str, str] = {}  # clave de pregunta -> explicación (solo durante la sesión)

    def set_provider(self, provider: AIProvider | None) -> None:
        """Activa, cambia o desactiva la IA en caliente. Las explicaciones en caché se descartan."""
        self._provider = provider
        self._explainer = CodeExplainer(provider) if provider else None
        self._grader = ExplanationGrader(provider) if provider else None
        self._cache.clear()

    @property
    def can_explain(self) -> bool:
        return self._explainer is not None

    @property
    def provider_name(self) -> str | None:
        return self._provider.name if self._provider else None

    @staticmethod
    def build_context(model: ProjectModel, evaluation: Evaluation) -> CodeContext:
        """Hilo principal (lee como mucho un fragmento). Sirve también para pedir consentimiento."""
        return ExplainService.context_for(model, evaluation.question)

    @staticmethod
    def context_for(model: ProjectModel, question: Question) -> CodeContext:
        return ContextBuilder(model).build(question.class_name, question.snippet)

    def grade(self, question: Question, answer: str, context: CodeContext) -> ExplanationFeedback:
        """Bloqueante: ejecutar en un worker. Lanza AIError (también si la respuesta es muy corta)."""
        if self._grader is None:
            raise AIError(AIErrorKind.UNAVAILABLE)
        return self._grader.grade(question, answer, context)

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
