# Troubleshooting Guide

**Protocol Version:** 1.0  
**Last Updated:** 2026-02-20

---

## Overview

This guide covers common issues and their solutions. If you encounter a problem not listed here, please open an issue on GitHub.

---

## Installation Issues

### Windows

#### "Installer requires admin rights"

**Problem:** The MSI installer requires administrator privileges.

**Solution:**
1. Right-click the `.msi` file
2. Select "Run as Administrator"
3. If UAC prompts, click "Yes"

#### "Windows protected your PC"

**Problem:** Windows SmartScreen blocks the installer.

**Solution:**
1. Click "More info"
2. Click "Run anyway"
3. Or disable SmartScreen temporarily:
   - Settings → Update & Security → Windows Security
   - App & browser control → Reputation-based protection settings
   - Turn off "Check apps and files"

#### "Installation failed with error code 1603"

**Problem:** Generic installation failure.

**Solution:**
1. Check Windows Event Viewer:
   - Press `Win + R`, type `eventvwr`
   - Windows Logs → Application
   - Look for MSIInstaller errors
2. Try installing with logging:
   ```cmd
   msiexec /i synapse-installer.msi /L*V install.log
   ```
3. Check `install.log` for specific errors

---

### macOS

#### "App can't be opened because it is from an unidentified developer"

**Problem:** macOS Gatekeeper blocks unsigned apps.

**Solution:**

**Option 1:**
1. Go to System Preferences → Privacy & Security
2. Click "Open Anyway" next to security warning
3. Click "Open" in confirmation dialog

**Option 2:**
```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine /Applications/Synapse.app
```

**Option 3:**
```bash
# Allow from anywhere (not recommended)
sudo spctl --master-disable
```

#### "App is damaged and can't be opened"

**Problem:** Corrupted download or signature issue.

**Solution:**
1. Re-download the DMG file
2. Verify checksum:
   ```bash
   shasum -a 256 synapse-3.1.0.dmg
   # Compare with published checksum
   ```
3. If still failing:
   ```bash
   # Remove extended attributes
   xattr -c /Applications/Synapse.app
   ```

---

### Linux

#### "Permission denied" when running AppImage

**Problem:** AppImage lacks execute permission.

**Solution:**
```bash
chmod +x synapse-3.1.0.AppImage
./synapse-3.1.0.AppImage
```

#### "Cannot open shared object file" (missing libraries)

**Problem:** Missing system libraries.

**Solution:**

**Debian/Ubuntu:**
```bash
sudo apt install libfuse2 libssl3
```

**RHEL/Fedora:**
```bash
sudo dnf install fuse-libs openssl-libs
```

**Arch Linux:**
```bash
sudo pacman -S fuse2 openssl
```

#### "Package architecture mismatch"

**Problem:** Wrong package architecture.

**Solution:**
1. Check your architecture:
   ```bash
   uname -m
   # x86_64 = amd64
   # aarch64 = arm64
   ```
2. Download correct package for your architecture

---

## Configuration Issues

### "LLM connection failed"

**Problem:** Cannot connect to LLM provider.

**Solutions:**

**1. Check API Key:**
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Or in config.yaml
llm:
  providers:
    openai:
      api_key: "sk-..."
```

**2. Test Connection Manually:**
```bash
# OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

**3. Check Network:**
```bash
# Test connectivity
ping api.openai.com

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**4. Check Firewall:**
- Ensure outbound HTTPS (port 443) is allowed
- Check corporate firewall rules

**5. Check Rate Limits:**
- Verify you haven't exceeded API rate limits
- Check provider dashboard for usage

---

### "Configuration file not found"

**Problem:** Synapse cannot find configuration files.

**Solution:**

**1. Initialize Configuration:**
```bash
synapse --init
```

**2. Check Config Path:**
```bash
# Show config location
synapse --config-path

