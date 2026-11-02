"""Credential Store protocol — zero-trust secret resolution.

Providers never hold raw credentials. They hold a ``secret://`` reference,
and the CredentialStore resolves it through a pluggable SecretBackend at the
moment of use. Raw values are wrapped in SecretValue, whose repr is masked,
so secrets are never accidentally logged or serialized.

Reference: Hermes secret-manager integration patterns (architectural idea,
clean-room implementation).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION: str = "1.0"

SCHEME = "secret"


class SecretError(RuntimeError):
    """Base error for credential operations."""


class SecretNotFound(SecretError):
    """No backend could resolve the reference."""

    def __init__(self, ref: str, backend: str | None = None):
        self.ref = ref
        self.backend = backend
        super().__init__(f"secret not found: {ref}" + (f" (backend={backend})" if backend else ""))


class SecretBackendUnavailable(SecretError):
    """The requested backend is not installed/usable."""

    def __init__(self, backend: str, reason: str = ""):
        self.backend = backend
        super().__init__(f"secret backend unavailable: {backend} {reason}".rstrip())


@dataclass(frozen=True)
class SecretRef:
    """Parsed ``secret://`` reference.

    Grammar::

        secret://<backend>/<key>     # explicit backend
        secret://<key>               # default backend

    ``key`` is backend specific: an environment variable name for ``env``, a
    hierarchical path (``tenant/<id>/providers/<pid>``) for ``keyring``/``db``.
    """

    backend: str | None
    key: str
    raw: str

    @property
    def scope(self) -> str:
        """First path segment of the key, or "" when the key is flat."""
        parts = [p for p in self.key.split("/") if p]
        return parts[0] if parts else ""

    @property
    def full_key(self) -> str:
        """The key including the first path segment when it is not a backend.

        parse() splits the first segment off as a *candidate* backend id; when
        it turns out to be part of the key instead (e.g.
        secret://tenant/acme/...), the store uses this property.
        """
        if self.backend is None:
            return self.key
        return f"{self.backend}/{self.key}"

    @staticmethod
    def parse(ref: str) -> "SecretRef":
        if not isinstance(ref, str):
            raise SecretError(f"secret reference must be a string, got {type(ref).__name__}")
        marker = f"{SCHEME}://"
        if not ref.startswith(marker):
            raise SecretError(f"not a {SCHEME}:// reference: {ref!r}")
        body = ref[len(marker):]
        if not body:
            raise SecretError(f"empty {SCHEME}:// reference")
        parts = body.split("/", 1)
        if len(parts) == 1:
            return SecretRef(backend=None, key=body, raw=ref)
        backend, key = parts[0], parts[1]
        if not key:
            raise SecretError(f"empty key in {SCHEME}:// reference: {ref!r}")
        return SecretRef(backend=backend, key=key, raw=ref)

    def to_dict(self) -> dict[str, Any]:
        return {"backend": self.backend, "key": self.key, "raw": self.raw}


@dataclass
class SecretValue:
    """Masked wrapper around a resolved secret.

    ``str(value)`` and ``repr(value)`` never expose the secret; callers must
    use :meth:`reveal` (or the ``secret`` attribute) deliberately.
    """

    _secret: str
    backend: str = ""
    ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def secret(self) -> str:
        return self._secret

    def reveal(self) -> str:
        """Return the raw secret value (audited at the store level)."""
        return self._secret

    @property
    def masked(self) -> str:
        if not self._secret:
            return ""
        if len(self._secret) <= 8:
            return "*" * len(self._secret)
        return f"{self._secret[:3]}***{self._secret[-3:]}"

    def __str__(self) -> str:
        return self.masked

    def __repr__(self) -> str:
        return f"SecretValue({self.masked!r}, backend={self.backend!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecretValue) and other._secret == self._secret

    def __hash__(self) -> int:
        return hash(self._secret)

    def to_dict(self) -> dict[str, Any]:
        """Never includes the raw value."""
        return {"backend": self.backend, "ref": self.ref, "masked": self.masked,
                "metadata": self.metadata, "protocol_version": PROTOCOL_VERSION}


class SecretBackend(ABC):
    """A single way of storing and resolving secrets.

    Backends are transport-only: they know nothing about providers. The store
    decides which backend a ``secret://`` reference points at.
    """

    #: stable id used in ``secret://<backend>/...`` references
    backend_id: str = "abstract"

    protocol_version: str = PROTOCOL_VERSION

    @abstractmethod
    async def resolve(self, key: str) -> SecretValue:
        """Resolve ``key`` or raise SecretNotFound."""

    async def store(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        """Persist a secret. Optional; raises SecretBackendUnavailable if read-only."""
        raise SecretBackendUnavailable(self.backend_id, "read-only backend")

    async def delete(self, key: str) -> bool:
        """Delete a secret; return whether it existed. Optional."""
        raise SecretBackendUnavailable(self.backend_id, "read-only backend")

    async def exists(self, key: str) -> bool:
        """Whether ``key`` is present."""
        return False

    async def health(self) -> dict[str, Any]:
        return {"backend": self.backend_id, "available": True,
                "protocol_version": self.protocol_version}


__all__ = [
    "SCHEME",
    "SecretBackend",
    "SecretBackendUnavailable",
    "SecretError",
    "SecretNotFound",
    "SecretRef",
    "SecretValue",
]
