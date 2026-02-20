# Deployment Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

This guide covers production deployment of Synapse across various environments: Docker, Kubernetes, and bare metal.

---

## Deployment Options

| Option | Use Case | Complexity |
|--------|----------|------------|
| Docker Compose | Small to medium deployments | Low |
| Kubernetes | Large-scale, high availability | High |
| Bare Metal | Maximum control, on-premise | Medium |
| Hybrid | Mixed environments | High |

---

## Docker Compose Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 50GB disk space

### Quick Start

```bash
# Clone repository
git clone https://github.com/synapse/synapse.git
cd synapse

# Copy environment file
cp .env.example .env

# Edit configuration
nano .env

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  synapse-core:
    build:
      context: .
      dockerfile: docker/Dockerfile
    image: synapse/core:3.1.0
    container_name: synapse-core
    restart: unless-stopped
    ports:
      - "8000:8000"   # API
      - "9090:9090"   # Prometheus metrics
    volumes:
      - ./config:/app/config
      - ./skills:/app/skills
      - synapse_data:/app/data
      - synapse_logs:/app/logs
    environment:
      - MODE=docker
      - DATABASE_URL=postgresql://synapse:${DB_PASSWORD}@db:5432/synapse
      - VECTOR_DB_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379/0
      - PROTOCOL_VERSION=1.0
      - SPEC_VERSION=3.1
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    depends_on:
      db:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    networks:
      - synapse-network

  db:
    image: postgres:15
    container_name: synapse-db
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=synapse
      - POSTGRES_USER=synapse
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U synapse -d synapse"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
    networks:
      - synapse-network

  qdrant:
    image: qdrant/qdrant:latest
    container_name: synapse-qdrant
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
    networks:
      - synapse-network

  redis:
    image: redis:7-alpine
    container_name: synapse-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    networks:
      - synapse-network

  prometheus:
    image: prom/prometheus:latest
    container_name: synapse-prometheus
    restart: unless-stopped
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9091:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    networks:
      - synapse-network

  grafana:
    image: grafana/grafana:latest
    container_name: synapse-grafana
    restart: unless-stopped
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
    networks:
      - synapse-network

volumes:
  synapse_data:
  synapse_logs:
  postgres_data:
  qdrant_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  synapse-network:
    driver: bridge
```

### Environment Variables

```bash
# .env
# Synapse Configuration
MODE=docker
PROTOCOL_VERSION=1.0
SPEC_VERSION=3.1
LOG_LEVEL=INFO

# Database
DB_PASSWORD=your_secure_password

# LLM Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your_grafana_password
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes 1.25+
- kubectl configured
- Helm 3.0+ (optional)
- Persistent storage provisioner

### Namespace and Secrets

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: synapse
  labels:
    app: synapse
    protocol_version: "1.0"
---
apiVersion: v1
kind: Secret
metadata:
  name: synapse-secrets
  namespace: synapse
type: Opaque
stringData:
  database-password: "your_secure_password"
  openai-api-key: "sk-..."
  anthropic-api-key: "sk-ant-..."
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: synapse-config
  namespace: synapse
data:
  MODE: "kubernetes"
  PROTOCOL_VERSION: "1.0"
  SPEC_VERSION: "3.1"
  LOG_LEVEL: "INFO"
  config.yaml: |
    system:
      name: "Synapse"
      version: "3.1"
      protocol_version: "1.0"
    llm:
      default_provider: "openai"
    security:
      require_approval_for_risk: 3
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: synapse
  namespace: synapse
  labels:
    app: synapse
    protocol_version: "1.0"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: synapse
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: synapse
        protocol_version: "1.0"
    spec:
      serviceAccountName: synapse
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: synapse
        image: synapse/core:3.1.0
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: api
        - containerPort: 9090
          name: metrics
        envFrom:
        - configMapRef:
            name: synapse-config
        - secretRef:
            name: synapse-secrets
        env:
        - name: DATABASE_URL
          value: "postgresql://synapse:$(database-password)@postgres:5432/synapse"
        - name: VECTOR_DB_URL
          value: "http://qdrant:6333"
        resources:
          limits:
            cpu: "2.0"
            memory: "4Gi"
          requests:
            cpu: "1.0"
            memory: "2Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: data
          mountPath: /app/data
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: config
        configMap:
          name: synapse-config
      - name: data
        persistentVolumeClaim:
          claimName: synapse-data
      - name: logs
        emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: synapse
              topologyKey: kubernetes.io/hostname
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: synapse
  namespace: synapse
  labels:
    app: synapse
    protocol_version: "1.0"
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    name: api
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: synapse
---
apiVersion: v1
kind: Service
metadata:
  name: synapse-external
  namespace: synapse
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: synapse
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: synapse-ingress
  namespace: synapse
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - synapse.example.com
    secretName: synapse-tls
  rules:
  - host: synapse.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: synapse
            port:
              number: 8000
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: synapse-hpa
  namespace: synapse
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: synapse
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Bare Metal Deployment

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Qdrant or ChromaDB
- Redis 7+
- Systemd (for service management)

### Installation

```bash
# Create user
sudo useradd -r -s /bin/false synapse

