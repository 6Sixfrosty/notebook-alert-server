import calendar
import re
import unicodedata
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DATE_LIMIT_PATTERN = re.compile(r"^\d{2}/\d{2}$")


class APIBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _has_control_character(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


class SearchMessage(APIBaseModel):
    id: int = Field(ge=1)
    query: str = Field(min_length=2, max_length=200)
    ativa: bool

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if _has_control_character(value):
            raise ValueError("query cannot contain control characters.")
        return re.sub(r" {2,}", " ", value.strip())


class CollectField(APIBaseModel):
    enabled: bool
    pattern: str = Field(min_length=1, max_length=300)

    @field_validator("pattern", mode="before")
    @classmethod
    def trim_pattern(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("pattern")
    @classmethod
    def pattern_must_compile(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"pattern must be a valid regex: {exc}") from exc
        return value


class Limits(APIBaseModel):
    max_mensagens_historico: int = Field(default=1000, ge=1, le=5000)
    max_tamanho_texto: int = Field(default=5000, ge=100, le=20000)
    timeout_telegram_segundos: int = Field(default=30, ge=5, le=120)


class CollectConfig(APIBaseModel):
    RAM: CollectField
    SSD: CollectField
    preco: CollectField
    link: CollectField

    @model_validator(mode="after")
    def at_least_one_field_enabled(self):
        if not any(
            field.enabled
            for field in (
                self.RAM,
                self.SSD,
                self.preco,
                self.link,
            )
        ):
            raise ValueError("at least one collection field must be enabled.")
        return self


class SearchConfig(APIBaseModel):
    config_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    ativa: bool = True
    version: int = Field(default=1, ge=1)
    MENSAGENS: list[SearchMessage] = Field(min_length=1)
    COLETA: CollectConfig
    LIMITES: Limits = Field(default_factory=Limits)

    @field_validator("config_id", mode="before")
    @classmethod
    def trim_config_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_messages(self):
        ids = [message.id for message in self.MENSAGENS]
        if len(ids) != len(set(ids)):
            raise ValueError("message ids cannot repeat.")

        normalized_queries = [message.query.casefold() for message in self.MENSAGENS]
        if len(normalized_queries) != len(set(normalized_queries)):
            raise ValueError("message queries cannot repeat.")

        if not any(message.ativa for message in self.MENSAGENS):
            raise ValueError("at least one message must be active.")

        return self


class HistoryRunRequest(APIBaseModel):
    date_limit: str

    @field_validator("date_limit")
    @classmethod
    def validate_date_limit(cls, value: str) -> str:
        if not DATE_LIMIT_PATTERN.fullmatch(value):
            raise ValueError("date_limit must use DD/MM format.")

        day_text, month_text = value.split("/")
        day = int(day_text)
        month = int(month_text)

        if month < 1 or month > 12:
            raise ValueError("date_limit month must be between 01 and 12.")

        last_day = calendar.monthrange(2024, month)[1]
        if day < 1 or day > last_day:
            raise ValueError("date_limit day is invalid for the given month.")

        return value


class ErrorDetail(APIBaseModel):
    code: str
    message: str
    field: str | None = None
    request_id: str | None = None


class ErrorResponse(APIBaseModel):
    error: ErrorDetail
