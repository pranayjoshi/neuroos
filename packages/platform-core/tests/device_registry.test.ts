import { describe, it, expect, beforeEach } from "vitest";
import { DeviceRegistry } from "../src/registry/device_registry.js";
import { SimulatorAdapter } from "../src/adapters/simulator_adapter.js";
import type { DeviceAdapter } from "@neuroos/shared-contracts/schema";

const defaultConfig = {
  sampleRateHz: 256,
  numChannels: 8,
  channelLabels: null,
  samplesPerFrame: 16,
  hardwareFilter: false,
  driverOptions: {},
};

describe("DeviceRegistry", () => {
  let registry: DeviceRegistry;

  beforeEach(() => {
    registry = new DeviceRegistry();
  });

  it("registers a valid adapter", () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    expect(() => registry.register(adapter)).not.toThrow();
    expect(registry.listAdapters()).toHaveLength(1);
  });

  it("throws on duplicate deviceId", () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);
    expect(() => registry.register(adapter)).toThrow(/already registered/);
  });

  it("throws when object does not implement DeviceAdapter interface", () => {
    const invalid = { deviceId: "x", adapterName: "bad" } as unknown as DeviceAdapter;
    expect(() => registry.register(invalid)).toThrow(/DeviceAdapter interface/);
  });

  it("unregisters an adapter", () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);
    registry.unregister(adapter.deviceId);
    expect(registry.listAdapters()).toHaveLength(0);
  });

  it("throws when unregistering unknown deviceId", () => {
    expect(() => registry.unregister("nonexistent")).toThrow(/No device registered/);
  });

  it("getAdapter returns undefined for unknown id", () => {
    expect(registry.getAdapter("unknown")).toBeUndefined();
  });

  it("getAdapter returns the adapter after registration", () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);
    expect(registry.getAdapter(adapter.deviceId)).toBe(adapter);
  });

  it("listAdapters returns deviceId, adapterName and state", () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);
    const list = registry.listAdapters();
    expect(list[0]).toMatchObject({
      deviceId: adapter.deviceId,
      adapterName: "neuroos-simulator",
      state: "disconnected",
    });
  });

  it("onFrame subscribes to frame events", async () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);

    const received: unknown[] = [];
    registry.onFrame(adapter.deviceId, (frame) => received.push(frame));

    await adapter.connect();
    await adapter.startRecording();

    await new Promise((r) => setTimeout(r, 100));
    await adapter.stopRecording();
    await adapter.disconnect();

    expect(received.length).toBeGreaterThan(0);
  });

  it("onFrame unsubscribe stops receiving frames", async () => {
    const adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);

    const received: unknown[] = [];
    const unsub = registry.onFrame(adapter.deviceId, (frame) => received.push(frame));

    await adapter.connect();
    await adapter.startRecording();
    await new Promise((r) => setTimeout(r, 80));
    const countBefore = received.length;
    unsub();
    await new Promise((r) => setTimeout(r, 80));
    await adapter.stopRecording();
    await adapter.disconnect();

    expect(received.length).toBe(countBefore);
  });

  it("onFrame throws for unknown deviceId", () => {
    expect(() => registry.onFrame("nonexistent", () => {})).toThrow(/No device registered/);
  });
});
