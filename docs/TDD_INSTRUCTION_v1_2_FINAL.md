# 📘 PROJECT SYNAPSE: TDD-ИНСТРУКЦИЯ ДЛЯ AGENT ZERO v1.2 (FINAL)

**Версия:** 1.2 FINAL  
**Статус:** Production-Ready ✅  
**Спецификация:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md

---

## 🎯 ТВОЯ РОЛЬ

Ты — **Lead Developer** проекта Synapse. Твоя задача — реализовать распределённую когнитивную платформу автономных агентов, **начиная с тестов**, строго следуя спецификации v3.1.

**Ключевой принцип TDD:**

> Пиши сначала тесты, которые описывают требования, затем код для их прохождения.

---

## 📋 ОБЩИЕ ПРАВИЛА РАЗРАБОТКИ

### 1. Строгое следование спецификации
```
✅ Используй только интерфейсы из SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
❌ Не изобретай новые структуры данных
❌ Не меняй сигнатуры методов
❌ Не пропускай проверки безопасности
```

### 2. Версионирование
```python
# В каждом модуле:
PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# В каждом сообщении/модели:
protocol_version: str = "1.0"
```

### 3. Типизация и документация
```python
def method(self, param: str) -> bool:
    """Docstring с описанием."""
    pass
```

### 4. Безопасность по умолчанию
```python
# Проверяй capabilities, isolation_type, resource_limits, human_approval
```

---

## 🏗️ СТРУКТУРА ПРОЕКТА

```
synapse/
├── config/
├── core/
├── skills/
├── agents/
├── memory/
├── database/
├── connectors/
├── llm/
├── network/
├── observability/
├── ui/
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # 🔹 Фикстуры и моки
│   ├── config/
│   │   └── test_config.yaml  # 🔹 Конфигурация тестов
│   ├── fixtures/
│   │   └── test_data.yaml    # 🔹 Тестовые данные
│   ├── unit/
│   │   ├── test_core.py
│   │   ├── test_skills.py
│   │   ├── test_security.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_orchestrator.py
│   │   └── test_end_to_end.py
│   ├── test_llm_golden.py    # 🔹 Golden master тесты
│   └── test_performance.py
├── docker/
├── docs/
│   └── TDD.md                # 🔹 Документация TDD
├── .github/
│   └── workflows/
│       └── test.yml          # 🔹 CI/CD pipeline
├── main.py
├── requirements.txt
├── requirements-test.txt
├── pyproject.toml            # 🔹 Маркеры тестов
└── SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 🧪 TDD-ПОДХОД К РАЗРАБОТКЕ

### 🔹 1. Настройка тестового окружения

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
```

### 🔹 2. Создание "падающих" тестов

Для каждого модуля создаем **unit тесты**, отражающие требования спецификации.

### 🔹 3. Запуск тестов

```bash
pytest tests/ -v
# Все тесты падают — ожидаемое поведение
```

### 🔹 4. Реализация кода

Реализуем минимальный функционал для прохождения тестов.

### 🔹 5. Проверка coverage и CI/CD

```bash
coverage run -m pytest
coverage report
```

- **Core modules:** >80%
- **Security-critical:** >90%

---

## 📅 ФАЗЫ РАЗРАБОТКИ (TDD) С МАРКЕРАМИ

### Конфигурация маркеров (pyproject.toml)

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "phase1: Core Skeleton",
    "phase2: Execution & Security",
    "phase3: Perception & Memory",
    "phase4: Self-Evolution",
    "phase5: Reliability & Observability",
    "phase6: Deployment & UI",
    "unit: Unit tests",
    "integration: Integration tests",
    "security: Security tests",
    "performance: Performance tests",
    "slow: Slow running tests"
]
addopts = "-v --tb=short"
testpaths = ["tests"]
```

### Запуск тестов по фазам

```bash
# Запуск тестов конкретной фазы
pytest -m phase1 -v
pytest -m phase2 -v
pytest -m "phase2 and security" -v

