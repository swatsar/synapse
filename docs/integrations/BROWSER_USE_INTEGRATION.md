# 📎 PROJECT SYNAPSE: BROWSER-USE INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## ⚠️ ВАЖНОЕ ПРИМЕЧАНИЕ

**О проекте browser-use:** Это проект для **AI-driven browser automation**, позволяющий LLM-агентам взаимодействовать с веб-страницами, выполнять задачи в браузере, и автоматизировать веб-работу.

**Ключевые возможности browser-use:**
- Управление браузером через LLM
- DOM понимание и навигация
- Web scraping с семантическим пониманием
- Автоматизация веб-задач
- Интеграция с Playwright/Selenium

**Подход этого документа:** Анализирует **публично известные возможности browser-use** для интеграции в Synapse с учётом security model, capability-based access, и protocol versioning.

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к:
- `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md` (основная спецификация)
- `OPENCLAW_INTEGRATION.md` (интеграция OpenClaw)
- `AGENT_ZERO_INTEGRATION.md` (интеграция Agent Zero)
- `ANTHROPIC_PATTERNS_INTEGRATION.md` (паттерны Anthropic)
- `CLAUDE_CODE_INTEGRATION.md` (паттерны Claude Code)
- `CODEX_INTEGRATION.md` (паттерны OpenAI Codex)

Он описывает стратегию интеграции полезных паттернов из **browser-use** в платформу Synapse, особенно для **Web Automation**, **Browser Control**, и **DOM Interaction** компонентов.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Паттернов для Заимствования | Статус |
|---------|---------------------|------------------------------|--------|
| Browser Automation | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| DOM Understanding | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Web Navigation | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Element Selection | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Web Scraping | ⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| Screenshot Analysis | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Security Model | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐⭐ | ~10% | ❌ НЕ брать |

---

## 1️⃣ BROWSER AUTOMATION PATTERNS (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | browser-use Pattern | Файл Synapse | Действие |
|-----------|---------------------|--------------|----------|
| Browser Controller | Playwright automation | `synapse/skills/browser_controller.py` | Адаптировать с capability checks |
| DOM Parser | Semantic DOM understanding | `synapse/skills/dom_parser.py` | Адаптировать с security filtering |
| Navigation Manager | Smart page navigation | `synapse/skills/navigation_manager.py` | Адаптировать с whitelist domains |
| Element Finder | AI-powered element selection | `synapse/skills/element_finder.py` | Адаптировать with validation |
| Form Filler | Automatic form completion | `synapse/skills/form_filler.py` | Адаптировать с data protection |
| Screenshot Analyzer | Visual page understanding | `synapse/skills/screenshot_analyzer.py` | Адаптировать с privacy controls |

### 1.2 Secure Browser Controller

