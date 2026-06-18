# Job 05 — Developer SDK

**Agent Role:** SDK / DX Engineer  
**Language:** TypeScript (npm package), Python (PyPI package)  
**Depends on:** Job 04 (Platform Core REST/WebSocket API is the integration point)  
**Consumed by:** App developers, Job 06 (CI/CD runs example apps as smoke tests)

---

## Purpose

Make NeuroOS developer-friendly. "No PhD required."

The SDK is the public face of NeuroOS. A developer should be able to go from `npm install @neuroos/sdk` to receiving brain-computer interface events in their app in under 5 minutes. The Platform Core handles all complexity; the SDK exposes only what developers need.

---

## Deliverables

### TypeScript SDK: `packages/sdk-ts/`

| File | Export | Responsibility |
|---|---|---|
| `src/client.ts` | `NeuroOS` | Main client class |
| `src/hooks/useIntent.ts` | `useIntent()` | React hook for intent events |
| `src/hooks/useSession.ts` | `useSession()` | React hook for session management |
| `src/hooks/useDevice.ts` | `useDevice()` | React hook for device state |
| `src/stream.ts` | `IntentStream` | Low-level WebSocket stream wrapper |
| `src/types.ts` | — | Re-exports types from 00_shared_contracts |
| `src/errors.ts` | `NeuroOSError` | Typed error class hierarchy |
| `src/index.ts` | — | Public API barrel export |

### Python SDK: `packages/sdk-py/`

| File | Export | Responsibility |
|---|---|---|
| `neuroos/client.py` | `NeuroOS` | Main client class |
| `neuroos/stream.py` | `IntentStream` | Async WebSocket stream |
| `neuroos/types.py` | — | TypedDicts matching shared contracts |
| `neuroos/errors.py` | `NeuroOSError` | Typed exceptions |
| `neuroos/__init__.py` | — | Public API exports |

### Playground CLI: `packages/playground/`

- `bin/neuroos.ts` — `npx neuroos` entry point
- `src/commands/playground.ts` — live intent stream to terminal
- `src/commands/simulate.ts` — start simulator + full stack in one command
- `src/commands/devices.ts` — list registered devices
- `src/commands/sessions.ts` — list/inspect sessions

### Example Apps: `examples/`

| Directory | Description |
|---|---|
| `examples/cursor-control/` | Move a dot with motor imagery (React) |
| `examples/p300-speller/` | 6×6 character speller (React) |
| `examples/motor-imagery-game/` | Simple game controlled by left/right imagery (React) |
| `examples/python-quickstart/` | 20-line Python script printing intents |

### Docs Scaffold: `docs/`

- `openapi.yaml` — auto-generated from Platform Core routes
- `docusaurus.config.js` — Docusaurus v3 setup
- `docs/getting-started.md` — 5-minute quickstart
- `docs/api-reference.md` — generated from OpenAPI

---

## TypeScript SDK — Public API

### `NeuroOS` Client Class

```typescript
import { NeuroOS } from '@neuroos/sdk';

// Connect to Platform Core (default: http://localhost:3000)
const neuroos = new NeuroOS({ baseUrl: 'http://localhost:3000' });

// Register and connect the simulator device
const device = await neuroos.devices.register('neuroos-simulator', {
  numChannels: 16,
  sampleRateHz: 256,
});

// Start a session
const session = await neuroos.sessions.start({
  deviceId: device.deviceId,
  subjectId: 'sub-001',
  sessionName: 'my-first-session',
  paradigm: 'motor_imagery',
});

// Subscribe to intent events
const stream = neuroos.intents.stream();
stream.on('intent', (event) => {
  console.log(event.label, event.confidence);
  // "motor_imagery_left", 0.83
});

// Send feedback (optional: for online adaptation)
stream.sendFeedback(event.intentId, 'motor_imagery_left');

// Stop
await neuroos.sessions.stop(session.sessionId);
await stream.close();
```

### TypeScript Interface — Full `NeuroOS` Class

