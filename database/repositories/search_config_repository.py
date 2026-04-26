from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from database import connection
from database.collections import SEARCH_CONFIGS

DEFAULT_CONFIG_ID = "default"


class VersionConflictError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_document(config: Any) -> dict[str, Any]:
    if hasattr(config, "model_dump"):
        return config.model_dump(mode="python")
    return dict(config)


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    clean_document = dict(document)
    clean_document.pop("_id", None)
    return clean_document


class SearchConfigRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[SEARCH_CONFIGS]

    async def get_default_config(self) -> dict[str, Any] | None:
        document = await self.collection.find_one({"config_id": DEFAULT_CONFIG_ID})
        return _without_mongo_id(document)

    async def upsert_default_config(self, config: Any) -> dict[str, Any]:
        incoming_document = _to_document(config)
        incoming_version = incoming_document.get("version")
        timestamp = _now()

        existing_document = await self.collection.find_one(
            {"config_id": DEFAULT_CONFIG_ID}
        )

        if existing_document is None:
            document = {
                **incoming_document,
                "config_id": DEFAULT_CONFIG_ID,
                "version": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            await self.collection.update_one(
                {"config_id": DEFAULT_CONFIG_ID},
                {"$setOnInsert": document},
                upsert=True,
            )
            saved_document = await self.collection.find_one(
                {"config_id": DEFAULT_CONFIG_ID}
            )
            return _without_mongo_id(saved_document) or document

        current_version = existing_document.get("version")
        if incoming_version != current_version:
            raise VersionConflictError("Search config version conflict.")

        next_version = current_version + 1
        document = {
            **incoming_document,
            "config_id": DEFAULT_CONFIG_ID,
            "version": next_version,
            "created_at": existing_document.get("created_at", timestamp),
            "updated_at": timestamp,
        }

        saved_document = await self.collection.find_one_and_update(
            {"config_id": DEFAULT_CONFIG_ID, "version": current_version},
            {"$set": document},
            return_document=ReturnDocument.AFTER,
        )
        if saved_document is None:
            raise VersionConflictError("Search config version conflict.")

        return _without_mongo_id(saved_document) or document
