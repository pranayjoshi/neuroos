"""
IntentEngine — main orchestrator for NeuroOS intent classification.

Pipeline per FeatureVector:
  1. Validate and extract feature arrays from the FeatureVector dict.
  2. Route to active classifier (LDA by default; CSP-LDA if spatialFeatures
     are present; P300Detector if evokedResponse is present).
  3. Apply IntentNormalizer → calibrated posteriors.
  4. Apply confidence threshold (suppress idle-level events).
  5. Emit an IntentEvent dict that matches the JSON schema.

Inference rate:  16 Hz default (configurable 1–50 Hz).
Latency budget:  <3 ms per vector (excluding I/O), <15 ms end-to-end.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

import numpy as np

from .classifiers.base_classifier import ClassificationResult, IntentClassifier
from .classifiers.ensemble_classifier import EnsembleClassifier
from .classifiers.lda_classifier import LDAClassifier
from .classifiers.p300_template_classifier import P300Detector
from .normalizer import IntentNormalizer

# Default motor imagery labels (2-class)
_MI_LABELS = ["motor_imagery_left", "motor_imagery_right"]
# Canonical MI channels expected by the feature extractor
_MI_CHANNELS = ["C3", "Cz", "C4"]
_MI_BANDS = ["alpha", "beta"]


@dataclass
class EngineConfig:
    """Dataclass for IntentEngine configuration."""

    classifier_type: str = "lda"
    """Active classifier: 'lda' | 'csp_lda' | 'p300_template' | 'ensemble'."""

    confidence_threshold: float = 0.55
    """Below this confidence the engine suppresses the event (emits 'idle')."""

    inference_rate_hz: float = 16.0
    """Target inference rate in Hz (1–50 Hz)."""

    normalizer_alpha: float = 0.01
    """EMA alpha for IntentNormalizer (smaller = slower adaptation)."""

    mi_channels: list[str] = field(default_factory=lambda: list(_MI_CHANNELS))
    """Channel labels to use for band-power feature extraction."""

    mi_bands: list[str] = field(default_factory=lambda: list(_MI_BANDS))
    """Frequency bands to include in the LDA feature vector."""


class IntentEngine:
    """
    Orchestrator: consumes FeatureVector dicts and emits IntentEvent dicts.

    Parameters
    ----------
    classifier:
        Fitted IntentClassifier instance.  If None, a default unfitted
        LDAClassifier is created (useful for offline calibration flows).
    config:
        EngineConfig dataclass; defaults are used if not provided.
    normalizer:
        IntentNormalizer instance; created from config if not provided.
    """

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        config: EngineConfig | None = None,
        normalizer: IntentNormalizer | None = None,
    ) -> None:
        self._config = config or EngineConfig()
        self._clf: IntentClassifier = classifier or LDAClassifier()
        self._normalizer = normalizer or IntentNormalizer(alpha=self._config.normalizer_alpha)

    # ------------------------------------------------------------------
    # Async streaming API
    # ------------------------------------------------------------------

    async def run(
        self, feature_stream: AsyncIterator[dict]
    ) -> AsyncIterator[dict]:
        """
        Async generator: consumes FeatureVector stream, yields IntentEvent dicts.

        Parameters
        ----------
        feature_stream:
            Async iterable of FeatureVector dicts (validated by caller).
        """
        async for fv in feature_stream:
            event = self._process(fv)
            if event is not None:
                yield event
            await asyncio.sleep(0)  # yield control

    # ------------------------------------------------------------------
    # Synchronous single-vector API (used by __main__ loop)
    # ------------------------------------------------------------------

    def process(self, feature_vector: dict) -> dict | None:
        """
        Classify one FeatureVector dict and return an IntentEvent dict.

        Returns None if the input has an artifact flag or confidence is below
        threshold and idle events are suppressed.
        """
        return self._process(feature_vector)

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def _process(self, fv: dict) -> dict | None:
        t_start_ns = time.perf_counter_ns()

        # Extract features based on active classifier type
        try:
            features, classifier_type = self._extract_features(fv)
        except Exception:
            return None

        # Run classifier
        try:
            result: ClassificationResult = self._clf.predict(features)
        except Exception:
            return None

        # Calibrate confidence scores
        calibrated = self._normalizer.normalize(result.posteriors)
        best_label = max(calibrated, key=calibrated.__getitem__)
        best_conf = calibrated[best_label]

        # Apply confidence threshold
        artifact_flag = bool(fv.get("artifactFlag", False))
        if artifact_flag or best_conf < self._config.confidence_threshold:
            best_label = "idle"
            # Rebuild posteriors with idle winning
            idle_conf = 1.0 - best_conf
            calibrated = {k: (idle_conf / max(len(calibrated) - 1, 1)) for k in calibrated}
            calibrated["idle"] = 1.0 - sum(v for k, v in calibrated.items() if k != "idle")
            best_conf = calibrated.get("idle", 0.5)

        t_end_ns = time.perf_counter_ns()
        latency_ms = (t_end_ns - t_start_ns) / 1_000_000.0
        # Add feature extraction + I/O margin for reported end-to-end latency
        e2e_latency_ms = latency_ms + float(fv.get("processingLatencyMs", 0.0))

        event = {
            "intentId": str(uuid.uuid4()),
            "label": best_label,
            "confidence": round(float(best_conf), 6),
            "posteriors": {k: round(v, 6) for k, v in calibrated.items()},
            "classifierType": classifier_type,
            "sourceVectorId": fv.get("vectorId", str(uuid.uuid4())),
            "timestampNs": fv.get("timestampNs", str(time.time_ns())),
            "endToEndLatencyMs": round(e2e_latency_ms, 3),
            "featureImportance": result.feature_importance,
            "artifactFlag": artifact_flag,
            "feedbackLabel": None,
        }
        return event

    # ------------------------------------------------------------------
    # Feature extraction from FeatureVector
    # ------------------------------------------------------------------

    def _extract_features(self, fv: dict) -> tuple[np.ndarray, str]:
        """
        Extract the appropriate feature array from a FeatureVector dict.

        Returns (features_array, classifier_type_string).

        Routing logic:
        - If evokedResponse is non-null and classifier is P300Detector → P300 path.
        - If spatialFeatures is non-empty → CSP-LDA path.
        - Otherwise → band-power LDA path.
        """
        # P300 path
        evoked = fv.get("evokedResponse")
        if (
            evoked is not None
            and len(evoked) > 0
            and isinstance(self._clf, P300Detector)
        ):
            return np.array(evoked, dtype=np.float32), "p300_template"

        # CSP-LDA path (spatialFeatures available)
        spatial = fv.get("spatialFeatures", [])
        if spatial and len(spatial) > 0:
            arr = np.array(spatial, dtype=np.float32)
            if not np.all(arr == 0):
                if isinstance(self._clf, EnsembleClassifier):
                    return arr, "ensemble"
                return arr, "csp_lda"

        # Default: band-power LDA features
        features = self._extract_band_power_features(fv)
        if isinstance(self._clf, EnsembleClassifier):
            return features, "ensemble"
        return features, "lda"

    def _extract_band_power_features(self, fv: dict) -> np.ndarray:
        """
        Build the LDA feature vector from band powers.

        Layout: [alpha_C3, alpha_Cz, alpha_C4, beta_C3, beta_Cz, beta_C4, ...]
        Falls back to 0.0 for missing channels or bands.
        """
        channel_labels: list[str] = fv.get("channelLabels", [])
        band_powers: dict = fv.get("bandPowers", {})
        features: list[float] = []

        for band in self._config.mi_bands:
            bp = band_powers.get(band, [])
            for ch in self._config.mi_channels:
                if ch in channel_labels:
                    idx = channel_labels.index(ch)
                    val = float(bp[idx]) if idx < len(bp) else 0.0
                else:
                    val = 0.0
                features.append(val)

        return np.array(features, dtype=np.float32)
