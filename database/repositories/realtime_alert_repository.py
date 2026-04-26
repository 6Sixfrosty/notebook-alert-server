from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from database import connection
from database.collections import REALTIME_ALERTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    clean_document = dict(document)
    clean_document.pop("_id", None)
    return clean_document


class RealtimeAlertRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[REALTIME_ALERTS]

    async def create_alert(
        self,
        message_id: int | str,
        query: str,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document = {
            "alert_id": uuid4().hex,
            "message_id": message_id,
            "query": query,
            "text": text,
            "metadata": metadata or {},
            "created_at": _now(),
        }

        await self.collection.insert_one(document)
        return _without_mongo_id(document) or document

    async def get_by_message_id(self, message_id: int | str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"message_id": message_id})
        return _without_mongo_id(document)
