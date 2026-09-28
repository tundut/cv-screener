"""OpenAI-platform CV evaluation provider.

Mirrors backend.bedrock.evaluate_cv so it is a drop-in alternative: same inputs,
same validated result contract (candidate_name, fit_score, summary, strengths,
gaps). Selected by setting AI_PROVIDER=openai in the environment.
"""

import os
from typing import Any

try:  # Package context (tests, dashboard)
    from .bedrock import _parse_evaluation
    from .config import Settings
    from .prompting import build_evaluation_prompt
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from bedrock import _parse_evaluation
    from config import Settings
    from prompting import build_evaluation_prompt

_SYSTEM_INSTRUCTION = (
    "You are a careful recruiting assistant. Respond with a single valid JSON "
    "object only, using the keys the user's instructions define."
)


def evaluate_cv(cv_text: str, job_description: str, settings: Settings) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if not settings.openai_model:
        raise RuntimeError("OPENAI_MODEL is not configured")

    try:
        from openai import OpenAI
    except ImportError as error:  # pragma: no cover - environment guard
        raise RuntimeError(
            "The 'openai' package is not installed. Run: pip install openai"
        ) from error

    # An empty OPENAI_BASE_URL in the environment (e.g. a blank line in .env)
    # would otherwise be used by the SDK as the base URL, breaking every request
    # with a misleading "Connection error". Only pass a real, non-empty value.
    base_url = (settings.openai_base_url or "").strip()
    if not base_url:
        os.environ.pop("OPENAI_BASE_URL", None)

    client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if base_url:
        # Allows Azure OpenAI or an OpenAI-compatible gateway.
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_INSTRUCTION},
                {"role": "user", "content": build_evaluation_prompt(cv_text, job_description)},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
    except Exception as error:  # noqa: BLE001 - surface a clean message to the UI
        raise RuntimeError(f"OpenAI request failed: {error}") from error

    if not response.choices:
        raise ValueError("OpenAI returned an empty response")

    output_text = response.choices[0].message.content or ""
    # Reuse the shared parser/validator so both providers enforce one contract.
    return _parse_evaluation(output_text)
