from codex_usage_pet.services.logger import redact


def test_credentials_are_redacted() -> None:
    text = (
        "Bearer secret123 access_token=abc refresh-token:xyz session_token qwerty "
        "Authorization:supersecret Cookie:sessionid=hidden session_credential=credential-secret"
    )
    redacted = redact(text)
    for secret in (
        "secret123",
        "abc",
        "xyz",
        "qwerty",
        "supersecret",
        "sessionid=hidden",
        "credential-secret",
    ):
        assert secret not in redacted
    assert redacted.count("[REDACTED]") == 7


def test_authorization_bearer_header_is_fully_redacted() -> None:
    redacted = redact("request failed: Authorization: Bearer header-secret")
    assert "header-secret" not in redacted
    assert "Bearer" not in redacted
    assert "Authorization: [REDACTED]" in redacted

