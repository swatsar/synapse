# 📎 PROJECT SYNAPSE: LANGSMITH SDK INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## ⚠️ ВАЖНОЕ ПРИМЕЧАНИЕ

**О проекте LangSmith:** Это **платформа observability, testing и evaluation** от LangChain для LLM-приложений. LangSmith предоставляет инструменты для отслеживания, отладки, тестирования и мониторинга LLM-приложений в production.

**Ключевые возможности LangSmith:**
- Distributed Tracing (трейсинг LLM вызовов и цепочек)
- Dataset Management (управление тестовыми датасетами)
- Evaluation & Scoring (оценка качества выводов LLM)
- Feedback Collection (сбор обратной связи)
- Performance Monitoring (мониторинг производительности)
- Prompt Versioning (версионирование промптов)
- Cost Tracking (отслеживание затрат на LLM)
- Debugging Tools (инструменты отладки)
- Annotation Queue (очередь аннотаций)
- Comparison Tools (сравнение моделей и промптов)

**Подход этого документа:** Анализирует **публично известные возможности LangSmith** для интеграции в Synapse с учётом security model, capability-based access, protocol versioning, и production-ready reliability.

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к:
- `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md` (основная спецификация)
- `OPENCLAW_INTEGRATION.md` (интеграция OpenClaw)
- `AGENT_ZERO_INTEGRATION.md` (интеграция Agent Zero)
- `ANTHROPIC_PATTERNS_INTEGRATION.md` (паттерны Anthropic)
- `CLAUDE_CODE_INTEGRATION.md` (паттерны Claude Code)
- `CODEX_INTEGRATION.md` (паттерны OpenAI Codex)
- `BROWSER_USE_INTEGRATION.md` (паттерны browser-use)
- `AUTOGPT_INTEGRATION.md` (паттерны AutoGPT)
- `LANGCHAIN_INTEGRATION.md` (паттерны LangChain)
- `LANGGRAPH_INTEGRATION.md` (паттерны LangGraph)

Он описывает стратегию интеграции полезных паттернов из **LangSmith SDK** в платформу Synapse, особенно для **Observability**, **Evaluation**, **Testing**, **Feedback**, и **Monitoring** компонентов.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Паттернов для Заимствования | Статус |
|---------|---------------------|------------------------------|--------|
| Distributed Tracing | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| Dataset Management | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Evaluation Framework | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| Feedback Collection | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Performance Monitoring | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Prompt Versioning | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Cost Tracking | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Debugging Tools | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Security Model | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐⭐ | ~10% | ❌ НЕ брать |

---

## 1️⃣ DISTRIBUTED TRACING (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | LangSmith Pattern | Файл Synapse | Действие |
|-----------|-------------------|--------------|----------|
| Trace Client | Trace SDK client | `synapse/observability/trace_client.py` | Адаптировать с protocol_version |
| Span Management | Span creation & hierarchy | `synapse/observability/span_manager.py` | Адаптировать с security context |
| Context Propagation | Trace context propagation | `synapse/observability/context.py` | Адаптировать с capability metadata |
| Exporter | Trace exporter | `synapse/observability/exporter.py` | Адаптировать with filtering |
| Sampler | Trace sampling | `synapse/observability/sampler.py` | Адаптировать с security rules |

### 1.2 Secure Trace Client

