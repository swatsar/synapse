# 📎 PROJECT SYNAPSE: LANGCHAIN INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## ⚠️ ВАЖНОЕ ПРИМЕЧАНИЕ

**О проекте LangChain:** Это **один из самых популярных фреймворков** для разработки приложений с большими языковыми моделями. LangChain pioneered многие концепции в области LLM application architecture.

**Ключевые возможности LangChain:**
- LLM Abstraction Layer (унифицированный интерфейс к моделям)
- Chain/Workflow Patterns (композиция LLM вызовов)
- Memory Systems (управление контекстом диалога)
- Tool/Agent Integration (интеграция инструментов и агентов)
- Retrieval Systems (RAG — Retrieval Augmented Generation)
- Output Parsers (структурированный вывод от LLM)
- Callback System (observability и tracing)
- Vector Store Integration (множество коннекторов)

**Подход этого документа:** Анализирует **публично известные возможности LangChain** для интеграции в Synapse с учётом security model, capability-based access, protocol versioning, и production-ready reliability.

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

Он описывает стратегию интеграции полезных паттернов из **LangChain** в платформу Synapse, особенно для **LLM Abstraction**, **Chain/Workflow**, **RAG Systems**, **Output Parsing**, и **Observability** компонентов.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Паттернов для Заимствования | Статус |
|---------|---------------------|------------------------------|--------|
| LLM Abstraction Layer | ⭐⭐⭐⭐⭐ | ~60% | ✅ Рекомендовано |
| Chain/Workflow Patterns | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| Memory Systems | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| RAG/Retrieval | ⭐⭐⭐⭐⭐ | ~55% | ✅ Рекомендовано |
| Output Parsers | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Tool Integration | ⭐⭐⭐⭐ | ~45% | ⚠️ Адаптировать |
| Callback/Observability | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Vector Store Integration | ⭐⭐⭐⭐⭐ | ~60% | ✅ Рекомендовано |
| Security Model | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐⭐ | ~10% | ❌ НЕ брать |

---

## 1️⃣ LLM ABSTRACTION LAYER (CRITICAL PRIORITY)

### 1.1 Что Заимствовать

| Компонент | LangChain Pattern | Файл Synapse | Действие |
|-----------|-------------------|--------------|----------|
| LLM Interface | BaseLLM abstract class | `synapse/llm/base_llm.py` | Адаптировать с protocol_version |
| Model Registry | LLM registry & routing | `synapse/llm/model_registry.py` | Адаптировать с failover |
| Chat Model | Chat message abstraction | `synapse/llm/chat_model.py` | Адаптировать с message types |
| Embeddings | Embedding interface | `synapse/llm/embeddings.py` | Адаптировать с caching |
| Token Counting | Token estimation | `synapse/llm/token_counter.py` | Адаптировать с tracking |

### 1.2 Unified LLM Interface with Security

```python
# LangChain LLM abstraction → synapse/llm/base_llm.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from pydantic import BaseModel, Field
from enum import Enum

class LLMProvider(str, Enum):
    """Поддерживаемые LLM провайдеры"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MISTRAL = "mistral"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"

class LLMMessage(BaseModel):
    """
    Абстракция сообщения LLM.
    Адаптировано из LangChain message patterns.
    
    🔹 Наше дополнение: protocol_version + trace injection
    """
    role: str  # system, user, assistant, function
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict] = None
    tool_calls: Optional[List[Dict]] = None
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None

class LLMResponse(BaseModel):
    """
    Ответ от LLM.
    Адаптировано из LangChain response patterns.
    
    🔹 Наше дополнение: Security metadata + protocol_version
    """
    content: str
    model: str
    provider: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    latency_ms: Optional[int] = None
    safety_check: Optional[Dict] = None

class BaseLLM(ABC):
    """
    Базовый абстрактный класс для LLM.
    Адаптировано из LangChain BaseLLM patterns.
    
    🔹 Наше дополнение: Capability checks + Audit logging + Protocol versioning
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        config: dict,
        security_manager=None,
        audit_logger=None
    ):
        self.provider = provider
        self.model = model
        self.config = config
        self.security = security_manager  # 🔹 Наше дополнение
        self.audit = audit_logger  # 🔹 Наше дополнение
        self._cache = {}
    
    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = None,
        stop: List[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Генерация ответа от LLM"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа"""
        pass
    
    async def _validate_request(self, messages: List[LLMMessage]) -> bool:
        """
        Валидация запроса перед отправкой к LLM.
        🔹 Наше дополнение (не было в LangChain)
        """
        # Проверка на injection атаки
        for msg in messages:
            if await self._detect_injection(msg.content):
                await self.security.log_security_event(
                    event_type="llm_injection_attempt",
                    user_id=msg.name,
                    details={'content_preview': msg.content[:100]}
                )
                return False
        
        # Проверка rate limits
        if not await self._check_rate_limit():
            return False
        
        return True
    
    async def _detect_injection(self, content: str) -> bool:
        """Обнаружение prompt injection попыток"""
        injection_patterns = [
            'ignore previous instructions',
            'bypass security',
            'system prompt',
            'you are now',
            'forget all',
            'new instructions',
            '###USER:',
            '###SYSTEM:'
        ]
        
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in injection_patterns)
    
    async def _check_rate_limit(self) -> bool:
        """Проверка rate limits"""
        # В реальной реализации — проверка через security manager
        return True
    
    async def _cache_response(self, key: str, response: LLMResponse):
        """Кэширование ответа"""
        self._cache[key] = {
            'response': response,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _get_cached_response(self, key: str) -> Optional[LLMResponse]:
        """Получение кэшированного ответа"""
        cached = self._cache.get(key)
        if cached:
            # Проверка TTL (5 минут)
            from datetime import datetime, timedelta
            cache_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.utcnow() - cache_time < timedelta(minutes=5):
                return cached['response']
        return None
    
    def _count_tokens(self, text: str) -> int:
        """Подсчёт токенов (эмпирически)"""
        return len(text) // 4  # Приблизительно
    
    async def _audit_llm_call(self, messages: List[LLMMessage], response: LLMResponse):
        """
        Audit logging LLM вызова.
        🔹 Наше дополнение из spec v3.1
        """
        await self.audit.log_action(
            action="llm_call",
            result={
                'provider': self.provider.value,
                'model': self.model,
                'input_tokens': response.usage.get('prompt_tokens', 0),
                'output_tokens': response.usage.get('completion_tokens', 0),
                'latency_ms': response.latency_ms,
                'protocol_version': self.PROTOCOL_VERSION
            },
            context={
                'trace_id': response.trace_id,
                'session_id': response.session_id
            }
        )
```

