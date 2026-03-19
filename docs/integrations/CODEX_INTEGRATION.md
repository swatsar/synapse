# 📎 PROJECT SYNAPSE: OPENAI CODEX INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## ⚠️ ВАЖНОЕ ПРИМЕЧАНИЕ

**Статус проекта:** OpenAI Codex был **официально deprecated** в январе 2023 года. Технология интегрирована в GitHub Copilot и другие продукты OpenAI.

**Подход этого документа:** Анализирует **публично известные возможности Codex** из исследовательских работ OpenAI, технической документации, публичных демонстраций и общих паттернов AI code generation, а не конкретный код репозитория.

**Что известно о Codex:**
- Fine-tuned версия GPT для генерации кода
- Поддержка множественных языков программирования
- Понимание контекста кодовой базы
- Генерация кода по натуральному языку
- Интеграция с IDE (GitHub Copilot)

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к:
- `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md` (основная спецификация)
- `OPENCLAW_INTEGRATION.md` (интеграция OpenClaw)
- `AGENT_ZERO_INTEGRATION.md` (интеграция Agent Zero)
- `ANTHROPIC_PATTERNS_INTEGRATION.md` (паттерны Anthropic)
- `CLAUDE_CODE_INTEGRATION.md` (паттерны Claude Code)

Он описывает стратегию интеграции полезных паттернов из **OpenAI Codex** в платформу Synapse, особенно для **Code Generation**, **Code Completion**, и **Multi-Language Support** компонентов.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Паттернов для Заимствования | Статус |
|---------|---------------------|------------------------------|--------|
| Code Generation | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| Code Completion | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Multi-Language Support | ⭐⭐⭐⭐⭐ | ~60% | ✅ Рекомендовано |
| Context-Aware Generation | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Test Generation | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Code Translation | ⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| Security Model | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐⭐ | ~10% | ❌ НЕ брать |

---

## 1️⃣ CODE GENERATION PATTERNS (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | Codex Pattern | Файл Synapse | Действие |
|-----------|---------------|--------------|----------|
| Code Generation | Codex code completion | `synapse/skills/code_generator.py` | Адаптировать с security scan |
| Code Completion | Inline suggestions | `synapse/skills/code_completer.py` | Адаптировать с context awareness |
| Function Generation | Natural language to code | `synapse/skills/function_generator.py` | Адаптировать с type hints |
| Docstring Generation | Automatic documentation | `synapse/skills/docstring_generator.py` | Адаптировать с spec compliance |

### 1.2 Multi-Language Code Generator

