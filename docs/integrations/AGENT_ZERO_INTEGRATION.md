# 📎 PROJECT SYNAPSE: AGENT ZERO INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к основной технической спецификации `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md` и документу интеграции OpenClaw `OPENCLAW_INTEGRATION.md`. Он описывает стратегию интеграции полезных паттернов и компонентов из проекта [Agent Zero](https://github.com/agent0ai/agent-zero) в платформу Synapse.

**Важно:** Agent Zero используется как **референс для self-evolution patterns**, а НЕ как архитектурная основа. Synapse имеет более строгую security model, production-ready reliability features, и формализованный protocol versioning.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Кода для Заимствования | Статус |
|---------|---------------------|-------------------------|--------|
| Self-Evolution Engine | ⭐⭐⭐⭐⭐ | ~40% | ✅ Рекомендовано |
| Agent Hierarchy | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Learning Engine | ⭐⭐⭐⭐⭐ | ~45% | ✅ Рекомендовано |
| Code Generation | ⭐⭐⭐⭐ | ~35% | ⚠️ Адаптировать |
| Memory Consolidation | ⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| Prompt Management | ⭐⭐⭐⭐ | ~30% | ⚠️ Адаптировать |
| Cognitive Loop | ⭐⭐⭐ | ~25% | ⚠️ Адаптировать |
| Security Model | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐⭐ | ~10% | ❌ НЕ брать |

---

## 1️⃣ SELF-EVOLUTION ENGINE (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | Файл Agent Zero | Файл Synapse | Действие |
|-----------|----------------|--------------|----------|
| Developer Agent | `agents/developer.py` | `synapse/agents/developer.py` | Адаптировать с security layer |
| Critic Agent | `agents/critic.py` | `synapse/agents/critic.py` | Адаптировать с evaluation metrics |
| Learning Loop | `learning/loop.py` | `synapse/learning/engine.py` | Адаптировать с checkpoint |
| Skill Generator | `skills/generator.py` | `synapse/skills/generator.py` | Адаптировать с isolation policy |

### 1.2 Паттерн Генерации Навыков

```python
# agent0ai/agents/developer.py → synapse/agents/developer.py
from typing import Optional, List
from core.models import SkillManifest, ExecutionContext, PROTOCOL_VERSION
from skills.base import BaseSkill, RuntimeIsolationType
from core.isolation_policy import IsolationEnforcementPolicy

class DeveloperAgent:
    """
    Агент-разработчик для генерации новых навыков.
    Адаптировано из Agent Zero с добавлением security layer.
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, llm_provider, security_manager):
        self.llm = llm_provider
        self.security = security_manager  # 🔹 Наше дополнение
        self.protocol_version = PROTOCOL_VERSION
    
    async def generate_skill(self, task_description: str, 
                             context: ExecutionContext) -> Optional[BaseSkill]:
        """
        Генерация нового навыка на основе задачи.
        
        Workflow из Agent Zero с нашими дополнениями:
        1. Анализ пробела в возможностях
        2. Генерация кода навыка
        3. Генерация тестов
        4. Проверка безопасности (наше дополнение)
        5. Применение isolation policy (наше дополнение)
        """
        
        # 1. Анализ задачи (паттерн из Agent Zero)
        analysis = await self._analyze_task_gap(task_description, context)
        
        # 2. Генерация кода (паттерн из Agent Zero)
        skill_code = await self._generate_skill_code(analysis)
        
        # 3. Генерация тестов (паттерн из Agent Zero)
        test_code = await self._generate_test_code(skill_code)
        
        # 4. 🔹 Проверка безопасности (наше дополнение из spec v3.1)
        security_scan = await self.security.scan_code(skill_code)
        if not security_scan.passed:
            await self.security.log_security_event(
                event_type="skill_generation_blocked",
                user_id=context.agent_id,
                details={"reason": security_scan.reason}
            )
            return None
        
        # 5. 🔹 Применение isolation policy (наше дополнение)
        manifest = await self._create_manifest(analysis)
        required_isolation = IsolationEnforcementPolicy.get_required_isolation(
            trust_level=manifest.trust_level,
            risk_level=manifest.risk_level
        )
        manifest.isolation_type = required_isolation
        
        # 6. 🔹 Добавление protocol version (наше дополнение)
        manifest.protocol_version = self.PROTOCOL_VERSION
        
        # 7. Создание навыка
        skill = await self._compile_skill(skill_code, manifest)
        
        return skill
    
    async def _analyze_task_gap(self, task: str, context: ExecutionContext) -> dict:
        """Анализ пробела в возможностях (паттерн из Agent Zero)"""
        prompt = f"""
        Analyze the following task and identify capability gaps:
        
        Task: {task}
        Current Context: {context}
        
        Identify:
        1. What skills are needed?
        2. What skills are missing?
        3. What would a new skill look like?
        """
        
        analysis = await self.llm.generate(prompt)
        return self._parse_analysis(analysis)
    
    async def _generate_skill_code(self, analysis: dict) -> str:
        """Генерация кода навыка (паттерн из Agent Zero)"""
        prompt = f"""
        Generate a Python skill class based on this analysis:
        
        {analysis}
        
        Requirements:
        - Inherit from BaseSkill
        - Include manifest with all required fields
        - Include execute() method
        - Include error handling
        - Follow protocol_version="1.0"
        """
        
        code = await self.llm.generate(prompt)
        return code
    
    async def _generate_test_code(self, skill_code: str) -> str:
        """Генерация тестов для навыка (паттерн из Agent Zero)"""
        prompt = f"""
        Generate pytest tests for this skill:
        
        {skill_code}
        
        Requirements:
        - Test all input combinations
        - Test error cases
        - Test capability requirements
        - Test resource limits
        """
        
        tests = await self.llm.generate(prompt)
        return tests
```

