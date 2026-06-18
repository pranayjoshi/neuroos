"""NeuroOS Data Format (.ndf) recorder and replay."""

from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

_HEADER_TERMINATOR = b"\r\n\r\n"
_FLOAT32 = struct.Struct("<f")


class DataRecorder:
    """
    Save and replay sessions in .ndf (NeuroOS Data Format).

    File format:
    - ASCII header: JSON SessionMetadata terminated by \\r\\n\\r\\n
    - Binary body: little-endian float32, row-major [frames × channels × samples]
    - Sidecar events: recording.ndf.events (JSON Lines)
    - Sidecar frames: recording.ndf.frames (per-frame metadata for exact replay)
    """

    def __init__(self) -> None:
        self._output_path: Path | None = None
        self._events_path: Path | None = None
        self._frames_path: Path | None = None
        self._binary: BinaryIO | None = None
        self._events_file: BinaryIO | None = None
        self._frames_file: BinaryIO | None = None
        self._session_metadata: dict | None = None
        self._frame_count = 0

    def start_recording(self, session_metadata: dict, output_path: str) -> None:
        if self._binary is not None:
            raise RuntimeError("Recording already in progress")

        self._output_path = Path(output_path)
        self._events_path = self._output_path.with_suffix(self._output_path.suffix + ".events")
        self._frames_path = self._output_path.with_suffix(self._output_path.suffix + ".frames")
        self._session_metadata = dict(session_metadata)
        self._frame_count = 0

        header_bytes = json.dumps(self._session_metadata, separators=(",", ":")).encode("ascii")
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._binary = self._output_path.open("wb")
        self._binary.write(header_bytes)
        self._binary.write(_HEADER_TERMINATOR)

        self._events_file = self._events_path.open("w", encoding="ascii")
        self._frames_file = self._frames_path.open("w", encoding="ascii")

    def write_frame(self, frame: dict) -> None:
        if self._binary is None:
            raise RuntimeError("Recording not started")

        for ch_idx, channel in enumerate(frame["channels"]):
            quantized: list[float] = []
            for sample in channel:
                value = float(_FLOAT32.unpack(_FLOAT32.pack(float(sample)))[0])
                self._binary.write(_FLOAT32.pack(value))
                quantized.append(value)
            frame["channels"][ch_idx] = quantized

        frame_meta = {
            "frameIndex": frame["frameIndex"],
            "timestampNs": frame["timestampNs"],
        }
        if "eventMarkers" in frame:
            frame_meta["eventMarkers"] = frame["eventMarkers"]
        assert self._frames_file is not None
        self._frames_file.write(json.dumps(frame_meta, separators=(",", ":")) + "\n")

        if "eventMarkers" in frame:
            assert self._events_file is not None
            for marker in frame["eventMarkers"]:
                event = dict(marker)
                event["frameIndex"] = frame["frameIndex"]
                self._events_file.write(json.dumps(event, separators=(",", ":")) + "\n")

        self._frame_count += 1

    def stop_recording(self) -> None:
        if self._binary is None:
            return

        if self._session_metadata is not None:
            self._session_metadata["totalFrames"] = self._frame_count

        self._binary.close()
        self._binary = None

        if self._events_file is not None:
            self._events_file.close()
            self._events_file = None

        if self._frames_file is not None:
            self._frames_file.close()
            self._frames_file = None

    @staticmethod
    async def replay(ndf_path: str, realtime: bool = True) -> AsyncIterator[dict]:
        path = Path(ndf_path)
        with path.open("rb") as handle:
            header_bytes = bytearray()
            while True:
                chunk = handle.read(1)
                if not chunk:
                    raise ValueError("Unexpected EOF while reading .ndf header")
                header_bytes.extend(chunk)
                if header_bytes.endswith(_HEADER_TERMINATOR):
                    break

            header_json = header_bytes[: -len(_HEADER_TERMINATOR)].decode("ascii")
            metadata = json.loads(header_json)
            device_info = metadata["deviceInfo"]

            num_channels = int(device_info["numChannels"])
            sample_rate_hz = float(device_info["sampleRateHz"])
            channel_labels = list(device_info["channelLabels"])
            device_id = str(device_info["deviceId"])

            samples_per_frame = int(metadata.get("samplesPerFrame", 10))
            binary = handle.read()

        frames_path = path.with_suffix(path.suffix + ".frames")
        frame_meta_lines: list[dict] = []
        if frames_path.exists():
            frame_meta_lines = [
                json.loads(line)
                for line in frames_path.read_text(encoding="ascii").splitlines()
                if line.strip()
            ]

        samples_per_frame_total = num_channels * samples_per_frame
        bytes_per_frame = samples_per_frame_total * _FLOAT32.size
        total_frames = len(binary) // bytes_per_frame
        frame_period_sec = samples_per_frame / sample_rate_hz

        for frame_index in range(total_frames):
            offset = frame_index * bytes_per_frame
            chunk = binary[offset : offset + bytes_per_frame]
            flat = struct.unpack(f"<{samples_per_frame_total}f", chunk)

            channels: list[list[float]] = []
            idx = 0
            for _ch in range(num_channels):
                channels.append([float(v) for v in flat[idx : idx + samples_per_frame]])
                idx += samples_per_frame

            if frame_index < len(frame_meta_lines):
                meta = frame_meta_lines[frame_index]
                timestamp_ns = meta["timestampNs"]
                event_markers = meta.get("eventMarkers")
            else:
                started_ms = int(metadata.get("startedAtMs", 0))
                period_ns = int(round(1e9 * frame_period_sec))
                timestamp_ns = str(started_ms * 1_000_000 + frame_index * period_ns)
                event_markers = None

            frame: dict = {
                "deviceId": device_id,
                "frameIndex": frame_index,
                "timestampNs": timestamp_ns,
                "signalType": "EEG",
                "channels": channels,
                "samplesPerFrame": samples_per_frame,
                "sampleRateHz": sample_rate_hz,
                "channelLabels": channel_labels,
                "calibrated": True,
            }
            if event_markers is not None:
                frame["eventMarkers"] = event_markers

            if realtime and frame_index > 0:
                await asyncio.sleep(frame_period_sec)

            yield frame
