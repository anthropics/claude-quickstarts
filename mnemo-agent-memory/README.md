# Mnemo - AI Agent Memory System

A lightweight, intelligent memory system for AI agents that enables persistent conversation context, semantic memory retrieval, and automatic project routing. Built for seamless integration with OpenClaw and Claude API.

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Persistent Conversation Memory**: Store and retrieve conversation context across sessions
- **Semantic Memory Retrieval**: Find relevant memories using vector similarity search
- **Auto-Project Routing**: Automatically categorize and route conversations to appropriate projects
- **OpenClaw Integration**: Native support for OpenClaw workspace and file operations
- **Local-First Storage**: SQLite + local vector store - no external databases required
- **Claude API Integration**: Built-in support for Anthropic's Claude API

## Quick Start

### 1. Installation

```bash
cd mnemo-agent-memory
pip install -r requirements.txt
```

### 2. Configuration

Copy the environment template and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENCLAW_WORKSPACE_PATH=/path/to/your/openclaw/workspace
MEMORY_DB_PATH=./memory.db
```

### 3. Run the Demo

```bash
python main.py
```

## How It Works

### Memory System Architecture

```
User Input → Context Analysis → Memory Retrieval → Claude Processing → 
Memory Storage → Project Routing → Response Generation
```

### Core Components

1. **Memory Store**: SQLite-based persistent storage with vector embeddings
2. **Context Manager**: Handles conversation threading and context windows
3. **Project Router**: Automatically categorizes conversations by topic/project
4. **Retrieval Engine**: Semantic search using sentence embeddings

## Usage Examples

### Basic Usage

```python
from main import AgentMemory

# Initialize the memory system
memory = AgentMemory()

# Store a conversation
memory.store_interaction(
    user_input="What's the status of the authentication feature?",
    agent_response="The authentication feature is 80% complete...",
    project="auth-system"
)

# Retrieve relevant memories
memories = memory.retrieve_relevant(
    query="login progress",
    project="auth-system",
    limit=5
)
```

### With Claude Integration

```python
from main import ClaudeAgentWithMemory

# Create an agent with memory
agent = ClaudeAgentWithMemory()

# The agent automatically:
# 1. Retrieves relevant past conversations
# 2. Routes to the appropriate project
# 3. Stores new context for future reference
response = agent.chat("How do I implement JWT authentication?")
```

### Project Auto-Routing

```python
# Memories are automatically categorized
memory.store_interaction(
    user_input="Fix the CSS on the login page",
    agent_response="I'll update the styles...",
    # Project is auto-detected as "frontend" based on content
)

# Retrieve all memories for a specific project
frontend_memories = memory.get_project_memories("frontend")
```

## API Reference

### AgentMemory Class

```python
class AgentMemory:
    def store_interaction(self, user_input: str, agent_response: str, 
                          project: str = None) -> str:
        """Store a conversation interaction with optional project tag."""
        
    def retrieve_relevant(self, query: str, project: str = None, 
                          limit: int = 5) -> List[Memory]:
        """Retrieve semantically similar memories."""
        
    def get_project_memories(self, project: str, 
                             limit: int = 50) -> List[Memory]:
        """Get all memories for a specific project."""
        
    def auto_route_project(self, content: str) -> str:
        """Automatically determine project from content."""
```

### ClaudeAgentWithMemory Class

```python
class ClaudeAgentWithMemory:
    def chat(self, message: str, project: str = None) -> str:
        """Chat with Claude using memory-augmented context."""
        
    def get_conversation_summary(self, project: str = None) -> str:
        """Generate a summary of recent conversations."""
```

## Project Structure

```
mnemo-agent-memory/
├── main.py                 # Main implementation
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
└── memory.db              # SQLite database (created on first run)
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Claude API key | Required |
| `OPENCLAW_WORKSPACE_PATH` | Path to OpenClaw workspace | Optional |
| `MEMORY_DB_PATH` | SQLite database path | `./memory.db` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |
| `MAX_CONTEXT_MEMORIES` | Max memories to include in context | `10` |

## Advanced Features

### Custom Project Routing Rules

```python
# Define custom routing rules
routing_rules = {
    "auth": ["login", "password", "jwt", "oauth", "authentication"],
    "frontend": ["css", "html", "react", "ui", "component"],
    "backend": ["api", "database", "server", "endpoint"]
}

memory = AgentMemory(routing_rules=routing_rules)
```

### Memory Expiration

```python
# Configure memory retention
memory = AgentMemory(
    retention_days=30,  # Auto-expire memories after 30 days
    max_memories_per_project=1000
)
```

## Integration with OpenClaw

Mnemo integrates seamlessly with OpenClaw's workspace system:

```python
# Auto-detect OpenClaw workspace
import os

workspace = os.environ.get("OPENCLAW_WORKSPACE_PATH", ".")
memory = AgentMemory(db_path=f"{workspace}/memory.db")

# Store memories in OpenClaw's memory folder
memory.export_to_file(f"{workspace}/memory/conversations.json")
```

## Deployment

### Local Development

```bash
python main.py
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

- [OpenClaw Documentation](https://docs.openclaw.io)
- [Anthropic Claude API Docs](https://docs.anthropic.com)
- Issues: [GitHub Issues](https://github.com/anthropics/claude-quickstarts/issues)
