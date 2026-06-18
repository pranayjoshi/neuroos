export type NeuroOSErrorCode =
  | "CONNECTION_FAILED"
  | "SESSION_ALREADY_ACTIVE"
  | "NO_ACTIVE_SESSION"
  | "DEVICE_NOT_FOUND"
  | "STREAM_CLOSED"
  | "VALIDATION_ERROR"
  | "TIMEOUT"
  | "UNKNOWN";

export class NeuroOSError extends Error {
  constructor(
    public readonly code: NeuroOSErrorCode,
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "NeuroOSError";
  }
}

export class ConnectionError extends NeuroOSError {
  constructor(baseUrl: string, cause?: unknown) {
    super(
      "CONNECTION_FAILED",
      `Could not connect to NeuroOS Platform Core at ${baseUrl}. ` +
        "Make sure the platform is running: npx neuroos start",
      cause,
    );
    this.name = "ConnectionError";
  }
}

export class SessionAlreadyActiveError extends NeuroOSError {
  constructor() {
    super(
      "SESSION_ALREADY_ACTIVE",
      "A session is already running. Stop it before starting a new one.",
    );
    this.name = "SessionAlreadyActiveError";
  }
}

export class NoActiveSessionError extends NeuroOSError {
  constructor() {
    super(
      "NO_ACTIVE_SESSION",
      "No active session. Start a session before streaming intents.",
    );
    this.name = "NoActiveSessionError";
  }
}

export class DeviceNotFoundError extends NeuroOSError {
  constructor(deviceId: string) {
    super("DEVICE_NOT_FOUND", `Device not found: ${deviceId}`);
    this.name = "DeviceNotFoundError";
  }
}

export class StreamClosedError extends NeuroOSError {
  constructor(cause?: unknown) {
    super("STREAM_CLOSED", "Intent stream was closed unexpectedly.", cause);
    this.name = "StreamClosedError";
  }
}

export class ValidationError extends NeuroOSError {
  constructor(message: string, cause?: unknown) {
    super("VALIDATION_ERROR", message, cause);
    this.name = "ValidationError";
  }
}

export class TimeoutError extends NeuroOSError {
  constructor(timeoutMs: number) {
    super("TIMEOUT", `Request exceeded timeout of ${timeoutMs}ms.`);
    this.name = "TimeoutError";
  }
}

export function mapHttpError(
  status: number,
  body: { error?: string; message?: string },
  baseUrl: string,
): NeuroOSError {
  const message = body.message ?? body.error ?? `HTTP ${status}`;

  switch (status) {
    case 404:
      if (body.error === "DEVICE_NOT_FOUND") {
        return new DeviceNotFoundError(message);
      }
      return new NeuroOSError("UNKNOWN", message);
    case 409:
      if (body.error === "SESSION_ALREADY_ACTIVE") {
        return new SessionAlreadyActiveError();
      }
      return new NeuroOSError("UNKNOWN", message);
    case 422:
      return new ValidationError(message);
    default:
      if (status === 0 || status >= 500) {
        return new ConnectionError(baseUrl);
      }
      return new NeuroOSError("UNKNOWN", message);
  }
}
