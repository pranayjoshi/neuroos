import { EventEmitter } from "node:events";
import type {
  DeviceAdapter,
  DeviceAdapterConfig,
  DeviceAdapterEvents,
  DeviceInfo,
  DeviceState,
  DeviceDiagnostics,
  RawSignalFrame,
} from "@neuroos/shared-contracts/schema";

let instanceCount = 0;

export class SimulatorAdapter extends EventEmitter implements DeviceAdapter {
  readonly deviceId: string;
  readonly adapterName = "neuroos-simulator";

  private _state: DeviceState = "disconnected";
  private intervalHandle: NodeJS.Timeout | null = null;
  private frameIndex = 0;
  private config: DeviceAdapterConfig;
  private deviceInfoSnapshot: DeviceInfo | null = null;

  constructor(config: DeviceAdapterConfig) {
    super();
    instanceCount++;
    this.deviceId = `simulator:default:SIM-${String(instanceCount).padStart(3, "0")}`;
    this.config = config;
  }

  get state(): DeviceState {
    return this._state;
  }

  on<K extends keyof DeviceAdapterEvents>(
    event: K,
    listener: DeviceAdapterEvents[K]
  ): this {
    return super.on(event, listener);
  }

  off<K extends keyof DeviceAdapterEvents>(
    event: K,
    listener: DeviceAdapterEvents[K]
  ): this {
    return super.off(event, listener);
  }

  async connect(): Promise<DeviceInfo> {
    this.setState("connecting");

    const channelLabels = this.config.channelLabels ?? this.generateChannelLabels();

    const info: DeviceInfo = {
      deviceId: this.deviceId,
      vendor: "NeuroOS",
      model: "Simulator",
      firmwareVersion: "1.0.0",
      numChannels: this.config.numChannels,
      sampleRateHz: this.config.sampleRateHz,
      signalType: "EEG",
      channelLabels,
      adResolutionBits: 24,
      referenceElectrode: "average",
    };

    this.deviceInfoSnapshot = info;
    this.setState("connected");

    this.emit("deviceInfo", info);
    return info;
  }

  async startRecording(): Promise<void> {
    if (this._state !== "connected" && this._state !== "paused") {
      throw new Error(`Cannot start recording from state: ${this._state}`);
    }

    this.setState("recording");

    const frameIntervalMs = (this.config.samplesPerFrame / this.config.sampleRateHz) * 1000;

    this.intervalHandle = setInterval(() => {
      this.emitFrame();
    }, frameIntervalMs);
  }

  async pauseRecording(): Promise<void> {
    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }
    this.setState("paused");
  }

  async stopRecording(): Promise<void> {
    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }
    this.setState("connected");
  }

  async disconnect(): Promise<void> {
    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }
    this.setState("disconnected");
    this.frameIndex = 0;
  }

  async getDiagnostics(): Promise<DeviceDiagnostics> {
    return {
      impedanceKOhm: new Array(this.config.numChannels).fill(5),
      batteryPercent: null,
      signalQuality: new Array(this.config.numChannels).fill(0.95),
      droppedFrames: 0,
      timestampMs: Date.now(),
    };
  }

  private emitFrame(): void {
    const numChannels = this.config.numChannels;
    const samplesPerFrame = this.config.samplesPerFrame;
    const channelLabels = this.deviceInfoSnapshot?.channelLabels ?? this.generateChannelLabels();

    const channels: Float32Array[] = Array.from({ length: numChannels }, () => {
      const samples = new Float32Array(samplesPerFrame);
      for (let i = 0; i < samplesPerFrame; i++) {
        samples[i] = (Math.random() - 0.5) * 50;
      }
      return samples;
    });

    const frame: RawSignalFrame = {
      deviceId: this.deviceId,
      frameIndex: this.frameIndex++,
      timestampNs: BigInt(Date.now()) * 1_000_000n,
      signalType: "EEG",
      channels,
      samplesPerFrame,
      sampleRateHz: this.config.sampleRateHz,
      channelLabels,
      calibrated: true,
    };

    this.emit("frame", frame);
  }

  private setState(newState: DeviceState): void {
    const prev = this._state;
    this._state = newState;
    this.emit("stateChange", newState, prev);
  }

  private generateChannelLabels(): string[] {
    const labels = ["Fp1","Fp2","F7","F3","Fz","F4","F8","T3",
                    "C3","Cz","C4","T4","P3","Pz","P4","O1"];
    return labels.slice(0, this.config.numChannels);
  }
}
