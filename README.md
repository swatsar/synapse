# 🧠 Project Synapse

**Universal Autonomous Agent Platform**

[![Protocol Version](https://img.shields.io/badge/protocol-1.0-blue.svg)](https://github.com/swatsar/PROJECT-SYNAPSE)
[![Spec Version](https://img.shields.io/badge/spec-3.1-green.svg)](https://github.com/swatsar/PROJECT-SYNAPSE)
[![Python](https://img.shields.io/badge/python-3.11+-yellow.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-965%20passing-brightgreen.svg)](tests/)

---

## 📖 Описание

**Synapse** — распределённая когнитивная платформа автономных агентов с возможностью саморазвития. Платформа объединяет лучшие практики из OpenClaw (модульность, коннекторы) и Agent Zero (самоэволюция), добавляя production-ready надёжность и многоуровневую безопасность.

### Ключевые возможности

- 🔄 **7-шаговый когнитивный цикл**: Perceive → Recall → Plan → Act → Observe → Evaluate → Learn
- 🧬 **Саморазвитие**: Автоматическая генерация и верификация новых навыков
- 🔐 **Capability-Based Security**: Токены доступа с минимальными привилегиями
- 🐳 **Контейнерная изоляция**: Автоматическая песочница для risk_level >= 3
- 📊 **Полная наблюдаемость**: Prometheus, Grafana, распределённый трейсинг
- 🔄 **Rollback система**: Восстановление после сбоев через checkpoint
- 🌐 **Распределённое выполнение**: Multi-node кластер с синхронизацией времени

---

## 🚀 Быстрый старт

### Установка через pip

```bash
pip install synapse-agent
```

### Docker

```bash
# Клонирование
git clone https://github.com/swatsar/PROJECT-SYNAPSE.git
cd PROJECT-SYNAPSE

# Настройка окружения
cp .env.example .env
# Отредактируйте .env с вашими API ключами

# Запуск
cd docker
docker-compose up -d

# Проверка
curl http://localhost:8000/health
```

### Локальная установка

```bash
# Клонирование
git clone https://github.com/swatsar/PROJECT-SYNAPSE.git
cd PROJECT-SYNAPSE

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# или .venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python -m synapse.main
```

---

## 📁 Структура проекта

```
synapse/
├── core/               # Ядро платформы
│   ├── orchestrator.py # 7-шаговый когнитивный цикл
│   ├── security.py     # Capability Manager
│   ├── rollback.py     # Система отката
│   └── isolation_policy.py
├── agents/             # Специализированные агенты
│   ├── planner.py      # Планировщик задач
│   ├── critic.py       # Критик и оценка
│   ├── developer.py    # Генерация навыков
│   └── guardian.py     # Контроль безопасности
├── skills/             # Навыки
│   ├── base.py         # BaseSkill класс
│   ├── builtins/       # Встроенные навыки
│   └── dynamic/        # Сгенерированные навыки
├── memory/             # Система памяти
│   ├── store.py        # Vector Store (ChromaDB)
│   └── distributed/    # Распределённая память
├── llm/                # LLM абстракция
│   ├── provider.py     # Унифицированный интерфейс
│   ├── router.py       # Маршрутизация моделей
│   └── failure_strategy.py
├── connectors/         # Коннекторы мессенджеров
│   ├── telegram.py
│   └── discord.py
├── distributed/        # Распределённое выполнение
├── observability/      # Мониторинг и метрики
└── security/           # Слой безопасности
```

---

## 🔧 Конфигурация

### Переменные окружения (.env)

```bash
# LLM API ключи (минимум один)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# База данных
DATABASE_URL=postgresql://user:pass@localhost:5432/synapse
VECTOR_DB_URL=http://localhost:6333

# Безопасность
REQUIRE_APPROVAL_FOR_RISK=3
AUDIT_LOG_PATH=/var/log/synapse/audit.log
```

### YAML конфигурация

```yaml
# config/default.yaml
system:
  name: "Synapse"
  version: "3.1"
  mode: "autonomous"

llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      priority: 1
    - name: "claude-3.5"
      priority: 2

security:
  require_approval_for_risk: 3
  isolation_policy:
    unverified_skills: "container"
    risk_level_3_plus: "container"
```

---

## 🛡️ Безопасность

### Многоуровневая защита

| Уровень | Механизм | Описание |
|---------|----------|----------|
| **1** | Capability Tokens | Токены с минимальными привилегиями |
| **2** | Isolation Policy | Контейнеризация для risk >= 3 |
| **3** | Human Approval | Подтверждение опасных действий |
| **4** | Audit Log | Полный журнал действий |
| **5** | Rollback | Восстановление после сбоев |

### Жизненный цикл навыков

```
GENERATED → TESTED → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
     ↓         ↓         ↓         ↓
   [LLM]   [Tests]  [Static]  [Human]
                     Analysis   Approval
```

---

## 📊 Мониторинг

### Prometheus метрики

```bash
curl http://localhost:9090/metrics
```

### Grafana дашборд

1. Откройте http://localhost:3000
2. Импортируйте дашборд из `docker/grafana/`

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "3.1", "protocol_version": "1.0"}
```

---

## 🧪 Тестирование

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=synapse --cov-report=html

# Только security тесты
pytest tests/ -m security -v

# Integration тесты
pytest tests/ -m integration -v
```

### Покрытие кода

| Модуль | Покрытие |
|--------|----------|
| Core | >80% |
| Security | >90% |
| Agents | >80% |
| Skills | >85% |

---

## 📚 Документация

- [Установка](docs/user/installation.md)
- [Быстрый старт](docs/user/quickstart.md)
- [Конфигурация](docs/user/configuration.md)
- [API Reference](docs/developer/api.md)
- [Разработка навыков](docs/developer/skills.md)
- [Docker Deployment](docker/README.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## 🤝 Участие в разработке

1. Fork репозитория
2. Создайте ветку (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл.

---

## 📞 Контакты

- **GitHub Issues**: [github.com/swatsar/PROJECT-SYNAPSE/issues](https://github.com/swatsar/PROJECT-SYNAPSE/issues)
- **Документация**: [docs/](docs/)

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1  
**Status:** Production Ready ✅
