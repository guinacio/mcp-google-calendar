"""Entry point for the Google Calendar MCP server."""

from .server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 