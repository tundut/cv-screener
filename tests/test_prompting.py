from backend.prompting import build_evaluation_prompt


def test_build_evaluation_prompt_includes_inputs():
    prompt = build_evaluation_prompt("Jane Doe, Python developer", "Need Python experience")

    assert "Jane Doe" in prompt
    assert "Need Python experience" in prompt
    assert "valid JSON" in prompt


def test_build_evaluation_prompt_requires_inputs():
    try:
        build_evaluation_prompt("", "A role")
    except ValueError as error:
        assert str(error) == "CV text is required"
    else:
        raise AssertionError("Expected empty CV text to be rejected")