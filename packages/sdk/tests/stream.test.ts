import { describe, expect, it, vi } from "vitest";
import { IntentStream } from "../src/stream.js";
import type { NeuroOSWebSocket } from "../src/ws.js";

class MockWebSocket implements NeuroOSWebSocket {
  readonly OPEN = 1;
  readyState = 0;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
    this.emit("close");
  });

  private listeners = {
    open: new Set<() => void>(),
    message: new Set<(event: { data: unknown }) => void>(),
    close: new Set<() => void>(),
    error: new Set<() => void>(),
  };

  constructor(private readonly autoOpen = true) {}

  addEventListener(type: "open", listener: () => void): void;
  addEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  addEventListener(type: "close", listener: () => void): void;
  addEventListener(type: "error", listener: () => void): void;
  addEventListener(type: "open" | "message" | "close" | "error", listener: (...args: never[]) => void): void {
    this.listeners[type].add(listener as never);

    if (type === "open" && this.autoOpen && this.readyState !== this.OPEN) {
      this.readyState = this.OPEN;
      (listener as () => void)();
      this.emit("message", {
        data: JSON.stringify({
          type: "connected",
          sessionId: "sess-1",
          deviceId: "dev-1",
          version: "0.1.0",
        }),
      });
    }
  }

  removeEventListener(type: "open", listener: () => void): void;
  removeEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  removeEventListener(type: "close", listener: () => void): void;
  removeEventListener(type: "error", listener: () => void): void;
  removeEventListener(type: "open" | "message" | "close" | "error", listener: (...args: never[]) => void): void {
    this.listeners[type].delete(listener as never);
  }

  emit(type: "open"): void;
  emit(type: "message", payload: { data: unknown }): void;
  emit(type: "close" | "error"): void;
  emit(type: "open" | "message" | "close" | "error", payload?: { data: unknown }): void {
    if (type === "message") {
      for (const listener of this.listeners.message) listener(payload as { data: unknown });
      return;
    }
    for (const listener of this.listeners[type]) (listener as () => void)();
  }

  pushIntent(label: string, confidence = 0.9): void {
    this.emit("message", {
      data: JSON.stringify({
        type: "intent",
        data: {
          intentId: `intent-${label}`,
          label,
          confidence,
          posteriors: { [label]: confidence },
          classifierType: "lda",
          sourceVectorId: "vec-1",
          timestampNs: "1700000000000000000",
          endToEndLatencyMs: 10,
          featureImportance: {},
          artifactFlag: false,
          feedbackLabel: null,
        },
      }),
    });
  }
}

describe("IntentStream", () => {
  it("supports async iteration", async () => {
    let socket!: MockWebSocket;
    const stream = new IntentStream({
      baseUrl: "http://localhost:3000",
      reconnect: false,
      wsFactory: () => {
        socket = new MockWebSocket();
        return socket;
      },
    });

    await new Promise((resolve) => stream.on("connected", resolve));

    socket.pushIntent("motor_imagery_left");
    socket.pushIntent("motor_imagery_right");

    const labels: string[] = [];
    for await (const intent of stream) {
      labels.push(intent.label);
      if (labels.length >= 2) break;
    }

    expect(labels).toEqual(["motor_imagery_left", "motor_imagery_right"]);
    await stream.close();
  });

  it("emits intent events and sendFeedback", async () => {
    let socket!: MockWebSocket;
    const stream = new IntentStream({
      baseUrl: "http://localhost:3000",
      reconnect: false,
      wsFactory: () => {
        socket = new MockWebSocket();
        return socket;
      },
    });

    await new Promise((resolve) => stream.on("connected", resolve));

    const received: string[] = [];
    stream.on("intent", (event) => received.push(event.label));
    socket.pushIntent("motor_imagery_rest");

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(received).toEqual(["motor_imagery_rest"]);

    stream.feedback("intent-1", "motor_imagery_rest");
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: "feedback",
        intentId: "intent-1",
        trueLabel: "motor_imagery_rest",
      }),
    );

    await stream.close();
  });
});
