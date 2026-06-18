# Job 01 — EEG/EMG Dummy Data Generator

**Agent Role:** Data Generator  
**Language:** Python 3.11  
**Depends on:** Job 00 (read `../00_shared_contracts/schema/` for type reference; implement the Python equivalents)  
**Consumed by:** Job 02 (DSP Pipeline), Job 06 (CI/CD integration tests)

---

## Purpose

Simulate realistic BCI hardware so that all downstream agents (DSP, Intent Engine, Platform, SDK) can develop and test without physical devices.

This is NeuroOS's equivalent of iOS Simulator — a software replica of the hardware source module that produces bit-for-bit compatible data frames.

---

## Deliverables

All code lives in `packages/data-generator/` within the NeuroOS monorepo.

### Source files (`src/`)

| File | Class | Responsibility |
|---|---|---|
| `generators/eeg_generator.py` | `EEGGenerator` | Synthesize multi-channel EEG |
| `generators/emg_generator.py` | `EMGGenerator` | Synthesize muscle artifact signal |
| `device/device_simulator.py` | `DeviceSimulator` | Wrap generators, implement DeviceAdapter protocol |
| `device/data_recorder.py` | `DataRecorder` | Save / replay .ndf files |
| `scenarios/scenario_library.py` | `ScenarioLibrary` | Canned BCI test scenarios |
| `scenarios/scenario.py` | `Scenario` (dataclass) | Scenario configuration |
| `__main__.py` | — | `python -m data_generator` CLI entry |

### Tests (`tests/`)

- `test_eeg_generator.py` — validates waveform statistics (band powers, SNR)
- `test_emg_generator.py` — validates artifact burst statistics
- `test_device_simulator.py` — validates frame rate, schema compliance
- `test_data_recorder.py` — round-trip save/load test

### Config (`config/`)

- `default_config.yaml` — default simulation parameters

---

## EEGGenerator Specification

```python
class EEGGenerator:
    def __init__(
        self,
        num_channels: int,          # 8, 16, or 64
        sample_rate_hz: int,        # 160 or 256
        channel_labels: list[str],  # e.g. ["Fp1","Fp2","C3","C4","Cz","P3","P4","Oz"]
        snr_db: float = 10.0,       # signal-to-noise ratio
        random_seed: int | None = None,
    ): ...

    def generate_frame(
        self,
        scenario: "Scenario",
        frame_index: int,
    ) -> dict:  # matches RawSignalFrame JSON schema
        """
        Synthesize one frame of EEG data for the given scenario.
        Returns a dict matching RawSignalFrame JSON schema (calibrated=True, μV).
        """
```

**Signal synthesis per scenario:**

| Scenario | Alpha (8–12 Hz) | Beta (18–26 Hz) | Notes |
|---|---|---|---|
| `rest` | High power (10–20 μV) bilateral | Moderate | Idle sensorimotor rhythms |
| `motor_imagery_left` | ERD at C4 (−30%), ERS at C3 | ERD at C4 | Contralateral suppression |
| `motor_imagery_right` | ERD at C3 (−30%), ERS at C4 | ERD at C3 | |
| `p300_target` | Background alpha | Background beta | + P300 component at Pz, 300 ms post-stimulus |
| `artifact_heavy` | Normal | Normal | + 200–500 Hz EMG bursts on T3/T4 |

**Synthesis method:**
1. Generate pink noise baseline across all channels using AR(1) process
2. Add sinusoidal components at band center frequencies
3. Apply spatial covariance (channels are correlated, not independent)
4. Add white noise floor scaled to achieve `snr_db`
5. Scale to μV range per `SIGNAL_TYPE_PROFILES["EEG"].amplitudeRangeUV`

---

## EMGGenerator Specification

```python
class EMGGenerator:
    def __init__(
        self,
        affected_channels: list[int],  # channel indices where EMG appears
        burst_probability: float = 0.1, # probability per frame of a burst
        amplitude_uv: tuple[float, float] = (200, 2000),
    ): ...

    def apply_artifact(self, frame: dict, frame_index: int) -> dict:
        """Inject EMG artifact into an existing EEG frame in-place."""
```

