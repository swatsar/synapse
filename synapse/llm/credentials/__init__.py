"""Zero-trust credential store."""
from synapse.llm.credentials.store import CredentialStore, create_default_credential_store
from synapse.llm.credentials.protocol import (  # noqa: F401
    SCHEME,
    SecretBackend,
    SecretBackendUnavailable,
    SecretError,
    SecretNotFound,
    SecretRef,
    SecretValue,
)

__all__ = [
    "SCHEME",
    "SecretBackend",
    "SecretBackendUnavailable",
    "SecretError",
    "SecretNotFound",
    "SecretRef",
    "SecretValue",
    "CredentialStore",
    "create_default_credential_store",
]
