import random
import string
from typing import Any


def generate_random_string(length: int) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def evaluate_cv_mock(cv_text: str, job_description: str) -> dict[str, Any]:
    if not cv_text.strip():
        raise ValueError("CV text is empty")

    if not job_description.strip():
        raise ValueError("Job description is empty")

    return {
        "job_id": f"job-demo-{generate_random_string(6)}",
        "candidate_id": f"candidate-demo-{generate_random_string(6)}",
        "candidate_name": "Nguyễn Phan Tuấn Đức",
        "created_at": "2026-09-21T15:20:00Z",
        "evaluation_id": f"demo-evaluation-{generate_random_string(6)}",
        "fit_score": 95,
        "gaps": [
            "Terraform",
            "Kubernetes"
        ],
        "job_description": "Backend Cloud Engineer: Python, AWS Lambda, DynamoDB, Docker and infrastructure as code.",
        "recommendation": "CONSIDER",
        "status": "COMPLETED",
        "strengths": [
            "Python",
            "AWS Lambda",
            "DynamoDB",
            "Docker"
        ],
        "summary": "Ứng viên có nền tảng Python và AWS tốt, phù hợp với vai trò Backend Cloud Engineer.",
        "user_id": "494ab54c-30a1-709a-d584-b3263c47d96a"
    }