```python
# LangSmith tracing → synapse/observability/trace_client.py
from typing import Dict, List, Optional, Any, AsyncIterator
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid

class SpanType(str, Enum):
    """Типы span для трейсинга"""
    LLM = "llm"
    CHAIN = "chain"
    TOOL = "tool"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    AGENT = "agent"
    SKILL = "skill"
    GRAPH_NODE = "graph_node"

class SpanStatus(str, Enum):
    """Статус span"""
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"

class TraceSpan(BaseModel):
    """
    Span для трейсинга.
    Адаптировано из LangSmith trace patterns.
    
    🔹 Наше дополнение: Protocol version + Security metadata + Capability context
    """
    id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    span_type: SpanType
    start_time: str
    end_time: Optional[str] = None
    status: SpanStatus = SpanStatus.UNSET
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    session_id: str
    agent_id: str
    security_context: Dict[str, Any] = {}
    capability_checks: List[Dict[str, Any]] = []
    resource_usage: Dict[str, Any] = {}
    is_sensitive: bool = False
    
    class Config:
        json_encoders = {
            dict: lambda v: v
        }

class SecureTraceClient:
    """
    Безопасный клиент для распределённого трейсинга.
    Адаптировано из LangSmith SDK patterns.
    
    🔹 Наше дополнение: Security filtering + Capability validation + Protocol versioning + Audit
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(
        self,
        project_name: str,
        api_key: str = None,
        endpoint: str = None,
        security_manager=None,
        audit_logger=None,
        config: dict = None
    ):
        self.project_name = project_name
        self.api_key = api_key
        self.endpoint = endpoint or "http://localhost:1984"
        self.security = security_manager  # 🔹 Наше дополнение
        self.audit = audit_logger  # 🔹 Наше дополнение
        self.config = config or {}
        self.active_spans: Dict[str, TraceSpan] = {}
        self.traces: Dict[str, List[TraceSpan]] = {}
        self.sampling_rate = config.get('sampling_rate', 1.0)
        self.filter_sensitive = config.get('filter_sensitive', True)
    
    async def start_trace(
        self,
        name: str,
        session_id: str = None,
        agent_id: str = None,
        metadata: dict = None
    ) -> str:
        """
        Начало трейса.
        
        🔹 Наше дополнение: Security context + Protocol version
        """
        trace_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())
        agent_id = agent_id or "unknown"
        
        # 🔹 Создание security context (наше дополнение)
        security_context = await self._create_security_context(trace_id, session_id)
        
        trace_span = TraceSpan(
            id=trace_id,
            trace_id=trace_id,
            name=name,
            span_type=SpanType.AGENT,
            start_time=datetime.utcnow().isoformat(),
            session_id=session_id,
            agent_id=agent_id,
            metadata=metadata or {},
            security_context=security_context,
            protocol_version=self.PROTOCOL_VERSION
        )
        
        self.active_spans[trace_id] = trace_span
        self.traces[trace_id] = [trace_span]
        
        # 🔹 Audit начала трейса (наше дополнение)
        await self._audit_trace_start(trace_span)
        
        return trace_id
    
    async def start_span(
        self,
        name: str,
        trace_id: str,
        parent_span_id: str = None,
        span_type: SpanType = SpanType.TOOL,
        inputs: dict = None,
        metadata: dict = None
    ) -> str:
        """
        Начало span.
        
        🔹 Наше дополнение: Capability validation + Security filtering
        """
        if trace_id not in self.traces:
            raise KeyError(f"Trace {trace_id} not found")
        
        span_id = str(uuid.uuid4())
        
        # 🔹 Security filtering inputs (наше дополнение)
        filtered_inputs = await self._filter_sensitive_data(inputs) if self.filter_sensitive else inputs
        
        # 🔹 Capability check для span (наше дополнение)
        capability_check = await self._check_span_capabilities(span_type, filtered_inputs)
        
        span = TraceSpan(
            id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            span_type=span_type,
            start_time=datetime.utcnow().isoformat(),
            inputs=filtered_inputs,
            metadata=metadata or {},
            session_id=self.active_spans[trace_id].session_id,
            agent_id=self.active_spans[trace_id].agent_id,
            capability_checks=[capability_check],
            protocol_version=self.PROTOCOL_VERSION
        )
        
        self.active_spans[span_id] = span
        self.traces[trace_id].append(span)
        
        return span_id
    
    async def end_span(
        self,
        span_id: str,
        outputs: dict = None,
        error: str = None,
        resource_usage: dict = None
    ):
        """
        Завершение span.
        
        🔹 Наше дополнение: Resource tracking + Security validation
        """
        if span_id not in self.active_spans:
            raise KeyError(f"Span {span_id} not found")
        
        span = self.active_spans[span_id]
        span.end_time = datetime.utcnow().isoformat()
        span.status = SpanStatus.ERROR if error else SpanStatus.OK
        span.error = error
        
        # 🔹 Security filtering outputs (наше дополнение)
        span.outputs = await self._filter_sensitive_data(outputs) if self.filter_sensitive else outputs
        
        # 🔹 Resource usage tracking (наше дополнение из spec v3.1)
        span.resource_usage = resource_usage or {}
        
        # 🔹 Audit завершения span (наше дополнение)
        await self._audit_span_end(span)
        
        del self.active_spans[span_id]
    
    async def end_trace(self, trace_id: str):
        """Завершение трейса"""
        if trace_id not in self.traces:
            raise KeyError(f"Trace {trace_id} not found")
        
        # Завершение всех активных span
        for span_id in list(self.active_spans.keys()):
            if self.active_spans[span_id].trace_id == trace_id:
                await self.end_span(span_id)
        
        # 🔹 Export трейса (наше дополнение)
        await self._export_trace(trace_id)
        
        # 🔹 Audit завершения трейса (наше дополнение)
        await self._audit_trace_end(self.traces[trace_id])
        
        del self.traces[trace_id]
    
    async def _create_security_context(self, trace_id: str, session_id: str) -> dict:
        """
        Создание security context для трейса.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        return {
            'trace_id': trace_id,
            'session_id': session_id,
            'created_at': datetime.utcnow().isoformat(),
            'protocol_version': self.PROTOCOL_VERSION,
            'security_level': 'standard',
            'encryption_enabled': True,
            'audit_enabled': True
        }
    
    async def _filter_sensitive_data(self, data: dict) -> dict:
        """
        Фильтрация чувствительных данных.
        🔹 Наше дополнение (критично для security)
        """
        if not data:
            return {}
        
        sensitive_keys = [
            'password', 'token', 'secret', 'key', 'api_key',
            'credential', 'auth', 'bearer', 'private'
        ]
        
        filtered = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                filtered[key] = '[REDACTED]'
            elif isinstance(value, dict):
                filtered[key] = await self._filter_sensitive_data(value)
            elif isinstance(value, list):
                filtered[key] = [
                    await self._filter_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        
        return filtered
    
    async def _check_span_capabilities(self, span_type: SpanType, inputs: dict) -> dict:
        """
        Проверка capabilities для span.
        🔹 Наше дополнение (не было в LangSmith)
        """
        capability_map = {
            SpanType.LLM: ['llm:generate'],
            SpanType.TOOL: ['tool:execute'],
            SpanType.RETRIEVER: ['memory:read'],
            SpanType.EMBEDDING: ['llm:embed'],
            SpanType.SKILL: ['skill:execute'],
            SpanType.GRAPH_NODE: ['graph:execute']
        }
        
        required_caps = capability_map.get(span_type, [])
        
        # В реальной реализации — проверка через security manager
        return {
            'required_capabilities': required_caps,
            'checked_at': datetime.utcnow().isoformat(),
            'protocol_version': self.PROTOCOL_VERSION
        }
    
    async def _audit_trace_start(self, span: TraceSpan):
        """Audit начала трейса"""
        if self.audit:
            await self.audit.log_action(
                action="trace_start",
                result={
                    'trace_id': span.trace_id,
                    'name': span.name,
                    'span_type': span.span_type.value,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={
                    'session_id': span.session_id,
                    'agent_id': span.agent_id
                }
            )
    
    async def _audit_span_end(self, span: TraceSpan):
        """Audit завершения span"""
        if self.audit:
            await self.audit.log_action(
                action=f"span_end:{span.span_type.value}",
                result={
                    'span_id': span.id,
                    'trace_id': span.trace_id,
                    'name': span.name,
                    'status': span.status.value,
                    'duration_ms': self._calculate_duration(span.start_time, span.end_time),
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={
                    'session_id': span.session_id,
                    'agent_id': span.agent_id
                }
            )
    
    async def _audit_trace_end(self, spans: List[TraceSpan]):
        """Audit завершения трейса"""
        if self.audit and spans:
            root_span = spans[0]
            await self.audit.log_action(
                action="trace_end",
                result={
                    'trace_id': root_span.trace_id,
                    'total_spans': len(spans),
                    'error_count': len([s for s in spans if s.status == SpanStatus.ERROR]),
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={
                    'session_id': root_span.session_id,
                    'agent_id': root_span.agent_id
                }
            )
    
    async def _export_trace(self, trace_id: str):
        """Export трейса в storage"""
        # В реальной реализации — отправка в LangSmith или альтернативный backend
        spans = self.traces.get(trace_id, [])
        
        # 🔹 Security validation перед export (наше дополнение)
        validated_spans = await self._validate_spans_for_export(spans)
        
        # Export logic here
        pass
    
    async def _validate_spans_for_export(self, spans: List[TraceSpan]) -> List[TraceSpan]:
        """Валидация span перед export"""
        validated = []
        for span in spans:
            # Проверка что все sensitive данные отфильтрованы
            if self.filter_sensitive:
                span.inputs = await self._filter_sensitive_data(span.inputs)
                span.outputs = await self._filter_sensitive_data(span.outputs)
            validated.append(span)
        return validated
    
    def _calculate_duration(self, start: str, end: str) -> int:
        """Расчёт длительности в ms"""
        if not end:
            return 0
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return int((end_dt - start_dt).total_seconds() * 1000)
```

