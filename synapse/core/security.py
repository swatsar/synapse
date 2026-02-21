"""
Capability-Based Security Manager для Synapse.
Spec v3.1 compliant с полной реализацией токенов и проверок.
"""
from typing import Dict, List, Optional, Set, Any, Callable
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone, timedelta
import hashlib
import uuid
import fnmatch

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class CapabilityError(Exception):
    """Exception raised when capability check fails."""
    pass


class CapabilityToken(BaseModel):
    """Токен возможности с ограниченной областью действия."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability: str  # Например: "fs:read:/workspace/**"
    scope: str  # Область действия
    expires_at: Optional[str] = None
    issued_to: str  # agent_id
    issued_by: str  # issuer_id
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = PROTOCOL_VERSION
    
    model_config = ConfigDict(frozen=True)


class SecurityCheckResult(BaseModel):
    """Результат проверки безопасности."""
    approved: bool
    blocked_capabilities: List[str] = []
    reason: Optional[str] = None
    requires_human_approval: bool = False
    protocol_version: str = PROTOCOL_VERSION


class CapabilityManager:
    """
    Менеджер возможностей с полной реализацией токенов.
    Реализует принцип минимальных привилегий.
    """
    
    def __init__(self, audit_logger=None):
        self._tokens: Dict[str, CapabilityToken] = {}
        self._agent_capabilities: Dict[str, Set[str]] = {}
        self.audit = audit_logger
        self.protocol_version = PROTOCOL_VERSION
    
    async def issue_token(
        self,
        capability: str,
        issued_to: str,
        issued_by: str,
        expires_in_hours: Optional[int] = None
    ) -> CapabilityToken:
        """Выдача токена возможности."""
        
        expires_at = None
        if expires_in_hours:
            expires_at = (
                datetime.now(timezone.utc) + 
                timedelta(hours=expires_in_hours)
            ).isoformat()
        
        token = CapabilityToken(
            capability=capability,
            scope=self._extract_scope(capability),
            expires_at=expires_at,
            issued_to=issued_to,
            issued_by=issued_by
        )
        
        self._tokens[token.id] = token
        
        # Audit logging
        if self.audit:
            await self.audit.log_action(
                action="capability_token_issued",
                result={
                    'token_id': token.id,
                    'capability': capability,
                    'issued_to': issued_to,
                    'protocol_version': PROTOCOL_VERSION
                },
                context={'issued_by': issued_by}
            )
        
        return token
    
    async def check_capabilities(
        self,
        required: List[str],
        agent_id: str
    ) -> SecurityCheckResult:
        """
        Проверка наличия required capabilities у агента.
        КРИТИЧЕСКАЯ ФУНКЦИЯ — должна работать корректно.
        """
        blocked = []
        
        for cap in required:
            has_cap = await self._has_capability(agent_id, cap)
            if not has_cap:
                blocked.append(cap)
        
        if blocked:
            # Audit logging denied access
            if self.audit:
                await self.audit.log_action(
                    action="capability_check_denied",
                    result={
                        'agent_id': agent_id,
                        'blocked_capabilities': blocked,
                        'protocol_version': PROTOCOL_VERSION
                    },
                    context={}
                )
            
            return SecurityCheckResult(
                approved=False,
                blocked_capabilities=blocked,
                reason=f"Missing capabilities: {blocked}"
            )
        
        return SecurityCheckResult(approved=True)
    
    async def _has_capability(self, agent_id: str, capability: str) -> bool:
        """Проверка конкретной capability у агента."""
        # 1. Проверка токенов агента
        agent_tokens = [
            t for t in self._tokens.values() 
            if t.issued_to == agent_id
        ]
        
        for token in agent_tokens:
            # Проверка expiration
            if token.expires_at:
                expires = datetime.fromisoformat(token.expires_at)
                if datetime.now(timezone.utc) > expires:
                    continue  # Token expired
            
            # Проверка scope matching
            if self._match_capability(token.capability, capability):
                return True
        
        return False
    
    def _match_capability(self, token_cap: str, required_cap: str) -> bool:
        """
        Проверка соответствия capability с поддержкой wildcard.
        Пример: "fs:read:/workspace/**" matches "fs:read:/workspace/test.txt"
        """
        # Exact match
        if token_cap == required_cap:
            return True
        
        # Wildcard match
        if '*' in token_cap:
            return fnmatch.fnmatch(required_cap, token_cap)
        
        # Prefix match for paths
        if required_cap.startswith(token_cap):
            return True
        
        return False
    
    def _extract_scope(self, capability: str) -> str:
        """Извлечение scope из capability строки."""
        parts = capability.split(':', 2)
        if len(parts) >= 3:
            return parts[2]  # Например: "/workspace/**"
        return "*"
    
    async def revoke_token(self, token_id: str, agent_id: str) -> bool:
        """Отзыв токена возможности."""
        if token_id in self._tokens:
            token = self._tokens[token_id]
            if token.issued_to == agent_id:
                del self._tokens[token_id]
                
                # Audit logging
                if self.audit:
                    await self.audit.log_action(
                        action="capability_token_revoked",
                        result={
                            'token_id': token_id,
                            'agent_id': agent_id,
                            'protocol_version': PROTOCOL_VERSION
                        },
                        context={}
                    )
                
                return True
        return False
    
    async def get_agent_capabilities(self, agent_id: str) -> List[str]:
        """Получение списка capabilities агента."""
        capabilities = []
        for token in self._tokens.values():
            if token.issued_to == agent_id:
                # Проверка expiration
                if token.expires_at:
                    expires = datetime.fromisoformat(token.expires_at)
                    if datetime.now(timezone.utc) > expires:
                        continue
                capabilities.append(token.capability)
        return capabilities
    
    async def require(self, capabilities: List[str], agent_id: str = "default") -> bool:
        """
        Legacy method for backward compatibility.
        Raises CapabilityError if capabilities are missing.
        """
        result = await self.check_capabilities(capabilities, agent_id)
        if not result.approved:
            raise CapabilityError(f"Missing required capabilities: {result.blocked_capabilities}")
        return True


# ============================================================================
# Phase 1: Capability Security Layer v1 Components
# ============================================================================

class CapabilityContract(BaseModel):
    """
    Контракт возможности с расширенными возможностями.
    Phase 1: Capability Security Layer v1
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability: str  # "fs:read:/workspace/**"
    scope: str  # Область действия
    constraints: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[str] = None
    issued_to: str  # agent_id
    issued_by: str  # issuer_id
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = PROTOCOL_VERSION
    
    model_config = ConfigDict(frozen=True)
    
    def is_expired(self) -> bool:
        """Проверка истечения срока действия."""
        if not self.expires_at:
            return False
        
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expires


