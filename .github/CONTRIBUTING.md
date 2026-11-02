# Как внести вклад в Synapse

Спасибо за интерес к проекту! Это руководство поможет вам эффективно участвовать в разработке.

---

## Быстрый старт

```bash
# 1. Fork репозитория на GitHub
# 2. Клонирование
git clone https://github.com/YOUR_USERNAME/synapse.git
cd synapse

# 3. Настройка окружения
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # добавьте тестовые ключи

# 4. Создание ветки
git checkout -b feature/your-feature-name
# или
git checkout -b fix/bug-description
```

---

## Перед отправкой Pull Request

```bash
# 1. Все тесты должны проходить
pytest tests/ -v --tb=short

# 2. Coverage должен быть ≥ 80%
pytest --cov=synapse --cov-report=term-missing --cov-fail-under=80

# 3. Линтинг без ошибок
flake8 synapse/ --max-line-length=100

# 4. Типы (опционально, но желательно)
mypy synapse/ --ignore-missing-imports
```

---

## Типы вклада

### 🐛 Исправление ошибок
1. Убедитесь что Issue существует или создайте его
2. Ветка: `fix/<описание>`
3. Напишите тест который воспроизводит баг
4. Исправьте баг
5. Убедитесь что тест проходит

### ✨ Новая функциональность
1. Сначала создайте Issue с описанием идеи
2. Дождитесь обсуждения и одобрения
3. Ветка: `feature/<название>`
4. Напишите тесты (TDD приветствуется)
5. Реализуйте функцию
6. Обновите документацию

### 📚 Документация
- Ветка: `docs/<что-именно>`
- Проверьте что примеры кода рабочие
- Актуализируйте версии и команды

### 🧪 Тесты
- Ветка: `test/<что-тестируется>`
- Тесты должны быть независимыми (не зависеть от порядка выполнения)
- Используйте `pytest.mark.*` для маркировки

---

## Стандарты кода

### Python
- Форматирование: **Black** (`line-length = 100`)
- Линтинг: **flake8**
- Типы: **mypy** (желательно)
- Docstrings: Google-style
- Все новые классы должны включать `protocol_version: str = "1.0"`

### Пример правильного кода
```python
"""Module docstring — всегда первой строкой."""
from typing import Optional, Dict, Any

PROTOCOL_VERSION: str = "1.0"


class MyComponent:
    """Компонент для XYZ.
    
    Args:
        name: Имя компонента
    """
    
    def __init__(self, name: str):
        self.name = name
        self.protocol_version = PROTOCOL_VERSION
    
    async def process(self, data: Dict[str, Any]) -> Optional[str]:
        """Обработать данные.
        
        Args:
            data: Входные данные
            
        Returns:
            Результат или None
        """
        try:
            return str(data)
        except Exception as e:
            raise ValueError(f"Processing failed: {e}") from e
```

### Тесты
```python
"""Tests for MyComponent."""
import pytest
from synapse.mymodule import MyComponent


class TestMyComponent:
    """Test MyComponent."""

    def test_init(self):
        comp = MyComponent("test")
        assert comp.name == "test"
        assert comp.protocol_version == "1.0"

    @pytest.mark.asyncio
    async def test_process(self):
        comp = MyComponent("test")
        result = await comp.process({"key": "value"})
        assert result is not None
```

---

## Именование коммитов

```
[Type] Краткое описание (до 72 символов)

Подробное описание (опционально)
```

Типы:
- `[Feature]` — новая функциональность
- `[Fix]` — исправление бага
- `[Docs]` — изменения документации
- `[Test]` — добавление/изменение тестов
- `[Refactor]` — рефакторинг без изменения поведения
- `[Security]` — исправление уязвимости
- `[Perf]` — улучшение производительности

Примеры:
```
[Fix] Add missing import os in api/app.py
[Feature] Implement broadcast() in ExternalAPIGateway
[Docs] Update API_REFERENCE with authentication details
[Test] Add tests for CapabilityManager.list_capabilities()
```

---

## Структура Pull Request

**Заголовок:** `[Type] Краткое описание`

**Описание:**
```markdown
## Что изменено
Краткое описание изменений.

## Почему
Ссылка на Issue (#123) или описание причины.

## Как тестировать
1. Шаги для проверки изменений

## Checklist
- [ ] Тесты написаны и проходят
- [ ] Coverage ≥ 80%
- [ ] Документация обновлена
- [ ] `flake8` без ошибок
```

---

## Вопросы и обсуждение

- **Issues:** баги, предложения, вопросы
- **Discussions:** архитектурные обсуждения, идеи
- **Email:** [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)