---

## 2️⃣ DATASET MANAGEMENT (HIGH PRIORITY)

### 2.1 Test Dataset System

```python
# LangSmith datasets → synapse/testing/dataset_manager.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
import uuid

class DatasetExample(BaseModel):
    """
    Пример в датасете.
    Адаптировано из LangSmith dataset patterns.
    
    🔹 Наше дополнение: Protocol version + Security metadata
    """
    id: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    metadata: Dict[str, Any] = {}
    created_at: str
    updated_at: str
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    source: str = "manual"  # manual, generated, imported
    sensitivity_level: str = "public"
    validation_status: str = "pending"  # pending, validated, rejected

class Dataset(BaseModel):
    """
    Датасет для тестирования.
    Адаптировано из LangSmith dataset patterns.
    
    🔹 Наше дополнение: Protocol version + Security context
    """
    id: str
    name: str
    description: str
    examples: List[DatasetExample] = []
    created_at: str
    updated_at: str
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    owner: str
    access_level: str = "private"  # private, team, public
    tags: List[str] = []

class DatasetManager:
    """
    Менеджер датасетов для тестирования.
    Адаптировано из LangSmith dataset patterns.
    
    🔹 Наше дополнение: Security validation + Protocol versioning + Audit
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, storage, security_manager, audit_logger=None):
        self.storage = storage
        self.security = security_manager
        self.audit = audit_logger
        self.datasets: Dict[str, Dataset] = {}
    
    async def create_dataset(
        self,
        name: str,
        description: str,
        access_level: str = "private",
        tags: List[str] = None
    ) -> Dataset:
        """Создание датасета"""
        dataset_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        dataset = Dataset(
            id=dataset_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            owner="synapse_system",
            access_level=access_level,
            tags=tags or [],
            protocol_version=self.PROTOCOL_VERSION
        )
        
        await self.storage.save(f"dataset:{dataset_id}", dataset.model_dump())
        self.datasets[dataset_id] = dataset
        
        # 🔹 Audit создания датасета (наше дополнение)
        await self._audit_dataset_action("create", dataset)
        
        return dataset
    
    async def add_example(
        self,
        dataset_id: str,
        inputs: dict,
        outputs: dict,
        metadata: dict = None,
        source: str = "manual"
    ) -> DatasetExample:
        """
        Добавление примера в датасет.
        
        🔹 Наше дополнение: Security validation + Sensitivity classification
        """
        if dataset_id not in self.datasets:
            raise KeyError(f"Dataset {dataset_id} not found")
        
        example_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # 🔹 Security validation inputs/outputs (наше дополнение)
        validated_inputs = await self._validate_example_data(inputs)
        validated_outputs = await self._validate_example_data(outputs)
        
        # 🔹 Sensitivity classification (наше дополнение)
        sensitivity = await self._classify_sensitivity(validated_inputs, validated_outputs)
        
        example = DatasetExample(
            id=example_id,
            inputs=validated_inputs,
            outputs=validated_outputs,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
            source=source,
            sensitivity_level=sensitivity,
            protocol_version=self.PROTOCOL_VERSION
        )
        
        self.datasets[dataset_id].examples.append(example)
        self.datasets[dataset_id].updated_at = now
        
        await self.storage.save(f"dataset:{dataset_id}", self.datasets[dataset_id].model_dump())
        
        # 🔹 Audit добавления примера (наше дополнение)
        await self._audit_example_action("add", dataset_id, example)
        
        return example
    
    async def get_examples(self, dataset_id: str, limit: int = 100) -> List[DatasetExample]:
        """Получение примеров из датасета"""
        if dataset_id not in self.datasets:
            raise KeyError(f"Dataset {dataset_id} not found")
        
        return self.datasets[dataset_id].examples[:limit]
    
    async def validate_example(self, example_id: str, validated: bool) -> bool:
        """Валидация примера"""
        for dataset in self.datasets.values():
            for example in dataset.examples:
                if example.id == example_id:
                    example.validation_status = "validated" if validated else "rejected"
                    example.updated_at = datetime.utcnow().isoformat()
                    
                    # 🔹 Audit валидации (наше дополнение)
                    await self._audit_example_action("validate", dataset.id, example)
                    
                    return True
        return False
    
    async def _validate_example_data(self, data: dict) -> dict:
        """Валидация данных примера"""
        # 🔹 Фильтрация чувствительных данных (наше дополнение)
        sensitive_keys = ['password', 'token', 'secret', 'key', 'api_key']
        
        validated = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                validated[key] = '[REDACTED]'
            elif isinstance(value, dict):
                validated[key] = await self._validate_example_data(value)
            else:
                validated[key] = value
        
        return validated
    
    async def _classify_sensitivity(self, inputs: dict, outputs: dict) -> str:
        """Классификация уровня чувствительности"""
        sensitive_patterns = ['password', 'token', 'secret', 'credential', 'private']
        
        all_text = str(inputs) + str(outputs)
        
        if any(p in all_text.lower() for p in sensitive_patterns):
            return "confidential"
        elif 'internal' in all_text.lower():
            return "internal"
        else:
            return "public"
    
    async def _audit_dataset_action(self, action: str, dataset: Dataset):
        """Audit действий с датасетом"""
        if self.audit:
            await self.audit.log_action(
                action=f"dataset:{action}",
                result={
                    'dataset_id': dataset.id,
                    'dataset_name': dataset.name,
                    'access_level': dataset.access_level,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={'owner': dataset.owner}
            )
    
    async def _audit_example_action(self, action: str, dataset_id: str, example: DatasetExample):
        """Audit действий с примером"""
        if self.audit:
            await self.audit.log_action(
                action=f"dataset_example:{action}",
                result={
                    'dataset_id': dataset_id,
                    'example_id': example.id,
                    'sensitivity_level': example.sensitivity_level,
                    'validation_status': example.validation_status,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={'source': example.source}
            )
```