---

## DeviceSimulator Specification

```python
class DeviceSimulator:
    """
    Implements the Python equivalent of the DeviceAdapter TypeScript interface.
    Streams RawSignalFrame-compatible dicts via asyncio queue at real-time rate.
    """
    def __init__(self, config: SimulatorConfig): ...

    async def connect(self) -> dict:            # returns DeviceInfo-compatible dict
    async def start_recording(self) -> None:   # begins emitting frames
    async def pause_recording(self) -> None
    async def stop_recording(self) -> None
    async def disconnect(self) -> None

    async def frame_stream(self) -> AsyncIterator[dict]:
        """Yields one RawSignalFrame dict per frame period."""
```

Frame emission timing: if `sample_rate_hz=256` and `samples_per_frame=16`, emit one frame every `16/256 = 62.5 ms`.

---

## DataRecorder Specification

```python
class DataRecorder:
    """
    Save and replay sessions in .ndf (NeuroOS Data Format).

    File format (modeled after BCI2000):
    - ASCII header: JSON-serialized SessionMetadata (terminated by \r\n\r\n)
    - Binary body: little-endian float32 samples, row-major [frames × channels × samples]
    - Event markers: separate .ndf.events JSON Lines sidecar file
    """
    def start_recording(self, session_metadata: dict, output_path: str) -> None
    def write_frame(self, frame: dict) -> None
    def stop_recording(self) -> None

    @staticmethod
    def replay(ndf_path: str, realtime: bool = True) -> AsyncIterator[dict]
```

---

## ScenarioLibrary

```python
SCENARIOS: dict[str, Scenario] = {
    "rest":                 Scenario(label="motor_imagery_rest",  duration_sec=10, ...),
    "motor_imagery_left":   Scenario(label="motor_imagery_left",  duration_sec=4,  ...),
    "motor_imagery_right":  Scenario(label="motor_imagery_right", duration_sec=4,  ...),
    "p300_target":          Scenario(label="p300_target",         duration_sec=2,  stimulus_onset_sec=0.5),
    "artifact_heavy":       Scenario(label="idle",                duration_sec=5,  emg_burst_probability=0.4),
    "mixed_sequence":       Scenario(...),  # cycles through all scenarios
}
```

---

## CLI Interface

```
python -m data_generator --scenario motor_imagery_left --channels 16 --duration 30
python -m data_generator --replay path/to/recording.ndf
python -m data_generator --list-scenarios
```

Output: streams JSON-serialized RawSignalFrame dicts to stdout, one per line (JSONL format).
The Platform Core can spawn this as a subprocess and pipe its stdout.

---

## Dependencies

```
numpy>=1.26
scipy>=1.12
asyncio (stdlib)
click>=8.1        # CLI
pyyaml>=6.0       # config
pytest>=7.4       # tests
```

No ML frameworks. No network I/O. Pure signal synthesis.

---

## Acceptance Criteria

- [ ] `pytest tests/ -v` passes with zero failures
- [ ] `EEGGenerator` produces alpha band power that is ≥20% lower at C4 during `motor_imagery_left` compared to `rest` (ERD validation)
- [ ] `DeviceSimulator.frame_stream()` emits frames within ±5 ms of the expected frame period (timing accuracy)
- [ ] Generated frames pass JSON Schema validation against `../00_shared_contracts/json-schema/RawSignalFrame.schema.json`
- [ ] `DataRecorder` round-trip: saved and replayed data is bit-for-bit identical
- [ ] `python -m data_generator --scenario rest --channels 8 --duration 2` runs without error

---

## Must NOT Do

- Apply any filtering or feature extraction (that is Job 02's scope)
- Implement any classification or intent detection (Job 03)
- Open network sockets or HTTP servers (Job 04)
- Import from any other job folder except `00_shared_contracts` (for type reference only)
