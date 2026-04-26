import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from config.settings import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client

    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.database_url)

    return _client


def get_database() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.database_name]


async def ping_database() -> bool:
    try:
        result = await get_database().command("ping")
    except PyMongoError as exc:
        logger.warning("MongoDB ping failed: %s", exc)
        return False

    return result.get("ok") == 1


def close_database_connection() -> None:
    global _client

    if _client is not None:
        _client.close()
        _client = None
