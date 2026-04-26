from core.security import generate_request_id, mask_secret, sanitize_log_message


def test_generate_request_id_has_expected_prefix_and_is_unique():
    first = generate_request_id()
    second = generate_request_id()

    assert first.startswith("req_")
    assert second.startswith("req_")
    assert first != second


def test_mask_secret_never_exposes_secret_value():
    secret = "super-secret-token"

    masked = mask_secret(secret)

    assert masked
    assert secret not in masked


def test_sanitize_log_message_masks_known_secret_values(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "super-secret-token")
    monkeypatch.setenv("DATABASE_URL", "mongodb://user:pass@localhost:27017/db")

    sanitized = sanitize_log_message(
        "Authorization: Bearer super-secret-token "
        "DATABASE_URL=mongodb://user:pass@localhost:27017/db"
    )

    assert "super-secret-token" not in sanitized
    assert "mongodb://user:pass@localhost:27017/db" not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_log_message_masks_extra_secrets():
    sanitized = sanitize_log_message(
        "raw value is one-off-secret",
        extra_secrets=("one-off-secret",),
    )

    assert "one-off-secret" not in sanitized