### 1.3 Lifecycle Management

```python
# agent0ai/skills/lifecycle.py → synapse/skills/lifecycle.py
from enum import Enum
from datetime import datetime
from typing import Optional

class SkillLifecycleStatus(str, Enum):
    """
    Статусы жизненного цикла навыка.
    Расширено из Agent Zero с добавлением checkpoint integration.
    """
    GENERATED = "generated"      # Только что сгенерирован
    TESTED = "tested"           # Тесты пройдены
    VERIFIED = "verified"       # Security scan пройден
    ACTIVE = "active"           # Активен и используется
    DEPRECATED = "deprecated"   # Устарел, не используется
    ARCHIVED = "archived"       # Архивирован

class SkillLifecycleManager:
    """
    Менеджер жизненного цикла навыков.
    Адаптировано из Agent Zero с добавлением checkpoint integration.
    """
    
    def __init__(self, database, checkpoint_manager):
        self.db = database
        self.checkpoint = checkpoint_manager  # 🔹 Наше дополнение
    
    async def transition(self, skill_id: str, from_status: SkillLifecycleStatus,
                         to_status: SkillLifecycleStatus, metadata: dict = None):
        """
        Переход между статусами жизненного цикла.
        
        🔹 Наше дополнение: Создание checkpoint при критических переходах
        """
        # Валидация перехода
        if not self._is_valid_transition(from_status, to_status):
            raise ValueError(f"Invalid transition: {from_status} → {to_status}")
        
        # 🔹 Создание checkpoint при активации навыка
        if to_status == SkillLifecycleStatus.ACTIVE:
            checkpoint_id = await self.checkpoint.create_checkpoint(
                agent_id="skill_lifecycle",
                session_id=skill_id
            )
            metadata = metadata or {}
            metadata['checkpoint_id'] = checkpoint_id
        
        # Обновление статуса в БД
        await self.db.update_skill_status(
            skill_id=skill_id,
            status=to_status.value,
            metadata=metadata
        )
        
        # Логирование перехода
        await self._log_transition(skill_id, from_status, to_status, metadata)
    
    def _is_valid_transition(self, from_status: SkillLifecycleStatus,
                             to_status: SkillLifecycleStatus) -> bool:
        """Валидация допустимых переходов (паттерн из Agent Zero)"""
        valid_transitions = {
            SkillLifecycleStatus.GENERATED: [
                SkillLifecycleStatus.TESTED,
                SkillLifecycleStatus.ARCHIVED
            ],
            SkillLifecycleStatus.TESTED: [
                SkillLifecycleStatus.VERIFIED,
                SkillLifecycleStatus.GENERATED
            ],
            SkillLifecycleStatus.VERIFIED: [
                SkillLifecycleStatus.ACTIVE,
                SkillLifecycleStatus.TESTED
            ],
            SkillLifecycleStatus.ACTIVE: [
                SkillLifecycleStatus.DEPRECATED,
                SkillLifecycleStatus.VERIFIED
            ],
            SkillLifecycleStatus.DEPRECATED: [
                SkillLifecycleStatus.ARCHIVED,
                SkillLifecycleStatus.ACTIVE
            ],
            SkillLifecycleStatus.ARCHIVED: []  # Terminal state
        }
        
        return to_status in valid_transitions.get(from_status, [])
```

