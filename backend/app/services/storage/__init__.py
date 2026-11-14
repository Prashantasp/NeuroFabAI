"""Storage provider registry."""

import os
from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.local_provider import LocalStorageProvider
from app.services.storage.provider import StorageError, StorageProvider

__all__ = [
    "StorageError",
    "StorageProvider",
    "get_storage_provider",
    "reset_storage_provider",
]


@lru_cache
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    base_dir = settings.STORAGE_DIR
    if not os.path.isabs(base_dir):
        # Resolve relative to the backend package root so the storage location
        # does not depend on the process working directory.
        package_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        base_dir = os.path.join(os.path.dirname(package_root), base_dir)
    return LocalStorageProvider(base_dir=base_dir)


def reset_storage_provider() -> None:
    get_storage_provider.cache_clear()
