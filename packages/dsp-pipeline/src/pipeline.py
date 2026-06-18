"""Main DSP pipeline orchestrator."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import numpy as np
from scipy.ndimage import uniform_filter1d

from artifact.artifact_detector import ArtifactDetector
from calibration.calibrator import Calibrator
from config import DSPConfig
from constants.signal_bands import BAND_NAMES
from features.band_power import compute_band_powers
from features.erd_computer import ERDComputer
from spatial.car_filter import CARFilter
from spatial.csp_filter import CSPFilter
from spatial.laplacian_filter import LaplacianFilter
from temporal.ar_spectral import ARSpectralEstimator, estimate_psd_burg
from temporal.bandpass_fir import BandpassFIR
from temporal.p300_averager import P300Averager
from utils.ring_buffer import RingBuffer


class PipelineLatencyError(RuntimeError):
    """Raised when per-frame processing exceeds the configured latency budget."""


class Pipeline:
    """
    Orchestrates RawSignalFrame → FeatureVector processing cascade.

    Pipeline: Calibrator → SpatialFilter → ArtifactDetector →
              TemporalFilter → FeatureExtractor
    """

    def __init__(self, config: DSPConfig | None = None) -> None:
        self.config = config or DSPConfig.default()
        self._lock = threading.Lock()
        self._calibrator = Calibrator(
            gain_uv_per_unit=self.config.gain_uv_per_unit,
            offset_uv=self.config.offset_uv,
            baseline_window_sec=self.config.baseline_window_sec,
        )
        self._car = CARFilter()
        self._laplacian = LaplacianFilter(self.config.standard_16_channel_labels)
        self._csp = CSPFilter(n_components=self.config.n_csp_components)
        self._artifact_detector: ArtifactDetector | None = None
        self._ar_estimator: ARSpectralEstimator | None = None
        self._bandpass: BandpassFIR | None = None
        self._p300: P300Averager | None = None
        self._erd = ERDComputer(baseline_sec=self.config.erd_baseline_sec)
        self._signal_buffer: RingBuffer | None = None
        self._configured = False
        self._sample_rate_hz = 160.0
        self._samples_per_frame = 10
        self._channel_labels: list[str] = list(self.config.standard_16_channel_labels)
        self._source_frame_indices: list[int] = []
        self._last_timestamp_ns = "0"

    def calibrate(self, frames: list[dict[str, Any]]) -> None:
        """Fit operators that require calibration data."""
        if not frames:
            return

        first = frames[0]
        self._configure_from_frame(first)
        stacked = np.concatenate(
            [np.asarray(frame["channels"], dtype=np.float64) for frame in frames],
            axis=1,
        )
        self._calibrator.fit(stacked)

        if self.config.spatial_method == "csp":
            class1, class2 = _split_csp_calibration(frames)
            if class1 and class2:
                trials1 = np.stack(class1, axis=0)
                trials2 = np.stack(class2, axis=0)
                self._csp.fit_classes(trials1, trials2)

    def process(self, frame: dict[str, Any]) -> dict[str, Any]:
        """Process one RawSignalFrame dict and return a FeatureVector dict."""
        with self._lock:
            return self._process_unlocked(frame)

    def _process_unlocked(self, frame: dict[str, Any]) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        self._configure_from_frame(frame)

        signal = np.asarray(frame["channels"], dtype=np.float64)
        already_calibrated = bool(frame.get("calibrated", False))
        calibrated = self._calibrator.process(signal, already_calibrated=already_calibrated)
        spatial = self._apply_spatial_filter(calibrated)
        _, artifact_flag, artifact_type = self._artifact_detector.detect(spatial)

        self._signal_buffer.append(spatial)
        window = self._signal_buffer.get_window()
        filtered = self._apply_temporal_filter(window)

        freqs, psd = estimate_psd_burg(
            filtered,
            self.config.ar_order,
            self.config.ar_nfft,
            self._sample_rate_hz,
        )
        band_powers = compute_band_powers(psd, freqs)
        self._erd.update_baseline(band_powers)
        erd = self._erd.compute(band_powers)

        spatial_features = np.sqrt(np.mean(spatial**2, axis=1))
        evoked_response = self._update_evoked_response(frame, window)

        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        if self.config.enforce_latency and latency_ms > self.config.max_latency_ms:
            raise PipelineLatencyError(
                f"Processing latency {latency_ms:.3f} ms exceeds "
                f"budget of {self.config.max_latency_ms} ms"
            )

        frame_index = int(frame["frameIndex"])
        self._source_frame_indices.append(frame_index)
        if len(self._source_frame_indices) > 10:
            self._source_frame_indices.pop(0)
        self._last_timestamp_ns = str(frame["timestampNs"])

        output_channel_labels = self._output_channel_labels()
        result: dict[str, Any] = {
            "vectorId": str(uuid.uuid4()),
            "sourceFrameIndices": list(self._source_frame_indices),
            "timestampNs": self._last_timestamp_ns,
            "deviceId": frame["deviceId"],
            "signalType": frame["signalType"],
            "bandPowers": {name: band_powers[name].tolist() for name in BAND_NAMES},
            "spatialFeatures": spatial_features.tolist(),
            "erd": {name: erd[name].tolist() for name in BAND_NAMES},
            "evokedResponse": evoked_response,
            "artifactFlag": artifact_flag,
            "processingLatencyMs": latency_ms,
            "channelLabels": output_channel_labels,
        }
        if artifact_flag and artifact_type is not None:
            result["artifactType"] = artifact_type
        return result

    def _configure_from_frame(self, frame: dict[str, Any]) -> None:
        sample_rate = float(frame["sampleRateHz"])
        samples_per_frame = int(frame["samplesPerFrame"])
        labels = list(frame["channelLabels"])
        num_channels = len(labels)

        if (
            self._configured
            and sample_rate == self._sample_rate_hz
            and samples_per_frame == self._samples_per_frame
            and labels == self._channel_labels
        ):
            return

        self._sample_rate_hz = sample_rate
        self._samples_per_frame = samples_per_frame
        self._channel_labels = labels
        self._calibrator.configure(sample_rate, num_channels)
        self._laplacian.set_channel_labels(labels)
        self._artifact_detector = ArtifactDetector(
            sample_rate_hz=sample_rate,
            emg_threshold_sd=self.config.emg_threshold_sd,
            ocular_threshold_uv=self.config.ocular_threshold_uv,
            saturation_clip_uv=self.config.saturation_clip_uv,
            motion_threshold_uv=self.config.motion_threshold_uv,
            channel_labels=labels,
        )
        window_samples = max(
            self.config.ar_order + 1,
            int(self.config.ar_window_sec * sample_rate),
        )
        self._signal_buffer = RingBuffer(window_samples, num_channels)
        self._ar_estimator = ARSpectralEstimator(
            sample_rate_hz=sample_rate,
            order=self.config.ar_order,
            nfft=self.config.ar_nfft,
        )
        self._bandpass = BandpassFIR(
            low_hz=self.config.bandpass_low_hz,
            high_hz=self.config.bandpass_high_hz,
            sample_rate_hz=sample_rate,
            num_taps=self.config.bandpass_num_taps,
        )
        self._p300 = P300Averager(
            sample_rate_hz=sample_rate,
            epoch_start_sec=self.config.p300_epoch_start_sec,
            epoch_end_sec=self.config.p300_epoch_end_sec,
            num_averages=self.config.p300_num_averages,
        )
        self._erd.configure(num_channels, sample_rate, samples_per_frame)
        self._configured = True

    def _apply_spatial_filter(self, signal: np.ndarray) -> np.ndarray:
        method = self.config.spatial_method
        if method == "car":
            return self._car.process(signal)
        if method == "laplacian":
            return self._laplacian.process(signal)
        if method == "csp":
            return self._csp.process(signal)
        return self._car.process(signal)

    def _apply_temporal_filter(self, signal: np.ndarray) -> np.ndarray:
        method = self.config.temporal_method
        if method == "bandpass_fir" and self._bandpass is not None:
            return self._bandpass.process(signal)
        if method == "slow_wave":
            window_samples = max(1, int(self.config.slow_wave_window_sec * self._sample_rate_hz))
            baseline_samples = max(
                1,
                int(self.config.slow_wave_baseline_sec * self._sample_rate_hz),
            )
            baseline_samples = min(baseline_samples, signal.shape[1])
            smoothed = uniform_filter1d(signal, size=window_samples, axis=1)
            baseline = smoothed[:, :baseline_samples].mean(axis=1, keepdims=True)
            return smoothed - baseline
        return signal

    def _update_evoked_response(
        self,
        frame: dict[str, Any],
        window: np.ndarray,
    ) -> list[float] | None:
        if self._p300 is None:
            return None
        markers = frame.get("eventMarkers") or []
        for marker in markers:
            offset = int(marker["sampleOffset"])
            global_offset = window.shape[1] - self._samples_per_frame + offset
            self._p300.add_epoch(window, global_offset)

        average = self._p300.get_average()
        if average is None:
            return None

        label_to_idx = {label: idx for idx, label in enumerate(self._channel_labels)}
        if "Pz" in label_to_idx:
            return average[label_to_idx["Pz"]].tolist()
        return average.reshape(-1).tolist()

    def _output_channel_labels(self) -> list[str]:
        if self.config.spatial_method == "csp" and self._csp.output_labels:
            return self._csp.output_labels
        return list(self._channel_labels)


DSPPipeline = Pipeline


def _split_csp_calibration(
    frames: list[dict[str, Any]],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    class1: list[np.ndarray] = []
    class2: list[np.ndarray] = []
    for frame in frames:
        scenario = frame.get("scenario") or frame.get("paradigmClass")
        signal = np.asarray(frame["channels"], dtype=np.float64)
        if scenario in {"motor_imagery_left", "class1", "left"}:
            class1.append(signal)
        elif scenario in {"motor_imagery_right", "class2", "right"}:
            class2.append(signal)
    return class1, class2