```python
# browser-use patterns → synapse/skills/browser_controller.py
from typing import Dict, List, Optional, Literal
from skills.base import BaseSkill, SkillManifest
from core.models import ExecutionContext, ResourceLimits
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

class SecureBrowserController(BaseSkill):
    """
    Безопасное управление браузером.
    Адаптировано из browser-use patterns.
    
    🔹 Наше дополнение: Capability-based access + domain whitelist + audit logging
    """
    
    manifest = SkillManifest(
        name="secure_browser_controller",
        version="1.0.0",
        description="Безопасное управление браузером с проверками безопасности",
        author="synapse_core",
        inputs={
            "action": "str",  # navigate, click, fill, screenshot, scrape
            "url": "str",
            "selector": "str",
            "value": "str",
            "timeout": "int"
        },
        outputs={
            "success": "bool",
            "result": "any",
            "screenshot": "str",
            "content": "str"
        },
        required_capabilities=[
            "network:http",
            "browser:automation"
        ],
        risk_level=4,  # 🔹 Высокий риск — доступ к вебу
        isolation_type="container",
        timeout_seconds=120,
        protocol_version="1.0"
    )
    
    # 🔹 Whitelist разрешённых доменов (критично для безопасности)
    ALLOWED_DOMAINS = [
        'localhost',
        '127.0.0.1',
        'example.com',
        'github.com',
        'pypi.org',
        'docs.python.org',
        # Добавить домены из конфигурации
    ]
    
    # 🔹 Blocked domains (критично для безопасности)
    BLOCKED_DOMAINS = [
        'malware',
        'phishing',
        'hack',
        'exploit',
        # Добавить из threat intelligence feeds
    ]
    
    # 🔹 Запрещённые действия
    BLOCKED_ACTIONS = [
        'download_executable',
        'upload_sensitive',
        'bypass_captcha',
        'automate_login',  # Требуется human approval
        'access_dark_web'
    ]
    
    def __init__(self, llm_provider, security_manager, config: dict):
        self.llm = llm_provider
        self.security = security_manager
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        super().__init__()
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Безопасное выполнение браузерных действий"""
        
        action = kwargs.get('action', 'navigate')
        url = kwargs.get('url', '')
        selector = kwargs.get('selector', '')
        value = kwargs.get('value', '')
        timeout = kwargs.get('timeout', 30000)
        
        # 1. 🔹 Проверка capabilities (наше дополнение из spec v3.1)
        if not await self._check_capabilities(context):
            return SkillResult(
                success=False,
                error="Missing required capabilities for browser automation",
                metrics={}
            )
        
        # 2. 🔹 Валидация URL (наше дополнение — критично)
        url_validation = await self._validate_url(url)
        if not url_validation['allowed']:
            await self.security.log_security_event(
                event_type="blocked_browser_access",
                user_id=context.agent_id,
                details={
                    'url': url,
                    'reason': url_validation['reason'],
                    'protocol_version': "1.0"
                }
            )
            return SkillResult(
                success=False,
                error=f"URL blocked: {url_validation['reason']}",
                metrics={}
            )
        
        # 3. 🔹 Проверка действия на безопасность (наше дополнение)
        action_validation = await self._validate_action(action, url, selector)
        if not action_validation['allowed']:
            return SkillResult(
                success=False,
                error=f"Action blocked: {action_validation['reason']}",
                metrics={}
            )
        
        # 4. 🔹 Human approval для高风险 действий (наше дополнение)
        if await self._requires_human_approval(action, url):
            approval = await self.security.request_human_approval(
                action_type="browser_automation",
                details={'action': action, 'url': url, 'selector': selector},
                trace_id=context.trace_id
            )
            if not approval.approved:
                return SkillResult(
                    success=False,
                    error="Human approval denied for browser action",
                    metrics={}
                )
        
        # 5. Инициализация браузера (паттерн из browser-use)
        try:
            await self._initialize_browser(context)
            
            # 6. Выполнение действия
            result = await self._execute_browser_action(
                action=action,
                url=url,
                selector=selector,
                value=value,
                timeout=timeout
            )
            
            # 7. 🔹 Audit logging (наше дополнение из spec v3.1)
            await self.security.audit_action(
                action=f"browser_{action}",
                result=str(result),
                context=context
            )
            
            return SkillResult(
                success=True,
                result=result,
                metrics={
                    'action': action,
                    'url': url,
                    'protocol_version': "1.0"
                }
            )
            
        except Exception as e:
            # 🔹 Безопасная очистка при ошибке
            await self._cleanup_browser()
            return SkillResult(
                success=False,
                error=f"Browser action failed: {str(e)}",
                metrics={}
            )
    
    async def _validate_url(self, url: str) -> dict:
        """
        Валидация URL на безопасность.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            
            # Проверка схемы
            if parsed.scheme not in ['http', 'https']:
                return {
                    'allowed': False,
                    'reason': f"Invalid scheme: {parsed.scheme}. Only http/https allowed"
                }
            
            # Проверка домена в whitelist
            domain = parsed.netloc.split(':')[0]  # Remove port
            
            # Проверка blocked domains
            for blocked in self.BLOCKED_DOMAINS:
                if blocked in domain.lower():
                    return {
                        'allowed': False,
                        'reason': f"Domain blocked: {domain}"
                    }
            
            # Если whitelist включён — проверка
            if self.config.get('enforce_domain_whitelist', True):
                domain_allowed = any(
                    allowed in domain or domain == allowed
                    for allowed in self.ALLOWED_DOMAINS
                )
                if not domain_allowed:
                    return {
                        'allowed': False,
                        'reason': f"Domain not in whitelist: {domain}"
                    }
            
            # Проверка на localhost bypass attempts
            if 'localhost' in domain or '127.0.0.1' in domain:
                # Разрешено только если явно в конфиге
                if not self.config.get('allow_localhost', False):
                    return {
                        'allowed': False,
                        'reason': "Localhost access disabled in configuration"
                    }
            
            return {'allowed': True, 'reason': 'URL validated'}
            
        except Exception as e:
            return {
                'allowed': False,
                'reason': f"URL validation error: {str(e)}"
            }
    
    async def _validate_action(self, action: str, url: str, selector: str) -> dict:
        """
        Валидация действия на безопасность.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        # Проверка на запрещённые действия
        for blocked in self.BLOCKED_ACTIONS:
            if blocked in action.lower():
                return {
                    'allowed': False,
                    'reason': f"Blocked action: {blocked}"
                }
        
        # Проверка селектора на опасные паттерны
        if selector:
            dangerous_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="passwd"]',
                'input[type="file"]',
                'input[name="credit"]',
                'input[name="card"]'
            ]
            for dangerous in dangerous_selectors:
                if dangerous in selector.lower():
                    return {
                        'allowed': False,
                        'reason': f"Sensitive element access blocked: {selector}",
                        'requires_approval': True
                    }
        
        return {'allowed': True, 'reason': 'Action validated'}
    
    async def _requires_human_approval(self, action: str, url: str) -> bool:
        """
        Определение необходимости human approval.
        🔹 Наше дополнение из spec v3.1
        """
        # Высокий риск действия
        high_risk_actions = ['form_fill', 'click', 'upload', 'download']
        if action in high_risk_actions:
            return True
        
        # Внешние домены
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.split(':')[0]
        
        # Если не localhost и не из trusted domains
        trusted = self.config.get('trusted_domains', [])
        if domain not in trusted and domain not in ['localhost', '127.0.0.1']:
            return True
        
        return False
    
    async def _initialize_browser(self, context: ExecutionContext):
        """Инициализация браузера с безопасными настройками"""
        playwright = await async_playwright().start()
        
        # 🔹 Безопасные настройки браузера (наше дополнение)
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Synapse Agent; protocol_version/1.0)',
            # 🔹 Блокировка опасных ресурсов
            ignore_https_errors=False,
            # 🔹 Ограничение разрешений
            permissions=[],
            # 🔹 Блокировка cookies из ненадёжных источников
            storage_state=None
        )
        
        self.page = await self.context.new_page()
        
        # 🔹 Установка resource limits (наше дополнение)
        await self.page.set_extra_http_headers({
            'X-Synapse-Protocol-Version': '1.0',
            'X-Synapse-Agent-ID': context.agent_id,
            'X-Synapse-Trace-ID': context.trace_id
        })
    
    async def _execute_browser_action(self,
                                       action: str,
                                       url: str,
                                       selector: str,
                                       value: str,
                                       timeout: int) -> dict:
        """Выполнение браузерного действия (паттерн из browser-use)"""
        
        actions = {
            'navigate': lambda: self._navigate(url, timeout),
            'click': lambda: self._click(selector, timeout),
            'fill': lambda: self._fill(selector, value, timeout),
            'screenshot': lambda: self._screenshot(),
            'scrape': lambda: self._scrape(selector),
            'evaluate': lambda: self._evaluate(value),
            'wait': lambda: self._wait(selector, timeout),
        }
        
        if action not in actions:
            raise ValueError(f"Unknown browser action: {action}")
        
        return await actions[action]()
    
    async def _navigate(self, url: str, timeout: int) -> dict:
        """Навигация к URL"""
        response = await self.page.goto(url, timeout=timeout, wait_until='networkidle')
        return {
            'status': response.status,
            'url': self.page.url,
            'title': await self.page.title()
        }
    
    async def _click(self, selector: str, timeout: int) -> dict:
        """Клик по элементу"""
        await self.page.click(selector, timeout=timeout)
        await self.page.wait_for_load_state('networkidle')
        return {'clicked': selector, 'url': self.page.url}
    
    async def _fill(self, selector: str, value: str, timeout: int) -> dict:
        """Заполнение формы"""
        # 🔹 Дополнительная проверка для чувствительных полей
        if await self._is_sensitive_field(selector):
            await self.security.log_security_event(
                event_type="sensitive_field_fill",
                user_id=self.context.agent_id if hasattr(self.context, 'agent_id') else "unknown",
                details={'selector': selector}
            )
        
        await self.page.fill(selector, value, timeout=timeout)
        return {'filled': selector, 'length': len(value)}
    
    async def _screenshot(self) -> dict:
        """Скриншот страницы"""
        screenshot = await self.page.screenshot(full_page=True)
        return {
            'screenshot': screenshot.hex(),
            'size': len(screenshot),
            'url': self.page.url
        }
    
    async def _scrape(self, selector: str) -> dict:
        """Scraping контента"""
        if selector:
            elements = await self.page.query_selector_all(selector)
            content = [await el.inner_text() for el in elements]
        else:
            content = await self.page.content()
        
        return {
            'content': content,
            'url': self.page.url,
            'elements_count': len(elements) if selector else 1
        }
    
    async def _evaluate(self, javascript: str) -> dict:
        """Выполнение JavaScript (требует осторожности)"""
        # 🔹 Ограничение на опасные JS функции
        dangerous_js = ['eval', 'exec', 'Function', 'setTimeout', 'setInterval']
        for dangerous in dangerous_js:
            if dangerous in javascript:
                raise ValueError(f"Dangerous JavaScript function: {dangerous}")
        
        result = await self.page.evaluate(javascript)
        return {'result': result}
    
    async def _wait(self, selector: str, timeout: int) -> dict:
        """Ожидание элемента"""
        await self.page.wait_for_selector(selector, timeout=timeout)
        return {'waited': selector, 'found': True}
    
    async def _is_sensitive_field(self, selector: str) -> bool:
        """Проверка является ли поле чувствительным"""
        sensitive_patterns = ['password', 'passwd', 'secret', 'token', 'credit', 'card']
        return any(pattern in selector.lower() for pattern in sensitive_patterns)
    
    async def _cleanup_browser(self):
        """Безопасная очистка браузера"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        self.page = None
        self.context = None
        self.browser = None
```