# Create directories
sudo mkdir -p /opt/synapse/{config,skills,data,logs}
sudo chown -R synapse:synapse /opt/synapse

# Clone and install
cd /opt/synapse
git clone https://github.com/synapse/synapse.git .
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config/default.yaml config/config.yaml
nano config/config.yaml
```

### Systemd Service

```ini
# /etc/systemd/system/synapse.service
[Unit]
Description=Synapse Autonomous Agent Platform
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=synapse
Group=synapse
WorkingDirectory=/opt/synapse
Environment="PATH=/opt/synapse/venv/bin"
Environment="PROTOCOL_VERSION=1.0"
Environment="SPEC_VERSION=3.1"
ExecStart=/opt/synapse/venv/bin/python -m synapse.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/synapse/data /opt/synapse/logs

[Install]
WantedBy=multi-user.target
```

### Enable Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable synapse
sudo systemctl start synapse
sudo systemctl status synapse
```

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# docker/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'synapse'
    static_configs:
      - targets: ['synapse-core:9090']
    metrics_path: /metrics

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Alert Rules

```yaml
# docker/alerting.yml
groups:
  - name: synapse
    rules:
      - alert: SynapseDown
        expr: up{job="synapse"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Synapse is down"
          description: "Synapse has been down for more than 1 minute"

      - alert: HighErrorRate
        expr: rate(synapse_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: HighMemoryUsage
        expr: synapse_memory_usage_bytes / synapse_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage above 90%"

      - alert: LLMLatencyHigh
        expr: histogram_quantile(0.95, rate(synapse_llm_latency_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM latency above 5 seconds"
```

---

## Backup and Recovery

### Database Backup

```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/backup/synapse"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL
pg_dump -U synapse synapse > $BACKUP_DIR/db_$DATE.sql

# Qdrant
curl http://localhost:6333/collections/synapse_memory/snapshots -X POST

# Redis
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Cleanup old backups
find $BACKUP_DIR -type f -mtime +30 -delete
```

### Recovery

```bash
# Restore PostgreSQL
psql -U synapse synapse < /backup/synapse/db_20260220.sql

# Restore Redis
redis-cli SHUTDOWN NOSAVE
cp /backup/synapse/redis_20260220.rdb /var/lib/redis/dump.rdb
redis-server
```

---

## Scaling Guidelines

| Users | Replicas | CPU | Memory | Database |
|-------|----------|-----|--------|----------|
| 1-10 | 1 | 2 cores | 4GB | Single |
| 10-50 | 2 | 4 cores | 8GB | Single |
| 50-200 | 3 | 8 cores | 16GB | Replicated |
| 200+ | 5+ | 16+ cores | 32GB+ | Cluster |

---

## Troubleshooting

### Container won't start
```bash
docker-compose logs synapse-core
docker-compose exec db pg_isready
```

### Database connection failed
```bash
# Check credentials
docker-compose exec db psql -U synapse -d synapse

# Check network
docker network inspect synapse-network
```

### High memory usage
```bash
# Check metrics
curl http://localhost:9090/metrics | grep memory

# Restart if needed
docker-compose restart synapse-core
```

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](../user/troubleshooting.md) or open an issue on GitHub.
