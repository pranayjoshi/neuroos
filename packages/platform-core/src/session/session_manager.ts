import { randomUUID } from "node:crypto";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { homedir } from "node:os";
import type {
  SessionMetadata,
  PipelineConfig,
  DeviceInfo,
} from "@neuroos/shared-contracts/schema";
import { globalEventBus } from "../bus/event_bus.js";
import { globalDeviceRegistry, DeviceRegistry } from "../registry/device_registry.js";
import { createLogger } from "../logger.js";

const logger = createLogger("SessionManager");

const NEUROOS_VERSION = "0.1.0";

function resolveDir(dir: string): string {
  if (dir.startsWith("~")) {
    return join(homedir(), dir.slice(1));
  }
  return resolve(dir);
}

export class SessionManager {
  private sessions = new Map<string, SessionMetadata>();
  private activeSessionId: string | null = null;
  private sessionsDir: string;
  private registry: DeviceRegistry;

  constructor(sessionsDir = "~/.neuroos/sessions", registry?: DeviceRegistry) {
    this.sessionsDir = resolveDir(sessionsDir);
    this.registry = registry ?? globalDeviceRegistry;
  }

  async startSession(params: {
    deviceId: string;
    subjectId: string;
    sessionName: string;
    paradigm: PipelineConfig["paradigm"]["type"];
  }): Promise<SessionMetadata> {
    if (this.activeSessionId !== null) {
      throw new Error(
        `SESSION_ALREADY_ACTIVE: Session "${this.activeSessionId}" is already running. Stop it first.`
      );
    }

    const adapter = this.registry.getAdapter(params.deviceId);
    if (!adapter) {
      throw new Error(`DEVICE_NOT_FOUND: No device registered with id: ${params.deviceId}`);
    }

    const deviceInfo: DeviceInfo = await adapter.connect();

    const pipelineConfig: PipelineConfig = {
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
      paradigm: {
        type: params.paradigm,
        trialLengthSec: 4.0,
        itiSec: 2.0,
      },
    };

    const session: SessionMetadata = {
      sessionId: randomUUID(),
      sessionName: params.sessionName,
      subjectId: params.subjectId,
      state: "active",
      startedAtMs: Date.now(),
      endedAtMs: null,
      totalFrames: 0,
      droppedFrames: 0,
      deviceInfo,
      pipelineConfig,
      notes: "",
      neuroosVersion: NEUROOS_VERSION,
    };

    this.sessions.set(session.sessionId, session);
    this.activeSessionId = session.sessionId;

    await adapter.startRecording();

    this.registry.onFrame(params.deviceId, () => {
      const s = this.sessions.get(session.sessionId);
      if (s && s.state === "active") {
        s.totalFrames++;
      }
    });

    await this.persistSession(session);
    globalEventBus.emit("session.started", session);

    logger.info(`Session started: ${session.sessionId}`);
    return session;
  }

  async pauseSession(sessionId: string): Promise<void> {
    const session = this.getSessionOrThrow(sessionId);

    if (session.state !== "active") {
      throw new Error(`Session "${sessionId}" is not active (state: ${session.state})`);
    }

    const adapter = this.registry.getAdapter(session.deviceInfo.deviceId);
    if (adapter) {
      await adapter.pauseRecording();
    }

    session.state = "paused";
    await this.persistSession(session);
    globalEventBus.emit("session.paused", { sessionId, timestamp: Date.now() });

    logger.info(`Session paused: ${sessionId}`);
  }

  async resumeSession(sessionId: string): Promise<void> {
    const session = this.getSessionOrThrow(sessionId);

    if (session.state !== "paused") {
      throw new Error(`Session "${sessionId}" is not paused (state: ${session.state})`);
    }

    const adapter = this.registry.getAdapter(session.deviceInfo.deviceId);
    if (adapter) {
      await adapter.startRecording();
    }

    session.state = "active";
    await this.persistSession(session);
    globalEventBus.emit("session.resumed", { sessionId, timestamp: Date.now() });

    logger.info(`Session resumed: ${sessionId}`);
  }

  async stopSession(sessionId: string): Promise<SessionMetadata> {
    const session = this.getSessionOrThrow(sessionId);

    if (session.state === "completed") {
      throw new Error(`Session "${sessionId}" is already completed.`);
    }

    const adapter = this.registry.getAdapter(session.deviceInfo.deviceId);
    if (adapter) {
      await adapter.stopRecording();
      await adapter.disconnect();
    }

    session.state = "completed";
    session.endedAtMs = Date.now();

    if (this.activeSessionId === sessionId) {
      this.activeSessionId = null;
    }

    await this.persistSession(session);
    globalEventBus.emit("session.stopped", {
      sessionId,
      totalFrames: session.totalFrames,
    });

    logger.info(`Session stopped: ${sessionId} (${session.totalFrames} frames)`);
    return session;
  }

  getActiveSession(): SessionMetadata | null {
    if (this.activeSessionId === null) return null;
    return this.sessions.get(this.activeSessionId) ?? null;
  }

  getSession(sessionId: string): SessionMetadata | undefined {
    return this.sessions.get(sessionId);
  }

  listSessions(): SessionMetadata[] {
    return Array.from(this.sessions.values());
  }

  private getSessionOrThrow(sessionId: string): SessionMetadata {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error(`SESSION_NOT_FOUND: No session with id: ${sessionId}`);
    }
    return session;
  }

  private async persistSession(session: SessionMetadata): Promise<void> {
    const dir = join(this.sessionsDir, session.sessionId);

    if (!existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }

    const serializable = {
      ...session,
      deviceInfo: {
        ...session.deviceInfo,
      },
    };

    await writeFile(
      join(dir, "metadata.json"),
      JSON.stringify(serializable, null, 2),
      "utf-8"
    );
  }

  async loadPersistedSessions(): Promise<void> {
    try {
      const { readdir } = await import("node:fs/promises");
      if (!existsSync(this.sessionsDir)) return;

      const entries = await readdir(this.sessionsDir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        const metaPath = join(this.sessionsDir, entry.name, "metadata.json");
        try {
          const raw = await readFile(metaPath, "utf-8");
          const session = JSON.parse(raw) as SessionMetadata;
          this.sessions.set(session.sessionId, session);
        } catch {
          // skip malformed sessions
        }
      }
    } catch {
      // sessions dir may not exist on first run
    }
  }
}

export const globalSessionManager = new SessionManager();