```typescript
interface NeuroOSClientConfig {
  baseUrl?: string;          // default: 'http://localhost:3000'
  timeout?: number;          // default: 5000 ms
  reconnect?: boolean;       // default: true
  reconnectDelayMs?: number; // default: 1000
}

class NeuroOS {
  constructor(config?: NeuroOSClientConfig);

  readonly devices: DevicesAPI;
  readonly sessions: SessionsAPI;
  readonly intents: IntentsAPI;
  readonly operator: OperatorAPI;
}

interface DevicesAPI {
  register(adapterName: string, config?: Partial<DeviceAdapterConfig>): Promise<DeviceInfo>;
  unregister(deviceId: string): Promise<void>;
  list(): Promise<DeviceInfo[]>;
  getDiagnostics(deviceId: string): Promise<DeviceDiagnostics>;
}

interface SessionsAPI {
  start(params: SessionStartParams): Promise<SessionMetadata>;
  stop(sessionId: string): Promise<SessionMetadata>;
  pause(sessionId: string): Promise<void>;
  resume(sessionId: string): Promise<void>;
  list(): Promise<SessionMetadata[]>;
  get(sessionId: string): Promise<SessionMetadata>;
}

interface IntentsAPI {
  stream(): IntentStream;
}

class IntentStream extends EventEmitter {
  on(event: 'intent', listener: (intent: IntentEvent) => void): this;
  on(event: 'connected', listener: () => void): this;
  on(event: 'disconnected', listener: () => void): this;
  on(event: 'error', listener: (err: NeuroOSError) => void): this;

  sendFeedback(intentId: string, trueLabel: IntentLabel): void;
  close(): Promise<void>;

  /** Async iteration support */
  [Symbol.asyncIterator](): AsyncIterator<IntentEvent>;
}
```

---

## React Hooks

```typescript
// useIntent — subscribe to intent events in React components
function useIntent(options?: {
  filter?: IntentLabel[];        // only receive these labels
  minConfidence?: number;        // default: 0.6
}): {
  intent: IntentEvent | null;    // latest intent event
  history: IntentEvent[];        // last 10 events
  isConnected: boolean;
  error: NeuroOSError | null;
};

// Example usage:
function MyBCIApp() {
  const { intent, isConnected } = useIntent({ filter: ['motor_imagery_left', 'motor_imagery_right'] });

  useEffect(() => {
    if (!intent) return;
    if (intent.label === 'motor_imagery_left') moveCursorLeft();
    if (intent.label === 'motor_imagery_right') moveCursorRight();
  }, [intent]);

  return <div>{isConnected ? `Last intent: ${intent?.label}` : 'Connecting...'}</div>;
}

// useSession — manage session lifecycle
function useSession(): {
  session: SessionMetadata | null;
  isActive: boolean;
  startSession(params: SessionStartParams): Promise<void>;
  stopSession(): Promise<void>;
  error: NeuroOSError | null;
};

// useDevice — device state
function useDevice(deviceId?: string): {
  device: DeviceInfo | null;
  state: DeviceState;
  diagnostics: DeviceDiagnostics | null;
};
```

---

## Python SDK

### Basic API

```python
import asyncio
from neuroos import NeuroOS

async def main():
    neuroos = NeuroOS(base_url="http://localhost:3000")

    # Register simulator device
    device = await neuroos.devices.register("neuroos-simulator", num_channels=16)

    # Start session
    session = await neuroos.sessions.start(
        device_id=device["deviceId"],
        subject_id="sub-001",
        session_name="python-test",
        paradigm="motor_imagery",
    )

    # Stream intents
    async for intent in neuroos.intents.stream():
        print(f"{intent['label']}: {intent['confidence']:.2f}")
        if intent['label'] == 'motor_imagery_left':
            print("Left!")

asyncio.run(main())
```

### Synchronous API (convenience wrapper)

```python
from neuroos import NeuroOS

with NeuroOS() as client:
    device = client.devices.register_sync("neuroos-simulator")
    session = client.sessions.start_sync(device_id=device["deviceId"], ...)
    for intent in client.intents.stream_sync(max_events=100):
        print(intent['label'])
```

