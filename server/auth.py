import hmac
from typing import Annotated

from fastapi import Header, Request

from config.settings import get_settings
from server.errors import APIError

AUTH_MISSING_CODE = "AUTH_MISSING"
AUTH_INVALID_CODE = "AUTH_INVALID"
AUTH_MISSING_MESSAGE = "Token ausente."
AUTH_INVALID_MESSAGE = "Token inválido."


async def require_api_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> bool:
    if not authorization:
        raise APIError(
            status_code=401,
            code=AUTH_MISSING_CODE,
            message=AUTH_MISSING_MESSAGE,
        )

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise APIError(
            status_code=403,
            code=AUTH_INVALID_CODE,
            message=AUTH_INVALID_MESSAGE,
        )

    expected_token = get_settings().api_token
    received_token = token.strip()
    if not hmac.compare_digest(received_token, expected_token):
        raise APIError(
            status_code=403,
            code=AUTH_INVALID_CODE,
            message=AUTH_INVALID_MESSAGE,
        )

    return True
