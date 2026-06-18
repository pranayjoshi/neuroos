/** @vitest-environment jsdom */

import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { NeuroOSProvider } from "../src/context.js";
import { useIntent } from "../src/hooks/useIntent.js";
import type { IntentStream } from "../src/stream.js";
import type { IntentEvent } from "../src/types.js";

function makeIntent(label: IntentEvent["label"]): IntentEvent {
  return {
    intentId: `intent-${label}`,
    label,
    confidence: 0.9,
    posteriors: { [label]: 0.9 },
    classifierType: "lda",
    sourceVectorId: "vec-1",
    timestampNs: 1700000000000000000n,
    endToEndLatencyMs: 10,
    featureImportance: {},
    artifactFlag: false,
    feedbackLabel: null,
  };
}

function TestComponent() {
  const { intent, isConnected } = useIntent();
  return (
    <div>
      <span data-testid="connected">{isConnected ? "yes" : "no"}</span>
      <span data-testid="label">{intent?.label ?? "none"}</span>
    </div>
  );
}

describe("useIntent", () => {
  it("re-renders when a new intent arrives", async () => {
    const listeners = new Map<string, Set<(payload?: unknown) => void>>();
    const mockStream = {
      on(event: string, listener: (payload?: unknown) => void) {
        const set = listeners.get(event) ?? new Set();
        set.add(listener);
        listeners.set(event, set);
        return mockStream;
      },
      off() {
        return mockStream;
      },
      close: vi.fn(async () => undefined),
      sendFeedback: vi.fn(),
      feedback: vi.fn(),
      [Symbol.asyncIterator]() {
        return {
          next: async () => ({ done: true, value: undefined }),
        };
      },
    } as unknown as IntentStream;

    const client = {
      intents: {
        stream: () => mockStream,
      },
    };

    render(
      <NeuroOSProvider client={client as never}>
        <TestComponent />
      </NeuroOSProvider>,
    );

    expect(screen.getByTestId("label").textContent).toBe("none");

    listeners.get("connected")?.forEach((fn) => fn());
    await waitFor(() => {
      expect(screen.getByTestId("connected").textContent).toBe("yes");
    });

    listeners.get("intent")?.forEach((fn) => fn(makeIntent("motor_imagery_left")));
    await waitFor(() => {
      expect(screen.getByTestId("label").textContent).toBe("motor_imagery_left");
    });

    listeners.get("intent")?.forEach((fn) => fn(makeIntent("motor_imagery_right")));
    await waitFor(() => {
      expect(screen.getByTestId("label").textContent).toBe("motor_imagery_right");
    });
  });
});
