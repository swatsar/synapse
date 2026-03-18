# Changelog

Все изменения в проекте Synapse.

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/), версионирование: [Semantic Versioning](https://semver.org/lang/ru/).

---

## [3.2.5] - 2026-03-18

### Исправлено (Bugfix Release)

**Критические синтаксические ошибки (проект не запускался):**
- `synapse/api/storage.py` — исправлена 1-пробельная индентация во всём файле; Python не мог парсить блоки методов `AsyncSafeDict` и `AsyncSafeList`
- `synapse/ui/configurator.py` — исправлен незавершённый строковый литерал на строке 98 (`print("` + реальный перенос строки)
- `tests/api/test_exceptions.py` — та же проблема с 1-пробельной индентацией, все 12 тест-классов недоступны

**Runtime-ошибки (падение при выполнении):**
- `synapse/api/app.py` — добавлен отсутствующий `import os` (использовался `os.getenv()` дважды без импорта)
- `synapse/api/app.py` — удалён дублированный `from synapse.api.middleware import ...` (строки 16 и 42)
- `synapse/api/app.py` — удалён неиспользуемый `from fastapi.staticfiles import StaticFiles`
- `synapse/core/security.py` — исправлен порядок: `from synapse.observability.logger import audit` стоял до docstring модуля
- `synapse/core/security.py` — устранены двойные определения `__init__`, `guard`, `log_action` в `RuntimeGuard` (методы определялись дважды из-за плавающего docstring между ними)
- `synapse/core/security.py` — добавлены недостающие методы: `CapabilityManager.list_capabilities()`, `AuditMechanism.get_event_count()`, `RuntimeGuard.activate()`, `RuntimeGuard.is_active()`
- `synapse/core/security.py` — исправлен вызов `SecurityManager.check_capabilities()`: передавался `context` (dict) вместо `agent_id` (str) в `CapabilityManager`
- `synapse/core/security.py` — исправлен вызов `SecurityManager.enforce_permissions()`: сигнатура `enforce(principal, resource, action)` не соответствовала `PermissionEnforcer.enforce(action, agent_id, ...)`
- `synapse/core/security.py` — удалён неиспользуемый `import hashlib`

**Логические ошибки и заглушки:**
- `synapse/governance/capability_policy.py` — `PROTOCOL_VERSION` объявлялся до docstring модуля
- `synapse/ecosystem/api_gateway.py` — метод `broadcast()` был пустой заглушкой `pass`; реализован через `asyncio.gather` с обработкой ошибок
- `synapse/policy/policy_validator.py` — `_validate_dependency_graph()` — заглушка; реализована проверка дублирующихся step ID
- `synapse/core/orchestrator.py` — раскомментирована и реализована проверка capabilities; реализовано создание checkpoint
- `synapse/agents/governor.py` — ветка `optimize_skill` реализована через вызов `self.optimizer`
- `synapse/agents/runtime/agent.py` — метод `learn()` реализован: сохранение опыта в `self.memory`
- `synapse/security/execution_guard.py` — capability validation реализована через `CapabilityManager.check_capabilities()`
- 12 файлов — голые `except:` заменены на `except Exception:` (PEP8 E722)

---

## [3.2.4] - 2026-02-24

### Добавлено
- **Phase 8: Zero-Trust Fabric** — начальная реализация
  - `TrustIdentityRegistry` — детерминированная регистрация узлов
  - `ExecutionAuthorizationToken` — токены авторизации выполнения
  - `RemoteAttestationVerifier` — верификация удалённых узлов
  - `TrustPolicyEngine` — движок политик доверия
  - `ZeroTrustExecutionEnforcement` — enforcement без неявного доверия
- 18 тестов для Phase 8 (100% pass)

### Изменено
- Перемещены completion reports в `docs/reports/phase-reports/`
- Обновлён README.md

---

## [3.2.3] - 2026-02-23

### Добавлено
- **Phase 7.2: Ecosystem Layer**
  - `DomainPacks` — пакеты доменов
  - `CapabilityMarketplace` — рынок capabilities
  - `ExternalAPIGateway` — внешний API-шлюз (REST + WebSocket)
- 89 тестов для Phase 7.2

---

## [3.2.2] - 2026-02-23

### Добавлено
- **Phase 7.1: Orchestrator Control Plane**
  - `OrchestratorControlAPI` — API управления оркестратором
  - `ExecutionProvenanceRegistry` — реестр происхождения выполнения
  - `ClusterMembershipAuthority` — авторитет членства кластера
- 67 тестов (97% coverage)

---

## [3.2.1] - 2026-02-21

### Добавлено
- **Phase 7: Control Plane**
  - Web UI Control Plane
  - Orchestrator Chat Interface
- 167 тестов

---

## [3.2.0] - 2026-02-21

### Добавлено
- **Phase 6: Deterministic Runtime**
  - Детерминированное выполнение через `execution_seed`
  - Replay системы для воспроизводимости
  - Tenant-level изоляция

---

## [3.1.0] - 2026-02-20

### Добавлено
- **Phase 5: Reliability & Observability**
  - `SnapshotManager`, `RollbackManager`, `FaultTolerance`
  - Prometheus metrics, structured logging
  - 142 теста

---

## [3.0.0] - 2026-02-18

### Добавлено
- **Phase 4: Self-Evolution**
  - `SelfImprovementEngine`, `SkillEvolutionEngine`
  - 6-статусный lifecycle навыков (GENERATED→ARCHIVED)
  - Предиктивная автономия

---

## [2.0.0] - 2026-02-15

### Добавлено
- **Phase 3: Perception & Memory**
  - `MemoryStore` (vector + SQL)
  - `DistributedMemoryStore`
  - ChromaDB integration

---

## [1.1.0] - 2026-02-12

### Добавлено
- **Phase 2: Execution & Security**
  - `CapabilityManager` с wildcard-scope токенами
  - `ExecutionGuard`, `IsolationPolicy`
  - `AuditMechanism`

---

## [1.0.0] - 2026-02-10

### Добавлено
- **Phase 1: Core Skeleton**
  - `Orchestrator`, `SecurityManager`, `DeterministicSeedManager`
  - FastAPI REST API
  - LLM Router с fallback
  - Telegram/Discord коннекторы
  - Base skill lifecycle
