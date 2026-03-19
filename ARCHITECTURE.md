# Архитектура Synapse

**Protocol Version:** 1.0 | **Spec Version:** 3.1 | **Версия:** 3.4.1

---

## Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNAPSE PLATFORM v3.4.1                      │
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
│  │  4-Level Trust Model · CapabilityScope Enum       │          │
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
│  ┌───────────────────────────────────────────────────┐          │
│  │     ENVIRONMENT ABSTRACTION LAYER                 │          │
│  │  WindowsAdapter · LinuxAdapter · MacOSAdapter     │          │
│  └───────────────────────────────────────────────────┘          │
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
  └── CapabilityScope  — enum: FILESYSTEM_READ, FILESYSTEM_WRITE, NETWORK_HTTP,
                         PROCESS_SPAWN, DEVICE_IOT, SYSTEM_INFO
PermissionEnforcer     — enforce(action, agent_id)
AuditMechanism         — emit_event(), get_events(), get_event_count()
RuntimeGuard           — guard(action, capabilities, agent_id)
SecurityManager        — единый фасад для всех security-операций
```

### Layer 3: Execution Trust Model (`synapse/core/isolation_policy.py`)

4-уровневая модель доверия к исполняемому коду:

| Trust Level | Isolation | Источник кода | Права |
|-------------|-----------|---------------|-------|
| **Trusted** | subprocess | Встроенные навыки ядра | Полный доступ через capability-токены |
| **Verified** | subprocess (isolated) | Прошли автотесты + AST-анализ | Только заявленные capabilities |
| **Unverified** | sandbox (strict) | Только что сгенерированы LLM | Только вычисления, нет I/O |
| **Human-Approved** | subprocess (extended) | Одобрены пользователем | Расширенный доступ по запросу |

### Layer 4: Deterministic Execution Fabric (`synapse/core/`)

```
DeterministicSeedManager   — детерминированные RNG seeds
DeterministicIDGenerator   — воспроизводимые UUIDs
Orchestrator               — 8-шаговый когнитивный цикл
CheckpointManager          — сохранение состояния
RollbackManager            — откат к предыдущему состоянию
```

### Layer 5: Agent Runtime (`synapse/agents/`)

```
agents/
├── runtime/agent.py    — BaseAgent: perceive→recall→plan→act→learn
├── supervisor/         — SupervisorAgent: координация подагентов
├── planner.py          — Планирование задач
├── critic.py           — Оценка качества выполнения (метапознание)
├── developer.py        — Разработка и тестирование навыков
├── forecaster.py       — Прогнозирование
├── governor.py         — Управление политиками и ресурсами
└── guardian.py         — Безопасность и мониторинг
```

### Layer 6: Skill System (`synapse/skills/`)

6-статусный lifecycle навыков:

```
GENERATED → TESTED → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
```

```
skills/
├── base.py              — BaseSkill (abstract), SkillTrustLevel
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

### Layer 7: LLM Abstraction (`synapse/llm/`)

```
LLMRouter
├── register(provider)              — регистрация провайдера
├── select_provider(capability)     — выбор по приоритету
├── generate(prompt, **kwargs)      — генерация с fallback
└── set_safe_provider(name)         — провайдер для safe mode

LLMModelRouter                      — task-based routing, cost tracking, failover
ChainSystem                         — LLMChain, SequentialChain, ParallelChain, RouterChain
OutputParsers                       — JSON, Pydantic, List, Boolean, Structured
```

Приоритеты: `PRIMARY=1`, `FALLBACK=2`, `SAFE=3`

### Layer 8: Memory (`synapse/memory/`)

```
MemoryStore               — SQL-backed: short_term, long_term, episodic
VectorStore               — ChromaDB/Qdrant: семантическая память
DistributedMemoryStore    — распределённая память кластера
```

### Layer 9: Environment Abstraction (`synapse/environment/`)

Кроссплатформенный слой, скрывающий специфику ОС:

```
environment/
├── base.py                 — EnvironmentAdapter (abstract interface)
├── local_os.py             — Локальное окружение
├── docker_env.py           — Docker-окружение
└── adapters/
    ├── factory.py          — Автоматический выбор адаптера по ОС
    ├── windows.py          — WindowsAdapter
    ├── linux.py            — LinuxAdapter
    └── macos.py            — MacOSAdapter
```

### Layer 10: Zero-Trust Fabric (`synapse/zero_trust/`)

Phase 8 (in progress):
```
identity.py      — TrustIdentityRegistry
attestation.py   — RemoteAttestationVerifier
policy.py        — TrustPolicyEngine
enforcement.py   — ZeroTrustEnforcement
authorization.py — ExecutionAuthorizationToken
```

---

## Когнитивный цикл агента (8 шагов)

Реализация спецификации: **Восприятие → Воспоминание → Планирование → Безопасность → Действие → Наблюдение → Оценка → Обучение**

```python
# synapse/core/orchestrator.py

async def run_cognitive_cycle(self, event):
    # 1. PERCEIVE — получение входящего события
    perceived = await self.perceive(event)

    # 2. RECALL — извлечение релевантной памяти
    recalled = await self.recall(perceived)

    # 3. PLAN — генерация плана действий через LLM
    plan = await self.plan(perceived, recalled)

    # 4. SECURITY — проверка capabilities + оценка риска
    security_result = await self.security_check(plan)
    if not security_result["approved"]:
        return CognitiveCycleResult(success=False, error="security_denied")

    # 5. ACT — выполнение в sandbox/subprocess/container через ExecutionGuard
    action_result = await self.act(plan)

    # 6. OBSERVE — анализ результата
    observation = await self.observe(action_result)

    # 7. EVALUATE — оценка качества через CriticAgent
    evaluation = await self.evaluate(observation)

    # 8. LEARN — консолидация в память + self-improvement
    learning = await self.learn(evaluation)

    return CognitiveCycleResult(success=True, ...)
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
  → ExecutionGuard.check_execution_allowed(skill, context)
  → IsolationPolicy.get_required_isolation(trust_level, risk_level)
  → CapabilityManager.check_capability(context, cap)
  → AuditMechanism → audit log
  → ExecutionCheckResult(allowed, requires_approval, required_isolation)
```

### Skill lifecycle

```
LLM generates code
  → SkillRegistry.register(status=GENERATED)
  → AutoTest passes → status=TESTED
  → SecurityScan (AST analysis) passes → status=VERIFIED
  → Human approval → status=ACTIVE
  → Low success_rate → status=DEPRECATED
  → Cleanup → status=ARCHIVED (terminal)
```

---

## Технологический стек

| Слой | Технология |
|------|------------|
| API | FastAPI + Uvicorn |
| Валидация | Pydantic v2 |
| LLM | litellm (100+ провайдеров) |
| ORM | SQLAlchemy 2.0 (async) |
| Vector DB | ChromaDB / Qdrant |
| Cache | Redis |
| Metrics | Prometheus + Grafana |
| Logging | structlog |
| Containers | Docker / Docker Compose |
| Security | Capability tokens + 4-Level Trust Model + Zero-Trust |
| Cross-platform | Environment Adapters (Windows/Linux/macOS) |
