"""Google Calendar MCP Server implementation."""

import json
import sys
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from googleapiclient.discovery import build
from pydantic import ValidationError

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .auth import authorize
from .tools import GOOGLE_CALENDAR_TOOLS
from .schemas import (
    CreateEventRequest,
    ListEventsRequest,
    UpdateEventRequest,
    DeleteEventRequest,
    FreeBusyRequest,
)
from .utils import cool_log, logs


# Create server instance
server = Server("mcp-server-google-calendar")

# Global variables for caching
_user_timezone = None


def get_user_timezone(calendar: Any) -> str:
    """Get the user's timezone from Google Calendar settings with caching."""
    global _user_timezone
    
    # Return cached timezone if available
    if _user_timezone is not None:
        return _user_timezone
    
    try:
        # Get timezone from Google Calendar settings
        settings = calendar.settings().get(setting="timezone").execute()
        _user_timezone = settings.get("value", "UTC")
        
        print(f"📍 Detected user timezone: {_user_timezone}", file=sys.stderr)
        return _user_timezone
        
    except Exception as e:
        print(f"⚠️ Could not get timezone from Google Calendar: {e}", file=sys.stderr)
        print("🕐 Falling back to UTC timezone", file=sys.stderr)
        _user_timezone = "UTC"
        return _user_timezone


def validate_and_fix_datetime(dt_string: Optional[str], default_timezone: str = "UTC") -> Optional[str]:
    """Validate and fix datetime format to include timezone if missing."""
    if not dt_string:
        return dt_string
    
    try:
        # If it's already in RFC3339 format with timezone, return as is
        if dt_string.endswith('Z') or '+' in dt_string[-6:] or dt_string.endswith('+00:00'):
            return dt_string
        
        # If it's in YYYY-MM-DDTHH:MM:SS format, add timezone
        if 'T' in dt_string and len(dt_string) == 19:
            # Parse the datetime
            dt = datetime.fromisoformat(dt_string)
            
            # Add timezone
            tz = pytz.timezone(default_timezone)
            dt_with_tz = tz.localize(dt)
            
            # Return in RFC3339 format
            return dt_with_tz.isoformat()
        
        # If it's just a date (YYYY-MM-DD), add time and timezone
        if len(dt_string) == 10 and '-' in dt_string:
            dt_string += "T00:00:00"
            dt = datetime.fromisoformat(dt_string)
            tz = pytz.timezone(default_timezone)
            dt_with_tz = tz.localize(dt)
            return dt_with_tz.isoformat()
        
        return dt_string
        
    except Exception as e:
        print(f"⚠️ Error fixing datetime format for '{dt_string}': {e}", file=sys.stderr)
        return dt_string


