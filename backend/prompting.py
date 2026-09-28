from pathlib import Path

_HERE = Path(__file__).resolve().parent

# The prompt template ships inside the backend package (backend/prompts/) so it
# is available both locally and in the Lambda artifact (CodeUri: backend/). The
# project-root location is kept as a fallback for older layouts.
_PROMPT_CANDIDATES = (
    _HERE / "prompts" / "cv_evaluation.txt",
    _HERE.parent / "prompts" / "cv_evaluation.txt",
)


def _prompt_path() -> Path:
    for candidate in _PROMPT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "cv_evaluation.txt not found in any of: "
        + ", ".join(str(candidate) for candidate in _PROMPT_CANDIDATES)
    )


def build_evaluation_prompt(cv_text: str, job_description: str) -> str:
    if not cv_text.strip():
        raise ValueError("CV text is required")
    if not job_description.strip():
        raise ValueError("Job description is required")

    template = _prompt_path().read_text(encoding="utf-8")
    return template.format(cv_text=cv_text.strip(), job_description=job_description.strip())