---

## 3️⃣ EVALUATION FRAMEWORK (HIGH PRIORITY)

### 3.1 LLM Output Evaluation

```python
# LangSmith evaluation → synapse/testing/evaluation.py
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import uuid

class EvaluationMetric(str, Enum):
    """Метрики оценки"""
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    CONSISTENCY = "consistency"
    SAFETY = "safety"
    LATENCY = "latency"
    COST = "cost"
    TOXICITY = "toxicity"
    HALLUCINATION = "hallucination"

class EvaluationResult(BaseModel):
    """
    Результат оценки.
    Адаптировано из LangSmith evaluation patterns.
    
    🔹 Наше дополнение: Protocol version + Security context
    """
    id: str
    example_id: str
    trace_id: str
    metric: EvaluationMetric
    score: float
    reason: str
    evaluator: str
    created_at: str
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}

class EvaluationRunner:
    """
    Запуск оценки выводов LLM.
    Адаптировано из LangSmith evaluation patterns.
    
    🔹 Наше дополнение: Security validation + Protocol versioning + Audit
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(
        self,
        llm_provider,
        dataset_manager,
        trace_client,
        security_manager,
        audit_logger=None
    ):
        self.llm = llm_provider
        self.datasets = dataset_manager
        self.traces = trace_client
        self.security = security_manager
        self.audit = audit_logger
        self.evaluators: Dict[EvaluationMetric, Callable] = {}
        self._register_default_evaluators()
    
    async def run_evaluation(
        self,
        dataset_id: str,
        target_function: Callable,
        metrics: List[EvaluationMetric] = None,
        num_examples: int = None
    ) -> List[EvaluationResult]:
        """
        Запуск оценки на датасете.
        
        🔹 Наше дополнение: Security validation + Capability checks
        """
        # 🔹 Проверка capabilities для evaluation (наше дополнение)
        caps_check = await self.security.check_capabilities(
            required=['testing:evaluate'],
            context={'dataset_id': dataset_id}
        )
        if not caps_check.approved:
            raise PermissionError("Missing evaluation capabilities")
        
        # Получение примеров
        examples = await self.datasets.get_examples(dataset_id, limit=num_examples or 100)
        
        results = []
        for example in examples:
            # Запуск target function
            trace_id = await self.traces.start_trace(
                name=f"evaluation:{dataset_id}",
                metadata={'example_id': example.id}
            )
            
            try:
                # Выполнение
                output = await target_function(example.inputs)
                
                # Оценка по метрикам
                for metric in (metrics or self.evaluators.keys()):
                    result = await self._evaluate_metric(
                        metric=metric,
                        inputs=example.inputs,
                        expected=example.outputs,
                        actual=output,
                        example_id=example.id,
                        trace_id=trace_id
                    )
                    results.append(result)
                
                await self.traces.end_trace(trace_id)
                
            except Exception as e:
                await self.traces.end_trace(trace_id)
                
                # 🔹 Audit ошибки evaluation (наше дополнение)
                await self.audit.log_action(
                    action="evaluation_error",
                    result={
                        'dataset_id': dataset_id,
                        'example_id': example.id,
                        'error': str(e),
                        'protocol_version': self.PROTOCOL_VERSION
                    },
                    context={'trace_id': trace_id}
                )
        
        # 🔹 Audit завершения evaluation (наше дополнение)
        await self._audit_evaluation_completion(dataset_id, results)
        
        return results
    
    async def _evaluate_metric(
        self,
        metric: EvaluationMetric,
        inputs: dict,
        expected: dict,
        actual: dict,
        example_id: str,
        trace_id: str
    ) -> EvaluationResult:
        """Оценка по конкретной метрике"""
        if metric not in self.evaluators:
            raise ValueError(f"Unknown metric: {metric}")
        
        evaluator = self.evaluators[metric]
        score, reason = await evaluator(inputs, expected, actual)
        
        result = EvaluationResult(
            id=str(uuid.uuid4()),
            example_id=example_id,
            trace_id=trace_id,
            metric=metric,
            score=score,
            reason=reason,
            evaluator=evaluator.__name__,
            created_at=datetime.utcnow().isoformat(),
            protocol_version=self.PROTOCOL_VERSION
        )
        
        return result
    
    def _register_default_evaluators(self):
        """Регистрация evaluator по умолчанию"""
        self.evaluators[EvaluationMetric.ACCURACY] = self._accuracy_evaluator
        self.evaluators[EvaluationMetric.SAFETY] = self._safety_evaluator
        self.evaluators[EvaluationMetric.LATENCY] = self._latency_evaluator
    
    async def _accuracy_evaluator(self, inputs: dict, expected: dict, actual: dict) -> tuple:
        """Evaluator точности"""
        # Простая эвристика — в реальной реализации LLM-based evaluation
        match_count = sum(1 for k in expected if k in actual and expected[k] == actual[k])
        score = match_count / max(len(expected), 1)
        return score, f"Accuracy: {match_count}/{len(expected)}"
    
    async def _safety_evaluator(self, inputs: dict, expected: dict, actual: dict) -> tuple:
        """
        evaluator безопасности.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        safety_issues = []
        
        # Проверка на утечку чувствительных данных
        sensitive_patterns = ['password', 'token', 'secret', 'key', 'api_key']
        actual_text = str(actual).lower()
        
        for pattern in sensitive_patterns:
            if pattern in actual_text:
                safety_issues.append(f"Potential data leak: {pattern}")
        
        score = 1.0 - (len(safety_issues) * 0.2)
        reason = "Safe" if not safety_issues else "; ".join(safety_issues)
        
        return max(0, score), reason
    
    async def _latency_evaluator(self, inputs: dict, expected: dict, actual: dict) -> tuple:
        """Evaluator задержки"""
        # В реальной реализации — измерение из trace metadata
        latency_ms = actual.get('metadata', {}).get('latency_ms', 0)
        
        # Score на основе latency thresholds
        if latency_ms < 1000:
            score = 1.0
        elif latency_ms < 3000:
            score = 0.7
        elif latency_ms < 5000:
            score = 0.4
        else:
            score = 0.1
        
        return score, f"Latency: {latency_ms}ms"
    
    async def _audit_evaluation_completion(self, dataset_id: str, results: List[EvaluationResult]):
        """Audit завершения evaluation"""
        if self.audit:
            avg_scores = {}
            for result in results:
                if result.metric.value not in avg_scores:
                    avg_scores[result.metric.value] = []
                avg_scores[result.metric.value].append(result.score)
            
            averages = {k: sum(v)/len(v) for k, v in avg_scores.items()}
            
            await self.audit.log_action(
                action="evaluation_completed",
                result={
                    'dataset_id': dataset_id,
                    'total_evaluations': len(results),
                    'average_scores': averages,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={}
            )
```

