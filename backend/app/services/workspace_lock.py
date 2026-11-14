"""Serialize index writes and deletion; PostgreSQL releases locks on a crashed connection."""

from contextlib import contextmanager
import hashlib
import threading
from functools import wraps
from fastapi import HTTPException

from sqlalchemy import text

_guard = threading.Lock()
_local_locks: dict[str, threading.Lock] = {}


@contextmanager
def workspace_lock(bind, workspace_id: str):
    if bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(workspace_id.encode()).digest()[:8], "big", signed=True)
        with bind.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            try:
                yield bool(acquired)
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    else:
        # SQLite is only supported for local development and tests.
        with _guard:
            lock = _local_locks.setdefault(workspace_id, threading.Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()


def serialized_workspace(method):
    @wraps(method)
    def wrapped(self, db, context, *args, **kwargs):
        workspace_id = getattr(context, "workspace_id", None) or context.id
        with workspace_lock(db.get_bind(), workspace_id) as acquired:
            if not acquired:
                raise HTTPException(409, "This workspace is processing a document. Please retry shortly.")
            return method(self, db, context, *args, **kwargs)
    return wrapped
