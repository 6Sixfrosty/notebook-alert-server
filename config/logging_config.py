import logging
import logging.config
import os
import re
from typing import Any


DEFAULT_LOG_LEVEL = "INFO"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

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


def _coerce_log_level(log_level: str | None) -> str:
    normalized = (log_level or os.getenv("LOG_LEVEL") or DEFAULT_LOG_LEVEL).strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        return DEFAULT_LOG_LEVEL
    return normalized


def redact_sensitive_data(value: Any) -> str:
    """Return a string with known credentials and connection strings redacted."""

    text = str(value)

    for key in SENSITIVE_ENV_KEYS:
        secret = os.getenv(key)
        if secret:
            replacement = f"[REDACTED_{key}]"
            text = text.replace(secret, replacement)

    text = _SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    text = _AUTHORIZATION_PATTERN.sub(
        lambda match: f"{match.group(1)}: [REDACTED]",
        text,
    )
    return _DATABASE_URL_PATTERN.sub("[REDACTED_DATABASE_URL]", text)


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive_data(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_data(super().format(record))


def setup_logging(log_level: str | None = None) -> None:
    level = _coerce_log_level(log_level)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "sensitive_data": {
                    "()": "config.logging_config.SensitiveDataFilter",
                },
            },
            "formatters": {
                "default": {
                    "()": "config.logging_config.RedactingFormatter",
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "default",
                    "filters": ["sensitive_data"],
                },
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
        }
    )


configure_logging = setup_logging