### 1.3 LLM Router with Failover

```python
# LangChain model routing → synapse/llm/model_router.py
from typing import List, Dict, Optional
from enum import IntEnum

class ModelPriority(IntEnum):
    """Приоритет модели для failover"""
    PRIMARY = 1
    FALLBACK_1 = 2
    FALLBACK_2 = 3
    SAFE = 4

class ModelConfig(BaseModel):
    """Конфигурация модели"""
    provider: str
    model: str
    priority: ModelPriority
    base_url: Optional[str] = None
    api_key_env: str
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 60
    max_tokens: int = 4096
    is_active: bool = True
    protocol_version: str = "1.0"

class LLMRouter:
    """
    Маршрутизатор LLM запросов с failover.
    Адаптировано из LangChain routing patterns.
    
    🔹 Наше дополнение: Health checks + Protocol versioning + Capability validation
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, models: List[ModelConfig], security_manager):
        self.models = sorted(models, key=lambda m: m.priority.value)
        self.security = security_manager
        self.current_index = 0
        self.failure_counts: Dict[str, int] = {}
        self.health_status: Dict[str, bool] = {}
    
    async def get_available_model(self, task_type: str = None) -> Optional[ModelConfig]:
        """
        Получение доступной модели с учётом failover.
        
        🔹 Наше дополнение: Task-based routing + Health checks
        """
        # Task-based routing
        if task_type:
            preferred = await self._get_preferred_model_for_task(task_type)
            if preferred and preferred.is_active:
                return preferred
        
        # Fallback chain
        for i, model in enumerate(self.models):
            if model.is_active and self.health_status.get(model.model, True):
                self.current_index = i
                return model
        
        return None
    
    async def record_failure(self, model_name: str, error: Exception):
        """
        Запись сбоя модели.
        
        🔹 Наше дополнение: Automatic failover trigger
        """
        self.failure_counts[model_name] = self.failure_counts.get(model_name, 0) + 1
        
        # После 3 сбоев — переключение на fallback
        if self.failure_counts[model_name] >= 3:
            await self._switch_to_fallback(model_name)
            
            # Логирование
            await self.security.log_security_event(
                event_type="llm_model_failover",
                user_id="system",
                details={
                    'failed_model': model_name,
                    'failure_count': self.failure_counts[model_name],
                    'protocol_version': self.PROTOCOL_VERSION
                }
            )
    
    async def record_success(self, model_name: str):
        """Запись успешного вызова"""
        self.failure_counts[model_name] = 0
        self.health_status[model_name] = True
    
    async def health_check(self) -> Dict[str, Dict]:
        """
        Проверка здоровья всех моделей.
        🔹 Наше дополнение (не было в LangChain)
        """
        results = {}
        for model in self.models:
            is_healthy = await self._check_model_health(model)
            results[model.model] = {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'priority': model.priority.value,
                'failure_count': self.failure_counts.get(model.model, 0),
                'is_active': model.is_active,
                'protocol_version': self.PROTOCOL_VERSION
            }
        return results
    
    async def _switch_to_fallback(self, failed_model: str):
        """Переключение на fallback модель"""
        for model in self.models:
            if model.model != failed_model:
                model.is_active = True
                self.health_status[failed_model] = False
                break
    
    async def _check_model_health(self, model: ModelConfig) -> bool:
        """Проверка здоровья модели"""
        # В реальной реализации — health check endpoint или тестовый запрос
        return self.health_status.get(model.model, True)
    
    async def _get_preferred_model_for_task(self, task_type: str) -> Optional[ModelConfig]:
        """Получение предпочтительной модели для типа задачи"""
        task_model_mapping = {
            'code_generation': ['gpt-4', 'claude-3.5', 'codex'],
            'creative_writing': ['gpt-4', 'claude-3.5'],
            'analysis': ['gpt-4', 'claude-3.5'],
            'simple_qa': ['gpt-3.5', 'llama3'],
            'embedding': ['text-embedding-ada-002']
        }
        
        preferred_models = task_model_mapping.get(task_type, [])
        
        for model in self.models:
            if model.model in preferred_models and model.is_active:
                return model
        
        return None
```

