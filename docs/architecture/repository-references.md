# Repository references (clean-room architectural use)

| Repository | TAKE | ADAPT | IGNORE | License/provenance posture | Synapse strategy |
|---|---|---|---|---|---|
| DeepSeek Harness | custom provider onboarding and protocol-specific UX | provider API route workflow | runtime/control plane | reference only; no copied code | ProviderRegistry + adapter contracts |
| Hermes Agent | ProviderProfile, secret resolution, extensible backends | plugin service registration | agent loop | reference only; verify upstream license before any code | clean-room profile/credential interfaces |
| Paperclip | durable work semantics, leases, budgets, heartbeats | atomic checkout | second scheduler/control plane | reference only | WorkEngine inside Synapse control plane |
| Hindsight | retain/recall/reflect, memory scopes | lexical fallback and reflection shape | independent memory product | reference only | MemoryBackend over MemoryStore |
| WeKnora | ingestion/retrieval/citations ideas | future KnowledgeBackend | second user/KB source of truth | reference only | future adapter, separate from Memory |
| Spynel | HarnessAdapter boundary | execution adapters | another orchestrator | reference only | adapters called by Synapse runs |
| Agent Zero / a0-plugins | plugin hub UX and index/review flow | manifest discovery | Agent Zero loop | reference only | future marketplace over PluginRuntime |
| CUA / browser extension | backend abstraction and tab/desktop leases | CapabilityManager integration | direct security bypass | reference only | BrowserBackend/ComputerUseBackend |
| Aider / Serena / Tree-sitter | symbol-aware context and code intelligence | context compiler | full-repository prompting | reference only | future CodeContextEngine |
| Cedar / OPA | policy-as-code patterns | PolicyEngine adapter | mandatory sidecar | reference only | extend existing capability layer |
