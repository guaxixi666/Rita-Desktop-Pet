from codex_usage_pet.services.logger import redact


def test_credentials_are_redacted() -> None:
    text = "Bearer secret123 access_token=abc refresh-token:xyz session_token qwerty"
    redacted = redact(text)
    for secret in ("secret123", "abc", "xyz", "qwerty"):
        assert secret not in redacted
    assert redacted.count("[REDACTED]") == 4

