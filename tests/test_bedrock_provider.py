import json

import pytest

from backend.bedrock import _parse_evaluation, evaluate_cv
from backend.config import Settings


def _settings(model_id: str = "apac.amazon.nova-lite-v1:0") -> Settings:
    return Settings(
        aws_region="ap-southeast-1",
        cv_bucket_name="test-bucket",
        cv_results_table="cv-evaluations",
        bedrock_model_id=model_id,
        ai_provider="bedrock",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        openai_base_url="",
    )


def _valid_payload() -> dict:
    return {
        "candidate_name": "Jane Doe",
        "fit_score": 82,
        "summary": "Strong Python and AWS background.",
        "strengths": ["Python", "AWS Lambda"],
        "gaps": ["Kubernetes"],
    }


def test_parse_evaluation_accepts_valid_payload():
    result = _parse_evaluation(json.dumps(_valid_payload()))
    assert result["candidate_name"] == "Jane Doe"
    assert result["fit_score"] == 82


def test_parse_evaluation_tolerates_markdown_fences():
    fenced = "```json\n" + json.dumps(_valid_payload()) + "\n```"
    assert _parse_evaluation(fenced)["candidate_name"] == "Jane Doe"


def test_parse_evaluation_coerces_string_score():
    payload = _valid_payload()
    payload["fit_score"] = "77"
    assert _parse_evaluation(json.dumps(payload))["fit_score"] == 77.0


def test_parse_evaluation_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_evaluation("not json at all")


def test_parse_evaluation_reports_missing_keys():
    with pytest.raises(ValueError, match="missing"):
        _parse_evaluation(json.dumps({"candidate_name": "Jane"}))


def test_evaluate_cv_requires_model_id():
    with pytest.raises(RuntimeError, match="BEDROCK_MODEL_ID"):
        evaluate_cv("cv text", "job description", _settings(model_id=""))
