"""TypedDicts matching shared NeuroOS contracts."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


IntentLabel = Literal[
    "motor_imagery_left",
    "motor_imagery_right",
    "motor_imagery_both_hands",
    "motor_imagery_feet",
    "motor_imagery_rest",
    "p300_target",
    "p300_non_target",
    "scp_positive",
    "scp_negative",
    "attention_high",
    "attention_low",
    "blink",
    "jaw_clench",
    "idle",
]

ClassifierType = Literal[
    "lda",
    "csp_lda",
    "p300_template",
    "cnn",
    "lstm",
    "transformer",
    "ensemble",
]

SessionState = Literal["initializing", "active", "paused", "completed", "error"]
DeviceState = Literal["disconnected", "connecting", "connected", "recording", "paused", "error"]
SignalType = Literal["EEG", "EMG", "ECoG", "LFP", "SPIKE"]
ParadigmType = Literal["motor_imagery", "p300_speller", "scp_control", "free"]


class IntentEvent(TypedDict):
    intentId: str
    label: IntentLabel
    confidence: float
    posteriors: dict[str, float]
    classifierType: ClassifierType
    sourceVectorId: str
    timestampNs: str
    endToEndLatencyMs: float
    featureImportance: dict[str, list[float]]
    artifactFlag: bool
    feedbackLabel: IntentLabel | None


class IntentEventSummary(TypedDict):
    intentId: str
    label: IntentLabel
    confidence: float
    endToEndLatencyMs: float
    timestampNs: str
    artifactFlag: bool


class DeviceInfo(TypedDict):
    deviceId: str
    vendor: str
    model: str
    firmwareVersion: str
    numChannels: int
    sampleRateHz: int
    signalType: SignalType
    channelLabels: list[str]
    adResolutionBits: int
    referenceElectrode: str
    state: NotRequired[DeviceState]


class DeviceDiagnostics(TypedDict):
    impedanceKOhm: list[float]
    batteryPercent: float | None
    signalQuality: list[float]
    droppedFrames: int
    timestampMs: int


class SessionMetadata(TypedDict, total=False):
    sessionId: str
    sessionName: str
    subjectId: str
    state: SessionState
    startedAtMs: int
    endedAtMs: int | None
    totalFrames: int
    droppedFrames: int
    deviceInfo: DeviceInfo
    pipelineConfig: dict[str, object]
    notes: str
    neuroosVersion: str


class RegisterDeviceResponse(TypedDict):
    deviceId: str
    state: DeviceState
