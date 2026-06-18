import { HttpClient } from "./http.js";
import { IntentStream } from "./stream.js";
import type {
  DeviceDiagnostics,
  DeviceInfo,
  DeviceListItem,
  DeviceState,
  DiagnosticsResponse,
  ListDevicesResponse,
  NeuroOSClientConfig,
  PartialDeviceAdapterConfig,
  RegisterDeviceResponse,
  SessionMetadata,
  SessionStartParams,
} from "./types.js";

const DEFAULT_BASE_URL = "http://localhost:3000";
const DEFAULT_TIMEOUT = 5000;

export class NeuroOS {
  private readonly http: HttpClient;
  private readonly config: Required<
    Pick<NeuroOSClientConfig, "baseUrl" | "timeout" | "reconnect" | "reconnectDelayMs">
  >;
  private activeStream: IntentStream | null = null;

  readonly devices: DevicesAPI;
  readonly sessions: SessionsAPI;
  readonly intents: IntentsAPI;
  readonly operator: OperatorAPI;

  constructor(config?: NeuroOSClientConfig) {
    this.config = {
      baseUrl: config?.baseUrl ?? DEFAULT_BASE_URL,
      timeout: config?.timeout ?? DEFAULT_TIMEOUT,
      reconnect: config?.reconnect ?? true,
      reconnectDelayMs: config?.reconnectDelayMs ?? 1000,
    };

    this.http = new HttpClient({
      baseUrl: this.config.baseUrl,
      timeout: this.config.timeout,
    });

    this.devices = new DevicesAPI(this.http);
    this.sessions = new SessionsAPI(this.http);
    this.intents = new IntentsAPI(this);
    this.operator = new OperatorAPI(this.http);
  }

  get baseUrl(): string {
    return this.config.baseUrl;
  }

  async connect(): Promise<void> {
    await this.http.get<{ status: string }>("/health");
  }

  async disconnect(): Promise<void> {
    if (this.activeStream) {
      await this.activeStream.close();
      this.activeStream = null;
    }
  }

  async startSession(params: SessionStartParams): Promise<SessionMetadata> {
    return this.sessions.start(params);
  }

  async stopSession(sessionId: string): Promise<SessionMetadata> {
    return this.sessions.stop(sessionId);
  }

  _createStream(): IntentStream {
    if (this.activeStream) {
      void this.activeStream.close();
    }
    const stream = new IntentStream({
      baseUrl: this.config.baseUrl,
      reconnect: this.config.reconnect,
      reconnectDelayMs: this.config.reconnectDelayMs,
    });
    this.activeStream = stream;
    return stream;
  }
}

/** Alias for NeuroOS — matches simplified client naming. */
export { NeuroOS as NeuroOSClient };

class DevicesAPI {
  constructor(private readonly http: HttpClient) {}

  async register(
    adapterName: string,
    config?: PartialDeviceAdapterConfig,
  ): Promise<DeviceInfo & { state: DeviceState }> {
    const response = await this.http.post<RegisterDeviceResponse>("/devices/register", {
      adapterName,
      config,
    });
    return {
      deviceId: response.deviceId,
      state: response.state,
      vendor: "NeuroOS",
      model: adapterName,
      firmwareVersion: "0.1.0",
      numChannels: config?.numChannels ?? 16,
      sampleRateHz: config?.sampleRateHz ?? 256,
      signalType: "EEG",
      channelLabels: config?.channelLabels ?? [],
      adResolutionBits: 24,
      referenceElectrode: "average",
    };
  }

  async unregister(_deviceId: string): Promise<void> {
    throw new Error("Device unregister is not supported by Platform Core yet.");
  }

  async list(): Promise<DeviceListItem[]> {
    const response = await this.http.get<ListDevicesResponse>("/devices");
    return response.devices;
  }

  async getDiagnostics(deviceId: string): Promise<DeviceDiagnostics> {
    const diagnostics = await this.http.get<DiagnosticsResponse>("/operator/diagnostics");
    if (diagnostics.device.deviceId !== deviceId) {
      const listed = await this.list();
      if (!listed.some((d) => d.deviceId === deviceId)) {
        const { DeviceNotFoundError } = await import("./errors.js");
        throw new DeviceNotFoundError(deviceId);
      }
    }
    return (
      diagnostics.device.diagnostics ?? {
        impedanceKOhm: [],
        batteryPercent: null,
        signalQuality: [],
        droppedFrames: 0,
        timestampMs: Date.now(),
      }
    );
  }
}

class SessionsAPI {
  constructor(private readonly http: HttpClient) {}

  async start(params: SessionStartParams): Promise<SessionMetadata> {
    return this.http.post<SessionMetadata>("/sessions/start", params);
  }

  async stop(sessionId: string): Promise<SessionMetadata> {
    return this.http.post<SessionMetadata>(`/sessions/${sessionId}/stop`);
  }

  async pause(sessionId: string): Promise<void> {
    await this.http.post<{ ok: boolean }>(`/sessions/${sessionId}/pause`);
  }

  async resume(sessionId: string): Promise<void> {
    await this.http.post<{ ok: boolean }>(`/sessions/${sessionId}/resume`);
  }

  async list(): Promise<SessionMetadata[]> {
    const response = await this.http.get<{ sessions: SessionMetadata[] }>("/sessions");
    return response.sessions;
  }

  async get(sessionId: string): Promise<SessionMetadata> {
    const sessions = await this.list();
    const session = sessions.find((item) => item.sessionId === sessionId);
    if (!session) {
      const { NeuroOSError } = await import("./errors.js");
      throw new NeuroOSError("UNKNOWN", `Session not found: ${sessionId}`);
    }
    return session;
  }
}

class IntentsAPI {
  constructor(private readonly client: NeuroOS) {}

  stream(): IntentStream {
    return this.client._createStream();
  }
}

class OperatorAPI {
  constructor(private readonly http: HttpClient) {}

  async getDiagnostics(): Promise<DiagnosticsResponse> {
    return this.http.get<DiagnosticsResponse>("/operator/diagnostics");
  }

  async getSignal(seconds = 5): Promise<{ frames: unknown[] }> {
    return this.http.get<{ frames: unknown[] }>(`/operator/signal?seconds=${seconds}`);
  }
}
