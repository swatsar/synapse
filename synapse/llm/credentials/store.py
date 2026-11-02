"""CredentialStore — the single entry point for secret resolution.

Routes a `secret://` reference to the right SecretBackend, audits every
resolution *without* the value, and supports a default backend plus optional
per-tenant backends. Nothing else in Synapse reads secrets directly.
"""
from __future__ import annotations

import logging
from typing import Any

from synapse.llm.credentials.backends import (
    EncryptedDatabaseSecretBackend,
    EnvironmentSecretBackend,
)
from synapse.llm.credentials.protocol import (
    SCHEME,
    SecretBackend,
    SecretBackendUnavailable,
    SecretError,
    SecretNotFound,
    SecretRef,
    SecretValue,
)

logger = logging.getLogger(__name__)

PROTOCOL_VERSION: str = "1.0"


class CredentialStore:
    """Registry of secret backends plus reference routing.

    Backends are registered by `backend_id`; a reference may name one
    explicitly (`secret://env/KEY`) or fall back to the default backend
    (`secret://KEY`).
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, default_backend_id: str = "env"):
        self._backends: dict[str, SecretBackend] = {}
        self._default_backend_id = default_backend_id
        self._audit: Any = None

    def set_audit_logger(self, audit) -> None:
        self._audit = audit

    def register_backend(self, backend: SecretBackend, make_default: bool = False) -> None:
        self._backends[backend.backend_id] = backend
        if make_default:
            self._default_backend_id = backend.backend_id

    def list_backends(self) -> list[str]:
        return sorted(self._backends)

    @property
    def default_backend_id(self) -> str:
        return self._default_backend_id

    def _select(self, ref: SecretRef) -> tuple[SecretBackend, str]:
        """Pick (backend, key) for a reference.

        The first path segment is only a backend when it names a *registered*
        backend; otherwise it is part of the key and the default backend is
        used. This keeps secret://env/KEY explicit while allowing scoped keys
        such as secret://tenant/acme/providers/openrouter.
        """
        if ref.backend is not None and ref.backend in self._backends:
            return self._backends[ref.backend], ref.key
        if ref.backend is None:
            return self._backends[self._default_backend_id], ref.key
        backend = self._backends.get(self._default_backend_id)
        if backend is None:
            raise SecretBackendUnavailable(
                self._default_backend_id,
                "registered backends: " + (",".join(self.list_backends()) or "(none)"),
            )
        return backend, ref.full_key

    async def resolve(self, ref: str) -> SecretValue:
        """Resolve a secret:// reference to a SecretValue (never logs the value)."""
        if not isinstance(ref, str) or not ref:
            raise SecretError("credential reference is required")
        if not ref.startswith(f"{SCHEME}://"):
            raise SecretError(f"not a {SCHEME}:// reference: {ref!r}")
        parsed = SecretRef.parse(ref)
        backend, key = self._select(parsed)
        try:
            value = await backend.resolve(key)
        except SecretNotFound:
            self._log("credential_resolve_miss", ref=ref, backend=backend.backend_id)
            raise
        self._log("credential_resolve", ref=ref, backend=backend.backend_id,
                  masked=value.masked)
        return value

    async def store(self, ref: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        parsed = SecretRef.parse(ref)
        backend, key = self._select(parsed)
        await backend.store(key, value, metadata)
        self._log("credential_store", ref=ref, backend=backend.backend_id)

    async def delete(self, ref: str) -> bool:
        parsed = SecretRef.parse(ref)
        backend, key = self._select(parsed)
        existed = await backend.delete(key)
        self._log("credential_delete", ref=ref, backend=backend.backend_id, existed=existed)
        return existed

    async def exists(self, ref: str) -> bool:
        parsed = SecretRef.parse(ref)
        backend, key = self._select(parsed)
        return await backend.exists(key)

    async def health(self) -> dict[str, Any]:
        return {
            "backends": {bid: await be.health() for bid, be in self._backends.items()},
            "default_backend": self._default_backend_id,
            "protocol_version": self.protocol_version,
        }

    def _log(self, event: str, **fields: Any) -> None:
        # Never include secret material here.
        if self._audit is not None:
            try:
                self._audit(event=event, **fields, protocol_version=self.protocol_version)
            except Exception:  # noqa: BLE001 - auditing must never break resolution
                logger.debug("audit hook failed for %s", event)
        else:
            logger.debug("%s %s", event, fields)


def create_default_credential_store() -> CredentialStore:
    """Build the standard store: env backend (default) + encrypted-db backend.

    The db backend is only registered when a master key is available, so an
    unconfigured deployment still works for environment-based credentials.
    """
    store = CredentialStore(default_backend_id="env")
    store.register_backend(EnvironmentSecretBackend(), make_default=True)
    try:
        store.register_backend(EncryptedDatabaseSecretBackend())
    except (SecretBackendUnavailable, Exception) as exc:
        logger.info("encrypted secret backend disabled (%s)", exc)
    return store


__all__ = ["CredentialStore", "create_default_credential_store"]
