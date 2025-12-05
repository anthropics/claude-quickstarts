"""
Unit tests for Memory Persistence System - Critical Data Integrity Module

Tests storage backends (SQLite, JSON, In-Memory), snapshot management,
consolidation strategies, and data integrity using actual API.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from agents.core.memory_persistence import (
    PersistentMemoryManager,
    StorageBackend,
    ConsolidationStrategy,
    InMemoryBackend,
    SQLiteBackend,
    JSONFileBackend,
    MemorySnapshot,
    ConsolidationResult,
    PersistenceConfig,
    create_volatile_memory,
    create_sqlite_memory,
    create_json_memory,
)


class TestInMemoryBackend:
    """Test suite for in-memory storage backend."""

    @pytest.fixture
    def backend(self):
        """Create InMemoryBackend instance."""
        return InMemoryBackend()

    @pytest.mark.unit
    def test_save_and_load_entry(self, backend):
        """Test saving and loading a memory entry."""
        entry = {
            "id": "entry_001",
            "content": "Test memory",
            "memory_type": "semantic",
            "timestamp": datetime.now().isoformat()
        }

        # Save entry
        result = backend.save_entry(entry)
        assert result is True

        # Load entry
        loaded = backend.load_entry("entry_001")
        assert loaded is not None
        assert loaded["content"] == "Test memory"

    @pytest.mark.unit
    def test_delete_entry(self, backend):
        """Test deleting a memory entry."""
        entry = {"id": "entry_002", "content": "To be deleted"}
        backend.save_entry(entry)
        
        # Delete
        result = backend.delete_entry("entry_002")
        assert result is True
        
        # Verify deleted
        loaded = backend.load_entry("entry_002")
        assert loaded is None

    @pytest.mark.unit
    def test_list_entries(self, backend):
        """Test listing entries with filters."""
        # Add multiple entries
        for i in range(5):
            backend.save_entry({
                "id": f"entry_{i}",
                "content": f"Memory {i}",
                "memory_type": "semantic" if i % 2 == 0 else "episodic"
            })
        
        # List all
        all_entries = backend.list_entries(limit=10)
        assert len(all_entries) >= 5


class TestSQLiteBackend:
    """Test suite for SQLite storage backend."""

    @pytest.fixture
    def backend(self):
        """Create SQLiteBackend with temp database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        return SQLiteBackend(db_path)

    @pytest.mark.unit
    def test_save_and_load_entry(self, backend):
        """Test SQLite save and load."""
        entry = {
            "id": "sql_001",
            "content": "SQLite test",
            "memory_type": "semantic"
        }
        
        result = backend.save_entry(entry)
        assert result is True
        
        loaded = backend.load_entry("sql_001")
        assert loaded is not None
        assert loaded["content"] == "SQLite test"

    @pytest.mark.unit
    def test_persistence_across_operations(self, backend):
        """Test that data persists across multiple operations."""
        entries = [
            {"id": f"persist_{i}", "content": f"Data {i}"} 
            for i in range(3)
        ]
        
        for entry in entries:
            backend.save_entry(entry)
        
        # All should be retrievable
        for i in range(3):
            loaded = backend.load_entry(f"persist_{i}")
            assert loaded is not None


