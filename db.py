"""
Supabase (Postgres) client + safe helpers.

If SUPABASE_URL / SUPABASE_KEY are not set, all helpers degrade to no-ops
(just log), so the server still runs and you can test the voice pipeline
before the database is wired up.
"""
import logging
import os
from typing import Any

log = logging.getLogger("voice-agent.db")

_client = None


_client_failed = False


def _get_client():
    """Return a Supabase client, or None if unconfigured/unusable.

    Never raises: a bad key must degrade to a no-op, not break a live call.
    """
    global _client, _client_failed
    if _client is not None:
        return _client
    if _client_failed:
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key or url.startswith("https://xxxx"):
        log.warning("Supabase not configured — DB calls are no-ops.")
        _client_failed = True
        return None

    try:
        from supabase import create_client

        _client = create_client(url, key)
    except Exception:  # noqa: BLE001 - bad creds must not break a call
        log.exception("Supabase client init failed — DB calls are no-ops.")
        _client_failed = True
        return None
    return _client


def save_record(table: str, row: dict[str, Any]) -> None:
    """Insert one row. Never raises — DB must not break a live call."""
    client = _get_client()
    if client is None:
        log.info("[no-db] would insert into %s: %s", table, row)
        return
    try:
        client.table(table).insert(row).execute()
    except Exception:  # noqa: BLE001
        log.exception("Insert into %s failed", table)


def log_call_event(event_type: str, payload: dict[str, Any]) -> None:
    """Lightweight event log — handy to show call flow to the reviewer."""
    save_record(
        "call_events",
        {"event_type": event_type, "payload": payload},
    )
