from datetime import datetime, timezone
from typing import Any

from database import connection
from database.collections import PROCESSED_MESSAGES


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessedMessageRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[PROCESSED_MESSAGES]

    async def exists(self, message_id: int | str, query: str) -> bool:
        document = await self.collection.find_one(
            {"message_id": message_id, "query": query},
            {"_id": 1},
        )
        return document is not None

    async def mark_processed(self, message_id: int | str, query: str) -> bool:
        result = await self.collection.update_one(
            {"message_id": message_id, "query": query},
            {
                "$setOnInsert": {
                    "message_id": message_id,
                    "query": query,
                    "created_at": _now(),
                }
            },
            upsert=True,
        )
        return bool(
            getattr(result, "upserted_id", None) is not None
            or getattr(result, "matched_count", 0)
        )
