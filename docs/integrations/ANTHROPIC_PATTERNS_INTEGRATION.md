# 📎 PROJECT SYNAPSE: ANTHROPIC PATTERNS INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## ⚠️ ВАЖНОЕ ПРИМЕЧАНИЕ

**Статус репозиториев:** На момент создания этого документа репозитории `https://github.com/anthropics/skills` и `https://github.com/anthropics/claude-code` могут быть:
- Внутренними проектами Anthropic
- Новыми публичными репозиториями (после knowledge cutoff)
- Концептуальными ссылками на паттерны Anthropic

**Подход этого документа:** Анализирует **известные публичные паттерны Anthropic** (Claude Tool Use, Skills API, Claude Code patterns) из официальной документации и публичных выступлений, а не конкретный код репозиториев.

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к:
- `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md` (основная спецификация)
- `OPENCLAW_INTEGRATION.md` (интеграция OpenClaw)
- `AGENT_ZERO_INTEGRATION.md` (интеграция Agent Zero)

Он описывает стратегию интеграции полезных паттернов из экосистемы **Anthropic Claude** в платформу Synapse.

**Важно:** Anthropic паттерны используются как **референс для production-ready LLM integration**, а НЕ как архитектурная основа. Synapse имеет более строгую security model, self-evolution capability, и protocol versioning.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Паттернов для Заимствования | Статус |
|---------|---------------------|------------------------------|--------|
| Tool Use / Function Calling | ⭐⭐⭐⭐⭐ | ~60% | ✅ Рекомендовано |
| Skill Discovery Patterns | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Prompt Engineering | ⭐⭐⭐⭐⭐ | ~45% | ✅ Рекомендовано |
| Safety & Alignment | ⭐⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| Context Management | ⭐⭐⭐⭐ | ~50% | ⚠️ Адаптировать |
| Error Handling | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Streaming Patterns | ⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| Security Model | ⭐⭐ | ~10% | ❌ НЕ брать (у нас capability-based) |

---

## 1️⃣ TOOL USE / FUNCTION CALLING (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | Anthropic Pattern | Файл Synapse | Действие |
|-----------|------------------|--------------|----------|
| Tool Definition Schema | Claude Tool Use API | `synapse/skills/tool_schema.py` | Адаптировать с protocol_version |
| Tool Selection Logic | Claude automatic tool use | `synapse/agents/tool_selector.py` | Адаптировать с capability checks |
| Tool Result Formatting | Claude tool_result | `synapse/skills/tool_result.py` | Адаптировать с error handling |
| Parallel Tool Execution | Claude parallel tool use | `synapse/skills/parallel_executor.py` | Адаптировать с resource limits |

### 1.2 Tool Definition Schema

```python
# Anthropic Tool Use API → synapse/skills/tool_schema.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Literal

class ToolInputSchema(BaseModel):
    """
    Схема входа инструмента (адаптировано из Anthropic Tool Use API).
    🔹 Наше дополнение: protocol_version и capability requirements
    """
    type: Literal["object"] = "object"
    properties: Dict[str, Dict[str, Any]]
    required: List[str]
    
    class Config:
        extra = "forbid"

class ToolDefinition(BaseModel):
    """
    Определение инструмента для LLM.
    Адаптировано из Anthropic Tool Use API с дополнениями Synapse.
    """
    
    name: str
    description: str
    input_schema: ToolInputSchema
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    required_capabilities: List[str] = []
    risk_level: int = 1
    isolation_type: str = "container"
    timeout_seconds: int = 60
    
    # 🔹 Наше дополнение: Resource limits
    resource_limits: Dict[str, int] = {
        "cpu_seconds": 60,
        "memory_mb": 512,
        "disk_mb": 100,
        "network_kb": 1024
    }
    
    # 🔹 Наше дополнение: Human approval requirement
    requires_human_approval: bool = False
    
    def to_anthropic_format(self) -> dict:
        """
        Конвертация в формат Anthropic Tool Use API.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_dump()
        }
    
    @classmethod
    def from_anthropic_format(cls, data: dict) -> "ToolDefinition":
        """
        Создание из формата Anthropic Tool Use API.
        """
        return cls(
            name=data["name"],
            description=data["description"],
            input_schema=ToolInputSchema(**data["input_schema"])
        )

class ToolUseRequest(BaseModel):
    """
    Запрос на использование инструмента.
    Адаптировано из Anthropic Tool Use API.
    """
    
    id: str
    name: str
    input: Dict[str, Any]
    
    # 🔹 Наше дополнение: Trace и security
    trace_id: str
    session_id: str
    protocol_version: str = "1.0"

class ToolUseResult(BaseModel):
    """
    Результат выполнения инструмента.
    Адаптировано из Anthropic Tool Use API с дополнениями.
    """
    
    tool_use_id: str
    content: Any
    is_error: bool = False
    
    # 🔹 Наше дополнение: Metrics и security
    execution_time_ms: int
    resources_used: Dict[str, int]
    protocol_version: str = "1.0"
    
    # 🔹 Наше дополнение: Для audit log
    agent_id: Optional[str] = None
    timestamp: Optional[str] = None
```

