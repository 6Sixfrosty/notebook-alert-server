from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ASCENDING, ReturnDocument

from core.security import sanitize_log_message
from database import connection
from database.collections import OUTBOX_EMAILS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    clean_document = dict(document)
    clean_document.pop("_id", None)
    return clean_document


class OutboxEmailRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[OUTBOX_EMAILS]

    async def create_email_task(
        self,
        to_email: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        next_attempt_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        document = {
            "email_id": uuid4().hex,
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "metadata": metadata or {},
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "next_attempt_at": next_attempt_at or timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        await self.collection.insert_one(document)
        return _without_mongo_id(document) or document

    async def list_pending(
        self,
        limit: int = 10,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        timestamp = now or _now()
        cursor = (
            self.collection.find(
                {"status": "pending", "next_attempt_at": {"$lte": timestamp}}
            )
            .sort([("next_attempt_at", ASCENDING), ("created_at", ASCENDING)])
            .limit(safe_limit)
        )
        documents = await cursor.to_list(length=safe_limit)
        return [_without_mongo_id(document) or document for document in documents]

    async def mark_processing(self, email_id: str) -> dict[str, Any] | None:
        timestamp = _now()
        document = await self.collection.find_one_and_update(
            {"email_id": email_id},
            {
                "$set": {
                    "status": "processing",
                    "processing_at": timestamp,
                    "updated_at": timestamp,
                },
                "$inc": {"attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return _without_mongo_id(document)

    async def mark_sent(self, email_id: str) -> dict[str, Any] | None:
        timestamp = _now()
        document = await self.collection.find_one_and_update(
            {"email_id": email_id},
            {
                "$set": {
                    "status": "sent",
                    "sent_at": timestamp,
                    "updated_at": timestamp,
                    "last_error": None,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return _without_mongo_id(document)

    async def mark_failed(
        self,
        email_id: str,
        last_error: str,
        next_attempt_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        timestamp = _now()
        update_fields = {
            "status": "failed",
            "last_error": sanitize_log_message(last_error),
            "updated_at": timestamp,
        }
        if next_attempt_at is not None:
            update_fields["next_attempt_at"] = next_attempt_at

        document = await self.collection.find_one_and_update(
            {"email_id": email_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )
        return _without_mongo_id(document)
