"""Async device simulator implementing the DeviceAdapter protocol."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Literal

from data_generator.device.simulator_config import SimulatorConfig
from data_generator.generators.eeg_generator import EEGGenerator, _labels_for_count
from data_generator.generators.emg_generator import EMGGenerator

DeviceState = Literal["disconnected", "connecting", "connected", "recording", "paused", "error"]


class DeviceSimulator:
    """
    Python equivalent of the DeviceAdapter TypeScript interface.

    Streams RawSignalFrame-compatible dicts via asyncio at real-time rate.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config
        labels = config.channel_labels or _labels_for_count(config.num_channels)
        self._eeg = EEGGenerator(
            num_channels=config.num_channels,
            sample_rate_hz=config.sample_rate_hz,
            channel_labels=labels,
            snr_db=config.snr_db,
            random_seed=config.random_seed,
            samples_per_frame=config.samples_per_frame,
            device_id=config.device_id,
        )

        emg_channels = self._emg_channel_indices(labels)
        burst_prob = config.emg_burst_probability
        if burst_prob is None:
            burst_prob = config.scenario.emg_burst_probability

        self._emg: EMGGenerator | None = None
        if burst_prob > 0.0 and emg_channels:
            self._emg = EMGGenerator(
                affected_channels=emg_channels,
                burst_probability=burst_prob,
                sample_rate_hz=config.sample_rate_hz,
                random_seed=config.random_seed,
            )

        self._state: DeviceState = "disconnected"
        self._frame_index = 0
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._stream_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    @staticmethod
    def _emg_channel_indices(labels: list[str]) -> list[int]:
        targets = {"T3", "T4", "F7", "F8"}
        return [idx for idx, label in enumerate(labels) if label in targets]

    @property
    def device_id(self) -> str:
        return self.config.device_id

    @property
    def state(self) -> DeviceState:
        return self._state

    async def connect(self) -> dict:
        self._state = "connecting"
        await asyncio.sleep(0)
        self._state = "connected"
        labels = self.config.channel_labels or _labels_for_count(self.config.num_channels)
        return {
            "deviceId": self.config.device_id,
            "vendor": "NeuroOS",
            "model": "Simulator",
            "firmwareVersion": "0.1.0",
            "numChannels": self.config.num_channels,
            "sampleRateHz": float(self.config.sample_rate_hz),
            "signalType": "EEG",
            "channelLabels": labels,
            "adResolutionBits": 24,
            "referenceElectrode": "linked-mastoids",
        }

    async def start_recording(self) -> None:
        if self._state not in ("connected", "paused"):
            raise RuntimeError(f"Cannot start recording from state {self._state}")
        self._state = "recording"
        self._stop_event.clear()
        self._pause_event.set()
        if self._stream_task is None or self._stream_task.done():
            self._stream_task = asyncio.create_task(self._emit_frames())

    async def pause_recording(self) -> None:
        if self._state != "recording":
            return
        self._state = "paused"
        self._pause_event.clear()

    async def stop_recording(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        if self._stream_task is not None:
            await self._stream_task
            self._stream_task = None
        if self._state in ("recording", "paused"):
            self._state = "connected"

    async def disconnect(self) -> None:
        await self.stop_recording()
        self._state = "disconnected"

    async def _emit_frames(self) -> None:
        frame_period = self.config.frame_period_sec
        max_frames = None
        if self.config.duration_sec is not None and self.config.duration_sec > 0:
            max_frames = int(self.config.duration_sec / frame_period)

        next_deadline = time.perf_counter()

        while not self._stop_event.is_set():
            await self._pause_event.wait()

            if max_frames is not None and self._frame_index >= max_frames:
                break

            frame = self._eeg.generate_frame(self.config.scenario, self._frame_index)
            if self._emg is not None:
                self._emg.apply_artifact(frame, self._frame_index)

            await self._queue.put(frame)
            self._frame_index += 1

            next_deadline += frame_period
            sleep_for = next_deadline - time.perf_counter()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                next_deadline = time.perf_counter()

        await self._queue.put(None)

    async def frame_stream(self) -> AsyncIterator[dict]:
        """Yield one RawSignalFrame dict per frame period."""
        while True:
            frame = await self._queue.get()
            if frame is None:
                break
            yield frame
