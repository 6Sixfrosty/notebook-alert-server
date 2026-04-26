import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from database.collections import REQUIRED_COLLECTIONS
from database.connection import ping_database
from database.init_db import INDEX_DEFINITIONS, init_db
from database.repositories.audit_log_repository import AuditLogRepository
from database.repositories.history_repository import HistoryRepository
from database.repositories.outbox_email_repository import OutboxEmailRepository
from database.repositories.processed_message_repository import ProcessedMessageRepository
from database.repositories.realtime_alert_repository import RealtimeAlertRepository
from database.repositories.search_config_repository import (
    SearchConfigRepository,
    VersionConflictError,
)


class FakeCursor:
    def __init__(self, documents):
        self.documents = [dict(document) for document in documents]
        self.limit_value = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list):
            sort_fields = key_or_list
        else:
            sort_fields = [(key_or_list, direction)]

        for key, sort_direction in reversed(sort_fields):
            self.documents.sort(
                key=lambda document: document.get(key),
                reverse=sort_direction == -1,
            )
        return self

    def limit(self, limit):
        self.limit_value = limit
        return self

    async def to_list(self, length=None):
        limit = self.limit_value or length or len(self.documents)
        return [dict(document) for document in self.documents[:limit]]


class FakeCollection:
    def __init__(self) -> None:
        self.created_indexes = []
        self.documents = []
        self.next_id = 1

    async def create_index(self, **kwargs):
        self.created_indexes.append(kwargs)
        return kwargs["name"]

    async def insert_one(self, document):
        inserted_document = dict(document)
        inserted_document.setdefault("_id", self.next_id)
        self.next_id += 1
        self.documents.append(inserted_document)
        document.setdefault("_id", inserted_document["_id"])
        return SimpleNamespace(inserted_id=inserted_document["_id"])

    async def find_one(self, filter, projection=None):
        document = self._find_first(filter)
        if document is None:
            return None
        return self._project(document, projection)

    async def update_one(self, filter, update, upsert=False):
        document = self._find_first(filter)
        if document is not None:
            self._apply_update(document, update, insert=False)
            return SimpleNamespace(
                matched_count=1,
                modified_count=1,
                upserted_id=None,
            )

        if not upsert:
            return SimpleNamespace(
                matched_count=0,
                modified_count=0,
                upserted_id=None,
            )

        inserted_document = {
            key: value
            for key, value in filter.items()
            if not isinstance(value, dict)
        }
        self._apply_update(inserted_document, update, insert=True)
        await self.insert_one(inserted_document)
        return SimpleNamespace(
            matched_count=0,
            modified_count=0,
            upserted_id=inserted_document["_id"],
        )

    async def find_one_and_update(self, filter, update, return_document=None):
        document = self._find_first(filter)
        if document is None:
            return None
        self._apply_update(document, update, insert=False)
        return dict(document)

    def find(self, filter):
        return FakeCursor(
            document for document in self.documents if self._matches(document, filter)
        )

    def _find_first(self, filter):
        for document in self.documents:
            if self._matches(document, filter):
                return document
        return None

    def _matches(self, document, filter):
        for key, expected_value in filter.items():
            current_value = document.get(key)
            if isinstance(expected_value, dict):
                if "$lte" in expected_value and current_value > expected_value["$lte"]:
                    return False
                if "$gte" in expected_value and current_value < expected_value["$gte"]:
                    return False
                continue

            if current_value != expected_value:
                return False
        return True

    def _apply_update(self, document, update, insert):
        for key, value in update.get("$set", {}).items():
            document[key] = value

        if insert:
            for key, value in update.get("$setOnInsert", {}).items():
                document[key] = value

        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value

    def _project(self, document, projection):
        if projection == {"_id": 1}:
            return {"_id": document["_id"]}
        return dict(document)


class FakeDatabase:
    def __init__(self, existing_collections=None, ping_response=None, ping_error=None):
        self.existing_collections = set(existing_collections or [])
        self.created_collections = []
        self.collections = {}
        self.ping_response = ping_response or {"ok": 1}
        self.ping_error = ping_error

    async def list_collection_names(self):
        return list(self.existing_collections)

    async def create_collection(self, name):
        self.created_collections.append(name)
        self.existing_collections.add(name)
        self.collections.setdefault(name, FakeCollection())

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())

    async def command(self, command_name):
        if self.ping_error:
            raise self.ping_error
        assert command_name == "ping"
        return self.ping_response


def test_init_db_creates_missing_collections_and_indexes():
    database = FakeDatabase()

    asyncio.run(init_db(database))

    assert set(database.created_collections) == set(REQUIRED_COLLECTIONS)
    for collection_name, index_definitions in INDEX_DEFINITIONS.items():
        created_indexes = database.collections[collection_name].created_indexes
        assert created_indexes == list(index_definitions)


def test_init_db_is_idempotent_when_collections_already_exist():
    database = FakeDatabase(existing_collections=REQUIRED_COLLECTIONS)

    asyncio.run(init_db(database))

    assert database.created_collections == []
    for collection_name, index_definitions in INDEX_DEFINITIONS.items():
        created_indexes = database.collections[collection_name].created_indexes
        assert created_indexes == list(index_definitions)


