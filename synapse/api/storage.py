"""Thread-safe async storage for Synapse API.

Protocol Version: 1.0
Specification: 3.1

This module provides async-safe storage with proper locking
to prevent race conditions in concurrent access scenarios.
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager


class AsyncSafeDict:
    """Async-safe dictionary wrapper with read/write locks."""

    def __init__(self, name: str = "storage"):
        self.name = name
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._write_count = 0
        self._read_count = 0

    @asynccontextmanager
    async def read_lock(self):
        """Acquire read lock."""
        async with self._read_lock:
            self._read_count += 1
            try:
                yield
            finally:
                self._read_count -= 1

    @asynccontextmanager
    async def write_lock(self):
        """Acquire write lock."""
        async with self._lock:
            self._write_count += 1
            try:
                yield
            finally:
                self._write_count -= 1

    async def get(self, key: str, default: Any = None) -> Any:
        """Safely get a value."""
        async with self.read_lock():
            return self._data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        """Safely set a value."""
        async with self.write_lock():
            self._data[key] = value

    async def delete(self, key: str) -> bool:
        """Safely delete a value."""
        async with self.write_lock():
            if key in self._data:
                del self._data[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Safely check if key exists."""
        async with self.read_lock():
            return key in self._data

    async def keys(self) -> List[str]:
        """Safely get all keys."""
        async with self.read_lock():
            return list(self._data.keys())

    async def values(self) -> List[Any]:
        """Safely get all values."""
        async with self.read_lock():
            return list(self._data.values())

    async def items(self) -> List[tuple]:
        """Safely get all items."""
        async with self.read_lock():
            return list(self._data.items())

    async def clear(self) -> None:
        """Safely clear all data."""
        async with self.write_lock():
            self._data.clear()

    async def count(self) -> int:
        """Safely get count of items."""
        async with self.read_lock():
            return len(self._data)

    async def stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        async with self.read_lock():
            return {
                "name": self.name,
                "count": len(self._data),
                "write_count": self._write_count,
                "read_count": self._read_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


class AsyncSafeList:
    """Async-safe list wrapper with read/write locks."""

    def __init__(self, name: str = "list_storage", max_size: int = 10000):
        self.name = name
        self.max_size = max_size
        self._data: List[Any] = []
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._append_count = 0

    @asynccontextmanager
    async def read_lock(self):
        """Acquire read lock."""
        async with self._read_lock:
            try:
                yield
            finally:
                pass

    @asynccontextmanager
    async def write_lock(self):
        """Acquire write lock."""
        async with self._lock:
            try:
                yield
            finally:
                pass

    async def append(self, value: Any) -> int:
        """Safely append a value, returns index."""
        async with self.write_lock():
            if len(self._data) >= self.max_size:
                remove_count = max(1, self.max_size // 10)
                self._data = self._data[remove_count:]
            self._append_count += 1
            self._data.append(value)
            return len(self._data) - 1

    async def get(self, index: int, default: Any = None) -> Any:
        """Safely get value at index."""
        async with self.read_lock():
            try:
                return self._data[index]
            except IndexError:
                return default

    async def slice(self, start: int = 0, end: Optional[int] = None) -> List[Any]:
        """Safely get a slice of the list."""
        async with self.read_lock():
            return self._data[start:end]

    async def count(self) -> int:
        """Safely get count of items."""
        async with self.read_lock():
            return len(self._data)

    async def clear(self) -> None:
        """Safely clear all data."""
        async with self.write_lock():
            self._data.clear()

    async def stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        async with self.read_lock():
            return {
                "name": self.name,
                "count": len(self._data),
                "max_size": self.max_size,
                "append_count": self._append_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


# Global storage instances
agents_storage = AsyncSafeDict("agents")
approvals_storage = AsyncSafeList("approvals")
logs_storage = AsyncSafeList("logs", max_size=10000)
tasks_storage = AsyncSafeList("tasks", max_size=10000)


__all__ = [
    "AsyncSafeDict",
    "AsyncSafeList",
    "agents_storage",
    "approvals_storage",
    "logs_storage",
    "tasks_storage",
]
