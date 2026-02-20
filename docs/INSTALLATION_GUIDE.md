# Synapse Installation Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## 📋 System Requirements

### Minimum Requirements
- **Python:** 3.11+
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 2GB free space
- **OS:** Linux, macOS, Windows (WSL2)

### Recommended
- **Python:** 3.12+
- **RAM:** 16GB
- **Disk:** 10GB SSD
- **OS:** Ubuntu 22.04+ / macOS 13+

---

## 🚀 Installation Methods

### Method 1: pip (Recommended)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install Synapse
pip install synapse-platform

# Verify installation
synapse --version
```

### Method 2: From Source

```bash
# Clone repository
git clone https://github.com/synapse/synapse.git
cd synapse

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Run tests
pytest tests/ -v
```

### Method 3: Docker

```bash
# Pull image
docker pull synapse/platform:3.1

# Run container
docker run -d \
  --name synapse \
  -p 8000:8000 \
  -p 9090:9090 \
  synapse/platform:3.1

# Check health
curl http://localhost:8000/health
```

### Method 4: Docker Compose

```bash
# Clone repository
git clone https://github.com/synapse/synapse.git
cd synapse

# Start services
docker-compose up -d

# View logs
docker-compose logs -f synapse
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/synapse
VECTOR_DB_URL=http://localhost:6333

# Security
SECRET_KEY=your-secret-key-here
REQUIRE_COMMAND_SIGNING=true

# Protocol
PROTOCOL_VERSION=1.0
SPEC_VERSION=3.1
```

### Configuration File

Create `config/local.yaml`:

```yaml
system:
  name: "Synapse"
  version: "3.1"
  mode: "autonomous"

llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      provider: "openai"
      priority: 1

memory:
  vector_db: "chromadb"
  url: "http://localhost:8000"

security:
  require_approval_for_risk: 3
  rate_limit_per_minute: 60

isolation_policy:
  unverified_skills: "container"
  risk_level_3_plus: "container"
```

---

## 🗄️ Database Setup

### PostgreSQL

```bash
# Create database
createdb synapse

# Run migrations
synapse migrate
```

### ChromaDB

```bash
# Start ChromaDB
docker run -d -p 8000:8000 chromadb/chroma
```

---

## ✅ Verification

### Check Installation

```bash
# Run tests
pytest tests/ -v

# Check coverage
coverage run -m pytest
coverage report

# Start server
python -m synapse.main

# Health check
curl http://localhost:8000/health
```

### Expected Output

```json
{
  "status": "healthy",
  "version": "3.1",
  "protocol_version": "1.0",
  "services": {
    "database": "connected",
    "vector_db": "connected",
    "llm": "available"
  }
}
```

---

## 🔧 Troubleshooting

### Common Issues

**ImportError: No module named 'synapse'**
```bash
pip install -e .
```

**Database connection failed**
```bash
# Check PostgreSQL is running
pg_isready

# Check connection string
echo $DATABASE_URL
```

**LLM API errors**
```bash
# Verify API keys
echo $OPENAI_API_KEY
```

---

## 📚 Next Steps

- [Quick Start Guide](QUICKSTART.md)
- [Security Guide](SECURITY_GUIDE.md)
- [API Reference](API_REFERENCE.md)

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1
