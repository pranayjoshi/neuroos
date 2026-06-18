# Job 04 — Platform Core

**Agent Role:** Platform Architect  
**Language:** TypeScript (Node.js 20)  
**Depends on:** Job 00 (schemas define all data contracts), Job 01 + 02 + 03 (spawned as subprocesses)  
**Consumed by:** Job 05 (Developer SDK builds on this API), Job 06 (CI/CD tests this service)

---

## Purpose

Platform Core is the OS layer of NeuroOS — the central nervous system that wires hardware, DSP, and intent together and exposes a clean API to developers.

Just as iOS provides UIKit/CoreMotion APIs that abstract sensor complexity, Platform Core provides `/stream/intents` that abstracts brain signal complexity. Developers interact only with this API — they never touch RawSignalFrame or FeatureVector.

---

## Deliverables

All code lives in `packages/platform-core/` in the NeuroOS monorepo.

### Source files (`src/`)

| File | Class / Module | Responsibility |
|---|---|---|
| `registry/device_registry.ts` | `DeviceRegistry` | Register/discover/validate device adapters |
| `session/session_manager.ts` | `SessionManager` | Session lifecycle: start/pause/stop |
| `pipeline/pipeline_orchestrator.ts` | `PipelineOrchestrator` | Wire adapter → DSP → Intent as subprocess chain |
| `bus/event_bus.ts` | `EventBus` | Internal typed pub/sub |
| `config/config_store.ts` | `ConfigStore` | YAML config loading and validation |
| `config/schema_validator.ts` | `SchemaValidator` | Runtime JSON Schema validation with Ajv |
| `plugins/plugin_system.ts` | `PluginSystem` | Third-party adapter registration |
| `api/server.ts` | — | Fastify server setup, middleware, lifecycle |
| `api/routes/devices.ts` | — | Device management routes |
| `api/routes/sessions.ts` | — | Session management routes |
| `api/routes/stream.ts` | — | WebSocket intent streaming |
| `api/routes/operator.ts` | — | Operator dashboard: diagnostics, signal viz |
| `api/types.ts` | — | Request/response types for all API routes |

### Config (`config/`)

- `neuroos.config.yaml` — default configuration with all options documented
- `neuroos.config.schema.json` — JSON Schema for config validation

### Tests (`tests/`)

- `device_registry.test.ts`
- `session_manager.test.ts`
- `pipeline_orchestrator.test.ts`
- `event_bus.test.ts`
- `api.test.ts` — integration tests using supertest + ws
- `latency.test.ts` — end-to-end latency assertion (<15 ms)

---

## EventBus

Internal typed pub/sub. All inter-module communication goes through here.

```typescript
import type { RawSignalFrame, FeatureVector, IntentEvent, SessionMetadata } from '../00_shared_contracts/schema';

type EventMap = {
  'signal.frame':    RawSignalFrame;
  'dsp.features':    FeatureVector;
  'intent.event':    IntentEvent;
  'session.started': SessionMetadata;
  'session.paused':  { sessionId: string; timestamp: number };
  'session.stopped': { sessionId: string; totalFrames: number };
  'device.connected': import('../00_shared_contracts/schema').DeviceInfo;
  'device.error':     import('../00_shared_contracts/schema').DeviceAdapterError;
};

class EventBus extends EventEmitter {
  emit<K extends keyof EventMap>(event: K, data: EventMap[K]): boolean;
  on<K extends keyof EventMap>(event: K, listener: (data: EventMap[K]) => void): this;
  once<K extends keyof EventMap>(event: K, listener: (data: EventMap[K]) => void): this;
  off<K extends keyof EventMap>(event: K, listener: (data: EventMap[K]) => void): this;
}
```

---

## DeviceRegistry

