import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from backend.config import Settings
from backend.evaluator import run_evaluation
from backend.openai_provider import evaluate_cv


def _settings(api_key: str = "sk-test", model: str = "gpt-4o-mini", provider: str = "openai") -> Settings:
    return Settings(
        aws_region="ap-southeast-1",
        cv_bucket_name="test-bucket",
        cv_results_table="cv-evaluations",
        bedrock_model_id="",
        ai_provider=provider,
        openai_api_key=api_key,
        openai_model=model,
        openai_base_url="",
    )


def _payload() -> dict:
    return {
        "candidate_name": "Jane Doe",
        "fit_score": 90,
        "summary": "Great match.",
        "strengths": ["Python"],
        "gaps": [],
    }


def _install_fake_openai(monkeypatch, content: str):
    """Install a fake 'openai' module whose client returns the given content."""
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=content))]

    client = MagicMock()
    client.chat.completions.create.return_value = completion

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    return fake_module, client


def test_evaluate_cv_requires_api_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        evaluate_cv("cv", "jd", _settings(api_key=""))


def test_evaluate_cv_returns_parsed_result(monkeypatch):
    _install_fake_openai(monkeypatch, json.dumps(_payload()))

    result = evaluate_cv("Jane Doe, Python dev", "Need Python", _settings())

    assert result["candidate_name"] == "Jane Doe"
    assert result["fit_score"] == 90.0


def test_evaluate_cv_passes_model_and_json_format(monkeypatch):
    fake_module, client = _install_fake_openai(monkeypatch, json.dumps(_payload()))

    evaluate_cv("cv", "jd", _settings(model="gpt-4.1"))

    fake_module.OpenAI.assert_called_once_with(api_key="sk-test")
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4.1"
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_run_evaluation_dispatches_to_openai(monkeypatch):
    _install_fake_openai(monkeypatch, json.dumps(_payload()))

    result = run_evaluation("cv", "jd", _settings(provider="openai"))

    assert result["candidate_name"] == "Jane Doe"


def test_run_evaluation_rejects_unknown_provider():
    with pytest.raises(RuntimeError, match="Unknown AI_PROVIDER"):
        run_evaluation("cv", "jd", _settings(provider="banana"))
