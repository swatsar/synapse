"""Unit tests for the zero-trust credential store."""
import pytest

from synapse.llm.credentials import (
    SCHEME,
    SecretBackendUnavailable,
    SecretError,
    SecretNotFound,
    SecretRef,
    SecretValue,
)
from synapse.llm.credentials.backends import (
    EncryptedDatabaseSecretBackend,
    EnvironmentSecretBackend,
)
from synapse.llm.credentials.store import CredentialStore, create_default_credential_store


class TestSecretRef:
    def test_explicit_backend(self):
        ref = SecretRef.parse("secret://env/MY_KEY")
        assert ref.backend == "env"
        assert ref.key == "MY_KEY"
        assert ref.raw == "secret://env/MY_KEY"

    def test_scoped_key(self):
        # The first segment is a *candidate* backend id; the store decides.
        ref = SecretRef.parse("secret://tenant/acme/providers/openrouter")
        assert ref.backend == "tenant"
        assert ref.key == "acme/providers/openrouter"
        assert ref.full_key == "tenant/acme/providers/openrouter"

    def test_scope_is_first_segment(self):
        assert SecretRef.parse("secret://db/tenant/acme/x").scope == "tenant"
        assert SecretRef.parse("secret://env/FLAT_NAME").scope == "FLAT_NAME"

    def test_rejects_non_secret_scheme(self):
        with pytest.raises(SecretError):
            SecretRef.parse("https://example.com/key")

    def test_rejects_empty(self):
        with pytest.raises(SecretError):
            SecretRef.parse("secret://")
        with pytest.raises(SecretError):
            SecretRef.parse("secret://env/")

    def test_rejects_non_string(self):
        with pytest.raises(SecretError):
            SecretRef.parse(None)


class TestSecretValueMasking:
    def test_repr_and_str_are_masked(self):
        v = SecretValue(_secret="sk-abcdefghij1234567890", backend="env")
        assert "sk-abc" not in repr(v)
        assert "sk-abc" not in str(v)
        assert "***" in repr(v)

    def test_short_values_fully_masked(self):
        v = SecretValue(_secret="abc", backend="env")
        assert str(v) == "***"

    def test_reveal_returns_raw(self):
        v = SecretValue(_secret="super-secret", backend="env")
        assert v.reveal() == "super-secret"
        assert v.secret == "super-secret"

    def test_to_dict_excludes_raw(self):
        v = SecretValue(_secret="super-secret", backend="env", ref="secret://env/K")
        d = v.to_dict()
        assert "super-secret" not in str(d)
        assert d["masked"] == "sup***ret"
        assert d["backend"] == "env"

    def test_equality_on_raw(self):
        assert SecretValue(_secret="x") == SecretValue(_secret="x")
        assert SecretValue(_secret="x") != SecretValue(_secret="y")


class TestEnvironmentBackend:
    @pytest.mark.asyncio
    async def test_resolve(self):
        backend = EnvironmentSecretBackend(env={"MY_KEY": "value-1"})
        value = await backend.resolve("MY_KEY")
        assert value.reveal() == "value-1"
        assert value.backend == "env"

    @pytest.mark.asyncio
    async def test_resolve_missing_raises(self):
        backend = EnvironmentSecretBackend(env={})
        with pytest.raises(SecretNotFound):
            await backend.resolve("MISSING")

    @pytest.mark.asyncio
    async def test_read_only(self):
        backend = EnvironmentSecretBackend(env={})
        with pytest.raises(SecretBackendUnavailable):
            await backend.store("X", "y")
        with pytest.raises(SecretBackendUnavailable):
            await backend.delete("X")

    @pytest.mark.asyncio
    async def test_exists(self):
        backend = EnvironmentSecretBackend(env={"A": "1"})
        assert await backend.exists("A") is True
        assert await backend.exists("B") is False


