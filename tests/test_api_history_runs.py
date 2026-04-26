import pytest
from pydantic import ValidationError

from server.schemas import ErrorResponse, HistoryRunRequest


def test_history_run_request_accepts_valid_date_limit():
    request = HistoryRunRequest.model_validate({"date_limit": "29/02"})

    assert request.date_limit == "29/02"


@pytest.mark.parametrize("date_limit", ["2026-01-01", "31/04", "00/01", "15/13"])
def test_history_run_request_rejects_invalid_date_limit(date_limit):
    with pytest.raises(ValidationError):
        HistoryRunRequest.model_validate({"date_limit": date_limit})


def test_error_response_contains_expected_error_shape():
    response = ErrorResponse.model_validate(
        {
            "error": {
                "code": "invalid_request",
                "message": "Invalid request.",
                "field": "date_limit",
                "request_id": "req-123",
            }
        }
    )

    assert response.error.code == "invalid_request"
    assert response.error.field == "date_limit"
