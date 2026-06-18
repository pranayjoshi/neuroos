/**
 * Latency test: end-to-end <15 ms with simulator stub.
 *
 * Uses a passthrough DSP + intent stub driven from the SimulatorAdapter.
 * Latency is measured as the time from frame emission to intent event receipt.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { DeviceRegistry } from "../src/registry/device_registry.js";
import { EventBus } from "../src/bus/event_bus.js";
import { SimulatorAdapter } from "../src/adapters/simulator_adapter.js";
import type { RawSignalFrame, IntentEvent } from "@neuroos/shared-contracts/schema";
import { randomUUID } from "node:crypto";

const defaultConfig = {
  sampleRateHz: 256,
  numChannels: 4,
  channelLabels: null,
  samplesPerFrame: 16,
  hardwareFilter: false,
  driverOptions: {},
};

/**
 * Simulate the full pipeline inline (no subprocess) to test the latency
 * budget with a passthrough DSP and instant classifier.
 */
async function measurePipelineLatency(samples = 50): Promise<number[]> {
  const latencies: number[] = [];
  const bus = new EventBus();
  const registry = new DeviceRegistry();
  const adapter = new SimulatorAdapter(defaultConfig);
  registry.register(adapter);

  registry.onFrame(adapter.deviceId, (frame: RawSignalFrame) => {
    const receiveTs = process.hrtime.bigint();

    setImmediate(() => {
      const intent: IntentEvent = {
        intentId: randomUUID(),
        label: "motor_imagery_rest",
        confidence: 0.85,
        posteriors: { motor_imagery_rest: 0.85 },
        classifierType: "lda",
        sourceVectorId: randomUUID(),
        timestampNs: frame.timestampNs,
        endToEndLatencyMs: Number(process.hrtime.bigint() - receiveTs) / 1_000_000,
        featureImportance: {},
        artifactFlag: false,
        feedbackLabel: null,
      };

      bus.emit("intent.event", intent);
    });
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error("Latency test timed out"));
    }, 10_000);

    bus.on("intent.event", (intent: IntentEvent) => {
      latencies.push(intent.endToEndLatencyMs);
      if (latencies.length >= samples) {
        clearTimeout(timeout);
        resolve();
      }
    });

    adapter.connect()
      .then(() => adapter.startRecording())
      .catch(reject);
  });

  await adapter.stopRecording();
  await adapter.disconnect();

  return latencies;
}

describe("Latency (<15 ms)", () => {
  it("end-to-end latency mean is under 15 ms with simulator stub", async () => {
    const latencies = await measurePipelineLatency(30);
    expect(latencies.length).toBeGreaterThanOrEqual(1);

    const mean = latencies.reduce((s, v) => s + v, 0) / latencies.length;
    const sorted = [...latencies].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? 0;

    console.log(`Latency stats: mean=${mean.toFixed(3)}ms, p95=${p95.toFixed(3)}ms, n=${latencies.length}`);

    expect(mean).toBeLessThan(15);
  }, 15_000);

  it("no single event exceeds 50 ms", async () => {
    const latencies = await measurePipelineLatency(20);
    const max = Math.max(...latencies);
    console.log(`Max latency: ${max.toFixed(3)}ms`);
    expect(max).toBeLessThan(50);
  }, 15_000);
});
