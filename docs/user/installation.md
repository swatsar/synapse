# Руководство по установке Synapse

**Protocol Version:** 1.0 | **Spec Version:** 3.1 | **Версия:** 3.4.1

---

## Системные требования

### Минимум

| Компонент | Требование |
|-----------|------------|
| Python | 3.11+ |
| RAM | 4 GB |
| Диск | 10 GB |
| CPU | 2 ядра |
| ОС | Linux / macOS / Windows 10+ |

### Рекомендуется (production)

| Компонент | Требование |
|-----------|------------|
| Python | 3.12+ |
| RAM | 16 GB |
| Диск | 50 GB |
| CPU | 4+ ядра |
| ОС | Ubuntu 22.04 LTS / Debian 12 |

### Опциональные зависимости

| Компонент | Назначение |
|-----------|------------|
| Docker 24+ | Изолированное выполнение навыков |
| PostgreSQL 15+ | Production БД |
| Qdrant / ChromaDB | Vector memory |
| Redis 7+ | Кэш и сессии |

---

## Вариант 1: Из исходников (разработка)

```bash
# 1. Клонирование
git clone https://github.com/swatsar/synapse.git
cd synapse

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Установка с dev-зависимостями
pip install -e ".[dev]"

# 4. Конфигурация
cp .env.example .env
# Отредактируйте .env — минимум задайте OPENAI_API_KEY или ANTHROPIC_API_KEY

# 5. Запуск
synapse --web-ui --port 8000
# Откройте http://localhost:8000
```

---

## Вариант 2: Docker Compose (рекомендуется)

```bash
# 1. Клонирование
git clone https://github.com/swatsar/synapse.git
cd synapse

# 2. Конфигурация
cp .env.example .env
nano .env  # заполните API ключи и DB_PASSWORD

# 3. Запуск всего стека
docker-compose -f docker/docker-compose.yml up -d

# 4. Проверка
docker-compose -f docker/docker-compose.yml ps
curl http://localhost:8000/health

# 5. Логи
docker-compose -f docker/docker-compose.yml logs -f synapse-core
```

Стек включает:
- `synapse-core` — основной сервис (порт 8000)
- `postgres:15` — база данных
- `qdrant:latest` — vector store (порт 6333)
- `redis:7` — кэш
- `prometheus` — метрики (порт 9091)
- `grafana` — дашборд (порт 3000)

---

## Вариант 3: Production (bare metal)

### Шаг 1. PostgreSQL

```bash
sudo apt install postgresql-15
sudo -u postgres psql -c "CREATE DATABASE synapse;"
sudo -u postgres psql -c "CREATE USER synapse_user WITH PASSWORD 'StrongPass123!';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE synapse TO synapse_user;"
```

### Шаг 2. Redis

```bash
sudo apt install redis-server
sudo systemctl enable redis --now
```

### Шаг 3. Qdrant (vector DB)

```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  --restart unless-stopped \
  qdrant/qdrant:latest
```

### Шаг 4. Synapse

```bash
pip install synapse-agent
# или
git clone ... && pip install -e .

# Переменные окружения
export SYNAPSE_API_KEY="$(openssl rand -hex 32)"
export DATABASE_URL="postgresql://synapse_user:StrongPass123!@localhost:5432/synapse"
export VECTOR_DB_URL="http://localhost:6333"
export OPENAI_API_KEY="sk-..."

synapse --mode local --web-ui --port 8000
```

### Шаг 5. systemd сервис

```ini
# /etc/systemd/system/synapse.service
[Unit]
Description=Synapse Agent Platform
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=synapse
WorkingDirectory=/opt/synapse
EnvironmentFile=/opt/synapse/.env
ExecStart=/opt/synapse/.venv/bin/synapse --web-ui --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable synapse --now
sudo systemctl status synapse
```

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `SYNAPSE_API_KEY` | ✅ | API ключ (32+ символа hex) |
| `OPENAI_API_KEY` | ✅* | OpenAI ключ (*хотя бы один LLM) |
| `ANTHROPIC_API_KEY` | ✅* | Anthropic ключ |
| `DATABASE_URL` | ❌ | PostgreSQL URL (SQLite по умолчанию) |
| `VECTOR_DB_URL` | ❌ | Qdrant URL |
| `REDIS_URL` | ❌ | Redis URL |
| `LOG_LEVEL` | ❌ | `DEBUG`/`INFO`/`WARNING` (по умолч. `INFO`) |

---

## Проверка установки

```bash
# Health check
curl http://localhost:8000/health

# Ожидаемый ответ:
# {"status":"healthy","version":"3.4.1","protocol_version":"1.0",...}

# Статус агентов
curl -H "X-API-Key: $SYNAPSE_API_KEY" http://localhost:8000/api/v1/agents

# Python smoke test
python -c "import synapse; print('OK:', synapse.__version__)"
```

---

## Обновление

```bash
git pull origin main
pip install -e ".[dev]"
# или для Docker:
docker-compose -f docker/docker-compose.yml pull
docker-compose -f docker/docker-compose.yml up -d
```

---

## Удаление

```bash
# Локальная установка
pip uninstall synapse-agent
rm -rf .venv

# Docker
docker-compose -f docker/docker-compose.yml down -v
docker rmi synapse/core:3.4.1
```