### 1.3 Tool Selection Logic

```python
# Anthropic automatic tool selection → synapse/agents/tool_selector.py
from typing import List, Optional, Dict
from skills.tool_schema import ToolDefinition, ToolUseRequest
from core.models import ExecutionContext

class ToolSelector:
    """
    Селектор инструментов на основе контекста.
    Адаптировано из Anthropic automatic tool use patterns.
    
    🔹 Наше дополнение: Capability-based filtering
    """
    
    def __init__(self, llm_provider, security_manager):
        self.llm = llm_provider
        self.security = security_manager  # 🔹 Наше дополнение
        self.protocol_version = "1.0"
    
    async def select_tools(
        self,
        available_tools: List[ToolDefinition],
        context: ExecutionContext,
        task_description: str
    ) -> List[ToolDefinition]:
        """
        Выбор подходящих инструментов для задачи.
        
        🔹 Наше дополнение: Фильтрация по capabilities перед LLM выбором
        """
        
        # 1. 🔹 Фильтрация по capabilities (наше дополнение из spec v3.1)
        capability_filtered = await self._filter_by_capabilities(
            available_tools,
            context.capabilities
        )
        
        # 2. 🔹 Фильтрация по risk level и human approval (наше дополнение)
        risk_filtered = await self._filter_by_risk(
            capability_filtered,
            context
        )
        
        # 3. LLM-based selection (паттерн из Anthropic)
        selected = await self._llm_select_tools(
            risk_filtered,
            task_description,
            context
        )
        
        return selected
    
    async def _filter_by_capabilities(
        self,
        tools: List[ToolDefinition],
        capabilities: List[str]
    ) -> List[ToolDefinition]:
        """
        Фильтрация инструментов по доступным capabilities.
        🔹 Наше дополнение (не было в Anthropic patterns)
        """
        filtered = []
        for tool in tools:
            has_all_caps = all(
                cap in capabilities
                for cap in tool.required_capabilities
            )
            if has_all_caps:
                filtered.append(tool)
            else:
                # Логирование отфильтрованных инструментов
                await self.security.log_security_event(
                    event_type="tool_filtered_no_capabilities",
                    user_id=context.agent_id if hasattr(context, 'agent_id') else "unknown",
                    details={
                        "tool": tool.name,
                        "missing_capabilities": [
                            cap for cap in tool.required_capabilities
                            if cap not in capabilities
                        ]
                    }
                )
        return filtered
    
    async def _filter_by_risk(
        self,
        tools: List[ToolDefinition],
        context: ExecutionContext
    ) -> List[ToolDefinition]:
        """
        Фильтрация по уровню риска.
        🔹 Наше дополнение из spec v3.1
        """
        filtered = []
        for tool in tools:
            if tool.risk_level >= 3 and not context.capabilities.get('high_risk_approval'):
                # Требуется human approval
                tool.requires_human_approval = True
            filtered.append(tool)
        return filtered
    
    async def _llm_select_tools(
        self,
        tools: List[ToolDefinition],
        task: str,
        context: ExecutionContext
    ) -> List[ToolDefinition]:
        """
        LLM-based выбор инструментов (паттерн из Anthropic).
        """
        tool_descriptions = "\n".join([
            f"- {t.name}: {t.description}"
            for t in tools
        ])
        
        prompt = f"""
        Select the most appropriate tools for this task:
        
        Task: {task}
        
        Available Tools:
        {tool_descriptions}
        
        Return only the names of selected tools as a JSON array.
        
        Consider:
        1. Tool capabilities match task requirements
        2. Minimal number of tools needed
        3. Tool dependencies and order
        """
        
        response = await self.llm.generate(prompt)
        selected_names = self._parse_tool_names(response)
        
        return [t for t in tools if t.name in selected_names]
```

### 1.4 Parallel Tool Execution