```python
# OpenAI Codex patterns → synapse/skills/code_generator.py
from typing import Dict, List, Optional, Literal
from skills.base import BaseSkill, SkillManifest
from core.models import ExecutionContext, ResourceLimits

class MultiLanguageCodeGenerator(BaseSkill):
    """
    Генерация кода на множественных языках.
    Адаптировано из OpenAI Codex patterns.
    
    🔹 Наше дополнение: Security scan + spec v3.1 compliance
    """
    
    manifest = SkillManifest(
        name="multi_language_code_generator",
        version="1.0.0",
        description="Генерация кода на Python, JavaScript, TypeScript, Go, Rust",
        author="synapse_core",
        inputs={
            "task_description": "str",
            "language": "str",
            "context_files": "list",
            "style_guide": "str"
        },
        outputs={
            "code": "str",
            "language": "str",
            "tests": "str",
            "documentation": "str",
            "security_report": "dict"
        },
        required_capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"],
        risk_level=4,
        isolation_type="container",
        timeout_seconds=120,
        protocol_version="1.0"
    )
    
    # 🔹 Поддерживаемые языки (расширено из Codex capabilities)
    SUPPORTED_LANGUAGES = {
        'python': {
            'extensions': ['.py'],
            'linter': 'flake8',
            'formatter': 'black',
            'test_framework': 'pytest',
            'type_system': 'dynamic'
        },
        'javascript': {
            'extensions': ['.js', '.mjs'],
            'linter': 'eslint',
            'formatter': 'prettier',
            'test_framework': 'jest',
            'type_system': 'dynamic'
        },
        'typescript': {
            'extensions': ['.ts', '.tsx'],
            'linter': 'eslint',
            'formatter': 'prettier',
            'test_framework': 'jest',
            'type_system': 'static'
        },
        'go': {
            'extensions': ['.go'],
            'linter': 'golangci-lint',
            'formatter': 'gofmt',
            'test_framework': 'go test',
            'type_system': 'static'
        },
        'rust': {
            'extensions': ['.rs'],
            'linter': 'clippy',
            'formatter': 'rustfmt',
            'test_framework': 'cargo test',
            'type_system': 'static'
        }
    }
    
    # 🔹 Языко-специфичные опасные паттерны
    LANGUAGE_DANGEROUS_PATTERNS = {
        'python': ['eval(', 'exec(', 'os.system(', 'subprocess.Popen('],
        'javascript': ['eval(', 'Function(', 'innerHTML =', 'document.write('],
        'typescript': ['eval(', 'Function('],
        'go': ['exec.Command(', 'os.Remove(', 'os.RemoveAll('],
        'rust': ['std::process::Command', 'fs::remove', 'unsafe {']
    }
    
    def __init__(self, llm_provider, security_manager):
        self.llm = llm_provider
        self.security = security_manager
        super().__init__()
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Генерация кода с поддержкой множественных языков"""
        
        task = kwargs.get('task_description')
        language = kwargs.get('language', 'python').lower()
        context_files = kwargs.get('context_files', [])
        style_guide = kwargs.get('style_guide', 'default')
        
        # 1. 🔹 Проверка поддержки языка (наше дополнение)
        if language not in self.SUPPORTED_LANGUAGES:
            return SkillResult(
                success=False,
                error=f"Language '{language}' not supported. Supported: {list(self.SUPPORTED_LANGUAGES.keys())}",
                metrics={}
            )
        
        # 2. 🔹 Проверка capabilities (наше дополнение из spec v3.1)
        if not await self._check_capabilities(context):
            return SkillResult(
                success=False,
                error="Missing required capabilities",
                metrics={}
            )
        
        # 3. Анализ контекста проекта (паттерн из Codex)
        project_context = await self._analyze_project_context(
            context_files,
            language
        )
        
        # 4. Генерация кода (паттерн из Codex + наше дополнение)
        generated_code = await self._generate_code(
            task=task,
            language=language,
            context=project_context,
            style_guide=style_guide
        )
        
        # 5. 🔹 Языко-специфичный security scan (наше дополнение)
        security_report = await self._language_specific_security_scan(
            generated_code,
            language
        )
        
        if not security_report['safe']:
            await self.security.log_security_event(
                event_type="unsafe_code_generation",
                user_id=context.agent_id,
                details={
                    'language': language,
                    'issues': security_report['issues'],
                    'protocol_version': "1.0"
                }
            )
            return SkillResult(
                success=False,
                error=f"Code generation blocked: {security_report['issues']}",
                metrics={'security_scan': 'failed'}
            )
        
        # 6. 🔹 Генерация тестов (паттерн из Codex)
        tests = await self._generate_tests(generated_code, language, task)
        
        # 7. 🔹 Генерация документации (наше дополнение)
        documentation = await self._generate_documentation(
            generated_code,
            language,
            task
        )
        
        # 8. 🔹 Форматирование кода (наше дополнение)
        formatted_code = await self._format_code(generated_code, language)
        
        return SkillResult(
            success=True,
            result={
                'code': formatted_code,
                'language': language,
                'tests': tests,
                'documentation': documentation,
                'security_report': security_report,
                'protocol_version': "1.0"
            },
            metrics={
                'security_scan': 'passed',
                'language': language,
                'lines_generated': len(formatted_code.split('\n'))
            }
        )
    
    async def _generate_code(self, 
                             task: str, 
                             language: str, 
                             context: dict,
                             style_guide: str) -> str:
        """
        Генерация кода с учётом языка и стиля.
        (паттерн из Codex)
        """
        lang_config = self.SUPPORTED_LANGUAGES[language]
        
        # Построение промпта с учётом языка
        prompt = self._build_language_specific_prompt(
            task=task,
            language=language,
            lang_config=lang_config,
            context=context,
            style_guide=style_guide
        )
        
        # 🔹 Использование temperature=0 для детерминизма (наше дополнение из spec v3.1)
        code = await self.llm.generate(
            prompt=prompt,
            temperature=0,  # Детерминированный вывод
            execution_seed=context.execution_seed
        )
        
        return self._extract_code_from_response(code, language)
    
    def _build_language_specific_prompt(self,
                                         task: str,
                                         language: str,
                                         lang_config: dict,
                                         context: dict,
                                         style_guide: str) -> str:
        """
        Построение промпта с учётом языка программирования.
        🔹 Наше дополнение (не было в Codex)
        """
        
        # Языко-специфичные инструкции
        language_instructions = {
            'python': """
- Use Python 3.11+ syntax
- Include type hints for all functions
- Include docstrings in Google style
- Follow PEP 8 style guide
- Use async/await for I/O operations
- Include protocol_version="1.0" in all models
""",
            'javascript': """
- Use ES2022+ syntax
- Use const/let instead of var
- Include JSDoc comments
- Follow Airbnb style guide
- Use async/await for promises
- Include protocol_version="1.0" in metadata
""",
            'typescript': """
- Use TypeScript 5.0+ syntax
- Include explicit type annotations
- Include JSDoc comments
- Follow TypeScript strict mode
- Use async/await for promises
- Include protocol_version="1.0" in interfaces
""",
            'go': """
- Use Go 1.21+ syntax
- Follow Go idioms and conventions
- Include godoc comments
- Use error handling patterns
- Include context.Context for cancellation
- Include protocol_version="1.0" in structs
""",
            'rust': """
- Use Rust 2021 edition
- Follow Rust idioms and conventions
- Include rustdoc comments
- Use Result<T, E} for error handling
- Include unsafe blocks only when necessary
- Include protocol_version="1.0" in structs
"""
        }
        
        prompt = f"""
Generate {language} code for this task:

Task: {task}

Project Context:
{context}

Language-Specific Requirements:
{language_instructions.get(language, '')}

Style Guide: {style_guide}

Important:
1. Follow best practices for {language}
2. Include comprehensive error handling
3. Include type hints/annotations
4. Include documentation comments
5. DO NOT use dangerous functions for {language}
6. Follow protocol_version="1.0" conventions

Return only the code, no explanations.
"""
        return prompt
    
    async def _language_specific_security_scan(self, 
                                                code: str, 
                                                language: str) -> dict:
        """
        Языко-специфичный security scan.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        issues = []
        dangerous_patterns = self.LANGUAGE_DANGEROUS_PATTERNS.get(language, [])
        
        import re
        for pattern in dangerous_patterns:
            # Экранирование специальных regex символов
            escaped_pattern = re.escape(pattern)
            if re.search(escaped_pattern, code):
                issues.append({
                    'type': 'dangerous_function',
                    'severity': 'high',
                    'language': language,
                    'pattern': pattern,
                    'suggestion': f'Remove or replace {pattern}'
                })
        
        # Языко-специфичные проверки
        if language == 'python':
            issues.extend(await self._python_security_checks(code))
        elif language == 'javascript':
            issues.extend(await self._javascript_security_checks(code))
        elif language == 'typescript':
            issues.extend(await self._typescript_security_checks(code))
        elif language == 'go':
            issues.extend(await self._go_security_checks(code))
        elif language == 'rust':
            issues.extend(await self._rust_security_checks(code))
        
        return {
            'safe': len(issues) == 0,
            'issues': issues,
            'language': language,
            'protocol_version': "1.0"
        }
    
    async def _python_security_checks(self, code: str) -> List[dict]:
        """Python-specific security checks"""
        issues = []
        import ast
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ['pickle', 'marshal', 'shelve']:
                            issues.append({
                                'type': 'unsafe_import',
                                'severity': 'high',
                                'import': alias.name,
                                'suggestion': 'Use json or yaml.safe_load instead'
                            })
        except SyntaxError:
            issues.append({
                'type': 'syntax_error',
                'severity': 'high',
                'message': 'Invalid Python syntax'
            })
        
        return issues
    
    async def _javascript_security_checks(self, code: str) -> List[dict]:
        """JavaScript-specific security checks"""
        issues = []
        
        # Проверка на innerHTML usage (XSS vulnerability)
        if 'innerHTML' in code:
            issues.append({
                'type': 'xss_vulnerability',
                'severity': 'high',
                'pattern': 'innerHTML',
                'suggestion': 'Use textContent or sanitize input'
            })
        
        # Проверка на document.write
        if 'document.write' in code:
            issues.append({
                'type': 'security_issue',
                'severity': 'high',
                'pattern': 'document.write',
                'suggestion': 'Use DOM manipulation methods instead'
            })
        
        return issues
    
    async def _format_code(self, code: str, language: str) -> str:
        """
        Форматирование кода согласно языковым стандартам.
        🔹 Наше дополнение (не было в Codex)
        """
        # В реальной реализации — вызов соответствующих инструментов
        # Здесь — базовая эмуляция
        lang_config = self.SUPPORTED_LANGUAGES[language]
        
        # Эмуляция форматирования
        formatted = code.strip()
        
        # Добавление protocol_version comment
        if language == 'python':
            formatted = f'# protocol_version: "1.0"\n\n{formatted}'
        elif language in ['javascript', 'typescript']:
            formatted = f'// protocol_version: "1.0"\n\n{formatted}'
        elif language == 'go':
            formatted = f'// protocol_version: "1.0"\n\n{formatted}'
        elif language == 'rust':
            formatted = f'// protocol_version: "1.0"\n\n{formatted}'
        
        return formatted
    
    async def _generate_documentation(self, 
                                       code: str, 
                                       language: str,
                                       task: str) -> str:
        """
        Генерация документации для кода.
        🔹 Наше дополнение (не было в Codex)
        """
        prompt = f"""
Generate documentation for this {language} code:

Code:
{code}

Task: {task}

Requirements:
- Include function/method descriptions
- Include parameter descriptions
- Include return value descriptions
- Include usage examples
- Include protocol_version="1.0" reference

Return only the documentation, no code.
"""
        documentation = await self.llm.generate(prompt)
        return documentation
    
    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Извлечение кода из ответа LLM"""
        import re
        
        # Языко-специфичные code block markers
        lang_markers = {
            'python': r'```(?:python|py)\n(.*?)```',
            'javascript': r'```(?:javascript|js)\n(.*?)```',
            'typescript': r'```(?:typescript|ts)\n(.*?)```',
            'go': r'```(?:go|golang)\n(.*?)```',
            'rust': r'```(?:rust|rs)\n(.*?)```'
        }
        
        marker = lang_markers.get(language, r'```\n(.*?)```')
        match = re.search(marker, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        return response.strip()
```