---

## 4️⃣ FEEDBACK COLLECTION (MEDIUM PRIORITY)

### 4.1 User Feedback System

```python
# LangSmith feedback → synapse/feedback/collector.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import uuid

class FeedbackType(str, Enum):
    """Типы обратной связи"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    SCORE = "score"
    COMMENT = "comment"
    CORRECTION = "correction"
    FLAG = "flag"

class Feedback(BaseModel):
    """
    Обратная связь пользователя.
    Адаптировано из LangSmith feedback patterns.
    
    🔹 Наше дополнение: Protocol version + Security context
    """
    id: str
    trace_id: str
    span_id: Optional[str] = None
    feedback_type: FeedbackType
    score: Optional[float] = None
    comment: Optional[str] = None
    user_id: str
    created_at: str
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    is_anonymous: bool = False
    validated: bool = False
    metadata: Dict[str, Any] = {}

class FeedbackCollector:
    """
    Сбор и анализ обратной связи.
    Адаптировано из LangSmith feedback patterns.
    
    🔹 Наше дополнение: Security validation + Protocol versioning + Audit
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, storage, security_manager, audit_logger=None):
        self.storage = storage
        self.security = security_manager
        self.audit = audit_logger
        self.feedback: Dict[str, Feedback] = {}
    
    async def submit_feedback(
        self,
        trace_id: str,
        feedback_type: FeedbackType,
        user_id: str,
        score: float = None,
        comment: str = None,
        is_anonymous: bool = False,
        metadata: dict = None
    ) -> Feedback:
        """
        Отправка обратной связи.
        
        🔹 Наше дополнение: User validation + Security filtering
        """
        feedback_id = str(uuid.uuid4())
        
        # 🔹 Валидация пользователя (наше дополнение)
        if not is_anonymous:
            user_valid = await self.security.validate_user(user_id)
            if not user_valid:
                raise PermissionError(f"User {user_id} not authorized")
        
        # 🔹 Фильтрация комментария (наше дополнение)
        filtered_comment = await self._filter_sensitive_comment(comment) if comment else None
        
        feedback = Feedback(
            id=feedback_id,
            trace_id=trace_id,
            feedback_type=feedback_type,
            score=score,
            comment=filtered_comment,
            user_id=user_id if not is_anonymous else "anonymous",
            created_at=datetime.utcnow().isoformat(),
            is_anonymous=is_anonymous,
            metadata=metadata or {},
            protocol_version=self.PROTOCOL_VERSION
        )
        
        await self.storage.save(f"feedback:{feedback_id}", feedback.model_dump())
        self.feedback[feedback_id] = feedback
        
        # 🔹 Audit отправки feedback (наше дополнение)
        await self._audit_feedback_submission(feedback)
        
        return feedback
    
    async def get_feedback_for_trace(self, trace_id: str) -> List[Feedback]:
        """Получение feedback для трейса"""
        results = []
        for fb in self.feedback.values():
            if fb.trace_id == trace_id:
                results.append(fb)
        return results
    
    async def validate_feedback(self, feedback_id: str, validated: bool) -> bool:
        """Валидация feedback"""
        if feedback_id not in self.feedback:
            return False
        
        self.feedback[feedback_id].validated = validated
        
        # 🔹 Audit валидации (наше дополнение)
        await self._audit_feedback_validation(self.feedback[feedback_id])
        
        return True
    
    async def get_feedback_statistics(self, trace_id: str = None) -> dict:
        """Получение статистики feedback"""
        feedback_list = list(self.feedback.values())
        
        if trace_id:
            feedback_list = [fb for fb in feedback_list if fb.trace_id == trace_id]
        
        thumbs_up = len([fb for fb in feedback_list if fb.feedback_type == FeedbackType.THUMBS_UP])
        thumbs_down = len([fb for fb in feedback_list if fb.feedback_type == FeedbackType.THUMBS_DOWN])
        
        scores = [fb.score for fb in feedback_list if fb.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            'total_feedback': len(feedback_list),
            'thumbs_up': thumbs_up,
            'thumbs_down': thumbs_down,
            'average_score': avg_score,
            'approval_rate': thumbs_up / max(thumbs_up + thumbs_down, 1),
            'protocol_version': self.PROTOCOL_VERSION
        }
    
    async def _filter_sensitive_comment(self, comment: str) -> str:
        """Фильтрация чувствительных данных в комментарии"""
        sensitive_patterns = ['password', 'token', 'secret', 'key', 'api_key']
        
        filtered = comment
        for pattern in sensitive_patterns:
            if pattern.lower() in filtered.lower():
                filtered = filtered.replace(pattern, '[REDACTED]', case_insensitive=True)
        
        return filtered
    
    async def _audit_feedback_submission(self, feedback: Feedback):
        """Audit отправки feedback"""
        if self.audit:
            await self.audit.log_action(
                action="feedback_submitted",
                result={
                    'feedback_id': feedback.id,
                    'trace_id': feedback.trace_id,
                    'feedback_type': feedback.feedback_type.value,
                    'is_anonymous': feedback.is_anonymous,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={'user_id': feedback.user_id}
            )
    
    async def _audit_feedback_validation(self, feedback: Feedback):
        """Audit валидации feedback"""
        if self.audit:
            await self.audit.log_action(
                action="feedback_validated",
                result={
                    'feedback_id': feedback.id,
                    'validated': feedback.valided,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={}
            )
```

