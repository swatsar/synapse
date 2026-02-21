# Deployment Architecture

## Overview

Synapse supports **multiple deployment modes** from single-node to distributed clusters.

---

## Deployment Modes

### 1. Local Mode

```
┌─────────────────────────────────────────┐
│           LOCAL DEPLOYMENT              │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │      Single Process             │   │
│  │  ┌─────────────────────────┐    │   │
│  │  │  Synapse Core           │    │   │
│  │  │  ┌─────────────────┐    │    │   │
│  │  │  │ Orchestrator    │    │    │   │
│  │  │  │ Security        │    │    │   │
│  │  │  │ Memory          │    │    │   │
│  │  │  │ Execution       │    │    │   │
│  │  │  └─────────────────┘    │    │   │
│  │  └─────────────────────────┘    │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Storage: SQLite + ChromaDB            │
│  Isolation: Subprocess                 │
└─────────────────────────────────────────┘
```

### 2. Docker Mode

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER DEPLOYMENT                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Synapse   │  │  PostgreSQL │  │   ChromaDB  │          │
│  │   Core      │  │             │  │             │          │
│  │  Container  │  │  Container  │  │  Container  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                           │
│                   │   Redis     │                           │
│                   │   Cache     │                           │
│                   └─────────────┘                           │
│                                                             │
│  Isolation: Docker containers                               │
│  Orchestration: Docker Compose                              │
└─────────────────────────────────────────────────────────────┘
```

### 3. Distributed Mode

```
┌─────────────────────────────────────────────────────────────┐
│                  DISTRIBUTED DEPLOYMENT                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CONTROL PLANE                           │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐         │   │
│  │  │ Cluster   │ │ Scheduler │ │  Mesh     │         │   │
│  │  │ Manager   │ │           │ │ Orchestr. │         │   │
│  │  └───────────┘ └───────────┘ └───────────┘         │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                    │                    │        │
│         ▼                    ▼                    ▼        │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐ │
│  │   Node 1    │      │   Node 2    │      │   Node 3    │ │
│  │  Execution  │      │  Execution  │      │  Execution  │ │
│  └─────────────┘      └─────────────┘      └─────────────┘ │
│                                                             │
│  Storage: PostgreSQL cluster + ChromaDB cluster            │
│  Consensus: State hash agreement                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Resource Requirements

| Mode | CPU | RAM | Storage |
|------|-----|-----|----------|
| Local | 2 cores | 4GB | 10GB |
| Docker | 4 cores | 8GB | 50GB |
| Distributed | 8+ cores | 16GB+ | 100GB+ |

---

## High Availability

- **Multi-node deployment** with automatic failover
- **State replication** across nodes
- **Health monitoring** with automatic recovery
- **Rollback capability** on failure
