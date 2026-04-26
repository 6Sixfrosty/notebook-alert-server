import pytest
from pydantic import ValidationError

from server.schemas import SearchConfig


def valid_search_config_payload():
    return {
        "ativa": True,
        "version": 1,
        "MENSAGENS": [
            {"id": 1, "query": " notebook   gamer ", "ativa": True},
            {"id": 2, "query": "macbook usado", "ativa": False},
        ],
        "COLETA": {
            "RAM": {"enabled": True, "pattern": r"(\d+)\s*GB"},
            "SSD": {"enabled": True, "pattern": r"(\d+)\s*GB\s*SSD"},
            "preco": {"enabled": True, "pattern": r"R\$\s*[\d.]+,\d{2}"},
            "link": {"enabled": False, "pattern": r"https?://\S+"},
        },
        "LIMITES": {
            "max_mensagens_historico": 100,
            "max_tamanho_texto": 5000,
            "timeout_telegram_segundos": 30,
        },
    }


def test_search_config_accepts_valid_payload_and_normalizes_query_spaces():
    config = SearchConfig.model_validate(valid_search_config_payload())

    assert config.config_id
    assert config.MENSAGENS[0].query == "notebook gamer"


def test_search_config_rejects_duplicate_queries_after_normalization():
    payload = valid_search_config_payload()
    payload["MENSAGENS"][1]["query"] = "notebook gamer"

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_duplicate_message_ids():
    payload = valid_search_config_payload()
    payload["MENSAGENS"][1]["id"] = 1

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_invalid_regex():
    payload = valid_search_config_payload()
    payload["COLETA"]["RAM"]["pattern"] = "("

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_control_characters_in_query():
    payload = valid_search_config_payload()
    payload["MENSAGENS"][0]["query"] = "notebook\ngamer"

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_when_no_message_is_active():
    payload = valid_search_config_payload()
    for message in payload["MENSAGENS"]:
        message["ativa"] = False

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_when_no_collect_field_is_enabled():
    payload = valid_search_config_payload()
    for field in payload["COLETA"].values():
        field["enabled"] = False

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)


def test_search_config_rejects_unknown_collect_fields():
    payload = valid_search_config_payload()
    payload["COLETA"]["gpu"] = {"enabled": True, "pattern": r"RTX"}

    with pytest.raises(ValidationError):
        SearchConfig.model_validate(payload)
