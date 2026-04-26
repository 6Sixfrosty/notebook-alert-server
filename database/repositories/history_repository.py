from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ASCENDING, ReturnDocument

from database import connection
from database.collections import HISTORY_RUNS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    clean_document = dict(document)
    clean_document.pop("_id", None)
    return clean_document


class HistoryRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[HISTORY_RUNS]

    async def create_history_run(self, date_limit: str) -> dict[str, Any]:
        timestamp = _now()
        document = {
            "run_id": uuid4().hex,
            "date_limit": date_limit,
            "status": "queued",
            "last_error": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        await self.collection.insert_one(document)
        return _without_mongo_id(document) or document

    async def get_history_run(self, run_id: str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"run_id": run_id})
        return _without_mongo_id(document)

    async def update_history_status(
        self,
        run_id: str,
        status: str,
        last_error: str | None = None,
    ) -> dict[str, Any] | None:
        timestamp = _now()
        update_fields: dict[str, Any] = {
            "status": status,
            "last_error": last_error,
            "updated_at": timestamp,
        }

        if status == "processing":
            update_fields["started_at"] = timestamp
        if status in {"completed", "failed", "cancelled"}:
            update_fields["completed_at"] = timestamp

        document = await self.collection.find_one_and_update(
            {"run_id": run_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )
        return _without_mongo_id(document)

    async def list_queued_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        cursor = (
            self.collection.find({"status": "queued"})
            .sort("created_at", ASCENDING)
            .limit(safe_limit)
        )
        documents = await cursor.to_list(length=safe_limit)
        return [_without_mongo_id(document) or document for document in documents]