---

## 2️⃣ CHAIN/WORKFLOW PATTERNS (CRITICAL PRIORITY)

### 2.1 Composable Chain System

```python
# LangChain chains → synapse/llm/chains.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel

class ChainInput(BaseModel):
    """Входные данные цепи"""
    data: Dict[str, Any]
    trace_id: str
    session_id: str
    protocol_version: str = "1.0"

class ChainOutput(BaseModel):
    """Выходные данные цепи"""
    result: Any
    intermediate_steps: List[Dict]
    trace_id: str
    session_id: str
    protocol_version: str = "1.0"

class BaseChain(ABC):
    """
    Базовый класс цепи.
    Адаптировано из LangChain chain patterns.
    
    🔹 Наше дополнение: Checkpoint + Audit + Protocol versioning
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, name: str, checkpoint_manager=None, audit_logger=None):
        self.name = name
        self.checkpoint = checkpoint_manager  # 🔹 Наше дополнение
        self.audit = audit_logger  # 🔹 Наше дополнение
    
    @abstractmethod
    async def execute(self, input: ChainInput) -> ChainOutput:
        """Выполнение цепи"""
        pass
    
    async def _create_checkpoint(self, input: ChainInput, state: dict) -> str:
        """
        Создание checkpoint состояния цепи.
        🔹 Наше дополнение (не было в LangChain)
        """
        if self.checkpoint:
            return await self.checkpoint.create_checkpoint(
                agent_id=f"chain:{self.name}",
                session_id=input.session_id
            )
        return None
    
    async def _audit_chain_step(self, step_name: str, input: Any, output: Any):
        """
        Audit logging шага цепи.
        🔹 Наше дополнение из spec v3.1
        """
        if self.audit:
            await self.audit.log_action(
                action=f"chain_step:{self.name}:{step_name}",
                result={'input': str(input)[:500], 'output': str(output)[:500]},
                context={'protocol_version': self.PROTOCOL_VERSION}
            )

class SequentialChain(BaseChain):
    """
    Последовательная цепь цепочек.
    Адаптировано из LangChain SequentialChain patterns.
    """
    
    def __init__(self, chains: List[BaseChain], **kwargs):
        super().__init__(name="sequential_chain", **kwargs)
        self.chains = chains
    
    async def execute(self, input: ChainInput) -> ChainOutput:
        """Последовательное выполнение цепей"""
        current_input = input
        intermediate_steps = []
        
        # 🔹 Checkpoint перед выполнением (наше дополнение)
        checkpoint_id = await self._create_checkpoint(input, {'step': 0})
        
        for i, chain in enumerate(self.chains):
            try:
                # Выполнение шага
                output = await chain.execute(current_input)
                
                intermediate_steps.append({
                    'chain': chain.name,
                    'step': i,
                    'input': current_input.data,
                    'output': output.result
                })
                
                # 🔹 Audit шага (наше дополнение)
                await self._audit_chain_step(chain.name, current_input.data, output.result)
                
                # Подготовка input для следующего шага
                current_input = ChainInput(
                    data={**current_input.data, **output.result},
                    trace_id=input.trace_id,
                    session_id=input.session_id,
                    protocol_version=self.PROTOCOL_VERSION
                )
                
            except Exception as e:
                # 🔹 Rollback при ошибке (наше дополнение)
                if self.checkpoint and checkpoint_id:
                    await self.checkpoint.rollback_to_checkpoint(checkpoint_id)
                
                raise
        
        return ChainOutput(
            result=current_input.data,
            intermediate_steps=intermediate_steps,
            trace_id=input.trace_id,
            session_id=input.session_id,
            protocol_version=self.PROTOCOL_VERSION
        )

class ParallelChain(BaseChain):
    """
    Параллельная цепь цепочек.
    Адаптировано из LangChain parallel patterns.
    """
    
    def __init__(self, chains: List[BaseChain], **kwargs):
        super().__init__(name="parallel_chain", **kwargs)
        self.chains = chains
    
    async def execute(self, input: ChainInput) -> ChainOutput:
        """Параллельное выполнение цепей"""
        import asyncio
        
        intermediate_steps = []
        results = {}
        
        tasks = [chain.execute(input) for chain in self.chains]
        outputs = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (chain, output) in enumerate(zip(self.chains, outputs)):
            if isinstance(output, Exception):
                intermediate_steps.append({
                    'chain': chain.name,
                    'step': i,
                    'error': str(output)
                })
            else:
                intermediate_steps.append({
                    'chain': chain.name,
                    'step': i,
                    'output': output.result
                })
                results[chain.name] = output.result
        
        return ChainOutput(
            result=results,
            intermediate_steps=intermediate_steps,
            trace_id=input.trace_id,
            session_id=input.session_id,
            protocol_version=self.PROTOCOL_VERSION
        )

class ConditionalChain(BaseChain):
    """
    Условная цепь (if-else логика).
    Адаптировано из LangChain conditional patterns.
    """
    
    def __init__(
        self,
        condition_chain: BaseChain,
        true_chain: BaseChain,
        false_chain: Optional[BaseChain] = None,
        **kwargs
    ):
        super().__init__(name="conditional_chain", **kwargs)
        self.condition_chain = condition_chain
        self.true_chain = true_chain
        self.false_chain = false_chain
    
    async def execute(self, input: ChainInput) -> ChainOutput:
        """Выполнение с условием"""
        # Оценка условия
        condition_output = await self.condition_chain.execute(input)
        condition_result = condition_output.result.get('condition', False)
        
        # Выбор ветки
        if condition_result:
            return await self.true_chain.execute(input)
        elif self.false_chain:
            return await self.false_chain.execute(input)
        else:
            return ChainOutput(
                result=input.data,
                intermediate_steps=[{'condition': False, 'branch': 'none'}],
                trace_id=input.trace_id,
                session_id=input.session_id,
                protocol_version=self.PROTOCOL_VERSION
            )
```

