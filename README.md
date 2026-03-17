# 🧠 Synapse — Distributed Cognitive Agent Platform

[![PyPI version](https://badge.fury.io/py/synapse-agent.svg)](https://badge.fury.io/py/synapse-agent)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1176%20passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-81.66%25-green.svg)](docs/reports/)
[![Production Ready](https://img.shields.io/badge/Production-98.5%25-brightgreen.svg)](docs/)

**Production-Ready Distributed Cognitive Agent Platform с Capability-Based Security, Self-Evolution и Zero-Trust Execution.**

---

## 📖 О Проекте

**Synapse** — это не просто AI-ассистент, а **цифровой организм**, способный к автономному развитию и обучению. Платформа реализует 8-шаговый когнитивный цикл агента с capability-based security моделью и распределённым выполнением.

### Ключевые Возможности

- 🧬 **Саморазвитие** — создание новых навыков и агентов для решения неизвестных задач
- 🛡️ **Самозащита** — встроенная многоуровневая система безопасности (Capability-Based + Zero-Trust)
- 🔄 **Самовосстановление** — автоматический откат к стабильным состояниям (Checkpoint/Rollback)
- 🌐 **Самораспределение** — работа на множестве узлов с синхронизацией

### Архитектурные Принципы

| Принцип | Описание |
|---------|----------|
| **Capability-Based Security** | Каждый навык требует явного разрешения (токена) для доступа к ресурсам |
| **Isolation Enforcement** | Непроверенный код выполняется в песочнице (контейнер) |
| **Protocol Versioning** | Все компоненты имеют `protocol_version="1.0"` для совместимости |
| **Deterministic Execution** | Воспроизводимые результаты через `execution_seed` |
| **Zero-Trust Fabric** | Ни один узел не доверяет другому без верификации (Phase 8) |
| **Audit Trail** | Полное логирование всех действий для прозрачности |

---

## 🚀 Быстрый Старт

### Установка

```bash
# Из PyPI
pip install synapse-agent

# Или из исходников
git clone https://github.com/swatsar/synapse.git
cd synapse
pip install -e .
```

### Запуск

```bash
# Локальный запуск
synapse-agent --config config/default.yaml

# Docker
 docker-compose up -d

# Проверка здоровья
curl http://localhost:8000/health
```

---

## 📊 Статус Проекта

### Завершённые Фазы

| Фаза | Статус | Тесты | Coverage | Описание |
|------|--------|-------|----------|----------|
| **Phase 1** | ✅ Complete | 156 | 95% | Core Skeleton, Security Model |
| **Phase 2** | ✅ Complete | 143 | 92% | Execution & Security |
| **Phase 3** | ✅ Complete | 128 | 90% | Perception & Memory |
| **Phase 4** | ✅ Complete | 134 | 88% | Self-Evolution |
| **Phase 5** | ✅ Complete | 142 | 91% | Reliability & Observability |
| **Phase 6** | ✅ Complete | 156 | 93% | Deterministic Runtime |
| **Phase 7** | ✅ Complete | 167 | 94% | Control Plane |
| **Phase 7.1** | ✅ Complete | 67 | 97.5% | Orchestrator Control Plane |
| **Phase 7.2** | ✅ Complete | 89 | 96% | Ecosystem Layer |
| **Phase 8** | 🔄 In Progress | 18/18 | 85% | Zero-Trust Fabric |

### Метрики

```
✅ Тесты: 1176+ passing (100%)
✅ Coverage: 81.66% (core >90%)
✅ Production Ready: 98.5%
✅ Audit: 27/27 проблем исправлено
```

---

## 🏗️ Архитектура

```
synapse/
├── core/ — оркестрация, безопасность, аудит, determinism
├── zero_trust/ — модель нулевого доверия (Phase 8)
├── orchestrator_control/ — управляющая плоскость
├── cluster_orchestration/ — распределённые вычисления
├── governance/ — capability management
├── memory/ — распределённая память (vector, SQL, cache)
├── runtime/ — изолированное выполнение навыков
├── transport/ — сетевая коммуникация
├── agents/ — planner, critic, developer, guardian
├── skills/ — base skill, builtins, dynamic registry
├── connectors/ — Telegram, Discord, REST API
├── llm/ — LLM abstraction, routing, fallback
└── ui/ — Web dashboard, API, CLI
```

### Когнитивный Цикл Агента

```
┌─────────────────────────────────────────────────────────────┐
│ AGENT COGNITIVE LOOP (8 шагов) │
├─────────────────────────────────────────────────────────────┤
│ 1. ВОСПРИЯТИЕ (Perceive) ← InputEvent от коннекторов │
│ 2. ВОСПОМИНАНИЕ (Recall) ← Memory retrieval │
│ 3. ПЛАНИРОВАНИЕ (Plan) ← ActionPlan generation │
│ 4. БЕЗОПАСНОСТЬ (Security) ← Capability + Risk check │
│ 5. ОДОБРЕНИЕ (Approval) ← Human-in-the-loop (if ≥3) │
│ 6. CHECKPOINT ← Save state before execute │
│ 7. ДЕЙСТВИЕ (Act) ← Skill execution │
│ 8. НАБЛЮДЕНИЕ (Observe) ← Result analysis │
│ 9. ОЦЕНКА (Evaluate) ← Critic evaluation │
│ 10. ОБУЧЕНИЕ (Learn) ← Memory consolidation │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Безопасность

### Multi-Layer Security Model

1. **Capability-Based Permissions** — токены доступа к ресурсам
2. **Isolation Enforcement** — контейнеризация навыков
3. **Zero-Trust Fabric** — верификация всех узлов (Phase 8)
4. **Human-in-the-Loop** — одобрение для risk_level ≥ 3
5. **Audit Trail** — полное логирование действий

### Threat Model (STRIDE)

| Угроза | Контрмера |
|--------|----------|
| **Spoofing** | JWT-токены, webhook-секреты |
| **Tampering** | Immutable audit log, security_hash |
| **Repudiation** | Full audit trail в PostgreSQL |
| **Information Disclosure** | Secrets не передаются в sandbox |
| **DoS** | Resource limits per skill |
| **Elevation of Privilege** | Strict isolation per skill |

---

## 📦 Установка

### Требования

- Python 3.11+
- PostgreSQL 15+ (для production)
- ChromaDB/Qdrant (для vector memory)
- Docker (опционально)

### Локальная Установка

```bash
# Клонирование
git clone https://github.com/swatsar/synapse.git
cd synapse

# Виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# Установка
pip install -e .

# Конфигурация
cp config/default.yaml config/local.yaml
# Отредактируйте config/local.yaml

# Запуск
synapse-agent --config config/local.yaml
```

### Docker Установка

```bash
# Docker Compose
docker-compose up -d

# Проверка
docker-compose ps
curl http://localhost:8000/health

# Логи
docker-compose logs -f synapse-core
```

### Production Установка

```bash
# PostgreSQL
CREATE DATABASE synapse;
CREATE USER synapse WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE synapse TO synapse;

# Environment variables
export DATABASE_URL="postgresql://synapse:secure_password@localhost:5432/synapse"
export VECTOR_DB_URL="http://localhost:6333"
export SYNAPSE_SECRET="your-secret-key"

# Запуск
synapse-agent --production
```

---

## 🧪 Тестирование

```bash
# Все тесты
pytest tests/ -v

# Конкретная фаза
pytest -m phase8 -v

# Coverage
coverage run -m pytest
coverage report --fail-under=80

# Security тесты
pytest -m security -v

# Performance тесты
pytest -m performance -v
```

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [INSTALLATION](docs/user/installation.md) | Подробная инструкция по установке |
| [QUICKSTART](docs/user/quickstart.md) | Быстрый старт |
| [CONFIGURATION](docs/user/configuration.md) | Настройка конфигурации |
| [SECURITY](docs/user/security.md) | Руководство по безопасности |
| [TROUBLESHOOTING](docs/user/troubleshooting.md) | Решение проблем |
| [API](docs/developer/api.md) | API документация |
| [ARCHITECTURE](docs/architecture/overview.md) | Архитектурное описание |
| [ROADMAP](docs/roadmap.md) | План развития |

---

## 🤝 Вклад

### Разработка

```bash
# Fork репозитория
git clone https://github.com/YOUR_USERNAME/synapse.git

# Создание ветки
git checkout -b feature/your-feature

# Внесение изменений
git add .
git commit -m "[Feature] Add your feature"

# Push и Pull Request
git push origin feature/your-feature
```

### Тестирование

Перед commit убедитесь:

```bash
# Все тесты проходят
pytest tests/ -v

# Coverage >80%
coverage report --fail-under=80

# Линтинг
flake8 synapse/

# Типы
mypy synapse/ --ignore-missing-imports
```

---

## 📈 Roadmap

### Phase 8: Zero-Trust Fabric (In Progress)
- [x] Trust Identity Registry
- [x] Execution Authorization Token
- [x] Remote Attestation Verifier
- [x] Trust Policy Engine
- [ ] Distributed Consensus
- [ ] Cluster Membership Protocol

### Phase 9: Enterprise Features (Q2 2026)
- [ ] Multi-Tenancy
- [ ] RBAC/ABAC
- [ ] Enterprise SSO
- [ ] Audit Dashboard

### Phase 10: Scaling (Q3 2026)
- [ ] Horizontal Scaling
- [ ] Load Balancing
- [ ] Caching Layer
- [ ] Performance Optimization

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE) файл.

---

## 👥 Авторы

**Евгений Савченко**
- Email: [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)
- GitHub: [@swatsar](https://github.com/swatsar)

---

## 🙏 Благодарности

- [OpenClaw](https://github.com/openclaw/openclaw) — за inspiration
- [Agent Zero](https://github.com/agent0ai/agent-zero) — за self-evolution концепции
- [LangChain](https://github.com/langchain-ai/langchain) — за LLM abstraction patterns
- [Anthropic](https://www.anthropic.com) — за safety research

---

## 📞 Контакты

- **Issues:** [GitHub Issues](https://github.com/swatsar/synapse/issues)
- **Discussions:** [GitHub Discussions](https://github.com/swatsar/synapse/discussions)
- **Documentation:** [docs/](docs/)

---

**Production Ready** с декабря 2025. Версия: **3.2.4** | Protocol: **1.0** | Spec: **3.1**
