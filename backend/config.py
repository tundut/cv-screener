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
    openai_api_key: str
    openai_model: str
    openai_base_url: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        aws_region=os.getenv("AWS_REGION", "ap-southeast-1"),
        cv_bucket_name=os.getenv("CV_BUCKET_NAME", ""),
        cv_results_table=os.getenv("CV_RESULTS_TABLE", ""),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", ""),
        ai_provider=os.getenv("AI_PROVIDER", "bedrock"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        # An empty OPENAI_BASE_URL must be treated as "unset"; the SDK otherwise
        # uses the empty string as the base URL and every request fails with a
        # confusing "Connection error".
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
    )