---

## 3️⃣ RAG/RETRIEVAL PATTERNS (HIGH PRIORITY)

### 3.1 Document Loading & Splitting

```python
# LangChain RAG → synapse/memory/rag.py
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Document(BaseModel):
    """
    Документ для RAG.
    Адаптировано из LangChain Document patterns.
    
    🔹 Наше дополнение: Protocol version + Security metadata
    """
    content: str
    metadata: Dict[str, Any]
    id: Optional[str] = None
    embedding: Optional[List[float]] = None
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    source_verified: bool = False
    sensitivity_level: str = "public"  # public, internal, confidential

class BaseDocumentLoader(ABC):
    """Базовый класс загрузчика документов"""
    
    @abstractmethod
    async def load(self, source: str) -> List[Document]:
        """Загрузка документов из источника"""
        pass

class TextDocumentLoader(BaseDocumentLoader):
    """Загрузчик текстовых файлов"""
    
    async def load(self, source: str) -> List[Document]:
        documents = []
        
        # В реальной реализации — чтение файла
        with open(source, 'r') as f:
            content = f.read()
        
        doc = Document(
            content=content,
            metadata={'source': source, 'type': 'text'},
            protocol_version="1.0"
        )
        documents.append(doc)
        
        return documents

class WebDocumentLoader(BaseDocumentLoader):
    """
    Загрузчик веб-страниц.
    Адаптировано из LangChain WebBaseLoader patterns.
    
    🔹 Наше дополнение: Domain whitelist + Security filtering
    """
    
    def __init__(self, security_manager, allowed_domains: List[str] = None):
        self.security = security_manager
        self.allowed_domains = allowed_domains or []
    
    async def load(self, url: str) -> List[Document]:
        # 🔹 Проверка домена (наше дополнение)
        if not await self._validate_domain(url):
            raise PermissionError(f"Domain not allowed: {url}")
        
        # В реальной реализации — HTTP запрос + parsing
        content = await self._fetch_and_parse(url)
        
        doc = Document(
            content=content,
            metadata={'source': url, 'type': 'web'},
            protocol_version="1.0",
            source_verified=True
        )
        
        return [doc]
    
    async def _validate_domain(self, url: str) -> bool:
        """Проверка домена в whitelist"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.split(':')[0]
        
        if self.allowed_domains:
            return any(allowed in domain for allowed in self.allowed_domains)
        return True
    
    async def _fetch_and_parse(self, url: str) -> str:
        """Получение и парсинг веб-страницы"""
        # В реальной реализации — aiohttp + BeautifulSoup
        return ""

class TextSplitter(ABC):
    """Базовый класс сплиттера текста"""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: callable = len
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
    
    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """Разделение текста на чанки"""
        pass

class RecursiveCharacterTextSplitter(TextSplitter):
    """
    Рекурсивный сплиттер текста.
    Адаптировано из LangChain RecursiveCharacterTextSplitter patterns.
    """
    
    def __init__(
        self,
        separators: List[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.separators = separators or ["\n\n", "\n", " ", ""]
    
    def split_text(self, text: str) -> List[str]:
        chunks = []
        self._split_text(text, chunks, self.separators)
        return chunks
    
    def _split_text(self, text: str, chunks: List[str], separators: List[str]):
        """Рекурсивное разделение текста"""
        if not text:
            return
        
        # Если текст меньше chunk_size — добавляем как есть
        if self.length_function(text) <= self.chunk_size:
            chunks.append(text)
            return
        
        # Пробуем разделить по текущему сепаратору
        separator = separators[0] if separators else ""
        new_separators = separators[1:] if separators else []
        
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        
        # Объединяем чанки с overlap
        current_chunk = ""
        for split in splits:
            if self.length_function(current_chunk + split) <= self.chunk_size:
                current_chunk += (separator + split if current_chunk else split)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = split
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Рекурсивное разделение больших чанков
        final_chunks = []
        for chunk in chunks:
            if self.length_function(chunk) > self.chunk_size:
                self._split_text(chunk, final_chunks, new_separators)
            else:
                final_chunks.append(chunk)
        
        chunks.clear()
        chunks.extend(final_chunks)

class RetrievalSystem:
    """
    Система retrieval для RAG.
    Адаптировано из LangChain RetrievalQA patterns.
    
    🔹 Наше дополнение: Security filtering + Protocol versioning + Checkpoint
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(
        self,
        vector_store,
        llm,
        security_manager,
        checkpoint_manager=None
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.security = security_manager
        self.checkpoint = checkpoint_manager
    
    async def retrieve_and_generate(
        self,
        query: str,
        k: int = 5,
        filter_sensitive: bool = True
    ) -> Dict:
        """
        RAG: Retrieval + Generation.
        
        🔹 Наше дополнение: Security filtering результатов
        """
        # 🔹 Checkpoint перед retrieval (наше дополнение)
        checkpoint_id = None
        if self.checkpoint:
            checkpoint_id = await self.checkpoint.create_checkpoint(
                agent_id="retrieval_system",
                session_id=query[:50]  # Эмуляция session_id
            )
        
        try:
            # 1. Поиск релевантных документов
            documents = await self.vector_store.similarity_search(
                query=query,
                k=k
            )
            
            # 2. 🔹 Фильтрация чувствительных документов (наше дополнение)
            if filter_sensitive:
                documents = await self._filter_sensitive_documents(documents)
            
            # 3. Формирование контекста
            context = self._build_context(documents)
            
            # 4. Генерация ответа с контекстом
            response = await self.llm.generate([
                LLMMessage(
                    role="system",
                    content=f"Answer based on this context:\n\n{context}",
                    protocol_version=self.PROTOCOL_VERSION
                ),
                LLMMessage(
                    role="user",
                    content=query,
                    protocol_version=self.PROTOCOL_VERSION
                )
            ])
            
            return {
                'answer': response.content,
                'sources': [doc.metadata.get('source') for doc in documents],
                'documents_count': len(documents),
                'checkpoint_id': checkpoint_id,
                'protocol_version': self.PROTOCOL_VERSION
            }
            
        except Exception as e:
            # 🔹 Rollback при ошибке (наше дополнение)
            if self.checkpoint and checkpoint_id:
                await self.checkpoint.rollback_to_checkpoint(checkpoint_id)
            raise
    
    async def _filter_sensitive_documents(self, documents: List[Document]) -> List[Document]:
        """
        Фильтрация чувствительных документов.
        🔹 Наше дополнение (критично для spec v3.1)
        """
        filtered = []
        for doc in documents:
            if doc.sensitivity_level == "public":
                filtered.append(doc)
            elif doc.sensitivity_level == "internal":
                # Проверка capabilities
                has_access = await self.security.check_capabilities(
                    required=["memory:internal"],
                    context={}
                )
                if has_access.approved:
                    filtered.append(doc)
            # confidential документы не возвращаются через RAG
        return filtered
    
    def _build_context(self, documents: List[Document]) -> str:
        """Построение контекста из документов"""
        context_parts = []
        for i, doc in enumerate(documents):
            context_parts.append(f"[Source {i+1}]: {doc.content}")
        return "\n\n".join(context_parts)
```

