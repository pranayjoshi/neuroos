# Integration Test Strategy — CI/CD Context

Testing strategy and patterns for the full NeuroOS integration test suite.

---

## Test Pyramid

```
           ┌───────────────────┐
           │  Integration (5%) │  Full stack: simulator → SDK
           │  E2E latency tests│
           ├───────────────────┤
           │  Component (20%)  │  Platform Core + SDK API tests
           │  WebSocket tests  │
           ├───────────────────┤
           │   Unit Tests      │  Each package: pytest + vitest
           │      (75%)        │  Mocked dependencies
           └───────────────────┘
```

---

## Service Startup Order for Integration Tests

```
1. data-generator starts (fast, no dependencies)
2. dsp-pipeline starts (imports numpy/scipy)
3. intent-engine starts (imports sklearn, onnxruntime)
4. platform-core starts (spawns Python subprocesses)
5. platform-core healthcheck: GET /health → 200
6. Tests run
```

In CI (GitHub Actions), use `npx wait-on` to wait for healthcheck:
```bash
npx wait-on http://localhost:3000/health --timeout 30000
```

---

## Latency Measurement Methodology

Mirrors BCI2000 Table I methodology (Schalk et al., 2004):

**Output Latency** = mean time from frame acquisition to IntentEvent emission
- Measured via `IntentEvent.endToEndLatencyMs`
- Target: <15.11 ms (BCI2000 configuration A mean)

**Latency Jitter** = standard deviation of output latency
- Target: <0.75 ms (BCI2000 Table I)
- NeuroOS relaxed target: <2 ms (Python overhead vs. C++)

**System Clock Jitter** = variation in intervals between successive frame acquisitions
- Measured at the DeviceSimulator level
- Target: <4.31 ms (BCI2000 Table I)

**Processor Load** = CPU % used by each service
- Measured via `/operator/diagnostics` API
- Target: <59% per service (BCI2000 Table I upper bound)

### Python vs. BCI2000 (C++) Latency

BCI2000 was implemented in C++. NeuroOS uses Python for DSP/Intent.
Expected overhead: +3–8 ms vs. C++ baseline.

Mitigation strategies:
1. NumPy vectorization (BLAS-optimized, near C speed for matrix ops)
2. ONNX Runtime for neural classifier (native C++ inference)
3. JSONL pipe vs. network socket (eliminates TCP stack overhead)
4. Pre-allocated numpy arrays (avoid GC pressure)
5. Process priority: `nice -n -5` for DSP + intent processes in production

---

## Test Isolation Patterns

### Unit Tests: Full Mocking

Each Python package tests in isolation with mocked dependencies:

```python
# packages/dsp-pipeline/tests/test_dsp_pipeline.py
import numpy as np
from dsp_pipeline import DSPPipeline, DSPConfig

def make_test_frame(num_channels=16, samples_per_frame=10) -> dict:
    """Create a minimal RawSignalFrame dict for testing."""
    return {
        "deviceId": "test:mock:TEST-001",
        "frameIndex": 0,
        "timestampNs": str(1_000_000_000_000_000_000),
        "signalType": "EEG",
        "channels": np.random.randn(num_channels, samples_per_frame).tolist(),
        "samplesPerFrame": samples_per_frame,
        "sampleRateHz": 256,
        "channelLabels": [f"Ch{i}" for i in range(num_channels)],
        "calibrated": True,
    }

def test_pipeline_produces_feature_vector():
    pipeline = DSPPipeline(DSPConfig.default())
    frame = make_test_frame()
    result = pipeline.process(frame)
    assert "vectorId" in result
    assert "bandPowers" in result
    assert "alpha" in result["bandPowers"]
    assert result["artifactFlag"] in (True, False)
```

### Component Tests: Platform Core with Stub Adapters

```typescript
// packages/platform-core/tests/api.test.ts
import { build } from '../src/api/server';

const mockAdapter: DeviceAdapter = {
  deviceId: 'test:mock:TEST-001',
  adapterName: 'MockAdapter',
  state: 'connected',
  on: vi.fn().mockReturnThis(),
  off: vi.fn().mockReturnThis(),
  connect: vi.fn().mockResolvedValue({ deviceId: 'test:mock:TEST-001', ... }),
  startRecording: vi.fn().mockResolvedValue(undefined),
  pauseRecording: vi.fn().mockResolvedValue(undefined),
  stopRecording: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn().mockResolvedValue(undefined),
  getDiagnostics: vi.fn().mockResolvedValue({ impedanceKOhm: [], batteryPercent: null, ... }),
};

test('POST /devices/register returns deviceId', async () => {
  const app = await build({ adapter: mockAdapter });
  const response = await app.inject({
    method: 'POST',
    url: '/devices/register',
    body: { adapterName: 'mock', config: {} },
  });
  expect(response.statusCode).toBe(200);
  expect(response.json()).toHaveProperty('deviceId');
});
```

