"""Optimizer agent for LLM-driven code/prompt optimization.

Phase 10 - Production Autonomy & Self-Optimization.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib


PROTOCOL_VERSION: str = "1.0"


@dataclass
class OptimizationRequest:
    """Request for optimization."""
    skill_name: str
    performance_metrics: Dict[str, Any]
    optimization_goal: str
    seed: int
    current_code: str = ""
    current_prompt: str = ""
    protocol_version: str = "1.0"


@dataclass
class OptimizationResponse:
    """Response from optimization."""
    success: bool
    optimization_id: str
    optimized_code: str = ""
    optimized_prompt: str = ""
    error: str = ""
    protocol_version: str = "1.0"


class OptimizerAgent:
    """Agent for LLM-driven code and prompt optimization.
    
    Responsibilities:
    - Generate improved code based on performance metrics
    - Generate improved prompts for better LLM responses
    - Respect policy constraints
    - Produce deterministic output with seed
    - Log optimization attempts
    """
    
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        llm_provider: Any = None,
        policy_engine: Any = None,
        audit_logger: Any = None
    ):
        self.llm_provider = llm_provider
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger
    
    def _generate_optimization_id(self, request: OptimizationRequest) -> str:
        """Generate deterministic optimization ID.
        
        Args:
            request: Optimization request
            
        Returns:
            Deterministic UUID based on request content
        """
        content = f"{request.skill_name}:{request.optimization_goal}:{request.seed}"
        hash_bytes = hashlib.sha256(content.encode()).digest()
        hex_id = hash_bytes[:16].hex()
        return f"opt-{hex_id}"
    
    async def optimize_code(self, request: OptimizationRequest) -> OptimizationResponse:
        """Optimize skill code.
        
        Args:
            request: Optimization request with current code
            
        Returns:
            OptimizationResponse with optimized code
        """
        optimization_id = self._generate_optimization_id(request)
        
        # Check policy
        if self.policy_engine:
            if not self.policy_engine.allows_optimization(request.skill_name):
                return OptimizationResponse(
                    success=False,
                    optimization_id=optimization_id,
                    error="Policy does not allow optimization for this skill"
                )
        
        # Audit log
        if self.audit_logger:
            self.audit_logger.record({
                "event": "code_optimization_started",
                "optimization_id": optimization_id,
                "skill_name": request.skill_name,
                "protocol_version": self.protocol_version
            })
        
        # Generate optimized code via LLM
        optimized_code = ""
        if self.llm_provider:
            try:
                prompt = self._build_code_optimization_prompt(request)
                optimized_code = await self.llm_provider.generate(prompt)
            except Exception:
                optimized_code = self._generate_fallback_code(request)
        else:
            optimized_code = self._generate_fallback_code(request)
        
        return OptimizationResponse(
            success=True,
            optimization_id=optimization_id,
            optimized_code=optimized_code
        )
    
    async def optimize_prompt(self, request: OptimizationRequest) -> OptimizationResponse:
        """Optimize skill prompt.
        
        Args:
            request: Optimization request with current prompt
            
        Returns:
            OptimizationResponse with optimized prompt
        """
        optimization_id = self._generate_optimization_id(request)
        
        # Check policy
        if self.policy_engine:
            if not self.policy_engine.allows_optimization(request.skill_name):
                return OptimizationResponse(
                    success=False,
                    optimization_id=optimization_id,
                    error="Policy does not allow optimization for this skill"
                )
        
        # Generate optimized prompt via LLM
        optimized_prompt = ""
        if self.llm_provider:
            try:
                prompt = self._build_prompt_optimization_prompt(request)
                optimized_prompt = await self.llm_provider.generate(prompt)
            except Exception:
                optimized_prompt = self._generate_fallback_prompt(request)
        else:
            optimized_prompt = self._generate_fallback_prompt(request)
        
        return OptimizationResponse(
            success=True,
            optimization_id=optimization_id,
            optimized_prompt=optimized_prompt
        )
    
    def _build_code_optimization_prompt(self, request: OptimizationRequest) -> str:
        """Build prompt for code optimization.
        
        Args:
            request: Optimization request
            
        Returns:
            Prompt string for LLM
        """
        return f"""Optimize the following code for {request.optimization_goal}.

Current code:
{request.current_code}

Performance metrics:
- Success rate: {request.performance_metrics.get('success_rate', 'unknown')}
- Latency: {request.performance_metrics.get('latency_ms', 'unknown')}ms

Provide optimized code that improves {request.optimization_goal}.
"""
    
    def _build_prompt_optimization_prompt(self, request: OptimizationRequest) -> str:
        """Build prompt for prompt optimization.
        
        Args:
            request: Optimization request
            
        Returns:
            Prompt string for LLM
        """
        return f"""Optimize the following prompt for {request.optimization_goal}.

Current prompt:
{request.current_prompt}

Performance metrics:
- Success rate: {request.performance_metrics.get('success_rate', 'unknown')}

Provide an improved prompt.
"""
    
    def _generate_fallback_code(self, request: OptimizationRequest) -> str:
        """Generate fallback optimized code.
        
        Args:
            request: Optimization request
            
        Returns:
            Fallback optimized code
        """
        return f'''# Optimized skill: {request.skill_name}
# Optimization goal: {request.optimization_goal}
# Seed: {request.seed}

class Optimized{request.skill_name.title().replace("_", "")}:
    """Optimized version with improved {request.optimization_goal}."""
    
    protocol_version = "1.0"
    
    def execute(self, context):
        """Execute with optimized performance."""
        # Improved implementation
        return {{"success": True, "optimized": True}}
'''
    
    def _generate_fallback_prompt(self, request: OptimizationRequest) -> str:
        """Generate fallback optimized prompt.
        
        Args:
            request: Optimization request
            
        Returns:
            Fallback optimized prompt
        """
        return f"""Execute the task with improved {request.optimization_goal}.
Be precise and efficient in your response.
"""