---

## 4️⃣ OUTPUT PARSER PATTERNS (HIGH PRIORITY)

### 4.1 Structured Output Parsing

```python
# LangChain output parsers → synapse/llm/output_parsers.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type
from pydantic import BaseModel, ValidationError
import json
import re

class BaseOutputParser(ABC):
    """
    Базовый класс парсера вывода LLM.
    Адаптировано из LangChain output parser patterns.
    
    🔹 Наше дополнение: Protocol version + Validation
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    @abstractmethod
    async def parse(self, text: str) -> Any:
        """Парсинг текста от LLM"""
        pass
    
    def get_format_instructions(self) -> str:
        """Инструкции по формату для LLM"""
        return ""

class PydanticOutputParser(BaseOutputParser):
    """
    Парсер вывода в Pydantic модель.
    Адаптировано из LangChain PydanticOutputParser patterns.
    
    🔹 Наше дополнение: Protocol version injection + Validation
    """
    
    def __init__(self, pydantic_class: Type[BaseModel]):
        self.pydantic_class = pydantic_class
    
    async def parse(self, text: str) -> BaseModel:
        """Парсинг в Pydantic модель"""
        try:
            # Извлечение JSON из текста
            json_text = self._extract_json(text)
            
            # 🔹 Добавление protocol_version (наше дополнение)
            json_data = json.loads(json_text)
            if 'protocol_version' not in json_data:
                json_data['protocol_version'] = self.PROTOCOL_VERSION
            
            # Валидация через Pydantic
            return self.pydantic_class(**json_data)
            
        except ValidationError as e:
            raise ValueError(f"Output validation failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parsing failed: {str(e)}")
    
    def get_format_instructions(self) -> str:
        """Инструкции формата для LLM"""
        schema = self.pydantic_class.model_json_schema()
        return f"""
Return output as JSON matching this schema:
{json.dumps(schema, indent=2)}

Include protocol_version: "{self.PROTOCOL_VERSION}" in your response.
"""
    
    def _extract_json(self, text: str) -> str:
        """Извлечение JSON из текста"""
        # Поиск JSON в markdown code blocks
        match = re.search(r'```(?:json)?\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Поиск JSON объекта
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group()
        
        return text

