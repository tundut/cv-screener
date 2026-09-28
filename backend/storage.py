import json
import json
import re
from datetime import datetime, timezone
from typing import Any

import boto3

try:  # Package context (tests, dashboard)
    from .config import Settings
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from config import Settings


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned or "unknown"


def _ascii_metadata(value: str) -> str:
    """Make a string safe for an S3 user-metadata header value.

    S3 metadata must be US-ASCII, and HTTP header values cannot contain control
    characters such as newlines or tabs. Non-ASCII is dropped and any control
    character (including CR/LF) is collapsed to a single space.
    """
    ascii_only = value.encode("ascii", "ignore").decode("ascii")
    # Replace any C0 control char (0x00-0x1F) and DEL (0x7F) with a space.
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", ascii_only)
    return re.sub(r"\s+", " ", cleaned).strip()


def upload_resume(
    settings: Settings,
    user_id: str,
    file_name: str,
    content: bytes,
    job_description: str = "",
) -> str:
    if not settings.cv_bucket_name:
        raise RuntimeError("CV_BUCKET_NAME is not configured")

    s3 = boto3.client("s3", region_name=settings.aws_region)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"users/{_safe_component(user_id)}/resumes/{timestamp}-{_safe_component(file_name)}"
    metadata = {"user-id": user_id, "original-file-name": _ascii_metadata(file_name)}

    # The job description can be long and multi-line, which is not valid in an
    # S3 metadata header. Store it as a sibling object and keep only a short
    # ASCII reference in the metadata so the S3-triggered Lambda can find it.
    brief = job_description.strip()
    if brief:
        jd_key = f"{key}.jobdescription.txt"
        s3.put_object(
            Bucket=settings.cv_bucket_name,
            Key=jd_key,
            Body=brief.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
            Metadata={"user-id": _ascii_metadata(user_id)},
        )
        metadata["job-description-key"] = jd_key

    s3.put_object(
        Bucket=settings.cv_bucket_name,
        Key=key,
        Body=content,
        ContentType="application/pdf",
        Metadata=metadata,
    )
    return key


def read_text_object(settings: Settings, key: str, s3_client: Any = None) -> str:
    """Read a UTF-8 text object (e.g. a stored job description) from S3."""
    if not settings.cv_bucket_name:
        raise RuntimeError("CV_BUCKET_NAME is not configured")
    s3_client = s3_client or boto3.client("s3", region_name=settings.aws_region)
    response = s3_client.get_object(Bucket=settings.cv_bucket_name, Key=key)
    return response["Body"].read().decode("utf-8")


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


def create_presigned_download_url(
    settings: Settings,
    user_id: str,
    object_key: str,
    expires_in: int = 300,
) -> str:
    if not settings.cv_bucket_name:
        raise RuntimeError("CV_BUCKET_NAME is not configured")

    user_prefix = f"users/{_safe_component(user_id)}/"
    if not object_key.startswith(user_prefix):
        raise PermissionError("This object does not belong to the signed-in user")

    return boto3.client("s3", region_name=settings.aws_region).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.cv_bucket_name, "Key": object_key},
        ExpiresIn=expires_in,
    )