---

## 2️⃣ DOM UNDERSTANDING PATTERNS (HIGH PRIORITY)

### 2.1 Semantic DOM Parser

```python
# browser-use DOM patterns → synapse/skills/dom_parser.py
from typing import Dict, List, Optional
from skills.base import BaseSkill, SkillManifest
from core.models import ExecutionContext

class SemanticDOMParser(BaseSkill):
    """
    Семантический парсинг DOM.
    Адаптировано из browser-use DOM understanding patterns.
    
    🔹 Наше дополнение: Security filtering + privacy protection
    """
    
    manifest = SkillManifest(
        name="semantic_dom_parser",
        version="1.0.0",
        description="Семантическое понимание структуры веб-страницы",
        author="synapse_core",
        inputs={
            "html": "str",
            "url": "str",
            "extraction_goal": "str"
        },
        outputs={
            "structured_data": "dict",
            "interactive_elements": "list",
            "semantic_tree": "dict"
        },
        required_capabilities=["network:http"],
        risk_level=2,
        isolation_type="subprocess",
        protocol_version="1.0"
    )
    
    # 🔹 Селекторы для извлечения чувствительных данных (блокировать)
    SENSITIVE_SELECTORS = [
        'input[type="password"]',
        'input[name*="password"]',
        'input[name*="passwd"]',
        'input[name*="secret"]',
        'input[name*="token"]',
        'input[name*="credit"]',
        'input[name*="card"]',
        'input[name*="ssn"]',
        'input[type="file"]',
        '[data-sensitive="true"]'
    ]
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Семантический парсинг DOM"""
        
        html = kwargs.get('html', '')
        url = kwargs.get('url', '')
        extraction_goal = kwargs.get('extraction_goal', 'general')
        
        # 1. 🔹 Проверка capabilities
        if not await self._check_capabilities(context):
            return SkillResult(
                success=False,
                error="Missing required capabilities",
                metrics={}
            )
        
        # 2. 🔹 Фильтрация чувствительных данных (наше дополнение)
        filtered_html = await self._filter_sensitive_content(html)
        
        # 3. Парсинг структуры (паттерн из browser-use)
        semantic_tree = await self._build_semantic_tree(filtered_html, url)
        
        # 4. Извлечение интерактивных элементов
        interactive_elements = await self._extract_interactive_elements(filtered_html)
        
        # 5. 🔹 Фильтрация опасных элементов (наше дополнение)
        safe_interactive = await self._filter_dangerous_elements(interactive_elements)
        
        # 6. Структурированное извлечение данных
        structured_data = await self._extract_structured_data(
            filtered_html,
            extraction_goal
        )
        
        return SkillResult(
            success=True,
            result={
                'structured_data': structured_data,
                'interactive_elements': safe_interactive,
                'semantic_tree': semantic_tree,
                'url': url,
                'protocol_version': "1.0"
            },
            metrics={
                'elements_parsed': len(semantic_tree.get('elements', [])),
                'sensitive_filtered': True,
                'protocol_version': "1.0"
            }
        )
    
    async def _filter_sensitive_content(self, html: str) -> str:
        """
        Фильтрация чувствительного контента.
        🔹 Наше дополнение (критично для privacy)
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Удаление чувствительных полей
        for selector in self.SENSITIVE_SELECTORS:
            for element in soup.select(selector):
                # Заменить value на [REDACTED]
                if element.has_attr('value'):
                    element['value'] = '[REDACTED]'
                # Удалить placeholder
                if element.has_attr('placeholder'):
                    element['placeholder'] = '[REDACTED]'
        
        # Удаление скрытых токенов
        for input_elem in soup.find_all('input', {'type': 'hidden'}):
            if any(name in str(input_elem.get('name', '')).lower() 
                   for name in ['token', 'csrf', 'secret', 'key']):
                if input_elem.has_attr('value'):
                    input_elem['value'] = '[REDACTED]'
        
        return str(soup)
    
    async def _build_semantic_tree(self, html: str, url: str) -> dict:
        """Построение семантического дерева DOM (паттерн из browser-use)"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        tree = {
            'url': url,
            'title': soup.title.string if soup.title else '',
            'elements': [],
            'forms': [],
            'links': [],
            'images': [],
            'headings': [],
            'protocol_version': "1.0"
        }
        
        # Извлечение заголовков
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                tree['headings'].append({
                    'level': i,
                    'text': h.get_text(strip=True),
                    'selector': self._generate_selector(h)
                })
        
        # Извлечение ссылок
        for a in soup.find_all('a', href=True):
            tree['links'].append({
                'text': a.get_text(strip=True),
                'href': a['href'],
                'selector': self._generate_selector(a)
            })
        
        # Извлечение форм
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action', ''),
                'method': form.get('method', 'GET'),
                'fields': []
            }
            for input_elem in form.find_all(['input', 'select', 'textarea']):
                field = {
                    'type': input_elem.get('type', 'text'),
                    'name': input_elem.get('name', ''),
                    'selector': self._generate_selector(input_elem)
                }
                # 🔹 Не включать value для чувствительных полей
                if field['type'] not in ['password', 'hidden']:
                    field['value'] = input_elem.get('value', '')
                form_data['fields'].append(field)
            tree['forms'].append(form_data)
        
        # Извлечение интерактивных элементов
        for button in soup.find_all(['button', 'input[type="button"]', 'input[type="submit"]']):
            tree['elements'].append({
                'type': 'button',
                'text': button.get_text(strip=True) or button.get('value', ''),
                'selector': self._generate_selector(button)
            })
        
        return tree
    
    async def _extract_interactive_elements(self, html: str) -> List[dict]:
        """Извлечение интерактивных элементов (паттерн из browser-use)"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        elements = []
        
        # Кликабельные элементы
        for tag in ['a', 'button', 'input']:
            for elem in soup.find_all(tag):
                if tag == 'a' and not elem.get('href'):
                    continue
                if tag == 'input' and elem.get('type') in ['hidden']:
                    continue
                
                elements.append({
                    'tag': tag,
                    'type': elem.get('type', 'link'),
                    'text': elem.get_text(strip=True) or elem.get('value', ''),
                    'selector': self._generate_selector(elem),
                    'visible': await self._is_visible(elem)
                })
        
        return elements
    
    async def _filter_dangerous_elements(self, elements: List[dict]) -> List[dict]:
        """
        Фильтрация опасных элементов.
        🔹 Наше дополнение (критично для безопасности)
        """
        safe_elements = []
        
        dangerous_patterns = [
            'download',
            'execute',
            'run',
            'install',
            'upload',
            'submit.*password',
            'transfer',
            'payment'
        ]
        
        for elem in elements:
            text_lower = elem.get('text', '').lower()
            selector_lower = elem.get('selector', '').lower()
            
            is_dangerous = any(
                pattern in text_lower or pattern in selector_lower
                for pattern in dangerous_patterns
            )
            
            if not is_dangerous:
                safe_elements.append(elem)
            else:
                # Пометить как требующее approval
                elem['requires_approval'] = True
                safe_elements.append(elem)  # Но вернуть с флагом
        
        return safe_elements
    
    def _generate_selector(self, element) -> str:
        """Генерация CSS селектора для элемента"""
        if element.get('id'):
            return f"#{element['id']}"
        if element.get('class'):
            classes = '.'.join(element['class']) if isinstance(element['class'], list) else element['class']
            return f".{classes}"
        return element.name
    
    async def _is_visible(self, element) -> bool:
        """Проверка видимости элемента (базовая эвристика)"""
        # В реальной реализации — проверка через browser
        style = element.get('style', '')
        if 'display:none' in style or 'visibility:hidden' in style:
            return False
        return True
    
    async def _extract_structured_data(self, html: str, goal: str) -> dict:
        """Извлечение структурированных данных по цели"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Извлечение schema.org данных
        structured = {}
        
        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                structured['json_ld'] = json.loads(script.string)
            except:
                pass
        
        # Microdata
        for item in soup.find_all(itemscope=True):
            item_type = item.get('itemtype', '')
            structured.setdefault('microdata', []).append({
                'type': item_type,
                'properties': self._extract_microdata_properties(item)
            })
        
        # Open Graph
        og_data = {}
        for meta in soup.find_all('meta', property=True):
            if meta['property'].startswith('og:'):
                og_data[meta['property']] = meta.get('content', '')
        structured['open_graph'] = og_data
        
        return structured
    
    def _extract_microdata_properties(self, element) -> dict:
        """Извлечение свойств microdata"""
        properties = {}
        for prop in element.find_all(itemprop=True):
            prop_name = prop['itemprop']
            prop_value = prop.get('content', prop.get_text(strip=True))
            properties[prop_name] = prop_value
        return properties
```