class EnumOutputParser(BaseOutputParser):
    """Парсер вывода в Enum"""
    
    def __init__(self, enum_class: Type):
        self.enum_class = enum_class
    
    async def parse(self, text: str) -> Any:
        """Парсинг в Enum"""
        text = text.strip().upper()
        try:
            return self.enum_class(text)
        except ValueError:
            valid_values = [e.value for e in self.enum_class]
            raise ValueError(f"Invalid enum value. Valid: {valid_values}")
    
    def get_format_instructions(self) -> str:
        valid_values = [e.value for e in self.enum_class]
        return f"Return one of: {', '.join(valid_values)}"

class RetryOutputParser(BaseOutputParser):
    """
    Парсер с автоматическими повторами.
    Адаптировано из LangChain RetryOutputParser patterns.
    
    🔹 Наше дополнение: Max retries + Protocol version
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(
        self,
        base_parser: BaseOutputParser,
        max_retries: int = 3,
        llm=None
    ):
        self.base_parser = base_parser
        self.max_retries = max_retries
        self.llm = llm
    
    async def parse(self, text: str) -> Any:
        """Парсинг с повторами при ошибках"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await self.base_parser.parse(text)
            except ValueError as e:
                last_error = e
                
                # Если есть LLM — запросить исправление
                if self.llm and attempt < self.max_retries - 1:
                    text = await self._request_fix(text, str(e))
        
        raise ValueError(f"Failed to parse after {self.max_retries} attempts: {last_error}")
    
    async def _request_fix(self, original_text: str, error: str) -> str:
        """Запрос исправления от LLM"""
        prompt = f"""
The previous output failed to parse:

Original Output:
{original_text}

Error:
{error}

Please fix the output to match the required format.
Include protocol_version: "{self.PROTOCOL_VERSION}"

Return only the corrected output.
"""
        response = await self.llm.generate([
            LLMMessage(role="user", content=prompt, protocol_version=self.PROTOCOL_VERSION)
        ])
        return response.content
    
    def get_format_instructions(self) -> str:
        return self.base_parser.get_format_instructions()

class StructuredOutputChain:
    """
    Цепь для структурированного вывода.
    Адаптировано из LangChain StructuredOutputChain patterns.
    """
    
    def __init__(self, llm, output_parser: BaseOutputParser, prompt_template: str):
        self.llm = llm
        self.parser = output_parser
        self.prompt_template = prompt_template
    
    async def execute(self, input_data: Dict) -> Any:
        """Выполнение цепи с структурированным выводом"""
        # Формирование промпта
        prompt = self.prompt_template.format(**input_data)
        prompt += f"\n\n{self.parser.get_format_instructions()}"
        
        # Генерация ответа
        response = await self.llm.generate([
            LLMMessage(role="user", content=prompt, protocol_version="1.0")
        ])
        
        # Парсинг ответа
        return await self.parser.parse(response.content)
```

---

## 5️⃣ CALLBACK/OBSERVABILITY PATTERNS (HIGH PRIORITY)

### 5.1 Callback System for Tracing

```python
# LangChain callbacks → synapse/observability/callbacks.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class CallbackEventType(str, Enum):
    """Типы событий callback"""
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    LLM_ERROR = "llm_error"
    CHAIN_START = "chain_start"
    CHAIN_END = "chain_end"
    CHAIN_ERROR = "chain_error"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    RETRIEVAL_START = "retrieval_start"
    RETRIEVAL_END = "retrieval_end"

class CallbackEvent(BaseModel):
    """Событие callback"""
    event_type: CallbackEventType
    name: str
    start_time: str
    end_time: Optional[str] = None
    input: Optional[Dict] = None
    output: Optional[Dict] = None
    error: Optional[str] = None
    trace_id: str
    session_id: str
    parent_id: Optional[str] = None
    
    # 🔹 Наше дополнение из spec v3.1
    protocol_version: str = "1.0"
    metadata: Optional[Dict] = None