```typescript
class DeviceRegistry {
  /**
   * Register an adapter. Validates that it implements the DeviceAdapter interface.
   * Throws if a device with the same deviceId is already registered.
   */
  register(adapter: DeviceAdapter): void;

  unregister(deviceId: string): void;

  getAdapter(deviceId: string): DeviceAdapter | undefined;

  listAdapters(): Array<{ deviceId: string; adapterName: string; state: DeviceState }>;

  /**
   * Subscribe to device lifecycle events. Called by PipelineOrchestrator.
   */
  onFrame(deviceId: string, handler: (frame: RawSignalFrame) => void): () => void;
}
```

---

## SessionManager

```typescript
class SessionManager {
  async startSession(params: {
    deviceId: string;
    subjectId: string;
    sessionName: string;
    paradigm: PipelineConfig['paradigm']['type'];
  }): Promise<SessionMetadata>;

  async pauseSession(sessionId: string): Promise<void>;
  async resumeSession(sessionId: string): Promise<void>;
  async stopSession(sessionId: string): Promise<SessionMetadata>;

  getActiveSession(): SessionMetadata | null;
  getSession(sessionId: string): SessionMetadata | undefined;
  listSessions(): SessionMetadata[];

  /**
   * Persist session metadata and .ndf index to disk.
   * Directory: ~/.neuroos/sessions/<sessionId>/
   */
  private persistSession(session: SessionMetadata): Promise<void>;
}
```

---

## PipelineOrchestrator

```typescript
class PipelineOrchestrator {
  /**
   * Spawn DSP pipeline and Intent Engine as child processes.
   * Wire frame stream via stdin/stdout JSONL pipes.
   *
   * Data flow:
   *   DeviceAdapter --frame--> (JSONL to stdin) --> dsp_pipeline subprocess
   *                                                    --> (JSONL stdout) --> IntentEngine subprocess
   *                                                                            --> (JSONL stdout) --> EventBus
   *
   * Latency monitoring:
   *   Track end-to-end latency = IntentEvent.timestampNs - RawSignalFrame.timestampNs
   *   Log warning if > 15ms. Emit 'pipeline.latency_warning' event if > 20ms.
   */
  async start(session: SessionMetadata): Promise<void>;
  async stop(): Promise<void>;
  async pause(): Promise<void>;
  async resume(): Promise<void>;

  getLatencyStats(): { mean: number; p95: number; p99: number; max: number };
}
```

**Subprocess communication protocol:** JSONL (one JSON object per line) over stdin/stdout.
This avoids gRPC complexity while remaining language-agnostic.

---

## ConfigStore

```typescript
class ConfigStore {
  constructor(configPath: string = 'neuroos.config.yaml') {}

  load(): void;  // reads and validates config file
  get<T>(path: string): T;  // dot-notation access: get('dsp.temporalFilterType')
  set(path: string, value: unknown): void;  // runtime override
  watch(path: string, callback: (value: unknown) => void): () => void;  // live reload
}
```

---

## REST API Routes

### POST /devices/register
Register a built-in or plugin adapter by name.
```json
// Request
{ "adapterName": "neuroos-simulator", "config": { "numChannels": 16, "sampleRateHz": 256 } }
// Response
{ "deviceId": "simulator:default:SIM-001", "state": "connected" }
```

### GET /devices
List all registered devices with state and diagnostics.

### POST /sessions/start
```json
// Request
{ "deviceId": "simulator:default:SIM-001", "subjectId": "sub-001", "sessionName": "motor-imagery-run-1", "paradigm": "motor_imagery" }
// Response: SessionMetadata
```

### POST /sessions/:id/pause
### POST /sessions/:id/resume
### POST /sessions/:id/stop

### GET /sessions
List historical sessions.

### WS /stream/intents
WebSocket endpoint. After upgrade, the server streams `IntentEvent` objects as JSON strings.
```
← {"type": "connected", "sessionId": "...", "deviceId": "..."}
← {"type": "intent", "data": IntentEvent}
← {"type": "intent", "data": IntentEvent}
...
→ {"type": "feedback", "intentId": "...", "trueLabel": "motor_imagery_left"}
← {"type": "feedback_ack", "intentId": "..."}
```

