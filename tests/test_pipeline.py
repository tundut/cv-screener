from io import BytesIO
from unittest.mock import MagicMock, patch

from backend.config import Settings
from backend.pipeline import is_resume_key, process_resume_object


def _settings() -> Settings:
    return Settings(
        aws_region="ap-southeast-1",
        cv_bucket_name="test-bucket",
        cv_results_table="cv-evaluations",
        bedrock_model_id="apac.amazon.nova-lite-v1:0",
        ai_provider="bedrock",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        openai_base_url="",
    )


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


def _fake_s3(body: bytes, metadata: dict) -> MagicMock:
    client = MagicMock()
    client.get_object.return_value = {"Body": _FakeBody(body), "Metadata": metadata}
    return client


def test_is_resume_key_matches_only_resume_pdfs():
    assert is_resume_key("users/u1/resumes/2026-cv.pdf")
    assert not is_resume_key("users/u1/evaluations/2026.json")
    assert not is_resume_key("users/u1/resumes/notes.txt")


def test_process_skips_non_resume_objects():
    s3 = _fake_s3(b"", {})
    result = process_resume_object(_settings(), "test-bucket", "users/u1/evaluations/x.json", s3)
    assert result is None
    s3.get_object.assert_not_called()


def test_process_skips_when_no_job_description():
    s3 = _fake_s3(b"%PDF-1.4", {"user-id": "u1"})
    result = process_resume_object(_settings(), "test-bucket", "users/u1/resumes/cv.pdf", s3)
    assert result is None


@patch("backend.pipeline.save_evaluation")
@patch("backend.pipeline.run_evaluation")
@patch("backend.pipeline.extract_text_from_pdf")
def test_process_evaluates_and_saves(mock_extract, mock_evaluate, mock_save):
    mock_extract.return_value = "Jane Doe, Python developer"
    mock_evaluate.return_value = {
        "candidate_name": "Jane Doe",
        "fit_score": 88,
        "summary": "Strong fit",
        "strengths": ["Python"],
        "gaps": [],
    }
    mock_save.side_effect = lambda settings, user_id, result: {
        "evaluation_id": "eval-1",
        "user_id": user_id,
        **result,
    }

    s3 = _fake_s3(b"%PDF-1.4 bytes", {"user-id": "u1", "job-description": "Need Python"})
    item = process_resume_object(_settings(), "test-bucket", "users/u1/resumes/cv.pdf", s3)

    assert item is not None
    assert item["user_id"] == "u1"
    assert item["resume_s3_key"] == "users/u1/resumes/cv.pdf"
    assert item["job_description"] == "Need Python"
    mock_evaluate.assert_called_once()
    mock_save.assert_called_once()


@patch("backend.pipeline.save_evaluation")
@patch("backend.pipeline.run_evaluation")
@patch("backend.pipeline.extract_text_from_pdf")
def test_process_falls_back_to_user_id_from_key(mock_extract, mock_evaluate, mock_save):
    mock_extract.return_value = "text"
    mock_evaluate.return_value = {
        "candidate_name": "X",
        "fit_score": 50,
        "summary": "",
        "strengths": [],
        "gaps": [],
    }
    mock_save.side_effect = lambda settings, user_id, result: {"user_id": user_id, **result}

    # No user-id in metadata: derive it from the key path.
    s3 = _fake_s3(b"pdf", {"job-description": "Need Python"})
    item = process_resume_object(_settings(), "test-bucket", "users/derived-user/resumes/cv.pdf", s3)

    assert item["user_id"] == "derived-user"


@patch("backend.pipeline.save_evaluation")
@patch("backend.pipeline.run_evaluation")
@patch("backend.pipeline.extract_text_from_pdf")
def test_process_reads_job_description_from_sibling_object(mock_extract, mock_evaluate, mock_save):
    mock_extract.return_value = "Jane Doe, Python developer"
    mock_evaluate.return_value = {
        "candidate_name": "Jane Doe",
        "fit_score": 80,
        "summary": "ok",
        "strengths": [],
        "gaps": [],
    }
    mock_save.side_effect = lambda settings, user_id, result: {"user_id": user_id, **result}

    resume_key = "users/u1/resumes/cv.pdf"
    jd_key = resume_key + ".jobdescription.txt"
    multiline_jd = "DATA ANALYST\n\nRESPONSIBILITIES\n- Write SQL queries.\n- Build dashboards."

    def get_object(Bucket, Key):  # noqa: N803 - boto3 kwarg names
        if Key == resume_key:
            return {"Body": _FakeBody(b"%PDF-1.4"), "Metadata": {"user-id": "u1", "job-description-key": jd_key}}
        if Key == jd_key:
            return {"Body": _FakeBody(multiline_jd.encode("utf-8")), "Metadata": {}}
        raise AssertionError(f"unexpected key {Key}")

    s3 = MagicMock()
    s3.get_object.side_effect = get_object

    item = process_resume_object(_settings(), "test-bucket", resume_key, s3)

    assert item is not None
    # The full multi-line brief is recovered from the sibling object.
    assert item["job_description"] == multiline_jd
    mock_evaluate.assert_called_once()
    args = mock_evaluate.call_args.args
    assert args[1] == multiline_jd
