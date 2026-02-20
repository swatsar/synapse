"""
Rollback Manager для Synapse.
Spec v3.1 compliant с асинхронной реализацией и capability enforcement.
"""
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class RollbackResult(BaseModel):
    """Результат операции rollback."""
    success: bool
    checkpoint_id: Optional[str] = None
    reason: Optional[str] = None
    rolled_back_state: Optional[Dict] = None
    protocol_version: str = PROTOCOL_VERSION


class RollbackRequest(BaseModel):
    """Запрос на выполнение rollback."""
    checkpoint_id: str
    reason: str = "User requested"
    agent_id: str
    trace_id: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION


class RollbackManager:
    """
    Менеджер отката к контрольным точкам.
    Асинхронная реализация с capability enforcement.
    """
    
    def __init__(
        self,
        checkpoint_manager=None,
        security_manager=None,
        audit_logger=None,
        # Legacy parameter names for backward compatibility
        cp_manager=None,
        cap_manager=None,
        audit=None
    ):
        # Support both new and legacy parameter names
        self.checkpoint_manager = checkpoint_manager or cp_manager
        self.security = security_manager or cap_manager
        self.audit = audit_logger or audit
        self.protocol_version = PROTOCOL_VERSION
    
    async def execute_rollback(
        self,
        checkpoint_id: str,
        agent_id: str,
        reason: str = "User requested"
    ) -> RollbackResult:
        """
        Выполнение отката к контрольной точке.
        КРИТИЧЕСКАЯ ФУНКЦИЯ — требует capability проверки.
        """
        # 1. Проверка capability на rollback
        if self.security:
            caps_result = await self.security.check_capabilities(
                required=["system:rollback"],
                agent_id=agent_id
            )
            
            if not caps_result.approved:
                return RollbackResult(
                    success=False,
                    reason=f"Capability denied: {caps_result.reason}",
                    protocol_version=PROTOCOL_VERSION
                )
        
        # 2. Получение checkpoint
        checkpoint = await self._get_checkpoint(checkpoint_id)
        
        if not checkpoint:
            return RollbackResult(
                success=False,
                reason=f"Checkpoint not found: {checkpoint_id}",
                protocol_version=PROTOCOL_VERSION
            )
        
        # 3. Проверка что checkpoint принадлежит агенту
        if hasattr(checkpoint, 'agent_id') and checkpoint.agent_id != agent_id:
            return RollbackResult(
                success=False,
                reason="Checkpoint belongs to different agent",
                protocol_version=PROTOCOL_VERSION
            )
        
        # 4. Выполнение rollback
        try:
            # Восстановление состояния
            restored_state = await self._restore_state(checkpoint_id)
            
            # Audit logging
            if self.audit:
                await self._audit_rollback(checkpoint_id, agent_id, reason, success=True)
            
            return RollbackResult(
                success=True,
                checkpoint_id=checkpoint_id,
                rolled_back_state=restored_state,
                protocol_version=PROTOCOL_VERSION
            )
            
        except Exception as e:
            # Audit logging failure
            if self.audit:
                await self._audit_rollback(checkpoint_id, agent_id, reason, success=False, error=str(e))
            
            return RollbackResult(
                success=False,
                reason=f"Rollback failed: {str(e)}",
                protocol_version=PROTOCOL_VERSION
            )
    
    async def _get_checkpoint(self, checkpoint_id: str):
        """Получение checkpoint по ID."""
        if not self.checkpoint_manager:
            return None
            
        if hasattr(self.checkpoint_manager, 'get_checkpoint'):
            result = self.checkpoint_manager.get_checkpoint(checkpoint_id)
            if hasattr(result, '__await__'):
                return await result
            return result
        elif hasattr(self.checkpoint_manager, 'get'):
            result = self.checkpoint_manager.get(checkpoint_id)
            if hasattr(result, '__await__'):
                return await result
            return result
        else:
            return None
    
    async def _restore_state(self, checkpoint_id) -> Dict:
        """Восстановление состояния из checkpoint."""
        if not self.checkpoint_manager:
            return {}
            
        # Call the CheckpointManager's restore method to actually restore state
        if hasattr(self.checkpoint_manager, 'restore'):
            cp_id = checkpoint_id
            if isinstance(checkpoint_id, str):
                try:
                    cp_id = uuid.UUID(checkpoint_id)
                except:
                    pass
            
            result = self.checkpoint_manager.restore(cp_id)
            if hasattr(result, '__await__'):
                return await result
            return result or {}
        
        return {}
    
    async def _audit_rollback(self, checkpoint_id: str, agent_id: str, reason: str, success: bool, error: str = None):
        """Audit logging для rollback операции."""
        if not self.audit:
            return
            
        if hasattr(self.audit, 'log_action'):
            import asyncio
            if asyncio.iscoroutinefunction(self.audit.log_action):
                await self.audit.log_action(
                    action="rollback_executed" if success else "rollback_failed",
                    result={
                        'checkpoint_id': checkpoint_id,
                        'agent_id': agent_id,
                        'reason': reason,
                        'success': success,
                        'error': error,
                        'protocol_version': PROTOCOL_VERSION
                    },
                    context={}
                )
            else:
                self.audit.log_action(
                    action="rollback_executed" if success else "rollback_failed",
                    result={
                        'checkpoint_id': checkpoint_id,
                        'agent_id': agent_id,
                        'reason': reason,
                        'success': success,
                        'error': error,
                        'protocol_version': PROTOCOL_VERSION
                    },
                    context={}
                )
        elif hasattr(self.audit, 'record'):
            self.audit.record(
                "rollback_executed" if success else "rollback_failed",
                {
                    'checkpoint_id': checkpoint_id,
                    'agent_id': agent_id,
                    'reason': reason,
                    'success': success,
                    'error': error
                }
            )
    
    # Legacy synchronous method for backward compatibility
    def rollback_to(self, checkpoint_id: uuid.UUID) -> None:
        """
        Legacy synchronous method for backward compatibility.
        Restores state to the checkpoint's original state.
        """
        # Directly call checkpoint manager's restore method
        if self.checkpoint_manager and hasattr(self.checkpoint_manager, 'restore'):
            self.checkpoint_manager.restore(checkpoint_id)
        
        # Audit logging
        if self.audit:
            if hasattr(self.audit, 'record'):
                self.audit.record("rollback_requested", {"checkpoint": str(checkpoint_id)})
                self.audit.record("rollback_completed", {"checkpoint": str(checkpoint_id)})