# Expected output:
# /home/user/.config/synapse/config.yaml
```

**3. Create Manually:**
```bash
mkdir -p ~/.config/synapse
cp /path/to/template/config.yaml ~/.config/synapse/
```

---

### "Invalid configuration"

**Problem:** Configuration validation fails.

**Solution:**

**1. Validate Configuration:**
```bash
synapse --validate-config
```

**2. Common Issues:**

| Error | Solution |
|-------|----------|
| Missing protocol_version | Add `protocol_version: "1.0"` |
| Invalid isolation_type | Use: main_process, subprocess, container |
| Invalid priority | Use: 1, 2, 3 (IntEnum) |
| Missing required field | Check spec for required fields |
| YAML syntax error | Check indentation and quotes |

**3. Example Valid Config:**
```yaml
system:
  name: "Synapse"
  version: "3.1"
  protocol_version: "1.0"

llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      priority: 1

security:
  require_approval_for_risk: 3
```

---

## Runtime Issues

### "Capability check failed"

**Problem:** Skill execution blocked due to missing capabilities.

**Solution:**

**1. Check Required Capabilities:**
```bash
synapse skills show <skill_name>
```

**2. Grant Capabilities:**
```bash
# Via CLI
synapse capabilities grant \
  --user user@example.com \
  --cap "fs:read:/workspace/**"

# Via API
POST /api/v1/capabilities/grant
{
  "user_id": "user@example.com",
  "capabilities": ["fs:read:/workspace/**"],
  "protocol_version": "1.0"
}
```

**3. Via GUI:**
1. Open Security Settings
2. Navigate to Capabilities
3. Add required capabilities
4. Save changes

---

### "Skill execution timeout"

**Problem:** Skill execution exceeds time limit.

**Solution:**

**1. Increase Timeout:**
```yaml
# config.yaml
resources:
  default_limits:
    cpu_seconds: 120  # Increase from 60
```

**2. Check Resource Usage:**
```bash
# Monitor resources
synapse metrics
```

**3. Simplify Task:**
- Break complex tasks into smaller steps
- Reduce data size
- Optimize skill implementation

---

### "Memory consolidation failed"

**Problem:** Memory cleanup process fails.

**Solution:**

**1. Check Vector DB:**
```bash
# ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Qdrant
curl http://localhost:6333/healthz
```

**2. Check Disk Space:**
```bash
df -h ~/.local/share/synapse/
```

**3. Check Logs:**
```bash
tail -f ~/.local/share/synapse/logs/synapse.log
```

**4. Manual Consolidation:**
```bash
synapse memory consolidate --force
```

---

### "Human approval timeout"

**Problem:** No response to approval request.

**Solution:**

**1. Check Notification Settings:**
```yaml
# config.yaml
notifications:
  enabled: true
  email: true
  telegram: true
```

**2. Extend Timeout:**
```yaml
security:
  approval_timeout_seconds: 3600  # 1 hour
```

**3. Manual Approval:**
```bash
# List pending approvals
synapse approvals list

# Approve manually
synapse approvals approve <request_id>
```

---

## Docker Issues

### "Container won't start"

**Problem:** Docker container fails to start.

**Solution:**

**1. Check Logs:**
```bash
docker-compose logs synapse-core
```

**2. Check Dependencies:**
```bash
docker-compose ps
# Ensure db, qdrant, redis are healthy
```

**3. Rebuild Container:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**4. Check Resources:**
```bash
docker stats
```

---

### "Database connection failed"

**Problem:** Cannot connect to PostgreSQL.

**Solution:**

**1. Check Database Status:**
```bash
docker-compose exec db pg_isready
```

**2. Check Connection String:**
```yaml
# config.yaml
memory:
  sql_db: "postgresql://user:pass@db:5432/synapse"
