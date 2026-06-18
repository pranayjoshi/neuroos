import { describe, it, expect, vi } from "vitest";
import { EventBus } from "../src/bus/event_bus.js";
import type { RawSignalFrame } from "@neuroos/shared-contracts/schema";

function makeFrame(overrides: Partial<RawSignalFrame> = {}): RawSignalFrame {
  return {
    deviceId: "test:sim:001",
    frameIndex: 0,
    timestampNs: BigInt(Date.now()) * 1_000_000n,
    signalType: "EEG",
    channels: [new Float32Array([1, 2, 3])],
    samplesPerFrame: 3,
    sampleRateHz: 256,
    channelLabels: ["C3"],
    calibrated: true,
    ...overrides,
  };
}

describe("EventBus", () => {
  it("emits and receives typed events", () => {
    const bus = new EventBus();
    const received: RawSignalFrame[] = [];

    bus.on("signal.frame", (frame) => {
      received.push(frame);
    });

    const frame = makeFrame();
    bus.emit("signal.frame", frame);

    expect(received).toHaveLength(1);
    expect(received[0]).toBe(frame);
  });

  it("supports multiple listeners on the same event", () => {
    const bus = new EventBus();
    const calls: number[] = [];

    bus.on("session.paused", () => calls.push(1));
    bus.on("session.paused", () => calls.push(2));

    bus.emit("session.paused", { sessionId: "s1", timestamp: Date.now() });

    expect(calls).toEqual([1, 2]);
  });

  it("once() fires only once", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    bus.once("session.stopped", fn);

    bus.emit("session.stopped", { sessionId: "s1", totalFrames: 10 });
    bus.emit("session.stopped", { sessionId: "s1", totalFrames: 10 });

    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("off() removes listener", () => {
    const bus = new EventBus();
    const fn = vi.fn();

    bus.on("session.paused", fn);
    bus.off("session.paused", fn);

    bus.emit("session.paused", { sessionId: "s1", timestamp: Date.now() });

    expect(fn).not.toHaveBeenCalled();
  });

  it("emit returns boolean", () => {
    const bus = new EventBus();
    const result = bus.emit("pipeline.latency_warning", { latencyMs: 25 });
    expect(typeof result).toBe("boolean");
  });
});
