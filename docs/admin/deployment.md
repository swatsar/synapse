# Deployment Guide — Synapse

**Protocol Version:** 1.0 | Для: Production

---

## Варианты развёртывания

| Вариант | Когда использовать |
|---------|-------------------|
| Docker Compose (single host) | Dev, staging, небольшой production |
| Bare metal + systemd | Production без Docker |
| Kubernetes | Высокая нагрузка, auto-scaling |

---

## Docker Compose (рекомендуется)

### Структура стека

```yaml
# docker/docker-compose.yml
services:
  synapse-core   # порт 8000 (API + Web UI)
  db             # PostgreSQL 15
  qdrant         # vector store, порт 6333
  redis          # кэш, порт 6379
  prometheus     # метрики, порт 9091
  grafana        # дашборд, порт 3000
```

### Запуск

```bash
# Подготовка
cp .env.example .env
# Заполните .env

# Генерируйте сильные секреты
echo "SYNAPSE_API_KEY=$(openssl rand -hex 32)" >> .env
echo "DB_PASSWORD=$(openssl rand -hex 16)" >> .env

# Запуск
docker-compose -f docker/docker-compose.yml up -d

# Проверка
docker-compose -f docker/docker-compose.yml ps
curl http://localhost:8000/health
```

### Обновление

```bash
git pull origin main
docker-compose -f docker/docker-compose.yml build synapse-core
docker-compose -f docker/docker-compose.yml up -d synapse-core
```

---

## Nginx как reverse proxy

```nginx
# /etc/nginx/sites-available/synapse
server {
    listen 443 ssl;
    server_name synapse.example.com;

    ssl_certificate     /etc/letsencrypt/live/synapse.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/synapse.example.com/privkey.pem;

    # Основной API и Web UI
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name synapse.example.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/synapse /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## systemd сервис (bare metal)

```ini
# /etc/systemd/system/synapse.service
[Unit]
Description=Synapse Agent Platform
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=synapse
Group=synapse
WorkingDirectory=/opt/synapse
EnvironmentFile=/opt/synapse/.env
ExecStart=/opt/synapse/.venv/bin/synapse --web-ui --port 8000 --host 127.0.0.1
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=synapse

# Ограничения безопасности
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/opt/synapse/data /var/log/synapse

[Install]
WantedBy=multi-user.target
```

```bash
# Создать пользователя
sudo useradd -r -s /bin/false synapse
sudo mkdir -p /opt/synapse/data /var/log/synapse
sudo chown -R synapse:synapse /opt/synapse /var/log/synapse

# Включить и запустить
sudo systemctl daemon-reload
sudo systemctl enable synapse --now
sudo systemctl status synapse
```

---

## Переменные окружения для production

```env
# === Обязательные ===
SYNAPSE_API_KEY=<hex-32+>

# === LLM (хотя бы один) ===
OPENAI_API_KEY=sk-...

# === Database ===
DATABASE_URL=postgresql://synapse_user:StrongPass@localhost:5432/synapse

# === Vector DB ===
VECTOR_DB_URL=http://localhost:6333

# === Cache ===
REDIS_URL=redis://:RedisPass@localhost:6379

# === Logging ===
LOG_LEVEL=INFO
AUDIT_LOG_PATH=/var/log/synapse/audit.log

# === Production mode ===
MODE=docker
```

---

## Healthcheck и мониторинг

```bash
# Базовый healthcheck
curl http://localhost:8000/health
# → {"status":"healthy","version":"3.4.1","protocol_version":"1.0",...}

# Prometheus метрики
curl http://localhost:9090/metrics | grep synapse_

# Проверка агентов
curl -H "X-API-Key: $SYNAPSE_API_KEY" http://localhost:8000/api/v1/agents
```

Grafana: http://localhost:3000 (admin / `$GRAFANA_PASSWORD`)

---

## Backup и восстановление

```bash
# PostgreSQL backup
pg_dump -U synapse_user synapse > backup_$(date +%Y%m%d).sql

# Восстановление
psql -U synapse_user synapse < backup_20260318.sql

# Docker volumes backup
docker run --rm -v synapse_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/synapse_data_$(date +%Y%m%d).tar.gz /data
```

---

## Логи

```bash
# systemd
journalctl -u synapse -f

# Docker
docker logs synapse-core -f --tail 100

# Аудит
tail -f /var/log/synapse/audit.log | python -m json.tool
```
