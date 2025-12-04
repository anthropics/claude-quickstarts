"""
Memory Persistence System - Phase 2 Enhancement

Provides persistent storage backends for the memory system:
- SQLite backend for durable storage
- JSON checkpoint/restore
- Memory consolidation and cleanup
- Version-controlled memory snapshots
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path
import json
import sqlite3
import hashlib
import threading
import time


class StorageBackend(Enum):
    """Available storage backends."""
    MEMORY = "memory"
    SQLITE = "sqlite"
    JSON_FILE = "json_file"


class ConsolidationStrategy(Enum):
    """Strategies for memory consolidation."""
    RECENT_PRIORITY = "recent_priority"  # Keep most recent
    ACCESS_FREQUENCY = "access_frequency"  # Keep most accessed
    IMPORTANCE_WEIGHTED = "importance_weighted"  # Keep highest importance
    HYBRID = "hybrid"  # Combination of factors


@dataclass
class MemorySnapshot:
    """A point-in-time snapshot of memory state."""
    snapshot_id: str
    timestamp: str
    version: int
    entry_count: int
    episodic_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""


@dataclass
class ConsolidationResult:
    """Result of a memory consolidation operation."""
    entries_before: int
    entries_after: int
    entries_removed: int
    entries_merged: int
    strategy_used: ConsolidationStrategy
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PersistenceConfig:
    """Configuration for persistence layer."""
    backend: StorageBackend = StorageBackend.MEMORY
    db_path: Optional[str] = None
    auto_checkpoint_interval_s: int = 300  # 5 minutes
    max_memory_entries: int = 10000
    consolidation_threshold: float = 0.8  # Consolidate at 80% capacity
    retention_days: int = 30
    enable_versioning: bool = True
    max_snapshots: int = 10


class PersistenceBackend(ABC):
    """Abstract base class for persistence backends."""
    
    @abstractmethod
    def save_entry(self, entry: Dict[str, Any]) -> bool:
        """Save a memory entry."""
        pass
    
    @abstractmethod
    def load_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Load a memory entry by ID."""
        pass
    
    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        pass
    
    @abstractmethod
    def list_entries(
        self, 
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List memory entries with optional filtering."""
        pass
    
    @abstractmethod
    def save_episodic(self, episodic: Dict[str, Any]) -> bool:
        """Save an episodic memory."""
        pass
    
    @abstractmethod
    def load_episodic(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Load an episodic memory."""
        pass
    
    @abstractmethod
    def count_entries(self) -> int:
        """Count total entries."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all data."""
        pass


class InMemoryBackend(PersistenceBackend):
    """Simple in-memory storage (for testing and development)."""
    
    def __init__(self):
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.episodics: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def save_entry(self, entry: Dict[str, Any]) -> bool:
        with self._lock:
            self.entries[entry["id"]] = entry
            return True
    
    def load_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.entries.get(entry_id)
    
    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            if entry_id in self.entries:
                del self.entries[entry_id]
                return True
            return False
    
    def list_entries(
        self, 
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._lock:
            entries = list(self.entries.values())
            if memory_type:
                entries = [e for e in entries if e.get("memory_type") == memory_type]
            return entries[offset:offset + limit]
    
    def save_episodic(self, episodic: Dict[str, Any]) -> bool:
        with self._lock:
            self.episodics[episodic["query_id"]] = episodic
            return True
    
    def load_episodic(self, query_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.episodics.get(query_id)
    
    def count_entries(self) -> int:
        with self._lock:
            return len(self.entries)
    
    def clear(self) -> None:
        with self._lock:
            self.entries.clear()
            self.episodics.clear()


class SQLiteBackend(PersistenceBackend):
    """SQLite-based persistent storage."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                keywords TEXT,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                importance REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS episodic_memories (
                query_id TEXT PRIMARY KEY,
                query_text TEXT NOT NULL,
                reasoning_steps TEXT,
                tools_used TEXT,
                outcome TEXT NOT NULL,
                confidence REAL,
                feedback TEXT,
                timestamp TEXT NOT NULL,
                duration_ms REAL DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                version INTEGER NOT NULL,
                entry_count INTEGER,
                episodic_count INTEGER,
                metadata TEXT,
                checksum TEXT,
                data BLOB
            );
            
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(memory_type);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memory_entries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_importance ON memory_entries(importance);
            CREATE INDEX IF NOT EXISTS idx_outcome ON episodic_memories(outcome);
        """)
        conn.commit()
    
    def save_entry(self, entry: Dict[str, Any]) -> bool:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO memory_entries 
                (id, memory_type, content, embedding, keywords, metadata, 
                 timestamp, access_count, last_accessed, importance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["id"],
                entry.get("memory_type", "fact"),
                entry["content"],
                json.dumps(entry.get("embedding")) if entry.get("embedding") else None,
                json.dumps(entry.get("keywords", [])),
                json.dumps(entry.get("metadata", {})),
                entry.get("timestamp", datetime.now().isoformat()),
                entry.get("access_count", 0),
                entry.get("last_accessed"),
                entry.get("importance", 0.5)
            ))
            conn.commit()
            return True
        except sqlite3.Error:
            return False
    
    def load_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM memory_entries WHERE id = ?", 
            (entry_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_entry(row)
        return None
    
    def _row_to_entry(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to entry dict."""
        return {
            "id": row["id"],
            "memory_type": row["memory_type"],
            "content": row["content"],
            "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
            "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "timestamp": row["timestamp"],
            "access_count": row["access_count"],
            "last_accessed": row["last_accessed"],
            "importance": row.get("importance", 0.5)
        }
    
    def delete_entry(self, entry_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM memory_entries WHERE id = ?", 
            (entry_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    
    def list_entries(
        self, 
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if memory_type:
            cursor = conn.execute(
                """SELECT * FROM memory_entries 
                   WHERE memory_type = ? 
                   ORDER BY timestamp DESC 
                   LIMIT ? OFFSET ?""",
                (memory_type, limit, offset)
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM memory_entries 
                   ORDER BY timestamp DESC 
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            )
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def save_episodic(self, episodic: Dict[str, Any]) -> bool:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO episodic_memories 
                (query_id, query_text, reasoning_steps, tools_used, 
                 outcome, confidence, feedback, timestamp, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episodic["query_id"],
                episodic["query_text"],
                json.dumps(episodic.get("reasoning_steps", [])),
                json.dumps(episodic.get("tools_used", [])),
                episodic["outcome"],
                episodic.get("confidence", 0.5),
                episodic.get("feedback"),
                episodic.get("timestamp", datetime.now().isoformat()),
                episodic.get("duration_ms", 0)
            ))
            conn.commit()
            return True
        except sqlite3.Error:
            return False
    
    def load_episodic(self, query_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM episodic_memories WHERE query_id = ?", 
            (query_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "query_id": row["query_id"],
                "query_text": row["query_text"],
                "reasoning_steps": json.loads(row["reasoning_steps"]) if row["reasoning_steps"] else [],
                "tools_used": json.loads(row["tools_used"]) if row["tools_used"] else [],
                "outcome": row["outcome"],
                "confidence": row["confidence"],
                "feedback": row["feedback"],
                "timestamp": row["timestamp"],
                "duration_ms": row["duration_ms"]
            }
        return None
    
    def count_entries(self) -> int:
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM memory_entries")
        return cursor.fetchone()[0]
    
    def clear(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM memory_entries")
        conn.execute("DELETE FROM episodic_memories")
        conn.commit()
    
    def get_entries_by_importance(
        self, 
        min_importance: float = 0.0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get entries above importance threshold."""
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT * FROM memory_entries 
               WHERE importance >= ? 
               ORDER BY importance DESC, access_count DESC 
               LIMIT ?""",
            (min_importance, limit)
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def get_stale_entries(
        self, 
        days_threshold: int = 30,
        access_threshold: int = 2
    ) -> List[str]:
        """Get IDs of entries that are old and rarely accessed."""
        conn = self._get_conn()
        cutoff_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()
        cursor = conn.execute(
            """SELECT id FROM memory_entries 
               WHERE timestamp < ? AND access_count <= ?
               ORDER BY timestamp ASC""",
            (cutoff_date, access_threshold)
        )
        return [row["id"] for row in cursor.fetchall()]


class JSONFileBackend(PersistenceBackend):
    """JSON file-based storage for portability."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._data = {"entries": {}, "episodics": {}}
        self._lock = threading.Lock()
        self._load()
    
    def _load(self) -> None:
        """Load data from file."""
        if self.file_path.exists():
            with self.file_path.open('r') as f:
                self._data = json.load(f)
    
    def _save(self) -> None:
        """Save data to file."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open('w') as f:
            json.dump(self._data, f, indent=2)
    
    def save_entry(self, entry: Dict[str, Any]) -> bool:
        with self._lock:
            self._data["entries"][entry["id"]] = entry
            self._save()
            return True
    
    def load_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data["entries"].get(entry_id)
    
    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            if entry_id in self._data["entries"]:
                del self._data["entries"][entry_id]
                self._save()
                return True
            return False
    
    def list_entries(
        self, 
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._lock:
            entries = list(self._data["entries"].values())
            if memory_type:
                entries = [e for e in entries if e.get("memory_type") == memory_type]
            # Sort by timestamp
            entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return entries[offset:offset + limit]
    
    def save_episodic(self, episodic: Dict[str, Any]) -> bool:
        with self._lock:
            self._data["episodics"][episodic["query_id"]] = episodic
            self._save()
            return True
    
    def load_episodic(self, query_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data["episodics"].get(query_id)
    
    def count_entries(self) -> int:
        with self._lock:
            return len(self._data["entries"])
    
    def clear(self) -> None:
        with self._lock:
            self._data = {"entries": {}, "episodics": {}}
            self._save()


class MemoryConsolidator:
    """Handles memory consolidation and cleanup."""
    
    def __init__(
        self, 
        backend: PersistenceBackend,
        config: PersistenceConfig
    ):
        self.backend = backend
        self.config = config
    
    def should_consolidate(self) -> bool:
        """Check if consolidation is needed."""
        count = self.backend.count_entries()
        threshold = int(self.config.max_memory_entries * self.config.consolidation_threshold)
        return count >= threshold
    
    def consolidate(
        self, 
        strategy: ConsolidationStrategy = ConsolidationStrategy.HYBRID
    ) -> ConsolidationResult:
        """Perform memory consolidation."""
        start_time = time.time()
        entries_before = self.backend.count_entries()
        entries_removed = 0
        entries_merged = 0
        
        if strategy == ConsolidationStrategy.RECENT_PRIORITY:
            entries_removed = self._consolidate_by_recency()
        elif strategy == ConsolidationStrategy.ACCESS_FREQUENCY:
            entries_removed = self._consolidate_by_access()
        elif strategy == ConsolidationStrategy.IMPORTANCE_WEIGHTED:
            entries_removed = self._consolidate_by_importance()
        else:  # HYBRID
            entries_removed, entries_merged = self._consolidate_hybrid()
        
        entries_after = self.backend.count_entries()
        duration_ms = (time.time() - start_time) * 1000
        
        return ConsolidationResult(
            entries_before=entries_before,
            entries_after=entries_after,
            entries_removed=entries_removed,
            entries_merged=entries_merged,
            strategy_used=strategy,
            duration_ms=duration_ms
        )
    
    def _consolidate_by_recency(self) -> int:
        """Remove oldest entries beyond retention period."""
        if not isinstance(self.backend, SQLiteBackend):
            return 0
        
        stale_ids = self.backend.get_stale_entries(
            days_threshold=self.config.retention_days
        )
        
        for entry_id in stale_ids:
            self.backend.delete_entry(entry_id)
        
        return len(stale_ids)
    
    def _consolidate_by_access(self) -> int:
        """Remove least accessed entries."""
        entries = self.backend.list_entries(limit=self.config.max_memory_entries * 2)
        
        # Sort by access count
        entries.sort(key=lambda x: x.get("access_count", 0))
        
        # Remove bottom 20%
        remove_count = len(entries) // 5
        removed = 0
        
        for entry in entries[:remove_count]:
            if self.backend.delete_entry(entry["id"]):
                removed += 1
        
        return removed
    
    def _consolidate_by_importance(self) -> int:
        """Remove low importance entries."""
        entries = self.backend.list_entries(limit=self.config.max_memory_entries * 2)
        
        # Sort by importance (low to high)
        entries.sort(key=lambda x: x.get("importance", 0.5))
        
        # Remove entries with importance < 0.3 up to 20%
        remove_count = len(entries) // 5
        removed = 0
        
        for entry in entries:
            if removed >= remove_count:
                break
            if entry.get("importance", 0.5) < 0.3:
                if self.backend.delete_entry(entry["id"]):
                    removed += 1
        
        return removed
    
    def _consolidate_hybrid(self) -> tuple[int, int]:
        """
        Hybrid consolidation combining multiple strategies.
        
        Returns (entries_removed, entries_merged)
        """
        entries = self.backend.list_entries(limit=self.config.max_memory_entries * 2)
        
        # Calculate composite score for each entry
        scored_entries = []
        now = datetime.now()
        
        for entry in entries:
            # Recency score (0-1, higher is more recent)
            try:
                timestamp = datetime.fromisoformat(entry.get("timestamp", now.isoformat()))
                days_old = (now - timestamp).days
                recency_score = max(0, 1 - (days_old / self.config.retention_days))
            except ValueError:
                recency_score = 0.5
            
            # Access score (normalized)
            access_count = entry.get("access_count", 0)
            access_score = min(1.0, access_count / 10)  # Cap at 10 accesses
            
            # Importance score
            importance_score = entry.get("importance", 0.5)
            
            # Composite score (weighted average)
            composite = (
                0.3 * recency_score +
                0.3 * access_score +
                0.4 * importance_score
            )
            
            scored_entries.append((entry, composite))
        
        # Sort by composite score (low to high)
        scored_entries.sort(key=lambda x: x[1])
        
        # Remove bottom 20% with score < 0.4
        remove_count = len(scored_entries) // 5
        removed = 0
        
        for entry, score in scored_entries:
            if removed >= remove_count:
                break
            if score < 0.4:
                if self.backend.delete_entry(entry["id"]):
                    removed += 1
        
        # For now, no merging (could be added later)
        merged = 0
        
        return removed, merged


class SnapshotManager:
    """Manages memory snapshots for versioning and recovery."""
    
    def __init__(
        self, 
        backend: PersistenceBackend,
        config: PersistenceConfig
    ):
        self.backend = backend
        self.config = config
        self.snapshots: List[MemorySnapshot] = []
        self._version = 0
    
    def create_snapshot(self, metadata: Optional[Dict[str, Any]] = None) -> MemorySnapshot:
        """Create a new snapshot of current memory state."""
        self._version += 1
        
        # Gather current state
        entries = self.backend.list_entries(limit=self.config.max_memory_entries)
        entry_count = len(entries)
        
        # Calculate checksum
        content = json.dumps(entries, sort_keys=True)
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        snapshot = MemorySnapshot(
            snapshot_id=f"snapshot_{self._version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            version=self._version,
            entry_count=entry_count,
            episodic_count=0,  # Would need separate count
            metadata=metadata or {},
            checksum=checksum
        )
        
        self.snapshots.append(snapshot)
        
        # Prune old snapshots
        if len(self.snapshots) > self.config.max_snapshots:
            self.snapshots = self.snapshots[-self.config.max_snapshots:]
        
        return snapshot
    
    def list_snapshots(self) -> List[MemorySnapshot]:
        """List all available snapshots."""
        return list(self.snapshots)
    
    def get_snapshot(self, snapshot_id: str) -> Optional[MemorySnapshot]:
        """Get a specific snapshot."""
        for snapshot in self.snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None


class PersistentMemoryManager:
    """
    Main interface for persistent memory management.
    
    Combines backend, consolidation, and snapshot management.
    """
    
    def __init__(self, config: Optional[PersistenceConfig] = None):
        self.config = config or PersistenceConfig()
        self.backend = self._create_backend()
        self.consolidator = MemoryConsolidator(self.backend, self.config)
        self.snapshot_manager = SnapshotManager(self.backend, self.config)
        
        self._checkpoint_thread: Optional[threading.Thread] = None
        self._running = False
    
    def _create_backend(self) -> PersistenceBackend:
        """Create the appropriate backend based on config."""
        if self.config.backend == StorageBackend.SQLITE:
            db_path = self.config.db_path or "memory.db"
            return SQLiteBackend(db_path)
        elif self.config.backend == StorageBackend.JSON_FILE:
            file_path = self.config.db_path or "memory.json"
            return JSONFileBackend(file_path)
        else:
            return InMemoryBackend()
    
    def save(self, entry: Dict[str, Any]) -> bool:
        """Save a memory entry."""
        success = self.backend.save_entry(entry)
        
        # Check if consolidation needed
        if success and self.consolidator.should_consolidate():
            self.consolidator.consolidate()
        
        return success
    
    def load(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Load a memory entry and update access count."""
        entry = self.backend.load_entry(entry_id)
        if entry:
            # Update access tracking
            entry["access_count"] = entry.get("access_count", 0) + 1
            entry["last_accessed"] = datetime.now().isoformat()
            self.backend.save_entry(entry)
        return entry
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        return self.backend.delete_entry(entry_id)
    
    def list_entries(
        self, 
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List memory entries."""
        return self.backend.list_entries(memory_type, limit, offset)
    
    def save_episodic(self, episodic: Dict[str, Any]) -> bool:
        """Save an episodic memory."""
        return self.backend.save_episodic(episodic)
    
    def load_episodic(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Load an episodic memory."""
        return self.backend.load_episodic(query_id)
    
    def create_checkpoint(self) -> MemorySnapshot:
        """Create a checkpoint snapshot."""
        return self.snapshot_manager.create_snapshot(
            metadata={"type": "checkpoint", "trigger": "manual"}
        )
    
    def consolidate(
        self, 
        strategy: ConsolidationStrategy = ConsolidationStrategy.HYBRID
    ) -> ConsolidationResult:
        """Manually trigger consolidation."""
        return self.consolidator.consolidate(strategy)
    
    def start_auto_checkpoint(self) -> None:
        """Start automatic checkpointing in background."""
        if self._running:
            return
        
        self._running = True
        self._checkpoint_thread = threading.Thread(
            target=self._checkpoint_loop,
            daemon=True
        )
        self._checkpoint_thread.start()
    
    def stop_auto_checkpoint(self) -> None:
        """Stop automatic checkpointing."""
        self._running = False
        if self._checkpoint_thread:
            self._checkpoint_thread.join(timeout=1)
    
    def _checkpoint_loop(self) -> None:
        """Background loop for automatic checkpoints."""
        while self._running:
            time.sleep(self.config.auto_checkpoint_interval_s)
            if self._running:
                self.snapshot_manager.create_snapshot(
                    metadata={"type": "checkpoint", "trigger": "auto"}
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return {
            "backend": self.config.backend.value,
            "entry_count": self.backend.count_entries(),
            "max_entries": self.config.max_memory_entries,
            "utilization": self.backend.count_entries() / self.config.max_memory_entries,
            "snapshot_count": len(self.snapshot_manager.snapshots),
            "retention_days": self.config.retention_days,
            "consolidation_threshold": self.config.consolidation_threshold
        }
    
    def export_json(self) -> str:
        """Export all memory to JSON string."""
        entries = self.backend.list_entries(limit=self.config.max_memory_entries)
        return json.dumps({
            "entries": entries,
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats()
        }, indent=2)
    
    def import_json(self, json_str: str) -> int:
        """Import memory from JSON string. Returns count of imported entries."""
        data = json.loads(json_str)
        imported = 0
        for entry in data.get("entries", []):
            if self.backend.save_entry(entry):
                imported += 1
        return imported


# Convenience factory functions

def create_sqlite_memory(db_path: str = "memory.db") -> PersistentMemoryManager:
    """Create a SQLite-backed persistent memory manager."""
    config = PersistenceConfig(
        backend=StorageBackend.SQLITE,
        db_path=db_path
    )
    return PersistentMemoryManager(config)


def create_json_memory(file_path: str = "memory.json") -> PersistentMemoryManager:
    """Create a JSON file-backed persistent memory manager."""
    config = PersistenceConfig(
        backend=StorageBackend.JSON_FILE,
        db_path=file_path
    )
    return PersistentMemoryManager(config)


def create_volatile_memory() -> PersistentMemoryManager:
    """Create an in-memory (non-persistent) memory manager."""
    config = PersistenceConfig(backend=StorageBackend.MEMORY)
    return PersistentMemoryManager(config)
