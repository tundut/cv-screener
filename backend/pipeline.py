"""Shared resume-evaluation pipeline used by the S3-triggered Lambda.

Flow: an object landing under ``users/<user_id>/resumes/`` triggers the Lambda,
which downloads the PDF, extracts text, evaluates it against the job description
carried in the object metadata, and stores the result in DynamoDB. The dashboard
reads that same table, so both entry points converge on one history store.
"""

from typing import Any

import boto3

try:  # Package context (tests, dashboard)
    from .config import Settings
    from .evaluator import run_evaluation
    from .history import save_evaluation
    from .pdf_extractor import extract_text_from_pdf
except ImportError:  # Flat context (Lambda: CodeUri backend/)
    from config import Settings
    from evaluator import run_evaluation
    from history import save_evaluation
    from pdf_extractor import extract_text_from_pdf

RESUME_PREFIX_MARKER = "/resumes/"


def is_resume_key(key: str) -> bool:
    """Only PDFs uploaded to a user's resumes/ folder should be evaluated.

    This also prevents an infinite loop: evaluation JSON is written back to the
    same bucket under evaluations/, which must not re-trigger the pipeline.
    """
    return RESUME_PREFIX_MARKER in key and key.lower().endswith(".pdf")


def _user_id_from_key(key: str) -> str:
    # Keys look like: users/<user_id>/resumes/<timestamp>-<file>.pdf
    parts = key.split("/")
    if len(parts) >= 3 and parts[0] == "users":
        return parts[1]
    return "unknown-user"


def _fetch_object(s3_client: Any, bucket: str, key: str) -> tuple[bytes, dict[str, str]]:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    metadata = response.get("Metadata", {}) or {}
    return body, metadata


def _resolve_job_description(s3_client: Any, bucket: str, metadata: dict[str, str]) -> str:
    """Load the job description for a resume.

    The current uploader stores the brief as a sibling text object and puts its
    key in the "job-description-key" metadata. Older resumes embedded a
    truncated brief directly in "job-description" metadata, which is used as a
    fallback for backward compatibility.
    """
    jd_key = (metadata.get("job-description-key") or "").strip()
    if jd_key:
        response = s3_client.get_object(Bucket=bucket, Key=jd_key)
        return response["Body"].read().decode("utf-8").strip()
    return (metadata.get("job-description") or "").strip()


def process_resume_object(
    settings: Settings,
    bucket: str,
    key: str,
    s3_client: Any = None,
) -> dict[str, Any] | None:
    """Evaluate a single uploaded resume and persist the result.

    Returns the saved DynamoDB item, or ``None`` if the object is not an
    evaluatable resume (e.g. an evaluation JSON) or has no job description.
    """
    if not is_resume_key(key):
        return None

    s3_client = s3_client or boto3.client("s3", region_name=settings.aws_region)
    content, metadata = _fetch_object(s3_client, bucket, key)

    job_description = _resolve_job_description(s3_client, bucket, metadata)
    if not job_description:
        # Uploaded before a brief was attached; the dashboard will evaluate it
        # interactively instead. Nothing to do server-side.
        return None

    user_id = metadata.get("user-id") or _user_id_from_key(key)
    cv_text = extract_text_from_pdf(content)

    result = run_evaluation(cv_text, job_description, settings)
    result["job_description"] = job_description
    result["resume_s3_key"] = key

    return save_evaluation(settings, user_id, result)
