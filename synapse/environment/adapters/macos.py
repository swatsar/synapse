"""
macOS Environment Adapter.

Protocol Version: 1.0
Spec Version: 3.1
"""

import asyncio
import platform
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

from synapse.environment.adapters.base import EnvironmentAdapter, PROTOCOL_VERSION


class MacOSAdapter(EnvironmentAdapter):
    """macOS-specific environment adapter.

    Handles macOS-specific paths, zsh commands,
    launchd service management, and macOS resource monitoring.
    """

    def __init__(self):
        self._platform = "Darwin"
        self._shell = "zsh"

    async def get_home_dir(self) -> Path:
        """Get macOS user home directory.

        Returns:
            Path: User home directory (e.g., /Users/username)
        """
        import os
        return Path.home()

    async def get_config_dir(self) -> Path:
        """Get macOS config directory.

        Returns:
            Path: ~/Library/Application Support/Synapse directory
        """
        import os
        return Path.home() / 'Library' / 'Application Support' / 'Synapse'

    async def get_data_dir(self) -> Path:
        """Get macOS data directory.

        Returns:
            Path: ~/Library/Application Support/Synapse/Data directory
        """
        import os
        return Path.home() / 'Library' / 'Application Support' / 'Synapse' / 'Data'

    async def get_temp_dir(self) -> Path:
        """Get macOS temp directory.

        Returns:
            Path: /tmp directory (or TMPDIR)
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
        """Execute command using zsh.

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
        """Get macOS system information.

        Returns:
            Dict with os, version, architecture, protocol_version
        """
        # Get macOS version using sw_vers
        result = await self.execute_command('sw_vers', timeout=10)

        version_info = {}
        if result['returncode'] == 0:
            for line in result['stdout'].split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    version_info[key.strip().lower().replace(' ', '_')] = value.strip()

        return self._create_response({
            'os': 'macOS',
            'name': version_info.get('productname', 'macOS'),
            'version': version_info.get('productversion', platform.version()),
            'build': version_info.get('buildversion', ''),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'hostname': platform.node()
        })

    async def get_network_info(self) -> Dict[str, Any]:
        """Get macOS network information.

        Returns:
            Dict with hostname, ip_addresses, protocol_version
        """
        import socket

        hostname = socket.gethostname()

        # Get IP addresses using ifconfig
        result = await self.execute_command(
            "ifconfig | grep \"inet \" | grep -v 127.0.0.1 | awk \"{print $2}\"",
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
        """Get macOS resource usage.

        Returns:
            Dict with cpu_percent, memory_percent, disk_percent, protocol_version
        """
        try:
            # CPU usage using top
            cpu_result = await self.execute_command(
                "top -l 1 | grep \"CPU usage\" | awk \"{print $3}\" | cut -d% -f1",
                timeout=10
            )
            cpu_percent = 0.0
            if cpu_result['returncode'] == 0:
                try:
                    cpu_percent = float(cpu_result['stdout'].strip())
                except:
                    pass

            # Memory usage using vm_stat
            mem_result = await self.execute_command(
                "vm_stat | head -10",
                timeout=10
            )
            memory_percent = 0.0
            if mem_result['returncode'] == 0:
                # Parse vm_stat output
                pages_free = 0
                pages_total = 0
                for line in mem_result['stdout'].split('\n'):
                    if 'Pages free' in line:
                        pages_free = int(line.split(':')[1].strip().rstrip('.'))
                    elif 'Pages active' in line or 'Pages inactive' in line:
                        pages_total += int(line.split(':')[1].strip().rstrip('.'))

                # Calculate percentage (page size is typically 4096 bytes)
                if pages_total > 0:
                    memory_percent = (pages_total / (pages_total + pages_free)) * 100

            # Disk usage using df
            disk_result = await self.execute_command(
                "df -h / | tail -1 | awk \"{print $5}\" | cut -d% -f1",
                timeout=10
            )
            disk_percent = 0.0
            if disk_result['returncode'] == 0:
                try:
                    disk_percent = float(disk_result['stdout'].strip())
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
        """Check if path exists on macOS.

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
        """Create directory on macOS.

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
        """Get all macOS environment variables.

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
        """Set environment variable on macOS.

        Args:
            key: Variable name
            value: Variable value
            persistent: Make persistent (add to ~/.zshrc or ~/.profile)

        Returns:
            bool: True if successful
        """
        import os
        os.environ[key] = value

        if persistent:
            # Add to ~/.zshrc
            home = str(Path.home())
            zshrc = Path(home) / '.zshrc'

            try:
                with open(zshrc, 'a') as f:
                    f.write(f'\nexport {key}="{value}"\n')
                return True
            except:
                return False

        return True

    async def get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes on macOS.

        Returns:
            List of process info dicts
        """
        result = await self.execute_command(
            "ps aux -r | head -20 | awk \"{print $1,$2,$3,$4,$11}\"",
            timeout=30
        )

        processes = []
        if result['returncode'] == 0:
            lines = result['stdout'].strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 5:
                    processes.append({
                        'user': parts[0],
                        'pid': int(parts[1]),
                        'cpu': float(parts[2]),
                        'memory': float(parts[3]),
                        'command': parts[4]
                    })

        return processes

    async def kill_process(self, pid: int) -> bool:
        """Kill process on macOS.

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
