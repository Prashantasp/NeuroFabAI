"""Local filesystem storage provider."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO

from app.services.storage.provider import StorageError, StorageProvider


class LocalStorageProvider(StorageProvider):
    name = "local"

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolve a storage key to an absolute path inside the storage root.

        Keys are built from workspace and document ids, but this is the last line
        of defence: a key containing `..` must never resolve outside base_dir.
        """
        candidate = (self.base_dir / key).resolve()
        if not candidate.is_relative_to(self.base_dir):
            raise StorageError(f"Refusing to access path outside storage root: {key}")
        return candidate

    def save(self, file_obj: BinaryIO, key: str) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        file_obj.seek(0)
        with open(target, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer, length=1024 * 1024)
        return key

    def open(self, key: str) -> BinaryIO:
        target = self._resolve(key)
        if not target.exists():
            raise StorageError(f"Stored object not found: {key}")
        return open(target, "rb")

    def delete(self, key: str) -> bool:
        target = self._resolve(key)
        if not target.exists():
            return False
        target.unlink()

        # Clean up the now-empty per-document directory.
        try:
            parent = target.parent
            if parent != self.base_dir and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        return True

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except StorageError:
            return False

    def get_absolute_path(self, key: str) -> str:
        return str(self._resolve(key))

    def size(self, key: str) -> int:
        target = self._resolve(key)
        return target.stat().st_size if target.exists() else 0
