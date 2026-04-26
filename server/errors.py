import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.security import generate_request_id, sanitize_log_message

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        field: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    request_id = request.headers.get(REQUEST_ID_HEADER) or generate_request_id()
    request.state.request_id = request_id
    return request_id


def build_error_payload(
    *,
    code: str,
    message: str,
    field: str | None,
    request_id: str,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "request_id": request_id,
        }
    }


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request: Request,
    field: str | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            code=code,
            message=message,
            field=field,
            request_id=request_id,
        ),
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        field=exc.field,
        request=request,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Erro HTTP."
    return error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=detail,
        field=None,
        request=request,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
    message = str(first_error.get("msg") or "Dados inválidos.")

    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message=message,
        field=field or None,
        request=request,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.exception(
        "Unhandled request error request_id=%s error=%s",
        request_id,
        sanitize_log_message(exc),
    )

    message = "Erro interno."
    if os.getenv("APP_ENV", "development").lower() != "production":
        detail = sanitize_log_message(exc)
        if detail:
            message = detail

    return JSONResponse(
        status_code=500,
        content=build_error_payload(
            code="INTERNAL_ERROR",
            message=message,
            field=None,
            request_id=request_id,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
