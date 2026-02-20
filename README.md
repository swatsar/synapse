# 🧠 Synapse

**Distributed Cognitive Platform for Autonomous Agents**

[![PyPI version](https://badge.fury.io/py/synapse-agent.svg)](https://badge.fury.io/py/synapse-agent)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1085%20passed-brightgreen.svg)](https://github.com/synapse/synapse)
[![Coverage](https://img.shields.io/badge/coverage-81%25-green.svg)](https://github.com/synapse/synapse)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Production Ready](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)](https://github.com/synapse/synapse)

---

## 📖 Overview

Synapse is a production-ready distributed cognitive platform for autonomous AI agents. 
It combines the modularity of OpenClaw with the self-evolution capabilities of Agent Zero, 
while adding enterprise-grade security, reliability, and protocol versioning.

**Key Features:**
- 🔐 **Capability-Based Security Model** — Non-executable tokens with scoped permissions
- 🔄 **Self-Evolution Engine** — Agent Zero patterns for autonomous skill generation
- 🌐 **Multi-Provider LLM Abstraction** — 100+ providers via LiteLLM
- 📊 **Full Observability** — Prometheus metrics + structured logging
- 🛡️ **Human-in-the-Loop Approval** — Required for high-risk actions
- 📦 **Universal Deployment** — Windows/macOS/Linux/Docker support
- 🔒 **Isolation Enforcement** — Container/subprocess isolation per skill
- ⏪ **Rollback & Recovery** — Checkpoint-based state recovery

---

## 🚀 Quick Start

### Installation

```bash
# From PyPI
pip install synapse-agent

# From source
git clone https://github.com/synapse/synapse.git
cd synapse
pip install -e .
```

### Basic Usage

```python
from synapse import Agent

agent = Agent(
    llm_provider="openai",
    model="gpt-4o",
    api_key="your-api-key"
)

response = agent.run("Read the file /workspace/test.txt and summarize it")
print(response)
```

### Docker Deployment

```bash
cd docker
docker-compose up -d
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/INSTALLATION_GUIDE.md) | Full installation instructions |
| [Quick Start](docs/QUICKSTART.md) | 5-minute quick start guide |
| [API Reference](docs/API_REFERENCE.md) | Complete API documentation |
| [Security Guide](docs/SECURITY_GUIDE.md) | Security best practices |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Release Notes](docs/RELEASE_NOTES_v3.1.md) | Version 3.1.0 release notes |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│  UI (Web/GUI) │ Connectors (Telegram/Discord) │ REST API   │
├─────────────────────────────────────────────────────────────┤
│                    ORCHESTRATION LAYER                      │
│  Orchestrator │ Agents (Planner/Critic/Developer/Guardian) │
├─────────────────────────────────────────────────────────────┤
│                    EXECUTION LAYER                          │
│  Skills │ Isolation Policy │ Resource Manager │ Runtime    │
├─────────────────────────────────────────────────────────────┤
│                    INTELLIGENCE LAYER                       │
│  LLM Router │ Failure Strategy │ Learning Engine           │
├─────────────────────────────────────────────────────────────┤
│                    MEMORY LAYER                             │
│  Vector Store │ SQL Store │ Distributed Memory             │
├─────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                     │
│  Security │ Checkpoint │ Rollback │ Time Sync │ Audit      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security

Synapse implements a multi-layer security model:

1. **Capability-Based Access Control** — Non-executable tokens with scoped permissions
2. **Isolation Enforcement** — Container/subprocess isolation per skill based on risk level
3. **Human Approval** — Required for high-risk actions (risk_level ≥ 3)
4. **Full Audit Trail** — Immutable logging of all actions
5. **AST Security Analysis** — Static analysis of generated code

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run security tests
pytest tests/ -m security -v

# Run with coverage
pytest tests/ -v --cov=synapse --cov-report=html
```

**Test Results:**
- Total Tests: 1,085
- Passed: 1,085 (100%)
- Coverage: 81%

---

## 📦 Release

Current Version: **3.1.0**

```bash
# Build package
python -m build

# Verify package
twine check dist/*

# Upload to PyPI
twine upload dist/*

# Create Docker image
docker build -t synapse/platform:3.1.0 .
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](.github/CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Synapse builds upon excellent work from:
- [OpenClaw](https://github.com/openclaw/openclaw) — Connector patterns
- [Agent Zero](https://github.com/agent0ai/agent-zero) — Self-evolution patterns
- [Anthropic](https://docs.anthropic.com/) — Tool Use patterns
- [LangChain](https://github.com/langchain-ai/langchain) — LLM abstraction
- [LangGraph](https://github.com/langchain-ai/langgraph) — State graphs
- [browser-use](https://github.com/browser-use/browser-use) — Browser automation

---

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/synapse/synapse/issues)
- **Discussions:** [GitHub Discussions](https://github.com/synapse/synapse/discussions)

---

**Protocol Version:** 1.0 | **Spec Version:** 3.1 | **Status:** Production Ready ✅
