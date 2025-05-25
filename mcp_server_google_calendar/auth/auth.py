"""Google Calendar API authentication."""

import json
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .scopes import SCOPES


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def get_token_path() -> Path:
    """Get the path to the token file."""
    return get_project_root() / "token.json"


def get_credentials_path() -> Path:
    """Get the path to the credentials file."""
    return get_project_root() / "mcp-calendar-google" / "mcp_server_google_calendar" / "credentials.json"


def load_saved_credentials() -> Optional[Credentials]:
    """Load saved credentials from token.json if it exists."""
    token_path = get_token_path()
    if token_path.exists():
        try:
            return Credentials.from_authorized_user_info(
                json.loads(token_path.read_text()), SCOPES
            )
        except Exception:
            return None
    return None


def save_credentials(creds: Credentials) -> None:
    """Save credentials to token.json."""
    token_path = get_token_path()
    token_path.write_text(creds.to_json())


def authorize() -> Credentials:
    """Authorize and return Google Calendar API credentials."""
    import sys
    print("Starting Google Calendar authentication...", file=sys.stderr)
    
    creds = load_saved_credentials()
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...", file=sys.stderr)
            try:
                creds.refresh(Request())
                print("Credentials refreshed successfully!", file=sys.stderr)
            except Exception as e:
                print(f"Failed to refresh credentials: {e}", file=sys.stderr)
                creds = None
        
        if not creds:
            credentials_path = get_credentials_path()
            print(f"Looking for credentials file at: {credentials_path}", file=sys.stderr)
            
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Credentials file not found at {credentials_path}. "
                    "Please download your OAuth2 credentials from Google Cloud Console and save as 'credentials.json' in the project root."
                )
            
            print("Starting OAuth flow - your browser will open...", file=sys.stderr)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            print("Authentication completed successfully!", file=sys.stderr)
        
        # Save the credentials for the next run
        save_credentials(creds)
        print("Credentials saved for future use.", file=sys.stderr)
    else:
        print("Using existing valid credentials.", file=sys.stderr)
    
    return creds 