### GET /operator/diagnostics
Returns current device diagnostics, pipeline latency stats, session state.

### GET /operator/signal
Returns last 5 seconds of raw signal frames (for operator display).

---

## neuroos.config.yaml Schema

```yaml
# neuroos.config.yaml
version: "1.0"

device:
  adapter: "neuroos-simulator"      # or "openbci-cyton", "brainproducts", etc.
  numChannels: 16
  sampleRateHz: 256
  samplesPerFrame: 16

dsp:
  spatialFilterType: "car"          # "car" | "laplacian" | "csp" | "none"
  temporalFilterType: "autoregressive"  # "bandpass_fir" | "autoregressive" | "p300_average" | "slow_wave"
  bandpassHz: [1, 40]
  windowLengthSec: 1.0
  windowStepSec: 0.0625             # 16 Hz update rate

intent:
  classifierType: "lda"             # "lda" | "csp_lda" | "p300_template" | "cnn" | "ensemble"
  modelPath: null                   # null = use pretrained default
  inferenceRateHz: 16
  confidenceThreshold: 0.6

paradigm:
  type: "motor_imagery"             # "motor_imagery" | "p300_speller" | "scp_control" | "free"
  trialLengthSec: 4.0
  itiSec: 2.0

api:
  port: 3000
  host: "127.0.0.1"
  corsOrigins: ["http://localhost:3000", "http://localhost:5173"]

storage:
  sessionsDir: "~/.neuroos/sessions"
  maxSessionAgeDays: 30
```

---

## Plugin System

Enables third-party device drivers without forking the core:

```typescript
// Third-party driver package: neuroos-plugin-unicorn
export default class UnicornAdapter implements DeviceAdapter {
  // implements full DeviceAdapter interface from 00_shared_contracts
}

// Registration in neuroos.config.yaml:
// device:
//   adapter: "neuroos-plugin-unicorn"
//   pluginPath: "./node_modules/neuroos-plugin-unicorn"
```

Plugin loading:
```typescript
const PluginAdapterClass = await import(config.device.pluginPath);
const adapter = new PluginAdapterClass.default(config.device);
registry.register(adapter);
```

---

## Dependencies

```json
{
  "dependencies": {
    "fastify": "^4.26",
    "@fastify/websocket": "^8.3",
    "@fastify/cors": "^9.0",
    "ajv": "^8.12",
    "js-yaml": "^4.1",
    "uuid": "^9.0",
    "winston": "^3.11"
  },
  "devDependencies": {
    "typescript": "^5.4",
    "@types/node": "^20",
    "vitest": "^1.4",
    "supertest": "^6.3",
    "ws": "^8.16"
  }
}
```

---

## Acceptance Criteria

- [ ] `tsc --noEmit` passes with zero errors
- [ ] `vitest run` passes with zero failures
- [ ] `latency.test.ts`: end-to-end latency <15 ms (measured with simulator + passthrough DSP stub)
- [ ] `DeviceRegistry` correctly validates that registered objects implement the `DeviceAdapter` interface at runtime
- [ ] `WS /stream/intents` endpoint streams IntentEvents to a connected WebSocket client with <500 ms first-event latency after session start
- [ ] `neuroos.config.yaml` with invalid fields is rejected with a descriptive error at startup
- [ ] `POST /sessions/start` returns 409 if a session is already active
- [ ] `PluginSystem` loads a minimal stub adapter from a local path

---

## Must NOT Do

- Implement DSP signal operators (Job 02)
- Train or run ML models (Job 03)
- Write SDK client code, React hooks, or CLI tools (Job 05)
- Write Dockerfiles or GitHub Actions workflows (Job 06)
- Import from any job folder except `00_shared_contracts`