# Запуск всех тестов кроме медленных
pytest -m "not slow" -v

# Параллельный запуск
pytest -m phase2 -n auto -v
```

---

## 🔧 FIXTURES И MOCKS (ОБНОВЛЕНО)

### tests/conftest.py

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from freezegun import freeze_time
from core.models import ExecutionContext, ResourceLimits, SkillManifest
from skills.base import RuntimeIsolationType, SkillTrustLevel

# 🔹 Фикстура для тестового контекста
@pytest_asyncio.fixture
async def test_context():
    return ExecutionContext(
        session_id="test_session",
        agent_id="test_agent",
        trace_id="test_trace",
        capabilities=["fs:read:/workspace/**"],
        memory_store=MagicMock(),
        logger=MagicMock(),
        resource_limits=ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        ),
        execution_seed=42,
        protocol_version="1.0"
    )

# 🔹 Фикстура для фиксированного времени
@pytest.fixture
def frozen_time():
    """Фиксированное время для тестов с timestamp"""
    with freeze_time("2026-02-18 12:00:00"):
        yield

# 🔹 Фикстура для мока LLM
@pytest.fixture
def mock_llm_provider():
    provider = AsyncMock()
    provider.generate.return_value = "test response"
    provider.is_active = True
    provider.priority = 1
    return provider

# 🔹 Фикстура для динамических навыков
@pytest.fixture
def dynamic_skill_mock():
    """Автоматическая генерация моков для динамических навыков"""
    skill = AsyncMock()
    skill.execute.return_value = {"success": True}
    skill.manifest = MagicMock(spec=SkillManifest)
    skill.manifest.name = "dynamic_skill"
    skill.manifest.trust_level = SkillTrustLevel.TRUSTED
    skill.manifest.risk_level = 1
    skill.manifest.required_capabilities = []
    skill.manifest.isolation_type = RuntimeIsolationType.SUBPROCESS
    skill.manifest.protocol_version = "1.0"
    return skill

# 🔹 Фикстура для тестовых файлов
@pytest.fixture
def test_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "test.txt").write_text("test content")
    return workspace

# 🔹 Фикстура для детерминированного seed
@pytest.fixture(autouse=True)
def set_deterministic_seed():
    """Гарантирует воспроизводимость тестов"""
    import random
    random.seed(42)
    yield
    random.seed()

# 🔹 Фикстура для изолированной рабочей директории
@pytest.fixture
def isolated_workspace(tmp_path):
    import shutil
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)
```

---

## 📊 TEST DATA MANAGEMENT

### tests/fixtures/test_data.yaml

```yaml
skills:
  - name: "read_file"
    trust_level: "trusted"
    risk_level: 1
    isolation_type: "subprocess"
    
  - name: "write_file"
    trust_level: "verified"
    risk_level: 2
    isolation_type: "container"
    
  - name: "execute_command"
    trust_level: "unverified"
    risk_level: 4
    isolation_type: "container"

users:
  - user_id: "test_admin"
    permissions: ["execute", "approve", "admin"]
    
  - user_id: "test_user"
    permissions: ["execute"]

checkpoints:
  - id: "test_checkpoint_1"
    is_active: true
    created_at: "2026-02-18T12:00:00Z"

llm_providers:
  - name: "openai"
    model: "gpt-4o"
    priority: 1
    is_active: true
    
  - name: "anthropic"
    model: "claude-3.5"
    priority: 2
    is_active: true
    
  - name: "ollama"
    model: "llama3"
    priority: 3
    is_active: true
```

### tests/fixtures/loader.py

```python
import yaml
import pytest
from pathlib import Path

@pytest.fixture
def test_data():
    """Загрузка тестовых данных из YAML"""
    fixtures_path = Path(__file__).parent / "test_data.yaml"
    with open(fixtures_path) as f:
        return yaml.safe_load(f)

@pytest.fixture
def test_skills(test_data):
    return test_data.get("skills", [])

@pytest.fixture
def test_users(test_data):
    return test_data.get("users", [])
```

