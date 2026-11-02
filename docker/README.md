# 🐳 Synapse Docker Deployment Guide

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Требования](#требования)
3. [Конфигурация](#конфигурация)
4. [Режимы запуска](#режимы-запуска)
5. [Переменные окружения](#переменные-окружения)
6. [Управление контейнерами](#управление-контейнерами)
7. [Мониторинг](#мониторинг)
8. [Устранение неполадок](#устранение-неполадок)

---

## 🚀 Быстрый старт

### Минимальный запуск (только ядро)

```bash
# Клонирование репозитория
git clone https://github.com/swatsar/PROJECT-SYNAPSE.git
cd PROJECT-SYNAPSE

# Создание .env файла
cp .env.example .env

# Запуск в режиме разработки
cd docker
docker-compose -f docker-compose.dev.yml up -d

# Проверка
 curl http://localhost:8000/health
```

### Полный запуск (production)

```bash
# Создание .env с паролями
cat > .env << ENVEOF
DB_PASSWORD=your_secure_password
GRAFANA_PASSWORD=your_grafana_password
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
ENVEOF

# Запуск всех сервисов
cd docker
docker-compose up -d

# Проверка статуса
docker-compose ps
```

---

## 📦 Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 10 GB | 20 GB |

### Проверка установки

```bash
docker --version
docker-compose --version
```

---

## ⚙️ Конфигурация

### Структура файлов

```
docker/
├── Dockerfile              # Образ Synapse
├── docker-compose.yml      # Production конфигурация
├── docker-compose.dev.yml  # Development конфигурация
├── docker-compose.test.yml # Test конфигурация
├── .dockerignore           # Исключения для сборки
└── README.md               # Этот файл
```

### Переменные окружения (.env)

```bash
# Обязательные
DB_PASSWORD=your_postgres_password
GRAFANA_PASSWORD=your_grafana_password

# LLM API ключи (минимум один)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Опциональные
LOG_LEVEL=INFO
MODE=production
PROTOCOL_VERSION=1.0
```

---

## 🎯 Режимы запуска

### 1. Development Mode (минимум сервисов)

```bash
cd docker
docker-compose -f docker-compose.dev.yml up -d
```

**Запускает:**
- synapse-core (основное приложение)
- redis (кэш)

**Порты:**
- 8000: API
- 9090: Prometheus metrics

### 2. Production Mode (полный стек)

```bash
cd docker
docker-compose up -d
```

**Запускает:**
- synapse-core (основное приложение)
- db (PostgreSQL)
- qdrant (векторная БД)
- redis (кэш)
- prometheus (метрики)
- grafana (визуализация)

**Порты:**
- 8000: API
- 3000: Grafana
- 6333: Qdrant
- 9090: Prometheus

### 3. Test Mode (для CI/CD)

```bash
cd docker
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

**Запускает:**
- synapse-core
- test runner
- временные БД

---

## 🔧 Управление контейнерами

### Основные команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f synapse-core

# Просмотр статуса
docker-compose ps

# Вход в контейнер
docker exec -it synapse-core /bin/bash

# Очистка (включая volumes)
docker-compose down -v
```

### Пересборка образа

```bash
# Пересборка с кэшем
docker-compose build

# Пересборка без кэша
docker-compose build --no-cache

# Пересборка и запуск
docker-compose up -d --build
```

---

## 📊 Мониторинг

### Health Check

```bash
# API health
curl http://localhost:8000/health

# Ожидаемый ответ:
# {"status": "healthy", "version": "3.1", "protocol_version": "1.0"}
```

### Prometheus Metrics

```bash
# Метрики
curl http://localhost:9090/metrics
```

### Grafana Dashboard

1. Откройте http://localhost:3000
2. Логин: admin / Пароль: из GRAFANA_PASSWORD
3. Импортируйте дашборд из `grafana/dashboards/`

### Логи

```bash
# Все логи
docker-compose logs

# Логи конкретного сервиса
docker-compose logs synapse-core

# Следить за логами
docker-compose logs -f --tail=100 synapse-core
```

---

## 🐛 Устранение неполадок

### Контейнер не запускается

```bash
# Проверить логи
docker-compose logs synapse-core

# Проверить конфигурацию
docker-compose config

# Проверить здоровье контейнера
docker inspect synapse-core | grep -A 10 Health
```

### Проблемы с БД

```bash
# Проверить PostgreSQL
docker-compose logs db

# Подключиться к БД
docker exec -it synapse-db psql -U synapse -d synapse

# Перезапустить БД
docker-compose restart db
```

### Проблемы с памятью

```bash
# Проверить использование ресурсов
docker stats

# Увеличить лимиты в docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 8G
```

### Очистка и перезапуск

```bash
# Полная очистка
docker-compose down -v
docker system prune -a

# Пересборка
docker-compose build --no-cache
docker-compose up -d
```

---

## 📁 Volumes

| Volume | Назначение |
|--------|------------|
| synapse_config | Конфигурация |
| synapse_data | Данные приложения |
| synapse_skills | Динамические навыки |
| postgres_data | Данные PostgreSQL |
| qdrant_data | Векторные эмбеддинги |
| redis_data | Кэш Redis |
| prometheus_data | Метрики Prometheus |
| grafana_data | Дашборды Grafana |

---

## 🔐 Безопасность

### Рекомендации для production

1. **Измените все пароли по умолчанию**
2. **Используйте secrets management** (Docker secrets, Vault)
3. **Настройте TLS/SSL** для внешних портов
4. **Ограничьте сеть** (firewall rules)
5. **Регулярно обновляйте** образы

### Пример с secrets

```yaml
# docker-compose.secrets.yml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  openai_key:
    file: ./secrets/openai_key.txt
```

---

## 🌐 Сеть

### Порты по умолчанию

| Порт | Сервис | Описание |
|------|--------|----------|
| 8000 | synapse-core | REST API |
| 3000 | grafana | Web UI |
| 6333 | qdrant | Vector DB API |
| 9090 | prometheus | Metrics |
| 5432 | db | PostgreSQL (внутренний) |
| 6379 | redis | Redis (внутренний) |

### Изменение портов

```yaml
# docker-compose.yml
services:
  synapse-core:
    ports:
      - "8080:8000"  # Изменить внешний порт
```

---

## 📝 Примеры использования

### API запрос

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Read file /app/data/test.txt",
    "session_id": "test-session"
  }'
```

### Проверка версии

```bash
curl http://localhost:8000/api/v1/version
# {"version": "3.4.1", "protocol_version": "1.0", "spec_version": "3.1"}
```

---

## 🔄 Обновление

```bash
# Получить последнюю версию
git pull origin main

# Пересобрать и перезапустить
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1  
**Docker Image:** synapse/core:3.4.1
