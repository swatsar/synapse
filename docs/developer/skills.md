# Разработка навыков (Skills)

**Protocol Version:** 1.0 | **Spec Version:** 3.1

---

## Что такое навык

Навык (Skill) — атомарная единица функциональности агента. Каждый навык:
- Наследует `BaseSkill`
- Имеет `SkillManifest` с метаданными
- Объявляет необходимые capabilities
- Выполняется в изолированном окружении
- Логируется через AuditMechanism

---

## Базовая структура навыка

```python
"""My custom skill."""
from typing import Any, Dict
from synapse.skills.base import BaseSkill
from synapse.core.models import SkillManifest, ResourceLimits
from synapse.core.isolation_policy import RuntimeIsolationType


# Манифест
MANIFEST = SkillManifest(
    name="my_skill",
    version="1.0.0",
    description="Описание того, что делает навык",
    capabilities_required=["fs:read:/workspace/**"],
    isolation_type=RuntimeIsolationType.SUBPROCESS,
    resource_limits=ResourceLimits(
        cpu_seconds=30,
        memory_mb=256,
        disk_mb=50,
        network_kb=0      # 0 = нет доступа к сети
    ),
    protocol_version="1.0"
)


class MySkill(BaseSkill):
    """Мой навык."""

    def __init__(self):
        super().__init__(manifest=MANIFEST)

    async def execute(self, context, **kwargs) -> Dict[str, Any]:
        """Выполнить навык.

        Args:
            context: ExecutionContext с agent_id, trace_id и т.д.
            **kwargs: Параметры навыка

        Returns:
            Dict с полем 'result' и 'protocol_version'
        """
        file_path = kwargs.get("path", "/workspace/data.txt")

        # Выполните логику навыка
        with open(file_path) as f:
            content = f.read()

        return {
            "result": content,
            "bytes_read": len(content),
            "protocol_version": "1.0"
        }
```

---

## Встроенные навыки

### `FileReadSkill` — чтение файлов

```python
from synapse.skills.builtins.read_file import FileReadSkill

skill = FileReadSkill()
result = await skill.execute(context, path="/workspace/report.txt")
# result["content"] — содержимое файла
```

**Requires:** `fs:read:<path>`

---

### `FileWriteSkill` — запись файлов

```python
from synapse.skills.builtins.write_file import FileWriteSkill

skill = FileWriteSkill()
result = await skill.execute(
    context,
    path="/workspace/output.txt",
    content="Hello, World!"
)
```

**Requires:** `fs:write:<path>`

---

### `WebSearchSkill` — поиск в интернете

```python
from synapse.skills.builtins.web_search import WebSearchSkill

skill = WebSearchSkill()
result = await skill.execute(context, query="Python async best practices")
# result["results"] — список результатов
```

**Requires:** `network:http:*`

---

## Регистрация навыка

### Через SkillRegistry

```python
from synapse.skills.dynamic.registry import SkillRegistry, SkillLifecycleStatus

registry = SkillRegistry()

# Регистрация
await registry.register(
    skill_id="my_skill_v1",
    manifest=MANIFEST,
    handler=MySkill().execute
)
# Начальный статус: GENERATED

# Перевод по lifecycle
await registry.transition(
    skill_id="my_skill_v1",
    new_status=SkillLifecycleStatus.TESTED
)
await registry.transition(
    skill_id="my_skill_v1",
    new_status=SkillLifecycleStatus.VERIFIED
)
await registry.transition(
    skill_id="my_skill_v1",
    new_status=SkillLifecycleStatus.ACTIVE
)

# Получить активный навык
skill_record = await registry.get_active("my_skill_v1")
```

### Lifecycle переходы

```
GENERATED → TESTED     (после автотестов)
TESTED    → VERIFIED   (после security scan)
VERIFIED  → ACTIVE     (ручная активация)
ACTIVE    → DEPRECATED (при выходе новой версии)
DEPRECATED → ARCHIVED  (финальное состояние)

Откаты:
TESTED    → GENERATED  (провалил повторный тест)
VERIFIED  → TESTED     (провалил повторный скан)
DEPRECATED → ACTIVE    (если новая версия отозвана)
```

---

## Capability декларация

Навык должен явно объявлять все нужные capabilities:

```python
MANIFEST = SkillManifest(
    name="data_processor",
    capabilities_required=[
        "fs:read:/workspace/input/**",   # читать входные файлы
        "fs:write:/workspace/output/**", # писать результаты
        "network:http:api.example.com",  # обращаться к API
    ],
    ...
)
```

Перед выполнением `ExecutionGuard` проверяет что у агента есть все эти capabilities.

---

## Тестирование навыка

```python
"""Tests for MySkill."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from mypackage.skills.my_skill import MySkill


class TestMySkill:

    @pytest.fixture
    def skill(self):
        return MySkill()

    @pytest.fixture
    def context(self):
        ctx = MagicMock()
        ctx.agent_id = "test_agent"
        ctx.trace_id = "trace_001"
        return ctx

    @pytest.mark.asyncio
    async def test_execute_returns_result(self, skill, context, tmp_path):
        # Создать тестовый файл
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = await skill.execute(context, path=str(test_file))

        assert result["result"] == "hello world"
        assert result["protocol_version"] == "1.0"

    @pytest.mark.asyncio
    async def test_execute_missing_file(self, skill, context):
        with pytest.raises(FileNotFoundError):
            await skill.execute(context, path="/nonexistent/file.txt")

    def test_manifest(self, skill):
        assert skill.manifest.name == "my_skill"
        assert "fs:read:/workspace/**" in skill.manifest.capabilities_required
```

---

## Автономная генерация навыков (Self-Evolution)

Агент может создавать навыки автоматически через LLM:

```python
from synapse.skills.evolution.engine import SkillEvolutionEngine

engine = SkillEvolutionEngine(llm_router=router, registry=registry)

# Генерация навыка по описанию задачи
new_skill_id = await engine.evolve(
    task_description="Нужен навык для парсинга CSV файлов",
    context=agent_context
)

# Навык создаётся со статусом GENERATED
# Автотесты → TESTED
# Security scan → VERIFIED
# После одобрения → ACTIVE
```

---

## Размещение файлов навыков

```
skills/              # пользовательские навыки (вне пакета)
├── __init__.py
└── my_custom_skill/
    ├── __init__.py
    ├── skill.py
    └── tests/
        └── test_skill.py

synapse/skills/      # встроенные навыки платформы
├── base.py
├── builtins/
└── dynamic/
```