```python
# Anthropic parallel tool use → synapse/skills/parallel_executor.py
import asyncio
from typing import List, Dict
from skills.tool_schema import ToolUseRequest, ToolUseResult
from core.models import ResourceLimits

class ParallelToolExecutor:
    """
    Параллельное выполнение инструментов.
    Адаптировано из Anthropic parallel tool use patterns.
    
    🔹 Наше дополнение: Resource limits и isolation enforcement
    """
    
    def __init__(self, security_manager, resource_manager):
        self.security = security_manager
        self.resources = resource_manager
        self.protocol_version = "1.0"
    
    async def execute_parallel(
        self,
        requests: List[ToolUseRequest],
        context: ExecutionContext
    ) -> List[ToolUseResult]:
        """
        Параллельное выполнение нескольких инструментов.
        
        🔹 Наше дополнение: Проверка resource limits перед параллельным выполнением
        """
        
        # 1. 🔹 Проверка общих resource limits (наше дополнение)
        total_limits = await self._calculate_total_limits(requests)
        can_execute = await self.resources.check_limits(total_limits, context)
        
        if not can_execute:
            # Fallback к последовательному выполнению
            return await self.execute_sequential(requests, context)
        
        # 2. Параллельное выполнение (паттерн из Anthropic)
        tasks = [
            self._execute_single(request, context)
            for request in requests
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. Обработка результатов
        return [
            self._process_result(request, result)
            for request, result in zip(requests, results)
        ]
    
    async def execute_sequential(
        self,
        requests: List[ToolUseRequest],
        context: ExecutionContext
    ) -> List[ToolUseResult]:
        """
        Последовательное выполнение (fallback).
        """
        results = []
        for request in requests:
            result = await self._execute_single(request, context)
            results.append(self._process_result(request, result))
        return results
    
    async def _calculate_total_limits(
        self,
        requests: List[ToolUseRequest]
    ) -> ResourceLimits:
        """
        Расчёт общих лимитов ресурсов.
        🔹 Наше дополнение (не было в Anthropic patterns)
        """
        return ResourceLimits(
            cpu_seconds=sum(r.resource_limits.get('cpu_seconds', 60) for r in requests),
            memory_mb=sum(r.resource_limits.get('memory_mb', 512) for r in requests),
            disk_mb=sum(r.resource_limits.get('disk_mb', 100) for r in requests),
            network_kb=sum(r.resource_limits.get('network_kb', 1024) for r in requests)
        )
```

---

## 2️⃣ SKILL DISCOVERY PATTERNS (HIGH PRIORITY)

### 2.1 Skill Discovery API

```python
# Anthropic Skills patterns → synapse/skills/discovery.py
from typing import List, Dict, Optional
from skills.tool_schema import ToolDefinition

class SkillDiscoveryService:
    """
    Сервис обнаружения и регистрации навыков.
    Адаптировано из Anthropic Skills patterns.
    
    🔹 Наше дополнение: Lifecycle management и capability validation
    """
    
    def __init__(self, database, security_manager):
        self.db = database
        self.security = security_manager
        self.protocol_version = "1.0"
    
    async def discover_skills(self, query: str = None) -> List[ToolDefinition]:
        """
        Обнаружение доступных навыков.
        
        🔹 Наше дополнение: Фильтрация по status и trust_level
        """
        skills = await self.db.get_all_skills()
        
        # 🔹 Фильтрация по lifecycle status (наше дополнение)
        active_skills = [
            s for s in skills
            if s.status in ['active', 'verified']
            and s.trust_level in ['trusted', 'verified', 'human_approved']
        ]
        
        # Поиск по query
        if query:
            active_skills = await self._search_skills(active_skills, query)
        
        # Конвертация в ToolDefinition
        return [self._to_tool_definition(skill) for skill in active_skills]
    
    async def register_skill(self, skill_data: dict) -> ToolDefinition:
        """
        Регистрация нового навыка.
        
        🔹 Наше дополнение: Validation по spec v3.1
        """
        
        # 1. Валидация манифеста
        manifest = await self._validate_manifest(skill_data)
        
        # 2. 🔹 Проверка capabilities (наше дополнение)
        capabilities_valid = await self.security.validate_capabilities(
            manifest.required_capabilities
        )
        if not capabilities_valid:
            raise ValueError("Invalid capabilities in skill manifest")
        
        # 3. 🔹 Определение isolation type (наше дополнение)
        from core.isolation_policy import IsolationEnforcementPolicy
        manifest.isolation_type = IsolationEnforcementPolicy.get_required_isolation(
            trust_level=manifest.trust_level,
            risk_level=manifest.risk_level
        )
        
        # 4. 🔹 Добавление protocol_version (наше дополнение)
        manifest.protocol_version = self.protocol_version
        
        # 5. Сохранение в БД
        skill_id = await self.db.save_skill(manifest)
        
        return self._to_tool_definition(manifest)
    
    async def _validate_manifest(self, data: dict) -> ToolDefinition:
        """Валидация манифеста навыка"""
        # Проверка всех required полей из spec v3.1
        required_fields = [
            'name', 'version', 'description', 'author',
            'inputs', 'outputs', 'required_capabilities'
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        return ToolDefinition(**data)
```

### 2.2 Skill Versioning