---

## 3️⃣ WEB AUTOMATION WORKFLOW PATTERNS (HIGH PRIORITY)

### 3.1 Task-Oriented Browser Automation

```python
# browser-use workflow patterns → synapse/skills/browser_workflow.py
from typing import Dict, List, Optional
from skills.base import BaseSkill, SkillManifest
from core.models import ExecutionContext

class BrowserWorkflowExecutor(BaseSkill):
    """
    Выполнение веб-автоматизации по задачам.
    Адаптировано из browser-use workflow patterns.
    
    🔹 Наше дополнение: Checkpoint after each step + rollback support
    """
    
    manifest = SkillManifest(
        name="browser_workflow_executor",
        version="1.0.0",
        description="Выполнение многошаговых веб-задач с checkpoint",
        author="synapse_core",
        inputs={
            "task_description": "str",
            "starting_url": "str",
            "max_steps": "int",
            "checkpoint_enabled": "bool"
        },
        outputs={
            "success": "bool",
            "steps_completed": "int",
            "result": "any",
            "screenshots": "list"
        },
        required_capabilities=["network:http", "browser:automation"],
        risk_level=4,
        isolation_type="container",
        protocol_version="1.0"
    )
    
    def __init__(self, llm_provider, security_manager, checkpoint_manager, browser_controller):
        self.llm = llm_provider
        self.security = security_manager
        self.checkpoint = checkpoint_manager  # 🔹 Наше дополнение
        self.browser = browser_controller
        super().__init__()
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Выполнение веб-воркфлоу"""
        
        task = kwargs.get('task_description')
        starting_url = kwargs.get('starting_url', 'about:blank')
        max_steps = kwargs.get('max_steps', 20)
        checkpoint_enabled = kwargs.get('checkpoint_enabled', True)
        
        # 1. 🔹 Проверка capabilities
        if not await self._check_capabilities(context):
            return SkillResult(
                success=False,
                error="Missing required capabilities",
                metrics={}
            )
        
        # 2. 🔹 Валидация URL
        url_validation = await self.browser._validate_url(starting_url)
        if not url_validation['allowed']:
            return SkillResult(
                success=False,
                error=f"Starting URL blocked: {url_validation['reason']}",
                metrics={}
            )
        
        steps_completed = 0
        screenshots = []
        checkpoint_ids = []
        
        try:
            # 3. Инициализация браузера
            await self.browser._initialize_browser(context)
            
            # 4. 🔹 Создание начального checkpoint (наше дополнение)
            if checkpoint_enabled:
                initial_checkpoint = await self.checkpoint.create_checkpoint(
                    agent_id=context.agent_id,
                    session_id=context.session_id
                )
                checkpoint_ids.append(initial_checkpoint)
            
            # 5. Главный цикл выполнения (паттерн из browser-use)
            current_state = {
                'url': starting_url,
                'step': 0,
                'task': task,
                'history': []
            }
            
            while steps_completed < max_steps:
                # 🔹 Checkpoint перед каждым шагом (наше дополнение)
                if checkpoint_enabled and steps_completed > 0:
                    step_checkpoint = await self.checkpoint.create_checkpoint(
                        agent_id=context.agent_id,
                        session_id=context.session_id
                    )
                    checkpoint_ids.append(step_checkpoint)
                
                # Анализ текущего состояния
                state_analysis = await self._analyze_page_state(current_state)
                
                # Определение следующего действия через LLM
                next_action = await self._determine_next_action(
                    task=task,
                    state=state_analysis,
                    history=current_state['history']
                )
                
                # Проверка завершения задачи
                if next_action.get('action') == 'complete':
                    break
                
                # Выполнение действия
                action_result = await self._execute_action(next_action, context)
                
                if not action_result['success']:
                    # 🔹 Rollback при ошибке (наше дополнение)
                    if checkpoint_enabled and checkpoint_ids:
                        await self.checkpoint.rollback_to_checkpoint(checkpoint_ids[-1])
                    return SkillResult(
                        success=False,
                        error=f"Step {steps_completed} failed: {action_result.get('error')}",
                        metrics={'steps_completed': steps_completed}
                    )
                
                # Обновление состояния
                current_state['history'].append({
                    'step': steps_completed,
                    'action': next_action,
                    'result': action_result
                })
                current_state['url'] = action_result.get('url', current_state['url'])
                current_state['step'] = steps_completed
                
                # Скриншот для аудита
                screenshot = await self.browser._screenshot()
                screenshots.append(screenshot)
                
                steps_completed += 1
            
            # Финальный результат
            final_result = await self._extract_final_result(current_state)
            
            return SkillResult(
                success=True,
                result={
                    'task': task,
                    'steps_completed': steps_completed,
                    'final_url': current_state['url'],
                    'final_result': final_result,
                    'screenshots_count': len(screenshots),
                    'protocol_version': "1.0"
                },
                metrics={
                    'steps_completed': steps_completed,
                    'max_steps': max_steps,
                    'checkpoints_created': len(checkpoint_ids),
                    'protocol_version': "1.0"
                }
            )
            
        except Exception as e:
            # 🔹 Rollback при критической ошибке (наше дополнение)
            if checkpoint_enabled and checkpoint_ids:
                await self.checkpoint.rollback_to_checkpoint(checkpoint_ids[0])
            
            return SkillResult(
                success=False,
                error=f"Workflow failed: {str(e)}",
                metrics={'steps_completed': steps_completed}
            )
        finally:
            # Очистка
            await self.browser._cleanup_browser()
    
    async def _analyze_page_state(self, current_state: dict) -> dict:
        """Анализ текущего состояния страницы (паттерн из browser-use)"""
        # Получение DOM через browser controller
        dom_tree = await self.browser._scrape('')
        
        return {
            'url': current_state['url'],
            'title': await self.browser.page.title() if self.browser.page else '',
            'dom_summary': self._summarize_dom(dom_tree),
            'available_actions': await self._identify_available_actions(),
            'step': current_state['step'],
            'remaining_steps': 20 - current_state['step']
        }
    
    async def _determine_next_action(self,
                                      task: str,
                                      state: dict,
                                      history: List[dict]) -> dict:
        """Определение следующего действия через LLM (паттерн из browser-use)"""
        prompt = f"""
Analyze the current page state and determine the next action to complete this task:

Task: {task}

Current State:
- URL: {state['url']}
- Title: {state['title']}
- Step: {state['step']}
- Remaining Steps: {state['remaining_steps']}

Available Elements:
{state['available_actions']}

Previous Actions:
{history[-5:]}  # Last 5 actions

Determine the next action. Choose from:
- navigate: Go to a URL
- click: Click an element (provide selector)
- fill: Fill a form field (provide selector and value)
- scroll: Scroll the page
- wait: Wait for an element
- complete: Task is complete
- fail: Task cannot be completed

Return as JSON:
{{
    "action": "click",
    "selector": "#submit-button",
    "reasoning": "Submit the form to complete the task",
    "confidence": 0.9
}}
"""
        response = await self.llm.generate(prompt)
        return self._parse_action_response(response)
    
    async def _execute_action(self, action: dict, context: ExecutionContext) -> dict:
        """Выполнение действия"""
        action_type = action.get('action')
        
        actions = {
            'navigate': lambda: self.browser._navigate(action.get('url'), 30000),
            'click': lambda: self.browser._click(action.get('selector'), 10000),
            'fill': lambda: self.browser._fill(
                action.get('selector'),
                action.get('value'),
                10000
            ),
            'wait': lambda: self.browser._wait(action.get('selector'), 10000),
            'scroll': lambda: self._scroll(action.get('direction', 'down')),
            'complete': lambda: {'success': True, 'completed': True},
            'fail': lambda: {'success': False, 'error': 'Task marked as failed'}
        }
        
        if action_type not in actions:
            return {'success': False, 'error': f'Unknown action: {action_type}'}
        
        try:
            result = await actions[action_type]()
            result['success'] = True
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _extract_final_result(self, state: dict) -> dict:
        """Извлечение финального результата"""
        # Scraping финального контента
        content = await self.browser._scrape('')
        
        return {
            'url': state['url'],
            'content_summary': self._summarize_content(content),
            'task_completed': True
        }
    
    def _summarize_dom(self, dom_tree: dict) -> str:
        """Краткое резюме DOM"""
        return f"Links: {len(dom_tree.get('links', []))}, Forms: {len(dom_tree.get('forms', []))}, Buttons: {len(dom_tree.get('elements', []))}"
    
    async def _identify_available_actions(self) -> List[dict]:
        """Идентификация доступных действий на странице"""
        elements = await self.browser._scrape('')
        return elements.get('interactive_elements', [])
    
    def _parse_action_response(self, response: str) -> dict:
        """Парсинг ответа LLM с действием"""
        import json
        import re
        
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        # Fallback
        return {
            'action': 'fail',
            'reasoning': 'Could not parse action from response',
            'confidence': 0.0
        }
    
    async def _scroll(self, direction: str):
        """Скроллинг страницы"""
        if self.browser.page:
            if direction == 'down':
                await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            elif direction == 'up':
                await self.page.evaluate('window.scrollBy(0, -window.innerHeight)')
        return {'scrolled': direction}
    
    def _summarize_content(self, content: dict) -> str:
        """Краткое резюме контента"""
        if isinstance(content.get('content'), list):
            return f"Extracted {len(content['content'])} elements"
        return f"Content length: {len(str(content))}"
```