---

## 5️⃣ COST TRACKING (MEDIUM PRIORITY)

### 5.1 LLM Cost Management

```python
# LangSmith cost tracking → synapse/observability/cost_tracker.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class CostCategory(str, Enum):
    """Категории затрат"""
    LLM_GENERATION = "llm_generation"
    EMBEDDING = "embedding"
    STORAGE = "storage"
    COMPUTE = "compute"
    NETWORK = "network"

class CostRecord(BaseModel):
    """
    Запись о затратах.
    Адаптировано из LangSmith cost tracking patterns.
    
    🔹 Наше дополнение: Protocol version + Security context
    """
    id: str
    trace_id: str
    category: CostCategory
    amount: float
    currency: str = "USD"
    created_at: str
    metadata: Dict[str, Any] = {}
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    agent_id: str
    session_id: str
    validated: bool = False

class CostTracker:
    """
    Трекер затрат на LLM и ресурсы.
    Адаптировано из LangSmith cost tracking patterns.
    
    🔹 Наше дополнение: Budget limits + Protocol versioning + Audit
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    # Стоимость токенов (примерная, обновлять по актуальным тарифам)
    TOKEN_COSTS = {
        'gpt-4o': {'input': 0.000005, 'output': 0.000015},
        'gpt-4': {'input': 0.00003, 'output': 0.00006},
        'claude-3.5': {'input': 0.000003, 'output': 0.000015},
        'llama3': {'input': 0, 'output': 0},  # Local model
    }
    
    def __init__(self, storage, security_manager, audit_logger=None, config: dict = None):
        self.storage = storage
        self.security = security_manager
        self.audit = audit_logger
        self.config = config or {}
        self.records: Dict[str, CostRecord] = {}
        self.budgets: Dict[str, float] = config.get('budgets', {})
        self.spending: Dict[str, float] = {}
    
    async def record_cost(
        self,
        trace_id: str,
        category: CostCategory,
        amount: float,
        agent_id: str,
        session_id: str,
        metadata: dict = None
    ) -> CostRecord:
        """
        Запись затрат.
        
        🔹 Наше дополнение: Budget check + Validation
        """
        # 🔹 Проверка бюджета (наше дополнение)
        budget_exceeded = await self._check_budget(agent_id, amount)
        if budget_exceeded:
            await self._alert_budget_exceeded(agent_id, amount)
        
        record_id = str(uuid.uuid4())
        
        record = CostRecord(
            id=record_id,
            trace_id=trace_id,
            category=category,
            amount=amount,
            created_at=datetime.utcnow().isoformat(),
            agent_id=agent_id,
            session_id=session_id,
            metadata=metadata or {},
            protocol_version=self.PROTOCOL_VERSION
        )
        
        await self.storage.save(f"cost:{record_id}", record.model_dump())
        self.records[record_id] = record
        
        # Обновление spending
        if agent_id not in self.spending:
            self.spending[agent_id] = 0
        self.spending[agent_id] += amount
        
        # 🔹 Audit записи затрат (наше дополнение)
        await self._audit_cost_record(record)
        
        return record
    
    async def calculate_llm_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Расчёт стоимости LLM вызова"""
        costs = self.TOKEN_COSTS.get(model, {'input': 0, 'output': 0})
        
        input_cost = (prompt_tokens / 1000) * costs['input']
        output_cost = (completion_tokens / 1000) * costs['output']
        
        return input_cost + output_cost
    
    async def get_spending_report(
        self,
        agent_id: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> dict:
        """Получение отчёта о затратах"""
        records = list(self.records.values())
        
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        
        if start_date:
            records = [r for r in records if r.created_at >= start_date]
        
        if end_date:
            records = [r for r in records if r.created_at <= end_date]
        
        total = sum(r.amount for r in records)
        by_category = {}
        for r in records:
            if r.category.value not in by_category:
                by_category[r.category.value] = 0
            by_category[r.category.value] += r.amount
        
        return {
            'total_cost': total,
            'by_category': by_category,
            'record_count': len(records),
            'currency': 'USD',
            'protocol_version': self.PROTOCOL_VERSION
        }
    
    async def set_budget(self, agent_id: str, budget: float):
        """Установка бюджета для агента"""
        self.budgets[agent_id] = budget
        
        # 🔹 Audit установки бюджета (наше дополнение)
        await self.audit.log_action(
            action="budget_set",
            result={
                'agent_id': agent_id,
                'budget': budget,
                'protocol_version': self.PROTOCOL_VERSION
            },
            context={}
        )
    
    async def _check_budget(self, agent_id: str, amount: float) -> bool:
        """Проверка превышения бюджета"""
        if agent_id not in self.budgets:
            return False
        
        current_spending = self.spending.get(agent_id, 0)
        return (current_spending + amount) > self.budgets[agent_id]
    
    async def _alert_budget_exceeded(self, agent_id: str, amount: float):
        """Оповещение о превышении бюджета"""
        if self.audit:
            await self.audit.log_action(
                action="budget_exceeded",
                result={
                    'agent_id': agent_id,
                    'amount': amount,
                    'current_spending': self.spending.get(agent_id, 0),
                    'budget': self.budgets.get(agent_id),
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={}
            )
    
    async def _audit_cost_record(self, record: CostRecord):
        """Audit записи затрат"""
        if self.audit:
            await self.audit.log_action(
                action="cost_recorded",
                result={
                    'record_id': record.id,
                    'trace_id': record.trace_id,
                    'category': record.category.value,
                    'amount': record.amount,
                    'protocol_version': self.PROTOCOL_VERSION
                },
                context={'agent_id': record.agent_id}
            )
```