---

## 2️⃣ CODE COMPLETION PATTERNS (HIGH PRIORITY)

### 2.1 Inline Code Completion

```python
# OpenAI Codex completion → synapse/skills/code_completer.py
from typing import List, Dict, Optional

class CodeCompleter(BaseSkill):
    """
    Inline завершение кода.
    Адаптировано из OpenAI Codex completion patterns.
    
    🔹 Наше дополнение: Context-aware + security filtering
    """
    
    manifest = SkillManifest(
        name="code_completer",
        version="1.0.0",
        description="Inline завершение кода с учётом контекста",
        author="synapse_core",
        inputs={
            "prefix": "str",
            "suffix": "str",
            "language": "str",
            "max_completions": "int"
        },
        outputs={
            "completions": "list",
            "confidence_scores": "list"
        },
        required_capabilities=["fs:read:/workspace/**"],
        risk_level=2,
        isolation_type="subprocess",
        protocol_version="1.0"
    )
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Генерация inline completions"""
        
        prefix = kwargs.get('prefix', '')
        suffix = kwargs.get('suffix', '')
        language = kwargs.get('language', 'python')
        max_completions = kwargs.get('max_completions', 3)
        
        # 1. 🔹 Анализ контекста (наше дополнение)
        context_info = await self._analyze_completion_context(
            prefix, suffix, language
        )
        
        # 2. Генерация completions (паттерн из Codex)
        completions = await self._generate_completions(
            prefix=prefix,
            suffix=suffix,
            language=language,
            max_completions=max_completions,
            context=context_info
        )
        
        # 3. 🔹 Security filtering completions (наше дополнение)
        filtered_completions = await self._filter_unsafe_completions(
            completions,
            language
        )
        
        # 4. 🔹 Calculation confidence scores (наше дополнение)
        confidence_scores = await self._calculate_confidence_scores(
            filtered_completions,
            prefix,
            suffix
        )
        
        return SkillResult(
            success=True,
            result={
                'completions': filtered_completions,
                'confidence_scores': confidence_scores,
                'language': language,
                'protocol_version': "1.0"
            },
            metrics={
                'completions_generated': len(filtered_completions),
                'filtered_out': len(completions) - len(filtered_completions)
            }
        )
    
    async def _generate_completions(self,
                                     prefix: str,
                                     suffix: str,
                                     language: str,
                                     max_completions: int,
                                     context: dict) -> List[str]:
        """Генерация multiple completions (паттерн из Codex)"""
        
        prompt = f"""
Complete the following {language} code:

Prefix:
{prefix}

Suffix:
{suffix}

Context:
{context}

Generate {max_completions} different completion options.
Each completion should be syntactically correct and follow best practices.

Return completions as a JSON array.
"""
        
        response = await self.llm.generate(prompt)
        completions = self._parse_completions(response, max_completions)
        
        return completions
    
    async def _filter_unsafe_completions(self,
                                          completions: List[str],
                                          language: str) -> List[str]:
        """
        Фильтрация небезопасных completions.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        filtered = []
        dangerous_patterns = self.LANGUAGE_DANGEROUS_PATTERNS.get(language, [])
        
        import re
        for completion in completions:
            is_safe = True
            for pattern in dangerous_patterns:
                if re.search(re.escape(pattern), completion):
                    is_safe = False
                    break
            
            if is_safe:
                filtered.append(completion)
        
        return filtered
    
    async def _calculate_confidence_scores(self,
                                            completions: List[str],
                                            prefix: str,
                                            suffix: str) -> List[float]:
        """
        Расчёт confidence scores для completions.
        🔹 Наше дополнение (не было в Codex)
        """
        scores = []
        
        for completion in completions:
            score = 1.0
            
            # Проверка синтаксической корректности
            if not await self._check_syntax(completion, prefix, suffix):
                score -= 0.3
            
            # Проверка соответствия стилю
            if not await self._check_style(completion):
                score -= 0.1
            
            # Проверка длины (слишком длинные = менее уверенные)
            if len(completion) > 500:
                score -= 0.1
            
            scores.append(max(0.0, min(1.0, score)))
        
        return scores
    
    async def _check_syntax(self, 
                            completion: str, 
                            prefix: str, 
                            suffix: str) -> bool:
        """Проверка синтаксической корректности"""
        full_code = f"{prefix}{completion}{suffix}"
        
        # В реальной реализации — вызов соответствующего парсера
        # Здесь — базовая проверка
        try:
            compile(full_code, '<string>', 'exec')
            return True
        except:
            return False
    
    async def _check_style(self, completion: str) -> bool:
        """Проверка соответствия стилю"""
        # Базовые проверки стиля
        if '  ' in completion:  # Double spaces
            return False
        if completion.startswith(' '):  # Leading space
            return False
        return True
    
    async def _analyze_completion_context(self,
                                           prefix: str,
                                           suffix: str,
                                           language: str) -> dict:
        """Анализ контекста для completion"""
        return {
            'prefix_lines': len(prefix.split('\n')),
            'suffix_lines': len(suffix.split('\n')),
            'in_function': self._detect_function_context(prefix),
            'in_class': self._detect_class_context(prefix),
            'indentation_level': self._detect_indentation(prefix),
            'language': language
        }
    
    def _detect_function_context(self, prefix: str) -> bool:
        """Обнаружение контекста функции"""
        import re
        return bool(re.search(r'def \w+\([^)]*\)\s*:', prefix))
    
    def _detect_class_context(self, prefix: str) -> bool:
        """Обнаружение контекста класса"""
        import re
        return bool(re.search(r'class \w+', prefix))
    
    def _detect_indentation(self, prefix: str) -> int:
        """Обнаружение уровня индентации"""
        last_line = prefix.split('\n')[-1]
        return len(last_line) - len(last_line.lstrip())
    
    def _parse_completions(self, response: str, max_completions: int) -> List[str]:
        """Парсинг completions из ответа LLM"""
        import json
        import re
        
        # Попытка парсинга JSON
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                completions = json.loads(match.group())
                return completions[:max_completions]
            except:
                pass
        
        # Fallback: разделение по новой строке
        return response.strip().split('\n')[:max_completions]
```

