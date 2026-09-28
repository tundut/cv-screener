import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

try:  # Package context (tests, dashboard)
    from .config import Settings
    from .prompting import build_evaluation_prompt
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from config import Settings
    from prompting import build_evaluation_prompt


def evaluate_cv(cv_text: str, job_description: str, settings: Settings) -> dict[str, Any]:
    if not settings.bedrock_model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not configured")

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    try:
        response = client.converse(
            modelId=settings.bedrock_model_id,
            messages=[{"role": "user", "content": [{"text": build_evaluation_prompt(cv_text, job_description)}]}],
            inferenceConfig={"temperature": 0.1, "maxTokens": 800},
        )
    except ClientError as error:
        error_message = error.response.get("Error", {}).get("Message", str(error))
        if "currently being verified" in error_message:
            raise RuntimeError(
                "AWS account verification is still in progress. Bedrock access will be available "
                "after AWS completes verification, normally within two hours."
            ) from error
        if "Too many tokens per day" in error_message:
            raise RuntimeError(
                "Bedrock daily token quota has been reached. Wait for the quota to reset, "
                "or request a quota increase in AWS Service Quotas."
            ) from error
        raise RuntimeError(f"Bedrock request was denied: {error_message}") from error
    output_text = response["output"]["message"]["content"][0]["text"]
    return _parse_evaluation(output_text)


def _parse_evaluation(output_text: str) -> dict[str, Any]:
    result = _load_json_object(output_text)

    required_keys = {"candidate_name", "fit_score", "summary", "strengths", "gaps"}
    missing_keys = required_keys - result.keys()
    if missing_keys:
        raise ValueError(f"Bedrock response is missing: {', '.join(sorted(missing_keys))}")

    result["fit_score"] = _coerce_fit_score(result["fit_score"])
    return result


def _load_json_object(output_text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating markdown fences or surrounding prose."""
    text = (output_text or "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Models often wrap JSON in ```json fences or add a sentence around it.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Bedrock returned invalid JSON")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("Bedrock returned invalid JSON") from error

    if not isinstance(parsed, dict):
        raise ValueError("Bedrock returned invalid JSON")
    return parsed


def _coerce_fit_score(value: Any) -> float:
    """Bedrock sometimes returns the score as a string; normalize to a number."""
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Bedrock returned a non-numeric fit_score") from error