class BaseCallbackHandler(ABC):
    """
    Базовый класс callback handler.
    Адаптировано из LangChain callback handler patterns.
    
    🔹 Наше дополнение: Protocol version + Security filtering
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    @abstractmethod
    async def on_event(self, event: CallbackEvent):
        """Обработка события"""
        pass

class LoggingCallbackHandler(BaseCallbackHandler):
    """Callback handler для логирования"""
    
    def __init__(self, logger, filter_sensitive: bool = True):
        self.logger = logger
        self.filter_sensitive = filter_sensitive
    
    async def on_event(self, event: CallbackEvent):
        """Логирование события"""
        # 🔹 Фильтрация чувствительных данных (наше дополнение)
        log_data = event.dict()
        if self.filter_sensitive:
            log_data = self._filter_sensitive_data(log_data)
        
        await self.logger.info(
            f"Callback Event: {event.event_type.value}",
            extra=log_data
        )
    
    def _filter_sensitive_data(self, data: Dict) -> Dict:
        """Фильтрация чувствительных данных"""
        sensitive_keys = ['password', 'token', 'secret', 'key', 'api_key']
        
        filtered = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                filtered[key] = '[REDACTED]'
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            else:
                filtered[key] = value
        
        return filtered

class MetricsCallbackHandler(BaseCallbackHandler):
    """
    Callback handler для метрик.
    Адаптировано из LangChain metrics patterns.
    
    🔹 Наше дополнение: Prometheus integration + Protocol version
    """
    
    def __init__(self, metrics_collector):
        self.metrics = metrics_collector
    
    async def on_event(self, event: CallbackEvent):
        """Сбор метрик"""
        if event.event_type == CallbackEventType.LLM_END:
            # Метрики LLM вызова
            duration = self._calculate_duration(event.start_time, event.end_time)
            await self.metrics.record(
                name='synapse_llm_call_duration_seconds',
                value=duration,
                labels={
                    'model': event.name,
                    'protocol_version': self.PROTOCOL_VERSION
                }
            )
        
        elif event.event_type == CallbackEventType.CHAIN_END:
            # Метрики цепи
            duration = self._calculate_duration(event.start_time, event.end_time)
            await self.metrics.record(
                name='synapse_chain_duration_seconds',
                value=duration,
                labels={
                    'chain': event.name,
                    'protocol_version': self.PROTOCOL_VERSION
                }
            )
        
        elif event.event_type == CallbackEventType.LLM_ERROR:
            # Метрики ошибок
            await self.metrics.record(
                name='synapse_llm_errors_total',
                value=1,
                labels={
                    'model': event.name,
                    'error_type': type(event.error).__name__,
                    'protocol_version': self.PROTOCOL_VERSION
                }
            )
    
    def _calculate_duration(self, start: str, end: str) -> float:
        """Расчёт длительности"""
        from datetime import datetime
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return (end_dt - start_dt).total_seconds()

class CallbackManager:
    """
    Менеджер callback handlers.
    Адаптировано из LangChain callback manager patterns.
    
    🔹 Наше дополнение: Trace propagation + Protocol version
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, handlers: List[BaseCallbackHandler] = None):
        self.handlers = handlers or []
        self.trace_stack: List[str] = []
    
    def add_handler(self, handler: BaseCallbackHandler):
        """Добавление handler"""
        self.handlers.append(handler)
    
    async def on_event(self, event: CallbackEvent):
        """Отправка события всем handlers"""
        # 🔹 Добавление protocol_version (наше дополнение)
        event.protocol_version = self.PROTOCOL_VERSION
        
        # 🔹 Trace propagation (наше дополнение)
        if self.trace_stack:
            event.parent_id = self.trace_stack[-1]
        
        for handler in self.handlers:
            try:
                await handler.on_event(event)
            except Exception as e:
                # Не позволяем ошибке handler остановить основную логику
                pass
    
    async def trace_start(self, name: str, event_type: CallbackEventType, 
                          input: Dict, trace_id: str, session_id: str):
        """Начало traced операции"""
        event = CallbackEvent(
            event_type=event_type,
            name=name,
            start_time=datetime.utcnow().isoformat(),
            input=input,
            trace_id=trace_id,
            session_id=session_id,
            protocol_version=self.PROTOCOL_VERSION
        )
        
        await self.on_event(event)
        self.trace_stack.append(event.event_type.value)
    
    async def trace_end(self, event_type: CallbackEventType, 
                        output: Dict, error: str = None):
        """Завершение traced операции"""
        if self.trace_stack:
            parent_type = self.trace_stack.pop()
            
            event = CallbackEvent(
                event_type=event_type,
                name=parent_type,
                start_time="",  # Будет заполнено handler
                end_time=datetime.utcnow().isoformat(),
                output=output,
                error=error,
                trace_id="",  # Будет заполнено handler
                session_id="",
                protocol_version=self.PROTOCOL_VERSION
            )
            
            await self.on_event(event)
