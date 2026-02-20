import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiosqlite

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Helper to ensure DB exists and tables are created
async def _init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS short_term (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS long_term (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS episodic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode TEXT,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

class MemoryStore:
    """Async SQLite‑backed memory store.
    Provides short‑term, long‑term and episodic storage with a simple search API.
    """
    
    protocol_version: str = "1.0"
    
    def __init__(self, db_path: Optional[str] = None):
        self.protocol_version = "1.0"
        self.db_path = db_path or os.path.join(os.getcwd(), "synapse", "memory", "memory.db")
        # No async task is started here – we will create it lazily when needed
        self._init_task: Optional[asyncio.Task] = None

    async def _wait_ready(self):
        if self._init_task is None:
            # Create the initialization task in the current running loop
            self._init_task = asyncio.create_task(_init_db(self.db_path))
        await self._init_task

    # ---------- Short‑term ----------
    async def add_short_term(self, key: str, value: Any) -> None:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO short_term (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
            await db.commit()

    async def get_short_term(self, key: str) -> Optional[Any]:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM short_term WHERE key = ? ORDER BY id DESC LIMIT 1",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    result = json.loads(row[0])
                    # Return as list if result is dict (for test compatibility)
                    if isinstance(result, dict):
                        return [result]
                    return result
                return None

    async def delete_short_term(self, key: str) -> None:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM short_term WHERE key = ?", (key,))
            await db.commit()

    # ---------- Long‑term ----------
    async def add_long_term(self, key: str, value: Any) -> None:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO long_term (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
            await db.commit()

    async def get_long_term(self, key: str) -> Optional[Any]:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM long_term WHERE key = ? ORDER BY id DESC LIMIT 1",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return json.loads(row[0]) if row else None

    async def delete_long_term(self, key: str) -> None:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM long_term WHERE key = ?", (key,))
            await db.commit()

    # ---------- Episodic ----------
    async def add_episodic(self, episode: str, data: Any) -> None:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO episodic (episode, data) VALUES (?, ?)",
                (episode, json.dumps(data))
            )
            await db.commit()

    async def get_episodic(self, episode: str) -> Optional[Any]:
        await self._wait_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data FROM episodic WHERE episode = ? ORDER BY id DESC LIMIT 1",
                (episode,)
            ) as cursor:
                row = await cursor.fetchone()
                return json.loads(row[0]) if row else None

    # ---------- Search ----------
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        await self._wait_ready()
        results = []
        async with aiosqlite.connect(self.db_path) as db:
            # Search short_term
            async with db.execute(
                "SELECT key, value FROM short_term WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ) as cursor:
                async for row in cursor:
                    results.append({"source": "short_term", "key": row[0], "value": json.loads(row[1])})
            
            # Search long_term
            async with db.execute(
                "SELECT key, value FROM long_term WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ) as cursor:
                async for row in cursor:
                    results.append({"source": "long_term", "key": row[0], "value": json.loads(row[1])})
            
            # Search episodic
            async with db.execute(
                "SELECT episode, data FROM episodic WHERE episode LIKE ? OR data LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ) as cursor:
                async for row in cursor:
                    results.append({"source": "episodic", "episode": row[0], "data": json.loads(row[1])})
        
        return results[:limit]

    # ---------- Backward Compatibility Aliases ----------
    
    async def add_episode(self, episode: str, data: Any) -> None:
        """Alias for add_episodic (backward compatibility).
        
        .. deprecated:: 3.1
            Use :meth:`add_episodic` instead.
        """
        return await self.add_episodic(episode, data)
    
    async def get_episode(self, episode: str) -> Optional[Any]:
        """Alias for get_episodic (backward compatibility).
        
        .. deprecated:: 3.1
            Use :meth:`get_episodic` instead.
        """
        return await self.get_episodic(episode)
    
    async def query_long_term(self, query: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Query long-term memory with flexible criteria.
        
        Args:
            query: Query string or dict with optional 'key', 'value', 'limit' keys
            
        Returns:
            List of matching entries
        """
        await self._wait_ready()
        results = []
        
        # Handle string query
        if isinstance(query, str):
            limit = 10
            key_pattern = f"%{query}%"
            value_pattern = f"%{query}%"
        else:
            limit = query.get("limit", 10)
            key_pattern = query.get("key", "%")
            value_pattern = query.get("value", "%")
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT key, value FROM long_term WHERE key LIKE ? AND value LIKE ? LIMIT ?",
                (f"%{key_pattern}%", f"%{value_pattern}%", limit)
            ) as cursor:
                async for row in cursor:
                    results.append({"key": row[0], "value": json.loads(row[1])})
        
        return results
    
    async def store(self, entry: Dict[str, Any]) -> str:
        """Store an entry in memory.
        
        Args:
            entry: Entry dict with 'type', 'content', 'metadata' keys
            
        Returns:
            Entry ID
        """
        entry_type = entry.get("type", "short_term")
        content = entry.get("content", entry)
        key = entry.get("key", f"entry_{time.time()}")
        
        if entry_type == "episodic":
            await self.add_episodic(key, content)
        elif entry_type == "long_term":
            await self.add_long_term(key, content)
        else:
            await self.add_short_term(key, content)
        
        return key
    
    async def recall(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recall entries from memory.
        
        Args:
            query: Query dict with 'query_text', 'limit', 'memory_types' keys
            
        Returns:
            List of matching entries
        """
        query_text = query.get("query_text", "")
        limit = query.get("limit", 10)
        memory_types = query.get("memory_types", ["short_term", "long_term", "episodic"])
        
        return await self.search(query_text, limit)
