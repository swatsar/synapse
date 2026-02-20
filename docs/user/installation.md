# Installation Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  
**Last Updated:** 2026-02-20

---

## System Requirements

### Minimum Requirements
| Component | Requirement |
|-----------|------------|
| Python | 3.11+ |
| RAM | 4GB minimum (8GB recommended) |
| Disk Space | 10GB free |
| CPU | 2 cores minimum |

### Recommended Requirements
| Component | Requirement |
|-----------|------------|
| Python | 3.12+ |
| RAM | 16GB |
| Disk Space | 50GB free (for memory storage) |
| CPU | 4+ cores |

### Optional Dependencies
| Component | Purpose |
|-----------|---------|
| Docker | Containerized deployment |
| PostgreSQL | Production database |
| Qdrant/ChromaDB | Vector memory storage |
| Redis | Cache layer |

---

## Windows Installation

### Option 1: MSI Installer (Recommended)

1. **Download the installer**
   - Download `synapse-installer-3.1.0.msi` from the releases page

2. **Run the installer**
   - Right-click the `.msi` file
   - Select "Run as Administrator"
   - Follow the installation wizard

3. **Complete Configuration Wizard**
   - Launch Synapse from Start Menu
   - Complete the 5-step configuration wizard
   - Configure your LLM provider

4. **Verify Installation**
   ```cmd
   synapse --version
   # Output: Synapse v3.1.0 (protocol_version: 1.0)
   ```

### Option 2: PyPI Installation

```powershell
# Create virtual environment
python -m venv synapse-env
synapse-env\Scripts\activate

# Install Synapse
pip install synapse-agent

# Initialize configuration
synapse --init

# Launch GUI
synapse-gui
```

### Option 3: Docker Installation

```powershell
# Clone repository
git clone https://github.com/synapse/synapse.git
cd synapse

# Start with Docker Compose
docker-compose up -d

# Access GUI
# Open browser: http://localhost:8000
```

---

## macOS Installation

### Option 1: DMG Installer (Recommended)

1. **Download the DMG**
   - Download `synapse-3.1.0.dmg` from releases

2. **Install Application**
   - Open the DMG file
   - Drag Synapse to Applications folder

3. **First Launch**
   - Open Applications folder
   - Right-click Synapse → Open
   - Click "Open" in security dialog
   - Or run in Terminal:
     ```bash
     xattr -d com.apple.quarantine /Applications/Synapse.app
     ```

4. **Complete Setup**
   - Follow the Configuration Wizard
   - Grant necessary permissions

### Option 2: Homebrew

```bash
# Add tap
brew tap synapse/tap

# Install Synapse
brew install synapse

# Initialize
synapse --init

# Launch GUI
synapse-gui
```

### Option 3: PyPI Installation

```bash
# Create virtual environment
python3 -m venv synapse-env
source synapse-env/bin/activate

# Install
pip install synapse-agent

# Initialize
synapse --init
```

---

## Linux Installation

### Option 1: DEB Package (Debian/Ubuntu)

```bash
# Download package
wget https://github.com/synapse/synapse/releases/download/v3.1.0/synapse_3.1.0_amd64.deb

# Install
sudo apt install ./synapse_3.1.0_amd64.deb

# Or using dpkg
sudo dpkg -i synapse_3.1.0_amd64.deb
sudo apt-get install -f  # Fix dependencies

# Verify
synapse --version
```

### Option 2: RPM Package (RHEL/Fedora/CentOS)

```bash
# Download package
wget https://github.com/synapse/synapse/releases/download/v3.1.0/synapse-3.1.0.x86_64.rpm

# Install
sudo dnf install ./synapse-3.1.0.x86_64.rpm

# Or using yum
sudo yum install ./synapse-3.1.0.x86_64.rpm

# Verify
synapse --version
```

### Option 3: AppImage (Universal)

```bash
# Download AppImage
wget https://github.com/synapse/synapse/releases/download/v3.1.0/synapse-3.1.0.AppImage

# Make executable
chmod +x synapse-3.1.0.AppImage

# Run
./synapse-3.1.0.AppImage

# Install system-wide (optional)
sudo mv synapse-3.1.0.AppImage /usr/local/bin/synapse
```

### Option 4: PyPI Installation

```bash
# Create virtual environment
python3 -m venv synapse-env
source synapse-env/bin/activate

# Install
pip install synapse-agent

# Initialize
synapse --init

# Launch GUI
synapse-gui
```

### Option 5: Docker Installation

```bash
# Clone repository
git clone https://github.com/synapse/synapse.git
cd synapse

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f synapse-core
```

---

## Post-Installation Setup

### Step 1: Launch GUI Configurator

| Platform | Method |
|----------|--------|
| Windows | Start Menu → Synapse Configurator |
| macOS | Applications → Synapse |
| Linux | Applications → Synapse or `synapse-gui` |

### Step 2: Complete Configuration Wizard

1. **Welcome Page**
   - Select interface language (EN/RU)

2. **LLM Provider Configuration**
   - Select provider: OpenAI, Anthropic, Ollama, etc.
   - Enter API key (stored securely)
   - Test connection

3. **Storage Paths**
   - Configure data directory
   - Configure skills directory
   - Configure memory storage

4. **Security Mode**
   - **Safe Mode:** All actions require approval
   - **Supervised Mode:** Risk ≥ 3 requires approval
   - **Autonomous Mode:** Minimal restrictions

5. **Review & Apply**
   - Review all settings
   - Apply configuration

### Step 3: Verify Installation

```bash
# Check version
synapse --version

# Check health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "3.1",
#   "protocol_version": "1.0",
#   "timestamp": "2026-02-20T12:00:00Z"
# }
```

---

## Configuration Files Location

| Platform | Config Path |
|----------|-------------|
| Windows | `%APPDATA%\Synapse\config\` |
| macOS | `~/.config/synapse/` |
| Linux | `~/.config/synapse/` |
| Docker | `/app/config/` (mounted volume) |

### Main Configuration File

```yaml
# config.yaml
system:
  name: "Synapse"
  version: "3.1"
  protocol_version: "1.0"  # Required

llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      priority: 1

security:
  require_approval_for_risk: 3
  trusted_users: []
  audit_log_enabled: true

isolation_policy:
  unverified_skills: "container"
  risk_level_3_plus: "container"
  trusted_skills: "subprocess"

resources:
  default_limits:
    cpu_seconds: 60
    memory_mb: 512
    disk_mb: 100
    network_kb: 1024
```

---

## Uninstallation

### Windows
```cmd
# Via Programs and Features
# Or via command line:
msiexec /x {INSTALL_GUID}
```

### macOS
```bash
# Remove application
rm -rf /Applications/Synapse.app

# Remove configuration (optional)
rm -rf ~/.config/synapse/
```

### Linux

```bash
# DEB package
sudo apt remove synapse

# RPM package
sudo dnf remove synapse

# AppImage
rm synapse-3.1.0.AppImage

# Remove configuration (optional)
rm -rf ~/.config/synapse/
```

### PyPI Installation
```bash
pip uninstall synapse-agent
rm -rf ~/.config/synapse/
```

---

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [Configuration Guide](configuration.md) - Detailed configuration options
- [Security Guide](security.md) - Security best practices
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](troubleshooting.md) or open an issue on GitHub.
