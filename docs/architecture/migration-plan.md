# Migration plan

## Completed verticals
1. Stabilization: suite green; memory default changed to explicit `:memory:`; governance errors become failed results; isolation test aligned with security model.
2. Foundation: CredentialStore, ProviderRegistry, ApiMode adapters, ModelDescriptor/ModelCatalog, PricingCatalog, PluginManifest/PluginRuntime.
3. API compatibility: provider routes now use JsonProfileStore/ProviderRegistry and real connection/model probes.
4. WorkEngine: SQLite-backed task/run ledger, atomic checkout, heartbeat, lease release, approvals, budgets, cost records.
5. Memory: MemoryBackend and SynapseNativeMemory retain/recall/reflect over MemoryStore.

## Next migrations
- Replace JsonProfileStore with the existing production SQLAlchemy persistence through a non-destructive migration.
- Add provider/model/plugin tables and indexes; backfill provider references without copying secrets.
- Add WorkEngine tables to the production database and preserve legacy task identifiers.
- Add KnowledgeBackend and HarnessAdapter behind feature flags.
- Add conformance and security evaluation gates before activation.

## Rollback
All new components are adapter boundaries. Disable their feature flag and continue using the existing route/runtime contracts. No destructive migration is required by the completed verticals.
