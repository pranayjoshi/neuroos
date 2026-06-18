import pytest
from pytest_httpx import HTTPXMock

from neuroos import NeuroOS
from neuroos.errors import SessionAlreadyActiveError


@pytest.mark.asyncio
async def test_connect_and_register_device(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://localhost:3000/health", json={"status": "ok"})
    httpx_mock.add_response(
        url="http://localhost:3000/devices/register",
        json={"deviceId": "simulator:default:SIM-001", "state": "connected"},
    )

    async with NeuroOS() as client:
        device = await client.devices.register("neuroos-simulator", num_channels=16)
        assert device["deviceId"] == "simulator:default:SIM-001"
        assert device["numChannels"] == 16


@pytest.mark.asyncio
async def test_start_session_maps_conflict(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://localhost:3000/sessions/start", status_code=409, json={
        "error": "SESSION_ALREADY_ACTIVE",
        "message": "A session is already running. Stop it first.",
    })

    client = NeuroOS()
    with pytest.raises(SessionAlreadyActiveError):
        await client.sessions.start(
            device_id="simulator:default:SIM-001",
            subject_id="sub-001",
            session_name="test",
            paradigm="motor_imagery",
        )
