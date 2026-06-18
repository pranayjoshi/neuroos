# NeuroOS

**NeuroOS is like iOS for brain-computer interfaces.**

Just as iOS abstracts iPhone sensors and exposes clean APIs, NeuroOS abstracts brain signal complexity and delivers reliable **intent detection** to application developers. One API works across EEG, EMG, and ECoG hardware. No PhD required to build BCI apps.

The architecture is grounded in the [BCI2000 four-module model](https://www.bci2000.org) (Schalk et al., 2004): **source → signal processing → user application → operator**. NeuroOS modernizes this with typed contracts, an AI intent layer, REST/WebSocket APIs, and developer SDKs.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Start the Platform](#start-the-platform)
  - [TypeScript SDK](#typescript-sdk)
  - [Python SDK](#python-sdk)
  - [REST API](#rest-api)
  - [WebSocket Streaming](#websocket-streaming)
  - [Data Generator (Standalone)](#data-generator-standalone)
- [Configuration](#configuration)
- [Applications & Use Cases](#applications--use-cases)
- [Intent Labels](#intent-labels)
- [BCI Paradigms Supported](#bci-paradigms-supported)
- [Performance Targets](#performance-targets)
- [Testing](#testing)
- [Docker](#docker)
- [Development](#development)
- [Agent Job System](#agent-job-system)
- [Roadmap](#roadmap)
- [References](#references)
- [License](#license)

---

## Features

| Capability | Description |
|---|---|
| **Hardware-agnostic platform** | Swap EEG headsets or simulators without changing app code |
| **AI-powered intent recognition** | LDA, CSP-LDA, P300 template matching, ensemble classifiers |
| **Real-time DSP pipeline** | Calibration, spatial filtering, artifact rejection, AR spectral estimation |
| **Built-in simulator** | Multi-channel EEG/EMG synthesis for development without hardware |
| **Developer-first SDKs** | TypeScript (`@neuroos/sdk`) and Python (`neuroos`) clients with React hooks |
| **Typed contracts** | Shared schemas for `RawSignalFrame`, `FeatureVector`, `IntentEvent` |
| **Session management** | Start/pause/stop recording with persisted metadata and `.ndf` files |
| **Plugin system** | Register third-party device adapters without patching core |

---

## Architecture

```
Hardware / Electrodes
        │  raw μV samples
        ▼
┌───────────────────┐
│  Data Generator   │  Job 01 — EEG/EMG simulator (Source Module)
│  (Python)         │
└────────┬──────────┘
         │  RawSignalFrame
         ▼
┌───────────────────┐
│  DSP Pipeline     │  Job 02 — Calibrate → Filter → Extract features
│  (Python)         │
└────────┬──────────┘
         │  FeatureVector
         ▼
┌───────────────────┐
│  Intent Engine    │  Job 03 — Classify features → decode intent
│  (Python)         │
└────────┬──────────┘
         │  IntentEvent
         ▼
┌───────────────────┐
│  Platform Core    │  Job 04 — Registry, sessions, REST/WS API
│  (TypeScript)     │
└────────┬──────────┘
         │  REST / WebSocket
         ▼
┌───────────────────┐
│  Developer SDK    │  Job 05 — @neuroos/sdk + neuroos (Python)
└───────────────────┘
         │
         ▼
   Your Application
```

**Inter-process communication:** Python services communicate with Platform Core via **JSONL** (one JSON object per line) over stdin/stdout pipes. This keeps the stack language-agnostic and low-latency.

**Shared contracts:** All modules import types from [`jobs/00_shared_contracts/`](jobs/00_shared_contracts/). Never redefine these types in individual packages.

---

## Repository Structure

```
neuroos/
├── jobs/                          # Agent job specs (architecture + contracts)
│   ├── 00_shared_contracts/       # TypeScript schemas + JSON Schema + constants
│   ├── 01_data_generator/         # Job spec + signal synthesis reference
│   ├── 02_dsp_pipeline/
│   ├── 03_intent_engine/
│   ├── 04_platform_core/
│   ├── 05_developer_sdk/
│   └── 06_cicd_infra/             # Wave 4 — CI/CD (planned)
├── packages/
│   ├── data-generator/            # EEG/EMG simulator + .ndf recorder
│   ├── dsp-pipeline/              # Bio-signal processing cascade
│   ├── intent-engine/             # AI classifiers + online adaptation
│   ├── platform-core/             # OS layer: API, sessions, pipeline orchestration
│   ├── sdk/                       # @neuroos/sdk (TypeScript + React hooks)
│   └── sdk-python/                # neuroos (Python client)
├── docker-compose.yml             # Multi-service dev environment
├── package.json                   # pnpm workspace root
├── pnpm-workspace.yaml
└── turbo.json
```

---

## Prerequisites

| Tool | Version | Used by |
|---|---|---|
| **Node.js** | ≥ 20 | Platform Core, SDK |
| **pnpm** | ≥ 9 | Monorepo package management |
| **Python** | ≥ 3.11 | Data generator, DSP, Intent Engine |
| **Docker** (optional) | ≥ 24 | Full-stack containerized dev |

---

## Installation

### 1. Clone and install Node dependencies

```bash
git clone <repository-url> neuroos
cd neuroos
pnpm install
```

### 2. Install Python packages (editable mode)

```bash
pip install -e packages/data-generator
pip install -e packages/dsp-pipeline
pip install -e packages/intent-engine
pip install -e packages/sdk-python
```

For development with test dependencies:

```bash
pip install -e "packages/data-generator[dev]"
pip install -e "packages/dsp-pipeline[dev]"
pip install -e "packages/intent-engine[dev]"
pip install -e "packages/sdk-python[dev]"
```

### 3. Build TypeScript packages

```bash
pnpm build
```

### 4. Copy configuration (optional)

Platform Core reads `neuroos.config.yaml` at startup. The default config is at:

```
packages/platform-core/config/neuroos.config.yaml
```

Point to it with the `NEUROOS_CONFIG` environment variable, or copy it to the repo root and customize.

---

## Quick Start

### Option A — Docker (recommended for full stack)

```bash
docker compose up --build
```

Platform Core will be available at `http://localhost:3000`. Check health:

```bash
curl http://localhost:3000/health
```

### Option B — Local development

**Terminal 1 — Platform Core**

```bash
cd packages/platform-core
pnpm build
NEUROOS_CONFIG=./config/neuroos.config.yaml \
  node --input-type=module -e "import { startServer } from './dist/api/server.js'; startServer()"
```

**Terminal 2 — Register device and start session**

```bash
# Register the built-in simulator
curl -X POST http://localhost:3000/devices/register \
  -H "Content-Type: application/json" \
  -d '{"adapterName":"neuroos-simulator","config":{"numChannels":16,"sampleRateHz":256}}'

# Start a motor imagery session
curl -X POST http://localhost:3000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"simulator:default:SIM-001","subjectId":"demo","sessionName":"quickstart","paradigm":"motor_imagery"}'
```

**Terminal 3 — Stream intents (WebSocket)**

Connect to `ws://localhost:3000/stream/intents` and receive `IntentEvent` JSON messages at ~16 Hz.

Or use the Python SDK:

```bash
python -c "
import asyncio
from neuroos import NeuroOS

async def main():
    async with NeuroOS() as client:
        device = await client.devices.register('neuroos-simulator', num_channels=16)
        session = await client.sessions.start(
            device_id=device['deviceId'],
            subject_id='demo',
            session_name='quickstart',
            paradigm='motor_imagery',
        )
        count = 0
        async for intent in client.intents.stream():
            print(f\"{intent['label']:25s}  conf={intent['confidence']:.2f}  latency={intent['endToEndLatencyMs']:.1f}ms\")
            count += 1
            if count >= 20:
                break
        await client.sessions.stop(session['sessionId'])

asyncio.run(main())
"
```

> **Note:** By default, Platform Core uses lightweight inline Python stubs for the DSP and Intent subprocesses. To wire the full Python packages, set `NEUROOS_DSP_SCRIPT` and `NEUROOS_INTENT_SCRIPT` environment variables to wrapper scripts that invoke `python -m cli` and `python -m intent_engine` respectively. Wave 4 CI/CD will provide Makefile targets for this.

---

## Usage

### Start the Platform

| Method | Command |
|---|---|
| Docker | `docker compose up` |
| Local (after build) | See [Quick Start Option B](#option-b--local-development) |
| Health check | `curl http://localhost:3000/health` |
| Diagnostics | `curl http://localhost:3000/operator/diagnostics` |

### TypeScript SDK

Install from the workspace (or publish target):

```typescript
import { NeuroOS } from "@neuroos/sdk";

const neuroos = new NeuroOS({ baseUrl: "http://localhost:3000" });

// Register simulator and start session
const { deviceId } = await neuroos.devices.register("neuroos-simulator", {
  numChannels: 16,
  sampleRateHz: 256,
});

const session = await neuroos.sessions.start({
  deviceId,
  subjectId: "sub-001",
  sessionName: "motor-imagery-run",
  paradigm: "motor_imagery",
});

// Stream intents
const stream = neuroos.intents.stream();
stream.on("intent", (event) => {
  console.log(event.label, event.confidence);
});

// Send feedback for online adaptation
stream.sendFeedback(event.intentId, "motor_imagery_left");

// Cleanup
await neuroos.sessions.stop(session.sessionId);
await stream.close();
```

#### React hooks

```tsx
import { NeuroOSProvider, useIntent, useSession } from "@neuroos/sdk/react";

function BCIApp() {
  const { session, startSession } = useSession();
  const { intent, isConnected } = useIntent({
    filter: ["motor_imagery_left", "motor_imagery_right"],
    minConfidence: 0.65,
  });

  return (
    <div>
      {!session && <button onClick={() => startSession({ paradigm: "motor_imagery" })}>Start</button>}
      {isConnected && <p>Intent: {intent?.label} ({((intent?.confidence ?? 0) * 100).toFixed(0)}%)</p>}
    </div>
  );
}
```

Wrap your app with `<NeuroOSProvider baseUrl="http://localhost:3000">`.

### Python SDK

```python
import asyncio
from neuroos import NeuroOS

async def main():
    async with NeuroOS(base_url="http://localhost:3000") as client:
        device = await client.devices.register("neuroos-simulator", num_channels=16)
        session = await client.sessions.start(
            device_id=device["deviceId"],
            subject_id="sub-001",
            session_name="python-demo",
            paradigm="motor_imagery",
        )

        async for intent in client.intents.stream():
            print(intent["label"], intent["confidence"])
            break  # demo: print one intent

        await client.sessions.stop(session["sessionId"])

asyncio.run(main())
```

Synchronous helpers are also available: `register_sync()`, `start_sync()`, `stream_sync()`.

### REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/devices/register` | Register a device adapter |
| `GET` | `/devices` | List registered devices |
| `POST` | `/sessions/start` | Start a recording session |
| `POST` | `/sessions/:id/pause` | Pause session |
| `POST` | `/sessions/:id/resume` | Resume session |
| `POST` | `/sessions/:id/stop` | Stop session |
| `GET` | `/sessions` | List sessions |
| `GET` | `/operator/diagnostics` | Device + pipeline diagnostics |
| `GET` | `/operator/signal?channels=C3,C4&seconds=5` | Recent raw signal frames |
| `GET` | `/operator/features?seconds=5` | Recent feature vectors |
| `WS` | `/stream/intents` | Real-time intent event stream |

#### Register a device

```bash
curl -X POST http://localhost:3000/devices/register \
  -H "Content-Type: application/json" \
  -d '{
    "adapterName": "neuroos-simulator",
    "config": {
      "numChannels": 16,
      "sampleRateHz": 256,
      "samplesPerFrame": 16
    }
  }'
```

#### Start a session

```bash
curl -X POST http://localhost:3000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "simulator:default:SIM-001",
    "subjectId": "sub-001",
    "sessionName": "mi-session-1",
    "paradigm": "motor_imagery"
  }'
```

Built-in adapters: `neuroos-simulator`, `openbci-cyton`. Third-party adapters load via the plugin system (`pluginPath` in config).

### WebSocket Streaming

Connect to `ws://localhost:3000/stream/intents`.

**Server → client messages:**

```json
{ "type": "connected", "sessionId": "...", "deviceId": "...", "version": "0.1.0" }
{ "type": "intent", "data": { "intentId": "...", "label": "motor_imagery_left", "confidence": 0.87, ... } }
{ "type": "session_stopped", "sessionId": "...", "totalFrames": 1024 }
{ "type": "error", "code": "PIPELINE_ERROR", "message": "..." }
```

**Client → server messages:**

```json
{ "type": "feedback", "intentId": "...", "trueLabel": "motor_imagery_left" }
{ "type": "ping" }
```

Feedback events enable **online adaptation** — the Intent Engine updates classifier weights from confirmed labels.

### Data Generator (Standalone)

Run the EEG simulator independently and pipe JSONL frames to stdout:

```bash
# List available scenarios
python -m data_generator --list-scenarios

# Stream motor imagery left scenario (16 channels, 256 Hz)
python -m data_generator --scenario motor_imagery_left --channels 16 --duration 30

# Record to .ndf file (NeuroOS Data Format)
python -m data_generator --scenario rest --channels 16 --record ./recording.ndf

# Replay a recording
python -m data_generator --replay ./recording.ndf
```

**Available scenarios:**

| Scenario | Dominant intent | Description |
|---|---|---|
| `rest` | `motor_imagery_rest` | Idle sensorimotor rhythms |
| `motor_imagery_left` | `motor_imagery_left` | ERD at C4, ERS at C3 |
| `motor_imagery_right` | `motor_imagery_right` | ERD at C3, ERS at C4 |
| `p300_target` | `p300_target` | P300 evoked response at Pz |
| `artifact_heavy` | `idle` | EMG bursts on temporal channels |
| `mixed_sequence` | varies | Cycles through all scenarios |

Pipe frames through the DSP pipeline:

```bash
python -m data_generator --scenario motor_imagery_left --channels 16 --duration 10 \
  | python -m cli
```

---

## Configuration

Platform behavior is controlled by `neuroos.config.yaml`:

```yaml
version: "1.0"

device:
  adapter: "neuroos-simulator"
  numChannels: 16
  sampleRateHz: 256
  samplesPerFrame: 16

dsp:
  spatialFilterType: "car"              # car | laplacian | csp | none
  temporalFilterType: "autoregressive"  # bandpass_fir | autoregressive | p300_average | slow_wave
  bandpassHz: [1, 40]
  windowLengthSec: 1.0
  windowStepSec: 0.0625                 # 16 Hz update rate

intent:
  classifierType: "lda"                 # lda | csp_lda | p300_template | cnn | ensemble
  modelPath: null                       # null = bundled pretrained model
  inferenceRateHz: 16
  confidenceThreshold: 0.6

paradigm:
  type: "motor_imagery"                 # motor_imagery | p300_speller | scp_control | free
  trialLengthSec: 4.0
  itiSec: 2.0

api:
  port: 3000
  host: "127.0.0.1"

storage:
  sessionsDir: "~/.neuroos/sessions"
  maxSessionAgeDays: 30
```

Set the config path:

```bash
export NEUROOS_CONFIG=/path/to/neuroos.config.yaml
```

Sessions are persisted under `~/.neuroos/sessions/<sessionId>/` with metadata, raw `.ndf` recordings, and intent logs.

---

## Applications & Use Cases

NeuroOS is designed for assistive technology, research, and consumer BCI apps. Developers subscribe to `IntentEvent` streams — they never touch raw EEG.

### Motor imagery control

Use `motor_imagery_left` / `motor_imagery_right` / `motor_imagery_rest` to drive UI:

- **Cursor control** — move a pointer left/right on screen
- **Wheelchair navigation** — directional commands from imagined hand movement
- **Gaming** — control characters with imagined left/right hand movement
- **Smart home** — turn devices on/off with distinct imagery patterns

Typical accuracy: 65–95% with CSP-LDA after calibration (~20 trials per class).

### P300 speller

Use `p300_target` / `p300_non_target` in a row/column flashing matrix (Donchin paradigm):

- **Communication aids** — spell words for locked-in patients
- **Menu selection** — choose items from a grid without muscle control

Typical accuracy: 80–99% with 15+ averages per row/column.

### Slow cortical potential (SCP) control

Use `scp_positive` / `scp_negative` for binary control:

- **Cursor up/down** — cortical positivity/negativity at Cz
- **Yes/no communication** — binary decision interface

### Passive monitoring

Use `attention_high`, `attention_low`, `blink`, `jaw_clench`:

- **Focus detection** — trigger break reminders when attention drops
- **Emergency stop** — jaw clench as a high-reliability interrupt
- **Accessibility** — blink-based click for users with limited mobility

### Research & prototyping

- Run experiments with the built-in simulator — no hardware required
- Record sessions to `.ndf` for offline analysis
- Swap DSP filters and classifiers via config without rewriting app code
- Compare algorithms systematically (the core motivation behind BCI2000)

---

## Intent Labels

NeuroOS defines 14 canonical intent labels. App code should only react to these strings:

| Label | Display name | Typical use |
|---|---|---|
| `motor_imagery_left` | Left Hand Imagery | Cursor left, scroll left |
| `motor_imagery_right` | Right Hand Imagery | Cursor right, click |
| `motor_imagery_both_hands` | Both Hands Imagery | Confirm, zoom |
| `motor_imagery_feet` | Feet Imagery | Scroll down, accelerate |
| `motor_imagery_rest` | Rest / Idle | No action, pause |
| `p300_target` | P300 Target | Selected character/item |
| `p300_non_target` | P300 Non-Target | Unselected stimulus |
| `scp_positive` | Cortical Positivity | Cursor up, yes |
| `scp_negative` | Cortical Negativity | Cursor down, no |
| `attention_high` | High Attention | Focus mode |
| `attention_low` | Low Attention | Break reminder |
| `blink` | Eye Blink | Click, back |
| `jaw_clench` | Jaw Clench | Emergency stop |
| `idle` | Idle | Below confidence threshold |

Full definitions with neural basis and accuracy ranges: [`jobs/00_shared_contracts/constants/intent_labels.ts`](jobs/00_shared_contracts/constants/intent_labels.ts).

---

## BCI Paradigms Supported

| Paradigm | Signal basis | Classifier | Info transfer rate |
|---|---|---|---|
| **Motor imagery** | Alpha/beta ERD at C3/C4 | CSP-LDA, LDA | 20–35 bits/min |
| **P300 speller** | Evoked potential ~300 ms | Template matching | 20–25 bits/min |
| **SCP control** | Slow cortical potentials | Slow-wave filter + LDA | 10–20 bits/min |
| **Passive monitoring** | Attention bands, artifacts | Threshold detectors | N/A |

---

## Performance Targets

Based on BCI2000 benchmarks (Schalk et al., 2004, Table I):

| Metric | BCI2000 (C++) | NeuroOS target |
|---|---|---|
| End-to-end output latency | 15.11 ms mean | < 15 ms |
| Latency jitter (σ) | 0.75 ms | < 2 ms |
| DSP per-frame processing | ~5 ms (total budget) | < 5 ms |
| Intent inference | ~5 ms | < 3 ms |
| Motor imagery accuracy | ~80–90% | ≥ 75% |
| P300 accuracy | 90–99% | ≥ 80% |

NeuroOS uses Python for DSP/ML (vs. BCI2000's C++), with NumPy vectorization and ONNX Runtime to stay within these budgets.

---

## Testing

### TypeScript (Platform Core + SDK)

```bash
pnpm test                    # all packages via Turborepo
pnpm --filter @neuroos/platform-core test
pnpm --filter @neuroos/sdk test
pnpm typecheck
```

### Python (Data Generator, DSP, Intent Engine, SDK)

```bash
pytest packages/data-generator/tests -v
pytest packages/dsp-pipeline/tests -v
pytest packages/intent-engine/tests -v
pytest packages/sdk-python/tests -v
```

### Benchmarks (Intent Engine + DSP)

```bash
pytest packages/intent-engine/tests/test_performance.py -v
pytest packages/dsp-pipeline/tests/test_performance.py -v --benchmark-only
```

---

## Docker

`docker-compose.yml` defines four services:

| Service | Package | Role |
|---|---|---|
| `data-generator` | Job 01 | Streams simulated EEG frames |
| `dsp-pipeline` | Job 02 | Processes frames → features |
| `intent-engine` | Job 03 | Classifies features → intents |
| `platform` | Job 04 | REST/WS API on port 3000 |

```bash
# Start full stack
docker compose up --build

# Start platform only
docker compose up platform

# Environment overrides
SCENARIO=motor_imagery_right NUM_CHANNELS=16 docker compose up data-generator
```

Sessions persist in the `neuroos-sessions` Docker volume.

---

## Development

### Monorepo commands

```bash
pnpm install          # install all Node dependencies
pnpm build            # build all TypeScript packages
pnpm dev              # start dev mode (persistent, per-package)
pnpm test             # run all tests
pnpm typecheck        # TypeScript type checking
pnpm clean            # remove build artifacts
```

### Python package layout

Each Python package is installable in editable mode and exposes a JSONL CLI:

| Package | Module | CLI |
|---|---|---|
| `neuroos-data-generator` | `data_generator` | `python -m data_generator` |
| `neuroos-dsp-pipeline` | `cli` / `pipeline` | `python -m cli` |
| `neuroos-intent-engine` | `intent_engine` | `python -m intent_engine` |
| `neuroos` (SDK) | `neuroos` | import in application code |

### Adding a device adapter

Implement the `DeviceAdapter` interface from shared contracts:

```typescript
import type { DeviceAdapter, RawSignalFrame } from "@neuroos/shared-contracts/schema";

class MyHeadsetAdapter implements DeviceAdapter {
  readonly deviceId = "myvendor:headset:001";
  readonly adapterName = "My BCI Headset";
  // ... implement connect(), startRecording(), on("frame", ...), etc.
}
```

Register via the plugin system or POST `/devices/register` with `pluginPath`.

---

## Agent Job System

NeuroOS was built using a **parallel agent architecture**. Each job in [`jobs/`](jobs/) is a self-contained module spec with typed input/output contracts, acceptance criteria, and scope boundaries. Multiple AI agents built the system in waves:

| Wave | Jobs | Status |
|---|---|---|
| **Wave 1** | Job 00 — Shared Contracts | Complete |
| **Wave 2** | Jobs 01–04 — Data Gen, DSP, Intent, Platform | Complete |
| **Wave 3** | Job 05 — Developer SDK | Complete |
| **Wave 4** | Job 06 — CI/CD & Infrastructure | Planned |

See [`jobs/README.md`](jobs/README.md) for the full agent coordination guide.

---

## Roadmap

Wave 4 (CI/CD) will deliver:

- [ ] `Makefile` — `make dev`, `make test`, `make lint`, `make benchmark`
- [ ] GitHub Actions — lint, unit tests, integration tests, latency gate (< 15 ms P95)
- [ ] Full pipeline wiring — Platform Core → real DSP/Intent subprocesses by default
- [ ] Integration test harness — scenario accuracy across all canned scenarios
- [ ] Benchmark suite replicating BCI2000 Table I
- [ ] Example apps — cursor control, P300 speller, motor imagery game
- [ ] npm/PyPI publish pipeline for SDK packages
- [ ] OpenAPI docs + Docusaurus site

Future beyond Wave 4:

- OpenBCI Cyton hardware adapter
- ONNX neural classifier (EEGNet) for improved motor imagery accuracy
- Multi-user session support
- Cloud-hosted Platform Core

---

## References

- Schalk, G. et al. (2004). *BCI2000: A General-Purpose Brain-Computer Interface (BCI) System.* IEEE Transactions on Biomedical Engineering, 51(6), 1034–1043. [doi:10.1109/TBME.2004.827072](https://doi.org/10.1109/TBME.2004.827072)
- [BCI2000 project](https://www.bci2000.org)
- Wolpaw, J.R. et al. (2002). *Brain-computer interfaces for communication and control.* Clinical Neurophysiology, 113(6), 767–791.
- Lawhern, V.J. et al. (2018). *EEGNet: A Compact Convolutional Network for EEG-based Brain-Computer Interfaces.* Journal of Neural Engineering, 15(5).

---

## License

See repository license file. Intended for research and educational use.
