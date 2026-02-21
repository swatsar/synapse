# Phase 1.2: Secure Execution Pipeline - Architectural Specification

**Version:** 1.0
**Date:** 2026-02-21
**Status:** Specification Complete
**Depends on:** Phase 1.1 - Capability Security Layer v1

---

## 🎯 ЦЕЛЬ ЭТАПА

Обеспечить, чтобы:

✔ ни один шаг workflow не выполнялся без capability
✔ enforcement происходил на уровне runtime
✔ security был встроен в execution pipeline
✔ поведение оставалось deterministic
✔ observability фиксировала каждое решение

---

## 🧱 АРХИТЕКТУРНЫЕ КОМПОНЕНТЫ

### 1. SecureExecutionContext

**Ответственность:** Контекст выполнения шага workflow.

```python
class SecureExecutionContext(BaseModel):
    """Контекст безопасного выполнения."""
    
    # Идентификация
    workflow_id: str
    step_id: str
    agent_id: str
    
    # Capability
    required_capability: str
    capability_scope: str
    
    # Audit
    audit_reference: str
    trace_id: str
    
    # Metadata
    created_at: str
    protocol_version: str = "1.0"
    
    # Execution
    action: Callable
    action_params: Dict[str, Any]
```

**Инварианты:**
- Не может быть создан без `required_capability`
- `trace_id` обязателен для observability
- `audit_reference` связывает с AuditMechanism

---

### 2. SecureWorkflowExecutor

**Ответственность:** Исполнение шагов workflow с enforcement.

```python
class SecureWorkflowExecutor:
    """Безопасный исполнитель workflow."""
    
    def __init__(
        self,
        capability_manager: CapabilityManager,
        runtime_guard: RuntimeGuard,
        audit: AuditMechanism
    ):
        self.capability_manager = capability_manager
        self.guard = runtime_guard
        self.audit = audit
    
    async def execute_step(
        self,
        context: SecureExecutionContext
    ) -> ExecutionResult:
        """Исполнить шаг workflow."""
        
        # 1. Публикация события запроса
        await self.audit.emit_event(
            event_type="step_execution_requested",
            details={
                "workflow_id": context.workflow_id,
                "step_id": context.step_id,
                "agent_id": context.agent_id,
                "capability": context.required_capability
            }
        )
        
        # 2. Проверка capability через guard
        result = await self.guard.guard(
            action=context.action,
            capabilities=[context.required_capability],
            agent_id=context.agent_id,
            capability_manager=self.capability_manager,
            audit=self.audit
        )
        
        # 3. Публикация результата
        if result.allowed:
            await self.audit.emit_event(
                event_type="step_execution_authorized",
                details={...}
            )
        else:
            await self.audit.emit_event(
                event_type="step_execution_denied",
                details={...}
            )
        
        return ExecutionResult(...)
```

**Инварианты:**
- Никогда не выполняет действие напрямую
- Всегда использует RuntimeGuard
- Всегда публикует observability события

---

### 3. AgentCapabilityBinding

**Ответственность:** Явное связывание агента и capability.

```python
class AgentCapabilityBinding(BaseModel):
    """Связывание агента с capability."""
    
    id: str
    agent_id: str
    capability: str
    scope: str
    constraints: Dict[str, Any]
    
    # Lifecycle
    created_at: str
    expires_at: Optional[str]
    is_active: bool = True
    
    # Audit
    created_by: str
    protocol_version: str = "1.0"


class BindingManager:
    """Менеджер связываний."""
    
    async def bind(
        self,
        agent_id: str,
        capability: str,
        scope: str,
        created_by: str
    ) -> AgentCapabilityBinding:
        """Создать связывание."""
        pass
    
    async def unbind(self, binding_id: str) -> bool:
        """Удалить связывание."""
        pass
    
    async def get_bindings(
        self,
        agent_id: str
    ) -> List[AgentCapabilityBinding]:
        """Получить все связывания агента."""
        pass
    
    async def has_binding(
        self,
        agent_id: str,
        capability: str
    ) -> bool:
        """Проверить наличие связывания."""
        pass
```

**Инварианты:**
- Агент не может выполнить действие без binding
- Binding можно отозвать
- Binding имеет срок действия

---

### 4. Execution Observability Events

**Обязательные события:**