---

## 3️⃣ CODE TRANSLATION PATTERNS (MEDIUM PRIORITY)

### 3.1 Cross-Language Translation

```python
# OpenAI Codex translation → synapse/skills/code_translator.py
from typing import Dict, List, Optional

class CodeTranslator(BaseSkill):
    """
    Перевод кода между языками.
    Адаптировано из OpenAI Codex translation patterns.
    
    🔹 Наше дополнение: Semantic equivalence verification
    """
    
    manifest = SkillManifest(
        name="code_translator",
        version="1.0.0",
        description="Перевод кода между Python, JavaScript, TypeScript, Go, Rust",
        author="synapse_core",
        inputs={
            "source_code": "str",
            "source_language": "str",
            "target_language": "str",
            "preserve_comments": "bool"
        },
        outputs={
            "translated_code": "str",
            "equivalence_report": "dict",
            "migration_notes": "list"
        },
        required_capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"],
        risk_level=3,
        isolation_type="container",
        protocol_version="1.0"
    )
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Перевод кода между языками"""
        
        source_code = kwargs.get('source_code')
        source_language = kwargs.get('source_language', 'python')
        target_language = kwargs.get('target_language', 'javascript')
        preserve_comments = kwargs.get('preserve_comments', True)
        
        # 1. 🔹 Проверка поддержки языков (наше дополнение)
        if source_language not in self.SUPPORTED_LANGUAGES:
            return SkillResult(
                success=False,
                error=f"Source language '{source_language}' not supported",
                metrics={}
            )
        
        if target_language not in self.SUPPORTED_LANGUAGES:
            return SkillResult(
                success=False,
                error=f"Target language '{target_language}' not supported",
                metrics={}
            )
        
        # 2. Анализ исходного кода (паттерн из Codex)
        source_analysis = await self._analyze_source_code(
            source_code,
            source_language
        )
        
        # 3. Перевод кода (паттерн из Codex)
        translated_code = await self._translate_code(
            source_code=source_code,
            source_language=source_language,
            target_language=target_language,
            analysis=source_analysis,
            preserve_comments=preserve_comments
        )
        
        # 4. 🔹 Verification semantic equivalence (наше дополнение)
        equivalence_report = await self._verify_semantic_equivalence(
            source_code=source_code,
            translated_code=translated_code,
            source_language=source_language,
            target_language=target_language
        )
        
        # 5. 🔹 Генерация migration notes (наше дополнение)
        migration_notes = await self._generate_migration_notes(
            source_language=source_language,
            target_language=target_language,
            analysis=source_analysis
        )
        
        # 6. 🔹 Security scan translated code (наше дополнение)
        security_report = await self._language_specific_security_scan(
            translated_code,
            target_language
        )
        
        if not security_report['safe']:
            return SkillResult(
                success=False,
                error=f"Translation blocked: {security_report['issues']}",
                metrics={}
            )
        
        return SkillResult(
            success=True,
            result={
                'translated_code': translated_code,
                'equivalence_report': equivalence_report,
                'migration_notes': migration_notes,
                'security_report': security_report,
                'protocol_version': "1.0"
            },
            metrics={
                'source_lines': len(source_code.split('\n')),
                'target_lines': len(translated_code.split('\n')),
                'equivalence_score': equivalence_report.get('score', 0)
            }
        )
    
    async def _translate_code(self,
                               source_code: str,
                               source_language: str,
                               target_language: str,
                               analysis: dict,
                               preserve_comments: bool) -> str:
        """Перевод кода (паттерн из Codex)"""
        
        prompt = f"""
Translate the following {source_language} code to {target_language}:

Source Code:
{source_code}

Code Analysis:
{analysis}

Requirements:
1. Preserve functionality and logic
2. Follow {target_language} best practices and idioms
3. {"Preserve" if preserve_comments else "Remove"} comments
4. Include appropriate type annotations for {target_language}
5. Handle errors according to {target_language} conventions
6. Include protocol_version="1.0" in translated code
7. Maintain semantic equivalence

Return only the translated code, no explanations.
"""
        
        translated = await self.llm.generate(prompt)
        return self._extract_code_from_response(translated, target_language)
    
    async def _verify_semantic_equivalence(self,
                                            source_code: str,
                                            translated_code: str,
                                            source_language: str,
                                            target_language: str) -> dict:
        """
        Verification semantic equivalence.
        🔹 Наше дополнение (не было в Codex)
        """
        # В реальной реализации — запуск эквивалентных тестов
        # Здесь — эмуляция на основе анализа
        
        issues = []
        
        # Проверка структуры
        source_funcs = self._extract_functions(source_code, source_language)
        target_funcs = self._extract_functions(translated_code, target_language)
        
        if len(source_funcs) != len(target_funcs):
            issues.append({
                'type': 'function_count_mismatch',
                'severity': 'high',
                'message': f'Function count differs: {len(source_funcs)} vs {len(target_funcs)}'
            })
        
        # Проверка основных паттернов
        source_patterns = self._extract_patterns(source_code)
        target_patterns = self._extract_patterns(translated_code)
        
        missing_patterns = set(source_patterns) - set(target_patterns)
        if missing_patterns:
            issues.append({
                'type': 'missing_patterns',
                'severity': 'medium',
                'message': f'Missing patterns in translation: {missing_patterns}'
            })
        
        # Расчёт scores эквивалентности
        score = 1.0
        score -= len(issues) * 0.2
        score = max(0.0, min(1.0, score))
        
        return {
            'equivalent': len([i for i in issues if i['severity'] == 'high']) == 0,
            'score': score,
            'issues': issues,
            'protocol_version': "1.0"
        }
    
    async def _generate_migration_notes(self,
                                         source_language: str,
                                         target_language: str,
                                         analysis: dict) -> List[str]:
        """
        Генерация заметок для миграции.
        🔹 Наше дополнение (не было в Codex)
        """
        notes = []
        
        # Языко-специфичные заметки
        if source_language == 'python' and target_language == 'javascript':
            notes.extend([
                'Python lists → JavaScript arrays',
                'Python dicts → JavaScript objects',
                'Python None → JavaScript null/undefined',
                'Python async/await → JavaScript async/await',
                'Python decorators → JavaScript decorators (limited support)',
                'Add protocol_version="1.0" to all exported modules'
            ])
        elif source_language == 'python' and target_language == 'go':
            notes.extend([
                'Python dynamic typing → Go static typing',
                'Python exceptions → Go error returns',
                'Python lists → Go slices',
                'Python dicts → Go maps',
                'Add protocol_version="1.0" to all structs',
                'Use context.Context for cancellation'
            ])
        elif source_language == 'python' and target_language == 'rust':
            notes.extend([
                'Python dynamic typing → Rust static typing',
                'Python exceptions → Rust Result<T, E>',
                'Python lists → Rust Vec<T>',
                'Python dicts → Rust HashMap<K, V>',
                'Add protocol_version="1.0" to all structs',
                'Consider ownership and borrowing rules'
            ])
        
        return notes
    
    def _extract_functions(self, code: str, language: str) -> List[str]:
        """Извлечение имён функций из кода"""
        import re
        
        patterns = {
            'python': r'def\s+(\w+)\s*\(',
            'javascript': r'function\s+(\w+)\s*\(',
            'typescript': r'function\s+(\w+)\s*\(',
            'go': r'func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(',
            'rust': r'fn\s+(\w+)\s*\('
        }
        
        pattern = patterns.get(language, r'function\s+(\w+)')
        matches = re.findall(pattern, code)
        return matches
    
    def _extract_patterns(self, code: str) -> List[str]:
        """Извлечение основных паттернов из кода"""
        patterns = []
        
        if 'async' in code:
            patterns.append('async')
        if 'class' in code:
            patterns.append('class')
        if 'try' in code or 'catch' in code or 'except' in code:
            patterns.append('error_handling')
        if 'for' in code or 'while' in code:
            patterns.append('loops')
        if 'import' in code or 'require' in code:
            patterns.append('imports')
        
        return patterns
```

