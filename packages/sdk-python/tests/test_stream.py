import pytest

from neuroos.stream import parse_intent_event


def test_parse_intent_event() -> None:
    event = parse_intent_event(
        {
            "intentId": "abc",
            "label": "motor_imagery_left",
            "confidence": 0.91,
            "posteriors": {"motor_imagery_left": 0.91},
            "classifierType": "lda",
            "sourceVectorId": "vec-1",
            "timestampNs": "1700000000000000000",
            "endToEndLatencyMs": 11.2,
            "featureImportance": {},
            "artifactFlag": False,
            "feedbackLabel": None,
        }
    )

    assert event["label"] == "motor_imagery_left"
    assert event["confidence"] == pytest.approx(0.91)
    assert event["timestampNs"] == "1700000000000000000"