class TestEncryptedDatabaseBackend:
    @pytest.fixture
    def backend(self):
        return EncryptedDatabaseSecretBackend(db_path=":memory:", master_key="test-key")

    @pytest.mark.asyncio
    async def test_store_and_resolve_roundtrip(self, backend):
        await backend.store("tenant/acme/providers/or", "sk-live-12345")
        value = await backend.resolve("tenant/acme/providers/or")
        assert value.reveal() == "sk-live-12345"

    @pytest.mark.asyncio
    async def test_missing_raises(self, backend):
        with pytest.raises(SecretNotFound):
            await backend.resolve("nope")

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        await backend.store("k", "v")
        assert await backend.delete("k") is True
        assert await backend.exists("k") is False
        assert await backend.delete("k") is False

    @pytest.mark.asyncio
    async def test_metadata_survives_roundtrip(self, backend):
        await backend.store("k", "v", metadata={"rotated_by": "admin"})
        value = await backend.resolve("k")
        assert value.metadata == {"rotated_by": "admin"}

    def test_requires_master_key(self, monkeypatch):
        monkeypatch.delenv("SYNAPSE_SECRET_KEY", raising=False)
        with pytest.raises(SecretBackendUnavailable):
            EncryptedDatabaseSecretBackend(db_path=":memory:")


class TestCredentialStore:
    @pytest.fixture
    def store(self):
        s = CredentialStore(default_backend_id="env")
        s.register_backend(EnvironmentSecretBackend(env={"K1": "sk-abcdefghij"}), make_default=True)
        return s

    @pytest.mark.asyncio
    async def test_resolve_explicit_backend(self, store):
        value = await store.resolve("secret://env/K1")
        assert value.reveal() == "sk-abcdefghij"

    @pytest.mark.asyncio
    async def test_resolve_default_backend(self, store):
        value = await store.resolve("secret://K1")
        assert value.reveal() == "sk-abcdefghij"

    @pytest.mark.asyncio
    async def test_unregistered_first_segment_falls_through_to_default(self, store):
        # secret://vault/anything: "vault" is not a registered backend, so the
        # whole path is treated as a key on the default backend.
        with pytest.raises(SecretNotFound):
            await store.resolve("secret://vault/anything")

    @pytest.mark.asyncio
    async def test_no_backend_registered_raises(self):
        empty = CredentialStore(default_backend_id="env")
        with pytest.raises(SecretBackendUnavailable):
            await empty.resolve("secret://env/K1")

    @pytest.mark.asyncio
    async def test_scoped_key_routes_to_default_backend(self):
        store = CredentialStore(default_backend_id="env")
        store.register_backend(
            EnvironmentSecretBackend(env={"tenant/acme/x": "scoped"}), make_default=True
        )
        value = await store.resolve("secret://tenant/acme/x")
        assert value.reveal() == "scoped"

    @pytest.mark.asyncio
    async def test_missing_secret_raises(self, store):
        with pytest.raises(SecretNotFound):
            await store.resolve("secret://env/DOES_NOT_EXIST")

    @pytest.mark.asyncio
    async def test_non_secret_ref_rejected(self, store):
        with pytest.raises(SecretError):
            await store.resolve("plain-string-key")

    @pytest.mark.asyncio
    async def test_audit_hook_never_sees_raw_value(self, store):
        seen = []
        store.set_audit_logger(lambda **kw: seen.append(kw))
        await store.resolve("secret://env/K1")
        assert len(seen) == 1
        payload = str(seen[0])
        assert "sk-abcdefghij" not in payload
        assert seen[0]["masked"] == "sk-***hij"

    @pytest.mark.asyncio
    async def test_health_lists_backends(self, store):
        h = await store.health()
        assert "env" in h["backends"]
        assert h["default_backend"] == "env"


class TestDefaultStoreFactory:
    @pytest.mark.asyncio
    async def test_env_backend_is_default(self):
        store = create_default_credential_store()
        assert store.default_backend_id == "env"
        assert "env" in store.list_backends()

    def test_scheme_constant(self):
        assert SCHEME == "secret"