---

## 4️⃣ TEST GENERATION PATTERNS (HIGH PRIORITY)

### 4.1 Automatic Test Generation

```python
# OpenAI Codex test patterns → synapse/skills/test_generator.py
from typing import Dict, List, Optional

class CodexTestGenerator(BaseSkill):
    """
    Генерация тестов в стиле Codex.
    Адаптировано из OpenAI Codex test generation patterns.
    
    🔹 Наше дополнение: Spec v3.1 compliance tests + coverage verification
    """
    
    manifest = SkillManifest(
        name="codex_test_generator",
        version="1.0.0",
        description="Генерация тестов с высоким покрытием",
        author="synapse_core",
        inputs={
            "code": "str",
            "language": "str",
            "test_framework": "str",
            "target_coverage": "float"
        },
        outputs={
            "tests": "str",
            "estimated_coverage": "float",
            "test_count": "int"
        },
        required_capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"],
        risk_level=2,
        isolation_type="subprocess",
        protocol_version="1.0"
    )
    
    # 🔹 Spec v3.1 обязательные тесты
    SPEC_REQUIRED_TESTS = [
        'test_protocol_version_present',
        'test_type_hints_present',
        'test_docstrings_present',
        'test_capability_checks',
        'test_error_handling',
        'test_audit_logging',
        'test_resource_limits',
        'test_isolation_type'
    ]
    
    async def execute(self, context: ExecutionContext, **kwargs) -> SkillResult:
        """Генерация тестов"""
        
        code = kwargs.get('code')
        language = kwargs.get('language', 'python')
        test_framework = kwargs.get('test_framework', 'pytest')
        target_coverage = kwargs.get('target_coverage', 0.8)
        
        # 1. Анализ кода (паттерн из Codex)
        analysis = await self._analyze_code(code, language)
        
        # 2. Генерация unit тестов (паттерн из Codex)
        unit_tests = await self._generate_unit_tests(
            code=code,
            language=language,
            analysis=analysis,
            test_framework=test_framework
        )
        
        # 3. 🔹 Генерация spec compliance тестов (наше дополнение)
        compliance_tests = self._generate_spec_compliance_tests(code, language)
        
        # 4. 🔹 Генерация security тестов (наше дополнение)
        security_tests = await self._generate_security_tests(code, language)
        
        # 5. 🔹 Генерация integration тестов (наше дополнение)
        integration_tests = await self._generate_integration_tests(code, language)
        
        # 6. Сборка всех тестов
        all_tests = self._assemble_tests([
            unit_tests,
            compliance_tests,
            security_tests,
            integration_tests
        ])
        
        # 7. 🔹 Оценка покрытия (наше дополнение)
        estimated_coverage = await self._estimate_coverage(code, all_tests, target_coverage)
        
        # 8. 🔹 Проверка достижения target coverage (наше дополнение)
        if estimated_coverage < target_coverage:
            additional_tests = await self._generate_additional_tests(
                code=code,
                language=language,
                current_tests=all_tests,
                target_coverage=target_coverage
            )
            all_tests = self._assemble_tests([all_tests, additional_tests])
            estimated_coverage = await self._estimate_coverage(code, all_tests, target_coverage)
        
        return SkillResult(
            success=True,
            result={
                'tests': all_tests,
                'estimated_coverage': estimated_coverage,
                'test_count': self._count_tests(all_tests),
                'target_coverage': target_coverage,
                'coverage_met': estimated_coverage >= target_coverage,
                'protocol_version': "1.0"
            },
            metrics={
                'estimated_coverage': estimated_coverage,
                'test_count': self._count_tests(all_tests),
                'spec_compliance_tests': len(self.SPEC_REQUIRED_TESTS)
            }
        )
    
    def _generate_spec_compliance_tests(self, code: str, language: str) -> str:
        """
        Генерация spec v3.1 compliance тестов.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        return f"""
# Spec v3.1 Compliance Tests
# Generated for protocol_version="1.0" compliance

import pytest

{self._generate_protocol_version_test(language)}

{self._generate_type_hints_test(language)}

{self._generate_docstrings_test(language)}

{self._generate_capability_checks_test(language)}

{self._generate_error_handling_test(language)}

{self._generate_audit_logging_test(language)}

{self._generate_resource_limits_test(language)}

{self._generate_isolation_type_test(language)}
"""
    
    def _generate_protocol_version_test(self, language: str) -> str:
        """Генерация теста на protocol_version"""
        if language == 'python':
            return """
def test_protocol_version_present():
    '''Все модели должны иметь protocol_version="1.0"'''
    import module
    assert hasattr(module, 'PROTOCOL_VERSION')
    assert module.PROTOCOL_VERSION == "1.0"
    
    # Проверка всех Pydantic моделей
    from pydantic import BaseModel
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and issubclass(obj, BaseModel):
            instance = obj()
            assert hasattr(instance, 'protocol_version')
            assert instance.protocol_version == "1.0"
"""
        return f"# Protocol version test for {language}"
    
    def _generate_type_hints_test(self, language: str) -> str:
        """Генерация теста на type hints"""
        if language == 'python':
            return """
def test_type_hints_present():
    '''Все функции должны иметь type hints'''
    import inspect
    import module
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj):
            sig = inspect.signature(obj)
            assert sig.return_annotation != inspect.Parameter.empty, \
                f"Function {name} missing return type hint"
            
            for param_name, param in sig.parameters.items():
                if param_name != 'self':
                    assert param.annotation != inspect.Parameter.empty, \
                        f"Function {name} parameter {param_name} missing type hint"
"""
        return f"# Type hints test for {language}"
    
    def _generate_capability_checks_test(self, language: str) -> str:
        """Генерация теста на capability checks"""
        return """
def test_capability_checks_present():
    '''Проверки capabilities должны быть перед действиями'''
    import module
    import inspect
    
    source = inspect.getsource(module)
    
    # Проверка наличия capability проверок
    assert 'capability' in source.lower() or 'security' in source.lower(), \
        "No capability checks detected in code"
    
    # Проверка что capability checks вызываются перед действиями
    # (базовая эвристика)
    assert 'check_capabilities' in source or 'has_capability' in source, \
        "Capability check method not found"
"""
    
    def _generate_audit_logging_test(self, language: str) -> str:
        """Генерация теста на audit logging"""
        return """
def test_audit_logging_present():
    '''Audit logging должен быть реализован'''
    import module
    import inspect
    
    source = inspect.getsource(module)
    
    assert 'audit' in source.lower() or 'log' in source.lower(), \
        "No audit logging detected in code"
    
    # Проверка что audit_action вызывается
    assert 'audit_action' in source or 'log_action' in source, \
        "Audit logging method not found"
"""
    
    async def _estimate_coverage(self,
                                  code: str,
                                  tests: str,
                                  target: float) -> float:
        """
        Оценка покрытия тестов.
        🔹 Наше дополнение (не было в Codex)
        """
        # В реальной реализации — запуск pytest-cov
        # Здесь — эмуляция на основе анализа
        
        code_lines = len([l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')])
        test_lines = len([l for l in tests.split('\n') if l.strip() and not l.strip().startswith('#')])
        
        # Эвристика: соотношение строк тестов к коду
        ratio = test_lines / max(code_lines, 1)
        
        # Корректировка на основе наличия spec compliance тестов
        spec_bonus = 0.1 if all(test in tests for test in self.SPEC_REQUIRED_TESTS) else 0
        
        coverage = min(0.95, (ratio * 0.8) + spec_bonus)
        
        return round(coverage, 2)
    
    async def _generate_additional_tests(self,
                                          code: str,
                                          language: str,
                                          current_tests: str,
                                          target_coverage: float) -> str:
        """
        Генерация дополнительных тестов для достижения target coverage.
        🔹 Наше дополнение (не было в Codex)
        """
        prompt = f"""
Generate additional tests to improve coverage for this {language} code:

Code:
{code}

Current Tests:
{current_tests}

Target Coverage: {target_coverage * 100}%

Requirements:
1. Focus on uncovered branches and edge cases
2. Test error conditions
3. Test boundary values
4. Include async tests if applicable
5. Follow {language} testing best practices
6. Include protocol_version="1.0" in test metadata

Return only the additional test code.
"""
        
        additional = await self.llm.generate(prompt)
        return self._extract_code_from_response(additional, language)
```

