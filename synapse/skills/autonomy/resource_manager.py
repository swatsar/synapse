"""Resource management for autonomous optimization.

Phase 10 - Production Autonomy & Self-Optimization.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


PROTOCOL_VERSION: str = "1.0"


@dataclass
class ResourceLimits:
    """Resource limits for skill execution."""
    max_cpu_percent: int = 100
    max_memory_mb: int = 1024
    max_disk_mb: int = 1024
    max_network_kb: int = 10240
    protocol_version: str = "1.0"


@dataclass
class ResourceUsage:
    """Current resource usage."""
    cpu_percent: int = 0
    memory_mb: int = 0
    disk_mb: int = 0
    network_kb: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = "1.0"


@dataclass
class AllocationResult:
    """Result of resource allocation attempt."""
    success: bool
    error: str = ""
    allocated: Dict[str, int] = field(default_factory=dict)
    protocol_version: str = "1.0"


class ResourceManager:
    """Manages resource allocation and limits for skill execution.
    
    Responsibilities:
    - Track resource usage per skill
    - Enforce resource limits
    - Provide available resources info
    - Record usage history
    """
    
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.protocol_version = "1.0"
        self.limits = limits or ResourceLimits()
        self._usage_history: Dict[str, List[ResourceUsage]] = {}
        self._current_allocations: Dict[str, ResourceUsage] = {}
    
    def check_within_limits(self, usage: ResourceUsage) -> bool:
        """Check if usage is within limits.
        
        Args:
            usage: Resource usage to check
            
        Returns:
            True if within limits
        """
        return (
            usage.cpu_percent <= self.limits.max_cpu_percent and
            usage.memory_mb <= self.limits.max_memory_mb and
            usage.disk_mb <= self.limits.max_disk_mb and
            usage.network_kb <= self.limits.max_network_kb
        )
    
    def get_available(self) -> Dict[str, int]:
        """Get available resources.
        
        Returns:
            Dict of available resources
        """
        # Calculate used resources
        used_cpu = sum(u.cpu_percent for u in self._current_allocations.values())
        used_memory = sum(u.memory_mb for u in self._current_allocations.values())
        used_disk = sum(u.disk_mb for u in self._current_allocations.values())
        used_network = sum(u.network_kb for u in self._current_allocations.values())
        
        return {
            "cpu": max(0, self.limits.max_cpu_percent - used_cpu),
            "memory": max(0, self.limits.max_memory_mb - used_memory),
            "disk": max(0, self.limits.max_disk_mb - used_disk),
            "network": max(0, self.limits.max_network_kb - used_network)
        }
    
    def record_usage(self, skill_name: str, usage: ResourceUsage) -> None:
        """Record resource usage for a skill.
        
        Args:
            skill_name: Name of skill
            usage: Resource usage to record
        """
        if skill_name not in self._usage_history:
            self._usage_history[skill_name] = []
        self._usage_history[skill_name].append(usage)
    
    def get_usage_history(self, skill_name: str) -> List[ResourceUsage]:
        """Get usage history for a skill.
        
        Args:
            skill_name: Name of skill
            
        Returns:
            List of usage records
        """
        return self._usage_history.get(skill_name, [])
    
    async def allocate(
        self,
        skill_name: str,
        cpu_percent: int,
        memory_mb: int,
        disk_mb: int,
        network_kb: int
    ) -> AllocationResult:
        """Attempt to allocate resources for a skill.
        
        Args:
            skill_name: Name of skill
            cpu_percent: CPU percent needed
            memory_mb: Memory needed in MB
            disk_mb: Disk needed in MB
            network_kb: Network needed in KB
            
        Returns:
            AllocationResult with success status
        """
        usage = ResourceUsage(
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            disk_mb=disk_mb,
            network_kb=network_kb
        )
        
        # Check if within limits
        if not self.check_within_limits(usage):
            errors = []
            if cpu_percent > self.limits.max_cpu_percent:
                errors.append("cpu")
            if memory_mb > self.limits.max_memory_mb:
                errors.append("memory")
            if disk_mb > self.limits.max_disk_mb:
                errors.append("disk")
            if network_kb > self.limits.max_network_kb:
                errors.append("network")
            
            return AllocationResult(
                success=False,
                error=f"Resource limits exceeded: {', '.join(errors)}"
            )
        
        # Check available resources
        available = self.get_available()
        if cpu_percent > available["cpu"]:
            return AllocationResult(
                success=False,
                error=f"Insufficient CPU: need {cpu_percent}, have {available['cpu']}"
            )
        if memory_mb > available["memory"]:
            return AllocationResult(
                success=False,
                error=f"Insufficient memory: need {memory_mb}MB, have {available['memory']}MB"
            )
        
        # Allocate
        self._current_allocations[skill_name] = usage
        self.record_usage(skill_name, usage)
        
        return AllocationResult(
            success=True,
            allocated={
                "cpu": cpu_percent,
                "memory": memory_mb,
                "disk": disk_mb,
                "network": network_kb
            }
        )
    
    def release(self, skill_name: str) -> bool:
        """Release resources allocated to a skill.
        
        Args:
            skill_name: Name of skill
            
        Returns:
            True if released
        """
        if skill_name in self._current_allocations:
            del self._current_allocations[skill_name]
            return True
        return False
