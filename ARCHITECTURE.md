# Архитектура Synapse

**Protocol Version:** 1.0 | **Spec Version:** 3.1 | **Версия:** 3.2.5

---

## Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNAPSE PLATFORM v3.2.5                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Control     │  │ Orchestrator │  │   Agent      │          │
│  │  Plane       │──│    Mesh      │──│   Runtime    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  ┌───────────────────────────────────────────────────┐          │
│  │          CAPABILITY SECURITY LAYER                │          │
│  │  CapabilityManager · ExecutionGuard · AuditMech   │          │
│  └───────────────────────────────────────────────────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  ┌───────────────────────────────────────────────────┐          │
│  │        DETERMINISTIC EXECUTION FABRIC             │          │
│  │  DeterministicSeedManager · ReplayManager         │          │
│  └───────────────────────────────────────────────────┘          │
│         │                 │                 │                   │
│  ┌──────┴──────┐  ┌───────┴──────┐  ┌──────┴──────┐           │
│  │ Execution   │  │   Memory     │  │   Policy    │           │
│  │   Nodes     │  │    Vault     │  │   Engine    │           │
│  └─────────────┘  └──────────────┘  └─────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Слои платформы

### Layer 1: Control Plane (`synapse/control_plane/`)

Управляет кластером и распределением задач:

- `ClusterManager` — реестр узлов и их статус
- `DeterministicScheduler` — детерминированное планирование с `execution_seed`
- `OrchestratorMesh` — маршрутизация между оркестраторами
- `TenantScheduler` — multi-tenant планировщик задач

### Layer 2: Capability Security Layer (`synapse/core/security.py`, `synapse/governance/`)

```
CapabilityManager      — выдача, проверка, отзыв токенов
  └── CapabilityToken  — wildcard scope + TTL
PermissionEnforcer     — enforce(action, agent_id)
AuditMechanism         — emit_event(), get_events(), get_event_count()
RuntimeGuard           — guard(action, capabilities, agent_id)
SecurityManager        — единый фасад для всех security-операций
```

### Layer 3: Deterministic Execution Fabric (`synapse/core/`)

```
DeterministicSeedManager   — детерминированные RNG seeds
DeterministicIDGenerator   — воспроизводимые UUIDs
Orchestrator               — 10-шаговый когнитивный цикл
CheckpointManager          — сохранение состояния
RollbackManager            — откат к предыдущему состоянию
```

### Layer 4: Agent Runtime (`synapse/agents/`)

```
agents/
├── runtime/agent.py    — BaseAgent: perceive→recall→plan→act→learn
├── supervisor/         — SupervisorAgent: координация подагентов
├── planner.py          — Планирование задач
├── critic.py           — Оценка качества выполнения
├── developer.py        — Разработка и тестирование навыков
├── governor.py         — Управление политиками и ресурсами
└── guardian.py         — Безопасность и мониторинг
```

### Layer 5: Skill System (`synapse/skills/`)

6-статусный lifecycle навыков:

```
GENERATED → TESTED → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
```

```
skills/
├── base.py              — BaseSkill (abstract)
├── builtins/
│   ├── read_file.py     — FileReadSkill
│   ├── write_file.py    — FileWriteSkill
│   └── web_search.py    — WebSearchSkill
├── dynamic/registry.py  — SkillRegistry с lifecycle
├── autonomy/            — Автономное выполнение
├── evolution/           — Саморазвитие навыков
├── predictive/          — Предиктивная автономия
└── self_improvement/    — Self-improvement engine
```

### Layer 6: LLM Abstraction (`synapse/llm/`)

```
LLMRouter
├── register(provider)              — регистрация провайдера
├── select_provider(capability)     — выбор по приоритету
├── generate(prompt, **kwargs)      — генерация с fallback
└── set_safe_provider(name)         — провайдер для safe mode
```

Приоритеты: `PRIMARY=1`, `FALLBACK=2`, `SAFE=3`

### Layer 7: Memory (`synapse/memory/`)

```
MemoryStore               — SQL + vector store
DistributedMemoryStore    — распределённая память кластера
```

### Layer 8: Zero-Trust Fabric (`synapse/zero_trust/`)

Phase 8 (in progress):
```
identity.py      — TrustIdentityRegistry
attestation.py   — RemoteAttestationVerifier
policy.py        — TrustPolicyEngine
enforcement.py   — ZeroTrustEnforcement
authorization.py — ExecutionAuthorizationToken
```

---

## Когнитивный цикл агента (10 шагов)

```python
# synapse/agents/runtime/agent.py

async def run_once(self):
    # 1. PERCEIVE — получение входящего события
    event = await self.perceive()

    # 2. RECALL — извлечение релевантной памяти
    context = await self.recall(event)

    # 3. PLAN — генерация плана действий через LLM
    plan = await self.plan(event, context)

    # 4. SECURITY — проверка capabilities + оценка риска
    security_result = await self.security_check(plan)
    if not security_result["approved"]:
        return

    # 5. APPROVE — Human-in-the-Loop для risk_level ≥ 3
    if plan.risk_level >= 3:
        approved = await self.request_approval(plan)
        if not approved:
            return

    # 6. CHECKPOINT — сохранение состояния
    await self.checkpoint(event, plan)

    # 7. ACT — выполнение в sandbox через ExecutionGuard
    result = await self.act(plan)

    # 8. OBSERVE — анализ результата
    observation = await self.observe(result)

    # 9. EVALUATE — оценка качества через CriticAgent
    evaluation = await self.evaluate(observation)

    # 10. LEARN — консолидация в память
    await self.learn(evaluation)
```

---

## Потоки данных

### Входящий запрос (REST)

```
Client → FastAPI → RateLimitMiddleware → SecurityHeadersMiddleware
       → RequestLoggingMiddleware → api_key_auth → Route Handler
       → Orchestrator → Agent → Skill → Response
```

### Capability check

```
Skill.execute()
  → ExecutionGuard.validate_capabilities()
  → CapabilityManager.check_capabilities(required, agent_id)
  → CapabilityToken.match_capability() [wildcard/exact/prefix]
  → AuditMechanism.emit_event("capability_checked"|"capability_denied")
  → SecurityCheckResult(approved: bool)
```

### Skill lifecycle

```
LLM generates code
  → SkillRegistry.register(status=GENERATED)
  → AutoTest passes → status=TESTED
  → SecurityScan passes → status=VERIFIED
  → Manual activation → status=ACTIVE
  → Obsolete → status=DEPRECATED
  → Cleanup → status=ARCHIVED (terminal)
```

---

## Технологический стек

| Слой | Технология |
|------|------------|
| API | FastAPI + Uvicorn |
| Валидация | Pydantic v2 |
| LLM | litellm (multi-provider) |
| ORM | SQLAlchemy 2.0 (async) |
| Vector DB | ChromaDB / Qdrant |
| Cache | Redis |
| Metrics | Prometheus + Grafana |
| Logging | structlog |
| Containers | Docker / Docker Compose |
| CI/CD | GitHub Actions |
| Security | Capability tokens + Zero-Trust |
