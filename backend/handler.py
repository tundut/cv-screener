import json
import os
from urllib.parse import unquote_plus

import boto3


def lambda_handler(event, context):
    textract = boto3.client("textract")
    started_jobs = []

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        response = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
            JobTag=key,
        )
        started_jobs.append({"bucket": bucket, "key": key, "job_id": response["JobId"]})

    return {
        "statusCode": 202,
        "body": json.dumps(
            {"started_jobs": started_jobs, "results_table": os.getenv("RESULTS_TABLE", "")}
        ),
    }