"""Authentication module for Google Calendar API."""

from .auth import authorize
from .scopes import SCOPES

__all__ = ["authorize", "SCOPES"] 