```

---

## 6️⃣ ЧТО НЕ БРАТЬ ИЗ LANGCHAIN

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая security model | Нет capability tokens | Capability-Based Security Model |
| Нет isolation policy | Нет enforcement | IsolationEnforcementPolicy class |
| Нет checkpoint/rollback | Нет recovery | RollbackManager с is_fresh() |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |
| Нет deterministic seeds | Нет воспроизводимости | execution_seed в контексте |
| Simple error handling | Нет structured recovery | StructuredError с rollback trigger |
| No protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Plugin security | Нет scan | Security Scan + Allowlist |

---

## 7️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: LLM Abstraction (Неделя 3-4)

| Задача | LangChain Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Base LLM Interface | BaseLLM abstract | `synapse/llm/base_llm.py` | ⏳ Ожидает |
| Model Router | LLM routing | `synapse/llm/model_router.py` | ⏳ Ожидает |
| Token Counter | Token tracking | `synapse/llm/token_counter.py` | ⏳ Ожидает |

### Фаза 2: Chain System (Неделя 4-5)

| Задача | LangChain Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Base Chain | Chain abstraction | `synapse/llm/chains.py` | ⏳ Ожидает |
| Sequential Chain | Sequential execution | `synapse/llm/chains.py` | ⏳ Ожидает |
| Parallel Chain | Parallel execution | `synapse/llm/chains.py` | ⏳ Ожидает |

### Фаза 3: RAG System (Неделя 5-6)

| Задача | LangChain Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Document Loader | Document loading | `synapse/memory/rag.py` | ⏳ Ожидает |
| Text Splitter | Text splitting | `synapse/memory/rag.py` | ⏳ Ожидает |
| Retrieval System | RAG pipeline | `synapse/memory/rag.py` | ⏳ Ожидает |

### Фаза 4: Output Parsing (Неделя 6-7)

| Задача | LangChain Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Output Parsers | Structured output | `synapse/llm/output_parsers.py` | ⏳ Ожидает |
| Pydantic Parser | Pydantic validation | `synapse/llm/output_parsers.py` | ⏳ Ожидает |
| Retry Parser | Retry logic | `synapse/llm/output_parsers.py` | ⏳ Ожидает |

### Фаза 5: Observability (Неделя 7-8)

| Задача | LangChain Pattern | Файл Synapse | Статус |
|--------|-------------------|--------------|--------|
| Callback System | Event callbacks | `synapse/observability/callbacks.py` | ⏳ Ожидает |
| Metrics Handler | Prometheus metrics | `synapse/observability/metrics.py` | ⏳ Ожидает |
| Trace Manager | Distributed tracing | `synapse/observability/tracing.py` | ⏳ Ожидает |

---

## 8️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить LangChain documentation
□ Изучить LLM abstraction patterns
□ Изучить chain/workflow patterns
□ Изучить RAG/retrieval patterns
□ Изучить output parser patterns
□ Изучить callback/observability patterns

□ НЕ брать security model (у нас capability-based)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)
□ НЕ брать resource management (у нас ResourceLimits schema)

□ Адаптировать LLM interface с protocol_version
□ Адаптировать chain system с checkpoint integration
□ Адаптировать RAG system с security filtering
□ Адаптировать output parsers с validation
□ Адаптировать callback system с trace propagation
□ Адаптировать все компоненты с protocol_version="1.0"

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 9️⃣ СРАВНЕНИЕ: ВСЕ ИСТОЧНИКИ

| Область | OpenClaw | Agent Zero | Anthropic | Claude Code | Codex | browser-use | AutoGPT | LangChain | Synapse |
|---------|----------|------------|-----------|-------------|-------|-------------|---------|-----------|---------|
| Коннекторы | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (OpenClaw) |
| Self-Evolution | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Agent Zero) |
| LLM Abstraction | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| Chain/Workflow | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| RAG/Retrieval | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| Output Parsing | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| Observability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LangChain) |
| Agent Loop | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (AutoGPT) |
| Goal Management | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (AutoGPT) |
| Memory System | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (AutoGPT) |
| Code Generation | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Codex/Claude) |
| Browser Automation | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (browser-use) |
| Safety | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Security | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (оригинальное) |
| Protocol Versioning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Capability Security | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |
| Rollback/Checkpoint | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (оригинальное) |

---

## 🔟 ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 10.1 LangChain License

```
LangChain License: MIT
Repository: https://github.com/langchain-ai/langchain

При использовании LangChain patterns:
1. Сохранить оригинальный copyright notice
2. Указать ссылку на оригинальный репозиторий
3. Добавить заметку об адаптации в docstring
```

### 10.2 Формат Атрибуции

```python
# synapse/llm/base_llm.py
"""
Base LLM Interface для Synapse.

Адаптировано из LangChain BaseLLM patterns:
https://github.com/langchain-ai/langchain

Оригинальная лицензия: MIT
Адаптация: Добавлен capability validation, protocol versioning,
           security filtering, audit logging, checkpoint integration

Copyright (c) 2023 LangChain, Inc.
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
**LangChain:** https://github.com/langchain-ai/langchain

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md