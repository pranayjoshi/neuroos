import type { IntentEvent } from "./types.js";
import {
  ConnectionError,
  mapHttpError,
  NeuroOSError,
  TimeoutError,
} from "./errors.js";

export interface HttpClientOptions {
  baseUrl: string;
  timeout: number;
}

export class HttpClient {
  constructor(private readonly options: HttpClientOptions) {}

  get baseUrl(): string {
    return this.options.baseUrl;
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.options.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.options.timeout);

    try {
      const init: RequestInit = {
        method,
        signal: controller.signal,
      };
      if (body !== undefined) {
        init.headers = { "Content-Type": "application/json" };
        init.body = JSON.stringify(body);
      }

      const response = await fetch(url, init);

      const text = await response.text();
      const parsed = text ? (JSON.parse(text) as Record<string, unknown>) : {};

      if (!response.ok) {
        throw mapHttpError(response.status, parsed as { error?: string; message?: string }, this.options.baseUrl);
      }

      return parsed as T;
    } catch (err) {
      if (err instanceof NeuroOSError) {
        throw err;
      }
      if (err instanceof Error && err.name === "AbortError") {
        throw new TimeoutError(this.options.timeout);
      }
      throw new ConnectionError(this.options.baseUrl, err);
    } finally {
      clearTimeout(timer);
    }
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }
}

export function parseIntentEvent(raw: Record<string, unknown>): IntentEvent {
  return {
    intentId: String(raw["intentId"]),
    label: raw["label"] as IntentEvent["label"],
    confidence: Number(raw["confidence"]),
    posteriors: (raw["posteriors"] ?? {}) as IntentEvent["posteriors"],
    classifierType: raw["classifierType"] as IntentEvent["classifierType"],
    sourceVectorId: String(raw["sourceVectorId"]),
    timestampNs: BigInt(String(raw["timestampNs"])),
    endToEndLatencyMs: Number(raw["endToEndLatencyMs"]),
    featureImportance: (raw["featureImportance"] ?? {}) as IntentEvent["featureImportance"],
    artifactFlag: Boolean(raw["artifactFlag"]),
    feedbackLabel: (raw["feedbackLabel"] ?? null) as IntentEvent["feedbackLabel"],
  };
}

export function toWebSocketUrl(baseUrl: string, path: string): string {
  const url = new URL(baseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = path;
  url.search = "";
  url.hash = "";
  return url.toString();
}
