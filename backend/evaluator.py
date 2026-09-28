"""Provider dispatch for CV evaluation.

Selects the evaluation backend from settings.ai_provider so the dashboard and
the S3-triggered Lambda share one entry point:

    bedrock (default) -> backend.bedrock.evaluate_cv
    openai            -> backend.openai_provider.evaluate_cv
    mock              -> backend.mock_ai.evaluate_cv_mock
"""

from typing import Any

try:  # Package context (tests, dashboard)
    from .config import Settings
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from config import Settings


def run_evaluation(cv_text: str, job_description: str, settings: Settings) -> dict[str, Any]:
    provider = (settings.ai_provider or "bedrock").lower()

    if provider == "mock":
        try:
            from .mock_ai import evaluate_cv_mock
        except ImportError:
            from mock_ai import evaluate_cv_mock
        return evaluate_cv_mock(cv_text, job_description)

    if provider == "openai":
        try:
            from .openai_provider import evaluate_cv as evaluate_openai
        except ImportError:
            from openai_provider import evaluate_cv as evaluate_openai
        return evaluate_openai(cv_text, job_description, settings)

    if provider == "bedrock":
        try:
            from .bedrock import evaluate_cv as evaluate_bedrock
        except ImportError:
            from bedrock import evaluate_cv as evaluate_bedrock
        return evaluate_bedrock(cv_text, job_description, settings)

    raise RuntimeError(f"Unknown AI_PROVIDER '{settings.ai_provider}'")
