import { EventEmitter } from "node:events";
import type {
  RawSignalFrame,
  FeatureVector,
  IntentEvent,
  SessionMetadata,
  DeviceInfo,
  DeviceAdapterError,
} from "@neuroos/shared-contracts/schema";

export type EventMap = {
  "signal.frame": RawSignalFrame;
  "dsp.features": FeatureVector;
  "intent.event": IntentEvent;
  "session.started": SessionMetadata;
  "session.paused": { sessionId: string; timestamp: number };
  "session.resumed": { sessionId: string; timestamp: number };
  "session.stopped": { sessionId: string; totalFrames: number };
  "device.connected": DeviceInfo;
  "device.error": DeviceAdapterError;
  "pipeline.latency_warning": { latencyMs: number; frameIndex?: number };
  "pipeline.error": { message: string; code: string };
};

export class EventBus extends EventEmitter {
  emit<K extends keyof EventMap>(event: K, data: EventMap[K]): boolean {
    return super.emit(event, data);
  }

  on<K extends keyof EventMap>(
    event: K,
    listener: (data: EventMap[K]) => void
  ): this {
    return super.on(event, listener);
  }

  once<K extends keyof EventMap>(
    event: K,
    listener: (data: EventMap[K]) => void
  ): this {
    return super.once(event, listener);
  }

  off<K extends keyof EventMap>(
    event: K,
    listener: (data: EventMap[K]) => void
  ): this {
    return super.off(event, listener);
  }
}

export const globalEventBus = new EventBus();
