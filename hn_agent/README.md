# HN Research Agent

A deep research agent for Hacker News that uses AI to analyze discussions and extract insights from HN stories and comments.

## Features

- **Semantic Search**: Search across all HN stories and comments
- **AI-Powered Summaries**: Generate structured summaries of discussions with themes, controversies, and key findings
- **Full Thread Analysis**: Read complete comment threads with hierarchical structure
- **MCP Integration**: Exposes tools via Model Context Protocol (MCP) for AI agents
- **Research Agent**: Autonomous agent that orchestrates multiple searches to answer complex questions

## Architecture

The project uses:
- **Fenic**: PySpark-inspired DataFrame framework for data operations
- **DuckDB**: Local database for efficient querying
- **PydanticAI**: Agent framework for orchestrating research
- **MCP**: Model Context Protocol for tool exposure
- **OpenAI GPT**: For semantic analysis and summarization

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key
- HuggingFace token (for dataset access)

### Setup

1. Clone the repository:

2. Install dependencies with uv:
```bash
uv sync
```

3. Set up environment variables:
```bash
export OPENAI_API_KEY="your-openai-api-key"
export HF_TOKEN="your-huggingface-token"
```

## Usage

### 1. Load the HN Dataset

First, download and load the Hacker News dataset from HuggingFace:

```bash
cd src
HF_TOKEN=$HF_TOKEN uv run python -m hn_agent.data.loader
```

This downloads ~2.5M comments and ~500K stories from 2025 into a local DuckDB database.

### 2. Run the MCP Server

Start the MCP server which automatically registers and exposes the tools via HTTP:

```bash
uv run python -m hn_agent.mcp.server
```

The server runs on `http://localhost:8080/mcp` and provides three tools:
- `search_stories`: Find stories by regex pattern
- `read_story`: Get full story with comment tree
- `summarize_story`: AI-powered discussion summary

### 3. Use the Research Agent

Run research queries using the CLI:

```bash
# Simple query
OPENAI_API_KEY=$OPENAI_API_KEY uv run python -m hn_agent.cli "What are concerns about AI safety?"

# With options
OPENAI_API_KEY=$OPENAI_API_KEY uv run python -m hn_agent.cli --max-stories 10 "Latest LLM developments"

# Output as JSON
OPENAI_API_KEY=$OPENAI_API_KEY uv run python -m hn_agent.cli --json "Rust vs Go discussions"

# Quiet mode (no progress spinner)
OPENAI_API_KEY=$OPENAI_API_KEY uv run python -m hn_agent.cli --quiet "Python trends"
```

## Project Structure

```
hn_agent/
├── src/hn_agent/
│   ├── agent/          # Research agent implementation
│   │   └── research.py  # PydanticAI agent for deep research
│   ├── data/           # Data loading utilities
│   │   └── loader.py   # HuggingFace dataset loader
│   ├── mcp/            # MCP server
│   │   └── server.py   # HTTP MCP server implementation
│   ├── tools/          # Tool definitions
│   │   ├── tools.py    # MCP tool registration
│   │   └── models.py   # Pydantic models for structured output
│   ├── session.py      # Fenic session management
│   └── cli.py          # Command-line interface
└── assets/data/        # Local DuckDB storage (created on first run)
```

## Available Tools

### search_stories
Search across HN stories and comments using regex patterns:
```python
pattern: "(?i)(rust|golang|python)"  # Case-insensitive search
# Returns: Ranked stories with title, score, comment count
```

### read_story
Fetch complete story with comment hierarchy:
```python
story_id: 45389500
# Returns: Story metadata + all comments with depth/path structure
```

### summarize_story
Generate AI summary of story discussion:
```python
story_id: 45389500
language: "en"  # Output language
extra_instructions: "Focus on technical details"
# Returns: Structured summary with themes, controversies, action items
```

## Research Agent

The research agent uses GPT-5 (when available, falls back to GPT-4) to:

1. **Search** - Find relevant stories using multiple search queries
2. **Analyze** - Summarize the most relevant discussions
3. **Synthesize** - Extract patterns across multiple stories
4. **Report** - Generate structured findings with citations

Example output:
- Key findings with evidence
- Common themes across discussions  
- Points of controversy
- Actionable insights
- Source citations (story IDs)

## Development

### Running Individual Components

```bash
# Test data loading
uv run python -m hn_agent.data.loader

# Start MCP server (automatically registers tools)
uv run python -m hn_agent.mcp.server

# Run research CLI
uv run python -m hn_agent.cli "Your research question"
```

### Python API

```python
from hn_agent.agent.research import run_research

# Run research programmatically
report = run_research("What are thoughts on remote work?")
print(report.key_findings)
print(report.themes)
print(report.sources)
```

## License

MIT

## Credits

- Dataset: [HuggingFace Hacker News Dataset](https://huggingface.co/datasets/typedef-ai/hacker-news-dataset)
- Framework: [Fenic](https://github.com/fenic-ai/fenic)
- Agent: [PydanticAI](https://github.com/pydantic/pydantic-ai)