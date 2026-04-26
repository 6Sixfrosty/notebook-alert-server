import asyncio

from pymongo.errors import ServerSelectionTimeoutError

from database.collections import REQUIRED_COLLECTIONS
from database.connection import ping_database
from database.init_db import INDEX_DEFINITIONS, init_db


class FakeCollection:
    def __init__(self) -> None:
        self.created_indexes = []

    async def create_index(self, **kwargs):
        self.created_indexes.append(kwargs)
        return kwargs["name"]


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