```

**3. Reset Database:**
```bash
docker-compose exec db psql -U user -d synapse
# Run migrations
```

---

## Performance Issues

### "Slow response times"

**Problem:** System responds slowly.

**Solution:**

**1. Check Resource Usage:**
```bash
# CPU and Memory
top -p $(pgrep -f synapse)

# Disk I/O
iotop -p $(pgrep -f synapse)
```

**2. Check LLM Latency:**
```bash
synapse metrics --filter llm_latency
```

**3. Optimize Configuration:**
```yaml
# Increase cache
memory:
  cache:
    enabled: true
    max_size_mb: 512

# Reduce logging
observability:
  log_level: "WARNING"
```

**4. Scale Resources:**
```yaml
resources:
  max_concurrent_skills: 10
  total_memory_mb: 8192
```

---

### "High memory usage"

**Problem:** Memory consumption is too high.

**Solution:**

**1. Check Memory Distribution:**
```bash
synapse memory stats
```

**2. Force Consolidation:**
```bash
synapse memory consolidate --force
```

**3. Reduce Cache Size:**
```yaml
memory:
  cache:
    max_size_mb: 128
```

**4. Limit Concurrent Skills:**
```yaml
resources:
  max_concurrent_skills: 3
```

---

## Log Locations

| Platform | Log Path |
|----------|----------|
| Windows | `%APPDATA%\Synapse\logs\` |
| macOS | `~/Library/Logs/Synapse/` |
| Linux | `~/.local/share/synapse/logs/` |
| Docker | `docker logs synapse-core` |

### Viewing Logs

```bash
# Tail logs
tail -f ~/.local/share/synapse/logs/synapse.log

# Search logs
grep "ERROR" ~/.local/share/synapse/logs/synapse.log

# Via Docker
docker-compose logs -f --tail=100 synapse-core
```

---

## Diagnostic Commands

### System Status
```bash
# Overall status
synapse status

# Health check
synapse health

# Version info
synapse --version
```

### Security Status
```bash
# Security status
synapse security status

# List capabilities
synapse capabilities list

# View audit log
synapse audit view --tail 100
```

### Memory Status
```bash
# Memory stats
synapse memory stats

# Vector DB status
synapse memory vector-status

# Cache status
synapse memory cache-status
```

### LLM Status
```bash
# LLM status
synapse llm status

# Test connection
synapse llm test-connection

# Token usage
synapse llm token-usage
```

---

## Getting Help

### Before Asking

1. **Check Documentation:**
   - [Installation Guide](installation.md)
   - [Configuration Guide](configuration.md)
   - [Security Guide](security.md)

2. **Check Logs:**
   - Review error messages
   - Check for recent changes

3. **Try Basic Fixes:**
   - Restart Synapse
   - Clear cache
   - Re-run with verbose logging

### Reporting Issues

When reporting an issue, include:

1. **System Information:**
   ```bash
   synapse --version
   uname -a
   python --version
   ```

2. **Error Message:**
   - Full error text
   - Stack trace if available

3. **Steps to Reproduce:**
   - Exact commands used
   - Configuration files

4. **Logs:**
   ```bash
   # Attach relevant logs
   tail -100 ~/.local/share/synapse/logs/synapse.log
   ```

### Support Channels

- **GitHub Issues:** https://github.com/synapse/synapse/issues
- **Documentation:** docs/
- **Community:** Telegram/Discord

---

## Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| E001 | Configuration not found | Run `synapse --init` |
| E002 | Invalid configuration | Check YAML syntax |
| E003 | LLM connection failed | Check API key and network |
| E004 | Capability denied | Grant required capabilities |
| E005 | Timeout exceeded | Increase timeout or simplify task |
| E006 | Memory error | Check memory limits |
| E007 | Database error | Check database connection |
| E008 | Permission denied | Check file permissions |
| E009 | Resource exhausted | Check resource limits |
| E010 | Approval required | Wait for human approval |

---

**Protocol Version:** 1.0  
**Need More Help?** Open an issue on GitHub with full details.
