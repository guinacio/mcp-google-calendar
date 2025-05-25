"""Entry point for the Google Calendar MCP server with SSE transport."""

from .server_sse import main_sse

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_sse()) 