---

## 2️⃣ AGENT HIERARCHY (CRITICAL PRIORITY)

### 2.1 Специализированные Агенты

| Тип Агента | Agent Zero | Synapse | Действие |
|------------|------------|---------|----------|
| Planner | `agents/planner.py` | `synapse/agents/planner.py` | Адаптировать с freeze mechanism |
| Executor | `agents/executor.py` | `synapse/agents/executor.py` | Адаптировать с capability checks |
| Critic | `agents/critic.py` | `synapse/agents/critic.py` | Адаптировать с metrics |
| Developer | `agents/developer.py` | `synapse/agents/developer.py` | Адаптировать с security scan |
| Guardian | — | `synapse/agents/guardian.py` | 🔹 Наше оригинальное дополнение |

### 2.2 Agent Communication Protocol

```python
# agent0ai/agents/communication.py → synapse/core/protocol.py
from pydantic import BaseModel
from typing import Any, Dict, Optional
from enum import Enum
import uuid
from datetime import datetime

class AgentRole(str, Enum):
    """
    Роли агентов в иерархии.
    Расширено из Agent Zero с добавлением Guardian role.
    """
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    EXECUTOR = "executor"
    CRITIC = "critic"
    DEVELOPER = "developer"
    GUARDIAN = "guardian"  # 🔹 Наше дополнение

class AgentMessage(BaseModel):
    """
    Сообщение между агентами.
    Адаптировано из Agent Zero с добавлением protocol_version.
    """
    
    protocol_version: str = "1.0"  # 🔹 Наше дополнение
    message_id: str = str(uuid.uuid4())
    sender: str
    sender_role: AgentRole
    recipient: str
    recipient_role: AgentRole
    message_type: str
    intent: str
    payload: Dict[str, Any]
    trace_id: str
    session_id: str
    timestamp: str = datetime.utcnow().isoformat()
    ttl_seconds: int = 300
    signature: Optional[str] = None
    
    # 🔹 Наше дополнение: Trace propagation
    trace_parent_id: Optional[str] = None
    trace_flags: Optional[int] = 0

class AgentHierarchy:
    """
    Иерархия агентов с координацией.
    Адаптировано из Agent Zero с добавлением security layer.
    """
    
    def __init__(self, config: dict):
        self.agents = {}
        self.message_bus = MessageBus()
        self.security = SecurityManager()  # 🔹 Наше дополнение
        self.protocol_version = "1.0"
    
    async def register_agent(self, role: AgentRole, agent):
        """Регистрация агента в иерархии"""
        self.agents[role.value] = agent
        
        # 🔹 Проверка capabilities агента
        capabilities = await self.security.get_agent_capabilities(role)
        agent.capabilities = capabilities
    
    async def delegate_task(self, from_role: AgentRole, to_role: AgentRole,
                            task: dict) -> dict:
        """
        Делегирование задачи между агентами.
        
        🔹 Наше дополнение: Проверка capabilities перед делегированием
        """
        # Проверка capabilities
        can_delegate = await self.security.check_delegation_permission(
            from_role=from_role,
            to_role=to_role,
            task=task
        )
        
        if not can_delegate:
            raise PermissionError("Delegation not allowed")
        
        # Создание сообщения
        message = AgentMessage(
            sender=from_role.value,
            sender_role=from_role,
            recipient=to_role.value,
            recipient_role=to_role,
            message_type="task",
            intent=task['intent'],
            payload=task,
            trace_id=task.get('trace_id', str(uuid.uuid4())),
            session_id=task.get('session_id'),
            protocol_version=self.protocol_version
        )
        
        # Отправка через message bus
        await self.message_bus.publish(message)
        
        # Ожидание ответа
        response = await self.message_bus.request_reply(
            message=message,
            timeout=task.get('timeout', 300)
        )
        
        return response.payload
```

### 2.3 Agent Specialization Patterns