---

## 4️⃣ ЧТО НЕ БРАТЬ ИЗ BROWSER-USE

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет domain whitelist | Нет контроля доступа | Domain Whitelist + Blocklist |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Нет checkpoint/rollback | Нет recovery | RollbackManager с is_fresh() |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет audit logging | Нет прозрачности | Full Audit Trail |
| Нет human approval | Нет контроля | Human Approval for High Risk |
| Simple error handling | Нет structured recovery | StructuredError с rollback |

---

## 5️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Browser Controller (Неделя 8-10)

| Задача | browser-use Pattern | Файл Synapse | Статус |
|--------|---------------------|--------------|--------|
| Secure Browser Controller | Browser automation | `synapse/skills/browser_controller.py` | ⏳ Ожидает |
| URL Validation | Domain filtering | `synapse/security/url_validator.py` | ⏳ Ожидает |
| Action Validation | Action security | `synapse/security/action_validator.py` | ⏳ Ожидает |

### Фаза 2: DOM Understanding (Неделя 10-11)

| Задача | browser-use Pattern | Файл Synapse | Статус |
|--------|---------------------|--------------|--------|
| Semantic DOM Parser | DOM understanding | `synapse/skills/dom_parser.py` | ⏳ Ожидает |
| Element Finder | Element selection | `synapse/skills/element_finder.py` | ⏳ Ожидает |
| Content Extractor | Data extraction | `synapse/skills/content_extractor.py` | ⏳ Ожидает |

