# API Design Reference — Platform Core Context

Design principles, patterns, and worked examples for NeuroOS Platform Core.

---

## Design Philosophy

NeuroOS Platform Core = iOS for BCIs.

| iOS | NeuroOS |
|---|---|
| ExternalAccessory framework | DeviceRegistry |
| Core Motion (CMMotionManager) | PipelineOrchestrator |
| UIEvent stream | IntentEvent stream |
| Info.plist configuration | neuroos.config.yaml |
| NSNotificationCenter | EventBus |
| App lifecycle (foreground/background) | SessionManager |
| TestFlight | Playground CLI (Job 05) |

### Key Principle: Hardware Agnosticism

A developer writing `neuroos.on('intent', handler)` should never need to know:
- Whether the device is EEG or ECoG
- Whether the classifier is LDA or neural
- What sample rate or channel count the hardware uses

The platform is the abstraction boundary. This is exactly the BCI2000 model:
*"Components are interchangeable if different implementations of each can be used
without changes elsewhere in the system."*

---

## Inter-Process Communication Design

### Why JSONL over stdin/stdout?

The DSP pipeline and Intent Engine are Python processes. Platform Core is TypeScript.
Options:
1. **gRPC** — type-safe, fast, but complex to set up
2. **REST/HTTP** — adds network overhead, harder to backpressure
3. **JSONL pipes** — zero dependencies, simple, fast enough for 16 Hz data

At 16 Hz with a 16-channel FeatureVector (~400 bytes JSON), pipe throughput is ~6 KB/s.
Well within OS pipe buffer limits (typically 64 KB).

### JSONL Protocol

Each line is a complete JSON object terminated by `\n`. No framing needed.

```
stdin of dsp_pipeline process:
{"deviceId":"sim:cyton:SIM-1","frameIndex":0,"timestampNs":"1750000000000000000",...}\n
{"deviceId":"sim:cyton:SIM-1","frameIndex":1,...}\n

stdout of dsp_pipeline process:
{"vectorId":"uuid-1","sourceFrameIndices":[0],"timestampNs":"...","bandPowers":{...},...}\n

stdin of intent_engine process (piped from dsp stdout):
{"vectorId":"uuid-1",...}\n

stdout of intent_engine process:
{"intentId":"uuid-2","label":"motor_imagery_left","confidence":0.82,...}\n
```

### Backpressure Handling

If the intent engine can't keep up with the DSP output rate, the pipe will block.
The PipelineOrchestrator must use non-blocking writes and an async queue:

```typescript
import { Writable } from 'stream';

class JSONLWriter {
  private queue: string[] = [];
  private writing = false;

  write(obj: object): void {
    this.queue.push(JSON.stringify(obj) + '\n');
    if (!this.writing) this.flush();
  }

  private async flush(): Promise<void> {
    this.writing = true;
    while (this.queue.length > 0) {
      const line = this.queue.shift()!;
      const ok = this.process.stdin!.write(line);
      if (!ok) await new Promise(r => this.process.stdin!.once('drain', r));
    }
    this.writing = false;
  }
}
```

---

## WebSocket Streaming Protocol

### Connection Lifecycle

```
Client                              Server
  |                                   |
  |--- WS Upgrade /stream/intents --->|
  |<-- 101 Switching Protocols -------|
  |                                   |
  |<-- {"type":"connected",...} ------|  (sent immediately on connect)
  |                                   |
  |--- POST /sessions/start (REST) -->|  (client starts session via REST)
  |                                   |
  |<-- {"type":"intent","data":{...}} |  (streaming at ~16 Hz)
  |<-- {"type":"intent","data":{...}} |
  |<-- {"type":"intent","data":{...}} |
  |                                   |
  |--> {"type":"feedback",...} ------>|  (optional: user confirms intent)
  |<-- {"type":"feedback_ack",...} ---|
  |                                   |
  |--- POST /sessions/stop (REST) --->|
  |<-- {"type":"session_stopped"} ----|
  |                                   |
  |--- WS Close ----------------------|
```

### Message Types

