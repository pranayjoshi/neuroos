import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { PipelineOrchestrator } from "../src/pipeline/pipeline_orchestrator.js";
import { DeviceRegistry } from "../src/registry/device_registry.js";
import { SimulatorAdapter } from "../src/adapters/simulator_adapter.js";
import { EventBus } from "../src/bus/event_bus.js";
import type { SessionMetadata } from "@neuroos/shared-contracts/schema";

const defaultConfig = {
  sampleRateHz: 256,
  numChannels: 4,
  channelLabels: null,
  samplesPerFrame: 16,
  hardwareFilter: false,
  driverOptions: {},
};

function makeSession(deviceInfo: { deviceId: string; [k: string]: unknown }): SessionMetadata {
  return {
    sessionId: "test-session-01",
    sessionName: "test",
    subjectId: "sub-001",
    state: "active",
    startedAtMs: Date.now(),
    endedAtMs: null,
    totalFrames: 0,
    droppedFrames: 0,
    deviceInfo: {
      deviceId: deviceInfo.deviceId as string,
      vendor: "NeuroOS",
      model: "Simulator",
      firmwareVersion: "1.0.0",
      numChannels: 4,
      sampleRateHz: 256,
      signalType: "EEG",
      channelLabels: ["C3", "C4", "Cz", "Pz"],
      adResolutionBits: 24,
      referenceElectrode: "average",
    },
    pipelineConfig: {
      dsp: {
        spatialFilterType: "car",
        temporalFilterType: "autoregressive",
        bandpassHz: [1, 40],
        windowLengthSec: 1.0,
        windowStepSec: 0.0625,
      },
      intent: {
        classifierType: "lda",
        modelPath: null,
        inferenceRateHz: 16,
        confidenceThreshold: 0.6,
      },
      paradigm: { type: "motor_imagery", trialLengthSec: 4.0, itiSec: 2.0 },
    },
    notes: "",
    neuroosVersion: "0.1.0",
  };
}

describe("PipelineOrchestrator", () => {
  let orchestrator: PipelineOrchestrator;
  let registry: DeviceRegistry;
  let adapter: SimulatorAdapter;

  beforeEach(() => {
    registry = new DeviceRegistry();
    adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);
    orchestrator = new PipelineOrchestrator(registry);
  });

  afterEach(async () => {
    await orchestrator.stop().catch(() => {});
    await adapter.stopRecording().catch(() => {});
    await adapter.disconnect().catch(() => {});
  });

  it("starts without error", async () => {
    await adapter.connect();
    await adapter.startRecording();
    const session = makeSession({ deviceId: adapter.deviceId });

    await expect(orchestrator.start(session)).resolves.not.toThrow();
  });

  it("getLatencyStats returns zeros initially", () => {
    const stats = orchestrator.getLatencyStats();
    expect(stats.mean).toBe(0);
    expect(stats.max).toBe(0);
  });

  it("pause and resume don't throw", async () => {
    await adapter.connect();
    await adapter.startRecording();
    const session = makeSession({ deviceId: adapter.deviceId });
    await orchestrator.start(session);

    await expect(orchestrator.pause()).resolves.not.toThrow();
    await expect(orchestrator.resume()).resolves.not.toThrow();
  });

  it("stop can be called multiple times safely", async () => {
    await adapter.connect();
    await adapter.startRecording();
    const session = makeSession({ deviceId: adapter.deviceId });
    await orchestrator.start(session);

    await expect(orchestrator.stop()).resolves.not.toThrow();
    await expect(orchestrator.stop()).resolves.not.toThrow();
  });
});
