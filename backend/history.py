from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import boto3

from .config import Settings


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
    }
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
    items: list[dict[str, Any]] = []
    scan_kwargs = {
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

    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]