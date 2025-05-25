# Google Calendar MCP Server

A Model Context Protocol (MCP) server that allows Claude and other MCP clients to interact with Google Calendar. This server enables AI assistants to manage your calendar events, check availability, and handle scheduling tasks.

## Features

### Calendar Management
- **List Events** (`get-events`)
  - View events from any calendar
  - Filter by time range
  - Limit number of results
  
- **List Calendars** (`list-calendars`)
  - View all available calendars
  - Access calendar IDs and settings

- **Get Timezone Info** (`get-timezone-info`)
  - Get user's timezone information

- **Get Current Date** (`get-current-date`)
  - Get current date and time in user's timezone
  - Useful for AI models with outdated knowledge cutoff dates

### Event Operations
- **Create Events** (`create-event`)
  - Schedule new events with full feature support
  - Add attendees and set reminders
  - Include conference links and attachments
  - Set visibility, transparency, and colors
  - Configure recurring events
  - Automatic timezone detection and conflict checking

- **Update Events** (`update-event`)
  - Modify existing events
  - Change time/date with conflict checking
  - Add/remove attendees
  - Update any event details
  - Control notification settings

- **Delete Events** (`delete-event`)
  - Remove events from calendar
  - Control notification settings for attendees

### Availability Management
- **Check Availability** (`check-availability`)
  - Check free/busy status for multiple calendars
  - Time zone awareness
  - Support for checking other users' availability

## Requirements

- Python >= 3.12
- Google Cloud Console Project with Calendar API enabled
- OAuth 2.0 credentials

## Installation

### 1. Set up Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials (Desktop Application type)
5. Download credentials and save as `credentials.json` in the \mcp_server_google_calendar folder

### 2. Install the Package

```bash
# Clone or download the project
cd mcp-google-calendar

# Install the package
pip install -e .
```

### 3. Authentication Setup

On first run, the server will automatically open your browser for OAuth authentication. Your credentials will be saved for future use.

## Usage

This server can run in two modes:

### STDIO Mode (for Claude Desktop)

**Configure Claude Desktop:**

Add the following to your Claude Desktop configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google_calendar": {
      "command": "mcp-server-google-calendar"
    }
  }
}
```

**Alternative using Python module:**
```json
{
  "mcpServers": {
    "google_calendar": {
      "command": "python",
      "args": ["-m", "mcp_server_google_calendar"]
    }
  }
}
```

**Restart Claude Desktop** after configuration changes.

### SSE Mode (for web applications and other clients)

Run the server with SSE transport:

```bash
# Using the installed command
mcp-server-google-calendar-sse

# Or using Python module
python -m mcp_server_google_calendar.server_sse

# With custom host/port
python -m mcp_server_google_calendar.server_sse --host 0.0.0.0 --port 8001
```

The SSE server will be available at:
- **Server:** `http://localhost:8000`
- **SSE Endpoint:** `http://localhost:8000/sse`

## Example Commands

Here are some things you can ask Claude:

### Event Creation
- "Create an event called 'Team Meeting' for tomorrow at 2pm"
- "Schedule a recurring meeting every Monday at 10am"
- "Set up a video call with John for next Tuesday afternoon"

### Event Management
- "Move my 2pm meeting to 4pm"
- "Add Jane (jane@example.com) to tomorrow's team meeting"
- "Cancel my meeting with John"
- "Update the location of today's team lunch"

### Calendar Queries
- "What meetings do I have this week?"
- "When am I free tomorrow afternoon?"
- "Check if both Alice and Bob are available next Monday at 3pm"
- "List all my recurring events"

### Date/Time Information
- "What's today's date?" (useful for models with outdated knowledge)
- "What day of the week is it?"
- "What's my current timezone?"

## Advanced Features

### Time Conflict Detection
The server automatically checks for time conflicts when creating or updating events and will warn you about overlapping events.

### Timezone Support
- Automatic timezone detection from your Google Calendar settings
- Manual timezone specification for events
- Proper handling of timezone conversions

### Recurring Events
Full support for recurring events using iCalendar RRULE format:
- Daily, weekly, monthly, yearly patterns
- Custom recurrence rules
- Exception dates and rules

### Attendee Management
- Add/remove attendees with email validation
- Set optional vs required attendees
- Control response status and notifications
- Support for additional guests

## Troubleshooting

### Authentication Issues
- Ensure `credentials.json` is in the project root directory
- Check if OAuth consent screen is configured in Google Cloud Console
- Verify Calendar API is enabled
- Delete `token.json` to force re-authentication if needed

### Server Connection Issues
- Verify Python version (>= 3.12 required)
- Check Claude Desktop configuration file syntax
- Restart Claude Desktop after configuration changes
- For SSE mode, ensure the port is not in use

### Event Creation Problems
- Confirm calendar permissions in Google Calendar
- Check for time conflicts with existing events
- Verify attendee email addresses are valid
- Ensure timezone format is correct

## File Structure

```
mcp-google-calendar/
├── mcp_server_google_calendar/
│   ├── __init__.py
│   ├── __main__.py          # STDIO mode entry point
│   ├── __main_sse__.py      # SSE mode entry point
│   ├── credentials.json      # Google OAuth credentials (you provide)
│   ├── server.py            # STDIO server implementation
│   ├── server_sse.py        # SSE server implementation
│   ├── schemas.py           # Pydantic schemas
│   ├── auth/                # Authentication module
│   ├── tools/               # Tool definitions
│   └── utils/               # Utility functions
├── token.json              # Saved auth token (auto-generated)
├── pyproject.toml          # Project configuration
└── README.md
```

## Notes

- The server maintains separate implementations for STDIO and SSE modes with identical features
- Both modes support automatic timezone detection and conflict checking
- All times should be specified in YYYY-MM-DDTHH:MM:SS format or RFC3339
- Calendar ID 'primary' refers to the user's default calendar
- Event updates maintain existing data for unspecified fields
- The server automatically handles timezone detection and conversion

## License

MIT License 