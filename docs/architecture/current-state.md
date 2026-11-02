# Synapse current state

## Audit snapshot
- Synapse already has one control-plane family under `synapse/control_plane`, a deterministic scheduler, agent runtime, capability security, durable SQLite memory, and FastAPI routes.
- Before this modernization, provider routes used an in-memory dictionary, discarded API keys, returned a fake connection success, and fabricated a 128000 context window.
- `synapse/llm/provider.py` fabricated SHA-512 vectors when embeddings failed. This was removed; lexical BM25 fallback is now explicit.
- There were two overlapping LLM router implementations. `synapse/llm/router.py` is now a compatibility re-export of the canonical provider router.
- Existing compliance tests found three stabilization defects: SQLite temporary-file latency, exception leakage from governance actions, and a contradictory unverified-isolation assertion. All were fixed.

## Existing ownership boundaries
| Concern | Existing owner | Modernization boundary |
|---|---|---|
| scheduling | `synapse/control_plane` | WorkEngine does not schedule; it owns durable work state and leases |
| capabilities | `synapse/security`, `synapse/governance` | Plugin permissions are declarations evaluated before activation |
| memory | `synapse/memory` | MemoryBackend delegates to existing MemoryStore; no second store |
| LLM transport | LiteLLM in `synapse/llm` | ProviderRegistry owns profiles; adapters own wire-protocol calls |
| API | FastAPI `synapse/api` | Routes remain compatibility surface over registries |

## Baseline
- 1,741 tests collected initially.
- Stabilization baseline: 1,730 passed, 3 failed, 8 skipped.
- After fixes: 1,780 passed, 8 skipped in the subsequent full run; one architecture allowlist test was updated for the approved `plugins` boundary and reverified.