def test_ping_database_returns_true_when_mongo_ping_succeeds(monkeypatch):
    database = FakeDatabase(ping_response={"ok": 1})

    monkeypatch.setattr("database.connection.get_database", lambda: database)

    assert asyncio.run(ping_database()) is True


def test_ping_database_returns_false_when_mongo_ping_fails(monkeypatch):
    database = FakeDatabase(
        ping_error=ServerSelectionTimeoutError("MongoDB unavailable")
    )

    monkeypatch.setattr("database.connection.get_database", lambda: database)

    assert asyncio.run(ping_database()) is False


def search_config_payload(version=1):
    return {
        "config_id": "ignored-by-repository",
        "ativa": True,
        "version": version,
        "MENSAGENS": [{"id": 1, "query": "notebook gamer", "ativa": True}],
        "COLETA": {
            "RAM": {"enabled": True, "pattern": r"(\d+)GB"},
            "SSD": {"enabled": False, "pattern": r"SSD"},
            "preco": {"enabled": True, "pattern": r"R\$"},
            "link": {"enabled": False, "pattern": r"https?://"},
        },
        "LIMITES": {
            "max_mensagens_historico": 100,
            "max_tamanho_texto": 5000,
            "timeout_telegram_segundos": 30,
        },
    }


def test_search_config_repository_upserts_and_gets_default_config():
    database = FakeDatabase()
    repository = SearchConfigRepository(database)

    created = asyncio.run(repository.upsert_default_config(search_config_payload()))
    fetched = asyncio.run(repository.get_default_config())

    assert created["config_id"] == "default"
    assert created["version"] == 1
    assert fetched == created
    assert "_id" not in fetched


def test_repository_uses_get_database_when_database_is_not_injected(monkeypatch):
    database = FakeDatabase()

    monkeypatch.setattr("database.connection.get_database", lambda: database)

    repository = SearchConfigRepository()
    created = asyncio.run(repository.upsert_default_config(search_config_payload()))

    assert created["config_id"] == "default"


def test_search_config_repository_increments_version_and_detects_conflict():
    database = FakeDatabase()
    repository = SearchConfigRepository(database)

    created = asyncio.run(repository.upsert_default_config(search_config_payload()))
    updated = asyncio.run(repository.upsert_default_config(search_config_payload(version=1)))

    assert updated["version"] == created["version"] + 1
    with pytest.raises(VersionConflictError):
        asyncio.run(repository.upsert_default_config(search_config_payload(version=1)))


def test_history_repository_creates_gets_updates_and_lists_runs():
    database = FakeDatabase()
    repository = HistoryRepository(database)

    created = asyncio.run(repository.create_history_run("25/04"))
    fetched = asyncio.run(repository.get_history_run(created["run_id"]))
    updated = asyncio.run(
        repository.update_history_status(created["run_id"], "processing")
    )
    queued = asyncio.run(repository.list_queued_runs())

    assert fetched["run_id"] == created["run_id"]
    assert updated["status"] == "processing"
    assert queued == []


def test_audit_log_repository_creates_sanitized_log(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret-token")
    database = FakeDatabase()
    repository = AuditLogRepository(database)

    created = asyncio.run(
        repository.create_log(
            "auth.failed",
            "warning",
            "Authorization: Bearer secret-token",
            metadata={"route": "/admin"},
        )
    )

    assert created["event"] == "auth.failed"
    assert created["level"] == "WARNING"
    assert "secret-token" not in created["message"]
    assert created["metadata"] == {"route": "/admin"}


def test_outbox_email_repository_creates_lists_and_marks_statuses():
    database = FakeDatabase()
    repository = OutboxEmailRepository(database)
    due_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    created = asyncio.run(
        repository.create_email_task(
            "user@example.com",
            "Oferta encontrada",
            "Notebook encontrado",
            next_attempt_at=due_at,
        )
    )
    pending = asyncio.run(repository.list_pending())
    processing = asyncio.run(repository.mark_processing(created["email_id"]))
    failed = asyncio.run(
        repository.mark_failed(created["email_id"], "failed with secret-token")
    )
    sent = asyncio.run(repository.mark_sent(created["email_id"]))

    assert pending[0]["email_id"] == created["email_id"]
    assert processing["status"] == "processing"
    assert processing["attempts"] == 1
    assert failed["status"] == "failed"
    assert sent["status"] == "sent"


def test_processed_message_repository_marks_and_checks_message():
    database = FakeDatabase()
    repository = ProcessedMessageRepository(database)

    assert asyncio.run(repository.exists(123, "notebook")) is False
    assert asyncio.run(repository.mark_processed(123, "notebook")) is True
    assert asyncio.run(repository.exists(123, "notebook")) is True


def test_realtime_alert_repository_creates_and_gets_by_message_id():
    database = FakeDatabase()
    repository = RealtimeAlertRepository(database)

    created = asyncio.run(
        repository.create_alert(
            message_id=123,
            query="notebook",
            text="Notebook em promocao",
            metadata={"source": "telegram"},
        )
    )
    fetched = asyncio.run(repository.get_by_message_id(123))

    assert fetched == created
    assert fetched["metadata"] == {"source": "telegram"}