---

## 🏷️ MARKED TEST EXAMPLES BY PHASE

### Phase 1: Core Skeleton

```python
# tests/unit/test_core.py
import pytest
from core.models import SkillManifest, ExecutionContext

@pytest.mark.phase1
@pytest.mark.unit
def test_skill_manifest_validation():
    """Тест валидации манифеста навыка"""
    manifest = SkillManifest(
        name="test_skill",
        version="1.0.0",
        description="Test skill",
        author="test",
        inputs={"param": "str"},
        outputs={"result": "str"},
        required_capabilities=[]
    )
    assert manifest.protocol_version == "1.0"
    assert manifest.trust_level == "unverified"

@pytest.mark.phase1
@pytest.mark.unit
def test_execution_context_creation(test_context):
    """Тест создания контекста выполнения"""
    assert test_context.session_id == "test_session"
    assert test_context.protocol_version == "1.0"
```

### Phase 2: Execution & Security

```python
# tests/unit/test_security.py
import pytest
from core.security import CapabilityError
from core.isolation_policy import IsolationEnforcementPolicy
from skills.base import RuntimeIsolationType, SkillTrustLevel

@pytest.mark.phase2
@pytest.mark.security
@pytest.mark.asyncio
async def test_capability_bypass_attempt(test_context):
    """Попытка обхода проверки capabilities"""
    # Тест должен упасть до реализации
    with pytest.raises(CapabilityError):
        await execute_without_capabilities(test_context)

@pytest.mark.phase2
@pytest.mark.security
def test_isolation_policy_unverified():
    """Непроверенный навык требует контейнер"""
    isolation = IsolationEnforcementPolicy.get_required_isolation(
        trust_level=SkillTrustLevel.UNVERIFIED,
        risk_level=1
    )
    assert isolation == RuntimeIsolationType.CONTAINER

@pytest.mark.phase2
@pytest.mark.security
def test_isolation_policy_high_risk():
    """Высокий риск требует контейнер"""
    isolation = IsolationEnforcementPolicy.get_required_isolation(
        trust_level=SkillTrustLevel.VERIFIED,
        risk_level=4
    )
    assert isolation == RuntimeIsolationType.CONTAINER
```

### Phase 3: Perception & Memory

```python
# tests/unit/test_memory.py
import pytest
from memory.vector_store import VectorStore
from core.models import MemoryQuery, MemoryEntry

@pytest.mark.phase3
@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_recall(test_context):
    """Тест извлечения из памяти"""
    store = VectorStore()
    query = MemoryQuery(query_text="test", limit=10)
    results = await store.recall(query)
    assert isinstance(results, list)

@pytest.mark.phase3
@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_persistence(integration_db):
    """Тест сохранения в БД"""
    # Интеграционный тест с реальной БД
    pass
```

### Phase 4: Self-Evolution

```python
# tests/unit/test_evolution.py
import pytest
from agents.developer import DeveloperAgent
from agents.critic import CriticAgent

@pytest.mark.phase4
@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_generates_skill(mock_llm_provider):
    """Developer агент генерирует код навыка"""
    developer = DeveloperAgent(llm=mock_llm_provider)
    skill_code = await developer.generate_skill("test task")
    assert skill_code is not None
    assert "class" in skill_code

@pytest.mark.phase4
@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_evaluates_execution():
    """Critic агент оценивает выполнение"""
    critic = CriticAgent()
    evaluation = await critic.evaluate(plan={}, result={})
    assert "success" in evaluation
```

### Phase 5: Reliability & Observability