### Фаза 3: Workflow Automation (Неделя 11-12)

| Задача | browser-use Pattern | Файл Synapse | Статус |
|--------|---------------------|--------------|--------|
| Workflow Executor | Task automation | `synapse/skills/browser_workflow.py` | ⏳ Ожидает |
| Checkpoint Integration | State management | `synapse/core/checkpoint.py` | ⏳ Ожидает |
| Screenshot Audit | Visual logging | `synapse/observability/screenshot.py` | ⏳ Ожидает |

---

## 6️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить browser-use documentation
□ Изучить Playwright automation patterns
□ Изучить DOM parsing best practices
□ Изучить web security best practices

□ НЕ брать security model (у нас capability-based)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)
□ НЕ брать resource management (у нас ResourceLimits schema)

□ Адаптировать browser controller с domain whitelist
□ Адаптировать DOM parser с sensitive data filtering
□ Адаптировать workflow executor с checkpoint integration
□ Адаптировать все компоненты с human approval for high risk
□ Адаптировать все компоненты с protocol_version="1.0"

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 7️⃣ СРАВНЕНИЕ: ВСЕ ИСТОЧНИКИ

| Область | OpenClaw | Agent Zero | Anthropic | Claude Code | Codex | browser-use | Synapse |
|---------|----------|------------|-----------|-------------|-------|-------------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (Agent Zero) |
| Code Generation | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ (Codex/Claude) |
| Browser Automation | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (browser-use) |
| DOM Understanding | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (browser-use) |
| Web Automation | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (browser-use) |
| Safety | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Protocol Versioning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |

