"""Logging utilities for Google Calendar MCP server."""

logs = {
    "init": """
╭-------------------------------------------╮
│                                           │
│         Google Calendar MCP init          │
│                                           │
╰-------------------------------------------╯
""",
    "running": """
╭-------------------------------------------╮
│                                           │
│      Google Calendar MCP Running          │
│                                           │
╰-------------------------------------------╯
""",
}


def cool_log(log: str) -> None:
    """Print a cool log message to stderr."""
    import sys
    print(log, file=sys.stderr) 