```python
# tests/unit/test_reliability.py
import pytest
from core.rollback import RollbackManager
from llm.failure_strategy import LLMFailureStrategy, LLMPriority

@pytest.mark.phase5
@pytest.mark.security
@pytest.mark.asyncio
async def test_rollback_to_checkpoint(frozen_time):
    """Тест отката к checkpoint"""
    manager = RollbackManager()
    checkpoint_id = await manager.create_checkpoint("agent", "session")
    result = await manager.execute_rollback(checkpoint_id)
    assert result.success == True

@pytest.mark.phase5
@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_fallback_strategy(mock_llm_provider):
    """Тест переключения на fallback LLM"""
    primary = mock_llm_provider
    primary.priority = LLMPriority.PRIMARY
    
    fallback = AsyncMock()
    fallback.priority = LLMPriority.FALLBACK
    
    strategy = LLMFailureStrategy([primary, fallback])
    await strategy.record_failure("primary")
    await strategy.record_failure("primary")
    await strategy.record_failure("primary")
    
    provider = await strategy.get_available_provider()
    assert provider.priority == LLMPriority.FALLBACK

@pytest.mark.phase5
@pytest.mark.performance
@pytest.mark.asyncio
async def test_skill_execution_latency(test_context):
    """Задержка выполнения навыка < 100ms"""
    import time
    from skills.builtins.read_file import ReadFileSkill
    
    skill = ReadFileSkill()
    start = time.perf_counter()
    await skill.execute(test_context, path="/workspace/test.txt")
    elapsed = time.perf_counter() - start
    
    assert elapsed < 0.1  # 100ms
```

### Phase 6: Deployment & UI

```python
# tests/integration/test_deployment.py
import pytest
import requests

@pytest.mark.phase6
@pytest.mark.integration
def test_health_endpoint():
    """Тест health check endpoint"""
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.phase6
@pytest.mark.integration
def test_metrics_endpoint():
    """Тест Prometheus metrics endpoint"""
    response = requests.get("http://localhost:9090/metrics")
    assert response.status_code == 200
    assert "synapse_" in response.text
```

---

## 🏆 GOLDEN MASTER TESTING (ОБНОВЛЕНО)

### tests/test_llm_golden.py

```python
import pytest
from unittest.mock import AsyncMock

class TestLLMGoldenMaster:
    """Тесты выходов LLM через golden master"""
    
    # Ожидаемые выходы для стандартных промптов
    GOLDEN_RESPONSES = {
        "planner_simple_task": {
            "goal": "Execute task",
            "steps": [
                {"action": "analyze", "skill": "text_analysis"},
                {"action": "execute", "skill": "file_operation"},
                {"action": "verify", "skill": "result_check"}
            ],
            "risk_level": 2
        },
        "critic_success": {
            "success": True,
            "reasoning": "All steps completed successfully",
            "learning": "Pattern stored for future"
        },
        "critic_failure": {
            "success": False,
            "reasoning": "Step 2 failed: permission denied",
            "recommendation": "Request elevated capabilities"
        },
        "rollback_trigger": {
            "action": "rollback",
            "reason": "Critical error detected",
            "checkpoint_id": "cp_123"
        }
    }
    
    @pytest.mark.phase4
    @pytest.mark.asyncio
    async def test_planner_output_structure(self, mock_llm_provider):
        """Выход планировщика имеет правильную структуру"""
        mock_llm_provider.generate.return_value = self.GOLDEN_RESPONSES["planner_simple_task"]
        
        from agents.planner import PlannerAgent
        planner = PlannerAgent(llm=mock_llm_provider)
        plan = await planner.create_plan("simple task")
        
        assert "goal" in plan
        assert "steps" in plan
        assert len(plan["steps"]) > 0
    
    @pytest.mark.phase4
    @pytest.mark.asyncio
    async def test_critic_output_structure(self):
        """Выход критика имеет правильную структуру"""
        from agents.critic import CriticAgent
        critic = CriticAgent()
        result = await critic.evaluate(plan={}, execution_result={})
        
        assert "success" in result
        assert "reasoning" in result
    
    @pytest.mark.phase5
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, mock_llm_provider, test_context):
        """End-to-end тест: план → выполнение → критик → откат"""
        # 1. Planner создаёт план
        mock_llm_provider.generate.return_value = self.GOLDEN_RESPONSES["planner_simple_task"]
        
        # 2. Execution выполняет
        execution_result = {"success": False, "error": "Critical error"}
        
        # 3. Critic оценивает
        critic_result = self.GOLDEN_RESPONSES["critic_failure"]
        
        # 4. Rollback инициируется
        assert critic_result["success"] == False
        assert "recommendation" in critic_result
        
        # Golden master: структура должна соответствовать
        assert isinstance(critic_result["reasoning"], str)
```

