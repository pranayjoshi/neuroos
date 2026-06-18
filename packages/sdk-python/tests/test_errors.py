import pytest

from neuroos.errors import ConnectionError, SessionAlreadyActiveError, map_http_error


def test_map_session_already_active() -> None:
    err = map_http_error(409, {"error": "SESSION_ALREADY_ACTIVE", "message": "busy"}, "http://localhost:3000")
    assert isinstance(err, SessionAlreadyActiveError)


def test_connection_error_message() -> None:
    err = ConnectionError("http://localhost:3000")
    assert "http://localhost:3000" in err.message
    assert err.code == "CONNECTION_FAILED"
