import json
import re
from datetime import datetime, timezone
from typing import Any

import boto3

from .config import Settings


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned or "unknown"


def upload_resume(settings: Settings, user_id: str, file_name: str, content: bytes) -> str:
    if not settings.cv_bucket_name:
        raise RuntimeError("CV_BUCKET_NAME is not configured")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"users/{_safe_component(user_id)}/resumes/{timestamp}-{_safe_component(file_name)}"
    boto3.client("s3", region_name=settings.aws_region).put_object(
        Bucket=settings.cv_bucket_name,
        Key=key,
        Body=content,
        ContentType="application/pdf",
        Metadata={"user-id": user_id, "original-file-name": file_name},
    )
    return key


def upload_evaluation_context(
    settings: Settings,
    user_id: str,
    resume_key: str,
    job_description: str,
    result: dict[str, Any],
) -> str:
    if not settings.cv_bucket_name:
        raise RuntimeError("CV_BUCKET_NAME is not configured")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"users/{_safe_component(user_id)}/evaluations/{timestamp}.json"
    payload = {
        "user_id": user_id,
        "resume_key": resume_key,
        "job_description": job_description,
        "evaluation": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    boto3.client("s3", region_name=settings.aws_region).put_object(
        Bucket=settings.cv_bucket_name,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
        ContentType="application/json",
        Metadata={"user-id": user_id, "resume-key": resume_key},
    )
    return key
