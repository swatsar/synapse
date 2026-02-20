# Synapse Troubleshooting Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## 🔍 Common Issues

### Installation Issues

#### ImportError: No module named 'synapse'

**Problem:** Python cannot find the synapse module.

**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Install in development mode
pip install -e .

# Verify installation
python -c "import synapse; print(synapse.PROTOCOL_VERSION)"
```

#### Dependency Conflicts

**Problem:** Package version conflicts.

**Solution:**
```bash
# Clear cache and reinstall
pip cache purge
pip install --force-reinstall -r requirements.txt
```

---

### Database Issues

#### Database Connection Failed

**Problem:** Cannot connect to PostgreSQL.

**Solution:**
```bash
# Check PostgreSQL is running
pg_isready

# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

#### Migration Errors

**Problem:** Database migrations fail.

**Solution:**
```bash
# Reset database (WARNING: destroys data)
dropdb synapse
createdb synapse
synapse migrate
```

---

### LLM Provider Issues

#### OpenAI API Errors

**Problem:** OpenAI API returns errors.

**Solution:**
```bash
# Verify API key
echo $OPENAI_API_KEY

# Test API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check rate limits
# Wait and retry if rate limited
```

#### LLM Timeout

**Problem:** LLM requests timeout.

**Solution:**
```yaml
# Increase timeout in config
llm:
  timeout_seconds: 60  # Increase from default 30
```

#### Fallback Not Working

**Problem:** LLM fallback doesn't activate.

**Solution:**
```python
# Check failure strategy configuration
from synapse.llm.failure_strategy import LLMFailureStrategy

strategy = LLMFailureStrategy(providers)
# Ensure multiple providers configured
```

---

### Security Issues

#### Capability Denied

**Problem:** Operation blocked due to missing capabilities.

**Solution:**
```python
# Check required capabilities
result = await security.check_capabilities(
    required=["fs:read:/workspace/**"],
    context=context
)

print(f"Approved: {result.approved}")
print(f"Blocked: {result.blocked_capabilities}")

# Grant capabilities in context
context.capabilities = ["fs:read:/workspace/**"]
```

#### Human Approval Timeout

**Problem:** Waiting for human approval times out.

**Solution:**
```yaml
# Increase approval timeout
security:
  approval_timeout_seconds: 3600  # 1 hour
```

#### Isolation Container Fails

**Problem:** Container isolation fails to start.

**Solution:**
```bash
# Check Docker is running
docker ps

# Check Docker permissions
sudo usermod -aG docker $USER

# Restart Docker
sudo systemctl restart docker
```

---

### Memory Issues

#### Vector Store Connection Failed

**Problem:** Cannot connect to ChromaDB/Qdrant.

**Solution:**
```bash
# Check ChromaDB is running
curl http://localhost:8000/api/v1/heartbeat

# Start ChromaDB
docker run -d -p 8000:8000 chromadb/chroma

# Check configuration
echo $VECTOR_DB_URL
```

#### Memory Recall Returns Empty

**Problem:** Memory queries return no results.

**Solution:**
```python
# Check if data exists
from synapse.memory import VectorStore

store = VectorStore()
count = await store.count()
print(f"Total entries: {count}")

# Lower similarity threshold
query = MemoryQuery(
    query_text="test",
    limit=10,
    min_similarity=0.5  # Lower threshold
)
```

---

### Performance Issues

#### Slow Task Execution

**Problem:** Tasks take too long.

**Solution:**
```bash
# Check resource usage
top

# Check Prometheus metrics
curl http://localhost:9090/metrics | grep synapse

# Increase resource limits
resource_limits:
  cpu_seconds: 120
  memory_mb: 1024
```

#### High Memory Usage

**Problem:** Memory usage grows over time.

**Solution:**
```python
# Trigger memory consolidation
from synapse.memory import MemoryConsolidator

consolidator = MemoryConsolidator()
await consolidator.run()

# Check for memory leaks
import gc
gc.collect()
```

---

### Network Issues

#### API Not Responding

**Problem:** HTTP API returns no response.

**Solution:**
```bash
# Check server is running
ps aux | grep synapse

# Check port is open
netstat -tlnp | grep 8000

# Check logs
tail -f /var/log/synapse/server.log
```

#### WebSocket Connection Failed

**Problem:** WebSocket connections fail.

**Solution:**
```bash
# Check WebSocket endpoint
wscat -c ws://localhost:8000/ws

# Check proxy configuration
# Ensure WebSocket upgrade headers are passed
```

---

## 🐛 Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Check Audit Logs

```bash
# View recent audit entries
tail -100 /var/log/synapse/audit.log | jq

# Search for errors
grep "error" /var/log/synapse/audit.log
```

### Run Diagnostics

```bash
# Run diagnostic script
synapse diagnose

# Check all components
synapse health-check
```

---

## 📊 Monitoring

### Prometheus Metrics

```bash
# Get all Synapse metrics
curl http://localhost:9090/metrics | grep synapse

# Check specific metrics
curl http://localhost:9090/metrics | grep synapse_tasks_total
```

### Grafana Dashboard

1. Open Grafana at `http://localhost:3000`
2. Import Synapse dashboard
3. Check for anomalies

---

## 🔄 Recovery

### Rollback to Checkpoint

```python
from synapse.core.rollback import RollbackManager

rollback = RollbackManager()
result = await rollback.execute_rollback(
    checkpoint_id="cp_123",
    reason="Recovery from error"
)
```

### Reset State

```bash
# Stop all services
docker-compose down

# Clear data
rm -rf data/

# Restart
docker-compose up -d
```

---

## 📞 Getting Help

### Check Documentation

- [Installation Guide](INSTALLATION_GUIDE.md)
- [Security Guide](SECURITY_GUIDE.md)
- [API Reference](API_REFERENCE.md)

### Report Issues

1. Collect diagnostic information:
```bash
synapse diagnose > diagnostic.txt
```

2. Create issue with:
   - Error messages
   - Steps to reproduce
   - Diagnostic output
   - Protocol version

---

## ✅ Quick Fixes Checklist

- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] Database running
- [ ] Vector store running
- [ ] API keys configured
- [ ] Ports not blocked
- [ ] Sufficient disk space
- [ ] Sufficient memory

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1