```typescript
// Server → Client
type ServerMessage =
  | { type: 'connected'; sessionId: string | null; deviceId: string | null; version: string }
  | { type: 'intent'; data: IntentEvent }
  | { type: 'session_started'; session: SessionMetadata }
  | { type: 'session_stopped'; sessionId: string; totalFrames: number }
  | { type: 'feedback_ack'; intentId: string }
  | { type: 'error'; code: string; message: string };

// Client → Server
type ClientMessage =
  | { type: 'feedback'; intentId: string; trueLabel: IntentLabel }
  | { type: 'ping' };
```

---

## Operator Dashboard

The operator module from BCI2000 provides real-time visibility for investigators.
In NeuroOS, this maps to the `GET /operator/` routes and a web UI served at `/operator`.

```
GET /operator/diagnostics → {
  device: DeviceDiagnostics,
  pipeline: {
    meanLatencyMs: number,
    p95LatencyMs: number,
    droppedFrames: number,
    currentScenario: string | null
  },
  session: SessionMetadata | null
}

GET /operator/signal?channels=C3,C4&seconds=5 → {
  frames: RawSignalFrame[]  // last N seconds of raw data
}

GET /operator/features?seconds=5 → {
  vectors: FeatureVector[]  // last N seconds of DSP output
}
```

From BCI2000: *"The operator module provides the investigator with a graphical interface
that displays current system parameters and real-time analysis results (e.g., frequency
spectra) communicated by other modules."*

---

## Error Handling Strategy

### HTTP Errors

```typescript
// Use Fastify's built-in error handling
reply.code(409).send({ error: 'SESSION_ALREADY_ACTIVE', message: 'A session is already running. Stop it first.' });
reply.code(404).send({ error: 'DEVICE_NOT_FOUND', message: `No device registered with id: ${deviceId}` });
reply.code(422).send({ error: 'VALIDATION_ERROR', details: ajvErrors });
```

### Pipeline Errors

When DSP or Intent engine subprocess crashes:
1. Emit `'pipeline.error'` on EventBus
2. Set session state to `'error'`
3. Send `{ type: 'error', ... }` to all connected WebSocket clients
4. Attempt restart if `config.pipeline.autoRestart = true` (default: true, max 3 retries)

---

## Latency Measurement

End-to-end latency = time from first sample acquisition to IntentEvent arrival at API layer.

```typescript
function measureLatency(frame: RawSignalFrame, intent: IntentEvent): number {
  const frameTs = BigInt(frame.timestampNs);
  const intentTs = BigInt(intent.timestampNs);
  return Number(intentTs - frameTs) / 1_000_000;  // ns → ms
}
```

The BCI2000 paper reports 15.11 ms mean latency with 0.75 ms jitter (Table I).
NeuroOS target: <15 ms mean, <2 ms jitter (P99).

Instrumented via `getLatencyStats()` on PipelineOrchestrator:
```typescript
interface LatencyStats {
  mean: number;   // arithmetic mean over last 100 events
  p50: number;    // median
  p95: number;    // 95th percentile
  p99: number;    // 99th percentile
  max: number;    // worst case since session start
  jitter: number; // std deviation = system clock jitter
}
```

---

## Session Persistence

Sessions are stored at `~/.neuroos/sessions/<sessionId>/`:
```
~/.neuroos/sessions/
└── session-uuid-123/
    ├── metadata.json          ← SessionMetadata
    ├── recording.ndf          ← raw signal data (from DataRecorder)
    ├── recording.ndf.events   ← event markers sidecar
    ├── features.jsonl         ← FeatureVector stream (optional, large)
    └── intents.jsonl          ← IntentEvent stream
```

This enables full offline reconstruction and analysis, matching BCI2000's data format principle.

---

## Security Considerations

- Bind to `127.0.0.1` by default — not exposed to network
- CORS restricted to localhost origins
- WebSocket connections require an active session (reject if no session started)
- Plugin adapters are loaded via explicit `pluginPath` — no auto-discovery of arbitrary code
- Config file is validated against JSON Schema before any modules are started
