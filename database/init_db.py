from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import CollectionInvalid

from database.collections import (
    AUDIT_LOGS,
    HISTORY_RESULTS,
    HISTORY_RUNS,
    OUTBOX_EMAILS,
    PROCESSED_MESSAGES,
    REALTIME_ALERTS,
    REQUIRED_COLLECTIONS,
    SEARCH_CONFIGS,
)
from database.connection import get_database

logger = logging.getLogger(__name__)

IndexDefinition = dict[str, Any]

INDEX_DEFINITIONS: dict[str, tuple[IndexDefinition, ...]] = {
    SEARCH_CONFIGS: (
        {
            "keys": [("config_id", ASCENDING)],
            "name": "idx_search_configs_config_id_unique",
            "unique": True,
        },
    ),
    PROCESSED_MESSAGES: (
        {
            "keys": [("message_id", ASCENDING), ("query", ASCENDING)],
            "name": "idx_processed_messages_message_id_query_unique",
            "unique": True,
        },
    ),
    REALTIME_ALERTS: (
        {
            "keys": [("message_id", ASCENDING)],
            "name": "idx_realtime_alerts_message_id_unique",
            "unique": True,
        },
    ),
    HISTORY_RUNS: (
        {
            "keys": [("status", ASCENDING), ("created_at", ASCENDING)],
            "name": "idx_history_runs_status_created_at",
        },
    ),
    HISTORY_RESULTS: (
        {
            "keys": [
                ("run_id", ASCENDING),
                ("message_id", ASCENDING),
                ("pesquisa", ASCENDING),
            ],
            "name": "idx_history_results_run_id_message_id_pesquisa",
        },
    ),
    OUTBOX_EMAILS: (
        {
            "keys": [
                ("status", ASCENDING),
                ("next_attempt_at", ASCENDING),
                ("created_at", ASCENDING),
            ],
            "name": "idx_outbox_emails_status_next_attempt_at_created_at",
        },
    ),
    AUDIT_LOGS: (
        {
            "keys": [
                ("created_at", ASCENDING),
                ("event", ASCENDING),
                ("level", ASCENDING),
            ],
            "name": "idx_audit_logs_created_at_event_level",
        },
    ),
}


async def init_db(database: Any | None = None) -> None:
    db = database or get_database()

    existing_collections = set(await db.list_collection_names())

    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name in existing_collections:
            continue

        try:
            await db.create_collection(collection_name)
            existing_collections.add(collection_name)
            logger.info("Created MongoDB collection: %s", collection_name)
        except CollectionInvalid:
            existing_collections.add(collection_name)

    for collection_name, index_definitions in INDEX_DEFINITIONS.items():
        collection = db[collection_name]
        for index_definition in index_definitions:
            await collection.create_index(**index_definition)
            logger.debug(
                "Ensured MongoDB index %s on %s",
                index_definition["name"],
                collection_name,
            )
