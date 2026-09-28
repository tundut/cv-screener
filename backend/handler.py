import json
import logging
from urllib.parse import unquote_plus

try:  # Package context (tests, dashboard: "backend.handler")
    from .config import load_settings
    from .pipeline import process_resume_object
except ImportError:  # Flat context (Lambda: CodeUri backend/, module "handler")
    from config import load_settings
    from pipeline import process_resume_object

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """S3 ObjectCreated trigger: evaluate an uploaded resume end to end.

    For each new object it downloads the PDF, extracts text, runs the Bedrock
    evaluation using the job description stored in the object metadata, and
    saves the result to DynamoDB. Objects that are not evaluatable resumes are
    skipped so the pipeline never re-triggers on its own output.
    """
    settings = load_settings()
    processed = []
    skipped = []

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        try:
            item = process_resume_object(settings, bucket, key)
        except Exception:  # noqa: BLE001 - log and continue with other records
            logger.exception("Failed to process s3://%s/%s", bucket, key)
            skipped.append({"key": key, "status": "error"})
            continue

        if item is None:
            skipped.append({"key": key, "status": "skipped"})
        else:
            processed.append(
                {
                    "key": key,
                    "evaluation_id": item.get("evaluation_id"),
                    "user_id": item.get("user_id"),
                }
            )

    return {
        "statusCode": 200,
        "body": json.dumps({"processed": processed, "skipped": skipped}),
    }
