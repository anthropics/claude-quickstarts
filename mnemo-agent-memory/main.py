#!/usr/bin/env python3
"""
Mnemo - AI Agent Memory System
A lightweight memory system for AI agents with semantic retrieval and auto-routing.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Memory:
    """Represents a stored memory/interaction."""
    id: str
    timestamp: str
    user_input: str
    agent_response: str
    project: str
    embedding: Optional[np.ndarray] = None
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert memory to dictionary."""
        data = asdict(self)
        if self.embedding is not None:
            data['embedding'] = self.embedding.tolist()
        return data


class MemoryStore:
    """SQLite-based persistent storage for memories."""
    
    def __init__(self, db_path: str = "./memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_input TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                project TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project ON memories(project)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
        ''')
        
        conn.commit()
        conn.close()
    
    def store(self, memory: Memory):
        """Store a memory in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        embedding_blob = memory.embedding.tobytes() if memory.embedding is not None else None
        metadata_json = json.dumps(memory.metadata) if memory.metadata else None
        
        cursor.execute('''
            INSERT INTO memories (id, timestamp, user_input, agent_response, project, embedding, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (memory.id, memory.timestamp, memory.user_input, memory.agent_response,
              memory.project, embedding_blob, metadata_json))
        
        conn.commit()
        conn.close()
    
    def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a specific memory by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM memories WHERE id = ?', (memory_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_memory(row)
        return None
    
    def get_by_project(self, project: str, limit: int = 50) -> List[Memory]:
        """Get all memories for a specific project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM memories WHERE project = ? ORDER BY timestamp DESC LIMIT ?
        ''', (project, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_memory(row) for row in rows]
    
    def get_all(self, limit: int = 100) -> List[Memory]:
        """Get all memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_memory(row) for row in rows]
    
    def delete_old_memories(self, days: int):
        """Delete memories older than specified days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM memories WHERE timestamp < ?', (cutoff,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def _row_to_memory(self, row) -> Memory:
        """Convert database row to Memory object."""
        embedding = None
        if row[5]:  # embedding column
            embedding = np.frombuffer(row[5], dtype=np.float32)
        
        metadata = None
        if row[6]:  # metadata column
            metadata = json.loads(row[6])
        
        return Memory(
            id=row[0],
            timestamp=row[1],
            user_input=row[2],
            agent_response=row[3],
            project=row[4],
            embedding=embedding,
            metadata=metadata
        )


class ProjectRouter:
    """Automatically routes content to appropriate projects."""
    
    DEFAULT_RULES = {
        "authentication": ["login", "password", "auth", "jwt", "oauth", "signin", "signup", "session"],
        "frontend": ["css", "html", "react", "vue", "angular", "ui", "component", "style", "layout"],
        "backend": ["api", "database", "server", "endpoint", "route", "middleware", "sql", "nosql"],
        "devops": ["docker", "kubernetes", "k8s", "ci/cd", "pipeline", "deploy", "infrastructure"],
        "testing": ["test", "jest", "pytest", "cypress", "unit test", "integration test"],
        "documentation": ["readme", "docs", "documentation", "wiki", "guide", "tutorial"],
        "general": []  # Default fallback
    }
    
    def __init__(self, custom_rules: Optional[Dict] = None):
        self.rules = custom_rules or self.DEFAULT_RULES
    
    def route(self, content: str) -> str:
        """Determine the project based on content."""
        content_lower = content.lower()
        scores = {}
        
        for project, keywords in self.rules.items():
            if project == "general":
                continue
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                scores[project] = score
        
        if scores:
            return max(scores, key=scores.get)
        return "general"


class AgentMemory:
    """Main memory system for AI agents."""
    
    def __init__(self, db_path: Optional[str] = None, 
                 embedding_model: str = "all-MiniLM-L6-v2",
                 routing_rules: Optional[Dict] = None):
        """
        Initialize the agent memory system.
        
        Args:
            db_path: Path to SQLite database
            embedding_model: Name of the sentence transformer model
            routing_rules: Custom project routing rules
        """
        self.db_path = db_path or os.getenv("MEMORY_DB_PATH", "./memory.db")
        self.store = MemoryStore(self.db_path)
        self.router = ProjectRouter(routing_rules)
        
        # Initialize embedding model
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer(embedding_model)
        print("Model loaded!")
    
    def store_interaction(self, user_input: str, agent_response: str, 
                          project: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> str:
        """
        Store a conversation interaction.
        
        Args:
            user_input: The user's input/message
            agent_response: The agent's response
            project: Optional project tag (auto-detected if not provided)
            metadata: Optional additional metadata
            
        Returns:
            The ID of the stored memory
        """
        # Auto-route if project not specified
        if project is None:
            project = self.router.route(user_input)
        
        # Generate unique ID
        content_hash = hashlib.md5(
            f"{user_input}{agent_response}{datetime.now()}".encode()
        ).hexdigest()[:12]
        memory_id = f"mem_{project}_{content_hash}"
        
        # Generate embedding for the user input
        embedding = self.embedding_model.encode(user_input)
        
        # Create memory object
        memory = Memory(
            id=memory_id,
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            agent_response=agent_response,
            project=project,
            embedding=embedding,
            metadata=metadata
        )
        
        # Store in database
        self.store.store(memory)
        
        return memory_id
    
    def retrieve_relevant(self, query: str, project: Optional[str] = None, 
                          limit: int = 5) -> List[Memory]:
        """
        Retrieve semantically similar memories.
        
        Args:
            query: The search query
            project: Optional project filter
            limit: Maximum number of results
            
        Returns:
            List of relevant memories
        """
        # Get query embedding
        query_embedding = self.embedding_model.encode(query)
        
        # Retrieve candidate memories
        if project:
            candidates = self.store.get_by_project(project, limit=100)
        else:
            candidates = self.store.get_all(limit=100)
        
        # Calculate similarities
        scored_memories = []
        for memory in candidates:
            if memory.embedding is not None:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
                scored_memories.append((similarity, memory))
        
        # Sort by similarity and return top results
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [memory for _, memory in scored_memories[:limit]]
    
    def get_project_memories(self, project: str, limit: int = 50) -> List[Memory]:
        """Get all memories for a specific project."""
        return self.store.get_by_project(project, limit)
    
    def auto_route_project(self, content: str) -> str:
        """Automatically determine project from content."""
        return self.router.route(content)
    
    def get_conversation_history(self, project: Optional[str] = None, 
                                  limit: int = 10) -> List[Dict]:
        """Get formatted conversation history."""
        if project:
            memories = self.store.get_by_project(project, limit)
        else:
            memories = self.store.get_all(limit)
        
        return [
            {
                "role": "user",
                "content": mem.user_input,
                "timestamp": mem.timestamp
            }
            for mem in reversed(memories)
        ] + [
            {
                "role": "assistant", 
                "content": mem.agent_response,
                "timestamp": mem.timestamp
            }
            for mem in reversed(memories)
        ]
    
    def cleanup_old_memories(self, days: int = 30):
        """Remove memories older than specified days."""
        deleted = self.store.delete_old_memories(days)
        print(f"Cleaned up {deleted} old memories")
        return deleted
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


class ClaudeAgentWithMemory:
    """Claude API integration with memory augmentation."""
    
    def __init__(self, api_key: Optional[str] = None, memory: Optional[AgentMemory] = None):
        """
        Initialize Claude agent with memory.
        
        Args:
            api_key: Anthropic API key
            memory: Optional AgentMemory instance
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
        
        self.client = Anthropic(api_key=self.api_key)
        self.memory = memory or AgentMemory()
    
    def chat(self, message: str, project: Optional[str] = None, 
             model: str = "claude-3-haiku-20240307") -> str:
        """
        Chat with Claude using memory-augmented context.
        
        Args:
            message: User message
            project: Optional project context
            model: Claude model to use
            
        Returns:
            Claude's response
        """
        # Auto-route if project not specified
        if project is None:
            project = self.memory.auto_route_project(message)
        
        # Retrieve relevant memories
        relevant_memories = self.memory.retrieve_relevant(message, project, limit=5)
        
        # Build context from memories
        context = self._build_context(relevant_memories)
        
        # Prepare messages
        messages = []
        if context:
            messages.append({
                "role": "user",
                "content": f"Previous context:\n{context}\n\nCurrent message: {message}"
            })
        else:
            messages.append({"role": "user", "content": message})
        
        # Call Claude API
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=messages
        )
        
        agent_response = response.content[0].text
        
        # Store the interaction
        self.memory.store_interaction(message, agent_response, project)
        
        return agent_response
    
    def _build_context(self, memories: List[Memory]) -> str:
        """Build context string from memories."""
        if not memories:
            return ""
        
        context_parts = []
        for mem in memories:
            context_parts.append(f"User: {mem.user_input}\nAgent: {mem.agent_response}")
        
        return "\n\n---\n\n".join(context_parts)