async def check_time_slot_availability(
    calendar: Any, calendar_id: str, start_time: str, end_time: str
) -> bool:
    """Check if a time slot is available (no overlapping events)."""
    try:
        res = calendar.freebusy().query(
            body={
                "timeMin": start_time,
                "timeMax": end_time,
                "items": [{"id": calendar_id}],
            }
        ).execute()

        busy_slots = res.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return len(busy_slots) == 0
    except Exception:
        # If we can't check availability, assume it's available
        return True


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return GOOGLE_CALENDAR_TOOLS


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Optional[Dict[str, Any]]
) -> List[types.TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}

    # Authorize and build calendar service
    creds = authorize()
    calendar = build("calendar", "v3", credentials=creds)

    try:
        if name == "get-events":
            # Validate arguments
            request_data = ListEventsRequest(**arguments)
            
            # Call Google Calendar API
            result = calendar.events().list(
                calendarId=request_data.calendarId,
                timeMin=request_data.timeMin,
                timeMax=request_data.timeMax,
                maxResults=request_data.maxResults,
                singleEvents=request_data.singleEvents,
                orderBy=request_data.orderBy,
            ).execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "list-calendars":
            # List all calendars
            result = calendar.calendarList().list().execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "get-timezone-info":
            # Get timezone information
            try:
                user_tz = get_user_timezone(calendar)
                
                # Get current time in user's timezone
                now_utc = datetime.now(pytz.UTC)
                user_tz_obj = pytz.timezone(user_tz)
                now_local = now_utc.astimezone(user_tz_obj)
                
                result = {
                    "timezone": user_tz,
                    "current_utc_time": now_utc.isoformat(),
                    "current_local_time": now_local.isoformat(),
                    "utc_offset": now_local.strftime("%z"),
                    "timezone_name": now_local.tzname()
                }
                
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"Error getting timezone info: {str(e)}"}, indent=2),
                    )
                ]

        elif name == "get-current-date":
            # Get current date and time
            try:
                user_tz = get_user_timezone(calendar)
                
                # Get current time in user's timezone
                now_utc = datetime.now(pytz.UTC)
                user_tz_obj = pytz.timezone(user_tz)
                now_local = now_utc.astimezone(user_tz_obj)
                
                result = {
                    "current_date": now_local.strftime("%Y-%m-%d"),
                    "current_time": now_local.strftime("%H:%M:%S"),
                    "current_datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
                    "current_datetime_iso": now_local.isoformat(),
                    "timezone": user_tz,
                    "day_of_week": now_local.strftime("%A"),
                    "formatted_date": now_local.strftime("%B %d, %Y"),
                    "utc_datetime": now_utc.isoformat(),
                    "timestamp": int(now_local.timestamp())
                }
                
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"Error getting current date: {str(e)}"}, indent=2),
                    )
                ]

        elif name == "check-availability":
            # Validate arguments
            request_data = FreeBusyRequest(**arguments)
            
            # Call Google Calendar API
            result = calendar.freebusy().query(
                body=request_data.model_dump(exclude_none=True)
            ).execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "create-event":
            # Validate arguments
            request_data = CreateEventRequest(**arguments)
            
            # Use provided timezone or auto-detect from user's Google Calendar
            user_tz = request_data.timezone or get_user_timezone(calendar)
            
            # Fix datetime formats to include proper timezone
            fixed_start = validate_and_fix_datetime(request_data.start_datetime, user_tz)
            fixed_end = validate_and_fix_datetime(request_data.end_datetime, user_tz)
            
            # Build event data
            event_data = {
                "summary": request_data.summary,
                "start": {
                    "dateTime": fixed_start,
                    "timeZone": user_tz
                },
                "end": {
                    "dateTime": fixed_end,
                    "timeZone": user_tz
                }
            }
            
            # Add optional fields
            if request_data.description is not None:
                event_data["description"] = request_data.description
            if request_data.location is not None:
                event_data["location"] = request_data.location
            if request_data.colorId is not None:
                event_data["colorId"] = request_data.colorId
            if request_data.visibility is not None:
                event_data["visibility"] = request_data.visibility
            if request_data.transparency is not None:
                event_data["transparency"] = request_data.transparency
            if request_data.recurrence is not None:
                event_data["recurrence"] = request_data.recurrence
            if request_data.reminders is not None:
                event_data["reminders"] = request_data.reminders.model_dump(exclude_none=True) if hasattr(request_data.reminders, 'model_dump') else request_data.reminders
            if request_data.attendees is not None:
                event_data["attendees"] = [attendee.model_dump(exclude_none=True) if hasattr(attendee, 'model_dump') else attendee for attendee in request_data.attendees]
            if request_data.attachments is not None:
                event_data["attachments"] = [attachment.model_dump(exclude_none=True) if hasattr(attachment, 'model_dump') else attachment for attachment in request_data.attachments]
            if request_data.conferenceData is not None:
                event_data["conferenceData"] = request_data.conferenceData
            
            # Check availability before creating the event
            is_available = await check_time_slot_availability(
                calendar,
                request_data.calendarId,
                event_data["start"]["dateTime"],
                event_data["end"]["dateTime"],
            )

            if not is_available:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({
                            "error": "Time slot is not available - there are overlapping events",
                            "status": "CONFLICT"
                        }, indent=2),
                    )
                ]
            
            # Create the event
            result = calendar.events().insert(
                calendarId=request_data.calendarId,
                body=event_data,
                conferenceDataVersion=1 if event_data.get("conferenceData") else 0,
                supportsAttachments=bool(event_data.get("attachments")),
            ).execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "event": result,
                        "message": f"Event '{request_data.summary}' created successfully from {request_data.start_datetime} to {request_data.end_datetime} ({user_tz})",
                        "event_link": result.get("htmlLink"),
                        "event_id": result.get("id")
                    }, indent=2),
                )
            ]

        elif name == "delete-event":
            # Validate arguments
            request_data = DeleteEventRequest(**arguments)
            
            # Delete the event
            calendar.events().delete(
                calendarId=request_data.calendarId,
                eventId=request_data.eventId,
                sendUpdates=request_data.sendUpdates,
            ).execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "message": f"Event {request_data.eventId} deleted successfully"
                    }, indent=2),
                )
            ]

        elif name == "update-event":
            # Validate arguments
            request_data = UpdateEventRequest(**arguments)
            
            # Build update data with only provided fields
            update_data = {}
            
            # Simple fields
            if request_data.summary is not None:
                update_data["summary"] = request_data.summary
            if request_data.description is not None:
                update_data["description"] = request_data.description
            if request_data.location is not None:
                update_data["location"] = request_data.location
            if request_data.colorId is not None:
                update_data["colorId"] = request_data.colorId
            if request_data.visibility is not None:
                update_data["visibility"] = request_data.visibility
            if request_data.transparency is not None:
                update_data["transparency"] = request_data.transparency
            if request_data.recurrence is not None:
                update_data["recurrence"] = request_data.recurrence
            if request_data.reminders is not None:
                update_data["reminders"] = request_data.reminders.model_dump(exclude_none=True) if hasattr(request_data.reminders, 'model_dump') else request_data.reminders
            if request_data.attendees is not None:
                update_data["attendees"] = [attendee.model_dump(exclude_none=True) if hasattr(attendee, 'model_dump') else attendee for attendee in request_data.attendees]
                
            # Handle datetime updates
            if request_data.start_datetime or request_data.end_datetime:
                # Use provided timezone or auto-detect from user's Google Calendar
                user_tz = request_data.timezone or get_user_timezone(calendar)
                
                if request_data.start_datetime:
                    fixed_start = validate_and_fix_datetime(request_data.start_datetime, user_tz)
                    update_data["start"] = {
                        "dateTime": fixed_start,
                        "timeZone": user_tz
                    }
                    
                if request_data.end_datetime:
                    fixed_end = validate_and_fix_datetime(request_data.end_datetime, user_tz)
                    update_data["end"] = {
                        "dateTime": fixed_end,
                        "timeZone": user_tz
                    }
                
                # If updating time, check for availability
                if update_data.get("start") and update_data.get("end"):
                    is_available = await check_time_slot_availability(
                        calendar,
                        request_data.calendarId,
                        update_data["start"]["dateTime"],
                        update_data["end"]["dateTime"],
                    )

                    if not is_available:
                        return [
                            types.TextContent(
                                type="text",
                                text=json.dumps({
                                    "error": "New time slot is not available - there are overlapping events",
                                    "status": "CONFLICT"
                                }, indent=2),
                            )
                        ]
            
            # If no fields to update, return error
            if not update_data:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({
                            "error": "No fields provided to update. Please specify at least one field to update."
                        }, indent=2),
                    )
                ]

            # Update the event
            result = calendar.events().patch(
                calendarId=request_data.calendarId,
                eventId=request_data.eventId,
                body=update_data,
                sendUpdates=request_data.sendUpdates,
            ).execute()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "event": result,
                        "message": f"Event '{result.get('summary', request_data.eventId)}' updated successfully",
                        "updated_fields": list(update_data.keys()),
                        "event_link": result.get("htmlLink")
                    }, indent=2),
                )
            ]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        raise ValueError(error_msg)
    except Exception as e:
        raise RuntimeError(f"Error calling Google Calendar API: {str(e)}")


async def main():
    """Main server function."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Google Calendar MCP Server")
        parser.add_argument("command", nargs="?", default="run", help="Command to run (init or run)")
        args = parser.parse_args()

        if args.command == "init":
            cool_log(logs["init"])
            # TODO: Implement init functionality for Claude Desktop configuration
            print("Init functionality not yet implemented for Python version.", file=sys.stderr)
            print("Please manually configure Claude Desktop to use this server.", file=sys.stderr)
            return

        # Authorize Google Calendar access
        print("Initializing Google Calendar authorization...", file=sys.stderr)
        try:
            authorize()
            print("Google Calendar authorization successful!", file=sys.stderr)
        except Exception as e:
            print(f"Error during Google Calendar authorization: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error in main setup: {e}", file=sys.stderr)
        sys.exit(1)

    # Run the server
    try:
        print("Starting MCP server...", file=sys.stderr)
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            print("MCP server connected, ready for requests", file=sys.stderr)
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp_server_google_calendar",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        sys.exit(1)


def main_sync():
    """Synchronous wrapper for the async main function."""
    import asyncio
    cool_log(logs["running"])
    asyncio.run(main())


if __name__ == "__main__":
    main_sync() 