class EnforcementResult(BaseModel):
    """Результат enforcement."""
    approved: bool
    enforced: bool = False
    reason: Optional[str] = None
    capability: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION


class PermissionEnforcer:
    """
    Исполнитель разрешений.
    Phase 1: Capability Security Layer v1
    """
    
    def __init__(self, audit_logger=None):
        self.audit = audit_logger
        self.protocol_version = PROTOCOL_VERSION
    
    async def enforce(
        self,
        action: str,
        agent_id: str,
        capability_manager: 'CapabilityManager',
        audit: 'AuditMechanism' = None
    ) -> EnforcementResult:
        """
        Принудительная проверка разрешения.
        """
        # Проверка capabilities
        result = await capability_manager.check_capabilities(
            required=[action],
            agent_id=agent_id
        )
        
        # Emit audit event
        if audit or self.audit:
            audit_obj = audit or self.audit
            await audit_obj.emit_event(
                event_type="capability_checked",
                details={
                    "action": action,
                    "agent_id": agent_id,
                    "approved": result.approved
                }
            )
        
        if result.approved:
            return EnforcementResult(
                approved=True,
                enforced=True,
                capability=action
            )
        else:
            return EnforcementResult(
                approved=False,
                enforced=False,
                reason=result.reason
            )


class AuditEvent(BaseModel):
    """
    Событие аудита.
    Phase 1: Capability Security Layer v1
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: Optional[str] = None
    capability: Optional[str] = None
    action: Optional[str] = None
    result: str = "logged"  # "approved", "denied", "executed", "logged"
    details: Dict[str, Any] = Field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION


class AuditMechanism:
    """
    Механизм аудита.
    Phase 1: Capability Security Layer v1
    """
    
    def __init__(self):
        self._events: List[AuditEvent] = []
        self.protocol_version = PROTOCOL_VERSION
    
    async def emit_event(
        self,
        event_type: str,
        details: Dict[str, Any]
    ) -> str:
        """
        Публикация события аудита.
        """
        event = AuditEvent(
            event_type=event_type,
            agent_id=details.get("agent_id"),
            capability=details.get("capability"),
            action=details.get("action"),
            result=details.get("result", "logged"),
            details=details
        )
        
        self._events.append(event)
        return event.id
    
    async def get_events(
        self,
        event_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Получение событий аудита.
        """
        events = self._events
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        
        return events[-limit:]
    
    async def log_action(
        self,
        action: str,
        result: Dict[str, Any],
        context: Dict[str, Any] = None
    ):
        """
        Compatibility method for CapabilityManager.
        Wraps emit_event with log_action interface.
        """
        await self.emit_event(
            event_type=action,
            details={
                **result,
                **(context or {})
            }
        )
    
    async def clear_events(self):
        """Очистка событий (для тестов)."""
        self._events.clear()


class GuardResult(BaseModel):
    """Результат guard."""
    allowed: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION


class RuntimeGuard:
    """
    Middleware для защиты выполнения.
    Phase 1: Capability Security Layer v1
    """
    
    def __init__(self, audit_logger=None):
        self.audit = audit_logger
        self.protocol_version = PROTOCOL_VERSION
    
    async def guard(
        self,
        action: Callable,
        capabilities: List[str],
        agent_id: str,
        capability_manager: 'CapabilityManager',
        audit: 'AuditMechanism' = None
    ) -> GuardResult:
        """
        Защита выполнения действия.
        """
        # Проверка capabilities
        result = await capability_manager.check_capabilities(
            required=capabilities,
            agent_id=agent_id
        )
        
        # Emit audit event
        audit_obj = audit or self.audit
        if audit_obj:
            await audit_obj.emit_event(
                event_type="capability_checked" if result.approved else "capability_denied",
                details={
                    "capabilities": capabilities,
                    "agent_id": agent_id,
                    "approved": result.approved
                }
            )
        
        if not result.approved:
            return GuardResult(
                allowed=False,
                error=result.reason
            )
        
        # Execute action
        try:
            action_result = await action()
            
            # Emit execution event
            if audit_obj:
                await audit_obj.emit_event(
                    event_type="capability_executed",
                    details={
                        "capabilities": capabilities,
                        "agent_id": agent_id,
                        "result": "success"
                    }
                )
            
            return GuardResult(
                allowed=True,
                result=action_result
            )
            
        except Exception as e:
            return GuardResult(
                allowed=False,
                error=str(e)
            )

    # Add log_action method for compatibility with CapabilityManager
    async def log_action(
        self,
        action: str,
        result: Dict[str, Any],
        context: Dict[str, Any] = None
    ):
        """
        Compatibility method for CapabilityManager.
        Wraps emit_event with log_action interface.
        """
        await self.emit_event(
            event_type=action,
            details={
                **result,
                **(context or {})
            }
        )