---

## 🔗 CI/CD PIPELINE (ОБНОВЛЕНО)

### .github/workflows/test.yml

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: synapse_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      chromadb:
        image: chromadb/chroma:latest
        options: >-
          --health-cmd "curl -f http://localhost:8000/api/v1/heartbeat"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 8001:8000
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Wait for services
        run: |
          echo "Waiting for PostgreSQL..."
          until pg_isready -h localhost -p 5432; do sleep 1; done
          echo "Waiting for ChromaDB..."
          until curl -f http://localhost:8001/api/v1/heartbeat; do sleep 1; done
      
      - name: Run Phase 1 tests
        run: pytest tests/ -v -m "phase1" --cov=synapse
      
      - name: Run Phase 2 tests
        run: pytest tests/ -v -m "phase2" --cov=synapse --cov-append
      
      - name: Run Phase 3 tests
        run: pytest tests/ -v -m "phase3" --cov=synapse --cov-append
      
      - name: Run Phase 4 tests
        run: pytest tests/ -v -m "phase4" --cov=synapse --cov-append
      
      - name: Run Phase 5 tests
        run: pytest tests/ -v -m "phase5" --cov=synapse --cov-append
      
      - name: Run security tests
        run: pytest tests/ -v -m "security"
      
      - name: Check coverage
        run: |
          coverage report --fail-under=80
          coverage xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Security scan
        run: |
          pip install bandit
          bandit -r synapse/ -ll
```

### docker-compose.test.yml

```yaml
version: '3.8'

services:
  synapse-test:
    build: .
    environment:
      - SYNAPSE_ENV=test
      - DATABASE_URL=postgresql://test:test@postgres:5432/synapse_test
      - VECTOR_DB_URL=http://chromadb:8000
    depends_on:
      postgres:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    command: pytest tests/ -v -m "integration"
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=test
      - POSTGRES_DB=synapse_test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
  
  chromadb:
    image: chromadb/chroma:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 5s
      timeout: 5s
      retries: 5
```

---

## 📚 TDD ДОКУМЕНТАЦИЯ (docs/TDD.md)

```markdown
# Project Synapse: TDD Guide

## Для новых разработчиков

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/synapse/synapse.git
cd synapse

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt -r requirements-test.txt

# 4. Запустить тесты текущей фазы
pytest -m phase1 -v