```python
# Anthropic versioning patterns → synapse/skills/versioning.py
from typing import List, Optional
from datetime import datetime

class SkillVersionManager:
    """
    Менеджер версий навыков.
    Адаптировано из Anthropic versioning patterns.
    
    🔹 Наше дополнение: Backward compatibility checking
    """
    
    def __init__(self, database):
        self.db = database
        self.protocol_version = "1.0"
    
    async def get_latest_version(self, skill_name: str) -> Optional[str]:
        """Получение последней версии навыка"""
        versions = await self.db.get_skill_versions(skill_name)
        if not versions:
            return None
        return max(versions, key=lambda v: self._parse_version(v))
    
    async def get_version(self, skill_name: str, version: str) -> Optional[dict]:
        """Получение конкретной версии навыка"""
        return await self.db.get_skill_version(skill_name, version)
    
    async def check_backward_compatibility(
        self,
        skill_name: str,
        new_version: dict,
        old_version: dict
    ) -> dict:
        """
        Проверка обратной совместимости.
        🔹 Наше дополнение (не было в Anthropic patterns)
        """
        issues = []
        
        # Проверка изменений в input_schema
        new_inputs = set(new_version.get('inputs', {}).keys())
        old_inputs = set(old_version.get('inputs', {}).keys())
        
        # Удаление required полей — breaking change
        removed_required = old_inputs - new_inputs
        if removed_required:
            issues.append({
                'type': 'breaking_change',
                'severity': 'high',
                'description': f'Removed required inputs: {removed_required}'
            })
        
        # Проверка изменений в output_schema
        new_outputs = set(new_version.get('outputs', {}).keys())
        old_outputs = set(old_version.get('outputs', {}).keys())
        
        removed_outputs = old_outputs - new_outputs
        if removed_outputs:
            issues.append({
                'type': 'breaking_change',
                'severity': 'medium',
                'description': f'Removed outputs: {removed_outputs}'
            })
        
        # Проверка изменений в capabilities
        new_caps = set(new_version.get('required_capabilities', []))
        old_caps = set(old_version.get('required_capabilities', []))
        
        added_caps = new_caps - old_caps
        if added_caps:
            issues.append({
                'type': 'capability_change',
                'severity': 'medium',
                'description': f'Added capabilities: {added_caps}'
            })
        
        return {
            'compatible': len([i for i in issues if i['severity'] == 'high']) == 0,
            'issues': issues,
            'protocol_version': self.protocol_version
        }
    
    def _parse_version(self, version: str) -> tuple:
        """Парсинг версии для сравнения"""
        try:
            return tuple(map(int, version.split('.')))
        except:
            return (0, 0, 0)
```

---

## 3️⃣ PROMPT ENGINEERING PATTERNS (HIGH PRIORITY)

### 3.1 System Prompt Templates

```python
# Anthropic prompt patterns → synapse/llm/prompt_templates.py
from typing import Dict, List, Optional

class PromptTemplateManager:
    """
    Менеджер шаблонов промптов.
    Адаптировано из Anthropic prompt engineering patterns.
    
    🔹 Наше дополнение: Protocol version injection и security context
    """
    
    def __init__(self, database):
        self.db = database
        self.templates: Dict[str, str] = {}
        self.protocol_version = "1.0"
    
    async def get_system_prompt(self, agent_role: str) -> str:
        """
        Получение системного промпта для роли агента.
        
        🔹 Наше дополнение: Injection security context и capabilities
        """
        base_prompt = await self._load_template(f"system/{agent_role}")
        
        # 🔹 Добавление security context (наше дополнение из spec v3.1)
        security_context = f"""
        <security_constraints>
        - You MUST check capabilities before any action
        - You MUST respect isolation_type requirements
        - You MUST request human approval for risk_level >= 3
        - You MUST log all actions to audit log
        - protocol_version: {self.protocol_version}
        </security_constraints>
        """
        
        # 🔹 Добавление resource constraints (наше дополнение)
        resource_context = f"""
        <resource_constraints>
        - Maximum execution time: 60 seconds per skill
        - Maximum memory: 512 MB per skill
        - Maximum concurrent skills: 5
        </resource_constraints>
        """
        
        return f"{base_prompt}\n\n{security_context}\n\n{resource_context}"
    
    async def get_tool_use_prompt(self, available_tools: List[dict]) -> str:
        """
        Промпт для использования инструментов.
        Адаптировано из Anthropic tool use patterns.
        """
        tools_xml = "\n".join([
            f"""<tool>
            <name>{t['name']}</name>
            <description>{t['description']}</description>
            <input_schema>{t['input_schema']}</input_schema>
            </tool>"""
            for t in available_tools
        ])
        
        prompt = f"""
        You have access to the following tools:
        
        <tools>
        {tools_xml}
        </tools>
        
        When using tools:
        1. Think step-by-step about which tool to use
        2. Ensure you have the required capabilities
        3. Format tool input correctly
        4. Handle errors gracefully
        5. Log all tool usage
        
        Always use tools when they can help accomplish the task.
        """
        
        return prompt
    
    async def get_critic_prompt(self) -> str:
        """
        Промпт для Critic агента.
        Адаптировано из Anthropic evaluation patterns.
        """
        return """
        You are a Critic Agent responsible for evaluating task execution.
        
        Evaluate the following aspects:
        1. Was the task completed successfully?
        2. Were all capabilities properly checked?
        3. Were resource limits respected?
        4. Was the isolation type appropriate?
        5. What can be learned from this execution?
        
        Provide structured feedback:
        - success: boolean
        - reasoning: string
        - improvements: list of suggestions
        - patterns_to_remember: list of patterns
        """
```

