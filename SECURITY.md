# Security Policy — Synapse

## Поддерживаемые версии

| Версия | Security-поддержка |
|--------|-------------------|
| 3.2.x (latest) | ✅ Активна |
| 3.1.x | ⚠️ Только критические патчи |
| < 3.1 | ❌ Не поддерживается |

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

## Модель угроз

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

## Реализованные меры защиты

### Аутентификация
- `X-API-Key` header + query param для REST
- WebSocket token через query param
- Все эндпоинты кроме `/health` требуют аутентификации

### Авторизация
- Capability-Based Security: нет прав по умолчанию
- Wildcard scope (`fs:read:/workspace/**`)
- TTL на токены (`expires_in_hours`)
- `CapabilityManager.check_capabilities()` перед каждым действием

### Изоляция выполнения
- `subprocess` для trusted skills
- Docker container для verified/unverified skills
- `ResourceLimits`: cpu_seconds, memory_mb, disk_mb, network_kb

### Audit Trail
- `AuditMechanism.emit_event()` для каждого capability check
- Типы событий: issued, revoked, checked, denied, executed
- Структурированные логи через `structlog`

### Сетевая защита
- CORS whitelist (не wildcard в production)
- Rate limiting: 60 req/min
- Security headers (middleware)

### Защита секретов
- Секреты только через переменные окружения
- `.env` в `.gitignore`
- Секреты не передаются в sandbox
- Не логируются в audit trail

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
