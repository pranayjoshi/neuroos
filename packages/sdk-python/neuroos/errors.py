"""Typed exceptions for the NeuroOS Python SDK."""

from __future__ import annotations


class NeuroOSError(Exception):
    def __init__(self, code: str, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.cause = cause


class ConnectionError(NeuroOSError):
    def __init__(self, base_url: str, cause: BaseException | None = None) -> None:
        super().__init__(
            "CONNECTION_FAILED",
            f"Could not connect to NeuroOS Platform Core at {base_url}. "
            "Make sure the platform is running: npx neuroos start",
            cause,
        )


class SessionAlreadyActiveError(NeuroOSError):
    def __init__(self) -> None:
        super().__init__(
            "SESSION_ALREADY_ACTIVE",
            "A session is already running. Stop it before starting a new one.",
        )


class NoActiveSessionError(NeuroOSError):
    def __init__(self) -> None:
        super().__init__(
            "NO_ACTIVE_SESSION",
            "No active session. Start a session before streaming intents.",
        )


class DeviceNotFoundError(NeuroOSError):
    def __init__(self, device_id: str) -> None:
        super().__init__("DEVICE_NOT_FOUND", f"Device not found: {device_id}")


class StreamClosedError(NeuroOSError):
    def __init__(self, cause: BaseException | None = None) -> None:
        super().__init__("STREAM_CLOSED", "Intent stream was closed unexpectedly.", cause)


class ValidationError(NeuroOSError):
    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__("VALIDATION_ERROR", message, cause)


class TimeoutError(NeuroOSError):
    def __init__(self, timeout_ms: int) -> None:
        super().__init__("TIMEOUT", f"Request exceeded timeout of {timeout_ms}ms.")


def map_http_error(status: int, body: dict[str, object], base_url: str) -> NeuroOSError:
    message = str(body.get("message") or body.get("error") or f"HTTP {status}")

    if status == 404 and body.get("error") == "DEVICE_NOT_FOUND":
        return DeviceNotFoundError(message)
    if status == 409 and body.get("error") == "SESSION_ALREADY_ACTIVE":
        return SessionAlreadyActiveError()
    if status == 422:
        return ValidationError(message)
    if status == 0 or status >= 500:
        return ConnectionError(base_url)
    return NeuroOSError("UNKNOWN", message)