```python
# agent0ai/agents/specialization.py → synapse/agents/specialization.py
from typing import List, Dict
from core.models import MemoryQuery

class AgentSpecializationManager:
    """
    Менеджер специализации агентов.
    Адаптировано из Agent Zero с добавлением performance tracking.
    """
    
    def __init__(self, memory_store, metrics_collector):
        self.memory = memory_store
        self.metrics = metrics_collector  # 🔹 Наше дополнение из spec v3.1
    
    async def analyze_performance(self, agent_id: str) -> dict:
        """
        Анализ производительности агента.
        
        🔹 Наше дополнение: Integration с Prometheus metrics
        """
        # Получение метрик из Prometheus
        success_rate = await self.metrics.get_metric(
            'synapse_agent_success_rate',
            labels={'agent_id': agent_id}
        )
        
        avg_latency = await self.metrics.get_metric(
            'synapse_agent_latency_seconds',
            labels={'agent_id': agent_id}
        )
        
        task_count = await self.metrics.get_metric(
            'synapse_agent_tasks_total',
            labels={'agent_id': agent_id}
        )
        
        return {
            'agent_id': agent_id,
            'success_rate': success_rate,
            'avg_latency': avg_latency,
            'task_count': task_count,
            'recommendation': await self._generate_recommendation(
                success_rate, avg_latency, task_count
            )
        }
    
    async def _generate_recommendation(self, success_rate: float,
                                        avg_latency: float,
                                        task_count: int) -> str:
        """Генерация рекомендаций по оптимизации"""
        if success_rate < 0.8:
            return "Consider retraining or capability adjustment"
        if avg_latency > 5.0:
            return "Consider optimization or caching"
        if task_count < 10:
            return "Insufficient data for recommendations"
        return "Performance within acceptable range"
    
    async def suggest_specialization(self, agent_id: str) -> List[str]:
        """
        Предложение специализации на основе истории.
        (паттерн из Agent Zero)
        """
        # Анализ эпизодической памяти
        episodes = await self.memory.recall(MemoryQuery(
            query_text=f"agent:{agent_id} successful tasks",
            memory_types=['episodic'],
            limit=100
        ))
        
        # Выявление паттернов
        task_types = self._extract_task_patterns(episodes)
        
        # Рекомендация специализации
        return self._recommend_specialization(task_types)
```

---

## 3️⃣ LEARNING ENGINE (CRITICAL PRIORITY)

### 3.1 Learning Loop

