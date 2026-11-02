# Security Policy — Synapse

## Поддерживаемые версии

| Версия | Security-поддержка |
|--------|-------------------|
| 3.4.x (latest) | ✅ Активна |
| 3.2.x - 3.3.x | ⚠️ Только критические патчи |
| < 3.2 | ❌ Не поддерживается |

---

## Сообщить об уязвимости

**Не публикуйте уязвимости в открытых GitHub Issues.**

### Приватный канал:
- **Email:** [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)
- **GitHub Security Advisories:** https://github.com/swatsar/synapse/security/advisories/new

### Что включить в отчёт:
1. Описание уязвимости
2. Шаги для воспроизведения
3. Версия Synapse (`synapse --version`)
4. Потенциальное воздействие (CVSS если применимо)
5. Предложение по исправлению (опционально)

**Ответ в течение:** 48 часов.
**Патч в течение:** 14 дней для критических, 30 дней для прочих.

---

## Модель угроз (STRIDE)

### Scope: что защищается
- API эндпоинты от несанкционированного доступа
- Capability токены от подделки и утечки
- Навыки от выполнения вредоносного кода за пределами sandbox
- Audit trail от фальсификации
- Секреты (API-ключи) от утечки в sandbox или логи

### Out of scope
- Безопасность самих LLM-провайдеров (OpenAI, Anthropic)
- Безопасность инфраструктуры хостинга
- Социальная инженерия против операторов платформы

---

## 4-уровневая Execution Trust Model

| Trust Level | Isolation | Источник | Права доступа |
|-------------|-----------|----------|---------------|
| **Trusted** | subprocess | Встроенные навыки ядра | Полный доступ через capability-токены |
| **Verified** | subprocess (isolated) | Автотесты + AST-анализ | Только заявленные capabilities |
| **Unverified** | sandbox (strict) | LLM-generated код | Только вычисления, нет I/O |
| **Human-Approved** | subprocess (extended) | Одобрены пользователем | Расширенный доступ |

---

## Реализованные меры защиты

### Аутентификация
- `X-API-Key` header + query param для REST
- WebSocket token через query param
- Если `SYNAPSE_API_KEY` не задан — dev-режим без auth
- Все эндпоинты кроме `/health` требуют аутентификации

### Авторизация (Capability-Based)
- CapabilityScope enum: `FILESYSTEM_READ`, `FILESYSTEM_WRITE`, `NETWORK_HTTP`, `PROCESS_SPAWN`, `DEVICE_IOT`, `SYSTEM_INFO`
- Wildcard scope (`fs:read:/workspace/**`)
- TTL на токены (`expires_in_hours`)
- `CapabilityManager.check_capabilities()` перед каждым действием

### Изоляция выполнения
- `sandbox` для unverified skills (нет сети, файлов, процессов)
- `subprocess` для trusted/verified/human-approved skills
- `container` для risk_level ≥ 3 (любой trust level)
- `ResourceLimits`: cpu_seconds, memory_mb, disk_mb, network_kb

### Human-in-the-Loop
- Обязательное одобрение для risk_level ≥ 3
- Запрос через Web UI и/или Telegram
- Блокировка выполнения до получения ответа

### Audit Trail
- `AuditMechanism.emit_event()` для каждого capability check
- TraceClient с span hierarchy и sensitive data filtering
- Структурированные логи через `structlog`
- Prometheus метрики

### Защита секретов
- Секреты только через переменные окружения
- `.env` в `.gitignore`
- Секреты не передаются в sandbox
- Sensitive data filtering в TraceClient (api_key → ***)

---

## Рекомендации по deployment

```bash
# 1. Генерируйте сильные ключи
export SYNAPSE_API_KEY="$(openssl rand -hex 32)"
export SYNAPSE_SECRET_KEY="$(openssl rand -hex 32)"

# 2. HTTPS через reverse proxy (nginx/traefik)
# 3. Ограничьте доступ к портам (8000 только через proxy)
# 4. Запускайте Docker контейнеры без root
# 5. Регулярно ротируйте SYNAPSE_API_KEY
```

Подробно: [docs/user/security.md](docs/user/security.md) и [docs/admin/security-hardening.md](docs/admin/security-hardening.md)
