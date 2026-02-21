# 🤝 Contributing to Synapse

Thank you for your interest in contributing to Synapse! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Contact](#contact)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainer.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/synapse.git`
3. Create a branch: `git checkout -b feature/my-feature`

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (optional)
- Docker (optional)

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Install in development mode
pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=synapse --cov-report=html

# Run specific test categories
pytest tests/ -v -m "security"
pytest tests/ -v -m "integration"
```

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/swatsar/synapse/issues)
2. If not, create a new issue using the Bug Report template
3. Include as much detail as possible:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details

### Suggesting Features

1. Check if the feature has already been suggested
2. Create a new issue using the Feature Request template
3. Describe the feature and its benefits

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`pytest tests/ -v`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Pull Request Process

1. Ensure your PR follows the coding standards
2. Update documentation if needed
3. Add tests for new functionality
4. Ensure all tests pass
5. Request review from maintainers

## Coding Standards

### Python Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Write docstrings for all classes and methods
- Maximum line length: 100 characters

### Code Quality

```python
# Good example
def calculate_total(items: list[dict]) -> float:
    """Calculate total price of items.
    
    Args:
        items: List of item dictionaries with 'price' key
    
    Returns:
        Total price as float
    """
    return sum(item.get('price', 0) for item in items)
```

### Security

- Never commit secrets or API keys
- Always validate user input
- Use parameterized queries for database operations
- Follow the principle of least privilege

## Testing Guidelines

### Test Categories

| Category | Marker | Description |
|----------|--------|-------------|
| Unit | `@pytest.mark.unit` | Single component tests |
| Integration | `@pytest.mark.integration` | Multi-component tests |
| Security | `@pytest.mark.security` | Security-focused tests |
| Performance | `@pytest.mark.performance` | Performance benchmarks |

### Test Requirements

- All new code must have tests
- Minimum 80% code coverage for core modules
- Minimum 90% coverage for security modules
- All tests must pass before merging

## Documentation

### Code Documentation

- Use docstrings for all public functions and classes
- Include type hints
- Provide usage examples

### Project Documentation

- Update README.md for user-facing changes
- Update API_REFERENCE.md for API changes
- Update SECURITY_GUIDE.md for security changes

## Contact

### Project Maintainer

**Евгений Савченко**
- 📧 Email: [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)
- 📍 Location: Россия, Саратов
- 🐙 GitHub: [@swatsar](https://github.com/swatsar)

### Reporting Security Issues

For security-related issues, please email directly to [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com) instead of using the public issue tracker.

---

Thank you for contributing to Synapse! 🚀
