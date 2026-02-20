"""Runtime Profile Manager - Production deployment configuration."""
import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

PROTOCOL_VERSION: str = "1.0"


class RuntimeProfileManager:
    """Manages runtime profiles for different deployment modes."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self, config_path: str = None):
        self._config_path = config_path or self._get_default_config_path()
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._load_all_profiles()
    
    def _get_default_config_path(self) -> str:
        """Get default config path."""
        return os.path.join(os.path.dirname(__file__), "..", "..", "config", "environments")
    
    def _load_all_profiles(self) -> None:
        """Load all available profiles."""
        if not os.path.exists(self._config_path):
            # Create default profiles if path doesn't exist
            self._create_default_profiles()
            return
        
        for filename in os.listdir(self._config_path):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                profile_name = filename.rsplit(".", 1)[0]
                self._load_profile_file(profile_name, os.path.join(self._config_path, filename))
    
    def _create_default_profiles(self) -> None:
        """Create default profiles in memory."""
        self._profiles = {
            "local": {
                "mode": "local",
                "port": 8000,
                "debug": True,
                "protocol_version": PROTOCOL_VERSION
            },
            "vps": {
                "mode": "vps",
                "port": 80,
                "debug": False,
                "protocol_version": PROTOCOL_VERSION
            },
            "docker": {
                "mode": "docker",
                "port": 8080,
                "debug": False,
                "protocol_version": PROTOCOL_VERSION
            },
            "distributed": {
                "mode": "distributed",
                "port": 8000,
                "nodes": 3,
                "debug": False,
                "protocol_version": PROTOCOL_VERSION
            }
        }
    
    def _load_profile_file(self, name: str, path: str) -> None:
        """Load a profile from file."""
        try:
            with open(path, "r") as f:
                self._profiles[name] = yaml.safe_load(f)
        except Exception:
            pass
    
    def load_profile(self, name: str) -> Dict[str, Any]:
        """Load a specific profile."""
        if name not in self._profiles:
            raise ValueError(f"Profile '{name}' not found")
        return self._profiles[name]
    
    def list_profiles(self) -> List[str]:
        """List all available profiles."""
        return list(self._profiles.keys())
    
    def get_bootstrap_config(self, name: str) -> Dict[str, Any]:
        """Get bootstrap configuration for a profile."""
        profile = self.load_profile(name)
        return {
            "mode": profile.get("mode", name),
            "port": profile.get("port", 8000),
            "nodes": profile.get("nodes", 1),
            "debug": profile.get("debug", False),
            "protocol_version": PROTOCOL_VERSION
        }