### Integration Tests: Full Stack

Use the actual simulator, actual DSP, actual intent engine:

```python
# tests/integration/test_full_pipeline.py
import asyncio, pytest
from neuroos import NeuroOS

@pytest.fixture(scope="module")
async def running_client():
    """Fixture: assumes platform core is running at localhost:3000."""
    async with NeuroOS() as client:
        device = await client.devices.register("neuroos-simulator", num_channels=16)
        session = await client.sessions.start(
            device_id=device["deviceId"],
            subject_id="ci-test",
            session_name="ci-integration",
            paradigm="motor_imagery",
        )
        yield client, session
        await client.sessions.stop(session["sessionId"])

@pytest.mark.asyncio
async def test_receives_10_intents(running_client):
    client, _ = running_client
    intents = []
    async for intent in client.intents.stream():
        intents.append(intent)
        if len(intents) >= 10:
            break
    assert len(intents) == 10

@pytest.mark.asyncio
async def test_all_intents_have_valid_schema(running_client):
    import jsonschema, json
    schema = json.load(open("jobs/00_shared_contracts/json-schema/IntentEvent.schema.json"))
    client, _ = running_client
    intents = []
    async for intent in client.intents.stream():
        intents.append(intent)
        if len(intents) >= 5:
            break
    for intent in intents:
        jsonschema.validate(intent, schema)  # raises if invalid
```

---

## Benchmark: Replicating BCI2000 Table I

BCI2000 tested three configurations. NeuroOS should measure against equivalent setups:

| Config | Channels | Sample Rate | Samples/Frame | Frame Rate |
|---|---|---|---|---|
| A (NeuroOS default) | 16 | 256 Hz | 16 | 16 Hz |
| B (high density) | 64 | 256 Hz | 16 | 16 Hz |
| C (high speed) | 16 | 25000 Hz | 1000 | 25 Hz |

```python
# tests/benchmarks/bench_e2e_latency.py
import asyncio, statistics, pytest
from neuroos import NeuroOS

CONFIGS = [
    {"name": "A (16ch, 256Hz)", "num_channels": 16, "sample_rate_hz": 256},
    {"name": "B (64ch, 256Hz)", "num_channels": 64, "sample_rate_hz": 256},
]

@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.asyncio
async def test_latency_config(config, benchmark):
    latencies = []
    async with NeuroOS() as client:
        device = await client.devices.register("neuroos-simulator", **config)
        session = await client.sessions.start(device_id=device["deviceId"], ...)
        async for intent in client.intents.stream():
            latencies.append(intent["endToEndLatencyMs"])
            if len(latencies) >= 1000:
                break
        await client.sessions.stop(session["sessionId"])

    print(f"\n{'='*50}")
    print(f"Config: {config['name']}")
    print(f"  Output Latency:  {statistics.mean(latencies):.2f} ms (BCI2000: 15.11 ms)")
    print(f"  Latency Jitter:  {statistics.stdev(latencies):.2f} ms (BCI2000: 0.75 ms)")
    print(f"  P95 Latency:     {sorted(latencies)[950]:.2f} ms")
    print(f"  P99 Latency:     {sorted(latencies)[990]:.2f} ms")
    print(f"  Max Latency:     {max(latencies):.2f} ms")
    print(f"{'='*50}")

    assert statistics.mean(latencies) < 25.0, "Mean latency >25ms (Python overhead budget exceeded)"
    assert statistics.stdev(latencies) < 5.0, "Jitter >5ms"
```

---

## Release Process

```
1. Merge to main → CI passes (all tests + latency gate)
2. Maintainer creates tag: git tag v0.2.0 && git push origin v0.2.0
3. release.yml triggers:
   a. Build @neuroos/sdk-ts → npm publish
   b. Build neuroos Python SDK → twine upload to PyPI
   c. Generate CHANGELOG.md from conventional commits
   d. Create GitHub Release with changelog
4. Announce in Discord #releases
```

### Semantic Versioning

- **MAJOR (1.x.x):** Breaking changes to IntentEvent, DeviceAdapter, or SDK public API
- **MINOR (x.1.x):** New intent labels, new classifiers, new API endpoints
- **PATCH (x.x.1):** Bug fixes, performance improvements, doc updates

### Schema Compatibility

When `IntentEvent.ts` or `DeviceAdapter.ts` changes:
1. Bump major version if field removed or type narrowed
2. Bump minor version if field added (optional field)
3. Never change field names without deprecation cycle

---

## Pre-commit Hooks (optional but recommended)

```json
// .husky/pre-commit
pnpm lint-staged

// package.json lint-staged config:
{
  "lint-staged": {
    "*.ts": ["eslint --fix", "prettier --write"],
    "*.py": ["ruff check --fix", "ruff format"]
  }
}
```