```python
# agent0ai/learning/loop.py → synapse/learning/engine.py
from typing import Dict, List
from core.models import MemoryEntry, Episode
from datetime import datetime

class LearningEngine:
    """
    Движок обучения и адаптации.
    Адаптировано из Agent Zero с добавлением checkpoint integration.
    """
    
    def __init__(self, memory_store, critic_agent, checkpoint_manager):
        self.memory = memory_store
        self.critic = critic_agent
        self.checkpoint = checkpoint_manager  # 🔹 Наше дополнение
    
    async def process_episode(self, episode: Episode):
        """
        Обработка эпизода для обучения.
        
        Workflow из Agent Zero с нашими дополнениями:
        1. Оценка результата (Critic)
        2. Извлечение паттернов
        3. Обновление памяти
        4. Создание checkpoint (наше дополнение)
        5. Генерация улучшений (Developer)
        """
        
        # 1. Оценка результата (паттерн из Agent Zero)
        evaluation = await self.critic.evaluate(
            plan=episode.action_plan,
            result=episode.execution_result
        )
        
        # 2. Извлечение паттернов (паттерн из Agent Zero)
        patterns = await self._extract_patterns(episode, evaluation)
        
        # 3. Обновление процедурной памяти (паттерн из Agent Zero)
        if evaluation['success']:
            await self._reinforce_successful_patterns(patterns)
        else:
            await self._analyze_failure_patterns(patterns, evaluation)
        
        # 4. 🔹 Создание checkpoint (наше дополнение из spec v3.1)
        if episode.success and episode.risk_level >= 3:
            checkpoint_id = await self.checkpoint.create_checkpoint(
                agent_id=episode.agent_id,
                session_id=episode.session_id
            )
            episode.learning_outcome['checkpoint_id'] = checkpoint_id
        
        # 5. Сохранение эпизода в память
        memory_entry = MemoryEntry(
            id=str(uuid.uuid4()),
            type='episodic',
            content=str(episode),
            metadata={
                'success': episode.success,
                'duration_ms': episode.duration_ms,
                'tokens_used': episode.tokens_used,
                'patterns': patterns,
                'evaluation': evaluation,
                'protocol_version': "1.0"  # 🔹 Наше дополнение
            },
            created_at=datetime.utcnow().isoformat()
        )
        
        await self.memory.store(memory_entry)
        
        # 6. 🔹 Trigger consolidation если нужно (наше дополнение)
        if await self._should_consolidate():
            await self.memory.consolidate()
    
    async def _extract_patterns(self, episode: Episode,
                                 evaluation: dict) -> List[dict]:
        """Извлечение паттернов из эпизода (паттерн из Agent Zero)"""
        patterns = []
        
        # Паттерны успешных действий
        if evaluation['success']:
            patterns.append({
                'type': 'successful_action',
                'skill': episode.action_plan.get('skills_used'),
                'context': episode.input_event.get('context'),
                'outcome': evaluation.get('reasoning')
            })
        
        # Паттерны ошибок
        if not evaluation['success']:
            patterns.append({
                'type': 'failure_pattern',
                'error': episode.execution_result.get('error'),
                'cause': evaluation.get('failure_cause'),
                'prevention': evaluation.get('prevention')
            })
        
        return patterns
    
    async def _reinforce_successful_patterns(self, patterns: List[dict]):
        """Усиление успешных паттернов (паттерн из Agent Zero)"""
        for pattern in patterns:
            if pattern['type'] == 'successful_action':
                # Добавление в процедурную память
                await self.memory.store(MemoryEntry(
                    id=str(uuid.uuid4()),
                    type='procedural',
                    content=str(pattern),
                    metadata={'strength': 1.0, 'protocol_version': "1.0"}
                ))
    
    async def _analyze_failure_patterns(self, patterns: List[dict],
                                         evaluation: dict):
        """Анализ паттернов ошибок (паттерн из Agent Zero)"""
        for pattern in patterns:
            if pattern['type'] == 'failure_pattern':
                # Генерация рекомендаций через Developer Agent
                recommendations = await self._generate_improvements(pattern)
                pattern['recommendations'] = recommendations
```

### 3.2 Memory Consolidation

```python
# agent0ai/memory/consolidation.py → synapse/memory/consolidator.py
from typing import List, Dict
from core.models import MemoryEntry
import numpy as np
from sklearn.cluster import KMeans

class MemoryConsolidator:
    """
    Консолидация памяти (кластеризация, удаление шума).
    Адаптировано из Agent Zero с добавлением checkpoint preservation.
    """
    
    def __init__(self, vector_store, config: dict):
        self.vector_store = vector_store
        self.config = config
        self.min_relevance_threshold = config.get('min_relevance', 0.3)
        self.cluster_count = config.get('cluster_count', 10)
    
    async def consolidate(self) -> dict:
        """
        Фоновая консолидация памяти.
        
        Workflow:
        1. Извлечение всех записей
        2. Кластеризация по схожести
        3. Удаление дубликатов
        4. Усиление важных паттернов
        5. 🔹 Сохранение checkpoint перед модификацией (наше дополнение)
        """
        
        # 🔹 Создание checkpoint перед консолидацией
        checkpoint_id = await self._create_pre_consolidation_checkpoint()
        
        # 1. Извлечение записей
        entries = await self.vector_store.get_all_entries()
        
        # 2. Кластеризация
        clusters = await self._cluster_entries(entries)
        
        # 3. Удаление дубликатов
        duplicates_removed = await self._remove_duplicates(clusters)
        
        # 4. Усиление важных паттернов
        patterns_reinforced = await self._reinforce_important_patterns(clusters)
        
        # 5. Удаление шума (низкая релевантность)
        noise_removed = await self._remove_low_relevance_entries(
            entries,
            self.min_relevance_threshold
        )
        
        return {
            'checkpoint_id': checkpoint_id,
            'entries_processed': len(entries),
            'clusters_created': len(clusters),
            'duplicates_removed': duplicates_removed,
            'patterns_reinforced': patterns_reinforced,
            'noise_removed': noise_removed,
            'protocol_version': "1.0"
        }
    
    async def _cluster_entries(self, entries: List[MemoryEntry]) -> List[List[MemoryEntry]]:
        """Кластеризация записей по схожести (паттерн из Agent Zero)"""
        if len(entries) < self.cluster_count:
            return [entries]
        
        # Получение эмбеддингов
        embeddings = np.array([entry.embedding for entry in entries])
        
        # K-Means кластеризация
        kmeans = KMeans(n_clusters=self.cluster_count, random_state=42)
        labels = kmeans.fit_predict(embeddings)
        
        # Группировка по кластерам
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(entries[i])
        
        return list(clusters.values())
    
    async def _remove_duplicates(self, clusters: List[List[MemoryEntry]]) -> int:
        """Удаление дубликатов внутри кластеров (паттерн из Agent Zero)"""
        removed_count = 0
        
        for cluster in clusters:
            if len(cluster) > 1:
                # Сортировка по релевантности
                cluster.sort(key=lambda x: x.relevance_score, reverse=True)
                
                # Удаление дубликатов (оставляем только лучший)
                for entry in cluster[1:]:
                    await self.vector_store.delete(entry.id)
                    removed_count += 1
        
        return removed_count
```

