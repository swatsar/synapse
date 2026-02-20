# Contributing to Synapse

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

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to conduct@synapse.dev.

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
pytest tests/ -v --cov=synapse

# Run specific test markers
pytest tests/ -m security -v
```

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported
2. Use the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md)
3. Include detailed reproduction steps

### Suggesting Features

1. Check if the feature has already been suggested
2. Use the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md)
3. Describe the use case and expected behavior

### Submitting Code

1. Create a feature branch
2. Make your changes
3. Add/update tests
4. Update documentation
5. Submit a pull request

## Pull Request Process

1. **Ensure all tests pass:** `pytest tests/ -v`
2. **Maintain code coverage:** Coverage should not decrease
3. **Follow coding standards:** See below
4. **Update documentation:** If applicable
5. **Request review:** From relevant code owners

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] No new warnings

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes

### Example

```python
from typing import Optional

def process_data(data: str, timeout: Optional[int] = None) -> bool:
    """
    Process the input data.
    
    Args:
        data: Input data to process
        timeout: Optional timeout in seconds
    
    Returns:
        True if successful, False otherwise
    """
    # Implementation
    return True
```

### Protocol Versioning

All modules must include:

```python
PROTOCOL_VERSION: str = "1.0"
```

All models must include:

```python
protocol_version: str = "1.0"
```

## Testing Guidelines

### Test Requirements

- Unit tests for all new functions
- Integration tests for workflows
- Security tests for security-related code
- Coverage > 80% for core modules

### Test Markers

```python
@pytest.mark.unit
def test_unit(): pass

@pytest.mark.integration
def test_integration(): pass

@pytest.mark.security
def test_security(): pass
```

## Documentation

### Code Documentation

- Use docstrings for all public APIs
- Include examples in docstrings
- Update README.md if needed

### User Documentation

- Update relevant docs in `docs/`
- Use clear, simple language
- Include code examples

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

- Open an issue for questions
- Join our discussions on GitHub
- Email: dev@synapse.dev

Thank you for contributing! 🎉