### 3.2 Context Management

```python
# Anthropic context window management → synapse/memory/context_manager.py
from typing import List, Dict, Optional
from core.models import MemoryEntry

class ContextManager:
    """
    Менеджер контекста для LLM.
    Адаптировано из Anthropic context window patterns.
    
    🔹 Наше дополнение: Priority-based context selection
    """
    
    def __init__(self, memory_store, config: dict):
        self.memory = memory_store
        self.max_context_tokens = config.get('max_context_tokens', 100000)
        self.protocol_version = "1.0"
    
    async def build_context(
        self,
        session_id: str,
        task_description: str,
        available_tools: List[dict]
    ) -> str:
        """
        Построение контекста для LLM.
        
        🔹 Наше дополнение: Priority-based selection из памяти
        """
        
        # 1. Получение релевантной памяти
        memories = await self.memory.recall({
            'query_text': task_description,
            'memory_types': ['episodic', 'semantic', 'procedural'],
            'limit': 50
        })
        
        # 2. 🔹 Сортировка по приоритету (наше дополнение)
        sorted_memories = await self._prioritize_memories(memories, task_description)
        
        # 3. Построение контекста
        context_parts = []
        
        # System metadata
        context_parts.append(f"""
        <system_metadata>
        protocol_version: {self.protocol_version}
        session_id: {session_id}
        </system_metadata>
        """)
        
        # Available tools
        context_parts.append(self._format_tools_context(available_tools))
        
        # Relevant memories (с ограничением по токенам)
        context_parts.append(
            await self._format_memories_context(sorted_memories)
        )
        
        # Current task
        context_parts.append(f"""
        <current_task>
        {task_description}
        </current_task>
        """)
        
        return "\n".join(context_parts)
    
    async def _prioritize_memories(
        self,
        memories: List[MemoryEntry],
        task: str
    ) -> List[MemoryEntry]:
        """
        Приоритизация воспоминаний.
        🔹 Наше дополнение (не было в Anthropic patterns)
        """
        # Сортировка по:
        # 1. Релевантности к задаче
        # 2. Свежести (recency)
        # 3. Успешности выполнения
        # 4. Частоте использования
        
        scored_memories = []
        for memory in memories:
            score = 0
            
            # Релевантность
            score += memory.relevance_score * 100
            
            # Свежесть
            from datetime import datetime
            age_days = (datetime.utcnow() - memory.created_at).days
            score += max(0, 50 - age_days)
            
            # Успешность
            if memory.metadata.get('success', False):
                score += 30
            
            # Частота использования
            score += memory.metadata.get('usage_count', 0) * 5
            
            scored_memories.append((score, memory))
        
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored_memories]
```

---

## 4️⃣ SAFETY & ALIGNMENT PATTERNS (CRITICAL PRIORITY)

### 4.1 Safety Layer

