# Project Synapse: TDD Guide v1.2

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt -r requirements-test.txt

# 2. Запустить тесты по фазе
pytest -m phase1 -v
pytest -m phase2 -v

# 3. Все тесты
pytest tests/ -v --cov=synapse

# 4. Только security тесты
pytest -m security -v
```

## Маркеры тестов

| Маркер | Описание | Команда |
|--------|----------|---------|
| `phase1` | Core Skeleton | `pytest -m phase1` |
| `phase2` | Execution & Security | `pytest -m phase2` |
| `phase3` | Perception & Memory | `pytest -m phase3` |
| `phase4` | Self-Evolution | `pytest -m phase4` |
| `phase5` | Reliability & Observability | `pytest -m phase5` |
| `phase6` | Deployment & UI | `pytest -m phase6` |
| `unit` | Unit tests | `pytest -m unit` |
| `integration` | Integration tests | `pytest -m integration` |
| `security` | Security tests | `pytest -m security` |
| `performance` | Performance tests | `pytest -m performance` |
| `slow` | Slow tests | `pytest -m "not slow"` |

## Структура тестов

```
tests/
├── conftest.py           # Общие фикстуры
├── config/               # Конфигурация тестов
│   └── test_config.yaml
├── fixtures/             # Тестовые данные
│   └── test_data.yaml
├── unit/                 # Unit тесты
│   ├── test_capability_scope.py
│   ├── test_llm_router.py
│   ├── test_chains.py
│   ├── test_goal_manager.py
│   ├── test_trace_client.py
│   └── test_output_parser.py
├── integration/          # Integration тесты
│   └── test_distributed_execution.py
├── test_llm_golden.py    # Golden master тесты
└── test_performance.py   # Performance тесты
```

## Покрытие кода

| Модуль | Минимальное покрытие |
|--------|---------------------|
| Core | 80% |
| Security | 90% |
| Skills | 85% |
| Agents | 80% |
| Memory | 80% |
| LLM | 80% |
| Observability | 80% |

## Golden Master правила

1. Не менять golden файлы без причины
2. Версионировать golden файлы при изменении структуры
3. Тестировать структуру, не точное совпадение текста
4. Документировать изменения в commit message

## TDD Workflow

```
RED → GREEN → REFACTOR
 ↑               |
 └───────────────┘
```

1. **RED**: Пишем падающий тест описывающий требование
2. **GREEN**: Минимальный код для прохождения теста
3. **REFACTOR**: Улучшаем код не меняя поведения
