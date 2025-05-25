"""Google Calendar MCP Server implementation with SSE support using FastMCP."""

import json
import sys
import argparse
from typing import Optional
from datetime import datetime
import re
import pytz
from dateutil import tz

from googleapiclient.discovery import build
from pydantic import ValidationError
import uvicorn

from mcp.server.fastmcp import FastMCP

from .auth import authorize
from .schemas import (
    CreateEventRequest,
    ListEventsRequest,
    UpdateEventRequest,
    DeleteEventRequest,
    FreeBusyRequest,
)
from .utils import cool_log, logs

# Create FastMCP server instance
mcp = FastMCP("Google Calendar MCP Server")

# Global cache for calendar service and timezone
_calendar_service = None
_user_timezone = None

def get_calendar_service():
    """Get authenticated Google Calendar service with caching."""
    global _calendar_service
    
    # Return cached service if available
    if _calendar_service is not None:
        return _calendar_service
    
    # Authenticate and create new service (only once)
    creds = authorize()
    _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


def initialize_calendar_service():
    """Initialize the calendar service and timezone at startup."""
    global _calendar_service, _user_timezone
    try:
        print("🚀 Starting Google Calendar MCP Server with SSE transport...")
        creds = authorize()
        _calendar_service = build("calendar", "v3", credentials=creds)
        print("✅ Authentication successful!")
        
        # Initialize timezone
        try:
            settings = _calendar_service.settings().get(setting="timezone").execute()
            _user_timezone = settings.get("value", "UTC")
            print(f"📍 User timezone detected: {_user_timezone}")
        except Exception as e:
            print(f"⚠️ Could not get timezone from Google Calendar: {e}")
            print("🕐 Using UTC as default timezone")
            _user_timezone = "UTC"
        
        return True
    except Exception as e:
        print(f"❌ Error during Google Calendar authorization: {e}", file=sys.stderr)
        return False


def validate_and_fix_datetime(dt_string: Optional[str], default_timezone: str = "UTC") -> Optional[str]:
    """Validate and fix datetime string to RFC3339 format with proper timezone.
    
    Args:
        dt_string: The datetime string to validate
        default_timezone: Default timezone to use if none specified (Brazil time)
    """
    if not dt_string:
        return dt_string
    
    # If it already has timezone info, return as is
    if dt_string.endswith('Z') or '+' in dt_string[-6:] or '-' in dt_string[-6:]:
        return dt_string
    
    # Get the default timezone
    try:
        default_timezone = get_user_timezone()
        tz_obj = pytz.timezone(default_timezone)
    except:
        tz_obj = pytz.timezone("UTC")  # Fallback to UTC
    
    # If it's just a date (YYYY-MM-DD), add time and timezone
    if re.match(r'^\d{4}-\d{2}-\d{2}$', dt_string):
        dt = datetime.strptime(dt_string, "%Y-%m-%d")
        dt = tz_obj.localize(dt)
        return dt.isoformat()
    
    # If it's datetime without timezone (YYYY-MM-DDTHH:MM:SS)
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', dt_string):
        dt = datetime.strptime(dt_string, "%Y-%m-%dT%H:%M:%S")
        dt = tz_obj.localize(dt)
        return dt.isoformat()
    
    # If it's datetime with milliseconds but no timezone
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$', dt_string):
        # Remove milliseconds for parsing
        dt_clean = re.sub(r'\.\d+$', '', dt_string)
        dt = datetime.strptime(dt_clean, "%Y-%m-%dT%H:%M:%S")
        dt = tz_obj.localize(dt)
        return dt.isoformat()
    
    # Return as is if we can't parse it
    return dt_string


