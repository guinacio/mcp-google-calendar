"""Pydantic schemas for Google Calendar MCP server."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class DateTime(BaseModel):
    """DateTime schema for Google Calendar events."""
    dateTime: str = Field(..., description="RFC3339 timestamp")
    timeZone: Optional[str] = Field(None, description="Time zone")


class Attendee(BaseModel):
    """Attendee schema for Google Calendar events."""
    email: EmailStr = Field(..., description="Attendee's email address")
    displayName: Optional[str] = Field(None, description="Attendee's display name")
    optional: Optional[bool] = Field(False, description="Whether attendee is optional")
    responseStatus: Optional[Literal["needsAction", "declined", "tentative", "accepted"]] = Field(
        "needsAction", description="Attendee's response status"
    )
    comment: Optional[str] = Field(None, description="Attendee's response comment")
    additionalGuests: Optional[int] = Field(0, ge=0, description="Number of additional guests")


class Attachment(BaseModel):
    """Attachment schema for Google Calendar events."""
    fileId: str = Field(..., description="Google Drive file ID")
    fileUrl: Optional[str] = Field(None, description="File URL")
    title: Optional[str] = Field(None, description="File title")
    mimeType: Optional[str] = Field(None, description="File MIME type")


class ReminderOverride(BaseModel):
    """Reminder override schema."""
    method: Literal["email", "popup"] = Field(..., description="Reminder method")
    minutes: int = Field(..., description="Minutes before event to remind")


class Reminders(BaseModel):
    """Reminders schema for Google Calendar events."""
    useDefault: Optional[bool] = Field(None, description="Use default reminders")
    overrides: Optional[List[ReminderOverride]] = Field(None, description="Custom reminder overrides")


class ConferenceData(BaseModel):
    """Conference data schema for Google Calendar events."""
    createRequest: Optional[dict] = Field(None, description="Conference creation request")


class Event(BaseModel):
    """Event schema for Google Calendar."""
    summary: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    colorId: Optional[str] = Field(None, description="Event color ID")
    start: DateTime = Field(..., description="Event start time")
    end: DateTime = Field(..., description="Event end time")
    recurrence: Optional[List[str]] = Field(None, description="Recurrence rules")
    attendees: Optional[List[Attendee]] = Field(None, description="Event attendees")
    attachments: Optional[List[Attachment]] = Field(None, max_length=25, description="Event attachments")
    reminders: Optional[Reminders] = Field(None, description="Event reminders")
    visibility: Optional[Literal["default", "public", "private", "confidential"]] = Field(
        "default", description="Event visibility"
    )
    transparency: Optional[Literal["opaque", "transparent"]] = Field(
        "opaque", description="Event transparency"
    )
    conferenceData: Optional[ConferenceData] = Field(None, description="Conference data")


class CreateEventRequest(BaseModel):
    """Create event request schema with all fields as top-level parameters."""
    calendarId: str = Field(..., description="Calendar ID or 'primary'")
    summary: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    colorId: Optional[str] = Field(None, description="Event color ID")
    start_datetime: str = Field(..., description="Event start time")
    end_datetime: str = Field(..., description="Event end time")
    timezone: Optional[str] = Field(None, description="Timezone for the event")
    recurrence: Optional[List[str]] = Field(None, description="Recurrence rules")
    attendees: Optional[List[Attendee]] = Field(None, description="Event attendees")
    attachments: Optional[List[Attachment]] = Field(None, max_length=25, description="Event attachments")
    reminders: Optional[Reminders] = Field(None, description="Event reminders")
    visibility: Optional[Literal["default", "public", "private", "confidential"]] = Field(
        "default", description="Event visibility"
    )
    transparency: Optional[Literal["opaque", "transparent"]] = Field(
        "opaque", description="Event transparency"
    )
    conferenceData: Optional[ConferenceData] = Field(None, description="Conference data")


class ListEventsRequest(BaseModel):
    """List events request schema."""
    calendarId: str = Field(..., description="Calendar ID")
    timeMin: Optional[str] = Field(None, description="Minimum time to list events from")
    timeMax: Optional[str] = Field(None, description="Maximum time to list events to")
    maxResults: Optional[int] = Field(None, gt=0, description="Maximum number of events to return")
    singleEvents: Optional[bool] = Field(None, description="Expand recurring events")
    orderBy: Optional[Literal["startTime", "updated"]] = Field(None, description="Order by field")


class UpdateEventRequest(BaseModel):
    """Update event request schema with all optional fields."""
    calendarId: str = Field(..., description="Calendar ID")
    eventId: str = Field(..., description="Event ID to update")
    summary: Optional[str] = Field(None, description="New event title")
    description: Optional[str] = Field(None, description="New event description")
    location: Optional[str] = Field(None, description="New event location")
    colorId: Optional[str] = Field(None, description="Event color ID")
    start_datetime: Optional[str] = Field(None, description="New start time")
    end_datetime: Optional[str] = Field(None, description="New end time")
    timezone: Optional[str] = Field(None, description="Timezone for the event")
    attendees: Optional[List[Attendee]] = Field(None, description="Event attendees")
    recurrence: Optional[List[str]] = Field(None, description="Recurrence rules")
    reminders: Optional[Reminders] = Field(None, description="Event reminders")
    visibility: Optional[Literal["default", "public", "private", "confidential"]] = Field(
        None, description="Event visibility"
    )
    transparency: Optional[Literal["opaque", "transparent"]] = Field(
        None, description="Event transparency"
    )
    sendUpdates: Optional[Literal["all", "externalOnly", "none"]] = Field(
        "all", description="Send updates to attendees"
    )


class DeleteEventRequest(BaseModel):
    """Delete event request schema."""
    calendarId: str = Field(..., description="Calendar ID")
    eventId: str = Field(..., description="Event ID to delete")
    sendUpdates: Optional[Literal["all", "externalOnly", "none"]] = Field(
        "all", description="Send updates to attendees"
    )


class FreeBusyItem(BaseModel):
    """Free/busy calendar item schema."""
    id: str = Field(..., description="Calendar ID")


class FreeBusyRequest(BaseModel):
    """Free/busy request schema."""
    timeMin: str = Field(..., description="Start time for free/busy query")
    timeMax: str = Field(..., description="End time for free/busy query")
    timeZone: Optional[str] = Field("UTC", description="Time zone for the query")
    groupExpansionMax: Optional[int] = Field(None, le=100, description="Max group expansion")
    calendarExpansionMax: Optional[int] = Field(None, le=50, description="Max calendar expansion")
    items: List[FreeBusyItem] = Field(..., description="Calendars to query")


 