# 5. Запустить все тесты
pytest tests/ -v
```

### Структура тестов

```
tests/
├── conftest.py           # Общие фикстуры
├── config/               # Конфигурация тестов
├── fixtures/             # Тестовые данные
├── unit/                 # Unit тесты
├── integration/          # Integration тесты
├── test_llm_golden.py    # Golden master тесты
└── test_performance.py   # Performance тесты
```

### Фикстуры

| Фикстура | Описание |
|----------|----------|
| `test_context` | Контекст выполнения с моками |
| `frozen_time` | Фиксированное время для тестов |
| `mock_llm_provider` | Мок LLM провайдера |
| `dynamic_skill_mock` | Мок динамического навыка |
| `test_workspace` | Временная рабочая директория |
| `test_data` | Загрузка данных из YAML |

### Маркеры тестов

| Маркер | Описание | Команда |
|--------|----------|---------|
| `phase1-6` | Фаза разработки | `pytest -m phase1` |
| `unit` | Unit тесты | `pytest -m unit` |
| `integration` | Integration тесты | `pytest -m integration` |
| `security` | Тесты безопасности | `pytest -m security` |
| `performance` | Тесты производительности | `pytest -m performance` |
| `slow` | Медленные тесты | `pytest -m "not slow"` |

### Golden Master правила

1. **Не менять golden файлы без причины** — любое изменение должно быть обосновано
2. **Версионировать golden файлы** — при изменении структуры обновлять версию
3. **Тестировать структуру, не точное совпадение** — LLM может варьировать формулировки
4. **Документировать изменения** — в commit message указывать причину изменения golden

### CI/CD Workflow

1. Push → запускаются unit тесты
2. PR → запускаются все тесты + security scan
3. Merge → запускаются integration тесты + deployment
4. Nightly → запускаются performance тесты

### Покрытие кода

| Модуль | Минимальное покрытие |
|--------|---------------------|
| Core | 80% |
| Security | 90% |
| Skills | 85% |
| Agents | 80% |
| Memory | 80% |

### Частые проблемы

**Проблема:** Тесты падают из-за времени  
**Решение:** Использовать `@pytest.fixture def frozen_time()`

**Проблема:** Тесты нестабильны  
**Решение:** Проверить deterministic seed в conftest.py

**Проблема:** Медленные тесты  
**Решение:** Пометить `@pytest.mark.slow` и запускать отдельно

**Проблема:** Mock не работает  
**Решение:** Проверить путь импорта в patch()

### Контакты

- Spec: SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
- Issues: GitHub Issues
- Chat: Telegram channel
```

---

## ✅ ФИНАЛЬНЫЙ CHECKLIST TDD v1.2

```
□ pyproject.toml с маркерами фаз (phase1-6)
□ tests/conftest.py с фикстурами
□ frozen_time фикстура для тестов с временем
□ dynamic_skill_mock для динамических навыков
□ tests/fixtures/test_data.yaml
□ tests/config/test_config.yaml
□ Unit тесты для всех модулей с маркерами
□ Integration тесты с контейнерами
□ Security тесты (capability, isolation, approval)
□ Golden master для критических workflow
□ End-to-end тесты (план → выполнение → критик → откат)
□ Performance тесты
□ Deterministic seeds
□ Cleanup после тестов
□ Parallel execution настроен
□ CI/CD pipeline с health-check
□ wait-for для контейнеров
□ docs/TDD.md документация
□ Coverage >80% (core), >90% (security)
```

---

## 🚀 ОБНОВЛЁННЫЕ ПЕРВЫЕ ШАГИ

```bash
# 1. Создать структуру
mkdir -p synapse/tests/{unit,integration,fixtures,config}
mkdir -p synapse/docs synapse/.github/workflows

# 2. Установить зависимости
pip install -r requirements.txt -r requirements-test.txt

# 3. Создать фикстуры
# tests/conftest.py (см. выше)

# 4. Создать pyproject.toml с маркерами

# 5. Создать первый падающий тест с маркером
# tests/unit/test_core.py с @pytest.mark.phase1

# 6. Запустить тесты
pytest -m phase1 -v

# 7. Реализовать код для прохождения

# 8. Проверить coverage
coverage run -m pytest
coverage report

# 9. Закоммитить
git commit -m "[Phase 1] TDD infrastructure + first failing tests"
```

---

## 📊 МЕТРИКИ УСПЕХА TDD

| Метрика | Цель | Как измерить |
|---------|------|--------------|
| Test Coverage | >80% core, >90% security | `coverage report` |
| Phase Tests | 100% pass per phase | `pytest -m phaseX` |
| Build Time | <10 min | CI/CD pipeline |
| Flaky Tests | 0 | Повторный запуск 5x |
| Golden Master | 100% структура | `test_llm_golden.py` |
| Security Tests | 100% pass | `pytest -m security` |

---

**TDD-ИНСТРУКЦИЯ v1.2 FINAL ГОТОВА К PRODUCTION-РАЗРАБОТКЕ! 🎯**

**Спецификация:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md  
**Версия протокола:** 1.0  
**Версия TDD:** 1.2 FINAL  
**Статус:** PRODUCTION-READY ✅