def get_user_timezone() -> str:
    """Get the user's timezone from Google Calendar settings with caching."""
    global _user_timezone
    
    # Return cached timezone if available
    if _user_timezone is not None:
        return _user_timezone
    
    try:
        # Get calendar service (but avoid circular dependency)
        if _calendar_service is None:
            # This should only happen during initialization
            return "UTC"
        
        # Get timezone from Google Calendar settings
        settings = _calendar_service.settings().get(setting="timezone").execute()
        _user_timezone = settings.get("value", "UTC")
        
        print(f"📍 Detected user timezone: {_user_timezone}")
        return _user_timezone
        
    except Exception as e:
        print(f"⚠️ Could not get timezone from Google Calendar: {e}")
        print("🕐 Falling back to UTC timezone")
        _user_timezone = "UTC"
        return _user_timezone


def check_time_slot_conflicts(
    calendar_id: str, start_time: str, end_time: str
) -> dict:
    """Check for conflicts in a time slot and return detailed information.
    
    Returns:
        dict: {
            "has_conflicts": bool,
            "conflicts": list,  # List of conflicting events with proper timezone info
            "error": str or None
        }
    """
    try:
        # Use the existing check_availability function for consistency
        calendar = get_calendar_service()
        user_tz = get_user_timezone()
        
        # Ensure times have proper timezone
        fixed_start = validate_and_fix_datetime(start_time, user_tz)
        fixed_end = validate_and_fix_datetime(end_time, user_tz)
        
        res = calendar.freebusy().query(
            body={
                "timeMin": fixed_start,
                "timeMax": fixed_end,
                "items": [{"id": calendar_id}],
            }
        ).execute()

        busy_slots = res.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        
        # Format conflicts with proper timezone information
        formatted_conflicts = []
        for slot in busy_slots:
            # Convert UTC times to user's timezone for display
            try:
                start_utc = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
                end_utc = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
                
                user_tz_obj = pytz.timezone(user_tz)
                start_local = start_utc.astimezone(user_tz_obj)
                end_local = end_utc.astimezone(user_tz_obj)
                
                formatted_conflicts.append({
                    "start": start_local.isoformat(),
                    "end": end_local.isoformat(),
                    "timezone": user_tz,
                    "start_display": start_local.strftime("%Y-%m-%d %H:%M"),
                    "end_display": end_local.strftime("%Y-%m-%d %H:%M")
                })
            except:
                # Fallback to original format if conversion fails
                formatted_conflicts.append(slot)
        
        return {
            "has_conflicts": len(busy_slots) > 0,
            "conflicts": formatted_conflicts,
            "error": None
        }
        
    except Exception as e:
        return {
            "has_conflicts": False,  # Assume no conflicts if check fails
            "conflicts": [],
            "error": f"Could not check for conflicts: {str(e)}"
        }


@mcp.tool()
def get_events(
    calendarId: str = "primary",
    timeMin: Optional[str] = None,
    timeMax: Optional[str] = None,
    maxResults: int = 10,
    singleEvents: bool = True,
    orderBy: str = "startTime"
) -> str:
    """Get events from Google Calendar.
    
    Args:
        calendarId: Calendar ID or 'primary' for the user's primary calendar
        timeMin: Lower bound (inclusive) for an event's end time to filter by. Optional. 
                Format: RFC3339 timestamp (e.g., '2023-10-02T00:00:00Z' or '2023-10-02')
        timeMax: Upper bound (exclusive) for an event's start time to filter by. Optional.
                Format: RFC3339 timestamp (e.g., '2023-10-08T23:59:59Z' or '2023-10-08')
        maxResults: Maximum number of events returned (1-2500, default: 10)
        singleEvents: Whether to expand recurring events into instances (default: True)
        orderBy: Order of events returned ('startTime' or 'updated', default: 'startTime')
    """
    try:
        # Fix datetime formats to include timezone
        user_tz = get_user_timezone()
        fixed_timeMin = validate_and_fix_datetime(timeMin, user_tz)
        fixed_timeMax = validate_and_fix_datetime(timeMax, user_tz)
        
        # Validate arguments
        request_data = ListEventsRequest(
            calendarId=calendarId,
            timeMin=fixed_timeMin,
            timeMax=fixed_timeMax,
            maxResults=maxResults,
            singleEvents=singleEvents,
            orderBy=orderBy
        )
        
        # Get calendar service
        calendar = get_calendar_service()
        
        # Call Google Calendar API
        result = calendar.events().list(
            calendarId=request_data.calendarId,
            timeMin=request_data.timeMin,
            timeMax=request_data.timeMax,
            maxResults=request_data.maxResults,
            singleEvents=request_data.singleEvents,
            orderBy=request_data.orderBy,
        ).execute()

        return json.dumps(result, indent=2)
        
    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error calling Google Calendar API: {str(e)}"}, indent=2)


