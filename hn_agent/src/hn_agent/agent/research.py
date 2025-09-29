"""
Deep research agent for Hacker News using PydanticAI and MCP.
"""

import os
import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from pydantic_ai import Agent
    from pydantic_ai.mcp import MCPServerStreamableHTTP
    from pydantic_ai.messages import ModelRequestPart, ToolCallPart, ToolReturnPart
except ImportError as e:
    raise RuntimeError(
        "pydantic-ai[mcp] is required. Install with: uv add 'pydantic-ai[mcp]'"
    ) from e


# Configuration
DEFAULT_MCP_URL = "http://localhost:8080/mcp"
MODEL = "openai:gpt-5"  # Future-proofing for GPT-5


class DeepResearchReport(BaseModel):
    """Structured output for research findings."""
    question: str
    method: List[str] = Field(default_factory=list, description="Methods used to research")
    key_findings: List[str] = Field(default_factory=list, description="Main discoveries")
    themes: List[Dict[str, Any]] = Field(default_factory=list, description="Common themes across stories")
    controversies: List[str] = Field(default_factory=list, description="Points of disagreement")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Story IDs and titles")
    limitations: List[str] = Field(default_factory=list, description="Research limitations")


SYSTEM_PROMPT = """
You are a deep research agent analyzing Hacker News discussions via MCP tools.

Available tools:
- search_stories(pattern): Find stories matching a regex pattern
- summarize_story(story_id): Get AI summary of a story and its discussion
- read_story(story_id): Get full story with comment tree (use sparingly)

Research process:
1. Use search_stories to find relevant content (max 5 searches, limit 10 per search)
2. Use summarize_story on the most relevant stories
3. Only use read_story if you need specific metadata not in summaries
4. Synthesize findings across all stories

Important:
- Keep search patterns broad initially, then refine
- Always cite story IDs in your findings
- Don't paste raw tool outputs into context
- Focus on patterns and insights across multiple stories

Return a JSON object matching the DeepResearchReport schema.
"""


async def run_research_async(question: str, max_stories_to_summarize: int = 8, verbose: bool = True) -> DeepResearchReport:
    """
    Run deep research on a Hacker News topic (async version).
    
    Args:
        question: Research question to investigate
        max_stories_to_summarize: Maximum number of stories to summarize
        verbose: Whether to print progress updates
        
    Returns:
        Structured research report
    """
    import sys
    import time
    import threading
    
    def progress(msg: str):
        if verbose:
            print(f"  → {msg}", file=sys.stderr, flush=True)
    
    # Spinner animation
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    stop_spinner = threading.Event()
    
    def spin(message: str):
        """Show a spinner while working."""
        if not verbose:
            return
        idx = 0
        while not stop_spinner.is_set():
            print(f"\r  {spinner_chars[idx]} {message}", end="", file=sys.stderr, flush=True)
            idx = (idx + 1) % len(spinner_chars)
            time.sleep(0.1)
        print(f"\r  ✓ {message}", file=sys.stderr, flush=True)
    
    # Get MCP URL from environment or use default
    mcp_url = os.getenv("HN_MCP_URL", DEFAULT_MCP_URL)
    
    progress(f"Connecting to MCP server at {mcp_url}")
    
    # Create MCP connection
    mcp_server = MCPServerStreamableHTTP(url=mcp_url)
    
    # Create agent with structured output
    agent = Agent(
        MODEL,
        system_prompt=SYSTEM_PROMPT,
        toolsets=[mcp_server],
        output_type=DeepResearchReport,
        output_retries=2
    )
    
    progress(f"Starting research with model {MODEL}")
    
    # Build user prompt
    user_prompt = f"""Research question: {question}

Please investigate this topic across Hacker News stories and discussions.
Budget: max 5 searches, summarize up to {max_stories_to_summarize} stories.
Focus on finding diverse perspectives and recurring themes."""
    
    start_time = time.time()
    
    # Start spinner in background thread
    spinner_thread = threading.Thread(target=spin, args=("Searching and analyzing HN discussions...",))
    spinner_thread.daemon = True
    spinner_thread.start()
    
    try:
        # Run the agent
        result = await agent.run(user_prompt)
    finally:
        # Stop spinner
        stop_spinner.set()
        spinner_thread.join(timeout=0.5)
    
    elapsed = time.time() - start_time
    progress(f"Research complete in {elapsed:.1f} seconds")
    
    return result.output


def run_research(question: str, max_stories_to_summarize: int = 8, verbose: bool = True) -> DeepResearchReport:
    """
    Run deep research on a Hacker News topic (sync wrapper).
    
    Args:
        question: Research question to investigate
        max_stories_to_summarize: Maximum number of stories to summarize
        verbose: Whether to print progress updates
        
    Returns:
        Structured research report
    """
    # Run the async version in a sync context
    return asyncio.run(run_research_async(question, max_stories_to_summarize, verbose))
