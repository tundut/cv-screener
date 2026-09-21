from types import SimpleNamespace

from backend.history import get_user_id


def test_get_user_id_prefers_cognito_subject():
    assert get_user_id(SimpleNamespace(sub="cognito-sub", email="user@example.com")) == "cognito-sub"


def test_get_user_id_falls_back_to_email_for_local_user():
    assert get_user_id(SimpleNamespace(email="user@example.com")) == "user@example.com"