@mcp.tool()
def list_calendars() -> str:
    """List all available calendars."""
    try:
        calendar = get_calendar_service()
        result = calendar.calendarList().list().execute()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error listing calendars: {str(e)}"}, indent=2)


@mcp.tool()
def get_timezone_info() -> str:
    """Get the current timezone information from Google Calendar."""
    try:
        user_tz = get_user_timezone()
        
        # Get current time in user's timezone
        import datetime
        now_utc = datetime.datetime.now(pytz.UTC)
        user_tz_obj = pytz.timezone(user_tz)
        now_local = now_utc.astimezone(user_tz_obj)
        
        return json.dumps({
            "timezone": user_tz,
            "current_utc_time": now_utc.isoformat(),
            "current_local_time": now_local.isoformat(),
            "utc_offset": now_local.strftime("%z"),
            "timezone_name": now_local.tzname()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error getting timezone info: {str(e)}"}, indent=2)


@mcp.tool()
def get_current_date() -> str:
    """Get the current date and time in the user's timezone.
    
    This tool is especially useful for AI models that may have outdated knowledge
    of the current date due to knowledge cutoff dates. It provides comprehensive
    current date/time information in the user's local timezone.
    
    Returns:
        JSON with current date, time, timezone, and various formatted versions
    """
    try:
        user_tz = get_user_timezone()
        
        # Get current time in user's timezone
        now_utc = datetime.now(pytz.UTC)
        user_tz_obj = pytz.timezone(user_tz)
        now_local = now_utc.astimezone(user_tz_obj)
        
        return json.dumps({
            "current_date": now_local.strftime("%Y-%m-%d"),
            "current_time": now_local.strftime("%H:%M:%S"),
            "current_datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "current_datetime_iso": now_local.isoformat(),
            "timezone": user_tz,
            "day_of_week": now_local.strftime("%A"),
            "formatted_date": now_local.strftime("%B %d, %Y"),
            "utc_datetime": now_utc.isoformat(),
            "timestamp": int(now_local.timestamp())
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error getting current date: {str(e)}"}, indent=2)


@mcp.tool()
def check_availability(
    timeMin: str,
    timeMax: str,
    items: list
) -> str:
    """Check availability for specified calendars and time range.
    
    Args:
        timeMin: Start time for availability check (RFC3339 format, e.g., '2023-10-02T00:00:00Z')
        timeMax: End time for availability check (RFC3339 format, e.g., '2023-10-08T23:59:59Z')
        items: List of calendar items to check (e.g., [{"id": "primary"}])
    """
    try:
        # Fix datetime formats to include timezone
        user_tz = get_user_timezone()
        fixed_timeMin = validate_and_fix_datetime(timeMin, user_tz)
        fixed_timeMax = validate_and_fix_datetime(timeMax, user_tz)
        
        # Validate arguments
        request_data = FreeBusyRequest(
            timeMin=fixed_timeMin,
            timeMax=fixed_timeMax,
            items=items
        )
        
        calendar = get_calendar_service()
        
        # Call Google Calendar API
        result = calendar.freebusy().query(
            body=request_data.model_dump(exclude_none=True)
        ).execute()

        return json.dumps(result, indent=2)
        
    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error checking availability: {str(e)}"}, indent=2)


@mcp.tool()
def create_event(
    calendarId: str,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    colorId: Optional[str] = None,
    timezone: Optional[str] = None,
    recurrence: Optional[list] = None,
    attendees: Optional[list] = None,
    attachments: Optional[list] = None,
    reminders: Optional[dict] = None,
    visibility: Optional[str] = None,
    transparency: Optional[str] = None,
    conferenceData: Optional[dict] = None
) -> str:
    """Create an event in Google Calendar with support for all features.
    
    Supports both simple events (title, time, location) and advanced features
    (recurring events, attendees, attachments, conference links, etc.).
    
    Args:
        calendarId: Calendar ID or 'primary' for the user's primary calendar
        summary: Event title (required)
        start_datetime: Start time in YYYY-MM-DDTHH:MM:SS format or RFC3339 (required)
        end_datetime: End time in YYYY-MM-DDTHH:MM:SS format or RFC3339 (required)
        description: Event description (optional)
        location: Event location (optional)
        colorId: Event color ID (optional)
        timezone: Timezone for the event (optional, auto-detected if not provided)
        recurrence: List of recurrence rules in iCalendar format (optional)
        attendees: List of attendees with email, displayName, optional, responseStatus (optional)
        attachments: List of Google Drive file attachments (optional)
        reminders: Reminder settings with useDefault and/or overrides (optional)
        visibility: Event visibility: "default", "public", "private", "confidential" (optional)
        transparency: Event transparency: "opaque", "transparent" (optional)
        conferenceData: Conference/meeting link settings (optional)
    
    Returns:
        JSON response with full event details or error message
    """
    try:
        # Validate arguments
        request_data = CreateEventRequest(
            calendarId=calendarId,
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=description,
            location=location,
            colorId=colorId,
            timezone=timezone,
            recurrence=recurrence,
            attendees=attendees,
            attachments=attachments,
            reminders=reminders,
            visibility=visibility,
            transparency=transparency,
            conferenceData=conferenceData
        )
        
        calendar = get_calendar_service()
        
        # Use provided timezone or auto-detect from user's Google Calendar
        user_tz = request_data.timezone or get_user_timezone()
        
        # Fix datetime formats to include proper timezone
        fixed_start = validate_and_fix_datetime(request_data.start_datetime, user_tz)
        fixed_end = validate_and_fix_datetime(request_data.end_datetime, user_tz)
        
        # Check for conflicts before creating the event
        conflict_check = check_time_slot_conflicts(
            request_data.calendarId,
            fixed_start,
            fixed_end,
        )

        if conflict_check["has_conflicts"]:
            return json.dumps({
                "error": "Time slot is not available - there are overlapping events",
                "status": "CONFLICT",
                "conflicting_events": conflict_check["conflicts"],
                "conflict_check_error": conflict_check["error"]
            }, indent=2)

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
        
        # Create the event
        result = calendar.events().insert(
            calendarId=request_data.calendarId,
            body=event_data,
            conferenceDataVersion=1 if event_data.get("conferenceData") else 0,
            supportsAttachments=bool(event_data.get("attachments")),
        ).execute()

        return json.dumps({
            "success": True,
            "event": result,
            "message": f"Event '{summary}' created successfully from {start_datetime} to {end_datetime} ({user_tz})",
            "event_link": result.get("htmlLink"),
            "event_id": result.get("id")
        }, indent=2)
        
    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error creating event: {str(e)}"}, indent=2)



@mcp.tool()
def delete_event(
    calendarId: str,
    eventId: str,
    sendUpdates: str = "all"
) -> str:
    """Delete an event from Google Calendar."""
    try:
        # Validate arguments
        request_data = DeleteEventRequest(
            calendarId=calendarId,
            eventId=eventId,
            sendUpdates=sendUpdates
        )
        
        calendar = get_calendar_service()
        
        # Delete the event
        calendar.events().delete(
            calendarId=request_data.calendarId,
            eventId=request_data.eventId,
            sendUpdates=request_data.sendUpdates,
        ).execute()

        return json.dumps({
            "success": True,
            "message": f"Event {request_data.eventId} deleted successfully"
        }, indent=2)
        
    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error deleting event: {str(e)}"}, indent=2)


@mcp.tool()
def update_event(
    calendarId: str,
    eventId: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    colorId: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    timezone: Optional[str] = None,
    attendees: Optional[list] = None,
    recurrence: Optional[list] = None,
    reminders: Optional[dict] = None,
    visibility: Optional[str] = None,
    transparency: Optional[str] = None,
    sendUpdates: str = "all"
) -> str:
    """Update an existing event in Google Calendar.
    
    All fields are optional - only specify the fields you want to update.
    Supports both simple updates (title, description, location) and advanced features
    (recurring events, attendees, reminders, etc.).
    
    Args:
        calendarId: Calendar ID or 'primary' for the user's primary calendar
        eventId: The ID of the event to update
        summary: New event title (optional)
        description: New event description (optional)
        location: New event location (optional)
        colorId: Event color ID (optional)
        start_datetime: New start time in YYYY-MM-DDTHH:MM:SS format or RFC3339 (optional)
        end_datetime: New end time in YYYY-MM-DDTHH:MM:SS format or RFC3339 (optional)
        timezone: Timezone for the event (optional, auto-detected if not provided)
        attendees: List of attendees with email, displayName, optional, responseStatus (optional)
        recurrence: List of recurrence rules in iCalendar format (optional)
        reminders: Reminder settings with useDefault and/or overrides (optional)
        visibility: Event visibility: "default", "public", "private", "confidential" (optional)
        transparency: Event transparency: "opaque", "transparent" (optional)
        sendUpdates: Whether to send notifications ("all", "externalOnly", "none")
    
    Returns:
        JSON response with updated event details or error message
    """
    try:
        # Validate arguments
        request_data = UpdateEventRequest(
            calendarId=calendarId,
            eventId=eventId,
            summary=summary,
            description=description,
            location=location,
            colorId=colorId,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            timezone=timezone,
            attendees=attendees,
            recurrence=recurrence,
            reminders=reminders,
            visibility=visibility,
            transparency=transparency,
            sendUpdates=sendUpdates
        )
        
        calendar = get_calendar_service()
        
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
            user_tz = request_data.timezone or get_user_timezone()
            
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
            
            # If updating time, check for conflicts
            if update_data.get("start") and update_data.get("end"):
                conflict_check = check_time_slot_conflicts(
                    request_data.calendarId,
                    update_data["start"]["dateTime"],
                    update_data["end"]["dateTime"],
                )

                if conflict_check["has_conflicts"]:
                    return json.dumps({
                        "error": "New time slot is not available - there are overlapping events",
                        "status": "CONFLICT",
                        "conflicting_events": conflict_check["conflicts"],
                        "conflict_check_error": conflict_check["error"]
                    }, indent=2)
        
        # If no fields to update, return error
        if not update_data:
            return json.dumps({
                "error": "No fields provided to update. Please specify at least one field to update."
            }, indent=2)

        # Update the event
        result = calendar.events().patch(
            calendarId=request_data.calendarId,
            eventId=request_data.eventId,
            body=update_data,
            sendUpdates=request_data.sendUpdates,
        ).execute()

        return json.dumps({
            "success": True,
            "event": result,
            "message": f"Event '{result.get('summary', eventId)}' updated successfully",
            "updated_fields": list(update_data.keys()),
            "event_link": result.get("htmlLink")
        }, indent=2)
        
    except ValidationError as e:
        error_msg = f"Invalid arguments: {'; '.join([f'{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}' for err in e.errors()])}"
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error updating event: {str(e)}"}, indent=2)




def main_sse():
    """Main SSE server function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Google Calendar MCP Server (SSE)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--log-level", default="info", help="Log level")
    args = parser.parse_args()

    # Initialize Google Calendar service
    if not initialize_calendar_service():
        sys.exit(1)

    print(f"🌐 Server starting on http://{args.host}:{args.port}")
    print(f"📡 SSE endpoint: http://{args.host}:{args.port}/sse")
    
    # Run the FastMCP server with SSE transport
    # Get the SSE app from FastMCP
    app = mcp.sse_app()
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower()
    )


if __name__ == "__main__":
    cool_log(logs["running"])
    main_sse() 