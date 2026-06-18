# SDK Examples Reference — Developer SDK Context

Worked code examples, design patterns, and DX guidelines for the NeuroOS SDK.

---

## Design Principles

### 1. Progressive Disclosure

Simplest use case = fewest lines possible. Advanced features are opt-in.

```python
# Minimal: 4 lines
from neuroos import NeuroOS
client = NeuroOS()
async for intent in client.intents.stream():
    print(intent['label'])
```

```typescript
// Minimal React component: useIntent hook
const { intent } = useIntent();
return <p>{intent?.label ?? 'Waiting...'}</p>;
```

### 2. Zero BCI Knowledge Required

The SDK vocabulary is everyday words: `intent`, `label`, `confidence`, `session`.
No `filterBank`, `classificationMatrix`, `spatialPattern` in the public API.

### 3. Fail Loudly and Helpfully

```typescript
// Bad error: "WebSocket error: ECONNREFUSED"
// Good error:
throw new NeuroOSError(
  'CONNECTION_FAILED',
  'Could not connect to NeuroOS Platform Core at http://localhost:3000. ' +
  'Make sure the platform is running: npx neuroos start'
);
```

### 4. Type Safety First

All SDK types derive from `00_shared_contracts/schema/`. The SDK re-exports them.
TypeScript users get full IntelliSense on `IntentEvent` fields.

---

## TypeScript — Complete Example: P300 Speller

```typescript
import { NeuroOS, type IntentEvent } from '@neuroos/sdk';

const neuroos = new NeuroOS();

// 6x6 character matrix
const MATRIX = [
  ['A','B','C','D','E','F'],
  ['G','H','I','J','K','L'],
  ['M','N','O','P','Q','R'],
  ['S','T','U','V','W','X'],
  ['Y','Z','1','2','3','4'],
  ['5','6','7','8','9','_'],
];

class P300Speller {
  private rowScores = new Array(6).fill(0);
  private colScores = new Array(6).fill(0);
  private flashCount = { row: new Array(6).fill(0), col: new Array(6).fill(0) };

  constructor(private stream: ReturnType<NeuroOS['intents']['stream']>) {}

  async spell(): Promise<string> {
    for await (const intent of this.stream) {
      if (intent.label === 'p300_target') {
        // In a real speller, the intent would carry which row/col flashed.
        // Here we use a simplified scoring approach.
        this.updateScores(intent);
      }

      if (this.readyToDecide()) {
        return this.decide();
      }
    }
    throw new Error('Stream ended before character was decoded');
  }

  private updateScores(intent: IntentEvent): void {
    // Implementation detail: the stimulus_onset event marker carries row/col info
    const rowIdx = intent.posteriors['p300_target'] ?? 0;
    // ... scoring logic
  }

  private readyToDecide(): boolean {
    return this.flashCount.row.every(n => n >= 15); // 15 averages per row/col
  }

  private decide(): string {
    const row = this.rowScores.indexOf(Math.max(...this.rowScores));
    const col = this.colScores.indexOf(Math.max(...this.colScores));
    return MATRIX[row][col];
  }
}

async function main() {
  const device = await neuroos.devices.register('neuroos-simulator');
  const session = await neuroos.sessions.start({
    deviceId: device.deviceId,
    subjectId: 'demo',
    sessionName: 'p300-speller-demo',
    paradigm: 'p300_speller',
  });

  const stream = neuroos.intents.stream();
  const speller = new P300Speller(stream);

  console.log('Focus on the letter you want to type...');
  const char = await speller.spell();
  console.log(`Decoded: ${char}`);

  await neuroos.sessions.stop(session.sessionId);
}
```

---

## React — Complete Example: Motor Imagery Game

```tsx
// examples/motor-imagery-game/src/Game.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { useIntent, useSession, useDevice } from '@neuroos/sdk/react';

type Direction = 'left' | 'right' | 'none';

const INTENT_TO_DIRECTION: Record<string, Direction> = {
  motor_imagery_left: 'left',
  motor_imagery_right: 'right',
  motor_imagery_rest: 'none',
};

export function Game() {
  const { session, isActive, startSession, stopSession } = useSession();
  const { device, state: deviceState } = useDevice();
  const { intent, isConnected } = useIntent({
    filter: ['motor_imagery_left', 'motor_imagery_right', 'motor_imagery_rest'],
    minConfidence: 0.65,
  });

  const [playerX, setPlayerX] = useState(50); // percent
  const [score, setScore] = useState(0);
  const [targets, setTargets] = useState([{ x: 20 }, { x: 80 }]);

  useEffect(() => {
    if (!intent) return;
    const dir = INTENT_TO_DIRECTION[intent.label];
    if (dir === 'left')  setPlayerX(x => Math.max(5, x - 3));
    if (dir === 'right') setPlayerX(x => Math.min(95, x + 3));
  }, [intent]);

  // Check collision with targets
  useEffect(() => {
    setTargets(prev => prev.filter(t => {
      if (Math.abs(t.x - playerX) < 5) {
        setScore(s => s + 1);
        return false; // remove hit target
      }
      return true;
    }));
  }, [playerX]);

  return (
    <div className="game-container">
      <header>
        <span>Score: {score}</span>
        <span>Device: {deviceState}</span>
        <span>Intent: {intent?.label ?? '—'} ({((intent?.confidence ?? 0) * 100).toFixed(0)}%)</span>
      </header>

      {!isActive ? (
        <button onClick={() => startSession({ paradigm: 'motor_imagery' })}>
          Start BCI Session
        </button>
      ) : (
        <div className="arena" style={{ position: 'relative', height: 400 }}>
          {/* Player */}
          <div className="player" style={{ left: `${playerX}%`, bottom: 20 }} />
          {/* Targets */}
          {targets.map((t, i) => (
            <div key={i} className="target" style={{ left: `${t.x}%`, bottom: 80 }} />
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## Python — Async Generator Pattern

```python
# examples/python-quickstart/main.py
"""
NeuroOS Python Quickstart
Prints intent events from a simulated BCI device.
"""
import asyncio
from neuroos import NeuroOS