```python
# Anthropic safety patterns → synapse/security/safety_layer.py
from typing import Dict, List, Optional
from core.models import ActionPlan, ExecutionContext

class SafetyLayer:
    """
    Слой безопасности и alignment.
    Адаптировано из Anthropic safety patterns.
    
    🔹 Наше дополнение: Integration с capability-based security
    """
    
    DANGEROUS_PATTERNS = [
        'delete all files',
        'format disk',
        'bypass security',
        'escalate privileges',
        'exfiltrate data',
        'disable logging',
        'modify system files'
    ]
    
    def __init__(self, security_manager, llm_provider):
        self.security = security_manager
        self.llm = llm_provider
        self.protocol_version = "1.0"
    
    async def evaluate_plan(self, plan: ActionPlan) -> Dict:
        """
        Оценка плана на безопасность.
        
        🔹 Наше дополнение: Multi-layer safety check
        """
        
        safety_report = {
            'safe': True,
            'risk_level': plan.risk_level,
            'issues': [],
            'recommendations': [],
            'protocol_version': self.protocol_version
        }
        
        # 1. Pattern matching (паттерн из Anthropic)
        pattern_issues = await self._check_dangerous_patterns(plan)
        safety_report['issues'].extend(pattern_issues)
        
        # 2. 🔹 Capability validation (наше дополнение из spec v3.1)
        capability_issues = await self._validate_capabilities(plan)
        safety_report['issues'].extend(capability_issues)
        
        # 3. 🔹 Resource limit check (наше дополнение)
        resource_issues = await self._check_resource_limits(plan)
        safety_report['issues'].extend(resource_issues)
        
        # 4. LLM-based safety evaluation (паттерн из Anthropic)
        llm_evaluation = await self._llm_safety_check(plan)
        safety_report['issues'].extend(llm_evaluation.get('issues', []))
        
        # 5. Определение final safety status
        safety_report['safe'] = len(safety_report['issues']) == 0
        safety_report['requires_human_approval'] = (
            plan.risk_level >= 3 or
            any(i.get('severity') == 'high' for i in safety_report['issues'])
        )
        
        # 6. Логирование
        if not safety_report['safe']:
            await self.security.log_security_event(
                event_type="safety_violation_detected",
                user_id=plan.agent_id if hasattr(plan, 'agent_id') else "unknown",
                details=safety_report
            )
        
        return safety_report
    
    async def _check_dangerous_patterns(self, plan: ActionPlan) -> List[dict]:
        """Проверка на опасные паттерны (паттерн из Anthropic)"""
        issues = []
        plan_text = str(plan).lower()
        
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in plan_text:
                issues.append({
                    'type': 'dangerous_pattern',
                    'severity': 'high',
                    'pattern': pattern,
                    'description': f'Dangerous pattern detected: {pattern}'
                })
        
        return issues
    
    async def _validate_capabilities(self, plan: ActionPlan) -> List[dict]:
        """
        Валидация capabilities.
        🔹 Наше дополнение (не было в Anthropic patterns)
        """
        issues = []
        
        for step in plan.steps:
            required_caps = step.get('required_capabilities', [])
            # Проверка наличия capabilities будет выполнена Security Manager
            # Здесь только предварительная проверка
            if not required_caps and step.get('risk_level', 1) >= 3:
                issues.append({
                    'type': 'missing_capabilities',
                    'severity': 'high',
                    'description': f'High risk step without capabilities: {step}'
                })
        
        return issues
    
    async def _check_resource_limits(self, plan: ActionPlan) -> List[dict]:
        """
        Проверка лимитов ресурсов.
        🔹 Наше дополнение из spec v3.1
        """
        issues = []
        
        total_cpu = sum(s.get('resource_limits', {}).get('cpu_seconds', 0) for s in plan.steps)
        total_memory = sum(s.get('resource_limits', {}).get('memory_mb', 0) for s in plan.steps)
        
        if total_cpu > 300:  # 5 минут общего времени
            issues.append({
                'type': 'resource_exceeded',
                'severity': 'medium',
                'description': f'Total CPU time ({total_cpu}s) exceeds limit'
            })
        
        if total_memory > 2048:  # 2 GB общей памяти
            issues.append({
                'type': 'resource_exceeded',
                'severity': 'medium',
                'description': f'Total memory ({total_memory}MB) exceeds limit'
            })
        
        return issues
    
    async def _llm_safety_check(self, plan: ActionPlan) -> Dict:
        """LLM-based проверка безопасности (паттерн из Anthropic)"""
        prompt = f"""
        Evaluate this action plan for safety concerns:
        
        {plan}
        
        Consider:
        1. Potential for unintended consequences
        2. Data privacy implications
        3. System stability risks
        4. Compliance with security policies
        
        Return:
        - safe: boolean
        - issues: list of concerns
        - recommendations: list of mitigations
        """
        
        response = await self.llm.generate(prompt)
        return self._parse_safety_response(response)
```

---

## 5️⃣ ERROR HANDLING PATTERNS (HIGH PRIORITY)

### 5.1 Structured Error Handling

