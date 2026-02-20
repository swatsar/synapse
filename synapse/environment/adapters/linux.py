"""
Linux Environment Adapter.

Protocol Version: 1.0
Spec Version: 3.1
"""

import asyncio
import platform
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

from synapse.environment.adapters.base import EnvironmentAdapter, PROTOCOL_VERSION


class LinuxAdapter(EnvironmentAdapter):
    """Linux-specific environment adapter.

    Handles Linux-specific paths, bash commands,
    systemd service management, and Linux resource monitoring.
    """

    def __init__(self):
        self._platform = "Linux"
        self._shell = "bash"

    async def get_home_dir(self) -> Path:
        """Get Linux user home directory.

        Returns:
            Path: User home directory (e.g., /home/username)
        """
        import os
        return Path.home()

    async def get_config_dir(self) -> Path:
        """Get Linux config directory.

        Returns:
            Path: ~/.config/synapse directory
        """
        import os
        xdg_config = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        return Path(xdg_config) / 'synapse'

    async def get_data_dir(self) -> Path:
        """Get Linux data directory.

        Returns:
            Path: ~/.local/share/synapse directory
        """
        import os
        xdg_data = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))
        return Path(xdg_data) / 'synapse'

    async def get_temp_dir(self) -> Path:
        """Get Linux temp directory.

        Returns:
            Path: /tmp directory
        """
        import os
        return Path(os.environ.get('TMPDIR', '/tmp'))

    async def execute_command(
        self, 
        command: str, 
        timeout: int = 60,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute command using bash.

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
                shell=True,
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
                'stderr': f'timeout: command timed out after {timeout} seconds',
                'returncode': -1
            })
        except Exception as e:
            return self._create_response({
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            })

    async def get_os_info(self) -> Dict[str, Any]:
        """Get Linux system information.

        Returns:
            Dict with os, version, architecture, protocol_version
        """
        # Get distro info
        distro_info = {}

        # Try /etc/os-release
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        distro_info[key.lower()] = value.strip('"')
        except:
            pass

        return self._create_response({
            'os': 'Linux',
            'distro': distro_info.get('name', 'Unknown'),
            'version': distro_info.get('version_id', platform.version()),
            'kernel': platform.release(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'hostname': platform.node()
        })

    async def get_network_info(self) -> Dict[str, Any]:
        """Get Linux network information.

        Returns:
            Dict with hostname, ip_addresses, protocol_version
        """
        import socket

        hostname = socket.gethostname()

        # Get IP addresses using ip command
        result = await self.execute_command(
            "ip -4 addr show | grep inet | awk \"{print $2}\" | cut -d/ -f1",
            timeout=10
        )

        ip_addresses = []
        if result['returncode'] == 0:
            for line in result['stdout'].split('\n'):
                line = line.strip()
                if line:
                    ip_addresses.append(line)

        return self._create_response({
            'hostname': hostname,
            'ip_addresses': ip_addresses
        })

    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get Linux resource usage.

        Returns:
            Dict with cpu_percent, memory_percent, disk_percent, protocol_version
        """
        try:
            # CPU usage (from /proc/stat)
            cpu_percent = 0.0
            try:
                result = await self.execute_command(
                    "top -bn1 | grep \"Cpu(s)\" | awk \"{print $2}\" | cut -d% -f1",
                    timeout=10
                )
                if result['returncode'] == 0:
                    cpu_percent = float(result['stdout'].strip())
            except:
                pass

            # Memory usage (from /proc/meminfo)
            memory_percent = 0.0
            try:
                result = await self.execute_command(
                    "free | grep Mem | awk \"{print ($3/$2) * 100.0}\"",
                    timeout=10
                )
                if result['returncode'] == 0:
                    memory_percent = float(result['stdout'].strip())
            except:
                pass

            # Disk usage
            disk_percent = 0.0
            try:
                result = await self.execute_command(
                    "df -h / | tail -1 | awk \"{print $5}\" | cut -d% -f1",
                    timeout=10
                )
                if result['returncode'] == 0:
                    disk_percent = float(result['stdout'].strip())
            except:
                pass

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
        """Check if path exists on Linux.

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
        """Create directory on Linux.

        Args:
            path: Directory path
            parents: Create parent directories if needed
            mode: Directory permissions

        Returns:
            bool: True if successful
        """
        try:
            p = Path(path)
            if parents:
                p.mkdir(parents=True, exist_ok=True, mode=mode)
            else:
                p.mkdir(exist_ok=True, mode=mode)
            return True
        except Exception:
            return False

    async def get_environment_variables(self) -> Dict[str, str]:
        """Get all Linux environment variables.

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
        """Set environment variable on Linux.

        Args:
            key: Variable name
            value: Variable value
            persistent: Make persistent (add to ~/.bashrc or ~/.profile)

        Returns:
            bool: True if successful
        """
        import os
        os.environ[key] = value

        if persistent:
            # Add to ~/.bashrc
            home = str(Path.home())
            bashrc = Path(home) / '.bashrc'

            try:
                with open(bashrc, 'a') as f:
                    f.write(f'\nexport {key}="{value}"\n')
                return True
            except:
                return False

        return True

    async def get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes on Linux.

        Returns:
            List of process info dicts
        """
        # Use ps with simpler format
        result = await self.execute_command(
            "ps -eo pid,comm --no-headers | head -20",
            timeout=30
        )

        processes = []
        if result['returncode'] == 0:
            for line in result['stdout'].strip().split('\n'):
                line = line.strip()
                if line:
                    parts = line.split(None, 1)  # Split on whitespace
                    if len(parts) >= 2:
                        try:
                            processes.append({
                                'pid': int(parts[0]),
                                'name': parts[1],
                                'protocol_version': self.protocol_version
                            })
                        except (ValueError, IndexError):
                            continue

        return processes

    async def kill_process(self, pid: int) -> bool:
        """Kill process on Linux.

        Args:
            pid: Process ID

        Returns:
            bool: True if successful
        """
        result = await self.execute_command(
            f'kill -9 {pid}',
            timeout=10
        )
        return result['returncode'] == 0