---

## Playground CLI

### Commands

```bash
# Start the full stack (simulator + platform core) and display live intents
npx neuroos playground --scenario motor_imagery_left --channels 16

# Start platform core (requires separately running Python services)
npx neuroos start

# List registered devices
npx neuroos devices list

# List sessions
npx neuroos sessions list

# Replay a recorded session
npx neuroos replay ~/.neuroos/sessions/session-uuid/recording.ndf
```

### `npx neuroos playground` Output

```
NeuroOS Playground v0.1.0
─────────────────────────────────────────────────────
Device:   simulator:default:SIM-001 (16ch, 256 Hz, EEG)
Session:  motor-imagery-demo (sub-demo)
Pipeline: DSP=autoregressive → Intent=lda @ 16 Hz

Streaming intents... (Ctrl+C to stop)

[00:01.062] motor_imagery_rest     │████████████████▌   │ 0.83
[00:01.125] motor_imagery_left     │██████████████████▊ │ 0.94 ◀ HIGH
[00:01.188] motor_imagery_left     │█████████████████▌  │ 0.87
[00:01.250] motor_imagery_rest     │████████████         │ 0.60
...
```

---

## Example App: Cursor Control

```typescript
// examples/cursor-control/src/App.tsx
import { useIntent, useSession, NeuroOSProvider } from '@neuroos/sdk/react';

function CursorApp() {
  const { session, startSession } = useSession();
  const { intent } = useIntent({ filter: ['motor_imagery_left', 'motor_imagery_right', 'motor_imagery_rest'] });
  const [x, setX] = useState(50); // percent

  useEffect(() => {
    if (intent?.label === 'motor_imagery_left') setX(x => Math.max(0, x - 5));
    if (intent?.label === 'motor_imagery_right') setX(x => Math.min(100, x + 5));
  }, [intent]);

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      {!session && <button onClick={() => startSession({ paradigm: 'motor_imagery' })}>Start BCI</button>}
      <div style={{ position: 'absolute', left: `${x}%`, top: '50%', width: 32, height: 32, borderRadius: '50%', background: '#0066ff' }} />
    </div>
  );
}
```

---

## Dependencies

### TypeScript SDK
```json
{
  "peerDependencies": { "react": ">=18" },
  "dependencies": { "ws": "^8.16" },
  "devDependencies": { "typescript": "^5.4", "vitest": "^1.4" }
}
```

Zero production dependencies except `ws` for WebSocket.

### Python SDK
```
httpx>=0.27        # async HTTP client
websockets>=12.0   # async WebSocket
```

### Playground CLI
```json
{
  "dependencies": {
    "commander": "^12.0",
    "chalk": "^5.3",
    "ora": "^8.0"
  }
}
```

---

## Acceptance Criteria

- [ ] `tsc --noEmit` passes on TypeScript SDK with zero errors
- [ ] `vitest run` passes with zero failures
- [ ] `useIntent()` hook re-renders React component on each new IntentEvent (tested with React Testing Library)
- [ ] `IntentStream[Symbol.asyncIterator]` works: `for await (const intent of stream) { ... }`
- [ ] Python SDK: `async for intent in neuroos.intents.stream(): ...` iterates successfully for 10 events against a running Platform Core
- [ ] `npx neuroos playground --help` prints usage without error
- [ ] `examples/cursor-control/` starts with `npm run dev` without error (vite dev server)
- [ ] `examples/python-quickstart/main.py` runs to completion against simulator
- [ ] SDK bundle size (TypeScript): <20 KB gzipped

---

## Must NOT Do

- Implement any signal processing, filtering, or classification (Jobs 02, 03)
- Start or manage Python subprocesses (Job 04)
- Write Dockerfiles or GitHub Actions (Job 06)
- Modify Platform Core routes or business logic
- Import from any job folder except `00_shared_contracts` (for type reference only)
