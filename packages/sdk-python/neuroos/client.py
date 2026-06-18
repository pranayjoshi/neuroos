"""NeuroOS Python SDK client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from .errors import NeuroOSError, TimeoutError, map_http_error
from .stream import IntentStream
from .types import (
    DeviceDiagnostics,
    DeviceInfo,
    DeviceState,
    IntentEvent,
    ParadigmType,
    RegisterDeviceResponse,
    SessionMetadata,
)


class DevicesAPI:
    def __init__(self, client: "NeuroOS") -> None:
        self._client = client

    async def register(
        self,
        adapter_name: str,
        *,
        num_channels: int = 16,
        sample_rate_hz: int = 256,
        **config: Any,
    ) -> DeviceInfo:
        payload = {
            "adapterName": adapter_name,
            "config": {"numChannels": num_channels, "sampleRateHz": sample_rate_hz, **config},
        }
        response = await self._client._request("POST", "/devices/register", payload)
        body = response.json()
        return {
            "deviceId": body["deviceId"],
            "state": body["state"],
            "vendor": "NeuroOS",
            "model": adapter_name,
            "firmwareVersion": "0.1.0",
            "numChannels": num_channels,
            "sampleRateHz": sample_rate_hz,
            "signalType": "EEG",
            "channelLabels": config.get("channelLabels", []),
            "adResolutionBits": 24,
            "referenceElectrode": "average",
        }

    def register_sync(self, adapter_name: str, **kwargs: Any) -> DeviceInfo:
        return asyncio.run(self.register(adapter_name, **kwargs))

    async def list(self) -> list[dict[str, str]]:
        response = await self._client._request("GET", "/devices")
        return response.json()["devices"]

    async def get_diagnostics(self, device_id: str) -> DeviceDiagnostics:
        response = await self._client._request("GET", "/operator/diagnostics")
        body = response.json()
        if body["device"]["deviceId"] not in (None, device_id):
            devices = await self.list()
            if not any(item["deviceId"] == device_id for item in devices):
                from .errors import DeviceNotFoundError

                raise DeviceNotFoundError(device_id)
        diagnostics = body["device"].get("diagnostics")
        if diagnostics:
            return diagnostics
        return {
            "impedanceKOhm": [],
            "batteryPercent": None,
            "signalQuality": [],
            "droppedFrames": 0,
            "timestampMs": 0,
        }


class SessionsAPI:
    def __init__(self, client: "NeuroOS") -> None:
        self._client = client

    async def start(
        self,
        *,
        device_id: str,
        subject_id: str,
        session_name: str,
        paradigm: ParadigmType,
    ) -> SessionMetadata:
        payload = {
            "deviceId": device_id,
            "subjectId": subject_id,
            "sessionName": session_name,
            "paradigm": paradigm,
        }
        response = await self._client._request("POST", "/sessions/start", payload)
        return response.json()

    def start_sync(self, **kwargs: Any) -> SessionMetadata:
        return asyncio.run(self.start(**kwargs))

    async def stop(self, session_id: str) -> SessionMetadata:
        response = await self._client._request("POST", f"/sessions/{session_id}/stop")
        return response.json()

    def stop_sync(self, session_id: str) -> SessionMetadata:
        return asyncio.run(self.stop(session_id))

    async def pause(self, session_id: str) -> None:
        await self._client._request("POST", f"/sessions/{session_id}/pause")

    async def resume(self, session_id: str) -> None:
        await self._client._request("POST", f"/sessions/{session_id}/resume")

    async def list(self) -> list[SessionMetadata]:
        response = await self._client._request("GET", "/sessions")
        return response.json()["sessions"]

    async def get(self, session_id: str) -> SessionMetadata:
        sessions = await self.list()
        for session in sessions:
            if session.get("sessionId") == session_id:
                return session
        raise NeuroOSError("UNKNOWN", f"Session not found: {session_id}")


class IntentsAPI:
    def __init__(self, client: "NeuroOS") -> None:
        self._client = client

    def stream(self) -> IntentStream:
        return IntentStream(
            self._client.base_url,
            reconnect=self._client.reconnect,
            reconnect_delay_ms=self._client.reconnect_delay_ms,
        )

    def stream_sync(self, *, max_events: int | None = None) -> Iterator[IntentEvent]:
        async def _collect() -> list[IntentEvent]:
            events: list[IntentEvent] = []
            async with self.stream() as stream:
                async for intent in stream:
                    events.append(intent)
                    if max_events is not None and len(events) >= max_events:
                        break
            return events

        for event in asyncio.run(_collect()):
            yield event


class NeuroOS:
    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        timeout: float = 5.0,
        reconnect: bool = True,
        reconnect_delay_ms: int = 1000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.reconnect = reconnect
        self.reconnect_delay_ms = reconnect_delay_ms
        self.devices = DevicesAPI(self)
        self.sessions = SessionsAPI(self)
        self.intents = IntentsAPI(self)
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NeuroOS":
        await self.connect()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.disconnect()

    def __enter__(self) -> "NeuroOS":
        asyncio.run(self.connect())
        return self

    def __exit__(self, *_args: object) -> None:
        asyncio.run(self.disconnect())

    async def connect(self) -> None:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        response = await self._request("GET", "/health")
        if response.status_code >= 400:
            raise map_http_error(response.status_code, response.json(), self.base_url)

    async def disconnect(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def start_session(
        self,
        *,
        device_id: str,
        subject_id: str,
        session_name: str,
        paradigm: ParadigmType,
    ) -> SessionMetadata:
        return await self.sessions.start(
            device_id=device_id,
            subject_id=subject_id,
            session_name=session_name,
            paradigm=paradigm,
        )

    async def stop_session(self, session_id: str) -> SessionMetadata:
        return await self.sessions.stop(session_id)

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        try:
            response = await self._http.request(method, path, json=json)
        except httpx.TimeoutException as exc:
            raise TimeoutError(int(self.timeout * 1000)) from exc
        except httpx.RequestError as exc:
            from .errors import ConnectionError

            raise ConnectionError(self.base_url, exc) from exc

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:  # noqa: BLE001
                body = {"message": response.text}
            raise map_http_error(response.status_code, body, self.base_url)
        return response