---

## 8️⃣ ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 8.1 browser-use License

```
browser-use License: MIT (предположительно)
Repository: https://github.com/browser-use/browser-use

При использовании browser-use patterns:
1. Проверить актуальную лицензию в репозитории
2. Указать ссылку на оригинальный репозиторий
3. Добавить заметку об адаптации в docstring
```

### 8.2 Формат Атрибуции

```python
# synapse/skills/browser_controller.py
"""
Secure Browser Controller для Synapse.

Адаптировано из browser-use patterns:
https://github.com/browser-use/browser-use

Оригинальная лицензия: MIT (предположительно)
Адаптация: Добавлен capability-based access, domain whitelist,
           checkpoint integration, audit logging, protocol versioning

Copyright (c) 2024 browser-use Contributors
Copyright (c) 2026 Synapse Contributors
"""
```

---

## 9️⃣ ВЕРСИОНИРОВАНИЕ ДОКУМЕНТА

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2026-01-03 | Initial release |

---

## 📞 КОНТАКТЫ И ПОДДЕРЖКА

**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**TDD Инструкция:** `TDD_INSTRUCTION_v1.2_FINAL.md`  
**OpenClaw Integration:** `OPENCLAW_INTEGRATION.md`  
**Agent Zero Integration:** `AGENT_ZERO_INTEGRATION.md`  
**Anthropic Patterns:** `ANTHROPIC_PATTERNS_INTEGRATION.md`  
**Claude Code:** `CLAUDE_CODE_INTEGRATION.md`  
**OpenAI Codex:** `CODEX_INTEGRATION.md`  
**browser-use:** https://github.com/browser-use/browser-use

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md