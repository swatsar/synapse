"""
Windows Environment Adapter.

Protocol Version: 1.0
Spec Version: 3.1
"""

import asyncio
import platform
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

from synapse.environment.adapters.base import EnvironmentAdapter, PROTOCOL_VERSION


class WindowsAdapter(EnvironmentAdapter):
    """Windows-specific environment adapter.

    Handles Windows-specific paths, PowerShell commands,
    registry access, and Windows service management.
    """

    def __init__(self):
        self._platform = "Windows"
        self._shell = "powershell"

    async def get_home_dir(self) -> Path:
        """Get Windows user home directory.

        Returns:
            Path: User home directory (e.g., C:/Users/username)
        """
        import os
        return Path.home()

    async def get_config_dir(self) -> Path:
        """Get Windows config directory.

        Returns:
            Path: APPDATA/Synapse directory
        """
        import os
        appdata = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
        return Path(appdata) / 'Synapse'

    async def get_data_dir(self) -> Path:
        """Get Windows data directory.

        Returns:
            Path: LOCALAPPDATA/Synapse directory
        """
        import os
        localappdata = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        return Path(localappdata) / 'Synapse'

    async def get_temp_dir(self) -> Path:
        """Get Windows temp directory.

        Returns:
            Path: TEMP directory
        """
        import os
        return Path(os.environ.get('TEMP', os.environ.get('TMP', 'C:/Windows/Temp')))

    async def execute_command(
        self, 
        command: str, 
        timeout: int = 60,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute command using PowerShell.

        Args:
            command: Command to execute
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables

        Returns:
            Dict with stdout, stderr, returncode, protocol_version
        """
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                shell=True,  # nosec B604
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env or None
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            return self._create_response({
                'stdout': stdout.decode('utf-8', errors='replace'),
                'stderr': stderr.decode('utf-8', errors='replace'),
                'returncode': process.returncode
            })

        except asyncio.TimeoutError:
            return self._create_response({
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'returncode': -1
            })
        except Exception as e:
            return self._create_response({
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            })

    async def get_os_info(self) -> Dict[str, Any]:
        """Get Windows system information.

        Returns:
            Dict with os, version, architecture, protocol_version
        """
        return self._create_response({
            'os': 'Windows',
            'version': platform.version(),
            'release': platform.release(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'hostname': platform.node()
        })

    async def get_network_info(self) -> Dict[str, Any]:
        """Get Windows network information.

        Returns:
            Dict with hostname, ip_addresses, protocol_version
        """
        import socket

        hostname = socket.gethostname()

        # Get IP addresses using ipconfig
        result = await self.execute_command(
            'ipconfig | findstr /i "IPv4"',
            timeout=10
        )

        ip_addresses = []
        if result['returncode'] == 0:
            for line in result['stdout'].split('\n'):
                if ':' in line:
                    ip = line.split(':')[-1].strip()
                    if ip:
                        ip_addresses.append(ip)

        return self._create_response({
            'hostname': hostname,
            'ip_addresses': ip_addresses
        })

    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get Windows resource usage.

        Returns:
            Dict with cpu_percent, memory_percent, disk_percent, protocol_version
        """
        try:
            # CPU usage
            cpu_result = await self.execute_command(
                'wmic cpu get loadpercentage /value',
                timeout=10
            )
            cpu_percent = 0.0
            if cpu_result['returncode'] == 0:
                for line in cpu_result['stdout'].split('\n'):
                    if 'LoadPercentage=' in line:
                        cpu_percent = float(line.split('=')[-1].strip())

            # Memory usage
            mem_result = await self.execute_command(
                'wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value',
                timeout=10
            )
            memory_percent = 0.0
            if mem_result['returncode'] == 0:
                free = 0
                total = 0
                for line in mem_result['stdout'].split('\n'):
                    if 'FreePhysicalMemory=' in line:
                        free = int(line.split('=')[-1].strip())
                    elif 'TotalVisibleMemorySize=' in line:
                        total = int(line.split('=')[-1].strip())
                if total > 0:
                    memory_percent = ((total - free) / total) * 100

            # Disk usage
            disk_result = await self.execute_command(
                'wmic logicaldisk get size,freespace,caption /value',
                timeout=10
            )
            disk_percent = 0.0
            if disk_result['returncode'] == 0:
                # Parse first disk
                free = 0
                total = 0
                for line in disk_result['stdout'].split('\n'):
                    if 'FreeSpace=' in line:
                        free = int(line.split('=')[-1].strip())
                    elif 'Size=' in line:
                        total = int(line.split('=')[-1].strip())
                if total > 0:
                    disk_percent = ((total - free) / total) * 100

            return self._create_response({
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent
            })

        except Exception as e:
            return self._create_response({
                'cpu_percent': 0.0,
                'memory_percent': 0.0,
                'disk_percent': 0.0,
                'error': str(e)
            })

    async def path_exists(self, path: str) -> bool:
        """Check if path exists on Windows.

        Args:
            path: Path to check

        Returns:
            bool: True if path exists
        """
        return Path(path).exists()

    async def create_directory(
        self, 
        path: str, 
        parents: bool = True,
        mode: int = 0o755
    ) -> bool:
        """Create directory on Windows.

        Args:
            path: Directory path
            parents: Create parent directories if needed
            mode: Directory permissions (ignored on Windows)

        Returns:
            bool: True if successful
        """
        try:
            p = Path(path)
            if parents:
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.mkdir(exist_ok=True)
            return True
        except Exception:
            return False

    async def get_environment_variables(self) -> Dict[str, str]:
        """Get all Windows environment variables.

        Returns:
            Dict of environment variables
        """
        import os
        return dict(os.environ)

    async def set_environment_variable(
        self, 
        key: str, 
        value: str,
        persistent: bool = False
    ) -> bool:
        """Set environment variable on Windows.

        Args:
            key: Variable name
            value: Variable value
            persistent: Make persistent (set in registry)

        Returns:
            bool: True if successful
        """
        import os
        os.environ[key] = value

        if persistent:
            # Set in user environment via setx
            result = await self.execute_command(
                f'setx {key} "{value}"',
                timeout=10
            )
            return result['returncode'] == 0

        return True

    async def get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes on Windows.

        Returns:
            List of process info dicts
        """
        result = await self.execute_command(
            'tasklist /fo csv /nh',
            timeout=30
        )

        processes = []
        if result['returncode'] == 0:
            for line in result['stdout'].split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        processes.append({
                            'name': parts[0].strip('"'),
                            'pid': int(parts[1].strip('"')),
                            'protocol_version': self.protocol_version
                        })

        return processes

    async def kill_process(self, pid: int) -> bool:
        """Kill process on Windows.

        Args:
            pid: Process ID

        Returns:
            bool: True if successful
        """
        result = await self.execute_command(
            f'taskkill /pid {pid} /f',
            timeout=10
        )
        return result['returncode'] == 0
