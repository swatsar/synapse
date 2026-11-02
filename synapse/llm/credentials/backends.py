"""Secret backend implementations.

- EnvironmentSecretBackend  — process environment (read-only)
- OSKeyringBackend          — OS credential vault (optional; needs 'keyring')
- EncryptedDatabaseSecretBackend — Fernet-encrypted SQLite store (read/write)

Each backend degrades honestly when its dependency is missing rather than
returning a fake value.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import UTC, datetime
from typing import Any

from synapse.llm.credentials.protocol import (
    SecretBackend,
    SecretBackendUnavailable,
    SecretError,
    SecretNotFound,
    SecretValue,
)

logger = logging.getLogger(__name__)

PROTOCOL_VERSION: str = "1.0"


class EnvironmentSecretBackend(SecretBackend):
    """Resolves secrets from the process environment.

    Keys are environment variable names (secret://env/MY_API_KEY).
    Read-only by design: writing to the environment of a running process is
    not a durable secret operation.
    """

    backend_id = "env"

    def __init__(self, env: dict[str, str] | None = None):
        self._env = env if env is not None else os.environ

    async def resolve(self, key: str) -> SecretValue:
        value = self._env.get(key)
        if value is None:
            raise SecretNotFound(f"secret://env/{key}", backend=self.backend_id)
        return SecretValue(_secret=value, backend=self.backend_id,
                           ref=f"secret://env/{key}")

    async def exists(self, key: str) -> bool:
        return key in self._env

    async def health(self) -> dict[str, Any]:
        return {"backend": self.backend_id, "available": True,
                "entries": len(self._env), "read_only": True,
                "protocol_version": self.protocol_version}


class OSKeyringBackend(SecretBackend):
    """Resolves secrets from the OS credential vault.

    Requires the optional 'keyring' package. When it is not installed, the
    backend reports unavailable instead of fabricating a value.
    """

    backend_id = "keyring"

    def __init__(self, service_name: str = "synapse"):
        self._service_name = service_name
        self._keyring = self._load_keyring()

    @staticmethod
    def _load_keyring() -> Any:
        try:
            import keyring  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SecretBackendUnavailable(
                "keyring", "the 'keyring' package is not installed"
            ) from exc
        return keyring

    async def resolve(self, key: str) -> SecretValue:
        loop = asyncio.get_event_loop()
        value = await loop.run_in_executor(
            None, self._keyring.get_password, self._service_name, key
        )
        if value is None:
            raise SecretNotFound(f"secret://keyring/{key}", backend=self.backend_id)
        return SecretValue(_secret=value, backend=self.backend_id,
                           ref=f"secret://keyring/{key}")

    async def store(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._keyring.set_password, self._service_name, key, value
        )

    async def delete(self, key: str) -> bool:
        existed = await self.exists(key)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._keyring.delete_password, self._service_name, key
        )
        return existed

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_event_loop()
        value = await loop.run_in_executor(
            None, self._keyring.get_password, self._service_name, key
        )
        return value is not None


class EncryptedDatabaseSecretBackend(SecretBackend):
    """Fernet-encrypted SQLite secret store.

    The master key is supplied by the caller (env var, KMS-wrapped key, ...)
    and is never persisted by this backend. Ciphertext-only rows are stored,
    so a stolen database file does not reveal secrets.
    """

    backend_id = "db"

    def __init__(self, db_path: str = ":memory:", master_key: str | None = None,
                 key_env_var: str = "SYNAPSE_SECRET_KEY"):
        try:
            import aiosqlite
            from cryptography.fernet import Fernet
        except ImportError as e:
            raise SecretBackendUnavailable("db", f"missing dependency: {e}")

        self._aiosqlite = aiosqlite
        self._db_path = db_path if db_path is not None else ":memory:"
        key = master_key if master_key is not None else os.getenv(key_env_var)
        if not key:
            raise SecretBackendUnavailable(
                "db", f"no master key (set {key_env_var} or pass master_key)"
            )
        self._fernet = Fernet(self._encode_key(key))
        self._db: Any = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _encode_key(key: str) -> bytes:
        """Derive a URL-safe 32-byte Fernet key from an arbitrary passphrase."""
        import hashlib
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    async def _get_db(self) -> Any:
        async with self._lock:
            if self._db is None:
                self._db = await self._aiosqlite.connect(self._db_path)
                await self._db.execute(
                    "CREATE TABLE IF NOT EXISTS secrets ("
                    "  key TEXT PRIMARY KEY,"
                    "  ciphertext BLOB NOT NULL,"
                    "  metadata TEXT,"
                    "  updated_at TEXT NOT NULL"
                    ")"
                )
                await self._db.commit()
            return self._db

    async def close(self) -> None:
        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None

    async def resolve(self, key: str) -> SecretValue:
        db = await self._get_db()
        async with db.execute(
            "SELECT ciphertext, metadata FROM secrets WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise SecretNotFound(f"secret://db/{key}", backend=self.backend_id)
        plaintext = self._fernet.decrypt(row[0]).decode("utf-8")
        metadata: dict[str, Any] = {}
        if row[1]:
            import json
            try:
                metadata = json.loads(row[1])
            except ValueError:
                metadata = {}
        return SecretValue(_secret=plaintext, backend=self.backend_id,
                           ref=f"secret://db/{key}", metadata=metadata)

    async def store(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        import json
        db = await self._get_db()
        ciphertext = self._fernet.encrypt(value.encode("utf-8"))
        await db.execute(
            "INSERT OR REPLACE INTO secrets (key, ciphertext, metadata, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (key, ciphertext, json.dumps(metadata or {}),
             datetime.now(UTC).isoformat()),
        )
        await db.commit()

    async def delete(self, key: str) -> bool:
        existed = await self.exists(key)
        db = await self._get_db()
        await db.execute("DELETE FROM secrets WHERE key = ?", (key,))
        await db.commit()
        return existed

    async def exists(self, key: str) -> bool:
        db = await self._get_db()
        async with db.execute(
            "SELECT 1 FROM secrets WHERE key = ?", (key,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def health(self) -> dict[str, Any]:
        return {"backend": self.backend_id, "available": True,
                "read_only": False, "protocol_version": self.protocol_version}


__all__ = [
    "EncryptedDatabaseSecretBackend",
    "EnvironmentSecretBackend",
    "OSKeyringBackend",
]
