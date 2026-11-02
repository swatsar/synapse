# Synapse target state

Synapse remains the only source of truth and control plane. External projects contribute patterns only.

- ProviderRegistry → ProviderProfile → protocol adapter → CredentialStore(secret://) → ModelCatalog.
- PluginRuntime owns manifest validation, dependency ordering, permission diff, service registration, and lifecycle; CapabilityManager remains the enforcement boundary.
- WorkEngine owns durable Tasks/Runs/Leases/Approvals/Budgets/Costs. It does not replace DeterministicScheduler or agent runtime.
- MemoryBackend provides retain/recall/reflect over Synapse MemoryStore. Knowledge remains a separate future backend.
- API clients retain compatibility shapes while new descriptors expose honest metadata.

## Invariants
1. No plaintext credentials in provider records.
2. No fake connection successes or fabricated model metadata.
3. No cryptographic digest used as semantic embedding.
4. Exclusive task checkout is atomic and lease-expiry aware.
5. Plugins cannot activate without declared permissions.
6. No external runtime owns Synapse entities.
