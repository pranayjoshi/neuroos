import type {
  DeviceAdapter,
  DeviceState,
  RawSignalFrame,
} from "@neuroos/shared-contracts/schema";
import { globalEventBus } from "../bus/event_bus.js";
import { createLogger } from "../logger.js";

const logger = createLogger("DeviceRegistry");

function isDeviceAdapter(obj: unknown): obj is DeviceAdapter {
  if (typeof obj !== "object" || obj === null) return false;
  const o = obj as Record<string, unknown>;
  return (
    typeof o["deviceId"] === "string" &&
    typeof o["adapterName"] === "string" &&
    typeof o["state"] === "string" &&
    typeof o["on"] === "function" &&
    typeof o["off"] === "function" &&
    typeof o["connect"] === "function" &&
    typeof o["startRecording"] === "function" &&
    typeof o["pauseRecording"] === "function" &&
    typeof o["stopRecording"] === "function" &&
    typeof o["disconnect"] === "function" &&
    typeof o["getDiagnostics"] === "function"
  );
}

export class DeviceRegistry {
  private adapters = new Map<string, DeviceAdapter>();
  private frameHandlers = new Map<string, Set<(frame: RawSignalFrame) => void>>();
  private adapterFrameListeners = new Map<string, (frame: RawSignalFrame) => void>();

  register(adapter: DeviceAdapter): void {
    if (!isDeviceAdapter(adapter)) {
      throw new TypeError(
        `Adapter does not implement the DeviceAdapter interface. ` +
          `Required properties: deviceId, adapterName, state, on, off, connect, ` +
          `startRecording, pauseRecording, stopRecording, disconnect, getDiagnostics.`
      );
    }

    if (this.adapters.has(adapter.deviceId)) {
      throw new Error(
        `Device "${adapter.deviceId}" is already registered. Unregister it first.`
      );
    }

    this.adapters.set(adapter.deviceId, adapter);
    this.frameHandlers.set(adapter.deviceId, new Set());

    const frameListener = (frame: RawSignalFrame) => {
      globalEventBus.emit("signal.frame", frame);
      const handlers = this.frameHandlers.get(adapter.deviceId);
      if (handlers) {
        for (const handler of handlers) {
          handler(frame);
        }
      }
    };

    this.adapterFrameListeners.set(adapter.deviceId, frameListener);
    adapter.on("frame", frameListener);

    adapter.on("deviceInfo", (info) => {
      globalEventBus.emit("device.connected", info);
    });

    adapter.on("error", (err) => {
      globalEventBus.emit("device.error", err);
    });

    logger.info(`Registered adapter: ${adapter.adapterName} (${adapter.deviceId})`);
  }

  unregister(deviceId: string): void {
    const adapter = this.adapters.get(deviceId);
    if (!adapter) {
      throw new Error(`No device registered with id: ${deviceId}`);
    }

    const frameListener = this.adapterFrameListeners.get(deviceId);
    if (frameListener) {
      adapter.off("frame", frameListener);
      this.adapterFrameListeners.delete(deviceId);
    }

    this.adapters.delete(deviceId);
    this.frameHandlers.delete(deviceId);

    logger.info(`Unregistered adapter: ${deviceId}`);
  }

  getAdapter(deviceId: string): DeviceAdapter | undefined {
    return this.adapters.get(deviceId);
  }

  listAdapters(): Array<{ deviceId: string; adapterName: string; state: DeviceState }> {
    return Array.from(this.adapters.values()).map((a) => ({
      deviceId: a.deviceId,
      adapterName: a.adapterName,
      state: a.state,
    }));
  }

  onFrame(
    deviceId: string,
    handler: (frame: RawSignalFrame) => void
  ): () => void {
    const handlers = this.frameHandlers.get(deviceId);
    if (!handlers) {
      throw new Error(`No device registered with id: ${deviceId}`);
    }

    handlers.add(handler);

    return () => {
      handlers.delete(handler);
    };
  }
}

export const globalDeviceRegistry = new DeviceRegistry();
