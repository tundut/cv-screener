from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    aws_region: str
    cv_bucket_name: str
    cv_results_table: str
    bedrock_model_id: str
    ai_provider: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        aws_region=os.getenv("AWS_REGION", "ap-southeast-1"),
        cv_bucket_name=os.getenv("CV_BUCKET_NAME", ""),
        cv_results_table=os.getenv("CV_RESULTS_TABLE", ""),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", ""),
        ai_provider=os.getenv("AI_PROVIDER", "bedrock")
    )