async def main():
    async with NeuroOS() as client:
        # Register the built-in simulator
        device = await client.devices.register("neuroos-simulator", num_channels=16)
        print(f"Connected: {device['deviceId']}")

        # Start a session
        session = await client.sessions.start(
            device_id=device["deviceId"],
            subject_id="demo",
            session_name="quickstart",
            paradigm="motor_imagery",
        )
        print(f"Session: {session['sessionId']}")

        # Stream and print 50 intent events
        count = 0
        async for intent in client.intents.stream():
            label = intent["label"]
            conf  = intent["confidence"]
            latency = intent["endToEndLatencyMs"]
            print(f"[{count:03d}] {label:<25} conf={conf:.2f}  latency={latency:.1f}ms")
            count += 1
            if count >= 50:
                break

        await client.sessions.stop(session["sessionId"])
        print("Done.")

asyncio.run(main())
```

---

## Error Classes

```typescript
// src/errors.ts

export class NeuroOSError extends Error {
  constructor(
    public readonly code: NeuroOSErrorCode,
    message: string,
    public readonly cause?: unknown
  ) {
    super(message);
    this.name = 'NeuroOSError';
  }
}

export type NeuroOSErrorCode =
  | 'CONNECTION_FAILED'        // Platform Core not reachable
  | 'SESSION_ALREADY_ACTIVE'   // tried to start when one is running
  | 'NO_ACTIVE_SESSION'        // tried to stream without a session
  | 'DEVICE_NOT_FOUND'         // deviceId not registered
  | 'STREAM_CLOSED'            // WebSocket closed unexpectedly
  | 'VALIDATION_ERROR'         // API returned 422
  | 'TIMEOUT'                  // request exceeded timeout
  | 'UNKNOWN';

// Typed subclasses for catching specific errors:
export class ConnectionError extends NeuroOSError {
  constructor(baseUrl: string, cause?: unknown) {
    super(
      'CONNECTION_FAILED',
      `Could not connect to NeuroOS at ${baseUrl}. Is the platform running? (npx neuroos start)`,
      cause
    );
  }
}
```

---

## React Hook Implementation Sketch

```typescript
// src/hooks/useIntent.ts
import { useEffect, useState, useRef, useContext } from 'react';
import type { IntentEvent, IntentLabel } from '../types';
import { NeuroOSContext } from '../context';

export function useIntent(options?: {
  filter?: IntentLabel[];
  minConfidence?: number;
}): { intent: IntentEvent | null; history: IntentEvent[]; isConnected: boolean; error: Error | null } {
  const client = useContext(NeuroOSContext);
  const [intent, setIntent] = useState<IntentEvent | null>(null);
  const [history, setHistory] = useState<IntentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const streamRef = useRef<ReturnType<typeof client.intents.stream> | null>(null);

  useEffect(() => {
    const stream = client.intents.stream();
    streamRef.current = stream;

    stream.on('connected', () => setIsConnected(true));
    stream.on('disconnected', () => setIsConnected(false));
    stream.on('error', (err) => setError(err));
    stream.on('intent', (event) => {
      // Apply filter
      if (options?.filter && !options.filter.includes(event.label)) return;
      if (options?.minConfidence && event.confidence < options.minConfidence) return;
      setIntent(event);
      setHistory(prev => [event, ...prev].slice(0, 10));
    });

    return () => { stream.close(); };
  }, []); // note: client is stable (created once in NeuroOSProvider)

  return { intent, history, isConnected, error };
}
```

---

## Bundle Size Guidelines

The TypeScript SDK must stay lean. Keep bundle <20 KB gzipped:

- No heavy dependencies (no lodash, no moment, no large utilities)
- Use native `WebSocket` in browser (no ws package at runtime in browser builds)
- Tree-shakeable exports (named exports only, no default class instance)
- React hooks are in a separate `@neuroos/sdk/react` entry point (so non-React users don't pay the cost)

ESM + CJS dual output:
```json
{
  "exports": {
    ".": { "import": "./dist/index.mjs", "require": "./dist/index.cjs" },
    "./react": { "import": "./dist/react.mjs", "require": "./dist/react.cjs" }
  }
}
```