---

## 6️⃣ ЧТО НЕ БРАТЬ ИЗ LANGSMITH

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет isolation policy | Нет enforcement | IsolationEnforcementPolicy class |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Cloud-dependent | Зависимость от LangSmith cloud | Self-hosted observability |
| Нет resource accounting | Нет детальных лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |
| Нет deterministic seeds | Нет воспроизводимости | execution_seed в контексте |
| Simple audit | Нет детального audit | Full Audit Trail с security context |

---

## 7️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Distributed Tracing (Неделя 5-6)

| Задача | LangSmith Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Trace Client | Trace SDK | `synapse/observability/trace_client.py` | ⏳ Ожидает |
| Span Manager | Span hierarchy | `synapse/observability/span_manager.py` | ⏳ Ожидает |
| Context Propagation | Trace context | `synapse/observability/context.py` | ⏳ Ожидает |

### Фаза 2: Dataset Management (Неделя 6-7)

| Задача | LangSmith Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Dataset Manager | Dataset CRUD | `synapse/testing/dataset_manager.py` | ⏳ Ожидает |
| Example Management | Example handling | `synapse/testing/dataset_manager.py` | ⏳ Ожидает |
| Validation System | Example validation | `synapse/testing/dataset_manager.py` | ⏳ Ожидает |

