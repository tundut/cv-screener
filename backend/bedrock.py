import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .config import Settings
from .prompting import build_evaluation_prompt


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
    try:
        result = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise ValueError("Bedrock returned invalid JSON") from error

    required_keys = {"candidate_name", "fit_score", "summary", "strengths", "gaps"}
    missing_keys = required_keys - result.keys()
    if missing_keys:
        raise ValueError(f"Bedrock response is missing: {', '.join(sorted(missing_keys))}")
    return result