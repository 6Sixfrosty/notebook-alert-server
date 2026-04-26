from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.security import sanitize_log_message
from database import connection
from database.collections import AUDIT_LOGS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    clean_document = dict(document)
    clean_document.pop("_id", None)
    return clean_document


class AuditLogRepository:
    def __init__(self, database: Any | None = None) -> None:
        self.database = database or connection.get_database()
        self.collection = self.database[AUDIT_LOGS]

    async def create_log(
        self,
        event: str,
        level: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document = {
            "log_id": uuid4().hex,
            "event": event,
            "level": level.upper(),
            "message": sanitize_log_message(message),
            "metadata": metadata or {},
            "created_at": _now(),
        }

        await self.collection.insert_one(document)
        return _without_mongo_id(document) or document