---

## 4️⃣ CODE GENERATION (HIGH PRIORITY)

### 4.1 Safe Code Generation Pattern

```python
# agent0ai/code/generator.py → synapse/skills/generator.py
import ast
from typing import Tuple, List

class SafeCodeGenerator:
    """
    Генерация кода с проверкой безопасности.
    Адаптировано из Agent Zero с добавлением AST analysis.
    """
    
    DANGEROUS_IMPORTS = [
        'os', 'sys', 'subprocess', 'multiprocessing',
        'socket', 'http', 'urllib', 'requests'
    ]
    
    DANGEROUS_FUNCTIONS = [
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'getattr', 'setattr'
    ]
    
    def __init__(self, llm_provider, security_manager):
        self.llm = llm_provider
        self.security = security_manager  # 🔹 Наше дополнение
    
    async def generate_skill_code(self, specification: dict) -> Tuple[str, dict]:
        """
        Генерация кода навыка с проверкой безопасности.
        
        🔹 Наше дополнение: AST analysis перед возвратом кода
        """
        # Генерация кода (паттерн из Agent Zero)
        prompt = self._build_generation_prompt(specification)
        code = await self.llm.generate(prompt)
        
        # 🔹 AST анализ безопасности (наше дополнение из spec v3.1)
        security_report = await self._analyze_code_security(code)
        
        if not security_report['safe']:
            # Логирование и отклонение
            await self.security.log_security_event(
                event_type="unsafe_code_generation",
                user_id=specification.get('agent_id'),
                details=security_report
            )
            return None, security_report
        
        return code, security_report
    
    def _analyze_code_security(self, code: str) -> dict:
        """
        AST анализ кода на безопасность.
        🔹 Наше дополнение (не было в Agent Zero)
        """
        issues = []
        
        try:
            tree = ast.parse(code)
            
            # Проверка импортов
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.DANGEROUS_IMPORTS:
                            issues.append(f"Dangerous import: {alias.name}")
                
                if isinstance(node, ast.ImportFrom):
                    if node.module in self.DANGEROUS_IMPORTS:
                        issues.append(f"Dangerous import from: {node.module}")
                
                # Проверка опасных функций
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.DANGEROUS_FUNCTIONS:
                            issues.append(f"Dangerous function: {node.func.id}")
            
            return {
                'safe': len(issues) == 0,
                'issues': issues,
                'protocol_version': "1.0"
            }
            
        except SyntaxError as e:
            return {
                'safe': False,
                'issues': [f"Syntax error: {str(e)}"],
                'protocol_version': "1.0"
            }
```

---

## 5️⃣ PROMPT MANAGEMENT (MEDIUM PRIORITY)

### 5.1 Prompt Versioning