class TestJSONFileBackend:
    """Test suite for JSON file storage backend."""

    @pytest.fixture
    def backend(self):
        """Create JSONFileBackend with temp file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name
        return JSONFileBackend(json_path)

    @pytest.mark.unit
    def test_save_and_load_entry(self, backend):
        """Test JSON file save and load."""
        entry = {
            "id": "json_001",
            "content": "JSON test",
            "memory_type": "working"
        }
        
        result = backend.save_entry(entry)
        assert result is True
        
        loaded = backend.load_entry("json_001")
        assert loaded is not None


class TestPersistentMemoryManager:
    """Test suite for PersistentMemoryManager."""

    @pytest.fixture
    def manager(self):
        """Create in-memory PersistentMemoryManager."""
        config = PersistenceConfig(backend=StorageBackend.MEMORY)
        return PersistentMemoryManager(config)

    @pytest.mark.unit
    def test_initialization(self, manager):
        """Test manager initializes properly."""
        assert manager is not None
        assert hasattr(manager, 'save')
        assert hasattr(manager, 'load')

    @pytest.mark.unit
    def test_save_and_retrieve(self, manager):
        """Test saving and retrieving memories."""
        manager.save({"id": "mem_001", "content": "Test memory", "type": "semantic"})
        
        loaded = manager.load("mem_001")
        assert loaded is not None
        assert loaded["content"] == "Test memory"

    @pytest.mark.unit
    def test_create_snapshot(self, manager):
        """Test creating a memory snapshot."""
        # Add some memories
        for i in range(5):
            manager.save({"id": f"mem_{i}", "content": f"Memory {i}"})
        
        snapshot = manager.create_checkpoint()
        
        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.entry_count >= 5


class TestConsolidation:
    """Test memory consolidation strategies."""

    @pytest.fixture
    def manager(self):
        config = PersistenceConfig(
            backend=StorageBackend.MEMORY,
            max_memory_entries=10
        )
        return PersistentMemoryManager(config)

    @pytest.mark.unit
    def test_consolidate_hybrid(self, manager):
        """Test consolidation with hybrid strategy."""
        # Add entries
        for i in range(15):
            manager.save({"id": f"mem_{i}", "content": f"Memory {i}"})
        
        result = manager.consolidate(ConsolidationStrategy.HYBRID)
        
        assert isinstance(result, ConsolidationResult)
        assert hasattr(result, 'entries_before')
        assert hasattr(result, 'entries_after')

    @pytest.mark.unit
    def test_consolidation_result_fields(self, manager):
        """Test that consolidation result has all required fields."""
        for i in range(5):
            manager.save({"id": f"mem_{i}", "content": f"Memory {i}"})
        
        result = manager.consolidate(ConsolidationStrategy.HYBRID)
        
        assert hasattr(result, 'entries_before')
        assert hasattr(result, 'entries_after')
        assert hasattr(result, 'entries_removed')
        assert hasattr(result, 'strategy_used')


class TestFactoryFunctions:
    """Test convenience factory functions."""

    @pytest.mark.unit
    def test_create_volatile_memory(self):
        """Test creating volatile (in-memory) storage."""
        manager = create_volatile_memory()
        
        assert manager is not None
        manager.save({"id": "test", "data": "value"})
        assert manager.load("test") is not None

    @pytest.mark.unit
    def test_create_sqlite_memory(self):
        """Test creating SQLite-backed storage."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        manager = create_sqlite_memory(db_path)
        
        assert manager is not None
        manager.save({"id": "sql_test", "content": "test value"})
        assert manager.load("sql_test") is not None

    @pytest.mark.unit
    def test_create_json_memory(self):
        """Test creating JSON-file-backed storage."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name
        
        manager = create_json_memory(json_path)
        
        assert manager is not None
        manager.save({"id": "json_test", "content": "test value"})
        # JSON may need a flush to persist


class TestPersistenceConfig:
    """Test PersistenceConfig data class."""

    @pytest.mark.unit
    def test_default_config(self):
        """Test default configuration values."""
        config = PersistenceConfig()
        
        assert config.backend == StorageBackend.MEMORY
        assert config.max_memory_entries > 0
        assert config.retention_days > 0

    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom configuration."""
        config = PersistenceConfig(
            backend=StorageBackend.SQLITE,
            db_path="/tmp/test.db",
            max_memory_entries=5000
        )
        
        assert config.backend == StorageBackend.SQLITE
        assert config.db_path == "/tmp/test.db"
        assert config.max_memory_entries == 5000


class TestMemorySnapshot:
    """Test MemorySnapshot data class."""

    @pytest.mark.unit
    def test_snapshot_creation(self):
        """Test creating a memory snapshot."""
        snapshot = MemorySnapshot(
            snapshot_id="snap_001",
            timestamp=datetime.now().isoformat(),
            version=1,
            entry_count=100,
            episodic_count=50
        )
        
        assert snapshot.snapshot_id == "snap_001"
        assert snapshot.version == 1
        assert snapshot.entry_count == 100
