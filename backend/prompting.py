from pathlib import Path


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "cv_evaluation.txt"


def build_evaluation_prompt(cv_text: str, job_description: str) -> str:
    if not cv_text.strip():
        raise ValueError("CV text is required")
    if not job_description.strip():
        raise ValueError("Job description is required")

    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(cv_text=cv_text.strip(), job_description=job_description.strip())