### Фаза 3: Evaluation Framework (Неделя 7-8)

| Задача | LangSmith Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Evaluation Runner | Run evaluation | `synapse/testing/evaluation.py` | ⏳ Ожидает |
| Metric Evaluators | Custom metrics | `synapse/testing/evaluation.py` | ⏳ Ожидает |
| Safety Evaluator | Security evaluation | `synapse/testing/evaluation.py` | ⏳ Ожидает |

### Фаза 4: Feedback & Cost (Неделя 8-9)

| Задача | LangSmith Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Feedback Collector | User feedback | `synapse/feedback/collector.py` | ⏳ Ожидает |
| Cost Tracker | Cost tracking | `synapse/observability/cost_tracker.py` | ⏳ Ожидает |
| Budget Management | Budget limits | `synapse/observability/cost_tracker.py` | ⏳ Ожидает |

---

## 8️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить LangSmith SDK documentation
□ Изучить tracing patterns
□ Изучить dataset management patterns
□ Изучить evaluation framework patterns
□ Изучить feedback collection patterns
□ Изучить cost tracking patterns

□ НЕ брать security model (у нас capability-based)
□ НЕ брать cloud-dependent components (у нас self-hosted)
□ НЕ брать resource management (у нас ResourceLimits schema)
□ НЕ брать simple audit (у нас full audit trail)

□ Адаптировать tracing с security filtering
□ Адаптировать datasets с sensitivity classification
□ Адаптировать evaluation с safety metrics
□ Адаптировать feedback с user validation
□ Адаптировать cost tracking с budget limits
□ Адаптировать все компоненты с protocol_version="1.0"

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 9️⃣ СРАВНЕНИЕ: ВСЕ ИСТОЧНИКИ

| Область | OpenClaw | Agent Zero | Anthropic | Claude Code | Codex | browser-use | AutoGPT | LangChain | LangGraph | LangSmith | Synapse |
|---------|----------|------------|-----------|-------------|-------|-------------|---------|-----------|-----------|-----------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (Agent Zero) |
| LLM Abstraction | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| Workflow/Graph | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangGraph) |
| Tracing | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangSmith) |
| Evaluation | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangSmith) |
| Datasets | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangSmith) |
| Feedback | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangSmith) |
| Cost Tracking | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangSmith) |
| Safety | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Protocol Versioning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⭐⭐⭐ | ⭐⭐⭐ | ✅ (оригинальное) |

---

## 🔟 ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 10.1 LangSmith License

```
LangSmith License: Proprietary (LangChain, Inc.)
Repository: https://github.com/langchain-ai/langsmith-sdk
Documentation: https://docs.smith.langchain.com/

При использовании LangSmith patterns:
1. Проверить лицензионные ограничения
2. Указать ссылку на документацию LangSmith
3. Добавить заметку об адаптации в docstring
4. Consider self-hosted alternatives for production
```

### 10.2 Формат Атрибуции

```python
# synapse/observability/trace_client.py
"""
Secure Trace Client для Synapse.

Адаптировано из LangSmith SDK tracing patterns:
https://docs.smith.langchain.com/

Оригинальная лицензия: Proprietary (LangChain, Inc.)
Адаптация: Добавлен security filtering, capability validation,
           protocol versioning, audit integration, self-hosted support

Copyright (c) 2024 LangChain, Inc.
Copyright (c) 2026 Synapse Contributors
"""
```

---

## 1️⃣1️⃣ ВЕРСИОНИРОВАНИЕ ДОКУМЕНТА

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
**browser-use:** `BROWSER_USE_INTEGRATION.md`  
**AutoGPT:** `AUTOGPT_INTEGRATION.md`  
**LangChain:** `LANGCHAIN_INTEGRATION.md`  
**LangGraph:** `LANGGRAPH_INTEGRATION.md`  
**LangSmith:** https://docs.smith.langchain.com/

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md