```python
# 1. step_execution_requested
{
    "event": "step_execution_requested",
    "workflow_id": "wf_123",
    "step_id": "step_456",
    "agent_id": "agent_001",
    "capability": "fs:read:/workspace/**",
    "timestamp": "2026-02-21T12:00:00Z",
    "protocol_version": "1.0"
}

# 2. step_execution_authorized
{
    "event": "step_execution_authorized",
    "workflow_id": "wf_123",
    "step_id": "step_456",
    "agent_id": "agent_001",
    "capability": "fs:read:/workspace/**",
    "binding_id": "bind_789",
    "timestamp": "2026-02-21T12:00:01Z",
    "protocol_version": "1.0"
}

# 3. step_execution_denied
{
    "event": "step_execution_denied",
    "workflow_id": "wf_123",
    "step_id": "step_456",
    "agent_id": "agent_001",
    "capability": "fs:read:/workspace/**",
    "reason": "no_binding_found",
    "timestamp": "2026-02-21T12:00:01Z",
    "protocol_version": "1.0"
}

# 4. step_execution_completed
{
    "event": "step_execution_completed",
    "workflow_id": "wf_123",
    "step_id": "step_456",
    "agent_id": "agent_001",
    "capability": "fs:read:/workspace/**",
    "result": "success",
    "duration_ms": 150,
    "timestamp": "2026-02-21T12:00:02Z",
    "protocol_version": "1.0"
}
```

---

## 🔐 ИНВАРИАНТЫ БЕЗОПАСНОСТИ

| Инвариант | Реализация | Проверка |
|-----------|------------|----------|
| Execution невозможен без capability | SecureWorkflowExecutor использует RuntimeGuard | test_execution_without_capability_denied |
| Capability проверяется до выполнения | guard.guard() перед action() | test_capability_checked_before_execution |
| Любой отказ фиксируется | audit.emit_event("step_execution_denied") | test_denial_is_logged |
| Агент не может обойти guard | Нет прямого вызова action | test_no_bypass_possible |
| Execution pipeline детерминирован | execution_seed в контексте | test_deterministic_execution |

---

## 🧪 ТЕСТОВЫЕ КАТЕГОРИИ

### Security Tests

1. `test_execution_without_capability_denied`
2. `test_agent_without_binding_denied`
3. `test_unauthorized_action_denied`
4. `test_no_bypass_possible`

### Determinism Tests

1. `test_deterministic_execution_same_input_same_output`
2. `test_replay_execution_identical_outcome`

### Integration Tests

1. `test_workflow_step_through_guard`
2. `test_audit_events_published`
3. `test_full_execution_pipeline`

### Concurrency Tests

1. `test_parallel_steps_isolation`
2. `test_concurrent_binding_operations`

---

## ⚙️ ТРЕБОВАНИЯ К РЕАЛИЗАЦИИ

### Dependency Injection

```python
# ✅ Правильно
class SecureWorkflowExecutor:
    def __init__(
        self,
        capability_manager: CapabilityManager,
        runtime_guard: RuntimeGuard,
        audit: AuditMechanism
    ):
        ...

# ❌ Неправильно
class SecureWorkflowExecutor:
    def __init__(self):
        self.capability_manager = get_global_manager()  # Глобальное состояние!
```

### No Global State

```python
# ✅ Правильно
executor = SecureWorkflowExecutor(
    capability_manager=manager,
    runtime_guard=guard,
    audit=audit
)

# ❌ Неправильно
executor = SecureWorkflowExecutor()  # Неявные зависимости
```

### Replay Support

```python
# Execution должен быть воспроизводим
context1 = SecureExecutionContext(
    workflow_id="wf_123",
    step_id="step_456",
    agent_id="agent_001",
    required_capability="fs:read",
    execution_seed=42,
    ...
)

context2 = SecureExecutionContext(
    workflow_id="wf_123",
    step_id="step_456",
    agent_id="agent_001",
    required_capability="fs:read",
    execution_seed=42,  # Тот же seed
    ...
)

# Результаты должны быть идентичны
result1 = await executor.execute_step(context1)
result2 = await executor.execute_step(context2)
assert result1 == result2
```

---

## 📊 ПОКРЫТИЕ КОДА

**Цель:** ≥ 90%

**Обязательные модули:**
- `synapse/core/execution.py` - SecureExecutionContext, SecureWorkflowExecutor
- `synapse/core/binding.py` - AgentCapabilityBinding, BindingManager

---

## 📂 СТРУКТУРА ФАЙЛОВ

```
synapse/
├── core/
│   ├── execution.py      # SecureExecutionContext, SecureWorkflowExecutor
│   ├── binding.py        # AgentCapabilityBinding, BindingManager
│   └── security.py       # (уже существует из Phase 1.1)

tests/
├── test_secure_execution_pipeline.py  # Все тесты Phase 1.2
```

---

## 🧭 КРИТЕРИЙ ЗАВЕРШЕНИЯ

Integration считается завершённой, если:

✔ ни один workflow step не выполняется без capability
✔ enforcement встроен в execution pipeline
✔ execution воспроизводим
✔ audit фиксирует все решения
✔ все тесты проходят
✔ coverage ≥ 90%

---

**Подпись:** Agent Zero
**Версия протокола:** 1.0
