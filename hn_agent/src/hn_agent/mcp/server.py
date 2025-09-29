"""
Simplest possible HTTP MCP server for Hacker News tools.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fenic.api.mcp.server import create_mcp_server, run_mcp_server_sync
from hn_agent.session import get_session
from hn_agent.tools.tools import register_tools


def start_server(port: int = 8080) -> None:
    """Start the HTTP MCP server."""
    session = get_session()
    
    # Register tools first with the same session
    register_tools(session=session)
    
    # Get all tools from catalog
    catalog = session.catalog
    tools = catalog.list_tools()
    
    print(f"\nFound {len(tools)} tools in catalog")
    for tool in tools:
        print(f"  - {tool.name}")
    
    # Create the MCP server with tools
    server = create_mcp_server(
        session=session,
        server_name="hn_agent",
        tools=tools
    )
    
    # Run the server with HTTP transport
    print(f"Starting MCP server on http://localhost:{port}")
    run_mcp_server_sync(
        server=server,
        transport="http",
        port=port
    )


if __name__ == "__main__":
    start_server()