"""
End-to-end tests for IntentEngine.

Acceptance criteria (from JOB.md):
  - Processes 100 motor_imagery_left FeatureVectors, emits ≥ 65 % motor_imagery_left
    IntentEvents with confidence ≥ 0.6.
  - All output dicts pass JSON Schema validation against IntentEvent.schema.json.
  - Artifact-flagged vectors → 'idle' label.
  - async run() interface works correctly.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import numpy as np
import pytest

from intent_engine.classifiers.lda_classifier import LDAClassifier
from intent_engine.engine import EngineConfig, IntentEngine
from intent_engine.normalizer import IntentNormalizer

from .conftest import make_feature_vector, make_mi_dataset

# Schema location relative to monorepo root
_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "jobs"
    / "00_shared_contracts"
    / "json-schema"
    / "IntentEvent.schema.json"
)

# Optional jsonschema import
try:
    import jsonschema

    _SCHEMA = json.loads(_SCHEMA_PATH.read_text())
    _JSONSCHEMA_AVAILABLE = True
except (ImportError, FileNotFoundError):
    _JSONSCHEMA_AVAILABLE = False


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_engine(confidence_threshold: float = 0.50) -> IntentEngine:
    """Build and return a trained IntentEngine for 2-class MI."""
    X, y = make_mi_dataset(n_per_class=100, seed=42)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    config = EngineConfig(confidence_threshold=confidence_threshold)
    return IntentEngine(classifier=clf, config=config, normalizer=IntentNormalizer(alpha=0.01))


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_single_vector_returns_dict():
    engine = _build_engine()
    fv = make_feature_vector("motor_imagery_left", seed=0)
    event = engine.process(fv)
    assert event is not None
    assert isinstance(event, dict)
    assert "intentId" in event
    assert "label" in event
    assert "confidence" in event


def test_required_fields_present():
    engine = _build_engine()
    required = {
        "intentId", "label", "confidence", "posteriors", "classifierType",
        "sourceVectorId", "timestampNs", "endToEndLatencyMs",
        "featureImportance", "artifactFlag", "feedbackLabel",
    }
    fv = make_feature_vector("motor_imagery_left", seed=1)
    event = engine.process(fv)
    assert event is not None
    missing = required - set(event.keys())
    assert not missing, f"Missing fields: {missing}"


def test_source_vector_id_matches():
    engine = _build_engine()
    fv = make_feature_vector("motor_imagery_right", seed=2)
    event = engine.process(fv)
    assert event is not None
    assert event["sourceVectorId"] == fv["vectorId"]


def test_confidence_in_unit_interval():
    engine = _build_engine()
    for seed in range(20):
        fv = make_feature_vector("motor_imagery_left", seed=seed)
        event = engine.process(fv)
        if event is not None:
            assert 0.0 <= event["confidence"] <= 1.0


def test_posteriors_sum_to_one():
    engine = _build_engine()
    for seed in range(20):
        fv = make_feature_vector("motor_imagery_left", seed=seed)
        event = engine.process(fv)
        if event is not None:
            total = sum(event["posteriors"].values())
            assert abs(total - 1.0) < 1e-5, f"Posteriors sum to {total}"


def test_artifact_flag_yields_idle():
    """Vectors with artifactFlag=True must produce 'idle' label."""
    engine = _build_engine(confidence_threshold=0.50)
    fv = make_feature_vector("motor_imagery_left", seed=5, artifact=True)
    event = engine.process(fv)
    assert event is not None
    assert event["label"] == "idle"
    assert event["artifactFlag"] is True


def test_motor_imagery_left_65_percent():
    """≥ 65 % of 100 left FeatureVectors must emit motor_imagery_left with conf ≥ 0.6."""
    engine = _build_engine(confidence_threshold=0.55)
    n_total = 100
    n_correct = 0
    for seed in range(n_total):
        fv = make_feature_vector("motor_imagery_left", seed=seed)
        event = engine.process(fv)
        if (
            event is not None
            and event["label"] == "motor_imagery_left"
            and event["confidence"] >= 0.6
        ):
            n_correct += 1
    rate = n_correct / n_total
    assert rate >= 0.65, f"Only {rate:.1%} of left events classified correctly (need ≥ 65 %)"


def test_classifier_type_field():
    engine = _build_engine()
    valid_types = {"lda", "csp_lda", "p300_template", "cnn", "lstm", "transformer", "ensemble"}
    fv = make_feature_vector("motor_imagery_left", seed=0)
    event = engine.process(fv)
    assert event is not None
    assert event["classifierType"] in valid_types


def test_feedback_label_is_null():
    engine = _build_engine()
    fv = make_feature_vector("motor_imagery_left", seed=0)
    event = engine.process(fv)
    assert event is not None
    assert event["feedbackLabel"] is None


@pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema not installed")
def test_json_schema_validation():
    """All IntentEvent dicts must pass JSON Schema validation."""
    engine = _build_engine()
    for seed in range(30):
        fv = make_feature_vector("motor_imagery_left", seed=seed)
        event = engine.process(fv)
        if event is not None:
            jsonschema.validate(instance=event, schema=_SCHEMA)


@pytest.mark.asyncio
async def test_async_run():
    """async run() yields IntentEvent dicts for each FeatureVector."""
    engine = _build_engine()

    async def make_stream():
        for seed in range(10):
            yield make_feature_vector("motor_imagery_left", seed=seed)

    events = []
    async for event in engine.run(make_stream()):
        events.append(event)

    assert len(events) == 10
    for event in events:
        assert "label" in event
        assert "confidence" in event