```python
# agent0ai/prompts/manager.py → synapse/llm/prompt_manager.py
from typing import Dict, List
from datetime import datetime

class PromptManager:
    """
    Менеджер промптов с версионированием.
    Адаптировано из Agent Zero с добавлением protocol versioning.
    """
    
    def __init__(self, database):
        self.db = database
        self.prompts: Dict[str, List[dict]] = {}
        self.protocol_version = "1.0"
    
    async def get_prompt(self, name: str, version: str = None) -> str:
        """
        Получение промпта по имени.
        
        🔹 Наше дополнение: Version tracking и protocol_version
        """
        if name not in self.prompts:
            self.prompts[name] = await self.db.get_prompt_versions(name)
        
        if version is None:
            # Последняя версия
            prompt = self.prompts[name][-1]
        else:
            # Конкретная версия
            prompt = next(
                (p for p in self.prompts[name] if p['version'] == version),
                None
            )
        
        if prompt is None:
            raise KeyError(f"Prompt {name}:{version} not found")
        
        # 🔹 Добавление protocol_version в контекст
        prompt_with_version = f"""
        <system_metadata>
        protocol_version: {self.protocol_version}
        prompt_version: {prompt['version']}
        created_at: {prompt['created_at']}
        </system_metadata>
        
        {prompt['content']}
        """
        
        return prompt_with_version
    
    async def update_prompt(self, name: str, content: str,
                            reason: str) -> str:
        """
        Обновление промпта с сохранением истории.
        (паттерн из Agent Zero)
        """
        versions = self.prompts.get(name, [])
        new_version = str(len(versions) + 1)
        
        prompt_record = {
            'version': new_version,
            'content': content,
            'reason': reason,
            'created_at': datetime.utcnow().isoformat(),
            'protocol_version': self.protocol_version  # 🔹 Наше дополнение
        }
        
        await self.db.save_prompt_version(name, prompt_record)
        
        if name not in self.prompts:
            self.prompts[name] = []
        self.prompts[name].append(prompt_record)
        
        return new_version
```

---

## 6️⃣ COGNITIVE LOOP (MEDIUM PRIORITY)

### 6.1 Enhanced Cognitive Loop

```python
# agent0ai/cognitive/loop.py → synapse/core/orchestrator.py
from typing import Optional, List
from core.models import InputEvent, OutputEvent, ActionPlan

class CognitiveLoop:
    """
    Цикл мышления агента.
    Адаптировано из Agent Zero с добавлением freeze и checkpoint.
    """
    
    def __init__(self, orchestrator, memory, security, checkpoint):
        self.orchestrator = orchestrator
        self.memory = memory
        self.security = security
        self.checkpoint = checkpoint  # 🔹 Наше дополнение
        self.protocol_version = "1.0"
    
    async def execute_cycle(self, event: InputEvent) -> OutputEvent:
        """
        Полный цикл мысли агента.
        
        🔹 Наше дополнение: Checkpoint перед рискованными действиями
        """
        
        # 1. PERCEIVE (паттерн из Agent Zero)
        perceived = await self._perceive(event)
        
        # 2. RECALL (паттерн из Agent Zero)
        context = await self.memory.recall(perceived)
        
        # 3. PLAN (паттерн из Agent Zero)
        plan = await self._create_plan(perceived, context)
        
        # 4. 🔹 SECURITY CHECK (наше дополнение из spec v3.1)
        security_result = await self.security.check_plan(plan)
        
        if not security_result.approved:
            if security_result.requires_human_approval:
                approval = await self.security.request_human_approval(plan)
                if not approval.approved:
                    return self._create_denied_output(event)
            else:
                return self._create_denied_output(event)
        
        # 5. 🔹 CHECKPOINT перед выполнением (наше дополнение)
        if plan.risk_level >= 3:
            checkpoint_id = await self.checkpoint.create_checkpoint(
                agent_id=event.agent_id,
                session_id=event.session_id
            )
            plan.checkpoint_id = checkpoint_id
        
        # 6. 🔹 FREEZE плана (наше дополнение из spec v3.1)
        plan.freeze()
        
        # 7. ACT (паттерн из Agent Zero)
        result = await self._execute_plan(plan)
        
        # 8. OBSERVE (паттерн из Agent Zero)
        observation = await self._observe(result)
        
        # 9. EVALUATE (паттерн из Agent Zero)
        evaluation = await self._evaluate(plan, observation)
        
        # 10. LEARN (паттерн из Agent Zero)
        await self._learn(event, plan, result, evaluation)
        
        # 11. Создание OutputEvent
        output = OutputEvent(
            input_event_id=event.id,
            result=result,
            evaluation=evaluation,
            protocol_version=self.protocol_version  # 🔹 Наше дополнение
        )
        
        return output
```

---

