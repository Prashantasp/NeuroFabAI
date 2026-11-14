from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageError(Exception):
    """Raised when an object cannot be stored or retrieved."""


class StorageProvider(ABC):
    """Blob storage interface.

    Implemented locally today; an S3/GCS provider only needs to satisfy this
    interface for the rest of the application to work unchanged.
    """

    name: str = "base"

    @abstractmethod
    def save(self, file_obj: BinaryIO, key: str) -> str:
        """Persist a file and return the storage key."""

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Open a stored object for reading."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a stored object. Returns False when it did not exist."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether an object exists."""

    @abstractmethod
    def get_absolute_path(self, key: str) -> str:
        """Local filesystem path, where the backend supports one."""

    @abstractmethod
    def size(self, key: str) -> int:
        """Size in bytes, or 0 when absent."""
