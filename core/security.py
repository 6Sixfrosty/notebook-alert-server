import os
import re
from uuid import uuid4


SECRET_MASK = "[REDACTED]"
REQUEST_ID_PREFIX = "req_"

SENSITIVE_ENV_KEYS = (
    "API_TOKEN",
    "DATABASE_URL",
    "BREVO_API_KEY",
    "TELEGRAM_API_HASH",
)

_DATABASE_URL_PATTERN = re.compile(
    r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql(?:\+\w+)?|mariadb|redis)://[^\s\"'<>]+",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"\b(API_TOKEN|DATABASE_URL|BREVO_API_KEY|TELEGRAM_API_HASH)\b\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_AUTHORIZATION_PATTERN = re.compile(
    r"\b(Authorization)\b\s*[:=]\s*(Bearer\s+)?[^\s,;]+",
    re.IGNORECASE,
)


def generate_request_id() -> str:
    return f"{REQUEST_ID_PREFIX}{uuid4().hex}"


def mask_secret(secret: str | None) -> str:
    if not secret:
        return SECRET_MASK
    return SECRET_MASK


def sanitize_log_message(message: object, extra_secrets: list[str] | tuple[str, ...] = ()) -> str:
    sanitized = str(message)

    for key in SENSITIVE_ENV_KEYS:
        secret = os.getenv(key)
        if secret:
            sanitized = sanitized.replace(secret, mask_secret(secret))

    for secret in extra_secrets:
        if secret:
            sanitized = sanitized.replace(secret, mask_secret(secret))

    sanitized = _SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}={SECRET_MASK}",
        sanitized,
    )
    sanitized = _AUTHORIZATION_PATTERN.sub(
        lambda match: f"{match.group(1)}: {SECRET_MASK}",
        sanitized,
    )
    return _DATABASE_URL_PATTERN.sub(SECRET_MASK, sanitized)