---

## 5️⃣ ЧТО НЕ БРАТЬ ИЗ CODEX

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет isolation policy | Нет enforcement | IsolationEnforcementPolicy class |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Нет checkpoint/rollback | Нет recovery | RollbackManager с is_fresh() |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |
| Нет deterministic seeds | Нет воспроизводимости | execution_seed в контексте |
| Simple error handling | Нет structured recovery | StructuredError с rollback trigger |

---

## 6️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Code Generation (Неделя 7-9)

| Задача | Codex Pattern | Файл Synapse | Статус |
|--------|---------------|--------------|--------|
| Multi-Language Generator | Code generation | `synapse/skills/code_generator.py` | ⏳ Ожидает |
| Code Completer | Inline completion | `synapse/skills/code_completer.py` | ⏳ Ожидает |
| Security Scan | Safe generation | `synapse/security/code_scan.py` | ⏳ Ожидает |

### Фаза 2: Code Translation (Неделя 9-10)

| Задача | Codex Pattern | Файл Synapse | Статус |
|--------|---------------|--------------|--------|
| Code Translator | Cross-language | `synapse/skills/code_translator.py` | ⏳ Ожидает |
| Equivalence Check | Semantic verification | `synapse/skills/equivalence.py` | ⏳ Ожидает |

