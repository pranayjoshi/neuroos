"""NeuroOS Python SDK."""

from .client import NeuroOS
from .errors import (
    ConnectionError,
    DeviceNotFoundError,
    NeuroOSError,
    NoActiveSessionError,
    SessionAlreadyActiveError,
    StreamClosedError,
    TimeoutError,
    ValidationError,
)
from .stream import IntentStream
from .types import IntentEvent, IntentEventSummary, IntentLabel, SessionMetadata

__all__ = [
    "NeuroOS",
    "IntentStream",
    "IntentEvent",
    "IntentEventSummary",
    "IntentLabel",
    "SessionMetadata",
    "NeuroOSError",
    "ConnectionError",
    "SessionAlreadyActiveError",
    "NoActiveSessionError",
    "DeviceNotFoundError",
    "StreamClosedError",
    "ValidationError",
    "TimeoutError",
]