def demo():
    """Run a demonstration of the memory system."""
    print("=" * 60)
    print("🧠 Mnemo - AI Agent Memory System Demo")
    print("=" * 60)
    print()
    
    # Initialize memory system
    print("Initializing memory system...")
    memory = AgentMemory()
    
    # Demo 1: Store some interactions
    print("\n📥 Storing sample interactions...")
    
    interactions = [
        ("How do I implement JWT authentication?", 
         "To implement JWT authentication, you'll need to...", "authentication"),
        ("What's the best way to style a login form?",
         "For styling login forms, consider using CSS Grid...", "frontend"),
        ("Should I use SQL or NoSQL for user data?",
         "For user data, SQL databases are often preferred...", "backend"),
        ("How do I hash passwords securely?",
         "Use bcrypt or Argon2 for password hashing...", "authentication"),
        ("What CSS framework do you recommend?",
         "Popular CSS frameworks include Tailwind CSS...", "frontend"),
    ]
    
    for user_input, response, project in interactions:
        mem_id = memory.store_interaction(user_input, response, project)
        print(f"  ✓ Stored: [{project}] {user_input[:40]}...")
    
    # Demo 2: Retrieve relevant memories
    print("\n🔍 Retrieving relevant memories...")
    
    queries = [
        "How to secure user login?",
        "Best practices for form styling",
        "Database recommendations"
    ]
    
    for query in queries:
        print(f"\n  Query: \"{query}\"")
        memories = memory.retrieve_relevant(query, limit=2)
        for mem in memories:
            print(f"    → [{mem.project}] {mem.user_input[:50]}...")
    
    # Demo 3: Auto-routing
    print("\n🚦 Auto-project routing demo...")
    
    test_inputs = [
        "I need help with React components",
        "What's the best way to handle OAuth?",
        "How do I set up Docker containers?"
    ]
    
    for content in test_inputs:
        project = memory.auto_route_project(content)
        print(f"  \"{content[:40]}...\" → {project}")
    
    # Demo 4: Project-specific retrieval
    print("\n📂 Project-specific memories...")
    
    auth_memories = memory.get_project_memories("authentication")
    print(f"  Authentication project has {len(auth_memories)} memories:")
    for mem in auth_memories:
        print(f"    • {mem.user_input}")
    
    # Demo 5: Claude integration (if API key available)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and api_key != "your_anthropic_api_key_here":
        print("\n🤖 Claude integration demo...")
        print("  (Using real Claude API)")
        
        try:
            agent = ClaudeAgentWithMemory(api_key=api_key, memory=memory)
            response = agent.chat("Remind me about password hashing", project="authentication")
            print(f"  Response: {response[:150]}...")
        except Exception as e:
            print(f"  Error calling Claude API: {e}")
    else:
        print("\n🤖 Claude integration demo...")
        print("  (Skipped - set ANTHROPIC_API_KEY to test)")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Set your ANTHROPIC_API_KEY in .env")
    print("  2. Run: python main.py")
    print("  3. Import AgentMemory or ClaudeAgentWithMemory in your project")


if __name__ == "__main__":
    demo()
