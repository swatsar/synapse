# 🧠 Synapse — Distributed Cognitive Agent Platform

[![PyPI version](https://badge.fury.io/py/synapse-agent.svg)](https://badge.fury.io/py/synapse-agent)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1176%20passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-82%25-green.svg)](docs/reports/)
[![Pre-Production](https://img.shields.io/badge/Status-Pre--Production-blue.svg)](docs/)
[![Protocol](https://img.shields.io/badge/Protocol-v1.0-orange.svg)](SPECIFICATION.md)

**Pre-Production Distributed Cognitive Agent Platform с Capability-Based Security, Self-Evolution и Zero-Trust Execution.**

> **v3.4.0** — Bugfix release: все синтаксические ошибки, дубли кода и незаполненные заглушки устранены. Проект готов к предпродакшн-развёртыванию.

---

## 📖 О проекте

**Synapse** — платформа автономных агентов с 10-шаговым когнитивным циклом, capability-based security и поддержкой распределённого выполнения. Агенты умеют самостоятельно планировать, создавать новые навыки, откатываться на стабильные чекпоинты и работать в кластере.

### Ключевые возможности

| Возможность | Описание |
|-------------|----------|
| 🧬 **Саморазвитие** | Создание новых навыков через LLM + автотестирование + 6-статусный lifecycle |
| 🛡️ **Capability-Based Security** | Токены доступа с wildcard scope, TTL и аудитом |
| 🔄 **Checkpoint/Rollback** | Сохранение состояния перед каждым действием |
| 🌐 **Распределённое выполнение** | Кластер узлов с детерминированным планировщиком |
| 🔍 **Zero-Trust Fabric** | Верификация каждого узла (Phase 8) |
| 📊 **Полный аудит** | Каждое действие логируется с `protocol_version` |

---

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.11+
- 4 GB RAM (8 GB рекомендуется)
- Docker (для production)

### Установка из исходников

```bash
git clone https://github.com/swatsar/synapse.git
cd synapse
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # заполните ключи LLM
```

### Запуск (локально)

```bash
# API-сервер + Web dashboard
synapse --web-ui --port 8000

# Только агент (без UI)
synapse --mode local

# Проверка здоровья
curl http://localhost:8000/health
```

### Запуск через Docker

```bash
cp .env.example .env
# Заполните .env своими значениями
docker-compose -f docker/docker-compose.yml up -d
curl http://localhost:8000/health
```

---

## 🏗️ Архитектура

```
synapse/
├── core/                    # Оркестратор, security, checkpoint, determinism, audit
├── agents/                  # Planner, Critic, Developer, Governor, Guardian
│   ├── runtime/             # Базовый агент с когнитивным циклом
│   └── supervisor/          # Управляющий агент
├── skills/                  # Навыки: base, builtins, dynamic registry, lifecycle
│   ├── builtins/            # read_file, write_file, web_search
│   └── dynamic/             # 6-статусный реестр (GENERATED→ARCHIVED)
├── security/                # ExecutionGuard, CapabilityManager, MemorySeal
├── governance/              # CapabilityPolicyEngine, реестр capabilities
├── zero_trust/              # Identity, attestation, policy, enforcement (Phase 8)
├── llm/                     # LLMRouter с fallback, priority и timeout
├── memory/                  # MemoryStore + distributed store
├── transport/               # Channel, Message, Protocol
├── connectors/              # Telegram, Discord, REST
├── control_plane/           # ClusterManager, Scheduler, OrchestratorMesh
├── cluster_orchestration/   # Распределённое выполнение
├── ecosystem/               # APIGateway, CapabilityMarketplace, DomainPacks
├── observability/           # Logger, Exporter (Prometheus)
├── api/                     # FastAPI app, routes, middleware, storage
└── ui/                      # Web dashboard (HTML), Configurator
```

### Когнитивный цикл агента (10 шагов)

```
1. PERCEIVE   ← InputEvent от коннекторов (Telegram, Discord, REST)
2. RECALL     ← Memory retrieval (vector + SQL)
3. PLAN       ← ActionPlan через LLM + DeterministicPlanner
4. SECURITY   ← CapabilityManager.check_capabilities() + risk assessment
5. APPROVE    ← Human-in-the-loop (если risk_level ≥ 3)
6. CHECKPOINT ← Сохранение состояния перед выполнением
7. ACT        ← ExecutionGuard → Skill execution в sandbox
8. OBSERVE    ← Результат + метрики
9. EVALUATE   ← CriticAgent оценивает качество
10. LEARN     ← Memory consolidation + self-improvement
```

---

## 🔒 Безопасность

### Многоуровневая модель

1. **Capability Tokens** — wildcard-scope токены с TTL (`fs:read:/workspace/**`)
2. **ExecutionGuard** — проверка capabilities перед каждым действием
3. **IsolationPolicy** — `subprocess` / `container` / `strict_sandbox` по risk level
4. **Zero-Trust Fabric** — верификация узлов кластера (Phase 8)
5. **Human-in-the-Loop** — одобрение для risk_level ≥ 3
6. **AuditMechanism** — полное логирование с `event_type`, `agent_id`, `timestamp`

### Матрица изоляции

| Trust Level | Isolation | Применение |
|-------------|-----------|------------|
| `trusted` | subprocess | Встроенные навыки |
| `verified` | container | Проверенные сторонние навыки |
| `unverified` | strict_sandbox | LLM-generated навыки |

---

## 📦 Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `fastapi` | ≥0.100 | REST API |
| `pydantic` | ≥2.0 | Валидация данных |
| `litellm` | ≥1.0 | LLM abstraction |
| `uvicorn` | ≥0.23 | ASGI сервер |
| `sqlalchemy` | ≥2.0 | ORM |
| `aiosqlite` | ≥0.19 | SQLite async |
| `chromadb` | ≥0.4 | Vector memory |
| `redis` | ≥5.0 | Cache |
| `asyncpg` | ≥0.29 | PostgreSQL async |
| `prometheus-client` | ≥0.19 | Метрики |
| `structlog` | ≥24.0 | Структурированные логи |

---

## 🧪 Тестирование

```bash
# Все тесты
pytest tests/ -v

# По маркеру
pytest -m unit -v
pytest -m security -v
pytest -m phase8 -v

# С coverage
pytest --cov=synapse --cov-report=term-missing

# Конкретный файл
pytest tests/api/test_exceptions.py -v
```

---

## 📊 Статус фаз

| Фаза | Статус | Тесты | Coverage |
|------|--------|-------|----------|
| Phase 1 — Core Skeleton | ✅ Complete | 156 | 95% |
| Phase 2 — Execution & Security | ✅ Complete | 143 | 92% |
| Phase 3 — Perception & Memory | ✅ Complete | 128 | 90% |
| Phase 4 — Self-Evolution | ✅ Complete | 134 | 88% |
| Phase 5 — Reliability & Observability | ✅ Complete | 142 | 91% |
| Phase 6 — Deterministic Runtime | ✅ Complete | 156 | 93% |
| Phase 7 — Control Plane | ✅ Complete | 167 | 94% |
| Phase 7.1 — Orchestrator Control | ✅ Complete | 67 | 97% |
| Phase 7.2 — Ecosystem Layer | ✅ Complete | 89 | 96% |
| Phase 8 — Zero-Trust Fabric | 🔄 In Progress | 18 | 85% |
| **Bugfix v3.4.0** | ✅ Applied | 401 files | — |

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [INSTALLATION](docs/user/installation.md) | Подробная установка |
| [QUICKSTART](docs/user/quickstart.md) | Старт за 5 минут |
| [CONFIGURATION](docs/user/configuration.md) | Все параметры конфигурации |
| [API Reference](docs/API_REFERENCE.md) | REST API эндпоинты |
| [SECURITY](docs/user/security.md) | Модель безопасности |
| [ARCHITECTURE](ARCHITECTURE.md) | Архитектура платформы |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Решение проблем |
| [CONTRIBUTING](.github/CONTRIBUTING.md) | Как внести вклад |
| [CHANGELOG](CHANGELOG.md) | История изменений |
| [ROADMAP](ROADMAP.md) | План развития |

---

## 🤝 Вклад в проект

```bash
git clone https://github.com/swatsar/synapse.git
git checkout -b feature/my-feature
# ... изменения ...
pytest tests/ -v && flake8 synapse/
git commit -m "[Feature] Describe your change"
git push origin feature/my-feature
# Откройте Pull Request
```

Подробнее: [CONTRIBUTING](.github/CONTRIBUTING.md)

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE).

---

## 👤 Автор

**Евгений Савченко** — [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com) · [@swatsar](https://github.com/swatsar)

---

**Версия:** 3.4.0 | **Protocol:** 1.0 | **Spec:** 3.1 | **Статус:** Pre-Production
