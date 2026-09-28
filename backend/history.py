from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

try:  # Package context (tests, dashboard)
    from .config import Settings
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from config import Settings

# GSI defined in template.yaml for per-user history queries.
USER_INDEX_NAME = "user-created-index"


def _to_dynamo_safe(value: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB.

    The boto3 DynamoDB resource rejects float ("Float types are not supported.
    Use Decimal types instead."). Serializing through str keeps the Decimal
    exact and free of binary float noise. bool is left untouched since it is a
    valid DynamoDB type and a subclass of int.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamo_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dynamo_safe(item) for item in value]
    return value


def get_user_id(user: Any) -> str:
    """Use Cognito's stable subject claim as the owner key."""
    return str(getattr(user, "sub", None) or getattr(user, "email", "unknown-user"))


def save_evaluation(settings: Settings, user_id: str, result: dict[str, Any]) -> dict[str, Any]:
    if not settings.cv_results_table:
        raise RuntimeError("CV_RESULTS_TABLE is not configured")

    item = {
        "job_id": str(uuid4()),
        "candidate_id": str(uuid4()),
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_id": str(uuid4()),
        "candidate_name": str(result.get("candidate_name", "Candidate")),
        "fit_score": result.get("fit_score", 0),
        "summary": str(result.get("summary", "")),
        "strengths": result.get("strengths", []),
        "gaps": result.get("gaps", []),
        "job_description": str(result.get("job_description", "")),
        "resume_s3_key": str(result.get("resume_s3_key", "")),
        "s3_evaluation_key": str(result.get("s3_evaluation_key", "")),
    }
    item = _to_dynamo_safe(item)
    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.cv_results_table)
    table.put_item(Item=item)
    return item


def delete_evaluation(settings: Settings, user_id: str, evaluation: dict[str, Any]) -> None:
    if not settings.cv_results_table:
        raise RuntimeError("CV_RESULTS_TABLE is not configured")

    job_id = evaluation.get("job_id")
    candidate_id = evaluation.get("candidate_id")
    if not job_id or not candidate_id:
        raise ValueError("This evaluation record is missing its DynamoDB key fields and cannot be deleted.")

    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.cv_results_table)
    table.delete_item(
        Key={"job_id": str(job_id), "candidate_id": str(candidate_id)},
        ConditionExpression="user_id = :user_id",
        ExpressionAttributeValues={":user_id": user_id},
    )


def list_evaluations(settings: Settings, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
    if not settings.cv_results_table:
        return []

    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.cv_results_table)

    try:
        items = _query_by_user(table, user_id, limit)
    except ClientError as error:
        # Older tables predate the GSI; fall back to a filtered scan.
        code = error.response.get("Error", {}).get("Code", "")
        if code not in {"ValidationException", "ResourceNotFoundException"}:
            raise
        items = _scan_by_user(table, user_id, limit)

    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]


def _query_by_user(table: Any, user_id: str, limit: int) -> list[dict[str, Any]]:
    """Query the per-user GSI, newest first."""
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": USER_INDEX_NAME,
        "KeyConditionExpression": Key("user_id").eq(user_id),
        "ScanIndexForward": False,
        "Limit": limit,
    }
    while len(items) < limit:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return items


def _scan_by_user(table: Any, user_id: str, limit: int) -> list[dict[str, Any]]:
    """Fallback for tables without the GSI: filtered scan on user_id."""
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": "user_id = :user_id",
        "ExpressionAttributeValues": {":user_id": user_id},
        "Limit": limit,
    }
    while len(items) < limit:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return items