```python
# Anthropic error handling → synapse/core/error_handler.py
from typing import Dict, Optional, Any
from enum import Enum

class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorType(str, Enum):
    CAPABILITY_ERROR = "capability_error"
    RESOURCE_ERROR = "resource_error"
    SECURITY_ERROR = "security_error"
    LLM_ERROR = "llm_error"
    SKILL_ERROR = "skill_error"
    SYSTEM_ERROR = "system_error"

class StructuredError(BaseModel):
    """
    Структурированная ошибка.
    Адаптировано из Anthropic error handling patterns.
    
    🔹 Наше дополнение: Integration с rollback и checkpoint
    """
    
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    
    # 🔹 Наше дополнение: Для recovery
    recoverable: bool = True
    suggested_action: Optional[str] = None
    checkpoint_id: Optional[str] = None
    
    # 🔹 Наше дополнение: Protocol version
    protocol_version: str = "1.0"
    timestamp: str

class ErrorHandler:
    """
    Обработчик ошибок.
    Адаптировано из Anthropic error handling patterns.
    
    🔹 Наше дополнение: Automatic rollback trigger
    """
    
    def __init__(self, security_manager, rollback_manager):
        self.security = security_manager
        self.rollback = rollback_manager  # 🔹 Наше дополнение
        self.protocol_version = "1.0"
    
    async def handle_error(
        self,
        error: Exception,
        context: ExecutionContext
    ) -> StructuredError:
        """
        Обработка ошибки с структурированным выводом.
        """
        
        structured = await self._classify_error(error, context)
        
        # 🔹 Автоматический rollback для критических ошибок (наше дополнение)
        if structured.severity == ErrorSeverity.CRITICAL:
            if context.checkpoint_id:
                await self.rollback.execute_rollback(context.checkpoint_id)
                structured.suggested_action = "Rollback executed"
            else:
                structured.suggested_action = "Emergency stop required"
        
        # Логирование
        await self.security.audit_action(
            action="error_handled",
            result=str(structured),
            context=context
        )
        
        return structured
    
    async def _classify_error(
        self,
        error: Exception,
        context: ExecutionContext
    ) -> StructuredError:
        """Классификация ошибки"""
        
        from core.security import CapabilityError
        from core.resource_manager import ResourceExceededError
        
        if isinstance(error, CapabilityError):
            return StructuredError(
                error_type=ErrorType.CAPABILITY_ERROR,
                severity=ErrorSeverity.HIGH,
                message=str(error),
                details={'capabilities': context.capabilities},
                recoverable=False,
                protocol_version=self.protocol_version
            )
        
        if isinstance(error, ResourceExceededError):
            return StructuredError(
                error_type=ErrorType.RESOURCE_ERROR,
                severity=ErrorSeverity.MEDIUM,
                message=str(error),
                details={'limits': context.resource_limits},
                recoverable=True,
                suggested_action="Retry with reduced resource requirements",
                protocol_version=self.protocol_version
            )
        
        # Default
        return StructuredError(
            error_type=ErrorType.SYSTEM_ERROR,
            severity=ErrorSeverity.HIGH,
            message=str(error),
            details={'type': type(error).__name__},
            recoverable=False,
            protocol_version=self.protocol_version
        )
```

---

## 6️⃣ STREAMING PATTERNS (MEDIUM PRIORITY)

### 6.1 Response Streaming

```python
# Anthropic streaming → synapse/llm/streaming.py
from typing import AsyncIterator, Dict, Any

class StreamingResponse:
    """
    Потоковый ответ от LLM.
    Адаптировано из Anthropic streaming patterns.
    
    🔹 Наше дополнение: Protocol version и trace injection
    """
    
    def __init__(self, stream: AsyncIterator, trace_id: str, session_id: str):
        self.stream = stream
        self.trace_id = trace_id
        self.session_id = session_id
        self.protocol_version = "1.0"
        self.chunks: list = []
    
    async def __aiter__(self):
        async for chunk in self.stream:
            self.chunks.append(chunk)
            
            # 🔹 Добавление metadata к каждому chunk (наше дополнение)
            enriched_chunk = {
                'content': chunk,
                'trace_id': self.trace_id,
                'session_id': self.session_id,
                'protocol_version': self.protocol_version,
                'chunk_index': len(self.chunks) - 1
            }
            
            yield enriched_chunk
    
    async def get_full_response(self) -> str:
        """Получение полного ответа после завершения стрима"""
        return "".join(self.chunks)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик стриминга"""
        return {
            'total_chunks': len(self.chunks),
            'trace_id': self.trace_id,
            'session_id': self.session_id,
            'protocol_version': self.protocol_version
        }

class StreamingLLMProvider:
    """
    LLM провайдер с поддержкой стриминга.
    Адаптировано из Anthropic streaming patterns.
    """
    
    def __init__(self, provider, config: dict):
        self.provider = provider
        self.config = config
        self.protocol_version = "1.0"
    
    async def generate_stream(
        self,
        prompt: str,
        trace_id: str,
        session_id: str
    ) -> StreamingResponse:
        """Генерация потокового ответа"""
        
        stream = await self.provider.generate_stream(
            prompt=prompt,
            stream=True
        )
        
        return StreamingResponse(
            stream=stream,
            trace_id=trace_id,
            session_id=session_id
        )
```

---