### Фаза 3: Test Generation (Неделя 7-9)

| Задача | Codex Pattern | Файл Synapse | Статус |
|--------|---------------|--------------|--------|
| Test Generator | Auto tests | `synapse/skills/test_generator.py` | ⏳ Ожидает |
| Coverage Check | Coverage verification | `synapse/skills/coverage.py` | ⏳ Ожидает |

---

## 7️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить OpenAI Codex documentation (архив)
□ Изучить Codex research papers
□ Изучить GitHub Copilot patterns
□ Изучить multi-language code generation best practices

□ НЕ брать security model (у нас capability-based)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)
□ НЕ брать resource management (у нас ResourceLimits schema)

□ Адаптировать code generation с multi-language support
□ Адаптировать code completion с context awareness
□ Адаптировать code translation с semantic verification
□ Адаптировать test generation с spec compliance tests
□ Адаптировать все компоненты с protocol_version="1.0"

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 8️⃣ СРАВНЕНИЕ: ВСЕ ИСТОЧНИКИ

| Область | OpenClaw | Agent Zero | Anthropic | Claude Code | Codex | Synapse |
|---------|----------|------------|-----------|-------------|-------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ (OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (Agent Zero) |
| Code Generation | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Codex/Claude) |
| Code Completion | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Codex) |
| Multi-Language | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Codex) |
| Code Translation | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Codex) |
| Test Generation | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Claude/Codex) |
| Tool Use | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (Anthropic) |
| Safety | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Protocol Versioning | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |

---

## 9️⃣ ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 9.1 OpenAI Terms

```
OpenAI API Terms: https://openai.com/terms
Codex Documentation: https://platform.openai.com/docs/guides/code

При использовании Codex patterns:
1. Соблюдать API Terms of Service
2. Указать ссылку на документацию OpenAI
3. Добавить заметку об адаптации в docstring
```

### 9.2 Формат Атрибуции

```python
# synapse/skills/code_generator.py
"""
Multi-Language Code Generator для Synapse.

Адаптировано из OpenAI Codex patterns:
https://platform.openai.com/docs/guides/code

Оригинальная лицензия: OpenAI Terms of Service
Адаптация: Добавлен multi-language security scan, protocol versioning,
           capability requirements, spec compliance tests, rollback integration

Copyright (c) 2024 OpenAI
Copyright (c) 2026 Synapse Contributors
"""
```

---

## 🔟 ВЕРСИОНИРОВАНИЕ ДОКУМЕНТА

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
**OpenAI Codex:** https://platform.openai.com/docs/guides/code

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md