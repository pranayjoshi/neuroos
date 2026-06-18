"""Async WebSocket intent stream."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets
from websockets.asyncio.client import ClientConnection

from .errors import ConnectionError, NeuroOSError, StreamClosedError
from .types import IntentEvent, IntentLabel


def _to_ws_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def parse_intent_event(raw: dict[str, Any]) -> IntentEvent:
    return {
        "intentId": str(raw["intentId"]),
        "label": raw["label"],
        "confidence": float(raw["confidence"]),
        "posteriors": {str(k): float(v) for k, v in (raw.get("posteriors") or {}).items()},
        "classifierType": raw["classifierType"],
        "sourceVectorId": str(raw["sourceVectorId"]),
        "timestampNs": str(raw["timestampNs"]),
        "endToEndLatencyMs": float(raw["endToEndLatencyMs"]),
        "featureImportance": raw.get("featureImportance") or {},
        "artifactFlag": bool(raw.get("artifactFlag", False)),
        "feedbackLabel": raw.get("feedbackLabel"),
    }


class IntentStream:
    def __init__(
        self,
        base_url: str,
        reconnect: bool = True,
        reconnect_delay_ms: int = 1000,
    ) -> None:
        self._base_url = base_url
        self._reconnect = reconnect
        self._reconnect_delay_ms = reconnect_delay_ms
        self._closed = False
        self._socket: ClientConnection | None = None
        self._queue: asyncio.Queue[IntentEvent | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "IntentStream":
        await self._ensure_connected()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def _ensure_connected(self) -> None:
        if self._closed:
            raise StreamClosedError()
        if self._socket is not None:
            return

        url = _to_ws_url(self._base_url, "/stream/intents")
        try:
            self._socket = await websockets.connect(url)
        except Exception as exc:  # noqa: BLE001
            raise ConnectionError(self._base_url, exc) from exc

        self._reader_task = asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        assert self._socket is not None
        try:
            async for message in self._socket:
                payload = json.loads(message)
                msg_type = payload.get("type")
                if msg_type == "intent":
                    await self._queue.put(parse_intent_event(payload["data"]))
                elif msg_type == "error":
                    raise NeuroOSError(
                        str(payload.get("code", "UNKNOWN")),
                        str(payload.get("message", "Stream error")),
                    )
        except Exception as exc:  # noqa: BLE001
            if not self._closed:
                await self._queue.put(None)
                if self._reconnect:
                    self._socket = None
                    await asyncio.sleep(self._reconnect_delay_ms / 1000)
                    if not self._closed:
                        await self._ensure_connected()
                else:
                    raise StreamClosedError(exc) from exc

    async def send_feedback(self, intent_id: str, true_label: IntentLabel) -> None:
        await self.feedback(intent_id, true_label)

    async def feedback(self, intent_id: str, true_label: IntentLabel) -> None:
        if not self._socket:
            raise StreamClosedError()
        message = json.dumps({"type": "feedback", "intentId": intent_id, "trueLabel": true_label})
        await self._socket.send(message)

    async def close(self) -> None:
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            self._reader_task = None
        if self._socket is not None:
            await self._socket.close()
            self._socket = None
        await self._queue.put(None)

    def __aiter__(self) -> AsyncIterator[IntentEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[IntentEvent]:
        await self._ensure_connected()
        while not self._closed:
            item = await self._queue.get()
            if item is None:
                if self._closed:
                    break
                continue
            yield item