## 7️⃣ ЧТО НЕ БРАТЬ ИЗ AGENT ZERO

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет isolation policy | Нет enforcement | IsolationEnforcementPolicy class |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Нет checkpoint/rollback | Нет recovery | RollbackManager с is_fresh() |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |
| Нет deterministic seeds | Нет воспроизводимости | execution_seed в контексте |
| Простой fallback LLM | Нет health checks | LLMFailureStrategy с priority |

---

## 8️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Learning Engine (Неделя 7-9)

| Задача | Файл Agent Zero | Файл Synapse | Статус |
|--------|----------------|--------------|--------|
| Learning Loop | `learning/loop.py` | `synapse/learning/engine.py` | ⏳ Ожидает |
| Memory Consolidation | `memory/consolidation.py` | `synapse/memory/consolidator.py` | ⏳ Ожидает |
| Pattern Extraction | `learning/patterns.py` | `synapse/learning/patterns.py` | ⏳ Ожидает |

### Фаза 2: Agent Hierarchy (Неделя 4-6)

| Задача | Файл Agent Zero | Файл Synapse | Статус |
|--------|----------------|--------------|--------|
| Developer Agent | `agents/developer.py` | `synapse/agents/developer.py` | ⏳ Ожидает |
| Critic Agent | `agents/critic.py` | `synapse/agents/critic.py` | ⏳ Ожидает |
| Agent Communication | `agents/communication.py` | `synapse/core/protocol.py` | ⏳ Ожидает |

### Фаза 3: Self-Evolution (Неделя 7-9)

| Задача | Файл Agent Zero | Файл Synapse | Статус |
|--------|----------------|--------------|--------|
| Skill Generator | `skills/generator.py` | `synapse/skills/generator.py` | ⏳ Ожидает |
| Lifecycle Manager | `skills/lifecycle.py` | `synapse/skills/lifecycle.py` | ⏳ Ожидает |
| Code Security | `code/security.py` | `synapse/security/code_scan.py` | ⏳ Ожидает |

### Фаза 4: Cognitive Loop (Неделя 3-4)

| Задача | Файл Agent Zero | Файл Synapse | Статус |
|--------|----------------|--------------|--------|
| Cognitive Loop | `cognitive/loop.py` | `synapse/core/orchestrator.py` | ⏳ Ожидает |
| Prompt Manager | `prompts/manager.py` | `synapse/llm/prompt_manager.py` | ⏳ Ожидает |

---

## 9️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить agent0ai/agents/ для паттернов иерархии агентов
□ Изучить agent0ai/learning/ для паттернов обучения
□ Изучить agent0ai/skills/ для паттернов генерации навыков
□ Изучить agent0ai/cognitive/ для паттернов cognitive loop
□ Изучить agent0ai/prompts/ для паттернов управления промптами

□ НЕ брать security model (у нас capability-based)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)
□ НЕ брать resource management (у нас ResourceLimits schema)

□ Адаптировать learning loop с checkpoint integration
□ Адаптировать agent hierarchy с Guardian role
□ Адаптировать code generation с AST security analysis
□ Адаптировать prompt management с versioning
□ Адаптировать cognitive loop с freeze mechanism

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 🔟 СРАВНЕНИЕ: OPENCLAW vs AGENT ZERO vs SYNAPSE

| Область | OpenClaw | Agent Zero | Synapse |
|---------|----------|------------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (адаптировано из OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (адаптировано из Agent Zero) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Deployment | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (адаптировано из OpenClaw) |
| Memory | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (адаптировано из обоих) |
| Protocol Versioning | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ✅ (оригинальное) |
| Resource Accounting | ❌ | ❌ | ✅ (оригинальное) |

---

## 1️⃣1️⃣ ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 11.1 Agent Zero License

```
Agent Zero License: MIT
Repository: https://github.com/agent0ai/agent-zero

При заимствовании кода необходимо:
1. Сохранить оригинальный copyright notice
2. Указать ссылку на оригинальный репозиторий
3. Добавить заметку об адаптации в docstring
```

### 11.2 Формат Атрибуции

```python
# synapse/agents/developer.py
"""
Developer Agent для Synapse.

Адаптировано из Agent Zero:
https://github.com/agent0ai/agent-zero/tree/main/agents/developer.py

Оригинальная лицензия: MIT
Адаптация: Добавлен security layer, AST analysis, protocol versioning,
           checkpoint integration, isolation enforcement

Copyright (c) 2024 Agent Zero Contributors
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
**Agent Zero Repository:** https://github.com/agent0ai/agent-zero

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md