## 7️⃣ ЧТО НЕ БРАТЬ ИЗ ANTHROPIC PATTERNS

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет isolation policy | Нет enforcement | IsolationEnforcementPolicy class |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Нет checkpoint/rollback | Нет recovery | RollbackManager с is_fresh() |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |
| Нет deterministic seeds | Нет воспроизводимости | execution_seed в контексте |
| Простой error handling | Нет structured recovery | StructuredError с rollback trigger |

---

## 8️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Tool Use (Неделя 3-4)

| Задача | Anthropic Pattern | Файл Synapse | Статус |
|--------|------------------|--------------|--------|
| Tool Schema | Tool Use API | `synapse/skills/tool_schema.py` | ⏳ Ожидает |
| Tool Selection | Automatic tool use | `synapse/agents/tool_selector.py` | ⏳ Ожидает |
| Parallel Execution | Parallel tool use | `synapse/skills/parallel_executor.py` | ⏳ Ожидает |

### Фаза 2: Skill Discovery (Неделя 5-6)

| Задача | Anthropic Pattern | Файл Synapse | Статус |
|--------|------------------|--------------|--------|
| Discovery Service | Skills API | `synapse/skills/discovery.py` | ⏳ Ожидает |
| Versioning | Version management | `synapse/skills/versioning.py` | ⏳ Ожидает |
| Compatibility | Backward compat | `synapse/skills/compatibility.py` | ⏳ Ожидает |

### Фаза 3: Prompt Engineering (Неделя 4-5)

| Задача | Anthropic Pattern | Файл Synapse | Статус |
|--------|------------------|--------------|--------|
| System Prompts | Prompt templates | `synapse/llm/prompt_templates.py` | ⏳ Ожидает |
| Context Mgmt | Context window | `synapse/memory/context_manager.py` | ⏳ Ожидает |

### Фаза 4: Safety & Error Handling (Неделя 6-7)

| Задача | Anthropic Pattern | Файл Synapse | Статус |
|--------|------------------|--------------|--------|
| Safety Layer | Safety patterns | `synapse/security/safety_layer.py` | ⏳ Ожидает |
| Error Handler | Error handling | `synapse/core/error_handler.py` | ⏳ Ожидает |
| Streaming | Streaming API | `synapse/llm/streaming.py` | ⏳ Ожидает |

---

## 9️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить Anthropic Tool Use API documentation
□ Изучить Anthropic Skills patterns (если доступны)
□ Изучить Anthropic prompt engineering guide
□ Изучить Anthropic safety & alignment patterns
□ Изучить Anthropic error handling patterns

□ НЕ брать security model (у нас capability-based)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)
□ НЕ брать resource management (у нас ResourceLimits schema)

□ Адаптировать tool schema с protocol_version
□ Адаптировать tool selection с capability filtering
□ Адаптировать prompt templates с security context
□ Адаптировать error handling с rollback trigger
□ Адаптировать streaming с trace injection

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 🔟 СРАВНЕНИЕ: ВСЕ ИСТОЧНИКИ

| Область | OpenClaw | Agent Zero | Anthropic | Synapse |
|---------|----------|------------|-----------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (Agent Zero) |
| Tool Use | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Anthropic) |
| Prompt Engineering | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Anthropic) |
| Safety | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Protocol Versioning | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ❌ | ✅ (оригинальное) |

---

## 1️⃣1️⃣ ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 11.1 Anthropic Terms

```
Anthropic API Terms: https://www.anthropic.com/legal/terms
Claude API Documentation: https://docs.anthropic.com/claude/docs

При использовании Anthropic patterns:
1. Соблюдать API Terms of Service
2. Указать ссылку на документацию Anthropic
3. Добавить заметку об адаптации в docstring
```

### 11.2 Формат Атрибуции

```python
# synapse/skills/tool_schema.py
"""
Tool Schema для Synapse.

Адаптировано из Anthropic Tool Use API:
https://docs.anthropic.com/claude/docs/tool-use

Оригинальная лицензия: Anthropic Terms of Service
Адаптация: Добавлен protocol versioning, capability requirements,
           resource limits, isolation enforcement

Copyright (c) 2024 Anthropic, PBC
Copyright (c) 2026 Synapse Contributors
"""
```

---

## 1️⃣2️⃣ ВЕРСИОНИРОВАНИЕ ДОКУМЕНТА

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2026-01-03 | Initial release |

---

## 📞 КОНТАКТЫ И ПОДДЕРЖКА

**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**TDD Инструкция:** `TDD_INSTRUCTION_v1.2_FINAL.md`  
**OpenClaw Integration:** `OPENCLAW_INTEGRATION.md`  
**Agent Zero Integration:** `AGENT_ZERO_INTEGRATION.md`  
**Anthropic Documentation:** https://docs.anthropic.com/claude/docs

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md